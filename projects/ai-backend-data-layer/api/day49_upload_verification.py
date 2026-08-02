"""Day49 — verified Object Storage upload boundary (provider-neutral, FAKE adapter).

IMPORTANT EVIDENCE LABEL: everything here runs against an IN-MEMORY FAKE object
storage adapter and an in-memory session/document store. These exercise the
APPLICATION CONTROL FLOW only — server-owned key identity, expected-vs-observed
verification, idempotent finalization, completion/cleanup concurrency, multipart
unknown-completion recovery, and output ResultArtifact recovery. They are NOT proof
of real presigned/checksum/multipart/versioning semantics, NOT PostgreSQL runtime,
NOT a real S3/Object Storage integration, and NOT production validation. No real
cloud credentials, buckets, tokens, or signed query strings appear anywhere; the
fake "grant" string is deliberately not shaped like a secret.

Boundary reused from earlier lessons (NOT re-implemented here):
  * Day47 short Unit of Work + guarded state transition (modeled in-memory).
  * Day48 rule that external side effects live OUTSIDE PostgreSQL rollback and that
    unknown outcomes are reconciled from evidence, never blindly retried.
  * Day31/Day46 schema: UploadSession 1 -> 0..1 Document via
    UNIQUE(documents.upload_session_id), with same-tenant provenance carried by the
    composite FK (tenant_id, upload_session_id). This module MODELS those invariants
    in memory; it does not redefine or migrate the schema.

Schema-honesty decision (see the design doc): the published upload_sessions status
allowlist is initiated/uploading/verified/failed/expired and has NO 'verifying'
state. This module keeps the row 'uploading' until every gate passes, so NO Alembic
change and NO edit to a published CHECK is required. Adding a 'verifying' status
would be a Day48-safe forward branch revision if operational visibility later needs
it — it is intentionally NOT done here.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Protocol


# ---------------------------------------------------------------------------
# Deterministic identity + evidence value objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ObjectReference:
    """Deterministic identity of external bytes: bucket + key + immutable version.
    A presigned URL is a CREDENTIAL, never this durable identity."""

    bucket: str
    key: str
    version: str


@dataclass(frozen=True)
class StoredObjectEvidence:
    """TRUSTED observed evidence returned by inspecting Object Storage. ``etag`` is
    provider-defined and MUST NOT be assumed to equal a SHA-256 (multipart/encryption
    change it), so a separate ``checksum_sha256`` carries the trustworthy full-object
    hash when (and only when) the provider can expose one."""

    bucket: str
    key: str
    version: str
    size: int
    etag: str
    checksum_sha256: Optional[str]


@dataclass(frozen=True)
class ExpectedContract:
    """Frozen BEFORE upload, in the Upload Session. Verification compares observed
    evidence against this; it MUST NEVER overwrite the expectation to force a pass."""

    expected_size: int
    expected_sha256: str
    expected_content_type: str


def derive_object_key(tenant_id: uuid.UUID, upload_session_id: uuid.UUID) -> str:
    """Server-owned deterministic key. The client chooses bytes + declares metadata;
    the SERVER chooses durable object identity. The original filename is untrusted
    metadata and never controls the internal storage path."""
    return f"uploads/{tenant_id}/{upload_session_id}/source"


# ---------------------------------------------------------------------------
# Least-privilege presigned grant contract (NO real credential)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PresignedGrant:
    """A least-privilege grant contract. ``fake_url`` is a non-secret placeholder for
    tests; a real signed URL is a bearer secret (TLS-only, redacted from logs, never
    stored as Artifact identity)."""

    operation: str  # exact method, e.g. "PUT" or "CREATE_MULTIPART"
    bucket: str
    key: str  # EXACT key only — never a prefix/wildcard
    expires_at: datetime
    max_size: int
    expected_sha256: str
    allowed_content_type: str
    fake_url: str = "fake-grant://placeholder/scoped-put"


def create_upload_grant(
    ref: ObjectReference,
    expected: ExpectedContract,
    *,
    now: datetime,
    ttl_seconds: int = 900,
    operation: str = "PUT",
) -> PresignedGrant:
    """Bind the credential to an EXACT operation/bucket/key/expiry/size/checksum.
    Never grants list, read-other, delete, arbitrary-key write, copy/admin, or ACL
    changes. Short TTL lowers leak/replay risk but is not immutability proof."""
    return PresignedGrant(
        operation=operation,
        bucket=ref.bucket,
        key=ref.key,
        expires_at=now + timedelta(seconds=ttl_seconds),
        max_size=expected.expected_size,
        expected_sha256=expected.expected_sha256,
        allowed_content_type=expected.expected_content_type,
    )


# ---------------------------------------------------------------------------
# Object Storage adapter seam
# ---------------------------------------------------------------------------
class ObjectStorageError(Exception):
    pass


class ObjectStorageAdapter(Protocol):
    def inspect_object(self, bucket: str, key: str) -> Optional[StoredObjectEvidence]: ...

    def delete_object(self, bucket: str, key: str, version: str) -> bool: ...


class InMemoryObjectStorage:
    """Deterministic fake for tests ONLY. Enforces create-only (no silent overwrite)
    and assigns a monotonic version per key so a re-PUT is a NEW immutable version.
    Multipart is modeled as: create -> upload parts -> complete assembles a final
    object. NOT a real Object Storage; no network, no real signing."""

    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], StoredObjectEvidence] = {}
        self._version_counter = 0
        self._multipart: dict[str, dict] = {}

    # --- single-object path ---
    def put_object(
        self, bucket: str, key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> StoredObjectEvidence:
        self._version_counter += 1
        version = f"v{self._version_counter}"
        ev = StoredObjectEvidence(
            bucket=bucket,
            key=key,
            version=version,
            size=len(data),
            etag=hashlib.md5(data).hexdigest(),  # provider ETag != SHA-256 on purpose
            checksum_sha256=hashlib.sha256(data).hexdigest(),
        )
        self._objects[(bucket, key)] = ev
        return ev

    def inspect_object(self, bucket: str, key: str) -> Optional[StoredObjectEvidence]:
        return self._objects.get((bucket, key))

    def delete_object(self, bucket: str, key: str, version: str) -> bool:
        cur = self._objects.get((bucket, key))
        if cur is not None and cur.version == version:
            del self._objects[(bucket, key)]
            return True
        return False  # version mismatch or absent -> nothing deleted (recoverable)

    # --- multipart path ---
    def create_multipart(self, bucket: str, key: str) -> str:
        upload_id = f"upl-{uuid.uuid4()}"
        self._multipart[upload_id] = {"bucket": bucket, "key": key, "parts": {}, "final": None}
        return upload_id

    def upload_part(self, upload_id: str, part_number: int, data: bytes) -> str:
        mp = self._multipart[upload_id]
        mp["parts"][part_number] = data
        return hashlib.md5(data).hexdigest()

    def complete_multipart(self, upload_id: str) -> StoredObjectEvidence:
        mp = self._multipart[upload_id]
        joined = b"".join(mp["parts"][n] for n in sorted(mp["parts"]))
        ev = self.put_object(mp["bucket"], mp["key"], joined)
        mp["final"] = ev
        return ev

    def inspect_multipart(self, upload_id: str) -> Optional[dict]:
        return self._multipart.get(upload_id)


# ---------------------------------------------------------------------------
# Expected vs observed verification (never rewrites the expectation)
# ---------------------------------------------------------------------------
class VerifyStatus(str, Enum):
    OK = "ok"
    MISMATCH = "mismatch"
    MISSING = "missing"


@dataclass(frozen=True)
class VerificationResult:
    status: VerifyStatus
    reason: str = ""


def verify_object(
    expected: ExpectedContract, observed: Optional[StoredObjectEvidence]
) -> VerificationResult:
    """Compare the FROZEN expected contract with TRUSTED observed evidence. Returns a
    NEW result; it never mutates ``expected``. A missing full-object SHA-256 is a hard
    failure (we do NOT fall back to ETag as a SHA-256 substitute)."""
    if observed is None:
        return VerificationResult(VerifyStatus.MISSING, "no object at reference")
    if not observed.version:
        return VerificationResult(VerifyStatus.MISMATCH, "no immutable version pinned")
    if observed.size != expected.expected_size:
        return VerificationResult(VerifyStatus.MISMATCH, "size mismatch")
    if observed.checksum_sha256 is None:
        return VerificationResult(
            VerifyStatus.MISMATCH, "provider exposed no trustworthy full-object SHA-256"
        )
    if observed.checksum_sha256 != expected.expected_sha256:
        return VerificationResult(VerifyStatus.MISMATCH, "checksum mismatch")
    return VerificationResult(VerifyStatus.OK)


# ---------------------------------------------------------------------------
# Content/security scan gate (separate from byte integrity)
# ---------------------------------------------------------------------------
class ScannerUnavailable(Exception):
    """Mandatory-gate outage -> fail CLOSED (keep waiting, create no Document)."""


class ScanVerdict(str, Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"


class ScanGate(Protocol):
    def scan(self, evidence: StoredObjectEvidence) -> ScanVerdict: ...


# ---------------------------------------------------------------------------
# In-memory session/document store — models the Day31/Day46 invariants
# ---------------------------------------------------------------------------
class SessionState(str, Enum):
    INITIATED = "initiated"
    UPLOADING = "uploading"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class UploadSessionRow:
    upload_session_id: uuid.UUID
    tenant_id: uuid.UUID
    object_key: str
    state: SessionState
    expected: ExpectedContract
    credential_expires_at: datetime


@dataclass(frozen=True)
class DocumentRow:
    document_id: uuid.UUID
    tenant_id: uuid.UUID
    upload_session_id: uuid.UUID
    reference: ObjectReference
    size: int
    checksum_sha256: str
    content_type: str


class ProvenanceError(Exception):
    """Models the composite FK (tenant_id, upload_session_id) ON DELETE RESTRICT."""


class DuplicateDocumentError(Exception):
    """Models UNIQUE(documents.upload_session_id) — at most one Document per session."""


class InMemoryStore:
    """Models the short-UoW guarded transition plus the two schema invariants. A real
    implementation is a PostgreSQL short transaction (Day47); this is control flow."""

    def __init__(self) -> None:
        self.sessions: dict[uuid.UUID, UploadSessionRow] = {}
        self.documents_by_session: dict[uuid.UUID, DocumentRow] = {}

    def add_session(self, row: UploadSessionRow) -> None:
        self.sessions[row.upload_session_id] = row

    def create_document(
        self, session: UploadSessionRow, observed: StoredObjectEvidence
    ) -> DocumentRow:
        # UNIQUE(upload_session_id): at most one Document per session.
        if session.upload_session_id in self.documents_by_session:
            raise DuplicateDocumentError(str(session.upload_session_id))
        # Composite FK provenance: the Document's tenant must match the parent session.
        existing = self.sessions.get(session.upload_session_id)
        if existing is None or existing.tenant_id != session.tenant_id:
            raise ProvenanceError("tenant/session provenance does not match parent")
        doc = DocumentRow(
            document_id=uuid.uuid4(),
            tenant_id=session.tenant_id,
            upload_session_id=session.upload_session_id,
            reference=ObjectReference(observed.bucket, observed.key, observed.version),
            size=observed.size,
            checksum_sha256=observed.checksum_sha256 or "",
            content_type=session.expected.expected_content_type,
        )
        self.documents_by_session[session.upload_session_id] = doc
        return doc


# ---------------------------------------------------------------------------
# Idempotent input finalization (Document)
# ---------------------------------------------------------------------------
class FinalizeOutcome(str, Enum):
    CREATED = "created"
    ALREADY_VERIFIED = "already_verified"  # idempotent retry
    VERIFY_FAILED = "verify_failed"
    SCAN_FAILED = "scan_failed"
    SCAN_RETRY_LATER = "scan_retry_later"  # fail-closed on scanner outage
    REJECTED_KEY = "rejected_key"  # client tried to override the persisted key


@dataclass
class FinalizeResult:
    outcome: FinalizeOutcome
    document: Optional[DocumentRow] = None
    reason: str = ""


def finalize_upload(
    store: InMemoryStore,
    adapter: ObjectStorageAdapter,
    scanner: ScanGate,
    upload_session_id: uuid.UUID,
    *,
    bucket: str,
    client_supplied_key: Optional[str] = None,
) -> FinalizeResult:
    """One idempotent finalization. Object Storage inspection + scanning happen
    OUTSIDE any DB transaction; then a short guarded UoW creates exactly one Document
    and marks the session verified in the same commit.

    Order: idempotency short-circuit -> reject client key override -> inspect+verify
    -> scan (fail-closed) -> guarded create-Document + verified transition."""
    session = store.sessions[upload_session_id]

    # Idempotent short-circuit: already verified -> return the existing Document.
    if session.state == SessionState.VERIFIED:
        return FinalizeResult(
            FinalizeOutcome.ALREADY_VERIFIED,
            document=store.documents_by_session.get(upload_session_id),
        )

    # The server-owned persisted key wins; a different client key is rejected.
    if client_supplied_key is not None and client_supplied_key != session.object_key:
        return FinalizeResult(FinalizeOutcome.REJECTED_KEY, reason="client key != persisted key")

    # External evidence (outside the DB tx).
    observed = adapter.inspect_object(bucket, session.object_key)
    verdict = verify_object(session.expected, observed)
    if verdict.status is not VerifyStatus.OK:
        return FinalizeResult(FinalizeOutcome.VERIFY_FAILED, reason=verdict.reason)

    # Content/security gate is SEPARATE from byte integrity, and fail-closed.
    try:
        scan = scanner.scan(observed)  # type: ignore[arg-type]
    except ScannerUnavailable as exc:
        # Fail closed: no Document, session stays 'uploading' for a bounded retry.
        return FinalizeResult(FinalizeOutcome.SCAN_RETRY_LATER, reason=str(exc) or "scanner down")
    if scan is ScanVerdict.UNSAFE:
        session.state = SessionState.FAILED
        return FinalizeResult(FinalizeOutcome.SCAN_FAILED, reason="unsafe content")

    # Short guarded UoW: create exactly one Document + flip to verified atomically.
    # DuplicateDocumentError models a lost race where another finalizer already won.
    try:
        doc = store.create_document(session, observed)  # type: ignore[arg-type]
    except DuplicateDocumentError:
        session.state = SessionState.VERIFIED
        return FinalizeResult(
            FinalizeOutcome.ALREADY_VERIFIED,
            document=store.documents_by_session.get(upload_session_id),
        )
    session.state = SessionState.VERIFIED
    return FinalizeResult(FinalizeOutcome.CREATED, document=doc)


# ---------------------------------------------------------------------------
# Completion vs cleanup concurrency + timing
# ---------------------------------------------------------------------------
def cleanup_not_before(
    credential_expires_at: datetime,
    *,
    max_clock_skew: timedelta,
    safety_buffer: timedelta,
) -> datetime:
    """Earliest safe delete = credential expiry + bounded clock skew + safety buffer.
    (Classroom example: 12:00 + 2m skew + 1m buffer -> 12:03.) 'Session expiry' must
    not precede 'credential expiry'."""
    return credential_expires_at + max_clock_skew + safety_buffer


class CleanupDecision(str, Enum):
    DELETE_ORPHAN = "delete_orphan"  # unverified + past cleanup_not_before
    KEEP_TOO_EARLY = "keep_too_early"  # not yet past the timing gate
    KEEP_VERIFIED = "keep_verified"  # verified / has a Document -> never delete
    KEEP_HAS_DOCUMENT = "keep_has_document"


def classify_cleanup(
    store: InMemoryStore, upload_session_id: uuid.UUID, *, now: datetime,
    max_clock_skew: timedelta, safety_buffer: timedelta,
) -> CleanupDecision:
    """Guarded cleanup eligibility. A verified session or one that already produced a
    Document is NEVER deleted (that would destroy a durable verified fact)."""
    session = store.sessions[upload_session_id]
    if session.state == SessionState.VERIFIED:
        return CleanupDecision.KEEP_VERIFIED
    if upload_session_id in store.documents_by_session:
        return CleanupDecision.KEEP_HAS_DOCUMENT
    not_before = cleanup_not_before(
        session.credential_expires_at, max_clock_skew=max_clock_skew, safety_buffer=safety_buffer
    )
    if now < not_before:
        return CleanupDecision.KEEP_TOO_EARLY
    return CleanupDecision.DELETE_ORPHAN


# ---------------------------------------------------------------------------
# Multipart unknown-completion recovery
# ---------------------------------------------------------------------------
class MultipartRecovery(str, Enum):
    COMPLETE_SUCCEEDED = "complete_succeeded"  # final object exists + matches
    FINAL_OBJECT_MISMATCH = "final_object_mismatch"  # exists but wrong -> quarantine
    RECOVER_FROM_PARTS = "recover_from_parts"  # no final object -> inspect upload_id/parts
    PARTS_NOT_ASSEMBLED = "parts_not_assembled"  # parts uploaded, no final object yet


def classify_multipart_completion(
    expected: ExpectedContract,
    final_object: Optional[StoredObjectEvidence],
    *,
    parts_present: bool,
) -> MultipartRecovery:
    """A timed-out CompleteMultipartUpload is an UNKNOWN external outcome. Inspect the
    deterministic FINAL object first; do not blindly start a new upload. Uploaded
    parts alone are transport progress, NOT a final object and NOT a Document."""
    if final_object is not None:
        return (
            MultipartRecovery.COMPLETE_SUCCEEDED
            if verify_object(expected, final_object).status is VerifyStatus.OK
            else MultipartRecovery.FINAL_OBJECT_MISMATCH
        )
    return (
        MultipartRecovery.RECOVER_FROM_PARTS
        if parts_present
        else MultipartRecovery.PARTS_NOT_ASSEMBLED
    )


# ---------------------------------------------------------------------------
# Output ResultArtifact publication + recovery
# ---------------------------------------------------------------------------
class ResultRecovery(str, Enum):
    COMPLETE_IDEMPOTENT_NO_PROVIDER = "complete_idempotent_no_provider"
    ALREADY_COMPLETED = "already_completed"
    PRESERVE_UNKNOWN = "preserve_unknown"  # evidence missing/inconsistent


def classify_result_recovery(
    expected: ExpectedContract,
    observed: Optional[StoredObjectEvidence],
    *,
    job_already_succeeded: bool,
) -> ResultRecovery:
    """Crash AFTER a verified output upload but BEFORE the DB completion commit: do
    NOT call the paid Provider again. Inspect the deterministic object; if it exists
    and matches, do an idempotent guarded completion. If evidence is missing or
    inconsistent, preserve the unknown/recovery state."""
    if job_already_succeeded:
        return ResultRecovery.ALREADY_COMPLETED
    if observed is not None and verify_object(expected, observed).status is VerifyStatus.OK:
        return ResultRecovery.COMPLETE_IDEMPOTENT_NO_PROVIDER
    return ResultRecovery.PRESERVE_UNKNOWN
