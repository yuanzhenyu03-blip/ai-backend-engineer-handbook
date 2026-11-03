"""Run the content-safe Day100 authorized hybrid-retrieval seed matrix."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "src"))

from examples.day100_hybrid_retrieval_filtering import (  # noqa: E402
    build_day100_fixture,
    retrieval_request,
)
from rag_dense_retrieval import DenseMode  # noqa: E402
from rag_retrieval_filters import FilterExpression  # noqa: E402


def _run_scenario(scenario: str):
    if scenario == "NO_SELECTED":
        fixture = build_day100_fixture(select_bundle=False)
        request = retrieval_request(fixture)
    elif scenario == "CLIENT_GENERATION":
        fixture = build_day100_fixture()
        request = retrieval_request(
            fixture, client_generation_id="untrusted-generation"
        )
    elif scenario == "SENSITIVE_QUERY":
        fixture = build_day100_fixture()
        request = retrieval_request(
            fixture, query_text="alice@example.com refund policy", top_k=2
        )
    elif scenario == "QUERY_CONTRACT":
        fixture = build_day100_fixture()
        request = replace(
            retrieval_request(fixture),
            query_encoder_contract_fingerprint="sha256:wrong",
        )
    elif scenario == "DENSE_TIMEOUT":
        fixture = build_day100_fixture(dense_mode=DenseMode.TIMEOUT)
        request = retrieval_request(fixture, top_k=2)
    elif scenario == "NO_GRANT":
        fixture = build_day100_fixture()
        fixture.authorization.put(replace(
            fixture.scope,
            allowed_occurrence_ids=(),
            decision_id="seed-no-grant",
        ))
        request = retrieval_request(fixture)
    elif scenario == "UNSUPPORTED_FILTER":
        fixture = build_day100_fixture()
        request = retrieval_request(
            fixture,
            client_filter=FilterExpression.eq("tenant_id", "tenant-other"),
        )
    else:
        fixture = build_day100_fixture()
        request = retrieval_request(fixture)
    return fixture, fixture.retriever.retrieve(request)


def run() -> dict[str, object]:
    path = Path(__file__).with_name(
        "day100_hybrid_retrieval_filtering_seed.jsonl"
    )
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        fixture, response = _run_scenario(item["scenario"])
        passed = (
            response.outcome.value == item["expected_outcome"]
            and response.safe_reason == item["expected_reason"]
        )
        cases.append({
            "case_id": item["case_id"],
            "passed": passed,
            "outcome": response.outcome.value,
            "reason": response.safe_reason,
            "provider_calls": response.provider_calls,
            "database_calls": response.database_calls,
            "raw_query_logged": fixture.audit.events()[-1].raw_query_logged,
        })
    return {
        "passed": sum(bool(case["passed"]) for case in cases),
        "total": len(cases),
        "cases": cases,
        "evidence_scope": "DAY100_PIPELINE_CORRECTNESS_EXPERIMENT",
        "synthetic_fixture_production_eligible": False,
        "real_provider": "NOT_RUN",
        "real_database": "NOT_RUN",
        "real_ann": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["passed"] != result["total"]:
        raise SystemExit(1)
