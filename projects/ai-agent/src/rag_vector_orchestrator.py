"""Thin Day99 EmbeddingSet-to-shadow-generation control flow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag_chunking_contracts import stable_hash
from rag_embedding_committer import InMemoryEmbeddingStore
from rag_vector_adapter import (
    ApplicationVectorAdapter,
    ProviderWriteAck,
    VectorProviderError,
    VectorProviderPort,
)
from rag_vector_committer import (
    VectorBuildClaim,
    VectorCommitResult,
    VectorGenerationCommitter,
)
from rag_vector_contracts import (
    GenerationState,
    VectorBuildAttempt,
    VectorBuildOperation,
    VectorGeneration,
    VectorIndexContract,
    VectorPoint,
    generation_manifest,
)
from rag_vector_validator import VectorGenerationValidator
from rag_vector_index_authorization import (
    AuthorizedIndexBuildInput,
    IndexBuildAuthorizationGuard,
)
from rag_vector_index_planner import VectorBatchPlan, plan_vector_batches


class VectorBuildOutcome(str, Enum):
    SEALED = "SEALED"
    REJECTED = "REJECTED"
    CLAIM_CONFLICT = "CLAIM_CONFLICT"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


@dataclass(frozen=True)
class VectorBuildRequest:
    operation_id: str
    idempotency_key: str
    tenant_id: str
    document_id: str
    chunk_set_id: str
    embedding_set_id: str
    expected_embedding_selection_revision: int
    expected_contract_selection_revision: int
    contract: VectorIndexContract
    authorization: AuthorizedIndexBuildInput
    attempt: VectorBuildAttempt


@dataclass(frozen=True)
class VectorBuildResult:
    outcome: VectorBuildOutcome
    safe_reason: str
    operation: VectorBuildOperation | None = None
    claim: VectorBuildClaim | None = None
    commit: VectorCommitResult | None = None
    generation_id: str | None = None


class VectorGenerationOrchestrator:
    def __init__(
        self,
        *,
        embeddings: InMemoryEmbeddingStore,
        provider: VectorProviderPort,
        validator: VectorGenerationValidator,
        committer: VectorGenerationCommitter,
        authorization_guard: IndexBuildAuthorizationGuard,
    ) -> None:
        self._embeddings = embeddings
        self._provider = provider
        self._adapter = ApplicationVectorAdapter(provider)
        self._validator = validator
        self._committer = committer
        self._authorization_guard = authorization_guard

    def run(self, request: VectorBuildRequest) -> VectorBuildResult:
        prepared = self._prepare(request)
        if isinstance(prepared, VectorBuildResult):
            return prepared
        operation, claim, generation_id, points, plan = prepared
        try:
            acknowledgements = self._provider.replace_generation(
                generation_id=generation_id,
                contract=request.contract,
                plan=plan,
                operation_id=operation.operation_id,
                request_id=request.attempt.request_id,
                fence=claim.fence,
            )
        except VectorProviderError as exc:
            if exc.execution_state == "UNKNOWN":
                self._committer.mark_unknown(claim)
                return VectorBuildResult(
                    VectorBuildOutcome.RECONCILIATION_REQUIRED,
                    exc.reason,
                    operation,
                    claim,
                    generation_id=generation_id,
                )
            return VectorBuildResult(
                VectorBuildOutcome.REJECTED,
                exc.reason,
                operation,
                claim,
                generation_id=generation_id,
            )
        return self._validate_and_persist(
            request=request,
            operation=operation,
            claim=claim,
            generation_id=generation_id,
            points=points,
            plan=plan,
            acknowledgements=acknowledgements,
        )

    def reconcile(self, request: VectorBuildRequest) -> VectorBuildResult:
        prepared = self._prepare(request)
        if isinstance(prepared, VectorBuildResult):
            return prepared
        operation, claim, generation_id, points, plan = prepared
        readback = self._provider.readback(generation_id)
        expected_acks = tuple(ProviderWriteAck(
            generation_id=batch.generation_id,
            namespace=batch.namespace,
            tenant_id=batch.tenant_id,
            request_id=request.attempt.request_id,
            batch_id=batch.batch_id,
            accepted_point_ids=tuple(
                point.point_id for point in batch.points
            ),
            operation_id=operation.operation_id,
            checkpoint=readback.checkpoint,
        ) for batch in plan.batches)
        return self._validate_and_persist(
            request=request,
            operation=operation,
            claim=claim,
            generation_id=generation_id,
            points=points,
            plan=plan,
            acknowledgements=expected_acks,
        )

    def _prepare(
        self, request: VectorBuildRequest
    ) -> tuple[
        VectorBuildOperation,
        VectorBuildClaim,
        str,
        tuple[VectorPoint, ...],
        VectorBatchPlan,
    ] | VectorBuildResult:
        if request.contract.embedding_set_id != request.embedding_set_id:
            return VectorBuildResult(
                VectorBuildOutcome.REJECTED,
                "REQUEST_CONTRACT_EMBEDDING_SET_MISMATCH",
            )
        authorization_error = self._authorization_guard.check(
            request.authorization, request.contract
        )
        if authorization_error is not None:
            return VectorBuildResult(
                VectorBuildOutcome.REJECTED,
                authorization_error,
            )
        embedding_set = self._embeddings.read_set(request.embedding_set_id)
        if embedding_set is None or not request.contract.accepts(embedding_set):
            return VectorBuildResult(
                VectorBuildOutcome.REJECTED,
                "EMBEDDING_SET_NOT_FOUND_OR_CONTRACT_MISMATCH",
            )
        if (
            request.tenant_id != embedding_set.operation.tenant_id
            or request.document_id != embedding_set.operation.document_id
            or request.chunk_set_id != embedding_set.operation.chunk_set_id
        ):
            return VectorBuildResult(
                VectorBuildOutcome.REJECTED,
                "REQUEST_EMBEDDING_SET_LINEAGE_MISMATCH",
            )
        selection = self._embeddings.read_selection(
            request.tenant_id,
            request.document_id,
            request.chunk_set_id,
        )
        if (
            selection is None
            or selection.embedding_set_id != request.embedding_set_id
            or selection.revision
            != request.expected_embedding_selection_revision
        ):
            return VectorBuildResult(
                VectorBuildOutcome.REJECTED,
                "CURRENT_EMBEDDING_SELECTION_CHANGED_BEFORE_DISPATCH",
            )
        operation = VectorBuildOperation(
            operation_id=request.operation_id,
            idempotency_key=request.idempotency_key,
            tenant_id=request.tenant_id,
            document_id=request.document_id,
            document_version_id=embedding_set.operation.document_version_id,
            chunk_set_id=request.chunk_set_id,
            embedding_set_id=request.embedding_set_id,
            embedding_selection_revision=(
                request.expected_embedding_selection_revision
            ),
            embedding_set_checksum=embedding_set.manifest_checksum,
            embedding_record_ids=tuple(
                record.embedding_id for record in embedding_set.records
            ),
            authorization_decision_id=(
                request.authorization.authorization_decision_id
            ),
            authorization_revisions=(
                request.authorization.authorization_revisions
            ),
            contract_fingerprint=request.contract.fingerprint,
            contract_selection_revision=(
                request.expected_contract_selection_revision
            ),
        )
        claim = self._committer.claim(operation, request.attempt)
        if claim is None:
            return VectorBuildResult(
                VectorBuildOutcome.CLAIM_CONFLICT,
                "VECTOR_OPERATION_ATTEMPT_OR_RECONCILIATION_CONFLICT",
                operation,
            )
        generation_id = "vector-generation:" + (
            operation.stable_result_key.removeprefix("sha256:")
        )
        points = tuple(VectorPoint(
            point_id="vector-point:" + stable_hash((
                request.tenant_id,
                generation_id,
                record.embedding_id,
            )).removeprefix("sha256:"),
            generation_id=generation_id,
            tenant_id=request.tenant_id,
            embedding_id=record.embedding_id,
            chunk_id=record.chunk_id,
            vector=record.vector,
            payload=tuple(sorted({
                "tenant_id": request.tenant_id,
                "document_id": request.document_id,
                "document_version_id": embedding_set.operation.document_version_id,
                "chunk_set_id": request.chunk_set_id,
                "embedding_set_id": request.embedding_set_id,
                "embedding_id": record.embedding_id,
                "chunk_id": record.chunk_id,
                "content_hash": record.content_hash,
            }.items())),
        ) for record in embedding_set.records)
        plan = plan_vector_batches(
            points,
            contract=request.contract,
            operation_id=operation.operation_id,
        )
        return operation, claim, generation_id, points, plan

    def _validate_and_persist(
        self,
        *,
        request: VectorBuildRequest,
        operation: VectorBuildOperation,
        claim: VectorBuildClaim,
        generation_id: str,
        points: tuple[VectorPoint, ...],
        plan: VectorBatchPlan,
        acknowledgements: tuple[ProviderWriteAck, ...],
    ) -> VectorBuildResult:
        manifest = generation_manifest(
            points,
            embedding_set_id=request.embedding_set_id,
            contract_fingerprint=request.contract.fingerprint,
        )
        readback = self._provider.readback(generation_id)
        validation = self._validator.evaluate(
            expected_points=points,
            expected_manifest=manifest,
            plan=plan,
            acknowledgements=acknowledgements,
            request_id=request.attempt.request_id,
            readback=readback,
            adapter=self._adapter,
        )
        if not validation.ready_to_seal:
            return VectorBuildResult(
                VectorBuildOutcome.REJECTED,
                validation.safe_reason,
                operation,
                claim,
                generation_id=generation_id,
            )
        generation = VectorGeneration(
            generation_id,
            operation,
            request.contract,
            manifest,
            validation.provider_checkpoint,
            validation.evidence,
            GenerationState.SEALED,
        )
        commit = self._committer.persist(
            claim=claim,
            contract=request.contract,
            generation=generation,
            authorization=request.authorization,
        )
        return VectorBuildResult(
            VectorBuildOutcome.SEALED
            if commit.generation is not None
            else VectorBuildOutcome.REJECTED,
            commit.safe_reason,
            operation,
            claim,
            commit,
            generation_id,
        )
