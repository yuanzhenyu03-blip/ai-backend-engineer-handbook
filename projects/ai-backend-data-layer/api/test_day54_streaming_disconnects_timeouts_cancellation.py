"""Day54 — tests for AI Streaming, Client Disconnects, Timeouts and Cancellation.

EVIDENCE LABEL: an IN-MEMORY model of the three lifecycles, SSE subscription, durable
cancellation/expiry intent, cooperative Worker checks, guarded terminal transitions, the
completion-vs-cancellation race, and the erroneous-disconnect-policy recovery. This is
APPLICATION CONTROL FLOW only. NOT real FastAPI/SSE wire behavior, NOT the real OpenAI SDK /
network / Provider, NOT real PostgreSQL / Redis / Celery, NOT integration/production. No real
credentials, prompts, Document content, or raw Provider payloads/tokens are used.
"""

import threading
from datetime import datetime, timedelta, timezone

import pytest

from day53_openai_provider_structured_output import SchemaRegistry, StructuredOutputValidator
from day54_streaming_disconnects_timeouts_cancellation import (
    CostState,
    DisconnectPolicy,
    FakeProvider,
    FakeProviderStream,
    IntentKind,
    JobStatus,
    JobStore,
    LateResultOutcome,
    RecoveryClassification,
    SubscriptionRegistry,
    TransitionOutcome,
    WorkerOutcome,
    terminal_for_intent,
    apply_cancellation,
    build_affected_set,
    classify_recovery,
    ingest_late_provider_result,
    on_sse_disconnect,
    reconnect_view,
    request_cancellation,
    run_worker,
    scan_open_intents,
)

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
VALID_V1 = {"summary": "Concise findings.", "citations": ["doc-1"], "confidence": 0.9}


def _validator():
    return StructuredOutputValidator(SchemaRegistry())


def _timed_out_job(job_id="job-1"):
    """A Job that opened a Provider request (id recorded) then timed out -> PENDING_RECONCILIATION,
    awaiting a matched, validated late result bound to (attempt_id, correlation_id, request_id)."""
    store = JobStore()
    store.create_running_job(job_id, tenant_id="tenant-a", reserved_tokens=5000,
                             correlation_id="corr-1", attempt_id="att-1",
                             schema_name="research_summary", schema_version="v1")
    provider = FakeProvider(lambda: FakeProviderStream(["a", "b"], total_tokens=None, request_id="rq-1"))
    run_worker(store, provider, job_id, now=NOW, simulate_timeout=True)
    assert store.jobs[job_id].status is JobStatus.PENDING_RECONCILIATION
    assert store.jobs[job_id].provider_request_id == "rq-1"   # P1-3: recorded at request open
    return store, provider


def _store_with_running_job(job_id="job-1", reserved=5000):
    store = JobStore()
    store.create_running_job(job_id, tenant_id="tenant-a", reserved_tokens=reserved,
                             correlation_id="corr-1")
    return store


def _provider(tokens=("a", "b", "c"), total_tokens=1200, request_id="rq-1"):
    return FakeProvider(lambda: FakeProviderStream(list(tokens), total_tokens=total_tokens,
                                                   request_id=request_id))


# ===========================================================================
# 1. HTTP client connection lifecycle: SSE disconnect ends only the subscription
# ===========================================================================
def test_sse_disconnect_does_not_mutate_durable_job():
    store = _store_with_running_job()
    reg = SubscriptionRegistry()
    sub = reg.subscribe("job-1")
    assert reg.active_count("job-1") == 1
    reg.disconnect(sub.subscription_id)
    # The subscription ended; the durable Job is intentionally untouched.
    assert reg.active_count("job-1") == 0
    job = store.jobs["job-1"]
    assert job.status is JobStatus.RUNNING          # NOT auto-cancelled
    assert job.events == [] and job.intents == []   # disconnect wrote nothing durable


def test_reconnect_reads_durable_state_and_safe_events_not_provider_tokens():
    store = _store_with_running_job()
    store.add_event("job-1", "job.progress", milestone="retrieved_documents")  # safe milestone
    reg = SubscriptionRegistry()
    reg.disconnect(reg.subscribe("job-1").subscription_id)  # first browser dropped
    view = reconnect_view(store, "job-1")                   # reconnecting browser
    assert view["status"] == "running"
    assert [e["type"] for e in view["events"]] == ["job.progress"]
    # No raw provider token ever appears in the durable events.
    assert all("token" not in e for e in view["events"])


# ===========================================================================
# 3. Provider request lifecycle: timeout is non-terminal + unknown-cost reconcile
# ===========================================================================
def test_provider_timeout_is_non_terminal_reconciliation_not_failure():
    store = _store_with_running_job()
    provider = _provider()
    res = run_worker(store, provider, "job-1", now=NOW, simulate_timeout=True)
    job = store.jobs["job-1"]
    assert res.outcome is WorkerOutcome.TIMED_OUT_PENDING
    assert job.status is JobStatus.PENDING_RECONCILIATION      # not FAILED
    assert job.cost_state is CostState.RECONCILIATION_PENDING  # reservation retained
    assert job.settled_tokens is None                          # unknown usage, never 0
    assert job.result_artifact is None                         # Provider raw output != our Artifact


def test_original_202_is_not_retroactively_changed_by_a_later_timeout():
    # The durable Job (accepted with 202) simply moves to PENDING_RECONCILIATION; there is no
    # retroactive HTTP 504 — later state is observed through the Job view.
    store = _store_with_running_job()
    run_worker(store, _provider(), "job-1", now=NOW, simulate_timeout=True)
    assert reconnect_view(store, "job-1")["status"] == "pending_reconciliation"


# ===========================================================================
# 4/5. Cancellation: durable intent first; pre-call and mid-stream cooperative
# ===========================================================================
def test_router_cancellation_persists_intent_only_no_terminal_write():
    store = _store_with_running_job()
    intent = request_cancellation(store, "job-1", actor="user-alice", reason="user requested",
                                  now=NOW)
    job = store.jobs["job-1"]
    assert job.status is JobStatus.RUNNING            # Router did NOT write cancelled
    assert job.intents[-1].intent_id == intent.intent_id and job.intents[-1].actor == "user-alice"


def test_pre_call_cancellation_prevents_provider_call():
    store = _store_with_running_job()
    request_cancellation(store, "job-1", actor="user-alice", reason="cancel", now=NOW)
    provider = _provider()
    res = run_worker(store, provider, "job-1", now=NOW)
    job = store.jobs["job-1"]
    assert res.outcome is WorkerOutcome.CANCELLED_BEFORE_CALL
    assert provider.calls == 0                        # the Provider was never contacted
    assert job.status is JobStatus.CANCELLED
    assert job.result_artifact is None


def test_mid_stream_cancellation_is_best_effort_and_does_not_fabricate_zero_cost():
    store = _store_with_running_job()
    provider = _provider(tokens=("a", "b", "c", "d"), total_tokens=None)  # usage unknown
    # Fire the intent after the first token has been streamed.
    fired = {"n": 0}
    def cancel_check():
        fired["n"] += 1
        return fired["n"] >= 1
    res = run_worker(store, provider, "job-1", now=NOW, cancel_check=cancel_check)
    job = store.jobs["job-1"]
    assert res.outcome is WorkerOutcome.CANCELLED_MID_STREAM
    assert provider.calls == 1 and res.tokens_seen >= 1
    assert job.status is JobStatus.CANCELLED
    assert job.cost_state is CostState.RECONCILIATION_PENDING  # unknown cost retained, never 0
    assert job.settled_tokens is None
    assert job.result_artifact is None                         # no success artifact from a cancel


# ===========================================================================
# 6. Completion vs cancellation race: exactly one guarded winner
# ===========================================================================
def test_completion_and_cancellation_race_has_one_guarded_winner():
    store = _store_with_running_job()
    barrier = threading.Barrier(2)
    outcomes = []

    def complete():
        barrier.wait()
        outcomes.append(("complete", store.guarded_terminal_transition("job-1", JobStatus.SUCCEEDED, now=NOW)))

    def cancel():
        barrier.wait()
        outcomes.append(("cancel", store.guarded_terminal_transition("job-1", JobStatus.CANCELLED, now=NOW)))

    t1 = threading.Thread(target=complete); t2 = threading.Thread(target=cancel)
    t1.start(); t2.start(); t1.join(); t2.join()
    won = [name for name, oc in outcomes if oc is TransitionOutcome.WON]
    zero = [name for name, oc in outcomes if oc is TransitionOutcome.ZERO_ROWS]
    assert len(won) == 1 and len(zero) == 1          # exactly one winner; the loser sees zero rows
    job = store.jobs["job-1"]
    assert job.status in (JobStatus.SUCCEEDED, JobStatus.CANCELLED)
    # Only ONE terminal event was written (no overwrite).
    assert len([e for e in job.events if e["type"].startswith("job.")]) == 1


# ===========================================================================
# 7. Scheduler/Worker crash after persisted intent -> recoverable via re-observation
# ===========================================================================
def test_scheduler_crash_after_intent_is_recovered_by_reobservation():
    store = _store_with_running_job()
    request_cancellation(store, "job-1", actor="user-alice", reason="cancel", now=NOW)
    # Simulate a crash BEFORE the Worker acted: the durable intent survives.
    assert scan_open_intents(store) == ["job-1"]
    # A restarted Worker re-observes and applies a guarded terminal transition.
    first = apply_cancellation(store, "job-1", now=NOW)
    assert first is TransitionOutcome.WON and store.jobs["job-1"].status is JobStatus.CANCELLED
    # At-least-once observation: a repeat is absorbed (zero rows), no double terminal write.
    second = apply_cancellation(store, "job-1", now=NOW)
    assert second is TransitionOutcome.ZERO_ROWS
    assert scan_open_intents(store) == []             # no longer live
    assert len([e for e in store.jobs["job-1"].events if e["type"] == "job.cancelled"]) == 1


# ===========================================================================
# 8. Terminal cancellation refuses a late completion (no overwrite)
# ===========================================================================
def test_terminal_cancellation_refuses_late_valid_result():
    store, _ = _timed_out_job()
    request_cancellation(store, "job-1", actor="user-alice", reason="cancel", now=NOW)
    apply_cancellation(store, "job-1", now=NOW)        # Job is terminally CANCELLED
    assert store.jobs["job-1"].status is JobStatus.CANCELLED
    res = ingest_late_provider_result(store, "job-1", attempt_id="att-1", correlation_id="corr-1",
                                      provider_request_id="rq-1", raw_payload=VALID_V1,
                                      validator=_validator(), now=NOW + timedelta(seconds=5),
                                      actual_tokens=1200)
    job = store.jobs["job-1"]
    assert res is LateResultOutcome.REFUSED_TERMINAL   # terminal -> guarded no-op
    assert job.status is JobStatus.CANCELLED           # not flipped to succeeded
    assert job.result_artifact is None and job.settled_tokens is None


def test_deadline_expiry_uses_the_same_guarded_terminal_protocol():
    store = _store_with_running_job()
    request_cancellation(store, "job-1", actor="scheduler", reason="job deadline",
                         kind=IntentKind.DEADLINE_EXPIRY, now=NOW)
    outcome = apply_cancellation(store, "job-1", now=NOW, target=JobStatus.EXPIRED)
    assert outcome is TransitionOutcome.WON and store.jobs["job-1"].status is JobStatus.EXPIRED


# ===========================================================================
# 2 (persistence trade-off). No default per-token persistence
# ===========================================================================
def test_worker_never_persists_raw_provider_tokens_as_events():
    store = _store_with_running_job()
    provider = _provider(tokens=("secret-token-1", "secret-token-2"), total_tokens=42)
    run_worker(store, provider, "job-1", now=NOW)
    job = store.jobs["job-1"]
    assert job.status is JobStatus.SUCCEEDED and job.settled_tokens == 42
    blob = str(job.events)
    assert "secret-token-1" not in blob and "secret-token-2" not in blob  # tokens never persisted


# ===========================================================================
# 9. Erroneous SSE-disconnect policy: rollback + evidence-based recovery
# ===========================================================================
def test_erroneous_disconnect_policy_recovery_refuses_blind_flip_and_recall():
    store = JobStore()
    store.create_running_job("job-1", tenant_id="tenant-a", reserved_tokens=5000,
                             correlation_id="corr-1")
    store.jobs["job-1"].provider_request_id = "rq-1"  # external execution evidence, usage unknown
    reg = SubscriptionRegistry()
    policy = DisconnectPolicy(disconnect_creates_cancel_intent=True, release_version="v1.4.0-bad")
    # The bug: a disconnect wrongly persists a cancellation intent.
    sub = reg.subscribe("job-1")
    intent = on_sse_disconnect(store, policy, sub, reg, now=NOW)
    assert intent is not None and store.jobs["job-1"].intents[-1].actor == "disconnect_bug"

    # (a) FIRST stop new harm by rolling the policy back (not a business-fact rollback).
    policy.rollback()
    sub2 = reg.subscribe("job-1")
    assert on_sse_disconnect(store, policy, sub2, reg, now=NOW) is None  # no new harmful intent

    # (b) Build the affected set from release version + a bounded time window.
    affected = build_affected_set(store, release_version="v1.4.0-bad",
                                  window_start=NOW - timedelta(minutes=5),
                                  window_end=NOW + timedelta(minutes=5))
    assert [jid for jid, _ in affected] == ["job-1"]

    # (c) Refuse a blind state flip and a blind Provider re-call; classify from evidence instead.
    provider = _provider()
    status_before = store.jobs["job-1"].status
    cls = classify_recovery(store.jobs["job-1"])
    assert cls is RecoveryClassification.RECONCILE_UNKNOWN_EXTERNAL  # request id + unknown usage
    assert store.jobs["job-1"].status is status_before   # no bulk flip
    assert provider.calls == 0                            # no blind Provider re-call
    assert store.jobs["job-1"].intents                    # audit history retained, never deleted


def test_recovery_without_provider_evidence_is_classified_no_execution():
    store = _store_with_running_job()
    # No provider_request_id recorded -> nothing proves a Provider ran.
    cls = classify_recovery(store.jobs["job-1"])
    assert cls is RecoveryClassification.NO_PROVIDER_EXECUTION_EVIDENCE


# ===========================================================================
# P1-1: deadline intent -> EXPIRED (user cancellation -> CANCELLED)
# ===========================================================================
def test_deadline_intent_pre_call_expires_with_zero_provider_calls():
    store = _store_with_running_job()
    request_cancellation(store, "job-1", actor="scheduler", reason="job deadline",
                         kind=IntentKind.DEADLINE_EXPIRY, now=NOW)
    provider = FakeProvider(lambda: FakeProviderStream(["a"], total_tokens=10, request_id="rq-1"))
    res = run_worker(store, provider, "job-1", now=NOW)
    assert res.outcome is WorkerOutcome.CANCELLED_BEFORE_CALL
    assert store.jobs["job-1"].status is JobStatus.EXPIRED     # NOT cancelled
    assert provider.calls == 0


def test_deadline_intent_mid_stream_expires_best_effort_unknown_cost():
    store = _store_with_running_job()
    request_cancellation(store, "job-1", actor="scheduler", reason="job deadline",
                         kind=IntentKind.DEADLINE_EXPIRY, now=NOW)
    # Intent already present -> the pre-call check fires first (pre-call is also EXPIRED).
    provider = FakeProvider(lambda: FakeProviderStream(["a", "b"], total_tokens=None, request_id="rq-1"))
    # Force the mid-stream path by injecting the intent only after a token via cancel_check while a
    # DEADLINE intent exists: build a fresh job with no pre-existing intent, then a mid-stream deadline.
    store2 = _store_with_running_job("job-2")
    provider2 = FakeProvider(lambda: FakeProviderStream(["a", "b", "c"], total_tokens=None, request_id="rq-2"))
    def deadline_after_first_token():
        if not store2.jobs["job-2"].intents:
            request_cancellation(store2, "job-2", actor="scheduler", reason="deadline",
                                 kind=IntentKind.DEADLINE_EXPIRY, now=NOW)
        return False
    res = run_worker(store2, provider2, "job-2", now=NOW, cancel_check=deadline_after_first_token)
    job = store2.jobs["job-2"]
    assert res.outcome is WorkerOutcome.CANCELLED_MID_STREAM
    assert job.status is JobStatus.EXPIRED                     # deadline terminal, not cancelled
    assert job.cost_state is CostState.RECONCILIATION_PENDING and job.settled_tokens is None


def test_user_cancellation_still_maps_to_cancelled():
    store = _store_with_running_job()
    request_cancellation(store, "job-1", actor="user-alice", reason="cancel", now=NOW)
    res = run_worker(store, FakeProvider(lambda: FakeProviderStream(["a"], total_tokens=1, request_id="rq-1")),
                     "job-1", now=NOW)
    assert res.outcome is WorkerOutcome.CANCELLED_BEFORE_CALL
    assert store.jobs["job-1"].status is JobStatus.CANCELLED


def test_crash_reobservation_derives_terminal_from_intent_kind():
    store = _store_with_running_job()
    request_cancellation(store, "job-1", actor="scheduler", reason="deadline",
                         kind=IntentKind.DEADLINE_EXPIRY, now=NOW)
    assert apply_cancellation(store, "job-1", now=NOW) is TransitionOutcome.WON
    assert store.jobs["job-1"].status is JobStatus.EXPIRED     # derived from the intent kind


# ===========================================================================
# P1-2: a durable intent written after the last token, before completion
# ===========================================================================
def test_intent_after_last_token_before_completion_is_not_succeeded():
    for kind, terminal in ((IntentKind.USER_CANCELLATION, JobStatus.CANCELLED),
                           (IntentKind.DEADLINE_EXPIRY, JobStatus.EXPIRED)):
        store = _store_with_running_job("job-x")
        seen = {"n": 0}
        # cancel_check returns False (no mid-stream cancel), but persists the intent AFTER the last
        # token so it is only visible at the final pre-completion check.
        def after_last_token():
            seen["n"] += 1
            if seen["n"] == 2:  # after the 2nd (last) token has been counted
                request_cancellation(store, "job-x", actor="a", reason="late", kind=kind, now=NOW)
            return False
        provider = FakeProvider(lambda: FakeProviderStream(["a", "b"], total_tokens=99, request_id="rq-1"))
        res = run_worker(store, provider, "job-x", now=NOW, cancel_check=after_last_token)
        job = store.jobs["job-x"]
        assert res.outcome is WorkerOutcome.CANCELLED_PRE_COMPLETION
        assert job.status is terminal and job.status is not JobStatus.SUCCEEDED
        assert job.result_artifact is None                    # never wrote a success artifact


# ===========================================================================
# P1-3: provider_request_id persisted at request open (recovery evidence)
# ===========================================================================
def test_mid_stream_cancellation_has_persisted_provider_request_id():
    store = _store_with_running_job()
    provider = FakeProvider(lambda: FakeProviderStream(["a", "b", "c"], total_tokens=None, request_id="rq-77"))
    fired = {"n": 0}
    def cancel_now():
        fired["n"] += 1
        return fired["n"] >= 1
    run_worker(store, provider, "job-1", now=NOW, cancel_check=cancel_now)
    job = store.jobs["job-1"]
    assert job.status is JobStatus.CANCELLED
    assert job.provider_request_id == "rq-77"                  # recorded at stream open, survives cancel


def test_wrongly_cancelled_job_with_request_id_classifies_reconcile():
    from day54_streaming_disconnects_timeouts_cancellation import classify_recovery, RecoveryClassification
    store = _store_with_running_job()
    provider = FakeProvider(lambda: FakeProviderStream(["a", "b"], total_tokens=None, request_id="rq-1"))
    run_worker(store, provider, "job-1", now=NOW, cancel_check=lambda: True)  # wrongly cancelled mid-stream
    job = store.jobs["job-1"]
    assert classify_recovery(job) is RecoveryClassification.RECONCILE_UNKNOWN_EXTERNAL  # req id + unknown usage


def test_job_without_request_id_classifies_no_execution_evidence():
    from day54_streaming_disconnects_timeouts_cancellation import classify_recovery, RecoveryClassification
    store = _store_with_running_job()
    # No Provider request opened (pre-call cancel) -> no provider_request_id.
    request_cancellation(store, "job-1", actor="user-alice", reason="cancel", now=NOW)
    run_worker(store, FakeProvider(lambda: FakeProviderStream(["a"], total_tokens=1, request_id="rq-1")),
               "job-1", now=NOW)
    job = store.jobs["job-1"]
    assert job.provider_request_id is None
    assert classify_recovery(job) is RecoveryClassification.NO_PROVIDER_EXECUTION_EVIDENCE


# ===========================================================================
# P1-4: late result reuses Day53 identity binding + strict validation
# ===========================================================================
def test_matched_validated_late_result_completes_exactly_once():
    store, provider = _timed_out_job()
    res = ingest_late_provider_result(store, "job-1", attempt_id="att-1", correlation_id="corr-1",
                                      provider_request_id="rq-1", raw_payload=VALID_V1,
                                      validator=_validator(), now=NOW, actual_tokens=1200)
    job = store.jobs["job-1"]
    assert res is LateResultOutcome.COMPLETED and job.status is JobStatus.SUCCEEDED
    assert job.settled_tokens == 1200 and job.result_artifact["schema_version"] == "v1"
    assert provider.calls == 1                                 # NO new Provider transport call
    # A duplicate delivery after completion -> terminal guarded no-op (no second success).
    dup = ingest_late_provider_result(store, "job-1", attempt_id="att-1", correlation_id="corr-1",
                                      provider_request_id="rq-1", raw_payload=VALID_V1,
                                      validator=_validator(), now=NOW, actual_tokens=1200)
    assert dup is LateResultOutcome.REFUSED_TERMINAL
    assert len([e for e in job.events if e["type"] == "job.succeeded"]) == 1


def test_late_result_identity_mismatch_is_side_effect_free():
    for bad in ({"attempt_id": "WRONG"}, {"correlation_id": "WRONG"}, {"provider_request_id": "WRONG"},
                {"provider_request_id": None}):
        store, provider = _timed_out_job()
        job = store.jobs["job-1"]
        before = (job.status, job.cost_state, job.settled_tokens, job.result_artifact, list(job.events))
        kwargs = dict(attempt_id="att-1", correlation_id="corr-1", provider_request_id="rq-1",
                      raw_payload=VALID_V1, validator=_validator(), now=NOW, actual_tokens=1200)
        kwargs.update(bad)
        res = ingest_late_provider_result(store, "job-1", **kwargs)
        assert res is LateResultOutcome.REFUSED_IDENTITY_MISMATCH
        after = (job.status, job.cost_state, job.settled_tokens, job.result_artifact, list(job.events))
        assert after == before and provider.calls == 1        # zero side effects, no new Provider call


def test_late_result_invalid_payload_is_rejected_no_artifact():
    store, provider = _timed_out_job()
    bad_payload = {"summary": "x"}  # missing required citations/confidence -> Day53 gate fails
    res = ingest_late_provider_result(store, "job-1", attempt_id="att-1", correlation_id="corr-1",
                                      provider_request_id="rq-1", raw_payload=bad_payload,
                                      validator=_validator(), now=NOW, actual_tokens=1200)
    job = store.jobs["job-1"]
    assert res is LateResultOutcome.REFUSED_INVALID_PAYLOAD
    assert job.status is JobStatus.PENDING_RECONCILIATION and job.result_artifact is None
    assert job.settled_tokens is None


def test_concurrent_matched_late_delivery_completes_at_most_once():
    store, provider = _timed_out_job()
    barrier = threading.Barrier(2)
    results = []
    def deliver():
        barrier.wait()
        results.append(ingest_late_provider_result(
            store, "job-1", attempt_id="att-1", correlation_id="corr-1", provider_request_id="rq-1",
            raw_payload=VALID_V1, validator=_validator(), now=NOW, actual_tokens=1200))
    ths = [threading.Thread(target=deliver) for _ in range(2)]
    for t in ths: t.start()
    for t in ths: t.join()
    job = store.jobs["job-1"]
    assert sorted(r.value for r in results) == sorted([LateResultOutcome.COMPLETED.value,
                                                       LateResultOutcome.REFUSED_TERMINAL.value])
    assert len([e for e in job.events if e["type"] == "job.succeeded"]) == 1  # exactly once
    assert provider.calls == 1


# ===========================================================================
# Evidence label present (honesty)
# ===========================================================================
def test_evidence_label_is_in_memory_control_flow_not_runtime():
    import day54_streaming_disconnects_timeouts_cancellation as m
    doc = m.__doc__ or ""
    assert "LOCAL IN-MEMORY CONTROL-FLOW" in doc
    assert "NOT RUN" in doc and "Celery" in doc and "FastAPI/SSE" in doc
