"""Day95 adapter from authoritative non-execution to a fresh parse attempt.

Recovery records evidence.  The shared bounded retry policy decides eligibility.
The sole Ingestion Committer changes durable lifecycle state.  This module never
calls the parser and never persists a dispatch marker.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mcp_client_transport import DispatchCertainty
from mcp_remote_lifecycle import (
    ExecutionCertainty,
    FailureEvidence,
    FailureKind,
    FailurePhase,
)
from mcp_retry_policy import (
    BoundedRetryPolicy,
    RetryContext,
    RetryDecisionKind,
    RetryDispatchContext,
    RetryDispatchDecisionKind,
    admit_retry_dispatch,
    plan_retry_attempt,
)
from rag_ingestion_committer import (
    InMemoryIngestionLifecycleStore,
    IngestionCommitter,
    IngestionOperationState,
    IngestionOperationTransitionOutcome,
)
from rag_ingestion_contracts import (
    IngestionOperationIdentity,
    ParserAttemptIdentity,
)


class IngestionRetryOutcome(str, Enum):
    READY_FOR_PREFLIGHT = "READY_FOR_PREFLIGHT"
    LIFECYCLE_NOT_RETRYABLE = "LIFECYCLE_NOT_RETRYABLE"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    DISPATCH_GATES_BLOCKED = "DISPATCH_GATES_BLOCKED"
    ATTEMPT_IDENTITY_CONFLICT = "ATTEMPT_IDENTITY_CONFLICT"
    COMMIT_BLOCKED = "COMMIT_BLOCKED"


@dataclass(frozen=True)
class IngestionRetryRequest:
    operation: IngestionOperationIdentity
    new_parser_request_id: str
    current_parser_generation: int
    retry_context: RetryContext
    dispatch_context: RetryDispatchContext

    def __post_init__(self) -> None:
        if not self.new_parser_request_id:
            raise ValueError("new parser request id must not be empty")
        if self.current_parser_generation < 0:
            raise ValueError("parser generation must be non-negative")


@dataclass(frozen=True)
class IngestionRetryResult:
    outcome: IngestionRetryOutcome
    safe_reason: str
    attempt: ParserAttemptIdentity | None = None
    expected_operation_state: IngestionOperationState | None = None
    expected_operation_state_version: int | None = None
    expected_operation_fence: int | None = None
    delay_seconds: float | None = None
    policy_decision: RetryDecisionKind | None = None
    dispatch_decision: RetryDispatchDecisionKind | None = None
    committer_calls: int = 0
    durable_transitions: int = 0
    parser_calls: int = 0


class IngestionRetryCoordinator:
    """Prepare, but never execute, one fresh ingestion retry attempt."""

    def __init__(
        self,
        *,
        store: InMemoryIngestionLifecycleStore,
        committer: IngestionCommitter,
        policy: BoundedRetryPolicy,
    ) -> None:
        self._store = store
        self._committer = committer
        self._policy = policy

    def prepare(self, request: IngestionRetryRequest) -> IngestionRetryResult:
        record = self._store.read_operation(request.operation.operation_id)
        if (
            record.identity != request.operation
            or record.state is not IngestionOperationState.PROVEN_NOT_EXECUTED
            or record.attempt is None
        ):
            return IngestionRetryResult(
                IngestionRetryOutcome.LIFECYCLE_NOT_RETRYABLE,
                "AUTHORITATIVE_PROVEN_NOT_EXECUTED_STATE_REQUIRED",
            )

        old_attempt = record.attempt
        evidence = FailureEvidence(
            operation_id=request.operation.operation_id,
            idempotency_key=request.operation.idempotency_key,
            protocol_request_id=old_attempt.parser_request_id,
            attempt_number=old_attempt.attempt_number,
            phase=FailurePhase.RECONCILIATION,
            kind=FailureKind.AUTHORITATIVE_NOT_EXECUTED,
            dispatch_certainty=DispatchCertainty.POSSIBLY_SENT,
            execution_certainty=ExecutionCertainty.PROVEN_NOT_EXECUTED,
            evidence_source="authoritative-parsed-artifact-registry",
        )
        decision = self._policy.decide(evidence, request.retry_context)
        if not decision.eligible:
            return IngestionRetryResult(
                IngestionRetryOutcome.POLICY_BLOCKED,
                decision.kind.value,
                policy_decision=decision.kind,
            )
        try:
            planned = plan_retry_attempt(
                evidence,
                decision,
                new_protocol_request_id=request.new_parser_request_id,
                transport_generation=request.current_parser_generation,
            )
        except ValueError:
            return IngestionRetryResult(
                IngestionRetryOutcome.ATTEMPT_IDENTITY_CONFLICT,
                "FRESH_PARSER_REQUEST_ID_AND_ATTEMPT_SEQUENCE_REQUIRED",
                policy_decision=decision.kind,
            )

        dispatch = admit_retry_dispatch(planned, request.dispatch_context)
        if not dispatch.admitted:
            return IngestionRetryResult(
                IngestionRetryOutcome.DISPATCH_GATES_BLOCKED,
                dispatch.kind.value,
                policy_decision=decision.kind,
                dispatch_decision=dispatch.kind,
            )

        transition = self._committer.prepare_proven_not_executed_retry(
            identity=request.operation,
            expected_state_version=record.state_version,
            expected_fence=record.fence_token,
        )
        if (
            transition.outcome
            is not IngestionOperationTransitionOutcome.COMMITTED
            or transition.record is None
        ):
            return IngestionRetryResult(
                IngestionRetryOutcome.COMMIT_BLOCKED,
                transition.outcome.value,
                policy_decision=decision.kind,
                dispatch_decision=dispatch.kind,
                committer_calls=1,
            )

        attempt = ParserAttemptIdentity(
            operation_id=planned.operation_id,
            idempotency_key=planned.idempotency_key,
            attempt_number=planned.attempt_number,
            parser_request_id=str(planned.protocol_request_id),
            parser_generation=request.current_parser_generation,
        )
        return IngestionRetryResult(
            IngestionRetryOutcome.READY_FOR_PREFLIGHT,
            "POLICY_APPROVED_RETRY_REQUIRES_FRESH_PREFLIGHT",
            attempt=attempt,
            expected_operation_state=IngestionOperationState.READY_FOR_DISPATCH,
            expected_operation_state_version=transition.record.state_version,
            expected_operation_fence=transition.record.fence_token,
            delay_seconds=planned.delay_seconds,
            policy_decision=decision.kind,
            dispatch_decision=dispatch.kind,
            committer_calls=1,
            durable_transitions=1,
        )
