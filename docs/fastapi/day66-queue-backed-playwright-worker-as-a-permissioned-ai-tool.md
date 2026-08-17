# Day66 — Queue-backed Playwright Worker as a Permissioned AI Tool

## 1. Lesson Metadata

```text
Status:        ✅ Completed — lesson + queue-backed permissioned-worker decision core; EXECUTED_LOCAL_RUNTIME (pure logic)
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 4-5 hours
Prerequisite:  Day65 recovery/security contract; Day63 final fence; Day60 Outbox/Relay/lease; Day50 Job lifecycle
Previous Lesson: Day65 — Browser Failure Recovery and Security Boundaries
Next Lesson:   Day67 — n8n Workflow Model, Triggers, FastAPI Integration and Responsibility Boundaries
Engineering Artifact: projects/fastapi-playwright/ (queue-backed permissioned-worker decision core + tests)
```

Day66 turns the Day62–Day65 browser capability into a DURABLE, QUEUE-BACKED, PERMISSIONED AI TOOL. The
LLM may PROPOSE a tool call, but the backend owns authorization, durable task truth, queue dispatch,
Worker execution authority, recovery, and audit.

> Evidence honesty: the LIVE CLASSROOM produced the architecture, state machine, failure analysis,
> rollback plan, and permissioned Tool Contract only (`CONCEPTUAL_STATIC`). The updating agent then wrote
> a pure decision core and ran it:
>
> ```
> cd projects/fastapi-playwright
> python3 -m pytest -q tests/test_day66_queue_backed_permissioned_worker.py
> ```
>
> Result: **14 passed, `EXECUTED_LOCAL_RUNTIME`** (pure decision-core rules; no Provider/LLM, PostgreSQL,
> Redis/Celery, Outbox Relay, Playwright, or Object Storage involved). **NOT RUN:** a real Provider/LLM
> tool loop; real guarded PostgreSQL concurrent claims; a real Outbox Relay/Broker; real Celery
> ACK/redelivery; real lease expiry/recovery; real Playwright BrowserContext execution; real Session
> revocation/cancellation; real Object Storage publication; integration; and production. **Day65's `20
> passed` and earlier Day59–Day61 evidence are NOT reused as Day66 validation.**

## 2. Learning Objectives

By the end of Day66 you can:

* Explain why an LLM tool-call proposal is untrusted request input, and why `idempotency_key` identifies
  one intent only when bound to a request fingerprint (tenant + operation + exact Origin + report scope).
* Separate the four responsibilities: Provider/LLM inference, AI Backend control, Queue notification, and
  Worker execution.
* Commit a Browser Task + Permissioned Tool Contract + Outbox dispatch intent in ONE transaction and
  return `202 Accepted + task_id`, dispatching via an independent Outbox Relay after commit.
* Decide execution ownership with a guarded PostgreSQL claim + lease, and reject a stale Worker's terminal
  write with the Day63 final fence.
* Design a minimal versioned Queue Envelope that carries identity only — never credentials — and
  dead-letter an unsupported version without loading a Job.
* Handle commit-before-ACK redelivery, Day65 UNKNOWN_OUTCOME reconciliation, durable cancellation, a safe
  retry gate, and a safe Tool Result boundary back to the model.

## 3. Why This Matters

An AI backend that lets a model "use a browser" is only safe if the model never actually holds power. The
model proposes; the backend authorizes, persists, dispatches, executes, recovers, and audits. Everything
that made Day62–Day65 correct — isolation, the final fence, strict action identity, UNKNOWN_OUTCOME
reconciliation, security stops — must now survive process crashes, duplicate queue deliveries, lease
takeovers, cancellations, and a bad Worker release. The failure that motivates the whole lesson is a
`browser-worker.v2` that drops the `lease_token` predicate from the final `succeeded` write: suddenly a
stale Worker can publish over a fresh one, and a poisoned Artifact can reach the model. Durable task truth
plus a lease and a final fence are what stop that.

## 4. Roadmap Position

```text
Day64 trusted Artifact
  -> Day65 recovery/security policy (UNKNOWN_OUTCOME, diagnostics, SSRF, credentials, security stop)
  -> Day66 durable queue-backed permissioned Playwright Worker   <- YOU ARE HERE
  -> Day67 n8n orchestration over constrained backends
```

Day66 sits on the Day50/Day60 Job lifecycle (Outbox atomic acceptance, Relay delivery, guarded Worker
claim, late ACK, lease triple, redelivery, recovery) and reuses the Day63 final fence and the Day65
recovery core. Day67 must call this constrained backend API rather than drive a browser, credentials, or
navigation directly; Day68 reuses Day66 task IDs, state semantics, correlation IDs, durable acceptance,
and idempotency for polling/callbacks. Day71+ builds the LLM runtime; Day79+ builds the Agent tool
registry — Day66 does NOT claim a completed Agent Runtime or real LLM tool-use integration.

## 5. Lesson Map

```text
1. Tool-call proposal is untrusted; idempotency binds to a request fingerprint
2. Provider vs AI Backend vs Queue vs Worker responsibilities
3. Atomic Task + Contract + Outbox acceptance; Relay after commit -> 202 + task_id
4. Guarded claim + lease decide ownership (not the queue)
5. Minimal versioned Queue Envelope; reload truth from PostgreSQL + protected Session Store
6. Day65 recovery enforced on the durable Worker lifecycle
7. Cancellation/revocation are durable, cooperative, fenced
8. Async 202 + task_id; safe Tool Result boundary
9. task/attempt/event/lease/trace identity
10. Stale-Worker fence-removal rollback exercise
```

## 6. Core Mental Model

```text
LLM / Provider = proposes a tool call; owns neither permission nor execution.
AI Backend     = validates user/tenant/policy, persists the durable contract, dispatches, recovers, audits.
PostgreSQL     = durable business truth: Task state, contract, idempotency identity, Attempt history, Lease, result.
Queue          = at-least-once notification, never authority or Secret storage.
Worker         = temporary executor only after a guarded claim; must pass the final fence before sensitive
                 actions and publication.

accepted != running != succeeded != published Artifact
task_id is stable; attempt_id changes; lease_token fences one authority grant.
Lease + final fence prevent stale or revoked execution from becoming business truth.
On crash/cancellation/possible external side effect: load current durable state and reconcile original
identity; do not blindly replay. Only a proven non-start may enter bounded retry.
```

## 7. Main Concepts

### Concept 1: A tool call is a proposal, not authorization or durable acceptance

The Provider may return a `browser.export_report` tool-call proposal, but it owns no authorization,
durable state, credentials, lease, or publication authority. The student's opening answer was right in
spirit: *“必须持久化intent以及idempotency key。防止被重放以及任务成为无人认领状态。浏览器权限应该有用户批准”*.
The sharpening: an `idempotency_key` identifies one business intent **only** when bound to a request
fingerprint — tenant, operation, exact Origin, and report/data scope. The authorization facts come from a
**server-authorized contract** (`ServerAuthorizedContract`: the authenticated tenant, the allowed
operation, the exact approved Origin, the allowed report/data scope, and a valid Session binding), never
from the proposal itself. The proposal's `tenant_id`, `target_origin`, and `report_scope` are untrusted
and must match the contract EXACTLY — they can never widen it — so a malicious Origin (e.g. cloud
metadata), a foreign tenant, or an out-of-scope report is rejected. Approval is a **server-side fact**
recorded in the contract (`approval_granted` / `approval_id`) — the proposal can never self-assert it — and
is necessary but **not** sufficient. Same key + different fingerprint is rejected; same key + same authorized fingerprint is an
idempotent replay of the existing task.

`validate_tool_proposal(proposal, contract, existing)` (the proposal has no `user_approved` field;
approval comes only from `contract.approval_granted`) →
`ACCEPT_NEW / REPLAY_EXISTING / REJECT_NOT_A_TOOL_CALL / REJECT_MISSING_IDEMPOTENCY / REJECT_UNAPPROVED /
REJECT_POLICY_BLOCKED / REJECT_TENANT_MISMATCH / REJECT_ORIGIN_NOT_APPROVED / REJECT_SCOPE_NOT_ALLOWED /
REJECT_SESSION_UNAUTHORIZED / REJECT_FINGERPRINT_MISMATCH`.

### Concept 2: Four separate responsibilities

The classroom explicitly resolved the student's question: *“我没有模型不是要去调用第三方的provider吗。我的后端在这里面又是什么角色。”*
The third-party Provider/LLM performs inference and returns text or a structured tool-call proposal — it
does not operate the browser or own tenant credentials. The AI Backend authenticates the user/tenant,
calls the Provider, exposes the tool schema, validates proposed calls, persists durable task truth,
dispatches through Outbox/queue, and manages policy, cancellation, recovery, and audit. The Queue is
at-least-once delivery notification — not business truth or execution authority. The Playwright Worker
executes only after a guarded DB claim, current policy/fence checks, and protected session loading.

### Concept 3: Atomic acceptance and Outbox dispatch

A tool call remains untrusted until backend validation completes and ONE transaction commits Browser
Task/Job + Permissioned Tool Contract + Outbox dispatch intent. Only then may the API return
`202 Accepted + task_id`. The student answered correctly that a Job cannot return `202` if the Job insert
committed but the Outbox insert did not — both roll back together (*“不能，因为是原子事务要一起回滚。”*).
Dispatch is then emitted by an **independent Outbox Relay after commit** (*“由独立的 Outbox Relay 在事务提交后投递。”*),
not a direct in-request Celery publish: a direct publish can be lost after DB commit but before the broker
send, while a committed Outbox record lets the Relay recover delivery after an API failure.

The student's *“第三步”* answer to "when does a model suggestion become an executable durable Task" was
corrected: the Provider response is step 3 (a proposal); validation is next; **durable acceptance occurs
at the committed transaction**. `becomes_durable_task_at(DURABLY_ACCEPTED)` is the only `True`.

### Concept 4: Guarded claim, lease, fence, and duplicate delivery

Execution ownership is decided by a PostgreSQL guarded claim plus a lease — **not** exactly-once queue
delivery (*“依靠 PostgreSQL 的 guarded claim 与 lease 决定谁拥有执行权”*). A queue message is a
notification; the guarded `UPDATE ... RETURNING` (with `lease_owner`, `lease_token`, `lease_expires_at`)
grants temporary execution authority to exactly one concurrent Worker — a claim takes ONLY a task with no
lease or an EXPIRED lease, so ANY still-valid lease is rejected, **including the same `attempt_id`'s** (a
duplicate/concurrent path must never re-claim and overwrite a live lease); an Attempt extends its OWN live
lease through a separate `renew_lease()` (same owner + token, an expiry pushed STRICTLY into the future —
`new_expires_at` must be `> now` AND `> the current lease_expires_at`, so a renewal can never shorten the
lease or write a past/equal time; a non-extending value is rejected and the current expiry is left
untouched — no token rotation, and never a re-execution of Playwright). A terminal write must require the current task state, matching
owner/token, and an unexpired lease. A stale Worker cannot publish merely
because it holds valid bytes: the student correctly answered that Worker A cannot publish after its token
expires and Worker B takes a new token, and that A's candidate data is not automatically a trusted
Artifact (*“不能”*). `guarded_claim(...)` and `terminal_publish_allowed(fence)` (reusing
`day63_session_gate.final_fence`) encode this, and `renew_lease(...)` / `renewed_expiry(...)` extend a live
lease without re-claiming.

Commit the durable task result **before** ACK. If a Worker crashes after commit but before ACK, the
redelivered Worker reads `succeeded`, does not run Playwright again, ACKs the duplicate, and lets the
caller read durable state (*“读取 PostgreSQL 中已提交的终态并安全结束”*). The intermediate English answer
— *“Early ACK; if the worker crashes, the task will be lost. An ACK should be sent, and the previous
successful result returned.”* — was corrected: ACK is sent only after durable commit, and a redelivered
Worker does not return a result to the Broker; it reads terminal DB state, avoids execution, and ACKs the
duplicate message.

### Concept 5: Minimal versioned Queue Envelope and protected state reload

The queue carries a minimal task identity; the Worker reloads current truth from PostgreSQL and
credentials from a protected Session Store (*“只携带最小任务身份，让 Worker 从 PostgreSQL 和受保护的 Session
Store 重新加载”*). Example envelope fields: `envelope_version`, `event_id`, `task_id`, `trace_id`,
`event_type`. **Never** carry Cookies, storage state, Authorization headers, Provider keys, raw
diagnostics, raw page data, or complete executable browser capabilities in Broker messages. Queue payload
fields are never authorization — fresh DB/policy/session checks are needed because a queued message may
outlive revocation, cancellation, a policy change, or a lease change. The envelope is validated by a
**strict allowlist** — it may carry ONLY `envelope_version`, `event_id`, `task_id`, `trace_id`, and
`event_type`; ANY extra field (a `session_token`, any credential, or an unknown/future field) is rejected
without relying on a denylist, and the `event_type` must be an approved browser-task dispatch. An
unsupported envelope version is classified, durably dead-lettered, and ACKed without loading a Job,
Session, or Playwright. `validate_envelope(env)` → `ACCEPT / DEAD_LETTER_UNSUPPORTED_VERSION /
REJECT_UNKNOWN_FIELD / REJECT_MISSING_IDENTITY / REJECT_EVENT_TYPE`.

### Concept 6: Day65 recovery enforced on the durable Worker lifecycle

When Worker A clicked Export, crashed, its lease expired, and Worker B received redelivery, the student
correctly chose UNKNOWN_OUTCOME reconciliation (*“必须先走 Day65 的 UNKNOWN_OUTCOME reconciliation”*). Lease
expiry means loss of authority, not proof the external action did not happen. Recovery uses the original
strict identity and authoritative server evidence:

```text
CONFIRMED_COMPLETED           -> validate/publish only under the current fence
ACCEPTED_OR_IN_FLIGHT         -> continue reconciling the same action; no replay
CONFIRMED_NOT_STARTED         -> may enter the bounded-retry gate
STILL_UNKNOWN                 -> retain/investigate; never click again
```

A BrowserContext creation failure **before** navigation or Export is `SAFE_TO_RETRY`; the complete gate
also requires an explicit retryable class, proven non-start, no security stop, a max-attempt limit, one
owner, current authorization/session/contract, the final fence, deadline/cancellation/budget, and
backoff/jitter (*“SAFE_TO_RETRY，满足final fence，deadline，cancellation，budget”*). New retries are new
auditable Attempts with a new `attempt_id` and lease token — never an in-process infinite loop or reuse of
the old lease. `worker_retry_decision(policy, ctx, fence)` delegates to the Day65 enforced
`authorize_retry`.

### Concept 7: Cancellation and revocation are durable, cooperative, and fenced

Both checks are required: check the latest durable truth **before** the claim, then revalidate the final
fence before credential load, before each critical browser action, and before final publication
(*“在 claim 前或关键动作前停止”*). When an external action may already have begun, record a durable
`cancellation_requested` rather than an immediate `cancelled` (*“先耐久地记录 cancellation_requested，由持有
当前 Lease 的 Worker 协作停止并在必要时 reconciliation”*); the current lease holder cooperatively stops, and if
an external effect may have happened it reconciles rather than falsely declaring cancellation. The
cancellation request and the external outcome are separate, auditable facts.

### Concept 8: Async response and the safe Tool Result boundary

A long-running browser Tool invocation returns `202 Accepted + task_id`, not an immediate complete report
(*“回 202 Accepted + task_id”*). The exact distinction: `accepted != running != succeeded != published
Artifact`. A task/status API is tenant-authorized and returns only safe state; a result reference appears
only after a guarded successful terminal write. The Tool Result for the Provider/LLM is validated by a
**strict allowlist** — it may carry ONLY `task_id`, `status`, `safe_summary` and `artifact_ref`
(*“只包含经过授权与验证的安全摘要和 Artifact 引用”*); ANY other field (a `session_token`, `authorization`,
`raw_prompt`, `cookies`, `trace`, `raw_csv`, or any unknown/future field) is rejected without a denylist.
The Artifact reference is a protected, access-controlled REFERENCE only — it never grants the model
object-read access.

### Concept 9: Correlation and audit identity

`task_id` identifies the durable business task and must not change across repeated execution;
`attempt_id` must change per attempt (*“不应改变。attempt应该改变”*). `lease_token` fences one authority
grant; `outbox_event_id` identifies dispatch intent; `trace_id` provides observability linkage. Safe audit
events are validated by a **strict allowlist**: task/attempt/outbox/trace identity, the state transition,
policy/contract version, a safe classification, and a timestamp — plus, for the lease, only a
non-reversible `lease_token_fingerprint`. The **raw `lease_token` is a fencing capability and is never
audit-safe**, and any unknown/future or credential field (e.g. `session_token`) is rejected.

## 8. Common Misconceptions

* **`idempotency_key` alone prevents replay** — incomplete. It must bind to a request fingerprint; same
  key with a different intent is rejected.
* **User approval alone authorizes browser execution** — incomplete, and the proposal cannot self-assert
  it. Approval is a durable server-side fact in the contract; backend policy is the enforceable authority
  and remains able to deny unsafe actions.
* **A Provider tool-call response (step 3) creates an executable Task** — wrong lifecycle boundary. A tool
  call is a proposal; a committed authorized Task/Contract/Outbox is durable acceptance.
* **Queue delivery gives the Worker execution authority** — corrected to a guarded PostgreSQL claim plus
  lease/fence.
* **Lease expiry proves no external effect** — corrected to UNKNOWN_OUTCOME and reconciliation.
* **A cancellation request can become an immediate final `cancelled`** — corrected to a durable
  cancellation intent plus cooperative, guarded handling and reconciliation where needed.
* **Early ACK / returning a prior result to the Broker** — corrected to durable commit first; the
  redelivered Worker reads terminal state, does not execute, then ACKs.
* **"Rollback configuration" fixes a Worker-code fence regression** — corrected to rolling back the faulty
  Worker release and pausing risky claims/Attempts.

## 9. Engineering Trade-offs

* **Outbox Relay vs direct in-request publish**: the Relay adds a table and a delivery hop but survives an
  API crash between DB commit and broker send; a direct publish is simpler but can silently drop a
  committed task. Day66 chooses the Relay.
* **Exactly-once queue delivery vs guarded claim + lease**: chasing exactly-once at the broker is fragile
  and expensive; at-least-once delivery made harmless by a durable guarded claim + lease + idempotent
  terminal state is robust and cheap. Day66 chooses the latter.
* **Immediate `cancelled` vs durable `cancellation_requested`**: an immediate cancel is simpler UX but can
  lie about an external effect already in flight; a durable request + cooperative fenced stop keeps the
  request and the outcome as separate, auditable truths.
* **Rich Tool Result vs safe summary**: returning raw CSV/DOM/trace to the model is convenient but leaks
  sensitive data into model context; a verified safe summary + a protected Artifact reference is the safe
  default.

## 10. Hands-on Exercises

The exercises are realized as the pure decision core `src/day66_queue_backed_permissioned_worker.py` and
its tests. Run:

```bash
cd projects/fastapi-playwright
python3 -m pytest -q tests/test_day66_queue_backed_permissioned_worker.py
```

1. **Proposal validation** — `validate_tool_proposal`: reject a non-tool-call, a missing idempotency key,
   an unapproved call, a policy-blocked operation, and a same-key/different-fingerprint replay; accept a
   new valid call and replay a same-key/same-fingerprint one.
2. **Lifecycle boundary** — `becomes_durable_task_at`: only `DURABLY_ACCEPTED` is a durable task.
3. **Atomic acceptance** — `atomic_acceptance`: any partial write rolls back; only all-three is a `202`;
   `dispatch_via_relay_after_commit` / `direct_in_request_publish_is_safe`.
4. **Envelope** — `validate_envelope`: accept a minimal identity envelope; dead-letter an unsupported
   version; reject Cookies/storage-state/provider-key fields and missing identity.
5. **Guarded claim** — `guarded_claim`: one winner; re-claim only on a no/expired lease; deny ANY live
   lease (even the SAME Attempt), terminal state, and non-claimable state; `renew_lease` extends an
   Attempt's own live lease ONLY strictly into the future (rejects `new_expires_at <= now` or `<= current
   expiry`), matching owner + token, no token rotation, no re-execution.
6. **Stale-write rejection** — `terminal_publish_allowed`: block a superseded token, a taken-over owner,
   an expired lease, and a bumped version.
7. **Commit-before-ACK** — `on_delivery`: terminal → ACK duplicate; running + live lease → ACK duplicate
   (`SKIP_ACTIVE_LEASE_ACK`, another Attempt owns it, no re-run); running + expired lease → reconcile;
   cancellation → stop; fresh → execute.
8. **Recovery hand-off** — `recovery_next_step`/`recovery_permits_publication`/`recovery_permits_replay`.
9. **Safe retry** — `worker_retry_decision`: proven non-start + valid fence → RETRY; revoked fence →
   UNAUTHORIZED; UNKNOWN → block; `retry_is_new_attempt_identity`.
10. **Cancellation** — `classify_cancellation` + `cancellation_checkpoints`.
11. **Safe Tool Result** — `shape_tool_result`: strict allowlist (`task_id`/`status`/`safe_summary`/
    `artifact_ref`); deny unauthorized, non-terminal, any non-allowlisted field, unverified; return a safe
    summary otherwise.
12. **Audit identity** — `audit_event_is_safe` + `task_id`/`attempt_id` semantics.
13. **Incident rollback** — `classify_worker_incident` + `incident_phases` +
    `stale_published_artifact_is_trusted` + `rollback_target_is_worker_release`.

## 11. Relevant Framework Connections

* **PostgreSQL** transactionally owns Task/Contract/Outbox truth, guarded claims, lease fencing, durable
  terminal state, cancellation intent, and audit.
* **Redis/Celery** delivers at least once; duplicate messages are expected and made harmless by durable
  state handling — it is not an authorization or Secret store.
* **Playwright** executes only inside an isolated, server-authorized BrowserContext after current
  Session/policy/fence checks; browser success signals are not automatically business success.
* **Day50/Day60** reuse: Job + Outbox atomic acceptance, Relay delivery, guarded Worker claim, late ACK,
  the lease triple, redelivery, repair, and recovery semantics.
* **Day63/Day64/Day65** reuse: the Session/final fence, strict action identity/Artifact evidence, and the
  UNKNOWN_OUTCOME/security/cancellation policy.

## 12. AI Backend Connections

An LLM function/tool-call output is untrusted request input. The browser tool is a constrained capability,
not a free-form Agent: the backend authorizes, persists, dispatches, recovers, and audits, and returns
only safe verified summaries — no credentials or diagnostics enter model context. Day66 is useful with a
deterministic/fake caller as well; it does **not** claim a completed Agent Runtime or real LLM tool-use
integration. Future: Day67 n8n orchestrates the backend; Day68 formalizes polling/callback/correlation/
idempotency; Day71+ builds the LLM runtime; Day79+ builds the Agent tool registry and control flow.

## 13. English Interview

**Beginner** — *Who decides whether a browser Worker may execute?*
Student answer (preserved): "Execution permissions should be determined by the database and actual
policies, rather than by the worker itself."
Refinement: a queue delivery is only a notification; execution authority comes from a guarded PostgreSQL
claim + lease, and every sensitive action and publication is gated again by the final fence.

**Intermediate** — *When should a Worker ACK a queue message, and what does a redelivered Worker do?*
Student answer (preserved): "Early ACK; if the worker crashes, the task will be lost. An ACK should be
sent, and the previous successful result returned."
Correction: ACK only **after** the durable result commit. A redelivered Worker does not return a result to
the Broker; it reads the terminal DB state, does not re-run Playwright, and ACKs the duplicate. Commit
before ACK is what makes at-least-once delivery safe.

**Senior** — *A Worker release removed the `lease_token` predicate from the final `succeeded` write, so a
stale Worker can publish after a new one takes over. Walk through your response.*
Student answer (preserved): a containment, scope, classification, remediation, and controlled-rollout plan
with release/time-window/task/attempt/lease/Artifact evidence. Refinement: `contain -> scope -> classify
-> repair -> controlled rollout`. Roll back the faulty Worker release (not merely configuration), pause
affected Browser Task claims/new Attempts so bad terminal writes stop, and preserve evidence; new API
acceptance may remain safely queued. Scope by release version/window, task ID, attempt ID, lease token,
Outbox/Worker records, and Artifact reference. Classify blocked stale writes, potentially published stale
Artifacts, conflicting attempts, and unknown cases. Quarantine suspect Artifacts from models/users;
reconcile against authority and external evidence; only retry when non-start is proven and the retry gate
passes; restore the fencing predicate; add concurrent A/B Worker regression tests; roll out in a limited
way while monitoring audit/metrics.

## 14. Mental Model Summary

```text
proposal (untrusted)   -> validate vs server contract: tool-call + idempotency/fingerprint + server-side
                          approval fact + exact tenant/operation/Origin/scope + Session (proposal never widens it)
durable acceptance     -> ONE tx: Task + Permissioned Contract + Outbox intent -> 202 + task_id
dispatch               -> independent Outbox Relay AFTER commit (never a direct in-request publish)
envelope               -> minimal identity only (version/event_id/task_id/trace_id/event_type); no secrets
authority              -> queue = notification; guarded PostgreSQL claim + lease = execution authority
publish                -> only under the current final fence (owner+token+lease+version); stale bytes != Artifact
duplicate delivery     -> commit before ACK; terminal -> ACK duplicate, no re-run
recovery               -> lease expiry != no external effect -> UNKNOWN_OUTCOME reconciliation (Day65)
retry                  -> proven non-start + gate -> a NEW Attempt (new attempt_id + lease token)
cancellation           -> durable cancellation_requested + cooperative, fenced stop + reconcile
tool result            -> safe verified summary + protected Artifact reference only
identity               -> task_id stable; attempt_id per attempt; lease_token fences one grant; trace_id links
incident               -> contain -> scope -> classify -> repair -> controlled rollout; quarantine stale Artifact
```

## 15. Today's Takeaway

The model proposes; the backend owns everything that matters. Durable task truth in PostgreSQL, a guarded
claim + lease for execution authority, and the final fence at every sensitive action and publication are
what keep a stale, revoked, or crashed Worker from turning valid bytes into business truth. At-least-once
queue delivery is made safe by durable state, commit-before-ACK, and idempotent terminal handling — not by
chasing exactly-once at the broker. On any crash, cancellation, or possible external side effect, reload
durable state and reconcile the original identity; only a proven non-start earns a new, bounded, audited
Attempt.

## 16. Before Next Lesson Checklist

- [ ] I can explain why a tool-call proposal is untrusted and how idempotency binds to a request
      fingerprint.
- [ ] I can separate Provider, AI Backend, Queue, and Worker responsibilities.
- [ ] I can commit Task + Contract + Outbox atomically and dispatch via a Relay after commit.
- [ ] I can decide ownership with a guarded claim + lease and reject a stale terminal write with the final
      fence.
- [ ] I can design a minimal versioned envelope that carries no credentials and dead-letter an unsupported
      version.
- [ ] I can handle commit-before-ACK redelivery, Day65 reconciliation, durable cancellation, a fenced
      retry gate, and a safe Tool Result.
- [ ] I can run the artifact: `python3 -m pytest -q tests/test_day66_queue_backed_permissioned_worker.py`
      (= 14 passed).
- [ ] I can distinguish `EXECUTED_LOCAL_RUNTIME` (pure decision core) from real
      PostgreSQL / Redis-Celery / Playwright / Object Storage / Provider (`NOT RUN`).

---

Related: [Day66 design/runbook](../../projects/fastapi-playwright/docs/day66-queue-backed-playwright-worker-as-a-permissioned-ai-tool-design.md)
· [queue-backed permissioned worker](../../projects/fastapi-playwright/src/day66_queue_backed_permissioned_worker.py)
· [tests](../../projects/fastapi-playwright/tests/test_day66_queue_backed_permissioned_worker.py)
· [cheat sheet](../../cheat_sheets/fastapi.md) · [interview](../../interview/fastapi.md)
· Previous: [Day65 — Browser Failure Recovery and Security Boundaries](day65-browser-failure-recovery-and-security-boundaries.md)
· Next: Day67 — n8n Workflow Model, Triggers, FastAPI Integration and Responsibility Boundaries
