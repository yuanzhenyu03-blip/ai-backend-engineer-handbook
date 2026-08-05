# Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation

## 1. Lesson Metadata

```text
Status: Completed
Template: LESSON_TEMPLATE_v2
Version: 1.0
Difficulty: Advanced
Estimated Time: 5-6 hours
Prerequisite: Day53 — OpenAI SDK, Provider Boundaries and Structured Output
Previous Lesson: Day53 — OpenAI SDK, Provider Boundaries and Structured Output
Next Lesson: Day55 — Celery, Worker Execution and Long-running AI Jobs
Engineering Artifact: projects/ai-backend-data-layer/api/day54-ai-streaming-client-disconnects-timeouts-and-cancellation-design.md
  + runnable day54_streaming_disconnects_timeouts_cancellation.py + test_day54_streaming_disconnects_timeouts_cancellation.py (in-memory control flow; 15 passed)
```

Main engineering artifact: a provider-neutral, standard-library-only in-memory model of the three lifecycles + the
durable cancellation/expiry protocol, plus the
[design/runbook](../../projects/ai-backend-data-layer/api/day54-ai-streaming-client-disconnects-timeouts-and-cancellation-design.md).

---

## 2. Learning Objectives

After this lesson you can:

- **Distinguish** the HTTP client connection, Provider request, and durable Job lifecycles, and state the boundary
  between them.
- **Distinguish** Provider token streaming from durable Job progress/event streaming, and never treat one as the
  other's durable truth.
- **Diagnose** an SSE disconnect: the durable running Job is unchanged; reconnection reads durable state/events.
- **Classify** a Provider timeout as non-terminal reconciliation with unknown-cost retention, not fabricated failure
  or blind retry.
- **Design** a durable, auditable, cooperative, guarded cancellation/deadline protocol (persist intent before signal).
- **Resolve** a completion-vs-cancellation race with a guarded terminal transition and a zero-row stop.
- **Decide** against default per-token persistence and defend the security/storage/recovery trade-off.
- **Recover** from an erroneous "disconnect → cancellation" rollout: stop new harm, build an affected set, reconcile
  from evidence, refuse blind state flips/re-calls.
- **Answer** beginner, intermediate, and senior interview questions in English.

---

## 3. Why This Matters

Day53 gave you a safe Provider boundary and guarded completion — but the moment a real Job streams to a real browser,
three lifecycles start racing. A browser loses Wi-Fi mid-stream; does the Job cancel? A Provider call times out; is the
Job failed? A user clicks "cancel"; can the Router just write `cancelled`? A late Provider result arrives after a
cancel; does it win? Getting these wrong is catastrophic in different ways: auto-cancelling a durable Job on every
disconnect throws away accepted, paid work; marking a timeout as `failed` and retrying duplicates billable Provider
execution; letting completion and cancellation overwrite each other corrupts the business fact; and a policy bug that
turns disconnects into cancellations can silently kill thousands of Jobs. Day54 makes the three lifecycles independent
and makes cancellation a durable, auditable, cooperative, guarded protocol so none of these confusions can occur.

---

## 4. Roadmap Position

```text
Day52 authorized, funded Job
        |
Day53 Provider boundary + guarded result acceptance (timeout -> PENDING_RECONCILIATION)
        |
        v
Day54 streaming + three lifecycle boundaries + timeout/cancellation semantics   <-- you are here
        |
        v
Day55 supported-Celery long-running Worker execution -> Day56 retry/backoff, resilience, cost, backpressure
```

### Knowledge Continuity

```text
Previous Knowledge
  Day47 guarded UoW + zero-row stop; Day50 idempotency/Outbox + at-least-once + duplicate-absorbing guards;
  Day52 reservation/reconciliation; Day53 Provider boundary, guarded completion, PENDING_RECONCILIATION, unknown-usage honesty
        |
        v
Current Lesson Concept
  three independent lifecycles (HTTP / Provider / durable Job); two streaming kinds; disconnect ends only a subscription;
  timeout is non-terminal reconciliation; durable+auditable+cooperative+guarded cancellation/expiry; one guarded winner;
  policy rollback != business-fact rollback
        |
        v
Future Production Usage
  Day55 runs long work on a supported Celery broker while preserving this cancellation/lifecycle contract;
  Day56 uses the disconnect vs timeout vs deadline vs cancellation distinction to decide retry/backoff/backpressure
```

Day54 does NOT implement Day55 Celery, Day56 automatic retry/backoff, a production raw-token retention system, or a
concrete schema migration; and it claims no real FastAPI/SSE, Provider, PostgreSQL, Redis, or Celery runtime.

---

## 5. Lesson Map

```text
Three lifecycles (HTTP conn / Provider request / durable Job) -> disconnect ends only the subscription
  -> two streams: Provider tokens (transient) vs durable Job progress/events (observable, reconnectable)
  -> reconnect reads durable state/events, NOT a token replay; don't default-persist tokens (Day53 minimization)
  -> Provider timeout: PENDING_RECONCILIATION, reservation retained, unknown usage (never 0); 202 not retro-504
  -> cancellation/deadline: persist durable auditable intent FIRST -> Worker cooperative check -> guarded terminal
       pre-call: no Provider call ; mid-stream: best-effort abort, unknown cost retained (no fabricated zero)
  -> completion vs cancellation: one guarded winner, loser sees zero rows and stops/reconciles
  -> crash after intent -> re-observe (at-least-once), guarded transition absorbs repeats
  -> late result after terminal -> refused, no success overwrite
  -> erroneous disconnect->cancel rollout: rollback policy (stop harm) != business-fact rollback; evidence-based recovery
```

---

## 6. Core Mental Model

```text
HTTP connection lifecycle  = a client's subscription; a disconnect ends ONLY that subscription
Provider request lifecycle = one call's transient token stream; its outcome/usage may be UNKNOWN
Durable Job lifecycle      = a PostgreSQL-owned business fact; it does NOT auto-cancel on disconnect
Cancellation               = a DURABLE, auditable intent FIRST -> cooperative Worker check -> GUARDED terminal write
Guarded terminal write     = exactly one winner (completion OR cancellation); the loser sees zero rows -> stop/reconcile
Policy rollback            = stop FUTURE harm; it is NOT a rollback of durable business facts
```

---

## 7. Main Concepts

## Concept 1: Three lifecycles — what an SSE disconnect actually ends

### Tech Lead Question

A Worker is consuming a Provider token stream while the browser watches Job progress over SSE. The browser loses
network. What happens to the durable Job?

### Student Thinking

The student reached for the familiar durable Job-state vocabulary first.

### Student Answer

First: "queued running success" (durable Job-state words, but answering the wrong lifecycle); and on the durable state
after the disconnect while running: "保持running".

### Tech Lead Review

The second answer is right. An SSE disconnect ends the HTTP client connection lifecycle — that subscription — only. The
Provider request lifecycle is independent and its outcome may be unknown. The durable Job lifecycle is a
PostgreSQL-owned business fact that stays `running` unless an explicit durable protocol changes it. The first answer
conflated the Job lifecycle with the three-lifecycle question. Boundary: HTTP disconnect ≠ the Provider call stops ≠
the Job auto-cancels ≠ the business commitment disappears.

### Engineering Thinking

Independent lifecycles are what let a browser drop, reconnect, and still see a correct, accepted Job — instead of
throwing away paid work on every flaky network.

### Framework Connection

`SubscriptionRegistry.disconnect` ends a subscription and never touches the `JobStore`.

---

## Concept 2: Two kinds of streaming

### Tech Lead Question

Map the two streams: the Worker reading Provider tokens, and the browser reading Job progress. Which is which?

### Student Answer

"第一个对应第一个第二个对应第二个" — correctly mapping the Worker's Provider tokens to Provider token streaming and the
browser's events to durable Job progress/event streaming.

### Tech Lead Review

Correct. Provider token streaming is transient chunks for one Provider request. Durable Job progress/event streaming is
safe observable state for an already-persisted Job, designed for subscription/reconnection. Never treat either as the
other's durable truth.

### Framework Connection

`FakeProviderStream` (transient tokens) vs `JobStore` events + `reconnect_view` (durable observable state).

---

## Concept 3: Reconnection and the persistence trade-off

### Tech Lead Question

The browser reconnects. What should it read — and should you persist every Provider token as a `JobEvent` so it can
replay?

### Student Answer

Reconnection should use "查询/订阅 durable Job 状态与进度事件"; persist every token as a Job event by default: "不应该".

### Tech Lead Review

Both correct. Reconnection reads/subscribes to durable Job state + safe progress events, not a Provider token replay.
Do not default-persist every token: it inflates writes/storage, can retain unvalidated/partial/sensitive content, and
conflicts with Day53 raw-data minimization. Persist low-frequency safe milestones; persist the final Result Artifact
only after Day53 validation + guarded completion. A replayable partial-text product needs its own explicit design.

### Framework Connection

`JobStore.add_event` (safe milestones only); the Worker never persists raw tokens.

---

## Concept 4: Timeout is non-terminal reconciliation

### Tech Lead Question

A Provider call times out. Do you mark the Job `failed` and retry? And does that timeout turn the original `202` into a
`504`?

### Student Answer

Mark failed and retry: "不能". Original 202 vs later Provider timeout: "不需要，只是返回一次，provider timeout也不表示
provider没有产出artifact以及没有在持续运行".

### Tech Lead Review

Correct. A Provider timeout means our side didn't receive a response in time; execution, raw result, and usage may be
unknown → `PENDING_RECONCILIATION`, reservation retained, no invented zero usage, no blind re-call (Day53 preserved).
The original `202` is not retroactively a `504`; users observe later state through Job reads/events. Refinement: the
Provider may have raw output, but it does not own/create the application's Result Artifact — only Day53 validation +
guarded completion creates that.

### Framework Connection

`record_timeout_pending` -> `PENDING_RECONCILIATION`; `reconnect_view` shows it; no HTTP status rewrite.

---

## Concept 5: The durable cancellation / deadline protocol

### Tech Lead Question

A user cancels. Can the Router write `cancelled` because the HTTP request arrived? What do you persist first, and why?

### Student Answer

Router direct cancellation: "不能". Cancellation detected before the Provider call: "是不调用并尝试 guarded transition
到 cancelled". Intent persistence order: "应先写入 durable expiry/cancellation intent，因为可以重试". Job deadline:
"触发一个 durable、auditable、cooperative 的 Job-level cancellation/expiry protocol".

### Tech Lead Review

All correct. The Router authorizes and persists a durable, auditable intent first (reason, timestamp, actor/system
source) — it must not write `cancelled` just because HTTP arrived. The Worker cooperatively observes the intent at safe
points: before the Provider call it does not call the Provider and attempts a guarded terminal cancellation. Extend the
"can retry" reasoning: persistence also survives process loss, gives auditability, and lets Workers re-observe
at-least-once — but it does NOT authorize Day56-style blind Provider retries. A deadline shares the same
durable/auditable/cooperative/guarded constraints with a different trigger (`expired`).

### Framework Connection

`request_cancellation` (intent only) -> `run_worker` pre-call check -> `guarded_terminal_transition`.

---

## Concept 6: Mid-stream cancellation is best effort

### Tech Lead Question

You cancel while tokens are streaming and close the Provider stream. Does that prove the remote model stopped and cost
is zero?

### Student Answer

"不能".

### Tech Lead Review

Correct. A mid-stream best-effort abort/stream-close stops publishing tokens to the client and records safe correlation
evidence, but it does not prove remote execution stopped or that cost is zero. Unknown usage stays
`reconciliation_pending`; never fabricate zero cost, never auto-release the reservation.

### Framework Connection

`run_worker` mid-stream: `stream.abort()` + `hold_cost_reconciliation` + guarded terminal cancel.

---

## Concept 7: Completion vs cancellation — one guarded winner

### Tech Lead Question

Completion and cancellation race. Should either overwrite the other? And can a late valid result after a terminal
cancel make the Job `succeeded`?

### Student Answer

Completion/cancellation overwrite: "不应该". Late result after terminal cancellation/expiry: "不能".

### Tech Lead Review

Correct. Both use guarded terminal writes; exactly one wins and the loser sees zero rows and stops/reconciles rather
than overwriting. A late valid Provider result after a terminal cancellation/expiry cannot flip the Job to `succeeded`;
no Result Artifact/success overwrite follows the late path.

### Framework Connection

`guarded_terminal_transition` (one WON, one ZERO_ROWS); `ingest_late_provider_result` -> `REFUSED_TERMINAL`.

---

## Concept 8: Crash recovery + the erroneous-disconnect rollout

### Tech Lead Question

A Scheduler crashes right after an intent is persisted. Is it lost? And a bad deploy turned every SSE disconnect into a
cancellation intent — how do you recover?

### Student Answer

Scheduler crash after intent: "因为worker会再次扫描intent，进行重试". Bad-deployment bulk state flip: "不能". Recovery
evidence: "provider request id、idempotency key、usage". Unknown Provider outcome after erroneous cancellation: "不能"
(do not directly re-call the Provider).

### Tech Lead Review

Correct. A persisted intent survives a crash: a restarted Worker re-observes it (at-least-once) and the guarded
transition absorbs repeats. For the bad rollout: FIRST roll the policy back to stop new harm (not a business-fact
rollback); do not bulk-flip terminal Jobs back to `running`; build the affected set from release version + a bounded
time window + stable intent IDs; retain audit history. Extend the evidence: a client idempotency key proves logical Job
acceptance, not Provider execution — Provider request/correlation/cost evidence decides reconciliation. If a request id
exists but result/usage are unknown, retain the reservation and reconcile; never blindly re-call the Provider.

### Framework Connection

`scan_open_intents` + `apply_cancellation` (repeat -> zero rows); `DisconnectPolicy.rollback`, `build_affected_set`,
`classify_recovery`.

---

## 8. Common Misconceptions

The correction trajectories from class (initial model -> reasoning -> correction -> durable model):

1. **"queued running success" for an SSE-disconnect question.** Reasonable (Job state is familiar and important), but
   it conflated the Job lifecycle with the three-lifecycle question. Correct: a disconnect ends the HTTP subscription
   only; the Provider outcome can be unknown; the durable Job stays `running` unless an explicit durable protocol
   changes it.

2. **Timeout/Artifact terminology.** The student rightly said a timeout doesn't mean the Provider produced nothing or
   stopped running. Refine: the Provider may have raw output, but it does not own/create the application's durable
   Result Artifact — only Day53 validation + guarded completion creates that.

3. **"Persist first because it can retry."** Correct and extended: persistence also survives process loss, gives
   auditability, and lets Workers re-observe at-least-once. It does NOT authorize Day56-style blind Provider retries.

4. **Recovery evidence.** Provider request ID, idempotency key, usage — correct, extended: the client idempotency key
   proves logical Job acceptance, not external Provider execution; Provider correlation/attempt/cost evidence decides
   reconciliation.

> The final Chinese engineering summary produced in class was **assistant-assisted** (the student explicitly asked the
> assistant to produce it); it is labeled as such and is not presented as independently authored student prose.

---

## 9. Engineering Trade-offs

- **Auto-cancel on disconnect vs keep the durable Job.** Auto-cancel frees resources instantly but discards accepted,
  paid work on any flaky network. Chosen: keep the durable Job; cancel only via the explicit protocol.
- **Persist every token vs safe milestones.** Full-token persistence enables replay but inflates storage, retains
  unvalidated/sensitive content, and breaks Day53 minimization. Chosen: low-frequency safe milestones + the validated
  final Artifact; a replay product is a separate explicit design.
- **Mark timeout failed (+retry) vs reconciliation-pending.** Failing fast is simple but fabricates a fact and can
  duplicate billable execution. Chosen: `PENDING_RECONCILIATION`, retain reservation, reconcile.
- **Router writes cancelled vs persist intent first.** A direct write is fewer steps but loses durability/audit and
  races completion. Chosen: durable intent first, cooperative Worker, guarded terminal write.
- **Bulk-flip affected Jobs vs evidence-based recovery.** Bulk flipping is fast but rewrites business facts blindly.
  Chosen: policy rollback (future harm) + per-Job evidence-based reconciliation, never a blind flip/re-call.

---

## 10. Hands-on Exercises

1. Diagnose an SSE disconnect: keep the durable running Job unchanged.
2. Identify the two streams and choose durable Job state/events for reconnect.
3. Classify a Provider timeout as non-terminal reconciliation rather than definite failure/retry.
4. Design a durable cancellation/deadline protocol and choose persist-intent-before-signal.
5. Resolve a completion-vs-cancellation race with guarded transitions / zero-row stop.
6. Decide against default per-token persistence and explain the security/storage/recovery trade-off.
7. Integrated failure/rollback: an erroneous "SSE disconnect → cancellation intent"; stop new harm, build an affected
   set, preserve audit, reconcile external evidence, and refuse blind state flips/re-calls.
8. Complete Beginner, Intermediate, and Senior English interview answers.

Run the model:

```bash
cd projects/ai-backend-data-layer/api
python3 -m pytest -q test_day54_streaming_disconnects_timeouts_cancellation.py   # 15 passed (standard-library only)
```

---

## 11. Relevant Framework Connections

- **FastAPI**: `202 + job_id` admission is separate from later Job observation; an SSE disconnect / connection timeout
  ends a subscription, not the Job; later state is read through a Job endpoint or event subscription.
- **PostgreSQL / Day47 guarded UoW**: durable cancellation/expiry intent, audit evidence, guarded terminal transition,
  and a zero-row stop/reconciliation.
- **Day45/Day53 Provider Adapter**: the Provider token stream and best-effort abort remain Provider-boundary concerns;
  the Adapter does not own durable Job truth.
- **Day50 idempotency / Outbox**: the client idempotency key is acceptance identity; durable notification/Worker
  observation can be repeated, while guarded facts absorb duplicates.
- **Day55 (future)**: Celery will execute long work but must preserve this protocol; no Celery runtime is claimed here.

---

## 12. AI Backend Connections

- A multi-tenant AI Research Job with Provider token streaming and an SSE Job-progress subscription.
- Raw-output minimization, strict structured-output validation, and final Result Artifact ownership.
- Unknown Provider execution/usage, budget reservation retention, and cost reconciliation.
- Cancellation of potentially billable long-running model calls without falsely claiming remote abort or zero cost.
- Release rollback and evidence-based recovery for wrongly cancelled AI Jobs.

---

## 13. English Interview

Key vocabulary: HTTP connection lifecycle, Provider request lifecycle, durable Job lifecycle, SSE subscription, token
streaming vs progress/event streaming, reconnection, Provider timeout, `PENDING_RECONCILIATION`, durable cancellation
intent, cooperative cancellation, guarded terminal transition, zero-row stop, deadline/expiry, at-least-once
observation, policy rollback vs business-fact rollback, evidence-based recovery.

### Beginner — what does an HTTP client disconnect mean for a durable Job?

Actual answer: "http client disconnect means subscribe finished, cancellation of a durable background Job is a durabel
cancellation intent".

Strong answer: "An HTTP client disconnect just means the client subscription has ended — the durable background Job is
unaffected and stays running. Cancelling a durable Job is different: it starts with a durable, auditable cancellation
intent, then requires the Worker to cooperate and a guarded terminal transition to actually make it `cancelled`."

### Intermediate — a Provider call times out; do you retry immediately?

Actual answer: "retry the provider call may waste provider".

Strong answer: "No — an immediate retry may waste Provider capacity, and more importantly a timeout leaves the
execution, result, and usage unknown, so an immediate retry can duplicate execution and cost. I move the Job to a
reconciliation-pending state, keep the budget reservation, and reconcile from Provider correlation/usage evidence
rather than fabricating a failure or a zero cost."

### Senior — design cancellation for a long-running, billable, streaming Job (incident runbook)

Strong answer: "First, an authorized cancel request persists a durable, auditable intent — reason, timestamp, actor —
it does not directly write `cancelled`. A Worker observes the intent cooperatively: before the Provider call it doesn't
call the Provider and takes a guarded terminal transition; mid-stream it best-effort aborts the Provider stream, stops
publishing tokens, records correlation evidence, and takes a guarded transition — without claiming the remote model
stopped or that cost is zero, so unknown usage stays reconciliation-pending. Completion and cancellation both use
guarded terminal writes, so exactly one wins and the loser sees zero rows and reconciles. A crash after the intent is
persisted is safe because a restarted Worker re-observes it and the guarded transition absorbs repeats. And if a bad
release turned disconnects into cancellations, my first step is to roll the policy back to stop new harm — that is not a
business-fact rollback; I then build an affected set from release version and a bounded time window, keep the audit
history, and reconcile each Job from Provider evidence instead of blindly flipping state or re-calling the Provider."

---

## 14. Mental Model Summary

```text
HTTP connection | Provider request | durable Job = THREE independent lifecycles
  SSE disconnect --ends--> the subscription ONLY (durable Job stays running; nothing durable written)
  Provider tokens = transient (never durable truth) ; durable Job progress/events = observable + reconnectable
        |
        v
Provider timeout --> PENDING_RECONCILIATION (reservation retained, usage unknown, never 0; 202 not retro-504)
        |
        v
cancel/deadline: durable auditable INTENT first --> cooperative Worker check --> GUARDED terminal (cancelled/expired)
  pre-call: no Provider call ; mid-stream: best-effort abort, unknown cost retained (no fabricated zero)
        |
        v
completion vs cancellation: ONE guarded winner; loser = zero rows -> stop/reconcile ; late result after terminal -> refused
        |
        v
crash after intent -> re-observe (at-least-once, repeats absorbed) ; policy rollback stops FUTURE harm != business-fact rollback
```

---

## 15. Today's Takeaway

Three lifecycles — HTTP connection, Provider request, durable Job — are independent, and confusing them corrupts
business truth or wastes billable work. A browser disconnect ends only a subscription; a Provider timeout is
non-terminal reconciliation, not failure; a cancellation or deadline must become a durable, auditable intent that a
Worker cooperatively turns into a guarded terminal fact; completion and cancellation never overwrite each other (zero
rows means stop and reconcile); and a policy rollback stops future harm but never blindly rewrites durable facts.

---

## 16. Before Next Lesson Checklist

- [ ] I can name the three lifecycles and say exactly what an SSE disconnect ends.
- [ ] I can separate Provider token streaming from durable Job progress/event streaming.
- [ ] I can explain why reconnection reads durable state/events and why tokens aren't default-persisted.
- [ ] I can classify a Provider timeout as `PENDING_RECONCILIATION` with unknown-cost retention.
- [ ] I can design persist-intent-first cancellation with a cooperative Worker + guarded terminal write.
- [ ] I can resolve a completion-vs-cancellation race and refuse a late result after a terminal state.
- [ ] I can recover from an erroneous disconnect→cancel rollout without a blind flip or re-call.
- [ ] Next: Day55 runs long work on a supported Celery broker while preserving this cancellation/lifecycle contract.
