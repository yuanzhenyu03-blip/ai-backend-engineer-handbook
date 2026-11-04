"""Versioned input-window builder and deterministic reranker fake."""

from __future__ import annotations

from enum import Enum

from rag_chunking_contracts import stable_hash
from rag_multi_query_fusion import MultiQueryCandidatePool
from rag_reranker_contracts import (
    RawRerankerItem,
    RawRerankerResponse,
    RerankerContract,
    RerankerInputItem,
    RerankerOutputMode,
    RerankerRequest,
    RerankerScoreDirection,
)


class RerankerProviderMode(str, Enum):
    NORMAL = "NORMAL"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class RerankerProviderError(RuntimeError):
    pass


class RerankerInputBuilder:
    def __init__(self, contract: RerankerContract) -> None:
        self.contract = contract

    def _window(self, text: str) -> str:
        limit = self.contract.max_input_chars
        if len(text) <= limit:
            return text
        if self.contract.input_window_strategy == "HEAD":
            return text[:limit]
        head = limit * 3 // 4
        tail = limit - head
        return text[:head] + text[-tail:]

    def build(
        self,
        *,
        original_query_digest: str,
        protected_query: str,
        pool: MultiQueryCandidatePool,
    ) -> RerankerRequest:
        if not pool.candidates:
            raise ValueError("reranker requires a non-empty candidate pool")
        if len(pool.candidates) > self.contract.max_candidates:
            raise ValueError("candidate pool exceeds reranker contract budget")
        items = tuple(
            RerankerInputItem(
                index,
                candidate.identity.occurrence_id,
                candidate.identity,
                index + 1,
                stable_hash((
                    self.contract.tokenizer_revision,
                    self.contract.input_window_policy_version,
                    self._window(candidate.source_hit.text),
                )),
                self.contract.input_window_policy_version,
                self._window(candidate.source_hit.text),
            )
            for index, candidate in enumerate(pool.candidates)
        )
        windows_digest = stable_hash(tuple((
            item.candidate_id,
            item.input_window_digest,
            item.input_window_policy_version,
        ) for item in items))
        attempt_id = stable_hash((
            "DAY101_RERANK_ATTEMPT",
            original_query_digest,
            pool.digest,
            self.contract.fingerprint,
            windows_digest,
        ))
        return RerankerRequest(
            attempt_id,
            original_query_digest,
            pool.digest,
            self.contract.fingerprint,
            windows_digest,
            items,
            protected_query,
        )


class DeterministicRerankerAdapter:
    """A controlled pointwise fake, not real model-quality evidence."""

    def __init__(
        self,
        *,
        contract: RerankerContract,
        scores_by_candidate_id: dict[str, float],
        mode: RerankerProviderMode = RerankerProviderMode.NORMAL,
        response_override: RawRerankerResponse | None = None,
    ) -> None:
        self.contract = contract
        self._scores = dict(scores_by_candidate_id)
        self._mode = mode
        self._response_override = response_override
        self.calls = 0

    def rank(self, request: RerankerRequest) -> RawRerankerResponse:
        self.calls += 1
        if self._mode is RerankerProviderMode.FAILED:
            raise RerankerProviderError("RERANKER_FAILED")
        if self._mode is RerankerProviderMode.TIMEOUT:
            raise RerankerProviderError("RERANKER_TIMEOUT")
        if self._response_override is not None:
            return self._response_override
        values = [
            RawRerankerItem(
                item.input_index,
                self._scores.get(item.candidate_id, 0.0),
            )
            for item in request.items
        ]
        reverse = self.contract.score_direction is RerankerScoreDirection.HIGHER_IS_BETTER
        values.sort(
            key=lambda item: (
                -item.score if reverse else item.score,
                request.items[item.input_index].prior_fusion_rank,
                request.items[item.input_index].candidate_id,
            )
        )
        if self.contract.output_mode is RerankerOutputMode.TOP_N:
            values = values[:self.contract.top_n]
        return RawRerankerResponse(
            request.attempt_id,
            request.candidate_pool_digest,
            request.reranker_contract_fingerprint,
            tuple(values),
        )
