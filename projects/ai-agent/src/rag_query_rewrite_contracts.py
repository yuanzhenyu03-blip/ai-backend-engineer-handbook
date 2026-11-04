"""Application-owned Day101 query-rewrite identities and policies."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import hmac

from rag_chunking_contracts import stable_hash


class QueryVariantSource(str, Enum):
    ORIGINAL = "ORIGINAL"
    NORMALIZED = "NORMALIZED"
    SPELLING_CORRECTED = "SPELLING_CORRECTED"
    ACRONYM_EXPANDED = "ACRONYM_EXPANDED"
    PARAPHRASE = "PARAPHRASE"
    DECOMPOSED = "DECOMPOSED"
    OTHER_APPROVED = "OTHER_APPROVED"


class QueryVariantValidation(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RewriteMode(str, Enum):
    FULL_REWRITE = "FULL_REWRITE"
    PARTIAL_REWRITE = "PARTIAL_REWRITE"
    ORIGINAL_ONLY_FALLBACK = "ORIGINAL_ONLY_FALLBACK"


class RewriteFailureReason(str, Enum):
    NONE = "NONE"
    REWRITE_EGRESS_DENIED = "REWRITE_EGRESS_DENIED"
    REWRITE_PROVIDER_FAILED = "REWRITE_PROVIDER_FAILED"
    REWRITE_PROVIDER_TIMEOUT = "REWRITE_PROVIDER_TIMEOUT"
    REWRITE_OUTPUT_INVALID = "REWRITE_OUTPUT_INVALID"
    SEMANTIC_DRIFT_REJECTED = "SEMANTIC_DRIFT_REJECTED"
    REWRITE_BUDGET_EXHAUSTED = "REWRITE_BUDGET_EXHAUSTED"


def protected_query_digest(secret: bytes, tenant_id: str, text: str) -> str:
    """Return a tenant-bound digest without exposing protected query text."""

    if not secret or not tenant_id or not text:
        raise ValueError("secret, tenant and protected query text are required")
    message = (tenant_id + "\x00" + text).encode("utf-8")
    return "hmac-sha256:" + hmac.new(secret, message, hashlib.sha256).hexdigest()


def normalized_query_text(text: str) -> str:
    return " ".join(text.split()).casefold()


@dataclass(frozen=True)
class OriginalQueryContract:
    operation_id: str
    tenant_id: str
    principal_hash: str
    action: str
    purpose: str
    query_digest: str
    selected_bundle_fingerprint: str
    client_filter_fingerprint: str
    protected_text: str = field(repr=False)

    def __post_init__(self) -> None:
        required = (
            self.operation_id,
            self.tenant_id,
            self.principal_hash,
            self.action,
            self.purpose,
            self.query_digest,
            self.selected_bundle_fingerprint,
            self.client_filter_fingerprint,
            self.protected_text,
        )
        if not all(required):
            raise ValueError("complete original-query identity is required")
        if not self.query_digest.startswith("hmac-sha256:"):
            raise ValueError("original query requires a keyed protected digest")

    @property
    def fingerprint(self) -> str:
        return stable_hash((
            self.operation_id,
            self.tenant_id,
            self.principal_hash,
            self.action,
            self.purpose,
            self.query_digest,
            self.selected_bundle_fingerprint,
            self.client_filter_fingerprint,
        ))


@dataclass(frozen=True)
class QueryRewriteContract:
    contract_version: str
    provider: str
    immutable_provider_revision: str
    prompt_revision: str
    tokenizer_revision: str
    normalization_version: str
    locale: str
    max_generated_variants: int
    max_variant_chars: int
    max_total_utf8_bytes: int
    max_rewrite_rounds: int
    timeout_ms: int
    allowed_sources: tuple[QueryVariantSource, ...]
    protected_query_policy: str
    egress_policy_version: str
    deterministic_seed: int = 0

    def __post_init__(self) -> None:
        required = (
            self.contract_version,
            self.provider,
            self.immutable_provider_revision,
            self.prompt_revision,
            self.tokenizer_revision,
            self.normalization_version,
            self.locale,
            self.protected_query_policy,
            self.egress_policy_version,
        )
        if not all(required):
            raise ValueError("rewrite contract bindings are required")
        if self.immutable_provider_revision.lower() in {"latest", "main", "unknown"}:
            raise ValueError("rewrite provider revision must be immutable")
        if min(
            self.max_generated_variants,
            self.max_variant_chars,
            self.max_total_utf8_bytes,
            self.max_rewrite_rounds,
            self.timeout_ms,
        ) <= 0:
            raise ValueError("rewrite budgets must be positive")
        if self.max_rewrite_rounds != 1:
            raise ValueError("Day101 reference permits one bounded rewrite round")
        if not self.allowed_sources or QueryVariantSource.ORIGINAL in self.allowed_sources:
            raise ValueError("generated-source allowlist must exclude ORIGINAL")

    @property
    def fingerprint(self) -> str:
        values = asdict(self)
        values["allowed_sources"] = tuple(item.value for item in self.allowed_sources)
        return stable_hash(values)


@dataclass(frozen=True)
class QueryRewriteDegradationPolicy:
    policy_version: str
    allow_original_only_on_egress_denied: bool
    allow_original_only_on_provider_failure: bool
    allow_original_only_on_timeout: bool
    allow_partial_valid_variants: bool

    def __post_init__(self) -> None:
        if not self.policy_version:
            raise ValueError("rewrite degradation policy version is required")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class RewriteEgressPolicy:
    policy_version: str
    allowed_providers: frozenset[str]
    allow_protected_query_egress: bool

    def __post_init__(self) -> None:
        if not self.policy_version:
            raise ValueError("rewrite egress policy version is required")


@dataclass(frozen=True)
class RewriteCandidate:
    source: QueryVariantSource
    locale: str
    provider_ordinal: int
    protected_text: str = field(repr=False)

    def __post_init__(self) -> None:
        if (
            self.source is QueryVariantSource.ORIGINAL
            or not self.locale
            or self.provider_ordinal <= 0
            or not self.protected_text
        ):
            raise ValueError("generated rewrite candidate is invalid")


@dataclass(frozen=True)
class QueryVariant:
    operation_id: str
    rewrite_set_id: str
    variant_id: str
    ordinal: int
    source: QueryVariantSource
    query_digest: str
    rewrite_contract_fingerprint: str
    locale: str
    validation: QueryVariantValidation
    protected_text: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all((
            self.operation_id,
            self.rewrite_set_id,
            self.variant_id,
            self.query_digest,
            self.rewrite_contract_fingerprint,
            self.locale,
            self.protected_text,
        )) or self.ordinal < 0:
            raise ValueError("complete query-variant identity is required")
        if self.ordinal == 0 and self.source is not QueryVariantSource.ORIGINAL:
            raise ValueError("variant ordinal zero must preserve the original query")
        if self.ordinal > 0 and self.source is QueryVariantSource.ORIGINAL:
            raise ValueError("only variant ordinal zero may be ORIGINAL")

    @property
    def fingerprint(self) -> str:
        return stable_hash((
            self.operation_id,
            self.rewrite_set_id,
            self.variant_id,
            self.ordinal,
            self.source.value,
            self.query_digest,
            self.rewrite_contract_fingerprint,
            self.locale,
            self.validation.value,
        ))


@dataclass(frozen=True)
class RewriteSet:
    rewrite_set_id: str
    original_query_fingerprint: str
    rewrite_contract_fingerprint: str
    degradation_policy_fingerprint: str
    mode: RewriteMode
    variants: tuple[QueryVariant, ...]
    rejected_candidates: tuple[tuple[str, str], ...] = ()
    degradation_reason: RewriteFailureReason = RewriteFailureReason.NONE

    def __post_init__(self) -> None:
        if not all((
            self.rewrite_set_id,
            self.original_query_fingerprint,
            self.rewrite_contract_fingerprint,
            self.degradation_policy_fingerprint,
        )) or not self.variants:
            raise ValueError("rewrite set requires identities and variants")
        if self.variants[0].source is not QueryVariantSource.ORIGINAL:
            raise ValueError("rewrite set must preserve original query as variant zero")
        if tuple(item.ordinal for item in self.variants) != tuple(range(len(self.variants))):
            raise ValueError("query-variant ordinals must be deterministic and contiguous")
        if len({item.variant_id for item in self.variants}) != len(self.variants):
            raise ValueError("query-variant identities must be unique")

    @property
    def fingerprint(self) -> str:
        return stable_hash((
            self.rewrite_set_id,
            self.original_query_fingerprint,
            self.rewrite_contract_fingerprint,
            self.degradation_policy_fingerprint,
            self.mode.value,
            tuple(item.fingerprint for item in self.variants),
            self.rejected_candidates,
            self.degradation_reason.value,
        ))


@dataclass(frozen=True)
class ContentSafeRewriteAudit:
    operation_id: str
    original_query_digest: str
    rewrite_set_id: str
    mode: str
    approved_variant_count: int
    rejected_count: int
    reason: str
    raw_query_logged: bool = False
    protected_variant_text_logged: bool = False
