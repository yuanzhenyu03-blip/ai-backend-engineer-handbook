"""Application-owned Day93 remote MCP lifecycle evidence.

Transport and SDK exceptions are converted here before recovery policy sees
them.  The module records what is known about dispatch; it deliberately does
not decide whether another attempt should run.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from mcp_client_transport import DispatchCertainty


class FailurePhase(str, Enum):
    CONNECT = "CONNECT"
    SEND = "SEND"
    READ = "READ"
    CANCELLATION = "CANCELLATION"
    AUTHENTICATION_DEPENDENCY = "AUTHENTICATION_DEPENDENCY"
    CAPACITY = "CAPACITY"
    VERSION_NEGOTIATION = "VERSION_NEGOTIATION"
    RECONCILIATION = "RECONCILIATION"


class FailureKind(str, Enum):
    CONNECT_TIMEOUT = "CONNECT_TIMEOUT"
    TRANSPORT_UNAVAILABLE = "TRANSPORT_UNAVAILABLE"
    SEND_FAILURE = "SEND_FAILURE"
    READ_TIMEOUT = "READ_TIMEOUT"
    CONNECTION_LOST = "CONNECTION_LOST"
    DISPATCH_OWNER_LOST = "DISPATCH_OWNER_LOST"
    CALLER_CANCELLED = "CALLER_CANCELLED"
    JWKS_REFRESH_FAILED = "JWKS_REFRESH_FAILED"
    CAPACITY_REJECTED = "CAPACITY_REJECTED"
    UNVERIFIED_REMOTE_FAILURE = "UNVERIFIED_REMOTE_FAILURE"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    AUTHORITATIVE_NOT_EXECUTED = "AUTHORITATIVE_NOT_EXECUTED"


class LifecycleOutcome(str, Enum):
    PRE_DISPATCH_ABORTED = "PRE_DISPATCH_ABORTED"
    REJECTED_BEFORE_EXECUTION = "REJECTED_BEFORE_EXECUTION"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"


class ExecutionCertainty(str, Enum):
    """What application-owned evidence proves about business execution."""

    PROVEN_NOT_EXECUTED = "PROVEN_NOT_EXECUTED"
    POSSIBLY_EXECUTED = "POSSIBLY_EXECUTED"
    PROVEN_EXECUTED = "PROVEN_EXECUTED"


@dataclass(frozen=True)
class FailureEvidence:
    """Auditable facts about one failed attempt, never a retry command."""

    operation_id: str
    idempotency_key: str
    protocol_request_id: str | int
    attempt_number: int
    phase: FailurePhase
    kind: FailureKind
    dispatch_certainty: DispatchCertainty
    execution_certainty: ExecutionCertainty
    evidence_source: str

    def __post_init__(self) -> None:
        if not self.operation_id:
            raise ValueError("operation_id must not be empty")
        if not self.idempotency_key:
            raise ValueError("idempotency_key must not be empty")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be positive")
        if not self.evidence_source:
            raise ValueError("evidence_source must not be empty")
        if (
            self.dispatch_certainty is DispatchCertainty.PROVEN_NOT_SENT
            and self.execution_certainty
            is not ExecutionCertainty.PROVEN_NOT_EXECUTED
        ):
            raise ValueError("not-sent evidence must also be not-executed")


@dataclass(frozen=True)
class CancellationObservation:
    """Cancellation delivery facts; not proof of transactional rollback."""

    operation_id: str
    idempotency_key: str
    protocol_request_id: str | int
    attempt_number: int
    dispatch_certainty: DispatchCertainty
    remote_task_cancelled: bool
    evidence_source: str


def cancellation_failure_evidence(
    observation: CancellationObservation,
) -> FailureEvidence:
    """Only a proven pre-dispatch cancellation proves non-execution."""

    return FailureEvidence(
        operation_id=observation.operation_id,
        idempotency_key=observation.idempotency_key,
        protocol_request_id=observation.protocol_request_id,
        attempt_number=observation.attempt_number,
        phase=FailurePhase.CANCELLATION,
        kind=FailureKind.CALLER_CANCELLED,
        dispatch_certainty=observation.dispatch_certainty,
        execution_certainty=(
            ExecutionCertainty.PROVEN_NOT_EXECUTED
            if observation.dispatch_certainty
            is DispatchCertainty.PROVEN_NOT_SENT
            else ExecutionCertainty.POSSIBLY_EXECUTED
        ),
        evidence_source=observation.evidence_source,
    )


def classify_lifecycle_outcome(
    evidence: FailureEvidence,
) -> LifecycleOutcome:
    """Classify uncertainty without deciding whether to retry."""

    if evidence.execution_certainty is ExecutionCertainty.PROVEN_NOT_EXECUTED:
        if evidence.dispatch_certainty is DispatchCertainty.PROVEN_NOT_SENT:
            return LifecycleOutcome.PRE_DISPATCH_ABORTED
        return LifecycleOutcome.REJECTED_BEFORE_EXECUTION
    return LifecycleOutcome.PENDING_RECONCILIATION


@dataclass(frozen=True)
class DeadlineBudget:
    """One absolute deadline shared by every phase of an operation."""

    deadline: float
    cleanup_reserve_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.deadline):
            raise ValueError("deadline must be finite")
        if (
            not math.isfinite(self.cleanup_reserve_seconds)
            or self.cleanup_reserve_seconds < 0
        ):
            raise ValueError("cleanup reserve must be finite and non-negative")

    def remaining(self, *, now: float) -> float:
        """Return usable time without ever extending the parent deadline."""

        return max(0.0, self.deadline - now - self.cleanup_reserve_seconds)

    def stage_timeout(
        self,
        *,
        now: float,
        configured_timeout: float,
    ) -> float:
        if not math.isfinite(configured_timeout) or configured_timeout <= 0:
            raise ValueError("configured timeout must be finite and positive")
        return min(configured_timeout, self.remaining(now=now))
