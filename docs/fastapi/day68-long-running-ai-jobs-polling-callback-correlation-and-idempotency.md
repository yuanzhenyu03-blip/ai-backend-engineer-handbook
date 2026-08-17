# Day68 — Long-running AI Jobs: Polling, Callback, Correlation and Idempotency

## 1. Lesson Metadata

```text
Status:        ✅ Completed (classroom scope) — lesson + n8n Long-running Job Orchestration Contract; CONCEPTUAL_STATIC only (no runtime)
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 4-5 hours
Prerequisite:  Day67 n8n orchestration boundary; Day66 durable acceptance; Day59-Day61 real backend + Job/Outbox lifecycle
Previous Lesson: Day67 — n8n Workflow Model, Triggers, FastAPI Integration and Responsibility Boundaries
Next Lesson:   Day69 — Human Approval, Retry, Secrets, Audit and Error Workflows
Engineering Artifact: projects/n8n-workflows/ (Day68 Long-running Job Orchestration Contract; NO exported JSON captured)
```

Day68 makes the n8n ↔ FastAPI boundary safe for **long-running** AI Tasks: it separates orchestration
observation from durable Task truth, preserves stable identities, and makes polling/callback delivery
retry-safe, duplicate-safe, correlation-safe, and ordering-safe.

> Evidence honesty. Day68 is `CONCEPTUAL_STATIC`: the class produced a state-machine/contract design and
> reviewed it interactively. **NOT RUN:** the Day68 n8n workflow runtime; the valid FastAPI
> acceptance/status integration; a real Polling loop (Wait/Switch nodes, 503/backoff, deadline behaviour);
> real Callback reachability/authentication/duplicate-delivery/ack-loss/replay/correlation-mismatch/
> out-of-order behaviour; real PostgreSQL idempotency/version/terminal enforcement; real Worker/Provider
> duplicate-call prevention and cancellation/reconciliation; and production. **No Day68 importable/exported
> n8n JSON was created or captured.** Day67's invalid-input local `400` is **not** reused as Day68
> validation, and nothing here is upgraded to `EXECUTED_LOCAL_RUNTIME`, `INTEGRATION_RUNTIME`, or
> `PRODUCTION`. Delivery is treated as **at-least-once** (never exactly-once); `correlation_id` is an
> association key, never authentication.

## 2. Learning Objectives

By the end of Day68 you can:

* Explain why an n8n execution timeout / Poll timeout / HTTP 503 / missing or duplicate or out-of-order
  Callback does **not** by itself change a durable Task's business state.
* Choose Polling vs Callback vs a Hybrid under real constraints, and design a bounded polling state machine
  (interval/backoff, observation deadline, max attempts, terminal stop conditions).
* Keep acceptance idempotent after a lost response by reusing the same business `request_id` + request
  fingerprint, and know when a new `request_id` is a new command.
* Hold the identity contract: `request_id` vs `task_id` vs `correlation_id` vs callback `event_id` vs
  `task_version` vs per-attempt `trace_id`.
* Build a safe at-least-once Callback gate (authenticate → validate → correlate → dedupe `event_id` →
  version ordering → legal transition → optional authoritative confirm → one idempotent downstream action).
* Reject correlation mismatch and out-of-order/stale events, and run a production incident:
  contain → scope → classify → cancel/reconcile/compensate → verify → controlled rollout.

## 3. Why This Matters

An eight-minute AI Research Report Task with paid Provider calls turns every "just retry it" reflex into a
money-and-side-effect hazard. The workflow that submitted the Task will often end — time out, be
redeployed, or disappear — long before the Task finishes. If the orchestrator treats its own end as the
Task's end, it will recreate work that is still running, double a Provider bill, produce conflicting
Artifacts, and publish the same completion twice. Day67 fixed *who owns durable truth* (FastAPI); Day68
fixes *how you safely watch and react to* a durable Task from an orchestrator that is fundamentally
unreliable and only sees at-least-once delivery. The whole lesson is one sentence made operational:
observation is not truth, and arrival order is not business order.

## 4. Roadmap Position

```text
Day67 trigger + FastAPI durable acceptance (202 + task_id)
  -> Day68 polling/callback + stable identity + correlation + idempotent delivery   <- YOU ARE HERE
  -> Day69 human approval, retry/error workflows, Secrets, and audit hardening
  -> Day70 n8n + FastAPI + AI Tool integration capstone and phase interview
```

Day68 reuses the Phase 4/5 Job/Outbox/Worker lifecycle and the Day67 boundary unchanged: n8n orchestrates
and observes; FastAPI/PostgreSQL owns durable truth, authorization, idempotency, recovery, and audit.
Day69 will build human approval, error/retry workflows, Secrets, and audit **on** Day68's stable
`task_id`/`request_id`/`correlation_id`/`event_id`/version rules — this lesson names callback
authentication as a required boundary but does not implement secret/auth workflows. Day70 integrates it
all without moving durable truth into n8n.

## 5. Lesson Map

```text
1. Lifecycle separation: n8n execution timeout != durable Task failure
2. Polling as observation + the bounded polling state machine
3. Observation failures (503/404) are not Task failures
4. Acceptance idempotency after a lost POST response (request_id + fingerprint)
5. The identity & correlation contract (six identities)
6. Callback at-least-once + the safe callback gate + duplicate handling
7. Ordering: stale / duplicate / out-of-order events by task_version; correlation mismatch
8. Production incident: contain -> scope -> classify -> cancel/reconcile/compensate -> verify -> rollout
```

## 6. Core Mental Model

```text
n8n     = orchestration + OBSERVATIONS (Wait/Poll/Switch, Callback entry, execution history).
FastAPI/PostgreSQL = durable Task truth: status, idempotency, Attempt, Provider-dispatch, Artifact facts.

After 202 + task_id, none of these change the Task's business state by itself:
  n8n timeout · Poll timeout · HTTP 503 · missing Callback · duplicate Callback · out-of-order Callback.

Acceptance retries reuse the SAME business request_id + fingerprint.
Polling ALWAYS observes the SAME task_id (retrying a Poll is not retrying the Job).
correlation_id stays stable across the business chain; each concrete HTTP/trace attempt may be new.
Delivery is AT-LEAST-ONCE: authenticate, validate, correlate, dedupe event_id, reject stale/conflicting
versions, verify legal transitions, make downstream effects idempotent.
arrival order != business-state order. n8n history/logs/traces are orchestration evidence, not truth,
and never permission to retry expensive/side-effecting work.
```

### Mental Model Evolution (Day67 → Day68)

```text
Day67: n8n orchestrates; FastAPI owns durable truth. A workflow may ASK; it never owns the Task.
Day68: the workflow must now OUTLIVE-safely observe an 8-minute Task it can no longer hold open.
       Observation (polling/callback) is added WITHOUT giving n8n any new authority: it watches the same
       task_id, correlates by correlation_id, dedupes by event_id, orders by task_version, and reacts only
       through idempotent, backend-owned actions. Nothing in n8n becomes authoritative.
```

## 7. Main Concepts

### Concept 1: n8n execution timeout is not durable Task failure

Tech Lead Question:

FastAPI committed an eight-minute Research Report Task and returned `202 + task_id=task-8421`. The n8n
workflow execution timed out after three minutes. Should n8n mark the Task failed or create a replacement?

Student Thinking:

The orchestration run ended, but the Worker "might still be running or might already have produced a
result" — ending an execution is not the same as ending the business Task.

Student Answer:

*`不能`* — cannot mark the Task failed or recreate it just because the n8n execution timed out.

Tech Lead Review:

Correct. `n8n execution timeout != durable Task failure`. Recreating the Task risks duplicate Provider
cost, duplicate browser/external side effects, and conflicting results. The orchestrator must observe or
reconcile the **existing** Task, never invent a new one on its own timeout.

Engineering Thinking:

Separate the lifecycle of the *observer* from the lifecycle of the *durable fact*. An unreliable observer
ending tells you nothing authoritative about the fact.

Production Example:

A workflow pod is redeployed mid-run; the 8-minute report keeps running in the Worker; on restart the
workflow re-observes `task-8421` rather than submitting a new report.

Framework Connection:

n8n execution record ends; FastAPI/PostgreSQL still holds `task-8421` as `running`. The Worker and Outbox
continue independently of the n8n execution.

Exercise:

State the three concrete harms of recreating a still-running paid Task. (See Section 10, Exercise 1.)

### Concept 2: Polling as observation, and the bounded polling state machine

Tech Lead Question:

FastAPI can expose `GET /tasks/{task_id}` but cannot call n8n (no inbound reachability). How do you follow
the Task to completion?

Student Thinking:

If the backend cannot call back, the workflow has to ask repeatedly — but "asking again" must not become
"doing again."

Student Answer:

*`Polling`*.

Tech Lead Review:

Correct, and precise: Polling is **observation of an existing Task**; retrying a Poll is not permission to
retry the Job. The state machine:

```text
Webhook -> POST FastAPI -> 202 + task_id + correlation_id -> Wait
  -> GET /tasks/{task_id} -> switch on the AUTHORITATIVE status:
       queued / running          -> bounded wait/backoff -> poll the SAME task_id
       succeeded                 -> consume the verified result / Artifact reference
       failed / cancelled / expired -> finish with the matching terminal outcome
       timeout / 429 / 503 / invalid -> retain task_id; retry observation or reconcile
```

It needs a bounded interval/backoff, an overall observation deadline, a max-attempts cap, and terminal
stop conditions.

Engineering Thinking:

Make the watcher bounded and idempotent: it only reads, it always reads the same identity, and it stops on
an authoritative terminal state or a deadline.

Production Example:

Poll every 10s with exponential backoff up to a 12-minute observation deadline; on deadline, hand off to
reconciliation rather than declaring failure.

Framework Connection:

n8n `Wait` + `HTTP Request (GET)` + `Switch` on `status`; FastAPI's authoritative public Task contract is
the switch input.

Exercise:

List the four bounding controls a polling loop needs. (See Section 10, Exercise 2.)

### Concept 3: Observation failures are not Task failures

Tech Lead Question:

`GET /tasks/{task_id}` returns HTTP 503 while the 8-minute Task runs. Does that mean the Task failed?

Student Thinking:

A 503 is about the *channel* I used to look, not about the Task itself.

Student Answer:

*`继续保留原 task_id`* — keep the original task_id.

Tech Lead Review:

Correct. `HTTP 503 = observation channel temporarily unavailable`, not `task_status == failed`. Keep the
same `task_id`, record the failed observation, retry with bounded backoff, and enter reconciliation if the
observation deadline expires. A `404` is also **not** automatically a business failure — it may signal an
identity, tenant, retention, or integration mismatch and needs investigation, not a replacement Task.

Engineering Thinking:

Distinguish "I could not see the state" from "the state is failure." Only an authoritative terminal state
is failure.

Production Example:

The status API briefly returns 503 during a deploy; the workflow backs off and re-reads, and the report
completes normally — no duplicate Task is created.

Framework Connection:

n8n treats 5xx/timeout as a retryable observation; FastAPI/PostgreSQL remains the only source of a terminal
`failed`.

Exercise:

Classify 503 and 404 from the status endpoint and give the safe next action for each. (See Section 10,
Exercise 3.)

### Concept 4: Acceptance idempotency after a lost POST response

Tech Lead Question:

n8n sent the acceptance POST but the **response was lost**. How does it retry without creating a duplicate
Task?

Student Thinking:

The command was "create this one report"; resending the same command must not mean "create a second
report."

Student Answer:

*`n8n 应沿用原来的 request_id`* — reuse the original business `request_id` (the answer dropped an initial "n",
a harmless typo only).

Tech Lead Review:

Correct. n8n resends with the same business `request_id` / idempotency key; FastAPI atomically collapses
the same logical intent onto the existing Task and returns the same `task_id`. Generating a **new**
`request_id` expresses a **new** business command and can legitimately create a duplicate. FastAPI binds
the `request_id` to a request fingerprint:

```text
same request_id + same meaning     -> return the existing task_id
same request_id + different meaning -> 409 Conflict
```

Engineering Thinking:

Idempotency is a property of the *record*, not of "trying once." Transport retries are expected; the
backend collapses intent.

Production Example:

A gateway timeout hides a committed acceptance; the resend with the same `request_id` returns
`task-8421` instead of creating `task-8422`.

Framework Connection:

n8n transport re-send (Day67 layer 1); FastAPI request-fingerprint + idempotency record (Day59/Day50
acceptance) is layer 2; Worker execution retry is layer 3.

Exercise:

Decide old vs new `request_id` for a lost-response retry and justify the 409 case. (See Section 10,
Exercise 4.)

### Concept 5: The identity and correlation contract

Tech Lead Question:

Across n8n, FastAPI, Outbox, Worker, Polling, Callback, and downstream actions, which identifiers are
stable, which change, and what is each for?

Student Thinking:

Some IDs name the *business fact*, some name a *single attempt*; conflating them is how duplicates and
mis-publishes happen.

Student Answer / Classroom record:

The class fixed six identities (below); the student consistently used the stable business identity for
observation and acceptance.

Tech Lead Review:

```text
business request_id / idempotency key = stable identity of ONE logical acceptance command
task_id            = durable Task identity created by FastAPI AFTER commit
correlation_id     = stable business-chain association across n8n/FastAPI/Outbox/Worker/Poll/Callback/downstream
event_id           = stable callback event identity, used for dedupe
task_version       = monotonic ordering / conflict evidence
trace_id / poll-attempt id = identity of ONE concrete HTTP/execution attempt; MAY be new each time
```

`correlation_id` is an **association key, not authentication or authorization**.

Engineering Thinking:

Give every distinct notion its own ID; never reuse an attempt ID as a business key, and never treat an
association key as a credential.

Production Example:

A support engineer traces one report across systems by `correlation_id`, while each retried HTTP call
carries its own `trace_id`.

Framework Connection:

FastAPI mints `task_id` on commit and echoes `correlation_id`; Outbox/Worker/Callback all carry
`correlation_id`; observability ties `trace_id`s to the chain.

Exercise:

Given a duplicate callback, name which ID dedupes it and which ID must NOT be used as authentication.

### Concept 6: Callback at-least-once and the safe callback gate

Tech Lead Question:

If FastAPI (or n8n) can deliver a completion Callback, how do you process it safely when the same event
may arrive twice?

Student Thinking:

A connection can drop after the work is done but before the ack, so "I received this event" must be
idempotent.

Student Answer:

*`不能`* — cannot process two duplicate deliveries as two new completion events.

Tech Lead Review:

Correct. Callback delivery is **at-least-once**. Contract fields: `event_id`, `event_type`, `task_id`,
`correlation_id`, `task_version`, and a safe `artifact_ref`. The safe gate:

```text
authenticate caller
  -> validate payload schema
  -> match task_id + correlation_id
  -> deduplicate stable event_id
  -> compare task_version / reject stale or conflicting events
  -> verify a legal transition
  -> optionally confirm authoritative FastAPI state when uncertain
  -> perform ONE idempotent downstream action
```

n8n execution history is **not** the authoritative idempotency store; a durable downstream action goes
through an idempotent FastAPI API (or another target with a stable idempotency key such as
`event_id:publish-report`).

Engineering Thinking:

Design for redelivery: stable event identity + idempotent effect makes "delivered twice" harmless without
claiming exactly-once.

Production Example:

The "publish report" step keys on `event_id:publish-report`; a duplicate callback re-runs the step as a
no-op and the report is published exactly once in effect.

Framework Connection:

n8n Callback entry (Webhook) → authenticate → the gate above → an idempotent FastAPI publish/downstream
call.

Exercise:

Decide whether two duplicate callbacks may both publish, and where dedupe lives. (See Section 10,
Exercise 5.)

### Concept 7: Ordering — stale, duplicate, and out-of-order events; correlation mismatch

Tech Lead Question:

The Task was already observed as `task_version=7, succeeded`; then a delayed `task_version=5, running`
event arrives. And separately, a callback arrives with the right `task_id=task-8421` but
`correlation_id=corr-777` instead of `corr-992`. What do you do?

Student Thinking:

Later arrival does not mean later truth; a wrong association key means "not this business chain."

Student Answer:

*`不能`* downgrade the succeeded Task to running; and *`不能`* accept/publish the mismatched-correlation
callback despite the matching `task_id`.

Tech Lead Review:

Correct on both. Version rules:

```text
incoming version < processed version  -> stale event: safe no-op / ack, NO side effect
incoming version == processed version -> identical duplicate = idempotent no-op;
                                         conflicting meaning  = integration error
incoming version > processed version  -> verify a LEGAL transition before processing
```

`arrival order != business-state order`; FastAPI/PostgreSQL stays authoritative and n8n holds only a
rebuildable orchestration view. For the correlation mismatch: do not publish or trigger downstream effects,
preserve safe metadata, query authenticated FastAPI for authoritative facts, and enter
reconciliation/integration-error handling. Matching correlation is necessary for this contract but **never
substitutes for callback authentication**.

Engineering Thinking:

Order by a monotonic version from the source of truth, not by arrival time; treat a wrong association key
as "not mine," not as "downgrade."

Production Example:

A retried callback from an earlier state lands after success; the gate acks it as stale and never
overwrites the succeeded result.

Framework Connection:

`task_version` from FastAPI drives the ordering `Switch`; a mismatched `correlation_id` routes to an
integration-error/reconciliation branch, not a publish branch.

Exercise:

Reject an out-of-order `running`-after-`succeeded` event and a correlation-mismatched callback, and say why
correlation matching is not authentication. (See Section 10, Exercise 6.)

## 8. Common Misconceptions

The student answered the core boundaries correctly; these preserve the accurate trajectory plus the one
real technical correction.

1. **Audit logs as an authoritative recovery mechanism (the one real correction).** In the intermediate
   interview the student said a 503 "can be recovered using audit logs." Correct parts: 503 does not prove
   the durable Task stopped, and Polling adds FastAPI request load. Correction: audit logs are supporting
   **investigation** evidence, not the authoritative state or a recovery mechanism. Retain the same
   `task_id`, retry the observation with bounded backoff, use FastAPI/PostgreSQL as authoritative truth,
   and reconcile if the observation deadline expires.
2. **Boundaries the student did NOT get wrong (do not invent mistakes).** The student did not treat an n8n
   timeout as Task failure, did not treat a Poll 503 as permission to create a replacement, did not treat a
   duplicate Callback as a duplicate completion, and did not treat arrival order as business-state order.
   Each was answered correctly and is preserved as such.
3. **Wording only, not concept (beginner English).** "a process of invocation" is understandable but
   unnatural; "an orchestration run" is clearer, and "durable task"/"durable business commitment" reads
   better than repeating "persistent."
4. **Compression, not error (senior incident answer).** The six-stage sequence was correct but too
   compressed for a senior spoken answer; it is expanded with a containment target, a bounded affected-set,
   per-state classification, no-blind-retry for possible Provider execution, verification, regression
   coverage, and gradual rollout.

## 9. Engineering Trade-offs

* **Polling vs Callback vs Hybrid.** Polling is simple and needs no inbound callback reachability, but adds
  HTTP/DB read load and a latency-vs-load trade-off (shorter intervals = fresher but noisier). Callback is
  timely and reduces empty queries, but requires reachability, authentication, duplicate handling,
  replay/ordering protection, and reconciliation. Hybrid (Callback for prompt notification + Polling/
  Reconciliation as a safety net) is the most resilient and the most complex.
* **New `request_id` vs reused `request_id`.** A new ID is a new command (may duplicate expensive work);
  reuse collapses intent. Choose reuse for lost-response retries; choose a new ID only for a genuinely new
  business command.
* **Delete vs compensate on a bad release.** Deleting durable Task facts looks like a clean undo but cannot
  reverse a Provider charge or an external side effect and destroys audit/recovery evidence. Classify and
  compensate/reconcile instead.
* **Trusting n8n history vs FastAPI/PostgreSQL.** Orchestration history is convenient and rebuildable but
  is not authoritative business state and is never permission to retry.

## 10. Hands-on Exercises

Day68 is `CONCEPTUAL_STATIC`: these are **design/decision** exercises with no runtime, no n8n execution,
and no commands — nothing was run. Each tests the mental model against the taught contract.

### Exercise 1 — n8n timeout vs durable Task failure

Question: FastAPI returned `202 + task_id=task-8421`; the n8n execution times out at 3 minutes. What is the
Task's business state, and what must n8n NOT do?

Think First: Whose lifecycle just ended — the observer's or the durable fact's?

Starter Artifact:

```text
FastAPI: task-8421 = running (8-minute Worker Task, paid Provider)
n8n:     execution ended at t=3m
```

Expected Output: The Task's state is unchanged (`running`); n8n must not mark it failed and must not create
a replacement — it re-observes or reconciles `task-8421`.

Explanation: `n8n execution timeout != durable Task failure`; recreation risks duplicate Provider cost,
duplicate side effects, and conflicting results.

Follow-up Question: What real backend evidence would you need before ever concluding the Task failed?

### Exercise 2 — Design the bounded polling loop

Question: Under no-inbound-reachability, design the polling state machine and its bounding controls.

Think First: How do you keep "observe again" from becoming "do again," and how do you stop?

Starter Artifact:

```text
Wait -> GET /tasks/{task_id} -> Switch(status):
  queued/running -> backoff -> poll same task_id
  succeeded -> consume artifact_ref
  failed/cancelled/expired -> terminal
  timeout/429/503/invalid -> retain task_id; retry or reconcile
```

Expected Output: A loop that always GETs the same `task_id`, with a bounded interval/backoff, an overall
observation deadline, a max-attempts cap, and terminal stop conditions; on deadline it reconciles, it does
not fail the Task.

Explanation: Polling is observation of an existing Task; retrying a Poll is not retrying the Job.

Follow-up Question: What changes if you add a Callback as well (Hybrid), and what new risks appear?

### Exercise 3 — Classify HTTP 503 (and 404) from the status endpoint

Question: `GET /tasks/{task_id}` returns 503 mid-Task. Then consider a 404. Classify each and give the safe
next action.

Think First: Is this about the channel or the Task?

Starter Artifact: `503 from GET /tasks/task-8421` … `404 from GET /tasks/task-8421`.

Expected Output: 503 = observation channel temporarily unavailable (retain `task_id`, backoff, reconcile on
deadline) — not `failed`. 404 = not automatically a business failure; investigate identity/tenant/retention/
integration mismatch. Neither authorizes a replacement Task.

Explanation: Observation failure is not Task failure; audit logs support investigation but are not
authoritative recovery.

Follow-up Question: Which authoritative source resolves a persistent 404, and why not audit logs alone?

### Exercise 4 — Old vs new `request_id` on a lost-response retry

Question: The acceptance POST's response was lost. Reuse the old `request_id` or mint a new one?

Think First: Is this the same command or a new command?

Starter Artifact:

```text
same request_id + same meaning      -> ?
same request_id + different meaning -> ?
new request_id                      -> ?
```

Expected Output: Reuse the same `request_id` → FastAPI returns the existing `task_id`. Same `request_id` +
different meaning → `409 Conflict`. A new `request_id` is a new command that may legitimately create a
duplicate.

Explanation: Idempotency lives in the backend record bound to a request fingerprint, not in "trying once."

Follow-up Question: Where is this idempotency enforced, and why can't n8n own it?

### Exercise 5 — May duplicate callbacks both publish?

Question: The same completion Callback is delivered twice. May both trigger the downstream publish?

Think First: What makes at-least-once delivery safe without claiming exactly-once?

Starter Artifact: Callback gate (authenticate → validate → match `task_id`+`correlation_id` → dedupe
`event_id` → version → legal transition → idempotent action).

Expected Output: No. Deduplicate on the stable `event_id` and make the downstream action idempotent (e.g.
`event_id:publish-report`), so the second delivery is a no-op; the report is published once in effect.

Explanation: n8n history is not the idempotency store; a backend idempotent API is.

Follow-up Question: Which single field carries dedupe, and what happens if it is missing?

### Exercise 6 — Ordering and correlation: incident classification

Question: (a) After `task_version=7, succeeded`, a `task_version=5, running` event arrives. (b) A callback
arrives `task_id=task-8421, correlation_id=corr-777` (expected `corr-992`). (c) Classify original task-A
(succeeded + verified artifact-A) and replacement task-B (queued, zero Worker Attempts,
`provider_dispatch_started_at=null`).

Think First: Does later arrival mean later truth? Does a matching `task_id` with a wrong `correlation_id`
belong to this chain?

Starter Artifact: the version rules + the incident classification table.

Expected Output: (a) Reject the downgrade — stale version is a safe no-op/ack, no side effect. (b) Reject —
do not publish; preserve safe metadata; query authenticated FastAPI; reconcile; correlation matching is not
authentication. (c) Retain task-A and its facts, review authority/duplicate impact; issue a **FastAPI
durable cancellation** for task-B (queued, no execution evidence) via the backend-owned path.

Explanation: `arrival order != business-state order`; delete/blind-cancel is never the tool — classify then
cancel/reconcile/compensate through FastAPI.

Follow-up Question: For a `running` replacement that *may* have called the Provider, why is
`PENDING_RECONCILIATION` correct instead of cancellation or retry?

## 11. Relevant Framework Connections

* **n8n** — Webhook acceptance flow, Wait/Poll/Switch orchestration, Callback entry, execution history as
  orchestration evidence, version rollback/deactivation, and bounded workflow observation.
* **FastAPI** — authenticated acceptance/status/cancellation/reconciliation/publication APIs; the
  authoritative public Task contract; request-fingerprint + idempotency enforcement; the callback
  sender/Task-query boundary.
* **PostgreSQL** — durable Task/status/idempotency/Attempt/Provider-dispatch/Artifact facts remain
  authoritative.
* **Outbox / Worker** — acceptance and execution continue after the n8n execution ends; queue
  delivery/Worker execution retry is separate from Poll/Callback delivery.
* **Observability** — `correlation_id` connects the business chain while per-request `trace_id`s may
  change; logs/traces explain but do not authorize retry or replace durable truth.

## 12. AI Backend Connections

Eight-minute AI Research Report Tasks and paid Provider calls make blind recreation economically and
semantically dangerous. The concrete risks — duplicate browser/Provider side effects and conflicting
Artifacts — are controlled by stable identities, durable idempotency, callback dedupe, ordering checks, and
reconciliation. A verified Artifact reference is preserved as a durable fact; raw results are not
repeatedly published by duplicate callbacks. Unknown Provider execution requires reconciliation, not blind
replay. Day69 will add human approval, error/retry workflows, Secrets, and audit on top of these Day68
identity and delivery contracts; Day68 only names callback authentication as a required boundary.

## 13. English Interview

Key Vocabulary:

long-running task · orchestration run vs durable business commitment · polling vs callback vs hybrid ·
observation deadline / bounded backoff · at-least-once delivery · idempotency key / request fingerprint ·
`request_id` / `task_id` / `correlation_id` / `event_id` / `task_version` / `trace_id` · dedupe · stale /
out-of-order event · legal transition · reconciliation vs compensation vs cancellation · contain → scope →
classify → verify → controlled rollout.

Useful Expressions:

- "An n8n execution is an orchestration run; the durable task is a committed business fact."
- "Observation is not truth — a 503 means I could not see the state, not that it failed."
- "Retrying a poll is not retrying the job."
- "Delivery is at-least-once, so I dedupe on a stable event ID and make the effect idempotent."
- "Arrival order is not business-state order; I order by the backend's task_version."
- "Rolling back the workflow stops future harm; it does not undo committed tasks or external side effects."

### Beginner

Question: What is the difference between an n8n workflow execution and a durable AI task?

Student answer (classroom record): *"An n8n execution is merely a process of invocation, whereas a
persistent AI task represents a persistent business commitment."* (Review: technically correct; improve
"process of invocation" → "orchestration run" and use "durable" consistently.)

Strong Answer: "An n8n execution is an orchestration run that may start, observe, or coordinate work. A
durable AI task is a committed business fact stored by the backend. If the n8n execution times out or
disappears, the task may still be running, so the workflow must query or reconcile the existing task
instead of creating a replacement."

### Intermediate

Question: A polling request returns HTTP 503 while an eight-minute AI task is running. How should the
workflow respond, and what trade-off does polling introduce?

Student answer (classroom record): *"Returning a 503 status does not mean the service has stopped; it can
be recovered using audit logs. The polling mechanism increases the request load on FastAPI."* (Review:
correctly rejected 503 as proof of failure and named request load; corrected the audit-log boundary — logs
support investigation, not authoritative recovery.)

Strong Answer: "An HTTP 503 means the workflow could not observe the task state; it does not prove the
durable task failed or stopped. The workflow should retain the same task ID, retry the status request with
bounded backoff, and enter reconciliation if its observation deadline expires. Polling is simple and needs
no callback endpoint, but it increases API and database read load and introduces a latency-versus-load
trade-off: shorter intervals give faster updates but generate more requests."

### Senior

Question: A faulty n8n release creates replacement tasks after five failed polls. Some original and
replacement tasks may already have called a paid provider. Walk through containment, classification,
recovery, and safe rollout.

Student answer (classroom record): *"contain → scope → classify → cancel/reconcile/compensate → verify →
controlled rollout"* (Review: correct structure, initially too compressed for a senior spoken answer.)

Strong Answer: "First I contain by deactivating the faulty workflow and restoring the last safe version so
it cannot create more replacement tasks. Next I build a bounded affected set using the workflow version,
release window, request IDs, task IDs, correlation IDs, Worker Attempts, and Provider-dispatch evidence.
Then I classify each task from durable evidence: a queued replacement with no execution evidence can get a
durable cancellation through FastAPI; a running task that may already have called the Provider must enter
reconciliation and must not be blindly retried; a succeeded task and its verified Artifact stay durable
facts, and if duplicate external effects occurred I compensate rather than delete history. After recovery I
verify authoritative PostgreSQL state, Provider and Artifact evidence, and idempotency records, add
regression coverage for failed polling and replacement-task creation, and roll out gradually while
monitoring duplicate creation, reconciliation backlog, and callback/polling errors. Rolling back the
workflow stops future harm but does not undo committed tasks or external side effects."

### Common Weak Answer

"The poll returned 503 and the n8n run timed out, so the task failed — I create a new task with a fresh
request_id, and when two completion callbacks arrive I publish both."

Strong Answer (why it fails): "This treats observation failure as task failure, treats an orchestration
timeout as a business terminal state, mints a new command that duplicates paid work, and treats
at-least-once delivery as two completions. Instead: keep the same `task_id` and back off, reuse the same
`request_id` so FastAPI returns the existing task, and dedupe callbacks on `event_id` with an idempotent
downstream effect so the report publishes once."

### Follow-up Questions

Beginner follow-up: If the n8n execution disappears entirely, is the task lost?

Strong Answer: "No — the task is a durable backend fact. A new or restarted execution re-observes the same
`task_id`; the orchestrator's disappearance changes nothing about the committed task."

Intermediate follow-up: Why is a stable `event_id` (not the payload contents) the right dedupe key for
at-least-once callbacks?

Strong Answer: "Because the same completion can be delivered more than once with identical contents; a
stable `event_id` lets the gate recognise the redelivery and make the downstream action a no-op, giving
exactly-once *effect* without claiming exactly-once *delivery*."

Senior follow-up: A running replacement task may already have called the paid Provider. Why
`PENDING_RECONCILIATION` rather than cancel or retry?

Strong Answer: "Because the external effect is unknown: cancelling could strand a real charge/result and
retrying could double it. Reconciliation determines the authoritative outcome from Provider/Artifact
evidence before any irreversible action, and only a proven non-start would be safe to cancel or retry."

## 14. Mental Model Summary

```text
202 + task_id  ->  observe, don't re-do.
n8n timeout / Poll timeout / 503 / missing|dup|out-of-order Callback  ->  business state UNCHANGED by itself.
acceptance retry   = same request_id + fingerprint (same->existing task_id; different->409).
polling            = same task_id, bounded backoff + deadline + max attempts; terminal or reconcile.
identities         = request_id · task_id · correlation_id · event_id · task_version · trace_id(new per attempt).
callback           = AT-LEAST-ONCE: authenticate -> validate -> correlate -> dedupe event_id -> version ->
                     legal transition -> optional authoritative confirm -> ONE idempotent downstream action.
ordering           = order by task_version, not arrival; stale=no-op, conflict=integration error.
correlation_id     = association key, NOT authentication.
incident           = contain -> scope -> classify -> cancel/reconcile/compensate -> verify -> controlled rollout.
authority          = FastAPI/PostgreSQL; n8n history/logs/traces = evidence, never truth or retry permission.
```

> Classroom-authorship note: at the end of the session the student explicitly asked the Tech Lead to
> provide this final synthesis (*`你帮我总结`*) rather than making another independent attempt, and the Tech
> Lead supplied the complete Chinese mental model directly (per the live-teaching rule to answer
> immediately when asked). This summary is therefore taught material, not an independent student answer.

## 15. Today's Takeaway

Once a Task can outlive the workflow that started it, the only safe posture is: observe the same durable
identity, never let observation failure or delivery quirks masquerade as business outcomes, and react only
through idempotent, backend-owned actions. Reuse the business `request_id` so retries collapse; poll the
same `task_id` with bounds; treat callbacks as at-least-once and dedupe on `event_id`; order by
`task_version`, not by arrival; and on a bad release, stop new orchestration, then classify and
cancel/reconcile/compensate through FastAPI — because deletion cannot undo a Provider charge or an external
side effect.

## 16. Before Next Lesson Checklist

- [ ] I can explain why an n8n timeout / Poll 503 / missing-or-duplicate-or-out-of-order Callback does not
      change a Task's business state.
- [ ] I can design a bounded polling state machine (same `task_id`, backoff, observation deadline, max
      attempts, terminal stops) and choose Polling vs Callback vs Hybrid.
- [ ] I can keep acceptance idempotent by reusing `request_id` + fingerprint (and know when a new
      `request_id` is a new command / when to return 409).
- [ ] I can name the six identities and their roles, and know `correlation_id` is not authentication.
- [ ] I can run the at-least-once callback gate (authenticate → validate → correlate → dedupe `event_id` →
      version → legal transition → idempotent action) and reject stale/out-of-order and correlation-mismatch
      events.
- [ ] I can run the incident flow (contain → scope → classify → cancel/reconcile/compensate → verify →
      controlled rollout) and explain why deletion/blind-retry is wrong.
- [ ] I understand the evidence limits: Day68 is CONCEPTUAL_STATIC; the n8n runtime, FastAPI integration,
      polling/callback/PostgreSQL/Worker/Provider behaviours, and production are NOT RUN, no workflow JSON
      was exported, and Day67's `400` is not Day68 evidence.

---

Related: [Day68 n8n Long-running Job Orchestration Contract](../../projects/n8n-workflows/README.md)
· [cheat sheet](../../cheat_sheets/fastapi.md) · [interview](../../interview/fastapi.md)
· Previous: [Day67 — n8n Workflow Model, Triggers, FastAPI Integration and Responsibility Boundaries](day67-n8n-workflow-model-triggers-fastapi-integration-and-responsibility-boundaries.md)
· Next: Day69 — Human Approval, Retry, Secrets, Audit and Error Workflows
