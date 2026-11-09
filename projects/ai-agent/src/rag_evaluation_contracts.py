"""Application-owned Day103 RAG evaluation identities and value contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

from rag_chunking_contracts import stable_hash


class ExpectedAction(str, Enum):
    ANSWER = "ANSWER"
    ABSTAIN = "ABSTAIN"


class SupportRelation(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNAVAILABLE = "UNAVAILABLE"


class MetricStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"


class RegressionDecisionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_RUN = "NOT_RUN"


class EvidenceLevel(str, Enum):
    OFFICIAL_STATIC = "OFFICIAL_STATIC"
    CONCEPTUAL = "CONCEPTUAL"
    DETERMINISTIC_FAKE = "DETERMINISTIC_FAKE"
    SIMULATED = "SIMULATED"
    EXECUTED_LOCAL_RUNTIME = "EXECUTED_LOCAL_RUNTIME"
    EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE = (
        "EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"
    )
    INTEGRATION_RUNTIME = "INTEGRATION_RUNTIME"
    PRODUCTION = "PRODUCTION"
    NOT_RUN = "NOT_RUN"


class EvaluationFailureReason(str, Enum):
    RETRIEVAL_EVALUATOR_UNAVAILABLE = "RETRIEVAL_EVALUATOR_UNAVAILABLE"
    ANSWER_EVALUATOR_UNAVAILABLE = "ANSWER_EVALUATOR_UNAVAILABLE"
    CITATION_EVALUATOR_UNAVAILABLE = "CITATION_EVALUATOR_UNAVAILABLE"
    INVALID_DATASET = "INVALID_DATASET"
    INVALID_RUN_IDENTITY = "INVALID_RUN_IDENTITY"
    INVALID_SYSTEM_OUTPUT = "INVALID_SYSTEM_OUTPUT"
    INCOMPARABLE_RUNS = "INCOMPARABLE_RUNS"


@dataclass(frozen=True)
class EvaluationDatasetIdentity:
    dataset_version: str
    query_set_digest: str
    source_snapshot_digest: str
    authorization_policy_snapshot: str
    label_policy_revision: str
    adjudication_revision: str
    split: str
    protected_data_policy: str
    created_at: str
    expires_at: str

    def __post_init__(self) -> None:
        if not all(asdict(self).values()):
            raise ValueError("complete evaluation dataset identity is required")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class EvaluationQuery:
    query_id: str
    safe_label: str
    request_item_ids: tuple[str, ...]
    slice_names: tuple[str, ...]
    protected_query: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all((self.query_id, self.safe_label, self.protected_query.strip())):
            raise ValueError("query identity and protected text are required")
        if not self.request_item_ids or not self.slice_names:
            raise ValueError("query request items and slices are required")
        if len(set(self.request_item_ids)) != len(self.request_item_ids):
            raise ValueError("query request item IDs must be unique")
        if len(set(self.slice_names)) != len(self.slice_names):
            raise ValueError("query slice names must be unique")

    @property
    def protected_query_digest(self) -> str:
        return stable_hash(("DAY103_QUERY", self.protected_query))


@dataclass(frozen=True)
class RelevanceJudgment:
    query_id: str
    occurrence_id: str
    relevance_grade: int
    policy_eligible: bool
    reason: str

    def __post_init__(self) -> None:
        if not all((self.query_id, self.occurrence_id, self.reason)):
            raise ValueError("complete relevance judgment is required")
        if self.relevance_grade < 0:
            raise ValueError("relevance grade cannot be negative")
        if not self.policy_eligible and self.relevance_grade != 0:
            raise ValueError("ineligible sources cannot be positive qrels")


@dataclass(frozen=True)
class RequestItemLabel:
    label_id: str
    query_id: str
    request_item_id: str
    expected_action: ExpectedAction
    accepted_occurrence_ids: tuple[str, ...]
    labeling_policy_revision: str
    annotator_revision: str
    adjudication_revision: str
    protected_expected_value: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        required = (
            self.label_id,
            self.query_id,
            self.request_item_id,
            self.labeling_policy_revision,
            self.annotator_revision,
            self.adjudication_revision,
        )
        if not all(required):
            raise ValueError("complete request-item label identity is required")
        if self.expected_action is ExpectedAction.ANSWER:
            if not self.protected_expected_value or not self.accepted_occurrence_ids:
                raise ValueError("answer labels require a value and accepted sources")
        elif self.protected_expected_value is not None:
            raise ValueError("abstention labels cannot contain an answer value")
        if len(set(self.accepted_occurrence_ids)) != len(
            self.accepted_occurrence_ids
        ):
            raise ValueError("accepted occurrence IDs must be unique")

    @property
    def expected_value_digest(self) -> str | None:
        if self.protected_expected_value is None:
            return None
        return stable_hash(("DAY103_EXPECTED_VALUE", self.protected_expected_value))


def claim_value_digest(value: str) -> str:
    return stable_hash(("DAY103_CLAIM_VALUE", value.strip().casefold()))


@dataclass(frozen=True)
class CitationSupportLabel:
    query_id: str
    request_item_id: str
    claim_value_digest: str
    occurrence_id: str
    relation: SupportRelation
    source_snapshot_digest: str
    adjudication_revision: str

    def __post_init__(self) -> None:
        if not all((
            self.query_id,
            self.request_item_id,
            self.claim_value_digest,
            self.occurrence_id,
            self.source_snapshot_digest,
            self.adjudication_revision,
        )):
            raise ValueError("complete citation-support label is required")


@dataclass(frozen=True)
class EvaluationCase:
    query: EvaluationQuery
    relevance_judgments: tuple[RelevanceJudgment, ...]
    request_item_labels: tuple[RequestItemLabel, ...]
    citation_support_labels: tuple[CitationSupportLabel, ...]

    def __post_init__(self) -> None:
        if not self.relevance_judgments or not self.request_item_labels:
            raise ValueError("evaluation cases require qrels and request labels")


def evaluation_query_set_digest(cases: tuple[EvaluationCase, ...]) -> str:
    return stable_hash(tuple((
        case.query.query_id,
        case.query.protected_query_digest,
        case.query.request_item_ids,
        case.query.slice_names,
        tuple((
            item.occurrence_id,
            item.relevance_grade,
            item.policy_eligible,
            item.reason,
        ) for item in case.relevance_judgments),
        tuple((
            item.label_id,
            item.request_item_id,
            item.expected_action.value,
            item.expected_value_digest,
            item.accepted_occurrence_ids,
            item.labeling_policy_revision,
            item.annotator_revision,
            item.adjudication_revision,
        ) for item in case.request_item_labels),
        tuple((
            item.request_item_id,
            item.claim_value_digest,
            item.occurrence_id,
            item.relation.value,
            item.source_snapshot_digest,
            item.adjudication_revision,
        ) for item in case.citation_support_labels),
    ) for case in cases))


@dataclass(frozen=True)
class EvaluationDataset:
    identity: EvaluationDatasetIdentity
    cases: tuple[EvaluationCase, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if not self.cases:
            raise ValueError("evaluation dataset cases are required")
        if len({case.query.query_id for case in self.cases}) != len(self.cases):
            raise ValueError("evaluation query IDs must be unique")

    @property
    def fingerprint(self) -> str:
        return stable_hash((
            self.identity.fingerprint,
            evaluation_query_set_digest(self.cases),
        ))


@dataclass(frozen=True)
class PredictedClaim:
    claim_id: str
    request_item_id: str
    citation_occurrence_ids: tuple[str, ...]
    day102_verification_relation: str
    protected_value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all((
            self.claim_id,
            self.request_item_id,
            self.day102_verification_relation,
            self.protected_value.strip(),
        )):
            raise ValueError("complete predicted Claim identity is required")
        if len(set(self.citation_occurrence_ids)) != len(
            self.citation_occurrence_ids
        ):
            raise ValueError("predicted Claim citations must be unique")

    @property
    def value_digest(self) -> str:
        return claim_value_digest(self.protected_value)


@dataclass(frozen=True)
class SystemQueryPrediction:
    query_id: str
    ranked_occurrence_ids: tuple[str, ...]
    released_claims: tuple[PredictedClaim, ...]
    abstained_request_item_ids: tuple[str, ...]
    day101_handoff_digest: str
    day102_response_digest: str
    day102_outcome: str

    def __post_init__(self) -> None:
        if not all((
            self.query_id,
            self.day101_handoff_digest,
            self.day102_response_digest,
            self.day102_outcome,
        )):
            raise ValueError("complete system prediction identity is required")
        if len(set(self.ranked_occurrence_ids)) != len(
            self.ranked_occurrence_ids
        ):
            raise ValueError("ranked occurrence IDs must be unique")
        if len({claim.claim_id for claim in self.released_claims}) != len(
            self.released_claims
        ):
            raise ValueError("released Claim IDs must be unique")
        if len(set(self.abstained_request_item_ids)) != len(
            self.abstained_request_item_ids
        ):
            raise ValueError("abstained request item IDs must be unique")


@dataclass(frozen=True)
class SystemUnderTestIdentity:
    system_version: str
    day101_contract_fingerprint: str
    day102_contract_fingerprint: str
    retriever_revision: str
    generator_revision: str
    verifier_revision: str

    def __post_init__(self) -> None:
        if not all(asdict(self).values()):
            raise ValueError("complete system-under-test identity is required")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class EvaluatorIdentity:
    evaluator_version: str
    retrieval_metric_revision: str
    answer_policy_revision: str
    citation_policy_revision: str
    slice_policy_revision: str
    threshold_policy_revision: str

    def __post_init__(self) -> None:
        if not all(asdict(self).values()):
            raise ValueError("complete evaluator identity is required")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class SliceThreshold:
    slice_name: str
    minimum_recall: float
    minimum_sample_size: int

    def __post_init__(self) -> None:
        if (
            not self.slice_name
            or not 0 <= self.minimum_recall <= 1
            or self.minimum_sample_size <= 0
        ):
            raise ValueError("invalid slice threshold")


@dataclass(frozen=True)
class EvaluationPolicy:
    policy_version: str
    retrieval_k: int
    ndcg_k: int
    minimum_overall_recall: float
    minimum_mrr: float
    minimum_ndcg: float
    minimum_request_coverage: float
    maximum_superseded_release_count: int
    slice_thresholds: tuple[SliceThreshold, ...]

    def __post_init__(self) -> None:
        if not self.policy_version or min(self.retrieval_k, self.ndcg_k) <= 0:
            raise ValueError("evaluation policy identity and cutoffs are required")
        rates = (
            self.minimum_overall_recall,
            self.minimum_mrr,
            self.minimum_ndcg,
            self.minimum_request_coverage,
        )
        if any(not 0 <= value <= 1 for value in rates):
            raise ValueError("evaluation thresholds must be between zero and one")
        if self.maximum_superseded_release_count < 0:
            raise ValueError("superseded-release maximum cannot be negative")
        if len({item.slice_name for item in self.slice_thresholds}) != len(
            self.slice_thresholds
        ):
            raise ValueError("slice thresholds must be unique")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class EvaluationRunIdentity:
    run_id: str
    dataset_fingerprint: str
    system_under_test_fingerprint: str
    evaluator_fingerprint: str
    policy_fingerprint: str
    started_at: str

    def __post_init__(self) -> None:
        if not all(asdict(self).values()):
            raise ValueError("complete evaluation-run identity is required")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class EvaluationRunRequest:
    identity: EvaluationRunIdentity
    dataset: EvaluationDataset = field(repr=False)
    system_under_test: SystemUnderTestIdentity
    evaluator: EvaluatorIdentity
    policy: EvaluationPolicy
    predictions: tuple[SystemQueryPrediction, ...] = field(repr=False)


@dataclass(frozen=True)
class RetrievalQueryResult:
    query_id: str
    precision_at_k: float
    recall_at_k: float
    reciprocal_rank: float
    dcg_at_k: float
    ndcg_at_k: float
    relevant_retrieved_ids: tuple[str, ...]
    unexpected_retrieved_ids: tuple[str, ...]


@dataclass(frozen=True)
class AnswerQueryResult:
    query_id: str
    correctness_numerator: int
    correctness_denominator: int
    faithfulness_numerator: int
    faithfulness_denominator: int
    request_coverage_numerator: int
    request_coverage_denominator: int
    correct_abstention_count: int
    over_abstention_count: int
    missed_abstention_count: int

    @property
    def correctness(self) -> float | None:
        if self.correctness_denominator == 0:
            return None
        return self.correctness_numerator / self.correctness_denominator

    @property
    def faithfulness(self) -> float | None:
        if self.faithfulness_denominator == 0:
            return None
        return self.faithfulness_numerator / self.faithfulness_denominator

    @property
    def request_coverage(self) -> float:
        return self.request_coverage_numerator / self.request_coverage_denominator


@dataclass(frozen=True)
class CitationQueryResult:
    query_id: str
    precision_numerator: int
    precision_denominator: int
    coverage_numerator: int
    coverage_denominator: int
    superseded_release_count: int
    unknown_citation_count: int

    @property
    def precision(self) -> float | None:
        if self.precision_denominator == 0:
            return None
        return self.precision_numerator / self.precision_denominator

    @property
    def coverage(self) -> float | None:
        if self.coverage_denominator == 0:
            return None
        return self.coverage_numerator / self.coverage_denominator


@dataclass(frozen=True)
class MetricResult:
    metric_name: str
    scope: str
    numerator: float
    denominator: int
    value: float | None
    threshold: float | None
    status: MetricStatus
    reason: str


@dataclass(frozen=True)
class SliceResult:
    slice_name: str
    sample_size: int
    metrics: tuple[MetricResult, ...]


@dataclass(frozen=True)
class HardGateResult:
    gate_name: str
    passed: bool | None
    observed_value: float | int | None
    expected: str
    reason: str


@dataclass(frozen=True)
class EvaluatorFailure:
    query_id: str
    evaluator_name: str
    reason: EvaluationFailureReason
    detail: str


@dataclass(frozen=True)
class EvaluationReport:
    run_identity: EvaluationRunIdentity
    decision: RegressionDecisionStatus
    decision_reason: str
    metrics: tuple[MetricResult, ...]
    slices: tuple[SliceResult, ...]
    hard_gates: tuple[HardGateResult, ...]
    failures: tuple[EvaluatorFailure, ...]
    evidence_level: EvidenceLevel
    not_run: tuple[str, ...]
    production_readiness: str
    raw_queries_logged: bool = False
    protected_claims_logged: bool = False
    protected_evidence_logged: bool = False
    provider_payloads_logged: bool = False

    def safe_payload(self) -> dict[str, object]:
        return {
            "run_identity": asdict(self.run_identity),
            "decision": self.decision.value,
            "decision_reason": self.decision_reason,
            "metrics": [asdict(item) for item in self.metrics],
            "slices": [asdict(item) for item in self.slices],
            "hard_gates": [asdict(item) for item in self.hard_gates],
            "failures": [asdict(item) for item in self.failures],
            "evidence_level": self.evidence_level.value,
            "not_run": self.not_run,
            "production_readiness": self.production_readiness,
            "raw_queries_logged": self.raw_queries_logged,
            "protected_claims_logged": self.protected_claims_logged,
            "protected_evidence_logged": self.protected_evidence_logged,
            "provider_payloads_logged": self.provider_payloads_logged,
        }

    @property
    def checksum(self) -> str:
        return stable_hash(self.safe_payload())


@dataclass(frozen=True)
class Day104BaselineHandoff:
    dataset_fingerprint: str
    evaluator_fingerprint: str
    policy_fingerprint: str
    system_under_test_fingerprint: str
    evaluation_report_checksum: str
    decision: RegressionDecisionStatus
    evidence_level: EvidenceLevel
    production_readiness: str

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))
