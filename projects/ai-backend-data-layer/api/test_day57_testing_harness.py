"""Day57 tests — deterministic verification of the Day56 policies + failure injection.

EXECUTED_LOCAL_RUNTIME evidence only: these prove the deterministic application state machine, the
Adapter contract, and failure-injection CONTROL FLOW over in-memory doubles (plus Day53's real
pydantic validator). They do NOT prove real PostgreSQL rollback/isolation, real Celery broker
redelivery, real Worker-kill, a real Redis limiter/circuit, or real Provider behavior — see
VALIDATION_MATRIX / not_run_claims().
"""
import threading
from datetime import timedelta

import pytest

from day53_openai_provider_structured_output import SchemaRegistry, StructuredOutputValidator, ValidationOutcome
from day54_streaming_disconnects_timeouts_cancellation import IntentKind
from day56_provider_resilience import (
    Attempt, CircuitBreaker, CostState, ExecutionCertainty, ExecutionContract, Job, JobStatus,
    OutboxDispatchIntent, ProviderAction, RepairOutcome, SharedRateLimiter, TenantBudgetLedger,
    admit_job, AdmissionDecision, classify_execution_certainty, compute_next_attempt_at,
    evaluate_dispatch, process_deadline, repair_id_for, repair_redispatch,
)
from day57_testing_harness import (
    ControllableFakeProvider, DeterministicRandom, EvidenceTier, FakeClock, LateResult,
    LateResultOutcome, ProviderAdapter, ProviderCallLog, ScriptedResponse, VALIDATION_MATRIX,
    attempt_late_completion, not_run_claims,
)

VALID_PAYLOAD = {"summary": "ok", "citations": ["a"], "confidence": 0.9}


def _contract(**kw):
    base = dict(provider="openai", account="acct1", model="gpt-x", region="us",
                max_tokens=1000, output_price_per_1k=0.01, max_input_tokens=0, input_price_per_1k=0.0)
    base.update(kw)
    return ExecutionContract(**base)


def _attempt(job_id="job-1", *, request_id=None, marker=None):
    return Attempt(attempt_id="att-1", job_id=job_id, provider_idempotency_key="pik-1",
                   correlation_id="cor-1", provider_request_id=request_id,
                   provider_dispatch_started_at=marker)


def _job(clock, ledger=None, *, status=JobStatus.RUNNING, attempt=None, minutes=30):
    j = Job(job_id="job-1", tenant_id="t1", contract=_contract(), status=status,
            deadline=clock.now() + timedelta(minutes=minutes), attempt=attempt)
    if ledger is not None:
        ledger.reserve_worst_case(j)
    return j


def _ready(ledger_balance=100.0, capacity=10, available=True):
    return SharedRateLimiter(capacity, available=available), TenantBudgetLedger({"t1": ledger_balance}), CircuitBreaker()


# --- 10/11. deterministic backoff + jitter with Retry-After floor ----------
def test_deterministic_backoff_jitter_retry_after_is_floor_not_wake_all():
    clock = FakeClock()
    r_lo = DeterministicRandom([0.0])
    r_hi = DeterministicRandom([1.0])
    r_mid = DeterministicRandom([0.5])
    floor = clock.now() + timedelta(seconds=100)
    t_lo = compute_next_attempt_at(clock.now(), 1, retry_after_seconds=100, rand=r_lo)
    t_mid = compute_next_attempt_at(clock.now(), 1, retry_after_seconds=100, rand=r_mid)
    t_hi = compute_next_attempt_at(clock.now(), 1, retry_after_seconds=100, rand=r_hi)
    assert t_lo >= floor and t_mid >= floor and t_hi >= floor   # every wake at/after the floor
    assert t_lo < t_mid < t_hi                                  # controlled draws spread (no wake-all)


# --- 5. Adapter delivers application-owned typed outcomes (no SDK leakage) --
def test_adapter_classifies_execution_certainty_without_sdk_leakage():
    ad = ProviderAdapter()
    bare_429 = ad.to_outcome(ScriptedResponse(http_status=429))
    not_accepted = ad.to_outcome(ScriptedResponse(http_status=429, accepted=False))
    with_id = ad.to_outcome(ScriptedResponse(http_status=429, provider_request_id="req-1"))
    assert bare_429.execution_certainty is ExecutionCertainty.UNKNOWN
    assert not_accepted.execution_certainty is ExecutionCertainty.DEFINITELY_NOT_ACCEPTED
    assert with_id.execution_certainty is ExecutionCertainty.MAY_HAVE_EXECUTED
    assert bare_429.failure_kind == "rate_limited"
    # only safe metadata is exposed upward — no SDK exception classes / private fields
    assert set(bare_429.safe_metadata.keys()) == {"http_status"}


def test_adapter_does_not_touch_job_or_cost():
    _, ledger, _ = _ready()
    clock = FakeClock()
    job = _job(clock, ledger)
    before = ledger.available("t1")
    ProviderAdapter().to_outcome(ScriptedResponse(http_status=500))   # adapter must not write state/cost
    assert ledger.available("t1") == before
    assert job.cost_state is CostState.RESERVED


# --- 6. schema-contract violation is not business success -----------------
def test_valid_json_that_violates_bound_schema_is_contract_violation():
    v = StructuredOutputValidator(SchemaRegistry())
    bad = {"summary": "ok", "confidence": 0.9}          # missing required citations
    assert v.validate("research_summary", "v1", bad).outcome is ValidationOutcome.CONTRACT_VIOLATION


# --- 1/4. bare-429 unknown execution + dispatch-marker crash window ---------
def test_dispatch_marker_forces_reconcile_only_no_second_call():
    clock = FakeClock()
    limiter, ledger, circuit = _ready()
    att = _attempt(marker=clock.now())                  # dispatched, request_id not yet persisted
    job = _job(clock, ledger, attempt=att)
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=clock.now())
    assert d.action is ProviderAction.RECONCILE          # missing request id != no execution
    assert limiter.in_flight == 0                         # no rate permit consumed -> no second call
    assert job.cost_state is CostState.RESERVED           # reservation HELD


def test_provider_request_id_evidence_forces_reconcile_only():
    clock = FakeClock()
    limiter, ledger, circuit = _ready()
    job = _job(clock, ledger, attempt=_attempt(request_id="req-1"))
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=clock.now())
    assert d.action is ProviderAction.RECONCILE
    assert limiter.in_flight == 0


# --- 3/11. controllable Fake Provider gate (no sleep) ----------------------
def test_controllable_fake_provider_gate_opens_a_deterministic_timeout_window():
    provider = ControllableFakeProvider([ScriptedResponse(http_status=200, provider_request_id="req-1",
                                                          payload=dict(VALID_PAYLOAD))],
                                        auto_release=False)
    result_box = {}

    def worker():
        result_box["resp"] = provider.call(provider_idempotency_key="pik-1")

    t = threading.Thread(target=worker)
    t.start()
    assert provider.request_received.wait(timeout=2) is True   # the request arrived
    assert provider.calls == 1
    assert provider.call_log.count == 1                        # receipt recorded (survives a crash here)
    assert t.is_alive() is True                                # response gated open -> in-flight window
    assert "resp" not in result_box                            # nothing returned yet (no sleep needed)
    provider.release_response.set()                            # close the controlled window
    t.join(timeout=2)
    assert result_box["resp"].provider_request_id == "req-1"


def test_timeout_after_receipt_is_not_proof_of_no_execution():
    # The Fake Provider recorded receipt; a timeout at this point must reconcile with the reservation
    # HELD, not release + retry. Modeled via the durable dispatch marker driving Day56.
    clock = FakeClock()
    limiter, ledger, circuit = _ready()
    log = ProviderCallLog()
    provider = ControllableFakeProvider([ScriptedResponse(http_status=200, provider_request_id="req-1")],
                                        call_log=log)
    provider.call(provider_idempotency_key="pik-1")           # receipt recorded
    assert log.count == 1
    att = _attempt(marker=clock.now())                        # request left the process
    job = _job(clock, ledger, attempt=att)
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=clock.now())
    assert d.action is ProviderAction.RECONCILE
    assert job.cost_state is CostState.RESERVED               # HELD, never released on unknown execution


# --- 12. late-result strict identity + schema match ------------------------
def _durable():
    return dict(durable_job_id="job-1", durable_attempt_id="att-1", durable_correlation_id="cor-1",
                durable_provider_request_id="req-1", schema_name="research_summary", schema_version="v1")


def test_late_result_completes_only_on_full_match():
    late = LateResult("job-1", "att-1", "cor-1", "req-1", dict(VALID_PAYLOAD))
    out = attempt_late_completion(job_status="pending_reconciliation", awaiting_reconciliation=True,
                                  late=late, **_durable())
    assert out is LateResultOutcome.COMPLETED


def test_late_result_rejected_on_identity_mismatch_and_missing_durable_id():
    ok_ids = _durable()
    wrong = LateResult("job-1", "att-1", "cor-1", "req-WRONG", dict(VALID_PAYLOAD))
    assert attempt_late_completion(job_status="pending_reconciliation", awaiting_reconciliation=True,
                                   late=wrong, **ok_ids) is LateResultOutcome.REFUSED_IDENTITY_MISMATCH
    no_durable = dict(ok_ids); no_durable["durable_provider_request_id"] = None
    match = LateResult("job-1", "att-1", "cor-1", "req-1", dict(VALID_PAYLOAD))
    assert attempt_late_completion(job_status="pending_reconciliation", awaiting_reconciliation=True,
                                   late=match, **no_durable) is LateResultOutcome.REFUSED_IDENTITY_MISMATCH


def test_late_result_rejected_on_invalid_payload():
    late = LateResult("job-1", "att-1", "cor-1", "req-1", {"summary": "ok"})   # missing fields
    assert attempt_late_completion(job_status="pending_reconciliation", awaiting_reconciliation=True,
                                   late=late, **_durable()) is LateResultOutcome.REFUSED_INVALID_PAYLOAD


def test_late_result_rejected_when_not_awaiting():
    late = LateResult("job-1", "att-1", "cor-1", "req-1", dict(VALID_PAYLOAD))
    assert attempt_late_completion(job_status="running", awaiting_reconciliation=False,
                                   late=late, **_durable()) is LateResultOutcome.REFUSED_NOT_AWAITING


def test_terminal_cancelled_job_rejects_matching_late_result():
    late = LateResult("job-1", "att-1", "cor-1", "req-1", dict(VALID_PAYLOAD))
    assert attempt_late_completion(job_status="cancelled", awaiting_reconciliation=True,
                                   late=late, **_durable()) is LateResultOutcome.REFUSED_TERMINAL


# --- 15. Redis limiter outage fails closed --------------------------------
def test_limiter_outage_fails_closed_defers_zero_calls_unchanged_execution_retry():
    clock = FakeClock()
    limiter, ledger, circuit = _ready(available=False)
    job = _job(clock, ledger)
    before_retry = job.execution_retry_count
    d = evaluate_dispatch(job, limiter=limiter, ledger=ledger, circuit=circuit, now=clock.now(),
                          rand=DeterministicRandom([0.0]))
    assert d.action is ProviderAction.DEFER and d.reason == "limiter_unavailable_fail_closed"
    assert job.status is JobStatus.DEFERRED
    assert job.defer_count == 1
    assert job.execution_retry_count == before_retry     # a defer never spends execution-retry budget


# --- 16. deadline with / without external execution evidence ---------------
def test_deadline_without_evidence_expires_and_releases_reservation():
    clock = FakeClock()
    ledger = TenantBudgetLedger({"t1": 10.0})
    job = _job(clock, ledger)
    out = process_deadline(job, ledger)
    assert out.terminal_status is JobStatus.EXPIRED
    assert ledger.available("t1") == 10.0                 # released (no execution evidence)


def test_deadline_with_marker_holds_reservation_and_reconciles():
    clock = FakeClock()
    ledger = TenantBudgetLedger({"t1": 10.0})
    job = _job(clock, ledger, attempt=_attempt(marker=clock.now()))
    out = process_deadline(job, ledger)
    assert out.action is ProviderAction.RECONCILE
    assert job.status is JobStatus.PENDING_RECONCILIATION
    assert ledger.available("t1") == 9.99                 # HELD, not released (reservation kept)


# --- 14. admission backpressure: 503 dominates 429 ------------------------
def test_admission_backpressure_503_dominates_429():
    assert admit_job(tenant_over_quota=True, system_unavailable=True) is AdmissionDecision.REJECT_503_SYSTEM
    assert admit_job(tenant_over_quota=True, system_unavailable=False) is AdmissionDecision.REJECT_429_TENANT
    assert admit_job(tenant_over_quota=False, system_unavailable=False) is AdmissionDecision.ACCEPT


# --- 17/18. guarded, idempotent repair via a unique repair id -------------
def _expired_job(clock, job_id="job-R", release="bad-r2", evidence=False):
    from day56_provider_resilience import DeferRecord
    j = Job(job_id=job_id, tenant_id="t1", contract=_contract(), status=JobStatus.EXPIRED,
            deadline=clock.now() + timedelta(hours=1), release_version=release)
    j.defer = DeferRecord(retry_reason="defer_deadline_expired", next_attempt_at=clock.now(),
                          defer_count=1, deadline=clock.now() + timedelta(hours=1))
    if evidence:
        j.attempt = _attempt(job_id=job_id, request_id="req-1")
    return j


def test_repair_is_idempotent_under_concurrency_one_outbox_intent():
    clock = FakeClock()
    outbox, rledger, ledger = [], {}, TenantBudgetLedger({"t1": 100.0})
    job = _expired_job(clock)
    results = {}
    barrier = threading.Barrier(2)

    def worker(name):
        barrier.wait()
        results[name] = repair_redispatch(job, outbox, rledger, ledger, now=clock.now(),
                                          affected_set={job.job_id}, release_version="bad-r2")

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start(); t2.start(); t1.join(); t2.join()
    outs = list(results.values())
    assert outs.count(RepairOutcome.REDISPATCHED) == 1
    assert outs.count(RepairOutcome.ALREADY_APPLIED) == 1
    assert len(outbox) == 1
    assert outbox[0].repair_id == repair_id_for(job, release_version="bad-r2")


def test_repair_with_provider_evidence_is_reconcile_only():
    clock = FakeClock()
    outbox, rledger, ledger = [], {}, TenantBudgetLedger({"t1": 100.0})
    job = _expired_job(clock, evidence=True)
    out = repair_redispatch(job, outbox, rledger, ledger, now=clock.now(),
                            affected_set={job.job_id}, release_version="bad-r2")
    assert out is RepairOutcome.BLOCKED_PROVIDER_EVIDENCE
    assert outbox == []


# --- 9/20. independent Provider call log survives "Worker loss" ------------
def test_provider_call_log_is_independent_of_job_store():
    log = ProviderCallLog()
    provider = ControllableFakeProvider([ScriptedResponse(http_status=200, provider_request_id="req-1")],
                                        call_log=log)
    provider.call(provider_idempotency_key="pik-1")
    del provider                                          # "Worker" gone; the call log persists
    assert log.count == 1
    assert log.records()[0].provider_request_id == "req-1"


# --- 3/20. honest evidence taxonomy ---------------------------------------
def test_validation_matrix_marks_real_infra_not_run():
    claims = not_run_claims()
    joined = " ".join(claims).lower()
    assert "postgresql" in joined and "celery" in joined and "redis" in joined and "provider" in joined
    # at least one executed-local row exists (the deterministic state machine)
    assert any(r.tier is EvidenceTier.EXECUTED_LOCAL_RUNTIME for r in VALIDATION_MATRIX)
    # the repair-history table is design-only (conceptual), never claimed as migrated
    assert any(r.tier is EvidenceTier.CONCEPTUAL_STATIC and "job_repair_history" in r.claim
               for r in VALIDATION_MATRIX)
