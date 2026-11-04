"""Application-owned Day101 reranking contracts and safe result types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math

from rag_chunking_contracts import stable_hash
from rag_retrieval_contracts import CandidateIdentity


class RerankerScoreDirection(str, Enum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


class RerankerOutputMode(str, Enum):
    FULL_PERMUTATION = "FULL_PERMUTATION"
    TOP_N = "TOP_N"
    ARBITRARY_SUBSET = "ARBITRARY_SUBSET"


class RerankingMode(str, Enum):
    RERANKED_SUCCESS = "RERANKED_SUCCESS"
    UNRERANKED_FALLBACK = "UNRERANKED_FALLBACK"


class Day101Outcome(str, Enum):
    FULL = "FULL"
    DEGRADED = "DEGRADED"
    EMPTY = "EMPTY"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"


class RerankingFailureReason(str, Enum):
    NONE = "NONE"
    NO_CURRENT_DAY100_BUNDLE = "NO_CURRENT_DAY100_BUNDLE"
    DAY100_HANDOFF_REJECTED = "DAY100_HANDOFF_REJECTED"
    MULTI_QUERY_POOL_INVALID = "MULTI_QUERY_POOL_INVALID"
    RERANK_EGRESS_DENIED = "RERANK_EGRESS_DENIED"
    RERANKER_FAILED = "RERANKER_FAILED"
    RERANKER_TIMEOUT = "RERANKER_TIMEOUT"
    RERANKER_OUTPUT_INVALID = "RERANKER_OUTPUT_INVALID"
    STALE_AUTHORIZATION = "STALE_AUTHORIZATION"
    STALE_PROVENANCE = "STALE_PROVENANCE"
    EMPTY_AUTHORIZED_RESULT = "EMPTY_AUTHORIZED_RESULT"


@dataclass(frozen=True)
class RerankerContract:
    contract_version: str
    provider: str
    immutable_model_revision: str
    tokenizer_revision: str
    score_direction: RerankerScoreDirection
    score_activation: str
    score_calibration: str
    output_mode: RerankerOutputMode
    top_n: int
    max_candidates: int
    max_input_chars: int
    input_window_strategy: str
    input_window_policy_version: str
    protected_data_policy: str
    egress_policy_version: str
    correlation_mode: str = "EXPLICIT_INPUT_INDEX_TO_CANDIDATE_ID"

    def __post_init__(self) -> None:
        required = (
            self.contract_version,
            self.provider,
            self.immutable_model_revision,
            self.tokenizer_revision,
            self.score_activation,
            self.score_calibration,
            self.input_window_strategy,
            self.input_window_policy_version,
            self.protected_data_policy,
            self.egress_policy_version,
            self.correlation_mode,
        )
        if not all(required) or min(
            self.top_n, self.max_candidates, self.max_input_chars
        ) <= 0:
            raise ValueError("reranker contract bindings and budgets are required")
        if self.immutable_model_revision.lower() in {"latest", "main", "unknown"}:
            raise ValueError("reranker model revision must be immutable")
        if self.top_n > self.max_candidates:
            raise ValueError("reranker top_n cannot exceed candidate budget")
        if self.input_window_strategy not in {"HEAD", "HEAD_TAIL"}:
            raise ValueError("unsupported reranker input-window strategy")
        if self.correlation_mode != "EXPLICIT_INPUT_INDEX_TO_CANDIDATE_ID":
            raise ValueError("Day101 requires explicit candidate correlation")

    @property
    def fingerprint(self) -> str:
        values = asdict(self)
        values["score_direction"] = self.score_direction.value
        values["output_mode"] = self.output_mode.value
        return stable_hash(values)


@dataclass(frozen=True)
class RerankingDegradationPolicy:
    policy_version: str
    allow_unreranked_on_egress_denied: bool
    allow_unreranked_on_provider_failure: bool
    allow_unreranked_on_timeout: bool
    allow_unreranked_on_invalid_output: bool

    def __post_init__(self) -> None:
        if not self.policy_version:
            raise ValueError("reranking degradation policy version is required")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class RerankerEgressPolicy:
    policy_version: str
    allowed_providers: frozenset[str]
    allow_protected_query_egress: bool
    allow_protected_candidate_egress: bool

    def __post_init__(self) -> None:
        if not self.policy_version:
            raise ValueError("reranker egress policy version is required")


@dataclass(frozen=True)
class RerankerInputItem:
    input_index: int
    candidate_id: str
    identity: CandidateIdentity
    prior_fusion_rank: int
    input_window_digest: str
    input_window_policy_version: str
    protected_input_window: str = field(repr=False)

    def __post_init__(self) -> None:
        if (
            self.input_index < 0
            or not all((
                self.candidate_id,
                self.input_window_digest,
                self.input_window_policy_version,
                self.protected_input_window,
            ))
            or self.prior_fusion_rank <= 0
            or self.candidate_id != self.identity.occurrence_id
        ):
            raise ValueError("complete reranker input-item identity is required")


@dataclass(frozen=True)
class RerankerRequest:
    attempt_id: str
    original_query_digest: str
    candidate_pool_digest: str
    reranker_contract_fingerprint: str
    input_windows_digest: str
    items: tuple[RerankerInputItem, ...]
    protected_query: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all((
            self.attempt_id,
            self.original_query_digest,
            self.candidate_pool_digest,
            self.reranker_contract_fingerprint,
            self.input_windows_digest,
            self.protected_query,
        )) or not self.items:
            raise ValueError("reranker request requires frozen identities and inputs")
        if tuple(item.input_index for item in self.items) != tuple(range(len(self.items))):
            raise ValueError("reranker input indexes must be contiguous")
        if len({item.candidate_id for item in self.items}) != len(self.items):
            raise ValueError("reranker input candidate IDs must be unique")


@dataclass(frozen=True)
class RawRerankerItem:
    input_index: int
    score: float

    def __post_init__(self) -> None:
        if self.input_index < 0 or not math.isfinite(self.score):
            raise ValueError("raw reranker item requires a valid index and finite score")


@dataclass(frozen=True)
class RawRerankerResponse:
    attempt_id: str
    candidate_pool_digest: str
    reranker_contract_fingerprint: str
    results: tuple[RawRerankerItem, ...]


@dataclass(frozen=True)
class ValidatedRerankItem:
    rank: int
    candidate_id: str
    identity: CandidateIdentity
    score: float
    input_window_digest: str
    prior_fusion_rank: int


@dataclass(frozen=True)
class ValidatedRerankResult:
    attempt_id: str
    candidate_pool_digest: str
    reranker_contract_fingerprint: str
    input_windows_digest: str
    items: tuple[ValidatedRerankItem, ...]

    @property
    def digest(self) -> str:
        return stable_hash((
            self.attempt_id,
            self.candidate_pool_digest,
            self.reranker_contract_fingerprint,
            self.input_windows_digest,
            tuple(asdict(item) for item in self.items),
        ))


@dataclass(frozen=True)
class FinalRerankedHit:
    rank: int
    identity: CandidateIdentity
    source_reference: str
    reranker_score: float | None
    prior_fusion_rank: int
    text: str = field(repr=False)


@dataclass(frozen=True)
class Day101Response:
    outcome: Day101Outcome
    safe_reason: str
    rewrite_mode: str | None
    reranking_mode: RerankingMode | None
    hits: tuple[FinalRerankedHit, ...] = field(default=(), repr=False)
    rewrite_set_fingerprint: str | None = None
    candidate_pool_digest: str | None = None
    validated_rerank_digest: str | None = None
    release_rejections: tuple[tuple[str, str], ...] = ()
    rewrite_provider_calls: int = 0
    reranker_provider_calls: int = 0


@dataclass(frozen=True)
class ContentSafeRerankingAudit:
    operation_id: str
    original_query_digest: str
    rewrite_mode: str
    candidate_pool_digest: str
    reranking_mode: str
    outcome: str
    returned_count: int
    release_rejection_count: int
    rewrite_provider_calls: int
    reranker_provider_calls: int
    raw_query_logged: bool = False
    protected_candidate_text_logged: bool = False
    vector_logged: bool = False
