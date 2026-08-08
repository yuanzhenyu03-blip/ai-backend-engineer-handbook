# Day58 — Production AI API Capstone, Observability and English Interview

## 1. Lesson Metadata

```text
Status: Completed
Template: LESSON_TEMPLATE_v2
Version: 1.0
Difficulty: Advanced
Estimated Time: 5-6 hours
Prerequisite: Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection
Previous Lesson: Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection
Next Lesson: Day59 — Playwright Runtime Model: Browser, Context, Page and Async Lifecycle (Phase 5)
Engineering Artifact: projects/ai-backend-data-layer/api/day58-production-ai-api-capstone-observability-and-english-interview-design.md
  + runnable day58_observability_capstone.py + test_day58_observability_capstone.py (in-process deterministic model; 28 passed)
```

Main engineering artifact: a deterministic in-process observability model — the five-identity lifecycle contract, a
safe structured-event contract, a low-cardinality metric registry (Counter/Gauge/Histogram), trace/span-link modeling,
a telemetry-exporter-failure policy, and the observability-release rollback drill — plus the
[design/runbook](../../projects/ai-backend-data-layer/api/day58-production-ai-api-capstone-observability-and-english-interview-design.md).
This is the Phase 4 capstone.

---

## 2. Learning Objectives

After this lesson you can:

- **Distinguish** the five identities — `job_id`, `attempt_id`, `correlation_id`, `request_id`, `trace_id` — and their
  stability rules across retries and HTTP requests.
- **Design** a safe structured-event contract that carries correlation IDs and safe fields but never raw
  prompts/responses/secrets.
- **Emit** `provider.call.timeout` (observed outcome) and `provider.call.suppressed`
  (`reason=prior_attempt_may_have_executed`) correctly.
- **Classify** metric types (Counter/Gauge/Histogram) and keep labels low-cardinality (no `job_id`/`attempt_id`/
  `trace_id`).
- **Model** async causality with child spans and span links instead of fake synchronous nesting.
- **Choose** a telemetry-exporter-failure policy that never fails an accepted Job or authorizes retry.
- **Run** the observability-release rollback drill: roll back config not DB facts, bound the affected set, mark
  telemetry gaps, keep marker-backed Jobs reconciliation-only.
- **Separate** the four evidence tiers and mark real FastAPI/OpenTelemetry/PostgreSQL/Redis/Celery/Provider work NOT RUN.
- **Answer** beginner, intermediate, and senior interview questions in English.

---

## 3. Why This Matters

You have shipped a distributed AI Job backend: an API accepts a Job, an Outbox Relay hands it to a Worker, the Worker
calls a Provider, and reconciliation cleans up after timeouts. The day a tenant asks "did my paid Job run twice?" you
need to answer from evidence — across four processes, across retries, hours later. If your logs can't correlate an
Attempt to its Job, if your metrics collapse under a per-Job label explosion, or if you fake asynchronous retries as one
synchronous trace, you can't answer. Worse, if you let observability drive business decisions — treating a missing log
as proof the Provider didn't run — you'll double-bill the tenant. Day58 closes Phase 4 by making the system explainable
and auditable WITHOUT letting telemetry become a retry-authority: PostgreSQL stays the source of truth, and
observability is the evidence layer around it.

---

## 4. Roadmap Position

```text
Day43-Day56 FastAPI AI Job API + durable/recovery rules
Day57 tested those rules under deterministic failures (repeatable evidence)
        |
        v
Day58 make distributed execution explainable + auditable — observability capstone   <-- you are here (Phase 4 close)
        |
        v
Day59 Playwright runtime model: the Phase 4 backend as a callable browser-automation capability (retain correlation)
        |
        v
Day60+ locator/auto-waiting failures distinguished from broader runtime failures via the same discipline
```

### Knowledge continuity

```text
Previous Knowledge
  Day57 assert durable fact AND side effects; in-process fake = EXECUTED LOCAL RUNTIME; missing request id != no execution
        |
        v
Current Lesson Concept
  correlate API -> Relay -> Attempt -> Adapter -> completion/reconciliation with safe structured events, low-cardinality
  metrics, and span-linked traces; telemetry is evidence around durable state, never a retry authority
        |
        v
Future Production Usage
  Day59 retains correlation through Browser/Context/Page; later queue-backed Browser Workers reuse durable Job/Attempt facts
```

Prerequisites reused: Day57's `EvidenceTier`/`RunStatus` taxonomy; Day56's `ExecutionCertainty`; Day55's
`provider_dispatch_started_at` marker as the durable fact that outranks telemetry absence.

---

## 5. Lesson Map

```text
production scenario: 202 + job_id, Provider timeout -> PENDING_RECONCILIATION (HELD)
  -> five identities + stability rules (job_id/correlation_id stable; attempt_id/trace_id per attempt; request_id per request)
  -> safe structured events (timeout vs suppressed; no raw prompts/secrets)
  -> metrics: Counter/Gauge/Histogram + low-cardinality labels (no job_id/attempt_id/trace_id)
  -> traces: child span for the Provider call; span link to the immediate prior async Attempt
  -> durable truth outranks telemetry: dispatch marker forces reconcile; missing telemetry != no execution
  -> telemetry exporter outage: keep core processing, never FAIL a Job, expose health metrics
  -> bad-observability-release rollback: config not DB facts; bounded set; mark gaps; marker-backed = reconcile-only
  -> four evidence tiers + reviewable runtime-evidence pack
```

---

## 6. Core Mental Model

```text
Observability = a correlated, safe, aggregatable, reviewable EVIDENCE system AROUND durable state.
It does NOT replace the durable state machine and does NOT grant permission to retry unknown external work.

durable truth (PostgreSQL)   = Job / Attempt / dispatch marker / reservation / Outbox facts
logs   = individual safe events (job_id, correlation_id, attempt_id, trace_id)
metrics = low-cardinality aggregate trends (provider, model, outcome) for alerting
traces = one execution's spans; async boundaries use Span Links, not fake nesting
missing telemetry = observability GAP, NEVER proof of no execution
```

Day57 proved the rules hold under failure. Day58 makes them observable — correlated, low-cardinality, span-linked — so a
tenant Job is auditable end to end, while durable facts (not telemetry) decide retry/reconciliation.

---

## 7. Main Concepts

### Concept 1: Five identities, five lifecycles

**Tech Lead Question:** A Job times out on Attempt A and reconciles on Attempt B. Which identifiers change?

**Student Thinking:** The student first offered "correlation id 以及 trace ID" and kept
`job_id correlation_id trace_id request_id` unchanged across the retry — reasonable, since all of them correlate the
same business path.

**Student Answer:** all identifiers stay the same across the retry.

**Tech Lead Review:** Correlation does NOT mean identical lifecycle. `job_id` and `correlation_id` stay STABLE (business
continuity); a new durable Attempt gets a NEW `attempt_id` and normally a NEW `trace_id`; a new HTTP request gets a NEW
`request_id`. `trace_id` is one distributed trace, not business truth. (`IdentityLifecycle.new_attempt()` vs
`new_http_request()`.)

**Engineering Thinking:** You need distinct BUSINESS, EXECUTION, REQUEST, and TELEMETRY identities so evidence can join
across processes and retries without conflating them.

**Production Example:** Attempt B's reconciliation log carries the same `job_id`/`correlation_id` as Attempt A but a new
`attempt_id`/`trace_id` — you can find both attempts of one Job and see they are distinct executions.

### Concept 2: Structured events — timeout vs suppressed

**Tech Lead Question:** Which events prove a timeout versus a deliberately suppressed second call?

**Student Answer:** (from the failure-injection intuition) a timeout is `provider.call.timeout`.

**Tech Lead Review:** Right, and add the suppression event. `provider.call.timeout` is the application's OBSERVED
timeout/unknown outcome — NOT proof the Provider did not execute. A later reconciliation Attempt that refuses to call
the Provider emits `provider.call.suppressed` with `reason=prior_attempt_may_have_executed` and
`dispatch_marker_present=True`. Neither event ever carries a raw prompt, raw response, or secret — the `StructuredEvent`
contract rejects those (`UnsafeTelemetryError`), and its `extra` field may never shadow a canonical id/name/field, so
audit correlation cannot be corrupted. Prompt/output minimization is a tenant-data boundary, not a logging preference.

### Concept 3: Metrics and cardinality

**Tech Lead Question:** Where do `job_id` and `attempt_id` go, and is `provider_calls_in_flight` a Counter or a Gauge?

**Student Thinking / Answer:** The student correctly put `provider`/`model`/`outcome` in metric labels and
`job_id`/`attempt_id`/`trace_id` in logs/traces, but initially chose a Counter for `provider_calls_in_flight`.

**Tech Lead Review:** `provider_calls_in_flight` is a GAUGE — it rises at call start and falls at completion/timeout. A
Counter is cumulative (query its RATE, not the raw total); a Histogram captures a distribution including tail latency.
`job_id`/`attempt_id`/`trace_id` must NEVER be metric labels — they explode cardinality (`MetricSpec` raises
`HighCardinalityLabelError`). Low cardinality also depends on VALUES, not just names: `provider`/`outcome` come from a
controlled allowlist and `model` from a bounded shape (`validate_label_values` raises `LabelValueError` on uncontrolled
or overlong values), so unbounded user input can't silently blow up the time series. And `jobs_pending_reconciliation`
is a Gauge for the backlog. Alert on a COMBINATION —
timeout rate + in-flight saturation + sustained reconciliation backlog — so one transient timeout does not page.

### Concept 4: Traces and async causality

**Tech Lead Question:** API acceptance, the Relay, Attempt A, and Attempt B — one trace or many? How do you link them?

**Student Answer:** separate traces for asynchronous execution, and link Attempt B directly to Attempt A.

**Tech Lead Review:** Correct. Each durable asynchronous boundary is a SEPARATE trace. A Provider Adapter call is a
CHILD span of the current Attempt trace (shares its `trace_id`). A later async Attempt uses a SPAN LINK to the immediate
preceding causal trace — never a child of an already-ended HTTP span. Link only the immediate prior; `job_id` +
`correlation_id` carry stable end-to-end continuity, so don't fan every retry out to every historical trace.

### Concept 5: Durable truth outranks telemetry; exporter outage

**Tech Lead Question:** The telemetry exporter is down during a timeout incident. Fail the Jobs?

**Student Answer:** continue core processing during the exporter outage.

**Tech Lead Review:** Correct. A missing `provider_request_id` or missing telemetry is NOT proof no call happened —
`provider_dispatch_started_at` (persisted before the call) forces reconciliation and the reservation stays HELD. An
exporter outage must NOT turn an accepted Job into FAILED or authorize retry: keep core processing, buffer telemetry to
a bound then drop, and expose health via `telemetry_export_failures_total`, `telemetry_events_dropped_total`,
`telemetry_export_queue_depth`. When the exporter recovers, `recover()` drains the buffered events (FIFO) to an
observable sink and resets the queue-depth gauge to 0 — events already dropped stay dropped. (`process_job_with_telemetry`
returns the unchanged durable status.)

### Concept 6: Bad-observability-release rollback

**Tech Lead Question:** A release removed `attempt_id` from Worker logs and added `job_id` to `provider_call_total`
labels — during a Provider timeout incident. What do you roll back?

**Student Answer:** "Rollback observability release -> halt further missing-association and high-cardinality damage ->
scope by release version and time window -> reconstruct affected items from durable PostgreSQL facts -> mark telemetry
gaps, do not fabricate -> do not overwrite valid Job/Attempt/reservation facts."

**Tech Lead Review:** Technically strong. Roll back the OBSERVABILITY release/config first (stop further correlation
loss + cardinality damage) — never the durable Job/Attempt/marker/reservation/Outbox facts (this is an observability
failure, not a business-state failure). Bound the affected set by release + time window, reconstruct from durable facts,
mark telemetry gaps honestly, and keep a marker-backed `PENDING_RECONCILIATION` Job reconciliation-only. Absence of a
marker/request id is NOT proof of no execution: an ordinary requeue needs a POSITIVE `DEFINITELY_NOT_ACCEPTED` certainty
(Day56), and even then Day58 only marks the Job `ELIGIBLE_FOR_GUARDED_RECOVERY` — it hands it to Day56's existing guarded
recovery (contract/deadline/budget/cancel re-check), never requeuing on its own; `UNKNOWN`/`MAY_HAVE_EXECUTED`/missing
certainty stay reconcile-only.

---

## 8. Common Misconceptions

```text
Identity lifecycle
❌ All identifiers (including trace_id and request_id) stay unchanged across retries because they correlate one path.
✅ job_id/correlation_id are stable; a new Attempt gets a new attempt_id and normally a new trace_id; request_id is per HTTP request.

Missing evidence as proof
❌ No dispatch marker / provider_request_id means the Provider did not execute, so it is safe to retry/requeue.
✅ Missing request evidence is not evidence of non-execution. A durable dispatch marker forces reconciliation; an ordinary requeue needs a POSITIVE DEFINITELY_NOT_ACCEPTED certainty and Day56's guarded eligibility re-check, never absence alone.

Metric semantics
❌ provider_calls_in_flight is a Counter.
✅ It is a Gauge (current value, rises and falls). Counter is cumulative; Histogram is a distribution incl. tail latency.

Metric labels
❌ Put job_id/attempt_id/trace_id in metric labels to slice per Job.
✅ Those belong in logs/traces; as metric labels they explode cardinality. Keep provider/model/outcome only.

Async traces
❌ Model a retry as one long synchronous trace nested under the HTTP span.
✅ Separate traces per async boundary; link the immediate prior with a Span Link; job_id+correlation_id give continuity.

Telemetry outage
❌ Exporter down -> fail the Jobs / allow retry.
✅ Keep core processing; never FAIL an accepted Job; buffer/degrade; expose telemetry health metrics.

Evidence terminology
❌ Local fake verification is the "control-flow layer".
✅ The tier is EXECUTED LOCAL RUNTIME; control-flow is the limited behavior it proves.
```

How to remember: **durable facts decide; telemetry explains. Missing telemetry is a gap, not a green light.**

---

## 9. Engineering Trade-offs

```text
Telemetry availability vs business safety (exporter outage)
Default: keep core processing, never fail an accepted Job, buffer/degrade telemetry, expose health. Correct default.
Strict: an explicit regulatory/product policy MAY block on audit — but only deliberately, never as an accidental exporter-failure side effect.

Child span vs span link (async)
Child span: synchronous, same trace — correct for a Provider call within an Attempt.
Span link: asynchronous, new trace linked to the prior — correct across Outbox/Worker/retry. Faking nesting is wrong.

Low-cardinality labels vs per-Job slicing
Labels provider/model/outcome: cheap, alertable, bounded. Correct.
Labels with job_id/attempt_id/trace_id: unbounded time series, storage/query blowup. Reject; use logs/traces.

Rollback observability config vs rolling back DB facts
Config rollback: stops further telemetry damage. Correct.
DB-fact rollback: corrupts durable business truth for an observability bug. Never.
```

A Tech Lead reviews: are labels low-cardinality, are async traces linked (not nested), does an exporter outage leave
durable status untouched, and does recovery roll back config (not facts) while keeping marker-backed Jobs reconcile-only?

---

## 10. Hands-on Exercises

### Exercise 1: Identity map

Question: map stable vs per-attempt/per-request identifiers across acceptance, Relay, Attempt A timeout, Attempt B
reconciliation.

Expected Output: `job_id`/`correlation_id` stable; new `attempt_id`/`trace_id` on B; `request_id` only on HTTP requests
(`test_new_attempt_keeps_business_ids_changes_attempt_and_trace`).

### Exercise 2: Metric label contract

Question: declare `provider_call_total` and try to add a `job_id` label.

Expected Output: `HighCardinalityLabelError`; the valid contract is `{provider,model,outcome}`
(`test_metric_rejects_high_cardinality_labels`, `test_day58_metric_types_are_correct`).

### Exercise 3: Async span link

Question: model Attempt B after Attempt A.

Expected Output: a new trace linked to A's context, `parent_span_id is None`
(`test_async_retry_uses_span_link_to_immediate_prior_not_nesting`).

### Exercise 4: Rollback drill

Question: recover the bad observability release during a timeout incident.

Expected Output: `rollback()` restores config; affected set bounded by release+window; gaps marked; marker-backed Job
`RECONCILE_ONLY` (`test_rollback_restores_observability_config_only`, `test_affected_set_bounded_by_release_and_window_and_gaps_marked`,
`test_marker_backed_reconciliation_job_is_never_requeued`).

---

## 11. Relevant Framework Connections

- **FastAPI**: the 202 acceptance is a short HTTP request lifecycle (`request_id`), NOT the durable Job lifecycle.
- **PostgreSQL**: Job/Attempt/dispatch-marker/reservation/Outbox state is durable business truth, checked through a NEW
  connection for committed facts (the tier that proves final facts; INTEGRATION RUNTIME, NOT RUN here).
- **Celery / supported broker / Relay**: asynchronous boundaries create SEPARATE execution traces; real redelivery and
  Worker-kill are integration evidence only when actually run.
- **Redis**: transient coordination/backpressure; real limiter/circuit validation is integration runtime only when
  executed.
- **OpenTelemetry**: the vendor-neutral structured-telemetry contract — trace/span context, Span Links, and export
  pipeline health (the real exporter is INTEGRATION RUNTIME, NOT RUN here).
- **Provider Adapter**: safe application-owned outcomes and request evidence; never raw prompts/responses/secrets as
  routine telemetry.

---

## 12. AI Backend Connections

Long-running, potentially billable Provider calls require a durable dispatch marker and reconciliation rather than blind
retry; correlation makes a tenant AI Job auditable across API, Relay, Worker, Provider Adapter, completion, and
recovery. Metrics identify model/provider degradation; logs and traces find the exact affected Job/Attempt; PostgreSQL
and external Provider evidence prove the recovery decision. Prompt/output minimization is a tenant-data/privacy
boundary. This is the capstone insight: observability is what lets you operate expensive AI work at fleet scale — detect
trends, audit one Job, and recover incidents — without ever letting telemetry override the durable state machine.

---

## 13. English Interview

### Key Vocabulary

structured log, metric, trace, span, span link, correlation, job_id / attempt_id / correlation_id / request_id /
trace_id, cardinality, Counter / Gauge / Histogram, reconciliation backlog, dispatch marker, telemetry exporter,
evidence tier, runtime evidence.

### Beginner Question

*What is the difference between a metric, a log, and a trace in an AI job backend?* (Student: "log in worker, metric is
trend, trace is process link" — correct direction.)

Strong answer: "Logs record detailed events from the API, relay, workers, and provider adapter. Metrics show aggregated
trends, such as timeout rate or reconciliation backlog. Traces show the causal path of one execution across components,
and span links connect asynchronous work."

### Intermediate Question

*A Provider call times out after the dispatch marker is persisted. What should the next Worker attempt do, and what
observability evidence should it produce?* (Student: "pending_reconciliation" — correct state, incomplete.)

Strong answer: "The next Worker attempt must enter reconciliation only and must not call the Provider again, because the
dispatch marker means the previous call may have executed. It keeps the reservation held and emits structured logs with
the job ID, correlation ID, attempt ID, trace ID, and the reason `prior_attempt_may_have_executed`. The new trace links
to the previous attempt trace. Metrics show the reconciliation backlog, while PostgreSQL remains the source of truth."

### Senior Question

*A release adds `job_id` to `provider_call_total` labels and removes `attempt_id` from Worker logs, during a Provider
timeout incident. Describe your rollback and recovery plan.* (Student gave a technically strong answer; language
refined.)

Strong answer: "First, I roll back the observability release to stop further impact from missing correlations and
high-cardinality metrics. I define a bounded impact window using the release version and timestamps, then reconstruct
the affected jobs from durable PostgreSQL Job, Attempt, dispatch-marker, and reservation facts. I explicitly mark the
telemetry gap and never fabricate missing logs or traces. I do not overwrite valid Job, Attempt, or reservation facts,
because this is an observability failure, not a business-state failure."

### Common Weak Answer

"Add job_id to every metric and log so we can slice per Job; if telemetry is down, fail the jobs so we don't lose data."

### Strong Answer

"Keep job_id/attempt_id/trace_id in logs and traces, not metric labels, to avoid a cardinality blowup. If the exporter
is down, keep core processing and never fail an accepted Job — telemetry is evidence around durable state, not a
retry-authority. Durable PostgreSQL facts, not telemetry, decide reconciliation."

(The final Chinese mental model is **assistant-assisted**, not independently authored student prose: 「Day58 的核心不是多打
几条日志，而是为异步、可重试、可能收费的 AI Job 建立可关联、可聚合、可追溯、可复核的证据链。PostgreSQL 中的 Job、Attempt、
dispatch marker、reservation、Outbox 是 durable facts，决定 Job 是否只能 reconciliation、是否绝不能盲目再次调用 Provider。
structured logs 带 job_id/correlation_id/attempt_id/trace_id；metrics 用有限 label 聚合趋势，不能把 job_id/attempt_id/
trace_id 放进 labels；traces 的异步关系用 Span Link 而不是伪造同步 Trace。telemetry 缺失只是 observability gap，不能变成
"Provider 一定没执行" 或 "可以重试"。可复核 runtime evidence 要如实标注 EXECUTED LOCAL / INTEGRATION / PRODUCTION 与 NOT
RUN 限制。」)

---

## 14. Mental Model Summary

```text
job_id / correlation_id  = STABLE business continuity
attempt_id / trace_id    = one execution attempt / one trace (new per Attempt)
request_id               = one HTTP request
logs                     = safe individual events (correlation IDs, no raw prompts/secrets)
metrics                  = low-cardinality trends (provider/model/outcome); Counter=rate, Gauge=current, Histogram=distribution
traces                   = spans of one execution; child span for the Provider call; Span Link across async boundaries
durable truth            = PostgreSQL Job/Attempt/marker/reservation/Outbox; outranks telemetry
missing telemetry        = observability GAP, never proof of no execution
exporter outage          = keep core processing, never FAIL a Job; expose health metrics
observability rollback   = roll back config, NOT DB facts; bound the set; mark gaps; absence != requeue (only positive DEFINITELY_NOT_ACCEPTED is eligible for Day56 guarded recovery)
evidence tiers           = CONCEPTUAL_STATIC / EXECUTED_LOCAL_RUNTIME / INTEGRATION_RUNTIME / PRODUCTION
```

---

## 15. Today's Takeaway

- **Most important mental model:** observability is evidence AROUND durable state, never a retry authority.
- **Most important production risk:** letting missing telemetry authorize a second paid Provider call — the dispatch
  marker + reconciliation prevent it.
- **Most important trade-off:** an exporter outage keeps core processing and never fails an accepted Job.
- **Most important framework connection:** OpenTelemetry span links model async causality; PostgreSQL (a new connection)
  proves committed facts.
- **Most important AI Backend connection:** correlation makes a billable tenant Job auditable end to end.
- **Most important interview answer:** `job_id`/`attempt_id`/`trace_id` go in logs/traces, never in metric labels.

---

## 16. Before Next Lesson Checklist

```markdown
- [ ] Can I explain the five identities and their stability rules across retries and HTTP requests?
- [ ] Can I design a safe structured event (correlation IDs, no raw prompts/secrets) and emit timeout vs suppressed?
- [ ] Can I classify Counter/Gauge/Histogram and keep metric labels low-cardinality?
- [ ] Can I model async causality with child spans and span links instead of fake nesting?
- [ ] Can I justify keeping core processing during a telemetry exporter outage?
- [ ] Can I run the observability-release rollback drill (config not DB facts; marker-backed = reconcile-only)?
- [ ] Can I separate the four evidence tiers and mark real infra NOT RUN?
- [ ] Can I answer the beginner/intermediate/senior interview questions in English?
```

---

Related: [`cheat_sheets/fastapi.md`](../../cheat_sheets/fastapi.md) (Day58) ·
[`interview/fastapi.md`](../../interview/fastapi.md) (Day58) ·
[Day58 design/runbook](../../projects/ai-backend-data-layer/api/day58-production-ai-api-capstone-observability-and-english-interview-design.md) ·
[model](../../projects/ai-backend-data-layer/api/day58_observability_capstone.py) ·
[tests](../../projects/ai-backend-data-layer/api/test_day58_observability_capstone.py) ·
[Day57 lesson](day57-ai-backend-testing-fake-providers-contract-tests-and-failure-injection.md)
