"""Day49 — verified Object Storage upload boundary (provider-neutral, FAKE adapter).

IMPORTANT EVIDENCE LABEL (three distinct claims — do not conflate them):
  * CONCEPTUAL ARTIFACT: the state machine, verification, hold/lease, atomic-UoW, and
    cleanup-race semantics described here and in the design doc.
  * STATIC / FAKE-ADAPTER VERIFICATION: what the pytest suite actually executes — the
    APPLICATION CONTROL FLOW against an IN-MEMORY fake Object Storage adapter and an
    in-memory session/document store. This includes a MODELED atomic Unit of Work
    (all-or-nothing over two in-memory facts) — it is control-flow evidence, not proof
    of real database transaction atomicity.
  * REAL RUNTIME VERIFICATION: NOT RUN here — no real PostgreSQL (FK/constraint/tx
    atomicity), no real Object Storage (presign/checksum/multipart/versioning), no real
    scanner, no FastAPI integration, no production. SQLAlchemy metadata inspection would
    prove declaration, not FK behavior; a fake adapter proves control flow, not storage
    semantics.

No real cloud credentials, buckets, tokens, or signed query strings appear anywhere;
the fake "grant" string is deliberately not shaped like a secret.

Boundary reused from earlier lessons (NOT re-implemented here):
  * Day47 short Unit of Work + guarded state transition (modeled in-memory).
  * Day48 rule that external side effects live OUTSIDE PostgreSQL rollback and that
    unknown outcomes are reconciled from evidence, never blindly retried.
  * Day31/Day46 schema: UploadSession 1 -> 0..1 Document via
    UNIQUE(documents.upload_session_id), with same-tenant provenance carried by the
    composite FK (tenant_id, upload_session_id). This module MODELS those invariants
    in memory; it does not redefine or migrate the schema.

SCHEMA-HONESTY (updated after review round 1): the published upload_sessions status
allowlist is initiated/uploading/verified/failed/expired and has NO 'verifying' state.
The hardened model needs a persistent "verification in progress / awaiting scan retry /
temporarily not cleanable" claim so a transient scanner outage cannot leave a session
that cleanup later deletes. This module MODELS that as a VERIFYING state plus a
``verification_hold_until`` deadline on the session row. In the REAL schema this
requires a Day48-safe FORWARD migration (add a 'verifying' status via a branch revision,
or a separate verification-hold/lease table) — that migration is NOT implemented here
and is documented as conceptual/real-runtime scope in the design doc. The fake model is
control-flow evidence only.
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
    ``version`` is None until the upload is confirmed and the exact version is bound.
    A presigned URL is a CREDENTIAL, never this durable identity."""

    bucket: str
    key: str
    version: Optional[str] = None


@dataclass(frozen=True)
class StoredObjectEvidence:
    """TRUSTED observed evidence returned by inspecting Object Storage. ``etag`` is
    provider-defined and MUST NOT be assumed to equal a SHA-256 (multipart/encryption
    change it), so a separate ``checksum_sha256`` carries the trustworthy full-object
    hash when (and only when) the provider can expose one. ``content_type`` is the
    provider-reported media type when available."""

    bucket: str
    key: str
    version: str
    size: int
    etag: str
    checksum_sha256: Optional[str]
    content_type: Optional[str] = None


@dataclass(frozen=True)
class ExpectedContract:
    """The server-owned expected object reference + integrity contract, frozen in the
    Upload Session BEFORE upload. bucket + key are chosen by the server at session
    creation; ``expected_version`` is None until the upload is confirmed and bound.
    Verification compares observed evidence against this; it MUST NEVER be overwritten
    to force a pass (frozen dataclass; binding the version creates a NEW contract)."""

    expected_bucket: str
    expected_key: str
    expected_size: int
    expected_sha256: str
    expected_content_type: str
    expected_version: Optional[str] = None


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
    expected: ExpectedContract,
    *,
    now: datetime,
    ttl_seconds: int = 900,
    operation: str = "PUT",
) -> PresignedGrant:
    """Bind the credential to an EXACT operation/bucket/key/expiry/size/checksum from
    the server-owned expected contract. Never grants list, read-other, delete,
    arbitrary-key write, copy/admin, or ACL changes. Short TTL lowers leak/replay risk
    but is not immutability proof."""
    return PresignedGrant(
        operation=operation,
        bucket=expected.expected_bucket,
        key=expected.expected_key,
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


class ObjectAlreadyExistsError(ObjectStorageError):
    """Raised by a create-only PUT when the (bucket, key) already exists — models a
    provider create-only/no-overwrite conditional write so a presigned replay cannot
    silently overwrite a verified object."""


class ObjectStorageAdapter(Protocol):
    def inspect_object(
        self, bucket: str, key: str, version: Optional[str] = None
    ) -> Optional[StoredObjectEvidence]: ...

    def delete_object(self, bucket: str, key: str, version: str) -> bool: ...


class InMemoryObjectStorage:
    """Deterministic fake for tests ONLY. Keeps a per-(bucket, key) VERSION HISTORY so
    a later write to the same key never masquerades as the original bytes: inspection
    and deletion target an EXACT version. ``put_object`` defaults to create-only (a
    second write to the same key raises) and can opt into versioning
    (``create_only=False``) to append a new immutable version. NOT a real Object
    Storage; no network, no real signing."""

    def __init__(self) -> None:
        # (bucket, key) -> ordered list of immutable versions (oldest first).
        self._versions: dict[tuple[str, str], list[StoredObjectEvidence]] = {}
        self._counter = 0
        self._multipart: dict[str, dict] = {}

    # --- single-object path ---
    def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        create_only: bool = True,
    ) -> StoredObjectEvidence:
        history = self._versions.setdefault((bucket, key), [])
        if create_only and history:
            raise ObjectAlreadyExistsError(f"{bucket}/{key} already exists (create-only)")
        self._counter += 1
        ev = StoredObjectEvidence(
            bucket=bucket,
            key=key,
            version=f"v{self._counter}",
            size=len(data),
            etag=hashlib.md5(data).hexdigest(),  # provider ETag != SHA-256 on purpose
            checksum_sha256=hashlib.sha256(data).hexdigest(),
            content_type=content_type,
        )
        history.append(ev)
        return ev

    def inspect_object(
        self, bucket: str, key: str, version: Optional[str] = None
    ) -> Optional[StoredObjectEvidence]:
        history = self._versions.get((bucket, key))
        if not history:
            return None
        if version is None:
            return history[-1]  # latest version
        for ev in history:
            if ev.version == version:
                return ev
        return None  # requested an exact version that does not exist

    def delete_object(self, bucket: str, key: str, version: str) -> bool:
        history = self._versions.get((bucket, key))
        if not history:
            return False
        for i, ev in enumerate(history):
            if ev.version == version:
                del history[i]
                if not history:
                    del self._versions[(bucket, key)]
                return True
        return False  # exact version absent -> nothing deleted (recoverable)

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
        ev = self.put_object(mp["bucket"], mp["key"], joined)  # create-only final object
        mp["final"] = ev
        return ev

    def inspect_multipart(self, upload_id: str) -> Optional[dict]:
        return self._multipart.get(upload_id)


# ---------------------------------------------------------------------------
# Expected vs observed verification (full identity + integrity; never rewrites)
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
    """Compare the FROZEN expected contract with TRUSTED observed evidence. Checks full
    server-owned identity (bucket, key, version) AND integrity (size, full-object
    SHA-256) AND content metadata when the provider exposes it. Returns a NEW result;
    it never mutates ``expected``. A missing full-object SHA-256 is a hard failure (we
    do NOT fall back to ETag as a SHA-256 substitute)."""
    if observed is None:
        return VerificationResult(VerifyStatus.MISSING, "no object at reference")
    if observed.bucket != expected.expected_bucket:
        return VerificationResult(VerifyStatus.MISMATCH, "bucket mismatch")
    if observed.key != expected.expected_key:
        return VerificationResult(VerifyStatus.MISMATCH, "key mismatch")
    if not observed.version:
        return VerificationResult(VerifyStatus.MISMATCH, "no immutable version pinned")
    if expected.expected_version is not None and observed.version != expected.expected_version:
        return VerificationResult(VerifyStatus.MISMATCH, "version mismatch")
    if observed.size != expected.expected_size:
        return VerificationResult(VerifyStatus.MISMATCH, "size mismatch")
    if observed.checksum_sha256 is None:
        return VerificationResult(
            VerifyStatus.MISMATCH, "provider exposed no trustworthy full-object SHA-256"
        )
    if observed.checksum_sha256 != expected.expected_sha256:
        return VerificationResult(VerifyStatus.MISMATCH, "checksum mismatch")
    if observed.content_type is not None and observed.content_type != expected.expected_content_type:
        return VerificationResult(VerifyStatus.MISMATCH, "content-type mismatch")
    return VerificationResult(VerifyStatus.OK)


# ---------------------------------------------------------------------------
# Content/security scan gate (separate from byte integrity)
# ---------------------------------------------------------------------------
class ScannerUnavailable(Exception):
    """Mandatory-gate TRANSIENT outage -> fail CLOSED (hold + retry, create no
    Document). A transient outage must NEVER become a permanent business failure."""


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
    VERIFYING = "verifying"  # MODELED hold state (real schema: Day48-safe forward migration)
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


# States from which a completion may legally proceed to verify + commit.
COMPLETABLE_STATES = frozenset({SessionState.UPLOADING, SessionState.VERIFYING})


@dataclass
class UploadSessionRow:
    upload_session_id: uuid.UUID
    tenant_id: uuid.UUID
    expected: ExpectedContract  # server-owned bucket+key (+ bound version) + integrity
    state: SessionState
    credential_expires_at: datetime
    session_expires_at: datetime
    verification_hold_until: Optional[datetime] = None

    # Convenience accessors so callers never re-derive identity from the client.
    @property
    def object_key(self) -> str:
        return self.expected.expected_key

    @property
    def bucket(self) -> str:
        return self.expected.expected_bucket


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


class SimulatedCommitFailure(Exception):
    """Injected in a test to prove the finalize UoW is all-or-nothing in the model."""


class InMemoryStore:
    """Models the short-UoW guarded transition plus the two schema invariants. A real
    implementation is a PostgreSQL short transaction (Day47); this is control flow."""

    def __init__(self) -> None:
        self.sessions: dict[uuid.UUID, UploadSessionRow] = {}
        self.documents_by_session: dict[uuid.UUID, DocumentRow] = {}

    def add_session(self, row: UploadSessionRow) -> None:
        self.sessions[row.upload_session_id] = row

    def finalize_document_and_verify(
        self,
        session: UploadSessionRow,
        observed: StoredObjectEvidence,
        *,
        fail_before_commit: bool = False,
    ) -> DocumentRow:
        """ATOMIC (modeled) Unit of Work: create exactly one Document AND flip the
        session to verified together, all-or-nothing. All validation and object
        construction happen BEFORE any mutation; the commit block then applies both
        facts with no intervening failure point, so an exception before commit leaves
        NEITHER fact. ``fail_before_commit`` injects a mid-transaction failure for the
        atomicity test. This models transactional atomicity; it is NOT proof of real
        PostgreSQL transaction behavior (see the module evidence label)."""
        parent = self.sessions.get(session.upload_session_id)
        # UNIQUE(upload_session_id): at most one Document per session.
        if session.upload_session_id in self.documents_by_session:
            raise DuplicateDocumentError(str(session.upload_session_id))
        # Composite FK provenance: the Document's tenant must match the parent session.
        if parent is None or parent.tenant_id != session.tenant_id:
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
        if fail_before_commit:
            # Nothing has been mutated yet -> atomic rollback (neither fact persists).
            raise SimulatedCommitFailure("injected mid-transaction failure before commit")
        # --- single logical commit: both facts applied together ---
        self.documents_by_session[session.upload_session_id] = doc
        parent.state = SessionState.VERIFIED
        parent.verification_hold_until = None
        parent.expected = replace(parent.expected, expected_version=observed.version)
        return doc


# ---------------------------------------------------------------------------
# Idempotent input finalization (Document) — state/expiry guarded
# ---------------------------------------------------------------------------
class FinalizeOutcome(str, Enum):
    CREATED = "created"
    ALREADY_VERIFIED = "already_verified"  # idempotent retry
    ILLEGAL_STATE = "illegal_state"  # not UPLOADING/VERIFYING (e.g. INITIATED/FAILED/EXPIRED)
    SESSION_EXPIRED = "session_expired"  # session/credential expiry re-checked at finalize
    VERIFY_FAILED = "verify_failed"
    SCAN_FAILED = "scan_failed"
    SCAN_RETRY_LATER = "scan_retry_later"  # fail-closed hold on scanner outage
    REJECTED_IDENTITY = "rejected_identity"  # client tried to override bucket/key/version


@dataclass
class FinalizeResult:
    outcome: FinalizeOutcome
    document: Optional[DocumentRow] = None
    reason: str = ""


DEFAULT_VERIFICATION_HOLD = timedelta(minutes=5)


def finalize_upload(
    store: InMemoryStore,
    adapter: ObjectStorageAdapter,
    scanner: ScanGate,
    upload_session_id: uuid.UUID,
    *,
    now: datetime,
    client_supplied_bucket: Optional[str] = None,
    client_supplied_key: Optional[str] = None,
    client_supplied_version: Optional[str] = None,
    hold_ttl: timedelta = DEFAULT_VERIFICATION_HOLD,
    fail_commit: bool = False,
) -> FinalizeResult:
    """One idempotent, state- and expiry-guarded finalization.

    Order:
      1. idempotency short-circuit (already VERIFIED -> return the existing Document);
      2. legal-state guard (only UPLOADING/VERIFYING may proceed; INITIATED/FAILED/
         EXPIRED and any cleanup-claimed state are rejected as ILLEGAL_STATE);
      3. expiry re-check (session or credential expired -> mark EXPIRED, SESSION_EXPIRED);
      4. reject any client-supplied bucket/key/version that differs from the persisted,
         server-owned identity (never trust the client for identity);
      5. inspect + verify the EXACT server-owned reference OUTSIDE the DB tx;
      6. scan (fail-closed: transient outage -> VERIFYING + hold deadline, retryable);
      7. ATOMIC finalize: create exactly one Document + flip to verified together.
    """
    session = store.sessions[upload_session_id]

    # (1) Idempotent short-circuit.
    if session.state == SessionState.VERIFIED:
        return FinalizeResult(
            FinalizeOutcome.ALREADY_VERIFIED,
            document=store.documents_by_session.get(upload_session_id),
        )

    # (2) Legal-state guard — reject INITIATED / FAILED / EXPIRED (and anything a
    #     cleanup worker has already claimed by transitioning to EXPIRED).
    if session.state not in COMPLETABLE_STATES:
        return FinalizeResult(
            FinalizeOutcome.ILLEGAL_STATE, reason=f"state {session.state.value} is not completable"
        )

    # (3) Re-check expiry at finalize time. A hard SESSION expiry stops completion in
    #     any state (that is the cleanup domain). CREDENTIAL expiry stops an UPLOADING
    #     session that has not started verifying (its upload window has closed); a
    #     VERIFYING session already has an uploaded object and continues (backend
    #     inspection does not use the client's presigned credential). If cleanup already
    #     owns the row it is EXPIRED and was rejected by the legal-state guard above.
    if now >= session.session_expires_at:
        session.state = SessionState.EXPIRED
        session.verification_hold_until = None
        return FinalizeResult(FinalizeOutcome.SESSION_EXPIRED, reason="session expired")
    if session.state == SessionState.UPLOADING and now >= session.credential_expires_at:
        session.state = SessionState.EXPIRED
        session.verification_hold_until = None
        return FinalizeResult(
            FinalizeOutcome.SESSION_EXPIRED, reason="upload credential expired before verification"
        )

    # (4) Never trust client-supplied identity; the server-owned reference wins.
    if client_supplied_bucket is not None and client_supplied_bucket != session.expected.expected_bucket:
        return FinalizeResult(FinalizeOutcome.REJECTED_IDENTITY, reason="client bucket != persisted")
    if client_supplied_key is not None and client_supplied_key != session.expected.expected_key:
        return FinalizeResult(FinalizeOutcome.REJECTED_IDENTITY, reason="client key != persisted")
    if (
        client_supplied_version is not None
        and session.expected.expected_version is not None
        and client_supplied_version != session.expected.expected_version
    ):
        return FinalizeResult(FinalizeOutcome.REJECTED_IDENTITY, reason="client version != bound")

    # (5) External evidence (outside the DB tx), inspected at the EXACT server-owned
    #     reference (and the bound version once known).
    observed = adapter.inspect_object(
        session.expected.expected_bucket,
        session.expected.expected_key,
        session.expected.expected_version,
    )
    verdict = verify_object(session.expected, observed)
    if verdict.status is not VerifyStatus.OK:
        return FinalizeResult(FinalizeOutcome.VERIFY_FAILED, reason=verdict.reason)

    # (6) Content/security gate is SEPARATE from byte integrity, and fail-closed.
    try:
        scan = scanner.scan(observed)  # type: ignore[arg-type]
    except ScannerUnavailable as exc:
        # Fail closed WITHOUT creating a permanent business failure: take/renew a
        # verification hold so cleanup will not delete this object while a live
        # verifier keeps retrying with bounded backoff.
        session.state = SessionState.VERIFYING
        session.verification_hold_until = now + hold_ttl
        return FinalizeResult(FinalizeOutcome.SCAN_RETRY_LATER, reason=str(exc) or "scanner down")
    if scan is ScanVerdict.UNSAFE:
        session.state = SessionState.FAILED
        session.verification_hold_until = None
        return FinalizeResult(FinalizeOutcome.SCAN_FAILED, reason="unsafe content")

    # (7) ATOMIC finalize (modeled): create Document + flip verified together.
    try:
        doc = store.finalize_document_and_verify(session, observed, fail_before_commit=fail_commit)
    except DuplicateDocumentError:
        # A concurrent finalizer already committed the Document; converge idempotently.
        session.state = SessionState.VERIFIED
        session.verification_hold_until = None
        return FinalizeResult(
            FinalizeOutcome.ALREADY_VERIFIED,
            document=store.documents_by_session.get(upload_session_id),
        )
    return FinalizeResult(FinalizeOutcome.CREATED, document=doc)


# ---------------------------------------------------------------------------
# Completion vs cleanup concurrency + timing (verification-hold aware)
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
    DELETE_ORPHAN = "delete_orphan"  # unverified + past timing gate + no live hold
    KEEP_TOO_EARLY = "keep_too_early"  # not yet past the timing gate
    KEEP_VERIFIED = "keep_verified"  # verified -> never delete
    KEEP_HAS_DOCUMENT = "keep_has_document"  # a Document exists -> never delete
    KEEP_VERIFICATION_HOLD = "keep_verification_hold"  # a live verifier owns the row


def classify_cleanup(
    store: InMemoryStore, upload_session_id: uuid.UUID, *, now: datetime,
    max_clock_skew: timedelta, safety_buffer: timedelta,
) -> CleanupDecision:
    """Guarded cleanup eligibility. NEVER deletes a verified/documented session, and
    NEVER deletes a session whose verification hold is still live (a scanner retry is
    in flight). Only an unverified row past the timing gate with NO live hold is an
    orphan. A hold whose deadline has passed (the verifier is presumed dead and did
    not renew) is reclaimable once past the timing gate — bounded, so a transient
    outage with a live retry loop is always protected while a dead one is not held
    forever."""
    session = store.sessions[upload_session_id]
    if session.state == SessionState.VERIFIED:
        return CleanupDecision.KEEP_VERIFIED
    if upload_session_id in store.documents_by_session:
        return CleanupDecision.KEEP_HAS_DOCUMENT
    if (
        session.state == SessionState.VERIFYING
        and session.verification_hold_until is not None
        and now < session.verification_hold_until
    ):
        return CleanupDecision.KEEP_VERIFICATION_HOLD
    not_before = cleanup_not_before(
        session.credential_expires_at, max_clock_skew=max_clock_skew, safety_buffer=safety_buffer
    )
    if now < not_before:
        return CleanupDecision.KEEP_TOO_EARLY
    return CleanupDecision.DELETE_ORPHAN


def claim_cleanup(
    store: InMemoryStore, upload_session_id: uuid.UUID, *, now: datetime,
    max_clock_skew: timedelta, safety_buffer: timedelta,
) -> Optional[ObjectReference]:
    """Guarded cleanup CLAIM: if (and only if) the row is a deletable orphan, commit
    the durable EXPIRED decision FIRST (so a later completion sees an illegal state and
    cannot commit), then return the exact unverified reference to delete OUTSIDE the DB
    tx. Returns None if the row must be kept. This makes the completion-vs-cleanup race
    deterministic: whoever commits its guarded DB decision first wins."""
    decision = classify_cleanup(
        store, upload_session_id, now=now, max_clock_skew=max_clock_skew, safety_buffer=safety_buffer
    )
    if decision is not CleanupDecision.DELETE_ORPHAN:
        return None
    session = store.sessions[upload_session_id]
    session.state = SessionState.EXPIRED  # durable decision committed before external delete
    session.verification_hold_until = None
    return ObjectReference(
        session.expected.expected_bucket,
        session.expected.expected_key,
        session.expected.expected_version,
    )


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
