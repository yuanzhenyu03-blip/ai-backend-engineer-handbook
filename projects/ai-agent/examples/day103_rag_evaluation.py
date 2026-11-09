"""Executable Day103 retrieval and grounded-answer evaluation fixture."""

from __future__ import annotations

import json

from rag_answer_evaluator import AnswerEvaluator
from rag_evaluation_dataset import (
    build_evaluation_run_request,
    build_refund_evaluation_dataset,
    build_slice_regression_predictions,
    build_superseded_release_predictions,
)
from rag_evaluation_contracts import EvaluationReport
from rag_evaluation_orchestrator import EvaluationOrchestrator


def _summary(report: EvaluationReport) -> dict[str, object]:
    return {
        "decision": report.decision.value,
        "decision_reason": report.decision_reason,
        "metrics": {
            item.metric_name: item.value for item in report.metrics
        },
        "metric_statuses": {
            item.metric_name: item.status.value for item in report.metrics
        },
        "slices": {
            item.slice_name: {
                metric.metric_name: metric.value for metric in item.metrics
            }
            for item in report.slices
        },
        "hard_gates": {
            item.gate_name: item.passed for item in report.hard_gates
        },
        "failure_count": len(report.failures),
        "evidence_level": report.evidence_level.value,
        "production_readiness": report.production_readiness,
        "report_checksum": report.checksum,
    }


def run_example() -> dict[str, object]:
    dataset = build_refund_evaluation_dataset()
    orchestrator = EvaluationOrchestrator()
    passing = orchestrator.evaluate(build_evaluation_run_request(
        system_version="day103-baseline-v1",
        run_id="day103-example-baseline",
    ))
    regression = orchestrator.evaluate(build_evaluation_run_request(
        predictions=build_slice_regression_predictions(),
        system_version="day103-candidate-regression-v1",
        run_id="day103-example-regression",
    ))
    superseded = orchestrator.evaluate(build_evaluation_run_request(
        predictions=build_superseded_release_predictions(),
        system_version="day103-candidate-superseded-v1",
        run_id="day103-example-superseded",
    ))
    timeout = EvaluationOrchestrator(
        answer_evaluator=AnswerEvaluator(frozenset({"Q3"}))
    ).evaluate(build_evaluation_run_request(
        system_version="day103-candidate-timeout-v1",
        run_id="day103-example-timeout",
    ))
    return {
        "experiment_kind": "EVALUATION_MECHANICS_EXPERIMENT",
        "dataset_fingerprint": dataset.fingerprint,
        "query_ids": tuple(case.query.query_id for case in dataset.cases),
        "ground_truth_owner": (
            "independent-label-review-adjudication-v1"
        ),
        "day102_verification_is_ground_truth": False,
        "passing": _summary(passing),
        "slice_regression": _summary(regression),
        "superseded_release": _summary(superseded),
        "evaluator_timeout": _summary(timeout),
        "raw_queries_in_output": False,
        "protected_claims_in_output": False,
        "protected_evidence_in_output": False,
        "real_retriever": "NOT_RUN",
        "real_generator": "NOT_RUN",
        "real_independent_human_label_set": "NOT_RUN",
        "calibrated_llm_judge": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2, sort_keys=True))
