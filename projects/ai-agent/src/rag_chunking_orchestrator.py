"""Day96 application flow from an active Day95 artifact to an immutable set."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag_chunking_committer import ChunkCommitOutcome, ChunkSetCommitter
from rag_chunking_contracts import (
    ChunkSet,
    ChunkingAttemptIdentity,
    ChunkingContract,
    ChunkingOperationIdentity,
)
from rag_chunking_strategies import ChunkGenerationError, ChunkingStrategyAdapter
from rag_chunking_validator import ChunkSetCandidateValidator
from rag_document_lifecycle import evaluate_day96_chunking_eligibility
from rag_ingestion_committer import InMemoryIngestionLifecycleStore
from rag_ingestion_contracts import sha256_text


class ChunkingRunOutcome(str, Enum):
    COMMITTED = "COMMITTED"
    ALREADY_COMMITTED = "ALREADY_COMMITTED"
    CANCELLED = "CANCELLED"
    CAPACITY_DENIED = "CAPACITY_DENIED"
    INELIGIBLE = "INELIGIBLE"
    CLAIM_CONFLICT = "CLAIM_CONFLICT"
    GENERATION_FAILED = "GENERATION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    COMMIT_REJECTED = "COMMIT_REJECTED"


@dataclass(frozen=True)
class ChunkingRunRequest:
    operation: ChunkingOperationIdentity
    attempt: ChunkingAttemptIdentity
    contract: ChunkingContract
    experiment_id: str
    cancelled: bool = False
    capacity_admitted: bool = True


@dataclass(frozen=True)
class ChunkingRunResult:
    outcome: ChunkingRunOutcome
    safe_reason: str
    chunk_set: ChunkSet | None = None
    adapter_calls: int = 0
    validation_calls: int = 0
    committer_persist_calls: int = 0
    durable_chunk_set_transitions: int = 0


class RAGChunkingOrchestrator:
    def __init__(
        self,
        *,
        day95_store: InMemoryIngestionLifecycleStore,
        adapter: ChunkingStrategyAdapter,
        validator: ChunkSetCandidateValidator,
        committer: ChunkSetCommitter,
    ) -> None:
        self._day95 = day95_store
        self._adapter = adapter
        self._validator = validator
        self._committer = committer

    def run(self, request: ChunkingRunRequest) -> ChunkingRunResult:
        if request.cancelled:
            return ChunkingRunResult(
                ChunkingRunOutcome.CANCELLED, "CALLER_CANCELLED_BEFORE_CLAIM"
            )
        if not request.capacity_admitted:
            return ChunkingRunResult(
                ChunkingRunOutcome.CAPACITY_DENIED, "CHUNKING_CAPACITY_DENIED"
            )
        operation = request.operation
        if operation.contract_fingerprint != request.contract.fingerprint:
            return ChunkingRunResult(
                ChunkingRunOutcome.INELIGIBLE, "CHUNKING_CONTRACT_MISMATCH"
            )
        try:
            document = self._day95.read_document(operation.version.document)
            version = self._day95.read_version(operation.version)
            ingestion = self._day95.read_operation(
                version.definition.created_by_operation_id
            )
        except KeyError:
            return ChunkingRunResult(
                ChunkingRunOutcome.INELIGIBLE, "DAY95_LIFECYCLE_FACT_MISSING"
            )
        eligibility = evaluate_day96_chunking_eligibility(
            document=document, version=version, operation=ingestion
        )
        parsed = self._day95.read_parsed_artifact(operation.parsed_artifact_id)
        source = self._day95.read_source_artifact(operation.source_artifact_id)
        if (
            not eligibility.eligible
            or parsed is None
            or source is None
            or eligibility.parsed_artifact_id != operation.parsed_artifact_id
            or parsed.version != operation.version
            or parsed.source_artifact_id != operation.source_artifact_id
            or source.version != operation.version
            or source.checksum_sha256
            != parsed.manifest.source_checksum_sha256
            or parsed.output_checksum_sha256 != sha256_text(parsed.canonical_text)
        ):
            return ChunkingRunResult(
                ChunkingRunOutcome.INELIGIBLE,
                "DAY95_ACTIVE_PARSED_ARTIFACT_NOT_ELIGIBLE",
            )
        claim = self._committer.claim(operation, request.attempt)
        if claim is None:
            return ChunkingRunResult(
                ChunkingRunOutcome.CLAIM_CONFLICT,
                "CHUNKING_OPERATION_OR_ATTEMPT_CONFLICT",
            )
        try:
            candidate = self._adapter.generate(
                parsed=parsed,
                contract=request.contract,
                operation=operation,
                attempt=request.attempt,
                experiment_id=request.experiment_id,
            )
        except ChunkGenerationError as error:
            return ChunkingRunResult(
                ChunkingRunOutcome.GENERATION_FAILED,
                error.safe_reason,
                adapter_calls=1,
            )
        decision = self._validator.evaluate(
            document=document,
            version=version,
            ingestion=ingestion,
            parsed=parsed,
            source=source,
            contract=request.contract,
            candidate=candidate,
        )
        if not decision.ready:
            return ChunkingRunResult(
                ChunkingRunOutcome.VALIDATION_FAILED,
                decision.safe_reason,
                adapter_calls=1,
                validation_calls=1,
            )
        committed = self._committer.persist(decision, contract=request.contract)
        outcome = (
            ChunkingRunOutcome.COMMITTED
            if committed.outcome is ChunkCommitOutcome.COMMITTED
            else ChunkingRunOutcome.ALREADY_COMMITTED
            if committed.outcome is ChunkCommitOutcome.ALREADY_COMMITTED
            else ChunkingRunOutcome.COMMIT_REJECTED
        )
        return ChunkingRunResult(
            outcome,
            committed.safe_reason,
            committed.chunk_set,
            adapter_calls=1,
            validation_calls=1,
            committer_persist_calls=1,
            durable_chunk_set_transitions=int(committed.durable_transition),
        )
