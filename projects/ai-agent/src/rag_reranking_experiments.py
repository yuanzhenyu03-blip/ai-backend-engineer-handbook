"""Content-safe, replayable Day101 pipeline-correctness experiment."""

from __future__ import annotations

from examples.day101_query_rewriting_reranking import (
    build_day101_fixture,
    day101_request,
    run_example,
)
from rag_chunking_contracts import stable_hash
from rag_query_rewriter import RewriteProviderMode
from rag_reranker_adapter import RerankerProviderMode


def _run_case(case_id: str, **fixture_options) -> dict[str, object]:
    fixture = build_day101_fixture(**fixture_options)
    response = fixture.pipeline.execute(day101_request(fixture))
    audit = fixture.reranking_audit.events()[-1]
    return {
        "case_id": case_id,
        "outcome": response.outcome.value,
        "safe_reason": response.safe_reason,
        "rewrite_mode": response.rewrite_mode,
        "reranking_mode": (
            response.reranking_mode.value if response.reranking_mode else None
        ),
        "returned_occurrence_ids": tuple(
            hit.identity.occurrence_id for hit in response.hits
        ),
        "release_rejections": response.release_rejections,
        "rewrite_provider_calls": response.rewrite_provider_calls,
        "reranker_provider_calls": response.reranker_provider_calls,
        "raw_query_logged": audit.raw_query_logged,
        "protected_candidate_text_logged": audit.protected_candidate_text_logged,
        "vector_logged": audit.vector_logged,
    }


def run_controlled_experiment() -> dict[str, object]:
    base = run_example()
    cases = (
        _run_case("full-deterministic"),
        _run_case("rewrite-egress-denied", allow_rewrite_egress=False),
        _run_case("rerank-egress-denied", allow_reranker_egress=False),
        _run_case(
            "rewrite-timeout",
            rewrite_provider_mode=RewriteProviderMode.TIMEOUT,
        ),
        _run_case(
            "reranker-failure",
            reranker_provider_mode=RerankerProviderMode.FAILED,
        ),
    )
    report = {
        "experiment_kind": "PIPELINE_CORRECTNESS_EXPERIMENT",
        "experiment_warning": (
            "not production rewrite/reranker quality evidence"
        ),
        "evidence_level": (
            "EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"
        ),
        "fixture_scope": base["synthetic_fixture_scope"],
        "fixture_production_eligible": (
            base["synthetic_fixture_production_eligible"]
        ),
        "real_production_negative": {
            "outcome": base["real_production_outcome"],
            "reason": base["real_production_reason"],
            "rewrite_provider_calls": (
                base["real_production_rewrite_provider_calls"]
            ),
            "reranker_provider_calls": base["real_production_reranker_calls"],
        },
        "cases": cases,
        "real_query_rewrite_provider": "NOT_RUN",
        "real_local_cross_encoder": "NOT_RUN",
        "real_cohere_rerank": "NOT_RUN",
        "real_voyage_or_jina_rerank": "NOT_RUN",
        "real_protected_candidate_egress": "NOT_RUN",
        "real_reranker_latency": "NOT_RUN",
        "real_reranker_capacity": "NOT_RUN",
        "real_reranker_quality": "NOT_RUN",
        "real_provider_calls": 0,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "raw_queries_in_report": False,
        "protected_text_in_report": False,
        "vectors_in_report": False,
    }
    report["fixture_checksum"] = stable_hash((
        report["experiment_kind"],
        report["fixture_scope"],
        tuple(case["case_id"] for case in cases),
    ))
    report["report_checksum"] = stable_hash(report)
    return report
