"""Day56 tests — Provider resilience, rate limits, token cost, backpressure (in-memory control flow).

These prove APPLICATION CONTROL FLOW over an in-memory model of the admission-to-Provider control
plane. They do NOT prove a real Celery broker/Worker, a real Redis distributed limiter/circuit,
real PostgreSQL, real Provider traffic/rate limits/costs, load, Worker-kill fault injection, or
production.
"""
import threading
from datetime import datetime, timedelta, timezone

import pytest

from day54_streaming_disconnects_timeouts_cancellation import IntentKind
from day56_provider_resilience import (
    AdmissionDecision, Attempt, CircuitBreaker, CircuitState, CostState, DeferRecord,
    ExecutionCertainty, ExecutionContract, Job, JobStatus, OutboxDispatchIntent, ProviderAction,
    RepairAction, RepairOutcome, ReleaseConfig, SettleOutcome, SharedRateLimiter, TenantBudgetLedger,
    admit_job, apply_authorized_degradation, backoff_delay_seconds, build_capacity_expiry_affected_set,
    can_ordinary_retry, classify_execution_certainty, classify_incident_repair, compute_next_attempt_at,
    evaluate_dispatch, process_deadline, repair_id_for, repair_redispatch, terminal_for_intent,
)

NOW = datetime(2026, 8, 6, 12, 0, 0, tzinfo=timezone.utc)


def _contract(**kw):
    base = dict(provider="openai", account="acct1", model="gpt-x", region="us",
                max_tokens=1000, output_price_per_1k=0.01, max_input_tokens=0, input_price_per_1k=0.0)
    base.update(kw)
    return ExecutionContract(**base)


def _job(ledger=None, *, tenant="t1", deadline_minutes=30, reserve=True, **ckw):
    c = _contract(**ckw)
    j = Job(job_id="job-1", tenant_id=tenant, contract=c, status=JobStatus.RUNNING,
            deadline=NOW + timedelta(minutes=deadline_minutes))
    if ledger is not None and reserve:
        assert ledger.reserve_worst_case(j)
    return j


def _ready_deps(balance=100.0, capacity=10, available=True):
    return (SharedRateLimiter(capacity, available=available),
            TenantBudgetLedger({"t1": balance}),
            CircuitBreaker())


# --- 1. bounded retry + jitter --------------------------------------------
def test_backoff_is_bounded_and_jittered():
    # cap bounds growth; full jitter keeps values within [0, raw].
    hi = backoff_delay_seconds(20, base=1.0, cap=30.0, rand=lambda: 1.0)
    lo = backoff_delay_seconds(20, base=1.0, cap=30.0, rand=lambda: 0.0)
    assert hi == 30.0 and lo == 0.0            # bounded by cap; jitter spreads across [0, cap]


def test_retry_after_is_earliest_floor_with_jitter_above_it():
    # Retry-After 100s is the FLOOR; different random draws must yield DIFFERENT times, all >= floor,
    # so a fleet does not wake at the same instant (P1-1).
    floor = NOW + timedelta(seconds=100)
    t0 = compute_next_attempt_at(NOW, 1, retry_after_seconds=100, rand=lambda: 0.0)
    t_mid = compute_next_attempt_at(NOW, 1, retry_after_seconds=100, rand=lambda: 0.5)
    t_hi = compute_next_attempt_at(NOW, 1, retry_after_seconds=100, rand=lambda: 1.0)
    assert t0 >= floor and t_mid >= floor and t_hi >= floor   # never earlier than the floor
    assert t0 < t_mid < t_hi                                  # bounded jitter spreads the fleet
    # an explicit jitter window is honored and stays bounded
    tw = compute_next_attempt_at(NOW, 1, retry_after_seconds=100, rand=lambda: 1.0,
                                 jitter_window_seconds=10)
    assert tw == floor + timedelta(seconds=10)


# --- 2. guarded claim vs rate permit: shared quota across simulated workers ---
def test_shared_limiter_caps_fleet_concurrency_across_workers():
    limiter = SharedRateLimiter(3)
    grants = [limiter.try_acquire() for _ in range(5)]     # 5 "workers" try to call
    assert grants == [True, True, True, False, False]      # only fleet capacity=3 may call now
    limiter.release()
    assert limiter.try_acquire() is True                   # a freed permit lets one more through


def test_all_gates_pass_yields_call_and_consumes_one_permit():
    limiter, ledger, circuit = _ready_deps(capacity=2)
    job = _job(ledger)
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=NOW)
    assert d.action is ProviderAction.CALL
    assert limiter.in_flight == 1


# --- 3. no-permit-before-call is DEFER (not FAILED / not PENDING_RECONCILIATION) ---
def test_no_capacity_defers_with_zero_provider_calls_and_no_execution_retry():
    limiter, ledger, circuit = _ready_deps(capacity=0)     # no capacity at all
    job = _job(ledger)
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=NOW,
                          rand=lambda: 0.0)
    assert d.action is ProviderAction.DEFER
    assert d.reason == "no_rate_capacity"
    assert job.status is JobStatus.DEFERRED
    assert job.defer is not None and job.defer.next_attempt_at is not None
    assert job.defer_count == 1
    assert job.execution_retry_count == 0                  # a defer consumes NO execution retry


def test_defer_never_scheduled_past_deadline():
    limiter, ledger, circuit = _ready_deps(capacity=0)
    job = _job(ledger, deadline_minutes=0)                 # deadline == NOW
    # deadline reached -> TERMINAL EXPIRED before any defer
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=NOW)
    assert d.action is ProviderAction.TERMINAL
    assert d.terminal_status is JobStatus.EXPIRED


# --- 4. limiter outage defaults to fail closed (defer), fail-open only explicit ---
def test_limiter_outage_fails_closed_by_default():
    limiter, ledger, circuit = _ready_deps(available=False)
    job = _job(ledger)
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=NOW,
                          rand=lambda: 0.0)
    assert d.action is ProviderAction.DEFER
    assert d.reason == "limiter_unavailable_fail_closed"


def test_limiter_outage_emergency_fail_open_is_explicit_policy():
    limiter, ledger, circuit = _ready_deps(available=False)
    job = _job(ledger)
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=NOW,
                          emergency_fail_open=True)
    assert d.action is ProviderAction.CALL                 # only because the policy is explicit


# --- 5. cost reservation: worst-case, settle actual, release unused -------
def test_reserve_worst_case_not_remaining_balance():
    ledger = TenantBudgetLedger({"t1": 100.0})
    job = _job(ledger, max_tokens=2000, output_price_per_1k=0.5)   # output worst case = 1.0
    assert job.reserved_cost == 1.0
    assert ledger.available("t1") == 99.0                  # only worst-case reserved, not the balance


def test_worst_case_cost_includes_bounded_input_and_output():
    # input 1000 tok @ 0.03 = 0.03 ; output 500 tok @ 0.06 = 0.03 ; total = 0.06 (P1-3)
    ledger = TenantBudgetLedger({"t1": 1.0})
    job = _job(ledger, max_tokens=500, output_price_per_1k=0.06,
               max_input_tokens=1000, input_price_per_1k=0.03)
    assert job.contract.worst_case_cost() == 0.06
    assert job.reserved_cost == 0.06
    assert ledger.available("t1") == 0.94                  # both input and output are reserved


def test_settle_actual_releases_unused_money_to_ledger_not_limiter():
    ledger = TenantBudgetLedger({"t1": 10.0})
    job = _job(ledger, max_tokens=1000, output_price_per_1k=1.0)   # worst case = 1.0
    assert ledger.available("t1") == 9.0
    out = ledger.settle_actual(job, actual_cost=0.4)
    assert out is SettleOutcome.SETTLED
    assert job.cost_state is CostState.SETTLED
    assert ledger.available("t1") == 9.6                   # 0.6 unused returned to the budget ledger


def test_settle_actual_over_reservation_does_not_bypass_budget():
    # actual > reserved must NOT silently deduct more than reserved (P1-3): protected reconciliation.
    ledger = TenantBudgetLedger({"t1": 10.0})
    job = _job(ledger, max_tokens=1000, output_price_per_1k=1.0)   # worst case = 1.0 reserved
    assert ledger.available("t1") == 9.0
    out = ledger.settle_actual(job, actual_cost=1.6)               # over the reservation
    assert out is SettleOutcome.OVERAGE_RECONCILE
    assert job.settled_cost == 1.0                                 # charged only what was reserved
    assert job.cost_overage == 0.6                                 # excess flagged, not auto-charged
    assert job.cost_state is CostState.RECONCILIATION_PENDING
    assert ledger.available("t1") == 9.0                           # tenant NOT overdrawn silently


def test_budget_blocked_pre_call_cannot_reserve():
    ledger = TenantBudgetLedger({"t1": 0.5})
    job = Job(job_id="job-1", tenant_id="t1", contract=_contract(max_tokens=1000, output_price_per_1k=1.0),
              status=JobStatus.RUNNING, deadline=NOW + timedelta(minutes=30))
    assert ledger.reserve_worst_case(job) is False         # worst case 1.0 > balance 0.5 -> do not call


def test_missing_reservation_defers_and_returns_permit():
    limiter, ledger, circuit = _ready_deps(capacity=1)
    job = _job(ledger, reserve=False)                      # no reservation made
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=NOW,
                          rand=lambda: 0.0)
    assert d.action is ProviderAction.DEFER
    assert d.reason == "no_cost_reservation"
    assert limiter.in_flight == 0                          # the permit was returned, not leaked


# --- 6. backpressure at admission: 429 tenant vs 503 system ---------------
def test_admission_backpressure_maps_429_and_503():
    assert admit_job(tenant_over_quota=False, system_unavailable=False) is AdmissionDecision.ACCEPT
    assert admit_job(tenant_over_quota=True, system_unavailable=False) is AdmissionDecision.REJECT_429_TENANT
    assert admit_job(tenant_over_quota=False, system_unavailable=True) is AdmissionDecision.REJECT_503_SYSTEM
    # system-wide unavailability dominates
    assert admit_job(tenant_over_quota=True, system_unavailable=True) is AdmissionDecision.REJECT_503_SYSTEM


# --- 7. degradation only if the persisted contract authorizes it ----------
def test_silent_degradation_rejected():
    c = _contract(degradation_allowed=False)
    with pytest.raises(ValueError):
        apply_authorized_degradation(c, target_model="gpt-mini", target_max_tokens=500)


def test_authorized_degradation_within_floor_allowed():
    c = _contract(model="gpt-x", max_tokens=1000, degradation_allowed=True,
                  min_model="gpt-mini", min_max_tokens=400)
    d = apply_authorized_degradation(c, target_model="gpt-mini", target_max_tokens=500)
    assert d.model == "gpt-mini" and d.max_tokens == 500
    with pytest.raises(ValueError):
        apply_authorized_degradation(c, target_model="gpt-mini", target_max_tokens=100)  # below floor


# --- 8. execution certainty: a 429 is not universal proof -----------------
def test_execution_certainty_classification():
    assert classify_execution_certainty(http_status=429, provider_request_id=None,
                                         accepted_header=False) is ExecutionCertainty.DEFINITELY_NOT_ACCEPTED
    assert classify_execution_certainty(http_status=429, provider_request_id="req-1") is ExecutionCertainty.MAY_HAVE_EXECUTED
    assert classify_execution_certainty(http_status=429, provider_request_id=None) is ExecutionCertainty.UNKNOWN
    assert classify_execution_certainty(http_status=503, provider_request_id=None) is ExecutionCertainty.UNKNOWN
    assert can_ordinary_retry(ExecutionCertainty.DEFINITELY_NOT_ACCEPTED) is True
    assert can_ordinary_retry(ExecutionCertainty.UNKNOWN) is False
    assert can_ordinary_retry(ExecutionCertainty.MAY_HAVE_EXECUTED) is False


def test_provider_evidence_forces_reconcile_not_call():
    limiter, ledger, circuit = _ready_deps()
    job = _job(ledger)
    job.attempt = Attempt(attempt_id="a1", job_id="job-1", provider_idempotency_key="pik",
                          correlation_id="cor", provider_request_id="req-1")
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=NOW)
    assert d.action is ProviderAction.RECONCILE
    assert limiter.in_flight == 0                          # no permit consumed for a reconcile


def test_dispatch_marker_only_also_reconciles():
    limiter, ledger, circuit = _ready_deps()
    job = _job(ledger)
    job.attempt = Attempt(attempt_id="a1", job_id="job-1", provider_idempotency_key="pik",
                          correlation_id="cor", provider_dispatch_started_at=NOW)
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=NOW)
    assert d.action is ProviderAction.RECONCILE            # conservative marker -> reconcile (Day55 P1)


# --- 9. circuit breaker OPEN / HALF_OPEN progressive recovery --------------
def test_circuit_open_defers_new_calls():
    limiter, ledger, circuit = _ready_deps()
    job = _job(ledger)
    key = job.contract.circuit_key()
    for _ in range(5):
        circuit.record_failure(key)
    assert circuit.state(key) is CircuitState.OPEN
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=NOW, rand=lambda: 0.0)
    assert d.action is ProviderAction.DEFER and d.reason == "circuit_open"


def test_half_open_allows_bounded_probes_not_herd_release():
    limiter, ledger, circuit = _ready_deps(capacity=10)
    key = _contract().circuit_key()
    for _ in range(5):
        circuit.record_failure(key)
    circuit.start_half_open(key)
    # only half_open_max_probes (2) jobs may probe; a 3rd defers (no herd release)
    actions = []
    for i in range(3):
        j = _job(ledger := TenantBudgetLedger({"t1": 100.0}))
        actions.append(evaluate_dispatch(j, limiter=limiter, ledger=ledger, circuit=circuit,
                                         now=NOW, rand=lambda: 0.0).action)
    assert actions.count(ProviderAction.CALL) == 2
    assert actions.count(ProviderAction.DEFER) == 1


def test_single_probe_success_does_not_close_circuit():
    circuit = CircuitBreaker(half_open_max_probes=2)
    key = _contract().circuit_key()
    for _ in range(5):
        circuit.record_failure(key)
    circuit.start_half_open(key)
    circuit.allow_probe(key)
    circuit.record_probe_success(key, needed_to_close=2)   # ONE success
    assert circuit.state(key) is CircuitState.HALF_OPEN     # still half-open, not closed
    circuit.allow_probe(key)
    circuit.record_probe_success(key, needed_to_close=2)   # a SECOND success -> progressive close
    assert circuit.state(key) is CircuitState.CLOSED


# --- 10. cancellation / terminal outrank ordinary retry; re-check on wake --
def test_cancellation_intent_outranks_capacity_retry():
    limiter, ledger, circuit = _ready_deps(capacity=0)     # even with no capacity...
    job = _job(ledger)
    job.intent_kind = IntentKind.USER_CANCELLATION         # a durable cancel intent exists
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=NOW)
    assert d.action is ProviderAction.TERMINAL
    assert d.terminal_status is JobStatus.CANCELLED        # cancellation, not a defer


def test_deferred_job_waking_to_terminal_status_is_noop():
    limiter, ledger, circuit = _ready_deps()
    job = _job(ledger)
    job.status = JobStatus.CANCELLED                       # already terminal when it wakes
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=NOW)
    assert d.action is ProviderAction.NOOP


# --- 11. deadline expiry + safe reservation release only w/o evidence -----
def test_deadline_expiry_releases_reservation_when_no_execution():
    ledger = TenantBudgetLedger({"t1": 10.0})
    job = _job(ledger, max_tokens=1000, output_price_per_1k=1.0)
    assert ledger.available("t1") == 9.0
    d = process_deadline(job, ledger)
    assert d.action is ProviderAction.TERMINAL and d.terminal_status is JobStatus.EXPIRED
    assert ledger.available("t1") == 10.0                  # money returned (proven no execution)


def test_deadline_with_execution_evidence_reconciles_and_holds_reservation():
    ledger = TenantBudgetLedger({"t1": 10.0})
    job = _job(ledger, max_tokens=1000, output_price_per_1k=1.0)
    job.attempt = Attempt(attempt_id="a1", job_id="job-1", provider_idempotency_key="pik",
                          correlation_id="cor", provider_request_id="req-1")
    d = process_deadline(job, ledger)
    assert d.action is ProviderAction.RECONCILE
    assert job.status is JobStatus.PENDING_RECONCILIATION
    assert job.cost_state is CostState.RECONCILIATION_PENDING
    assert ledger.available("t1") == 9.0                   # reservation HELD, not released


# --- 12. zero-defer incident: containment + evidence-based repair ---------
def test_config_rollback_is_not_business_fact_rollback():
    cfg = ReleaseConfig("bad-r2", max_defer_seconds=0)
    cfg.rollback(safe_max_defer_seconds=3600)
    assert cfg.max_defer_seconds == 3600                   # future harm stopped; expired Jobs untouched


def _expired_capacity_job(job_id, release, when, *, evidence=False):
    j = Job(job_id=job_id, tenant_id="t1", contract=_contract(), status=JobStatus.EXPIRED,
            deadline=NOW + timedelta(hours=1), release_version=release)
    j.defer = DeferRecord(retry_reason="defer_deadline_expired", next_attempt_at=when,
                          defer_count=1, deadline=NOW + timedelta(hours=1))
    if evidence:
        j.attempt = Attempt(attempt_id="a", job_id=job_id, provider_idempotency_key="p",
                            correlation_id="c", provider_request_id="req")
    return j


def test_affected_set_bounded_by_release_window_reason():
    jobs = [
        _expired_capacity_job("in", "bad-r2", NOW),                          # in window, bad release
        _expired_capacity_job("out", "bad-r2", NOW - timedelta(hours=3)),    # out of window
        _expired_capacity_job("other", "good-r1", NOW),                      # other release
    ]
    affected = build_capacity_expiry_affected_set(
        jobs, release_version="bad-r2",
        window_start=NOW - timedelta(minutes=30), window_end=NOW + timedelta(minutes=30))
    assert affected == ["in"]


def _repair_deps(balance=10.0):
    return [], {}, TenantBudgetLedger({"t1": balance})     # outbox, repair_ledger, budget ledger


def test_repair_redispatches_only_no_evidence_valid_jobs_via_new_outbox_intent():
    outbox, rledger, ledger = _repair_deps()
    clean = _expired_capacity_job("clean", "bad-r2", NOW)
    assert classify_incident_repair(clean, now=NOW) is RepairAction.REDISPATCH_NEW_OUTBOX_INTENT
    out = repair_redispatch(clean, outbox, rledger, ledger, now=NOW,
                            affected_set={"clean"}, release_version="bad-r2")
    assert out is RepairOutcome.REDISPATCHED
    assert clean.status is JobStatus.QUEUED                # re-opened
    assert clean.repair_history and clean.repair_history[0]["was_status"] == "expired"  # EXPIRED preserved
    assert len(outbox) == 1 and outbox[0].job_id == "clean"
    assert ledger.has_reservation(clean)                   # a fresh worst-case reservation was made


def test_repair_is_idempotent_one_intent_for_duplicate_calls():
    outbox, rledger, ledger = _repair_deps()
    clean = _expired_capacity_job("clean", "bad-r2", NOW)
    a = repair_redispatch(clean, outbox, rledger, ledger, now=NOW,
                          affected_set={"clean"}, release_version="bad-r2")
    # a duplicate / concurrent repair with the same identity must NOT write a second intent
    b = repair_redispatch(clean, outbox, rledger, ledger, now=NOW,
                          affected_set={"clean"}, release_version="bad-r2")
    assert a is RepairOutcome.REDISPATCHED and b is RepairOutcome.ALREADY_APPLIED
    assert len(outbox) == 1                                # exactly one Outbox dispatch intent
    assert outbox[0].repair_id == repair_id_for(clean, release_version="bad-r2")
    assert ledger.available("t1") == 10.0 - clean.reserved_cost   # reserved exactly once


def test_repair_reconcile_only_when_provider_evidence():
    outbox, rledger, ledger = _repair_deps()
    dirty = _expired_capacity_job("dirty", "bad-r2", NOW, evidence=True)
    assert classify_incident_repair(dirty, now=NOW) is RepairAction.RECONCILE_ONLY
    out = repair_redispatch(dirty, outbox, rledger, ledger, now=NOW,
                            affected_set={"dirty"}, release_version="bad-r2")
    assert out is RepairOutcome.BLOCKED_PROVIDER_EVIDENCE
    assert outbox == [] and dirty.status is JobStatus.EXPIRED   # never blind re-dispatch, history intact


def test_repair_blocked_by_cancellation_intent():
    outbox, rledger, ledger = _repair_deps()
    j = _expired_capacity_job("c", "bad-r2", NOW)
    j.intent_kind = IntentKind.USER_CANCELLATION
    out = repair_redispatch(j, outbox, rledger, ledger, now=NOW,
                            affected_set={"c"}, release_version="bad-r2")
    assert out is RepairOutcome.BLOCKED_CANCELLED and outbox == []


def test_repair_blocked_by_passed_deadline():
    outbox, rledger, ledger = _repair_deps()
    j = _expired_capacity_job("d", "bad-r2", NOW)
    j.deadline = NOW - timedelta(minutes=1)               # commitment no longer valid
    out = repair_redispatch(j, outbox, rledger, ledger, now=NOW,
                            affected_set={"d"}, release_version="bad-r2")
    assert out is RepairOutcome.BLOCKED_DEADLINE_PASSED and outbox == []


def test_repair_blocked_by_insufficient_budget():
    outbox, rledger, ledger = _repair_deps(balance=0.0)   # cannot re-fund the worst case
    j = _expired_capacity_job("b", "bad-r2", NOW)
    out = repair_redispatch(j, outbox, rledger, ledger, now=NOW,
                            affected_set={"b"}, release_version="bad-r2")
    assert out is RepairOutcome.BLOCKED_BUDGET and outbox == [] and j.status is JobStatus.EXPIRED


def test_repair_blocked_when_not_in_affected_set():
    outbox, rledger, ledger = _repair_deps()
    j = _expired_capacity_job("x", "bad-r2", NOW)
    out = repair_redispatch(j, outbox, rledger, ledger, now=NOW,
                            affected_set=set(), release_version="bad-r2")
    assert out is RepairOutcome.BLOCKED_NOT_IN_AFFECTED_SET and outbox == []


def test_repair_blocked_when_status_not_expired():
    outbox, rledger, ledger = _repair_deps()
    j = _expired_capacity_job("s", "bad-r2", NOW)
    j.status = JobStatus.SUCCEEDED                        # already resolved another way
    out = repair_redispatch(j, outbox, rledger, ledger, now=NOW,
                            affected_set={"s"}, release_version="bad-r2")
    assert out is RepairOutcome.BLOCKED_WRONG_STATUS and outbox == []


def test_repair_reconcile_only_when_deadline_passed():
    past = Job(job_id="late", tenant_id="t1", contract=_contract(), status=JobStatus.EXPIRED,
               deadline=NOW - timedelta(minutes=1), release_version="bad-r2")
    assert classify_incident_repair(past, now=NOW) is RepairAction.RECONCILE_ONLY


# --- terminal mapping sanity ----------------------------------------------
def test_terminal_for_intent_mapping():
    assert terminal_for_intent(IntentKind.USER_CANCELLATION) is JobStatus.CANCELLED
    assert terminal_for_intent(IntentKind.DEADLINE_EXPIRY) is JobStatus.EXPIRED


# ===========================================================================
# P1-2 regression: a HALF_OPEN probe slot must not leak when the Job DEFERs
# ===========================================================================
def _half_open_circuit():
    c = CircuitBreaker(half_open_max_probes=1)
    key = _contract().circuit_key()
    for _ in range(5):
        c.record_failure(key)
    c.start_half_open(key)
    return c, key


def test_half_open_no_capacity_defer_does_not_leak_probe_slot():
    circuit, key = _half_open_circuit()
    ledger = TenantBudgetLedger({"t1": 100.0})
    limiter0 = SharedRateLimiter(0)                        # no capacity -> DEFER
    job = _job(ledger)
    d = evaluate_dispatch(job, limiter=limiter0, ledger=ledger, circuit=circuit, now=NOW,
                          rand=lambda: 0.0)
    assert d.action is ProviderAction.DEFER
    assert circuit.has_probe_capacity(key) is True        # slot NOT consumed by a non-call
    # a subsequent healthy Job can still take the single probe and CALL
    l2 = TenantBudgetLedger({"t1": 100.0})
    j2 = _job(l2)
    d2 = evaluate_dispatch(j2, limiter=SharedRateLimiter(1), ledger=l2, circuit=circuit, now=NOW)
    assert d2.action is ProviderAction.CALL


def test_half_open_limiter_outage_defer_does_not_leak_probe_slot():
    circuit, key = _half_open_circuit()
    ledger = TenantBudgetLedger({"t1": 100.0})
    job = _job(ledger)
    outage = SharedRateLimiter(5, available=False)         # limiter outage -> fail closed DEFER
    d = evaluate_dispatch(job, limiter=outage, ledger=ledger, circuit=circuit, now=NOW, rand=lambda: 0.0)
    assert d.action is ProviderAction.DEFER and d.reason == "limiter_unavailable_fail_closed"
    assert circuit.has_probe_capacity(key) is True         # slot not consumed


def test_half_open_missing_reservation_defer_does_not_leak_probe_slot():
    circuit, key = _half_open_circuit()
    limiter = SharedRateLimiter(1)
    job = _job(TenantBudgetLedger({"t1": 100.0}), reserve=False)   # no reservation -> DEFER
    ledger = TenantBudgetLedger({"t1": 100.0})             # ledger without this job's reservation
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=NOW, rand=lambda: 0.0)
    assert d.action is ProviderAction.DEFER and d.reason == "no_cost_reservation"
    assert circuit.has_probe_capacity(key) is True         # slot not consumed
    assert limiter.in_flight == 0                          # and the permit was returned


def test_half_open_call_consumes_probe_slot_only_on_call():
    circuit, key = _half_open_circuit()
    job = _job(l := TenantBudgetLedger({"t1": 100.0}))
    d = evaluate_dispatch(job, limiter=SharedRateLimiter(1), ledger=l, circuit=circuit, now=NOW)
    assert d.action is ProviderAction.CALL
    assert circuit.has_probe_capacity(key) is False        # the single probe slot is now taken


# ===========================================================================
# Concurrency regression (in-memory control-flow only; NOT PostgreSQL/Redis/Celery/prod)
# ===========================================================================
def test_half_open_probe_acquire_is_atomic_under_concurrency():
    """P1-1: two Workers race the HALF_OPEN check-and-acquire with a single probe slot. Exactly one
    must CALL and one must safely DEFER, and the loser must not leak its rate permit."""
    circuit = CircuitBreaker(half_open_max_probes=1)
    key = _contract().circuit_key()
    for _ in range(5):
        circuit.record_failure(key)
    circuit.start_half_open(key)
    limiter = SharedRateLimiter(10)                     # plenty of fleet capacity: probe slot is the scarce gate
    results = {}
    barrier = threading.Barrier(2)

    def worker(name):
        lg = TenantBudgetLedger({"t1": 100.0})
        job = _job(lg)                                  # each Worker its own Job + reserved ledger
        barrier.wait()                                  # maximize the real race window
        results[name] = evaluate_dispatch(job, limiter=limiter, ledger=lg, circuit=circuit,
                                          now=NOW, rand=lambda: 0.0).action

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start(); t2.start(); t1.join(); t2.join()

    actions = list(results.values())
    assert actions.count(ProviderAction.CALL) == 1     # never two probes past half_open_max_probes=1
    assert actions.count(ProviderAction.DEFER) == 1
    assert limiter.in_flight == 1                       # exactly one permit held; the loser released its permit


def test_repair_is_atomic_under_concurrency():
    """P1-2: two threads repair the SAME Job / repair id at once. Exactly one REDISPATCHED and one
    ALREADY_APPLIED, exactly one Outbox intent, and exactly one reservation."""
    outbox, rledger, ledger = [], {}, TenantBudgetLedger({"t1": 100.0})
    job = _expired_capacity_job("clean", "bad-r2", NOW)
    reserved = job.contract.worst_case_cost()
    results = {}
    barrier = threading.Barrier(2)

    def worker(name):
        barrier.wait()
        results[name] = repair_redispatch(job, outbox, rledger, ledger, now=NOW,
                                          affected_set={"clean"}, release_version="bad-r2")

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start(); t2.start(); t1.join(); t2.join()

    outs = list(results.values())
    assert outs.count(RepairOutcome.REDISPATCHED) == 1
    assert outs.count(RepairOutcome.ALREADY_APPLIED) == 1
    assert len(outbox) == 1                             # exactly one durable Outbox dispatch intent
    assert len(rledger) == 1                            # one committed repair id
    assert ledger.available("t1") == round(100.0 - reserved, 6)   # reserved exactly once
    assert job.status is JobStatus.QUEUED
    assert job.repair_history and job.repair_history[0]["was_status"] == "expired"  # EXPIRED preserved


def _budget_job(job_id, **ckw):
    return Job(job_id=job_id, tenant_id="t1", contract=_contract(**ckw),
               status=JobStatus.RUNNING, deadline=NOW + timedelta(minutes=30))


def test_reserve_worst_case_is_atomic_under_concurrency():
    """P1: a tenant whose balance covers EXACTLY one Job's worst-case cost must not be overspent when
    two Jobs race reserve_worst_case. Exactly one reservation succeeds; the balance never goes
    negative; only one job_id is reserved."""
    worst = _contract().worst_case_cost()               # default contract worst-case = 0.01
    ledger = TenantBudgetLedger({"t1": worst})          # room for exactly ONE reservation
    jobA, jobB = _budget_job("job-A"), _budget_job("job-B")
    results = {}
    barrier = threading.Barrier(2)

    def worker(name, job):
        barrier.wait()                                  # maximize the real race window
        results[name] = ledger.reserve_worst_case(job)

    tA = threading.Thread(target=worker, args=("A", jobA))
    tB = threading.Thread(target=worker, args=("B", jobB))
    tA.start(); tB.start(); tA.join(); tB.join()

    assert list(results.values()).count(True) == 1      # exactly one succeeds
    assert list(results.values()).count(False) == 1     # the other fails
    assert ledger.available("t1") >= 0.0                # never negative
    assert ledger.available("t1") == 0.0                # the single winner consumed the whole balance
    assert len(ledger._reserved) == 1                   # only ONE job_id reserved

    winner, loser = (jobA, jobB) if results["A"] else (jobB, jobA)
    assert winner.reserved_cost == worst and winner.cost_state is CostState.RESERVED
    assert ledger.has_reservation(winner)
    assert loser.reserved_cost is None                  # loser got no reservation
    assert loser.cost_state is not CostState.RESERVED
    assert not ledger.has_reservation(loser)


def test_reserve_worst_case_idempotent_no_double_charge():
    worst = _contract().worst_case_cost()
    ledger = TenantBudgetLedger({"t1": 10.0})
    job = _budget_job("job-1")
    assert ledger.reserve_worst_case(job) is True
    after_first = ledger.available("t1")
    assert ledger.reserve_worst_case(job) is True       # same job_id again -> idempotent
    assert ledger.available("t1") == after_first        # NOT double-charged
    assert len(ledger._reserved) == 1


def test_concurrent_reserve_and_settle_stay_consistent():
    """Optional: a settle of one already-reserved Job racing a reserve of another Job keeps the
    ledger consistent (no lost update). In-memory threading only."""
    worst = _contract().worst_case_cost()
    ledger = TenantBudgetLedger({"t1": worst})          # only enough for one at a time
    reserved_job = _budget_job("job-R")
    assert ledger.reserve_worst_case(reserved_job) is True   # balance now 0
    new_job = _budget_job("job-N")
    results = {}
    barrier = threading.Barrier(2)

    def do_settle():
        barrier.wait()
        ledger.settle_actual(reserved_job, actual_cost=0.0)  # releases the full reservation back

    def do_reserve():
        barrier.wait()
        results["reserve"] = ledger.reserve_worst_case(new_job)

    t1 = threading.Thread(target=do_settle)
    t2 = threading.Thread(target=do_reserve)
    t1.start(); t2.start(); t1.join(); t2.join()

    # Regardless of interleaving the ledger is consistent: total money is conserved and non-negative.
    assert ledger.available("t1") >= 0.0
    # exactly the reservations that are still open sum to (initial - available)
    open_sum = round(sum(ledger._reserved.values()), 6)
    assert round(ledger.available("t1") + open_sum, 6) == worst
