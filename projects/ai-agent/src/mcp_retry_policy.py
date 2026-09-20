"""Pure, bounded Day93 retry policy for remote MCP attempts."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, replace
from enum import Enum
from threading import Lock

from mcp_client_transport import DispatchCertainty
from mcp_remote_lifecycle import (
    ExecutionCertainty,
    FailureEvidence,
    FailureKind,
    FailurePhase,
)


class RetryDecisionKind(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    POSSIBLE_DISPATCH = "POSSIBLE_DISPATCH"
    POSSIBLE_EXECUTION = "POSSIBLE_EXECUTION"
    CALLER_INTENT_INACTIVE = "CALLER_INTENT_INACTIVE"
    FAILURE_NOT_RETRYABLE = "FAILURE_NOT_RETRYABLE"
    RETRY_BUDGET_EXHAUSTED = "RETRY_BUDGET_EXHAUSTED"
    DEADLINE_EXHAUSTED = "DEADLINE_EXHAUSTED"
    AUTHORIZATION_NOT_CURRENT = "AUTHORIZATION_NOT_CURRENT"
    CAPACITY_NOT_ADMITTED = "CAPACITY_NOT_ADMITTED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"


@dataclass(frozen=True)
class RetryContext:
    now: float
    deadline: float
    retries_used: int
    max_retries: int
    caller_intent_active: bool
    authorization_current: bool
    capacity_admitted: bool
    circuit_allows_request: bool

    def __post_init__(self) -> None:
        if not math.isfinite(self.now) or not math.isfinite(self.deadline):
            raise ValueError("retry clock values must be finite")
        if self.retries_used < 0 or self.max_retries < 0:
            raise ValueError("retry counts must be non-negative")


@dataclass(frozen=True)
class RetryDecision:
    kind: RetryDecisionKind
    operation_id: str
    idempotency_key: str
    next_attempt_number: int | None = None
    delay_seconds: float | None = None

    @property
    def eligible(self) -> bool:
        return self.kind is RetryDecisionKind.ELIGIBLE


@dataclass(frozen=True)
class RetryAttemptPlan:
    """A new protocol attempt under the same application operation."""

    operation_id: str
    idempotency_key: str
    protocol_request_id: str | int
    attempt_number: int
    delay_seconds: float
    transport_generation: int | None = None


class RetryDispatchDecisionKind(str, Enum):
    ADMITTED = "ADMITTED"
    CALLER_INTENT_INACTIVE = "CALLER_INTENT_INACTIVE"
    DEADLINE_EXHAUSTED = "DEADLINE_EXHAUSTED"
    AUTHORIZATION_NOT_CURRENT = "AUTHORIZATION_NOT_CURRENT"
    CAPACITY_NOT_ADMITTED = "CAPACITY_NOT_ADMITTED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"


@dataclass(frozen=True)
class RetryDispatchContext:
    """Fresh application facts read after backoff, immediately pre-dispatch."""

    now: float
    deadline: float
    caller_intent_active: bool
    authorization_current: bool
    capacity_admitted: bool
    circuit_allows_request: bool
    minimum_attempt_window_seconds: float = 0.05

    def __post_init__(self) -> None:
        if not math.isfinite(self.now) or not math.isfinite(self.deadline):
            raise ValueError("dispatch clock values must be finite")
        if self.minimum_attempt_window_seconds < 0:
            raise ValueError("minimum attempt window must be non-negative")


@dataclass(frozen=True)
class RetryDispatchDecision:
    kind: RetryDispatchDecisionKind
    attempt: RetryAttemptPlan
    transport_calls: int = 0

    @property
    def admitted(self) -> bool:
        return self.kind is RetryDispatchDecisionKind.ADMITTED


def admit_retry_dispatch(
    attempt: RetryAttemptPlan,
    context: RetryDispatchContext,
) -> RetryDispatchDecision:
    """Recheck volatile gates after backoff; this function never dispatches."""

    if not context.caller_intent_active:
        kind = RetryDispatchDecisionKind.CALLER_INTENT_INACTIVE
    elif (
        context.now + context.minimum_attempt_window_seconds
        > context.deadline
    ):
        kind = RetryDispatchDecisionKind.DEADLINE_EXHAUSTED
    elif not context.authorization_current:
        kind = RetryDispatchDecisionKind.AUTHORIZATION_NOT_CURRENT
    elif not context.capacity_admitted:
        kind = RetryDispatchDecisionKind.CAPACITY_NOT_ADMITTED
    elif not context.circuit_allows_request:
        kind = RetryDispatchDecisionKind.CIRCUIT_OPEN
    else:
        kind = RetryDispatchDecisionKind.ADMITTED
    return RetryDispatchDecision(kind, attempt)


class RetryDispatchRecordState(str, Enum):
    READY_FOR_DISPATCH = "READY_FOR_DISPATCH"
    READY_FOR_RETRY = "READY_FOR_RETRY"
    DISPATCH_STARTED = "DISPATCH_STARTED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class RetryDispatchRecord:
    operation_id: str
    idempotency_key: str
    state: RetryDispatchRecordState
    version: int
    attempt_number: int
    protocol_request_id: str | int | None
    tenant_id: str | None = None
    resource_id: str | None = None
    tool_name: str | None = None
    fence_token: int = 0
    transport_generation: int | None = None
    external_object_id: str | None = None


class RetryDispatchClaimOutcome(str, Enum):
    CLAIMED = "CLAIMED"
    NOT_ADMITTED = "NOT_ADMITTED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    STATE_CONFLICT = "STATE_CONFLICT"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    FENCE_CONFLICT = "FENCE_CONFLICT"
    ATTEMPT_SEQUENCE_CONFLICT = "ATTEMPT_SEQUENCE_CONFLICT"
    TRANSPORT_GENERATION_REQUIRED = "TRANSPORT_GENERATION_REQUIRED"


@dataclass(frozen=True)
class RetryDispatchClaim:
    outcome: RetryDispatchClaimOutcome
    record: RetryDispatchRecord | None = None
    durable_transition: bool = False
    transport_calls: int = 0

    @property
    def claimed(self) -> bool:
        return self.outcome is RetryDispatchClaimOutcome.CLAIMED


class InMemoryRetryDispatchStore:
    """Teaching equivalent of conditional UPDATE ... RETURNING."""

    def __init__(self) -> None:
        self._records: dict[str, RetryDispatchRecord] = {}
        self._lock = Lock()

    def add_retryable(
        self,
        evidence: FailureEvidence,
        *,
        tenant_id: str | None = None,
        resource_id: str | None = None,
        tool_name: str | None = None,
        version: int = 1,
        fence_token: int = 0,
    ) -> None:
        if (
            evidence.execution_certainty
            is not ExecutionCertainty.PROVEN_NOT_EXECUTED
        ):
            raise ValueError("only proven-not-executed attempts can retry")
        supplied_binding = (tenant_id, resource_id, tool_name)
        if any(value is not None for value in supplied_binding) and not all(
            value for value in supplied_binding
        ):
            raise ValueError("retryable operation binding must be complete")
        if version < 0 or fence_token < 0:
            raise ValueError("retryable version and fence must be non-negative")
        with self._lock:
            if evidence.operation_id in self._records:
                raise ValueError("operation is already registered")
            self._records[evidence.operation_id] = RetryDispatchRecord(
                evidence.operation_id,
                evidence.idempotency_key,
                RetryDispatchRecordState.READY_FOR_RETRY,
                version=version,
                attempt_number=evidence.attempt_number,
                protocol_request_id=evidence.protocol_request_id,
                tenant_id=tenant_id,
                resource_id=resource_id,
                tool_name=tool_name,
                fence_token=fence_token,
            )

    def add_ready_operation(
        self,
        *,
        operation_id: str,
        idempotency_key: str,
        tenant_id: str,
        resource_id: str,
        tool_name: str,
        version: int,
        fence_token: int,
        previous_attempt_number: int = 0,
    ) -> None:
        """Register an initial Day94 operation without duplicating claim logic."""

        if not all(
            (operation_id, idempotency_key, tenant_id, resource_id, tool_name)
        ):
            raise ValueError("ready operation identity must be complete")
        if version < 0 or fence_token < 0 or previous_attempt_number < 0:
            raise ValueError("ready operation counters must be non-negative")
        with self._lock:
            if operation_id in self._records:
                raise ValueError("operation is already registered")
            self._records[operation_id] = RetryDispatchRecord(
                operation_id=operation_id,
                idempotency_key=idempotency_key,
                state=RetryDispatchRecordState.READY_FOR_DISPATCH,
                version=version,
                attempt_number=previous_attempt_number,
                protocol_request_id=None,
                tenant_id=tenant_id,
                resource_id=resource_id,
                tool_name=tool_name,
                fence_token=fence_token,
            )

    def read(self, operation_id: str) -> RetryDispatchRecord | None:
        with self._lock:
            return self._records.get(operation_id)

    def claim_dispatch(
        self,
        dispatch: RetryDispatchDecision,
        *,
        expected_version: int,
        expected_state: RetryDispatchRecordState = (
            RetryDispatchRecordState.READY_FOR_RETRY
        ),
        expected_fence: int | None = None,
        new_fence: int | None = None,
        tenant_id: str | None = None,
        resource_id: str | None = None,
        tool_name: str | None = None,
    ) -> RetryDispatchClaim:
        """Persist DISPATCH_STARTED before the winner may call transport."""

        if not dispatch.admitted:
            return RetryDispatchClaim(RetryDispatchClaimOutcome.NOT_ADMITTED)
        attempt = dispatch.attempt
        with self._lock:
            current = self._records.get(attempt.operation_id)
            if (
                current is None
                or current.idempotency_key != attempt.idempotency_key
                or (tenant_id is not None and current.tenant_id != tenant_id)
                or (resource_id is not None and current.resource_id != resource_id)
                or (tool_name is not None and current.tool_name != tool_name)
            ):
                return RetryDispatchClaim(
                    RetryDispatchClaimOutcome.IDENTITY_CONFLICT
                )
            if current.state is not expected_state:
                return RetryDispatchClaim(RetryDispatchClaimOutcome.STATE_CONFLICT)
            if current.version != expected_version:
                return RetryDispatchClaim(
                    RetryDispatchClaimOutcome.VERSION_CONFLICT
                )
            if expected_fence is not None and current.fence_token != expected_fence:
                return RetryDispatchClaim(RetryDispatchClaimOutcome.FENCE_CONFLICT)
            if (
                new_fence is not None
                and expected_fence is not None
                and new_fence <= expected_fence
            ):
                return RetryDispatchClaim(RetryDispatchClaimOutcome.FENCE_CONFLICT)
            if attempt.attempt_number != current.attempt_number + 1:
                return RetryDispatchClaim(
                    RetryDispatchClaimOutcome.ATTEMPT_SEQUENCE_CONFLICT
                )
            if (
                current.tenant_id is not None
                and attempt.transport_generation is None
            ):
                return RetryDispatchClaim(
                    RetryDispatchClaimOutcome.TRANSPORT_GENERATION_REQUIRED
                )
            updated = replace(
                current,
                state=RetryDispatchRecordState.DISPATCH_STARTED,
                version=current.version + 1,
                attempt_number=attempt.attempt_number,
                protocol_request_id=attempt.protocol_request_id,
                fence_token=(
                    current.fence_token if new_fence is None else new_fence
                ),
                transport_generation=attempt.transport_generation,
            )
            self._records[attempt.operation_id] = updated
            return RetryDispatchClaim(
                RetryDispatchClaimOutcome.CLAIMED,
                updated,
                durable_transition=True,
            )

    def compare_and_set_completed(
        self,
        *,
        operation_id: str,
        idempotency_key: str,
        tenant_id: str,
        resource_id: str,
        tool_name: str,
        attempt_number: int,
        protocol_request_id: str | int,
        transport_generation: int,
        expected_state: RetryDispatchRecordState,
        expected_version: int,
        expected_fence: int,
        external_object_id: str,
    ) -> RetryDispatchRecord | None:
        """Atomically turn one exact dispatched attempt into durable success."""

        with self._lock:
            current = self._records.get(operation_id)
            if (
                current is None
                or current.idempotency_key != idempotency_key
                or current.tenant_id != tenant_id
                or current.resource_id != resource_id
                or current.tool_name != tool_name
                or current.attempt_number != attempt_number
                or current.protocol_request_id != protocol_request_id
                or current.transport_generation != transport_generation
                or current.state is not expected_state
                or current.version != expected_version
                or current.fence_token != expected_fence
            ):
                return None
            updated = replace(
                current,
                state=RetryDispatchRecordState.COMPLETED,
                version=current.version + 1,
                external_object_id=external_object_id,
            )
            self._records[operation_id] = updated
            return updated


def recover_abandoned_dispatch(
    record: RetryDispatchRecord,
) -> FailureEvidence:
    """Recover a crashed dispatch owner without rewriting dispatch history."""

    if record.state is not RetryDispatchRecordState.DISPATCH_STARTED:
        raise ValueError("only a started dispatch can lose its owner")
    return FailureEvidence(
        operation_id=record.operation_id,
        idempotency_key=record.idempotency_key,
        protocol_request_id=record.protocol_request_id,
        attempt_number=record.attempt_number,
        phase=FailurePhase.SEND,
        kind=FailureKind.DISPATCH_OWNER_LOST,
        dispatch_certainty=DispatchCertainty.POSSIBLY_SENT,
        execution_certainty=ExecutionCertainty.POSSIBLY_EXECUTED,
        evidence_source="durable-dispatch-marker-recovery",
    )


def plan_retry_attempt(
    evidence: FailureEvidence,
    decision: RetryDecision,
    *,
    new_protocol_request_id: str | int,
    transport_generation: int | None = None,
) -> RetryAttemptPlan:
    """Bind a policy-approved retry to a fresh protocol request identity."""

    if not decision.eligible:
        raise ValueError("only an eligible retry decision can create an attempt")
    if (
        decision.operation_id != evidence.operation_id
        or decision.idempotency_key != evidence.idempotency_key
    ):
        raise ValueError("retry decision changed application operation identity")
    if new_protocol_request_id == evidence.protocol_request_id:
        raise ValueError("a retry requires a fresh protocol_request_id")
    if (
        decision.next_attempt_number != evidence.attempt_number + 1
        or decision.delay_seconds is None
    ):
        raise ValueError("retry decision has an invalid attempt sequence")
    return RetryAttemptPlan(
        operation_id=evidence.operation_id,
        idempotency_key=evidence.idempotency_key,
        protocol_request_id=new_protocol_request_id,
        attempt_number=decision.next_attempt_number,
        delay_seconds=decision.delay_seconds,
        transport_generation=transport_generation,
    )


@dataclass(frozen=True)
class BoundedRetryPolicy:
    base_delay_seconds: float = 0.25
    maximum_delay_seconds: float = 5.0
    jitter_ratio: float = 0.2
    minimum_attempt_window_seconds: float = 0.05

    def __post_init__(self) -> None:
        if self.base_delay_seconds <= 0 or not math.isfinite(
            self.base_delay_seconds
        ):
            raise ValueError("base delay must be finite and positive")
        if self.maximum_delay_seconds < self.base_delay_seconds:
            raise ValueError("maximum delay must not be below base delay")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter ratio must be between zero and one")
        if self.minimum_attempt_window_seconds < 0:
            raise ValueError("minimum attempt window must be non-negative")

    def decide(
        self,
        evidence: FailureEvidence,
        context: RetryContext,
    ) -> RetryDecision:
        """Return a decision; never dispatch and never call a Committer."""

        blocked = self._blocked_reason(evidence, context)
        if blocked is not None:
            return RetryDecision(
                blocked,
                evidence.operation_id,
                evidence.idempotency_key,
            )

        delay = self._delay_seconds(evidence, context.retries_used)
        if (
            context.now
            + delay
            + self.minimum_attempt_window_seconds
            > context.deadline
        ):
            return RetryDecision(
                RetryDecisionKind.DEADLINE_EXHAUSTED,
                evidence.operation_id,
                evidence.idempotency_key,
            )
        return RetryDecision(
            RetryDecisionKind.ELIGIBLE,
            evidence.operation_id,
            evidence.idempotency_key,
            next_attempt_number=evidence.attempt_number + 1,
            delay_seconds=delay,
        )

    def _blocked_reason(
        self,
        evidence: FailureEvidence,
        context: RetryContext,
    ) -> RetryDecisionKind | None:
        if (
            evidence.execution_certainty
            is not ExecutionCertainty.PROVEN_NOT_EXECUTED
        ):
            return RetryDecisionKind.POSSIBLE_EXECUTION
        if not context.caller_intent_active:
            return RetryDecisionKind.CALLER_INTENT_INACTIVE
        if evidence.kind not in {
            FailureKind.CONNECT_TIMEOUT,
            FailureKind.TRANSPORT_UNAVAILABLE,
            FailureKind.SEND_FAILURE,
            FailureKind.JWKS_REFRESH_FAILED,
            FailureKind.CAPACITY_REJECTED,
            FailureKind.AUTHORITATIVE_NOT_EXECUTED,
        }:
            return RetryDecisionKind.FAILURE_NOT_RETRYABLE
        if context.retries_used >= context.max_retries:
            return RetryDecisionKind.RETRY_BUDGET_EXHAUSTED
        if context.now >= context.deadline:
            return RetryDecisionKind.DEADLINE_EXHAUSTED
        if not context.authorization_current:
            return RetryDecisionKind.AUTHORIZATION_NOT_CURRENT
        if not context.capacity_admitted:
            return RetryDecisionKind.CAPACITY_NOT_ADMITTED
        if not context.circuit_allows_request:
            return RetryDecisionKind.CIRCUIT_OPEN
        return None

    def _delay_seconds(
        self,
        evidence: FailureEvidence,
        retries_used: int,
    ) -> float:
        base = min(
            self.maximum_delay_seconds,
            self.base_delay_seconds * (2**retries_used),
        )
        digest = hashlib.sha256(
            (
                f"{evidence.operation_id}:"
                f"{evidence.idempotency_key}:"
                f"{evidence.attempt_number}"
            ).encode("utf-8")
        ).digest()
        unit = int.from_bytes(digest[:8], "big") / (2**64 - 1)
        factor = 1.0 + self.jitter_ratio * ((2.0 * unit) - 1.0)
        return min(self.maximum_delay_seconds, base * factor)
