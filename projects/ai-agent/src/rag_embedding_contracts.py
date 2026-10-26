"""Application-owned immutable Day98 embedding identities and value contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math

from rag_acl_contracts import AuthorizationRevisionVector
from rag_chunking_contracts import stable_hash
from rag_chunking_contracts import SourceSegment


class DeploymentKind(str, Enum):
    HOSTED = "HOSTED"
    SELF_HOSTED = "SELF_HOSTED"


class InputRole(str, Enum):
    DOCUMENT = "DOCUMENT"
    QUERY = "QUERY"


class OverflowPolicy(str, Enum):
    REJECT = "REJECT"


class NumericType(str, Enum):
    FLOAT32 = "FLOAT32"


class NormalizationPolicy(str, Enum):
    UNIT_L2 = "UNIT_L2"
    NONE = "NONE"


class UsageConfidence(str, Enum):
    EXACT = "EXACT"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


class AttemptState(str, Enum):
    CREATED = "CREATED"
    DISPATCHED = "DISPATCHED"
    SUCCEEDED = "SUCCEEDED"
    PROVEN_NOT_EXECUTED = "PROVEN_NOT_EXECUTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ModelIdentity:
    provider: str
    model_id: str
    immutable_revision: str
    deployment: DeploymentKind

    def __post_init__(self) -> None:
        if not all((self.provider, self.model_id, self.immutable_revision)):
            raise ValueError("model identity must be complete")
        if self.immutable_revision.lower() in {"latest", "main", "unknown"}:
            raise ValueError("an immutable model revision is required")


@dataclass(frozen=True)
class TokenizerIdentity:
    name: str
    version: str
    immutable_revision: str

    def __post_init__(self) -> None:
        if not all((self.name, self.version, self.immutable_revision)):
            raise ValueError("tokenizer identity must be complete")


@dataclass(frozen=True)
class BatchLimits:
    max_items: int
    max_tokens: int
    max_utf8_bytes: int

    def __post_init__(self) -> None:
        if min(self.max_items, self.max_tokens, self.max_utf8_bytes) <= 0:
            raise ValueError("batch limits must be positive")


@dataclass(frozen=True)
class EgressPolicy:
    allowed: bool
    destination: str
    retention: str
    zero_data_retention_required: bool

    def __post_init__(self) -> None:
        if not self.destination or not self.retention:
            raise ValueError("egress destination and retention policy are required")
        if not self.allowed and self.destination != "local-only":
            raise ValueError("disallowed egress must remain local-only")


@dataclass(frozen=True)
class EmbeddingContract:
    contract_version: str
    model: ModelIdentity
    tokenizer: TokenizerIdentity
    preprocessing_version: str
    input_role: InputRole
    input_prefix: str
    hard_max_tokens: int
    overflow_policy: OverflowPolicy
    dimensions: int
    numeric_type: NumericType
    normalization: NormalizationPolicy
    api_version: str
    response_schema_version: str
    batch_limits: BatchLimits
    egress: EgressPolicy
    zero_vector_allowed: bool = False
    norm_tolerance: float = 1e-5

    def __post_init__(self) -> None:
        if not all((
            self.contract_version,
            self.preprocessing_version,
            self.api_version,
            self.response_schema_version,
        )):
            raise ValueError("all behavioral versions are required")
        if self.hard_max_tokens <= 0 or self.dimensions <= 0:
            raise ValueError("model limits must be positive")
        if self.overflow_policy is not OverflowPolicy.REJECT:
            raise ValueError("Day98 forbids silent truncation")
        if self.input_role is InputRole.QUERY:
            raise ValueError("Day98 Chunk embedding requires DOCUMENT input role")
        if (
            self.model.deployment is DeploymentKind.HOSTED
            and not self.egress.allowed
        ):
            raise ValueError("a hosted model requires explicit protected-data egress approval")
        if (
            self.zero_vector_allowed
            and self.normalization is NormalizationPolicy.UNIT_L2
        ):
            raise ValueError("a zero vector cannot satisfy unit-L2 normalization")
        if self.norm_tolerance <= 0:
            raise ValueError("normalization tolerance must be positive")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class EmbeddingItem:
    chunk_id: str
    ordinal: int
    text: str = field(repr=False)
    content_hash: str
    source_segments: tuple[SourceSegment, ...]
    token_count: int
    utf8_bytes: int

    def __post_init__(self) -> None:
        if not self.chunk_id or not self.text or not self.content_hash:
            raise ValueError("embedding item identity and text are required")
        if self.ordinal < 0 or self.token_count <= 0 or self.utf8_bytes <= 0:
            raise ValueError("embedding item measurements are invalid")


@dataclass(frozen=True)
class EmbeddingBatch:
    batch_id: str
    ordinal: int
    items: tuple[EmbeddingItem, ...]
    total_tokens: int
    total_utf8_bytes: int


@dataclass(frozen=True)
class EmbeddingOperationIdentity:
    operation_id: str
    idempotency_key: str
    tenant_id: str
    principal_subject: str = field(repr=False)
    authorization_decision_id: str = field(repr=False)
    authorization_revisions: AuthorizationRevisionVector
    document_id: str
    document_version_id: str
    chunk_set_id: str
    authorized_chunk_ids: tuple[str, ...]
    selection_revision: int
    document_state_version: int
    document_fence: int
    contract_fingerprint: str
    contract_selection_revision: int

    def __post_init__(self) -> None:
        if not all((
            self.operation_id,
            self.idempotency_key,
            self.tenant_id,
            self.principal_subject,
            self.authorization_decision_id,
            self.document_id,
            self.document_version_id,
            self.chunk_set_id,
            self.contract_fingerprint,
        )):
            raise ValueError("embedding operation bindings are required")
        if not self.authorized_chunk_ids:
            raise ValueError("embedding operation requires exact chunks")
        if self.contract_selection_revision <= 0:
            raise ValueError("current contract selection revision is required")

    @property
    def stable_result_key(self) -> str:
        return stable_hash((
            self.tenant_id,
            self.document_id,
            self.document_version_id,
            self.chunk_set_id,
            self.authorized_chunk_ids,
            self.contract_fingerprint,
        ))


@dataclass(frozen=True)
class EmbeddingAttemptIdentity:
    operation_id: str
    attempt_number: int
    request_id: str
    generation: int

    def __post_init__(self) -> None:
        if not self.operation_id or not self.request_id:
            raise ValueError("attempt correlation is required")
        if self.attempt_number <= 0 or self.generation <= 0:
            raise ValueError("attempt and generation must be positive")


@dataclass(frozen=True)
class ProviderEmbeddingItem:
    item_id: str
    vector: tuple[float, ...] = field(repr=False)


@dataclass(frozen=True)
class ProviderEmbeddingCandidate:
    request_id: str
    batch_id: str
    model: ModelIdentity
    response_schema_version: str
    items: tuple[ProviderEmbeddingItem, ...]
    usage_tokens: int | None
    usage_confidence: UsageConfidence
    latency_ms: float
    cost_microunits: int | None
    cost_confidence: UsageConfidence
    partial: bool = False


@dataclass(frozen=True)
class ValidatedEmbeddingBatch:
    batch: EmbeddingBatch
    candidate: ProviderEmbeddingCandidate


@dataclass(frozen=True)
class EmbeddingRecord:
    embedding_id: str
    embedding_set_id: str
    tenant_id: str
    chunk_id: str
    ordinal: int
    content_hash: str
    source_segments: tuple[SourceSegment, ...]
    contract_fingerprint: str
    vector: tuple[float, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if not self.vector or not all(math.isfinite(value) for value in self.vector):
            raise ValueError("durable embedding vector must be finite and non-empty")


@dataclass(frozen=True)
class EmbeddingSet:
    embedding_set_id: str
    operation: EmbeddingOperationIdentity
    contract: EmbeddingContract
    records: tuple[EmbeddingRecord, ...]
    manifest_checksum: str

    def __post_init__(self) -> None:
        if tuple(record.ordinal for record in self.records) != tuple(range(len(self.records))):
            raise ValueError("embedding records must preserve exact Chunk order")
        if any(
            record.embedding_set_id != self.embedding_set_id
            or record.tenant_id != self.operation.tenant_id
            or record.contract_fingerprint != self.contract.fingerprint
            or len(record.vector) != self.contract.dimensions
            for record in self.records
        ):
            raise ValueError("EmbeddingSet must be homogeneous")


@dataclass(frozen=True)
class EmbeddingSelection:
    tenant_id: str
    document_id: str
    chunk_set_id: str
    embedding_set_id: str
    revision: int


@dataclass(frozen=True)
class EmbeddingOutboxIntent:
    event_id: str
    tenant_id: str
    document_id: str
    chunk_set_id: str
    embedding_set_id: str
    selection_revision: int
    state: str = "PENDING"


def vector_manifest_checksum(
    *,
    chunk_ids: tuple[str, ...],
    vectors: tuple[tuple[float, ...], ...],
    contract_fingerprint: str,
) -> str:
    """Bind protected vectors without emitting them in ordinary evidence."""

    return stable_hash((chunk_ids, vectors, contract_fingerprint))
