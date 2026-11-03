"""Application-owned Day100 authorized hybrid-retrieval contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math

from rag_acl_contracts import AuthorizationRevisionVector
from rag_chunking_contracts import stable_hash
from rag_vector_contracts import GenerationState, ProductionReadiness


RETRIEVAL_ACTION = "chunk:retrieve"
RETRIEVAL_PURPOSE = "day100-authorized-hybrid-retrieval"


class RetrievalBranch(str, Enum):
    LEXICAL = "LEXICAL"
    DENSE = "DENSE"


class RetrievalOutcome(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"
    REJECTED = "REJECTED"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    UNAVAILABLE = "UNAVAILABLE"


class DegradationReason(str, Enum):
    NONE = "NONE"
    LEXICAL_BRANCH_FAILED = "LEXICAL_BRANCH_FAILED"
    DENSE_BRANCH_FAILED = "DENSE_BRANCH_FAILED"
    DENSE_EGRESS_DENIED = "DENSE_EGRESS_DENIED"
    REFILL_BUDGET_EXHAUSTED = "REFILL_BUDGET_EXHAUSTED"
    DEADLINE_EXHAUSTED = "DEADLINE_EXHAUSTED"


class ScoreDirection(str, Enum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


@dataclass(frozen=True)
class QueryEncoderContract:
    contract_version: str
    provider: str
    immutable_model_revision: str
    document_contract_fingerprint: str
    dimensions: int
    query_input_role: str
    query_prefix: str
    document_input_role: str
    document_prefix: str
    tokenizer_revision: str
    normalization: str
    protected_data_policy: str
    egress_policy_version: str

    def __post_init__(self) -> None:
        required = (
            self.contract_version,
            self.provider,
            self.immutable_model_revision,
            self.document_contract_fingerprint,
            self.query_input_role,
            self.document_input_role,
            self.tokenizer_revision,
            self.normalization,
            self.protected_data_policy,
            self.egress_policy_version,
        )
        if not all(required) or self.dimensions <= 0:
            raise ValueError("query encoder contract bindings are required")
        if self.immutable_model_revision.lower() in {
            "latest", "main", "unknown"
        }:
            raise ValueError("query encoder requires an immutable model revision")
        if self.query_input_role == self.document_input_role:
            raise ValueError("query and document input roles must be explicit")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class LexicalRetrievalContract:
    contract_version: str
    corpus_generation_id: str
    chunk_set_id: str
    analyzer_version: str
    tokenizer_version: str
    language: str
    k1: float
    b: float
    stop_words: tuple[str, ...] = ()
    stemming_policy: str = "NONE"
    field_weights: tuple[tuple[str, float], ...] = (("text", 1.0),)

    def __post_init__(self) -> None:
        if not all((
            self.contract_version,
            self.corpus_generation_id,
            self.chunk_set_id,
            self.analyzer_version,
            self.tokenizer_version,
            self.language,
            self.stemming_policy,
        )):
            raise ValueError("lexical retrieval contract bindings are required")
        if self.k1 <= 0 or not 0 <= self.b <= 1:
            raise ValueError("BM25 requires k1 > 0 and 0 <= b <= 1")
        if not self.field_weights or any(weight <= 0 for _, weight in self.field_weights):
            raise ValueError("positive lexical field weights are required")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class FusionPolicy:
    policy_version: str
    rrf_k: int
    candidate_depth: int
    lexical_weight: float = 1.0
    dense_weight: float = 1.0
    tie_break: tuple[str, ...] = (
        "RRF_SCORE_DESC",
        "BEST_BRANCH_RANK_ASC",
        "OCCURRENCE_ID_ASC",
    )

    def __post_init__(self) -> None:
        if not self.policy_version or self.rrf_k <= 0 or self.candidate_depth <= 0:
            raise ValueError("valid fusion policy bindings are required")
        if self.lexical_weight <= 0 or self.dense_weight <= 0:
            raise ValueError("branch weights must be positive")
        if not self.tie_break:
            raise ValueError("deterministic tie-break policy is required")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class HybridRetrievalPolicy:
    policy_version: str
    max_top_k: int
    max_candidate_depth: int
    max_refill_rounds: int
    max_candidate_budget: int
    deadline_ms: int
    allow_lexical_only: bool
    allow_dense_only: bool
    allow_split_or: bool
    allow_business_post_filter: bool

    def __post_init__(self) -> None:
        numeric = (
            self.max_top_k,
            self.max_candidate_depth,
            self.max_refill_rounds,
            self.max_candidate_budget,
            self.deadline_ms,
        )
        if not self.policy_version or min(numeric) <= 0:
            raise ValueError("positive bounded retrieval policy values are required")
        if self.max_candidate_depth > self.max_candidate_budget:
            raise ValueError("candidate depth cannot exceed the total budget")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class SelectedRetrievalBundle:
    bundle_id: str
    revision: int
    tenant_id: str
    generation_id: str
    generation_state: GenerationState
    generation_contract_fingerprint: str
    embedding_set_id: str
    embedding_contract_fingerprint: str
    chunk_set_id: str
    lexical_corpus_generation_id: str
    query_encoder: QueryEncoderContract
    lexical: LexicalRetrievalContract
    filter_schema_fingerprint: str
    retrieval_policy: HybridRetrievalPolicy
    fusion_policy: FusionPolicy
    selected: bool
    evidence_level: str
    fixture_scope: str
    production_eligible: bool
    production_readiness: ProductionReadiness

    def __post_init__(self) -> None:
        if not all((
            self.bundle_id,
            self.tenant_id,
            self.generation_id,
            self.generation_contract_fingerprint,
            self.embedding_set_id,
            self.embedding_contract_fingerprint,
            self.chunk_set_id,
            self.lexical_corpus_generation_id,
            self.filter_schema_fingerprint,
            self.evidence_level,
            self.fixture_scope,
        )) or self.revision <= 0:
            raise ValueError("selected retrieval bundle bindings are required")
        if not self.selected:
            raise ValueError("a selected retrieval bundle must be application-selected")
        if self.lexical.chunk_set_id != self.chunk_set_id:
            raise ValueError("lexical corpus and selected ChunkSet must align")
        if self.lexical.corpus_generation_id != self.lexical_corpus_generation_id:
            raise ValueError("lexical generation binding is inconsistent")
        if (
            self.query_encoder.document_contract_fingerprint
            != self.embedding_contract_fingerprint
        ):
            raise ValueError("query encoder and document embeddings are incompatible")
        if self.fixture_scope == "DAY100_CLASSROOM_ONLY" and self.production_eligible:
            raise ValueError("synthetic classroom bundles cannot be production eligible")
        if self.production_eligible and (
            self.generation_state is not GenerationState.ACTIVATED
            or self.production_readiness is not ProductionReadiness.PRODUCTION_READY
        ):
            raise ValueError("production eligibility requires activated ready generation")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class RetrievalRequest:
    operation_id: str
    request_id: str
    tenant_id: str
    principal_subject: str = field(repr=False)
    action: str
    purpose: str
    query_text: str = field(repr=False)
    top_k: int
    client_filter: object | None = field(default=None, repr=False)
    client_generation_id: str | None = None
    query_encoder_contract_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not all((
            self.operation_id,
            self.request_id,
            self.tenant_id,
            self.principal_subject,
            self.action,
            self.purpose,
        )):
            raise ValueError("retrieval request identity is required")
        if not self.query_text.strip() or self.top_k <= 0:
            raise ValueError("non-empty query and positive top_k are required")

    @property
    def query_hash(self) -> str:
        return stable_hash(("PROTECTED_QUERY", self.query_text))


@dataclass(frozen=True)
class RetrievalAuthorizationScope:
    tenant_id: str
    principal_subject: str = field(repr=False)
    action: str
    purpose: str
    revisions: AuthorizationRevisionVector
    allowed_occurrence_ids: tuple[str, ...]
    decision_id: str

    def __post_init__(self) -> None:
        if not all((
            self.tenant_id,
            self.principal_subject,
            self.action,
            self.purpose,
            self.decision_id,
        )):
            raise ValueError("authorization scope identity is required")
        if len(set(self.allowed_occurrence_ids)) != len(self.allowed_occurrence_ids):
            raise ValueError("authorization scope occurrences must be unique")

    @property
    def fingerprint(self) -> str:
        return stable_hash((
            self.tenant_id,
            self.principal_subject,
            self.action,
            self.purpose,
            asdict(self.revisions),
            self.allowed_occurrence_ids,
        ))


@dataclass(frozen=True)
class CandidateIdentity:
    tenant_id: str
    document_id: str
    document_version_id: str
    chunk_set_id: str
    chunk_id: str
    occurrence_id: str
    provenance_fingerprint: str
    content_hash: str

    def __post_init__(self) -> None:
        if not all(asdict(self).values()):
            raise ValueError("complete candidate occurrence identity is required")

    @property
    def key(self) -> str:
        return self.occurrence_id


@dataclass(frozen=True)
class RetrievalRecord:
    identity: CandidateIdentity
    text: str = field(repr=False)
    metadata: tuple[tuple[str, object], ...]
    embedding: tuple[float, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if not self.text or not self.embedding:
            raise ValueError("retrieval records require text and embedding")
        values = dict(self.metadata)
        if values.get("tenant_id") != self.identity.tenant_id:
            raise ValueError("record metadata tenant must match occurrence identity")
        if len({key for key, _ in self.metadata}) != len(self.metadata):
            raise ValueError("record metadata keys must be unique")

    @property
    def metadata_dict(self) -> dict[str, object]:
        return dict(self.metadata)


@dataclass(frozen=True)
class BranchCandidate:
    identity: CandidateIdentity
    branch: RetrievalBranch
    branch_rank: int
    raw_score: float
    score_direction: ScoreDirection
    generation_id: str
    corpus_generation_id: str
    bundle_fingerprint: str
    metadata: tuple[tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        if self.branch_rank <= 0 or not math.isfinite(self.raw_score):
            raise ValueError("candidate rank and finite score are required")
        if not all((
            self.generation_id,
            self.corpus_generation_id,
            self.bundle_fingerprint,
        )):
            raise ValueError("candidate source bindings are required")

    @property
    def metadata_dict(self) -> dict[str, object]:
        return dict(self.metadata)


@dataclass(frozen=True)
class FusedCandidate:
    identity: CandidateIdentity
    rrf_score: float
    best_branch_rank: int
    branch_candidates: tuple[BranchCandidate, ...]

    def __post_init__(self) -> None:
        if not self.branch_candidates or self.rrf_score <= 0:
            raise ValueError("fused candidate requires ranked branch evidence")
        if any(item.identity.key != self.identity.key for item in self.branch_candidates):
            raise ValueError("fusion cannot mix different occurrence identities")


@dataclass(frozen=True)
class AuthorizedRetrievalHit:
    identity: CandidateIdentity
    rank: int
    rrf_score: float
    text: str = field(repr=False)
    source_reference: str


@dataclass(frozen=True)
class RetrievalResponse:
    outcome: RetrievalOutcome
    safe_reason: str
    operation_id: str
    bundle_id: str | None
    authorization_decision_id: str | None
    hits: tuple[AuthorizedRetrievalHit, ...] = field(default=(), repr=False)
    completed_branches: tuple[RetrievalBranch, ...] = ()
    missing_branches: tuple[RetrievalBranch, ...] = ()
    degradation_reason: DegradationReason = DegradationReason.NONE
    requested_top_k: int = 0
    candidates_examined: int = 0
    refill_rounds: int = 0
    provider_calls: int = 0
    database_calls: int = 0
    cursor: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.requested_top_k < 0 or self.candidates_examined < 0:
            raise ValueError("retrieval counts cannot be negative")
        if self.outcome is RetrievalOutcome.FULL and self.missing_branches:
            raise ValueError("full results cannot omit a required branch")
        if self.outcome is RetrievalOutcome.PARTIAL and (
            self.degradation_reason is DegradationReason.NONE
        ):
            raise ValueError("partial results require an explicit reason")
        if self.outcome in {
            RetrievalOutcome.REJECTED,
            RetrievalOutcome.AUTHORIZATION_DENIED,
            RetrievalOutcome.UNAVAILABLE,
        } and self.hits:
            raise ValueError("failed retrieval cannot carry protected hits")


@dataclass(frozen=True)
class ContentSafeRetrievalAudit:
    operation_id: str
    request_id: str
    tenant_id: str
    principal_hash: str
    query_hash: str
    selected_bundle_id: str | None
    selected_generation_id: str | None
    client_generation_hint: str | None
    client_generation_authoritative: bool
    authorization_scope_fingerprint: str | None
    filter_plan_fingerprint: str | None
    outcome: str
    reason: str
    completed_branches: tuple[str, ...]
    missing_branches: tuple[str, ...]
    candidates_examined: int
    returned_count: int
    provider_calls: int
    database_calls: int
    raw_query_logged: bool = False
    protected_text_logged: bool = False
