"""Day60 — the REAL Celery application + Worker task.

This is an ACTUAL Celery app (not a config dict): it applies the delivery-safety settings
and registers the Worker task the Relay publishes. Running it needs a real Redis broker
(``DAY60_BROKER_URL``) and a real PostgreSQL (``DAY60_DATABASE_URL``); ``import celery`` is
only needed at run time, so ``py_compile`` succeeds without the broker installed.

Boundaries:
  * The task takes execution authority through the guarded runtime
    (``run_worker_attempt``) — Celery delivery is NOT authority.
  * ``task_acks_late`` + ``task_reject_on_worker_lost`` + ``worker_prefetch_multiplier=1``
    make a lost Worker redeliver, so the durable lease + sweeper own recovery.
  * ONLY the Relay publishes (``day60_relay.py`` calls ``execute_job_attempt.apply_async``).
    Recovery/repair NEVER publish; they write durable Outbox intents the Relay later delivers.

No secrets/URLs are hardcoded; the broker/DB URLs come from environment variables at run time.
"""

from __future__ import annotations

import os

from celery import Celery  # type: ignore
from sqlalchemy import create_engine

from day60_celery_config import DAY60_CELERY_SETTINGS
from day61_telemetry import bootstrap_telemetry
from day61_worker_runtime import run_authoritative_attempt

celery_app = Celery("day60")
celery_app.conf.update(
    broker_url=os.environ.get("DAY60_BROKER_URL"),
    result_backend=os.environ.get("DAY60_RESULT_BACKEND"),
    **DAY60_CELERY_SETTINGS,  # task_acks_late / task_reject_on_worker_lost / prefetch 1
)

_ENGINE = None


try:  # bootstrap telemetry once per worker PROCESS (idempotent, disabled by default).
    from celery.signals import worker_process_init  # type: ignore

    @worker_process_init.connect
    def _init_worker_telemetry(**_kwargs):  # pragma: no cover - needs a live worker
        bootstrap_telemetry("celery-worker")
except Exception:  # pragma: no cover - signals unavailable at import time
    pass


def _engine():
    """Process-scoped sync engine for the Worker. A SYNC ``postgresql://`` URL (psycopg2)
    is used because the Worker/guarded claim path is synchronous SQLAlchemy Core."""
    global _ENGINE
    if _ENGINE is None:
        url = os.environ.get("DAY60_DATABASE_URL")
        if not url:
            raise RuntimeError("DAY60_DATABASE_URL is required (a disposable local sync URL).")
        _ENGINE = create_engine(url, pool_pre_ping=True)
    return _ENGINE


@celery_app.task(name="day60.execute_job_attempt", bind=True)
def execute_job_attempt(self, job_id: str, outbox_event_id: str,
                        event_type: str = "job.dispatch_requested", trace_carrier: dict | None = None):
    """The Worker task. Delivery gives it the Job/Outbox identity; the guarded runtime
    decides authority. ``task_reject_on_worker_lost`` + ``task_acks_late`` mean a crash
    redelivers rather than silently acking.

    ``trace_carrier`` is the propagated W3C text-map (``{"traceparent": ...}``) the Relay put
    on the task kwargs. It is extracted here so the Day61 external-operation spans (Provider
    HTTP, Object Storage, guarded DB completion) CONTINUE the original request's trace. A
    missing/empty/corrupt carrier degrades to a local trace and never changes authority. The
    extracted context is not a business input — the guarded runtime remains the only authority."""
    bootstrap_telemetry("celery-worker")  # idempotent; also covers the solo/eager path
    worker_id = self.request.hostname or f"worker-{os.getpid()}"
    # The PRODUCTION path: a real Provider HTTP call + Object Storage + guarded completion.
    # There is NO "no Provider, straight to succeeded" branch here. The Provider URL is the
    # SEPARATE fake HTTP Provider, taken from the environment (never from the message).
    provider_url = os.environ.get("DAY61_PROVIDER_URL")
    if not provider_url:
        raise RuntimeError("DAY61_PROVIDER_URL is required (the SEPARATE fake HTTP Provider URL).")
    # tenant + correlation key are loaded from PostgreSQL durable facts inside the composition;
    # the message supplies only Job identity + the diagnostic trace carrier.
    return run_authoritative_attempt(
        _engine(), job_id, worker_id, provider_url=provider_url, trace_carrier=trace_carrier or {}
    )
