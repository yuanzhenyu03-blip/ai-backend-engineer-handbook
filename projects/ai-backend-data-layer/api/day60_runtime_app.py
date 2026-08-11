"""Day60 — local-only app-factory with an EXPLICIT expected-revision parameter.

The Day59 readiness app pinned exactly ``0008_day59_acceptance`` and (correctly) returned
503 once the database moved to ``0009_day60_delivery_runtime``. Rather than mutate hidden
module state, Day60 exposes a production-quality ``create_app(expected_revision=...)``
factory so each composition declares the schema revision it requires. The Day60
composition requires the Day60 head revision ``0011_day60_lease_realign``.

BOUNDARIES (unchanged from Day59): this is a COMPOSITION/readiness seam only. The HTTP
process NEVER calls a Broker, Celery Worker, Provider, or Object Storage — the Relay and
Worker are SEPARATE processes (see ``day60_celery_config.py`` and the design/runbook). The
disposable database URL is read from ``DAY60_DATABASE_URL`` (or an override passed to the
factory); no URL/password/token/fixture id is hardcoded.

Evidence tier: running this under Uvicorn + PostgreSQL + Alembic-at-0009 is
INTEGRATION_RUNTIME. The updating repository agent re-ran only ``py_compile`` and the
standard-library ``test_day60_delivery_recovery_logic.py``; it did NOT run the
Docker/PostgreSQL/Redis/Celery integration — see the design/runbook for the exact commands
and NOT RUN limits.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Response
from sqlalchemy import text

from day47_async_uow import create_engine, create_session_factory
from day60_delivery_recovery_logic import revision_ready

DAY60_EXPECTED_REVISION = "0011_day60_lease_realign"


def _resolve_database_url(explicit: Optional[str]) -> str:
    url = explicit or os.environ.get("DAY60_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Day60 local integration requires DAY60_DATABASE_URL (a disposable local "
            "async PostgreSQL URL, e.g. postgresql+asyncpg://USER:PASS@127.0.0.1:5432/DB). "
            "No credential is hardcoded in the repository."
        )
    return url


def create_app(
    *,
    expected_revision: str = DAY60_EXPECTED_REVISION,
    database_url: Optional[str] = None,
) -> FastAPI:
    """Build a Day60 app that gates readiness on ``expected_revision`` (default 0009).

    ``expected_revision`` is an EXPLICIT parameter, not hidden module state, so tests and
    alternate compositions can pin a different revision deterministically.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_engine(_resolve_database_url(database_url))
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        app.state.expected_revision = expected_revision
        try:
            yield
        finally:
            await engine.dispose()  # lifespan owns disposal; app never self-runs migrations

    app = FastAPI(title="Day60 Delivery Runtime (readiness seam)", lifespan=lifespan)

    @app.get("/livez")
    async def livez() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/readyz")
    async def readyz(response: Response) -> dict[str, str]:
        current: Optional[str] = None
        reachable = True
        try:
            session = app.state.session_factory()
            async with session:
                row = await session.execute(text("SELECT version_num FROM alembic_version"))
                current = row.scalar_one_or_none()
        except Exception:
            reachable = False
        if not reachable:
            response.status_code = 503
            return {"status": "not_ready", "reason": "database_unreachable"}
        if not revision_ready(current, app.state.expected_revision):
            response.status_code = 503
            return {
                "status": "not_ready",
                "reason": f"revision_mismatch:expected={app.state.expected_revision}:actual={current}",
            }
        return {"status": "ready", "revision": app.state.expected_revision}

    return app
