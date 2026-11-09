"""Pure retrieval metrics over independent Day103 relevance judgments."""

from __future__ import annotations

import math

from rag_evaluation_contracts import (
    EvaluationCase,
    RetrievalQueryResult,
    SystemQueryPrediction,
)


class RetrievalEvaluatorUnavailable(RuntimeError):
    """Raised when the retrieval evaluator cannot produce a valid result."""


class RetrievalEvaluator:
    def __init__(self, fail_query_ids: frozenset[str] = frozenset()) -> None:
        self._fail_query_ids = fail_query_ids

    @staticmethod
    def _dcg(grades: tuple[int, ...]) -> float:
        return sum(
            ((2 ** grade) - 1) / math.log2(rank + 1)
            for rank, grade in enumerate(grades, start=1)
        )

    def evaluate(
        self,
        *,
        case: EvaluationCase,
        prediction: SystemQueryPrediction,
        retrieval_k: int,
        ndcg_k: int,
    ) -> RetrievalQueryResult:
        query_id = case.query.query_id
        if query_id in self._fail_query_ids:
            raise RetrievalEvaluatorUnavailable(
                f"retrieval evaluator unavailable for {query_id}"
            )
        if prediction.query_id != query_id:
            raise ValueError("prediction Query does not match evaluation case")

        grades = {
            item.occurrence_id: (
                item.relevance_grade if item.policy_eligible else 0
            )
            for item in case.relevance_judgments
        }
        relevant_ids = {
            occurrence_id
            for occurrence_id, grade in grades.items()
            if grade > 0
        }
        if not relevant_ids:
            raise ValueError("retrieval evaluation requires a positive qrel")

        top_retrieval = prediction.ranked_occurrence_ids[:retrieval_k]
        relevant_retrieved = tuple(
            occurrence_id
            for occurrence_id in top_retrieval
            if occurrence_id in relevant_ids
        )
        unexpected_retrieved = tuple(
            occurrence_id
            for occurrence_id in top_retrieval
            if occurrence_id not in relevant_ids
        )
        precision = len(relevant_retrieved) / retrieval_k
        recall = len(set(relevant_retrieved)) / len(relevant_ids)

        first_relevant_rank = next((
            rank
            for rank, occurrence_id in enumerate(top_retrieval, start=1)
            if occurrence_id in relevant_ids
        ), None)
        reciprocal_rank = (
            0.0 if first_relevant_rank is None else 1 / first_relevant_rank
        )

        ranked_grades = tuple(
            grades.get(occurrence_id, 0)
            for occurrence_id in prediction.ranked_occurrence_ids[:ndcg_k]
        )
        dcg = self._dcg(ranked_grades)
        ideal_grades = tuple(sorted(grades.values(), reverse=True)[:ndcg_k])
        idcg = self._dcg(ideal_grades)
        ndcg = 0.0 if idcg == 0 else dcg / idcg

        return RetrievalQueryResult(
            query_id=query_id,
            precision_at_k=round(precision, 6),
            recall_at_k=round(recall, 6),
            reciprocal_rank=round(reciprocal_rank, 6),
            dcg_at_k=round(dcg, 6),
            ndcg_at_k=round(ndcg, 6),
            relevant_retrieved_ids=relevant_retrieved,
            unexpected_retrieved_ids=unexpected_retrieved,
        )
