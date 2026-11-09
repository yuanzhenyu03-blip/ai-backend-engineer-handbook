"""Independent correctness, faithfulness, coverage and Abstention evaluation."""

from __future__ import annotations

from rag_evaluation_contracts import (
    AnswerQueryResult,
    EvaluationCase,
    ExpectedAction,
    PredictedClaim,
    SupportRelation,
    SystemQueryPrediction,
)


class AnswerEvaluatorUnavailable(RuntimeError):
    """Raised when answer evaluation cannot produce a valid result."""


class AnswerEvaluator:
    def __init__(self, fail_query_ids: frozenset[str] = frozenset()) -> None:
        self._fail_query_ids = fail_query_ids

    @staticmethod
    def _is_correct(case: EvaluationCase, claim: PredictedClaim) -> bool:
        label = next(
            item
            for item in case.request_item_labels
            if item.request_item_id == claim.request_item_id
        )
        return (
            label.expected_action is ExpectedAction.ANSWER
            and label.protected_expected_value is not None
            and claim.protected_value.strip().casefold()
            == label.protected_expected_value.strip().casefold()
        )

    @staticmethod
    def _relations(
        case: EvaluationCase,
        claim: PredictedClaim,
    ) -> tuple[SupportRelation, ...]:
        lookup = {
            (
                item.request_item_id,
                item.claim_value_digest,
                item.occurrence_id,
            ): item.relation
            for item in case.citation_support_labels
        }
        return tuple(
            lookup.get(
                (
                    claim.request_item_id,
                    claim.value_digest,
                    occurrence_id,
                ),
                SupportRelation.UNSUPPORTED,
            )
            for occurrence_id in claim.citation_occurrence_ids
        )

    @classmethod
    def _is_faithful(
        cls,
        case: EvaluationCase,
        claim: PredictedClaim,
    ) -> bool:
        relations = cls._relations(case, claim)
        return (
            SupportRelation.SUPPORTED in relations
            and SupportRelation.CONTRADICTED not in relations
            and SupportRelation.UNAVAILABLE not in relations
        )

    def evaluate(
        self,
        *,
        case: EvaluationCase,
        prediction: SystemQueryPrediction,
    ) -> AnswerQueryResult:
        query_id = case.query.query_id
        if query_id in self._fail_query_ids:
            raise AnswerEvaluatorUnavailable(
                f"answer evaluator unavailable for {query_id}"
            )
        if prediction.query_id != query_id:
            raise ValueError("prediction Query does not match evaluation case")

        claims = prediction.released_claims
        correct_by_claim = {
            claim.claim_id: self._is_correct(case, claim) for claim in claims
        }
        faithful_by_claim = {
            claim.claim_id: self._is_faithful(case, claim) for claim in claims
        }
        claims_by_item = {
            label.request_item_id: tuple(
                claim
                for claim in claims
                if claim.request_item_id == label.request_item_id
            )
            for label in case.request_item_labels
        }
        abstained_ids = set(prediction.abstained_request_item_ids)
        request_coverage_numerator = 0
        correct_abstention_count = 0
        over_abstention_count = 0
        missed_abstention_count = 0

        for label in case.request_item_labels:
            item_claims = claims_by_item[label.request_item_id]
            abstained = label.request_item_id in abstained_ids
            if label.expected_action is ExpectedAction.ABSTAIN:
                if abstained and not item_claims:
                    correct_abstention_count += 1
                    request_coverage_numerator += 1
                else:
                    missed_abstention_count += 1
                continue
            if abstained:
                over_abstention_count += 1
            if any(
                correct_by_claim[claim.claim_id]
                and faithful_by_claim[claim.claim_id]
                for claim in item_claims
            ):
                request_coverage_numerator += 1

        return AnswerQueryResult(
            query_id=query_id,
            correctness_numerator=sum(correct_by_claim.values()),
            correctness_denominator=len(claims),
            faithfulness_numerator=sum(faithful_by_claim.values()),
            faithfulness_denominator=len(claims),
            request_coverage_numerator=request_coverage_numerator,
            request_coverage_denominator=len(case.request_item_labels),
            correct_abstention_count=correct_abstention_count,
            over_abstention_count=over_abstention_count,
            missed_abstention_count=missed_abstention_count,
        )
