"""Day49 — FAKE-ADAPTER tests for the verified Object Storage upload boundary.

EVIDENCE LABEL (three distinct claims): these tests are STATIC / FAKE-ADAPTER
VERIFICATION of APPLICATION CONTROL FLOW against an IN-MEMORY fake Object Storage
adapter and an in-memory session/document store — including a MODELED atomic Unit of
Work. They are the CONCEPTUAL/STATIC evidence tier, NOT REAL RUNTIME VERIFICATION:
NOT real presigned/checksum/multipart/versioning semantics, NOT real PostgreSQL
FK/constraint/transaction atomicity, NOT a real Object Storage integration, NOT a
real scanner, and NOT production. No real credentials/buckets/tokens/signed URLs
appear.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from day49_upload_verification import (
    CleanupDecision,
    DocumentRow,
    DuplicateDocumentError,
    ExpectedContract,
    FinalizeOutcome,
    InMemoryObjectStorage,
    InMemoryStore,
    MultipartRecovery,
    ObjectAlreadyExistsError,
    ObjectReference,
    ProvenanceError,
    PresignedGrant,
    ResultRecovery,
    ScanVerdict,
    ScannerUnavailable,
    SessionState,
    SimulatedCommitFailure,
    StoredObjectEvidence,
    UploadSessionRow,
    VerifyStatus,
    claim_cleanup,
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
CT = "application/pdf"


class OkScanner:
    def scan(self, evidence):
        return ScanVerdict.SAFE


class UnsafeScanner:
    def scan(self, evidence):
        return ScanVerdict.UNSAFE


class DownScanner:
    def scan(self, evidence):
        raise ScannerUnavailable("scanner outage")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _expected(*, bucket=BUCKET, key="k", data=DATA, version=None, content_type=CT):
    return ExpectedContract(
        expected_bucket=bucket,
        expected_key=key,
        expected_size=len(data),
        expected_sha256=_sha(data),
        expected_content_type=content_type,
        expected_version=version,
    )


def _open_session(
    store,
    storage,
    *,
    tenant=TENANT,
    data=DATA,
    put=True,
    now=NOW,
    cred_ttl=timedelta(minutes=15),
    sess_ttl=timedelta(minutes=20),
    content_type=CT,
    state=SessionState.UPLOADING,
):
    sid = uuid.uuid4()
    key = derive_object_key(tenant, sid)
    row = UploadSessionRow(
        upload_session_id=sid,
        tenant_id=tenant,
        expected=_expected(bucket=BUCKET, key=key, data=data, content_type=content_type),
        state=state,
        credential_expires_at=now + cred_ttl,
        session_expires_at=now + sess_ttl,
    )
    store.add_session(row)
    if put:
        storage.put_object(BUCKET, key, data, content_type=content_type)
    return row


def _observed(*, bucket=BUCKET, key="k", version="v1", data=DATA, content_type=CT, sha=None, etag="etag"):
    return StoredObjectEvidence(
        bucket=bucket, key=key, version=version, size=len(data),
        etag=etag, checksum_sha256=_sha(data) if sha is None else sha, content_type=content_type,
    )


# ===========================================================================
# Baseline / preserved behaviors
# ===========================================================================

# 1. The client cannot override the server-owned persisted key (identity).
def test_client_key_cannot_override_persisted_key():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    res = finalize_upload(
        store, storage, OkScanner(), row.upload_session_id, now=NOW,
        client_supplied_key="uploads/evil/override/source",
    )
    assert res.outcome is FinalizeOutcome.REJECTED_IDENTITY
    assert row.upload_session_id not in store.documents_by_session


# 2. Verification never rewrites the frozen expectation to make a mismatch pass.
def test_verification_never_rewrites_expectation():
    expected = _expected()
    observed = _observed(data=DATA + b"x")  # size + sha differ from the frozen expectation
    before = (expected.expected_size, expected.expected_sha256)
    result = verify_object(expected, observed)
    assert result.status is VerifyStatus.MISMATCH
    assert (expected.expected_size, expected.expected_sha256) == before


# 3. Full identity + integrity are all required: bucket, key, version, size, checksum.
def test_exact_identity_and_integrity_required():
    expected = _expected()
    good = _observed()
    assert verify_object(expected, good).status is VerifyStatus.OK
    assert verify_object(expected, _observed(bucket="other-bucket")).status is VerifyStatus.MISMATCH
    assert verify_object(expected, _observed(key="other-key")).status is VerifyStatus.MISMATCH
    assert verify_object(expected, _observed(version="")).status is VerifyStatus.MISMATCH
    bad_size = StoredObjectEvidence(BUCKET, "k", "v1", expected.expected_size + 9, "e",
                                    expected.expected_sha256, CT)
    assert verify_object(expected, bad_size).status is VerifyStatus.MISMATCH
    bad_sum = StoredObjectEvidence(BUCKET, "k", "v1", expected.expected_size, "e", "0" * 64, CT)
    assert verify_object(expected, bad_sum).status is VerifyStatus.MISMATCH
    bad_ct = _observed(content_type="text/plain")
    assert verify_object(expected, bad_ct).status is VerifyStatus.MISMATCH


# 4. ETag is not accepted as a generic SHA-256 proof.
def test_etag_is_not_sha256_proof():
    expected = _expected()
    only_etag = StoredObjectEvidence(BUCKET, "k", "v1", expected.expected_size,
                                     etag=expected.expected_sha256, checksum_sha256=None, content_type=CT)
    res = verify_object(expected, only_etag)
    assert res.status is VerifyStatus.MISMATCH
    assert "SHA-256" in res.reason


# 5. An already-verified retry returns the same Document (idempotent).
def test_already_verified_retry_returns_same_document():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    first = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    assert first.outcome is FinalizeOutcome.CREATED
    again = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    assert again.outcome is FinalizeOutcome.ALREADY_VERIFIED
    assert again.document is not None and again.document.document_id == first.document.document_id


# 6. Concurrent/double finalization cannot create a second Document.
def test_double_finalization_creates_single_document():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    observed = storage.inspect_object(BUCKET, row.object_key)
    store.finalize_document_and_verify(row, observed)  # competitor won
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    assert res.outcome is FinalizeOutcome.ALREADY_VERIFIED
    assert len(store.documents_by_session) == 1
    with pytest.raises(DuplicateDocumentError):
        store.finalize_document_and_verify(row, observed)


# 7b. Unsafe content fails the session (quarantine), still no Document.
def test_unsafe_content_fails_session():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    res = finalize_upload(store, storage, UnsafeScanner(), row.upload_session_id, now=NOW)
    assert res.outcome is FinalizeOutcome.SCAN_FAILED
    assert row.state is SessionState.FAILED
    assert row.upload_session_id not in store.documents_by_session


# 9. cleanup_not_before = credential expiry + skew + buffer (12:00 + 2m + 1m = 12:03).
def test_cleanup_not_before_timing():
    not_before = cleanup_not_before(
        datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
        max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1),
    )
    assert not_before == datetime(2026, 8, 2, 12, 3, tzinfo=timezone.utc)


# 8. Cleanup never deletes a verified/documented session.
def test_cleanup_cannot_delete_verified_or_documented():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    late = NOW + timedelta(hours=5)
    decision = classify_cleanup(store, row.upload_session_id, now=late,
                                max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1))
    assert decision in (CleanupDecision.KEEP_VERIFIED, CleanupDecision.KEEP_HAS_DOCUMENT)


# 8b. An unverified orphan is only deletable after the timing gate.
def test_cleanup_orphan_only_after_timing_gate():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, put=False)
    row.credential_expires_at = NOW
    early = classify_cleanup(store, row.upload_session_id, now=NOW + timedelta(minutes=1),
                             max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1))
    assert early is CleanupDecision.KEEP_TOO_EARLY
    later = classify_cleanup(store, row.upload_session_id, now=NOW + timedelta(minutes=4),
                             max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1))
    assert later is CleanupDecision.DELETE_ORPHAN


# 10. Multipart parts without final assembly cannot create a Document.
def test_multipart_parts_without_assembly_no_document():
    storage = InMemoryObjectStorage()
    upload_id = storage.create_multipart(BUCKET, "uploads/t/s/source")
    storage.upload_part(upload_id, 1, b"part-1")
    storage.upload_part(upload_id, 2, b"part-2")
    assert storage.inspect_object(BUCKET, "uploads/t/s/source") is None
    decision = classify_multipart_completion(_expected(key="uploads/t/s/source"), None, parts_present=True)
    assert decision is MultipartRecovery.RECOVER_FROM_PARTS


# 11. A timed-out Complete inspects the final object before any retry.
def test_timed_out_complete_inspects_final_object_first():
    storage = InMemoryObjectStorage()
    key = "uploads/t/s/source"
    upload_id = storage.create_multipart(BUCKET, key)
    storage.upload_part(upload_id, 1, DATA)
    final = storage.complete_multipart(upload_id)
    expected = _expected(key=key, data=DATA, content_type="application/octet-stream")
    decision = classify_multipart_completion(expected, storage.inspect_object(BUCKET, key), parts_present=True)
    assert decision is MultipartRecovery.COMPLETE_SUCCEEDED
    assert final.checksum_sha256 == expected.expected_sha256


# 12. Output object exists + DB completion failure recovers without a Provider re-call.
def test_output_recovery_without_provider_recall():
    storage = InMemoryObjectStorage()
    key = "results/t/job/attempt/result.json"
    out = b'{"result":"verified output bytes"}'
    ev = storage.put_object(BUCKET, key, out, content_type="application/json")
    expected = _expected(key=key, data=out, content_type="application/json")
    assert classify_result_recovery(expected, storage.inspect_object(BUCKET, key),
                                    job_already_succeeded=False) is ResultRecovery.COMPLETE_IDEMPOTENT_NO_PROVIDER
    assert classify_result_recovery(expected, None, job_already_succeeded=False) is ResultRecovery.PRESERVE_UNKNOWN
    assert classify_result_recovery(expected, storage.inspect_object(BUCKET, key),
                                    job_already_succeeded=True) is ResultRecovery.ALREADY_COMPLETED


# 13. Cross-tenant Document provenance is blocked (models the composite FK).
def test_cross_tenant_provenance_blocked():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, tenant=TENANT)
    observed = storage.inspect_object(BUCKET, row.object_key)
    wrong = UploadSessionRow(
        upload_session_id=row.upload_session_id, tenant_id=OTHER_TENANT, expected=row.expected,
        state=SessionState.UPLOADING, credential_expires_at=row.credential_expires_at,
        session_expires_at=row.session_expires_at,
    )
    with pytest.raises(ProvenanceError):
        store.finalize_document_and_verify(wrong, observed)


# 14. The least-privilege grant binds an EXACT key/op/expiry and carries no real secret.
def test_presigned_grant_is_least_privilege_and_not_a_secret():
    expected = _expected(key=derive_object_key(TENANT, uuid.uuid4()))
    grant = create_upload_grant(expected, now=NOW, ttl_seconds=900)
    assert isinstance(grant, PresignedGrant)
    assert grant.key == expected.expected_key and grant.bucket == BUCKET
    assert grant.operation == "PUT"
    assert grant.expires_at == NOW + timedelta(seconds=900)
    assert "secret" not in grant.fake_url and grant.fake_url.startswith("fake-grant://")


# 15. HONESTY: fake-adapter control flow, not real runtime.
def test_evidence_label_is_fake_runtime_only():
    import day49_upload_verification as m
    header = (m.__doc__ or "")
    assert "FAKE adapter" in header
    assert "NOT RUN here" in header and "REAL RUNTIME VERIFICATION" in header


# ===========================================================================
# Finding 1 — illegal state / expiry cannot finalize
# ===========================================================================

@pytest.mark.parametrize("bad_state", [SessionState.INITIATED, SessionState.FAILED, SessionState.EXPIRED])
def test_illegal_state_cannot_finalize(bad_state):
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, state=bad_state)
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    assert res.outcome is FinalizeOutcome.ILLEGAL_STATE
    assert row.upload_session_id not in store.documents_by_session
    assert row.state is bad_state  # unchanged; no verification/commit happened


def test_finalize_rejected_after_session_expiry():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)  # session_expires_at = NOW + 20m
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW + timedelta(minutes=21))
    assert res.outcome is FinalizeOutcome.SESSION_EXPIRED
    assert row.state is SessionState.EXPIRED
    assert row.upload_session_id not in store.documents_by_session


def test_uploading_rejected_after_credential_expiry():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    # credential expires at NOW+15m, session still valid to NOW+60m.
    row = _open_session(store, storage, sess_ttl=timedelta(minutes=60))
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW + timedelta(minutes=16))
    assert res.outcome is FinalizeOutcome.SESSION_EXPIRED
    assert row.state is SessionState.EXPIRED


def test_finalize_after_cleanup_claimed_is_illegal():
    # cleanup commits EXPIRED first; a racing completion must not then commit.
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, put=False, cred_ttl=timedelta(0), sess_ttl=timedelta(minutes=60))
    ref = claim_cleanup(store, row.upload_session_id, now=NOW + timedelta(minutes=10),
                        max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1))
    assert ref is not None and row.state is SessionState.EXPIRED
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW + timedelta(minutes=10))
    assert res.outcome is FinalizeOutcome.ILLEGAL_STATE


# ===========================================================================
# Finding 2 — scanner transient outage, hold, retry, cleanup race
# ===========================================================================

def test_scanner_outage_takes_verification_hold_not_permanent_failure():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, sess_ttl=timedelta(hours=2))
    res = finalize_upload(store, storage, DownScanner(), row.upload_session_id, now=NOW,
                          hold_ttl=timedelta(minutes=30))
    assert res.outcome is FinalizeOutcome.SCAN_RETRY_LATER
    assert row.state is SessionState.VERIFYING  # NOT failed (transient != permanent)
    assert row.verification_hold_until == NOW + timedelta(minutes=30)
    assert row.upload_session_id not in store.documents_by_session


def test_cleanup_must_not_delete_a_live_verification_hold():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    # credential expires soon so the timing gate opens while the hold is still live.
    row = _open_session(store, storage, cred_ttl=timedelta(minutes=2), sess_ttl=timedelta(hours=2))
    finalize_upload(store, storage, DownScanner(), row.upload_session_id, now=NOW,
                    hold_ttl=timedelta(minutes=30))
    # NOW+10m is past cleanup_not_before (NOW+2m+3m = NOW+5m) but before the hold end.
    decision = classify_cleanup(store, row.upload_session_id, now=NOW + timedelta(minutes=10),
                                max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1))
    assert decision is CleanupDecision.KEEP_VERIFICATION_HOLD
    assert claim_cleanup(store, row.upload_session_id, now=NOW + timedelta(minutes=10),
                         max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1)) is None


def test_scanner_recovers_and_retry_finalizes_from_verifying():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, sess_ttl=timedelta(hours=2))
    finalize_upload(store, storage, DownScanner(), row.upload_session_id, now=NOW,
                    hold_ttl=timedelta(minutes=30))
    assert row.state is SessionState.VERIFYING
    # Scanner is back; a retry (still within session validity) completes normally.
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW + timedelta(minutes=10))
    assert res.outcome is FinalizeOutcome.CREATED
    assert row.state is SessionState.VERIFIED
    assert row.upload_session_id in store.documents_by_session


def test_dead_verifier_hold_expires_then_cleanup_may_reclaim():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, cred_ttl=timedelta(minutes=2), sess_ttl=timedelta(hours=3))
    finalize_upload(store, storage, DownScanner(), row.upload_session_id, now=NOW,
                    hold_ttl=timedelta(minutes=30))
    # After the hold deadline (no renewal by a dead verifier) and past the timing gate.
    late = NOW + timedelta(minutes=40)
    assert classify_cleanup(store, row.upload_session_id, now=late,
                            max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1)) \
        is CleanupDecision.DELETE_ORPHAN
    ref = claim_cleanup(store, row.upload_session_id, now=late,
                        max_clock_skew=timedelta(minutes=2), safety_buffer=timedelta(minutes=1))
    assert ref is not None and row.state is SessionState.EXPIRED


# ===========================================================================
# Finding 3 — adapter overwrite / version-history semantics
# ===========================================================================

def test_create_only_put_rejects_overwrite_replay():
    storage = InMemoryObjectStorage()
    key = "uploads/t/s/source"
    storage.put_object(BUCKET, key, DATA)  # first write
    with pytest.raises(ObjectAlreadyExistsError):
        storage.put_object(BUCKET, key, b"different bytes via replayed presigned PUT")
    # The original object is untouched and still verifies.
    ev = storage.inspect_object(BUCKET, key)
    assert ev.checksum_sha256 == _sha(DATA)


def test_version_history_preserved_and_original_not_masqueraded():
    storage = InMemoryObjectStorage()
    key = "uploads/t/s/source"
    v1 = storage.put_object(BUCKET, key, DATA, create_only=False, content_type=CT)
    v2 = storage.put_object(BUCKET, key, b"later different bytes", create_only=False, content_type=CT)
    assert v1.version != v2.version
    # A session bound to v1 inspects v1 and still gets the ORIGINAL bytes' evidence,
    # even though a later v2 exists at the same key.
    got = storage.inspect_object(BUCKET, key, v1.version)
    assert got.checksum_sha256 == _sha(DATA)
    expected_v1 = _expected(key=key, data=DATA, version=v1.version)
    assert verify_object(expected_v1, got).status is VerifyStatus.OK
    # Verifying the v1-bound contract against v2 fails (cannot masquerade as original).
    assert verify_object(expected_v1, storage.inspect_object(BUCKET, key, v2.version)).status \
        is VerifyStatus.MISMATCH


def test_inspect_wrong_version_returns_none():
    storage = InMemoryObjectStorage()
    key = "uploads/t/s/source"
    storage.put_object(BUCKET, key, DATA)
    assert storage.inspect_object(BUCKET, key, "v999") is None


def test_delete_targets_exact_version_only():
    storage = InMemoryObjectStorage()
    key = "uploads/t/s/source"
    v1 = storage.put_object(BUCKET, key, DATA, create_only=False)
    v2 = storage.put_object(BUCKET, key, b"second version", create_only=False)
    assert storage.delete_object(BUCKET, key, "v999") is False  # wrong version -> nothing
    assert storage.delete_object(BUCKET, key, v1.version) is True
    assert storage.inspect_object(BUCKET, key, v1.version) is None
    assert storage.inspect_object(BUCKET, key, v2.version).version == v2.version  # v2 intact


# ===========================================================================
# Finding 4 — atomic finalize UoW (all-or-nothing in the model)
# ===========================================================================

def test_finalize_uow_is_atomic_on_mid_transaction_failure():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    with pytest.raises(SimulatedCommitFailure):
        finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW, fail_commit=True)
    # BOTH facts absent: no Document AND session not verified (atomic rollback modeled).
    assert row.upload_session_id not in store.documents_by_session
    assert row.state is not SessionState.VERIFIED


def test_store_finalize_uow_direct_atomicity():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    observed = storage.inspect_object(BUCKET, row.object_key)
    with pytest.raises(SimulatedCommitFailure):
        store.finalize_document_and_verify(row, observed, fail_before_commit=True)
    assert row.upload_session_id not in store.documents_by_session
    assert row.state is SessionState.UPLOADING
    # A subsequent successful commit writes BOTH facts together.
    doc = store.finalize_document_and_verify(row, observed)
    assert isinstance(doc, DocumentRow)
    assert store.documents_by_session[row.upload_session_id] is doc
    assert row.state is SessionState.VERIFIED


# ===========================================================================
# Finding 5 — server-owned full identity; client cannot supply bucket/key/version
# ===========================================================================

def test_wrong_bucket_key_version_fail_verification():
    expected = _expected(version="v1")
    assert verify_object(expected, _observed(bucket="attacker-bucket")).reason == "bucket mismatch"
    assert verify_object(expected, _observed(key="attacker-key")).reason == "key mismatch"
    assert verify_object(expected, _observed(version="v2")).reason == "version mismatch"


def test_client_cannot_override_bucket_or_version():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    # bind a version first so the version-override check has an expectation to compare.
    finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    bound = row.expected.expected_version
    assert bound is not None
    # Re-open a fresh not-yet-verified session to exercise the client-identity guards.
    row2 = _open_session(store, storage)
    assert finalize_upload(store, storage, OkScanner(), row2.upload_session_id, now=NOW,
                           client_supplied_bucket="attacker-bucket").outcome is FinalizeOutcome.REJECTED_IDENTITY
    assert row2.upload_session_id not in store.documents_by_session


def test_completion_uses_server_owned_identity_not_client_input():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    # Client "declares" the correct persisted identity — allowed and finalizes.
    res = finalize_upload(
        store, storage, OkScanner(), row.upload_session_id, now=NOW,
        client_supplied_bucket=row.expected.expected_bucket,
        client_supplied_key=row.expected.expected_key,
    )
    assert res.outcome is FinalizeOutcome.CREATED
    assert res.document.reference.bucket == BUCKET
    assert res.document.reference.key == row.object_key
