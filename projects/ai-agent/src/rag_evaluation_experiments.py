"""Content-safe replayable Day103 evaluation-mechanics experiment."""

from __future__ import annotations

from rag_answer_evaluator import AnswerEvaluator
from rag_chunking_contracts import stable_hash
from rag_evaluation_dataset import (
    build_correct_unfaithful_predictions,
    build_evaluation_run_request,
    build_over_abstention_predictions,
    build_slice_regression_predictions,
    build_superseded_release_predictions,
)
from rag_evaluation_contracts import SystemQueryPrediction
from rag_evaluation_orchestrator import EvaluationOrchestrator


def _case(
    case_id: str,
    *,
    predictions: tuple[SystemQueryPrediction, ...] | None = None,
    fail_answer_query_ids: frozenset[str] = frozenset(),
) -> dict[str, object]:
    orchestrator = EvaluationOrchestrator(
        answer_evaluator=AnswerEvaluator(fail_answer_query_ids)
    )
    report = orchestrator.evaluate(build_evaluation_run_request(
        predictions=predictions,
        system_version=f"system:{case_id}",
        run_id=f"run:{case_id}",
    ))
    return {
        "case_id": case_id,
        "decision": report.decision.value,
        "decision_reason": report.decision_reason,
        "metrics": tuple((
            item.metric_name,
            item.value,
            item.status.value,
        ) for item in report.metrics),
        "slices": tuple((
            item.slice_name,
            item.sample_size,
            tuple((
                metric.metric_name,
                metric.value,
                metric.status.value,
            ) for metric in item.metrics),
        ) for item in report.slices),
        "hard_gates": tuple((
            item.gate_name,
            item.passed,
            item.observed_value,
        ) for item in report.hard_gates),
        "failure_reasons": tuple(
            item.reason.value for item in report.failures
        ),
        "report_checksum": report.checksum,
    }


def run_controlled_experiment() -> dict[str, object]:
    cases = (
        _case("passing-baseline"),
        _case(
            "slice-and-coverage-regression",
            predictions=build_slice_regression_predictions(),
        ),
        _case(
            "superseded-source-release",
            predictions=build_superseded_release_predictions(),
        ),
        _case(
            "correct-but-unfaithful",
            predictions=build_correct_unfaithful_predictions(),
        ),
        _case(
            "over-abstention",
            predictions=build_over_abstention_predictions(),
        ),
        _case(
            "answer-evaluator-timeout",
            fail_answer_query_ids=frozenset({"Q3"}),
        ),
    )
    report: dict[str, object] = {
        "experiment_kind": "EVALUATION_MECHANICS_EXPERIMENT",
        "experiment_warning": (
            "deterministic mechanics are not real RAG quality evidence"
        ),
        "evidence_level": (
            "EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"
        ),
        "fixture_scope": "DAY103_REFUND_CLASSROOM_ONLY",
        "fixture_production_eligible": False,
        "ground_truth_owner": "independent-label-review-adjudication-v1",
        "day102_verification_is_ground_truth": False,
        "cases": cases,
        "real_retriever": "NOT_RUN",
        "real_generator": "NOT_RUN",
        "real_independent_human_labels": "NOT_RUN",
        "calibrated_llm_judge": "NOT_RUN",
        "real_latency_capacity_cost_error_rate": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "raw_queries_in_report": False,
        "protected_claims_in_report": False,
        "protected_evidence_in_report": False,
        "provider_payloads_in_report": False,
    }
    report["fixture_checksum"] = stable_hash((
        report["experiment_kind"],
        report["fixture_scope"],
        tuple(case["case_id"] for case in cases),
    ))
    report["report_checksum"] = stable_hash(report)
    return report
