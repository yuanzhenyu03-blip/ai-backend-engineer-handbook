from __future__ import annotations

from dataclasses import replace
import unittest

from rag_evaluation_dataset import (
    build_evaluation_run_request,
    build_refund_evaluation_dataset,
    build_slice_regression_predictions,
)
from rag_evaluation_orchestrator import EvaluationOrchestrator
from rag_evaluation_validator import (
    EvaluationValidationError,
    EvaluationValidator,
)


class Day103EvaluationContractTests(unittest.TestCase):
    def test_fixed_dataset_identity_validates(self) -> None:
        dataset = build_refund_evaluation_dataset()
        EvaluationValidator().validate_dataset(dataset)
        self.assertEqual(len(dataset.cases), 3)
        self.assertTrue(dataset.fingerprint.startswith("sha256:"))

    def test_tampered_query_set_digest_is_rejected(self) -> None:
        dataset = build_refund_evaluation_dataset()
        tampered = replace(
            dataset,
            identity=replace(
                dataset.identity,
                query_set_digest="sha256:tampered",
            ),
        )
        with self.assertRaisesRegex(
            EvaluationValidationError, "query-set digest"
        ):
            EvaluationValidator().validate_dataset(tampered)

    def test_run_identity_must_bind_dataset(self) -> None:
        request = build_evaluation_run_request()
        tampered = replace(
            request,
            identity=replace(
                request.identity,
                dataset_fingerprint="sha256:tampered",
            ),
        )
        with self.assertRaisesRegex(
            EvaluationValidationError, "dataset identity"
        ):
            EvaluationValidator().validate_run(tampered)

    def test_predictions_must_exactly_cover_dataset(self) -> None:
        request = build_evaluation_run_request()
        incomplete = replace(request, predictions=request.predictions[:2])
        with self.assertRaisesRegex(
            EvaluationValidationError, "exactly cover"
        ):
            EvaluationValidator().validate_run(incomplete)

    def test_baseline_and_candidate_are_comparable_on_same_ruler(self) -> None:
        orchestrator = EvaluationOrchestrator()
        baseline = orchestrator.evaluate(build_evaluation_run_request(
            system_version="baseline-v1",
            run_id="baseline-run",
        ))
        candidate = orchestrator.evaluate(build_evaluation_run_request(
            predictions=build_slice_regression_predictions(),
            system_version="candidate-v1",
            run_id="candidate-run",
        ))
        orchestrator.validate_comparable(baseline, candidate)

    def test_same_system_identity_is_not_a_regression_comparison(self) -> None:
        orchestrator = EvaluationOrchestrator()
        baseline = orchestrator.evaluate(build_evaluation_run_request(
            system_version="same-v1",
            run_id="left-run",
        ))
        candidate = orchestrator.evaluate(build_evaluation_run_request(
            system_version="same-v1",
            run_id="right-run",
        ))
        with self.assertRaisesRegex(
            EvaluationValidationError, "system identities"
        ):
            orchestrator.validate_comparable(baseline, candidate)


if __name__ == "__main__":
    unittest.main()
