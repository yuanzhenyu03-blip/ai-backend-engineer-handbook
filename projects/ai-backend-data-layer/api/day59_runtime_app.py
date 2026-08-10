"""Day59 — local-only real FastAPI runtime composition (INTEGRATION_RUNTIME seam).

This module composes the EXISTING Day47 async engine / session-factory boundaries with
FastAPI so the Day43–Day58 acceptance CONTRACT can be exercised as bounded, reviewable
LOCAL integration evidence: a real Uvicorn process against a real PostgreSQL with real
Alembic migrations. It is a COMPOSITION layer — it does not re-implement Day46 mapping,
Day47 Unit of Work, or Day48 migrations.

STRICT BOUNDARIES (do not relax):
  * The HTTP acceptance transaction NEVER calls a Broker, Celery Worker, Provider, or
    Object Storage. It commits durable acceptance facts and persists ONE
    ``job.dispatch_requested`` Outbox intent for a LATER Relay (Day60) to deliver.
  * The disposable local database URL is read from the ``DAY59_DATABASE_URL`` env var
    ONLY. No URL, password, token, or tenant fixture value is hardcoded here.
  * The ``X-Integration-Tenant`` seam exists ONLY when ``DAY59_INTEGRATION_TEST=1`` AND
    the target host is loopback. It is NOT production authentication and MUST NEVER be
    used as a client-supplied tenant authority. Production identity remains Day51 JWT +
    Day52 active-membership/role authorization.
  * Readiness ( ``/readyz`` ) requires BOTH database connectivity AND the expected
    Alembic revision. A ready process on the WRONG revision returns 503 — it must not
    silently accept traffic.

Evidence tier: running this under Uvicorn + PostgreSQL + Alembic is INTEGRATION_RUNTIME
and was executed in a DISPOSABLE local environment during the Day59 class. The updating
repository agent re-ran only ``py_compile`` and the standard-library
``test_day59_acceptance_logic.py`` suite; it did NOT re-run the Docker/PostgreSQL
integration. See the design/runbook for the exact commands and NOT RUN limits.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from day47_async_uow import create_engine, create_session_factory
from day59_acceptance_logic import (
    IdempotencyDecision,
    Readiness,
    classify_idempotency,
    compute_request_fingerprint,
    evaluate_readiness,
)

# The API build declares the schema revision it REQUIRES. Readiness fails if the live
# database is not exactly at this revision.
EXPECTED_ALEMBIC_REVISION = "0008_day59_acceptance"
DISPATCH_EVENT_TYPE = "job.dispatch_requested"


def _database_url() -> str:
    url = os.environ.get("DAY59_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Day59 local integration requires DAY59_DATABASE_URL (a disposable local "
            "async PostgreSQL URL, e.g. postgresql+asyncpg://USER:PASS@127.0.0.1:5432/DB). "
            "No credential is hardcoded in the repository."
        )
    return url


def _integration_seam_enabled(url: str) -> bool:
    """The X-Integration-Tenant seam is allowed ONLY in explicit local test mode and
    ONLY when the database host is loopback. Otherwise it is disabled entirely."""
    if os.environ.get("DAY59_INTEGRATION_TEST") != "1":
        return False
    host = (urlparse(url.replace("+asyncpg", "")).hostname or "").lower()
    return host in {"127.0.0.1", "::1", "localhost"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = _database_url()
    engine = create_engine(url)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.integration_seam = _integration_seam_enabled(url)
    try:
        yield
    finally:
        # Lifespan owns engine disposal; the app never self-runs migrations on startup.
        await engine.dispose()


app = FastAPI(title="Day59 Local Runtime (integration seam)", lifespan=lifespan)


class JobAcceptRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=200)
    document_ids: list[str] = Field(default_factory=list)
    business_input: dict[str, Any] = Field(default_factory=dict)


def _resolve_tenant(
    app: FastAPI, x_integration_tenant: Optional[str]
) -> str:
    """Resolve the authenticated tenant.

    The header seam is honored ONLY when the local integration seam is enabled; it is a
    controlled test authority, never a client-supplied production tenant. Without the
    seam, this route has no production identity system yet (Day51/Day52 own that), so it
    refuses rather than trusting a raw header.
    """
    if getattr(app.state, "integration_seam", False):
        if not x_integration_tenant:
            raise HTTPException(status_code=401, detail="missing integration tenant")
        return x_integration_tenant
    raise HTTPException(
        status_code=401,
        detail="production identity (Day51 JWT + Day52 membership) is not part of Day59",
    )


async def _get_session(app: FastAPI) -> AsyncSession:
    return app.state.session_factory()


@app.get("/livez")
async def livez() -> dict[str, str]:
    # Liveness: the process is up. It says NOTHING about schema readiness.
    return {"status": "alive"}


@app.get("/readyz")
async def readyz(response: Response) -> dict[str, str]:
    db_reachable = True
    current_revision: Optional[str] = None
    try:
        session = app.state.session_factory()
        async with session:
            row = await session.execute(text("SELECT version_num FROM alembic_version"))
            current_revision = row.scalar_one_or_none()
    except Exception:
        db_reachable = False

    result = evaluate_readiness(db_reachable, current_revision, EXPECTED_ALEMBIC_REVISION)
    if result.state is Readiness.NOT_READY:
        response.status_code = 503
        return {"status": "not_ready", "reason": result.reason}
    return {"status": "ready", "revision": EXPECTED_ALEMBIC_REVISION}


@app.post("/v1/jobs", status_code=202)
async def accept_job(
    body: JobAcceptRequest,
    response: Response,
    x_integration_tenant: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant(app, x_integration_tenant)
    fingerprint = compute_request_fingerprint(
        tenant_id, body.idempotency_key, body.business_input
    )

    session = app.state.session_factory()
    async with session:
        # 1) Check durable idempotency facts BEFORE revalidating mutable Document state.
        existing = (
            await session.execute(
                text(
                    "SELECT job_id, request_fingerprint FROM app.jobs "
                    "WHERE tenant_id = :t AND idempotency_key = :k"
                ),
                {"t": tenant_id, "k": body.idempotency_key},
            )
        ).first()

        if existing is not None:
            decision = classify_idempotency(existing.request_fingerprint, fingerprint)
            if decision is IdempotencyDecision.RETURN_ORIGINAL:
                response.status_code = 202
                return {"job_id": str(existing.job_id), "idempotent_replay": True}
            if decision is IdempotencyDecision.CONFLICT_409:
                raise HTTPException(
                    status_code=409,
                    detail="idempotency key reused for a different request",
                )

        # 2) Validate referenced Documents are verified AND owned by this tenant.
        #    A wrong/unverified Document -> 422 and NO acceptance facts are written.
        if body.document_ids:
            verified = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM app.documents "
                        "WHERE tenant_id = :t AND document_id = ANY(:ids) "
                        "AND verified_at IS NOT NULL"
                    ),
                    {"t": tenant_id, "ids": body.document_ids},
                )
            ).scalar_one()
            if verified != len(set(body.document_ids)):
                raise HTTPException(
                    status_code=422, detail="unverified or wrong-tenant document"
                )

        # 3) One SHORT transaction: queued Job + fingerprint + Document links + exactly
        #    one dispatch Outbox intent. No Broker/Worker/Provider/Object-Storage call.
        try:
            async with session.begin():
                job_id = (
                    await session.execute(
                        text(
                            "INSERT INTO app.jobs (tenant_id, idempotency_key, "
                            "request_fingerprint, job_status) "
                            "VALUES (:t, :k, :fp, 'queued') RETURNING job_id"
                        ),
                        {"t": tenant_id, "k": body.idempotency_key, "fp": fingerprint},
                    )
                ).scalar_one()

                for document_id in set(body.document_ids):
                    await session.execute(
                        text(
                            "INSERT INTO app.job_documents (tenant_id, job_id, document_id) "
                            "VALUES (:t, :j, :d)"
                        ),
                        {"t": tenant_id, "j": job_id, "d": document_id},
                    )

                await session.execute(
                    text(
                        "INSERT INTO app.outbox_events (job_id, event_type, payload) "
                        "VALUES (:j, :etype, '{}'::jsonb)"
                    ),
                    {"j": job_id, "etype": DISPATCH_EVENT_TYPE},
                )
        except IntegrityError:
            # A concurrent same-key request won the UNIQUE(tenant_id, idempotency_key)
            # race: return the already-committed Job instead of a second acceptance.
            row = (
                await session.execute(
                    text(
                        "SELECT job_id FROM app.jobs "
                        "WHERE tenant_id = :t AND idempotency_key = :k"
                    ),
                    {"t": tenant_id, "k": body.idempotency_key},
                )
            ).first()
            if row is None:
                raise
            response.status_code = 202
            return {"job_id": str(row.job_id), "idempotent_replay": True}

    return {"job_id": str(job_id), "idempotent_replay": False}


@app.get("/v1/jobs/{job_id}")
async def get_job(
    job_id: str,
    x_integration_tenant: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant(app, x_integration_tenant)
    session = app.state.session_factory()
    async with session:
        row = (
            await session.execute(
                text(
                    "SELECT job_id, job_status FROM app.jobs "
                    "WHERE tenant_id = :t AND job_id = :j"
                ),
                {"t": tenant_id, "j": job_id},
            )
        ).first()
    # Cross-tenant / missing -> 404 with no existence oracle (Day43 read boundary).
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": str(row.job_id), "job_status": row.job_status}
