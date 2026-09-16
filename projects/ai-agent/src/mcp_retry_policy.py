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
    READY_FOR_RETRY = "READY_FOR_RETRY"
    DISPATCH_STARTED = "DISPATCH_STARTED"


@dataclass(frozen=True)
class RetryDispatchRecord:
    operation_id: str
    idempotency_key: str
    state: RetryDispatchRecordState
    version: int
    attempt_number: int
    protocol_request_id: str | int


class RetryDispatchClaimOutcome(str, Enum):
    CLAIMED = "CLAIMED"
    NOT_ADMITTED = "NOT_ADMITTED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    STATE_CONFLICT = "STATE_CONFLICT"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    ATTEMPT_SEQUENCE_CONFLICT = "ATTEMPT_SEQUENCE_CONFLICT"


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

    def add_retryable(self, evidence: FailureEvidence) -> None:
        if (
            evidence.execution_certainty
            is not ExecutionCertainty.PROVEN_NOT_EXECUTED
        ):
            raise ValueError("only proven-not-executed attempts can retry")
        with self._lock:
            if evidence.operation_id in self._records:
                raise ValueError("operation is already registered")
            self._records[evidence.operation_id] = RetryDispatchRecord(
                evidence.operation_id,
                evidence.idempotency_key,
                RetryDispatchRecordState.READY_FOR_RETRY,
                version=1,
                attempt_number=evidence.attempt_number,
                protocol_request_id=evidence.protocol_request_id,
            )

    def read(self, operation_id: str) -> RetryDispatchRecord | None:
        with self._lock:
            return self._records.get(operation_id)

    def claim_dispatch(
        self,
        dispatch: RetryDispatchDecision,
        *,
        expected_version: int,
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
            ):
                return RetryDispatchClaim(
                    RetryDispatchClaimOutcome.IDENTITY_CONFLICT
                )
            if current.state is not RetryDispatchRecordState.READY_FOR_RETRY:
                return RetryDispatchClaim(RetryDispatchClaimOutcome.STATE_CONFLICT)
            if current.version != expected_version:
                return RetryDispatchClaim(
                    RetryDispatchClaimOutcome.VERSION_CONFLICT
                )
            if attempt.attempt_number != current.attempt_number + 1:
                return RetryDispatchClaim(
                    RetryDispatchClaimOutcome.ATTEMPT_SEQUENCE_CONFLICT
                )
            updated = replace(
                current,
                state=RetryDispatchRecordState.DISPATCH_STARTED,
                version=current.version + 1,
                attempt_number=attempt.attempt_number,
                protocol_request_id=attempt.protocol_request_id,
            )
            self._records[attempt.operation_id] = updated
            return RetryDispatchClaim(
                RetryDispatchClaimOutcome.CLAIMED,
                updated,
                durable_transition=True,
            )


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
