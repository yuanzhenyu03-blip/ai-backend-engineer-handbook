"""Day97 current-input eligibility and immutable provenance verification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag_chunking_committer import InMemoryChunkSetStore
from rag_chunking_contracts import (
    Chunk,
    ChunkSet,
    SourceSegment,
    candidate_chunks_checksum,
)
from rag_document_lifecycle import evaluate_day96_chunking_eligibility
from rag_ingestion_committer import InMemoryIngestionLifecycleStore
from rag_ingestion_contracts import (
    DocumentIdentity,
    DocumentVersionIdentity,
    sha256_text,
)


class ProvenanceOutcome(str, Enum):
    VALID = "VALID"
    NOT_ACCESSIBLE = "NOT_ACCESSIBLE"
    NOT_CURRENT = "NOT_CURRENT"
    LINEAGE_INCOMPLETE = "LINEAGE_INCOMPLETE"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"


@dataclass(frozen=True)
class ChunkProvenance:
    tenant_id: str
    document_id: str
    document_version_id: str
    source_artifact_id: str
    source_checksum: str
    parsed_artifact_id: str
    parsed_checksum: str
    chunk_set_id: str
    chunk_set_checksum: str
    chunk_id: str
    chunk_content_hash: str
    source_segments: tuple[SourceSegment, ...]


@dataclass(frozen=True)
class CurrentRAGBinding:
    version: DocumentVersionIdentity
    source_artifact_id: str
    parsed_artifact_id: str
    chunk_set_id: str
    chunk_ids: tuple[str, ...]
    document_state_version: int
    document_fence: int
    selection_revision: int
    selection_fence: int


@dataclass(frozen=True)
class ProvenanceDecision:
    outcome: ProvenanceOutcome
    safe_reason: str
    binding: CurrentRAGBinding | None = None
    records: tuple[ChunkProvenance, ...] = ()
    chunk_set: ChunkSet | None = None

    @property
    def valid(self) -> bool:
        return self.outcome is ProvenanceOutcome.VALID

    def __post_init__(self) -> None:
        if self.valid != (
            self.binding is not None
            and bool(self.records)
            and self.chunk_set is not None
        ):
            raise ValueError("valid provenance requires complete current evidence")


class CurrentRAGProvenanceValidator:
    """Reread Day95/Day96 authority; never trust an Outbox payload."""

    def __init__(
        self,
        *,
        day95_store: InMemoryIngestionLifecycleStore,
        chunk_store: InMemoryChunkSetStore,
    ) -> None:
        self._day95 = day95_store
        self._chunks = chunk_store

    def evaluate(
        self,
        *,
        document: DocumentIdentity,
        expected_chunk_set_id: str | None = None,
    ) -> ProvenanceDecision:
        """Validate the current selected set and every exact source occurrence."""

        # These process-local stores use re-entrant locks.  Holding both models
        # one authoritative snapshot; production requires a durable equivalent.
        with self._day95._lock, self._chunks._lock:
            try:
                head = self._day95.read_document(document)
            except KeyError:
                return self._blocked(
                    ProvenanceOutcome.NOT_ACCESSIBLE,
                    "CURRENT_RESOURCE_NOT_ACCESSIBLE",
                )
            selection = self._chunks.read_selection(document)
            if selection is None:
                return self._blocked(
                    ProvenanceOutcome.NOT_CURRENT,
                    "CURRENT_CHUNK_SELECTION_MISSING",
                )
            if (
                expected_chunk_set_id is not None
                and selection.chunk_set_id != expected_chunk_set_id
            ):
                return self._blocked(
                    ProvenanceOutcome.NOT_CURRENT,
                    "SELECTED_CHUNK_SET_REVISION_CHANGED",
                )
            chunk_set = self._chunks.read_chunk_set(selection.chunk_set_id)
            if chunk_set is None:
                return self._blocked(
                    ProvenanceOutcome.LINEAGE_INCOMPLETE,
                    "SELECTED_CHUNK_SET_FACT_MISSING",
                )
            operation = chunk_set.operation
            if (
                operation.version.document != document
                or selection.tenant_id != document.tenant_id
                or selection.document_id != document.document_id
                or selection.document_version_id
                != operation.version.document_version_id
                or head.active_version_id
                != operation.version.document_version_id
            ):
                return self._blocked(
                    ProvenanceOutcome.NOT_CURRENT,
                    "DAY95_ACTIVE_VERSION_OR_DAY96_SELECTION_CHANGED",
                )
            try:
                version = self._day95.read_version(operation.version)
                ingestion = self._day95.read_operation(
                    version.definition.created_by_operation_id
                )
            except KeyError:
                return self._blocked(
                    ProvenanceOutcome.LINEAGE_INCOMPLETE,
                    "DAY95_LIFECYCLE_FACT_MISSING",
                )
            eligibility = evaluate_day96_chunking_eligibility(
                document=head,
                version=version,
                operation=ingestion,
            )
            if (
                not eligibility.eligible
                or eligibility.parsed_artifact_id
                != operation.parsed_artifact_id
            ):
                return self._blocked(
                    ProvenanceOutcome.NOT_CURRENT,
                    "DAY95_CURRENT_VERSION_NOT_ELIGIBLE",
                )
            parsed = self._day95.read_parsed_artifact(
                operation.parsed_artifact_id
            )
            source = self._day95.read_source_artifact(
                operation.source_artifact_id
            )
            if parsed is None or source is None:
                return self._blocked(
                    ProvenanceOutcome.LINEAGE_INCOMPLETE,
                    "SOURCE_OR_PARSED_ARTIFACT_BINDING_MISSING",
                )
            if (
                parsed.version != operation.version
                or source.version != operation.version
                or parsed.source_artifact_id != source.source_artifact_id
                or parsed.manifest.source_artifact_id
                != source.source_artifact_id
                or version.definition.source_artifact_id
                != source.source_artifact_id
                or parsed.manifest.source_checksum_sha256
                != source.checksum_sha256
            ):
                return self._blocked(
                    ProvenanceOutcome.LINEAGE_INCOMPLETE,
                    "SOURCE_PARSED_CHUNK_LINEAGE_BINDING_CONFLICT",
                )
            if (
                parsed.output_checksum_sha256
                != sha256_text(parsed.canonical_text)
                or parsed.manifest.output_checksum_sha256
                != parsed.output_checksum_sha256
                or chunk_set.manifest.source_checksum
                != parsed.output_checksum_sha256
            ):
                return self._blocked(
                    ProvenanceOutcome.CHECKSUM_MISMATCH,
                    "PROVENANCE_ARTIFACT_CHECKSUM_MISMATCH",
                )

            records: list[ChunkProvenance] = []
            if candidate_chunks_checksum(tuple(
                chunk.candidate for chunk in chunk_set.chunks
            )) != chunk_set.manifest.chunks_checksum:
                return self._blocked(
                    ProvenanceOutcome.CHECKSUM_MISMATCH,
                    "CHUNK_SET_MANIFEST_CHECKSUM_MISMATCH",
                )
            for chunk in chunk_set.chunks:
                if not self._valid_chunk(chunk, parsed.canonical_text):
                    return self._blocked(
                        ProvenanceOutcome.CHECKSUM_MISMATCH,
                        "CHUNK_SOURCE_SPAN_OR_CHECKSUM_MISMATCH",
                    )
                records.append(ChunkProvenance(
                    tenant_id=document.tenant_id,
                    document_id=document.document_id,
                    document_version_id=operation.version.document_version_id,
                    source_artifact_id=source.source_artifact_id,
                    source_checksum=source.checksum_sha256,
                    parsed_artifact_id=parsed.parsed_artifact_id,
                    parsed_checksum=parsed.output_checksum_sha256,
                    chunk_set_id=chunk_set.chunk_set_id,
                    chunk_set_checksum=chunk_set.manifest.chunks_checksum,
                    chunk_id=chunk.chunk_id,
                    chunk_content_hash=chunk.candidate.content_hash,
                    source_segments=chunk.candidate.source_segments,
                ))

            if len({record.chunk_id for record in records}) != len(records):
                return self._blocked(
                    ProvenanceOutcome.LINEAGE_INCOMPLETE,
                    "CHUNK_PROVENANCE_OCCURRENCE_ID_CONFLICT",
                )
            binding = CurrentRAGBinding(
                version=operation.version,
                source_artifact_id=source.source_artifact_id,
                parsed_artifact_id=parsed.parsed_artifact_id,
                chunk_set_id=chunk_set.chunk_set_id,
                chunk_ids=tuple(record.chunk_id for record in records),
                document_state_version=head.state_version,
                document_fence=head.fence_token,
                selection_revision=selection.revision,
                selection_fence=selection.fence,
            )
            return ProvenanceDecision(
                ProvenanceOutcome.VALID,
                "CURRENT_SELECTED_CHUNK_PROVENANCE_VALID",
                binding=binding,
                records=tuple(records),
                chunk_set=chunk_set,
            )

    @staticmethod
    def _valid_chunk(chunk: Chunk, canonical_text: str) -> bool:
        candidate = chunk.candidate
        if not candidate.source_segments:
            return False
        if tuple(sorted(candidate.source_segments)) != candidate.source_segments:
            return False
        if any(
            segment.end > len(canonical_text)
            for segment in candidate.source_segments
        ):
            return False
        # Day96 may have used a validated normalization source map.  Day97 does
        # not reinterpret that contract; it verifies the immutable manifest,
        # content hash, and retained canonical source-span coordinates.
        return sha256_text(candidate.text) == candidate.content_hash

    @staticmethod
    def _blocked(
        outcome: ProvenanceOutcome,
        reason: str,
    ) -> ProvenanceDecision:
        return ProvenanceDecision(outcome, reason)
