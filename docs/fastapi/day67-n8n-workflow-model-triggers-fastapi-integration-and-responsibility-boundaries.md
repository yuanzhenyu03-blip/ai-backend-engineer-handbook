# Day67 — n8n Workflow Model, Triggers, FastAPI Integration and Responsibility Boundaries

## 1. Lesson Metadata

```text
Status:        ✅ Completed — lesson + n8n draft-workflow configuration record; classroom EXECUTED_LOCAL_RUNTIME (invalid-input 400 only)
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 3-4 hours
Prerequisite:  Day66 queue-backed permissioned worker; Day59-Day61 real backend + Job/Outbox lifecycle
Previous Lesson: Day66 — Queue-backed Playwright Worker as a Permissioned AI Tool
Next Lesson:   Day68 — Long-running AI Jobs: Polling, Callback, Correlation and Idempotency
Engineering Artifact: projects/n8n-workflows/ (Day67 draft-workflow configuration record; NO exported JSON captured)
```

Day67 introduces n8n as a **permissioned orchestration layer** around a FastAPI-owned durable task
system. n8n may trigger and coordinate work, but authorization, durable acceptance, idempotency, recovery,
and audit stay under FastAPI control. Workflow executions are NOT durable business Tasks.

> Evidence honesty. Three distinct tiers are used deliberately in this lesson:
>
> * `CONCEPTUAL_STATIC` — the responsibility-boundary architecture and the drawn workflow design.
> * static configuration review — the node-by-node n8n configuration inspected in the editor (a
>   configured-looking node is NOT runtime proof).
> * `EXECUTED_LOCAL_RUNTIME` — the ONE thing actually executed in class: a real local n8n invalid-webhook
>   test that returned **HTTP 400** with the documented JSON error; the IF false branch and its Respond to
>   Webhook node ran, and the HTTP Request node did NOT run.
>
> **NOT RUN / NOT CONFIGURED:** a valid FastAPI success path, service authentication, durable Task
> creation, PostgreSQL persistence, queue/Outbox dispatch, browser-worker execution, a published
> Production URL, and production readiness. The HTTP endpoint was an unverified local placeholder
> (`http://host.docker.internal:8000/api/v1/browser-tasks`) with authentication intentionally `None`. **No
> exported n8n workflow JSON was captured into the repository** — the artifact is a documented
> configuration record, not an importable/runnable file.

## 2. Learning Objectives

By the end of Day67 you can:

* Explain the n8n workflow model — `trigger -> execution -> nodes -> result` — and place Webhook Trigger,
  Schedule Trigger, Edit Fields, IF, HTTP Request, and Respond to Webhook correctly.
* State the integration boundary: n8n calls **authenticated FastAPI**, never PostgreSQL, the queue, or the
  browser worker directly.
* Explain why a published/active n8n Webhook receiving an event is **not** FastAPI durably accepting a
  Task, and when `202 + task_id` may honestly be returned.
* Distinguish a Test URL's manual-listening lifecycle from a published Production URL, and why neither
  implies durable backend acceptance.
* Separate service identity from business/user identity, and prefer short-lived scoped delegation over
  forwarding long-lived user login tokens.
* Separate the three retry layers (n8n transport retry, FastAPI business idempotency, worker execution
  retry) and choose a reconciliation idempotency basis.
* Roll back a bad workflow safely: stop future orchestration first, then compensate durable business facts
  through FastAPI — never by deleting durable Task records.

## 3. Why This Matters

A low-code orchestrator is attractive precisely because it can call anything — which is also the danger.
If n8n can write `browser_tasks` directly, hand a workflow a long-lived user token, or claim it "accepted"
a task just because a Webhook fired, then authorization, idempotency, recovery, and audit quietly leak out
of the backend into a place with no transactions and no policy engine. n8n's execution history is real and
useful as ORCHESTRATION evidence, but it is not the authoritative business audit source and cannot
atomically commit business state together with an external side effect — FastAPI and its database remain
the authoritative boundary for business facts, authorization, idempotency, and audit. Day66 spent
the whole lesson proving that the LLM proposes and FastAPI owns everything durable. Day67's job is to add
orchestration **without moving any of those boundaries**: n8n orchestrates, FastAPI still owns the truth.
The classroom failure mode that makes this concrete is small but exact — a node that *looks* configured
routed a malformed request into the HTTP branch and returned an empty 200, because an `$json...`
expression never evaluated. Configuration is not behavior; only a re-run proves it.

## 4. Roadmap Position

```text
Day66 durable acceptance + permissioned worker (FastAPI owns authorization/truth/dispatch/recovery/audit)
  -> Day67 n8n workflow / trigger / orchestration boundary   <- YOU ARE HERE (Phase 6 begins)
  -> Day68 polling, callback, correlation, and idempotency (make the FastAPI <-> n8n boundary observable + retry-safe)
  -> Day69 human approval, retry, secrets, audit, and error workflows
```

Day67 opens Phase 6 (n8n AI Workflow Integration). It reuses the Phase 5 backend and the Day66 ownership
model unchanged. Day68 will make the FastAPI ↔ n8n boundary observable and retry-safe through
polling/callback contracts, correlation IDs, and idempotency; Day69 adds human-in-the-loop approval, error
workflows, retry control, secret handling, and auditability. Those are cross-referenced here only as
dependencies of this boundary — they are **not** implemented in Day67.

## 5. Lesson Map

```text
1. The integration boundary: n8n -> authenticated FastAPI (never DB/queue/worker directly)
2. Acceptance semantics: Webhook receipt != durable acceptance; 202 + task_id only after FastAPI commits
3. The local draft workflow: Webhook -> Edit Fields -> IF -> (HTTP Request | Respond 400)
4. Trigger semantics: Test URL lifecycle vs published Production URL; Webhook vs Schedule
5. Authentication & identity: service identity != business/user identity; short-lived delegation
6. Retry & idempotency: n8n transport retry vs FastAPI business idempotency vs worker execution retry
7. Production failure & rollback: stop orchestration first; compensate through FastAPI
```

## 6. Core Mental Model

```text
n8n            = permissioned ORCHESTRATION only: triggers, mapping, branching, HTTP calls, version rollback.
                 It has NO authority to create or mutate a durable Browser Task, and NO direct DB/queue/worker access.
FastAPI        = the trusted business + security boundary: authentication/authorization, durable Task
                 acceptance, the idempotency record, and reconciliation/cancellation/compensation APIs.
Workflow execution != durable business Task.
Webhook receipt   != FastAPI durable acceptance.
Test URL          != Production URL != durable backend acceptance.
Service identity  != tenant/user identity != action authorization.
n8n may resend an uncertain call; FastAPI collapses the same intent by idempotency key.
Rollback: stop future orchestration first, then compensate durable facts through FastAPI — never delete Task records.
```

### Mental Model Evolution (Day66 → Day67)

```text
Day66: LLM PROPOSES a tool call; FastAPI owns authorization, durable truth, dispatch, recovery, audit;
       the queue is only a notification; worker claim/lease/final fence protects execution.
Day67: n8n ORCHESTRATES (trigger -> nodes -> HTTP -> respond); it inherits Day66's boundaries UNCHANGED.
       n8n is one more untrusted proposer/caller in front of FastAPI — a workflow node has exactly the
       same lack of authority as an LLM proposal: it may ASK FastAPI, but it never creates the durable
       Task, never owns idempotency, never owns recovery, and never becomes the audit source of truth.
```

## 7. Main Concepts

### Concept 1: The integration boundary — n8n calls authenticated FastAPI

Tech Lead Question:

Should the n8n workflow reach the durable system directly (PostgreSQL / the queue / the browser worker),
or should it go through authenticated FastAPI?

Student Thinking:

The workflow needs to "start a browser task," so the shortest path is tempting — but something has to own
authorization and the transaction.

Student Answer:

*“B,现在当前我已经启动了本地n8n”* — chose the n8n → authenticated FastAPI boundary and started a local n8n
for the artifact work. Reason: *“因为FastAPI是受信任的业务与安全边界”*. And on who may create the task:
*“没有node有权创建”*.

Tech Lead Review:

Correct. No n8n node has authority to create a durable Browser Task. An HTTP Request node only **asks**
FastAPI; the FastAPI transaction is what creates Task + contract + Outbox as appropriate. Even when n8n
"checked" something first, FastAPI must revalidate — the student affirmed this (*“是，因为FastAPI是受信任的
业务与安全边界”*).

Engineering Thinking:

Keep one authoritative boundary. Durable truth, authorization, and audit belong to a system with
transactions and a policy engine; an orchestrator that can call anything must still be treated as an
untrusted caller.

Production Example:

A user clicks "Generate research report." The n8n workflow POSTs to
`POST /api/v1/browser-tasks`; FastAPI authenticates the service, authorizes the tenant/action, and commits
Task + contract + Outbox in one transaction. n8n never touches `browser_tasks`.

Framework Connection:

n8n `HTTP Request` node → FastAPI route with `Depends(...)` auth; the durable write is a single FastAPI/DB
transaction, exactly as in Day66's acceptance path.

Exercise:

State one reason (schema coupling / bypassed policy / transient-state misread) why even read-only direct DB
access from n8n is unsafe. (Covered in Concept 7 and Section 10.)

```text
n8n (untrusted caller)  --HTTP-->  FastAPI (auth + policy + tx)  -->  durable Task/contract/outbox
```

### Concept 2: Acceptance semantics — receipt is not acceptance

Tech Lead Question:

An n8n Webhook received an event. Is that the same as the task being durably accepted, and when may the
workflow answer `202 + task_id`?

Student Thinking:

The Webhook fired, so the request "arrived" — but arriving is not the same as being committed.

Student Answer:

*“在 FastAPI 耐久接受任务后就返回安全的 202 + task_id”*. And that a Production Webhook receipt does not let
n8n claim durable acceptance before FastAPI receives/commits: *“不能”*.

Tech Lead Review:

Correct. A published/active Webhook receiving an event is **not** FastAPI accepting a durable task. `202 +
task_id` is honest only **after** FastAPI commits acceptance. If n8n fails before that commit, it must
return a failure (e.g. 502/503) or allow an upstream retry — it must never invent a `task_id`.

Engineering Thinking:

A response code is a promise about durable state. Only the system that committed the state may make that
promise.

Production Example:

n8n POSTs to FastAPI but the pod is killed mid-call. The workflow returns 502; the caller retries with the
same `request_id`; FastAPI either commits once or returns the already-committed `task_id`.

Framework Connection:

FastAPI returns `202 Accepted` with `{"status":"accepted","task_id":...}` only inside/after the commit;
n8n's `Respond to Webhook` node relays that, it does not originate it.

Exercise:

Given "Webhook received but FastAPI unreachable," pick the correct workflow response and justify it.

### Concept 3: Static configuration versus runtime behavior (the draft workflow)

Tech Lead Question:

You built the draft workflow and every node *looks* configured. Is a configured-looking workflow proof of
correct behavior?

Student Thinking:

The IF and Edit Fields nodes are filled in, so the branch logic should route correctly on the first run.

Student Answer (runtime record):

On the first real run a malformed request was misrouted into the HTTP Request branch and returned an
**empty 200**; the placeholder HTTP call then failed to connect. The cause was that expression fields
using `$json...` did not evaluate as intended.

Tech Lead Review:

A node UI that looks configured is **not** runtime proof. The fix was to use explicit `{{ $json... }}`
expressions in Edit Fields, IF conditions, and the HTTP body, then rerun the identical invalid input.
Only after the rerun did the workflow behave correctly. The draft (`Day67 - FastAPI Orchestration
Boundary`) was kept as a **draft, not published/activated**:

```text
Webhook (test path: day67/research-report)
  -> Edit Fields (map report_scope, request_id)      # explicit {{ $json.body.report_scope }} etc.
  -> IF ({{ $json... }} both present?)
       true  -> HTTP Request (POST placeholder) -> Respond to Webhook (202 JSON)   # NEVER executed
       false -> Respond to Webhook (400 JSON)
```

* Allowed inputs: `report_scope`, `request_id`.
* Invalid body: `{ "error": "invalid_request", "message": "report_scope and request_id are required" }`.
* Intended success body: `{ "status": "accepted", "task_id": "..." }` (INTENDED — never executed).
* HTTP endpoint (unverified local placeholder): `http://host.docker.internal:8000/api/v1/browser-tasks`.
* HTTP authentication intentionally `None`. **No exported workflow JSON was captured** — this is a
  documented configuration record, not an importable/runnable artifact.

Engineering Thinking:

Configuration is not behavior. Trust a branch only after an execution record proves which nodes actually
ran.

Production Example:

A "validated" workflow silently routes bad input to the success branch because an expression never
evaluated; only the execution log (which node ran) reveals it.

Framework Connection:

n8n expressions must be `{{ ... }}`; the Executions panel shows the real per-node path — the ground truth
used in Section 10.

Exercise:

Reproduce the invalid-input 400 and confirm from the execution record that the HTTP Request node did NOT
run. (Full steps in Section 10.)

### Concept 4: Trigger semantics — Test URL vs Production URL; Webhook vs Schedule

Tech Lead Question:

The Test URL behaved unreliably. Is that fundamentally a concurrency problem?

Student Thinking:

Initial guess: it is likely a concurrency issue — concurrent calls make a temporary test endpoint visibly
flaky.

Student Answer / Correction:

Reasonable but not the root cause. The root problem is **lifecycle**: a Test URL exists only while n8n is
actively listening for a test event; it is not a continuously registered production endpoint. Concurrency
is secondary.

Tech Lead Review:

A Production URL requires a published/activated workflow — but production availability still does **not**
mean durable backend acceptance. A Webhook Trigger serves an external request; a Schedule Trigger drives
internal periodic work such as reconciliation, and a scheduled reconciliation workflow must call an
**authenticated FastAPI reconciliation API**, not scan `browser_tasks` directly.

Engineering Thinking:

Distinguish three lifecycles — debug listening, published entrypoint, and durable acceptance — and never
collapse them.

Production Example:

A "prod" Schedule Trigger reconciles stuck jobs by calling `POST /api/v1/reconcile` hourly; it never opens
a DB connection to the tasks table.

Framework Connection:

n8n Webhook (Test URL vs Production URL) and Schedule Trigger; FastAPI reconciliation endpoint as the only
door to durable state.

Exercise:

Explain why moving from Test URL to a published Production URL still does not let n8n claim durable
acceptance.

### Concept 5: Authentication and identity

Tech Lead Question:

n8n attached a shared service credential and sent `tenant_id`/`user_id` in the body. Does that make the
body identity trustworthy?

Student Thinking:

The call is authenticated, so maybe the identity it carries can be trusted too.

Student Answer:

*“不能”* — a shared service key does not make the body tenant identity trustworthy; and *“不能”* to handing
a long-lived user login token to n8n.

Tech Lead Review:

Correct. A shared service credential proves the calling workflow/service — not the tenant, the final user,
or the action authorization. Do not trust body-provided `tenant_id`/`user_id`, and do not store or forward
a long-lived user login token through n8n execution data.

Engineering Thinking:

Separate service identity from business/user identity from action authorization; bind delegation narrowly
and briefly.

Production Example:

Instead of forwarding a user's session token, FastAPI resolves trusted context by `request_id`, or n8n
carries a short-lived signed delegation token bound to tenant, user, allowed action, request ID, and
expiry.

Framework Connection:

n8n service credential on the HTTP Request node ≠ end-user identity; FastAPI auth dependency derives the
real tenant/user server-side.

Exercise:

Design a delegation-token claim set that lets FastAPI authorize exactly one action for one request.

### Concept 6: Retry and idempotency (three separate layers)

Tech Lead Question:

An HTTP call's outcome is uncertain. Who owns the retry — n8n, FastAPI, or the worker?

Student Thinking:

FastAPI owns business correctness, so maybe FastAPI should own retry.

Student Answer / Correction:

The student first centered retry on FastAPI (*“由 FastAPI 负责”*), then identified the reused idempotency
key/request ID (*“idempoetency key”*). Correction into three layers: **n8n** owns whether to re-send an
uncertain transport call; **FastAPI** owns business idempotency so repeated delivery returns the existing
`task_id` rather than duplicating work; the **worker** owns execution retry.

Tech Lead Review:

The safe model is "n8n can resend; FastAPI collapses the same intent." For scheduled reconciliation, bind
idempotency to `task_id + recovery_action + recovery_generation` — the original Task identity alone does
not express every future legitimate recovery action (the student first bound reconciliation to the
original Task identity, *“使用它扫描到的原始 Browser Task 的标识作为幂等依据”*, then refined it).

Engineering Thinking:

Make redelivery safe by design: transport retry is cheap and expected; business correctness comes from an
idempotency record, not from "trying only once."

Production Example:

n8n retries a timed-out POST twice; FastAPI's unique idempotency key means only one Task is created and the
same `task_id` is returned all three times.

Framework Connection:

n8n node "Retry On Fail" (transport) vs FastAPI idempotency record (Day59/Day50 acceptance) vs the Day66
worker execution-retry gate.

Exercise:

For a reconciliation that may legitimately run twice, choose the idempotency key and justify including
`recovery_generation`.

### Concept 7: Production failure and rollback

Tech Lead Question:

A bad workflow release is causing problems. What is your first move, and can you roll back by deleting the
n8n side or the task records?

Student Thinking:

Stop the bad entrypoint first; deleting things feels like an "undo," but durable facts may already exist.

Student Answer:

*“第一步应该回滚/停用 n8n 工作流入口”*; deleting the n8n side cannot cancel a durable backend task (*“不能”*);
and read-only direct n8n access to the Browser Tasks database is *“不接受”*.

Tech Lead Review:

Correct. First stop the blast radius (deactivate the bad workflow or publish a prior version). Then
identify affected requests from n8n execution history **and** authoritative FastAPI records. Repair via
FastAPI controlled cancellation, compensation, or reconciliation — never delete durable Task records as a
workflow rollback mechanism. Do not grant n8n even read-only direct access to `browser_tasks`: it creates
schema coupling, bypasses backend policy/audit, and can misinterpret transient lease/state.

Engineering Thinking:

Rollback stops future harm; committed facts and external side effects need compensation, not deletion.

Production Example:

`workflow.v2` mis-maps a field; you deactivate it, publish `v1`, list affected `request_id`s from
executions, and call FastAPI cancel/compensate for the durable Tasks — nothing is deleted.

Framework Connection:

n8n deactivate/version rollback + Executions list; FastAPI cancellation/compensation/reconciliation APIs as
the only mutation path.

Exercise:

Given a stale Task possibly mid-execution, choose compensation vs cancellation vs reconciliation and justify
it.

## 8. Common Misconceptions

These are the actual classroom missteps, kept as runtime-learning records — the final result did **not**
pass on the first static configuration.

1. **Test URL unreliability is a concurrency problem.** Initial answer: probably a concurrent-request
   issue (reasonable — concurrent calls make a temporary endpoint visibly flaky). Correction: the root
   cause is **lifecycle** — a Test URL exists only while manually listening for a test event; it is not a
   continuously registered production endpoint. Concurrency is secondary.
2. **A configured-looking node is runtime proof.** The first real run routed a malformed request into the
   HTTP Request branch and returned an **empty 200**, then the HTTP placeholder failed to connect. Cause:
   n8n expression fields using `$json...` did not evaluate as intended. Correction: use explicit
   `{{ $json... }}` expressions in Edit Fields, IF conditions, and HTTP body fields, then rerun the same
   invalid input. Durable lesson: **a node UI that looks configured is not runtime proof.**
3. **FastAPI should own retry.** Initial answer: FastAPI should own retry (reasonable — FastAPI owns
   business correctness). Correction: n8n owns whether to **re-send** an uncertain transport request;
   FastAPI owns **idempotency** so re-delivery preserves business semantics; the worker owns **execution**
   retry.
4. **"Using a new database connection" is the senior control.** The student correctly reused `request_id`
   to retrieve an existing job, but framed the key control as "using a new database connection." That
   phrasing is not the control and must not imply n8n accesses the database. Correction: FastAPI
   atomically persists/enforces idempotency, returns the existing `task_id`, and performs
   cancellation/compensation/reconciliation under backend control after a workflow rollback.

## 9. Engineering Trade-offs

* **n8n direct DB/queue access vs authenticated FastAPI calls.** Direct access is faster to wire but
  couples n8n to the schema, bypasses policy/audit, and lets a low-code layer misread transient
  lease/state. Day67 chooses authenticated FastAPI calls; durable truth stays in one place.
* **Forwarding a long-lived user token vs short-lived scoped delegation.** Forwarding is simplest but
  turns n8n execution data into a credential store and a lateral-movement path. A short-lived signed
  delegation token (tenant + user + allowed action + request ID + expiry), or a FastAPI-side `request_id`
  lookup, bounds the blast radius.
* **Trusting body identity vs server-side context.** Trusting `tenant_id`/`user_id` in the body is
  convenient but a shared service credential cannot vouch for them; server-side context resolution is the
  safe default.
* **Deleting Task records vs FastAPI compensation on rollback.** Deleting looks like a clean "undo" but
  destroys audit/recovery evidence and cannot un-run an external effect; controlled
  cancellation/compensation/reconciliation preserves truth.

## 10. Hands-on Exercises

Day67 has **no repository code artifact and no pytest** — the artifact is an n8n draft workflow and one
local runtime observation. The exercises below are reproducible against a **local** n8n only; the Test URL
is a debug entrypoint, not a production endpoint, and none of this is a CI, automated-test, or production
validation.

### Exercise 1 — Reproduce the invalid-input 400 (the only runtime proof)

Question:

Configure the draft workflow so a malformed request is validated and rejected, and prove which nodes
actually ran.

Think First:

Which branch should a request with an empty `report_scope` and a missing `request_id` take, and which node
must NOT run?

Starter Artifact (local n8n draft `Day67 - FastAPI Orchestration Boundary`):

```text
Webhook (test path: day67/research-report)
  -> Edit Fields  ({{ $json.body.report_scope }}, {{ $json.body.request_id }})
  -> IF (both present?)
       true  -> HTTP Request (POST placeholder) -> Respond to Webhook (202 JSON)
       false -> Respond to Webhook (400 JSON)
```

Reproduce (local only):

```text
1. In the n8n editor, open the draft and click "Execute workflow" (listen on the Test URL).
2. Send the invalid request to the local test webhook:

   curl -i -X POST http://localhost:5678/webhook-test/day67/research-report         -H "Content-Type: application/json"         -d '{"report_scope":""}'
```

Expected Output:

```text
HTTP/1.1 400 Bad Request
{"error":"invalid_request","message":"report_scope and request_id are required"}
```

Explanation:

This exercises the IF **false** branch only. In the n8n Executions panel the false-branch `Respond to
Webhook` node ran and the `HTTP Request` node did **NOT** run — so no FastAPI call, durable Task, database
write, queue/Outbox dispatch, or worker execution occurred. This is the single `EXECUTED_LOCAL_RUNTIME`
fact for Day67. (If instead you see an empty `200`, an expression is using `$json...` rather than
`{{ $json... }}` and the request was misrouted into the HTTP branch — fix the expressions and rerun the
identical request.)

Follow-up Question:

The valid/`true` branch (HTTP Request → FastAPI → `202 + task_id`) is deliberately NOT exercised here.
Which real things would have to exist and be configured before you could honestly test it? (A running,
authenticated FastAPI at the endpoint; durable Task creation; PostgreSQL; queue/Outbox; a worker — all
currently NOT RUN / NOT CONFIGURED, with the endpoint an unverified placeholder and auth `None`.)

### Exercise 2 — Static configuration vs runtime behavior

Question:

Every node looks configured. How do you prove the branch logic before trusting it?

Think First:

What single piece of evidence distinguishes "looks configured" from "behaves correctly"?

Starter Artifact:

The same draft, plus the n8n Executions panel after the run in Exercise 1.

Expected Output:

An execution record showing the exact per-node path (false branch ran; HTTP Request did not).

Explanation:

A configured-looking node is not runtime proof; the execution record is. The class's first attempt
returned an empty 200 because `$json...` did not evaluate — only the rerun with `{{ $json... }}` proved the
400 path.

Follow-up Question:

How would you catch the same class of bug in a future workflow before it reaches a published URL?

### Exercise 3 — Design a scheduled reconciliation boundary (system design)

Question:

Design a periodic reconciliation that recovers stuck browser tasks without giving n8n database access.

Think First:

What is the trigger, what does n8n call, and what is the idempotency basis?

Starter Artifact:

```text
Schedule Trigger -> HTTP Request (POST /api/v1/reconcile, authenticated) -> Respond/log
idempotency basis: task_id + recovery_action + recovery_generation
```

Expected Output:

A design in which n8n only calls an authenticated FastAPI reconciliation API and FastAPI owns the
decision, the idempotency, and the audit.

Explanation:

Scheduled work is internal periodic orchestration; the original Task identity alone cannot express every
legitimate future recovery action, so the idempotency key includes the recovery action and generation.

Follow-up Question:

Why must reconciliation never scan `browser_tasks` directly, even read-only?
## 11. Relevant Framework Connections

* **FastAPI** — the trusted business and security boundary: authentication/authorization; durable `Task`
  acceptance; the idempotency record; reconciliation/cancellation/compensation APIs; the authoritative
  audit/query layer.
* **n8n** — Webhook and Schedule triggers; the execution record; Edit Fields (mapping), IF, HTTP Request,
  Respond to Webhook nodes; orchestration retry and version rollback — but no direct database/queue/worker
  ownership.
* **PostgreSQL / queue / Playwright** — carried forward from Day66 only as backend-owned durable state, a
  dispatch notification, and permissioned worker execution. Day67 does not add or exercise them.

## 12. AI Backend Connections

A user-facing AI research/report request may use an n8n workflow as orchestration, but it must create a
permissioned Browser Task **through FastAPI**. The LLM/agent or the workflow may propose and coordinate; it
does **not** own authorization, durable acceptance, worker-dispatch truth, recovery, or audit. Scheduled
reconciliation (a Schedule Trigger calling an authenticated FastAPI reconciliation API) protects
long-running AI/browser work from stuck-state recovery errors while keeping the decisions in FastAPI. This
is the same boundary as Day66's "the LLM proposes; FastAPI owns" — n8n is simply another untrusted caller
in front of the same trusted backend.

## 13. English Interview

Key Vocabulary:

orchestration layer · trigger / node / execution · Webhook Trigger vs Schedule Trigger · Test URL vs
Production URL · durable acceptance · idempotency key / request ID · service identity vs business/user
identity · short-lived signed delegation token · transport retry vs business idempotency vs execution
retry · reconciliation · compensation vs cancellation · blast radius · execution history vs authoritative
audit.

Useful Expressions:

- "n8n orchestrates; FastAPI owns the durable truth."
- "Receiving a Webhook is not the same as durably accepting the task."
- "A `202 + task_id` is a promise about committed state, so only FastAPI may make it."
- "A service credential proves the caller, not the tenant or the user."
- "n8n can resend; FastAPI collapses the same intent by its idempotency key."
- "Stop the orchestration first, then compensate durable facts through the backend."

### Beginner

Question: Why should an n8n workflow call FastAPI instead of the database directly?

Student answer (classroom record): *“因为FastAPI是受信任的业务与安全边界”* / *“没有node有权创建”*.

Strong Answer: "FastAPI is the trusted business and security boundary. n8n is an orchestration layer with
no authority to create or change a durable Task. If it wrote the database directly it would bypass
authentication, policy, idempotency, and audit, and it could misread transient lease/state. So the
workflow only asks FastAPI over an authenticated call, and FastAPI's transaction decides what durably
happens."

### Intermediate

Question: An n8n Webhook received the event. Can the workflow return `202 + task_id`? Walk through the
reasoning and the trade-off.

Student answer (classroom record): *“在 FastAPI 耐久接受任务后就返回安全的 202 + task_id”*.

Strong Answer: "Not by itself — receiving a Webhook is not FastAPI durably accepting the task. `202 +
task_id` is honest only after FastAPI commits acceptance; if n8n fails before that commit it returns a
failure such as 502/503 or lets the caller retry, and never invents a `task_id`. The trade-off is that
retries are layered: n8n may re-send an uncertain HTTP call, FastAPI collapses the same intent by its
idempotency key so redelivery returns the existing `task_id`, and the worker owns execution retry
separately. Trying to make n8n 'exactly once' is the wrong lever; the idempotency record is the right one."

### Senior

Question: A bad workflow release is creating problems in production. Walk me through the response and the
main production risk.

Student answer (classroom record): *“第一步应该回滚/停用 n8n 工作流入口”* and *“不接受”* to direct n8n DB
access.

Strong Answer: "Stop the blast radius first: deactivate the bad workflow or publish a prior version so no
new bad orchestration runs. Then scope affected requests from n8n execution history and, authoritatively,
from FastAPI records. Repair through FastAPI only — controlled cancellation, compensation, or
reconciliation — because durable facts and any external side effects live in the backend. The main
production risk is treating a low-code layer as authoritative: deleting Task records or giving n8n direct
DB access destroys audit/recovery evidence, cannot un-run an external effect, and can misread transient
lease/state. Identity is resolved by FastAPI via `request_id` or a short-lived signed delegation token,
never a forwarded long-lived user token, and idempotency is enforced atomically so a re-sent request
returns the existing `task_id`."

### Common Weak Answer

"The Webhook fired and n8n mapped the fields, so I return `202 + task_id`, trust the `tenant_id` in the
body because our shared service key is attached, and if something breaks I delete the task rows to roll
back."

Strong Answer (why it fails and what to do): "This treats receipt as acceptance, treats a service
credential as a user/tenant identity, and destroys durable audit/recovery evidence (and still cannot
un-run an external effect). Instead: FastAPI commits acceptance before any `202`, resolves trusted context
server-side, enforces idempotency atomically, and compensates via controlled backend APIs — while n8n only
stops future orchestration and provides execution-history evidence, which is helpful but not the
authoritative business audit."

## 14. Mental Model Summary

```text
trigger -> execution -> nodes -> result     (n8n orchestration only)
n8n asks FastAPI (HTTP) -> FastAPI tx creates Task + contract + outbox -> 202 + task_id (only after commit)
Webhook receipt != durable acceptance   ·   Test URL != Production URL != backend acceptance
service identity != tenant/user identity != action authorization
retry layers: n8n transport re-send | FastAPI business idempotency (collapse same request_id) | worker execution
reconciliation idempotency = task_id + recovery_action + recovery_generation (via authenticated FastAPI API)
rollback: stop orchestration first -> scope from n8n history + FastAPI records -> compensate via FastAPI (never delete Tasks)
Day66 boundaries UNCHANGED: n8n is one more untrusted caller in front of the trusted backend.
```

## 15. Today's Takeaway

n8n makes work easy to trigger and coordinate — which is exactly why the ownership boundaries must not
move. A workflow node is an untrusted caller with the same lack of authority as an LLM proposal: it may ask
FastAPI, but FastAPI still owns authentication, durable acceptance, idempotency, recovery, and audit. A
Webhook firing is not acceptance; a Test URL is not a Production URL; a Production URL is not durable
acceptance; a service credential is not a user. And configuration is not behavior — the class only trusted
the 400 path because it was **re-run** and the execution record proved the false branch ran while the HTTP
Request node did not.

## 16. Before Next Lesson Checklist

- [ ] I can state the boundary: n8n → authenticated FastAPI, never DB/queue/worker directly.
- [ ] I can explain why a Webhook receipt is not durable acceptance and when `202 + task_id` is honest.
- [ ] I can distinguish a Test URL's manual-listening lifecycle from a published Production URL, and note
      neither implies durable backend acceptance.
- [ ] I can separate service identity from tenant/user identity and prefer short-lived scoped delegation
      over forwarding a long-lived user token.
- [ ] I can separate n8n transport retry, FastAPI business idempotency, and worker execution retry, and
      pick a reconciliation idempotency basis (`task_id + recovery_action + recovery_generation`).
- [ ] I can roll back a bad workflow by stopping orchestration first, then compensating through FastAPI —
      never by deleting Task records or giving n8n direct DB access.
- [ ] I understand the evidence limits: only the invalid-input **400** ran locally; the FastAPI success
      path, service auth, durable Task, PostgreSQL, queue/Outbox, worker execution, and a Production URL
      are **NOT RUN / NOT CONFIGURED**, and no workflow JSON was exported.

---

Related: [Day67 n8n-workflows project](../../projects/n8n-workflows/README.md)
· [cheat sheet](../../cheat_sheets/fastapi.md) · [interview](../../interview/fastapi.md)
· Previous: [Day66 — Queue-backed Playwright Worker as a Permissioned AI Tool](day66-queue-backed-playwright-worker-as-a-permissioned-ai-tool.md)
· Next: Day68 — Long-running AI Jobs: Polling, Callback, Correlation and Idempotency
