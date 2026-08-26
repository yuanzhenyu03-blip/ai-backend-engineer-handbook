"""Day76 classified recovery and cost-accounting decision model.

No function here performs a Provider call, durable write, repair, compensation,
or reconciliation.  The values returned are decisions/evidence that a real LLM
Runtime and Durable Store would have to enforce atomically.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Tuple

from provider_contract import (
    AttemptExecutionContract,
    CapabilityProfile,
    ProfileStatus,
)


class ExecutionCertainty(str, Enum):
    DEFINITELY_NOT_ACCEPTED = "DEFINITELY_NOT_ACCEPTED"
    TIMEOUT_UNKNOWN = "TIMEOUT_UNKNOWN"


class FailureClass(str, Enum):
    RATE_LIMITED = "RATE_LIMITED"
    TRANSPORT_BEFORE_DISPATCH = "TRANSPORT_BEFORE_DISPATCH"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    UNAUTHORIZED = "UNAUTHORIZED"
    CONTRACT_INCOMPATIBLE = "CONTRACT_INCOMPATIBLE"
    AUTH_OR_CONFIGURATION = "AUTH_OR_CONFIGURATION"


class RecoveryAction(str, Enum):
    FALLBACK_NEW_ATTEMPT = "FALLBACK_NEW_ATTEMPT"
    RECONCILE = "RECONCILE"
    REJECT = "REJECT"
    DISABLE_PATH = "DISABLE_PATH"
    FALLBACK_EXHAUSTED = "FALLBACK_EXHAUSTED"


@dataclass(frozen=True)
class FallbackPolicy:
    revision: str
    max_attempts: int
    budget_units: int
    allowed: Tuple[FailureClass, ...]


@dataclass(frozen=True)
class RecoveryDecision:
    source_attempt_id: str
    action: RecoveryAction
    reason: str
    policy_revision: str
    new_attempt_id: Optional[str] = None
    target_profile_id: Optional[str] = None


def plan_recovery(
    *,
    source: AttemptExecutionContract,
    failure: FailureClass,
    certainty: ExecutionCertainty,
    policy: FallbackPolicy,
    attempt_count: int,
    remaining_deadline_ms: int,
    job_cost_and_reservations: int,
    target_estimated_cost: int,
    target: Optional[CapabilityProfile],
    target_current_status: ProfileStatus,
    new_attempt_id: str,
) -> tuple[RecoveryDecision, Optional[AttemptExecutionContract]]:
    """Classify recovery before creating a different execution path."""

    if certainty is ExecutionCertainty.TIMEOUT_UNKNOWN:
        return RecoveryDecision(
            source.attempt_id,
            RecoveryAction.RECONCILE,
            "EXECUTION_UNKNOWN",
            policy.revision,
        ), None

    if failure in {FailureClass.UNAUTHORIZED, FailureClass.CONTRACT_INCOMPATIBLE}:
        return RecoveryDecision(
            source.attempt_id,
            RecoveryAction.REJECT,
            "BOUNDARY_REJECTION",
            policy.revision,
        ), None

    if failure is FailureClass.AUTH_OR_CONFIGURATION:
        return RecoveryDecision(
            source.attempt_id,
            RecoveryAction.DISABLE_PATH,
            "REPAIR_CONFIGURATION",
            policy.revision,
        ), None

    target_eligible = (
        target is not None
        and target_current_status is ProfileStatus.ACTIVE
        and target.supports(source.application_contract)
    )
    exhausted = (
        failure not in policy.allowed
        or not target_eligible
        or attempt_count >= policy.max_attempts
        or remaining_deadline_ms <= 0
        or job_cost_and_reservations + target_estimated_cost > policy.budget_units
    )
    if exhausted:
        return RecoveryDecision(
            source.attempt_id,
            RecoveryAction.FALLBACK_EXHAUSTED,
            "NO_COMPLIANT_FALLBACK",
            policy.revision,
        ), None

    assert target is not None  # established by target_eligible
    binding = AttemptExecutionContract.plan(
        new_attempt_id,
        source.job_id,
        target,
        source.application_contract,
    )
    return RecoveryDecision(
        source_attempt_id=source.attempt_id,
        action=RecoveryAction.FALLBACK_NEW_ATTEMPT,
        reason="CLASSIFIED_FALLBACK",
        policy_revision=policy.revision,
        new_attempt_id=new_attempt_id,
        target_profile_id=target.profile_id,
    ), binding


class CostStatus(str, Enum):
    RESERVED = "RESERVED"
    SETTLED = "SETTLED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"


@dataclass(frozen=True)
class AttemptCost:
    attempt_id: str
    pricing_revision: str
    estimate: int
    reservation: int
    actual: Optional[int] = None
    released: int = 0
    status: CostStatus = CostStatus.RESERVED


def mark_unknown(item: AttemptCost) -> AttemptCost:
    """Keep the reservation while actual usage remains unknown."""

    return replace(
        item,
        actual=None,
        released=0,
        status=CostStatus.PENDING_RECONCILIATION,
    )


def settle(item: AttemptCost, *, pricing_revision: str, actual: int) -> AttemptCost:
    """Settle against the Attempt-bound pricing revision."""

    if pricing_revision != item.pricing_revision:
        raise ValueError("pricing revision mismatch")
    if actual < 0 or actual > item.reservation:
        raise ValueError("invalid cost or explicit overage policy required")
    return replace(
        item,
        actual=actual,
        released=item.reservation - actual,
        status=CostStatus.SETTLED,
    )


class BatchItemCostStatus(str, Enum):
    PROVIDER_REPORTED = "PROVIDER_REPORTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class BatchItemCost:
    item_id: str
    units: Optional[int]
    status: BatchItemCostStatus


def record_batch_cost(
    item_ids: Tuple[str, ...],
    total_units: int,
    per_item: Optional[Tuple[Tuple[str, int], ...]] = None,
) -> Tuple[BatchItemCost, ...]:
    """Preserve unknown per-item allocation instead of inventing equal actuals."""

    if total_units < 0 or len(set(item_ids)) != len(item_ids):
        raise ValueError("invalid batch identity/total")
    if per_item is None:
        return tuple(
            BatchItemCost(item, None, BatchItemCostStatus.UNKNOWN)
            for item in item_ids
        )

    reported = dict(per_item)
    if (
        len(reported) != len(per_item)
        or set(reported) != set(item_ids)
        or any(units < 0 for units in reported.values())
        or sum(reported.values()) != total_units
    ):
        raise ValueError("per-item evidence mismatch")
    return tuple(
        BatchItemCost(item, reported[item], BatchItemCostStatus.PROVIDER_REPORTED)
        for item in item_ids
    )


@dataclass(frozen=True)
class IncidentRecoveryEvidence:
    stable_policy_active: bool
    bad_policy_stopped: bool
    bad_profile_quarantined: bool
    attempts_classified: bool
    unknowns_reconciling_or_resolved: bool
    costs_settled_or_reconciling: bool
    repairs_verified: bool
    compensations_verified: bool
    regression_tests_passed: bool


def may_close_incident(item: IncidentRecoveryEvidence) -> bool:
    """Rollback and tests alone cannot close an incident."""

    return all(item.__dict__.values())
