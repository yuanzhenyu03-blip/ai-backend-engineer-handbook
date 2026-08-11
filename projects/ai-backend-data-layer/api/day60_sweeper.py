"""Day60 — recovery sweeper process entrypoint.

Periodically runs ``recovery_sweep``: it recovers ONLY legitimately expired ``running`` Jobs
(``lease_expires_at <= now``). With external evidence a Job goes to
``pending_reconciliation`` (never a second Provider call); without evidence it is atomically
requeued with ONE new ``job.redispatch_requested`` Outbox intent for the Relay to deliver.
The sweeper NEVER publishes to the broker.

Run:
    DAY60_DATABASE_URL=postgresql://... python3 day60_sweeper.py
"""

from __future__ import annotations

import os
import time

from sqlalchemy import create_engine

from day60_delivery_runtime import recovery_sweep


def main() -> None:
    url = os.environ.get("DAY60_DATABASE_URL")
    if not url:
        raise SystemExit("DAY60_DATABASE_URL is required (a disposable local sync URL).")
    engine = create_engine(url, pool_pre_ping=True)
    poll_seconds = float(os.environ.get("DAY60_SWEEP_POLL_SECONDS", "5.0"))
    while True:
        recovery_sweep(engine, limit=50)
        time.sleep(poll_seconds)


if __name__ == "__main__":  # pragma: no cover
    main()
