"""Execute the 16 deterministic Day95 boundary seeds."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = PROJECT_ROOT / "tests"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(TEST_ROOT))

SEED_PATH = Path(__file__).with_name("day95_rag_ingestion_seed.jsonl")


def load_cases() -> tuple[dict[str, object], ...]:
    return tuple(
        json.loads(line)
        for line in SEED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def evaluate_case(case: dict[str, object]) -> dict[str, object]:
    suite = unittest.defaultTestLoader.loadTestsFromName(str(case["test"]))
    result = unittest.TextTestRunner(
        stream=io.StringIO(),
        verbosity=0,
    ).run(suite)
    actual = "PASS" if result.wasSuccessful() else "FAIL"
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "expected_outcome": case["expected_outcome"],
        "actual_outcome": actual,
        "passed": actual == case["expected_outcome"],
    }


def run() -> dict[str, object]:
    results = tuple(evaluate_case(case) for case in load_cases())
    passed = sum(bool(item["passed"]) for item in results)
    return {
        "day": 95,
        "case_version": 1,
        "passed": passed,
        "total": len(results),
        "results": results,
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["passed"] == report["total"] else 1)
