"""Independent, zero-partial-acceptance Day98 response validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from rag_embedding_contracts import (
    EmbeddingBatch,
    EmbeddingContract,
    NormalizationPolicy,
    ProviderEmbeddingCandidate,
    UsageConfidence,
    ValidatedEmbeddingBatch,
)


class EmbeddingValidationOutcome(str, Enum):
    READY = "READY"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class EmbeddingValidationDecision:
    outcome: EmbeddingValidationOutcome
    safe_reason: str
    validated: ValidatedEmbeddingBatch | None = None

    @property
    def ready(self) -> bool:
        return self.outcome is EmbeddingValidationOutcome.READY


class EmbeddingCandidateValidator:
    def evaluate(
        self,
        *,
        batch: EmbeddingBatch,
        contract: EmbeddingContract,
        candidate: ProviderEmbeddingCandidate,
        expected_request_id: str,
    ) -> EmbeddingValidationDecision:
        if candidate.request_id != expected_request_id:
            return self._reject("REQUEST_CORRELATION_MISMATCH")
        if candidate.batch_id != batch.batch_id:
            return self._reject("BATCH_CORRELATION_MISMATCH")
        if candidate.model != contract.model:
            return self._reject("MODEL_IDENTITY_MISMATCH")
        if candidate.response_schema_version != contract.response_schema_version:
            return self._reject("RESPONSE_SCHEMA_MISMATCH")
        if candidate.partial:
            return self._reject("PARTIAL_PROVIDER_RESPONSE")
        expected_ids = tuple(item.chunk_id for item in batch.items)
        actual_ids = tuple(item.item_id for item in candidate.items)
        if len(actual_ids) != len(expected_ids):
            return self._reject("RESPONSE_COUNT_MISMATCH")
        if len(set(actual_ids)) != len(actual_ids):
            return self._reject("DUPLICATE_RESPONSE_ITEM")
        missing = set(expected_ids) - set(actual_ids)
        unknown = set(actual_ids) - set(expected_ids)
        if unknown:
            return self._reject("UNKNOWN_RESPONSE_ITEM")
        if missing:
            return self._reject("MISSING_RESPONSE_ITEM")
        by_id = {item.item_id: item.vector for item in candidate.items}
        for item_id in expected_ids:
            vector = by_id[item_id]
            if len(vector) != contract.dimensions:
                return self._reject("VECTOR_DIMENSION_MISMATCH")
            if not all(
                isinstance(value, (int, float)) and not isinstance(value, bool)
                for value in vector
            ):
                return self._reject("VECTOR_NUMERIC_TYPE_MISMATCH")
            if not all(math.isfinite(value) for value in vector):
                return self._reject("NON_FINITE_VECTOR")
            norm = math.sqrt(sum(value * value for value in vector))
            if norm == 0 and not contract.zero_vector_allowed:
                return self._reject("ZERO_VECTOR_REJECTED")
            if (
                contract.normalization is NormalizationPolicy.UNIT_L2
                and abs(norm - 1.0) > contract.norm_tolerance
            ):
                return self._reject("VECTOR_NORMALIZATION_MISMATCH")
        expected_usage = sum(item.token_count for item in batch.items)
        if (
            candidate.usage_confidence is UsageConfidence.EXACT
            and candidate.usage_tokens != expected_usage
        ):
            return self._reject("EXACT_USAGE_MISMATCH")
        if (
            candidate.usage_confidence is UsageConfidence.ESTIMATED
            and (candidate.usage_tokens is None or candidate.usage_tokens < 0)
        ):
            return self._reject("ESTIMATED_USAGE_INVALID")
        if (
            candidate.usage_confidence is UsageConfidence.UNKNOWN
            and candidate.usage_tokens is not None
        ):
            return self._reject("UNKNOWN_USAGE_MUST_NOT_CLAIM_COUNT")
        if not math.isfinite(candidate.latency_ms) or candidate.latency_ms < 0:
            return self._reject("LATENCY_EVIDENCE_INVALID")
        if (
            candidate.cost_confidence is UsageConfidence.UNKNOWN
            and candidate.cost_microunits is not None
        ):
            return self._reject("UNKNOWN_COST_MUST_NOT_CLAIM_AMOUNT")
        if (
            candidate.cost_confidence is not UsageConfidence.UNKNOWN
            and (
                candidate.cost_microunits is None
                or candidate.cost_microunits < 0
            )
        ):
            return self._reject("COST_EVIDENCE_INVALID")
        return EmbeddingValidationDecision(
            EmbeddingValidationOutcome.READY,
            "COMPLETE_CORRELATED_BATCH_VALID",
            ValidatedEmbeddingBatch(batch, candidate),
        )

    @staticmethod
    def _reject(reason: str) -> EmbeddingValidationDecision:
        return EmbeddingValidationDecision(
            EmbeddingValidationOutcome.REJECTED, reason
        )
