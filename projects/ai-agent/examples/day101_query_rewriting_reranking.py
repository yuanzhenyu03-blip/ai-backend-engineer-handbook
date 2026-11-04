"""Executable Day101 negative handoff and deterministic correctness fixture."""

from __future__ import annotations

from dataclasses import dataclass
import json

from examples.day100_hybrid_retrieval_filtering import (
    Day100Fixture,
    build_day100_fixture,
    load_real_day99_handoff,
    retrieval_request,
)
from rag_multi_query_fusion import MultiQueryFusionPolicy
from rag_multi_query_retrieval import (
    Day100VariantRetrievalExecutor,
    MultiQueryExecutionPolicy,
)
from rag_query_rewrite_contracts import (
    QueryRewriteContract,
    QueryRewriteDegradationPolicy,
    QueryVariantSource,
    RewriteCandidate,
    RewriteEgressPolicy,
)
from rag_query_rewriter import (
    BoundedQueryRewriter,
    ContentSafeRewriteAuditSink,
    DeterministicRewriteProvider,
    QueryVariantValidator,
    RewriteProviderMode,
)
from rag_reranker_adapter import (
    DeterministicRerankerAdapter,
    RerankerInputBuilder,
    RerankerProviderMode,
)
from rag_reranker_contracts import (
    RawRerankerResponse,
    RerankerContract,
    RerankerEgressPolicy,
    RerankerOutputMode,
    RerankerScoreDirection,
    RerankingDegradationPolicy,
)
from rag_reranking_orchestrator import (
    AuthorizedRerankingOrchestrator,
    ContentSafeRerankingAuditSink,
    Day100CurrentnessOracle,
    Day101Eligibility,
)
from rag_reranking_validator import RerankingValidator


QUERY_DIGEST_SECRET = b"day101-classroom-query-digest-secret"


def classroom_rewrite_contract() -> QueryRewriteContract:
    return QueryRewriteContract(
        contract_version="day101-rewrite-v1",
        provider="classroom-deterministic-rewriter",
        immutable_provider_revision="fake-rewriter-sha256-001",
        prompt_revision="scope-preserving-prompt-v1",
        tokenizer_revision="classroom-rewrite-tokenizer-v1",
        normalization_version="collapse-space-casefold-v1",
        locale="en",
        max_generated_variants=2,
        max_variant_chars=120,
        max_total_utf8_bytes=512,
        max_rewrite_rounds=1,
        timeout_ms=100,
        allowed_sources=(
            QueryVariantSource.NORMALIZED,
            QueryVariantSource.SPELLING_CORRECTED,
            QueryVariantSource.ACRONYM_EXPANDED,
            QueryVariantSource.PARAPHRASE,
            QueryVariantSource.DECOMPOSED,
        ),
        protected_query_policy="PROTECTED_QUERY_NO_LOG",
        egress_policy_version="day101-rewrite-egress-v1",
    )


def classroom_reranker_contract() -> RerankerContract:
    return RerankerContract(
        contract_version="day101-reranker-v1",
        provider="classroom-deterministic-pointwise-reranker",
        immutable_model_revision="fake-reranker-sha256-001",
        tokenizer_revision="classroom-reranker-tokenizer-v1",
        score_direction=RerankerScoreDirection.HIGHER_IS_BETTER,
        score_activation="RAW_CONTROLLED_SCORE",
        score_calibration="NOT_CALIBRATED_NOT_A_PROBABILITY",
        output_mode=RerankerOutputMode.FULL_PERMUTATION,
        top_n=5,
        max_candidates=5,
        max_input_chars=64,
        input_window_strategy="HEAD_TAIL",
        input_window_policy_version="day101-head-tail-window-v1",
        protected_data_policy="CLASSROOM_SYNTHETIC_ONLY",
        egress_policy_version="day101-reranker-egress-v1",
    )


def default_rewrite_outputs() -> tuple[RewriteCandidate, ...]:
    return (
        RewriteCandidate(
            QueryVariantSource.PARAPHRASE,
            "en",
            1,
            "customer refund rules",
        ),
        RewriteCandidate(
            QueryVariantSource.DECOMPOSED,
            "en",
            2,
            "finance refund requirements",
        ),
    )


@dataclass
class Day101Fixture:
    day100: Day100Fixture
    rewrite_provider: DeterministicRewriteProvider
    rewrite_audit: ContentSafeRewriteAuditSink
    currentness: Day100CurrentnessOracle
    reranker: DeterministicRerankerAdapter
    reranking_audit: ContentSafeRerankingAuditSink
    pipeline: AuthorizedRerankingOrchestrator


def build_day101_fixture(
    *,
    select_bundle: bool = True,
    classroom_mode: bool = True,
    production_mode: bool = False,
    rewrite_outputs: tuple[RewriteCandidate, ...] | None = None,
    rewrite_provider_mode: RewriteProviderMode = RewriteProviderMode.NORMAL,
    allow_rewrite_egress: bool = True,
    reranker_provider_mode: RerankerProviderMode = RerankerProviderMode.NORMAL,
    allow_reranker_egress: bool = True,
    reranker_response_override: RawRerankerResponse | None = None,
) -> Day101Fixture:
    day100 = build_day100_fixture(
        select_bundle=select_bundle,
        classroom_mode=classroom_mode,
    )
    rewrite_contract = classroom_rewrite_contract()
    rewrite_provider = DeterministicRewriteProvider(
        rewrite_outputs if rewrite_outputs is not None else default_rewrite_outputs(),
        rewrite_provider_mode,
    )
    rewrite_audit = ContentSafeRewriteAuditSink()
    rewriter = BoundedQueryRewriter(
        contract=rewrite_contract,
        degradation=QueryRewriteDegradationPolicy(
            "day101-rewrite-degradation-v1",
            allow_original_only_on_egress_denied=True,
            allow_original_only_on_provider_failure=True,
            allow_original_only_on_timeout=True,
            allow_partial_valid_variants=True,
        ),
        egress=RewriteEgressPolicy(
            "day101-rewrite-egress-v1",
            frozenset({rewrite_contract.provider}),
            allow_rewrite_egress,
        ),
        provider=rewrite_provider,
        validator=QueryVariantValidator(
            lambda original, candidate: (
                "bypass" not in candidate.protected_text.casefold()
                and original.tenant_id == day100.bundle.tenant_id
            )
        ),
        audit=rewrite_audit,
        digest_secret=QUERY_DIGEST_SECRET,
    )
    currentness = Day100CurrentnessOracle(
        authorization=day100.authorization,
        records=day100.records,
    )
    reranker_contract = classroom_reranker_contract()
    reranker = DeterministicRerankerAdapter(
        contract=reranker_contract,
        scores_by_candidate_id={
            "occurrence:A": 0.82,
            "occurrence:B": 0.96,
            "occurrence:C": 0.71,
            "occurrence:A2": 0.63,
        },
        mode=reranker_provider_mode,
        response_override=reranker_response_override,
    )
    reranking_audit = ContentSafeRerankingAuditSink()
    pipeline = AuthorizedRerankingOrchestrator(
        selected_bundle=day100.bundle if select_bundle else None,
        eligibility=Day101Eligibility(classroom_mode, production_mode),
        rewriter=rewriter,
        multi_query=Day100VariantRetrievalExecutor(
            day100.retriever,
            MultiQueryExecutionPolicy(
                "day101-multi-query-v1",
                max_variants=3,
                max_total_candidate_observations=15,
                allow_partial_variant_failures=False,
            ),
        ),
        fusion_policy=MultiQueryFusionPolicy(
            "day101-multi-query-rrf-v1", 60, 5
        ),
        currentness=currentness,
        reranker_contract=reranker_contract,
        reranker_egress=RerankerEgressPolicy(
            "day101-reranker-egress-v1",
            frozenset({reranker_contract.provider}),
            allow_protected_query_egress=allow_reranker_egress,
            allow_protected_candidate_egress=allow_reranker_egress,
        ),
        reranking_degradation=RerankingDegradationPolicy(
            "day101-reranking-degradation-v1",
            allow_unreranked_on_egress_denied=True,
            allow_unreranked_on_provider_failure=True,
            allow_unreranked_on_timeout=True,
            allow_unreranked_on_invalid_output=True,
        ),
        input_builder=RerankerInputBuilder(reranker_contract),
        reranker=reranker,
        validator=RerankingValidator(),
        audit=reranking_audit,
        query_digest_secret=QUERY_DIGEST_SECRET,
    )
    return Day101Fixture(
        day100,
        rewrite_provider,
        rewrite_audit,
        currentness,
        reranker,
        reranking_audit,
        pipeline,
    )


def day101_request(fixture: Day101Fixture):
    return retrieval_request(
        fixture.day100,
        query_text="refund policy",
        top_k=4,
        operation_id="operation-day101-v1",
        request_id="request-day101-v1",
    )


def run_example() -> dict[str, object]:
    real_handoff = load_real_day99_handoff()
    negative = build_day101_fixture(
        select_bundle=False,
        classroom_mode=False,
        production_mode=True,
    )
    negative_result = negative.pipeline.execute(day101_request(negative))

    positive = build_day101_fixture()
    positive_result = positive.pipeline.execute(day101_request(positive))
    return {
        "experiment_kind": "PIPELINE_CORRECTNESS_EXPERIMENT",
        "real_day99_handoff": real_handoff,
        "real_production_outcome": negative_result.outcome.value,
        "real_production_reason": negative_result.safe_reason,
        "real_production_rewrite_provider_calls": (
            negative_result.rewrite_provider_calls
        ),
        "real_production_reranker_calls": negative_result.reranker_provider_calls,
        "synthetic_fixture_scope": positive.day100.bundle.fixture_scope,
        "synthetic_fixture_production_eligible": (
            positive.day100.bundle.production_eligible
        ),
        "synthetic_outcome": positive_result.outcome.value,
        "synthetic_rewrite_mode": positive_result.rewrite_mode,
        "synthetic_reranking_mode": positive_result.reranking_mode.value,
        "synthetic_occurrence_ids": tuple(
            hit.identity.occurrence_id for hit in positive_result.hits
        ),
        "synthetic_raw_query_logged": (
            positive.reranking_audit.events()[-1].raw_query_logged
        ),
        "synthetic_protected_text_logged": (
            positive.reranking_audit.events()[-1].protected_candidate_text_logged
        ),
        "real_rewrite_provider": "NOT_RUN",
        "real_local_cross_encoder": "NOT_RUN",
        "real_cohere_rerank": "NOT_RUN",
        "real_jina_or_voyage_rerank": "NOT_RUN",
        "real_protected_candidate_egress": "NOT_RUN",
        "real_latency_capacity_quality": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2, sort_keys=True))
