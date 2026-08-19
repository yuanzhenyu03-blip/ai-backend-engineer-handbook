# Day70 — n8n + FastAPI + AI Tool Integration Capstone and Interview

## 1. Lesson Metadata

```text
Status:        ✅ Completed (Phase 6 capstone) — decision model + workflow static contract EXECUTED_LOCAL_RUNTIME (18 passed; the classroom's 14 pre-fix tests superseded); a bounded, authenticated real n8n → FastAPI service-call acceptance slice reached INTEGRATION_RUNTIME for the PRE-FIX workflow (the FIXED workflow is NOT RERUN; inbound caller → n8n auth NOT RUN); rest CONCEPTUAL_STATIC / NOT RUN
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 5-6 hours
Prerequisite:  Day67 boundary; Day68 observation/delivery; Day69 approval/retry/Secrets/audit; Day59-Day61 real backend integration; Day66 permissioned browser tool
Previous Lesson: Day69 — Human Approval, Retry, Secrets, Audit and Error Workflows
Next Lesson:   Day71 — LLM Application Engineering (Phase 7A; PHASE TRANSITION, not an n8n dependency)
Engineering Artifact: projects/n8n-workflows/ (DAY70_CAPSTONE.md + day70_capstone.py + test_day70_capstone.py + day70_minimal_acceptance_workflow.json)
```

Day70 integrates the Phase 6 contracts into one failure-aware capstone, runs the **maximum feasible real
`n8n -> FastAPI -> PostgreSQL` acceptance slice**, keeps strict runtime-evidence boundaries, and completes
the Phase 6 rollback exercise and English interview. n8n still gains no authority over durable facts.

> Evidence honesty — Day70 spans three tiers, and each is scoped narrowly:
>
> * `EXECUTED_LOCAL_RUNTIME` — the pure Python decision model (`day70_capstone.py`) plus the n8n workflow
>   static contract, driven by `test_day70_capstone.py`: the classroom ran the pre-fix suite on Python 3.11.5
>   → **14 passed** (now **superseded** — before the Approval-binding, request-body, IF-validation and
>   inbound-auth fixes); a first attempt on Python 3.9.6 reported "No module named pytest" (a
>   missing-dependency skip, **NOT RUN**, not a failure); the updating agent re-ran the **FIXED** suite on
>   Python 3.10.12 → **18 passed**, and re-ran the affected Day59 fingerprint test → **12 passed**;
>   repository-standard Python 3.12 is **NOT RUN**. The four added areas are: the full Approval authorization
>   binding (a complete expected-authorization context plus one negative per mismatched field), the workflow
>   request-body contract (`document_ids` + `business_input.report_scope`), the IF validation of
>   `report_scope`/`request_id`/`document_id`, the inbound-Webhook-auth reference, and the Day59 proof that a
>   changed `report_scope` is a different fingerprint (409, not a replay). A real n8n inspection alone (n8n
>   2.25.6, `GET /healthz -> 200`) is also `EXECUTED_LOCAL_RUNTIME`, not cumulative integration.
> * `INTEGRATION_RUNTIME` — performed **in class** against disposable local infra (NOT re-run by the
>   updating agent), for the **PRE-FIX** workflow (top-level `report_scope`; no inbound Webhook auth): a
>   bounded real **authenticated `n8n -> FastAPI/Uvicorn -> PostgreSQL` service-call acceptance** slice —
>   `POST /webhook/day70/research-report -> 202` with a stable Task id, an exact redelivery -> the same id
>   with `idempotency_replayed=true`, a new-connection DB check (`jobs=1, outbox=1, document_links=1`,
>   64-char fingerprint, `queued`), and invalid input -> `400` with zero Jobs. This proves the acceptance
>   boundary only; the credential exercised was the **n8n -> FastAPI** service identity, so it does **not**
>   prove external-caller -> n8n Webhook authentication. It is **not** evidence for the **FIXED** workflow
>   (report_scope in `business_input`, three-field IF, inbound `headerAuth` reference): that workflow's real
>   integration is **NOT RERUN**, and the "different `report_scope` -> different fingerprint -> 409" behaviour
>   is proven only by the Day59 fingerprint contract test, not by an integration run. It does **not** upgrade
>   the rest of the capstone.
> * `CONCEPTUAL_STATIC` / **NOT RUN** — everything else: budget reservation in the acceptance transaction;
>   a FastAPI-persisted/returned `correlation_id` and its propagation; real Polling/Callback/Approval/
>   Publication/Error-Workflow runtime; real Worker/Outbox-Relay/broker/Browser-Tool/Provider execution;
>   verified Artifact generation; real credential revoke/rotation/exposure review (only controlled local
>   Credential Store injection ran); the rollback/kill-switch/canary incident exercise; production. No real
>   or paid Provider call; no production credentials/customer data; no captured n8n post-run export (the
>   published Workflow was imported and run, but the post-run export could not be captured). Day59–Day69
>   evidence is a named prerequisite, **not** Day70 validation.

## 2. Learning Objectives

By the end of Day70 you can:

* Configure an n8n workflow with two independent auth boundaries (inbound caller -> n8n and n8n -> FastAPI,
  each a Credential Store reference) and prove a bounded authenticated n8n -> FastAPI service-call acceptance
  `n8n -> FastAPI -> PostgreSQL` acceptance + idempotent redelivery with new-connection DB evidence.
* Keep the responsibility boundary exact: n8n orchestrates; FastAPI authenticates/authorizes and enforces
  transitions; PostgreSQL owns durable truth.
* Reuse the Day68 long-running observation/identity/idempotency and Day69 approval/retry/Secrets/audit
  contracts as one cumulative path — and state honestly which parts ran.
* Classify and recover the six capstone failure areas (acceptance recovery, event dedupe/conflict, exact
  Approval binding, Publication recovery, credential classification, incident Task classification).
* Run the Phase 6 rollback exercise (contain → revoke/rotate → preserve → scope → classify →
  cancel/reconcile/compensate → verify → regression → controlled rollout).
* Apply the four-tier evidence taxonomy without upgrading conceptual/static reasoning or a single
  integration run into cumulative-integration or production evidence.

## 3. Why This Matters

A capstone is where "each contract works on its own" meets "does the whole chain stay honest under
failure." The tempting mistake is to let a green pytest suite or one working acceptance call stand in for a
whole integrated system. Day70's discipline is the opposite: run the maximum feasible real slice — a real
n8n workflow POSTing to a real FastAPI on a real PostgreSQL, proving `202` + idempotent redelivery with a
new-connection DB read — and then **stop and label** everything the slice did not exercise as NOT RUN. That
honesty is the deliverable. It is also what keeps a production incident survivable: when a bad release
duplicates publications and leaks a credential, the team that already separated orchestration evidence from
durable truth can contain, rotate, scope, classify, and compensate — instead of deleting history and
hoping.

## 4. Roadmap Position

```text
Day59-Day61 real FastAPI/runtime integration evidence
  + Day66 permissioned queue-backed browser-tool contract
  + Day67 n8n/FastAPI responsibility boundary
  + Day68 long-running observation/identity/Callback/idempotency contracts
  + Day69 Approval/retry/Secrets/audit/Error-Workflow hardening
  -> Day70 Phase 6 integration capstone   <- YOU ARE HERE (Phase 6 closes)
  == PHASE TRANSITION (not a technical prerequisite) ==
  -> Day71 LLM Application Engineering (Phase 7A; primary foundations = Day53-Day61 Provider/runtime)
```

Day70 closes Phase 6. Day71 begins Phase 7A as a **phase transition**: its technical foundations are the
Day53–Day61 Provider boundary, resilience, testing, observability, and runtime integration — not n8n. n8n
may later call an LLM Application Runtime as an external orchestration client, but it is not that runtime's
prerequisite.

## 5. Lesson Map

```text
1. The cumulative path and the responsibility boundary
2. Honest 202: the real acceptance slice (what ran) and its evidence tier
3. Observe the same Task; observation failure changes no durable state
4. Exact-version Approval binding (v7 cannot authorize v8)
5. Duplicate delivery vs identity conflict
6. Classified recovery: acceptance / publication / credential
7. Incident classification + the Phase 6 rollback exercise
8. The four-tier evidence taxonomy and NOT RUN discipline
```

## 6. Core Mental Model

```text
n8n owns permissioned orchestration, not durable truth.
FastAPI/PostgreSQL owns authn/authz, tenant isolation, durable Task/Approval/Publication state, idempotency,
legal transitions, recovery, and authoritative audit.

202 is honest only after the acceptance bundle commits; after 202, observe the SAME Task identity.
Observation failure and n8n execution failure do not mutate or replace the durable Task.
Browser/Worker output becomes usable through a verified protected Artifact; validation is evidence, not
permission; high-risk action needs an authorized Approval for the exact Artifact version and action.
Retry = classified recovery: preserve identity, query authoritative evidence, retry only when proven safe,
else reconcile. Same event_id+same fingerprint = no-op; same event_id+different fingerprint = conflict.
Rollback stops future harm · cancellation handles proven-safe work · reconciliation resolves unknown
outcomes · compensation addresses completed effects · audit preserves history.
Evidence: real n8n->FastAPI->PostgreSQL ACCEPTANCE + idempotent redelivery reached INTEGRATION_RUNTIME;
the rest stays explicitly NOT RUN. A green test suite or one integration run is not cumulative integration
or production.
```

### Mental Model Evolution (Day69 → Day70)

```text
Day69: each hardening contract (approval, classified retry, Secrets, audit, error workflow) is correct on
       its own, as CONCEPTUAL_STATIC design.
Day70: the contracts become ONE cumulative path, and the class ran the maximum feasible REAL slice (n8n ->
       FastAPI -> PostgreSQL acceptance + idempotent redelivery) — while explicitly refusing to pretend the
       remaining Polling/Callback/Approval/Publication/Worker/Provider/rollback path ran. Integration is
       earned per-boundary, not inherited from adjacent green evidence.
```

## 7. Main Concepts

### Concept 1: The cumulative path and the responsibility boundary

Tech Lead Question:

Wire the whole Phase 6 chain end to end. Who owns each step, and can n8n ever hold the durable fact?

Student Thinking:

n8n moves data between steps, so it feels like it "runs" the process — but the durable state and identity
have to live somewhere transactional.

Student Answer (English interview): *"n8n handles workflow orchestration and data passing, while FastAPI and
PostgreSQL manage the persistent storage of factual data and authoritative authentication."*

Tech Lead Review:

Right split, one correction: n8n handles orchestration/mapping/waiting/branching/authenticated calls;
**FastAPI** authenticates/authorizes and enforces transitions; **PostgreSQL** stores durable business
truth. Do not assign authentication to PostgreSQL. There are two independent auth boundaries — inbound caller → n8n
(a Webhook credential reference, NOT RUN at run time) and n8n → FastAPI (the HTTP service credential). The
path is: authenticated-service trigger → map/validate report_scope+request_id+document_id →
FastAPI durable acceptance → honest `202` + stable Task identity → observe the same Task → permissioned
execution boundary → verified protected Artifact reference → durable exact-version Approval → idempotent
Publication → correlated audit + terminal result.

Engineering Thinking:

Keep one authoritative boundary; an orchestrator that can call anything is still an untrusted caller.

Production Example:

A tenant user submits a research report; n8n POSTs to FastAPI; FastAPI's transaction (not n8n) creates the
Job + Outbox intent + Document link.

Framework Connection:

n8n `HTTP Request` → FastAPI `POST /v1/jobs` (auth + idempotency) → PostgreSQL acceptance bundle.

Exercise:

Name the durable facts n8n may never write. (Section 10.)

### Concept 2: Honest 202 — the real acceptance slice

Tech Lead Question:

What did we actually prove by running the real workflow, and what is its evidence tier?

Student Thinking:

`202` should mean the task is durably accepted, not merely that the webhook fired.

Student Answer: *`task_id outbox intent budget`* (acceptance proof fields).

Tech Lead Review:

Job/Task and Outbox intent are correct; the actual Day59 gate **also** required a request fingerprint and a
verified Document link, read from a **new** DB connection. **Budget reservation belongs in the complete
production acceptance bundle but is absent from the current Day59 implementation, so budget remained NOT
RUN.** What ran, in class, `INTEGRATION_RUNTIME` for the **PRE-FIX** workflow (top-level `report_scope`; no
inbound Webhook auth): an authenticated **n8n → FastAPI service call** — `POST /webhook/day70/research-report
-> 202` with a stable Task id; an exact webhook redelivery -> the same id with `idempotency_replayed=true`; a
new-connection DB check `jobs=1, outbox=1, document_links=1`, fingerprint length 64, state `queued`; invalid
input -> `400` with zero Jobs for that request identity. That proves the acceptance boundary — nothing
downstream. It used the **n8n → FastAPI** service credential, so it did **not** prove external-caller → n8n
Webhook authentication, and it is **not** evidence for the FIXED workflow (report_scope in `business_input`,
three-field IF, inbound `headerAuth` reference), whose real integration is **NOT RERUN**. The corrected body
contract is `{ "document_ids": [document_id], "business_input": { "report_scope": ... } }` so `report_scope`
enters the Day59 fingerprint; a changed `report_scope` is a different fingerprint (**409, not a replay**),
proven by the Day59 fingerprint contract test, not by an integration run.

Engineering Thinking:

`202` is a promise about committed state; only the system that committed may make it, and the proof is a
new-connection read, not the HTTP response alone.

Production Example:

A dropped acceptance response is retried with the same `Idempotency-Key`; FastAPI returns the existing Job,
`idempotency_replayed=true`.

Framework Connection:

FastAPI Day59 `POST /v1/jobs` (`Idempotency-Key` header, fingerprint over ordered `document_ids` **and**
sorted `business_input`, so `report_scope` is inside the fingerprint); `day70_capstone.acceptance_recovery`.

Exercise:

State the acceptance-bundle facts and which one is NOT RUN. (Section 10.)

### Concept 3: Observe the same Task; observation failure changes no durable state

Tech Lead Question:

n8n polls a long Task and a Poll fails, or the n8n execution disappears. Does the Task change?

Student Thinking:

The observer failing says nothing about the durable fact.

Student Answer: *`n8n 轮询时应该持续查询同一个 task_id`*; for a QUEUED Task, *`允许n8n响应状态，不能做业务动作`*; on
observation-deadline expiry, *`不能，n8n execution可以重新发起。durable Task应该继续处于queued`*.

Tech Lead Review:

Correct. Every Poll observes the **same** `task_id` with bounded backoff and an observation deadline. For a
QUEUED Task n8n may wait, re-query, and send non-authoritative progress — it may not start a Worker, mutate
Task state, fail the Task, or publish. On deadline expiry a **new** orchestration execution may resume
observation of the same `task_id`; it must not issue a new business command. An observation failure (e.g. a
503 while checking Artifact verification) is retried as an authenticated **observation** only — never
Browser/Provider execution — preserving the same Task/Artifact identity (*`可以wait 结合backoff+jitter 之后受控
retry`*).

Engineering Thinking:

Separate the observer lifecycle from the durable-fact lifecycle; only backend-owned transitions move truth.

Production Example:

A redeployed n8n pod re-observes the same `task_id`; the report finishes normally; no replacement Task is
created.

Framework Connection:

`day70_capstone.poll_decision` / `observation_failure_changes_durable_state`.

Exercise:

Decide what n8n may and may not do for a QUEUED Task. (Section 10.)

### Concept 4: Exact-version Approval binding

Tech Lead Question:

Can n8n set `approved=true` and publish? And can a v7 approval publish v8?

Student Thinking:

n8n coordinates approval, but the decision and its exact scope must be a backend fact.

Student Answer: *`不行，需要经过审批`*; binding fields initially only *`task_id artifact version Approval_id`*;
for v7→v8, *tenant_id/task_id/policy_id/approver_actor_id could remain stable*.

Tech Lead Review:

n8n requests/waits/branches; FastAPI authenticates + authorizes the tenant approver and **atomically**
persists the Approval decision and audit event. An Approval binds at least `approval_id, tenant_id, task_id,
artifact_id/version, exact action, approver actor/role, policy/version, expiry, decision, decision time`:

```text
Approval = exact tenant + authorized actor + exact action + exact Artifact/version + exact policy + bounded lifetime
```

For v7→v8: `tenant_id`/`task_id`/`correlation_id` may stay stable; the same policy/action/actor **may**
apply but must be **revalidated**; `artifact_version`, `approval_id`, approval `event_id`, Publication
`operation_id`, and the Publication idempotency identity must be **new**. A v7 approval can never authorize
v8.

Engineering Thinking:

Bind authorization to the exact object version and action; identity reuse across changed meaning is a bug or
an attack.

Production Example:

An editor produces v8 after v7 was approved; publishing v8 requires a fresh Approval + fresh event/
publication identities.

Framework Connection:

`day70_capstone.approval_authorizes` (takes an `AuthorizationContext` and compares tenant/task/artifact
id+version/action/policy **and** approver role, requires `decision == APPROVED` and not expired — presence of
fields is not enough) / `approval_binding_complete` / `identity_is_stable_v7_to_v8` /
`identity_is_new_v7_to_v8`.

Exercise:

Classify stable vs new vs revalidate identities for a legitimate v8 approval. (Section 10.)

### Concept 5: Duplicate delivery vs identity conflict

Tech Lead Question:

The same Approve/Publish callback arrives twice; then the same `event_id` arrives carrying a different
Artifact version. What happens?

Student Thinking:

A redelivery is one decision; a reused identity with changed meaning is not a new approval.

Student Answer: *`第二次应该返回同一个发布而不是创建第二次发布`* (same event_id, same meaning); *`进入冲突调查`* (same
event_id, different Artifact version).

Tech Lead Review:

Correct. Delivery identity and business idempotency stay separate:

```text
same event_id + same fingerprint     = idempotent no-op
same event_id + different fingerprint = conflict / investigation (never a new approval/publication)
```

Engineering Thinking:

Bind identity to meaning via a fingerprint; a reused identity with changed meaning fails closed.

Production Example:

A retried Approve callback is a no-op; a spoofed callback reusing `event_id` for v8 routes to conflict
evidence, not publication.

Framework Connection:

`day70_capstone.classify_event`.

Exercise:

Classify the two deliveries above. (Section 10.)

### Concept 6: Classified recovery — acceptance, publication, credential

Tech Lead Question:

An acceptance response is lost; a publish times out; a call returns 401. What do you do for each?

Student Thinking:

A timeout is unknown, not failed; and not every 401 means rotate.

Student Answer: lost acceptance → *`进入PENDING_RECONCILATIOn`* (and preserve identity); unknown publication →
`PENDING_RECONCILIATION`; ordinary 401 always rotate? → *`不是`*; NOT_FOUND proves never-accepted? → *`不能`*.

Tech Lead Review:

n8n cannot write `PENDING_RECONCILIATION`; it preserves the original request/operation/idempotency identity
and queries authenticated FastAPI — **FastAPI/PostgreSQL owns the reconciliation state**. Reissue is allowed
only after authoritative `NEVER_ACCEPTED` proof **and** a still-valid idempotency retention window
(`same idempotency key != unconditional proof of safety`). A `NOT_FOUND`/404 is ambiguous (wrong
tenant/auth/route/environment, replica delay, retention/archival, wrong key type, or true absence) — verify
authoritative facts first. A publish timeout is `OUTCOME_UNKNOWN`: query the authoritative operation status
and a strictly-matching external receipt — confirmed success is recorded (no republish), proven non-start
may be reissued under the same identity, unknown stays reconciliation, business rejection is terminal. A
`401` is stopped and **classified**: rotate only when expiry/revocation/compromise/leak/established-
invalidity is proven; fix configuration for audience/issuer/scheme/header/endpoint/clock skew.

Engineering Thinking:

Recover by identity + authoritative query; classify by cause; never let unknown masquerade as safe.

Production Example:

A publish times out; the operation status says `SUCCEEDED`, so the workflow continues without republishing.

Framework Connection:

`day70_capstone.acceptance_recovery` / `publication_recovery` / `classify_credential_failure` /
`not_found_proves_never_accepted`.

Exercise:

Run the three recovery matrices. (Section 10.)

### Concept 7: Incident classification and the rollback exercise

Tech Lead Question:

A bad release duplicated Approvals/Publications, some outcomes are unknown, and an `Authorization` header
leaked to logs. Contain and classify.

Student Thinking:

Rollback stops future harm but cannot undo committed facts or external effects.

Student Answer: containment *`回滚坏release停止继续创建新的 Approval 和 Publication，并停止retry，backend kill switch，
从credential store进行credential替换`*; PostgreSQL history deleted to roll back? → *`不能`*; a QUEUED Task with no
claim/dispatch/artifact → *`可以通过 FastAPI 执行持久取消`*; Provider-dispatched unknown → `PENDING_RECONCILIATION`.

Tech Lead Review:

Correct containment chain; strengthen it: immediately **revoke/rotate** the exposed credential (not merely
replace configuration), verify the old one is rejected, and do not resume traffic yet. Scope with a padded
time window + in-flight executions, joining workflow/release/execution → tenant/request/task/correlation →
Attempt/Provider-request → Approval/event → Artifact/version → Publication operation/idempotency/external
receipt (the credential exposure window is separate: first-possible-exposure → revocation). Classify: a
publication that succeeded **without** approval stays a real `SUCCEEDED` with a **separate** policy-violation
record + compensation (never rewritten as failure, never retro-approved); a provably-unstarted Task takes a
guarded FastAPI durable cancellation (**0 rows affected → facts moved → stop + reclassify**); a
Provider-dispatched unknown outcome enters `PENDING_RECONCILIATION`. When n8n history says "Publication
failed" but a strictly-matching external receipt proves success, record Publication `SUCCEEDED` and record
the acknowledgement/orchestration failure separately.

Engineering Thinking:

Contain future harm first; committed facts + external effects need cancel/reconcile/compensate, not deletion.

Production Example:

`workflow.v3` double-published; you deactivate it, kill-switch publication, rotate the leaked credential,
scope by stable IDs, and compensate — nothing is deleted.

Framework Connection:

`day70_capstone.classify_incident_task` / `guarded_cancellation_result`; the full runbook in
`DAY70_CAPSTONE.md`.

Exercise:

Classify three incident Tasks. (Section 10.)

### Concept 8: Evidence taxonomy and NOT RUN discipline

Tech Lead Question:

The pure tests pass and one acceptance call worked. Is the capstone integrated? Is it production-ready?

Student Thinking:

Green tests and one working call are necessary but far from cumulative integration or production.

Student Answer: pure Python tests classified as `EXECUTED_LOCAL_RUNTIME`.

Tech Lead Review:

Correct — and tests/fakes never auto-upgrade to `INTEGRATION_RUNTIME`; real n8n, FastAPI/Uvicorn, and
PostgreSQL must participate and evidence must be saved. The only `INTEGRATION_RUNTIME` here is the bounded
acceptance slice; a single integration run is not production. Where the classroom wanted separate
`CONCEPTUAL` vs `STATIC` language, treat them as subcategories inside `CONCEPTUAL_STATIC` (architecture
reasoning vs static configuration review) — do not invent runtime evidence.

Engineering Thinking:

Earn integration per-boundary; label the rest NOT RUN; never inherit adjacent green evidence.

Production Example:

A dashboard shows "all Phase 6 green"; the honest capstone shows one acceptance boundary integrated and a
long explicit NOT RUN list.

Framework Connection:

The four-tier taxonomy (`CONCEPTUAL_STATIC` / `EXECUTED_LOCAL_RUNTIME` / `INTEGRATION_RUNTIME` /
`PRODUCTION`); `DAY70_CAPSTONE.md` evidence matrix.

Exercise:

Tier each Day70 activity. (Section 10.)

## 8. Common Misconceptions

1. **n8n can write `PENDING_RECONCILIATION`.** Correction: n8n preserves identity and queries authenticated
   FastAPI; FastAPI/PostgreSQL owns the reconciliation state.
2. **A 404/NOT_FOUND proves the command was never accepted.** Correction: it is ambiguous; verify
   authoritative facts, and a same idempotency key is not unconditional retry permission.
3. **A v7 approval can authorize v8 because the task is "the same."** Correction: exact-version binding —
   new artifact_version/approval_id/event_id/publication identities; revalidate policy/action/actor.
4. **Duplicate deliveries are two approvals; a reused `event_id` with a new version is a new approval.**
   Correction: same fingerprint = no-op; different fingerprint = conflict.
5. **An ordinary 401 always means rotate.** Correction: classify first; rotate only when the credential is
   established expired/revoked/compromised/leaked/invalid, else fix configuration.
6. **Rollback reverses completed external effects; delete history to roll back.** Correction: rollback stops
   future harm; preserve succeeded Publications + policy-violation record, reconcile unknowns, compensate
   completed effects; audit never rewrites history.
7. **Assign authentication to PostgreSQL (interview wording).** Correction: FastAPI authenticates/authorizes;
   PostgreSQL stores durable truth.
8. **A green test suite / one acceptance run means the capstone is integrated or production-ready.**
   Correction: only the bounded acceptance slice reached INTEGRATION_RUNTIME; the rest is NOT RUN.

## 9. Engineering Trade-offs

* **Run the maximum feasible real slice vs mock the whole chain.** Mocking is fast but proves nothing about
  real n8n/FastAPI/PostgreSQL behaviour; the real acceptance slice earns one honest INTEGRATION_RUNTIME
  boundary and exposes exactly what remains NOT RUN.
* **One "all green" capstone claim vs per-boundary evidence tiers.** A single green banner hides risk;
  per-boundary tiers make the integration frontier explicit and auditable.
* **Blind retry vs classified recovery.** Blind retry duplicates paid/irreversible effects; identity +
  authoritative query + classification preserves correctness at higher engineering cost.
* **Delete/rollback vs preserve + cancel/reconcile/compensate.** Deletion looks clean but destroys evidence
  and cannot undo external effects.
* **Ship the capstone now vs gate on the NOT RUN list.** Declaring "done" on green pieces is tempting;
  Day70's honesty is to close Phase 6 on the acceptance slice while listing every unexecuted boundary as the
  Day70→production backlog.

## 10. Hands-on Exercises

Two artifacts are runnable; the rest are design/classification exercises. Run the decision model:

```bash
cd projects/n8n-workflows
python3 -m pytest -q test_day70_capstone.py
```

(Classroom pre-fix suite: Python 3.11.5 → 14 passed, now superseded. Updating agent, FIXED suite: Python
3.10.12 → 18 passed; affected Day59 fingerprint test → 12 passed. Python 3.12: NOT RUN.)

### Exercise 1 — Acceptance recovery after a lost response

Question: The acceptance response was lost. What do you do, and when may you reissue?
Think First: Does a timeout mean not-accepted?
Starter Artifact: `day70_capstone.acceptance_recovery(state, retention_valid)`.
Expected Output: `ACCEPTED → RETURN_EXISTING`; `NEVER_ACCEPTED + retention valid → REISSUE_SAME_KEY`;
`NEVER_ACCEPTED + retention expired → PENDING_RECONCILIATION`; `UNKNOWN/NOT_FOUND → PENDING_RECONCILIATION`.
Explanation: n8n preserves identity + queries FastAPI; same key is not unconditional safety.
Follow-up: Why is `NOT_FOUND` never proof of never-accepted?

### Exercise 2 — Duplicate delivery vs conflict

Question: Same callback twice; then same `event_id` with a different Artifact version.
Think First: Is a delivery attempt a business decision?
Starter Artifact: `day70_capstone.classify_event`.
Expected Output: same fingerprint → `IDEMPOTENT_NO_OP`; different fingerprint → `CONFLICT`; new event_id →
`PROCESS_NEW`.
Explanation: delivery identity ≠ business meaning.
Follow-up: What must a reused `event_id` for v8 trigger instead of publication?

### Exercise 3 — Exact-version Approval binding

Question: `approval-301` approved v7; publish v8 now?
Think First: What exactly did the approver accept?
Starter Artifact: `day70_capstone.approval_authorizes` (full `AuthorizationContext` match) + the v7→v8 identity plan.
Expected Output: v8 → not authorized; stable = tenant_id/task_id/correlation_id; new =
artifact_version/approval_id/approval_event_id/publication_operation_id/publication_idempotency_key;
revalidate = policy_version/action/approver_actor.
Explanation: authorization binds to exact object version + action.
Follow-up: Which fields are neither auto-stable nor fresh business-intent identities?

### Exercise 4 — Publication recovery

Question: The publish timed out.
Think First: Unknown or failed?
Starter Artifact: `day70_capstone.publication_recovery`.
Expected Output: SUCCEEDED→no republish; PROCESSING→observe; FAILED_TERMINAL→no retry;
PENDING_RECONCILIATION→reconcile; NOT_FOUND→verify before any reissue.
Explanation: OUTCOME_UNKNOWN; query authoritative status + strict external receipt.
Follow-up: When may proven non-start be reissued under the same identity?

### Exercise 5 — Credential 401 classification

Question: A publish returns 401.
Think First: Is rotation always right?
Starter Artifact: `day70_capstone.classify_credential_failure`.
Expected Output: expired/revoked/compromised/leaked/invalid → ROTATE; audience/issuer/scheme/header/
endpoint/clock-skew → FIX_CONFIGURATION; unknown → STOP_AND_CLASSIFY.
Explanation: rotate only when the credential itself is established bad; the leaked-header scenario is
scenario-specific rotation, not the universal 401 response.
Follow-up: Why must you never blind-retry a 401?

### Exercise 6 — Incident Task classification

Question: Classify (a) published-without-approval; (b) provably-unstarted duplicate; (c) Provider-dispatched
unknown.
Think First: Can rollback undo any of these?
Starter Artifact: `day70_capstone.classify_incident_task` + `guarded_cancellation_result`.
Expected Output: (a) PRESERVE_AND_COMPENSATE; (b) DURABLE_CANCELLATION (0 rows → RECLASSIFY); (c)
PENDING_RECONCILIATION.
Explanation: preserve facts; cancel proven-safe; reconcile unknown; compensate completed.
Follow-up: Why are "publication succeeded" and "publication complied with policy" separate dimensions?

### Exercise 7 — Tier the Day70 evidence

Question: Tier each activity: architecture reasoning; node inspection; pure tests; the acceptance slice;
Approval/Publication runtime; production.
Think First: What must participate for INTEGRATION_RUNTIME?
Starter Artifact: `DAY70_CAPSTONE.md` evidence matrix.
Expected Output: reasoning/inspection → CONCEPTUAL_STATIC; pure tests + n8n inspection →
EXECUTED_LOCAL_RUNTIME; acceptance slice → INTEGRATION_RUNTIME; Approval/Publication runtime + production →
NOT RUN.
Explanation: earn integration per boundary; never inherit adjacent green evidence.
Follow-up: Why can't Day59–Day69 evidence serve as Day70 validation?

## 11. Relevant Framework Connections

* **n8n** — Webhook acceptance flow, Wait/Poll/Switch, Callback entry, Error Workflow, version
  deactivation/rollback, execution history as orchestration evidence; the importable
  `day70_minimal_acceptance_workflow.json` (Secret-free, Credential Store reference only).
* **FastAPI** — the Day59 `POST /v1/jobs` acceptance route (`Idempotency-Key`, request fingerprint, verified
  Document link); authenticated status/reconciliation/cancellation/compensation surfaces (mostly NOT RUN for
  Day70).
* **PostgreSQL** — durable acceptance bundle (Job + Outbox intent + Document link + 64-char fingerprint);
  new-connection reads as the proof of `202`.
* **Outbox/Worker/Provider/Browser Tool** — carried forward as contracts; NOT executed in this cumulative
  path.
* **Credential Store / Secret Manager** — a runtime-only local test identity was injected and the plaintext
  import file deleted immediately; real revoke/rotation/exposure review is NOT RUN.

## 12. AI Backend Connections

A user-facing AI research/report request flows through n8n but must be accepted, approved, and published by
the backend; the Browser/Worker output becomes usable only through a verified protected Artifact reference
(never raw DOM/screenshots/download content to n8n). Provider cost and external publication risk make blind
recreation dangerous, so unknown outcomes reconcile rather than replay. Day70 closes Phase 6; Day71 begins
Phase 7A (LLM Application Engineering) as a phase transition built on Day53–Day61 — n8n may later call that
runtime as an external client but is not its prerequisite.

## 13. English Interview

Key Vocabulary:

responsibility boundary · durable acceptance bundle · honest 202 · idempotency_replayed · observe the same
task_id · exact-version Approval binding · delivery identity vs business fingerprint · OUTCOME_UNKNOWN ·
classified recovery · credential classification (rotate vs fix-config) · contain/revoke-rotate/preserve/
scope/classify/cancel-reconcile-compensate/verify/rollout · four-tier evidence taxonomy · NOT RUN.

Useful Expressions:

- "n8n orchestrates; FastAPI/PostgreSQL owns durable truth and authentication."
- "202 is honest only after the acceptance bundle commits."
- "An observation failure never changes the durable Task."
- "A v7 approval cannot authorize v8."
- "A timeout is unknown, not failed — I preserve identity and query authoritative evidence."
- "One integration run is not cumulative integration, and it is not production."

### Beginner

Question: What is the responsibility boundary between n8n and FastAPI/PostgreSQL?

Student answer (preserved): *"n8n handles workflow orchestration and data passing, while FastAPI and
PostgreSQL manage the persistent storage of factual data and authoritative authentication."* (Correction:
n8n orchestrates/maps/waits/branches/calls; FastAPI authenticates/authorizes and enforces transitions;
PostgreSQL stores durable truth — do not assign authentication to PostgreSQL.)

Strong Answer: "n8n is a permissioned orchestrator: it triggers, maps, waits, branches, and makes
authenticated calls, and its history is orchestration evidence. FastAPI is the security boundary that
authenticates and authorizes and enforces legal state transitions and idempotency. PostgreSQL holds the
durable business truth. n8n never owns the durable fact."

### Intermediate

Question: A long Task with Approval and Publication times out. How do retry and idempotency work?

Student answer (preserved): *"Retries should employ a combination of backoff and jitter, along with a
deadline… Idempotency relies on a constraint formed by the event ID and the idempotency key; this ensures
that a retry returns the result of the original request rather than generating a new one."* (Correction:
backoff/jitter only for safe observation or a classified retryable failure; a Publication timeout is
OUTCOME_UNKNOWN; separate the request fingerprint, the event fingerprint, and the Publication operation
idempotency identity.)

Strong Answer: "Backoff+jitter+deadline apply to safe observation and classified-retryable failures, not to
a Publication whose outcome is unknown. On a publish timeout I keep the operation and idempotency identity
and query the authoritative operation status plus a strictly-matching external receipt: succeeded → don't
republish; processing → observe; unknown → reconcile; rejected → terminal. The request fingerprint (dedupes
acceptance), the event fingerprint (dedupes callbacks), and the Publication operation idempotency identity
are three separate things."

### Senior

Question: A bad release duplicated approvals/publications, some Provider outcomes are unknown, and an
`Authorization` header leaked to logs. Walk through it.

Student answer (preserved): *"Deactivate/Unpublish; identify affected sets and classify them; remediate and
contain; verify facts and recovery history; validate regression coverage; controlled rollout."* (Correction:
contain first; stop replay + backend kill switch; immediately revoke/rotate the exposed credential; preserve
evidence; bound the affected set; explicitly cancel/reconcile/compensate; verify, regress, canary with stop
conditions.)

Strong Answer: "Contain first — deactivate the workflow, stop Error-Workflow replay, activate the backend
publication kill switch, and immediately revoke/rotate the leaked credential and verify the old one is
rejected before resuming any traffic. Preserve restricted evidence and scope the affected set with a padded
window and stable joins (workflow/release/execution → tenant/request/task/correlation → Attempt/Provider →
Approval/event → Artifact/version → Publication operation/idempotency/receipt), remembering the credential
exposure window is separate. Classify from durable evidence: publications that succeeded without approval
stay successes with a policy-violation record and compensation, never a retro-approval; provably-unstarted
Tasks get guarded durable cancellation; Provider-dispatched unknowns reconcile. Then verify every durable/
external fact, add regression coverage for the whole failure surface, and roll out synthetic → test tenant →
canary → allowlist → gradual, stopping on approval bypass, duplicate publication, event conflict, Provider
amplification, auth spikes, reconciliation growth, identity mismatch, audit gaps, or Secret exposure.
Rollback stops future harm; it does not undo committed Tasks, Provider cost, or external publications."

### Common Weak Answer

"The acceptance call and the tests both passed, so the Phase 6 capstone is integrated and production-ready;
if the publish times out I retry it, and I'll delete the bad rows to roll back."

Strong Answer: "Only the bounded acceptance slice reached INTEGRATION_RUNTIME; the pure tests are
EXECUTED_LOCAL_RUNTIME and the rest is NOT RUN — one run is not cumulative integration or production. A
publish timeout is unknown, so I query authoritative status on the same identity rather than blind-retrying,
and I never delete durable rows — I preserve, reconcile, and compensate while rollback only stops future
harm."

### Follow-up Questions

Beginner follow-up: Why is n8n's execution history not the authoritative business audit?
Strong Answer: "It records orchestration attempts, not committed business truth, and cannot enforce tenant
authorization or atomic transitions; the authoritative audit is FastAPI/PostgreSQL's append-only events."

Intermediate follow-up: Why must budget reservation be marked NOT RUN even though acceptance ran?
Strong Answer: "Budget reservation belongs in the complete production acceptance bundle but is absent from
the current Day59 implementation, so the acceptance slice that ran did not reserve budget — claiming it
would be inventing evidence."

Senior follow-up: Why is 'publication succeeded' separate from 'publication complied with policy'?
Strong Answer: "Success is a durable external fact; compliance is an authorization fact. A publication that
bypassed approval is genuinely SUCCEEDED and is preserved as such, with a separate policy-violation record
and compensation — post-incident acknowledgement can never be rewritten as pre-publication approval."

## 14. Mental Model Summary

```text
boundary   = n8n orchestrates | FastAPI authn/authz + transitions | PostgreSQL durable truth.
202        = honest only after the acceptance bundle commits; proof = new-connection DB read.
observe    = same task_id, bounded backoff + deadline; observation/n8n failure changes NO durable state.
approval   = exact tenant+actor+action+artifact/version+policy+lifetime; v7 != v8; new event/publication IDs.
delivery   = same event_id+same fingerprint = no-op; same event_id+different fingerprint = conflict.
recovery   = timeout = OUTCOME_UNKNOWN; preserve identity + query FastAPI; reissue only when proven safe.
credential = 401 stop+classify; rotate only when expired/revoked/compromised/leaked/invalid; else fix config.
incident   = contain -> revoke/rotate -> preserve -> scope -> classify -> cancel/reconcile/compensate -> verify -> regression -> rollout.
evidence   = acceptance slice = INTEGRATION_RUNTIME; pure tests + n8n inspection = EXECUTED_LOCAL_RUNTIME;
             rest = CONCEPTUAL_STATIC / NOT RUN. One run != cumulative integration != production.
phase      = Day70 closes Phase 6; Day71 = phase transition (foundations Day53-Day61), not an n8n dependency.
```

> Classroom-authorship note: at the student's explicit request (*`你帮我总结吧`*) the Tech Lead supplied the
> final Chinese Mental Model directly, per the live-teaching standard. It is taught material, not an
> independently authored student answer.

## 15. Today's Takeaway

The capstone is not "everything is green"; it is "everything is honestly tiered." The class ran the maximum
feasible real slice — a real n8n workflow accepting through real FastAPI on real PostgreSQL, with idempotent
redelivery proven by a new-connection read — and then refused to let that one boundary, or a passing test
suite, stand in for Polling, Callback, Approval, Publication, Worker, Provider, or the rollback exercise,
all of which stay NOT RUN. n8n orchestrates; FastAPI/PostgreSQL owns durable truth; recovery is classified,
not blind; and Day71 is a phase transition, not the next n8n layer.

## 16. Before Next Lesson Checklist

- [ ] I can state the n8n / FastAPI / PostgreSQL responsibility boundary without assigning auth to Postgres.
- [ ] I can explain the honest-202 acceptance bundle and prove it with a new-connection DB read.
- [ ] I can observe the same `task_id`, and know observation/n8n failure changes no durable state.
- [ ] I can bind an Approval to the exact version/action and separate v7→v8 stable/new/revalidate identities.
- [ ] I can classify duplicate delivery vs identity conflict, and run the acceptance/publication/credential
      recovery matrices.
- [ ] I can run the incident flow (contain → revoke/rotate → preserve → scope → classify →
      cancel/reconcile/compensate → verify → regression → controlled rollout).
- [ ] I can run `python3 -m pytest -q test_day70_capstone.py` (= 18 passed) and tier every Day70 activity.
- [ ] I understand the evidence limits: only the acceptance slice reached INTEGRATION_RUNTIME; the rest is
      NOT RUN; Day59–Day69 evidence is a prerequisite, not Day70 validation; Day70→Day71 is a phase
      transition.

---

Related: [Day70 capstone (project)](../../projects/n8n-workflows/DAY70_CAPSTONE.md)
· [n8n-workflows README](../../projects/n8n-workflows/README.md)
· [cheat sheet](../../cheat_sheets/fastapi.md) · [FastAPI interview](../../interview/fastapi.md) · [n8n interview](../../interview/n8n.md)
· Previous: [Day69 — Human Approval, Retry, Secrets, Audit and Error Workflows](day69-human-approval-retry-secrets-audit-and-error-workflows.md)
· Next: Day71 — LLM Application Engineering (Phase 7A; phase transition)
