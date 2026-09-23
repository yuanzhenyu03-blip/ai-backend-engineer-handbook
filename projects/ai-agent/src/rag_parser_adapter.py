"""Day95 controlled Parser Adapter.

The adapter is the only place where parser-private output exists.  It performs a
pure preflight, invokes a deterministic dependency-free text parser, and converts the
private result into the application-owned ``ParsedDocumentCandidate`` contract.
Parser success remains candidate evidence and never calls the Ingestion Committer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from html.parser import HTMLParser
import hashlib
import unicodedata

from rag_ingestion_contracts import (
    DocumentVersionDefinition,
    IngestionOperationIdentity,
    ParseManifest,
    ParsedDocumentCandidate,
    ParserAttemptIdentity,
    SourceArtifactReference,
    sha256_text,
)


class ParserPreflightOutcome(str, Enum):
    READY = "READY"
    BINDING_CONFLICT = "BINDING_CONFLICT"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    GENERATION_MISMATCH = "GENERATION_MISMATCH"


class ParserAdapterOutcome(str, Enum):
    CANDIDATE = "CANDIDATE"
    PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"
    SOURCE_BYTES_CHANGED = "SOURCE_BYTES_CHANGED"
    PARSER_FAILED = "PARSER_FAILED"


@dataclass(frozen=True)
class ParserCapability:
    parser_name: str
    parser_version: str
    parse_contract_version: str
    parser_generation: int
    supported_media_types: tuple[str, ...]
    maximum_input_bytes: int

    def __post_init__(self) -> None:
        required = (
            self.parser_name,
            self.parser_version,
            self.parse_contract_version,
        )
        if not all(value.strip() for value in required):
            raise ValueError("parser capability identity is required")
        if self.parser_generation < 0:
            raise ValueError("parser generation must be non-negative")
        if not self.supported_media_types:
            raise ValueError("parser must support at least one media type")
        if self.maximum_input_bytes <= 0:
            raise ValueError("parser input budget must be positive")


@dataclass(frozen=True)
class ParserPreflightDecision:
    outcome: ParserPreflightOutcome
    safe_reason: str
    parser_calls: int = 0
    committer_calls: int = 0

    @property
    def ready(self) -> bool:
        return self.outcome is ParserPreflightOutcome.READY

    def __post_init__(self) -> None:
        if self.parser_calls != 0 or self.committer_calls != 0:
            raise ValueError("parser preflight cannot parse or commit")


@dataclass(frozen=True)
class ParserAdapterResult:
    outcome: ParserAdapterOutcome
    safe_reason: str
    candidate: ParsedDocumentCandidate | None = None
    parser_calls: int = 0
    committer_calls: int = 0
    durable_transitions: int = 0

    def __post_init__(self) -> None:
        produced = self.outcome is ParserAdapterOutcome.CANDIDATE
        if produced != (self.candidate is not None):
            raise ValueError("only successful parsing carries a candidate")
        if self.committer_calls != 0 or self.durable_transitions != 0:
            raise ValueError("Parser Adapter cannot own durable authority")


@dataclass(frozen=True)
class _PrivateParserOutput:
    canonical_text: str
    sections: tuple[str, ...]
    page_count: int
    warnings: tuple[str, ...] = ()


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag.lower() in {"script", "style"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self._parts.append(data)

    def text(self) -> str:
        return "\n".join(self._parts)


class _DeterministicTextParser:
    """Parser-private dependency-free implementation for controlled classroom data."""

    def parse(self, content: bytes, media_type: str) -> _PrivateParserOutput:
        decoded = content.decode("utf-8")
        if media_type == "text/html":
            extractor = _HTMLTextExtractor()
            extractor.feed(decoded)
            decoded = extractor.text()
        elif media_type not in {"text/plain", "text/markdown"}:
            raise ValueError("private parser received unsupported media type")

        canonical = self._canonicalize(decoded)
        if not canonical:
            raise ValueError("parser produced empty canonical content")
        sections = tuple(
            section.strip()
            for section in canonical.split("\n\n")
            if section.strip()
        )
        return _PrivateParserOutput(
            canonical_text=canonical,
            sections=sections,
            page_count=1,
        )

    @staticmethod
    def _canonicalize(value: str) -> str:
        normalized = unicodedata.normalize("NFC", value)
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in normalized.split("\n")]
        return "\n".join(lines).strip()


class ControlledParserAdapter:
    """Translate controlled parser-private output into application contracts."""

    def __init__(self, capability: ParserCapability) -> None:
        self._capability = capability
        self._private_parser = _DeterministicTextParser()

    def preflight(
        self,
        *,
        operation: IngestionOperationIdentity,
        version: DocumentVersionDefinition,
        source: SourceArtifactReference,
        attempt: ParserAttemptIdentity,
    ) -> ParserPreflightDecision:
        if (
            operation.version != version.identity
            or operation.version != source.version
            or operation.source_artifact_id != version.source_artifact_id
            or operation.source_artifact_id != source.source_artifact_id
            or attempt.operation_id != operation.operation_id
            or attempt.idempotency_key != operation.idempotency_key
        ):
            return ParserPreflightDecision(
                ParserPreflightOutcome.BINDING_CONFLICT,
                "PARSER_PREFLIGHT_IDENTITY_BINDING_CONFLICT",
            )
        if (
            version.parse_contract_version
            != self._capability.parse_contract_version
        ):
            return ParserPreflightDecision(
                ParserPreflightOutcome.CONTRACT_MISMATCH,
                "DOCUMENT_VERSION_REQUIRES_A_DIFFERENT_PARSE_CONTRACT",
            )
        if source.detected_media_type not in (
            self._capability.supported_media_types
        ):
            return ParserPreflightDecision(
                ParserPreflightOutcome.UNSUPPORTED_MEDIA_TYPE,
                "PARSER_DOES_NOT_SUPPORT_DETECTED_MEDIA_TYPE",
            )
        if source.size_bytes > self._capability.maximum_input_bytes:
            return ParserPreflightDecision(
                ParserPreflightOutcome.RESOURCE_LIMIT,
                "SOURCE_EXCEEDS_PARSER_INPUT_BUDGET",
            )
        if attempt.parser_generation != self._capability.parser_generation:
            return ParserPreflightDecision(
                ParserPreflightOutcome.GENERATION_MISMATCH,
                "ATTEMPT_IS_NOT_BOUND_TO_CURRENT_PARSER_GENERATION",
            )
        return ParserPreflightDecision(
            ParserPreflightOutcome.READY,
            "PARSER_PREFLIGHT_PASSED",
        )

    def parse(
        self,
        *,
        operation: IngestionOperationIdentity,
        version: DocumentVersionDefinition,
        source: SourceArtifactReference,
        attempt: ParserAttemptIdentity,
        source_bytes: bytes,
    ) -> ParserAdapterResult:
        preflight = self.preflight(
            operation=operation,
            version=version,
            source=source,
            attempt=attempt,
        )
        if not preflight.ready:
            return ParserAdapterResult(
                ParserAdapterOutcome.PREFLIGHT_BLOCKED,
                preflight.safe_reason,
            )

        observed_checksum = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
        if (
            len(source_bytes) != source.size_bytes
            or observed_checksum != source.checksum_sha256
        ):
            return ParserAdapterResult(
                ParserAdapterOutcome.SOURCE_BYTES_CHANGED,
                "PARSER_INPUT_DOES_NOT_MATCH_ADMITTED_SOURCE_ARTIFACT",
            )

        try:
            private_output = self._private_parser.parse(
                source_bytes,
                source.detected_media_type,
            )
        except (UnicodeDecodeError, ValueError):
            return ParserAdapterResult(
                ParserAdapterOutcome.PARSER_FAILED,
                "CONTROLLED_PARSER_REJECTED_SOURCE",
                parser_calls=1,
            )

        manifest = ParseManifest(
            tenant_id=operation.tenant_id,
            document_id=operation.document_id,
            document_version_id=operation.document_version_id,
            source_artifact_id=operation.source_artifact_id,
            source_checksum_sha256=source.checksum_sha256,
            operation_id=operation.operation_id,
            idempotency_key=operation.idempotency_key,
            parser_name=self._capability.parser_name,
            parser_version=self._capability.parser_version,
            parse_contract_version=self._capability.parse_contract_version,
            attempt_number=attempt.attempt_number,
            parser_request_id=attempt.parser_request_id,
            parser_generation=attempt.parser_generation,
            output_checksum_sha256=sha256_text(private_output.canonical_text),
            page_count=private_output.page_count,
            section_count=len(private_output.sections),
            record_count=len(private_output.sections),
            warnings=private_output.warnings,
        )
        candidate = ParsedDocumentCandidate(
            manifest=manifest,
            canonical_text=private_output.canonical_text,
            sections=private_output.sections,
        )
        return ParserAdapterResult(
            ParserAdapterOutcome.CANDIDATE,
            "PARSER_RETURNED_APPLICATION_CANDIDATE",
            candidate=candidate,
            parser_calls=1,
        )
