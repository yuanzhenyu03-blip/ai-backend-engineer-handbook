# Day58 — Production AI API Capstone, Observability and English Interview (Design + Runbook)

Phase 4 capstone. Day43-Day56 built the FastAPI AI Job backend and its durable/recovery rules; Day57 tested those rules
under deterministic failures. Day58 makes the distributed execution EXPLAINABLE and AUDITABLE: events correlate across
`API -> Outbox Relay -> Worker Attempt -> Provider Adapter -> completion/reconciliation`, metrics detect fleet trends,
traces show causal paths — while PostgreSQL remains the source of business truth.

Runnable model + tests: [`day58_observability_capstone.py`](day58_observability_capstone.py) +
[`test_day58_observability_capstone.py`](test_day58_observability_capstone.py).

---

## 0. Core principle + evidence label (read first)

> Observability is a correlated, safe, aggregatable, reviewable EVIDENCE system AROUND durable state. It does NOT
> replace the durable state machine and does NOT grant permission to retry unknown external work. Missing telemetry is
> an observability GAP, never proof of no execution.

```text
CONCEPTUAL / STATIC DESIGN                                : COMPLETED (this runbook + lesson)
EXECUTED LOCAL RUNTIME (in-process deterministic model)   : RUN (pytest)
INTEGRATION RUNTIME (real FastAPI + OpenTelemetry exporter): NOT RUN
INTEGRATION RUNTIME (real PostgreSQL / Redis / Celery)     : NOT RUN
PRODUCTION (real Provider traffic / prod observability)    : NOT RUN
```

Executed: `python3 -m pytest -q test_day58_observability_capstone.py` -> **28 passed** (Python 3.10.12, pytest 7.4.3).
Full `projects/ai-backend-data-layer/api/` suite -> **493 passed**. These prove the identity/lifecycle rules, the safe
structured-event contract, the low-cardinality metric label contract, trace/span-link modeling, the telemetry-exporter
-failure policy, and the observability-release rollback drill over an in-process deterministic model. They do NOT prove
a real FastAPI runtime, a real OpenTelemetry exporter, real PostgreSQL/Redis/Celery integration, or real Provider
traffic (`VALIDATION_MATRIX_DAY58` / `day58_not_run_claims()` encode this).

SECURITY: no secrets, no raw prompts, no raw Provider responses, no tenant documents. Events carry only safe identifiers
and bounded, low-cardinality fields.

---

## 1. Identity + lifecycle contract (five distinct identities)

```text
job_id         = durable business identity            (STABLE across retries)
correlation_id = stable business-chain association     (STABLE across retries)
attempt_id     = one concrete execution attempt        (NEW per durable Attempt)
trace_id       = one distributed execution trace        (NEW per Attempt, normally; NOT business truth)
request_id     = one short-lived HTTP request identity  (NEW per HTTP request)
```

`IdentityLifecycle.new_attempt()` keeps `job_id` + `correlation_id`, mints a new `attempt_id` + `trace_id`, and clears
`request_id`. `new_http_request()` changes only `request_id`. Correlation does NOT mean identical lifecycle: `job_id` /
`correlation_id` bridge business continuity; `attempt_id` identifies an execution decision; `trace_id` identifies one
trace; `request_id` identifies one HTTP request.

---

## 2. Structured event contract (safe fields only)

`StructuredEvent` allows ONLY safe fields (`event_name`, `job_id`, `correlation_id`, `attempt_id`, `trace_id`,
`provider`, `model`, `outcome`, `duration_ms`, `request_id_present`, `dispatch_marker_present`, `reason`) and REJECTS
forbidden raw/secret fields (`prompt`, `provider_response`, `api_key`, `document`, ...) with `UnsafeTelemetryError`. The
`extra` field may NEVER shadow a canonical field (any id, `event_name`, provider/model/outcome, duration, reason, or a
presence flag) — a collision raises `UnsafeTelemetryError`, and `to_safe_dict` never lets `extra` overwrite a canonical
value — so audit correlation cannot be corrupted; only explicitly-allowlisted safe extension keys are accepted.

- `provider.call.timeout` (`emit_provider_call_timeout`) = the application's OBSERVED timeout/unknown outcome. It is NOT
  proof the Provider did not execute.
- `provider.call.suppressed` (`emit_provider_call_suppressed`) = a later reconciliation Attempt REFUSED to call the
  Provider because prior durable evidence forbids it; `reason="prior_attempt_may_have_executed"`,
  `dispatch_marker_present=True`.

Only PRESENCE flags (`request_id_present`, `dispatch_marker_present`) are surfaced — never the raw values as metric
dimensions.

---

## 3. Metric contract + cardinality

```text
Counter   provider_call_total{provider,model,outcome}          -> query its RATE, not the raw cumulative total
Histogram provider_call_duration_seconds{provider,model}        -> latency distribution / tail latency, not an average
Gauge     provider_calls_in_flight{provider,model}              -> rises at call start, falls at completion/timeout
Gauge     jobs_pending_reconciliation{provider,model}           -> reconciliation backlog rises and falls
```

Low cardinality depends on label NAMES **and** VALUES. `MetricSpec.__post_init__` REJECTS `job_id` / `attempt_id` /
`trace_id` / `request_id` / `correlation_id` as label NAMES (`HighCardinalityLabelError`); and `validate_label_values`
(run on every metric op) REJECTS uncontrolled VALUES (`LabelValueError`) — `provider` and `outcome` must be from a
controlled allowlist, `model` must match a bounded shape, and every value is length/type-checked — so an unbounded
value from user input cannot silently explode cardinality. Alerting should COMBINE timeout rate + in-flight saturation + a sustained reconciliation backlog, so one
transient timeout does not page.

---

## 4. Traces and async causality (span links, not fake nesting)

- API acceptance, Outbox Relay, Worker Attempt A, and later Worker Attempt B are SEPARATE traces across durable
  asynchronous boundaries.
- A Provider Adapter call is a CHILD span of the current Worker Attempt trace (`child_span` shares the parent's
  `trace_id`).
- A later asynchronous Attempt uses a SPAN LINK (`linked_trace`: new trace, `links=(prior.context,)`) to the immediate
  preceding causal trace — NOT a child of an already-ended HTTP span. Link only the immediate prior by default; `job_id`
  + `correlation_id` carry stable end-to-end business continuity. Do NOT fan every retry out to every historical trace.

OpenTelemetry is the vendor-neutral way to produce/export logs, metrics, and traces (the real exporter is
INTEGRATION_RUNTIME, NOT RUN here).

---

## 5. Durable correctness vs observability

`provider_dispatch_started_at` must be persisted BEFORE the external call. A missing `provider_request_id` or missing
telemetry is NOT proof that no call happened. PostgreSQL Job/Attempt/marker/reservation facts determine
retry/reconciliation safety; logs, traces, and metrics EXPLAIN and help PROVE behavior but never AUTHORIZE a repeat
Provider call.

---

## 6. Telemetry exporter-failure policy

`TelemetryPipeline`: if the exporter is DOWN, core Job processing CONTINUES and no accepted Job becomes FAILED
(`process_job_with_telemetry` returns the unchanged durable status). Events buffer up to a bound then drop; health is
exposed via `telemetry_export_failures_total`, `telemetry_events_dropped_total`, and `telemetry_export_queue_depth`. When
the exporter RECOVERS, `recover()` DRAINS the buffered events (FIFO) to an observable sink and resets the queue-depth
gauge to 0; events already dropped during the outage stay dropped (the dropped counter remains accurate). This is a
minimal, deterministic flush — NOT a real OpenTelemetry exporter (INTEGRATION_RUNTIME, NOT RUN). An
explicit regulatory/product policy MAY choose a stricter availability/audit trade-off, but it must never be the
ACCIDENTAL consequence of an exporter failure.

---

## 7. Observability-release rollback drill

A bad observability release removed `attempt_id` from Worker logs and added `job_id` to `provider_call_total` labels
(high cardinality).

1. **Roll back the observability release/config FIRST** (`ObservabilityRelease.rollback`) to stop further correlation
   loss and cardinality damage. This touches CONFIG only.
2. **Do NOT roll back or overwrite** valid Job/Attempt/dispatch-marker/reservation/Outbox facts — this is an
   OBSERVABILITY failure, not a business-state failure.
3. **Bound the affected set** by release version + time window (`build_observability_affected_set`); reconstruct
   affected Jobs from durable PostgreSQL facts; **mark telemetry gaps** honestly (`mark_telemetry_gaps`) — never
   fabricate missing historical logs/traces.
4. A `PENDING_RECONCILIATION` Job whose telemetry is incomplete but whose DATABASE has a dispatch marker (or a
   `provider_request_id`) stays **reconciliation-only** (`classify_observability_recovery` -> `RECONCILE_ONLY`) — it must
   NOT be requeued for an ordinary Provider call. **Absence of a marker/request id is NOT proof of no execution** (Day57):
   an ordinary requeue is permitted ONLY with a POSITIVE `DEFINITELY_NOT_ACCEPTED` execution certainty (Day56), and even
   then Day58 does not itself requeue — `classify_observability_recovery` returns `ELIGIBLE_FOR_GUARDED_RECOVERY`, meaning
   the Job may enter Day56's EXISTING guarded recovery path (which re-checks contract / deadline / budget / cancellation
   before any dispatch). `UNKNOWN` / `MAY_HAVE_EXECUTED` / missing certainty stay `RECONCILE_ONLY`. This lightweight model
   does not own the Day56 eligibility facts and does not fabricate a new business state machine.

---

## 8. Evidence matrix

| Claim | Tier | How shown |
|-------|------|-----------|
| Identity/lifecycle stability (job_id/correlation_id stable; attempt_id/trace_id per attempt; request_id per request) | EXECUTED LOCAL | `test_new_attempt_keeps_business_ids_changes_attempt_and_trace`, `test_new_http_request_only_changes_request_id` |
| Safe structured-event contract; timeout vs suppressed(reason=prior_attempt_may_have_executed); rejects raw/secret + unknown fields | EXECUTED LOCAL | `test_timeout_event_carries_safe_fields_only`, `test_suppressed_event_reason_is_prior_attempt_may_have_executed`, `test_event_rejects_forbidden_raw_and_secret_fields`, `test_event_rejects_unrecognized_fields` |
| Low-cardinality metric contract; Counter/Gauge/Histogram semantics; exact label set | EXECUTED LOCAL | `test_metric_rejects_high_cardinality_labels`, `test_day58_metric_types_are_correct`, `test_metric_registry_counter_gauge_histogram`, `test_metric_requires_exact_label_set` |
| Trace child span shares trace; async retry uses a span link to the immediate prior (no fake nesting) | EXECUTED LOCAL | `test_child_span_shares_parent_trace`, `test_async_retry_uses_span_link_to_immediate_prior_not_nesting` |
| Exporter outage does not FAIL a Job or authorize retry; health metrics; healthy path no drops | EXECUTED LOCAL | `test_exporter_outage_does_not_fail_job_or_authorize_retry`, `test_healthy_exporter_reports_healthy_and_no_drops` |
| Rollback restores observability config only; bounded affected set + marked gaps; marker/request-id/uncertainty -> reconcile-only; ONLY positive DEFINITELY_NOT_ACCEPTED -> eligible for Day56 guarded recovery (absence != proof) | EXECUTED LOCAL | `test_rollback_restores_observability_config_only`, `test_affected_set_bounded_by_release_and_window_and_gaps_marked`, `test_marker_backed_reconciliation_job_is_never_requeued`, `test_provider_request_id_evidence_is_reconcile_only`, `test_absence_of_evidence_alone_does_not_authorize_requeue`, `test_unknown_or_may_have_executed_certainty_stays_reconcile_only`, `test_positive_definitely_not_accepted_is_eligible_for_day56_guarded_recovery`, `test_evidence_overrides_even_definitely_not_accepted` |
| Honest evidence taxonomy (integration + production NOT RUN) | EXECUTED LOCAL | `test_validation_matrix_marks_integration_and_production_not_run` |
| Real FastAPI + OpenTelemetry exporter pipeline | INTEGRATION RUNTIME — NOT RUN | needs a real FastAPI app + OTel collector |
| Real PostgreSQL/Redis/Celery integration with committed correlation evidence | INTEGRATION RUNTIME — NOT RUN | needs real disposable PostgreSQL/Redis/broker + Worker |
| Real Provider traffic / production observability validation | PRODUCTION — NOT RUN | no production Provider credentials authorized |

---

## 9. Reviewable runtime-evidence pack (what a real run must preserve)

A reviewable evidence pack requires: the scenario and expected outcome; the exact command / revision / config / time
window; the fault point; structured logs / traces / metrics; committed database queries FROM A NEW CONNECTION;
independent Provider call evidence; Worker/Relay/broker lifecycle evidence; the actual result; and the explicit
validation tier plus NOT RUN limits. `pytest passed` alone is not a reviewable evidence pack.

---

## 10. Boundaries

- Day58 is the Phase 4 CAPSTONE (observability integration + phase English interview). This module models the
  observability CONTRACT deterministically; the real FastAPI/OpenTelemetry/PostgreSQL/Redis/Celery integration and real
  Provider production evidence are NOT RUN here.
- Day59 uses the completed Phase 4 backend as a callable browser-automation capability and must retain correlation
  through the Browser/Context/Page lifecycle; Day60 relies on the same observability discipline to distinguish
  locator/auto-waiting failures from broader runtime failures.
