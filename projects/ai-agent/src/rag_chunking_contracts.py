"""Application-owned Day96 chunking identities and immutable value contracts.

These types contain no framework or model-provider objects. A candidate is a
proposal, while a ChunkSet is a durable fact created only by the Committer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json

from rag_ingestion_contracts import DocumentVersionIdentity


def stable_hash(value: object) -> str:
    """Hash a JSON-serializable application contract deterministically."""

    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class ChunkStrategy(str, Enum):
    FIXED_TOKEN = "fixed-token"
    RECURSIVE = "recursive-structure-aware"
    SECTION_AWARE = "section-paragraph-sentence-aware"


class OversizedPolicy(str, Enum):
    FAIL_CLOSED = "fail-closed"
    BOUNDED_FALLBACK = "bounded-token-fallback"


@dataclass(frozen=True)
class TokenizerContract:
    name: str
    version: str

    def __post_init__(self) -> None:
        if not self.name or not self.version:
            raise ValueError("tokenizer name and version are required")


@dataclass(frozen=True)
class ChunkingContract:
    strategy: ChunkStrategy
    strategy_version: str
    tokenizer: TokenizerContract
    normalization_version: str
    soft_target_tokens: int
    hard_max_tokens: int
    min_useful_tokens: int
    overlap_tokens: int
    max_chunk_count: int
    max_input_chars: int
    max_output_chars: int
    deadline_seconds: float
    oversized_policy: OversizedPolicy
    max_token_work_units: int = 1_000_000
    max_estimated_memory_bytes: int = 64_000_000
    boundary_policy_version: str = "markdown-structure-v1"

    def __post_init__(self) -> None:
        if not all((
            self.strategy_version,
            self.normalization_version,
            self.boundary_policy_version,
        )):
            raise ValueError("all behavioral policy versions are required")
        if self.normalization_version not in {
            "identity-v1", "collapse-horizontal-space-v1"
        }:
            raise ValueError("unsupported normalization requires a source map")
        if self.soft_target_tokens <= 0 or self.hard_max_tokens <= 0:
            raise ValueError("token budgets must be positive")
        if self.soft_target_tokens > self.hard_max_tokens:
            raise ValueError("soft target cannot exceed hard maximum")
        if not 0 < self.min_useful_tokens <= self.hard_max_tokens:
            raise ValueError("minimum useful size is invalid")
        if not 0 <= self.overlap_tokens < self.soft_target_tokens:
            raise ValueError("overlap must be smaller than soft target")
        if min(
            self.max_chunk_count,
            self.max_input_chars,
            self.max_output_chars,
            self.max_token_work_units,
            self.max_estimated_memory_bytes,
        ) <= 0 or self.deadline_seconds <= 0:
            raise ValueError("resource budgets must be positive")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class ChunkingOperationIdentity:
    version: DocumentVersionIdentity
    source_artifact_id: str
    parsed_artifact_id: str
    operation_id: str
    idempotency_key: str
    contract_fingerprint: str

    def __post_init__(self) -> None:
        if not all((
            self.source_artifact_id,
            self.parsed_artifact_id,
            self.operation_id,
            self.idempotency_key,
            self.contract_fingerprint,
        )):
            raise ValueError("chunking operation bindings are required")

    @property
    def stable_result_key(self) -> str:
        return stable_hash((
            self.version.tenant_id,
            self.version.document_id,
            self.version.document_version_id,
            self.source_artifact_id,
            self.parsed_artifact_id,
            self.contract_fingerprint,
        ))


@dataclass(frozen=True)
class ChunkingAttemptIdentity:
    operation_id: str
    attempt_number: int
    request_id: str
    generation: int

    def __post_init__(self) -> None:
        if not self.operation_id or not self.request_id:
            raise ValueError("attempt correlation is required")
        if self.attempt_number <= 0 or self.generation <= 0:
            raise ValueError("attempt and generation must be positive")


@dataclass(frozen=True, order=True)
class SourceSegment:
    start: int
    end: int
    role: str = "body"

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start or not self.role:
            raise ValueError("source segment must be non-empty and non-negative")


@dataclass(frozen=True)
class ChunkCandidate:
    ordinal: int
    text: str
    source_segments: tuple[SourceSegment, ...]
    token_count: int
    content_hash: str
    boundary_reason: str
    overlap_left_tokens: int = 0
    overlap_right_tokens: int = 0
    joiner: str = ""


@dataclass(frozen=True)
class ChunkManifest:
    chunk_count: int
    source_checksum: str
    contract_fingerprint: str
    chunks_checksum: str


@dataclass(frozen=True)
class ChunkSetCandidate:
    operation: ChunkingOperationIdentity
    attempt: ChunkingAttemptIdentity
    experiment_id: str
    chunks: tuple[ChunkCandidate, ...]
    manifest: ChunkManifest


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    chunk_set_id: str
    candidate: ChunkCandidate


@dataclass(frozen=True)
class ChunkSet:
    chunk_set_id: str
    operation: ChunkingOperationIdentity
    experiment_id: str
    manifest: ChunkManifest
    chunks: tuple[Chunk, ...]


def candidate_chunks_checksum(chunks: tuple[ChunkCandidate, ...]) -> str:
    """Bind text, source, order, boundary, and overlap in one manifest hash."""

    return stable_hash([asdict(chunk) for chunk in chunks])
