"""Day60 — Relay process entrypoint (the ONLY component that publishes to the broker).

Claims unpublished Outbox intents and publishes each by calling the real Celery task's
``apply_async`` OUTSIDE the database lock, then guarded-checkpoints ``published_at`` under
the fencing token (``OutboxRelay`` in ``day60_delivery_runtime``). Recovery and repair NEVER
publish — they only write durable Outbox intents that this Relay later delivers.

Run (see the design/runbook for the full disposable-local setup):
    DAY60_DATABASE_URL=postgresql://... DAY60_BROKER_URL=redis://... \
        python3 day60_relay.py
"""

from __future__ import annotations

import os
import time

from sqlalchemy import create_engine

from day60_celery_app import execute_job_attempt
from day60_delivery_runtime import OutboxRelay


def _publish(job_id: str, event_type: str, outbox_event_id: str) -> None:
    # The ONLY publish path. apply_async is a RELAY concern (transport), never business repair.
    execute_job_attempt.apply_async(
        kwargs={"job_id": job_id, "outbox_event_id": outbox_event_id, "event_type": event_type}
    )


def main() -> None:
    url = os.environ.get("DAY60_DATABASE_URL")
    if not url:
        raise SystemExit("DAY60_DATABASE_URL is required (a disposable local sync URL).")
    engine = create_engine(url, pool_pre_ping=True)
    relay = OutboxRelay(engine, _publish)
    poll_seconds = float(os.environ.get("DAY60_RELAY_POLL_SECONDS", "1.0"))
    while True:
        delivered = relay.deliver_batch(limit=50)
        if delivered == 0:
            time.sleep(poll_seconds)


if __name__ == "__main__":  # pragma: no cover
    main()
