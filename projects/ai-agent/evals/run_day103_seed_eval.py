from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from rag_answer_evaluator import AnswerEvaluator  # noqa: E402
from rag_citation_evaluator import CitationEvaluator  # noqa: E402
from rag_evaluation_dataset import (  # noqa: E402
    build_correct_unfaithful_predictions,
    build_evaluation_run_request,
    build_over_abstention_predictions,
    build_slice_regression_predictions,
    build_superseded_release_predictions,
)
from rag_evaluation_orchestrator import EvaluationOrchestrator  # noqa: E402
from rag_retrieval_evaluator import RetrievalEvaluator  # noqa: E402


SEED_PATH = ROOT / "evals" / "day103_rag_evaluation_seed.jsonl"
ALL_QUERY_IDS = frozenset({"Q1", "Q2", "Q3"})


def _run_case(case: dict[str, object]) -> tuple[bool, dict[str, object]]:
    case_id = str(case["case_id"])
    predictions = None
    retrieval_failures: frozenset[str] = frozenset()
    answer_failures: frozenset[str] = frozenset()
    citation_failures: frozenset[str] = frozenset()

    if case_id == "slice-regression":
        predictions = build_slice_regression_predictions()
    elif case_id == "superseded-release":
        predictions = build_superseded_release_predictions()
    elif case_id == "correct-unfaithful":
        predictions = build_correct_unfaithful_predictions()
    elif case_id == "over-abstention":
        predictions = build_over_abstention_predictions()
    elif case_id == "answer-timeout":
        answer_failures = frozenset({"Q3"})
    elif case_id == "retrieval-timeout":
        retrieval_failures = frozenset({"Q3"})
    elif case_id == "citation-timeout":
        citation_failures = frozenset({"Q3"})
    elif case_id == "all-evaluators-timeout":
        retrieval_failures = ALL_QUERY_IDS
        answer_failures = ALL_QUERY_IDS
        citation_failures = ALL_QUERY_IDS
    elif case_id == "observed-gate-plus-timeout":
        predictions = build_superseded_release_predictions()
        answer_failures = frozenset({"Q3"})

    report = EvaluationOrchestrator(
        retrieval_evaluator=RetrievalEvaluator(retrieval_failures),
        answer_evaluator=AnswerEvaluator(answer_failures),
        citation_evaluator=CitationEvaluator(citation_failures),
    ).evaluate(build_evaluation_run_request(
        predictions=predictions,
        system_version=f"seed-system:{case_id}",
        run_id=f"seed-run:{case_id}",
    ))
    request_coverage = next(
        item
        for item in report.metrics
        if item.metric_name == "request_coverage"
    )
    multi_facet = next(
        item
        for item in report.slices
        if item.slice_name == "multi-facet"
    ).metrics[0]
    superseded_gate = next(
        item
        for item in report.hard_gates
        if item.gate_name == "superseded_source_release_count"
    )
    actual: dict[str, object] = {
        "decision": report.decision.value,
        "decision_reason": report.decision_reason,
        "failure_count": len(report.failures),
        "request_coverage_status": request_coverage.status.value,
        "multi_facet_status": multi_facet.status.value,
        "superseded_gate": superseded_gate.passed,
    }
    expected = dict(case["expected"])
    passed = all(actual.get(key) == value for key, value in expected.items())
    return passed, {
        "case_id": case_id,
        "passed": passed,
        "expected": expected,
        "actual": actual,
    }


def run() -> dict[str, object]:
    cases = [
        json.loads(line)
        for line in SEED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results = [_run_case(case) for case in cases]
    return {
        "cases": len(results),
        "passed": sum(passed for passed, _ in results),
        "all_passed": all(passed for passed, _ in results),
        "results": [detail for _, detail in results],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
