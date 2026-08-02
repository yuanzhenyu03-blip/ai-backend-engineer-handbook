"""Day49 — FAKE-ADAPTER tests for the verified Object Storage upload boundary.

IMPORTANT EVIDENCE LABEL: these run against an IN-MEMORY fake object storage adapter
and an in-memory session/document store. They verify APPLICATION CONTROL FLOW ONLY
(server-owned key identity, expected-vs-observed verification, idempotent
finalization, completion/cleanup concurrency, multipart unknown-completion recovery,
output ResultArtifact recovery, and the modeled schema invariants). They are NOT
proof of real presigned/checksum/multipart/versioning semantics, NOT PostgreSQL
runtime, NOT a real Object Storage integration, and NOT production validation. No
real credentials/buckets/tokens/signed URLs appear.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from day49_upload_verification import (
    CleanupDecision,
    DuplicateDocumentError,
    ExpectedContract,
    FinalizeOutcome,
    InMemoryObjectStorage,
    InMemoryStore,
    MultipartRecovery,
    ObjectReference,
    ProvenanceError,
    PresignedGrant,
    ResultRecovery,
    ScanGate,
    ScanVerdict,
    ScannerUnavailable,
    SessionState,
    StoredObjectEvidence,
    UploadSessionRow,
    VerifyStatus,
    classify_cleanup,
    classify_multipart_completion,
    classify_result_recovery,
    cleanup_not_before,
    create_upload_grant,
    derive_object_key,
    finalize_upload,
    verify_object,
)

TENANT = uuid.UUID("0f9b0e3a-6a1e-4c2b-9c1f-2b7a4d5e6f70")
OTHER_TENANT = uuid.UUID("11111111-2222-4333-8444-555555555555")
BUCKET = "ai-research-uploads"
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
DATA = b"a 2GB research file, modeled as a few bytes for a deterministic test"


class OkScanner:
    def scan(self, evidence):  # noqa: D401
        return ScanVerdict.SAFE


class UnsafeScanner:
    def scan(self, evidence):
        return ScanVerdict.UNSAFE


class DownScanner:
    def scan(self, evidence):
        raise ScannerUnavailable("scanner outage")


def _expected(data: bytes = DATA) -> ExpectedContract:
    import hashlib

    return ExpectedContract(
        expected_size=len(data),
        expected_sha256=hashlib.sha256(data).hexdigest(),
        expected_content_type="application/pdf",
    )


def _session(store, storage, *, tenant=TENANT, data=DATA, put=True):
    sid = uuid.uuid4()
    key = derive_object_key(tenant, sid)
    row = UploadSessionRow(
        upload_session_id=sid,
        tenant_id=tenant,
        object_key=key,
        state=SessionState.UPLOADING,
        expected=_expected(data),
        credential_expires_at=NOW + timedelta(minutes=15),
    )
    store.add_session(row)
    if put:
        storage.put_object(BUCKET, key, data)
    return row


# 1. The client cannot override the server-owned persisted key.
def test_client_key_cannot_override_persisted_key():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _session(store, storage)
    res = finalize_upload(
        store, storage, OkScanner(), row.upload_session_id,
        bucket=BUCKET, client_supplied_key="uploads/evil/override/source",
    )
    assert res.outcome is FinalizeOutcome.REJECTED_KEY
    assert row.upload_session_id not in store.documents_by_session  # no Document


# 2. Verification never rewrites the frozen expectation to make a mismatch pass.
def test_verification_never_rewrites_expectation():
    expected = _expected()
    observed = StoredObjectEvidence(
        bucket=BUCKET, key="k", version="v1", size=expected.expected_size + 1,
        etag="abc", checksum_sha256="deadbeef",
    )
    before = (expected.expected_size, expected.expected_sha256)
    result = verify_object(expected, observed)
    assert result.status is VerifyStatus.MISMATCH
    # The frozen contract is unchanged (frozen dataclass + no mutation).
    assert (expected.expected_size, expected.expected_sha256) == before


# 3. Exact version + size + checksum are all required.
def test_exact_version_size_checksum_required():
    expected = _expected()
    good = StoredObjectEvidence(BUCKET, "k", "v1", expected.expected_size, "etag",
                                expected.expected_sha256)
    assert verify_object(expected, good).status is VerifyStatus.OK
    no_version = StoredObjectEvidence(BUCKET, "k", "", expected.expected_size, "etag",
                                      expected.expected_sha256)
    assert verify_object(expected, no_version).status is VerifyStatus.MISMATCH
    bad_size = StoredObjectEvidence(BUCKET, "k", "v1", expected.expected_size + 9, "etag",
                                    expected.expected_sha256)
    assert verify_object(expected, bad_size).status is VerifyStatus.MISMATCH
    bad_sum = StoredObjectEvidence(BUCKET, "k", "v1", expected.expected_size, "etag", "0" * 64)
    assert verify_object(expected, bad_sum).status is VerifyStatus.MISMATCH


# 4. ETag is not accepted as a generic SHA-256 proof.
def test_etag_is_not_sha256_proof():
    expected = _expected()
    # Provider exposed NO trustworthy full-object SHA-256 (only an ETag).
    only_etag = StoredObjectEvidence(BUCKET, "k", "v1", expected.expected_size,
                                     etag=expected.expected_sha256, checksum_sha256=None)
    res = verify_object(expected, only_etag)
    assert res.status is VerifyStatus.MISMATCH
    assert "SHA-256" in res.reason  # verification refuses to treat ETag as the hash


# 5. An already-verified retry returns the same Document (idempotent).
def test_already_verified_retry_returns_same_document():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _session(store, storage)
    first = finalize_upload(store, storage, OkScanner(), row.upload_session_id, bucket=BUCKET)
    assert first.outcome is FinalizeOutcome.CREATED
    again = finalize_upload(store, storage, OkScanner(), row.upload_session_id, bucket=BUCKET)
    assert again.outcome is FinalizeOutcome.ALREADY_VERIFIED
    assert again.document is not None
    assert again.document.document_id == first.document.document_id


# 6. Concurrent/double finalization cannot create a second Document.
def test_double_finalization_creates_single_document():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _session(store, storage)
    # Simulate a lost race: a competing finalizer already inserted the Document while
    # this one was scanning, so the guarded create hits UNIQUE(upload_session_id).
    observed = storage.inspect_object(BUCKET, row.object_key)
    store.create_document(row, observed)  # competitor won
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, bucket=BUCKET)
    assert res.outcome is FinalizeOutcome.ALREADY_VERIFIED
    assert len(store.documents_by_session) == 1
    with pytest.raises(DuplicateDocumentError):
        store.create_document(row, observed)  # a second create is impossible


# 7. Scanner unavailable stays fail-closed (no Document, session still uploading).
def test_scanner_unavailable_is_fail_closed():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _session(store, storage)
    res = finalize_upload(store, storage, DownScanner(), row.upload_session_id, bucket=BUCKET)
    assert res.outcome is FinalizeOutcome.SCAN_RETRY_LATER
    assert row.state is SessionState.UPLOADING  # NOT verified, NOT failed
    assert row.upload_session_id not in store.documents_by_session


# 7b. Unsafe content fails the session (quarantine), still no Document.
def test_unsafe_content_fails_session():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _session(store, storage)
    res = finalize_upload(store, storage, UnsafeScanner(), row.upload_session_id, bucket=BUCKET)
    assert res.outcome is FinalizeOutcome.SCAN_FAILED
    assert row.state is SessionState.FAILED
    assert row.upload_session_id not in store.documents_by_session


# 8. Cleanup cannot delete objects for a verifying/verified session with a Document.
def test_cleanup_cannot_delete_verified_or_documented():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _session(store, storage)
    finalize_upload(store, storage, OkScanner(), row.upload_session_id, bucket=BUCKET)
    # Even long after credential expiry, a verified/documented session is never deleted.
    late = NOW + timedelta(hours=5)
    decision = classify_cleanup(
        store, row.upload_session_id, now=late,
        max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1),
    )
    assert decision in (CleanupDecision.KEEP_VERIFIED, CleanupDecision.KEEP_HAS_DOCUMENT)


# 8b. An unverified orphan is only deletable after the timing gate.
def test_cleanup_orphan_only_after_timing_gate():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _session(store, storage, put=False)  # never completed
    row.credential_expires_at = NOW  # credential expired at 12:00
    early = classify_cleanup(store, row.upload_session_id, now=NOW + timedelta(minutes=1),
                             max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1))
    assert early is CleanupDecision.KEEP_TOO_EARLY
    later = classify_cleanup(store, row.upload_session_id, now=NOW + timedelta(minutes=4),
                             max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1))
    assert later is CleanupDecision.DELETE_ORPHAN


# 9. cleanup_not_before = credential expiry + skew + buffer (12:00 + 2m + 1m = 12:03).
def test_cleanup_not_before_timing():
    not_before = cleanup_not_before(
        datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
        max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1),
    )
    assert not_before == datetime(2026, 8, 2, 12, 3, tzinfo=timezone.utc)


# 10. Multipart parts without final assembly cannot create a Document.
def test_multipart_parts_without_assembly_no_document():
    storage = InMemoryObjectStorage()
    upload_id = storage.create_multipart(BUCKET, "uploads/t/s/source")
    storage.upload_part(upload_id, 1, b"part-1")
    storage.upload_part(upload_id, 2, b"part-2")
    # No complete_multipart yet -> no final object exists.
    assert storage.inspect_object(BUCKET, "uploads/t/s/source") is None
    decision = classify_multipart_completion(_expected(), None, parts_present=True)
    assert decision is MultipartRecovery.RECOVER_FROM_PARTS  # not a Document


# 11. A timed-out Complete inspects the final object before any retry.
def test_timed_out_complete_inspects_final_object_first():
    storage = InMemoryObjectStorage()
    key = "uploads/t/s/source"
    upload_id = storage.create_multipart(BUCKET, key)
    storage.upload_part(upload_id, 1, DATA)
    final = storage.complete_multipart(upload_id)  # actually assembled despite timeout
    expected = _expected(DATA)
    # Recovery inspects the deterministic final object and finds Complete succeeded.
    decision = classify_multipart_completion(expected, storage.inspect_object(BUCKET, key),
                                             parts_present=True)
    assert decision is MultipartRecovery.COMPLETE_SUCCEEDED
    assert final.checksum_sha256 == expected.expected_sha256


# 12. Output object exists + DB completion failure recovers without a Provider re-call.
def test_output_recovery_without_provider_recall():
    storage = InMemoryObjectStorage()
    key = "results/t/job/attempt/result.json"
    out = b'{"result":"verified output bytes"}'
    ev = storage.put_object(BUCKET, key, out)
    expected = ExpectedContract(len(out), ev.checksum_sha256, "application/json")
    # Crash after verified upload, before DB completion -> idempotent completion, no Provider.
    decision = classify_result_recovery(expected, storage.inspect_object(BUCKET, key),
                                        job_already_succeeded=False)
    assert decision is ResultRecovery.COMPLETE_IDEMPOTENT_NO_PROVIDER
    # Missing/inconsistent evidence -> preserve unknown, still no Provider re-call.
    assert classify_result_recovery(expected, None, job_already_succeeded=False) \
        is ResultRecovery.PRESERVE_UNKNOWN
    # Already succeeded -> idempotent no-op.
    assert classify_result_recovery(expected, storage.inspect_object(BUCKET, key),
                                    job_already_succeeded=True) is ResultRecovery.ALREADY_COMPLETED


# 13. Cross-tenant Document provenance is blocked (models the composite FK).
def test_cross_tenant_provenance_blocked():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _session(store, storage, tenant=TENANT)
    observed = storage.inspect_object(BUCKET, row.object_key)
    # A Document claiming a DIFFERENT tenant than its parent session is rejected.
    wrong = UploadSessionRow(
        upload_session_id=row.upload_session_id, tenant_id=OTHER_TENANT,
        object_key=row.object_key, state=SessionState.UPLOADING,
        expected=row.expected, credential_expires_at=row.credential_expires_at,
    )
    with pytest.raises(ProvenanceError):
        store.create_document(wrong, observed)


# 14. The least-privilege grant binds an EXACT key/op/expiry and carries no real secret.
def test_presigned_grant_is_least_privilege_and_not_a_secret():
    ref = ObjectReference(BUCKET, derive_object_key(TENANT, uuid.uuid4()), version="pending")
    grant = create_upload_grant(ref, _expected(), now=NOW, ttl_seconds=900)
    assert isinstance(grant, PresignedGrant)
    assert grant.key == ref.key and grant.bucket == BUCKET  # exact key, no wildcard/prefix
    assert grant.operation == "PUT"
    assert grant.expires_at == NOW + timedelta(seconds=900)
    assert "secret" not in grant.fake_url and grant.fake_url.startswith("fake-grant://")


# 15. HONESTY: this suite is fake-adapter control flow, not PostgreSQL/Object Storage runtime.
def test_evidence_label_is_fake_runtime_only():
    import day49_upload_verification as m
    header = (m.__doc__ or "")
    assert "FAKE adapter" in header or "FAKE object storage adapter" in header
    assert "NOT PostgreSQL runtime" in header
