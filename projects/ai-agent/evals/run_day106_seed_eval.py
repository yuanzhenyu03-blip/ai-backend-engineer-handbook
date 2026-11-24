"""Evaluate the deterministic Day106 capstone seed assertions."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from examples.day106_production_rag_capstone import run_example  # noqa: E402


SEED_PATH = ROOT / "evals" / "day106_production_rag_capstone_seed.jsonl"


def load_cases() -> tuple[dict[str, Any], ...]:
    """Load stable seed assertions in file order."""

    return tuple(
        json.loads(line)
        for line in SEED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _read_path(payload: object, path: list[object]) -> object:
    current = payload
    for segment in path:
        if isinstance(current, dict) and isinstance(segment, str):
            current = current[segment]
        elif isinstance(current, list) and isinstance(segment, int):
            current = current[segment]
        else:
            raise ValueError(f"invalid seed path segment: {segment!r}")
    return current


def run() -> dict[str, object]:
    """Run the cumulative fixture once and grade every content-safe assertion."""

    report = run_example()
    results: list[dict[str, object]] = []
    for case in load_cases():
        case_id = case.get("case_id")
        path = case.get("path")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("seed case_id must be non-empty")
        if not isinstance(path, list) or not path:
            raise ValueError("seed path must be a non-empty list")
        actual = _read_path(report, path)
        expected = case.get("expected")
        results.append(
            {
                "case_id": case_id,
                "passed": actual == expected,
                "expected": expected,
                "actual": actual,
            }
        )
    return {
        "cases": len(results),
        "passed": sum(bool(item["passed"]) for item in results),
        "failed": sum(not bool(item["passed"]) for item in results),
        "all_passed": all(bool(item["passed"]) for item in results),
        "results": results,
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["all_passed"] is True else 1)
