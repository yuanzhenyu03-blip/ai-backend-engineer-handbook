"""Day60 — pure delivery/recovery decision logic (standard library only).

The DECISION CORE of the Day60 Relay + Worker + recovery boundary, separated from the
real runtime (``day60_delivery_runtime.py``) so the RULES can be unit-tested WITHOUT a
database, a broker, or Docker. Every function here is deterministic control flow over
plain values.

Evidence tier: functions here are ``EXECUTED_LOCAL_RUNTIME`` when driven by
``test_day60_delivery_recovery_logic.py``. They prove the RULES only. They do NOT prove
real PostgreSQL ``FOR UPDATE SKIP LOCKED`` / guarded ``UPDATE ... RETURNING`` /
transaction / isolation, a real Redis/Celery broker, ACK timing, redelivery, or
Worker-kill — that is ``INTEGRATION_RUNTIME`` (the runtime lives in
``day60_delivery_runtime.py``; see the design/runbook for its NOT-RERUN status).

No secrets, URLs, passwords, tokens, or fixture ids live in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

REDISPATCH_EVENT_TYPE = "job.redispatch_requested"
DISPATCH_EVENT_TYPE = "job.dispatch_requested"
RECOVERY_EVENT_TYPE = "job.recovery_requeued"

# Terminal business states are never redispatched or swept.
TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


# ---------------------------------------------------------------------------
# Lease boundary — ONE rule shared by the Worker classifier and the sweeper.
# ---------------------------------------------------------------------------
def lease_active(lease_expiry_epoch: Optional[int], now_epoch: int) -> bool:
    """A lease is ACTIVE only while ``lease_expiry > now`` (strictly greater). At exactly
    ``lease_expiry == now`` the lease is EXPIRED. ``None`` means no lease -> not active."""
    return lease_expiry_epoch is not None and lease_expiry_epoch > now_epoch


def lease_expired(lease_expiry_epoch: Optional[int], now_epoch: int) -> bool:
    """Exact complement of :func:`lease_active`: expired when ``lease_expiry <= now`` (so
    ``== now`` is expired) or when there is no lease."""
    return not lease_active(lease_expiry_epoch, now_epoch)


def in_time_window(
    event_epoch: Optional[int], incident_start_epoch: int, incident_end_epoch: int
) -> bool:
    """Bounded early-ACK repair window predicate. A candidate is in-window ONLY if a
    persisted time fact (e.g. the original dispatch Outbox ``created_at``) falls in the
    caller-supplied incident window ``[start, end]`` (inclusive). ``None`` (no persisted
    time fact) is NEVER in-window — the affected set must be genuinely bounded, so this is
    never hardcoded ``True`` and an empty/unknown time is conservatively rejected."""
    if event_epoch is None or incident_start_epoch > incident_end_epoch:
        return False
    return incident_start_epoch <= event_epoch <= incident_end_epoch


# ---------------------------------------------------------------------------
# 1) Relay ordering: publish BEFORE checkpointing published_at.
# ---------------------------------------------------------------------------
class RelayStep(str, Enum):
    PUBLISH_TO_BROKER = "publish_to_broker"          # first
    GUARDED_CHECKPOINT = "guarded_checkpoint"        # then, under the fencing token


def relay_publish_order() -> tuple[RelayStep, RelayStep]:
    """The Relay publishes to the Broker FIRST, then guarded-checkpoints ``published_at``.

    If it crashes between the two, the row keeps ``published_at IS NULL`` and is retried
    -> at-least-once delivery. ``published_at`` is a DELIVERY checkpoint, never proof the
    Job executed or succeeded. The database lock is NOT held across Broker I/O.
    """
    return (RelayStep.PUBLISH_TO_BROKER, RelayStep.GUARDED_CHECKPOINT)


def published_at_null_meaning() -> str:
    """``published_at IS NULL`` proves only that NO Relay checkpoint was recorded. It is
    necessary evidence of an absent checkpoint but is NOT enough alone to decide whether
    execution occurred — that needs Job/Attempt/Event (and, after Day61, Provider/Result)
    facts."""
    return "no_relay_checkpoint_only"


# ---------------------------------------------------------------------------
# 2) Guarded claims (Relay claim + Worker authority) — shape, not execution proof.
# ---------------------------------------------------------------------------
class ClaimOutcome(str, Enum):
    WON = "won"
    LOST = "lost"


def classify_guarded_claim(rows_updated: int) -> ClaimOutcome:
    """A guarded ``UPDATE ... WHERE <guard> RETURNING`` either updates the row (WON) or
    not (LOST). Celery delivery is NOT execution authority; the PostgreSQL guarded claim
    is. Exactly one Worker wins ``UPDATE jobs SET status='running' ... WHERE
    status='queued' RETURNING``."""
    return ClaimOutcome.WON if rows_updated == 1 else ClaimOutcome.LOST


# ---------------------------------------------------------------------------
# 3) Duplicate / redelivery / expiry classification (post-claim / duplicate branch).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LeaseView:
    status: str                       # 'queued' | 'running' | terminal | 'pending_reconciliation'
    lease_owner: Optional[str]
    lease_expiry_epoch: Optional[int]
    has_external_evidence: bool       # provider_request_id OR provider_dispatch_started_at


class DeliveryDecision(str, Enum):
    TERMINAL_NOOP = "terminal_noop"                    # already succeeded/failed/cancelled
    NOOP_HEALTHY_LEASE = "noop_healthy_lease"          # dup while lease credibly active
    DEFER_TO_RECOVERY_SWEEP = "defer_to_recovery_sweep"  # worker-loss redelivery before expiry
    RECONCILE_ONLY = "reconcile_only"                  # expired running + external evidence
    SWEEP_REDISPATCH = "sweep_redispatch"              # expired running + NO external evidence


def classify_delivery(now_epoch: int, this_worker: str, view: LeaseView) -> DeliveryDecision:
    """Decide what an incoming (possibly duplicate) delivery should do.

    * A terminal Job (succeeded/failed/cancelled) -> TERMINAL_NOOP.
    * A duplicate while THIS Worker holds a credibly active lease -> NOOP (no Provider
      call, no second claim).
    * A redelivery to a DIFFERENT worker while the lease is still active (worker-loss only
      SUSPECTED) -> DEFER to the durable PostgreSQL recovery sweep.
    * An EXPIRED ``running`` lease is not a retry license: external evidence ->
      RECONCILE_ONLY (PENDING_RECONCILIATION, never a second Provider call); no evidence ->
      the sweeper may redispatch.
    """
    if view.status in TERMINAL_STATUSES:
        return DeliveryDecision.TERMINAL_NOOP
    if view.status == "running" and view.lease_owner is not None and lease_active(
        view.lease_expiry_epoch, now_epoch
    ):
        if view.lease_owner == this_worker:
            return DeliveryDecision.NOOP_HEALTHY_LEASE
        return DeliveryDecision.DEFER_TO_RECOVERY_SWEEP
    # Not active. Only an EXPIRED running lease is a recovery/reconcile case.
    if view.status == "running" and lease_expired(view.lease_expiry_epoch, now_epoch):
        return (
            DeliveryDecision.RECONCILE_ONLY
            if view.has_external_evidence
            else DeliveryDecision.SWEEP_REDISPATCH
        )
    # queued / pending_reconciliation / anything else -> the sweeper is NOT the authority.
    return DeliveryDecision.DEFER_TO_RECOVERY_SWEEP


# ---------------------------------------------------------------------------
# 4) Expired-lease recovery sweep result — ONLY a legitimately expired running Job.
# ---------------------------------------------------------------------------
class SweepResult(str, Enum):
    NO_OP = "no_op"                                    # not eligible (queued/terminal/active lease)
    RECONCILE_ONLY = "reconcile_only"                  # external evidence -> no requeue
    REQUEUED_WITH_REDISPATCH = "requeued_with_redispatch"  # atomic running->queued + 1 intent


def classify_recovery_sweep(view: LeaseView, now_epoch: int) -> SweepResult:
    """The durable sweeper recovers ONLY a legitimately EXPIRED ``running`` Job.

    * A ``queued`` Job is NEVER swept/redispatched (it is already awaiting delivery).
    * A terminal Job (succeeded/failed/cancelled) is a terminal NO-OP.
    * A ``running`` Job whose lease is still ACTIVE is not the sweeper's job yet.
    * An EXPIRED ``running`` Job with external evidence -> RECONCILE_ONLY
      (PENDING_RECONCILIATION, never a second Provider call).
    * An EXPIRED ``running`` Job with NO external evidence -> atomically ``running ->
      queued``, record a recovery audit Event, and write EXACTLY ONE new
      ``job.redispatch_requested`` Outbox intent.
    """
    if view.status != "running":
        return SweepResult.NO_OP
    if lease_active(view.lease_expiry_epoch, now_epoch):
        return SweepResult.NO_OP
    if view.has_external_evidence:
        return SweepResult.RECONCILE_ONLY
    return SweepResult.REQUEUED_WITH_REDISPATCH


# ---------------------------------------------------------------------------
# 5) Bounded early-ACK repair: idempotent id + eligibility predicate (release-filtered).
# ---------------------------------------------------------------------------
def repair_id(job_id: str, release_version: str, reason: str) -> str:
    """Deterministic idempotency key. Committing it to ``app.job_repair_history``
    (PRIMARY KEY) makes repair idempotent: a duplicate/concurrent repair for the same
    (job, release, reason) collides and applies exactly once, so exactly one new
    redispatch intent is written."""
    return f"repair:{job_id}:{release_version}:{reason}"


@dataclass(frozen=True)
class RepairCandidate:
    actual_release_version: str             # the candidate Job's REAL release/version
    within_time_window: bool
    status: str
    has_original_dispatch_checkpoint: bool  # the Day59 job.dispatch_requested was checkpointed
    has_attempts_or_external_evidence: bool
    has_conflict: bool
    deadline_contract_budget_valid: bool
    repair_already_applied: bool


def is_repair_eligible(c: RepairCandidate, affected_release_version: str) -> bool:
    """Bounded early-ACK repair eligibility.

    A bad early-ACK release is contained by rolling back the config FIRST; repair then
    selects a BOUNDED eligible set and re-verifies it inside the repair transaction. A Job
    is eligible ONLY if its ACTUAL release matches the explicitly-passed
    ``affected_release_version`` (a job from a DIFFERENT release is rejected even if every
    other condition holds) AND it is in the time window AND still ``queued`` AND its
    original dispatch Outbox was checkpointed AND it has NO attempts/external evidence AND
    no conflict AND a valid deadline/contract/budget AND the repair was not already
    applied. Repair writes a durable Outbox intent — never a direct Celery ``.delay()`` /
    ``apply_async()``.
    """
    return (
        c.actual_release_version == affected_release_version
        and c.within_time_window
        and c.status == "queued"
        and c.has_original_dispatch_checkpoint
        and not c.has_attempts_or_external_evidence
        and not c.has_conflict
        and c.deadline_contract_budget_valid
        and not c.repair_already_applied
    )


# ---------------------------------------------------------------------------
# 6) Readiness revision gate (Day60 app-factory expects the Day60 head revision).
# ---------------------------------------------------------------------------
def revision_ready(current_revision: Optional[str], expected_revision: str) -> bool:
    """A Day60 composition explicitly REQUIRES its expected revision. A ready process on
    the wrong revision must fail readiness (503)."""
    return current_revision == expected_revision


# ---------------------------------------------------------------------------
# 7) Repair IntegrityError classification — a true duplicate vs an unrelated failure.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RepairFact:
    """The committed repair facts re-read AFTER an IntegrityError, and the facts the current
    repair EXPECTED. Used to decide whether the conflict was a genuine duplicate of the same
    logical repair or an unrelated integrity failure. The linked-Outbox flags carry the
    JOINED semantics, not merely ``redispatch_outbox_event_id IS NOT NULL``:

    * ``has_linked_outbox``            — the FK is non-null AND a matching ``outbox_events`` row exists.
    * ``linked_outbox_job_matches``    — that Outbox row's ``job_id`` equals this Job.
    * ``linked_outbox_is_redispatch``  — that Outbox row's ``event_type`` is ``job.redispatch_requested``.
    """
    job_id: str
    release_version: str
    reason: str
    has_linked_outbox: bool
    linked_outbox_job_matches: bool
    linked_outbox_is_redispatch: bool


def classify_repair_integrity(existing: Optional[RepairFact], expected: RepairFact) -> str:
    """After an ``IntegrityError``, the runtime rolls back and RE-READS the committed
    ``job_repair_history`` row for ``repair_id`` JOINED to its linked ``outbox_events`` row in
    a FRESH transaction, then calls this.

    ``already_applied`` requires the FULL semantic match — same ``job_id`` / ``release_version``
    / ``reason``, AND a linked redispatch Outbox that (a) exists, (b) belongs to this Job, and
    (c) has ``event_type == 'job.redispatch_requested'``. A non-null FK alone is NOT enough.

    Anything else — no row, mismatched repair facts, a missing/foreign/wrong-type linked Outbox
    row — is ``"repair_failed"``: the integrity error was NOT a same-repair duplicate, so it
    MUST NOT be silently disguised as an idempotent success.
    """
    if existing is None:
        return "repair_failed"
    if (
        existing.job_id == expected.job_id
        and existing.release_version == expected.release_version
        and existing.reason == expected.reason
        and existing.has_linked_outbox
        and existing.linked_outbox_job_matches
        and existing.linked_outbox_is_redispatch
    ):
        return "already_applied"
    return "repair_failed"
