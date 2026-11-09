"""Versioned Day103 refund-policy dataset and deterministic predictions."""

from __future__ import annotations

from dataclasses import replace

from rag_chunking_contracts import stable_hash
from rag_evaluation_contracts import (
    CitationSupportLabel,
    EvaluationCase,
    EvaluationDataset,
    EvaluationDatasetIdentity,
    EvaluationPolicy,
    EvaluationQuery,
    EvaluationRunIdentity,
    EvaluationRunRequest,
    EvaluatorIdentity,
    ExpectedAction,
    PredictedClaim,
    RelevanceJudgment,
    RequestItemLabel,
    SliceThreshold,
    SupportRelation,
    SystemQueryPrediction,
    SystemUnderTestIdentity,
    claim_value_digest,
    evaluation_query_set_digest,
)


OCCURRENCE_A = "occurrence:A"
OCCURRENCE_B = "occurrence:B"
OCCURRENCE_C = "occurrence:C"
REFUND_WINDOW_ITEM = "request-item:refund-window"
SUBMISSION_CHANNEL_ITEM = "request-item:submission-channel"
REFUND_14_DAYS = "14 days"
REFUND_30_DAYS = "30 days"
ONLINE_CUSTOMER_SERVICE = "online customer service"
SOURCE_SNAPSHOT_DIGEST = stable_hash((
    "DAY103_REFUND_SOURCE_SNAPSHOT_V1",
    (OCCURRENCE_A, "2026-current", REFUND_14_DAYS),
    (OCCURRENCE_B, "2024-superseded", REFUND_30_DAYS),
    (OCCURRENCE_C, "current-manual", ONLINE_CUSTOMER_SERVICE),
))


def _qrels(query_id: str, positive_ids: tuple[str, ...]) -> tuple[
    RelevanceJudgment, ...
]:
    return tuple(RelevanceJudgment(
        query_id=query_id,
        occurrence_id=occurrence_id,
        relevance_grade=1 if occurrence_id in positive_ids else 0,
        policy_eligible=occurrence_id != OCCURRENCE_B,
        reason=(
            "ADJUDICATED_CURRENT_RELEVANT"
            if occurrence_id in positive_ids
            else (
                "SUPERSEDED_SOURCE"
                if occurrence_id == OCCURRENCE_B
                else "NOT_RELEVANT_TO_QUERY"
            )
        ),
    ) for occurrence_id in (
        OCCURRENCE_A, OCCURRENCE_B, OCCURRENCE_C
    ))


def _request_label(
    *,
    query_id: str,
    request_item_id: str,
    value: str,
    accepted_occurrence_id: str,
) -> RequestItemLabel:
    return RequestItemLabel(
        label_id=f"label:{query_id}:{request_item_id}",
        query_id=query_id,
        request_item_id=request_item_id,
        expected_action=ExpectedAction.ANSWER,
        protected_expected_value=value,
        accepted_occurrence_ids=(accepted_occurrence_id,),
        labeling_policy_revision="refund-label-policy-v1",
        annotator_revision="independent-annotators-v1",
        adjudication_revision="refund-adjudication-v1",
    )


def _support_labels(
    *,
    query_id: str,
    request_item_id: str,
    values: tuple[tuple[str, tuple[SupportRelation, ...]], ...],
) -> tuple[CitationSupportLabel, ...]:
    occurrences = (OCCURRENCE_A, OCCURRENCE_B, OCCURRENCE_C)
    return tuple(CitationSupportLabel(
        query_id=query_id,
        request_item_id=request_item_id,
        claim_value_digest=claim_value_digest(value),
        occurrence_id=occurrence_id,
        relation=relation,
        source_snapshot_digest=SOURCE_SNAPSHOT_DIGEST,
        adjudication_revision="refund-adjudication-v1",
    ) for value, relations in values for occurrence_id, relation in zip(
        occurrences, relations, strict=True
    ))


def _refund_support_labels(query_id: str) -> tuple[
    CitationSupportLabel, ...
]:
    return _support_labels(
        query_id=query_id,
        request_item_id=REFUND_WINDOW_ITEM,
        values=(
            (
                REFUND_14_DAYS,
                (
                    SupportRelation.SUPPORTED,
                    SupportRelation.CONTRADICTED,
                    SupportRelation.UNSUPPORTED,
                ),
            ),
            (
                REFUND_30_DAYS,
                (
                    SupportRelation.CONTRADICTED,
                    SupportRelation.SUPPORTED,
                    SupportRelation.UNSUPPORTED,
                ),
            ),
        ),
    )


def _channel_support_labels(query_id: str) -> tuple[
    CitationSupportLabel, ...
]:
    return _support_labels(
        query_id=query_id,
        request_item_id=SUBMISSION_CHANNEL_ITEM,
        values=((
            ONLINE_CUSTOMER_SERVICE,
            (
                SupportRelation.UNSUPPORTED,
                SupportRelation.UNSUPPORTED,
                SupportRelation.SUPPORTED,
            ),
        ),),
    )


def refund_evaluation_cases() -> tuple[EvaluationCase, ...]:
    q1 = EvaluationCase(
        query=EvaluationQuery(
            query_id="Q1",
            safe_label="single-facet refund-window query",
            request_item_ids=(REFUND_WINDOW_ITEM,),
            slice_names=("single-facet", "refund-window"),
            protected_query="How long may an unopened item be refunded?",
        ),
        relevance_judgments=_qrels("Q1", (OCCURRENCE_A,)),
        request_item_labels=(_request_label(
            query_id="Q1",
            request_item_id=REFUND_WINDOW_ITEM,
            value=REFUND_14_DAYS,
            accepted_occurrence_id=OCCURRENCE_A,
        ),),
        citation_support_labels=_refund_support_labels("Q1"),
    )
    q2 = EvaluationCase(
        query=EvaluationQuery(
            query_id="Q2",
            safe_label="single-facet submission-channel query",
            request_item_ids=(SUBMISSION_CHANNEL_ITEM,),
            slice_names=("single-facet", "submission-channel"),
            protected_query="Which channel must be used for a refund request?",
        ),
        relevance_judgments=_qrels("Q2", (OCCURRENCE_C,)),
        request_item_labels=(_request_label(
            query_id="Q2",
            request_item_id=SUBMISSION_CHANNEL_ITEM,
            value=ONLINE_CUSTOMER_SERVICE,
            accepted_occurrence_id=OCCURRENCE_C,
        ),),
        citation_support_labels=_channel_support_labels("Q2"),
    )
    q3 = EvaluationCase(
        query=EvaluationQuery(
            query_id="Q3",
            safe_label="multi-facet refund-window and channel query",
            request_item_ids=(REFUND_WINDOW_ITEM, SUBMISSION_CHANNEL_ITEM),
            slice_names=("multi-facet",),
            protected_query=(
                "What are the refund window and submission channel for an "
                "unopened item?"
            ),
        ),
        relevance_judgments=_qrels(
            "Q3", (OCCURRENCE_A, OCCURRENCE_C)
        ),
        request_item_labels=(
            _request_label(
                query_id="Q3",
                request_item_id=REFUND_WINDOW_ITEM,
                value=REFUND_14_DAYS,
                accepted_occurrence_id=OCCURRENCE_A,
            ),
            _request_label(
                query_id="Q3",
                request_item_id=SUBMISSION_CHANNEL_ITEM,
                value=ONLINE_CUSTOMER_SERVICE,
                accepted_occurrence_id=OCCURRENCE_C,
            ),
        ),
        citation_support_labels=(
            _refund_support_labels("Q3")
            + _channel_support_labels("Q3")
        ),
    )
    return q1, q2, q3


def build_refund_evaluation_dataset() -> EvaluationDataset:
    cases = refund_evaluation_cases()
    return EvaluationDataset(
        identity=EvaluationDatasetIdentity(
            dataset_version="day103-refund-eval-v1",
            query_set_digest=evaluation_query_set_digest(cases),
            source_snapshot_digest=SOURCE_SNAPSHOT_DIGEST,
            authorization_policy_snapshot=stable_hash((
                "tenant-day103",
                "customer-support",
                "refund-eval-policy-v1",
            )),
            label_policy_revision="refund-label-policy-v1",
            adjudication_revision="refund-adjudication-v1",
            split="test",
            protected_data_policy="CLASSROOM_SYNTHETIC_ONLY",
            created_at="2026-11-09T00:00:00Z",
            expires_at="2027-11-09T00:00:00Z",
        ),
        cases=cases,
    )


def classroom_system_identity(
    version: str = "day103-candidate-v1",
) -> SystemUnderTestIdentity:
    return SystemUnderTestIdentity(
        system_version=version,
        day101_contract_fingerprint=stable_hash("day101-contract-v1"),
        day102_contract_fingerprint=stable_hash("day102-contract-v1"),
        retriever_revision="deterministic-retriever-v1",
        generator_revision="deterministic-generator-v1",
        verifier_revision="deterministic-verifier-v1",
    )


def classroom_evaluator_identity() -> EvaluatorIdentity:
    return EvaluatorIdentity(
        evaluator_version="day103-evaluator-v1",
        retrieval_metric_revision="binary-dcg-log2-v1",
        answer_policy_revision="exact-adjudicated-value-v1",
        citation_policy_revision="independent-support-label-v1",
        slice_policy_revision="refund-slices-v1",
        threshold_policy_revision="day103-thresholds-v1",
    )


def classroom_evaluation_policy() -> EvaluationPolicy:
    return EvaluationPolicy(
        policy_version="day103-release-policy-v1",
        retrieval_k=2,
        ndcg_k=3,
        minimum_overall_recall=0.8,
        minimum_mrr=0.8,
        minimum_ndcg=0.8,
        minimum_request_coverage=1.0,
        maximum_superseded_release_count=0,
        slice_thresholds=(
            SliceThreshold("single-facet", 0.8, 2),
            SliceThreshold("multi-facet", 0.8, 1),
        ),
    )


def _claim(
    query_id: str,
    request_item_id: str,
    value: str,
    citations: tuple[str, ...],
    verification_relation: str = "SUPPORTED",
) -> PredictedClaim:
    suffix = request_item_id.rsplit(":", maxsplit=1)[-1]
    return PredictedClaim(
        claim_id=f"claim:{query_id}:{suffix}",
        request_item_id=request_item_id,
        citation_occurrence_ids=citations,
        day102_verification_relation=verification_relation,
        protected_value=value,
    )


def _prediction(
    query_id: str,
    ranked: tuple[str, ...],
    claims: tuple[PredictedClaim, ...],
    abstained: tuple[str, ...] = (),
) -> SystemQueryPrediction:
    return SystemQueryPrediction(
        query_id=query_id,
        ranked_occurrence_ids=ranked,
        released_claims=claims,
        abstained_request_item_ids=abstained,
        day101_handoff_digest=stable_hash((query_id, "day101-handoff")),
        day102_response_digest=stable_hash((
            query_id,
            ranked,
            tuple((claim.claim_id, claim.value_digest) for claim in claims),
            abstained,
        )),
        day102_outcome="FULL" if not abstained else "PARTIAL",
    )


def build_passing_predictions() -> tuple[SystemQueryPrediction, ...]:
    return (
        _prediction(
            "Q1",
            (OCCURRENCE_A, OCCURRENCE_B, OCCURRENCE_C),
            (_claim(
                "Q1", REFUND_WINDOW_ITEM, REFUND_14_DAYS, (OCCURRENCE_A,)
            ),),
        ),
        _prediction(
            "Q2",
            (OCCURRENCE_C, OCCURRENCE_A, OCCURRENCE_B),
            (_claim(
                "Q2",
                SUBMISSION_CHANNEL_ITEM,
                ONLINE_CUSTOMER_SERVICE,
                (OCCURRENCE_C,),
            ),),
        ),
        _prediction(
            "Q3",
            (OCCURRENCE_A, OCCURRENCE_C, OCCURRENCE_B),
            (
                _claim(
                    "Q3",
                    REFUND_WINDOW_ITEM,
                    REFUND_14_DAYS,
                    (OCCURRENCE_A,),
                ),
                _claim(
                    "Q3",
                    SUBMISSION_CHANNEL_ITEM,
                    ONLINE_CUSTOMER_SERVICE,
                    (OCCURRENCE_C,),
                ),
            ),
        ),
    )


def build_slice_regression_predictions() -> tuple[
    SystemQueryPrediction, ...
]:
    passing = build_passing_predictions()
    return (
        replace(
            passing[0],
            ranked_occurrence_ids=(
                OCCURRENCE_B, OCCURRENCE_A, OCCURRENCE_C
            ),
        ),
        passing[1],
        _prediction(
            "Q3",
            (OCCURRENCE_A, OCCURRENCE_B, OCCURRENCE_C),
            (_claim(
                "Q3", REFUND_WINDOW_ITEM, REFUND_14_DAYS, (OCCURRENCE_A,)
            ),),
        ),
    )


def build_superseded_release_predictions() -> tuple[
    SystemQueryPrediction, ...
]:
    predictions = list(build_passing_predictions())
    predictions[0] = _prediction(
        "Q1",
        (OCCURRENCE_B, OCCURRENCE_A, OCCURRENCE_C),
        (_claim(
            "Q1",
            REFUND_WINDOW_ITEM,
            REFUND_30_DAYS,
            (OCCURRENCE_B,),
            verification_relation="SUPPORTED",
        ),),
    )
    return tuple(predictions)


def build_correct_unfaithful_predictions() -> tuple[
    SystemQueryPrediction, ...
]:
    predictions = list(build_passing_predictions())
    predictions[0] = _prediction(
        "Q1",
        (OCCURRENCE_A, OCCURRENCE_C, OCCURRENCE_B),
        (_claim(
            "Q1", REFUND_WINDOW_ITEM, REFUND_14_DAYS, (OCCURRENCE_C,)
        ),),
    )
    return tuple(predictions)


def build_over_abstention_predictions() -> tuple[
    SystemQueryPrediction, ...
]:
    predictions = list(build_passing_predictions())
    predictions[0] = _prediction(
        "Q1",
        (OCCURRENCE_A, OCCURRENCE_B, OCCURRENCE_C),
        (),
        abstained=(REFUND_WINDOW_ITEM,),
    )
    return tuple(predictions)


def build_evaluation_run_request(
    *,
    predictions: tuple[SystemQueryPrediction, ...] | None = None,
    system_version: str = "day103-candidate-v1",
    run_id: str = "evaluation-run-day103-v1",
) -> EvaluationRunRequest:
    dataset = build_refund_evaluation_dataset()
    system = classroom_system_identity(system_version)
    evaluator = classroom_evaluator_identity()
    policy = classroom_evaluation_policy()
    return EvaluationRunRequest(
        identity=EvaluationRunIdentity(
            run_id=run_id,
            dataset_fingerprint=dataset.fingerprint,
            system_under_test_fingerprint=system.fingerprint,
            evaluator_fingerprint=evaluator.fingerprint,
            policy_fingerprint=policy.fingerprint,
            started_at="2026-11-09T01:00:00Z",
        ),
        dataset=dataset,
        system_under_test=system,
        evaluator=evaluator,
        policy=policy,
        predictions=(
            predictions if predictions is not None else build_passing_predictions()
        ),
    )
