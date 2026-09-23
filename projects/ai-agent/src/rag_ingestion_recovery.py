"""Day95 authoritative ingestion recovery without parser replay."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from rag_ingestion_committer import (
    InMemoryIngestionLifecycleStore,
    IngestionActivationGuard,
    IngestionCommitOutcome,
    IngestionCommitter,
    IngestionOperationState,
)
from rag_ingestion_contracts import (
    CandidateValidationOutcome,
    DocumentVersionDefinition,
    IngestionOperationIdentity,
    ParsedCandidateValidator,
    ParsedDocumentCandidate,
    ParserAttemptIdentity,
    SourceArtifactReference,
)


class AuthoritativeParseStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_EXECUTED = "NOT_EXECUTED"
    NOT_FOUND = "NOT_FOUND"
    UNKNOWN = "UNKNOWN"


class IngestionRecoveryOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED_CONFIRMED = "FAILED_CONFIRMED"
    NOT_EXECUTED_CONFIRMED = "NOT_EXECUTED_CONFIRMED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    AUTHORITY_BINDING_CONFLICT = "AUTHORITY_BINDING_CONFLICT"
    CANDIDATE_REJECTED = "CANDIDATE_REJECTED"
    COMMIT_BLOCKED = "COMMIT_BLOCKED"
    OPERATION_NOT_RECOVERABLE = "OPERATION_NOT_RECOVERABLE"


@dataclass(frozen=True)
class AuthoritativeParseEvidence:
    status: AuthoritativeParseStatus
    operation_id: str
    idempotency_key: str
    attempt_number: int
    parser_request_id: str
    parser_generation: int
    candidate: ParsedDocumentCandidate | None = None

    def __post_init__(self) -> None:
        succeeded = self.status is AuthoritativeParseStatus.SUCCEEDED
        if succeeded != (self.candidate is not None):
            raise ValueError("only authoritative success carries a candidate")


class AuthoritativeParsedArtifactRegistry(Protocol):
    def query(
        self,
        *,
        operation: IngestionOperationIdentity,
        attempt: ParserAttemptIdentity,
    ) -> AuthoritativeParseEvidence: ...


@dataclass(frozen=True)
class IngestionRecoveryPolicy:
    maximum_queries: int

    def __post_init__(self) -> None:
        if self.maximum_queries <= 0:
            raise ValueError("reconciliation query budget must be positive")


@dataclass(frozen=True)
class IngestionRecoveryResult:
    outcome: IngestionRecoveryOutcome
    safe_reason: str
    registry_queries: int = 0
    parser_transport_calls: int = 0
    parser_calls: int = 0
    candidate_validation_calls: int = 0
    committer_calls: int = 0
    durable_transitions: int = 0
    requery_scheduled: bool = False
    operator_alert_required: bool = False


class SequenceAuthoritativeParsedArtifactRegistry:
    """Deterministic registry fake; it never executes a parser."""

    def __init__(self, evidence: tuple[AuthoritativeParseEvidence, ...]) -> None:
        if not evidence:
            raise ValueError("at least one authoritative response is required")
        self._evidence = evidence
        self.queries = 0

    def query(
        self,
        *,
        operation: IngestionOperationIdentity,
        attempt: ParserAttemptIdentity,
    ) -> AuthoritativeParseEvidence:
        del operation, attempt
        index = min(self.queries, len(self._evidence) - 1)
        self.queries += 1
        return self._evidence[index]


class IngestionRecoveryCoordinator:
    """Read authority, validate evidence, and route proposals to the Committer."""

    def __init__(
        self,
        *,
        store: InMemoryIngestionLifecycleStore,
        registry: AuthoritativeParsedArtifactRegistry,
        committer: IngestionCommitter,
        policy: IngestionRecoveryPolicy,
    ) -> None:
        self._store = store
        self._registry = registry
        self._committer = committer
        self._policy = policy

    def recover(
        self,
        *,
        operation: IngestionOperationIdentity,
        version: DocumentVersionDefinition,
        source: SourceArtifactReference,
        query_number: int,
    ) -> IngestionRecoveryResult:
        if query_number <= 0:
            raise ValueError("reconciliation query number must be positive")
        current = self._store.read_operation(operation.operation_id)
        if current.identity != operation or current.attempt is None:
            return IngestionRecoveryResult(
                IngestionRecoveryOutcome.OPERATION_NOT_RECOVERABLE,
                "RECOVERY_OPERATION_BINDING_IS_INCOMPLETE",
            )
        transition_count = 0
        committer_calls = 0
        if current.state is IngestionOperationState.PARSE_DISPATCH_STARTED:
            pending = self._committer.mark_pending_reconciliation(
                identity=operation,
                expected_state_version=current.state_version,
                expected_fence=current.fence_token,
            )
            committer_calls += pending.committer_calls
            transition_count += int(pending.durable_transition)
            if pending.record is None:
                return IngestionRecoveryResult(
                    IngestionRecoveryOutcome.COMMIT_BLOCKED,
                    "PENDING_RECONCILIATION_TRANSITION_BLOCKED",
                    committer_calls=committer_calls,
                    durable_transitions=transition_count,
                )
            current = pending.record
        elif current.state is not IngestionOperationState.PENDING_RECONCILIATION:
            return IngestionRecoveryResult(
                IngestionRecoveryOutcome.OPERATION_NOT_RECOVERABLE,
                "OPERATION_IS_NOT_PENDING_RECONCILIATION",
            )

        attempt = current.attempt
        assert attempt is not None
        evidence = self._registry.query(operation=operation, attempt=attempt)
        if not self._evidence_binds(evidence, operation, attempt):
            return IngestionRecoveryResult(
                IngestionRecoveryOutcome.AUTHORITY_BINDING_CONFLICT,
                "AUTHORITATIVE_EVIDENCE_BINDING_CONFLICT",
                registry_queries=1,
                committer_calls=committer_calls,
                durable_transitions=transition_count,
                operator_alert_required=True,
            )

        if evidence.status in {
            AuthoritativeParseStatus.NOT_FOUND,
            AuthoritativeParseStatus.UNKNOWN,
        }:
            budget_remaining = query_number < self._policy.maximum_queries
            return IngestionRecoveryResult(
                IngestionRecoveryOutcome.PENDING_RECONCILIATION,
                evidence.status.value,
                registry_queries=1,
                committer_calls=committer_calls,
                durable_transitions=transition_count,
                requery_scheduled=budget_remaining,
                operator_alert_required=not budget_remaining,
            )

        if evidence.status in {
            AuthoritativeParseStatus.FAILED,
            AuthoritativeParseStatus.NOT_EXECUTED,
        }:
            target = (
                IngestionOperationState.FAILED
                if evidence.status is AuthoritativeParseStatus.FAILED
                else IngestionOperationState.PROVEN_NOT_EXECUTED
            )
            committed = self._committer.commit_authoritative_reconciliation(
                identity=operation,
                target_state=target,
                expected_state_version=current.state_version,
                expected_fence=current.fence_token,
            )
            return IngestionRecoveryResult(
                (
                    IngestionRecoveryOutcome.FAILED_CONFIRMED
                    if target is IngestionOperationState.FAILED
                    else IngestionRecoveryOutcome.NOT_EXECUTED_CONFIRMED
                ),
                evidence.status.value,
                registry_queries=1,
                committer_calls=committer_calls + committed.committer_calls,
                durable_transitions=(
                    transition_count + int(committed.durable_transition)
                ),
            )

        assert evidence.candidate is not None
        validation = ParsedCandidateValidator().evaluate(
            operation=operation,
            version=version,
            source=source,
            attempt=attempt,
            candidate=evidence.candidate,
        )
        if validation.outcome is not CandidateValidationOutcome.READY_FOR_COMMIT:
            return IngestionRecoveryResult(
                IngestionRecoveryOutcome.CANDIDATE_REJECTED,
                validation.safe_reason,
                registry_queries=1,
                candidate_validation_calls=1,
                committer_calls=committer_calls,
                durable_transitions=transition_count,
                operator_alert_required=True,
            )

        document = self._store.read_document(operation.version.document)
        version_record = self._store.read_version(operation.version)
        guard = IngestionActivationGuard(
            expected_document_state=document.state,
            expected_active_version_id=document.active_version_id,
            expected_document_state_version=document.state_version,
            expected_document_fence=document.fence_token,
            expected_version_state=version_record.state,
            expected_version_state_version=version_record.state_version,
            expected_version_fence=version_record.fence_token,
            expected_operation_state=IngestionOperationState.PENDING_RECONCILIATION,
            expected_operation_state_version=current.state_version,
            expected_operation_fence=current.fence_token,
        )
        committed = self._committer.commit(validation, guard=guard)
        if committed.outcome not in {
            IngestionCommitOutcome.COMMITTED,
            IngestionCommitOutcome.ALREADY_COMMITTED,
        }:
            return IngestionRecoveryResult(
                IngestionRecoveryOutcome.COMMIT_BLOCKED,
                committed.safe_reason,
                registry_queries=1,
                candidate_validation_calls=1,
                committer_calls=committer_calls + committed.committer_calls,
                durable_transitions=transition_count,
            )
        return IngestionRecoveryResult(
            IngestionRecoveryOutcome.SUCCEEDED,
            "AUTHORITATIVE_PARSE_SUCCESS_COMMITTED",
            registry_queries=1,
            candidate_validation_calls=1,
            committer_calls=committer_calls + committed.committer_calls,
            durable_transitions=(
                transition_count + int(committed.durable_transition)
            ),
        )

    @staticmethod
    def _evidence_binds(
        evidence: AuthoritativeParseEvidence,
        operation: IngestionOperationIdentity,
        attempt: ParserAttemptIdentity,
    ) -> bool:
        return (
            evidence.operation_id == operation.operation_id
            and evidence.idempotency_key == operation.idempotency_key
            and evidence.attempt_number == attempt.attempt_number
            and evidence.parser_request_id == attempt.parser_request_id
            and evidence.parser_generation == attempt.parser_generation
        )
