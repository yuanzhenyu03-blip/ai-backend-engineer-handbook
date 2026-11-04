from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from examples.day101_query_rewriting_reranking import (  # noqa: E402
    build_day101_fixture,
    day101_request,
)
from rag_query_rewrite_contracts import QueryVariantSource, RewriteCandidate  # noqa: E402
from rag_query_rewriter import RewriteProviderMode  # noqa: E402
from rag_reranker_adapter import RerankerProviderMode  # noqa: E402


def _revoke(fixture, occurrence_id: str) -> None:
    request = day101_request(fixture)
    fixture.day100.authorization.revoke_occurrence(
        tenant_id=request.tenant_id,
        principal_subject=request.principal_subject,
        action=request.action,
        purpose=request.purpose,
        occurrence_id=occurrence_id,
    )


def _run_case(case: dict[str, object]) -> tuple[bool, dict[str, object]]:
    case_id = str(case["case_id"])
    options: dict[str, object] = {}
    if case_id == "real-production-no-bundle":
        options.update(select_bundle=False, classroom_mode=False, production_mode=True)
    elif case_id == "rewrite-egress-denied":
        options["allow_rewrite_egress"] = False
    elif case_id == "rewrite-timeout":
        options["rewrite_provider_mode"] = RewriteProviderMode.TIMEOUT
    elif case_id == "rerank-egress-denied":
        options["allow_reranker_egress"] = False
    elif case_id == "reranker-failure":
        options["reranker_provider_mode"] = RerankerProviderMode.FAILED
    elif case_id == "semantic-drift":
        options["rewrite_outputs"] = (
            RewriteCandidate(QueryVariantSource.PARAPHRASE, "en", 1, "refund rules"),
            RewriteCandidate(QueryVariantSource.PARAPHRASE, "en", 2, "bypass policy"),
        )
    fixture = build_day101_fixture(**options)
    if case_id in {"post-rerank-revocation", "post-rerank-provenance"}:
        original_rank = fixture.reranker.rank

        def mutate_after_rank(request):
            response = original_rank(request)
            if case_id == "post-rerank-revocation":
                _revoke(fixture, "occurrence:B")
            else:
                fixture.currentness.change_provenance(
                    "occurrence:B", "sha256:changed"
                )
            return response

        fixture.reranker.rank = mutate_after_rank
    result = fixture.pipeline.execute(day101_request(fixture))
    event = fixture.reranking_audit.events()[-1]
    actual = {
        "outcome": result.outcome.value,
        "reason": result.safe_reason,
        "rewrite_mode": result.rewrite_mode,
        "reranking_mode": (
            result.reranking_mode.value if result.reranking_mode else None
        ),
        "rewrite_calls": result.rewrite_provider_calls,
        "reranker_calls": result.reranker_provider_calls,
        "rejection_reasons": tuple(reason for _, reason in result.release_rejections),
        "occurrence_ids": tuple(hit.identity.occurrence_id for hit in result.hits),
        "raw_query_logged": event.raw_query_logged,
        "protected_text_logged": event.protected_candidate_text_logged,
    }
    checks = []
    mapping = {
        "expected_outcome": "outcome",
        "expected_reason": "reason",
        "expected_rewrite_mode": "rewrite_mode",
        "expected_reranking_mode": "reranking_mode",
        "expected_rewrite_calls": "rewrite_calls",
        "expected_reranker_calls": "reranker_calls",
        "expected_raw_query_logged": "raw_query_logged",
        "expected_protected_text_logged": "protected_text_logged",
    }
    for expected_key, actual_key in mapping.items():
        if expected_key in case:
            checks.append(case[expected_key] == actual[actual_key])
    if "expected_rejected_reason" in case:
        audit = fixture.rewrite_audit.events()[-1]
        checks.append(audit.rejected_count == 1)
    if "expected_rejection" in case:
        checks.append(case["expected_rejection"] in actual["rejection_reasons"])
    if "forbidden_occurrence" in case:
        checks.append(case["forbidden_occurrence"] not in actual["occurrence_ids"])
    return all(checks), actual


def run() -> dict[str, object]:
    path = Path(__file__).with_name("day101_query_rewriting_reranking_seed.jsonl")
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    results = []
    for case in cases:
        passed, actual = _run_case(case)
        results.append({"case_id": case["case_id"], "passed": passed, "actual": actual})
    return {
        "passed": sum(1 for item in results if item["passed"]),
        "total": len(results),
        "results": results,
        "synthetic_fixture_production_eligible": False,
        "real_provider_calls": 0,
        "real_model_quality": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
