"""Fail-closed Day101 reranker response validation and correlation."""

from __future__ import annotations

from dataclasses import dataclass
import math

from rag_reranker_contracts import (
    RawRerankerResponse,
    RerankerContract,
    RerankerOutputMode,
    RerankerRequest,
    RerankerScoreDirection,
    ValidatedRerankItem,
    ValidatedRerankResult,
)


class RerankingValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class RerankingValidationReport:
    result: ValidatedRerankResult
    correlation_mode: str


class RerankingValidator:
    def validate(
        self,
        *,
        request: RerankerRequest,
        response: RawRerankerResponse,
        contract: RerankerContract,
    ) -> RerankingValidationReport:
        if response.attempt_id != request.attempt_id:
            raise RerankingValidationError("RERANK_ATTEMPT_MISMATCH")
        if response.candidate_pool_digest != request.candidate_pool_digest:
            raise RerankingValidationError("RERANK_CANDIDATE_POOL_MISMATCH")
        if (
            response.reranker_contract_fingerprint
            != request.reranker_contract_fingerprint
            or response.reranker_contract_fingerprint != contract.fingerprint
        ):
            raise RerankingValidationError("RERANKER_CONTRACT_MISMATCH")

        expected = len(request.items)
        if contract.output_mode is RerankerOutputMode.FULL_PERMUTATION:
            required = expected
            if len(response.results) != required:
                raise RerankingValidationError("RERANKER_OUTPUT_INCOMPLETE")
        elif contract.output_mode is RerankerOutputMode.TOP_N:
            required = min(contract.top_n, expected)
            if len(response.results) != required:
                raise RerankingValidationError("RERANKER_TOP_N_INCOMPLETE")
        elif len(response.results) > expected:
            raise RerankingValidationError("RERANKER_SUBSET_TOO_LARGE")

        indexes = [item.input_index for item in response.results]
        if len(set(indexes)) != len(indexes):
            raise RerankingValidationError("RERANKER_DUPLICATE_CANDIDATE")
        if any(index < 0 or index >= expected for index in indexes):
            raise RerankingValidationError("RERANKER_UNKNOWN_CANDIDATE")
        if any(not math.isfinite(item.score) for item in response.results):
            raise RerankingValidationError("RERANKER_NON_FINITE_SCORE")

        mapped = [
            (raw, request.items[raw.input_index]) for raw in response.results
        ]
        higher = contract.score_direction is RerankerScoreDirection.HIGHER_IS_BETTER
        mapped.sort(key=lambda pair: (
            -pair[0].score if higher else pair[0].score,
            pair[1].prior_fusion_rank,
            pair[1].candidate_id,
        ))
        items = tuple(
            ValidatedRerankItem(
                rank,
                request_item.candidate_id,
                request_item.identity,
                raw.score,
                request_item.input_window_digest,
                request_item.prior_fusion_rank,
            )
            for rank, (raw, request_item) in enumerate(mapped, start=1)
        )
        return RerankingValidationReport(
            ValidatedRerankResult(
                request.attempt_id,
                request.candidate_pool_digest,
                request.reranker_contract_fingerprint,
                request.input_windows_digest,
                items,
            ),
            contract.correlation_mode,
        )
