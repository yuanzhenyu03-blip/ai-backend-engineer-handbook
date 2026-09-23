"""Day95 source admission boundary for untrusted uploaded bytes.

The boundary consumes a controlled read of the exact immutable object version that
Day49 verified.  It never treats filename, extension, or request-provided MIME as
authority.  Successful admission yields only an application-owned source reference;
the bytes remain in Object Storage and are not embedded in durable records or logs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib

from rag_ingestion_contracts import (
    DocumentVersionIdentity,
    SourceArtifactReference,
)


class SourceAdmissionOutcome(str, Enum):
    ADMITTED = "ADMITTED"
    EMPTY_SOURCE = "EMPTY_SOURCE"
    OVERSIZED_SOURCE = "OVERSIZED_SOURCE"
    SIZE_MISMATCH = "SIZE_MISMATCH"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    UNSAFE_FILENAME = "UNSAFE_FILENAME"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    MEDIA_TYPE_MISMATCH = "MEDIA_TYPE_MISMATCH"
    UNSUPPORTED_ARCHIVE = "UNSUPPORTED_ARCHIVE"
    ENCRYPTED_DOCUMENT = "ENCRYPTED_DOCUMENT"
    MALFORMED_TEXT = "MALFORMED_TEXT"


@dataclass(frozen=True)
class SourceAdmissionPolicy:
    maximum_size_bytes: int
    supported_media_types: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.maximum_size_bytes <= 0:
            raise ValueError("source size limit must be positive")
        if not self.supported_media_types:
            raise ValueError("at least one supported media type is required")
        if any(not item for item in self.supported_media_types):
            raise ValueError("supported media types must not be empty")


@dataclass(frozen=True)
class SourceUploadCandidate:
    version: DocumentVersionIdentity
    source_artifact_id: str
    original_filename: str
    declared_media_type: str
    object_bucket: str
    object_key: str
    object_version: str
    expected_size_bytes: int
    expected_checksum_sha256: str
    content: bytes

    def __post_init__(self) -> None:
        required = (
            self.source_artifact_id,
            self.original_filename,
            self.declared_media_type,
            self.object_bucket,
            self.object_key,
            self.object_version,
            self.expected_checksum_sha256,
        )
        if not all(value.strip() for value in required):
            raise ValueError("source candidate identity and evidence are required")
        if self.expected_size_bytes < 0:
            raise ValueError("expected source size must be non-negative")


@dataclass(frozen=True)
class SourceAdmissionDecision:
    outcome: SourceAdmissionOutcome
    safe_reason: str
    source_artifact: SourceArtifactReference | None = None
    detected_media_type: str | None = None
    quarantine_required: bool = False
    parser_calls: int = 0
    committer_calls: int = 0

    def __post_init__(self) -> None:
        admitted = self.outcome is SourceAdmissionOutcome.ADMITTED
        if admitted != (self.source_artifact is not None):
            raise ValueError("only an admitted source carries an artifact reference")
        if self.parser_calls != 0 or self.committer_calls != 0:
            raise ValueError("source admission cannot parse or commit")


@dataclass(frozen=True)
class _MediaDetection:
    outcome: SourceAdmissionOutcome
    safe_reason: str
    detected_media_type: str | None = None
    quarantine_required: bool = False


class SourceAdmissionGate:
    _ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")

    def __init__(self, policy: SourceAdmissionPolicy) -> None:
        self._policy = policy

    def evaluate(self, candidate: SourceUploadCandidate) -> SourceAdmissionDecision:
        if not self._safe_filename(candidate.original_filename):
            return self._blocked(
                SourceAdmissionOutcome.UNSAFE_FILENAME,
                "ORIGINAL_FILENAME_IS_UNSAFE_PRESENTATION_METADATA",
                quarantine=True,
            )

        actual_size = len(candidate.content)
        if actual_size == 0:
            return self._blocked(
                SourceAdmissionOutcome.EMPTY_SOURCE,
                "SOURCE_BYTES_ARE_EMPTY",
            )
        if actual_size > self._policy.maximum_size_bytes:
            return self._blocked(
                SourceAdmissionOutcome.OVERSIZED_SOURCE,
                "SOURCE_SIZE_EXCEEDS_CURRENT_POLICY",
                quarantine=True,
            )
        if actual_size != candidate.expected_size_bytes:
            return self._blocked(
                SourceAdmissionOutcome.SIZE_MISMATCH,
                "OBSERVED_SOURCE_SIZE_DOES_NOT_MATCH_VERIFIED_EVIDENCE",
                quarantine=True,
            )

        checksum = "sha256:" + hashlib.sha256(candidate.content).hexdigest()
        if checksum != candidate.expected_checksum_sha256:
            return self._blocked(
                SourceAdmissionOutcome.CHECKSUM_MISMATCH,
                "OBSERVED_SOURCE_CHECKSUM_DOES_NOT_MATCH_VERIFIED_EVIDENCE",
                quarantine=True,
            )

        detection = self._detect(candidate.content, candidate.declared_media_type)
        if detection.outcome is not SourceAdmissionOutcome.ADMITTED:
            return self._blocked(
                detection.outcome,
                detection.safe_reason,
                detected_media_type=detection.detected_media_type,
                quarantine=detection.quarantine_required,
            )
        assert detection.detected_media_type is not None

        if detection.detected_media_type not in self._policy.supported_media_types:
            return self._blocked(
                SourceAdmissionOutcome.UNSUPPORTED_MEDIA_TYPE,
                "DETECTED_MEDIA_TYPE_IS_NOT_IN_CURRENT_CONTRACT",
                detected_media_type=detection.detected_media_type,
            )

        source = SourceArtifactReference(
            version=candidate.version,
            source_artifact_id=candidate.source_artifact_id,
            object_bucket=candidate.object_bucket,
            object_key=candidate.object_key,
            object_version=candidate.object_version,
            checksum_sha256=checksum,
            size_bytes=actual_size,
            detected_media_type=detection.detected_media_type,
        )
        return SourceAdmissionDecision(
            SourceAdmissionOutcome.ADMITTED,
            "SOURCE_ADMISSION_PASSED",
            source_artifact=source,
            detected_media_type=detection.detected_media_type,
        )

    def _detect(
        self,
        content: bytes,
        declared_media_type: str,
    ) -> _MediaDetection:
        if content.startswith(self._ZIP_SIGNATURES):
            return _MediaDetection(
                SourceAdmissionOutcome.UNSUPPORTED_ARCHIVE,
                "ARCHIVE_CONTENT_IS_OUTSIDE_DAY95_CONTRACT",
                detected_media_type="application/zip",
                quarantine_required=True,
            )

        if content.startswith(b"%PDF-"):
            if b"/Encrypt" in content:
                return _MediaDetection(
                    SourceAdmissionOutcome.ENCRYPTED_DOCUMENT,
                    "ENCRYPTED_PDF_REQUIRES_A_SEPARATE_CONTROLLED_WORKFLOW",
                    detected_media_type="application/pdf",
                    quarantine_required=True,
                )
            if declared_media_type != "application/pdf":
                return _MediaDetection(
                    SourceAdmissionOutcome.MEDIA_TYPE_MISMATCH,
                    "DECLARED_MEDIA_TYPE_CONFLICTS_WITH_PDF_SIGNATURE",
                    detected_media_type="application/pdf",
                    quarantine_required=True,
                )
            return _MediaDetection(
                SourceAdmissionOutcome.ADMITTED,
                "PDF_SIGNATURE_CONFIRMED",
                detected_media_type="application/pdf",
            )

        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError:
            return _MediaDetection(
                SourceAdmissionOutcome.MALFORMED_TEXT,
                "CONTENT_IS_NEITHER_SUPPORTED_BINARY_NOR_VALID_UTF8",
                quarantine_required=True,
            )

        lowered = decoded.lstrip().lower()
        looks_like_html = (
            lowered.startswith("<!doctype html")
            or lowered.startswith("<html")
            or ("<body" in lowered and "</body>" in lowered)
        )
        if looks_like_html:
            detected = "text/html"
            if declared_media_type != detected:
                return _MediaDetection(
                    SourceAdmissionOutcome.MEDIA_TYPE_MISMATCH,
                    "DECLARED_MEDIA_TYPE_CONFLICTS_WITH_HTML_CONTENT",
                    detected_media_type=detected,
                    quarantine_required=True,
                )
        elif declared_media_type in {"text/plain", "text/markdown"}:
            # The UTF-8 safety probe proves text compatibility.  The declared type
            # selects one of two controlled text contracts; it is not trusted alone.
            detected = declared_media_type
        else:
            return _MediaDetection(
                SourceAdmissionOutcome.MEDIA_TYPE_MISMATCH,
                "DECLARED_MEDIA_TYPE_CONFLICTS_WITH_UTF8_TEXT_CONTENT",
                detected_media_type="text/plain",
                quarantine_required=True,
            )

        return _MediaDetection(
            SourceAdmissionOutcome.ADMITTED,
            "CONTROLLED_CONTENT_TYPE_CONFIRMED",
            detected_media_type=detected,
        )

    @staticmethod
    def _safe_filename(filename: str) -> bool:
        if filename in {".", ".."} or "\x00" in filename:
            return False
        if "/" in filename or "\\" in filename:
            return False
        return bool(filename.strip())

    @staticmethod
    def _blocked(
        outcome: SourceAdmissionOutcome,
        reason: str,
        *,
        detected_media_type: str | None = None,
        quarantine: bool = False,
    ) -> SourceAdmissionDecision:
        return SourceAdmissionDecision(
            outcome,
            reason,
            detected_media_type=detected_media_type,
            quarantine_required=quarantine,
        )
