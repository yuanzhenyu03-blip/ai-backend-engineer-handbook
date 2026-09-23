"""Day95 thin RAG ingestion orchestrator.

The orchestrator routes typed decisions without absorbing their authority.  It
requires preflight, persists ``PARSE_DISPATCH_STARTED`` before parser handoff,
validates the returned candidate, and invokes the sole Ingestion Committer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from rag_ingestion_committer import (
    DocumentVersionLifecycle,
    InMemoryIngestionLifecycleStore,
    IngestionActivationGuard,
    IngestionCommitOutcome,
    IngestionCommitter,
    IngestionDispatchClaimOutcome,
    IngestionOperationState,
)
from rag_ingestion_contracts import (
    CandidateValidationOutcome,
    DocumentVersionDefinition,
    IngestionOperationIdentity,
    ParsedCandidateValidator,
    ParserAttemptIdentity,
    SourceArtifactReference,
)
from rag_parser_adapter import (
    ControlledParserAdapter,
    ParserAdapterOutcome,
    ParserAdapterResult,
)


class IngestionPreflightOutcome(str, Enum):
    READY = "READY"
    AUTHORIZATION_BLOCKED = "AUTHORIZATION_BLOCKED"
    CALLER_INTENT_INACTIVE = "CALLER_INTENT_INACTIVE"
    DEADLINE_EXHAUSTED = "DEADLINE_EXHAUSTED"
    CAPACITY_REJECTED = "CAPACITY_REJECTED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    PARSER_PREFLIGHT_BLOCKED = "PARSER_PREFLIGHT_BLOCKED"


class IngestionOrchestrationOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"
    DISPATCH_CLAIM_BLOCKED = "DISPATCH_CLAIM_BLOCKED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    PARSER_REJECTED = "PARSER_REJECTED"
    CANDIDATE_REJECTED = "CANDIDATE_REJECTED"
    COMMIT_BLOCKED = "COMMIT_BLOCKED"


@dataclass(frozen=True)
class IngestionOrchestrationRequest:
    operation: IngestionOperationIdentity
    version: DocumentVersionDefinition
    source: SourceArtifactReference
    attempt: ParserAttemptIdentity
    source_bytes: bytes
    expected_operation_state: IngestionOperationState
    expected_operation_state_version: int
    expected_operation_fence: int
    current_authorization: bool
    parser_permit_current: bool
    caller_intent_active: bool
    cancelled: bool
    now: float
    deadline: float
    capacity_admitted: bool
    circuit_allows_request: bool


@dataclass(frozen=True)
class IngestionPreflightDecision:
    outcome: IngestionPreflightOutcome
    safe_reason: str
    parser_calls: int = 0
    committer_calls: int = 0

    @property
    def ready(self) -> bool:
        return self.outcome is IngestionPreflightOutcome.READY


@dataclass(frozen=True)
class VerifiedIngestionObservation:
    operation_id: str
    tenant_id: str
    document_id: str
    document_version_id: str
    parsed_artifact_id: str
    durable_document_state_version: int


@dataclass(frozen=True)
class IngestionOrchestrationResult:
    outcome: IngestionOrchestrationOutcome
    safe_reason: str
    parser_transport_calls: int = 0
    parser_calls: int = 0
    candidate_validation_calls: int = 0
    committer_calls: int = 0
    durable_transitions: int = 0
    verified_observation: VerifiedIngestionObservation | None = None


class ParserTransport(Protocol):
    def execute(
        self,
        *,
        operation: IngestionOperationIdentity,
        version: DocumentVersionDefinition,
        source: SourceArtifactReference,
        attempt: ParserAttemptIdentity,
        source_bytes: bytes,
    ) -> ParserAdapterResult: ...


class ParserOutcomeUnknown(RuntimeError):
    """The handoff may have executed but no trustworthy response was received."""

    def __init__(self, safe_reason: str, *, parser_transport_calls: int = 1) -> None:
        super().__init__(safe_reason)
        self.safe_reason = safe_reason
        self.parser_transport_calls = parser_transport_calls


class LocalControlledParserTransport:
    def __init__(self, adapter: ControlledParserAdapter) -> None:
        self._adapter = adapter

    def execute(
        self,
        *,
        operation: IngestionOperationIdentity,
        version: DocumentVersionDefinition,
        source: SourceArtifactReference,
        attempt: ParserAttemptIdentity,
        source_bytes: bytes,
    ) -> ParserAdapterResult:
        return self._adapter.parse(
            operation=operation,
            version=version,
            source=source,
            attempt=attempt,
            source_bytes=source_bytes,
        )


class IngestionPreflight:
    def evaluate(
        self,
        request: IngestionOrchestrationRequest,
        adapter: ControlledParserAdapter,
    ) -> IngestionPreflightDecision:
        if not request.current_authorization or not request.parser_permit_current:
            return IngestionPreflightDecision(
                IngestionPreflightOutcome.AUTHORIZATION_BLOCKED,
                "CURRENT_AUTHORIZATION_AND_PARSER_PERMIT_REQUIRED",
            )
        if not request.caller_intent_active or request.cancelled:
            return IngestionPreflightDecision(
                IngestionPreflightOutcome.CALLER_INTENT_INACTIVE,
                "CALLER_INTENT_OR_CANCELLATION_BLOCKS_DISPATCH",
            )
        if request.now >= request.deadline:
            return IngestionPreflightDecision(
                IngestionPreflightOutcome.DEADLINE_EXHAUSTED,
                "PARENT_DEADLINE_EXHAUSTED",
            )
        if not request.capacity_admitted:
            return IngestionPreflightDecision(
                IngestionPreflightOutcome.CAPACITY_REJECTED,
                "CURRENT_PARSER_CAPACITY_NOT_ADMITTED",
            )
        if not request.circuit_allows_request:
            return IngestionPreflightDecision(
                IngestionPreflightOutcome.CIRCUIT_OPEN,
                "PARSER_CIRCUIT_IS_OPEN",
            )
        parser_preflight = adapter.preflight(
            operation=request.operation,
            version=request.version,
            source=request.source,
            attempt=request.attempt,
        )
        if not parser_preflight.ready:
            return IngestionPreflightDecision(
                IngestionPreflightOutcome.PARSER_PREFLIGHT_BLOCKED,
                parser_preflight.safe_reason,
            )
        return IngestionPreflightDecision(
            IngestionPreflightOutcome.READY,
            "INGESTION_PREFLIGHT_PASSED",
        )


class RAGIngestionOrchestrator:
    """Sequence pure gates, durable claim, parser, validation, and Committer."""

    def __init__(
        self,
        *,
        store: InMemoryIngestionLifecycleStore,
        adapter: ControlledParserAdapter,
        transport: ParserTransport,
        committer: IngestionCommitter,
    ) -> None:
        self._store = store
        self._adapter = adapter
        self._transport = transport
        self._committer = committer

    def run(
        self,
        request: IngestionOrchestrationRequest,
    ) -> IngestionOrchestrationResult:
        preflight = IngestionPreflight().evaluate(request, self._adapter)
        if not preflight.ready:
            return IngestionOrchestrationResult(
                IngestionOrchestrationOutcome.PREFLIGHT_BLOCKED,
                preflight.safe_reason,
            )

        claim = self._store.claim_parse_dispatch(
            identity=request.operation,
            attempt=request.attempt,
            expected_state=request.expected_operation_state,
            expected_state_version=request.expected_operation_state_version,
            expected_fence=request.expected_operation_fence,
        )
        if (
            claim.outcome is not IngestionDispatchClaimOutcome.CLAIMED
            or claim.record is None
        ):
            return IngestionOrchestrationResult(
                IngestionOrchestrationOutcome.DISPATCH_CLAIM_BLOCKED,
                claim.outcome.value,
                durable_transitions=int(claim.durable_transition),
            )

        try:
            parser_result = self._transport.execute(
                operation=request.operation,
                version=request.version,
                source=request.source,
                attempt=request.attempt,
                source_bytes=request.source_bytes,
            )
        except ParserOutcomeUnknown as unknown:
            pending = self._committer.mark_pending_reconciliation(
                identity=request.operation,
                expected_state_version=claim.record.state_version,
                expected_fence=claim.record.fence_token,
            )
            return IngestionOrchestrationResult(
                IngestionOrchestrationOutcome.PENDING_RECONCILIATION,
                unknown.safe_reason,
                parser_transport_calls=unknown.parser_transport_calls,
                committer_calls=pending.committer_calls,
                durable_transitions=(
                    1 + int(pending.durable_transition)
                ),
            )

        if (
            parser_result.outcome is not ParserAdapterOutcome.CANDIDATE
            or parser_result.candidate is None
        ):
            quarantined = self._committer.mark_quarantined(
                identity=request.operation,
                expected_state_version=claim.record.state_version,
                expected_fence=claim.record.fence_token,
            )
            return IngestionOrchestrationResult(
                IngestionOrchestrationOutcome.PARSER_REJECTED,
                parser_result.safe_reason,
                parser_transport_calls=1,
                parser_calls=parser_result.parser_calls,
                committer_calls=quarantined.committer_calls,
                durable_transitions=(
                    1 + int(quarantined.durable_transition)
                ),
            )

        validation = ParsedCandidateValidator().evaluate(
            operation=request.operation,
            version=request.version,
            source=request.source,
            attempt=request.attempt,
            candidate=parser_result.candidate,
        )
        if validation.outcome is not CandidateValidationOutcome.READY_FOR_COMMIT:
            quarantined = self._committer.mark_quarantined(
                identity=request.operation,
                expected_state_version=claim.record.state_version,
                expected_fence=claim.record.fence_token,
            )
            return IngestionOrchestrationResult(
                IngestionOrchestrationOutcome.CANDIDATE_REJECTED,
                validation.safe_reason,
                parser_transport_calls=1,
                parser_calls=parser_result.parser_calls,
                candidate_validation_calls=1,
                committer_calls=quarantined.committer_calls,
                durable_transitions=(
                    1 + int(quarantined.durable_transition)
                ),
            )

        document = self._store.read_document(request.operation.version.document)
        version = self._store.read_version(request.operation.version)
        guard = IngestionActivationGuard(
            expected_document_state=document.state,
            expected_active_version_id=document.active_version_id,
            expected_document_state_version=document.state_version,
            expected_document_fence=document.fence_token,
            expected_version_state=version.state,
            expected_version_state_version=version.state_version,
            expected_version_fence=version.fence_token,
            expected_operation_state=IngestionOperationState.PARSE_DISPATCH_STARTED,
            expected_operation_state_version=claim.record.state_version,
            expected_operation_fence=claim.record.fence_token,
        )
        committed = self._committer.commit(validation, guard=guard)
        if committed.outcome not in {
            IngestionCommitOutcome.COMMITTED,
            IngestionCommitOutcome.ALREADY_COMMITTED,
        }:
            return IngestionOrchestrationResult(
                IngestionOrchestrationOutcome.COMMIT_BLOCKED,
                committed.safe_reason,
                parser_transport_calls=1,
                parser_calls=parser_result.parser_calls,
                candidate_validation_calls=1,
                committer_calls=committed.committer_calls,
                durable_transitions=1,
            )

        assert committed.document is not None
        assert committed.parsed_artifact is not None
        observation = VerifiedIngestionObservation(
            operation_id=request.operation.operation_id,
            tenant_id=request.operation.tenant_id,
            document_id=request.operation.document_id,
            document_version_id=request.operation.document_version_id,
            parsed_artifact_id=committed.parsed_artifact.parsed_artifact_id,
            durable_document_state_version=(
                committed.document.state_version
            ),
        )
        return IngestionOrchestrationResult(
            IngestionOrchestrationOutcome.SUCCEEDED,
            committed.safe_reason,
            parser_transport_calls=1,
            parser_calls=parser_result.parser_calls,
            candidate_validation_calls=1,
            committer_calls=committed.committer_calls,
            durable_transitions=(1 + int(committed.durable_transition)),
            verified_observation=observation,
        )
