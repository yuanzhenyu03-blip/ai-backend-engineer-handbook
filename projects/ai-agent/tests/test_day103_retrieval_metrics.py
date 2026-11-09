from __future__ import annotations

import unittest

from rag_evaluation_dataset import (
    OCCURRENCE_B,
    build_evaluation_run_request,
    build_refund_evaluation_dataset,
    build_slice_regression_predictions,
)
from rag_evaluation_contracts import RetrievalQueryResult
from rag_retrieval_evaluator import RetrievalEvaluator


class Day103RetrievalMetricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = build_refund_evaluation_dataset()
        self.cases = {
            case.query.query_id: case for case in self.dataset.cases
        }
        self.predictions = {
            item.query_id: item
            for item in build_slice_regression_predictions()
        }
        self.evaluator = RetrievalEvaluator()

    def evaluate(self, query_id: str) -> RetrievalQueryResult:
        return self.evaluator.evaluate(
            case=self.cases[query_id],
            prediction=self.predictions[query_id],
            retrieval_k=2,
            ndcg_k=3,
        )

    def test_q1_precision_recall_and_reciprocal_rank(self) -> None:
        result = self.evaluate("Q1")
        self.assertEqual(result.precision_at_k, 0.5)
        self.assertEqual(result.recall_at_k, 1.0)
        self.assertEqual(result.reciprocal_rank, 0.5)
        self.assertEqual(result.ndcg_at_k, 0.63093)

    def test_q3_metrics_capture_missing_second_relevant_source(self) -> None:
        result = self.evaluate("Q3")
        self.assertEqual(result.precision_at_k, 0.5)
        self.assertEqual(result.recall_at_k, 0.5)
        self.assertEqual(result.reciprocal_rank, 1.0)
        self.assertEqual(result.dcg_at_k, 1.5)
        self.assertEqual(result.ndcg_at_k, 0.919721)

    def test_superseded_b_is_not_a_positive_qrel(self) -> None:
        result = self.evaluate("Q1")
        self.assertIn(OCCURRENCE_B, result.unexpected_retrieved_ids)
        qrel = next(
            item
            for item in self.cases["Q1"].relevance_judgments
            if item.occurrence_id == OCCURRENCE_B
        )
        self.assertFalse(qrel.policy_eligible)
        self.assertEqual(qrel.relevance_grade, 0)

    def test_overall_regression_metrics_match_closed_book_exercise(self) -> None:
        request = build_evaluation_run_request(
            predictions=build_slice_regression_predictions()
        )
        results = [
            self.evaluator.evaluate(
                case=case,
                prediction=self.predictions[case.query.query_id],
                retrieval_k=request.policy.retrieval_k,
                ndcg_k=request.policy.ndcg_k,
            )
            for case in request.dataset.cases
        ]
        self.assertAlmostEqual(
            sum(item.recall_at_k for item in results) / 3,
            0.8333333333,
        )
        self.assertAlmostEqual(
            sum(item.reciprocal_rank for item in results) / 3,
            0.8333333333,
        )


if __name__ == "__main__":
    unittest.main()
