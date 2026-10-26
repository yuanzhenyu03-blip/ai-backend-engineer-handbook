"""Thin Day98 authorization-to-candidate-to-Committer control flow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag_authorized_chunk_reader import AuthorizedEmbeddingInput
from rag_embedding_adapter import EmbeddingProviderPort, ProviderDispatchError
from rag_embedding_batching import BatchPlanError, plan_batches
from rag_embedding_committer import (
    EmbeddingClaim,
    EmbeddingCommitResult,
    EmbeddingCommitter,
)
from rag_embedding_contracts import (
    EmbeddingAttemptIdentity,
    EmbeddingContract,
    EmbeddingOperationIdentity,
    ValidatedEmbeddingBatch,
)
from rag_embedding_requirements import (
    EmbeddingEligibilityError,
    prepare_authorized_items,
)
from rag_embedding_validator import EmbeddingCandidateValidator
from rag_tokenizer_adapter import TokenizerPort


class EmbeddingRunOutcome(str, Enum):
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
    CLAIM_CONFLICT = "CLAIM_CONFLICT"
    RETRY_ALLOWED = "RETRY_ALLOWED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


@dataclass(frozen=True)
class EmbeddingRunRequest:
    handoff: AuthorizedEmbeddingInput
    contract: EmbeddingContract
    operation_id: str
    idempotency_key: str
    attempt: EmbeddingAttemptIdentity
    expected_selected_id: str | None = None
    expected_selection_revision: int = 0
    expected_contract_selection_revision: int = 1


@dataclass(frozen=True)
class EmbeddingRunResult:
    outcome: EmbeddingRunOutcome
    safe_reason: str
    operation: EmbeddingOperationIdentity | None = None
    claim: EmbeddingClaim | None = None
    commit: EmbeddingCommitResult | None = None
    validated_batch_count: int = 0


def deterministic_retry_delay_seconds(
    *, attempt_number: int, retry_after_seconds: float | None = None
) -> float:
    """Bounded exponential delay plus deterministic test jitter."""

    if attempt_number <= 0:
        raise ValueError("attempt number must be positive")
    base = min(30.0, float(2 ** (attempt_number - 1)))
    jitter = ((attempt_number * 37) % 10) / 10.0
    return max(base + jitter, retry_after_seconds or 0.0)


class EmbeddingOrchestrator:
    def __init__(
        self,
        *,
        tokenizer: TokenizerPort,
        provider: EmbeddingProviderPort,
        validator: EmbeddingCandidateValidator,
        committer: EmbeddingCommitter,
    ) -> None:
        self._tokenizer = tokenizer
        self._provider = provider
        self._validator = validator
        self._committer = committer

    def run(self, request: EmbeddingRunRequest) -> EmbeddingRunResult:
        handoff = request.handoff
        operation = EmbeddingOperationIdentity(
            operation_id=request.operation_id,
            idempotency_key=request.idempotency_key,
            tenant_id=handoff.tenant_id,
            principal_subject=handoff.principal_subject,
            authorization_decision_id=handoff.authorization_decision_id,
            authorization_revisions=handoff.authorization_revisions,
            document_id=handoff.document_id,
            document_version_id=handoff.document_version_id,
            chunk_set_id=handoff.chunk_set_id,
            authorized_chunk_ids=handoff.authorized_chunk_ids,
            selection_revision=handoff.selection_revision,
            document_state_version=handoff.document_state_version,
            document_fence=handoff.document_fence,
            contract_fingerprint=request.contract.fingerprint,
            contract_selection_revision=(
                request.expected_contract_selection_revision
            ),
        )
        claim = self._committer.claim(operation, request.attempt)
        if claim is None:
            return EmbeddingRunResult(
                EmbeddingRunOutcome.CLAIM_CONFLICT,
                "EMBEDDING_OPERATION_OR_ATTEMPT_CONFLICT",
                operation,
            )
        try:
            items = prepare_authorized_items(
                handoff,
                contract=request.contract,
                tokenizer=self._tokenizer,
            )
            batches = plan_batches(
                items,
                limits=request.contract.batch_limits,
                operation_id=operation.operation_id,
            )
        except (EmbeddingEligibilityError, BatchPlanError) as exc:
            return EmbeddingRunResult(
                EmbeddingRunOutcome.REJECTED,
                str(exc),
                operation,
                claim,
            )

        validated: list[ValidatedEmbeddingBatch] = []
        for batch in batches:
            request_id = f"{request.attempt.request_id}:batch:{batch.ordinal}"
            try:
                candidate = self._provider.embed(
                    batch=batch,
                    contract=request.contract,
                    request_id=request_id,
                )
            except ProviderDispatchError as exc:
                outcome = (
                    EmbeddingRunOutcome.RECONCILIATION_REQUIRED
                    if exc.execution_state == "UNKNOWN"
                    else EmbeddingRunOutcome.RETRY_ALLOWED
                )
                return EmbeddingRunResult(
                    outcome,
                    exc.reason,
                    operation,
                    claim,
                    validated_batch_count=len(validated),
                )
            decision = self._validator.evaluate(
                batch=batch,
                contract=request.contract,
                candidate=candidate,
                expected_request_id=request_id,
            )
            if not decision.ready or decision.validated is None:
                # A single invalid item rejects the whole operation; nothing
                # from earlier batches may become a durable EmbeddingSet.
                return EmbeddingRunResult(
                    EmbeddingRunOutcome.REJECTED,
                    decision.safe_reason,
                    operation,
                    claim,
                    validated_batch_count=len(validated),
                )
            validated.append(decision.validated)
        commit = self._committer.persist(
            claim=claim,
            handoff=handoff,
            contract=request.contract,
            batches=tuple(validated),
            expected_selected_id=request.expected_selected_id,
            expected_selection_revision=request.expected_selection_revision,
        )
        return EmbeddingRunResult(
            EmbeddingRunOutcome.COMMITTED
            if commit.embedding_set is not None
            else EmbeddingRunOutcome.REJECTED,
            commit.safe_reason,
            operation,
            claim,
            commit,
            len(validated),
        )
