"""Application-owned Day99 vector generation and retrieval contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math

from rag_chunking_contracts import stable_hash
from rag_acl_contracts import AuthorizationRevisionVector
from rag_embedding_contracts import (
    EmbeddingSet,
    NormalizationPolicy,
    NumericType,
)


class IndexAlgorithm(str, Enum):
    FLAT = "FLAT"
    HNSW = "HNSW"
    IVFFLAT = "IVFFLAT"


class DistanceMetric(str, Enum):
    COSINE_DISTANCE = "COSINE_DISTANCE"


class ThresholdOperator(str, Enum):
    GREATER_THAN_OR_EQUAL = "GREATER_THAN_OR_EQUAL"
    GREATER_THAN = "GREATER_THAN"


class EvidenceState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"


class EvidenceGate(str, Enum):
    CONTENT_READBACK = "CONTENT_READBACK"
    SCORE_SEMANTICS = "SCORE_SEMANTICS"
    EXACT_PARITY = "EXACT_PARITY"
    TENANT_FILTER = "TENANT_FILTER"
    ANN_RECALL = "ANN_RECALL"
    LATENCY_CAPACITY = "LATENCY_CAPACITY"
    RECOVERY = "RECOVERY"
    REAL_PROVIDER = "REAL_PROVIDER"


class GenerationState(str, Enum):
    SEALED = "SEALED"
    PRODUCTION_READY = "PRODUCTION_READY"
    ACTIVATED = "ACTIVATED"
    FAILED = "FAILED"


class ProductionReadiness(str, Enum):
    MORE_EVIDENCE_NEEDED = "MORE_EVIDENCE_NEEDED"
    PRODUCTION_READY = "PRODUCTION_READY"


@dataclass(frozen=True)
class VectorProviderIdentity:
    provider: str
    api_version: str
    immutable_engine_revision: str

    def __post_init__(self) -> None:
        if not all((
            self.provider,
            self.api_version,
            self.immutable_engine_revision,
        )):
            raise ValueError("vector Provider identity must be complete")
        if self.immutable_engine_revision.lower() in {
            "latest", "main", "unknown"
        }:
            raise ValueError("an immutable vector engine revision is required")


@dataclass(frozen=True)
class IndexBuildParameters:
    algorithm: IndexAlgorithm
    m: int | None = None
    ef_construction: int | None = None
    lists: int | None = None

    def __post_init__(self) -> None:
        if self.algorithm is IndexAlgorithm.FLAT:
            if any(value is not None for value in (
                self.m, self.ef_construction, self.lists
            )):
                raise ValueError("Flat has no ANN build parameters")
        elif self.algorithm is IndexAlgorithm.HNSW:
            if (
                self.m is None
                or self.ef_construction is None
                or self.m <= 0
                or self.ef_construction <= 0
                or self.lists is not None
            ):
                raise ValueError("HNSW requires positive m and ef_construction")
        elif self.algorithm is IndexAlgorithm.IVFFLAT:
            if (
                self.lists is None
                or self.lists <= 0
                or self.m is not None
                or self.ef_construction is not None
            ):
                raise ValueError("IVFFlat requires positive lists")


@dataclass(frozen=True)
class VectorIndexContract:
    contract_version: str
    provider: VectorProviderIdentity
    tenant_id: str
    embedding_set_id: str
    embedding_contract_fingerprint: str
    dimensions: int
    numeric_type: NumericType
    normalization: NormalizationPolicy
    metric: DistanceMetric
    build: IndexBuildParameters
    namespace_schema_version: str
    point_identity_version: str
    payload_schema_version: str
    quantization_policy: str
    tenant_isolation_strategy: str
    batch_max_items: int
    batch_max_bytes: int
    durability_expectation: str
    backup_policy_version: str
    update_policy_version: str
    protected_data_policy: str

    def __post_init__(self) -> None:
        if not all((
            self.contract_version,
            self.tenant_id,
            self.embedding_set_id,
            self.embedding_contract_fingerprint,
            self.namespace_schema_version,
            self.point_identity_version,
            self.payload_schema_version,
            self.quantization_policy,
            self.tenant_isolation_strategy,
            self.durability_expectation,
            self.backup_policy_version,
            self.update_policy_version,
            self.protected_data_policy,
        )):
            raise ValueError("vector index contract bindings are required")
        if self.dimensions <= 0:
            raise ValueError("vector dimensions must be positive")
        if self.batch_max_items <= 0 or self.batch_max_bytes <= 0:
            raise ValueError("vector write batch limits must be positive")
        if self.numeric_type is not NumericType.FLOAT32:
            raise ValueError("Day99 reference supports exact float32 only")
        if self.metric is not DistanceMetric.COSINE_DISTANCE:
            raise ValueError("Day99 reference implements cosine distance only")
        if self.normalization is not NormalizationPolicy.UNIT_L2:
            raise ValueError("Day99 cosine reference requires unit-L2 vectors")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))

    def accepts(self, embedding_set: EmbeddingSet) -> bool:
        return (
            embedding_set.embedding_set_id == self.embedding_set_id
            and embedding_set.operation.tenant_id == self.tenant_id
            and embedding_set.contract.fingerprint
            == self.embedding_contract_fingerprint
            and embedding_set.contract.dimensions == self.dimensions
            and embedding_set.contract.numeric_type is self.numeric_type
            and embedding_set.contract.normalization is self.normalization
        )

    def accepts_policy(self, policy: RetrievalPolicyRevision) -> bool:
        if policy.generation_contract_fingerprint != self.fingerprint:
            return False
        if self.build.algorithm is IndexAlgorithm.FLAT:
            return policy.ef_search is None and policy.probes is None
        if self.build.algorithm is IndexAlgorithm.HNSW:
            return policy.ef_search is not None and policy.probes is None
        return policy.probes is not None and policy.ef_search is None


@dataclass(frozen=True)
class RetrievalPolicyRevision:
    policy_version: str
    generation_contract_fingerprint: str
    top_k: int
    minimum_similarity: float
    threshold_operator: ThresholdOperator
    ef_search: int | None = None
    probes: int | None = None

    def __post_init__(self) -> None:
        if not self.policy_version or not self.generation_contract_fingerprint:
            raise ValueError("retrieval policy bindings are required")
        if self.top_k <= 0 or not -1.0 <= self.minimum_similarity <= 1.0:
            raise ValueError("invalid retrieval limits")
        if self.ef_search is not None and self.ef_search <= 0:
            raise ValueError("ef_search must be positive")
        if self.probes is not None and self.probes <= 0:
            raise ValueError("probes must be positive")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))

    def passes(self, similarity: float) -> bool:
        if self.threshold_operator is ThresholdOperator.GREATER_THAN:
            return similarity > self.minimum_similarity
        return similarity >= self.minimum_similarity


@dataclass(frozen=True)
class VectorBuildOperation:
    operation_id: str
    idempotency_key: str
    tenant_id: str
    document_id: str
    document_version_id: str
    chunk_set_id: str
    embedding_set_id: str
    embedding_selection_revision: int
    embedding_set_checksum: str
    embedding_record_ids: tuple[str, ...]
    authorization_decision_id: str = field(repr=False)
    authorization_revisions: AuthorizationRevisionVector
    contract_fingerprint: str
    contract_selection_revision: int

    def __post_init__(self) -> None:
        if not all((
            self.operation_id,
            self.idempotency_key,
            self.tenant_id,
            self.document_id,
            self.document_version_id,
            self.chunk_set_id,
            self.embedding_set_id,
            self.embedding_set_checksum,
            self.authorization_decision_id,
            self.contract_fingerprint,
        )):
            raise ValueError("vector build operation bindings are required")
        if (
            self.embedding_selection_revision <= 0
            or self.contract_selection_revision <= 0
        ):
            raise ValueError("current selection revisions are required")
        if (
            not self.embedding_record_ids
            or len(set(self.embedding_record_ids))
            != len(self.embedding_record_ids)
        ):
            raise ValueError("exact unique EmbeddingRecord identities are required")

    @property
    def stable_result_key(self) -> str:
        return stable_hash((
            self.tenant_id,
            self.document_id,
            self.document_version_id,
            self.chunk_set_id,
            self.embedding_set_id,
            self.embedding_selection_revision,
            self.embedding_set_checksum,
            self.embedding_record_ids,
            self.contract_fingerprint,
            self.contract_selection_revision,
        ))


@dataclass(frozen=True)
class VectorBuildAttempt:
    operation_id: str
    attempt_number: int
    request_id: str

    def __post_init__(self) -> None:
        if not self.operation_id or not self.request_id:
            raise ValueError("vector build attempt correlation is required")
        if self.attempt_number <= 0:
            raise ValueError("attempt number must be positive")


@dataclass(frozen=True)
class VectorPoint:
    point_id: str
    generation_id: str
    tenant_id: str
    embedding_id: str
    chunk_id: str
    vector: tuple[float, ...] = field(repr=False)
    payload: tuple[tuple[str, str], ...] = field(repr=False)

    def __post_init__(self) -> None:
        if not all((
            self.point_id,
            self.generation_id,
            self.tenant_id,
            self.embedding_id,
            self.chunk_id,
        )):
            raise ValueError("vector point identity is required")
        if not self.vector or not all(math.isfinite(value) for value in self.vector):
            raise ValueError("vector point values must be finite and non-empty")
        keys = tuple(key for key, _ in self.payload)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ValueError("payload keys must be canonical")


@dataclass(frozen=True)
class GenerationManifest:
    point_count: int
    point_ids_digest: str
    vector_digest: str
    payload_digest: str
    embedding_set_id: str
    contract_fingerprint: str

    def __post_init__(self) -> None:
        if self.point_count <= 0:
            raise ValueError("generation manifest cannot be empty")
        if not all((
            self.point_ids_digest,
            self.vector_digest,
            self.payload_digest,
            self.embedding_set_id,
            self.contract_fingerprint,
        )):
            raise ValueError("generation manifest bindings are required")


def generation_manifest(
    points: tuple[VectorPoint, ...],
    *,
    embedding_set_id: str,
    contract_fingerprint: str,
) -> GenerationManifest:
    ordered = tuple(sorted(points, key=lambda point: point.point_id))
    return GenerationManifest(
        point_count=len(ordered),
        point_ids_digest=stable_hash(tuple(point.point_id for point in ordered)),
        vector_digest=stable_hash(tuple(
            (point.point_id, point.vector) for point in ordered
        )),
        payload_digest=stable_hash(tuple(
            (point.point_id, point.payload) for point in ordered
        )),
        embedding_set_id=embedding_set_id,
        contract_fingerprint=contract_fingerprint,
    )


@dataclass(frozen=True)
class GateEvidence:
    gate: EvidenceGate
    state: EvidenceState
    scope: str
    safe_detail: str


@dataclass(frozen=True)
class GenerationEvidence:
    gates: tuple[GateEvidence, ...]

    def __post_init__(self) -> None:
        gate_names = tuple(item.gate for item in self.gates)
        if len(set(gate_names)) != len(gate_names):
            raise ValueError("evidence gates must be unique")

    def state_for(self, gate: EvidenceGate) -> EvidenceState:
        return next(
            (item.state for item in self.gates if item.gate is gate),
            EvidenceState.NOT_RUN,
        )

    @property
    def readiness(self) -> ProductionReadiness:
        required = set(EvidenceGate)
        states = {item.gate: item.state for item in self.gates}
        if required <= set(states) and all(
            states[gate] is EvidenceState.PASS for gate in required
        ):
            return ProductionReadiness.PRODUCTION_READY
        return ProductionReadiness.MORE_EVIDENCE_NEEDED


@dataclass(frozen=True)
class VectorGeneration:
    generation_id: str
    operation: VectorBuildOperation
    contract: VectorIndexContract
    manifest: GenerationManifest
    provider_checkpoint: str
    evidence: GenerationEvidence
    state: GenerationState

    def __post_init__(self) -> None:
        if self.manifest.contract_fingerprint != self.contract.fingerprint:
            raise ValueError("generation manifest contract mismatch")
        if self.manifest.embedding_set_id != self.contract.embedding_set_id:
            raise ValueError("generation manifest EmbeddingSet mismatch")
        if (
            self.state in {
                GenerationState.PRODUCTION_READY,
                GenerationState.ACTIVATED,
            }
            and self.evidence.readiness is not ProductionReadiness.PRODUCTION_READY
        ):
            raise ValueError("serving states require every hard gate")


@dataclass(frozen=True)
class ApplicationVectorHit:
    point_id: str
    chunk_id: str
    similarity: float
    generation_id: str


@dataclass(frozen=True)
class SelectedVectorBundle:
    tenant_id: str
    generation_id: str
    generation_contract_fingerprint: str
    retrieval_policy_fingerprint: str
    revision: int


@dataclass(frozen=True)
class VectorOutboxIntent:
    event_id: str
    event_type: str
    tenant_id: str
    generation_id: str
    revision: int
    state: str = "PENDING"
