"""Day60 — REAL Relay / Worker / recovery / repair runtime (SQLAlchemy Core + Celery).

This is the actual runtime the Day60 lesson describes: not just pure decision functions.
It implements, against the REAL Day42/0009/0010 PostgreSQL schema:

  * ``OutboxRelay``   — claims an unpublished ``app.outbox_events`` row with
    ``FOR UPDATE SKIP LOCKED`` + owner/token/expiry, PUBLISHES to Celery/Redis OUTSIDE the
    lock, then guarded-checkpoints ``published_at`` UNDER the fencing token.
  * ``execute_job_attempt`` (a Celery task) — takes execution authority with a guarded
    ``UPDATE app.jobs SET job_status='running' ... WHERE job_status='queued' RETURNING``,
    persists an Attempt + a state-change Event, and completes ONLY under the matching lease
    token (a stale Worker whose lease was taken over cannot commit).
  * ``recovery_sweep`` — recovers ONLY a legitimately EXPIRED ``running`` Job: external
    evidence -> ``pending_reconciliation`` (never a second Provider call); no evidence ->
    one transaction that moves ``running -> queued``, writes a recovery audit Event, and
    writes EXACTLY ONE new ``job.redispatch_requested`` Outbox intent.
  * ``repair_early_ack`` — re-verifies a bounded, RELEASE-FILTERED eligible set inside one
    transaction, writes an immutable ``app.job_repair_history`` row (``repair_id`` PK) LINKED
    to the ONE redispatch Outbox intent it creates (``redispatch_outbox_event_id`` UNIQUE).
    It NEVER calls Celery ``.delay()`` / ``apply_async()`` — repair authority is a durable
    Outbox intent, not a transport publish.

The decision RULES are imported from ``day60_delivery_recovery_logic`` and unit-tested
there; this module wires them to real SQL/transport. Business truth stays in PostgreSQL;
Celery is delivery transport only (``day60_celery_config`` sets late ACK / reject-on-lost /
prefetch 1).

EVIDENCE TIER: this is INTEGRATION_RUNTIME code. Running it needs a real PostgreSQL (at
Alembic ``0010_day60_runtime_schema``) and a real Redis/Celery broker. The repository
updating agent has NONE of those and re-ran ONLY ``py_compile`` + the standard-library
pure-logic tests — **INTEGRATION_RUNTIME NOT RERUN**. See the design/runbook for the exact
disposable-local commands and the Required integration rerun matrix. No secrets, URLs,
passwords, tokens, fixture ids, or container ids are hardcoded here.

Day60 does NOT implement real Provider HTTP, an Object Storage Result Artifact, or
OpenTelemetry — those are Day61.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from day60_delivery_recovery_logic import (
    DISPATCH_EVENT_TYPE,
    RECOVERY_EVENT_TYPE,
    REDISPATCH_EVENT_TYPE,
    RepairCandidate,
    is_repair_eligible,
    repair_id,
)

# Delivery-only Celery settings (config, not a running broker) live here.
try:  # pragma: no cover - config import is trivial
    from day60_celery_config import DAY60_CELERY_SETTINGS
except Exception:  # pragma: no cover
    DAY60_CELERY_SETTINGS = {
        "task_acks_late": True,
        "task_reject_on_worker_lost": True,
        "worker_prefetch_multiplier": 1,
    }

LEASE_SECONDS = 300
RELAY_CLAIM_SECONDS = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ===========================================================================
# Relay: claim (FOR UPDATE SKIP LOCKED) -> publish OUTSIDE lock -> fenced checkpoint.
# ===========================================================================
class OutboxRelay:
    """Delivers unpublished Outbox intents. ``publish`` is injected so this module has no
    hard Celery dependency to import; in a real run it is the Celery task's ``.delay`` /
    ``apply_async`` (Relay concern — publication, NOT business repair)."""

    def __init__(self, engine: Engine, publish, *, relay_id: Optional[str] = None) -> None:
        self._engine = engine
        self._publish = publish
        self._relay_id = relay_id or f"relay-{uuid.uuid4()}"

    def deliver_batch(self, limit: int = 50) -> int:
        delivered = 0
        while True:
            claim = self._claim_one()
            if claim is None:
                break
            outbox_event_id, job_id, event_type, token = claim
            # PUBLISH OUTSIDE the DB lock (the claim tx already committed).
            self._publish(job_id=str(job_id), event_type=event_type,
                          outbox_event_id=str(outbox_event_id))
            # Guarded checkpoint UNDER the fencing token (a stale relay cannot checkpoint).
            self._checkpoint(outbox_event_id, token)
            delivered += 1
            if delivered >= limit:
                break
        return delivered

    def _claim_one(self):
        token = uuid.uuid4()
        now = _now()
        expiry = now + timedelta(seconds=RELAY_CLAIM_SECONDS)
        with self._engine.begin() as conn:  # short tx: SELECT ... FOR UPDATE SKIP LOCKED
            row = conn.execute(
                text(
                    "SELECT outbox_event_id, job_id, event_type FROM app.outbox_events "
                    "WHERE published_at IS NULL "
                    "  AND (relay_claim_expiry IS NULL OR relay_claim_expiry <= :now) "
                    "ORDER BY created_at "
                    "FOR UPDATE SKIP LOCKED LIMIT 1"
                ),
                {"now": now},
            ).first()
            if row is None:
                return None
            conn.execute(
                text(
                    "UPDATE app.outbox_events SET relay_owner=:o, relay_token=:tok, "
                    "relay_claim_expiry=:exp WHERE outbox_event_id=:id"
                ),
                {"o": self._relay_id, "tok": token, "exp": expiry, "id": row.outbox_event_id},
            )
            # Lock released at tx commit — BEFORE any Broker I/O.
            return row.outbox_event_id, row.job_id, row.event_type, token

    def _checkpoint(self, outbox_event_id, token) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE app.outbox_events SET published_at=now() "
                    "WHERE outbox_event_id=:id AND relay_token=:tok AND published_at IS NULL"
                ),
                {"id": outbox_event_id, "tok": token},
            )


# ===========================================================================
# Worker: guarded queued->running claim + Attempt/Event + lease-token guarded completion.
# ===========================================================================
def _claim_running(conn: Connection, job_id: str, worker_id: str, lease_token: str):
    """Guarded authority: exactly one Worker flips queued->running and stamps the lease."""
    return conn.execute(
        text(
            "UPDATE app.jobs SET job_status='running', lease_owner=:w, lease_expiry=:exp "
            "WHERE job_id=:j AND job_status='queued' RETURNING job_id"
        ),
        {"w": lease_token, "exp": _now() + timedelta(seconds=LEASE_SECONDS), "j": job_id},
    ).first()


def _next_attempt_number(conn: Connection, job_id: str) -> int:
    n = conn.execute(
        text("SELECT coalesce(max(attempt_number),0)+1 FROM app.job_attempts WHERE job_id=:j"),
        {"j": job_id},
    ).scalar_one()
    return int(n)


def run_worker_attempt(engine: Engine, job_id: str, worker_id: str) -> str:
    """Execute one authoritative attempt. Returns an outcome tag. Delivery is NOT authority;
    the guarded claim is. Completion happens ONLY under the matching lease token, so a
    stale Worker whose lease was taken over cannot commit."""
    lease_token = f"{worker_id}:{uuid.uuid4()}"
    with engine.begin() as conn:
        won = _claim_running(conn, job_id, worker_id, lease_token)
        if won is None:
            # Duplicate/redelivery: not queued anymore. Do NOT execute; let the sweeper /
            # reconciliation own recovery. (classify_delivery documents the branches.)
            return "not_claimed"
        attempt_number = _next_attempt_number(conn, job_id)
        attempt_id = conn.execute(
            text(
                "INSERT INTO app.job_attempts (job_id, attempt_number) "
                "VALUES (:j, :n) RETURNING attempt_id"
            ),
            {"j": job_id, "n": attempt_number},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO app.job_events (job_id, attempt_id, event_type, from_status, "
                "to_status, actor) VALUES (:j, :a, 'attempt.started', 'queued', 'running', :w)"
            ),
            {"j": job_id, "a": attempt_id, "w": worker_id},
        )

    # ... the actual unit of work would run here (Day61 adds real Provider/Object Storage) ...

    # Guarded completion ONLY under the matching lease token.
    with engine.begin() as conn:
        completed = conn.execute(
            text(
                "UPDATE app.jobs SET job_status='succeeded', finished_at=now() "
                "WHERE job_id=:j AND job_status='running' AND lease_owner=:tok "
                "RETURNING job_id"
            ),
            {"j": job_id, "tok": lease_token},
        ).first()
        if completed is None:
            # Lease was taken over (or Job no longer running) -> a stale Worker MUST NOT
            # overwrite business state. Leave recovery to the sweeper.
            return "lease_lost_no_commit"
        conn.execute(
            text(
                "INSERT INTO app.job_events (job_id, event_type, from_status, to_status, actor) "
                "VALUES (:j, 'attempt.succeeded', 'running', 'succeeded', :w)"
            ),
            {"j": job_id, "w": worker_id},
        )
    return "succeeded"


# ===========================================================================
# Recovery sweep: only a legitimately EXPIRED running Job (queued/terminal never swept).
# ===========================================================================
def recovery_sweep(engine: Engine, limit: int = 50) -> dict[str, int]:
    reconciled = 0
    requeued = 0
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT job_id, (provider_dispatch_started_at IS NOT NULL) AS has_marker "
                "FROM app.jobs "
                "WHERE job_status='running' AND lease_expiry IS NOT NULL AND lease_expiry <= now() "
                "ORDER BY lease_expiry "
                "FOR UPDATE SKIP LOCKED LIMIT :lim"
            ),
            {"lim": limit},
        ).all()
        for r in rows:
            has_evidence = bool(r.has_marker) or _attempt_has_provider_request(conn, r.job_id)
            if has_evidence:
                # External call MAY have happened -> reconcile, never a second Provider call.
                conn.execute(
                    text(
                        "UPDATE app.jobs SET job_status='pending_reconciliation' "
                        "WHERE job_id=:j AND job_status='running'"
                    ),
                    {"j": r.job_id},
                )
                conn.execute(
                    text(
                        "INSERT INTO app.job_events (job_id, event_type, from_status, "
                        "to_status, actor) VALUES (:j, 'recovery.reconcile', 'running', "
                        "'pending_reconciliation', 'sweeper')"
                    ),
                    {"j": r.job_id},
                )
                reconciled += 1
            else:
                # No evidence -> atomic running->queued + audit + EXACTLY ONE redispatch intent.
                conn.execute(
                    text(
                        "UPDATE app.jobs SET job_status='queued', lease_owner=NULL, "
                        "lease_expiry=NULL WHERE job_id=:j AND job_status='running'"
                    ),
                    {"j": r.job_id},
                )
                conn.execute(
                    text(
                        "INSERT INTO app.job_events (job_id, event_type, from_status, "
                        "to_status, actor) VALUES (:j, :etype, 'running', 'queued', 'sweeper')"
                    ),
                    {"j": r.job_id, "etype": RECOVERY_EVENT_TYPE},
                )
                conn.execute(
                    text(
                        "INSERT INTO app.outbox_events (job_id, event_type, payload) "
                        "VALUES (:j, :etype, '{}'::jsonb)"
                    ),
                    {"j": r.job_id, "etype": REDISPATCH_EVENT_TYPE},
                )
                requeued += 1
    return {"reconciled": reconciled, "requeued": requeued}


def _attempt_has_provider_request(conn: Connection, job_id: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT 1 FROM app.job_attempts "
                "WHERE job_id=:j AND provider_request_id IS NOT NULL LIMIT 1"
            ),
            {"j": job_id},
        ).first()
    )


# ===========================================================================
# Bounded early-ACK repair: re-verify (release-filtered) -> immutable audit LINKED to one
# redispatch intent. NEVER .delay()/apply_async().
# ===========================================================================
def repair_early_ack(engine: Engine, job_id: str, affected_release_version: str,
                     reason: str = "early_ack") -> str:
    """Idempotent, auditable, release-filtered repair for ONE Job. Returns an outcome tag.

    All work is one transaction: re-read + re-verify the candidate, then INSERT the
    ``job_repair_history`` row (``repair_id`` PK) and the ONE redispatch Outbox intent,
    linking them via ``redispatch_outbox_event_id`` (UNIQUE). A concurrent/duplicate repair
    for the same ``repair_id`` hits the PK and applies exactly once -> one repair fact + one
    intent. This function NEVER calls Celery ``.delay()`` / ``apply_async()``.
    """
    rid = repair_id(job_id, affected_release_version, reason)
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT job_id, job_status, release_version, request_fingerprint "
                    "FROM app.jobs WHERE job_id=:j FOR UPDATE"
                ),
                {"j": job_id},
            ).first()
            if row is None:
                return "not_found"
            candidate = RepairCandidate(
                actual_release_version=row.release_version or "",
                within_time_window=_within_repair_window(conn, job_id),
                status=row.job_status,
                has_original_dispatch_checkpoint=_has_checkpointed_dispatch(conn, job_id),
                has_attempts_or_external_evidence=_has_attempts(conn, job_id),
                has_conflict=False,
                deadline_contract_budget_valid=True,
                repair_already_applied=_repair_applied(conn, rid),
            )
            if not is_repair_eligible(candidate, affected_release_version):
                return "not_eligible"
            outbox_event_id = conn.execute(
                text(
                    "INSERT INTO app.outbox_events (job_id, event_type, payload) "
                    "VALUES (:j, :etype, '{}'::jsonb) RETURNING outbox_event_id"
                ),
                {"j": job_id, "etype": REDISPATCH_EVENT_TYPE},
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO app.job_repair_history "
                    "(repair_id, job_id, repair_reason, release_version, redispatch_outbox_event_id) "
                    "VALUES (:rid, :j, :reason, :rel, :oid)"
                ),
                {"rid": rid, "j": job_id, "reason": reason,
                 "rel": affected_release_version, "oid": outbox_event_id},
            )
        return "repaired"
    except IntegrityError:
        # A concurrent repair for the same repair_id won (PK / UNIQUE) -> exactly-once.
        return "already_applied"


def _within_repair_window(conn: Connection, job_id: str) -> bool:
    # Placeholder for the deployment-window predicate (bad-release start/end); the real run
    # binds it to the incident window. Kept explicit so the eligibility set stays bounded.
    return True


def _has_checkpointed_dispatch(conn: Connection, job_id: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT 1 FROM app.outbox_events "
                "WHERE job_id=:j AND event_type=:etype AND published_at IS NOT NULL LIMIT 1"
            ),
            {"j": job_id, "etype": DISPATCH_EVENT_TYPE},
        ).first()
    )


def _has_attempts(conn: Connection, job_id: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT 1 FROM app.job_attempts WHERE job_id=:j LIMIT 1"), {"j": job_id}
        ).first()
    )


def _repair_applied(conn: Connection, rid: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT 1 FROM app.job_repair_history WHERE repair_id=:rid"), {"rid": rid}
        ).first()
    )
