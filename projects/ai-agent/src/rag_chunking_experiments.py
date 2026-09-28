"""Controlled Day96 experiment records; this runner has no commit authority."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean, median

from rag_chunking_contracts import (
    ChunkSetCandidate,
    ChunkingAttemptIdentity,
    ChunkingContract,
    ChunkingOperationIdentity,
)
from rag_chunking_normalization import normalize
from rag_chunking_strategies import ChunkGenerationError, ChunkingStrategyAdapter
from rag_chunking_validator import ChunkSetCandidateValidator
from rag_document_lifecycle import evaluate_day96_chunking_eligibility
from rag_ingestion_committer import (
    DocumentVersionLifecycleRecord,
    IngestionOperationRecord,
)
from rag_ingestion_contracts import (
    DocumentHeadSnapshot,
    ParsedArtifactDefinition,
    SourceArtifactReference,
)


@dataclass(frozen=True)
class StructuralMetrics:
    chunk_count: int
    min_token_count: int
    max_token_count: int
    p50_token_count: float
    p95_token_count: float | None
    mean_token_count: float
    empty_chunk_count: int
    oversized_chunk_count: int
    hard_fallback_count: int
    boundary_break_count: int
    heading_context_chunk_count: int
    table_header_context_chunk_count: int
    coverage_ratio: float
    gap_count: int
    overlap_source_ratio: float
    unintended_duplication_count: int
    provenance_roundtrip_pass_count: int
    deterministic_rerun_match: bool


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    parsed_artifact_id: str
    contract_fingerprint: str
    strategy: str
    status: str
    safe_reason: str
    metrics: StructuralMetrics | None
    chunks_checksum: str | None
    contract: ChunkingContract
    candidate: ChunkSetCandidate | None = None

    def safe_report(self) -> dict[str, object]:
        """Never put raw document or Chunk text into experiment evidence."""

        return {
            "experiment_id": self.experiment_id,
            "parsed_artifact_id": self.parsed_artifact_id,
            "contract_fingerprint": self.contract_fingerprint,
            "contract": asdict(self.contract),
            "strategy": self.strategy,
            "status": self.status,
            "safe_reason": self.safe_reason,
            "metrics": None if self.metrics is None else asdict(self.metrics),
            "chunks_checksum": self.chunks_checksum,
            "evidence_scope": "DAY96_STRUCTURAL_ONLY",
        }


@dataclass(frozen=True)
class SelectionProposal:
    candidate_experiment_id: str
    hypothesis: str
    selection_reason: str
    rejected_alternatives: tuple[str, ...]
    remaining_uncertainty: str
    evidence_level: str = "EXECUTED_LOCAL_RUNTIME"

    def __post_init__(self) -> None:
        if not all((
            self.candidate_experiment_id,
            self.hypothesis,
            self.selection_reason,
            self.remaining_uncertainty,
        )):
            raise ValueError("selection proposal must retain its rationale")


class ControlledChunkingExperimentRunner:
    """Compare contracts on one fixed Day95 input without selecting a winner."""

    def __init__(
        self,
        adapter: ChunkingStrategyAdapter,
        validator: ChunkSetCandidateValidator,
    ) -> None:
        self._adapter = adapter
        self._validator = validator

    def run(
        self,
        *,
        document: DocumentHeadSnapshot,
        version: DocumentVersionLifecycleRecord,
        ingestion: IngestionOperationRecord,
        parsed: ParsedArtifactDefinition,
        source: SourceArtifactReference,
        contract: ChunkingContract,
        operation: ChunkingOperationIdentity,
        attempt: ChunkingAttemptIdentity,
        experiment_id: str,
    ) -> ExperimentRecord:
        eligibility = evaluate_day96_chunking_eligibility(
            document=document, version=version, operation=ingestion
        )
        if (
            not eligibility.eligible
            or eligibility.parsed_artifact_id != parsed.parsed_artifact_id
            or source.version != parsed.version
            or source.checksum_sha256
            != parsed.manifest.source_checksum_sha256
        ):
            return self._failed(
                experiment_id, parsed, contract, "DAY95_INPUT_INELIGIBLE"
            )
        try:
            candidate = self._adapter.generate(
                parsed=parsed,
                contract=contract,
                operation=operation,
                attempt=attempt,
                experiment_id=experiment_id,
            )
            rerun = self._adapter.generate(
                parsed=parsed,
                contract=contract,
                operation=operation,
                attempt=attempt,
                experiment_id=experiment_id,
            )
        except ChunkGenerationError as error:
            return self._failed(
                experiment_id, parsed, contract, error.safe_reason
            )
        decision = self._validator.evaluate(
            document=document,
            version=version,
            ingestion=ingestion,
            parsed=parsed,
            source=source,
            contract=contract,
            candidate=candidate,
        )
        if not decision.ready:
            return self._failed(
                experiment_id, parsed, contract, decision.safe_reason
            )
        metrics = self._metrics(parsed, contract, candidate, rerun)
        if not metrics.deterministic_rerun_match:
            return ExperimentRecord(
                experiment_id,
                parsed.parsed_artifact_id,
                contract.fingerprint,
                contract.strategy.value,
                "REJECTED",
                "DETERMINISTIC_RERUN_MISMATCH",
                metrics,
                candidate.manifest.chunks_checksum,
                contract,
            )
        return ExperimentRecord(
            experiment_id,
            parsed.parsed_artifact_id,
            contract.fingerprint,
            contract.strategy.value,
            "VALIDATED",
            "STRUCTURAL_VALIDATION_PASSED",
            metrics,
            candidate.manifest.chunks_checksum,
            contract,
            candidate,
        )

    @staticmethod
    def _failed(
        experiment_id: str,
        parsed: ParsedArtifactDefinition,
        contract: ChunkingContract,
        reason: str,
    ) -> ExperimentRecord:
        return ExperimentRecord(
            experiment_id,
            parsed.parsed_artifact_id,
            contract.fingerprint,
            contract.strategy.value,
            "REJECTED",
            reason,
            None,
            None,
            contract,
        )

    @staticmethod
    def _metrics(
        parsed: ParsedArtifactDefinition,
        contract: ChunkingContract,
        candidate: ChunkSetCandidate,
        rerun: ChunkSetCandidate,
    ) -> StructuralMetrics:
        counts = sorted(chunk.token_count for chunk in candidate.chunks)
        p95 = None
        if len(counts) >= 20:
            p95 = float(counts[(95 * len(counts) + 99) // 100 - 1])
        spans = sorted(
            segment
            for chunk in candidate.chunks
            for segment in chunk.source_segments
        )
        cursor = 0
        covered = 0
        gaps = 0
        for segment in spans:
            if segment.start > cursor:
                gaps += 1
            newly_covered = max(0, segment.end - max(segment.start, cursor))
            covered += newly_covered
            cursor = max(cursor, segment.end)
        if cursor < len(parsed.canonical_text):
            gaps += 1
        overlap_chars = sum(
            max(0, min(left.end, right.end) - max(left.start, right.start))
            for previous, current in zip(candidate.chunks, candidate.chunks[1:])
            for left in previous.source_segments
            for right in current.source_segments
            if left.role == "body" and right.role == "body"
        )
        span_keys = [
            tuple((segment.start, segment.end) for segment in chunk.source_segments)
            for chunk in candidate.chunks
        ]
        roundtrip = sum(
            chunk.text == chunk.joiner.join(
                normalize(
                    parsed.canonical_text[segment.start:segment.end],
                    contract.normalization_version,
                ).text
                for segment in chunk.source_segments
            )
            for chunk in candidate.chunks
        )
        return StructuralMetrics(
            chunk_count=len(counts),
            min_token_count=counts[0],
            max_token_count=counts[-1],
            p50_token_count=float(median(counts)),
            p95_token_count=p95,
            mean_token_count=mean(counts),
            empty_chunk_count=sum(not chunk.text for chunk in candidate.chunks),
            oversized_chunk_count=sum(
                count > contract.hard_max_tokens for count in counts
            ),
            hard_fallback_count=sum(
                chunk.boundary_reason == "HARD_TOKEN_FALLBACK"
                for chunk in candidate.chunks
            ),
            boundary_break_count=sum(
                chunk.boundary_reason in {
                    "FIXED_TOKEN_WINDOW",
                    "WHITESPACE_FALLBACK",
                    "HARD_TOKEN_FALLBACK",
                }
                for chunk in candidate.chunks
            ),
            heading_context_chunk_count=sum(
                any(
                    segment.role == "heading-context"
                    for segment in chunk.source_segments
                )
                for chunk in candidate.chunks
            ),
            table_header_context_chunk_count=sum(
                any(
                    segment.role == "table-header-context"
                    for segment in chunk.source_segments
                )
                for chunk in candidate.chunks
            ),
            coverage_ratio=covered / max(1, len(parsed.canonical_text)),
            gap_count=gaps,
            overlap_source_ratio=overlap_chars / max(1, len(parsed.canonical_text)),
            unintended_duplication_count=len(span_keys) - len(set(span_keys)),
            provenance_roundtrip_pass_count=roundtrip,
            deterministic_rerun_match=(
                candidate.manifest.chunks_checksum
                == rerun.manifest.chunks_checksum
            ),
        )
