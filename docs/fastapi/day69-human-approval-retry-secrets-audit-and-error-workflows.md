# Day69 — Human Approval, Retry, Secrets, Audit and Error Workflows

## 1. Lesson Metadata

```text
Status:        ✅ Completed (classroom scope) — lesson + n8n Risk-based Approval Gate contract; CONCEPTUAL_STATIC only (no runtime)
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 4-5 hours
Prerequisite:  Day68 long-running observation/delivery contract; Day66/Day67 permissioned boundary; Day59-Day61 real backend + Job/Outbox lifecycle
Previous Lesson: Day68 — Long-running AI Jobs: Polling, Callback, Correlation and Idempotency
Next Lesson:   Day70 — n8n + FastAPI + AI Tool Integration Capstone and Interview
Engineering Artifact: projects/n8n-workflows/ (Day69 Risk-based Approval Gate contract; NO exported JSON captured)
```

Day69 hardens the Day68 long-running orchestration contract with **risk-based human approval**, classified
retry/error recovery, safe credential handling, authoritative business audit, and evidence-driven incident
rollback/reconciliation/compensation — **without moving durable truth or authorization into n8n**.

> Evidence honesty. Day69 is `CONCEPTUAL_STATIC`: an interactive scenario-driven design review over the
> same multi-tenant To B AI Research and Automation Platform. **NOT RUN:** the Day69 n8n workflow runtime;
> a valid authenticated FastAPI acceptance/approval/publication integration; a real Approval UI/Form/Slack/
> email callback; real approver authentication/authorization/tenant checks; a real PostgreSQL Approval
> schema/migration/constraints/transactions/audit-events/Outbox; real retry/backoff/error workflow; real
> callback duplicate/ACK-loss/fingerprint-conflict behaviour; real credential-store integration/revoke/
> rotate/log-redaction/access-review; real publication/notification target or external reconciliation; real
> Worker/Provider/Browser-Tool execution; real rollback/kill-switch/canary rollout; production. **No
> importable/exported Day69 n8n workflow JSON was created or captured.** No commands, tests, n8n executions,
> FastAPI processes, DB queries, or Provider calls were run. Day67's local invalid-input `400`, Day68's
> conceptual contract, and earlier Phase 4/5 evidence are **not** reused as Day69 runtime validation.
> Delivery is **at-least-once** (never exactly-once); `correlation_id` is an association key, never
> authentication; append-only audit is **not** automatically tamper-proof; approval is **risk/policy based**,
> not required for every AI output.

## 2. Learning Objectives

By the end of Day69 you can:

* Decide when human approval is required (risk/irreversibility/impact/tenant policy), and identify the real
  approver in a To B platform (an authorized role in the **customer's** organization, not platform staff).
* Distinguish validation (evidence) from authorization (who may decide) from approval (whether to act) from
  audit (who decided what, when, under which policy, for which exact object/version).
* Design a durable Approval Gate that binds `tenant + actor + action + artifact/version + policy + expiry`,
  where a v7 approval can never authorize v8.
* Keep the Approval lifecycle independent of the n8n execution lifecycle (an n8n timeout changes no business
  state; `PENDING` holds until a backend-owned `expires_at`).
* Recover a lost-response publish by classified recovery (same `operation_id` + idempotency key, query an
  authenticated FastAPI status/reconciliation API) and classify errors (429/503 vs 400/422 vs 401 vs 403 vs
  409 vs business-terminal vs unknown → `PENDING_RECONCILIATION`).
* Keep Secrets in a Credential Store (workflow holds only a reference), redact evidence, and recover a 401
  by rotation rather than blind retry.
* Model current-state + append-only Business Audit, treat duplicate deliveries as one business decision, and
  classify a reused `event_id` with a different fingerprint as a conflict.
* Resume an Error Workflow at the smallest safe operation boundary, and run the incident flow
  contain → revoke/rotate → preserve → scope → classify → cancel/reconcile/compensate → verify → regression
  → controlled rollout.

## 3. Why This Matters

The moment an AI platform can publish to a customer's clients, charge a paid Provider, or mutate production,
"the model produced a file" stops being the interesting event — "an authorized human accepted the business,
legal, and reputational consequence of *this exact* action on *this exact* artifact version" becomes the
interesting event. Day68 made observation safe; Day69 makes the **high-risk action** safe. The concrete
platform failure that motivates the lesson is exact: a release bypassed the approval condition for some
artifacts, restarted whole workflows on error, and leaked an `Authorization` header into execution logs —
so some reports published without approval, some outcomes were unknown, and a credential was exposed. None
of that is fixable by "rolling back the workflow": rollback stops future harm, but committed tasks, Provider
charges, and external publications need cancellation, reconciliation, or compensation — and the exposed
credential is compromised until it is revoked.

## 4. Roadmap Position

```text
Day66 permissioned browser tool
  -> Day67 n8n/FastAPI responsibility boundary
  -> Day68 safe long-running Task observation and delivery
  -> Day69 risk-based human authorization and workflow hardening   <- YOU ARE HERE
  -> Day70 Phase 6 integration capstone (DIRECT consumer of Day69)
```

Day70 directly consumes the Day69 hardened contract (approval, retry/error classification, Secrets, audit)
and should attempt real cumulative integration evidence. Day71 begins **Phase 7A** as a **phase
transition**, not an n8n dependency: its technical foundations are the Day53–Day61 Provider boundary,
resilience, testing, observability, and runtime-integration lessons. n8n may *later* be an external
consumer/orchestrator of an LLM Application Runtime, but it is not Day71's technical prerequisite —
chronological adjacency is not technical dependency.

## 5. Lesson Map

```text
1. Product & responsibility boundary: To B; the approver is a customer-org role; approval is risk-based
2. Validation vs Authorization vs Approval vs Audit
3. Durable Approval Gate & exact binding (v7 approval cannot authorize v8)
4. Approval lifecycle is independent of the n8n execution lifecycle
5. Retry is classified recovery, not replay (+ the retry/error matrix)
6. Secrets & credential recovery (401 -> stop + classify; rotate only when established, else fix config)
7. Current-state + append-only Business Audit; delivery attempts != business decisions; event-identity conflict
8. Error Workflow resumes at the smallest safe boundary
9. Production incident: contain -> revoke/rotate -> preserve -> scope -> classify -> cancel/reconcile/compensate -> verify -> rollout
```

## 6. Core Mental Model

```text
Human decides risk acceptance.  Backend verifies authority and persists truth.  n8n orchestrates but never
owns approval or recovery truth.

Approval  = exact tenant + actor + action + artifact/version + policy + lifetime.
Validation evidence != permission to publish.
Retry     = classify + preserve identity + query/reconcile.   Timeout != failure.
Workflow  = credential reference.   Secret Manager = real credential.   Logs/Audit/Export = no Secret.
Current state = what is true now.   Append-only audit = how it became true.   Delivery attempt != decision.
Error Workflow = resume the smallest safe operation boundary.
Rollback stops future harm · Cancellation stops safe/proven work · Reconciliation resolves unknown outcomes
· Compensation addresses completed external effects · Audit preserves the truth of what happened.
```

### Mental Model Evolution (Day68 → Day69)

```text
Day68: after 202 + task_id, observation is not truth; observe the same durable Task, dedupe/order deliveries,
       classify before cancel/reconcile/compensate. (Boundary: n8n orchestrates; FastAPI/PostgreSQL owns truth.)
Day69: the SAME boundary now governs the high-risk ACTION. A durable Approval lifecycle, classified retry,
       Secret boundaries, and authoritative append-only audit are added on top of Day68's stable
       task/request/correlation/event identities — n8n still gains NO new authority: it requests approval,
       waits, and calls authenticated APIs, but FastAPI/PostgreSQL owns the approval fact, the transition,
       idempotency, recovery, and audit.
```

## 7. Main Concepts

### Concept 1: Product & responsibility boundary — who approves, and when

Tech Lead Question:

On this multi-tenant To B platform, can n8n's execution history authorize publishing a report, and who is
the approver — platform staff or someone in the customer's organization?

Student Thinking:

If a workflow "ran and passed," it feels like it approved the action — but a workflow run is not a business
decision, and a platform team reviewing every tenant document seems unscalable.

Student Answer:

*“不能，但是我有一个问题这里的意思是需要人工审批？是谁来审批？”* and *“…这个审批的人是客户自己吗？还是说有个专门的人类团队进行
审批，那这样不是太麻烦了吗？…难道市面上的产品也是需要人工审批？”*

Tech Lead Review:

Correct to reject n8n history as authority, and the student's question produced the key model. The approver
is normally an authorized person in the **customer's** organization (Report Owner, Manager, Tenant Admin, or
Compliance role) per risk policy; a dedicated review team fits only specific regulated/managed services.
Approval is **risk-based, not mandatory for every AI output** — low-risk internal drafts may be
auto-authorized (a durable, bounded pre-authorization policy), while high-risk external publication needs an
explicit human decision. (The scenario is intentionally To B; a To C variant may let the individual user be
requester and confirmer while the backend still verifies identity and persists the action.)

Engineering Thinking:

Put the decision where the consequence lands: the tenant owns the business/legal/reputational risk, so an
authorized tenant role decides; the platform enforces identity, policy, and durability.

Production Example:

A low-risk internal draft is saved automatically under a tenant pre-authorization policy; an external client
publication opens a durable Approval Request routed to the tenant's Compliance role.

Framework Connection:

n8n notifies/waits; FastAPI verifies approver identity/role/scope and persists the decision in PostgreSQL.

Exercise:

For a given action, decide auto-authorize vs explicit approval and name the approver role. (Section 10.)

### Concept 2: Validation is evidence; authorization/approval/audit are different questions

Tech Lead Question:

The artifact passed schema, security, artifact, and grounding validation. Does that mean it may be published?

Student Thinking:

"It validated" feels like "it's allowed," but passing checks is about quality/safety, not consequence.

Student Answer / Classroom record:

The class separated the four questions and the student affirmed the distinction (*“不能”* to "internal draft
pre-authorization can authorize external publication").

Tech Lead Review:

```text
Validation  = structure/security/artifact/grounding evidence is satisfied  (quality & safety)
Authorization = the actor is allowed to make the decision                  (who may decide)
Approval     = an authorized actor decides whether THIS exact action occurs (whether to act)
Audit        = records who decided what, when, under which policy, for which exact object/version
```

Validation cannot prove the organization accepts the consequence of external publication. Human approval is
required by the **risk/irreversibility** of the action, not merely because the file was AI-generated.

Engineering Thinking:

Never collapse four distinct questions into one boolean; each has a different owner and a different failure
mode.

Production Example:

A grounded, schema-valid report still cannot be published to a client until an authorized approver accepts
it and the decision is persisted.

Framework Connection:

FastAPI validation endpoints produce evidence; a separate approval endpoint records the authorized decision.

Exercise:

Given a validated artifact, list what still must be true before publication. (Section 10.)

### Concept 3: Durable Approval Gate & exact binding — v7 approval cannot authorize v8

Tech Lead Question:

`approval-301` approved `artifact-v7`. The artifact changes to v8. Can the same approval publish v8?

Student Thinking:

The task and chain are "the same," so maybe the approval carries over — but the *content* changed.

Student Answer:

*“task_id correlation_id tenant_id。继续。approval_id event_id 最终 publication operation_id / idempotency_key
新建”* — stable chain IDs continue; business-intent IDs are new.

Tech Lead Review:

Correct. An Approval binds at least `approval_id, tenant_id, task_id, artifact_id/artifact_version, action,
status, requested_by, required role/policy version, decided_by, decided_at, expires_at`. Approval for
`artifact-v7` cannot authorize `artifact-v8`: a changed artifact needs a **new** approval and **new**
event/publication identities. `task_id`/`correlation_id`/`tenant_id` stay stable as chain association;
`approval_id`, `event_id`, publication `operation_id`, and the publication idempotency key must be new for
the new business intent. n8n may request approval, notify, wait, and call an authenticated API — it may not
use its execution history as the authoritative approval fact; FastAPI verifies tenant/human identity/role/
scope/policy/action/object/version/expiry/revocation/legal-transition, and PostgreSQL persists it.

Engineering Thinking:

Bind authorization to the exact object version and action; identity reuse across changed meaning is a bug or
an attack.

Production Example:

An approver signs off `artifact-v7`; an editor produces v8; publishing v8 requires a fresh Approval Request,
not the v7 record.

Framework Connection:

The Approval row + `approval_events` reference the exact `artifact_version`; the publication idempotency key
is `approval_id:action:artifact_version`.

Exercise:

Classify which identities are stable and which are new for a legitimate v8 approval. (Section 10.)

### Concept 4: Approval lifecycle is independent of the n8n execution lifecycle

Tech Lead Question:

An n8n `Wait` node times out after two hours. Does the Approval move to another state?

Student Thinking:

The waiting execution ended, so maybe the Approval should change too.

Student Answer:

*“进入其他状态”* — then, after correction, *“pending，再次启用一个新的n8n编排任务”*.

Tech Lead Review:

`n8n execution timeout != durable Approval decision or expiry`. If the backend-owned deadline has not
arrived, the Approval remains `PENDING`; a **new** n8n execution observes the **same** `approval_id` (not a
new Task or Approval). Only the authoritative `expires_at` causes `PENDING → EXPIRED`. `REJECTED` is a human
decision; `EXPIRED` is no valid decision before the deadline; a late approve for an expired Approval is
rejected and audited, never a silent revival.

```text
PENDING -> APPROVED    PENDING -> REJECTED    PENDING -> EXPIRED    PENDING -> CANCELLED
```

Engineering Thinking:

Separate the observer's lifecycle from the durable decision's lifecycle; only backend-owned time/decisions
move the decision.

Production Example:

An approver is out for the day; the two-hour workflow times out and re-runs tomorrow, observing the same
still-`PENDING` `approval-301`.

Framework Connection:

FastAPI owns `expires_at`; n8n `Wait`/re-trigger only observes; the transition is a guarded FastAPI update.

Exercise:

Classify the Approval state after an n8n `Wait` timeout vs after the backend deadline. (Section 10.)

### Concept 5: Retry is classified recovery, not replay

Tech Lead Question:

After `approval-301` approved v7, n8n sent the publish and timed out before the response. What now?

Student Thinking:

A timeout feels like a failure to retry — but the publish may already have happened.

Student Answer:

*“应该查询数据库事实”* (refined: query authenticated FastAPI, not the DB directly) and same-key retry
*“approval-301:publish-report:artifact-v7”*.

Tech Lead Review:

`HTTP timeout -> OUTCOME_UNKNOWN`. Preserve stable identity (`operation_id = publish-op-701`,
`idempotency_key = approval-301:publish-report:artifact-v7`) and query an authenticated FastAPI status/
reconciliation API (FastAPI reads PostgreSQL and enforces tenant/authz):

```text
SUCCEEDED              -> do not publish again
PROCESSING             -> observe the same operation_id
FAILED_TERMINAL        -> no blind retry
PENDING_RECONCILIATION -> reconcile the external outcome
NOT_FOUND              -> do NOT immediately reissue (see below)
```

`NOT_FOUND` is ambiguous: it may mean a wrong `task_id`/`correlation_id`/`tenant_id`/`operation_id`, a
query-routing/integration error, a state record past its retention window, an expired idempotency record, a
store-vs-provider-side-effect inconsistency, or simply that whether the original command executed is still
unknown. Treat it as `OUTCOME_UNKNOWN`, not "safe to resend":

```text
NOT_FOUND
-> do not immediately reissue
-> verify task_id / correlation_id / tenant_id / operation_id
-> inspect audit, database, logs and provider evidence
-> verify routing and retention boundaries
-> reissue with the SAME idempotency key ONLY when BOTH hold:
     1. authoritative backend state proves NEVER_ACCEPTED / NOT_STARTED, and
     2. the idempotency retention contract is still valid
-> otherwise enter PENDING_RECONCILIATION or coordinated human handling
```

`same idempotency key != unconditional proof of safety`: if the idempotency record has already expired,
re-sending the same key can still cause a duplicate external publication or extra Provider cost.

Error classification:

```text
429 / transient 503                 -> bounded backoff + jitter + Retry-After
write timeout                       -> unknown outcome; query/reconcile first
400 / 422                           -> contract/input error; fix, do not auto-retry
401                                 -> stop blind retries; CLASSIFY the auth failure (see below)
403                                 -> stop; investigate authorization/policy
409 idempotency meaning conflict    -> stop and investigate
rejected / expired Approval         -> business terminal; do not retry
unknown external outcome            -> PENDING_RECONCILIATION; no blind replay
```

A `401` is not automatically "rotate the credential" — first classify the cause:

```text
401
-> stop blind retries
-> classify the authentication failure
-> refresh or rotate ONLY when expiration, compromise, revocation, or an invalid credential is established
-> fix CONFIGURATION when the cause is audience, issuer, auth scheme, a missing header, the wrong endpoint,
   or clock skew
-> verify the recovery
-> perform a controlled retry
```

If the external target offers neither status lookup nor idempotency, unknown high-risk side effects enter
reconciliation/manual escalation; a low-risk duplicate-tolerant notification may have an explicit policy
allowing a bounded retry.

Engineering Thinking:

A timeout is missing knowledge, not a terminal outcome; recover by identity + authoritative query, classify
by error meaning.

Production Example:

A publish times out; the status API says `SUCCEEDED`, so the workflow continues without republishing.

Framework Connection:

FastAPI status/reconciliation endpoint; the publication idempotency key collapses a re-issued command.

Exercise:

Recover a lost-response publish and classify 401 vs 409 vs 429. (Section 10.)

### Concept 6: Secrets & credential recovery

Tech Lead Question:

A publish returns `401` because the service credential expired. Do you retry, and may you log the
`Authorization` header to debug it?

Student Thinking:

Retrying won't fix an expired credential, and headers carry the secret.

Student Answer:

*“不应该”* (blind retry of 401) and *“不能”* (logging the Authorization header).

Tech Lead Review:

Correct. A 401 is not automatically "rotate": stop blind retries → preserve safe evidence → mark
orchestration blocked by authentication (not business failure) → **classify** the auth failure. Rotate/
refresh the credential ONLY when expiration, compromise, revocation, or an invalid credential is
established; **fix configuration** instead when the cause is audience/issuer/auth-scheme/missing-header/
wrong-endpoint/clock-skew. In this scenario the credential expired, so rotation is the **scenario-specific**
recovery — not the universal response to every 401. After the fix: notify ops/security → revalidate
Approval/action/version → verify the recovery → resume the **same** `operation_id`/idempotency key with a
controlled retry.

```text
Workflow artifact = credential reference
Credential Store / Secret Manager = real Token/Secret
Runtime = controlled injection
Logs / Audit / Export / Evidence Pack = NEVER a raw Secret or Authorization header
```

Safe evidence may record workflow/execution/version, credential reference/version, environment, endpoint
method + redacted path, status/error category, tenant + correlation identities, trace ID, retry count, and
rotation metadata — never Tokens, Authorization headers, API keys, cookies, private keys, raw Provider
payloads, or tenant-sensitive content.

Engineering Thinking:

Treat a secret as a referenced capability with a lifecycle; a credential failure is an ops/security event,
not a business retry.

Production Example:

A rotated key resolves the 401; the same publish operation resumes on its original idempotency key with no
duplicate publication.

Framework Connection:

Credential Store/Secret Manager holds the secret; runtime injects it; the workflow and its export carry only
a reference.

Exercise:

Select safe 401 evidence fields and reject the unsafe ones. (Section 10.)

### Concept 7: Current-state + append-only Business Audit; delivery attempts are not decisions

Tech Lead Question:

Is overwriting `approvals.status` from `PENDING` to `APPROVED` enough audit? And if the same Approve callback
is delivered twice, is that two business approvals?

Student Thinking:

Current status answers "what is true now," but not "how it became true"; and a retried delivery is still one
decision.

Student Answer:

*“不能”* (mutable final state alone is insufficient audit). But first *“写入两条”* (two audit events for two
deliveries) and *“一次新的审批”* (same event_id + different fingerprint = a new approval) — both were corrected.

Tech Lead Review:

Current state ≠ transition history; operational log ≠ business audit; n8n history ≠ authoritative audit.

```text
approvals             = current state / constraints / efficient reads
approval_events       = append-only business transition history
callback receipts     = delivery/security evidence
logs / traces         = operational diagnosis
n8n execution history = orchestration evidence, NOT authoritative business audit
```

The guarded state transition and the `approval.approved` audit event commit **atomically**; corrections/
revocation/compensation **append** new events, never rewrite history. Append-only still needs write
permissions, retention, access monitoring, and backup — it is **not** automatically tamper-proof, and it
records safe identities/reasons, not Secrets. Delivery is at-least-once: **same `event_id` + same fingerprint
= duplicate-safe no-op** (one logical `approval.approved`, two receipts/traces); **same `event_id` +
different fingerprint = integration/security conflict, no action** (a bug, tampering, or replay — produce
safe conflict evidence, query authoritative FastAPI facts, never authorize the changed artifact); **new
content/action = new `approval_id` + new `event_id`**. This misconception recurred for two genuine attempts,
so the Tech Lead taught the full event-identity model directly.

Engineering Thinking:

Separate "what is true" from "how it became true" and "how it was delivered"; bind identity to meaning so a
reused identity with changed meaning fails closed.

Production Example:

A retried Approve callback re-runs the gate as a no-op; a spoofed callback reusing `event_id` for v8 is
routed to conflict evidence, not to publication.

Framework Connection:

PostgreSQL `approvals` + append-only `approval_events` in one transaction; callback receipts recorded
separately as delivery evidence.

Exercise:

Classify duplicate deliveries and a reused-`event_id`/changed-fingerprint callback. (Section 10.)

### Concept 8: Error Workflow resumes at the smallest safe boundary

Tech Lead Question:

Task succeeded → artifact approved → publication succeeded → the final internal notification returned 503 and
the Global Error Workflow fired. Restart the whole workflow?

Student Thinking:

The completed business work must not be redone just because a notification failed.

Student Answer:

*“不安全，应该从第5个开始”* — start from step 5 (notification), not the whole chain.

Tech Lead Review:

Correct, refined: begin the notification **recovery protocol**, not a blind resend. `Workflow retry !=
business operation retry`. The Error Workflow must carry safe context, classify the failure, query
authoritative completed business facts, identify the **smallest** incomplete/unknown operation, and
retry/reconcile/escalate only that operation. If the notification target supports status lookup, query it; if
it supports idempotency, retry with the same notification identity/key; if neither exists and the outcome is
unknown, reconcile or escalate based on duplicate risk.

Engineering Thinking:

Recover at the granularity of the failed operation, not the workflow; completed durable work is a fact, not a
step to redo.

Production Example:

The report is already published; only the "notify owner" step is retried on its own idempotency key.

Framework Connection:

n8n Error Workflow carries correlation context; it calls FastAPI status/idempotent-notify endpoints for the
single failed operation.

Exercise:

Choose the resume boundary for a post-publication notification 503. (Section 10.)

## 8. Common Misconceptions

These are the actual classroom missteps and corrections — the student was not correct from the beginning on
all of them.

1. **An n8n `Wait` timeout should move the Approval state.** Correction: the n8n execution lifecycle and the
   durable Approval lifecycle are independent; the Approval stays `PENDING` until a backend-owned decision/
   expiry/cancellation/legal transition.
2. **n8n should query the database.** Correction: right authority, wrong access — n8n calls an authenticated
   FastAPI API; FastAPI enforces tenant/authz and reads PostgreSQL. No direct n8n DB access.
3. **Each Callback delivery is another business approval event** (*“写入两条”*). Correction: two delivery
   receipts/traces, one logical business event and one legal state transition.
4. **Same `event_id` with a changed fingerprint is a new approval** (*“一次新的审批”*). Correction: same
   `event_id` + changed fingerprint is a conflict/security incident, no action; new content/action needs a
   new `approval_id` + new `event_id`. (This persisted for two genuine attempts, so the full model was
   taught directly, then verified once with a correct v8 classification.)
5. **Final state alone is audit.** The student correctly rejected this: current state ≠ transition history;
   operational log ≠ business audit; n8n history ≠ authoritative audit.
6. **Rollback reverses completed external effects.** Correction: rollback stops future workflow harm;
   cancellation stops proven-unstarted/cooperatively-cancellable work; reconciliation resolves unknown
   outcomes; compensation addresses completed external effects; audit never rewrites what happened.

## 9. Engineering Trade-offs

* **Manual approval for every output vs risk-based policy approval.** Blanket manual approval controls
  high-risk irreversible actions but adds latency, staffing burden, and expiry/retry complexity; use it
  selectively and permit bounded pre-authorization for low-risk reversible actions.
* **n8n history as convenient state vs FastAPI/PostgreSQL authoritative business state.** n8n history helps
  orchestration diagnosis but cannot enforce tenant authorization, atomic business transitions, or durable
  idempotency.
* **Blind automatic retry vs query/reconcile/same-key retry.** Blind retry is simpler but duplicates paid/
  irreversible effects; classified recovery costs engineering effort but preserves correctness.
* **Mutable final status only vs current-state snapshot + append-only audit events.** The hybrid costs
  storage/write complexity but supports efficient reads and reconstructable history.
* **Global workflow restart vs smallest-safe-boundary resume.** Whole-flow restart is simple but redoes
  completed operations; boundary-aware resume needs stable operation identities and recovery APIs but limits
  blast radius.
* **Rollback/delete vs preserve + cancel/reconcile/compensate.** Deletion looks clean but destroys evidence
  and cannot undo external effects; evidence-driven recovery is more demanding but truthful and auditable.

## 10. Hands-on Exercises

Day69 is `CONCEPTUAL_STATIC`: these are **design/decision** exercises with no runtime, no n8n execution, and
no commands — nothing was run. Each tests the mental model against the taught contract.

### Exercise 1 — Approver & approval requirement

Question: For (a) an internal draft save and (b) an external client publication on the To B platform, decide
auto-authorize vs explicit approval and name the approver.

Think First: Where does the business/legal risk land, and is the action reversible?

Starter Artifact: the risk-based Approval Gate (`Validation → policy → low-risk internal save | high-risk
Approval Request → tenant approver`).

Expected Output: (a) auto-authorize under a durable tenant pre-authorization policy; (b) explicit approval by
an authorized tenant role (Report Owner/Manager/Tenant Admin/Compliance), verified and persisted by FastAPI.

Explanation: approval is risk-based; validation is not permission; platform staff are not the default
approvers.

Follow-up Question: When is a dedicated review team appropriate?

### Exercise 2 — Validation vs authorization vs approval vs audit

Question: An artifact passed schema/security/artifact/grounding validation. List what must still be true
before publication.

Think First: Which of the four questions has validation answered?

Starter Artifact: the four-question table (validation/authorization/approval/audit).

Expected Output: an authorized approver must decide (`APPROVED`) for the exact artifact version and action,
FastAPI must verify and persist it, and the decision must be audited — validation alone is insufficient.

Explanation: validation is quality/safety evidence, not business permission.

Follow-up Question: Why can a grounded, schema-valid report still be unpublishable?

### Exercise 3 — Exact binding: can v7 approval publish v8?

Question: `approval-301` approved `artifact-v7`; the artifact is now v8. Which identities stay stable and
which are new?

Think First: What exactly did the approver accept?

Starter Artifact: the Approval binding fields + the identity table.

Expected Output: stable — `task_id`, `correlation_id`, `tenant_id`; new — `approval_id`, `event_id`,
publication `operation_id`, and the publication idempotency key. v7 approval cannot authorize v8.

Explanation: authorization binds to the exact object version and action.

Follow-up Question: What must a reused `event_id` for v8 trigger instead of publication?

### Exercise 4 — Approval state after an n8n `Wait` timeout

Question: The n8n `Wait` times out at two hours with no decision. What is the Approval state, and what does a
new execution do?

Think First: Whose clock moves the decision?

Starter Artifact: the `PENDING → APPROVED/REJECTED/EXPIRED/CANCELLED` model + backend `expires_at`.

Expected Output: still `PENDING` (n8n timeout changes no business state); a new execution observes the same
`approval_id`; only the backend `expires_at` yields `EXPIRED`; a late approve on an expired Approval is
rejected + audited.

Explanation: the n8n and Approval lifecycles are independent.

Follow-up Question: How does `REJECTED` differ from `EXPIRED`?

### Exercise 5 — Recover a lost-response publish

Question: The publish timed out (`OUTCOME_UNKNOWN`). How do you recover, and how do you classify 401 vs 409
vs 429?

Think First: Does a timeout mean the publish failed?

Starter Artifact: stable `operation_id` + `idempotency_key = approval-301:publish-report:artifact-v7`; the
status/error matrices.

Expected Output: keep the same operation/idempotency identity, query the authenticated FastAPI status/
reconciliation API, and act on `SUCCEEDED/PROCESSING/FAILED_TERMINAL/PENDING_RECONCILIATION/NOT_FOUND` (where
`NOT_FOUND` is ambiguous → verify identity/routing/retention + evidence and reissue only if the backend
proves NEVER_ACCEPTED and the idempotency retention is still valid, else reconcile); 401 → stop + classify
the auth failure (rotate only when expiry/compromise/revocation/invalid is established, else fix config);
409 → stop + investigate; 429/503 → bounded backoff + jitter + Retry-After.

Explanation: timeout is unknown outcome; recover by identity + authoritative query, classify by error
meaning.

Follow-up Question: When must an unknown external outcome enter `PENDING_RECONCILIATION`?

### Exercise 6 — Audit, duplicate delivery, and event-identity conflict

Question: (a) The same Approve callback is delivered twice. (b) A callback reuses `event_id` but carries a
different fingerprint (v8). How many business events, and what actions?

Think First: Is a delivery attempt a business decision? Does a reused identity with changed meaning approve
anything?

Starter Artifact: `approvals` + append-only `approval_events`; the event-identity rules.

Expected Output: (a) one logical `approval.approved` (two receipts/traces) — the second delivery is a
duplicate-safe no-op. (b) integration/security conflict — no action; produce safe conflict evidence; query
authoritative FastAPI; never authorize v8. Corrections/revocation append new events, never rewrite history;
append-only is not automatically tamper-proof.

Explanation: bind identity to meaning; separate current state, business audit, and delivery evidence.

Follow-up Question: Why is `n8n execution history` not the authoritative business audit?

### Exercise 7 — Error Workflow smallest safe boundary

Question: Publication succeeded; the final internal notification returned 503 and the Global Error Workflow
fired. What do you resume?

Think First: What completed durable work must NOT be redone?

Starter Artifact: the succeeded Task/Approval/Publication facts + the failed notification step.

Expected Output: resume only the notification recovery protocol (query status if available; retry on the same
notification idempotency key if available; else reconcile/escalate by duplicate risk) — not the whole
workflow.

Explanation: `Workflow retry != business operation retry`; recover the smallest incomplete operation.

Follow-up Question: What decides retry vs reconcile vs escalate for the notification?

### Exercise 8 — Incident classification (faulty release)

Question: `n8n-day69-v3` bypassed approval for some artifacts, restarted whole workflows, and leaked an
`Authorization` header, over a 20-minute window. Classify: (a) a publication that succeeded **without**
approval; (b) a duplicate Task provably not started; (c) a RUNNING Task that may have called the Provider.

Think First: Can rollback undo any of these? What is the credential exposure window?

Starter Artifact: the incident flow + the affected-set joins + authoritative-evidence hierarchy.

Expected Output: (a) preserve `publication=SUCCEEDED`, record the policy violation, **do not** fabricate
retroactive approval, create a compensation operation (retract/restrict/correct/notify where possible),
record partial/failed compensation honestly. (b) `ACCEPTED` + no Worker Attempt +
`provider_dispatch_started_at=null` + no Artifact/Publication → FastAPI durable guarded cancellation (never
delete; a late queue delivery observes the cancelled state and no-ops). (c) Worker Attempt exists +
`provider_dispatch_started_at != null` + no stored response/Artifact → `PENDING_RECONCILIATION` (cancel may
strand a charge; retry may double cost — reconcile Provider/Attempt/Object-Storage/DB/logs first).

Explanation: contain → revoke/rotate → preserve → scope → classify → cancel/reconcile/compensate → verify →
regression → controlled rollout; the credential exposure window runs until revocation and may exceed the
failure window; missing logs do not prove no operation occurred.

Follow-up Question: Why are "publication succeeded" and "publication complied with policy" separate
dimensions?

## 11. Relevant Framework Connections

* **n8n** — permissioned triggers, mapping, waiting, branching, notification, authenticated HTTP calls,
  Error Workflow, workflow version deactivation/rollback; execution history is orchestration evidence only.
* **FastAPI** — the trusted API/security boundary: approver identity/authz; Approval creation/decision/
  status; publication operation status; cancellation/reconciliation/compensation; guarded transitions and
  idempotency.
* **PostgreSQL** — durable Task/Approval/Publication truth; current-state constraints; append-only audit
  events; atomic state + audit/Outbox transitions.
* **Outbox/Worker** — one publication intent after one legal approval; late/duplicate queue delivery
  re-checks durable state; Provider-dispatched unknown outcomes require reconciliation.
* **Credential Store / Secret Manager** — real credentials, versions, controlled injection, revocation/
  rotation; no Secret in workflow/export/logs.
* **Permissioned Browser/AI Tool & Provider** — execution stays behind backend-owned contracts; external
  cost/side effects make blind retries unsafe.
* **Object Storage** — verified Artifact identity/version bound to the Approval; existence/integrity is not
  business approval.
* **Observability** — trace/execution/delivery evidence supports diagnosis; `correlation_id` connects the
  chain; logs never replace durable truth or contain Secrets.

## 12. AI Backend Connections

An AI-generated Research Report carries Provider/browser cost and external publication risk, so exact
Artifact/version binding prevents an old approval from authorizing changed AI output, and Provider-call
uncertainty requires reconciliation rather than blind replay. Validation/grounding evidence is not business
permission to publish; stable IDs control at-least-once delivery and duplicate external effects; risk-based
human approval supports enterprise AI automation without forcing manual review of every output; and audit,
Secret safety, and compensation protect tenant trust, security, compliance, cost, and reputation. Day70
directly consumes this hardened contract in the Phase 6 capstone; Day71 begins Phase 7A (LLM Application
Engineering) as a phase transition built on Day53–Day61, not on n8n.

## 13. English Interview

Key Vocabulary:

risk-based human approval · requester vs approver · tenant role (Report Owner / Manager / Tenant Admin /
Compliance) · validation vs authorization vs approval vs audit · exact binding (tenant/actor/action/
artifact-version/policy/expiry) · Approval lifecycle (PENDING/APPROVED/REJECTED/EXPIRED/CANCELLED) ·
OUTCOME_UNKNOWN · idempotency key / operation_id · PENDING_RECONCILIATION · credential reference vs Secret
Manager · redaction · append-only audit vs current state · duplicate delivery vs business decision ·
event-identity conflict · smallest-safe-boundary resume · contain/revoke/rotate/preserve/scope/classify/
cancel/reconcile/compensate/verify/rollout.

Useful Expressions:

- "Validation is evidence; approval is permission."
- "An n8n timeout changes no business state — the Approval stays PENDING until the backend deadline."
- "A timeout means the outcome is unknown, not that it failed — I keep the same idempotency key and query."
- "The workflow holds a credential reference; the real secret lives in the Secret Manager."
- "Two deliveries are one decision; a reused event_id with a different fingerprint is a conflict."
- "Rollback stops future harm; it does not undo a Provider charge or an external publication."

### Beginner

Question: Why do some AI-generated reports need human approval before external publication, and where is the
approval state stored?

Student answer (classroom record): *"These are high-risk documents intended for external clients that require
tenant management or specialized manual navigation; the authorization status should be stored in a
database."* (Review: correct direction; "tenant management / specialized manual navigation" → "approval from
an authorized user in the tenant organization"; "authorization status" → "approval state"; make FastAPI
verification + PostgreSQL authority explicit.)

Strong Answer: "Human approval is a risk-control step before a high-impact action such as publishing an
AI-generated report to an external client. An authorized user in the customer's organization approves or
rejects the exact action and artifact version. n8n may request and wait for the decision, but FastAPI must
verify the approver's authorization and store the authoritative approval state in PostgreSQL."

### Intermediate

Question: A publish request times out while an eight-minute AI task's report is being published. How should
the workflow respond, and why?

Student answer (classroom record): *"Retries cannot be performed casually; the current status of the FastAPI
result is unknown … Directly re-invoking the service could trigger a duplicate call to the provider and incur
additional costs."* (Review: strong direction; improve to "must not retry blindly"; replace "FastAPI result"
with the publication-operation outcome; make the status/reconciliation API + PostgreSQL authority + same
idempotency identity explicit.)

Strong Answer: "The workflow must not retry blindly because a timeout means the outcome is unknown, not that
the operation failed. It keeps the same operation ID and idempotency key, then queries FastAPI for the
authoritative publication state. If it succeeded, the workflow continues without publishing again; if it is
still processing, it keeps observing; if the external outcome cannot be verified, it enters reconciliation
instead of replaying. A blind retry could cause a duplicate publication, duplicate Provider work, extra cost,
or another irreversible side effect."

### Senior

Question: A faulty n8n release bypassed approval for some artifacts, restarted whole workflows, and leaked an
`Authorization` header. Walk through containment, classification, recovery, and safe rollout.

Student answer (classroom record): *"contain → revoke/rotate → preserve evidence → scope → classify →
cancel/reconcile/compensate → verify → regression checks → controlled rollout"* (Review: correct structure,
too compressed for a senior spoken answer.)

Strong Answer: "First I contain: deactivate the faulty workflow, stop automatic Error-Workflow replay,
activate a backend publication kill switch, and restore the last known-safe version without immediate full
traffic. Because a credential leaked, I revoke/rotate it and review its use from exposure to revocation —
the exposure window can exceed the workflow failure window. I preserve workflow/execution/audit/DB/log
evidence and bound the affected set by workflow/release version and a padded time window, joining
request/task/correlation/tenant IDs to approval/event/artifact-version to publication operation/idempotency/
external message IDs. Then I classify from durable evidence: a publication that succeeded without approval
stays a real success but gets a policy-violation record and compensation, never a retroactive approval; a
provably unstarted duplicate Task gets a FastAPI durable cancellation; a Provider-dispatched unknown-outcome
Task enters `PENDING_RECONCILIATION` — cancel could strand a charge and retry could double it. I verify
authoritative PostgreSQL/Provider/Artifact/idempotency evidence, add regression coverage for approval-bypass,
duplicate publication, Error-Workflow boundary, error classification, and Secret redaction, and roll out via
test tenant → canary → monitored expansion with stop conditions on approval bypass, duplicate publication,
fingerprint-conflict spikes, auth-error spikes, reconciliation backlog, or Secret exposure. Rollback stops
future harm but does not undo committed Tasks, Provider cost, or external publications."

### Common Weak Answer

"The publish timed out and the notification failed, so I restart the whole workflow, retry the publish, mark
the Approval expired because the n8n Wait ended, and log the Authorization header to debug the 401."

Strong Answer (why it fails): "This redoes completed business operations, risks a duplicate publication and
duplicate Provider cost, expires an Approval on the wrong (orchestration) clock, and leaks a secret. Instead:
resume only the failed notification on its own idempotency key; recover the publish by querying the
authoritative status on the same idempotency key; leave the Approval `PENDING` until the backend `expires_at`;
and never log the Authorization header — rotate the credential and record only redacted evidence."

### Follow-up Questions

Beginner follow-up: Is human approval required for every AI output?

Strong Answer: "No — approval is risk-based. Low-risk reversible actions (like saving an internal draft) can
be auto-authorized under a durable tenant policy; high-risk irreversible actions (external publication,
payment, deletion) need an explicit authorized decision."

Intermediate follow-up: Why can a v7 approval never authorize publishing v8?

Strong Answer: "The approver accepted the consequence of that exact artifact version and action. Changed
content is a new business intent: it needs a new `approval_id`, a new `event_id`, and a new publication
operation/idempotency identity, while `task_id`/`correlation_id`/`tenant_id` stay stable as chain
association."

Senior follow-up: Why is 'publication succeeded' separate from 'publication complied with policy', and how do
you record it?

Strong Answer: "Success is a durable external fact; policy compliance is an authorization fact. A publication
that bypassed approval is genuinely `SUCCEEDED` and must be preserved as such, with a separate policy-
violation record and a compensation operation — post-incident acknowledgement can never be rewritten as
pre-publication approval, because audit preserves what actually happened."

## 14. Mental Model Summary

```text
approve?          = risk/irreversibility/impact/tenant policy (NOT "because it's AI").
approver          = authorized tenant role; platform enforces identity/policy/durability.
validation        = quality/safety evidence != permission to publish.
approval binding  = tenant + actor + action + artifact/version + policy + expiry; v7 approval != v8.
lifecycles        = n8n execution timeout != Approval state; PENDING until backend expires_at.
retry             = OUTCOME_UNKNOWN on timeout; same operation_id + idempotency key; query FastAPI; classify. NOT_FOUND is ambiguous -> verify identity/routing/retention + evidence; reissue only if backend proves NEVER_ACCEPTED AND idempotency retention still valid; else reconcile (same key != unconditional safety).
error classes     = 429/503 backoff | 400/422 fix | 401 stop+classify (rotate only if expired/compromised/revoked/invalid, else fix config) | 403 investigate | 409 stop | terminal no-retry | unknown -> reconcile.
secrets           = workflow=reference; Secret Manager=real; logs/audit/export = NO secret (401 -> stop+classify; rotate only when established, else fix config; never blind retry).
audit             = current state + append-only events (atomic); delivery attempt != decision;
                    same event_id+same fingerprint=no-op; same event_id+different fingerprint=conflict; not tamper-proof.
error workflow    = resume smallest safe operation boundary (workflow retry != business operation retry).
incident          = contain -> revoke/rotate -> preserve -> scope -> classify -> cancel/reconcile/compensate -> verify -> regression -> rollout.
authority         = FastAPI/PostgreSQL; n8n history/logs/traces = evidence, never truth or retry permission.
```

> Classroom-authorship note: at the student's explicit request (*“你帮我总结吧”*) the Tech Lead supplied the
> final Chinese Mental Model directly, per the live-teaching standard. That synthesis is taught material, not
> an independently authored student answer.

## 15. Today's Takeaway

Hardening a long-running AI workflow is not "add a human click node." It is giving high-risk actions explicit
authorization, classified recovery, secret safety, and authoritative audit — while n8n gains no new
authority. A human accepts the risk; the backend verifies authority and persists truth; stable identities and
idempotency absorb duplicates; timeouts mean unknown, not failed; secrets never enter artifacts or logs;
audit keeps the real history; and on a bad release you contain, rotate, preserve, scope, classify, then
cancel/reconcile/compensate through FastAPI — because rollback cannot undo a Provider charge or an external
publication.

## 16. Before Next Lesson Checklist

- [ ] I can decide when approval is required (risk-based) and name the correct tenant approver.
- [ ] I can distinguish validation, authorization, approval, and audit.
- [ ] I can design an Approval that binds tenant/actor/action/artifact-version/policy/expiry, where v7 ≠ v8.
- [ ] I can keep the Approval lifecycle independent of the n8n execution lifecycle (PENDING until backend
      `expires_at`).
- [ ] I can recover a lost-response publish by identity + authoritative query, and classify 429/503 vs
      400/422 vs 401 vs 403 vs 409 vs terminal vs unknown.
- [ ] I can keep Secrets in a Credential Store, redact evidence, and recover a 401 by first classifying it
      (rotate only when expiry/compromise/revocation/invalid is established, else fix config), never blind retry.
- [ ] I can model current-state + append-only audit, treat duplicate deliveries as one decision, and reject a
      reused `event_id` with a different fingerprint as a conflict.
- [ ] I can resume an Error Workflow at the smallest safe boundary and run contain → revoke/rotate → preserve
      → scope → classify → cancel/reconcile/compensate → verify → rollout.
- [ ] I understand the evidence limits: Day69 is CONCEPTUAL_STATIC; the n8n runtime, FastAPI integration,
      approval/callback/PostgreSQL/credential-store/Provider behaviours, and production are NOT RUN, no
      workflow JSON was exported, and Day67's `400` / Day68's contract are not Day69 evidence.

---

Related: [Day69 n8n Risk-based Approval Gate contract](../../projects/n8n-workflows/README.md)
· [cheat sheet](../../cheat_sheets/fastapi.md) · [interview](../../interview/fastapi.md)
· Previous: [Day68 — Long-running AI Jobs: Polling, Callback, Correlation and Idempotency](day68-long-running-ai-jobs-polling-callback-correlation-and-idempotency.md)
· Next: Day70 — n8n + FastAPI + AI Tool Integration Capstone and Interview
