"""Content-safe replayable Day102 pipeline-correctness experiment."""

from __future__ import annotations

from examples.day102_grounding_citations import (
    CLAIM_CHANNEL,
    build_day102_fixture,
    default_claim_templates,
    run_example,
)
from rag_chunking_contracts import stable_hash
from rag_grounding_adapters import AdapterMode, ClaimTemplate
from rag_grounding_contracts import SemanticRelation


def _run_case(case_id: str, **fixture_options) -> dict[str, object]:
    fixture = build_day102_fixture(**fixture_options)
    response = fixture.pipeline.execute(fixture.request)
    audit = fixture.audit.events()[-1]
    return {
        "case_id": case_id,
        "outcome": response.outcome.value,
        "safe_reason": response.safe_reason,
        "upstream_outcome": response.upstream_outcome,
        "upstream_reranking_mode": response.upstream_reranking_mode,
        "generator_mode": response.generator_mode.value,
        "verification_mode": response.verification_mode.value,
        "released_claim_ids": tuple(
            item.claim_id for item in response.released_claims
        ),
        "rejected_reasons": tuple(sorted(
            item.reason for item in response.rejected_claims
        )),
        "citation_targets": tuple(
            citation.exact_span
            for item in response.released_claims
            for citation in item.citations
        ),
        "abstained_request_item_count": sum(
            item.status.value == "ABSTAINED"
            for item in response.request_coverage
        ),
        "generator_calls": response.generator_calls,
        "verifier_calls": response.verifier_calls,
        "raw_query_logged": audit.raw_query_logged,
        "protected_source_text_logged": audit.protected_source_text_logged,
        "protected_answer_logged": audit.protected_answer_logged,
    }


def run_controlled_experiment() -> dict[str, object]:
    base = run_example()
    cases = (
        _run_case("full-deterministic"),
        _run_case(
            "unsupported-channel",
            relations_by_claim_id={
                "claim:refund-window": SemanticRelation.SUPPORTED,
                "claim:submission-channel": SemanticRelation.UNSUPPORTED,
            },
        ),
        _run_case(
            "out-of-bundle-citation",
            claim_templates=(
                default_claim_templates()[0],
                ClaimTemplate(
                    "claim:submission-channel",
                    "request-item:submission-channel",
                    CLAIM_CHANNEL,
                    ("occurrence:B",),
                ),
            ),
        ),
        _run_case(
            "generator-egress-denied",
            allow_generator_egress=False,
        ),
        _run_case(
            "verifier-timeout-fallback",
            verifier_mode=AdapterMode.TIMEOUT,
            use_verifier_fallback=True,
        ),
    )
    report: dict[str, object] = {
        "experiment_kind": "PIPELINE_CORRECTNESS_EXPERIMENT",
        "experiment_warning": (
            "not production generator, citation or verifier quality evidence"
        ),
        "evidence_level": (
            "EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"
        ),
        "fixture_scope": "DAY102_CLASSROOM_ONLY",
        "fixture_production_eligible": False,
        "real_production_negative": {
            "outcome": base["invalid_handoff_outcome"],
            "reason": base["invalid_handoff_reason"],
            "generator_calls": base["invalid_handoff_generator_calls"],
        },
        "cases": cases,
        "real_generator": "NOT_RUN",
        "real_claim_extractor": "NOT_RUN",
        "real_nli_or_llm_verifier": "NOT_RUN",
        "real_protected_data_egress": "NOT_RUN",
        "real_grounding_quality": "NOT_RUN",
        "real_latency_capacity_cost": "NOT_RUN",
        "real_provider_calls": 0,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "raw_queries_in_report": False,
        "protected_source_text_in_report": False,
        "protected_answer_text_in_report": False,
    }
    report["fixture_checksum"] = stable_hash((
        report["experiment_kind"],
        report["fixture_scope"],
        tuple(case["case_id"] for case in cases),
    ))
    report["report_checksum"] = stable_hash(report)
    return report
