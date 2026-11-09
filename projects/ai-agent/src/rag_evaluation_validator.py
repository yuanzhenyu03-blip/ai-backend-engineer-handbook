"""Fail-closed correlation and comparability checks for Day103 evaluation."""

from __future__ import annotations

from rag_evaluation_contracts import (
    EvaluationDataset,
    EvaluationReport,
    EvaluationRunRequest,
    evaluation_query_set_digest,
)


class EvaluationValidationError(ValueError):
    """Raised when evaluation identities or correlations are invalid."""


class EvaluationValidator:
    def validate_dataset(self, dataset: EvaluationDataset) -> None:
        if (
            evaluation_query_set_digest(dataset.cases)
            != dataset.identity.query_set_digest
        ):
            raise EvaluationValidationError("evaluation query-set digest mismatch")

        for case in dataset.cases:
            query_id = case.query.query_id
            qrel_ids = [
                item.occurrence_id for item in case.relevance_judgments
            ]
            if len(set(qrel_ids)) != len(qrel_ids):
                raise EvaluationValidationError("duplicate relevance judgment")
            if any(
                item.query_id != query_id
                for item in case.relevance_judgments
            ):
                raise EvaluationValidationError("qrel Query correlation mismatch")
            if not any(
                item.policy_eligible and item.relevance_grade > 0
                for item in case.relevance_judgments
            ):
                raise EvaluationValidationError(
                    "every retrieval case requires a positive eligible qrel"
                )

            label_item_ids = [
                item.request_item_id for item in case.request_item_labels
            ]
            if set(label_item_ids) != set(case.query.request_item_ids):
                raise EvaluationValidationError(
                    "request-item labels must exactly cover the Query"
                )
            if len(set(label_item_ids)) != len(label_item_ids):
                raise EvaluationValidationError("duplicate request-item label")
            for item_label in case.request_item_labels:
                if item_label.query_id != query_id:
                    raise EvaluationValidationError(
                        "request-item label Query correlation mismatch"
                    )
                if (
                    item_label.labeling_policy_revision
                    != dataset.identity.label_policy_revision
                    or item_label.adjudication_revision
                    != dataset.identity.adjudication_revision
                ):
                    raise EvaluationValidationError(
                        "request-item label revision mismatch"
                    )

            support_keys: set[tuple[str, str, str]] = set()
            for support_label in case.citation_support_labels:
                if support_label.query_id != query_id:
                    raise EvaluationValidationError(
                        "Citation label Query correlation mismatch"
                    )
                if (
                    support_label.request_item_id
                    not in case.query.request_item_ids
                ):
                    raise EvaluationValidationError(
                        "Citation label has unknown request item"
                    )
                if support_label.occurrence_id not in qrel_ids:
                    raise EvaluationValidationError(
                        "Citation label has unknown source occurrence"
                    )
                if (
                    support_label.source_snapshot_digest
                    != dataset.identity.source_snapshot_digest
                    or support_label.adjudication_revision
                    != dataset.identity.adjudication_revision
                ):
                    raise EvaluationValidationError(
                        "Citation label snapshot or adjudication mismatch"
                    )
                key = (
                    support_label.request_item_id,
                    support_label.claim_value_digest,
                    support_label.occurrence_id,
                )
                if key in support_keys:
                    raise EvaluationValidationError(
                        "duplicate Citation support label"
                    )
                support_keys.add(key)

    def validate_run(self, request: EvaluationRunRequest) -> None:
        self.validate_dataset(request.dataset)
        identity = request.identity
        if identity.dataset_fingerprint != request.dataset.fingerprint:
            raise EvaluationValidationError("run dataset identity mismatch")
        if (
            identity.system_under_test_fingerprint
            != request.system_under_test.fingerprint
        ):
            raise EvaluationValidationError("run system identity mismatch")
        if identity.evaluator_fingerprint != request.evaluator.fingerprint:
            raise EvaluationValidationError("run evaluator identity mismatch")
        if identity.policy_fingerprint != request.policy.fingerprint:
            raise EvaluationValidationError("run policy identity mismatch")

        prediction_by_query = {
            item.query_id: item for item in request.predictions
        }
        if len(prediction_by_query) != len(request.predictions):
            raise EvaluationValidationError("duplicate system Query prediction")
        expected_query_ids = {
            case.query.query_id for case in request.dataset.cases
        }
        if set(prediction_by_query) != expected_query_ids:
            raise EvaluationValidationError(
                "system predictions must exactly cover the dataset"
            )

        for case in request.dataset.cases:
            prediction = prediction_by_query[case.query.query_id]
            known_occurrence_ids = {
                item.occurrence_id for item in case.relevance_judgments
            }
            if not set(prediction.ranked_occurrence_ids).issubset(
                known_occurrence_ids
            ):
                raise EvaluationValidationError(
                    "ranked prediction references unknown source snapshot"
                )
            request_item_ids = set(case.query.request_item_ids)
            claim_item_ids = {
                claim.request_item_id for claim in prediction.released_claims
            }
            if not claim_item_ids.issubset(request_item_ids):
                raise EvaluationValidationError(
                    "predicted Claim references unknown request item"
                )
            if not set(prediction.abstained_request_item_ids).issubset(
                request_item_ids
            ):
                raise EvaluationValidationError(
                    "Abstention references unknown request item"
                )
            if claim_item_ids.intersection(
                prediction.abstained_request_item_ids
            ):
                raise EvaluationValidationError(
                    "one request item cannot be answered and abstained"
                )
            for claim in prediction.released_claims:
                if not set(claim.citation_occurrence_ids).issubset(
                    known_occurrence_ids
                ):
                    raise EvaluationValidationError(
                        "predicted Claim cites an unknown source occurrence"
                    )

    def validate_comparable(
        self,
        baseline: EvaluationReport,
        candidate: EvaluationReport,
    ) -> None:
        left = baseline.run_identity
        right = candidate.run_identity
        stable_identities = (
            "dataset_fingerprint",
            "evaluator_fingerprint",
            "policy_fingerprint",
        )
        for field_name in stable_identities:
            if getattr(left, field_name) != getattr(right, field_name):
                raise EvaluationValidationError(
                    f"incomparable reports: {field_name} differs"
                )
        if (
            left.system_under_test_fingerprint
            == right.system_under_test_fingerprint
        ):
            raise EvaluationValidationError(
                "baseline and candidate system identities must differ"
            )
