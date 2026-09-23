"""Day95 application-owned RAG ingestion contracts.

This first increment deliberately models only immutable identities, source evidence,
parser candidates, and the pure candidate-validation boundary.  It does not create a
second upload store, retry engine, reconciliation registry, or durable Committer.
Those responsibilities remain behind the existing Day49 and Day82-Day94 boundaries
and will be composed by the ingestion orchestrator in later increments.

All parser output is untrusted.  A ``ParsedDocumentCandidate`` can only become an
``IngestionActivationProposal`` after correlation, manifest, structure, and output
checksum validation.  Even that proposal is not an active document version: only a
sole Committer may persist the lifecycle transition.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib


def _require_non_empty(*values: str) -> None:
    if not all(value.strip() for value in values):
        raise ValueError("identity and contract values must not be empty")


def sha256_text(value: str) -> str:
    """Return the application-owned checksum representation for canonical text."""

    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


class DocumentHeadState(str, Enum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    TOMBSTONED = "TOMBSTONED"


class CandidateValidationOutcome(str, Enum):
    READY_FOR_COMMIT = "READY_FOR_COMMIT"
    CORRELATION_CONFLICT = "CORRELATION_CONFLICT"
    MANIFEST_BINDING_CONFLICT = "MANIFEST_BINDING_CONFLICT"
    SOURCE_CHECKSUM_CONFLICT = "SOURCE_CHECKSUM_CONFLICT"
    STRUCTURE_INVALID = "STRUCTURE_INVALID"
    OUTPUT_CHECKSUM_CONFLICT = "OUTPUT_CHECKSUM_CONFLICT"


@dataclass(frozen=True)
class DocumentIdentity:
    tenant_id: str
    document_id: str

    def __post_init__(self) -> None:
        _require_non_empty(self.tenant_id, self.document_id)


@dataclass(frozen=True)
class DocumentVersionIdentity:
    tenant_id: str
    document_id: str
    document_version_id: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.tenant_id,
            self.document_id,
            self.document_version_id,
        )

    @property
    def document(self) -> DocumentIdentity:
        return DocumentIdentity(self.tenant_id, self.document_id)


@dataclass(frozen=True)
class DocumentHeadSnapshot:
    """Current mutable document-head facts read from durable authority.

    The active pointer belongs to the logical Document, not to an immutable version.
    A snapshot is evidence for a future guarded write; it is not write authority.
    """

    identity: DocumentIdentity
    state: DocumentHeadState
    active_version_id: str | None
    state_version: int
    fence_token: int

    def __post_init__(self) -> None:
        if self.state_version < 0 or self.fence_token < 0:
            raise ValueError("document state version and fence must be non-negative")
        if self.state is DocumentHeadState.ACTIVE and not self.active_version_id:
            raise ValueError("an active document requires an active version pointer")
        if self.state is not DocumentHeadState.ACTIVE and self.active_version_id:
            raise ValueError("only an active document may carry an active pointer")


@dataclass(frozen=True)
class SourceArtifactReference:
    """Verified Day49 output adapted into the Day95 application contract.

    It stores an immutable object reference and observed evidence, never raw bytes,
    a signed URL, or credentials.  The filename is intentionally absent because it
    is untrusted presentation metadata, not source or document identity.
    """

    version: DocumentVersionIdentity
    source_artifact_id: str
    object_bucket: str
    object_key: str
    object_version: str
    checksum_sha256: str
    size_bytes: int
    detected_media_type: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.source_artifact_id,
            self.object_bucket,
            self.object_key,
            self.object_version,
            self.checksum_sha256,
            self.detected_media_type,
        )
        if self.size_bytes <= 0:
            raise ValueError("a verified source artifact must be non-empty")


@dataclass(frozen=True)
class DocumentVersionDefinition:
    """Immutable version definition; it deliberately has no ACTIVE constructor.

    Lifecycle facts are persisted separately by the Committer.  Consequently, code
    that merely creates this value cannot mark the version active.
    """

    identity: DocumentVersionIdentity
    source_artifact_id: str
    parse_contract_version: str
    created_by_operation_id: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.source_artifact_id,
            self.parse_contract_version,
            self.created_by_operation_id,
        )


@dataclass(frozen=True)
class IngestionOperationIdentity:
    tenant_id: str
    document_id: str
    document_version_id: str
    source_artifact_id: str
    operation_id: str
    idempotency_key: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.tenant_id,
            self.document_id,
            self.document_version_id,
            self.source_artifact_id,
            self.operation_id,
            self.idempotency_key,
        )

    @property
    def version(self) -> DocumentVersionIdentity:
        return DocumentVersionIdentity(
            self.tenant_id,
            self.document_id,
            self.document_version_id,
        )


@dataclass(frozen=True)
class ParserAttemptIdentity:
    operation_id: str
    idempotency_key: str
    attempt_number: int
    parser_request_id: str
    parser_generation: int

    def __post_init__(self) -> None:
        _require_non_empty(
            self.operation_id,
            self.idempotency_key,
            self.parser_request_id,
        )
        if self.attempt_number <= 0:
            raise ValueError("parser attempt number must be positive")
        if self.parser_generation < 0:
            raise ValueError("parser generation must be non-negative")


@dataclass(frozen=True)
class ParseManifest:
    tenant_id: str
    document_id: str
    document_version_id: str
    source_artifact_id: str
    source_checksum_sha256: str
    operation_id: str
    idempotency_key: str
    parser_name: str
    parser_version: str
    parse_contract_version: str
    attempt_number: int
    parser_request_id: str
    parser_generation: int
    output_checksum_sha256: str
    page_count: int
    section_count: int
    record_count: int
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(
            self.tenant_id,
            self.document_id,
            self.document_version_id,
            self.source_artifact_id,
            self.source_checksum_sha256,
            self.operation_id,
            self.idempotency_key,
            self.parser_name,
            self.parser_version,
            self.parse_contract_version,
            self.parser_request_id,
            self.output_checksum_sha256,
        )
        if self.attempt_number <= 0 or self.parser_generation < 0:
            raise ValueError("manifest attempt identity is invalid")
        if any(
            count < 0
            for count in (self.page_count, self.section_count, self.record_count)
        ):
            raise ValueError("manifest counts must be non-negative")


@dataclass(frozen=True)
class ParsedDocumentCandidate:
    """Untrusted parser proposal; construction is not acceptance."""

    manifest: ParseManifest
    canonical_text: str
    sections: tuple[str, ...]


@dataclass(frozen=True)
class ParsedArtifactDefinition:
    """Immutable parsed output definition produced only after validation."""

    parsed_artifact_id: str
    version: DocumentVersionIdentity
    source_artifact_id: str
    output_checksum_sha256: str
    canonical_text: str
    sections: tuple[str, ...]
    manifest: ParseManifest


@dataclass(frozen=True)
class IngestionActivationProposal:
    """Validated proposal; it still has no durable lifecycle authority."""

    operation: IngestionOperationIdentity
    attempt: ParserAttemptIdentity
    parsed_artifact: ParsedArtifactDefinition


@dataclass(frozen=True)
class CandidateValidationDecision:
    outcome: CandidateValidationOutcome
    safe_reason: str
    proposal: IngestionActivationProposal | None = None
    correlation_checks: int = 0
    manifest_validation_calls: int = 0
    structural_validation_calls: int = 0
    output_validation_calls: int = 0
    committer_calls: int = 0
    durable_transitions: int = 0

    def __post_init__(self) -> None:
        ready = self.outcome is CandidateValidationOutcome.READY_FOR_COMMIT
        if ready != (self.proposal is not None):
            raise ValueError("only a ready validation decision carries a proposal")
        if self.committer_calls != 0 or self.durable_transitions != 0:
            raise ValueError("candidate validation cannot own durable authority")


class ParsedCandidateValidator:
    """Pure application validation from parser candidate to transition proposal."""

    def evaluate(
        self,
        *,
        operation: IngestionOperationIdentity,
        version: DocumentVersionDefinition,
        source: SourceArtifactReference,
        attempt: ParserAttemptIdentity,
        candidate: ParsedDocumentCandidate,
    ) -> CandidateValidationDecision:
        manifest = candidate.manifest

        correlation_ok = (
            attempt.operation_id == operation.operation_id
            and attempt.idempotency_key == operation.idempotency_key
            and manifest.operation_id == attempt.operation_id
            and manifest.idempotency_key == attempt.idempotency_key
            and manifest.attempt_number == attempt.attempt_number
            and manifest.parser_request_id == attempt.parser_request_id
            and manifest.parser_generation == attempt.parser_generation
        )
        if not correlation_ok:
            return self._blocked(
                CandidateValidationOutcome.CORRELATION_CONFLICT,
                "PARSER_RESPONSE_DOES_NOT_BIND_CURRENT_ATTEMPT",
                correlation_checks=1,
            )

        expected_version = operation.version
        manifest_binding_ok = (
            version.identity == expected_version
            and source.version == expected_version
            and version.source_artifact_id == operation.source_artifact_id
            and source.source_artifact_id == operation.source_artifact_id
            and manifest.tenant_id == operation.tenant_id
            and manifest.document_id == operation.document_id
            and manifest.document_version_id == operation.document_version_id
            and manifest.source_artifact_id == operation.source_artifact_id
            and manifest.parse_contract_version == version.parse_contract_version
        )
        if not manifest_binding_ok:
            return self._blocked(
                CandidateValidationOutcome.MANIFEST_BINDING_CONFLICT,
                "PARSE_MANIFEST_DOES_NOT_BIND_EXPECTED_DOCUMENT_VERSION",
                correlation_checks=1,
                manifest_validation_calls=1,
            )

        if manifest.source_checksum_sha256 != source.checksum_sha256:
            return self._blocked(
                CandidateValidationOutcome.SOURCE_CHECKSUM_CONFLICT,
                "PARSE_MANIFEST_SOURCE_CHECKSUM_MISMATCH",
                correlation_checks=1,
                manifest_validation_calls=1,
            )

        structure_ok = (
            bool(candidate.canonical_text.strip())
            and manifest.section_count == len(candidate.sections)
            and manifest.errors == ()
        )
        if not structure_ok:
            return self._blocked(
                CandidateValidationOutcome.STRUCTURE_INVALID,
                "PARSED_CANDIDATE_STRUCTURE_REJECTED",
                correlation_checks=1,
                manifest_validation_calls=1,
                structural_validation_calls=1,
            )

        if manifest.output_checksum_sha256 != sha256_text(
            candidate.canonical_text
        ):
            return self._blocked(
                CandidateValidationOutcome.OUTPUT_CHECKSUM_CONFLICT,
                "PARSED_OUTPUT_CHECKSUM_MISMATCH",
                correlation_checks=1,
                manifest_validation_calls=1,
                structural_validation_calls=1,
                output_validation_calls=1,
            )

        artifact_material = "\x1f".join(
            (
                operation.operation_id,
                operation.document_version_id,
                manifest.output_checksum_sha256,
                manifest.parse_contract_version,
            )
        )
        parsed_artifact_id = "parsed:" + hashlib.sha256(
            artifact_material.encode("utf-8")
        ).hexdigest()
        artifact = ParsedArtifactDefinition(
            parsed_artifact_id=parsed_artifact_id,
            version=expected_version,
            source_artifact_id=operation.source_artifact_id,
            output_checksum_sha256=manifest.output_checksum_sha256,
            canonical_text=candidate.canonical_text,
            sections=candidate.sections,
            manifest=manifest,
        )
        return CandidateValidationDecision(
            CandidateValidationOutcome.READY_FOR_COMMIT,
            "CANDIDATE_VALIDATION_PASSED",
            proposal=IngestionActivationProposal(operation, attempt, artifact),
            correlation_checks=1,
            manifest_validation_calls=1,
            structural_validation_calls=1,
            output_validation_calls=1,
        )

    @staticmethod
    def _blocked(
        outcome: CandidateValidationOutcome,
        reason: str,
        *,
        correlation_checks: int,
        manifest_validation_calls: int = 0,
        structural_validation_calls: int = 0,
        output_validation_calls: int = 0,
    ) -> CandidateValidationDecision:
        return CandidateValidationDecision(
            outcome,
            reason,
            correlation_checks=correlation_checks,
            manifest_validation_calls=manifest_validation_calls,
            structural_validation_calls=structural_validation_calls,
            output_validation_calls=output_validation_calls,
        )
