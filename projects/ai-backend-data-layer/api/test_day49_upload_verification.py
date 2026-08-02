"""Day49 — FAKE-ADAPTER tests for the verified Object Storage upload boundary.

EVIDENCE LABEL (three distinct claims): STATIC / FAKE-ADAPTER VERIFICATION of
APPLICATION CONTROL FLOW against an IN-MEMORY fake Object Storage adapter and an
in-memory store that MODELS guarded compare-and-set transitions. Completion-vs-cleanup
determinism is demonstrated by explicit INTERLEAVING tests (a scanner double that calls
``claim_cleanup`` mid-scan while a mock clock advances). This is the Conceptual /
Static tier, NOT REAL RUNTIME VERIFICATION: NOT real presigned/checksum/multipart/
versioning semantics, NOT real PostgreSQL FK/constraint/transaction-atomicity or real
``SELECT ... FOR UPDATE`` fencing, NOT a real Object Storage integration, NOT a real
scanner, NOT production. No real credentials/buckets/tokens/signed URLs appear.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from day49_upload_verification import (
    CleanupClaim,
    CleanupClaimStatus,
    CleanupDecision,
    CommitGuardFailed,
    DeleteResult,
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
    VerificationClaimUnavailable,
    VerifyStatus,
    VersionAlreadyBoundError,
    claim_cleanup,
    classify_cleanup,
    classify_multipart_completion,
    classify_result_recovery,
    cleanup_not_before,
    create_upload_grant,
    derive_object_key,
    execute_cleanup_delete,
    finalize_upload,
    verify_object,
)

TENANT = uuid.UUID("0f9b0e3a-6a1e-4c2b-9c1f-2b7a4d5e6f70")
OTHER_TENANT = uuid.UUID("11111111-2222-4333-8444-555555555555")
BUCKET = "ai-research-uploads"
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
DATA = b"a 2GB research file, modeled as a few bytes for a deterministic test"
CT = "application/pdf"
SKEW = timedelta(minutes=2)
BUF = timedelta(minutes=1)


class Clock:
    """A mutable mock clock so interleaving tests can advance time during scan()."""

    def __init__(self, t: datetime) -> None:
        self.t = t

    def __call__(self) -> datetime:
        return self.t

    def advance(self, d: timedelta) -> None:
        self.t += d


class OkScanner:
    def scan(self, evidence):
        return ScanVerdict.SAFE


class UnsafeScanner:
    def scan(self, evidence):
        return ScanVerdict.UNSAFE


class DownScanner:
    def scan(self, evidence):
        raise ScannerUnavailable("scanner outage")


class RaceScanner:
    """Runs an interleaving hook mid-scan (e.g. a cleanup claim), then returns a verdict."""

    def __init__(self, hook, verdict=ScanVerdict.SAFE):
        self.hook = hook
        self.verdict = verdict

    def scan(self, evidence):
        self.hook()
        return self.verdict


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _expected(*, bucket=BUCKET, key="k", data=DATA, version=None, content_type=CT):
    return ExpectedContract(
        expected_bucket=bucket, expected_key=key, expected_size=len(data),
        expected_sha256=_sha(data), expected_content_type=content_type, expected_version=version,
    )


def _open_session(store, storage, *, tenant=TENANT, data=DATA, put=True, now=NOW,
                  cred_ttl=timedelta(minutes=15), sess_ttl=timedelta(minutes=20),
                  content_type=CT, state=SessionState.UPLOADING):
    sid = uuid.uuid4()
    key = derive_object_key(tenant, sid)
    row = UploadSessionRow(
        upload_session_id=sid, tenant_id=tenant,
        expected=_expected(bucket=BUCKET, key=key, data=data, content_type=content_type),
        state=state, credential_expires_at=now + cred_ttl, session_expires_at=now + sess_ttl,
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
# Preserved baseline behaviors (round 0/1), adapted to the guarded API
# ===========================================================================

def test_client_key_cannot_override_persisted_key():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW,
                          client_supplied_key="uploads/evil/override/source")
    assert res.outcome is FinalizeOutcome.REJECTED_IDENTITY
    assert row.upload_session_id not in store.documents_by_session


def test_verification_never_rewrites_expectation():
    expected = _expected()
    observed = _observed(data=DATA + b"x")  # size + sha differ from the frozen expectation
    before = (expected.expected_size, expected.expected_sha256)
    assert verify_object(expected, observed).status is VerifyStatus.MISMATCH
    assert (expected.expected_size, expected.expected_sha256) == before


def test_exact_identity_and_integrity_required():
    expected = _expected()
    assert verify_object(expected, _observed()).status is VerifyStatus.OK
    assert verify_object(expected, _observed(bucket="other-bucket")).status is VerifyStatus.MISMATCH
    assert verify_object(expected, _observed(key="other-key")).status is VerifyStatus.MISMATCH
    assert verify_object(expected, _observed(version="")).status is VerifyStatus.MISMATCH
    bad_size = StoredObjectEvidence(BUCKET, "k", "v1", expected.expected_size + 9, "e",
                                    expected.expected_sha256, CT)
    assert verify_object(expected, bad_size).status is VerifyStatus.MISMATCH
    bad_sum = StoredObjectEvidence(BUCKET, "k", "v1", expected.expected_size, "e", "0" * 64, CT)
    assert verify_object(expected, bad_sum).status is VerifyStatus.MISMATCH
    assert verify_object(expected, _observed(content_type="text/plain")).status is VerifyStatus.MISMATCH


def test_etag_is_not_sha256_proof():
    expected = _expected()
    only_etag = StoredObjectEvidence(BUCKET, "k", "v1", expected.expected_size,
                                     etag=expected.expected_sha256, checksum_sha256=None, content_type=CT)
    res = verify_object(expected, only_etag)
    assert res.status is VerifyStatus.MISMATCH and "SHA-256" in res.reason


def test_already_verified_retry_returns_same_document():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    first = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    assert first.outcome is FinalizeOutcome.CREATED
    again = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    assert again.outcome is FinalizeOutcome.ALREADY_VERIFIED
    assert again.document.document_id == first.document.document_id


def test_double_finalization_creates_single_document():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    r1 = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    r2 = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    assert r1.outcome is FinalizeOutcome.CREATED
    assert r2.outcome is FinalizeOutcome.ALREADY_VERIFIED
    assert len(store.documents_by_session) == 1


def test_duplicate_document_guard_direct():
    # A VERIFYING session that somehow already has a Document row cannot get a second.
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    observed = storage.inspect_object(BUCKET, row.object_key)
    store.claim_verification(row.upload_session_id, owner_token="A",
                             observed_version=observed.version, now=NOW, hold_ttl=timedelta(minutes=5))
    store.commit_document_if_owner(row.upload_session_id, observed, owner_token="A", now=NOW)
    # Force the invariant path: re-open VERIFYING with the same session but a doc present.
    row.state = SessionState.VERIFYING
    row.verification_owner = "A"
    with pytest.raises(DuplicateDocumentError):
        store.commit_document_if_owner(row.upload_session_id, observed, owner_token="A", now=NOW)


def test_unsafe_content_fails_session():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    res = finalize_upload(store, storage, UnsafeScanner(), row.upload_session_id, now=NOW)
    assert res.outcome is FinalizeOutcome.SCAN_FAILED
    assert row.state is SessionState.FAILED
    assert row.upload_session_id not in store.documents_by_session


def test_cleanup_not_before_timing():
    assert cleanup_not_before(datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
                              max_clock_skew=SKEW, safety_buffer=BUF) == datetime(2026, 8, 2, 12, 3, tzinfo=timezone.utc)


def test_cleanup_cannot_delete_verified_or_documented():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    late = NOW + timedelta(hours=5)
    assert classify_cleanup(store, row.upload_session_id, now=late,
                            max_clock_skew=SKEW, safety_buffer=BUF) in (
        CleanupDecision.KEEP_VERIFIED, CleanupDecision.KEEP_HAS_DOCUMENT)


def test_cleanup_orphan_only_after_timing_gate():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, put=False)
    row.credential_expires_at = NOW
    assert classify_cleanup(store, row.upload_session_id, now=NOW + timedelta(minutes=1),
                            max_clock_skew=SKEW, safety_buffer=BUF) is CleanupDecision.KEEP_TOO_EARLY
    assert classify_cleanup(store, row.upload_session_id, now=NOW + timedelta(minutes=4),
                            max_clock_skew=SKEW, safety_buffer=BUF) is CleanupDecision.DELETE_ORPHAN


def test_multipart_parts_without_assembly_no_document():
    storage = InMemoryObjectStorage()
    upload_id = storage.create_multipart(BUCKET, "uploads/t/s/source")
    storage.upload_part(upload_id, 1, b"part-1")
    assert storage.inspect_object(BUCKET, "uploads/t/s/source") is None
    assert classify_multipart_completion(_expected(key="uploads/t/s/source"), None, parts_present=True) \
        is MultipartRecovery.RECOVER_FROM_PARTS


def test_timed_out_complete_inspects_final_object_first():
    storage = InMemoryObjectStorage()
    key = "uploads/t/s/source"
    upload_id = storage.create_multipart(BUCKET, key)
    storage.upload_part(upload_id, 1, DATA)
    final = storage.complete_multipart(upload_id)
    expected = _expected(key=key, data=DATA, content_type="application/octet-stream")
    assert classify_multipart_completion(expected, storage.inspect_object(BUCKET, key), parts_present=True) \
        is MultipartRecovery.COMPLETE_SUCCEEDED
    assert final.checksum_sha256 == expected.expected_sha256


def test_output_recovery_without_provider_recall():
    storage = InMemoryObjectStorage()
    key = "results/t/job/attempt/result.json"
    out = b'{"result":"verified output bytes"}'
    storage.put_object(BUCKET, key, out, content_type="application/json")
    expected = _expected(key=key, data=out, content_type="application/json")
    assert classify_result_recovery(expected, storage.inspect_object(BUCKET, key),
                                    job_already_succeeded=False) is ResultRecovery.COMPLETE_IDEMPOTENT_NO_PROVIDER
    assert classify_result_recovery(expected, None, job_already_succeeded=False) is ResultRecovery.PRESERVE_UNKNOWN
    assert classify_result_recovery(expected, storage.inspect_object(BUCKET, key),
                                    job_already_succeeded=True) is ResultRecovery.ALREADY_COMPLETED


def test_cross_tenant_provenance_blocked():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, tenant=TENANT)
    store.assert_document_provenance(row.upload_session_id, TENANT)  # same tenant -> ok
    with pytest.raises(ProvenanceError):
        store.assert_document_provenance(row.upload_session_id, OTHER_TENANT)


def test_presigned_grant_is_least_privilege_and_not_a_secret():
    expected = _expected(key=derive_object_key(TENANT, uuid.uuid4()))
    grant = create_upload_grant(expected, now=NOW, ttl_seconds=900)
    assert isinstance(grant, PresignedGrant)
    assert grant.key == expected.expected_key and grant.bucket == BUCKET and grant.operation == "PUT"
    assert grant.expires_at == NOW + timedelta(seconds=900)
    assert "secret" not in grant.fake_url and grant.fake_url.startswith("fake-grant://")


def test_evidence_label_is_fake_runtime_only():
    import day49_upload_verification as m
    header = (m.__doc__ or "")
    assert "FAKE adapter" in header
    assert "NOT RUN here" in header and "REAL RUNTIME VERIFICATION" in header


# ===========================================================================
# Round 1 (preserved): illegal state / expiry / atomic UoW / identity
# ===========================================================================

@pytest.mark.parametrize("bad_state", [SessionState.INITIATED, SessionState.FAILED])
def test_illegal_state_cannot_finalize(bad_state):
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, state=bad_state)
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    assert res.outcome is FinalizeOutcome.ILLEGAL_STATE
    assert row.upload_session_id not in store.documents_by_session
    assert row.state is bad_state


def test_expired_state_maps_to_cleanup_won():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, state=SessionState.EXPIRED)
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    assert res.outcome is FinalizeOutcome.CLEANUP_WON
    assert row.upload_session_id not in store.documents_by_session


def test_finalize_rejected_after_session_expiry():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)  # session_expires_at = NOW + 20m
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW + timedelta(minutes=21))
    assert res.outcome is FinalizeOutcome.SESSION_EXPIRED
    assert row.upload_session_id not in store.documents_by_session


def test_atomic_finalize_mid_transaction_failure():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    with pytest.raises(SimulatedCommitFailure):
        finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW, fail_commit=True)
    assert row.upload_session_id not in store.documents_by_session
    assert row.state is not SessionState.VERIFIED


def test_wrong_bucket_key_version_fail_verification():
    expected = _expected(version="v1")
    assert verify_object(expected, _observed(bucket="attacker-bucket")).reason == "bucket mismatch"
    assert verify_object(expected, _observed(key="attacker-key")).reason == "key mismatch"
    assert verify_object(expected, _observed(version="v2")).reason == "version mismatch"


def test_completion_uses_server_owned_identity_not_client_input():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage)
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW,
                          client_supplied_bucket=row.expected.expected_bucket,
                          client_supplied_key=row.expected.expected_key)
    assert res.outcome is FinalizeOutcome.CREATED
    assert res.document.reference.bucket == BUCKET and res.document.reference.key == row.object_key
    # A wrong client bucket is rejected.
    row2 = _open_session(store, storage)
    assert finalize_upload(store, storage, OkScanner(), row2.upload_session_id, now=NOW,
                           client_supplied_bucket="attacker-bucket").outcome is FinalizeOutcome.REJECTED_IDENTITY


# ===========================================================================
# Finding 1 (round 2) — verification lease fencing + completion/cleanup interleaving
# ===========================================================================

def test_version_and_lease_bound_before_scanner_runs():
    # On a scanner outage the lease + exact version are already persisted (before scan).
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, sess_ttl=timedelta(hours=2))
    v1 = storage.inspect_object(BUCKET, row.object_key).version
    res = finalize_upload(store, storage, DownScanner(), row.upload_session_id, now=NOW,
                          hold_ttl=timedelta(minutes=30), owner_token="A")
    assert res.outcome is FinalizeOutcome.SCAN_RETRY_LATER
    assert row.state is SessionState.VERIFYING
    assert row.verification_owner == "A"
    assert row.verification_hold_until == NOW + timedelta(minutes=30)
    assert row.expected.expected_version == v1  # exact version bound BEFORE scanning


def test_live_hold_blocks_cleanup_during_slow_scan_and_completion_wins():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, cred_ttl=timedelta(minutes=2), sess_ttl=timedelta(hours=2))
    clock = Clock(NOW)
    seen = {}

    def hook():
        clock.advance(timedelta(minutes=5))  # slow-but-normal scan; well past the timing gate (NOW+5m)
        seen["claim"] = claim_cleanup(store, storage, row.upload_session_id, now=clock(),
                                      max_clock_skew=SKEW, safety_buffer=BUF)

    res = finalize_upload(store, storage, RaceScanner(hook), row.upload_session_id,
                          clock=clock, hold_ttl=timedelta(minutes=30), owner_token="A")
    # Cleanup saw a LIVE hold -> kept (no delete ref); completion won -> Document created.
    assert seen["claim"].status is CleanupClaimStatus.KEPT
    assert seen["claim"].decision is CleanupDecision.KEEP_VERIFICATION_HOLD
    assert res.outcome is FinalizeOutcome.CREATED
    assert row.upload_session_id in store.documents_by_session


def test_cleanup_wins_completion_creates_no_document():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, cred_ttl=timedelta(minutes=2), sess_ttl=timedelta(hours=3))
    clock = Clock(NOW)
    seen = {}

    def hook():
        clock.advance(timedelta(minutes=10))  # scan outlives the short lease (hold_ttl=1m)
        seen["claim"] = claim_cleanup(store, storage, row.upload_session_id, now=clock(),
                                      max_clock_skew=SKEW, safety_buffer=BUF)

    res = finalize_upload(store, storage, RaceScanner(hook), row.upload_session_id,
                          clock=clock, hold_ttl=timedelta(minutes=1), owner_token="A")
    # Cleanup won (lease expired mid-scan) -> completion must NOT create a Document,
    # and must NOT flip EXPIRED back to VERIFIED.
    assert seen["claim"].status is CleanupClaimStatus.DELETE_EXACT_VERSION
    assert res.outcome is FinalizeOutcome.CLEANUP_WON
    assert row.upload_session_id not in store.documents_by_session
    assert row.state is SessionState.EXPIRED


def test_completion_wins_then_cleanup_returns_no_delete_ref():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, cred_ttl=timedelta(minutes=2), sess_ttl=timedelta(hours=2))
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW)
    assert res.outcome is FinalizeOutcome.CREATED
    claim = claim_cleanup(store, storage, row.upload_session_id, now=NOW + timedelta(hours=1),
                          max_clock_skew=SKEW, safety_buffer=BUF)
    assert claim.status is CleanupClaimStatus.KEPT
    assert claim.decision in (CleanupDecision.KEEP_VERIFIED, CleanupDecision.KEEP_HAS_DOCUMENT)
    assert claim.reference is None  # nothing to delete; the object backs a Document


def test_stale_lease_worker_cannot_commit():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, sess_ttl=timedelta(hours=3))
    observed = storage.inspect_object(BUCKET, row.object_key)
    store.claim_verification(row.upload_session_id, owner_token="A", observed_version=observed.version,
                             now=NOW, hold_ttl=timedelta(minutes=1))
    # A's lease expired; a legitimate retry B re-claims (renews) with a new token.
    store.claim_verification(row.upload_session_id, owner_token="B", observed_version=observed.version,
                             now=NOW + timedelta(minutes=2), hold_ttl=timedelta(minutes=30))
    with pytest.raises(CommitGuardFailed) as exc:
        store.commit_document_if_owner(row.upload_session_id, observed, owner_token="A",
                                       now=NOW + timedelta(minutes=2))
    assert exc.value.code == "lease_lost"
    # B (the current lease owner) can commit exactly once.
    doc = store.commit_document_if_owner(row.upload_session_id, observed, owner_token="B",
                                         now=NOW + timedelta(minutes=2))
    assert isinstance(doc, DocumentRow) and len(store.documents_by_session) == 1


def test_live_lease_blocks_a_second_claimer():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, sess_ttl=timedelta(hours=2))
    observed = storage.inspect_object(BUCKET, row.object_key)
    store.claim_verification(row.upload_session_id, owner_token="A", observed_version=observed.version,
                             now=NOW, hold_ttl=timedelta(minutes=30))
    with pytest.raises(VerificationClaimUnavailable) as exc:
        store.claim_verification(row.upload_session_id, owner_token="B", observed_version=observed.version,
                                 now=NOW + timedelta(minutes=5), hold_ttl=timedelta(minutes=30))
    assert exc.value.code == "held_by_other"


def test_transient_failure_then_retry_renews_and_completes():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, sess_ttl=timedelta(hours=2))
    r1 = finalize_upload(store, storage, DownScanner(), row.upload_session_id, now=NOW,
                         hold_ttl=timedelta(minutes=30), owner_token="A")
    assert r1.outcome is FinalizeOutcome.SCAN_RETRY_LATER and row.state is SessionState.VERIFYING
    r2 = finalize_upload(store, storage, OkScanner(), row.upload_session_id,
                         now=NOW + timedelta(minutes=10), hold_ttl=timedelta(minutes=30), owner_token="A")
    assert r2.outcome is FinalizeOutcome.CREATED
    assert row.state is SessionState.VERIFIED and row.upload_session_id in store.documents_by_session


def test_dead_verifier_hold_expires_then_cleanup_reclaims_exact_version():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, cred_ttl=timedelta(minutes=2), sess_ttl=timedelta(hours=3))
    v1 = storage.inspect_object(BUCKET, row.object_key).version
    finalize_upload(store, storage, DownScanner(), row.upload_session_id, now=NOW,
                    hold_ttl=timedelta(minutes=30), owner_token="A")  # dead verifier, no renewal
    late = NOW + timedelta(minutes=40)
    assert classify_cleanup(store, row.upload_session_id, now=late,
                            max_clock_skew=SKEW, safety_buffer=BUF) is CleanupDecision.DELETE_ORPHAN
    claim = claim_cleanup(store, storage, row.upload_session_id, now=late, max_clock_skew=SKEW, safety_buffer=BUF)
    assert claim.status is CleanupClaimStatus.DELETE_EXACT_VERSION
    assert claim.reference.version == v1 and row.state is SessionState.EXPIRED
    assert execute_cleanup_delete(storage, claim) is DeleteResult.DELETED
    assert storage.inspect_object(BUCKET, row.object_key, v1) is None


# ===========================================================================
# Finding 2 (round 2) — bind exact version; cleanup deletes the exact version
# ===========================================================================

def test_scanner_outage_new_version_same_key_retry_checks_original():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, sess_ttl=timedelta(hours=2))
    v1 = storage.inspect_object(BUCKET, row.object_key).version
    finalize_upload(store, storage, DownScanner(), row.upload_session_id, now=NOW,
                    hold_ttl=timedelta(minutes=30), owner_token="A")
    assert row.expected.expected_version == v1
    # A DIFFERENT object is written to the same key (versioning mode).
    v2 = storage.put_object(BUCKET, row.object_key, b"totally different bytes",
                            content_type=CT, create_only=False).version
    assert v2 != v1
    # The retry inspects the BOUND version (v1), not the latest (v2), and completes on v1.
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id,
                          now=NOW + timedelta(minutes=5), owner_token="A")
    assert res.outcome is FinalizeOutcome.CREATED
    assert res.document.reference.version == v1


def test_concurrent_workers_bind_different_versions_only_one_wins():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, put=False)
    assert store.bind_object_version(row.upload_session_id, "v1") == "v1"
    assert store.bind_object_version(row.upload_session_id, "v1") == "v1"  # idempotent
    with pytest.raises(VersionAlreadyBoundError):
        store.bind_object_version(row.upload_session_id, "v2")


def test_claim_cleanup_returns_exact_version_and_deletes_only_it():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, put=False, cred_ttl=timedelta(0), sess_ttl=timedelta(hours=2))
    v1 = storage.put_object(BUCKET, row.object_key, DATA, content_type=CT, create_only=False).version
    v2 = storage.put_object(BUCKET, row.object_key, b"a second object at the same key",
                            content_type=CT, create_only=False).version
    store.bind_object_version(row.upload_session_id, v1)  # this session verified v1
    claim = claim_cleanup(store, storage, row.upload_session_id, now=NOW + timedelta(minutes=10),
                          max_clock_skew=SKEW, safety_buffer=BUF)
    assert claim.status is CleanupClaimStatus.DELETE_EXACT_VERSION and claim.reference.version == v1
    assert execute_cleanup_delete(storage, claim) is DeleteResult.DELETED
    assert storage.inspect_object(BUCKET, row.object_key, v1) is None
    assert storage.inspect_object(BUCKET, row.object_key, v2).version == v2  # other version intact


def test_claim_cleanup_binds_version_when_unbound():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, cred_ttl=timedelta(0), sess_ttl=timedelta(hours=2))
    v1 = storage.inspect_object(BUCKET, row.object_key).version
    assert row.expected.expected_version is None  # never finalized -> unbound
    claim = claim_cleanup(store, storage, row.upload_session_id, now=NOW + timedelta(minutes=10),
                          max_clock_skew=SKEW, safety_buffer=BUF)
    assert claim.status is CleanupClaimStatus.DELETE_EXACT_VERSION
    assert claim.reference.version == v1  # never version=None
    assert row.expected.expected_version == v1  # persisted the binding before deleting
    assert execute_cleanup_delete(storage, claim) is DeleteResult.DELETED


def test_claim_cleanup_no_object_present():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, put=False, cred_ttl=timedelta(0), sess_ttl=timedelta(hours=2))
    claim = claim_cleanup(store, storage, row.upload_session_id, now=NOW + timedelta(minutes=10),
                          max_clock_skew=SKEW, safety_buffer=BUF)
    assert claim.status is CleanupClaimStatus.NO_OBJECT_PRESENT and claim.reference is None
    assert execute_cleanup_delete(storage, claim) is DeleteResult.NO_OBJECT


def test_delete_wrong_or_missing_version_is_reconcile_not_success():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, put=False, cred_ttl=timedelta(0), sess_ttl=timedelta(hours=2))
    v1 = storage.put_object(BUCKET, row.object_key, DATA, content_type=CT, create_only=False).version
    store.bind_object_version(row.upload_session_id, v1)
    claim = claim_cleanup(store, storage, row.upload_session_id, now=NOW + timedelta(minutes=10),
                          max_clock_skew=SKEW, safety_buffer=BUF)
    # The object is deleted out-of-band before cleanup runs its delete.
    assert storage.delete_object(BUCKET, row.object_key, v1) is True
    assert execute_cleanup_delete(storage, claim) is DeleteResult.VERSION_ABSENT_RECONCILE  # not "deleted"


def test_cleanup_vs_version_binding_race_is_deterministic():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, cred_ttl=timedelta(0), sess_ttl=timedelta(hours=2))
    claim = claim_cleanup(store, storage, row.upload_session_id, now=NOW + timedelta(minutes=10),
                          max_clock_skew=SKEW, safety_buffer=BUF)
    assert claim.status is CleanupClaimStatus.DELETE_EXACT_VERSION and row.state is SessionState.EXPIRED
    # A completion that arrives after the cleanup claim cannot commit.
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW + timedelta(minutes=10))
    assert res.outcome is FinalizeOutcome.CLEANUP_WON
    assert row.upload_session_id not in store.documents_by_session


# ===========================================================================
# Finding 3 (round 2) — credential expiry != stored-object invalidation
# ===========================================================================

def test_object_uploaded_before_credential_expiry_completes_after():
    # Uploaded at 11:59 (implicit), credential expires 12:00, completion at 12:01, session valid to 15:00.
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, cred_ttl=timedelta(0), sess_ttl=timedelta(hours=3))  # credential expires at NOW
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW + timedelta(minutes=1))
    assert res.outcome is FinalizeOutcome.CREATED  # credential expiry did NOT invalidate the stored object
    assert row.upload_session_id in store.documents_by_session


def test_no_object_after_credential_expiry_does_not_create_document():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, put=False, cred_ttl=timedelta(0), sess_ttl=timedelta(hours=3))
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW + timedelta(minutes=1))
    assert res.outcome is FinalizeOutcome.UPLOAD_WINDOW_EXPIRED
    assert row.upload_session_id not in store.documents_by_session


def test_object_not_found_while_credential_still_valid():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, put=False, cred_ttl=timedelta(minutes=15), sess_ttl=timedelta(hours=3))
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW + timedelta(minutes=1))
    assert res.outcome is FinalizeOutcome.OBJECT_NOT_FOUND  # client may still be uploading
    assert row.upload_session_id not in store.documents_by_session


def test_session_expiry_blocks_even_with_object_present():
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, cred_ttl=timedelta(0), sess_ttl=timedelta(minutes=30))
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW + timedelta(minutes=31))
    assert res.outcome is FinalizeOutcome.SESSION_EXPIRED
    assert row.upload_session_id not in store.documents_by_session


def test_three_time_boundaries_are_distinct():
    # credential_expires_at < session_expires_at; cleanup_not_before derives from credential.
    cred = NOW
    not_before = cleanup_not_before(cred, max_clock_skew=SKEW, safety_buffer=BUF)
    assert not_before == NOW + timedelta(minutes=3)
    store, storage = InMemoryStore(), InMemoryObjectStorage()
    row = _open_session(store, storage, cred_ttl=timedelta(0), sess_ttl=timedelta(hours=1))
    # Between credential expiry and cleanup_not_before, an unverified orphan is too early to delete...
    assert classify_cleanup(store, row.upload_session_id, now=NOW + timedelta(minutes=1),
                            max_clock_skew=SKEW, safety_buffer=BUF) is CleanupDecision.KEEP_TOO_EARLY
    # ...but a completion in that window still succeeds (object present, session valid).
    res = finalize_upload(store, storage, OkScanner(), row.upload_session_id, now=NOW + timedelta(minutes=1))
    assert res.outcome is FinalizeOutcome.CREATED
