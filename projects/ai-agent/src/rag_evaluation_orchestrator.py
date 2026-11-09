"""Day103 evaluation orchestration, aggregation and fail-closed decisions."""

from __future__ import annotations

from rag_answer_evaluator import (
    AnswerEvaluator,
    AnswerEvaluatorUnavailable,
)
from rag_citation_evaluator import (
    CitationEvaluator,
    CitationEvaluatorUnavailable,
)
from rag_evaluation_contracts import (
    AnswerQueryResult,
    CitationQueryResult,
    Day104BaselineHandoff,
    EvaluationFailureReason,
    EvaluationReport,
    EvaluationRunRequest,
    EvaluatorFailure,
    EvidenceLevel,
    HardGateResult,
    MetricResult,
    MetricStatus,
    RegressionDecisionStatus,
    RetrievalQueryResult,
    SliceResult,
)
from rag_evaluation_validator import EvaluationValidator
from rag_retrieval_evaluator import (
    RetrievalEvaluator,
    RetrievalEvaluatorUnavailable,
)


class EvaluationOrchestrator:
    def __init__(
        self,
        *,
        retrieval_evaluator: RetrievalEvaluator | None = None,
        answer_evaluator: AnswerEvaluator | None = None,
        citation_evaluator: CitationEvaluator | None = None,
        validator: EvaluationValidator | None = None,
    ) -> None:
        self._retrieval = retrieval_evaluator or RetrievalEvaluator()
        self._answer = answer_evaluator or AnswerEvaluator()
        self._citation = citation_evaluator or CitationEvaluator()
        self._validator = validator or EvaluationValidator()

    @staticmethod
    def _metric(
        *,
        name: str,
        scope: str,
        numerator: float,
        denominator: int,
        threshold: float | None,
        complete: bool,
        reason: str,
    ) -> MetricResult:
        value = None if denominator == 0 else round(numerator / denominator, 6)
        if value is None or not complete:
            status = MetricStatus.NOT_RUN
        elif threshold is not None and value < threshold:
            status = MetricStatus.FAIL
        else:
            status = MetricStatus.PASS
        return MetricResult(
            metric_name=name,
            scope=scope,
            numerator=round(numerator, 6),
            denominator=denominator,
            value=value,
            threshold=threshold,
            status=status,
            reason=reason,
        )

    def _retrieval_metrics(
        self,
        request: EvaluationRunRequest,
        results: dict[str, RetrievalQueryResult],
    ) -> tuple[MetricResult, ...]:
        complete = len(results) == len(request.dataset.cases)
        reason = "COMPLETE_DATASET" if complete else "PARTIAL_EVALUATOR_RESULTS"
        count = len(results)
        return (
            self._metric(
                name=f"precision_at_{request.policy.retrieval_k}",
                scope="overall",
                numerator=sum(item.precision_at_k for item in results.values()),
                denominator=count,
                threshold=None,
                complete=complete,
                reason=reason,
            ),
            self._metric(
                name=f"recall_at_{request.policy.retrieval_k}",
                scope="overall",
                numerator=sum(item.recall_at_k for item in results.values()),
                denominator=count,
                threshold=request.policy.minimum_overall_recall,
                complete=complete,
                reason=reason,
            ),
            self._metric(
                name="mrr",
                scope="overall",
                numerator=sum(
                    item.reciprocal_rank for item in results.values()
                ),
                denominator=count,
                threshold=request.policy.minimum_mrr,
                complete=complete,
                reason=reason,
            ),
            self._metric(
                name=f"ndcg_at_{request.policy.ndcg_k}",
                scope="overall",
                numerator=sum(item.ndcg_at_k for item in results.values()),
                denominator=count,
                threshold=request.policy.minimum_ndcg,
                complete=complete,
                reason=reason,
            ),
        )

    def _answer_metrics(
        self,
        request: EvaluationRunRequest,
        results: dict[str, AnswerQueryResult],
    ) -> tuple[MetricResult, ...]:
        complete = len(results) == len(request.dataset.cases)
        reason = "COMPLETE_DATASET" if complete else "PARTIAL_EVALUATOR_RESULTS"
        return (
            self._metric(
                name="answer_correctness",
                scope="overall",
                numerator=sum(
                    item.correctness_numerator for item in results.values()
                ),
                denominator=sum(
                    item.correctness_denominator for item in results.values()
                ),
                threshold=None,
                complete=complete,
                reason=reason,
            ),
            self._metric(
                name="claim_faithfulness",
                scope="overall",
                numerator=sum(
                    item.faithfulness_numerator for item in results.values()
                ),
                denominator=sum(
                    item.faithfulness_denominator for item in results.values()
                ),
                threshold=None,
                complete=complete,
                reason=reason,
            ),
            self._metric(
                name="request_coverage",
                scope="overall",
                numerator=sum(
                    item.request_coverage_numerator for item in results.values()
                ),
                denominator=sum(
                    item.request_coverage_denominator for item in results.values()
                ),
                threshold=request.policy.minimum_request_coverage,
                complete=complete,
                reason=reason,
            ),
        )

    def _citation_metrics(
        self,
        request: EvaluationRunRequest,
        results: dict[str, CitationQueryResult],
    ) -> tuple[MetricResult, ...]:
        complete = len(results) == len(request.dataset.cases)
        reason = "COMPLETE_DATASET" if complete else "PARTIAL_EVALUATOR_RESULTS"
        return (
            self._metric(
                name="citation_precision",
                scope="overall",
                numerator=sum(
                    item.precision_numerator for item in results.values()
                ),
                denominator=sum(
                    item.precision_denominator for item in results.values()
                ),
                threshold=None,
                complete=complete,
                reason=reason,
            ),
            self._metric(
                name="citation_coverage",
                scope="overall",
                numerator=sum(
                    item.coverage_numerator for item in results.values()
                ),
                denominator=sum(
                    item.coverage_denominator for item in results.values()
                ),
                threshold=None,
                complete=complete,
                reason=reason,
            ),
        )

    def _slice_results(
        self,
        request: EvaluationRunRequest,
        retrieval_results: dict[str, RetrievalQueryResult],
    ) -> tuple[SliceResult, ...]:
        slices: list[SliceResult] = []
        for threshold in request.policy.slice_thresholds:
            query_ids = tuple(
                case.query.query_id
                for case in request.dataset.cases
                if threshold.slice_name in case.query.slice_names
            )
            available = tuple(
                retrieval_results[query_id]
                for query_id in query_ids
                if query_id in retrieval_results
            )
            complete = (
                len(available) == len(query_ids)
                and len(available) >= threshold.minimum_sample_size
            )
            metric = self._metric(
                name=f"recall_at_{request.policy.retrieval_k}",
                scope=f"slice:{threshold.slice_name}",
                numerator=sum(item.recall_at_k for item in available),
                denominator=len(available),
                threshold=threshold.minimum_recall,
                complete=complete,
                reason=(
                    "COMPLETE_SLICE"
                    if complete else "INCOMPLETE_OR_TOO_SMALL_SLICE"
                ),
            )
            slices.append(SliceResult(
                slice_name=threshold.slice_name,
                sample_size=len(available),
                metrics=(metric,),
            ))
        return tuple(slices)

    @staticmethod
    def _hard_gates(
        request: EvaluationRunRequest,
        answers: dict[str, AnswerQueryResult],
        citations: dict[str, CitationQueryResult],
    ) -> tuple[HardGateResult, ...]:
        expected_count = len(request.dataset.cases)
        coverages = [item.request_coverage for item in answers.values()]
        observed_coverage = min(coverages) if coverages else None
        coverage_violation = any(
            value < request.policy.minimum_request_coverage
            for value in coverages
        )
        coverage_complete = len(answers) == expected_count
        coverage_passed = (
            False
            if coverage_violation
            else (True if coverage_complete else None)
        )

        superseded_count = sum(
            item.superseded_release_count for item in citations.values()
        )
        superseded_violation = (
            superseded_count
            > request.policy.maximum_superseded_release_count
        )
        citation_complete = len(citations) == expected_count
        superseded_passed = (
            False
            if superseded_violation
            else (True if citation_complete else None)
        )

        unknown_count = sum(
            item.unknown_citation_count for item in citations.values()
        )
        unknown_passed = (
            False
            if unknown_count > 0
            else (True if citation_complete else None)
        )
        return (
            HardGateResult(
                gate_name="per_query_request_coverage",
                passed=coverage_passed,
                observed_value=observed_coverage,
                expected=(
                    f">={request.policy.minimum_request_coverage:.3f} "
                    "for every Query"
                ),
                reason=(
                    "OBSERVED_REQUEST_COVERAGE_VIOLATION"
                    if coverage_violation
                    else (
                        "COMPLETE" if coverage_complete else "EVALUATOR_INCOMPLETE"
                    )
                ),
            ),
            HardGateResult(
                gate_name="superseded_source_release_count",
                passed=superseded_passed,
                observed_value=superseded_count,
                expected=(
                    f"<={request.policy.maximum_superseded_release_count}"
                ),
                reason=(
                    "OBSERVED_SUPERSEDED_SOURCE_RELEASE"
                    if superseded_violation
                    else (
                        "COMPLETE" if citation_complete else "EVALUATOR_INCOMPLETE"
                    )
                ),
            ),
            HardGateResult(
                gate_name="unknown_citation_count",
                passed=unknown_passed,
                observed_value=unknown_count,
                expected="0",
                reason=(
                    "OBSERVED_UNKNOWN_CITATION"
                    if unknown_count > 0
                    else (
                        "COMPLETE" if citation_complete else "EVALUATOR_INCOMPLETE"
                    )
                ),
            ),
        )

    @staticmethod
    def _decision(
        *,
        metrics: tuple[MetricResult, ...],
        slices: tuple[SliceResult, ...],
        hard_gates: tuple[HardGateResult, ...],
        failures: tuple[EvaluatorFailure, ...],
    ) -> tuple[RegressionDecisionStatus, str]:
        threshold_metrics = tuple(
            item for item in metrics if item.threshold is not None
        ) + tuple(
            metric
            for slice_result in slices
            for metric in slice_result.metrics
            if metric.threshold is not None
        )
        if any(item.passed is False for item in hard_gates):
            return (
                RegressionDecisionStatus.FAIL,
                "OBSERVED_HARD_GATE_VIOLATION",
            )
        if any(item.status is MetricStatus.FAIL for item in threshold_metrics):
            return RegressionDecisionStatus.FAIL, "OBSERVED_QUALITY_THRESHOLD_FAILURE"
        if failures:
            return RegressionDecisionStatus.INCONCLUSIVE, "EVALUATOR_FAILURE"
        if (
            any(item.passed is None for item in hard_gates)
            or any(
                item.status is MetricStatus.NOT_RUN
                for item in threshold_metrics
            )
        ):
            return RegressionDecisionStatus.INCONCLUSIVE, "INSUFFICIENT_EVIDENCE"
        return RegressionDecisionStatus.PASS, "ALL_GATES_AND_THRESHOLDS_PASSED"

    def evaluate(self, request: EvaluationRunRequest) -> EvaluationReport:
        self._validator.validate_run(request)
        predictions = {
            item.query_id: item for item in request.predictions
        }
        retrieval_results: dict[str, RetrievalQueryResult] = {}
        answer_results: dict[str, AnswerQueryResult] = {}
        citation_results: dict[str, CitationQueryResult] = {}
        failures: list[EvaluatorFailure] = []

        for case in request.dataset.cases:
            query_id = case.query.query_id
            prediction = predictions[query_id]
            try:
                retrieval_results[query_id] = self._retrieval.evaluate(
                    case=case,
                    prediction=prediction,
                    retrieval_k=request.policy.retrieval_k,
                    ndcg_k=request.policy.ndcg_k,
                )
            except RetrievalEvaluatorUnavailable:
                failures.append(EvaluatorFailure(
                    query_id=query_id,
                    evaluator_name="retrieval",
                    reason=(
                        EvaluationFailureReason.RETRIEVAL_EVALUATOR_UNAVAILABLE
                    ),
                    detail="evaluator unavailable; protected payload omitted",
                ))
            try:
                answer_results[query_id] = self._answer.evaluate(
                    case=case,
                    prediction=prediction,
                )
            except AnswerEvaluatorUnavailable:
                failures.append(EvaluatorFailure(
                    query_id=query_id,
                    evaluator_name="answer",
                    reason=EvaluationFailureReason.ANSWER_EVALUATOR_UNAVAILABLE,
                    detail="evaluator unavailable; protected payload omitted",
                ))
            try:
                citation_results[query_id] = self._citation.evaluate(
                    case=case,
                    prediction=prediction,
                )
            except CitationEvaluatorUnavailable:
                failures.append(EvaluatorFailure(
                    query_id=query_id,
                    evaluator_name="citation",
                    reason=(
                        EvaluationFailureReason.CITATION_EVALUATOR_UNAVAILABLE
                    ),
                    detail="evaluator unavailable; protected payload omitted",
                ))

        metrics = (
            self._retrieval_metrics(request, retrieval_results)
            + self._answer_metrics(request, answer_results)
            + self._citation_metrics(request, citation_results)
        )
        slices = self._slice_results(request, retrieval_results)
        hard_gates = self._hard_gates(
            request, answer_results, citation_results
        )
        failure_tuple = tuple(failures)
        decision, decision_reason = self._decision(
            metrics=metrics,
            slices=slices,
            hard_gates=hard_gates,
            failures=failure_tuple,
        )
        not_run = [
            "real_retrieval_relevance",
            "real_answer_correctness",
            "real_claim_faithfulness",
            "real_citation_precision_and_coverage",
            "real_abstention_quality",
            "calibrated_llm_judge_accuracy",
            "production_latency_capacity_cost_error_rate",
        ]
        not_run.extend(
            f"{item.query_id}:{item.evaluator_name}"
            for item in failure_tuple
        )
        return EvaluationReport(
            run_identity=request.identity,
            decision=decision,
            decision_reason=decision_reason,
            metrics=metrics,
            slices=slices,
            hard_gates=hard_gates,
            failures=failure_tuple,
            evidence_level=(
                EvidenceLevel.EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE
            ),
            not_run=tuple(not_run),
            production_readiness="MORE_EVIDENCE_NEEDED",
        )

    def validate_comparable(
        self,
        baseline: EvaluationReport,
        candidate: EvaluationReport,
    ) -> None:
        self._validator.validate_comparable(baseline, candidate)

    @staticmethod
    def build_day104_handoff(
        report: EvaluationReport,
    ) -> Day104BaselineHandoff:
        identity = report.run_identity
        return Day104BaselineHandoff(
            dataset_fingerprint=identity.dataset_fingerprint,
            evaluator_fingerprint=identity.evaluator_fingerprint,
            policy_fingerprint=identity.policy_fingerprint,
            system_under_test_fingerprint=(
                identity.system_under_test_fingerprint
            ),
            evaluation_report_checksum=report.checksum,
            decision=report.decision,
            evidence_level=report.evidence_level,
            production_readiness=report.production_readiness,
        )
