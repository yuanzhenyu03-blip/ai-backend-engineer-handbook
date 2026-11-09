from __future__ import annotations

from dataclasses import replace
import unittest

from rag_answer_evaluator import AnswerEvaluator
from rag_citation_evaluator import CitationEvaluator
from rag_evaluation_dataset import (
    OCCURRENCE_B,
    build_correct_unfaithful_predictions,
    build_over_abstention_predictions,
    build_passing_predictions,
    build_refund_evaluation_dataset,
    build_slice_regression_predictions,
    build_superseded_release_predictions,
)


class Day103AnswerCitationTests(unittest.TestCase):
    def setUp(self) -> None:
        dataset = build_refund_evaluation_dataset()
        self.cases = {
            case.query.query_id: case for case in dataset.cases
        }
        self.answer = AnswerEvaluator()
        self.citation = CitationEvaluator()

    def test_passing_q3_is_correct_faithful_and_complete(self) -> None:
        prediction = build_passing_predictions()[2]
        answer = self.answer.evaluate(
            case=self.cases["Q3"], prediction=prediction
        )
        citation = self.citation.evaluate(
            case=self.cases["Q3"], prediction=prediction
        )
        self.assertEqual(answer.correctness, 1.0)
        self.assertEqual(answer.faithfulness, 1.0)
        self.assertEqual(answer.request_coverage, 1.0)
        self.assertEqual(citation.precision, 1.0)
        self.assertEqual(citation.coverage, 1.0)

    def test_correct_answer_can_be_unfaithful(self) -> None:
        prediction = build_correct_unfaithful_predictions()[0]
        answer = self.answer.evaluate(
            case=self.cases["Q1"], prediction=prediction
        )
        citation = self.citation.evaluate(
            case=self.cases["Q1"], prediction=prediction
        )
        self.assertEqual(answer.correctness, 1.0)
        self.assertEqual(answer.faithfulness, 0.0)
        self.assertEqual(answer.request_coverage, 0.0)
        self.assertEqual(citation.precision, 0.0)
        self.assertEqual(citation.coverage, 0.0)

    def test_old_policy_answer_can_be_faithful_but_incorrect(self) -> None:
        prediction = build_superseded_release_predictions()[0]
        answer = self.answer.evaluate(
            case=self.cases["Q1"], prediction=prediction
        )
        citation = self.citation.evaluate(
            case=self.cases["Q1"], prediction=prediction
        )
        self.assertEqual(answer.correctness, 0.0)
        self.assertEqual(answer.faithfulness, 1.0)
        self.assertEqual(citation.precision, 1.0)
        self.assertEqual(citation.coverage, 1.0)
        self.assertEqual(citation.superseded_release_count, 1)
        self.assertEqual(
            prediction.released_claims[0].day102_verification_relation,
            "SUPPORTED",
        )
        self.assertEqual(
            prediction.released_claims[0].citation_occurrence_ids,
            (OCCURRENCE_B,),
        )

    def test_valid_existing_citation_does_not_prove_request_coverage(self) -> None:
        prediction = build_slice_regression_predictions()[2]
        answer = self.answer.evaluate(
            case=self.cases["Q3"], prediction=prediction
        )
        citation = self.citation.evaluate(
            case=self.cases["Q3"], prediction=prediction
        )
        self.assertEqual(citation.precision, 1.0)
        self.assertEqual(citation.coverage, 1.0)
        self.assertEqual(answer.request_coverage, 0.5)

    def test_missing_citation_has_undefined_precision_and_zero_coverage(self) -> None:
        prediction = build_passing_predictions()[0]
        claim = replace(
            prediction.released_claims[0],
            citation_occurrence_ids=(),
        )
        prediction = replace(prediction, released_claims=(claim,))
        result = self.citation.evaluate(
            case=self.cases["Q1"], prediction=prediction
        )
        self.assertIsNone(result.precision)
        self.assertEqual(result.coverage, 0.0)

    def test_abstaining_with_available_evidence_is_over_abstention(self) -> None:
        prediction = build_over_abstention_predictions()[0]
        result = self.answer.evaluate(
            case=self.cases["Q1"], prediction=prediction
        )
        self.assertEqual(result.request_coverage, 0.0)
        self.assertEqual(result.over_abstention_count, 1)
        self.assertEqual(result.correct_abstention_count, 0)


if __name__ == "__main__":
    unittest.main()
