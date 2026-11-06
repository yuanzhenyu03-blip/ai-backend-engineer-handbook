"""Application-owned Day102 grounding, citation and release contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

from rag_chunking_contracts import stable_hash
from rag_reranker_contracts import Day101Response
from rag_retrieval_contracts import CandidateIdentity


class Day102Outcome(str, Enum):
    FULL = "FULL"
    DEGRADED = "DEGRADED"
    PARTIAL = "PARTIAL"
    ABSTAINED = "ABSTAINED"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"


class Day102FailureReason(str, Enum):
    NONE = "NONE"
    INVALID_DAY101_HANDOFF = "INVALID_DAY101_HANDOFF"
    UPSTREAM_OUTCOME_NOT_ALLOWED = "UPSTREAM_OUTCOME_NOT_ALLOWED"
    NO_CURRENT_GROUNDING_SOURCES = "NO_CURRENT_GROUNDING_SOURCES"
    GROUNDING_PLAN_INVALID = "GROUNDING_PLAN_INVALID"
    GENERATOR_EGRESS_DENIED = "GENERATOR_EGRESS_DENIED"
    GENERATOR_FAILED = "GENERATOR_FAILED"
    GENERATOR_TIMEOUT = "GENERATOR_TIMEOUT"
    GENERATOR_OUTPUT_INVALID = "GENERATOR_OUTPUT_INVALID"
    CLAIM_EXTRACTION_INVALID = "CLAIM_EXTRACTION_INVALID"
    CITATION_OUT_OF_BUNDLE = "CITATION_OUT_OF_BUNDLE"
    CITATION_REQUIRED = "CITATION_REQUIRED"
    VERIFIER_EGRESS_DENIED = "VERIFIER_EGRESS_DENIED"
    VERIFIER_FAILED = "VERIFIER_FAILED"
    VERIFIER_TIMEOUT = "VERIFIER_TIMEOUT"
    VERIFIER_OUTPUT_INVALID = "VERIFIER_OUTPUT_INVALID"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    CONTRADICTED_CLAIM = "CONTRADICTED_CLAIM"
    STALE_AUTHORIZATION = "STALE_AUTHORIZATION"
    STALE_PROVENANCE = "STALE_PROVENANCE"
    SUPERSEDED_SOURCE = "SUPERSEDED_SOURCE"
    REQUEST_ITEM_UNANSWERED = "REQUEST_ITEM_UNANSWERED"


class GeneratorMode(str, Enum):
    PRIMARY = "PRIMARY"
    FALLBACK = "FALLBACK"
    NOT_RUN = "NOT_RUN"


class VerificationMode(str, Enum):
    PRIMARY = "PRIMARY"
    FALLBACK = "FALLBACK"
    NOT_RUN = "NOT_RUN"


class SemanticRelation(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTION = "CONTRADICTION"


class ClaimDisposition(str, Enum):
    RELEASED = "RELEASED"
    REJECTED = "REJECTED"


class RequestItemStatus(str, Enum):
    ANSWERED = "ANSWERED"
    ABSTAINED = "ABSTAINED"


@dataclass(frozen=True)
class RequestItem:
    item_id: str
    safe_label: str
    protected_text: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all((self.item_id, self.safe_label, self.protected_text.strip())):
            raise ValueError("request item identity and text are required")


@dataclass(frozen=True)
class GroundingContract:
    contract_version: str
    generator_provider: str
    immutable_generator_revision: str
    generator_prompt_revision: str
    claim_extractor_revision: str
    verifier_provider: str
    verifier_revision: str
    verification_policy_version: str
    source_window_policy_version: str
    max_source_windows: int
    max_chars_per_window: int
    max_total_source_chars: int
    max_claims: int
    protected_data_policy: str
    egress_policy_version: str

    def __post_init__(self) -> None:
        required = (
            self.contract_version,
            self.generator_provider,
            self.immutable_generator_revision,
            self.generator_prompt_revision,
            self.claim_extractor_revision,
            self.verifier_provider,
            self.verifier_revision,
            self.verification_policy_version,
            self.source_window_policy_version,
            self.protected_data_policy,
            self.egress_policy_version,
        )
        if not all(required):
            raise ValueError("grounding contract identities are required")
        if min(
            self.max_source_windows,
            self.max_chars_per_window,
            self.max_total_source_chars,
            self.max_claims,
        ) <= 0:
            raise ValueError("grounding budgets must be positive")
        if self.max_total_source_chars < self.max_chars_per_window:
            raise ValueError("total source budget cannot be smaller than one window")
        if self.immutable_generator_revision.lower() in {
            "latest", "main", "unknown"
        }:
            raise ValueError("generator revision must be immutable")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class GeneratorEgressPolicy:
    policy_version: str
    allowed_providers: frozenset[str]
    allow_protected_query_egress: bool
    allow_protected_source_egress: bool

    def __post_init__(self) -> None:
        if not self.policy_version:
            raise ValueError("generator egress policy version is required")


@dataclass(frozen=True)
class VerifierEgressPolicy:
    policy_version: str
    allowed_providers: frozenset[str]
    allow_protected_claim_egress: bool
    allow_protected_source_egress: bool

    def __post_init__(self) -> None:
        if not self.policy_version:
            raise ValueError("verifier egress policy version is required")


@dataclass(frozen=True)
class GroundingDegradationPolicy:
    policy_version: str
    allow_degraded_day101_handoff: bool
    allow_generator_fallback_on_failure: bool
    allow_generator_fallback_on_timeout: bool
    allow_verifier_fallback_on_failure: bool
    allow_verifier_fallback_on_timeout: bool

    def __post_init__(self) -> None:
        if not self.policy_version:
            raise ValueError("grounding degradation policy version is required")


@dataclass(frozen=True)
class GroundingRequest:
    operation_id: str
    request_id: str
    tenant_id: str
    principal_subject: str = field(repr=False)
    action: str
    purpose: str
    original_query: str = field(repr=False)
    request_items: tuple[RequestItem, ...]
    day101_response: Day101Response = field(repr=False)
    day101_handoff_digest: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all((
            self.operation_id,
            self.request_id,
            self.tenant_id,
            self.principal_subject,
            self.action,
            self.purpose,
            self.original_query.strip(),
            self.day101_handoff_digest,
        )):
            raise ValueError("complete Day102 request identity is required")
        if not self.request_items:
            raise ValueError("Day102 request items are required for coverage")
        if len({item.item_id for item in self.request_items}) != len(
            self.request_items
        ):
            raise ValueError("request item IDs must be unique")


@dataclass(frozen=True)
class SourceWindow:
    window_id: str
    identity: CandidateIdentity
    source_reference: str
    exact_span: str
    day101_rank: int
    window_policy_version: str
    text_digest: str
    protected_text: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all((
            self.window_id,
            self.source_reference,
            self.exact_span,
            self.window_policy_version,
            self.text_digest,
            self.protected_text,
        )) or self.day101_rank <= 0:
            raise ValueError("complete source-window identity is required")
        if stable_hash(self.protected_text) != self.text_digest:
            raise ValueError("source-window text digest mismatch")


@dataclass(frozen=True)
class GroundingBundle:
    operation_id: str
    original_query_digest: str
    request_items_digest: str
    day101_handoff_digest: str
    authorization_scope_fingerprint: str
    contract_fingerprint: str
    upstream_outcome: str
    upstream_reranking_mode: str
    upstream_safe_reason: str
    windows: tuple[SourceWindow, ...] = field(repr=False)

    def __post_init__(self) -> None:
        required = (
            self.operation_id,
            self.original_query_digest,
            self.request_items_digest,
            self.day101_handoff_digest,
            self.authorization_scope_fingerprint,
            self.contract_fingerprint,
            self.upstream_outcome,
            self.upstream_reranking_mode,
            self.upstream_safe_reason,
        )
        if not all(required) or not self.windows:
            raise ValueError("grounding bundle requires frozen identities and windows")
        if len({window.window_id for window in self.windows}) != len(self.windows):
            raise ValueError("grounding source-window IDs must be unique")
        if len({window.identity.occurrence_id for window in self.windows}) != len(
            self.windows
        ):
            raise ValueError("one grounding window per occurrence is required")

    @property
    def digest(self) -> str:
        return stable_hash((
            "DAY102_GROUNDING_BUNDLE_V1",
            self.operation_id,
            self.original_query_digest,
            self.request_items_digest,
            self.day101_handoff_digest,
            self.authorization_scope_fingerprint,
            self.contract_fingerprint,
            self.upstream_outcome,
            self.upstream_reranking_mode,
            self.upstream_safe_reason,
            tuple((
                window.window_id,
                asdict(window.identity),
                window.source_reference,
                window.exact_span,
                window.day101_rank,
                window.window_policy_version,
                window.text_digest,
            ) for window in self.windows),
        ))


@dataclass(frozen=True)
class GeneratedAnswer:
    attempt_id: str
    bundle_digest: str
    generator_contract_fingerprint: str
    answer_text: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all((
            self.attempt_id,
            self.bundle_digest,
            self.generator_contract_fingerprint,
            self.answer_text.strip(),
        )):
            raise ValueError("generated answer identity and text are required")

    @property
    def answer_digest(self) -> str:
        return stable_hash(self.answer_text)


@dataclass(frozen=True)
class ExtractedClaim:
    claim_id: str
    request_item_id: str
    answer_start: int
    answer_end: int
    protected_text: str = field(repr=False)
    citation_window_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not all((self.claim_id, self.request_item_id, self.protected_text.strip()))
            or self.answer_start < 0
            or self.answer_end <= self.answer_start
        ):
            raise ValueError("claim identity, text and answer span are required")
        if len(set(self.citation_window_ids)) != len(self.citation_window_ids):
            raise ValueError("claim citation-window IDs must be unique")

    @property
    def digest(self) -> str:
        return stable_hash((
            self.claim_id,
            self.request_item_id,
            self.answer_start,
            self.answer_end,
            self.protected_text,
        ))


@dataclass(frozen=True)
class ClaimExtractionResult:
    attempt_id: str
    answer_digest: str
    extractor_revision: str
    claims: tuple[ExtractedClaim, ...] = field(repr=False)


@dataclass(frozen=True)
class CitationRecord:
    citation_id: str
    window_id: str
    source_identity: CandidateIdentity
    source_reference: str
    exact_span: str
    evidence_digest: str


@dataclass(frozen=True)
class ValidatedClaim:
    claim: ExtractedClaim = field(repr=False)
    citations: tuple[CitationRecord, ...]


@dataclass(frozen=True)
class RawVerificationResult:
    claim_id: str
    claim_digest: str
    bundle_digest: str
    citation_window_ids: tuple[str, ...]
    verifier_revision: str
    verification_policy_version: str
    relation: SemanticRelation
    reason: str


@dataclass(frozen=True)
class VerificationResult:
    claim_id: str
    claim_digest: str
    bundle_digest: str
    citations: tuple[CitationRecord, ...]
    verifier_revision: str
    verification_policy_version: str
    relation: SemanticRelation
    reason: str

    @property
    def digest(self) -> str:
        return stable_hash((
            self.claim_id,
            self.claim_digest,
            self.bundle_digest,
            tuple((item.citation_id, item.evidence_digest) for item in self.citations),
            self.verifier_revision,
            self.verification_policy_version,
            self.relation.value,
            self.reason,
        ))


@dataclass(frozen=True)
class ClaimDecision:
    claim_id: str
    request_item_id: str
    protected_text: str = field(repr=False)
    disposition: ClaimDisposition
    semantic_relation: SemanticRelation | None
    reason: str
    citations: tuple[CitationRecord, ...] = ()
    verification_digest: str | None = None


@dataclass(frozen=True)
class RequestCoverage:
    request_item_id: str
    status: RequestItemStatus
    released_claim_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class Day102Response:
    outcome: Day102Outcome
    safe_reason: str
    answer_text: str = field(repr=False)
    bundle_digest: str | None
    upstream_outcome: str | None
    upstream_reranking_mode: str | None
    upstream_safe_reason: str | None
    generator_mode: GeneratorMode
    verification_mode: VerificationMode
    released_claims: tuple[ClaimDecision, ...] = field(default=(), repr=False)
    rejected_claims: tuple[ClaimDecision, ...] = field(default=(), repr=False)
    request_coverage: tuple[RequestCoverage, ...] = ()
    source_rejections: tuple[tuple[str, str], ...] = ()
    generator_calls: int = 0
    verifier_calls: int = 0


@dataclass(frozen=True)
class ContentSafeGroundingAudit:
    operation_id: str
    original_query_digest: str
    day101_handoff_digest: str
    bundle_digest: str
    upstream_outcome: str
    generator_mode: str
    verification_mode: str
    outcome: str
    released_claim_count: int
    rejected_claim_count: int
    abstained_request_item_count: int
    source_rejection_count: int
    generator_calls: int
    verifier_calls: int
    raw_query_logged: bool = False
    protected_source_text_logged: bool = False
    protected_answer_logged: bool = False
