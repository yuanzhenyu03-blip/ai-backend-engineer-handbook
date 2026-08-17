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
of the backend into a place with no transactions, no policy engine, and no real audit trail. Day66 spent
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

When asked whether n8n should reach the durable system directly or go through FastAPI, the student chose
the authenticated-FastAPI boundary and started a local n8n for the artifact work (*“B,现在当前我已经启动了
本地n8n”*). The reason, in the student's words: *“因为FastAPI是受信任的业务与安全边界”*. No n8n node has the
authority to create a durable Browser Task (*“没有node有权创建”*). An HTTP Request node only **asks**
FastAPI; the FastAPI transaction is what creates Task + contract + Outbox as appropriate. Even if n8n
already "checked" something, FastAPI must revalidate — the student affirmed this (*“是，因为FastAPI是受信任
的业务与安全边界”*).

### Concept 2: Acceptance semantics — receipt is not acceptance

A published/active n8n Webhook receiving an event is **not** equivalent to FastAPI accepting a durable
task. Only after FastAPI durably accepts the task is the safe response `202 + task_id` (*“在 FastAPI 耐久
接受任务后就返回安全的 202 + task_id”*). If n8n crashes **before** FastAPI acceptance, it cannot honestly
return `202 + task_id`; it must return a failure such as 502/503 or allow an upstream retry. The student
confirmed a Production Webhook receipt does not let n8n claim durable acceptance before FastAPI
receives/commits (*“不能”*).

### Concept 3: The local draft workflow (configuration record)

Created locally in n8n and kept as a **draft (not published/activated)**: `Day67 - FastAPI Orchestration
Boundary`.

```text
Webhook (test path: day67/research-report)
  -> Edit Fields (map report_scope, request_id)
  -> IF ({{ $json... }} both present?)
       true  -> HTTP Request (POST placeholder) -> Respond to Webhook (202 JSON)
       false -> Respond to Webhook (400 JSON)
```

* Allowed inputs: `report_scope` and `request_id`.
* Invalid response body:
  `{ "error": "invalid_request", "message": "report_scope and request_id are required" }`.
* Intended successful response body: `{ "status": "accepted", "task_id": "..." }` (INTENDED — never
  executed).
* HTTP endpoint (unverified local placeholder): `http://host.docker.internal:8000/api/v1/browser-tasks`.
* HTTP authentication intentionally `None` — no real credential, secret, or production endpoint was
  configured.

This flow is a documented configuration record. **No exported workflow JSON was captured**, so it is not
an importable/runnable repository artifact.

### Concept 4: Trigger semantics — Test URL vs Production URL; Webhook vs Schedule

A Test URL is a temporary manual-listening/debug lifecycle: it exists only while n8n is actively listening
for a test event; it is **not** a continuously registered production entrypoint. A Production URL requires
a published/activated workflow — but production availability still does **not** mean durable backend
acceptance. A Webhook Trigger serves an external request; a Schedule Trigger drives internal periodic work
such as reconciliation. Crucially, a scheduled reconciliation workflow must call an **authenticated
FastAPI reconciliation API**, not scan `browser_tasks` directly.

### Concept 5: Authentication and identity

A shared n8n service credential proves the calling workflow/service — **not** the tenant, the final user,
or the action authorization (*“不能”* to "does a shared service key make body tenant identity
trustworthy"). Do not trust body-provided `tenant_id`/`user_id` merely because n8n sent them. Do not store
or forward a long-lived user login token through n8n execution data (*“不能”*). Safer designs: FastAPI
looks up trusted context by `request_id`, or n8n carries a **short-lived signed delegation token** bound
to tenant, user, allowed action, request ID, and expiry.

### Concept 6: Retry and idempotency (three separate layers)

n8n may decide to retry an uncertain HTTP **transport** call. FastAPI owns **business idempotency** and
must persist/enforce the reused `request_id`/idempotency key so repeated delivery returns the existing
`task_id` rather than duplicating work (*“由 FastAPI 负责”*, *“idempoetency key”*). Worker **execution**
retry is a third, separate layer. The safe model: "n8n can resend; FastAPI collapses the same intent." For
scheduled reconciliation, bind idempotency to `task_id + recovery_action + recovery_generation` — the
original Task identity alone does not express every possible future legitimate recovery action (the
student first bound reconciliation to the original Task identity, *“使用它扫描到的原始 Browser Task 的标识作为
幂等依据”*, then refined it to include the recovery action/generation).

### Concept 7: Production failure and rollback

For a bad workflow release, **first stop the blast radius**: deactivate the bad workflow or publish a
prior version (*“第一步应该回滚/停用 n8n 工作流入口”*). Then identify affected requests from n8n execution
history **and** authoritative FastAPI records. Repair via FastAPI controlled cancellation, compensation,
or reconciliation — **never delete durable Task records as a workflow rollback mechanism** (*“不能”* to
"can deleting the n8n side cancel a durable backend task"). Do not give n8n even read-only direct access
to `browser_tasks` (*“不接受”*): it creates schema coupling, bypasses backend policy/audit, and can
misinterpret transient lease/state conditions.

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

These are the exercises actually performed in class (n8n editor + one local run). There is **no repository
code artifact and no pytest** for Day67.

1. **Design and configure** the local draft workflow `Day67 - FastAPI Orchestration Boundary`
   (`Webhook -> Edit Fields -> IF -> HTTP Request | Respond 400`), with test path `day67/research-report`
   and inputs `report_scope`, `request_id`.
2. **Execute a real local invalid-webhook test** with missing `request_id` / empty `report_scope`.
3. **Observe the first failure:** malformed request misrouted into the HTTP Request branch, returning an
   empty 200; then the placeholder HTTP call failed to connect (the `$json...` expressions did not
   evaluate).
4. **Correct the expression syntax** to explicit `{{ $json... }}` in Edit Fields, IF, and HTTP body.
5. **Re-execute the identical invalid request** → **HTTP 400** with
   `{ "error": "invalid_request", "message": "report_scope and request_id are required" }`. The n8n
   execution showed the **false branch / invalid Respond to Webhook node ran; the HTTP Request node did
   NOT run** — `EXECUTED_LOCAL_RUNTIME`.
6. **Reason through** (conceptually): published-workflow failure before FastAPI acceptance, shared service
   identity, short-lived delegation, transport retry, reconciliation identity, and rollback containment.
7. Complete the Beginner, Intermediate, and Senior English interview exercises.

> The valid/`true` branch (HTTP Request → FastAPI → `202 + task_id`) was **NOT** exercised: the endpoint
> was an unverified placeholder with authentication `None`, so no FastAPI path, durable Task, or
> persistence was created.

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

**Beginner** — *Why should n8n call FastAPI instead of the database directly?*
Because FastAPI is the trusted business and security boundary. n8n is an orchestration layer with no
authority to create or change a durable Task; if it wrote the database directly it would bypass
authentication, policy, idempotency, and audit, and could misread transient lease/state. So the workflow
only *asks* FastAPI, and FastAPI's transaction decides what durably happens.

**Intermediate** — *An n8n Webhook received the event. Can the workflow return `202 + task_id`?*
Not by itself. Receiving a Webhook is not the same as FastAPI durably accepting the task. `202 + task_id`
is only honest **after** FastAPI commits acceptance. If n8n fails before that commit, it must return a
failure such as 502/503 or let the caller retry — never invent a `task_id`. Retries are layered: n8n may
re-send an uncertain HTTP call, FastAPI collapses the same intent by its idempotency key so redelivery
returns the existing `task_id`, and the worker owns execution retry separately.

**Senior** — *A bad workflow release is creating problems in production. Walk me through the response.*
Stop the blast radius first: deactivate the bad workflow or publish a prior version so no new bad
orchestration runs. Then scope the affected requests from n8n execution history **and** authoritative
FastAPI records. Repair through FastAPI only — controlled cancellation, compensation, or reconciliation —
because durable facts and any external side effects live in the backend; I never delete Task records as a
rollback mechanism, and I never give n8n direct database access. If identity mattered, FastAPI resolves
trusted context by `request_id` or a short-lived signed delegation token, never a forwarded long-lived
user login token, and it enforces idempotency atomically so a re-sent request returns the existing
`task_id`.

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
