"""Day60 — Celery delivery configuration (design values; NOT a running broker).

These are the exact delivery-safety settings the Day60 Relay/Worker path uses. This module
holds CONFIGURATION ONLY: importing it starts no broker, no Worker, and no network. A real
run needs a real Redis/Celery broker (see the design/runbook), which the updating agent did
NOT run.

Rationale:
  * ``task_acks_late=True``            — ACK AFTER task processing, so a Worker crash mid-task
                                         redelivers the message. ACK is TRANSPORT acknowledgement,
                                         never a business-state commit.
  * ``task_reject_on_worker_lost=True``— a lost Worker's task is rejected/redelivered rather than
                                         silently acked.
  * ``worker_prefetch_multiplier=1``   — one in-flight task per Worker; no hidden prefetch backlog
                                         that would blur redelivery/recovery reasoning.

Celery ``.delay()`` / ``apply_async()`` are RELAY concerns (immediate Broker publication). They
are NOT durable business repair authority: they publish a message but create no transactionally
coupled, replayable, auditable Outbox intent. Durable recovery authority is PostgreSQL state plus a
newly committed ``job.redispatch_requested`` Outbox intent.
"""

from __future__ import annotations

# A plain mapping so this file has no Celery import dependency to compile/inspect.
DAY60_CELERY_SETTINGS: dict[str, object] = {
    "task_acks_late": True,
    "task_reject_on_worker_lost": True,
    "worker_prefetch_multiplier": 1,
}
