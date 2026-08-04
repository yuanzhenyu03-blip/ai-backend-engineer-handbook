# Day52 — Authorization, Tenant Isolation, Quotas and API Security

## 1. Lesson Metadata

```text
Status: Completed
Template: LESSON_TEMPLATE_v2
Version: 1.0
Difficulty: Advanced
Estimated Time: 5-6 hours
Prerequisite: Day51 — Authentication, Password Security and JWT
Previous Lesson: Day51 — Authentication, Password Security and JWT
Next Lesson: Day53 — OpenAI SDK, Provider Boundaries and Structured Output
Engineering Artifact: projects/ai-backend-data-layer/api/day52-authorization-tenant-isolation-quotas-and-api-security-design.md
  + runnable day52_authorization_tenant_quota_security.py + test_day52_authorization_tenant_quota_security.py (in-memory control flow; 22 passed)
```

Main engineering artifact: a provider-neutral, standard-library-only in-memory model of the Day52 admission boundary,
plus the
[design/runbook](../../projects/ai-backend-data-layer/api/day52-authorization-tenant-isolation-quotas-and-api-security-design.md).

---

## 2. Learning Objectives

After this lesson you can:

- **Explain** why a trusted `user_id` (Day51) is not tenant authority, and why a client `tenant_id` is only a selector.
- **Model** User / Tenant / Membership / role / action, and match an action name to its business effect.
- **Design** an `AuthorizedTenantContext` built only after verified identity + active Membership + required action.
- **Implement** tenant- and owner-scoped resource reads that return a public 404 instead of an existence oracle.
- **Separate** rate limit, quota, and concurrency, and choose shared Redis coordination vs durable PostgreSQL cost.
- **Apply** a guarded atomic token reservation with `UPDATE ... RETURNING`, all-or-nothing rollback, and reconciliation.
- **Compare** fixed / sliding / token-bucket limiting and design 429 (`Retry-After`) vs fail-closed 503.
- **Diagnose** idempotent recovery that adds no cost and is not an authorization bypass.
- **Contain** an erroneous cancel-policy grant with rollback, classification, and a guarded repair.
- **Answer** beginner, intermediate, and senior interview questions in English.

---

## 3. Why This Matters

Day50 made AI Job acceptance idempotent and Day51 established a trusted caller identity — but a trusted `user_id`
alone is dangerous the moment there is more than one customer. Without Day52, any authenticated user could pass a
different `tenant_id` and read or cancel another company's Jobs (IDOR/BOLA); a member could be handed cancel authority
by a careless policy release; and — worst for an AI backend — a caller could burn unlimited Provider tokens because
request counting never bounds cost. This lesson turns identity into **current, tenant-scoped, action-specific,
cost-aware authority**: active Membership and role decide the action, tenant + owner predicates decide the data, a
shared limiter bounds speed, and a durable guarded reservation bounds spend — all funded in the same Job + Outbox
transaction so the system never accepts an unfunded Job or leaks a ghost reservation.

---

## 4. Roadmap Position

```text
Day50 idempotent Job acceptance + transactional Outbox (one logical Job accepted reliably)
        |
        v
Day51 authentication: trusted user identity (verified sub -> user_id)
        |
        v
Day52 authorization + tenant isolation + quotas (may THIS user, in THIS tenant, do THIS, and afford it?)   <-- you are here
        |
        v
Day53 real Provider behind this boundary -> Day54 streaming + durable cancellation -> Day55 Celery Workers
```

### Knowledge Continuity

```text
Previous Knowledge
  Day47 short UoW + guarded transition; Day50 DB-as-arbiter, atomic Job+Outbox, rollback, retain evidence;
  Day51 trusted user_id (a client tenant_id is not authority); Day39-Day41 Redis coordination
        |
        v
Current Lesson Concept
  Membership/role authorization; AuthorizedTenantContext; tenant+owner scoped reads (404 no-oracle);
  rate limit vs quota vs concurrency; guarded token reservation + atomic Reservation+Job+Outbox + reconcile;
  idempotent recovery after authz; guarded cancel-policy repair
        |
        v
Future Production Usage
  Day53 puts the real OpenAI-compatible Provider behind this authorized/quota boundary; Day54 authorizes streaming
  reads + durable cancellation; Day55 Workers consume the authorized context, audit, and quota state, never bypass them
```

Day52 does not implement the real Provider (Day53), streaming/cancellation (Day54), or Celery Workers (Day55). RLS,
real PostgreSQL, real Redis, and FastAPI/CORS wiring are described as contracts, not run here.

---

## 5. Lesson Map

```text
Authentication (trusted user_id) vs authorization (may do)  -> client tenant_id is a selector
  -> User/Tenant/Membership/role/action (action name == business effect; cancel != create)
  -> AuthorizedTenantContext (verified identity + active Membership + required action)
  -> tenant + owner scoped reads -> public 404 (no existence oracle); generic 403 for missing action
  -> safe API boundary (no oracle; audit metadata only; CORS != authz)
  -> rate limit (shared, fail-closed) vs quota (durable) vs concurrency
  -> guarded token reservation UPDATE...RETURNING -> atomic Reservation+Job+Outbox -> rollback -> reconcile
  -> idempotency AFTER authz: same command = no new cost; changed fingerprint = 409; not an authz bypass
  -> production: erroneous cancel grant -> rollback + classify + guarded repair (zero rows -> reconcile)
```

---

## 6. Core Mental Model

```text
Authentication (Day51) = a trusted user_id (verified `sub`)                          -> WHO
Authorization (Day52)  = active Membership + role action + resource scope            -> MAY THIS USER DO THIS HERE
Tenant isolation       = tenant_id (+ owner) predicates carried into every query     -> WHICH DATA
Rate limit             = requests/second (shared, ephemeral, fail-closed)            -> HOW FAST
Quota / budget         = accumulated tokens/cost (PostgreSQL, durable, reserved)     -> HOW MUCH SPEND
AuthorizedTenantContext = the server-built authority object; a client tenant_id is only a selector
```

---

## 7. Main Concepts

## Concept 1: Authentication vs authorization — a client tenant_id is a selector

### Tech Lead Question

Day51 gives you a verified `user_id`. If the request body also carries a `tenant_id`, can you trust it to scope the
Job?

### Student Thinking

The student saw that the JWT is verified and tamper-evident, but recognized the request body is separate from the
token.

### Student Answer

"因为请求中的tenant可以被修改。"

### Tech Lead Review

Correct. The JWT proves `user_id` only; the `tenant_id` in the body/header is unauthenticated input a client can set
to anything. It is a **requested tenant selector**, never authority. You must prove authority separately: an active
Membership of that user in that tenant. A JWT role claim also cannot be the sole long-lived authority, because a
Membership removal or role downgrade would stay stale until the token expires.

### Engineering Thinking

Authentication answers "who"; authorization answers "may this who do this, here". Collapsing them lets a valid token
act across tenants — the classic broken-object-level-authorization (BOLA) hole.

### Production Example

A support engineer's valid token plus a guessed `tenant_id` must never read another customer's Jobs.

### Framework Connection

FastAPI: a centralized Dependency turns identity + selector into an `AuthorizedTenantContext`; raw client tenant
authority is forbidden.

---

## Concept 2: User / Tenant / Membership / role / action

### Tech Lead Question

Does being a member of a tenant let a user perform every Job operation? And which tenant's role governs an action on a
tenant-A Job?

### Student Thinking

The student intuitively separated "being in the tenant" from "being allowed to do everything", and located authority
in the resource's tenant.

### Student Answer

"不是" (Membership alone does not permit every operation); "tenant b"'s role does not govern a tenant-A action — the
governing role is the one in **the resource's** tenant (refined to: authority comes from the Membership in the tenant
that owns the resource).

### Tech Lead Review

Right on both. `tenant_memberships(user_id, tenant_id, role, status)` is the many-to-many authority relation. A role
is a maintainable SET OF ACTIONS whose names match the business effect: `job.create`, `job.read_own`, `job.read_all`,
`job.cancel`, `job.retry`. Tenant-A admin authority never becomes Tenant-B authority, and each protected request
checks the current active Membership + role.

### Engineering Thinking

Naming actions by effect (not by endpoint shape) keeps least privilege maintainable and auditable; roles map to action
sets you can review and roll back.

### Production Example

`POST /jobs/{id}/cancel` must require `job.cancel`, not "any Job endpoint" — see Misconception 1.

### Framework Connection

PostgreSQL/SQLAlchemy: Membership facts + role->action policy resolved server-side.

---

## Concept 3: AuthorizedTenantContext and tenant/owner-scoped reads

### Tech Lead Question

After you confirm Membership and action, how do you actually stop a cross-tenant read, and what extra check does
`job.read_own` need?

### Student Thinking

The student reached for a scoped key and, after a nudge, separated "same tenant" from "mine".

### Student Answer

"tenant id unique tenant id jobid" (refined to an authorized `tenant_id + job_id` predicate); and "404" for a
cross-tenant tenant-scoped miss; the built context is
"AuthorizedTenantContext(user_id, tenant_id, permissions)".

### Tech Lead Review

Correct. Build `AuthorizedTenantContext` only after verified identity + active Membership + required action, then
scope every query: `WHERE tenant_id = :authorized_tenant_id AND job_id = :job_id`. For `job.read_own` also require
`created_by_user_id = :authenticated_user_id`; same-Tenant Membership alone cannot read a colleague's Job. A
tenant-scoped miss returns a **public 404** so you don't build an existence oracle; a missing action can be a generic
403. FastAPI Dependencies centralize policy but do not constrain SQL — the repository must carry the context.

### Engineering Thinking

Centralized policy + context-carrying repositories is the only combination that survives new endpoints; RLS can be
defense in depth but its tenant context must come from `AuthorizedTenantContext`, never a header.

### Production Example

A tenant-B admin requesting a tenant-A `job_id` gets a 404 identical to a truly missing Job.

### Framework Connection

`JobRepository.read_job(ctx, job_id)` applies tenant + owner predicates; optional PostgreSQL RLS as defense in depth.

---

## Concept 4: Safe API boundary (no existence oracle; audit; CORS)

### Tech Lead Question

If a user asks for another tenant's Job and you return 403 "forbidden for tenant X", what did you just leak?

### Student Answer

"暴露了资源。客户应该只能得到404。"

### Tech Lead Review

Exactly — a 403 that names the other tenant confirms the resource exists (an existence oracle). Return a public 404
for a tenant-scoped miss. Audit evidence is metadata only (request/trace ID, actor, authorized tenant scope,
resource, action, decision, timestamp, policy version) — never raw JWTs, Refresh Tokens, passwords, Provider keys,
full prompts, or Document content. CORS is a browser-origin policy, not authentication or tenant authorization; the
Day51 cookie + Origin + CSRF requirements are separate.

### Engineering Thinking

Error shape is part of your security surface; consistent 404s deny attackers a probing signal.

### Framework Connection

FastAPI: 404 vs 403 semantics; CORS configured separately from authz; structured audit logging.

---

## Concept 5: Rate limit vs quota vs concurrency; shared coordination; fail-closed

### Tech Lead Question

You run four FastAPI instances, each enforcing "100 requests/min" with a local counter. What is the real limit, and
where should the limiter live?

### Student Thinking

The student computed the multi-instance sum and reached for shared state.

### Student Answer

"实际会最多叠加到400。限流应该放在一个共有的..." (a shared store); and for a limiter outage on a paid path,
"fail-closed"; keys should include "单个成员最大使用量" (per-member limits); and "不能" to trusting a client IP header,
to CORS replacing authz, and to a JWT tenant role as sole authority.

### Tech Lead Review

All correct. Four local counters admit ~400 — use a shared low-latency atomic coordinator (Redis) for rate limiting,
but not as the durable budget truth. Keys can be `tenant+action`, `tenant+user+action`, and IP as an auxiliary signal
only (client `X-Forwarded-For` cannot replace JWT identity). A limiter outage on a paid `POST /jobs` is **fail-closed**
-> 503, NOT 429 (429 means a healthy limiter confirmed a breach). Rate limit (speed) ≠ quota (accumulated cost) ≠
concurrency (in-flight pressure).

### Engineering Thinking

Ephemeral speed control and durable cost truth are different systems with different correctness needs; conflating them
either double-counts money or throttles wrongly.

### Framework Connection

Redis / Day39-Day41: shared token bucket / sliding window; fail-closed paid admission policy.

---

## Concept 6: Durable token/cost quota — guarded reservation + atomic Reservation+Job+Outbox

### Tech Lead Question

Two requests for 5,000 tokens each arrive with only 8,000 remaining. How do you guarantee exactly one succeeds, and
what commits together?

### Student Thinking

The student reached for a database-arbitrated conditional update and a rollback on failure — the Day50 mental model.

### Student Answer

"由数据库的update returning"; and "回滚" after a reservation failure. For unknown Provider timeout: save the record,
secure evidence, and fix (refined below).

### Tech Lead Review

Correct core. Use a guarded `UPDATE tenant_budgets SET reserved_tokens = reserved_tokens + :amount WHERE token_limit -
used_tokens - reserved_tokens >= :amount RETURNING ...`. One returned row = reservation succeeded (not a credit limit
"obtained"); zero rows = insufficient budget, so no Job and no Outbox. The Reservation + Job + Outbox intent commit in
ONE transaction; a failure rolls all three back (no ghost reservation, no unfunded Job). Reconcile actual usage
safely: `actual <= reserved` settles the EXACT actual into `used_tokens` and releases the remainder; an unknown
Provider outcome holds `reconciliation_pending` (keep the reservation); a negative actual is rejected; and an
`actual > reserved` **overage** must NOT be `min()`-truncated or released as if settled — it keeps the reservation,
records the exact observed usage + reason, and returns `OVERAGE_RECONCILIATION_REQUIRED` for controlled settlement, so
a real cost fact is never lost. (A real system reserves the total billable cost, not only `max_tokens`; Day53's
Provider adapter owns the estimate/headroom and overage policy.)

### Engineering Thinking

The database is the only honest concurrent arbiter of money; a request counter cannot protect Provider spend.

### Production Example

Two concurrent 5,000-token jobs on an 8,000 budget: one `CREATED`, one `QUOTA_EXCEEDED`, 5,000 reserved, 3,000 left
(`test_two_concurrent_requests_only_one_reserves_when_budget_is_tight`).

### Framework Connection

PostgreSQL + Day47 UoW: guarded reservation, atomic Reservation+Job+Outbox, rollback, reconciliation.

---

## Concept 7: Idempotency ordering — recovery adds no cost and is not an authz bypass

### Tech Lead Question

A client retries a `POST /jobs` after a lost 202 with the same Idempotency-Key. What must happen — and what if their
Membership was removed in between?

### Student Answer

"返回原job" (same key + same command returns the original Job); "重试等待时间与指数退避" for 429 recovery. (In the
model the fingerprint proving "same command" is server-computed, not a value the client sends.)

### Tech Lead Review

Correct. After current identity + Membership + action authorization: same Tenant + same key + same fingerprint returns
the original Job with NO second reservation, Job, or Outbox; a changed behavior-relevant field is 409 with no new
facts. The fingerprint is COMPUTED SERVER-SIDE (`compute_request_fingerprint`: canonical JSON of the
behavior-relevant fields `max_tokens`/`document_id`/`task_type` -> SHA-256, never Python `hash()`, never a
client-asserted value), so a caller cannot reuse a key with a changed `max_tokens` and be handed the old Job. Crucially,
idempotency is not an authz bypass — a removed Membership blocks old-Key recovery (checked at authorization, before
recovery). Recommended order: authorize -> same-command tenant-scoped recovery (no new cost, no rate-limit charge) ->
rate-limit new commands -> reserve + create; optionally rate-limit recovery reads separately (see Misconception 4).

### Engineering Thinking

Recovery must be cheap and safe: cheap so a lost-202 retry isn't punished, safe so a stale key can't resurrect
authority.

### Framework Connection

Day50 idempotency reused; `admit_job` sequences authz -> recovery -> rate-limit -> reserve.

---

## Concept 8: Production exercise — erroneous cancel grant: contain, classify, repair

### Tech Lead Question

A policy release wrongly expanded `member` to include `job.cancel`. How do you contain it, and how do you clean up the
bad cancel intents already created?

### Student Thinking

The student first wanted to stop the affected traffic broadly, then narrowed to the specific bad grant and a guarded
repair.

### Student Answer

Containment: "停止新的job继续采用错误权限" (refined to stopping the erroneous cancellation grant, not safe Job
creation). Classification: "应该先区别哪些是正常具有取消权限的请求，以及哪些是超过权限的请求。" Final repair:
"停止该记录的自动修复并进入 reconciliation".

### Tech Lead Review

Correct trajectory. Contain by rolling back / disabling the erroneous centralized `job.cancel` grant (or fail closed
for member cancellation) — do not stop safe Job creation. Policy rollback protects FUTURE traffic only. Classify
historical cancel intents by actor, tenant, Job, policy version, time, Membership/role facts, state, and whether
Worker/Provider work occurred. Preserve legitimate cancels and audit evidence; never delete bad intents. Invalidate a
pending bad-policy intent only through a guarded repair targeted by stable intent ID + policy version. Zero
`UPDATE ... RETURNING` rows means facts changed: stop automatic repair and reconcile — never overwrite a later
legitimate cancel or blindly re-run paid Provider work.

### Engineering Thinking

A security incident cleanup is itself a guarded, audited state machine; blind bulk fixes destroy evidence and can
clobber legitimate actions.

### Framework Connection

Guarded repair (`repair_bad_intent`) with a retained audit ledger; zero rows -> reconcile.

---

## 8. Common Misconceptions

The four correction trajectories from class (initial model -> reasoning -> correction -> durable model):

1. **`POST /jobs/{id}/cancel` was first assigned `job.create`.** Reasonable because both are Job endpoints. Correct:
   name actions by business effect — cancel = `job.cancel`, retry = `job.retry`. Test: does the action name match the
   state change it causes?

2. **"role" was first offered as the extra own-only read check.** Correct: role selects the *rule*;
   `created_by_user_id == authenticated_user_id` proves *ownership*. Test: could a same-tenant colleague pass this
   check? If yes, it is not an ownership check.

3. **A zero-row guarded repair was first read as permission to continue cancellation.** Correct: zero rows mean
   stale/changed/unknown facts — stop automatic repair and reconcile. Test: did the guarded `RETURNING` return a row?
   No row = do not act.

4. **"Always rate-limit before idempotency recovery."** Defensible for abuse control, but it harms lost-202 recovery.
   Recommended: current authz -> same-command tenant-scoped recovery with no new cost -> rate-limit new commands;
   optionally rate-limit recovery reads separately. Test: does a legitimate retry of a lost 202 get punished?

> The final Chinese synthesis produced in class was **assistant-assisted** (the student explicitly asked
> "你帮我总结吧"); it is labeled as such and is not presented as student-authored prose.

---

## 9. Engineering Trade-offs

- **JWT role claims vs per-request Membership check.** Claims are fast and local but go stale on removal/downgrade
  until expiry; per-request checks are current but add a lookup. Chosen: current Membership per protected request, or
  an explicit cache + revocation trade-off.
- **Public 404 vs informative 403.** A specific 403 helps legitimate debugging but leaks existence; a uniform 404
  denies an oracle. Chosen: 404 for tenant-scoped misses, generic 403 for missing actions.
- **Shared Redis limiter vs local counters.** Local counters are simplest but multiply the real limit across
  instances; shared coordination is correct but adds a dependency (and must fail closed on a paid path). Chosen:
  shared limiter for speed, PostgreSQL for durable cost.
- **Fixed vs sliding vs token bucket.** Fixed windows allow edge bursts; sliding windows smooth them at tracking cost;
  token bucket gives bounded burst + sustained refill. Chosen: token bucket for Job creation.
- **Rate-limit-first vs recovery-first.** Rate-limit-first is stronger against abuse; recovery-first protects lost-202
  retries. Chosen: authz -> recovery -> rate-limit new commands, with optional separate recovery-read limits.
- **Release vs retain on unknown Provider cost.** Releasing frees budget but risks under-charging on a real spend;
  retaining holds budget but is honest. Chosen: retain + `reconciliation_pending` until the outcome is known.

---

## 10. Hands-on Exercises

1. Diagnose a client-controlled `tenant_id` and explain why it is a selector, not authority.
2. Model User/Tenant/Membership/action/resource-ownership and map roles to action sets.
3. Choose safe 404 vs action-level 403 for cross-tenant and missing-action cases.
4. Separate rate limit, quota, and concurrency for `POST /jobs`.
5. Choose shared Redis coordination vs PostgreSQL durable cost facts and justify each.
6. Design the guarded reservation, rollback, actual-usage reconciliation, and unknown-cost retention.
7. Compare fixed/sliding/token-bucket limiting and design 429 (`Retry-After`) vs fail-closed 503 recovery.
8. Design idempotent recovery with no double reservation and prove it is not an authz bypass.
9. Solve the erroneous cancellation grant: containment, classification, guarded repair, and reconciliation.
10. Complete Beginner, Intermediate, and Senior English interview answers.

Run the model:

```bash
cd projects/ai-backend-data-layer/api
python3 -m pytest -q test_day52_authorization_tenant_quota_security.py   # 22 passed
```

---

## 11. Relevant Framework Connections

- **FastAPI**: a centralized Dependency builds `AuthorizedTenantContext`; raw client tenant authority is forbidden;
  CORS is configured separately; 429 (healthy limiter breach) vs 503 (limiter outage) semantics.
- **PostgreSQL / SQLAlchemy / Day47 UoW**: Membership facts, tenant/owner predicates, guarded `UPDATE ... RETURNING`
  reservation, atomic Reservation + Job + Outbox, rollback, guarded repair, optional RLS as defense in depth.
- **Redis / Day39-Day41**: shared multi-instance rate coordination (token bucket / sliding window), ephemeral
  coordination distinct from durable cost truth, fail-closed paid admission.

---

## 12. AI Backend Connections

- Multi-tenant AI Job creation must prevent cross-Tenant Document/Job access and action misuse.
- Request count alone cannot control AI cost: per-Job `max_tokens`, tenant reservation, actual-usage reconciliation,
  and unknown-cost retention control Provider spend.
- The Day50 Job + Outbox remains the accepted durable commitment; quota is funded in that same transaction.
- Day53 (Provider), Day54 (streaming/cancellation), and Day55 (Workers) consume the Day52 authorized context,
  audit/correlation, and quota state rather than bypassing them.

---

## 13. English Interview

Key vocabulary: authentication, authorization, subject/user ID, tenant, tenant membership, role, permission/action,
AuthorizedTenantContext, least privilege, resource scope, ownership predicate, IDOR/BOLA, existence oracle, RLS, rate
limit, quota, concurrency limit, token bucket, sliding window, `Retry-After`, fail-open/fail-closed, reservation,
reconciliation, idempotency key, request fingerprint, guarded `UPDATE ... RETURNING`, audit evidence, rollback,
forward repair.

### Beginner — authentication vs authorization

Actual answer: "Authentication acts like an access control gate, while authorization defines the scope of resource
usage."

Strong answer: "Authentication verifies who is making the request, for example by validating a JWT and extracting the
user ID. Authorization then checks whether that user has the required permission in the current tenant to access or
modify a specific resource."

### Intermediate — a client sends a different tenant_id

Actual answer: "It should be rejected."

Strong answer: "The backend treats the client-supplied tenant ID only as a requested tenant selector, not as
authority. After JWT verification, it checks active Membership and the required action in tenant-A before loading the
Job. The Job query is also tenant-scoped, so the user cannot access a Job from another tenant."

### Senior — guarded token reservation under concurrency and unknown cost

Actual answer: "An update set is used to return the result: returning one row indicates that the credit limit has been
obtained, while returning zero rows indicates it has not. A rollback is performed if the operation fails. In the event
of a timeout, it is necessary to save the record, secure evidence, and perform a manual fix."

Correction: one row means a guarded budget reservation atomically succeeded, not that a credit limit was "obtained";
on timeout, preserve evidence and first use reconciliation/correlation — manual escalation is the fallback.

Strong answer: "I would use a guarded database update that reserves tokens only when the tenant has enough available
budget. Only one concurrent request can succeed; a zero-row result means the budget is no longer sufficient, so no Job
or Outbox event is created. The reservation, Job, and Outbox intent commit in one transaction, and a failure rolls
back all of them. If the Provider times out and actual usage is unknown, I keep the reservation and move the Job into a
reconciliation state. I preserve correlation and audit evidence, then settle or release the reservation only after the
Provider outcome is known."

---

## 14. Mental Model Summary

```text
Trusted user_id (Day51)  --authorize-->  AuthorizedTenantContext(user_id, tenant_id, permissions)
   client tenant_id = selector, never authority        (active Membership + role action; else generic 403)
        |
        v
Data scope: WHERE tenant_id = authorized AND (job.read_all OR created_by = user)   (miss -> public 404)
        |
        v
Speed: shared limiter (token bucket; fail-closed on paid path -> 503; healthy breach -> 429 + Retry-After)
        |
        v
Spend: guarded UPDATE ... RETURNING reservation + Job + Outbox in ONE tx  (rollback all; reconcile actual; hold unknown)
        |
        v
Idempotency AFTER authz: same command -> original Job, no new cost; changed fingerprint -> 409; removal blocks recovery
```

---

## 15. Today's Takeaway

Identity is not authority. Day52 converts a trusted `user_id` into an `AuthorizedTenantContext` — active Membership +
role action + tenant/owner scope — and funds every accepted Job with a guarded, durable token reservation committed in
the same Job + Outbox transaction. Speed is bounded by a shared, fail-closed limiter; spend is bounded by PostgreSQL;
recovery is cheap but never a bypass; and an erroneous grant is contained by rollback plus a guarded, audited repair.

---

## 16. Before Next Lesson Checklist

- [ ] I can explain why a client `tenant_id` is a selector, not authority.
- [ ] I can build an `AuthorizedTenantContext` and scope reads by tenant + owner (404 on a miss).
- [ ] I can separate rate limit, quota, and concurrency, and justify shared Redis vs durable PostgreSQL.
- [ ] I can write a guarded `UPDATE ... RETURNING` reservation and commit Reservation + Job + Outbox atomically.
- [ ] I can reconcile actual usage and retain the reservation on an unknown Provider outcome.
- [ ] I can order idempotent recovery so it adds no cost and is not an authz bypass.
- [ ] I can contain an erroneous cancel grant with rollback, classification, and a guarded repair.
- [ ] Next: Day53 puts the real OpenAI-compatible Provider behind this authorization/quota boundary.
