"""Day82 durable Agent Job recovery contract and in-memory teaching store.

The types model facts that a production PostgreSQL store would persist. The
store itself is process-local and proves only deterministic decision/apply
behaviour. It is not evidence of database durability, transaction isolation,
queue delivery, cross-process fencing, or real crash recovery.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import threading
from typing import Optional

from agent_state_machine import AgentState, TERMINAL_STATES


class ExternalCertainty(str, Enum):
    DEFINITELY_NOT_DISPATCHED = "DEFINITELY_NOT_DISPATCHED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    VERIFIED_TERMINAL = "VERIFIED_TERMINAL"


class DurableRecoveryDecision(str, Enum):
    RESUME = "RESUME"
    RETRY = "RETRY"
    REPLAN = "REPLAN"
    RECONCILE = "RECONCILE"
    REPAIR = "REPAIR"
    SETTLE = "SETTLE"
    COMPENSATE = "COMPENSATE"
    ESCALATE = "ESCALATE"
    BLOCKED = "BLOCKED"
    TERMINAL_NOOP = "TERMINAL_NOOP"
    REJECT_STALE = "REJECT_STALE"


class ReservationStatus(str, Enum):
    HELD = "HELD"
    SETTLED = "SETTLED"
    RELEASED = "RELEASED"


class ReservationAction(str, Enum):
    NO_CHANGE = "NO_CHANGE"
    KEEP_HELD = "KEEP_HELD"
    RELEASE = "RELEASE"
    SETTLE_VERIFIED = "SETTLE_VERIFIED"


class OutboxAction(str, Enum):
    NONE = "NONE"
    CREATE_RECOVERY_INTENT = "CREATE_RECOVERY_INTENT"
    PUBLISH_ORIGINAL_INTENT = "PUBLISH_ORIGINAL_INTENT"


class RecoveryApplyStatus(str, Enum):
    APPLIED = "APPLIED"
    DUPLICATE_REPLAY = "DUPLICATE_REPLAY"
    NOOP_STALE = "NOOP_STALE"
    NOOP_TERMINAL = "NOOP_TERMINAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DeliveryStatus(str, Enum):
    NEW = "NEW"
    DUPLICATE = "DUPLICATE"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


@dataclass(frozen=True)
class ExecutionBindings:
    controller_release: str
    prompt_binding: str
    provider_binding: str
    tool_binding: str
    policy_binding: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.controller_release,
                self.prompt_binding,
                self.provider_binding,
                self.tool_binding,
                self.policy_binding,
            )
        ):
            raise ValueError("all execution bindings are required")


@dataclass(frozen=True)
class DurableCheckpoint:
    tenant_id: str
    job_id: str
    step_id: str
    attempt_id: str
    checkpoint_id: str
    checkpoint_version: int
    authoritative_state: AgentState
    state_version: int
    fence_token: int
    lease_generation: int
    bindings: ExecutionBindings
    progress_fingerprint: str
    verified_observation_ids: tuple[str, ...]
    reservation_ids: tuple[str, ...]
    pending_reconciliation_ids: tuple[str, ...]
    previous_checkpoint_id: Optional[str] = None

    def __post_init__(self) -> None:
        identities = (
            self.tenant_id,
            self.job_id,
            self.step_id,
            self.attempt_id,
            self.checkpoint_id,
            self.progress_fingerprint,
        )
        if not all(identities):
            raise ValueError("checkpoint identity and progress are required")
        versions = (
            self.checkpoint_version,
            self.state_version,
            self.fence_token,
            self.lease_generation,
        )
        if any(value < 0 for value in versions):
            raise ValueError("checkpoint versions must be non-negative")
        if len(set(self.verified_observation_ids)) != len(
            self.verified_observation_ids
        ):
            raise ValueError("verified observation identities must be unique")


@dataclass(frozen=True)
class ReservationRecord:
    reservation_id: str
    attempt_id: str
    reserved_units: int
    status: ReservationStatus = ReservationStatus.HELD
    settled_units: Optional[int] = None
    released_units: int = 0

    def __post_init__(self) -> None:
        if not self.reservation_id or not self.attempt_id:
            raise ValueError("reservation identity is required")
        if self.reserved_units < 0 or self.released_units < 0:
            raise ValueError("reservation units must be non-negative")
        if self.settled_units is not None and not (
            0 <= self.settled_units <= self.reserved_units
        ):
            raise ValueError("settled units must fit reservation")


@dataclass(frozen=True)
class OutboxIntent:
    event_id: str
    job_id: str
    step_id: str
    attempt_id: str
    event_type: str
    published_at_epoch_ms: Optional[int] = None


@dataclass(frozen=True)
class RecoveryOperation:
    recovery_id: str
    source_attempt_id: str
    recovery_generation: int
    attempts_used: int
    attempt_limit: int
    deadline_epoch_ms: int
    last_evidence_fingerprint: Optional[str]

    @property
    def automatic_recovery_available(self) -> bool:
        return self.attempts_used < self.attempt_limit


@dataclass(frozen=True)
class DurableAgentJobRecord:
    tenant_id: str
    job_id: str
    current_step_id: str
    current_attempt_id: str
    state: AgentState
    state_version: int
    fence_token: int
    lease_owner: Optional[str]
    lease_expiry_epoch_ms: Optional[int]
    lease_generation: int
    current_checkpoint: DurableCheckpoint
    reservations: tuple[ReservationRecord, ...]
    recovery_operations: tuple[RecoveryOperation, ...] = ()
    outbox_intents: tuple[OutboxIntent, ...] = ()
    audit_events: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecoveryRequest:
    recovery_id: str
    tenant_id: str
    job_id: str
    step_id: str
    attempt_id: str
    checkpoint_id: str
    expected_state: AgentState
    expected_state_version: int
    expected_fence_token: int
    now_epoch_ms: int
    external_certainty: ExternalCertainty
    current_authorization: bool
    original_binding_currently_allowed: bool
    internal_repair_required: bool = False
    verified_effect_unwanted: bool = False
    verified_usage_units: Optional[int] = None


@dataclass(frozen=True)
class DurableRecoveryCandidate:
    phase: str
    status: str
    recovery_id: str
    tenant_id: str
    job_id: str
    step_id: str
    attempt_id: str
    checkpoint_id: str
    expected_state: AgentState
    expected_state_version: int
    expected_fence_token: int
    decision: DurableRecoveryDecision
    recovery_reason: str
    next_state: AgentState
    reservation_action: ReservationAction
    outbox_action: OutboxAction
    evidence: tuple[str, ...]
    verified_usage_units: Optional[int] = None


def _candidate(
    request: RecoveryRequest,
    *,
    decision: DurableRecoveryDecision,
    status: str,
    reason: str,
    next_state: AgentState,
    reservation_action: ReservationAction = ReservationAction.NO_CHANGE,
    outbox_action: OutboxAction = OutboxAction.NONE,
    evidence: tuple[str, ...] = (),
) -> DurableRecoveryCandidate:
    return DurableRecoveryCandidate(
        phase="DURABLE_RECOVERY",
        status=status,
        recovery_id=request.recovery_id,
        tenant_id=request.tenant_id,
        job_id=request.job_id,
        step_id=request.step_id,
        attempt_id=request.attempt_id,
        checkpoint_id=request.checkpoint_id,
        expected_state=request.expected_state,
        expected_state_version=request.expected_state_version,
        expected_fence_token=request.expected_fence_token,
        decision=decision,
        recovery_reason=reason,
        next_state=next_state,
        reservation_action=reservation_action,
        outbox_action=outbox_action,
        evidence=evidence,
        verified_usage_units=request.verified_usage_units,
    )


def decide_durable_recovery(
    record: DurableAgentJobRecord,
    recovery: RecoveryOperation,
    request: RecoveryRequest,
) -> DurableRecoveryCandidate:
    """Return a deterministic recovery candidate with zero side effects."""

    checkpoint = record.current_checkpoint
    requested_identity = (
        request.tenant_id,
        request.job_id,
        request.step_id,
        request.attempt_id,
        request.checkpoint_id,
    )
    current_identity = (
        record.tenant_id,
        record.job_id,
        record.current_step_id,
        record.current_attempt_id,
        checkpoint.checkpoint_id,
    )
    if requested_identity != current_identity:
        return _candidate(
            request,
            decision=DurableRecoveryDecision.REJECT_STALE,
            status="CHECKPOINT_IDENTITY_MISMATCH",
            reason="recovery identity does not match durable current identity",
            next_state=record.state,
            evidence=("reload_authoritative_record",),
        )
    if (
        request.expected_state is not record.state
        or request.expected_state_version != record.state_version
        or request.expected_fence_token != record.fence_token
    ):
        return _candidate(
            request,
            decision=DurableRecoveryDecision.REJECT_STALE,
            status="STALE_RECOVERY_SNAPSHOT",
            reason="state, version, or fence advanced",
            next_state=record.state,
            evidence=("conditional_apply_would_affect_zero_rows",),
        )
    if (
        not recovery.automatic_recovery_available
        or request.now_epoch_ms >= recovery.deadline_epoch_ms
    ):
        return _candidate(
            request,
            decision=DurableRecoveryDecision.ESCALATE,
            status="BOUNDED_RECOVERY_EXHAUSTED",
            reason="automatic recovery limit or deadline reached",
            next_state=(
                record.state
                if record.state in TERMINAL_STATES
                else AgentState.PENDING_RECONCILIATION
            ),
            reservation_action=ReservationAction.KEEP_HELD,
            evidence=("manual_or_operator_owned_follow_up_required",),
        )
    if request.external_certainty is ExternalCertainty.OUTCOME_UNKNOWN:
        return _candidate(
            request,
            decision=DurableRecoveryDecision.RECONCILE,
            status="EXTERNAL_OUTCOME_UNKNOWN",
            reason="query and classify the original operation identity",
            next_state=(
                record.state
                if record.state in TERMINAL_STATES
                else AgentState.PENDING_RECONCILIATION
            ),
            reservation_action=ReservationAction.KEEP_HELD,
            outbox_action=OutboxAction.CREATE_RECOVERY_INTENT,
            evidence=(
                "original_attempt_identity_preserved",
                "unknown_usage_is_not_zero",
            ),
        )
    if request.internal_repair_required:
        return _candidate(
            request,
            decision=DurableRecoveryDecision.REPAIR,
            status="INTERNAL_DURABLE_REFERENCE_REPAIR",
            reason="repair internal truth without changing history",
            next_state=record.state,
            evidence=("append_only_repair_audit_required",),
        )
    if request.verified_effect_unwanted:
        if not request.current_authorization:
            return _candidate(
                request,
                decision=DurableRecoveryDecision.BLOCKED,
                status="COMPENSATION_NOT_AUTHORIZED",
                reason="new external effect requires current authorization",
                next_state=record.state,
                evidence=("verified_effect_remains_historical_fact",),
            )
        return _candidate(
            request,
            decision=DurableRecoveryDecision.COMPENSATE,
            status="COMPENSATION_CANDIDATE",
            reason="create a new operation for the unwanted verified effect",
            next_state=record.state,
            outbox_action=OutboxAction.CREATE_RECOVERY_INTENT,
            evidence=("source_attempt_not_rewritten",),
        )
    if request.verified_usage_units is not None:
        return _candidate(
            request,
            decision=DurableRecoveryDecision.SETTLE,
            status="VERIFIED_USAGE_SETTLEMENT",
            reason="settle actual usage and release unused capacity",
            next_state=record.state,
            reservation_action=ReservationAction.SETTLE_VERIFIED,
            evidence=("verified_usage_evidence",),
        )
    if record.state in TERMINAL_STATES:
        return _candidate(
            request,
            decision=DurableRecoveryDecision.TERMINAL_NOOP,
            status="ALREADY_TERMINAL",
            reason="terminal Job cannot be reopened by recovery",
            next_state=record.state,
            evidence=("terminal_history_preserved",),
        )
    if not request.original_binding_currently_allowed:
        if not request.current_authorization:
            return _candidate(
                request,
                decision=DurableRecoveryDecision.BLOCKED,
                status="CURRENT_AUTHORIZATION_REVOKED",
                reason="old binding is preserved and new planning is blocked",
                next_state=record.state,
                reservation_action=ReservationAction.RELEASE,
                evidence=("old_binding_not_rewritten",),
            )
        return _candidate(
            request,
            decision=DurableRecoveryDecision.REPLAN,
            status="CURRENT_BINDING_REPLAN_REQUIRED",
            reason="old binding is no longer valid for new execution",
            next_state=AgentState.WAITING,
            reservation_action=ReservationAction.RELEASE,
            outbox_action=OutboxAction.CREATE_RECOVERY_INTENT,
            evidence=("old_binding_not_rewritten",),
        )
    if request.external_certainty is (
        ExternalCertainty.DEFINITELY_NOT_DISPATCHED
    ):
        if not request.current_authorization:
            return _candidate(
                request,
                decision=DurableRecoveryDecision.BLOCKED,
                status="CURRENT_AUTHORIZATION_REVOKED",
                reason="Retry cannot bypass current authorization",
                next_state=record.state,
                reservation_action=ReservationAction.RELEASE,
            )
        return _candidate(
            request,
            decision=DurableRecoveryDecision.RETRY,
            status="SAFE_NEW_ATTEMPT_CANDIDATE",
            reason="original execution is proven not dispatched",
            next_state=AgentState.RUNNING,
            reservation_action=ReservationAction.RELEASE,
            outbox_action=OutboxAction.CREATE_RECOVERY_INTENT,
            evidence=("new_attempt_identity_required",),
        )
    return _candidate(
        request,
        decision=DurableRecoveryDecision.RESUME,
        status="SAFE_RESUME_CANDIDATE",
        reason="continue the same identity from committed facts",
        next_state=record.state,
        evidence=("immutable_execution_bindings_preserved",),
    )


def _next_checkpoint_id(checkpoint: DurableCheckpoint, recovery_id: str) -> str:
    material = "\x1f".join(
        (checkpoint.checkpoint_id, str(checkpoint.checkpoint_version), recovery_id)
    )
    return "checkpoint-" + hashlib.sha256(
        material.encode("utf-8")
    ).hexdigest()[:20]


class InMemoryDurableAgentJobStore:
    """Atomic in-process model; not a durable or cross-process store."""

    def __init__(self, record: DurableAgentJobRecord) -> None:
        self.record = record
        self._applied_recovery_ids: set[str] = set()
        self._lock = threading.RLock()

    def apply(
        self, candidate: DurableRecoveryCandidate
    ) -> RecoveryApplyStatus:
        with self._lock:
            current = self.record
            if candidate.recovery_id in self._applied_recovery_ids:
                return RecoveryApplyStatus.DUPLICATE_REPLAY
            if (
                candidate.tenant_id != current.tenant_id
                or candidate.job_id != current.job_id
                or candidate.step_id != current.current_step_id
                or candidate.attempt_id != current.current_attempt_id
                or candidate.checkpoint_id
                != current.current_checkpoint.checkpoint_id
                or candidate.expected_state is not current.state
                or candidate.expected_state_version != current.state_version
                or candidate.expected_fence_token != current.fence_token
            ):
                return RecoveryApplyStatus.NOOP_STALE
            terminal_allowed = {
                DurableRecoveryDecision.RECONCILE,
                DurableRecoveryDecision.REPAIR,
                DurableRecoveryDecision.SETTLE,
                DurableRecoveryDecision.COMPENSATE,
                DurableRecoveryDecision.ESCALATE,
            }
            if (
                current.state in TERMINAL_STATES
                and candidate.decision not in terminal_allowed
            ):
                return RecoveryApplyStatus.NOOP_TERMINAL
            if candidate.decision in {
                DurableRecoveryDecision.REJECT_STALE,
                DurableRecoveryDecision.TERMINAL_NOOP,
            }:
                return RecoveryApplyStatus.NOT_APPLICABLE
            if (
                candidate.decision is DurableRecoveryDecision.BLOCKED
                and candidate.reservation_action is ReservationAction.NO_CHANGE
                and candidate.outbox_action is OutboxAction.NONE
            ):
                return RecoveryApplyStatus.NOT_APPLICABLE

            reservations = list(current.reservations)
            for index, reservation in enumerate(reservations):
                if reservation.attempt_id != candidate.attempt_id:
                    continue
                if candidate.reservation_action is ReservationAction.RELEASE:
                    reservations[index] = replace(
                        reservation,
                        status=ReservationStatus.RELEASED,
                        released_units=reservation.reserved_units,
                    )
                elif candidate.reservation_action is (
                    ReservationAction.SETTLE_VERIFIED
                ):
                    actual = candidate.verified_usage_units
                    if actual is None or not 0 <= actual <= reservation.reserved_units:
                        raise ValueError("verified usage does not fit reservation")
                    reservations[index] = replace(
                        reservation,
                        status=ReservationStatus.SETTLED,
                        settled_units=actual,
                        released_units=reservation.reserved_units - actual,
                    )

            event_intents = current.outbox_intents
            if candidate.outbox_action is OutboxAction.CREATE_RECOVERY_INTENT:
                event_intents += (
                    OutboxIntent(
                        event_id=f"recovery:{candidate.recovery_id}",
                        job_id=current.job_id,
                        step_id=current.current_step_id,
                        attempt_id=current.current_attempt_id,
                        event_type=candidate.decision.value,
                    ),
                )

            checkpoint = current.current_checkpoint
            next_checkpoint = replace(
                checkpoint,
                checkpoint_id=_next_checkpoint_id(
                    checkpoint, candidate.recovery_id
                ),
                checkpoint_version=checkpoint.checkpoint_version + 1,
                authoritative_state=candidate.next_state,
                state_version=current.state_version + 1,
                fence_token=current.fence_token + 1,
                previous_checkpoint_id=checkpoint.checkpoint_id,
            )
            operation = RecoveryOperation(
                recovery_id=candidate.recovery_id,
                source_attempt_id=current.current_attempt_id,
                recovery_generation=current.lease_generation,
                attempts_used=1,
                attempt_limit=1,
                deadline_epoch_ms=0,
                last_evidence_fingerprint=hashlib.sha256(
                    "\x1f".join(candidate.evidence).encode("utf-8")
                ).hexdigest(),
            )
            self.record = replace(
                current,
                state=candidate.next_state,
                state_version=current.state_version + 1,
                fence_token=current.fence_token + 1,
                current_checkpoint=next_checkpoint,
                reservations=tuple(reservations),
                recovery_operations=current.recovery_operations + (operation,),
                outbox_intents=event_intents,
                audit_events=current.audit_events
                + (f"recovery_applied:{candidate.recovery_id}",),
            )
            self._applied_recovery_ids.add(candidate.recovery_id)
            return RecoveryApplyStatus.APPLIED

    def take_over_expired_lease(
        self, *, worker_id: str, now_epoch_ms: int
    ) -> bool:
        with self._lock:
            current = self.record
            if (
                current.lease_expiry_epoch_ms is None
                or current.lease_expiry_epoch_ms > now_epoch_ms
                or current.state in TERMINAL_STATES
            ):
                return False
            self.record = replace(
                current,
                lease_owner=worker_id,
                lease_expiry_epoch_ms=None,
                lease_generation=current.lease_generation + 1,
                fence_token=current.fence_token + 1,
                audit_events=current.audit_events
                + (f"lease_taken_over:{worker_id}",),
            )
            return True

    def unpublished_outbox_intents(self) -> tuple[OutboxIntent, ...]:
        """Rescan committed intents whose publication timestamp is null."""

        with self._lock:
            return tuple(
                intent
                for intent in self.record.outbox_intents
                if intent.published_at_epoch_ms is None
            )

    def accept_result(
        self,
        *,
        worker_id: str,
        result_fence_token: int,
        evidence_id: str,
    ) -> bool:
        """Return write authority; always retain the evidence reference."""

        with self._lock:
            current = self.record
            authorized = (
                current.lease_owner == worker_id
                and current.fence_token == result_fence_token
                and current.state not in TERMINAL_STATES
            )
            self.record = replace(
                current,
                audit_events=current.audit_events
                + (f"late_or_current_result:{evidence_id}",),
            )
            return authorized


class InMemoryOutboxConsumerGuard:
    """Models delivery dedupe only; not a real Broker or durable Consumer."""

    def __init__(self) -> None:
        self._events: dict[str, tuple[str, str, str]] = {}

    def accept(self, intent: OutboxIntent) -> DeliveryStatus:
        identity = (intent.job_id, intent.step_id, intent.attempt_id)
        existing = self._events.get(intent.event_id)
        if existing is None:
            self._events[intent.event_id] = identity
            return DeliveryStatus.NEW
        if existing == identity:
            return DeliveryStatus.DUPLICATE
        return DeliveryStatus.IDENTITY_CONFLICT
