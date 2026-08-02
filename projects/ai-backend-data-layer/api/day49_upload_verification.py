"""Day49 — verified Object Storage upload boundary (provider-neutral, FAKE adapter).

IMPORTANT EVIDENCE LABEL (three distinct claims — do not conflate them):
  * CONCEPTUAL ARTIFACT: the state machine, verification lease/fencing, version
    binding, guarded compare-and-set (CAS) transitions, and cleanup-race semantics
    described here and in the design doc.
  * STATIC / FAKE-ADAPTER VERIFICATION: what the pytest suite actually executes — the
    APPLICATION CONTROL FLOW against an IN-MEMORY fake Object Storage adapter and an
    in-memory session/document store that MODELS guarded compare-and-set transitions
    (not plain check-then-set). The completion-vs-cleanup determinism is demonstrated
    by explicit interleaving tests (a scanner double that calls ``claim_cleanup``
    mid-scan). This is control-flow evidence, NOT proof of real database transaction
    atomicity or real distributed fencing.
  * REAL RUNTIME VERIFICATION: NOT RUN here — no real PostgreSQL (FK/constraint/tx
    atomicity, ``SELECT ... FOR UPDATE``), no real Object Storage
    (presign/checksum/multipart/versioning), no real scanner, no FastAPI integration,
    no production. SQLAlchemy metadata inspection would prove declaration, not FK
    behavior; a fake adapter proves control flow, not storage semantics.

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

SCHEMA-HONESTY (round 1 + round 2): the published upload_sessions status allowlist is
initiated/uploading/verified/failed/expired and has NO 'verifying' state, NO
verification owner/lease token, NO verification_hold_until, and NO bound object
version column. The hardened model needs all of these so that (a) a slow-but-normal
scan is protected by a persistent lease cleanup can see, (b) an exact object version
is bound BEFORE scanning and used by every later step incl. cleanup deletion, and
(c) a stale finalizer cannot commit after cleanup wins. This module MODELS them
in-memory (a VERIFYING state, ``verification_owner`` fencing token,
``verification_hold_until`` deadline, and ``ExpectedContract.expected_version``). In
the REAL production schema these require a Day48-safe FORWARD migration (add the
'verifying' status + owner/hold columns via a branch revision, or a separate
verification-lease table, plus a bound-version column). That migration is NOT
implemented here and is documented as Real-Runtime scope; no published Alembic
revision is rewritten. The fake model is control-flow evidence only, and this file
does NOT claim any real PostgreSQL/Object Storage runtime verification.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Optional, Protocol


# ---------------------------------------------------------------------------
# Deterministic identity + evidence value objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ObjectReference:
    """Deterministic identity of external bytes: bucket + key + immutable version.
    ``version`` is None only before an exact version has been bound. A presigned URL
    is a CREDENTIAL, never this durable identity."""

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
    creation; ``expected_version`` is None until an exact observed version is BOUND
    (which happens BEFORE scanning, not at Document commit). Verification compares
    observed evidence against this; it MUST NEVER be overwritten to force a pass
    (frozen dataclass; binding the version creates a NEW contract)."""

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
# In-memory session/document store — models guarded CAS transitions
# ---------------------------------------------------------------------------
class SessionState(str, Enum):
    INITIATED = "initiated"
    UPLOADING = "uploading"
    VERIFYING = "verifying"  # MODELED lease state (real schema: Day48-safe forward migration)
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
    verification_owner: Optional[str] = None  # fencing token of the current verifier
    verification_hold_until: Optional[datetime] = None

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


class VersionAlreadyBoundError(Exception):
    """Models a guarded version-binding CAS: once an exact version is bound it cannot
    be rebound to a different version (concurrent binders converge on one value)."""


class VerificationClaimUnavailable(Exception):
    """A guarded verification-lease claim was refused. ``code`` is one of
    illegal_state / session_expired / held_by_other / version_conflict."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class CommitGuardFailed(Exception):
    """A guarded Document-commit CAS was refused. ``code`` is one of
    cleanup_won / lease_lost / session_expired / not_verifying."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class InMemoryStore:
    """Models the durable session/document facts and GUARDED COMPARE-AND-SET
    transitions (not plain check-then-set). A real implementation is a PostgreSQL
    short transaction with ``SELECT ... FOR UPDATE`` / a guarded UPDATE (Day47); this
    is control flow only."""

    def __init__(self) -> None:
        self.sessions: dict[uuid.UUID, UploadSessionRow] = {}
        self.documents_by_session: dict[uuid.UUID, DocumentRow] = {}

    def add_session(self, row: UploadSessionRow) -> None:
        self.sessions[row.upload_session_id] = row

    # -- guarded version binding (CAS) --
    def bind_object_version(self, upload_session_id: uuid.UUID, version: str) -> str:
        """CAS: bind an exact observed version. Unbound -> bound(version); already
        bound to the SAME version -> idempotent; already bound to a DIFFERENT version
        -> refuse (VersionAlreadyBoundError). One binding result wins under
        concurrency."""
        s = self.sessions[upload_session_id]
        current = s.expected.expected_version
        if current is None:
            s.expected = replace(s.expected, expected_version=version)
            return version
        if current != version:
            raise VersionAlreadyBoundError(f"{current} != {version}")
        return current

    # -- guarded verification lease claim (CAS) --
    def claim_verification(
        self,
        upload_session_id: uuid.UUID,
        *,
        owner_token: str,
        observed_version: str,
        now: datetime,
        hold_ttl: timedelta,
    ) -> str:
        """Guarded CAS to take/renew the verification lease and bind the exact version
        BEFORE the scanner runs. Refuses if the row is not completable, the workflow
        session has expired, a DIFFERENT owner holds a live lease, or a different
        version is already bound. Returns the owner token on success."""
        s = self.sessions[upload_session_id]
        if s.state not in COMPLETABLE_STATES:
            raise VerificationClaimUnavailable(
                "cleanup_won" if s.state == SessionState.EXPIRED else "illegal_state",
                f"state {s.state.value}",
            )
        if now >= s.session_expires_at:
            raise VerificationClaimUnavailable("session_expired")
        if (
            s.state == SessionState.VERIFYING
            and s.verification_owner not in (None, owner_token)
            and s.verification_hold_until is not None
            and now < s.verification_hold_until
        ):
            raise VerificationClaimUnavailable("held_by_other")
        # Bind version CAS (unbound -> observed; bound must match).
        if s.expected.expected_version is None:
            s.expected = replace(s.expected, expected_version=observed_version)
        elif s.expected.expected_version != observed_version:
            raise VerificationClaimUnavailable("version_conflict")
        s.state = SessionState.VERIFYING
        s.verification_owner = owner_token
        s.verification_hold_until = now + hold_ttl
        return owner_token

    def renew_verification_hold(
        self, upload_session_id: uuid.UUID, *, owner_token: str, now: datetime, hold_ttl: timedelta
    ) -> None:
        """Guarded renewal used on a transient scanner outage: extend the hold only if
        we still own a VERIFYING lease and the session has not hard-expired."""
        s = self.sessions[upload_session_id]
        if s.state != SessionState.VERIFYING or s.verification_owner != owner_token:
            raise CommitGuardFailed("lease_lost")
        if now >= s.session_expires_at:
            raise CommitGuardFailed("session_expired")
        s.verification_hold_until = now + hold_ttl

    def fail_verification_if_owner(
        self, upload_session_id: uuid.UUID, *, owner_token: str
    ) -> None:
        """Guarded transition to FAILED (unsafe content) only if we still own the lease."""
        s = self.sessions[upload_session_id]
        if s.state != SessionState.VERIFYING or s.verification_owner != owner_token:
            raise CommitGuardFailed("lease_lost")
        s.state = SessionState.FAILED
        s.verification_owner = None
        s.verification_hold_until = None

    # -- guarded atomic Document commit (CAS) --
    def commit_document_if_owner(
        self,
        upload_session_id: uuid.UUID,
        observed: StoredObjectEvidence,
        *,
        owner_token: str,
        now: datetime,
        fail_before_commit: bool = False,
    ) -> DocumentRow:
        """ATOMIC (modeled) guarded commit. Re-reads the row and refuses UNLESS it is
        still VERIFYING, still owned by ``owner_token``, and the workflow session has
        not expired. Crucially: if cleanup already won (state EXPIRED) this refuses and
        NEVER flips EXPIRED back to VERIFIED; if another worker re-claimed the lease
        (owner changed) it refuses (lease_lost). On success it creates exactly one
        Document AND flips to VERIFIED together (all-or-nothing; a failure before the
        commit block leaves NEITHER fact). Models transactional atomicity + fencing;
        NOT proof of real PostgreSQL behavior."""
        s = self.sessions[upload_session_id]
        if s.state == SessionState.EXPIRED:
            raise CommitGuardFailed("cleanup_won", "cleanup already claimed the row")
        if s.state != SessionState.VERIFYING:
            raise CommitGuardFailed("not_verifying", f"state {s.state.value}")
        if s.verification_owner != owner_token:
            raise CommitGuardFailed("lease_lost", "verification lease no longer ours")
        if now >= s.session_expires_at:
            raise CommitGuardFailed("session_expired")
        if upload_session_id in self.documents_by_session:
            raise DuplicateDocumentError(str(upload_session_id))
        # Provenance is structural here: the Document's tenant is copied from the
        # parent session row, so the composite FK (tenant_id, upload_session_id) can
        # never be violated by this path. ``assert_document_provenance`` models a
        # buggy caller trying to attach a cross-tenant Document.
        doc = DocumentRow(
            document_id=uuid.uuid4(),
            tenant_id=s.tenant_id,
            upload_session_id=upload_session_id,
            reference=ObjectReference(observed.bucket, observed.key, observed.version),
            size=observed.size,
            checksum_sha256=observed.checksum_sha256 or "",
            content_type=s.expected.expected_content_type,
        )
        if fail_before_commit:
            raise SimulatedCommitFailure("injected mid-transaction failure before commit")
        # --- single logical commit: both facts applied together ---
        self.documents_by_session[upload_session_id] = doc
        s.state = SessionState.VERIFIED
        s.verification_owner = None
        s.verification_hold_until = None
        s.expected = replace(s.expected, expected_version=observed.version)
        return doc


    def assert_document_provenance(
        self, upload_session_id: uuid.UUID, claimed_tenant_id: uuid.UUID
    ) -> None:
        """Models the composite FK (tenant_id, upload_session_id): a Document may only
        claim the SAME tenant as its parent Upload Session. Raises ProvenanceError on a
        cross-tenant attempt."""
        parent = self.sessions.get(upload_session_id)
        if parent is None or parent.tenant_id != claimed_tenant_id:
            raise ProvenanceError("tenant/session provenance does not match parent")


# ---------------------------------------------------------------------------
# Idempotent input finalization (Document) — lease-fenced + version-bound
# ---------------------------------------------------------------------------
class FinalizeOutcome(str, Enum):
    CREATED = "created"
    ALREADY_VERIFIED = "already_verified"  # idempotent retry
    ILLEGAL_STATE = "illegal_state"  # not UPLOADING/VERIFYING (e.g. INITIATED/FAILED)
    SESSION_EXPIRED = "session_expired"  # workflow session expiry re-checked
    UPLOAD_WINDOW_EXPIRED = "upload_window_expired"  # credential expired AND no object present
    OBJECT_NOT_FOUND = "object_not_found"  # credential still valid, object not there yet
    VERIFY_FAILED = "verify_failed"
    SCAN_FAILED = "scan_failed"
    SCAN_RETRY_LATER = "scan_retry_later"  # transient outage; lease held, hold renewed
    REJECTED_IDENTITY = "rejected_identity"  # client tried to override bucket/key/version
    CLEANUP_WON = "cleanup_won"  # cleanup claimed the row before/while we finalized
    LEASE_LOST = "lease_lost"  # another finalizer re-claimed the lease


@dataclass
class FinalizeResult:
    outcome: FinalizeOutcome
    document: Optional[DocumentRow] = None
    reason: str = ""
    owner_token: Optional[str] = None


DEFAULT_VERIFICATION_HOLD = timedelta(minutes=5)


def _resolve_clock(now: Optional[datetime], clock: Optional[Callable[[], datetime]]):
    if clock is not None:
        return clock
    if now is None:
        raise ValueError("finalize_upload requires either now= or clock=")
    return lambda: now


def finalize_upload(
    store: InMemoryStore,
    adapter: ObjectStorageAdapter,
    scanner: ScanGate,
    upload_session_id: uuid.UUID,
    *,
    now: Optional[datetime] = None,
    clock: Optional[Callable[[], datetime]] = None,
    owner_token: Optional[str] = None,
    client_supplied_bucket: Optional[str] = None,
    client_supplied_key: Optional[str] = None,
    client_supplied_version: Optional[str] = None,
    hold_ttl: timedelta = DEFAULT_VERIFICATION_HOLD,
    fail_commit: bool = False,
) -> FinalizeResult:
    """One idempotent, lease-fenced, version-bound finalization.

    Order (guarded compare-and-set at every DB step; NO DB lock held across the scan):
      1. idempotency short-circuit (already VERIFIED -> return the existing Document);
      2. legal-state guard; workflow session-expiry re-check;
      3. reject client-supplied bucket/key/version != persisted server-owned identity;
      4. inspect the EXACT server-owned reference (bound version if known, else latest)
         and verify. Credential expiry does NOT by itself invalidate an already-present
         object; a missing object maps to OBJECT_NOT_FOUND (credential still valid) or
         UPLOAD_WINDOW_EXPIRED (credential expired, nothing arrived);
      5. guarded CAS ``claim_verification``: take/renew the lease AND bind the exact
         version BEFORE scanning;
      6. scan OUTSIDE any DB lock (a slow scan is protected by the live lease). A
         transient outage renews the hold (SCAN_RETRY_LATER); unsafe -> guarded FAILED;
      7. re-read the clock, then guarded CAS ``commit_document_if_owner``: commit only
         if still VERIFYING + still our token + not session-expired + cleanup has not
         won. A stale worker or a cleanup-won row is refused; EXPIRED is never flipped
         back to VERIFIED.
    """
    tick = _resolve_clock(now, clock)
    token = owner_token or f"verifier-{uuid.uuid4()}"
    session = store.sessions[upload_session_id]

    # (1) Idempotent short-circuit.
    if session.state == SessionState.VERIFIED:
        return FinalizeResult(
            FinalizeOutcome.ALREADY_VERIFIED,
            document=store.documents_by_session.get(upload_session_id),
        )

    # (2) Legal-state guard + workflow session-expiry re-check.
    if session.state not in COMPLETABLE_STATES:
        code = FinalizeOutcome.CLEANUP_WON if session.state == SessionState.EXPIRED else FinalizeOutcome.ILLEGAL_STATE
        return FinalizeResult(code, reason=f"state {session.state.value} is not completable")
    t0 = tick()
    if t0 >= session.session_expires_at:
        # Hard workflow expiry: cleanup domain. Do not claim; a guarded cleanup will
        # decide deletion. We do not force EXPIRED here to avoid racing cleanup's claim.
        return FinalizeResult(FinalizeOutcome.SESSION_EXPIRED, reason="workflow session expired")

    # (3) Never trust client-supplied identity; the server-owned reference wins.
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

    # (4) Inspect the EXACT server-owned reference (bound version if known, else latest)
    #     OUTSIDE the DB tx. Credential expiry alone does NOT invalidate a stored object.
    observed = adapter.inspect_object(
        session.expected.expected_bucket,
        session.expected.expected_key,
        session.expected.expected_version,
    )
    if observed is None:
        if t0 >= session.credential_expires_at:
            return FinalizeResult(
                FinalizeOutcome.UPLOAD_WINDOW_EXPIRED,
                reason="credential window closed and no object was uploaded",
            )
        return FinalizeResult(FinalizeOutcome.OBJECT_NOT_FOUND, reason="object not present yet")
    verdict = verify_object(session.expected, observed)
    if verdict.status is not VerifyStatus.OK:
        return FinalizeResult(FinalizeOutcome.VERIFY_FAILED, reason=verdict.reason)

    # (5) Guarded CAS: take/renew the verification lease AND bind the exact version
    #     BEFORE scanning. No DB lock is held across the scan.
    try:
        store.claim_verification(
            upload_session_id, owner_token=token, observed_version=observed.version,
            now=t0, hold_ttl=hold_ttl,
        )
    except VerificationClaimUnavailable as exc:
        mapping = {
            "cleanup_won": FinalizeOutcome.CLEANUP_WON,
            "session_expired": FinalizeOutcome.SESSION_EXPIRED,
            "held_by_other": FinalizeOutcome.LEASE_LOST,
            "version_conflict": FinalizeOutcome.VERIFY_FAILED,
            "illegal_state": FinalizeOutcome.ILLEGAL_STATE,
        }
        return FinalizeResult(mapping.get(exc.code, FinalizeOutcome.ILLEGAL_STATE), reason=exc.code, owner_token=token)

    # (6) Scan OUTSIDE the DB lock. The live lease protects the object during a slow scan.
    try:
        scan = scanner.scan(observed)  # type: ignore[arg-type]
    except ScannerUnavailable as exc:
        try:
            store.renew_verification_hold(upload_session_id, owner_token=token, now=tick(), hold_ttl=hold_ttl)
        except CommitGuardFailed as guard:
            return FinalizeResult(_guard_to_outcome(guard.code), reason=guard.code, owner_token=token)
        return FinalizeResult(FinalizeOutcome.SCAN_RETRY_LATER, reason=str(exc) or "scanner down", owner_token=token)
    if scan is ScanVerdict.UNSAFE:
        try:
            store.fail_verification_if_owner(upload_session_id, owner_token=token)
        except CommitGuardFailed as guard:
            return FinalizeResult(_guard_to_outcome(guard.code), reason=guard.code, owner_token=token)
        return FinalizeResult(FinalizeOutcome.SCAN_FAILED, reason="unsafe content", owner_token=token)

    # (7) Re-read the clock (time may have passed during the scan) and guarded-commit.
    t1 = tick()
    try:
        doc = store.commit_document_if_owner(
            upload_session_id, observed, owner_token=token, now=t1, fail_before_commit=fail_commit,
        )
    except DuplicateDocumentError:
        return FinalizeResult(
            FinalizeOutcome.ALREADY_VERIFIED,
            document=store.documents_by_session.get(upload_session_id),
            owner_token=token,
        )
    except CommitGuardFailed as guard:
        return FinalizeResult(_guard_to_outcome(guard.code), reason=guard.code, owner_token=token)
    return FinalizeResult(FinalizeOutcome.CREATED, document=doc, owner_token=token)


def _guard_to_outcome(code: str) -> FinalizeOutcome:
    return {
        "cleanup_won": FinalizeOutcome.CLEANUP_WON,
        "lease_lost": FinalizeOutcome.LEASE_LOST,
        "session_expired": FinalizeOutcome.SESSION_EXPIRED,
        "not_verifying": FinalizeOutcome.ILLEGAL_STATE,
    }.get(code, FinalizeOutcome.ILLEGAL_STATE)


# ---------------------------------------------------------------------------
# Completion vs cleanup concurrency + timing (lease-aware, exact-version delete)
# ---------------------------------------------------------------------------
def cleanup_not_before(
    credential_expires_at: datetime,
    *,
    max_clock_skew: timedelta,
    safety_buffer: timedelta,
) -> datetime:
    """Earliest safe delete = credential expiry + bounded clock skew + safety buffer.
    (Classroom example: 12:00 + 2m skew + 1m buffer -> 12:03.) Distinct from
    session_expires_at (the whole-workflow deadline)."""
    return credential_expires_at + max_clock_skew + safety_buffer


class CleanupDecision(str, Enum):
    DELETE_ORPHAN = "delete_orphan"  # unverified + past timing gate + no live lease
    KEEP_TOO_EARLY = "keep_too_early"  # not yet past the timing gate
    KEEP_VERIFIED = "keep_verified"  # verified -> never delete
    KEEP_HAS_DOCUMENT = "keep_has_document"  # a Document exists -> never delete
    KEEP_VERIFICATION_HOLD = "keep_verification_hold"  # a live verifier lease owns the row


def classify_cleanup(
    store: InMemoryStore, upload_session_id: uuid.UUID, *, now: datetime,
    max_clock_skew: timedelta, safety_buffer: timedelta,
) -> CleanupDecision:
    """Guarded cleanup eligibility. NEVER deletes a verified/documented session, and
    NEVER deletes a session whose verification lease is still live. Only an unverified
    row past the timing gate with NO live lease is an orphan. A lease whose deadline
    passed (a dead verifier that did not renew) is reclaimable once past the timing
    gate — bounded, so a live retry loop is always protected while a dead one is not
    held forever."""
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


class CleanupClaimStatus(str, Enum):
    KEPT = "kept"  # not eligible; nothing claimed, nothing to delete
    DELETE_EXACT_VERSION = "delete_exact_version"  # claimed; delete the exact bound version
    NO_OBJECT_PRESENT = "no_object_present"  # claimed the row; storage had no object to delete


@dataclass
class CleanupClaim:
    status: CleanupClaimStatus
    decision: CleanupDecision
    reference: Optional[ObjectReference] = None  # exact-version ref iff DELETE_EXACT_VERSION


def claim_cleanup(
    store: InMemoryStore,
    adapter: ObjectStorageAdapter,
    upload_session_id: uuid.UUID,
    *,
    now: datetime,
    max_clock_skew: timedelta,
    safety_buffer: timedelta,
) -> CleanupClaim:
    """Guarded cleanup CLAIM (CAS). If the row is NOT a deletable orphan, returns KEPT
    and changes nothing. Otherwise it commits the durable EXPIRED decision FIRST (so a
    racing completion's guarded commit sees EXPIRED and refuses), THEN resolves the
    EXACT version to delete: it uses the bound version if present, otherwise inspects
    the server-owned bucket/key for the exact observed version and PERSISTS that
    binding — so the returned reference ALWAYS carries a usable exact version, never
    ``version=None``. If storage has no object, returns NO_OBJECT_PRESENT (there is
    nothing to delete). The delete itself is a separate step
    (``execute_cleanup_delete``) whose result is reconciliation-honest."""
    decision = classify_cleanup(
        store, upload_session_id, now=now, max_clock_skew=max_clock_skew, safety_buffer=safety_buffer
    )
    if decision is not CleanupDecision.DELETE_ORPHAN:
        return CleanupClaim(CleanupClaimStatus.KEPT, decision)

    session = store.sessions[upload_session_id]
    # Commit the durable claim FIRST (guarded): whoever writes the terminal decision
    # first wins the completion-vs-cleanup race.
    session.state = SessionState.EXPIRED
    session.verification_owner = None
    session.verification_hold_until = None

    bound = session.expected.expected_version
    observed = adapter.inspect_object(
        session.expected.expected_bucket, session.expected.expected_key, bound
    )
    if observed is None and bound is None:
        observed = adapter.inspect_object(
            session.expected.expected_bucket, session.expected.expected_key
        )
    if observed is None:
        return CleanupClaim(CleanupClaimStatus.NO_OBJECT_PRESENT, decision)
    if bound is None:
        store.bind_object_version(upload_session_id, observed.version)  # persist exact version
    return CleanupClaim(
        CleanupClaimStatus.DELETE_EXACT_VERSION,
        decision,
        ObjectReference(observed.bucket, observed.key, observed.version),
    )


class DeleteResult(str, Enum):
    DELETED = "deleted"  # the exact version existed and was removed
    VERSION_ABSENT_RECONCILE = "version_absent_reconcile"  # exact version gone -> reconcile, not "success"
    NO_OBJECT = "no_object"  # there was nothing to delete


def execute_cleanup_delete(adapter: ObjectStorageAdapter, claim: CleanupClaim) -> DeleteResult:
    """Perform the EXACT-version delete for a claim. Never deletes ``version=None`` and
    never deletes 'the latest object'. If the exact version is already gone the result
    is VERSION_ABSENT_RECONCILE (a reconciliation signal, NOT a false success)."""
    if claim.status is CleanupClaimStatus.NO_OBJECT_PRESENT:
        return DeleteResult.NO_OBJECT
    if claim.status is not CleanupClaimStatus.DELETE_EXACT_VERSION or claim.reference is None:
        return DeleteResult.NO_OBJECT
    ref = claim.reference
    if ref.version is None:
        return DeleteResult.VERSION_ABSENT_RECONCILE  # never an ambiguous version=None delete
    ok = adapter.delete_object(ref.bucket, ref.key, ref.version)
    return DeleteResult.DELETED if ok else DeleteResult.VERSION_ABSENT_RECONCILE


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
