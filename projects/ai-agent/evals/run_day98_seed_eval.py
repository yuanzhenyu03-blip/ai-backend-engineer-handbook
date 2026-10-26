"""Content-safe deterministic Day98 boundary evaluator."""

from __future__ import annotations

import json
from pathlib import Path

from examples.day98_embedding_selection_versioning import (
    build_day98_fixture,
    run_request,
)
from rag_embedding_adapter import FakeResponseMode


SEED_PATH = Path(__file__).with_name(
    "day98_embedding_selection_versioning_seed.jsonl"
)


def run(path: Path = SEED_PATH) -> dict[str, object]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        fixture = build_day98_fixture(mode=FakeResponseMode(item["mode"]))
        result = run_request(fixture)
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
        "passed": sum(case["passed"] for case in cases),
        "total": len(cases),
        "cases": cases,
        "vectors_in_report": False,
        "evidence_scope": "DAY98_DETERMINISTIC_FAKE_BOUNDARIES",
        "real_provider_execution": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["passed"] != result["total"]:
        raise SystemExit(1)
