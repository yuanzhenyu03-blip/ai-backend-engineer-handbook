"""Pure, bounded Day96 strategy Adapter producing untrusted candidates only."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable

from rag_chunking_contracts import (
    ChunkCandidate,
    ChunkManifest,
    ChunkSetCandidate,
    ChunkStrategy,
    ChunkingAttemptIdentity,
    ChunkingContract,
    ChunkingOperationIdentity,
    OversizedPolicy,
    SourceSegment,
    candidate_chunks_checksum,
)
from rag_chunking_normalization import normalize
from rag_ingestion_contracts import ParsedArtifactDefinition, sha256_text
from rag_tokenizer_adapter import TokenSpan, TokenizerPort


@dataclass(frozen=True)
class ChunkGenerationError(Exception):
    safe_reason: str

    def __str__(self) -> str:
        return self.safe_reason


class ChunkingStrategyAdapter:
    """No durable store, selection pointer, or model Provider is reachable here."""

    def __init__(
        self,
        tokenizer: TokenizerPort,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._tokenizer = tokenizer
        self._clock = clock

    def generate(
        self,
        *,
        parsed: ParsedArtifactDefinition,
        contract: ChunkingContract,
        operation: ChunkingOperationIdentity,
        attempt: ChunkingAttemptIdentity,
        experiment_id: str,
    ) -> ChunkSetCandidate:
        if not experiment_id:
            raise ChunkGenerationError("EXPERIMENT_ID_REQUIRED")
        if contract.tokenizer != self._tokenizer.contract:
            raise ChunkGenerationError("TOKENIZER_CONTRACT_MISMATCH")
        if operation.contract_fingerprint != contract.fingerprint:
            raise ChunkGenerationError("CHUNKING_CONTRACT_MISMATCH")
        if operation.parsed_artifact_id != parsed.parsed_artifact_id:
            raise ChunkGenerationError("PARSED_ARTIFACT_BINDING_MISMATCH")
        if attempt.operation_id != operation.operation_id:
            raise ChunkGenerationError("ATTEMPT_OPERATION_MISMATCH")
        canonical = parsed.canonical_text
        if not canonical or len(canonical) > contract.max_input_chars:
            raise ChunkGenerationError("INPUT_SIZE_BUDGET_EXCEEDED")
        if parsed.output_checksum_sha256 != sha256_text(canonical):
            raise ChunkGenerationError("PARSED_ARTIFACT_CHECKSUM_MISMATCH")
        normalized = normalize(canonical, contract.normalization_version)
        text = normalized.text

        started = self._clock()
        spans = self._tokenizer.spans(text)
        if not spans:
            raise ChunkGenerationError("EMPTY_PARSED_ARTIFACT")
        work_units = len(spans)
        estimated_memory_bytes = (
            len(canonical.encode("utf-8"))
            + len(text.encode("utf-8"))
            + 32 * len(spans)
        )
        if work_units > contract.max_token_work_units:
            raise ChunkGenerationError("TOKEN_WORK_BUDGET_EXCEEDED")
        if estimated_memory_bytes > contract.max_estimated_memory_bytes:
            raise ChunkGenerationError("ESTIMATED_MEMORY_BUDGET_EXCEEDED")
        chunks: list[ChunkCandidate] = []
        start = 0
        output_chars = 0
        while start < len(spans):
            if self._clock() - started > contract.deadline_seconds:
                raise ChunkGenerationError("CHUNKING_DEADLINE_EXCEEDED")
            if len(chunks) >= contract.max_chunk_count:
                raise ChunkGenerationError("MAX_CHUNK_COUNT_EXCEEDED")
            work_units += min(
                contract.hard_max_tokens, len(spans) - start
            )
            if work_units > contract.max_token_work_units:
                raise ChunkGenerationError("TOKEN_WORK_BUDGET_EXCEEDED")
            body_source_start = normalized.source_offsets[spans[start].start][0]
            context_segments = ()
            if contract.strategy is ChunkStrategy.SECTION_AWARE:
                context_segments = self._context_segments(
                    canonical, body_source_start
                )
            context_parts = [
                normalize(
                    canonical[segment.start:segment.end],
                    contract.normalization_version,
                ).text
                for segment in context_segments
            ]
            context_prefix = "\n".join(context_parts) + (
                "\n" if context_parts else ""
            )
            body_budget = contract.hard_max_tokens - self._tokenizer.count(
                context_prefix
            )
            if body_budget < max(
                contract.min_useful_tokens, contract.overlap_tokens + 1
            ):
                raise ChunkGenerationError("STRUCTURAL_CONTEXT_EXCEEDS_TOKEN_BUDGET")
            end, reason = self._choose_end(
                text, spans, start, contract, body_budget
            )
            if end <= start or end - start > contract.hard_max_tokens:
                raise ChunkGenerationError("INVALID_STRATEGY_BOUNDARY")
            normalized_start = spans[start].start
            normalized_end = spans[end - 1].end
            chunk_start, chunk_end = normalized.source_interval(
                normalized_start, normalized_end
            )
            body_content = text[normalized_start:normalized_end]
            content = context_prefix + body_content
            actual_count = self._tokenizer.count(content)
            if actual_count > contract.hard_max_tokens:
                raise ChunkGenerationError("STRUCTURAL_CONTEXT_EXCEEDS_TOKEN_BUDGET")
            output_chars += len(content)
            if output_chars > contract.max_output_chars:
                raise ChunkGenerationError("OUTPUT_SIZE_BUDGET_EXCEEDED")
            if (
                estimated_memory_bytes + 4 * output_chars
                > contract.max_estimated_memory_bytes
            ):
                raise ChunkGenerationError("ESTIMATED_MEMORY_BUDGET_EXCEEDED")
            if (
                end - start < contract.min_useful_tokens
                and len(spans) >= contract.min_useful_tokens
            ):
                raise ChunkGenerationError("MINIMUM_USEFUL_SIZE_NOT_MET")
            next_start = max(0, end - contract.overlap_tokens)
            if end < len(spans) and next_start <= start:
                raise ChunkGenerationError("NON_ADVANCING_OVERLAP")
            chunk = ChunkCandidate(
                ordinal=len(chunks),
                text=content,
                source_segments=(
                    context_segments + (SourceSegment(chunk_start, chunk_end),)
                ),
                token_count=actual_count,
                content_hash=sha256_text(content),
                boundary_reason=reason,
                overlap_left_tokens=(
                    contract.overlap_tokens if start > 0 else 0
                ),
                overlap_right_tokens=(
                    contract.overlap_tokens if end < len(spans) else 0
                ),
                joiner="\n" if context_segments else "",
            )
            chunks.append(chunk)
            if end == len(spans):
                break
            start = next_start

        immutable_chunks = tuple(chunks)
        manifest = ChunkManifest(
            chunk_count=len(immutable_chunks),
            source_checksum=parsed.output_checksum_sha256,
            contract_fingerprint=contract.fingerprint,
            chunks_checksum=candidate_chunks_checksum(immutable_chunks),
        )
        return ChunkSetCandidate(
            operation=operation,
            attempt=attempt,
            experiment_id=experiment_id,
            chunks=immutable_chunks,
            manifest=manifest,
        )

    def _choose_end(
        self,
        text: str,
        spans: tuple[TokenSpan, ...],
        start: int,
        contract: ChunkingContract,
        body_budget: int,
    ) -> tuple[int, str]:
        total = len(spans)
        if total - start <= body_budget:
            return total, "SOURCE_END"
        limit = min(start + body_budget, total)
        target = min(start + contract.soft_target_tokens, limit)
        if contract.strategy is ChunkStrategy.FIXED_TOKEN:
            return target, "FIXED_TOKEN_WINDOW"

        lower = start + max(contract.min_useful_tokens, contract.overlap_tokens + 1)
        priorities = (
            ("SECTION", self._is_section),
            ("PARAGRAPH", self._is_paragraph),
            ("SENTENCE", self._is_sentence),
        )
        if contract.strategy is ChunkStrategy.SECTION_AWARE:
            priorities = (
                ("SECTION", self._is_section),
                ("PARAGRAPH", self._is_paragraph),
                ("TABLE_ROW", self._is_table_row),
                ("CODE_LINE", self._is_code_line),
                ("SENTENCE", self._is_sentence),
            )
        if contract.oversized_policy is OversizedPolicy.BOUNDED_FALLBACK:
            priorities += (("WHITESPACE_FALLBACK", self._is_whitespace),)
        for reason, predicate in priorities:
            choices = [
                index
                for index in range(lower, limit + 1)
                if predicate(text, spans[index - 1].end)
            ]
            if choices:
                selected = min(
                    choices, key=lambda index: (abs(index - target), index)
                )
                return selected, reason
        if contract.oversized_policy is OversizedPolicy.FAIL_CLOSED:
            raise ChunkGenerationError("OVERSIZED_ATOMIC_UNIT")
        return limit, "HARD_TOKEN_FALLBACK"

    @staticmethod
    def _is_section(text: str, offset: int) -> bool:
        return text[offset:offset + 1] == "#" and (
            offset == 0 or text[offset - 1] == "\n"
        )

    @staticmethod
    def _is_paragraph(text: str, offset: int) -> bool:
        return text[max(0, offset - 2):offset] == "\n\n"

    @staticmethod
    def _is_sentence(text: str, offset: int) -> bool:
        prefix = text[:offset].rstrip()
        return bool(prefix) and prefix[-1] in ".!?。！？"

    @staticmethod
    def _is_whitespace(text: str, offset: int) -> bool:
        return offset > 0 and text[offset - 1].isspace()

    @staticmethod
    def _is_table_row(text: str, offset: int) -> bool:
        return (
            offset > 0
            and text[offset - 1] == "\n"
            and text[offset:offset + 1] == "|"
        )

    @staticmethod
    def _is_code_line(text: str, offset: int) -> bool:
        return (
            offset > 0
            and text[offset - 1] == "\n"
            and text[:offset].count("```") % 2 == 1
        )

    @staticmethod
    def _context_segments(
        canonical: str, body_start: int
    ) -> tuple[SourceSegment, ...]:
        """Repeat exact heading/table-header source, never invent one broad span."""

        heading = None
        table_header = None
        current_table = None
        offset = 0
        for line in canonical.splitlines(keepends=True):
            line_end = offset + len(line)
            visible_end = offset + len(line.rstrip("\r\n"))
            stripped = line.lstrip()
            if stripped.startswith("#") and offset <= body_start:
                heading = SourceSegment(offset, visible_end, "heading-context")
            if stripped.startswith("|"):
                if current_table is None:
                    table_header = SourceSegment(
                        offset, visible_end, "table-header-context"
                    )
                current_table = (offset, line_end)
            else:
                current_table = None
                table_header = None
            if offset <= body_start < line_end:
                break
            offset = line_end
        result = []
        if heading is not None and heading.end <= body_start:
            result.append(heading)
        if (
            current_table is not None
            and table_header is not None
            and table_header.end <= body_start
        ):
            result.append(table_header)
        return tuple(result)
