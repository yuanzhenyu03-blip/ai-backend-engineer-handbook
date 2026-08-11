"""Day60 — pure delivery/recovery decision logic (standard library only).

The DECISION CORE of the Day60 Relay + Worker + recovery boundary, separated from any
FastAPI/SQLAlchemy/Celery runtime so the rules can be unit-tested WITHOUT a database, a
broker, or Docker. Every function here is deterministic control flow over plain values.

Evidence tier: functions here are ``EXECUTED_LOCAL_RUNTIME`` when driven by
``test_day60_delivery_recovery_logic.py``. They prove the RULES only. They do NOT prove
real PostgreSQL ``FOR UPDATE SKIP LOCKED`` / guarded ``UPDATE ... RETURNING`` /
transaction / isolation, a real Redis/Celery broker, ACK timing, redelivery, or
Worker-kill — that is ``INTEGRATION_RUNTIME`` (see the Day60 design/runbook).

No secrets, URLs, passwords, tokens, or fixture ids live in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

REDISPATCH_EVENT_TYPE = "job.redispatch_requested"
DISPATCH_EVENT_TYPE = "job.dispatch_requested"


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
# 3) Duplicate / redelivery / expiry classification.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LeaseView:
    status: str                       # 'queued' | 'running' | terminal
    lease_owner: Optional[str]
    lease_expiry_epoch: Optional[int]
    has_external_evidence: bool       # provider_request_id OR provider_dispatch_started_at


class DeliveryDecision(str, Enum):
    NOOP_HEALTHY_LEASE = "noop_healthy_lease"          # dup while lease credibly active
    DEFER_TO_RECOVERY_SWEEP = "defer_to_recovery_sweep"  # worker-loss redelivery before expiry
    RECONCILE_ONLY = "reconcile_only"                  # expired + external evidence
    SWEEP_REDISPATCH = "sweep_redispatch"              # expired + NO external evidence


def classify_delivery(now_epoch: int, this_worker: str, view: LeaseView) -> DeliveryDecision:
    """Decide what an incoming (possibly duplicate) delivery should do.

    * A duplicate while the FIRST Worker holds a credibly active lease -> NOOP (no Provider
      call, no second claim).
    * A redelivery arriving to a DIFFERENT worker while the lease is still unexpired
      (worker-loss suspected) -> DEFER to the durable PostgreSQL recovery sweep, NOT a
      Celery-retry execution authority.
    * An EXPIRED lease is not a retry license: if an external call MAY have been sent
      (evidence present) -> RECONCILE_ONLY (move to PENDING_RECONCILIATION, never a second
      Provider call). With NO external evidence -> the sweeper may redispatch.
    """
    lease_active = (
        view.status == "running"
        and view.lease_owner is not None
        and view.lease_expiry_epoch is not None
        and view.lease_expiry_epoch >= now_epoch
    )
    if lease_active:
        if view.lease_owner == this_worker:
            return DeliveryDecision.NOOP_HEALTHY_LEASE
        # A different, still-valid owner: worker-loss is only SUSPECTED; do not seize.
        return DeliveryDecision.DEFER_TO_RECOVERY_SWEEP
    # Lease not active (expired or absent):
    if view.has_external_evidence:
        return DeliveryDecision.RECONCILE_ONLY
    return DeliveryDecision.SWEEP_REDISPATCH


# ---------------------------------------------------------------------------
# 4) Expired-lease recovery sweep result (running -> queued + one redispatch intent).
# ---------------------------------------------------------------------------
class SweepResult(str, Enum):
    RECONCILE_ONLY = "reconcile_only"                  # external evidence -> no requeue
    REQUEUED_WITH_REDISPATCH = "requeued_with_redispatch"  # atomic running->queued + 1 intent


def classify_recovery_sweep(view: LeaseView, now_epoch: int) -> SweepResult:
    """The durable sweeper handles an EXPIRED lease. With external evidence it is
    RECONCILE_ONLY (PENDING_RECONCILIATION, no second call). Without it, it atomically
    moves ``running -> queued``, records a recovery audit event, and writes EXACTLY ONE
    new ``job.redispatch_requested`` Outbox intent for the Relay to deliver."""
    expired = view.lease_expiry_epoch is None or view.lease_expiry_epoch < now_epoch
    if not expired:
        # Not the sweeper's job yet; the lease is still active.
        return SweepResult.RECONCILE_ONLY if view.has_external_evidence else SweepResult.RECONCILE_ONLY
    if view.has_external_evidence:
        return SweepResult.RECONCILE_ONLY
    return SweepResult.REQUEUED_WITH_REDISPATCH


# ---------------------------------------------------------------------------
# 5) Bounded early-ACK repair: idempotent id + eligibility predicate.
# ---------------------------------------------------------------------------
def repair_id(job_id: str, release_version: str, reason: str) -> str:
    """Deterministic idempotency key. Committing it to ``app.job_repair_history``
    (PRIMARY KEY) makes repair idempotent: a duplicate/concurrent repair for the same
    (job, release, reason) collides and applies exactly once, so exactly one new
    redispatch intent is written."""
    return f"repair:{job_id}:{release_version}:{reason}"


@dataclass(frozen=True)
class RepairCandidate:
    bad_release_version: str
    within_time_window: bool
    status: str
    has_original_dispatch_checkpoint: bool  # the Day59 job.dispatch_requested was checkpointed
    has_attempts_or_external_evidence: bool
    has_conflict: bool
    deadline_contract_budget_valid: bool
    repair_already_applied: bool


def is_repair_eligible(c: RepairCandidate) -> bool:
    """A bad early-ACK release is contained by rolling back the config FIRST; repair then
    selects a BOUNDED eligible set and re-verifies it inside the repair transaction. A Job
    is eligible only if it is from the bad release AND in the time window AND still queued
    AND its original dispatch Outbox was checkpointed AND it has NO attempts/external
    evidence AND no conflict AND a valid deadline/contract/budget AND the repair was not
    already applied. Repair writes a durable Outbox intent — never a direct Celery
    ``.delay()`` (which publishes immediately but creates no transactional, replayable,
    auditable business intent)."""
    return (
        c.within_time_window
        and c.status == "queued"
        and c.has_original_dispatch_checkpoint
        and not c.has_attempts_or_external_evidence
        and not c.has_conflict
        and c.deadline_contract_budget_valid
        and not c.repair_already_applied
    )


# ---------------------------------------------------------------------------
# 6) Readiness revision gate (Day60 app-factory expects 0009).
# ---------------------------------------------------------------------------
def revision_ready(current_revision: Optional[str], expected_revision: str) -> bool:
    """A Day60 composition explicitly REQUIRES its expected revision. The Day59 app
    expected exactly 0008 and correctly returns 503 once the database is at 0009; the
    Day60 app expects 0009. A ready process on the wrong revision must fail readiness."""
    return current_revision == expected_revision
