"""Pure Day96 validation: a chunk candidate cannot create durable truth."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag_chunking_contracts import (
    ChunkSetCandidate,
    ChunkingContract,
    candidate_chunks_checksum,
)
from rag_chunking_normalization import normalize
from rag_document_lifecycle import evaluate_day96_chunking_eligibility
from rag_ingestion_committer import (
    DocumentVersionLifecycleRecord,
    IngestionOperationRecord,
)
from rag_ingestion_contracts import (
    DocumentHeadSnapshot,
    ParsedArtifactDefinition,
    SourceArtifactReference,
    sha256_text,
)
from rag_tokenizer_adapter import TokenizerPort


class ChunkValidationOutcome(str, Enum):
    READY_FOR_COMMIT = "READY_FOR_COMMIT"
    INELIGIBLE = "INELIGIBLE"
    BINDING_CONFLICT = "BINDING_CONFLICT"
    CORRELATION_CONFLICT = "CORRELATION_CONFLICT"
    MANIFEST_CONFLICT = "MANIFEST_CONFLICT"
    SOURCE_SPAN_INVALID = "SOURCE_SPAN_INVALID"
    COVERAGE_GAP = "COVERAGE_GAP"
    TOKEN_BUDGET_INVALID = "TOKEN_BUDGET_INVALID"
    OVERLAP_INVALID = "OVERLAP_INVALID"
    CONTENT_MISMATCH = "CONTENT_MISMATCH"


@dataclass(frozen=True)
class ChunkValidationDecision:
    outcome: ChunkValidationOutcome
    safe_reason: str
    candidate: ChunkSetCandidate | None = None
    committer_calls: int = 0
    durable_transitions: int = 0

    @property
    def ready(self) -> bool:
        return self.outcome is ChunkValidationOutcome.READY_FOR_COMMIT

    def __post_init__(self) -> None:
        if self.ready != (self.candidate is not None):
            raise ValueError("only a ready decision may contain a candidate")
        if self.committer_calls or self.durable_transitions:
            raise ValueError("validation has no durable write authority")


class ChunkSetCandidateValidator:
    def __init__(self, tokenizer: TokenizerPort) -> None:
        self._tokenizer = tokenizer

    def evaluate(
        self,
        *,
        document: DocumentHeadSnapshot,
        version: DocumentVersionLifecycleRecord,
        ingestion: IngestionOperationRecord,
        parsed: ParsedArtifactDefinition,
        source: SourceArtifactReference,
        contract: ChunkingContract,
        candidate: ChunkSetCandidate,
    ) -> ChunkValidationDecision:
        eligibility = evaluate_day96_chunking_eligibility(
            document=document, version=version, operation=ingestion
        )
        if not eligibility.eligible:
            return self._blocked(
                ChunkValidationOutcome.INELIGIBLE, eligibility.safe_reason
            )

        operation = candidate.operation
        if (
            parsed.version != version.definition.identity
            or source.version != parsed.version
            or source.source_artifact_id != parsed.source_artifact_id
            or source.checksum_sha256
            != parsed.manifest.source_checksum_sha256
            or parsed.source_artifact_id != version.definition.source_artifact_id
            or parsed.parsed_artifact_id != eligibility.parsed_artifact_id
            or parsed.manifest.tenant_id != parsed.version.tenant_id
            or parsed.manifest.document_id != parsed.version.document_id
            or parsed.manifest.document_version_id
            != parsed.version.document_version_id
            or parsed.manifest.source_artifact_id != parsed.source_artifact_id
            or parsed.manifest.operation_id != ingestion.identity.operation_id
            or parsed.manifest.idempotency_key
            != ingestion.identity.idempotency_key
            or parsed.manifest.parse_contract_version
            != version.definition.parse_contract_version
            or ingestion.identity.version != parsed.version
            or ingestion.identity.source_artifact_id
            != parsed.source_artifact_id
            or ingestion.attempt is None
            or parsed.manifest.attempt_number
            != ingestion.attempt.attempt_number
            or parsed.manifest.parser_request_id
            != ingestion.attempt.parser_request_id
            or parsed.manifest.parser_generation
            != ingestion.attempt.parser_generation
            or operation.version != parsed.version
            or operation.source_artifact_id != parsed.source_artifact_id
            or operation.parsed_artifact_id != parsed.parsed_artifact_id
        ):
            return self._blocked(
                ChunkValidationOutcome.BINDING_CONFLICT,
                "DAY95_PARSED_ARTIFACT_BINDING_CONFLICT",
            )
        if (
            candidate.attempt.operation_id != operation.operation_id
            or not candidate.experiment_id
        ):
            return self._blocked(
                ChunkValidationOutcome.CORRELATION_CONFLICT,
                "CHUNKING_ATTEMPT_CORRELATION_CONFLICT",
            )
        if (
            contract.tokenizer != self._tokenizer.contract
            or operation.contract_fingerprint != contract.fingerprint
        ):
            return self._blocked(
                ChunkValidationOutcome.BINDING_CONFLICT,
                "CHUNKING_CONTRACT_BINDING_CONFLICT",
            )
        if (
            parsed.output_checksum_sha256 != sha256_text(parsed.canonical_text)
            or parsed.manifest.output_checksum_sha256
            != parsed.output_checksum_sha256
            or candidate.manifest.source_checksum
            != parsed.output_checksum_sha256
            or candidate.manifest.contract_fingerprint != contract.fingerprint
            or candidate.manifest.chunk_count != len(candidate.chunks)
            or candidate.manifest.chunks_checksum
            != candidate_chunks_checksum(candidate.chunks)
        ):
            return self._blocked(
                ChunkValidationOutcome.MANIFEST_CONFLICT,
                "CHUNK_OR_PARSE_MANIFEST_CHECKSUM_MISMATCH",
            )
        if not candidate.chunks or len(candidate.chunks) > contract.max_chunk_count:
            return self._blocked(
                ChunkValidationOutcome.TOKEN_BUDGET_INVALID,
                "CHUNK_COUNT_BUDGET_INVALID",
            )
        if len(parsed.canonical_text) > contract.max_input_chars:
            return self._blocked(
                ChunkValidationOutcome.TOKEN_BUDGET_INVALID,
                "INPUT_SIZE_BUDGET_EXCEEDED",
            )

        text = parsed.canonical_text
        all_segments = []
        output_chars = 0
        previous = None
        previous_body = None
        for ordinal, chunk in enumerate(candidate.chunks):
            if chunk.ordinal != ordinal or not chunk.source_segments:
                return self._blocked(
                    ChunkValidationOutcome.SOURCE_SPAN_INVALID,
                    "CHUNK_ORDINAL_OR_SEGMENTS_INVALID",
                )
            if tuple(sorted(chunk.source_segments)) != chunk.source_segments:
                return self._blocked(
                    ChunkValidationOutcome.SOURCE_SPAN_INVALID,
                    "UNSORTED_SOURCE_SEGMENTS",
                )
            if any(
                left.end > right.start
                for left, right in zip(
                    chunk.source_segments, chunk.source_segments[1:]
                )
            ):
                return self._blocked(
                    ChunkValidationOutcome.SOURCE_SPAN_INVALID,
                    "OVERLAPPING_SEGMENTS_WITHIN_CHUNK",
                )
            if (
                chunk.source_segments[-1].role != "body"
                or sum(s.role == "body" for s in chunk.source_segments) != 1
                or chunk.joiner
                != ("\n" if len(chunk.source_segments) > 1 else "")
                or any(
                    segment.role not in {
                        "body", "heading-context", "table-header-context"
                    }
                    for segment in chunk.source_segments
                )
            ):
                return self._blocked(
                    ChunkValidationOutcome.SOURCE_SPAN_INVALID,
                    "SEGMENT_ROLE_OR_JOINER_POLICY_INVALID",
                )
            if any(segment.end > len(text) for segment in chunk.source_segments):
                return self._blocked(
                    ChunkValidationOutcome.SOURCE_SPAN_INVALID,
                    "SOURCE_SEGMENT_OUT_OF_RANGE",
                )
            body = chunk.source_segments[-1]
            if (
                (previous_body is None and body.start != 0)
                or (
                    previous_body is not None
                    and (
                        body.start > previous_body.end
                        or body.end <= previous_body.end
                    )
                )
            ):
                return self._blocked(
                    ChunkValidationOutcome.SOURCE_SPAN_INVALID,
                    "BODY_SOURCE_ORDER_OR_PROGRESS_INVALID",
                )
            for segment in chunk.source_segments[:-1]:
                source_text = text[segment.start:segment.end].lstrip()
                if (
                    segment.role == "heading-context"
                    and not source_text.startswith("#")
                ) or (
                    segment.role == "table-header-context"
                    and not source_text.startswith("|")
                ):
                    return self._blocked(
                        ChunkValidationOutcome.SOURCE_SPAN_INVALID,
                        "STRUCTURAL_CONTEXT_SOURCE_INVALID",
                    )
            reconstructed = chunk.joiner.join(
                normalize(
                    text[segment.start:segment.end],
                    contract.normalization_version,
                ).text
                for segment in chunk.source_segments
            )
            if (
                chunk.text != reconstructed
                or chunk.content_hash != sha256_text(reconstructed)
                or not chunk.text
            ):
                return self._blocked(
                    ChunkValidationOutcome.CONTENT_MISMATCH,
                    "CHUNK_TEXT_DOES_NOT_ROUNDTRIP_TO_SOURCE",
                )
            actual_tokens = self._tokenizer.count(chunk.text)
            output_chars += len(chunk.text)
            if (
                actual_tokens != chunk.token_count
                or actual_tokens > contract.hard_max_tokens
                or (
                    actual_tokens < contract.min_useful_tokens
                    and self._tokenizer.count(text) >= contract.min_useful_tokens
                )
                or output_chars > contract.max_output_chars
            ):
                return self._blocked(
                    ChunkValidationOutcome.TOKEN_BUDGET_INVALID,
                    "CHUNK_TOKEN_OR_OUTPUT_BUDGET_INVALID",
                )
            if previous is not None:
                overlap = sum(
                    self._tokenizer.count(normalize(
                        text[max(a.start, b.start):min(a.end, b.end)],
                        contract.normalization_version,
                    ).text)
                    for a in previous.source_segments
                    for b in chunk.source_segments
                    if a.role == "body" and b.role == "body"
                    if max(a.start, b.start) < min(a.end, b.end)
                )
                if (
                    overlap != previous.overlap_right_tokens
                    or overlap != chunk.overlap_left_tokens
                    or overlap > contract.overlap_tokens
                ):
                    return self._blocked(
                        ChunkValidationOutcome.OVERLAP_INVALID,
                        "SOURCE_OVERLAP_DOES_NOT_MATCH_CONTRACT",
                    )
            elif chunk.overlap_left_tokens != 0:
                return self._blocked(
                    ChunkValidationOutcome.OVERLAP_INVALID,
                    "FIRST_CHUNK_CANNOT_HAVE_LEFT_OVERLAP",
                )
            all_segments.extend(chunk.source_segments)
            previous = chunk
            previous_body = body
        if candidate.chunks[-1].overlap_right_tokens != 0:
            return self._blocked(
                ChunkValidationOutcome.OVERLAP_INVALID,
                "LAST_CHUNK_CANNOT_HAVE_RIGHT_OVERLAP",
            )
        cursor = 0
        for segment in sorted(all_segments):
            if segment.start > cursor:
                return self._blocked(
                    ChunkValidationOutcome.COVERAGE_GAP,
                    "CANONICAL_SOURCE_COVERAGE_GAP",
                )
            cursor = max(cursor, segment.end)
        if cursor != len(text):
            return self._blocked(
                ChunkValidationOutcome.COVERAGE_GAP,
                "CANONICAL_SOURCE_COVERAGE_GAP",
            )
        return ChunkValidationDecision(
            ChunkValidationOutcome.READY_FOR_COMMIT,
            "CANDIDATE_SOURCE_AND_BUDGET_VALIDATED",
            candidate,
        )

    @staticmethod
    def _blocked(
        outcome: ChunkValidationOutcome, reason: str
    ) -> ChunkValidationDecision:
        return ChunkValidationDecision(outcome, reason)
