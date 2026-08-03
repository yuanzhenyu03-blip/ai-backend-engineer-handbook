"""Day50 — FAKE-ADAPTER tests for idempotent Job acceptance + transactional Outbox.

EVIDENCE LABEL (three distinct claims): STATIC / FAKE-ADAPTER VERIFICATION of
APPLICATION CONTROL FLOW against an IN-MEMORY store that MODELS guarded compare-and-set
transitions and a FAKE/in-memory TransportAdapter. This is the Conceptual/Static tier,
NOT REAL RUNTIME VERIFICATION: NOT real PostgreSQL UNIQUE/constraint/transaction/
isolation or `INSERT ... ON CONFLICT`/`FOR UPDATE SKIP LOCKED`, NOT a real broker/Celery
(ACK/redelivery/poison), NOT a real Worker/Provider, NOT integration, NOT production. No
real credentials/broker URLs/secrets appear.
"""

import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from day50_job_acceptance_outbox import (
    DISPATCH_EVENT_TYPE,
    AcceptOutcome,
    CrashAfterPublishTransport,
    DispatchIntentExists,
    Envelope,
    FailingTransport,
    FencingError,
    InMemoryDocumentDirectory,
    InMemoryJobStore,
    InMemoryTransport,
    JobStatus,
    OutboxState,
    RelayReport,
    SimulatedCommitFailure,
    TransportError,
    accept_job,
    build_envelope,
    compute_next_attempt,
    compute_request_fingerprint,
    run_relay_once,
)

TENANT = uuid.UUID("0f9b0e3a-6a1e-4c2b-9c1f-2b7a4d5e6f70")
OTHER_TENANT = uuid.UUID("11111111-2222-4333-8444-555555555555")
NOW = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
DOC_A = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
DOC_B = uuid.UUID("bbbbbbbb-0000-4000-8000-000000000002")
KEY = "idem-key-one-logical-command"


def _dir(*docs, tenant=TENANT):
    d = InMemoryDocumentDirectory()
    for doc in docs:
        d.add_verified(tenant, str(doc))
    return d


def _request(documents=(DOC_A,), prompt="summarize", model="gpt-x", **extra):
    req = {"documents": [str(x) for x in documents], "prompt": prompt, "model": model,
           "output_contract": "summary_v1", "api_version": "2026-08"}
    req.update(extra)
    return req


# ===========================================================================
# Acceptance idempotency + fingerprint
# ===========================================================================

def test_missing_idempotency_key_rejected_before_writes():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    for bad in (None, "", "   "):
        res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=bad, request=_request(), now=NOW)
        assert res.outcome is AcceptOutcome.MISSING_IDEMPOTENCY_KEY
    assert store.jobs == {} and store.outbox == {}  # no durable facts written


def test_unverified_or_cross_tenant_document_rejected():
    store = InMemoryJobStore()
    # DOC_A verified for OTHER_TENANT only -> our tenant cannot accept it.
    docs = _dir(DOC_A, tenant=OTHER_TENANT)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    assert res.outcome is AcceptOutcome.DOCUMENT_NOT_VERIFIED
    assert store.jobs == {} and store.outbox == {}


def test_accept_creates_one_job_and_one_dispatch_intent():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    assert res.outcome is AcceptOutcome.CREATED
    assert res.job.job_status is JobStatus.QUEUED
    assert len(store.jobs) == 1
    intents = [r for r in store.outbox.values() if r.event_type == DISPATCH_EVENT_TYPE]
    assert len(intents) == 1 and intents[0].job_id == res.job.job_id
    assert intents[0].state is OutboxState.UNPUBLISHED and intents[0].published_at is None


def test_lost_202_retry_returns_original_job_no_second_event():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    first = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    # SDK + user both retry the SAME logical command (same key + same fingerprint).
    r2 = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    r3 = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    assert r2.outcome is AcceptOutcome.RETURNED_EXISTING and r3.outcome is AcceptOutcome.RETURNED_EXISTING
    assert r2.job.job_id == first.job.job_id == r3.job.job_id
    assert len(store.jobs) == 1
    assert len([r for r in store.outbox.values() if r.event_type == DISPATCH_EVENT_TYPE]) == 1


def test_same_key_changed_fingerprint_conflicts_with_no_new_facts():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(prompt="summarize"), now=NOW)
    before_jobs, before_outbox = len(store.jobs), len(store.outbox)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY,
                     request=_request(prompt="translate to French"), now=NOW)  # changed semantics
    assert res.outcome is AcceptOutcome.CONFLICT and res.job is None
    assert len(store.jobs) == before_jobs and len(store.outbox) == before_outbox  # no new durable facts


def test_key_is_not_fingerprint_material():
    # Two different keys, same command semantics -> different accepted Jobs, same fingerprint.
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    r1 = accept_job(store, docs, tenant_id=TENANT, idempotency_key="k1", request=_request(), now=NOW)
    r2 = accept_job(store, docs, tenant_id=TENANT, idempotency_key="k2", request=_request(), now=NOW)
    assert r1.job.job_id != r2.job.job_id
    assert r1.job.request_fingerprint == r2.job.request_fingerprint  # key not in fingerprint


def test_fingerprint_covers_behavior_changing_fields():
    base = compute_request_fingerprint(_request())
    assert compute_request_fingerprint(_request(prompt="other")) != base
    assert compute_request_fingerprint(_request(model="gpt-y")) != base
    assert compute_request_fingerprint(_request(output_contract="summary_v2")) != base
    assert compute_request_fingerprint(_request()) == base  # stable


def test_document_order_preserved_by_default_but_canonical_when_unordered():
    ab = _request(documents=(DOC_A, DOC_B))
    ba = _request(documents=(DOC_B, DOC_A))
    # Default: order changes model semantics -> different fingerprints.
    assert compute_request_fingerprint(ab) != compute_request_fingerprint(ba)
    # Explicit unordered product contract -> canonicalized to the same fingerprint.
    assert compute_request_fingerprint(ab, unordered_documents=True) == \
        compute_request_fingerprint(ba, unordered_documents=True)


# ===========================================================================
# Atomic Job + Outbox UoW
# ===========================================================================

def test_acceptance_uow_is_atomic_on_failure():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    with pytest.raises(SimulatedCommitFailure):
        accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW, fail_commit=True)
    # Neither the Job nor the Outbox intent committed.
    assert store.jobs == {} and store.outbox == {}
    assert store.find_by_idempotency(TENANT, KEY) is None


def test_at_most_one_dispatch_intent_per_job():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    with pytest.raises(DispatchIntentExists):
        store.add_dispatch_intent(res.job.job_id, NOW)  # a second dispatch intent is refused


# ===========================================================================
# Outbox Relay — at-least-once, retention, backoff, quarantine, envelope
# ===========================================================================

def test_relay_publishes_and_checkpoints():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    transport = InMemoryTransport()
    report = run_relay_once(store, transport, owner_token="relay-A", now=NOW)
    assert report.published == 1 and len(transport.published) == 1
    row = res.outbox
    assert store.outbox[row.outbox_event_id].state is OutboxState.PUBLISHED
    assert store.outbox[row.outbox_event_id].published_at == NOW


def test_envelope_is_small_and_carries_no_sensitive_content():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY,
                     request=_request(prompt="TOP SECRET PROMPT"), now=NOW)
    env = build_envelope(res.outbox)
    assert isinstance(env, Envelope)
    assert set(env.__dict__) == {"outbox_event_id", "event_type", "job_id", "correlation_id"}
    assert "SECRET" not in str(env) and "prompt" not in str(env).lower()
    assert env.job_id == res.job.job_id  # Worker re-reads the Job by job_id


def test_transport_timeout_retains_intent_with_retry_evidence():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    report = run_relay_once(store, FailingTransport("connect timeout to broker://redacted"),
                            owner_token="relay-A", now=NOW, max_attempts=5)
    assert report.failed == 1 and report.published == 0
    row = store.outbox[res.outbox.outbox_event_id]
    assert row.published_at is None and row.state is OutboxState.UNPUBLISHED
    assert row.attempt_count == 1
    assert row.next_attempt_at is not None and row.next_attempt_at > NOW  # scheduled later
    assert row.relay_owner is None  # lease released for a due retry
    assert "redacted" in row.last_error and "broker://" not in row.last_error  # no secret retained


def test_retry_not_eligible_until_next_attempt_at():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    run_relay_once(store, FailingTransport(), owner_token="relay-A", now=NOW, base_seconds=60)
    # A pass before next_attempt_at claims nothing (not due yet).
    r_early = run_relay_once(store, InMemoryTransport(), owner_token="relay-A", now=NOW + timedelta(seconds=1))
    assert r_early.published == 0 and r_early.failed == 0
    # A pass after next_attempt_at publishes.
    r_late = run_relay_once(store, InMemoryTransport(), owner_token="relay-A", now=NOW + timedelta(minutes=5))
    assert r_late.published == 1


def test_backoff_is_bounded_and_jittered():
    j = lambda ceiling: ceiling * 0.5  # deterministic 50% jitter
    a1 = compute_next_attempt(1, now=NOW, base_seconds=1, cap_seconds=300, jitter=j)
    a2 = compute_next_attempt(2, now=NOW, base_seconds=1, cap_seconds=300, jitter=j)
    a10 = compute_next_attempt(10, now=NOW, base_seconds=1, cap_seconds=300, jitter=j)
    assert (a1 - NOW).total_seconds() == pytest.approx(1.5)   # 1 + 0.5*1
    assert (a2 - NOW).total_seconds() == pytest.approx(3.0)   # 2 + 0.5*2
    assert (a10 - NOW).total_seconds() == pytest.approx(450)  # capped 300 + 0.5*300
    assert (a10 - NOW).total_seconds() <= 300 * 1.5           # bounded by cap+jitter


def test_exhausted_policy_quarantines_and_does_not_fail_job():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    t = NOW
    for _ in range(5):  # max_attempts=5
        run_relay_once(store, FailingTransport(), owner_token="relay-A", now=t, max_attempts=5, base_seconds=1, cap_seconds=1)
        t += timedelta(seconds=5)
    row = store.outbox[res.outbox.outbox_event_id]
    assert row.state is OutboxState.QUARANTINED
    assert row.published_at is None  # never falsely marked published
    assert store.jobs[res.job.job_id].job_status is JobStatus.QUEUED  # Job NOT marked failed


def test_publish_success_then_crash_before_checkpoint_redelivers():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    sink = InMemoryTransport()
    # Pass 1: publish DID go out, but the Relay crashed before the checkpoint.
    r1 = run_relay_once(store, CrashAfterPublishTransport(sink), owner_token="relay-A",
                        now=NOW, hold_ttl=timedelta(minutes=1))
    assert r1.crashed_before_checkpoint == 1
    row = store.outbox[res.outbox.outbox_event_id]
    assert row.published_at is None and row.state is OutboxState.UNPUBLISHED  # not lost, not "published"
    # Pass 2 after the lease expires: republish (at-least-once) -> duplicate message.
    r2 = run_relay_once(store, sink, owner_token="relay-B", now=NOW + timedelta(minutes=2))
    assert r2.published == 1
    assert len(sink.published) == 2  # duplicate delivery is acceptable; the Job was not lost
    assert store.outbox[res.outbox.outbox_event_id].state is OutboxState.PUBLISHED


# ===========================================================================
# Relay concurrency: SKIP LOCKED claim, no lock over I/O, fencing
# ===========================================================================

def test_second_relay_skips_a_live_claim():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    a = store.claim_outbox_batch(owner_token="relay-A", now=NOW, hold_ttl=timedelta(minutes=1))
    b = store.claim_outbox_batch(owner_token="relay-B", now=NOW, hold_ttl=timedelta(minutes=1))
    assert len(a) == 1 and b == []  # SKIP LOCKED: B does not double-claim A's live row


def test_stale_relay_cannot_checkpoint_after_takeover():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    oid = res.outbox.outbox_event_id
    store.claim_outbox_batch(owner_token="relay-A", now=NOW, hold_ttl=timedelta(minutes=1))  # A holds
    # A's lease expires; B takes over.
    store.claim_outbox_batch(owner_token="relay-B", now=NOW + timedelta(minutes=2), hold_ttl=timedelta(minutes=5))
    with pytest.raises(FencingError):
        store.checkpoint_published_if_owner(oid, owner_token="relay-A", now=NOW + timedelta(minutes=2))
    # B (current owner) checkpoints successfully.
    store.checkpoint_published_if_owner(oid, owner_token="relay-B", now=NOW + timedelta(minutes=2))
    assert store.outbox[oid].state is OutboxState.PUBLISHED


def test_relay_does_not_publish_inside_the_claim():
    # Structural: claim only mutates the DB row (owner/hold); publish happens after,
    # via the transport. A transport that asserts it is called only post-claim proves
    # no transport I/O happens inside the claim step.
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    calls = {"claimed_before_publish": False}
    claimed = store.claim_outbox_batch(owner_token="relay-A", now=NOW, hold_ttl=timedelta(minutes=1))
    calls["claimed_before_publish"] = len(claimed) == 1

    class AssertingTransport:
        def publish(self, envelope):
            assert calls["claimed_before_publish"]  # claim already returned before any publish

    for oid in claimed:
        AssertingTransport().publish(build_envelope(store.outbox[oid]))
        store.checkpoint_published_if_owner(oid, owner_token="relay-A", now=NOW)
    assert store.outbox[claimed[0]].state is OutboxState.PUBLISHED


# ===========================================================================
# Worker guarded claim — duplicate delivery absorption
# ===========================================================================

def test_worker_guarded_claim_only_one_winner():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    # Duplicate deliveries -> two Workers attempt queued -> running.
    first = store.worker_claim(res.job.job_id)
    second = store.worker_claim(res.job.job_id)
    assert first is True and second is False  # exactly one 'RETURNING' row; the other calls no Provider
    assert store.jobs[res.job.job_id].job_status is JobStatus.RUNNING


# ===========================================================================
# Integrated failure/rollback drill (exercise 5)
# ===========================================================================

def test_integrated_relay_takeover_fencing_duplicate_and_single_worker():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    oid = res.outbox.outbox_event_id
    sink = InMemoryTransport()
    # Relay A publishes and pauses (crash before checkpoint).
    run_relay_once(store, CrashAfterPublishTransport(sink), owner_token="relay-A", now=NOW,
                   hold_ttl=timedelta(minutes=1))
    assert store.outbox[oid].published_at is None
    # A's lease expires; Relay B takes over the claim.
    t2 = NOW + timedelta(minutes=2)
    assert store.claim_outbox_batch(owner_token="relay-B", now=t2, hold_ttl=timedelta(minutes=5)) == [oid]
    # A's stale fencing-token checkpoint is rejected (B owns the lease, not yet published).
    with pytest.raises(FencingError):
        store.checkpoint_published_if_owner(oid, owner_token="relay-A", now=t2)
    # B republishes (at-least-once duplicate) and checkpoints.
    sink.publish(build_envelope(store.outbox[oid]))
    store.checkpoint_published_if_owner(oid, owner_token="relay-B", now=t2)
    assert store.outbox[oid].state is OutboxState.PUBLISHED
    assert len(sink.published) == 2  # at-least-once duplicate delivery; the Job was not lost
    # Duplicate messages -> exactly one Worker wins queued -> running.
    wins = [store.worker_claim(res.job.job_id) for _ in range(2)]
    assert wins.count(True) == 1 and wins.count(False) == 1


# ===========================================================================
# Honesty label
# ===========================================================================

def test_evidence_label_is_fake_runtime_only():
    import day50_job_acceptance_outbox as m
    header = (m.__doc__ or "")
    assert "FAKE" in header and "REAL RUNTIME VERIFICATION: NOT RUN" in header
    assert "no exactly-once" in header.lower()


# ===========================================================================
# Review round 1 (P1) regression tests
# ===========================================================================

# P1-1: concurrent acceptance is arbitrated atomically (one CREATED, one existing).
def test_concurrent_same_key_same_fingerprint_creates_single_job_forced_interleave():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    barrier = threading.Barrier(2)
    results: list = []

    def worker():
        # Force both threads past the existence read (both see absence) BEFORE either
        # reaches the atomic arbiter, so the atomic op is the only thing preventing a
        # double create.
        res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(),
                         now=NOW, _after_read_hook=barrier.wait)
        results.append(res.outcome)

    t1, t2 = threading.Thread(target=worker), threading.Thread(target=worker)
    t1.start(); t2.start(); t1.join(); t2.join()

    assert sorted(o.value for o in results) == ["created", "returned_existing"]
    assert len(store.jobs) == 1  # exactly one Job
    assert len([r for r in store.outbox.values() if r.event_type == DISPATCH_EVENT_TYPE]) == 1  # one intent


def test_sequential_two_creates_are_arbitrated_by_the_atomic_op():
    # Even calling the atomic arbiter twice for the same key creates only one Job:
    # the second call observes the conflict and returns the existing Job (created=False).
    store = InMemoryJobStore()
    j1, o1, created1 = store.upsert_job_on_conflict(
        tenant_id=TENANT, idempotency_key=KEY, request_fingerprint="fp", document_ids=(), now=NOW)
    j2, o2, created2 = store.upsert_job_on_conflict(
        tenant_id=TENANT, idempotency_key=KEY, request_fingerprint="fp", document_ids=(), now=NOW)
    assert created1 is True and created2 is False
    assert j1.job_id == j2.job_id and o2.outbox_event_id == o1.outbox_event_id
    assert len(store.jobs) == 1
    assert len([r for r in store.outbox.values() if r.event_type == DISPATCH_EVENT_TYPE]) == 1


# P1-2: an EXPIRED relay lease cannot checkpoint even before a new owner takes over.
def test_expired_relay_lease_cannot_checkpoint_even_without_takeover():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    oid = res.outbox.outbox_event_id
    store.claim_outbox_batch(owner_token="relay-A", now=NOW, hold_ttl=timedelta(minutes=1))  # short lease
    # No one takes over; A's lease simply expired.
    with pytest.raises(FencingError):
        store.checkpoint_published_if_owner(oid, owner_token="relay-A", now=NOW + timedelta(minutes=2))
    assert store.outbox[oid].published_at is None  # never falsely marked published
    assert store.outbox[oid].state is OutboxState.UNPUBLISHED


def test_expired_relay_lease_cannot_record_failure():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    res = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    oid = res.outbox.outbox_event_id
    store.claim_outbox_batch(owner_token="relay-A", now=NOW, hold_ttl=timedelta(minutes=1))
    with pytest.raises(FencingError):
        store.record_transport_failure(
            oid, owner_token="relay-A", exc=TransportError("boom"),
            next_attempt_at=NOW + timedelta(minutes=5), max_attempts=5, now=NOW + timedelta(minutes=2))
    assert store.outbox[oid].attempt_count == 0  # no state written by an expired lease


# P1-3: an exact retry returns the original Job even if the Document later became unavailable.
def test_exact_retry_returns_original_job_even_if_document_now_unavailable():
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    first = accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    assert first.outcome is AcceptOutcome.CREATED
    # The Document later becomes unavailable / no longer passes admission.
    docs_gone = InMemoryDocumentDirectory()  # DOC_A is NOT verified anymore
    retry = accept_job(store, docs_gone, tenant_id=TENANT, idempotency_key=KEY, request=_request(), now=NOW)
    assert retry.outcome is AcceptOutcome.RETURNED_EXISTING
    assert retry.job.job_id == first.job.job_id
    # But a NEW command (new key) against the now-unavailable Document is still rejected.
    new_cmd = accept_job(store, docs_gone, tenant_id=TENANT, idempotency_key="k-new", request=_request(), now=NOW)
    assert new_cmd.outcome is AcceptOutcome.DOCUMENT_NOT_VERIFIED
    assert len(store.jobs) == 1  # no second Job created


def test_same_key_changed_fingerprint_still_conflicts_after_document_change():
    # Ordering must not let a changed fingerprint slip through as a retry.
    store, docs = InMemoryJobStore(), _dir(DOC_A)
    accept_job(store, docs, tenant_id=TENANT, idempotency_key=KEY, request=_request(prompt="summarize"), now=NOW)
    docs_gone = InMemoryDocumentDirectory()
    res = accept_job(store, docs_gone, tenant_id=TENANT, idempotency_key=KEY,
                     request=_request(prompt="translate"), now=NOW)
    assert res.outcome is AcceptOutcome.CONFLICT  # changed semantics -> 409, not a retry
    assert len(store.jobs) == 1
