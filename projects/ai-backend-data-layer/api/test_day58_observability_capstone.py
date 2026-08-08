"""Day58 tests — observability capstone (in-process deterministic model; EXECUTED_LOCAL_RUNTIME).

These prove the identity/lifecycle rules, the safe structured-event contract, the low-cardinality
metric label contract, trace/span-link modeling, the telemetry-exporter-failure policy, and the
observability-release rollback drill. They do NOT prove a real FastAPI runtime, a real OpenTelemetry
exporter, real PostgreSQL/Redis/Celery integration, or real Provider traffic (see
VALIDATION_MATRIX_DAY58 / day58_not_run_claims()).
"""
import pytest

from day57_testing_harness import EvidenceTier, RunStatus
from day58_observability_capstone import (
    FORBIDDEN_EVENT_FIELDS, HIGH_CARDINALITY_LABELS, HighCardinalityLabelError,
    JOBS_PENDING_RECONCILIATION, MetricRegistry, MetricSpec, MetricType, ObservabilityRelease,
    ObservabilityRecoveryAction, ObservedJob, PROVIDER_CALLS_IN_FLIGHT, PROVIDER_CALL_DURATION_SECONDS,
    PROVIDER_CALL_TOTAL, Span, StructuredEvent, TELEMETRY_EVENTS_DROPPED_TOTAL,
    TELEMETRY_EXPORT_FAILURES_TOTAL, TELEMETRY_EXPORT_QUEUE_DEPTH, TelemetryHealth, TelemetryPipeline,
    UnsafeTelemetryError, VALIDATION_MATRIX_DAY58, build_observability_affected_set, child_span,
    classify_observability_recovery, day58_not_run_claims, emit_provider_call_suppressed,
    emit_provider_call_timeout, linked_trace, mark_telemetry_gaps, process_job_with_telemetry,
    start_job_chain, start_trace,
)


# --- 1. identity / lifecycle contract --------------------------------------
def test_new_attempt_keeps_business_ids_changes_attempt_and_trace():
    a = start_job_chain("job-1")
    b = a.new_attempt()
    assert b.job_id == a.job_id and b.correlation_id == a.correlation_id     # stable business chain
    assert b.attempt_id != a.attempt_id and b.trace_id != a.trace_id         # new execution identity
    assert b.request_id is None                                              # an Attempt is not an HTTP request


def test_new_http_request_only_changes_request_id():
    a = start_job_chain("job-1")
    b = a.new_http_request()
    assert (b.job_id, b.correlation_id, b.attempt_id, b.trace_id) == \
           (a.job_id, a.correlation_id, a.attempt_id, a.trace_id)
    assert b.request_id != a.request_id


# --- 2. structured event contract ------------------------------------------
def test_timeout_event_carries_safe_fields_only():
    ident = start_job_chain("job-1")
    e = emit_provider_call_timeout(ident, provider="openai", model="gpt-x", duration_ms=8000,
                                   dispatch_marker_present=True)
    d = e.to_safe_dict()
    assert e.event_name == "provider.call.timeout" and d["outcome"] == "timeout"
    assert d["job_id"] == ident.job_id and d["attempt_id"] == ident.attempt_id
    assert d["dispatch_marker_present"] is True and d["request_id_present"] is True
    # a timeout event is the OBSERVED outcome, never proof of non-execution — no raw payload leaks
    assert not (set(d) & FORBIDDEN_EVENT_FIELDS)


def test_suppressed_event_reason_is_prior_attempt_may_have_executed():
    ident = start_job_chain("job-1").new_attempt()
    e = emit_provider_call_suppressed(ident, provider="openai", model="gpt-x")
    assert e.event_name == "provider.call.suppressed"
    assert e.reason == "prior_attempt_may_have_executed"
    assert e.dispatch_marker_present is True


def test_event_rejects_forbidden_raw_and_secret_fields():
    with pytest.raises(UnsafeTelemetryError):
        StructuredEvent(event_name="x", job_id="j", correlation_id="c", attempt_id="a", trace_id="t",
                        extra={"prompt": "hello"})
    with pytest.raises(UnsafeTelemetryError):
        StructuredEvent(event_name="x", job_id="j", correlation_id="c", attempt_id="a", trace_id="t",
                        extra={"api_key": "sk-xxx"})


def test_event_rejects_unrecognized_fields():
    with pytest.raises(UnsafeTelemetryError):
        StructuredEvent(event_name="x", job_id="j", correlation_id="c", attempt_id="a", trace_id="t",
                        extra={"mystery": 1})


# --- 3. metric contract + cardinality --------------------------------------
def test_metric_rejects_high_cardinality_labels():
    for bad in ("job_id", "attempt_id", "trace_id"):
        with pytest.raises(HighCardinalityLabelError):
            MetricSpec("bad_metric", MetricType.COUNTER, ("provider", bad))


def test_day58_metric_types_are_correct():
    assert PROVIDER_CALL_TOTAL.mtype is MetricType.COUNTER
    assert PROVIDER_CALL_DURATION_SECONDS.mtype is MetricType.HISTOGRAM
    assert PROVIDER_CALLS_IN_FLIGHT.mtype is MetricType.GAUGE       # rises at start, falls at completion
    assert JOBS_PENDING_RECONCILIATION.mtype is MetricType.GAUGE    # backlog rises and falls
    assert PROVIDER_CALL_TOTAL.labels == ("provider", "model", "outcome")


def test_metric_registry_counter_gauge_histogram():
    m = MetricRegistry()
    lbl = {"provider": "openai", "model": "gpt-x", "outcome": "timeout"}
    m.inc(PROVIDER_CALL_TOTAL, lbl); m.inc(PROVIDER_CALL_TOTAL, lbl)
    assert m.counter_value(PROVIDER_CALL_TOTAL, lbl) == 2.0
    g = {"provider": "openai", "model": "gpt-x"}
    m.set_gauge(PROVIDER_CALLS_IN_FLIGHT, 3, g); m.set_gauge(PROVIDER_CALLS_IN_FLIGHT, 1, g)
    assert m.gauge_value(PROVIDER_CALLS_IN_FLIGHT, g) == 1.0        # current value, not cumulative
    m.observe(PROVIDER_CALL_DURATION_SECONDS, 0.2, g); m.observe(PROVIDER_CALL_DURATION_SECONDS, 8.0, g)
    assert m.histogram_values(PROVIDER_CALL_DURATION_SECONDS, g) == [0.2, 8.0]   # distribution, incl. tail


def test_metric_requires_exact_label_set():
    m = MetricRegistry()
    with pytest.raises(ValueError):
        m.inc(PROVIDER_CALL_TOTAL, {"provider": "openai"})         # missing model/outcome


# --- 4. trace model + span links -------------------------------------------
def test_child_span_shares_parent_trace():
    attempt = start_trace("worker.attempt")
    call = child_span(attempt, "provider.adapter.call")            # a Provider call is a child span
    assert call.context.trace_id == attempt.context.trace_id
    assert call.parent_span_id == attempt.context.span_id


def test_async_retry_uses_span_link_to_immediate_prior_not_nesting():
    attempt_a = start_trace("worker.attempt.A")
    attempt_b = linked_trace("worker.attempt.B", prior=attempt_a)  # separate async trace
    assert attempt_b.context.trace_id != attempt_a.context.trace_id  # NOT a child of an ended span
    assert attempt_b.links == (attempt_a.context,)                 # link only the immediate prior
    assert attempt_b.parent_span_id is None


# --- 5. telemetry exporter-failure policy ----------------------------------
def test_exporter_outage_does_not_fail_job_or_authorize_retry():
    m = MetricRegistry()
    pipe = TelemetryPipeline(m, buffer_bound=2)
    pipe.exporter_up = False                                        # exporter DOWN
    ident = start_job_chain("job-1")
    events = [emit_provider_call_timeout(ident, provider="openai", model="gpt-x", duration_ms=8000,
                                         dispatch_marker_present=True) for _ in range(5)]
    res = process_job_with_telemetry(pipe, ident, events=events, durable_status="pending_reconciliation")
    assert res.job_status == "pending_reconciliation"              # durable status UNAFFECTED
    assert res.telemetry_health is TelemetryHealth.DEGRADED
    assert m.counter_value(TELEMETRY_EXPORT_FAILURES_TOTAL) == 5.0  # health exposed via metrics
    assert m.counter_value(TELEMETRY_EVENTS_DROPPED_TOTAL) == 3.0   # 5 events, buffer bound 2 -> 3 dropped
    assert m.gauge_value(TELEMETRY_EXPORT_QUEUE_DEPTH) == 2.0


def test_healthy_exporter_reports_healthy_and_no_drops():
    m = MetricRegistry()
    pipe = TelemetryPipeline(m)
    ident = start_job_chain("job-1")
    res = process_job_with_telemetry(pipe, ident, events=[
        emit_provider_call_timeout(ident, provider="openai", model="gpt-x", duration_ms=10,
                                   dispatch_marker_present=False)], durable_status="succeeded")
    assert res.telemetry_health is TelemetryHealth.HEALTHY
    assert res.events_dropped == 0


# --- 6. observability-release rollback drill -------------------------------
def test_rollback_restores_observability_config_only():
    rel = ObservabilityRelease("bad-obs-2", logs_include_attempt_id=False,
                               provider_call_total_has_job_id_label=True)
    rel.rollback()
    assert rel.logs_include_attempt_id is True                     # correlation restored
    assert rel.provider_call_total_has_job_id_label is False       # high-cardinality label removed


def _jobs():
    return [
        ObservedJob("job-in", "pending_reconciliation", True, None, "bad-obs-2", 5, telemetry_complete=False),
        ObservedJob("job-out", "pending_reconciliation", True, None, "bad-obs-2", 99, telemetry_complete=False),
        ObservedJob("job-other", "running", False, None, "good-obs-1", 5, telemetry_complete=True),
    ]


def test_affected_set_bounded_by_release_and_window_and_gaps_marked():
    jobs = _jobs()
    affected = build_observability_affected_set(jobs, release_version="bad-obs-2",
                                                window_start=0, window_end=10)
    assert affected == ["job-in"]                                  # in-window bad release only
    gaps = mark_telemetry_gaps(jobs, affected)
    assert gaps == {"job-in": True}                                # gap recorded honestly, not fabricated


def test_marker_backed_reconciliation_job_is_never_requeued():
    # incomplete telemetry but a durable dispatch marker -> reconciliation-only, never ordinary requeue
    j = ObservedJob("job-in", "pending_reconciliation", True, None, "bad-obs-2", 5, telemetry_complete=False)
    assert classify_observability_recovery(j) is ObservabilityRecoveryAction.RECONCILE_ONLY


def test_provider_request_id_evidence_is_reconcile_only():
    j = ObservedJob("job-r", "running", False, "req-1", "bad-obs-2", 5)
    assert classify_observability_recovery(j) is ObservabilityRecoveryAction.RECONCILE_ONLY


def test_proven_no_execution_job_may_requeue():
    j = ObservedJob("job-clean", "queued", False, None, "bad-obs-2", 5)
    assert classify_observability_recovery(j) is ObservabilityRecoveryAction.REQUEUE_ORDINARY


# --- 7. evidence taxonomy honesty ------------------------------------------
def test_validation_matrix_marks_integration_and_production_not_run():
    claims = " ".join(day58_not_run_claims()).lower()
    assert "fastapi" in claims and "opentelemetry" in claims
    assert "postgresql" in claims and ("provider" in claims)
    # every executed-local row is RUN; every integration/production row is NOT RUN
    assert all(r.run_status is RunStatus.RUN for r in VALIDATION_MATRIX_DAY58
               if r.tier is EvidenceTier.EXECUTED_LOCAL_RUNTIME)
    assert all(r.run_status is RunStatus.NOT_RUN for r in VALIDATION_MATRIX_DAY58
               if r.tier in (EvidenceTier.INTEGRATION_RUNTIME, EvidenceTier.PRODUCTION))


def test_high_cardinality_label_set_documents_the_forbidden_labels():
    assert {"job_id", "attempt_id", "trace_id"} <= HIGH_CARDINALITY_LABELS
