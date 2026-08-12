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

Acceptance transaction shape (single short Unit of Work; NO autobegin-then-begin):
  A request opens ONE explicit ``async with session.begin()`` and inside it uses
  ``INSERT INTO app.jobs ... ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
  RETURNING job_id`` as the atomic create-or-return (Day43 contract: not
  SELECT-then-INSERT). If a row is returned it is a FRESH acceptance and the same
  transaction validates the referenced Documents (rolling everything back on failure so
  an invalid Document leaves Job=0 / Outbox=0 / link=0) and writes the Job–Document
  links + exactly one dispatch Outbox intent. If NO row is returned the key already has
  a committed Job: re-read its ``request_fingerprint`` and classify — same fingerprint
  is an idempotent replay, a different fingerprint is a 409 — without revalidating
  mutable Document state and without swallowing an unrelated integrity error.

Evidence tier: running this under Uvicorn + PostgreSQL + Alembic is INTEGRATION_RUNTIME.
After the Day59 review fixes (autobegin/ON CONFLICT, real Document verification via
``upload_sessions.session_status='verified'``, ``Idempotency-Key`` header, fingerprint
covering ``document_ids``, conflict re-read) the corrected acceptance path has NOT been
re-run against real PostgreSQL by the updating agent — INTEGRATION_RUNTIME NOT RERUN.
Only ``py_compile`` and the standard-library ``test_day59_acceptance_logic.py`` were
executed. See the design/runbook for the exact commands and NOT RUN limits.
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from day47_async_uow import create_engine, create_session_factory
from day61_telemetry import (
    bootstrap_telemetry,
    inject_trace_context,
    root_span,
    store_traceparent_in_payload,
)
from day59_acceptance_logic import (
    IdempotencyDecision,
    Readiness,
    classify_idempotency,
    compute_request_fingerprint,
    evaluate_readiness,
    has_duplicate_document_ids,
)

# The API build declares the schema revision it REQUIRES. Readiness fails if the live
# database is not exactly at this revision.
# This runtime is reused by the Day60/Day61 execution path.  Readiness must
# require the schema head that supplies the lease/recovery facts used by the
# Worker, rather than reporting an already-upgraded Day61 database as stale.
EXPECTED_ALEMBIC_REVISION = "0012_day60_repair_audit_attestation"
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
    # Real-process telemetry bootstrap (P1-3): idempotent, disabled unless
    # DAY61_TELEMETRY_ENABLED is set; failure degrades to a no-op and never blocks startup.
    bootstrap_telemetry("fastapi-acceptance")
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
    # The idempotency key travels in the `Idempotency-Key` HEADER (Day43 contract), NOT
    # in the body. `document_ids` must have at least one entry — an empty list may not
    # create a Job. Order is preserved (it feeds the request fingerprint).
    document_ids: list[str] = Field(min_length=1)
    business_input: dict[str, Any] = Field(default_factory=dict)


def _resolve_tenant(app: FastAPI, x_integration_tenant: Optional[str]) -> str:
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


async def _all_documents_verified_and_owned(
    session: AsyncSession, tenant_id: str, document_ids: list[str]
) -> bool:
    """A Document is acceptable only if it belongs to this tenant AND its upload session
    is verified. There is NO `documents.verified_at`; verification lives in
    `upload_sessions.session_status = 'verified'` (Day49/Day42 schema). Duplicate ids are
    already rejected (422) before this runs, so the count is compared to the full list."""
    verified = (
        await session.execute(
            text(
                "SELECT count(*) FROM app.documents d "
                "JOIN app.upload_sessions u "
                "  ON u.tenant_id = d.tenant_id "
                " AND u.upload_session_id = d.upload_session_id "
                "WHERE d.tenant_id = :t "
                "  AND d.document_id = ANY(:ids) "
                "  AND u.session_status = 'verified'"
            ),
            {"t": tenant_id, "ids": list(document_ids)},
        )
    ).scalar_one()
    return verified == len(document_ids)


@app.post("/v1/jobs", status_code=202)
async def accept_job(
    body: JobAcceptRequest,
    response: Response,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    x_integration_tenant: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    # Identity first (401 if the seam is disabled or the tenant header is absent).
    tenant_id = _resolve_tenant(app, x_integration_tenant)

    # Contract: an expensive POST without an Idempotency-Key is rejected BEFORE any
    # write (Day43). A missing OR blank header is a 400.
    if idempotency_key is None or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="missing Idempotency-Key header")

    # Duplicate document_ids are a MALFORMED command (they collide on the job_documents
    # PK and make input_order ambiguous). Reject with 422 BEFORE the transaction so no
    # Job / Outbox / links are written. Client order is preserved (never de-duplicated).
    if has_duplicate_document_ids(body.document_ids):
        raise HTTPException(status_code=422, detail="duplicate document_id in request")

    # The fingerprint covers the COMPLETE logical command, including ordered documents.
    # Day50 contract: the fingerprint is the behavior-relevant command (documents +
    # business_input); the Idempotency-Key is the dedup key, never part of the digest.
    fingerprint = compute_request_fingerprint(body.document_ids, body.business_input)

    # Establish a request ROOT span so this acceptance actually STARTS a trace; the
    # traceparent injected below is serialized into the Outbox payload IN THIS SAME
    # transaction (no external auto-instrumentation required; a no-op without the SDK).
    with root_span("fastapi.accept_job"):
            session = app.state.session_factory()
            async with session:
                # ONE short, explicit Unit of Work (no autobegin then begin()).
                async with session.begin():
                    # Atomic create-or-return (Day43): the UNIQUE(tenant_id, idempotency_key)
                    # constraint is the idempotency mechanism, not a SELECT-then-INSERT.
                    inserted = (
                        await session.execute(
                            text(
                                "INSERT INTO app.jobs "
                                "(tenant_id, idempotency_key, request_fingerprint, job_status) "
                                "VALUES (:t, :k, :fp, 'queued') "
                                "ON CONFLICT (tenant_id, idempotency_key) DO NOTHING "
                                "RETURNING job_id"
                            ),
                            {"t": tenant_id, "k": idempotency_key, "fp": fingerprint},
                        )
                    ).first()

                    if inserted is None:
                        # The key already has a committed Job (this or a concurrent request won
                        # the race). Re-read its fingerprint and classify — NEVER assume replay.
                        existing = (
                            await session.execute(
                                text(
                                    "SELECT job_id, request_fingerprint FROM app.jobs "
                                    "WHERE tenant_id = :t AND idempotency_key = :k"
                                ),
                                {"t": tenant_id, "k": idempotency_key},
                            )
                        ).first()
                        decision = classify_idempotency(
                            existing.request_fingerprint if existing else None, fingerprint
                        )
                        if decision is IdempotencyDecision.RETURN_ORIGINAL:
                            response.status_code = 202
                            return {"job_id": str(existing.job_id), "idempotent_replay": True}
                        # Different fingerprint for the same key -> 409 (exact retry only).
                        raise HTTPException(
                            status_code=409,
                            detail="idempotency key reused for a different request",
                        )

                    # FRESH acceptance. Validate Documents INSIDE the same transaction so an
                    # invalid/wrong-tenant Document rolls the whole thing back -> Job=0/Outbox=0/link=0.
                    job_id = inserted.job_id
                    if not await _all_documents_verified_and_owned(
                        session, tenant_id, body.document_ids
                    ):
                        raise HTTPException(
                            status_code=422, detail="unverified or wrong-tenant document"
                        )

                    # Job–Document links in the CLIENT'S ORDER: document_role='input' and
                    # input_order=1..n make the input sequence a durable PostgreSQL fact a later
                    # Worker can reconstruct. No set()/dict.fromkeys(): duplicates were already
                    # rejected (422) above, so the client's list is written verbatim and in order.
                    for input_order, document_id in enumerate(body.document_ids, start=1):
                        await session.execute(
                            text(
                                "INSERT INTO app.job_documents "
                                "(tenant_id, job_id, document_id, document_role, input_order) "
                                "VALUES (:t, :j, :d, 'input', :ord)"
                            ),
                            {"t": tenant_id, "j": job_id, "d": document_id, "ord": input_order},
                        )

                    # Exactly one dispatch Outbox intent (0008 partial unique index enforces one).
                    # Carry the W3C trace context of THIS request on the dispatch payload (existing
                    # JSONB; no migration) so a later Relay -> Celery Worker can CONTINUE the trace.
                    # Only the low-cardinality `traceparent` string is stored — never a secret or a
                    # provider_request_id. Without the OTel SDK this is an empty carrier (safe no-op).
                    dispatch_payload = store_traceparent_in_payload({}, inject_trace_context({}))
                    await session.execute(
                        text(
                            "INSERT INTO app.outbox_events (job_id, event_type, payload) "
                            "VALUES (:j, :etype, CAST(:payload AS jsonb))"
                        ),
                        {"j": job_id, "etype": DISPATCH_EVENT_TYPE, "payload": json.dumps(dispatch_payload)},
                    )

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
