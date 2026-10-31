"""Run the content-safe Day99 vector generation seed matrix."""

from __future__ import annotations

import json
from pathlib import Path

from examples.day99_vector_database_index_design import (
    build_day99_fixture,
    vector_build_request,
)
from rag_vector_adapter import FakeVectorMode


def run() -> dict[str, object]:
    path = Path(__file__).with_name(
        "day99_vector_database_index_design_seed.jsonl"
    )
    cases: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        fixture = build_day99_fixture(mode=FakeVectorMode(item["mode"]))
        request = vector_build_request(fixture)
        result = fixture.orchestrator.run(request)
        if item["reconcile"]:
            result = fixture.orchestrator.reconcile(request)
        cases.append({
            "case_id": item["case_id"],
            "passed": result.outcome.value == item["expected"],
            "outcome": result.outcome.value,
            "reason": result.safe_reason,
            "durable_transition": bool(
                result.commit and result.commit.durable_transition
            ),
        })
    return {
        "passed": sum(bool(case["passed"]) for case in cases),
        "total": len(cases),
        "cases": cases,
        "vectors_in_report": False,
        "evidence_scope": "DAY99_DETERMINISTIC_FAKE_FLAT_BOUNDARIES",
        "ann_execution": "NOT_RUN",
        "real_provider_execution": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["passed"] != result["total"]:
        raise SystemExit(1)
