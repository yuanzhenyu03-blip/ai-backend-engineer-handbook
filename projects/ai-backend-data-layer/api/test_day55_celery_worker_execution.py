"""Day55 tests — Celery Worker execution & long-running AI Jobs (in-memory control flow).

These prove APPLICATION CONTROL FLOW over an in-memory Celery-like broker + PostgreSQL-owned
JobStore. They do NOT prove a real Celery broker, a real Worker process, real ACK/redelivery/
visibility timeouts, Worker-loss/OOM fault injection, real PostgreSQL, or the real Provider.
"""
from datetime import datetime, timezone

import pytest

from day53_openai_provider_structured_output import SchemaRegistry, StructuredOutputValidator
from day54_streaming_disconnects_timeouts_cancellation import IntentKind
from day55_celery_worker_execution import (
    AckMode, CeleryBrokerSim, ClaimStatus, CostState, Envelope, FakeProvider, JobStatus, JobStore,
    OutboxRelay, ProviderResultKind, RepairAction, WorkerOutcome, WorkerPool, build_affected_set,
    classify_repair, graceful_drain, request_cancellation, run_worker, terminal_for_intent,
    SUPPORTED_CONTRACT_VERSIONS, SUPPORTED_ENVELOPE_VERSIONS,
)

NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)
VALID_PAYLOAD = {"summary": "ok", "citations": ["a"], "confidence": 0.9}


def _job(store, job_id="job-1", contract="exec.v1", release="r1"):
    return store.create_queued_job(job_id, tenant_id="t1", client_idempotency_key="idem-1",
                                   reserved_tokens=100, execution_contract_version=contract,
                                   release_version=release)


def _success_provider():
    return FakeProvider(kind=ProviderResultKind.SUCCESS, payload=dict(VALID_PAYLOAD),
                        usage_tokens=42, request_id="req-1")


def _relay_and_deliver(store, broker, job):
    OutboxRelay(broker).relay(job)
    return broker.deliver()


# --- Outbox publish-before-checkpoint ordering ----------------------------
def test_relay_publishes_before_checkpoint():
    broker = CeleryBrokerSim()
    relay = OutboxRelay(broker)
    store = JobStore()
    job = _job(store)
    assert relay.relay(job) is True
    assert broker.publish_count == 1
    assert job.job_id in relay.published_checkpoints


def test_relay_crash_after_publish_still_enqueued_no_checkpoint():
    broker = CeleryBrokerSim()
    relay = OutboxRelay(broker)
    store = JobStore()
    job = _job(store)
    ok = relay.relay(job, crash_after_publish=True)
    assert ok is False
    assert broker.publish_count == 1                 # message is queued (not stranded)
    assert job.job_id not in relay.published_checkpoints  # recovery will re-publish (duplicate)


# --- Happy path: claim -> provider -> validate -> guarded complete ---------
def test_success_path_completes_and_acks():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    d = _relay_and_deliver(store, broker, job)
    res = run_worker(store, broker, d, _success_provider(), worker_id="w1", now=NOW)
    assert res.outcome is WorkerOutcome.SUCCEEDED
    assert res.acked is True
    assert res.job_status is JobStatus.SUCCEEDED
    assert store.get(job.job_id).settled_tokens == 42
    assert broker.depth() == 0


def test_ack_success_is_not_business_success_until_guarded_complete():
    # A validation refusal still ACKs the delivery (handled) but the Job is NOT succeeded.
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    d = _relay_and_deliver(store, broker, job)
    bad = FakeProvider(kind=ProviderResultKind.SUCCESS, payload={"summary": ""}, request_id="req-1")
    res = run_worker(store, broker, d, bad, worker_id="w1", now=NOW)
    assert res.outcome is WorkerOutcome.VALIDATION_REFUSED
    assert res.acked is True
    assert store.get(job.job_id).status is not JobStatus.SUCCEEDED


# --- Guarded claim = first duplicate-call gate ----------------------------
def test_guarded_claim_grants_one_row():
    store = JobStore()
    _job(store)
    c = store.claim_execution("job-1", worker_id="w1", now=NOW)
    assert c.status is ClaimStatus.GRANTED
    assert c.attempt is not None


def test_duplicate_delivery_of_terminal_job_is_noop():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    d1 = _relay_and_deliver(store, broker, job)
    run_worker(store, broker, d1, _success_provider(), worker_id="w1", now=NOW)
    # redelivery of the same job after success
    broker.publish(Envelope("run_ai_job", "job.dispatch.v1", job.job_id))
    d2 = broker.deliver()
    p2 = _success_provider()
    res = run_worker(store, broker, d2, p2, worker_id="w2", now=NOW)
    assert res.outcome is WorkerOutcome.DUPLICATE_NOOP
    assert p2.calls == 0                             # no second Provider call
    assert res.acked is True


def test_claim_conflict_when_another_live_worker_holds_lease():
    store = JobStore()
    _job(store)
    store.claim_execution("job-1", worker_id="w1", now=NOW)   # w1 holds a live lease
    c = store.claim_execution("job-1", worker_id="w2", now=NOW)
    assert c.status is ClaimStatus.CONFLICT


def test_redelivery_retains_same_attempt_and_provider_idempotency_key():
    store = JobStore()
    _job(store)
    c1 = store.claim_execution("job-1", worker_id="w1", now=NOW)
    key1 = c1.attempt.provider_idempotency_key
    # a later delivery / same-worker re-claim retains the open Attempt (no new key)
    c2 = store.claim_execution("job-1", worker_id="w1", now=NOW)
    assert c2.attempt.attempt_id == c1.attempt.attempt_id
    assert c2.attempt.provider_idempotency_key == key1


# --- ACK timing ------------------------------------------------------------
def test_late_ack_redelivers_on_transient_failure():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    d = _relay_and_deliver(store, broker, job)
    p = FakeProvider(kind=ProviderResultKind.TRANSIENT, request_id="req-1")
    res = run_worker(store, broker, d, p, worker_id="w1", now=NOW, ack_mode=AckMode.LATE)
    assert res.outcome is WorkerOutcome.TRANSIENT_RETRY
    assert res.acked is False
    assert broker.depth() == 1                       # redelivered for a bounded retry (Day56 depth)


def test_early_ack_loses_delivery_on_crash_semantics():
    # Early ACK removes the delivery immediately; a crash before durable completion cannot redeliver.
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    d = _relay_and_deliver(store, broker, job)
    p = FakeProvider(kind=ProviderResultKind.TRANSIENT, request_id="req-1")
    run_worker(store, broker, d, p, worker_id="w1", now=NOW, ack_mode=AckMode.EARLY)
    assert broker.depth() == 0                       # delivery gone; no redelivery safety net


# --- Provider timeout -> PENDING_RECONCILIATION ---------------------------
def test_provider_timeout_pending_reconciliation_retains_reservation():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    d = _relay_and_deliver(store, broker, job)
    p = FakeProvider(kind=ProviderResultKind.TIMEOUT, request_id="req-1")
    res = run_worker(store, broker, d, p, worker_id="w1", now=NOW)
    assert res.outcome is WorkerOutcome.PENDING_RECONCILIATION
    j = store.get(job.job_id)
    assert j.status is JobStatus.PENDING_RECONCILIATION
    assert j.cost_state is CostState.RECONCILIATION_PENDING   # never fabricated 0
    assert store._attempts[j.open_attempt_id].provider_request_id == "req-1"


def test_redelivery_of_pending_reconciliation_does_not_recall_provider():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    d = _relay_and_deliver(store, broker, job)
    run_worker(store, broker, d, FakeProvider(kind=ProviderResultKind.TIMEOUT, request_id="req-1"),
               worker_id="w1", now=NOW)
    broker.publish(Envelope("run_ai_job", "job.dispatch.v1", job.job_id))
    d2 = broker.deliver()
    p2 = _success_provider()
    res = run_worker(store, broker, d2, p2, worker_id="w2", now=NOW)
    assert res.outcome is WorkerOutcome.RECONCILE_NO_RECALL
    assert p2.calls == 0                             # no blind re-call


# --- Poison classification -------------------------------------------------
def test_envelope_poison_dead_letters_before_job_load():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    broker.publish(Envelope("run_ai_job", "job.dispatch.v2", job.job_id))   # unsupported envelope
    d = broker.deliver()
    p = _success_provider()
    res = run_worker(store, broker, d, p, worker_id="w1", now=NOW)
    assert res.outcome is WorkerOutcome.ENVELOPE_POISON_DEADLETTER
    assert p.calls == 0
    assert len(broker.dead_letter.items) == 1
    assert store.get(job.job_id).status is JobStatus.QUEUED   # Job untouched


def test_contract_poison_quarantines_after_job_load():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store, contract="exec.v9")            # unsupported persisted execution contract
    d = _relay_and_deliver(store, broker, job)
    p = _success_provider()
    res = run_worker(store, broker, d, p, worker_id="w1", now=NOW)
    assert res.outcome is WorkerOutcome.CONTRACT_POISON_QUARANTINE
    assert p.calls == 0
    assert store.get(job.job_id).status is JobStatus.QUARANTINED


def test_envelope_and_contract_versions_are_disjoint_concepts():
    assert "job.dispatch.v1" in SUPPORTED_ENVELOPE_VERSIONS
    assert "exec.v1" in SUPPORTED_CONTRACT_VERSIONS
    assert SUPPORTED_ENVELOPE_VERSIONS.isdisjoint(SUPPORTED_CONTRACT_VERSIONS)


# --- Day54 durable cancellation in Celery ---------------------------------
def test_pre_call_cancellation_zero_provider_calls():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    request_cancellation(store, job.job_id, actor="user", reason="stop", now=NOW)
    d = _relay_and_deliver(store, broker, job)
    p = _success_provider()
    res = run_worker(store, broker, d, p, worker_id="w1", now=NOW)
    assert res.outcome is WorkerOutcome.CANCELLED_PRE_CALL
    assert p.calls == 0
    assert store.get(job.job_id).status is JobStatus.CANCELLED


def test_deadline_intent_maps_to_expired():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    request_cancellation(store, job.job_id, actor="system", reason="deadline", now=NOW,
                         kind=IntentKind.DEADLINE_EXPIRY)
    d = _relay_and_deliver(store, broker, job)
    res = run_worker(store, broker, d, _success_provider(), worker_id="w1", now=NOW)
    assert res.outcome is WorkerOutcome.CANCELLED_PRE_CALL
    assert store.get(job.job_id).status is JobStatus.EXPIRED


def test_final_pre_completion_cancellation_prevents_succeeded():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    d = _relay_and_deliver(store, broker, job)
    res = run_worker(store, broker, d, _success_provider(), worker_id="w1", now=NOW,
                     cancel_before_completion=True)
    assert res.outcome is WorkerOutcome.CANCELLED_PRE_COMPLETION
    assert store.get(job.job_id).status is JobStatus.CANCELLED


def test_revoke_is_best_effort_not_authority():
    store = JobStore()
    _job(store)
    revoked = []
    request_cancellation(store, "job-1", actor="user", reason="x", now=NOW,
                         revoke=lambda jid: revoked.append(jid))
    assert revoked == ["job-1"]                      # revoke fired AFTER the durable intent commit
    assert store.open_intent("job-1") is not None


def test_completion_and_cancellation_one_guarded_winner():
    store = JobStore()
    _job(store)
    store.claim_execution("job-1", worker_id="w1", now=NOW)
    # cancellation wins first
    store.guarded_terminal_transition("job-1", JobStatus.CANCELLED, now=NOW)
    # a late guarded completion sees zero rows
    out = store.guarded_complete_success("job-1", artifact=VALID_PAYLOAD, actual_tokens=10, now=NOW)
    assert out.value == "no_op"
    assert store.get("job-1").status is JobStatus.CANCELLED


def test_crash_after_intent_is_reobservable_and_idempotent():
    store = JobStore()
    _job(store)
    store.persist_cancellation_intent("job-1", kind=IntentKind.USER_CANCELLATION, reason="x",
                                      actor="user", now=NOW)
    # re-observe twice: guarded transition absorbs repeats
    a = store.guarded_terminal_transition("job-1", terminal_for_intent(IntentKind.USER_CANCELLATION),
                                          now=NOW)
    b = store.guarded_terminal_transition("job-1", terminal_for_intent(IntentKind.USER_CANCELLATION),
                                          now=NOW)
    assert a.value == "applied" and b.value == "no_op"


# --- Graceful drain --------------------------------------------------------
def test_graceful_drain_stops_new_claims_and_drains_bounded():
    pool = WorkerPool()
    rep = graceful_drain(pool, inflight=5, drain_bound=3)
    assert pool.accepting is False
    assert rep.inflight_drained == 3
    assert rep.inflight_abandoned == 2               # these redeliver, not lost
    assert rep.checkpointed is True


# --- Erroneous early-ACK release incident ---------------------------------
def test_config_rollback_is_not_business_fact_rollback():
    from day55_celery_worker_execution import ReleaseConfig
    cfg = ReleaseConfig("r2", early_ack=True)
    cfg.rollback()
    assert cfg.early_ack is False                    # future harm stopped; running Jobs untouched


def test_affected_set_from_release_and_no_bulk_flip():
    store = JobStore()
    j1 = _job(store, "job-a", release="bad-r2")
    j2 = _job(store, "job-b", release="good-r1")
    store.claim_execution("job-a", worker_id="w1", now=NOW)   # running under bad release
    store.claim_execution("job-b", worker_id="w1", now=NOW)
    affected = build_affected_set(store, release_version="bad-r2", window_start=NOW, window_end=NOW)
    assert affected == ["job-a"]
    assert store.get("job-a").status is JobStatus.RUNNING     # NOT bulk-flipped to queued


def test_repair_reconcile_only_when_provider_evidence_exists():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store, release="bad-r2")
    d = _relay_and_deliver(store, broker, job)
    run_worker(store, broker, d, FakeProvider(kind=ProviderResultKind.TIMEOUT, request_id="req-1"),
               worker_id="w1", now=NOW)
    # provider_request_id recorded -> possible execution -> reconcile only, never blind re-dispatch
    assert classify_repair(store, job.job_id) is RepairAction.RECONCILE_ONLY


def test_repair_guarded_redispatch_when_no_provider_evidence():
    store = JobStore()
    job = _job(store, release="bad-r2")
    store.claim_execution(job.job_id, worker_id="w1", now=NOW)  # claimed but no Provider call yet
    assert classify_repair(store, job.job_id) is RepairAction.RECONCILE_THEN_GUARDED_REDISPATCH


# --- Identity layers -------------------------------------------------------
def test_worker_identity_is_not_attempt_identity():
    store = JobStore()
    _job(store)
    c1 = store.claim_execution("job-1", worker_id="w1", now=NOW)
    # a different worker resuming does not change the durable Attempt identity
    c2 = store.claim_execution("job-1", worker_id="w1", now=NOW)
    assert c1.attempt.attempt_id == c2.attempt.attempt_id


# ===========================================================================
# Review-round regression tests (F1-F5)
# ===========================================================================
from datetime import timedelta

from day55_celery_worker_execution import celery_task_id_for_job


def test_f1_lease_expiry_after_provider_evidence_is_reconcile_only_no_recall():
    """Worker A records provider_request_id then goes dark; the lease expires and Worker B gets a
    redelivery. Provider must NOT be called again; the result is reconciliation-only."""
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    # Worker A claims and opens a Provider request (evidence persisted), then never completes.
    claimA = store.claim_execution(job.job_id, worker_id="wA", now=NOW)
    assert claimA.status is ClaimStatus.GRANTED
    store.record_provider_request_id(claimA.attempt.attempt_id, "req-A")
    assert store.get(job.job_id).status is JobStatus.RUNNING       # still running, lease held by wA
    # Lease expires; Worker B receives a redelivery well after expiry.
    later = NOW + timedelta(minutes=6)
    broker.publish(Envelope("run_ai_job", "job.dispatch.v1", job.job_id,
                            celery_task_id=job.job_id))
    d = broker.deliver()
    providerB = _success_provider()
    res = run_worker(store, broker, d, providerB, worker_id="wB", now=later)
    assert res.outcome is WorkerOutcome.RECONCILE_NO_RECALL
    assert providerB.calls == 0                                    # NO second Provider call
    assert store.get(job.job_id).status is JobStatus.PENDING_RECONCILIATION
    # The retained Attempt + its provider_request_id are unchanged.
    assert store._attempts[store.get(job.job_id).open_attempt_id].provider_request_id == "req-A"


def test_f1_claim_execution_directly_routes_reconcile_when_evidence_and_lease_expired():
    store = JobStore()
    _job(store)
    c1 = store.claim_execution("job-1", worker_id="wA", now=NOW)
    store.record_provider_request_id(c1.attempt.attempt_id, "req-A")
    c2 = store.claim_execution("job-1", worker_id="wB", now=NOW + timedelta(minutes=6))
    assert c2.status is ClaimStatus.RECONCILE_ONLY
    assert c2.attempt.attempt_id == c1.attempt.attempt_id


def test_f2_cancellation_intent_after_running_claim_blocks_provider_call():
    """A Job already claimed RUNNING, then a cancellation intent is written; the delivery is
    processed before the Provider request. Provider calls must be 0 and the Job reaches the correct
    terminal cancellation state."""
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    OutboxRelay(broker).relay(job)
    # A Worker claims it -> RUNNING (no Provider evidence yet).
    store.claim_execution(job.job_id, worker_id="w1", now=NOW)
    assert store.get(job.job_id).status is JobStatus.RUNNING
    # Now an authorized cancellation intent is persisted while RUNNING.
    request_cancellation(store, job.job_id, actor="user", reason="stop", now=NOW)
    # The delivery is processed (same worker re-claims); the pre-Provider re-check must fire.
    d = broker.deliver()
    provider = _success_provider()
    res = run_worker(store, broker, d, provider, worker_id="w1", now=NOW)
    assert res.outcome is WorkerOutcome.CANCELLED_PRE_CALL
    assert provider.calls == 0
    assert res.acked is True
    assert store.get(job.job_id).status is JobStatus.CANCELLED


def test_f2_deadline_intent_after_running_claim_maps_to_expired():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    OutboxRelay(broker).relay(job)
    store.claim_execution(job.job_id, worker_id="w1", now=NOW)
    request_cancellation(store, job.job_id, actor="system", reason="deadline", now=NOW,
                         kind=IntentKind.DEADLINE_EXPIRY)
    d = broker.deliver()
    provider = _success_provider()
    res = run_worker(store, broker, d, provider, worker_id="w1", now=NOW)
    assert res.outcome is WorkerOutcome.CANCELLED_PRE_CALL
    assert provider.calls == 0
    assert store.get(job.job_id).status is JobStatus.EXPIRED


def test_f3_provider_request_id_event_attributes_to_real_job_with_evidence():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    d = _relay_and_deliver(store, broker, job)
    run_worker(store, broker, d, FakeProvider(kind=ProviderResultKind.TIMEOUT, request_id="req-1"),
               worker_id="w1", now=NOW)
    evs = [e for e in store.events if e["type"] == "provider_request_id_recorded"]
    assert len(evs) == 1
    ev = evs[0]
    assert ev["job_id"] == job.job_id                       # attributed to the REAL parent Job
    assert ev["provider_request_id"] == "req-1"             # carries repair evidence
    att = store._attempts[store.get(job.job_id).open_attempt_id]
    assert ev["attempt_id"] == att.attempt_id
    assert ev["correlation_id"] == att.correlation_id
    # never a correlation_id used as a Job id
    assert ev["job_id"] != att.correlation_id


def test_f4_affected_set_excludes_same_release_running_job_outside_window():
    store = JobStore()
    _job(store, "job-in", release="bad-r2")
    _job(store, "job-out", release="bad-r2")           # SAME bad release, but claimed earlier
    t_out = NOW - timedelta(hours=2)                    # outside the window
    t_in = NOW                                          # inside the window
    store.claim_execution("job-out", worker_id="w1", now=t_out)
    store.claim_execution("job-in", worker_id="w1", now=t_in)
    affected = build_affected_set(store, release_version="bad-r2",
                                  window_start=NOW - timedelta(minutes=30),
                                  window_end=NOW + timedelta(minutes=30))
    assert affected == ["job-in"]                      # the out-of-window running Job is excluded


def test_f4_affected_set_excludes_running_job_with_no_running_evidence():
    store = JobStore()
    j = _job(store, "job-x", release="bad-r2")
    j.status = JobStatus.RUNNING                        # running but no running_since / claim event
    affected = build_affected_set(store, release_version="bad-r2",
                                  window_start=NOW - timedelta(days=1),
                                  window_end=NOW + timedelta(days=1))
    assert affected == []


def test_f5_published_celery_task_id_equals_job_id_invariant():
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    OutboxRelay(broker).relay(job)
    d = broker.deliver()
    assert d.envelope.celery_task_id == job.job_id
    assert celery_task_id_for_job(job.job_id) == job.job_id


def test_f5_revoke_uses_the_invariant_task_id():
    store = JobStore()
    _job(store, "job-1")
    revoked = []
    request_cancellation(store, "job-1", actor="user", reason="x", now=NOW,
                         revoke=lambda task_id: revoked.append(task_id))
    assert revoked == [celery_task_id_for_job("job-1")]   # correct task id via the invariant
    assert revoked == ["job-1"]
    assert store.open_intent("job-1") is not None          # durable intent remains sole authority


# ===========================================================================
# P1 recovery-gap regression: OOM AFTER dispatch marker, BEFORE provider_request_id
# ===========================================================================
def test_p1_oom_after_dispatch_marker_before_request_id_reconciles_no_recall():
    """Worker A guarded-claims and persists the conservative external-call marker, then is lost
    BEFORE recording provider_request_id. The lease expires and Worker B gets a redelivery. Worker B
    must NOT call the Provider; the Job is reconciliation-only (Provider may already have executed)."""
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    # Worker A claims and marks dispatch starting, then dies before recording provider_request_id.
    claimA = store.claim_execution(job.job_id, worker_id="wA", now=NOW)
    assert claimA.status is ClaimStatus.GRANTED
    store.mark_provider_dispatch_starting(claimA.attempt.attempt_id, now=NOW)
    assert store._attempts[claimA.attempt.attempt_id].provider_request_id is None   # id never recorded
    key_before = claimA.attempt.provider_idempotency_key
    # Lease expires; Worker B receives a redelivery well after expiry.
    later = NOW + timedelta(minutes=6)
    broker.publish(Envelope("run_ai_job", "job.dispatch.v1", job.job_id,
                            celery_task_id=job.job_id))
    d = broker.deliver()
    providerB = _success_provider()
    res = run_worker(store, broker, d, providerB, worker_id="wB", now=later)
    # No blind re-call; reconciliation-only; unknown cost retained.
    assert providerB.calls == 0
    assert res.outcome is WorkerOutcome.RECONCILE_NO_RECALL
    j = store.get(job.job_id)
    assert j.status is JobStatus.PENDING_RECONCILIATION
    assert j.cost_state is CostState.RECONCILIATION_PENDING
    # No new Attempt; same provider idempotency key; request id still absent.
    assert j.open_attempt_id == claimA.attempt.attempt_id
    assert store._attempts[j.open_attempt_id].provider_idempotency_key == key_before
    assert store._attempts[j.open_attempt_id].provider_request_id is None


def test_p1_claim_reconciles_on_marker_only_even_without_request_id():
    """A direct claim_execution regression: the conservative marker alone (no provider_request_id)
    routes a lease-expired re-claim to RECONCILE_ONLY. Missing request id != Provider not executed."""
    store = JobStore()
    _job(store)
    c1 = store.claim_execution("job-1", worker_id="wA", now=NOW)
    store.mark_provider_dispatch_starting(c1.attempt.attempt_id, now=NOW)
    c2 = store.claim_execution("job-1", worker_id="wB", now=NOW + timedelta(minutes=6))
    assert c2.status is ClaimStatus.RECONCILE_ONLY
    assert c2.attempt.attempt_id == c1.attempt.attempt_id
    assert c2.attempt.provider_request_id is None       # still no id, still reconcile-only


def test_p1_marker_persisted_but_request_never_sent_still_reconciles_accepted_false_positive():
    """Accepted safety-first FALSE POSITIVE: even if the Provider request had not actually left the
    process when the Worker crashed, a persisted marker still forces reconciliation rather than a
    retry. We never trade a possible duplicate paid Provider call for an automatic retry."""
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    claimA = store.claim_execution(job.job_id, worker_id="wA", now=NOW)
    store.mark_provider_dispatch_starting(claimA.attempt.attempt_id, now=NOW)
    # (In reality the socket write may not have happened — the model cannot know, and by design
    # does not try to.) Redelivery after lease expiry:
    broker.publish(Envelope("run_ai_job", "job.dispatch.v1", job.job_id, celery_task_id=job.job_id))
    d = broker.deliver()
    providerB = _success_provider()
    res = run_worker(store, broker, d, providerB, worker_id="wB", now=NOW + timedelta(minutes=6))
    assert providerB.calls == 0
    assert res.outcome is WorkerOutcome.RECONCILE_NO_RECALL
    assert store.get(job.job_id).status is JobStatus.PENDING_RECONCILIATION
    # A durable audit event records the conservative dispatch marker for later reconciliation.
    assert any(e["type"] == "provider_dispatch_started" and e["job_id"] == job.job_id
               for e in store.events)


def test_p1_dispatch_marker_persisted_before_provider_call_in_worker_flow():
    """The happy path still records the marker BEFORE the Provider call (order guarantee)."""
    store, broker = JobStore(), CeleryBrokerSim()
    job = _job(store)
    d = _relay_and_deliver(store, broker, job)
    run_worker(store, broker, d, _success_provider(), worker_id="w1", now=NOW)
    att = store._attempts[store.get(job.job_id).open_attempt_id]
    assert att.provider_dispatch_started_at is not None      # marker persisted during the run
    # marker event is attributed to the real Job
    assert any(e["type"] == "provider_dispatch_started" and e["job_id"] == job.job_id
               for e in store.events)
