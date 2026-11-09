"""Independent Citation precision, coverage and eligibility evaluation."""

from __future__ import annotations

from rag_evaluation_contracts import (
    CitationQueryResult,
    EvaluationCase,
    SupportRelation,
    SystemQueryPrediction,
)


class CitationEvaluatorUnavailable(RuntimeError):
    """Raised when Citation evaluation cannot produce a valid result."""


class CitationEvaluator:
    def __init__(self, fail_query_ids: frozenset[str] = frozenset()) -> None:
        self._fail_query_ids = fail_query_ids

    def evaluate(
        self,
        *,
        case: EvaluationCase,
        prediction: SystemQueryPrediction,
    ) -> CitationQueryResult:
        query_id = case.query.query_id
        if query_id in self._fail_query_ids:
            raise CitationEvaluatorUnavailable(
                f"citation evaluator unavailable for {query_id}"
            )
        if prediction.query_id != query_id:
            raise ValueError("prediction Query does not match evaluation case")

        support_lookup = {
            (
                item.request_item_id,
                item.claim_value_digest,
                item.occurrence_id,
            ): item.relation
            for item in case.citation_support_labels
        }
        known_occurrence_ids = {
            item.occurrence_id for item in case.relevance_judgments
        }
        ineligible_occurrence_ids = {
            item.occurrence_id
            for item in case.relevance_judgments
            if not item.policy_eligible
        }
        precision_numerator = 0
        precision_denominator = 0
        coverage_numerator = 0
        superseded_release_count = 0
        unknown_citation_count = 0

        for claim in prediction.released_claims:
            claim_supported = False
            for occurrence_id in claim.citation_occurrence_ids:
                precision_denominator += 1
                relation = support_lookup.get((
                    claim.request_item_id,
                    claim.value_digest,
                    occurrence_id,
                ))
                if relation is SupportRelation.SUPPORTED:
                    precision_numerator += 1
                    claim_supported = True
                if occurrence_id not in known_occurrence_ids or relation is None:
                    unknown_citation_count += 1
                if occurrence_id in ineligible_occurrence_ids:
                    superseded_release_count += 1
            if claim_supported:
                coverage_numerator += 1

        return CitationQueryResult(
            query_id=query_id,
            precision_numerator=precision_numerator,
            precision_denominator=precision_denominator,
            coverage_numerator=coverage_numerator,
            coverage_denominator=len(prediction.released_claims),
            superseded_release_count=superseded_release_count,
            unknown_citation_count=unknown_citation_count,
        )
