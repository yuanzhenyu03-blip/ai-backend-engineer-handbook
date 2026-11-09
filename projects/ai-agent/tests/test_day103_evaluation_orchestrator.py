from __future__ import annotations

import unittest

from rag_answer_evaluator import AnswerEvaluator
from rag_evaluation_contracts import (
    EvaluationReport,
    HardGateResult,
    MetricResult,
    MetricStatus,
    RegressionDecisionStatus,
)
from rag_evaluation_dataset import (
    build_evaluation_run_request,
    build_slice_regression_predictions,
    build_superseded_release_predictions,
)
from rag_evaluation_orchestrator import EvaluationOrchestrator
from evals.run_day103_evidence_replay import run as replay_evidence


def metric(report: EvaluationReport, name: str) -> MetricResult:
    return next(item for item in report.metrics if item.metric_name == name)


def gate(report: EvaluationReport, name: str) -> HardGateResult:
    return next(item for item in report.hard_gates if item.gate_name == name)


class Day103EvaluationOrchestratorTests(unittest.TestCase):
    def test_passing_fixture_passes_all_thresholds_and_gates(self) -> None:
        report = EvaluationOrchestrator().evaluate(
            build_evaluation_run_request()
        )
        self.assertIs(report.decision, RegressionDecisionStatus.PASS)
        self.assertTrue(all(item.passed for item in report.hard_gates))
        self.assertEqual(metric(report, "recall_at_2").value, 1.0)
        self.assertEqual(metric(report, "request_coverage").value, 1.0)

    def test_overall_pass_does_not_hide_slice_and_coverage_failure(self) -> None:
        report = EvaluationOrchestrator().evaluate(
            build_evaluation_run_request(
                predictions=build_slice_regression_predictions()
            )
        )
        self.assertIs(report.decision, RegressionDecisionStatus.FAIL)
        self.assertEqual(metric(report, "recall_at_2").value, 0.833333)
        self.assertIs(metric(report, "recall_at_2").status, MetricStatus.PASS)
        multi = next(
            item for item in report.slices if item.slice_name == "multi-facet"
        )
        self.assertEqual(multi.metrics[0].value, 0.5)
        self.assertIs(multi.metrics[0].status, MetricStatus.FAIL)
        self.assertFalse(gate(report, "per_query_request_coverage").passed)

    def test_superseded_release_is_non_compensable_hard_gate(self) -> None:
        report = EvaluationOrchestrator().evaluate(
            build_evaluation_run_request(
                predictions=build_superseded_release_predictions()
            )
        )
        self.assertIs(report.decision, RegressionDecisionStatus.FAIL)
        superseded = gate(report, "superseded_source_release_count")
        self.assertFalse(superseded.passed)
        self.assertEqual(superseded.observed_value, 1)

    def test_evaluator_timeout_makes_run_inconclusive(self) -> None:
        report = EvaluationOrchestrator(
            answer_evaluator=AnswerEvaluator(frozenset({"Q3"}))
        ).evaluate(build_evaluation_run_request())
        self.assertIs(report.decision, RegressionDecisionStatus.INCONCLUSIVE)
        self.assertEqual(report.decision_reason, "EVALUATOR_FAILURE")
        self.assertEqual(len(report.failures), 1)
        self.assertIs(
            metric(report, "request_coverage").status,
            MetricStatus.NOT_RUN,
        )
        self.assertIsNone(gate(report, "per_query_request_coverage").passed)

    def test_observed_hard_gate_failure_wins_over_timeout(self) -> None:
        report = EvaluationOrchestrator(
            answer_evaluator=AnswerEvaluator(frozenset({"Q3"}))
        ).evaluate(build_evaluation_run_request(
            predictions=build_superseded_release_predictions()
        ))
        self.assertIs(report.decision, RegressionDecisionStatus.FAIL)
        self.assertEqual(
            report.decision_reason, "OBSERVED_HARD_GATE_VIOLATION"
        )

    def test_report_is_content_safe_and_honest(self) -> None:
        report = EvaluationOrchestrator().evaluate(
            build_evaluation_run_request()
        )
        payload = report.safe_payload()
        self.assertFalse(payload["raw_queries_logged"])
        self.assertFalse(payload["protected_claims_logged"])
        self.assertFalse(payload["protected_evidence_logged"])
        self.assertIn("real_retrieval_relevance", report.not_run)
        self.assertEqual(report.production_readiness, "MORE_EVIDENCE_NEEDED")
        self.assertTrue(report.checksum.startswith("sha256:"))

    def test_day104_handoff_binds_report_and_evidence_level(self) -> None:
        orchestrator = EvaluationOrchestrator()
        report = orchestrator.evaluate(build_evaluation_run_request())
        handoff = orchestrator.build_day104_handoff(report)
        self.assertEqual(handoff.evaluation_report_checksum, report.checksum)
        self.assertEqual(handoff.decision, report.decision)
        self.assertEqual(handoff.evidence_level, report.evidence_level)
        self.assertTrue(handoff.digest.startswith("sha256:"))

    def test_saved_evidence_replays_exactly(self) -> None:
        replay = replay_evidence()
        self.assertEqual(replay["status"], "PASS")
        self.assertTrue(all(replay["checks"].values()))


if __name__ == "__main__":
    unittest.main()
