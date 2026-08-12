"""Day60 — REAL Relay / Worker / recovery / repair runtime (SQLAlchemy Core).

Implements, against the REAL Day42 + Day48 lease schema (0002/0003) and the additive Day60
migrations (0009-0011):

  * ``OutboxRelay``   — claims an unpublished ``app.outbox_events`` row with
    ``FOR UPDATE SKIP LOCKED`` + owner/token/expiry, PUBLISHES OUTSIDE the DB lock (via an
    injected publisher — in production the Celery task's ``apply_async``; see
    ``day60_relay.py``), then guarded-checkpoints ``published_at`` UNDER the fencing token.
  * ``run_worker_attempt`` — takes execution authority with a guarded
    ``UPDATE app.jobs SET job_status='running', lease_owner=:owner, lease_token=:token,
    lease_expires_at=:exp WHERE job_status='queued' RETURNING`` that writes the EXISTING
    Day48 lease TRIPLE (``lease_owner``/``lease_token``/``lease_expires_at``) atomically so
    it satisfies ``jobs_lease_triple_coherent`` and ``jobs_running_requires_lease``. It
    persists an Attempt + a state-change Event, and completes ONLY under the matching
    ``lease_token`` (a stale, taken-over Worker cannot commit and does not close its Attempt
    or overwrite the new owner).
  * ``recovery_sweep`` — recovers ONLY a legitimately EXPIRED ``running`` Job
    (``lease_expires_at <= now``): external evidence -> ``pending_reconciliation`` (never a
    second Provider call); no evidence -> one transaction that clears the lease triple, moves
    ``running -> queued``, writes a recovery audit Event (leaving the old unfinished Attempt
    as interrupted evidence), and writes EXACTLY ONE new ``job.redispatch_requested`` Outbox
    intent. A queued/terminal Job is never swept.
  * ``repair_early_ack`` — re-verifies a BOUNDED, release-filtered, TIME-WINDOWED,
    caller-ATTESTED set inside one transaction, writes an immutable ``job_repair_history`` row
    (``repair_id`` PK) LINKED to the ONE redispatch Outbox intent it creates
    (``redispatch_outbox_event_id`` UNIQUE). It NEVER calls Celery ``.delay()`` /
    ``apply_async()`` — only the Relay publishes.

The lease boundary is the SHARED rule: ``lease_expires_at > now`` active,
``lease_expires_at <= now`` expired (so ``== now`` is expired). Business truth stays in
PostgreSQL; Celery is delivery transport only.

EVIDENCE TIER: INTEGRATION_RUNTIME code. Running it needs a real PostgreSQL (at Alembic
``0011_day60_lease_realign``) and a real Redis/Celery broker. The repository updating agent
has NONE of those and re-ran ONLY ``py_compile`` + the standard-library pure-logic tests —
**INTEGRATION_RUNTIME NOT RERUN**. See the design/runbook for the exact commands and the
Required integration rerun matrix. No secrets/URLs/passwords/tokens/fixture ids are
hardcoded. Day60 does NOT implement real Provider HTTP, an Object Storage Result Artifact,
or OpenTelemetry — those are Day61; a Worker "succeeds" the skeleton without a Provider call.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from day61_telemetry import extract_trace_context, load_traceparent_from_payload, operation_span
from sqlalchemy.exc import IntegrityError

from day60_delivery_recovery_logic import (
    DISPATCH_EVENT_TYPE,
    RECOVERY_EVENT_TYPE,
    REDISPATCH_EVENT_TYPE,
    RepairCandidate,
    RepairFact,
    classify_repair_integrity,
    in_time_window,
    is_repair_eligible,
    repair_id,
)

LEASE_SECONDS = 300
RELAY_CLAIM_SECONDS = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _epoch(dt: Optional[datetime]) -> Optional[int]:
    return None if dt is None else int(dt.timestamp())


# ===========================================================================
# Relay: claim (FOR UPDATE SKIP LOCKED) -> publish OUTSIDE lock -> fenced checkpoint.
# ===========================================================================
class OutboxRelay:
    """Delivers unpublished Outbox intents. ``publish`` is injected (``day60_relay.py`` wires
    it to the real Celery task's ``apply_async``); ONLY the Relay publishes — repair and
    recovery never call ``.delay()``/``apply_async()``, they only write durable intents."""

    def __init__(self, engine: Engine, publish, *, relay_id: Optional[str] = None) -> None:
        self._engine = engine
        self._publish = publish
        self._relay_id = relay_id or f"relay-{uuid.uuid4()}"

    def deliver_batch(self, limit: int = 50) -> int:
        delivered = 0
        while delivered < limit:
            claim = self._claim_one()
            if claim is None:
                break
            outbox_event_id, job_id, event_type, token, payload = claim
            # The SAME durable Outbox payload carries the request's W3C traceparent, so a Relay
            # RETRY of this intent reuses the SAME trace association; each publish still gets a
            # fresh span id from the SDK. Loading is a pure read of the existing JSONB.
            trace_carrier = load_traceparent_from_payload(payload)
            self._publish(job_id=str(job_id), event_type=event_type,
                          outbox_event_id=str(outbox_event_id),
                          trace_carrier=trace_carrier)          # OUTSIDE the DB lock
            self._checkpoint(outbox_event_id, token)             # fenced by relay_token
            delivered += 1
        return delivered

    def _claim_one(self):
        token = uuid.uuid4()
        now = _now()
        with self._engine.begin() as conn:  # short tx; lock released at commit, before I/O
            row = conn.execute(
                text(
                    "SELECT outbox_event_id, job_id, event_type, payload FROM app.outbox_events "
                    "WHERE published_at IS NULL "
                    "  AND (relay_claim_expiry IS NULL OR relay_claim_expiry <= :now) "
                    "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"
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
                {"o": self._relay_id, "tok": token,
                 "exp": now + timedelta(seconds=RELAY_CLAIM_SECONDS), "id": row.outbox_event_id},
            )
            return row.outbox_event_id, row.job_id, row.event_type, token, row.payload

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
# Worker: guarded queued->running claim writes the FULL lease triple + Attempt/Event;
# completion matches lease_token (not owner) and keeps Job/Attempt/Event/lease consistent.
# ===========================================================================
def run_worker_attempt(engine: Engine, job_id: str, worker_id: str,
                       trace_carrier: Optional[dict] = None) -> str:
    """Execute one authoritative attempt. Returns an outcome tag. Delivery is NOT authority;
    the guarded claim is. Completion happens ONLY under the matching ``lease_token``.

    ``trace_carrier`` is the propagated W3C text-map extracted from the Celery message; the
    unit-of-work seam runs UNDER that context so the Worker's spans continue the request's
    trace. It is DIAGNOSTIC only — it never changes the claim/completion authority."""
    lease_token = uuid.uuid4()  # the fencing token (NOT mixed into lease_owner)

    # --- claim tx: guarded queued->running writing the FULL lease triple + start Attempt ---
    with engine.begin() as conn:
        won = conn.execute(
            text(
                "UPDATE app.jobs SET job_status='running', lease_owner=:owner, "
                "lease_token=:token, lease_expires_at=:exp "
                "WHERE job_id=:j AND job_status='queued' RETURNING job_id"
            ),
            {"owner": worker_id, "token": lease_token,
             "exp": _now() + timedelta(seconds=LEASE_SECONDS), "j": job_id},
        ).first()
        if won is None:
            return "not_claimed"  # duplicate/redelivery: let the sweeper/reconciliation own it
        attempt_number = int(
            conn.execute(
                text("SELECT coalesce(max(attempt_number),0)+1 FROM app.job_attempts WHERE job_id=:j"),
                {"j": job_id},
            ).scalar_one()
        )
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

    # ... the unit of work runs here. Day60 has NO real Provider/Object Storage/Result
    # Artifact (that is Day61); the skeleton "succeeds" without a Provider call. The seam is
    # wrapped in a span UNDER the propagated trace context (diagnostic only — no authority
    # change); in the Day61 integration `run_external_operation` runs the real Provider/
    # Storage/DB spans here under the SAME context.
    _parent_ctx = extract_trace_context(trace_carrier) if trace_carrier else None
    with operation_span("worker.unit_of_work", str(job_id), str(attempt_id), parent_context=_parent_ctx):
        pass

    # --- guarded completion tx: ONE transaction keeps Job/Attempt/Event/lease consistent ---
    with engine.begin() as conn:
        completed = conn.execute(
            text(
                "UPDATE app.jobs SET job_status='succeeded', finished_at=now(), "
                "attempt_count=attempt_count+1, "
                "lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL "
                "WHERE job_id=:j AND job_status='running' AND lease_token=:token RETURNING job_id"
            ),
            {"j": job_id, "token": lease_token},
        ).first()
        if completed is None:
            # Lease taken over (or Job no longer running): a stale Worker MUST NOT write
            # success, MUST NOT close its Attempt, and MUST NOT overwrite the new owner.
            return "lease_lost_no_commit"
        conn.execute(
            text("UPDATE app.job_attempts SET finished_at=now() WHERE attempt_id=:a"),
            {"a": attempt_id},
        )
        conn.execute(
            text(
                "INSERT INTO app.job_events (job_id, attempt_id, event_type, from_status, "
                "to_status, actor) VALUES (:j, :a, 'attempt.succeeded', 'running', 'succeeded', :w)"
            ),
            {"j": job_id, "a": attempt_id, "w": worker_id},
        )
    return "succeeded"


# ===========================================================================
# Recovery sweep: only a legitimately EXPIRED running Job (queued/terminal never swept).
# ===========================================================================
def recovery_sweep(engine: Engine, limit: int = 50) -> dict[str, int]:
    reconciled = requeued = 0
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT job_id, (provider_dispatch_started_at IS NOT NULL) AS has_marker "
                "FROM app.jobs "
                "WHERE job_status='running' AND lease_expires_at IS NOT NULL "
                "  AND lease_expires_at <= now() "  # <= now: == now is expired
                "ORDER BY lease_expires_at FOR UPDATE SKIP LOCKED LIMIT :lim"
            ),
            {"lim": limit},
        ).all()
        for r in rows:
            has_evidence = bool(r.has_marker) or _attempt_has_provider_request(conn, r.job_id)
            if has_evidence:
                # Clear the lease triple (coherent: all NULL) and reconcile; NO 2nd call.
                conn.execute(
                    text(
                        "UPDATE app.jobs SET job_status='pending_reconciliation', "
                        "lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL "
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
                # Clear the lease triple, running->queued, audit, ONE redispatch intent.
                # The old unfinished Attempt (finished_at IS NULL) is LEFT as interrupted
                # evidence; the next Worker uses the next attempt_number.
                conn.execute(
                    text(
                        "UPDATE app.jobs SET job_status='queued', "
                        "lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL "
                        "WHERE job_id=:j AND job_status='running'"
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
# Bounded early-ACK repair: TIME-WINDOWED + release-filtered + caller-ATTESTED.
# ===========================================================================
@dataclass(frozen=True)
class RepairAttestation:
    """Caller-provided, AUDITABLE eligibility attestation for fields the current schema
    cannot verify itself. The repository has no deadline/contract/budget/conflict columns,
    so these are EXPLICIT operator attestations recorded in the repair audit — NOT silent
    hardcoded truths. If a caller cannot attest them, the repair is conservatively refused."""
    no_conflict: bool
    deadline_contract_budget_valid: bool


def repair_early_ack(
    engine: Engine,
    job_id: str,
    affected_release_version: str,
    incident_start: datetime,
    incident_end: datetime,
    attestation: RepairAttestation,
    reason: str = "early_ack",
) -> str:
    """Idempotent, auditable, BOUNDED repair for ONE Job. Requires an explicit incident
    ``[incident_start, incident_end]`` window (verified against the persisted dispatch-Outbox
    time fact) and a caller ``attestation``. All checks are re-verified inside the repair
    transaction. NEVER calls Celery ``.delay()``/``apply_async()``."""
    rid = repair_id(job_id, affected_release_version, reason)
    start_epoch, end_epoch = _epoch(incident_start), _epoch(incident_end)
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT job_status, release_version FROM app.jobs "
                    "WHERE job_id=:j FOR UPDATE"
                ),
                {"j": job_id},
            ).first()
            if row is None:
                return "not_found"
            dispatch_created = conn.execute(
                text(
                    "SELECT min(created_at) FROM app.outbox_events "
                    "WHERE job_id=:j AND event_type=:etype AND published_at IS NOT NULL"
                ),
                {"j": job_id, "etype": DISPATCH_EVENT_TYPE},
            ).scalar()
            candidate = RepairCandidate(
                actual_release_version=row.release_version or "",
                within_time_window=in_time_window(_epoch(dispatch_created), start_epoch, end_epoch),
                status=row.job_status,
                has_original_dispatch_checkpoint=dispatch_created is not None,
                has_attempts_or_external_evidence=_has_attempts_or_marker(conn, job_id),
                has_conflict=not attestation.no_conflict,
                deadline_contract_budget_valid=attestation.deadline_contract_budget_valid,
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
                    "(repair_id, job_id, repair_reason, release_version, redispatch_outbox_event_id, "
                    " incident_start, incident_end, no_conflict_attested, "
                    " deadline_contract_budget_valid_attested) "
                    "VALUES (:rid, :j, :reason, :rel, :oid, :istart, :iend, :nca, :dcbva)"
                ),
                {"rid": rid, "j": job_id, "reason": reason,
                 "rel": affected_release_version, "oid": outbox_event_id,
                 "istart": incident_start, "iend": incident_end,
                 "nca": attestation.no_conflict,
                 "dcbva": attestation.deadline_contract_budget_valid},
            )
        return "repaired"
    except IntegrityError:
        # Do NOT assume a duplicate. The tx rolled back; RE-READ the committed repair row for
        # this repair_id in a FRESH transaction and classify: a genuine same-repair duplicate
        # is "already_applied"; an unrelated integrity failure is "repair_failed" (never a
        # silent fake success).
        with engine.begin() as conn2:
            existing = conn2.execute(
                text(
                    "SELECT h.job_id, h.release_version, h.repair_reason, "
                    "       h.redispatch_outbox_event_id, "
                    "       o.outbox_event_id AS linked_outbox_id, "
                    "       o.job_id          AS linked_outbox_job_id, "
                    "       o.event_type      AS linked_outbox_event_type "
                    "FROM app.job_repair_history h "
                    "LEFT JOIN app.outbox_events o "
                    "  ON o.outbox_event_id = h.redispatch_outbox_event_id "
                    "WHERE h.repair_id=:rid"
                ),
                {"rid": rid},
            ).first()
        existing_fact = (
            None if existing is None
            else RepairFact(
                job_id=str(existing.job_id),
                release_version=existing.release_version or "",
                reason=existing.repair_reason,
                # A non-null FK is NOT enough: the JOINED Outbox row must actually exist,
                # belong to THIS Job, and be a job.redispatch_requested intent.
                has_linked_outbox=(
                    existing.redispatch_outbox_event_id is not None
                    and existing.linked_outbox_id is not None
                ),
                linked_outbox_job_matches=(
                    existing.linked_outbox_job_id is not None
                    and str(existing.linked_outbox_job_id) == str(job_id)
                ),
                linked_outbox_is_redispatch=(
                    existing.linked_outbox_event_type == REDISPATCH_EVENT_TYPE
                ),
            )
        )
        expected_fact = RepairFact(
            job_id=str(job_id),
            release_version=affected_release_version,
            reason=reason,
            has_linked_outbox=True,
            linked_outbox_job_matches=True,
            linked_outbox_is_redispatch=True,
        )
        return classify_repair_integrity(existing_fact, expected_fact)


def _has_attempts_or_marker(conn: Connection, job_id: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT 1 FROM app.jobs j "
                "WHERE j.job_id=:j AND j.provider_dispatch_started_at IS NOT NULL "
                "UNION ALL SELECT 1 FROM app.job_attempts WHERE job_id=:j LIMIT 1"
            ),
            {"j": job_id},
        ).first()
    )


def _repair_applied(conn: Connection, rid: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT 1 FROM app.job_repair_history WHERE repair_id=:rid"), {"rid": rid}
        ).first()
    )
