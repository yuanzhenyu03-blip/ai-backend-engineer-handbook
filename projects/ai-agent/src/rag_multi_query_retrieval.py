"""Execute approved Day101 variants through the unchanged Day100 boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from rag_query_rewrite_contracts import QueryVariant, RewriteSet
from rag_chunking_contracts import stable_hash
from rag_retrieval_contracts import RetrievalOutcome, RetrievalRequest, RetrievalResponse
from rag_retrieval_orchestrator import AuthorizedHybridRetriever


class MultiQueryRetrievalError(RuntimeError):
    pass


@dataclass(frozen=True)
class MultiQueryExecutionPolicy:
    policy_version: str
    max_variants: int
    max_total_candidate_observations: int
    allow_partial_variant_failures: bool

    def __post_init__(self) -> None:
        if not self.policy_version or min(
            self.max_variants, self.max_total_candidate_observations
        ) <= 0:
            raise ValueError("multi-query execution budgets are required")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class VariantRetrievalResult:
    variant: QueryVariant
    response: RetrievalResponse


@dataclass(frozen=True)
class MultiQueryRetrievalReport:
    rewrite_set_fingerprint: str
    results: tuple[VariantRetrievalResult, ...]
    failed_variants: tuple[tuple[str, str], ...]
    candidate_observations: int


class Day100VariantRetrievalExecutor:
    def __init__(
        self,
        retriever: AuthorizedHybridRetriever,
        policy: MultiQueryExecutionPolicy,
    ) -> None:
        self._retriever = retriever
        self.policy = policy

    def execute(
        self,
        *,
        base_request: RetrievalRequest,
        rewrite_set: RewriteSet,
    ) -> MultiQueryRetrievalReport:
        if len(rewrite_set.variants) > self.policy.max_variants:
            raise MultiQueryRetrievalError("MULTI_QUERY_VARIANT_BUDGET_EXCEEDED")
        results: list[VariantRetrievalResult] = []
        failed: list[tuple[str, str]] = []
        observations = 0
        for variant in rewrite_set.variants:
            request = replace(
                base_request,
                operation_id=base_request.operation_id + ":" + variant.variant_id,
                request_id=base_request.request_id + f":variant:{variant.ordinal}",
                query_text=variant.protected_text,
            )
            response = self._retriever.retrieve(request)
            if response.outcome in {
                RetrievalOutcome.REJECTED,
                RetrievalOutcome.AUTHORIZATION_DENIED,
                RetrievalOutcome.UNAVAILABLE,
            }:
                failed.append((variant.variant_id, response.safe_reason))
                if not self.policy.allow_partial_variant_failures:
                    raise MultiQueryRetrievalError(
                        "DAY100_VARIANT_RETRIEVAL_FAILED:" + response.safe_reason
                    )
                continue
            observations += len(response.hits)
            if observations > self.policy.max_total_candidate_observations:
                raise MultiQueryRetrievalError(
                    "MULTI_QUERY_CANDIDATE_OBSERVATION_BUDGET_EXCEEDED"
                )
            results.append(VariantRetrievalResult(variant, response))
        if not results:
            raise MultiQueryRetrievalError("NO_DAY100_VARIANT_RETRIEVAL_SUCCEEDED")
        return MultiQueryRetrievalReport(
            rewrite_set.fingerprint,
            tuple(results),
            tuple(failed),
            observations,
        )
