# Lesson 43 — AI Backend Product Contract and FastAPI Request Lifecycle

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day42 — Backend Data Design Capstone

Previous Lesson: [Day42 — Backend Data Design Capstone](../redis/day42-backend-data-design-capstone.md)

Next Lesson: Day44 — Pydantic v2 and Structured AI Input/Output Contracts (planned — Phase 4; see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day44 lesson file does not exist yet)

Phase: Phase 4 — Production AI API Engineering (Day43 opens Phase 4)

Engineering Artifact: The Day43 AI Job API contract (`projects/ai-backend-data-layer/api/day43-ai-job-api-contract.md`) — the commit-before-`202` acceptance boundary, the route/method/error/status matrix, the idempotency decision table, tenant isolation at the read boundary, the HTTP-vs-durable lifecycle boundary + Outbox/guarded-claim gate, the cancellation-intent boundary, and the integrated failure/rollback exercise, all labelled conceptual/static — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

FastAPI Cheat Sheet: [cheat_sheets/fastapi.md](../../cheat_sheets/fastapi.md)

FastAPI Interview: [interview/fastapi.md](../../interview/fastapi.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 100-130 minutes
Hands-on API-contract + lifecycle design: 100-130 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Explain why an HTTP response is a promise about committed business state, and place `202` exactly after the one PostgreSQL transaction that commits Job + `(tenant_id, idempotency_key)` uniqueness + Outbox intent.
2. Classify HTTP outcomes correctly: `202` async accepted, `201` created (not a redirect), `200` for a found Job with its business status, `4xx` client-contract failures, `409` for same-key-different-input, and `5xx` for dependency outages (never a fake `404`/`202`).
3. Design lost-response idempotency as database uniqueness + atomic create-or-return, binding the key to request meaning, rather than `SELECT`-then-`INSERT`.
4. Resolve routing before the handler runs, distinguishing `404` (no route) from `405` (wrong method) and ordering static routes before conflicting dynamic ones.
5. Design tenant-scoped Job reads (`tenant + job_id`) that return `404` cross-tenant, avoid an existence oracle, and allowlist public representation fields.
6. Separate the HTTP request lifecycle from the durable background lifecycle, and reject an in-process Background Task as a durable Worker.
7. Explain the Outbox/at-least-once boundary and why the guarded `queued -> running` (1 row winner / 0 rows stop) is the first duplicate-delivery gate.
8. Reject Artifact existence as completion proof, and design cancellation as a persisted, audited intent (`POST /cancel`, not destructive delete) that is not the same as completed cancellation.
9. Solve the integrated lost-response + duplicate-dispatch + cross-tenant-read failure sequence and the senior pre-`COMMIT` `202` rollback.
10. Answer Beginner/Intermediate/Senior English interview questions on the AI Job API contract.

---

# Why This Matters

Phase 3 built and integrated the durable data contract; Phase 4 opens by exposing it. Day43 is the seam where
the Day42 ownership model becomes a public HTTP API — and the central idea is small and easy to get wrong: an
HTTP response is a **promise about committed business state**, not a description of what the code tried to do.
Return `202` a millisecond too early — before the Job + Outbox transaction commits — and you have promised a
durable asynchronous Job that may not exist, so a client polls a `status_url` for a Job that was never
persisted.

The scenario is the same multi-tenant AI Research and Automation Platform: `POST /jobs` for an uploaded
document, a durable asynchronous acceptance, a readable status, later dispatch through Outbox/Relay/Worker, and
tenant isolation throughout. Every decision here is a **contract** decision with real consequences. Misclassify
an invalid upload as `5xx` and clients retry a request that will never succeed. Return an old Job for a
same-key-but-different-input retry and you silently execute the wrong task. Filter a read by `job_id` alone and
you turn a UUID into an existence oracle that leaks one tenant's Jobs to another. Wait inside the request for an
eight-minute Provider call and you tie a durable business commitment to a fragile HTTP connection.

So Day43 is about drawing the API boundary precisely over a durable model: when `202` is honest, how retries
converge without duplicating a Job, how routing and status codes tell the truth, and how the short HTTP
lifecycle hands off to the durable background lifecycle. This is contract and design work.

Nothing was executed — no FastAPI app or route, no PostgreSQL query or commit, no Relay/Worker/Provider/Object
Storage, no migration. Conceptual/static contract review is complete; **FastAPI, PostgreSQL, Relay/Worker,
Redis/Object Storage/Provider, integration, and production runtime are all NOT RUN.** Pydantic v2 (Day44),
DI/lifespan/provider adapters (Day45), SQLAlchemy/Alembic (Day46-48), the durable cancellation protocol (Day54),
and Celery (Day55) are future boundaries, not Day43 content.

---

# Roadmap Position

```text
Day42 durable data-ownership + failure contract (Phase 3 capstone)
Day43 expose it as the AI Job HTTP product contract + FastAPI request lifecycle   <-- you are here (Phase 4 opens)
Day44 Pydantic v2 typed input/output/error contracts
Day45 DI, lifespan, configuration, provider adapters
Day46-48 SQLAlchemy mapping / transactional persistence / Alembic evolution (no ownership change)
```

Knowledge continuity:

```text
Previous knowledge
  Day42 acceptance-at-202 (Job + (tenant_id, idempotency_key) uniqueness + Outbox intent), guarded transitions,
        Artifact-existence != success, tenant isolation, Outbox/Relay at-least-once delivery
        |
        v
Current lesson
  the HTTP product contract: commit-before-202, the status/error matrix, idempotent create-or-return, routing
  vs handler, tenant-scoped reads without an existence oracle, HTTP vs durable lifecycle, the guarded-claim gate,
  cancellation intent, and the failure/rollback exercise
        |
        v
Future production usage
  Day44 makes today's request/response/error decisions typed Pydantic models; Day45 wires DI/lifespan/provider
  adapters; Day46-48 persist/evolve the same model with SQLAlchemy/Alembic; Day54 durable cancellation; Day55
  durable long-running Workers
```

Mental models reused by name: the Day42 acceptance contract (durable-at-202), the guarded `queued -> running`
claim (Day34/Day42), the Outbox + at-least-once delivery (Day40/Day42), Artifact-existence-is-not-success and
tenant isolation (Day42).

---

# Lesson Map

```text
1. Commit before 202          -> the response is a promise about committed state
2. Status + error matrix      -> 202/201/200; 4xx/409/5xx; never a fake 404/202
3. Idempotent create-or-return -> DB uniqueness, not SELECT-then-INSERT; key bound to meaning
4. Routing before handler      -> 404 vs 405; static routes before dynamic
5. Tenant-scoped reads         -> tenant + job_id; cross-tenant 404; no existence oracle; allowlist fields
6. HTTP vs durable lifecycle    -> no 8-min wait; BackgroundTask != durable Worker
7. Outbox + guarded claim       -> at-least-once normal; 1 row winner / 0 rows stop is the first gate
8. Artifact + cancellation      -> existence != success; POST cancel intent, audited; requested != completed
9. Integrated failure/rollback  -> lost response + duplicate dispatch + cross-tenant read; pre-COMMIT 202 rollback
```

---

# Core Mental Model

```text
An HTTP response is a PROMISE about COMMITTED business state, not a report of what the code attempted.

ACCEPT   commit Job + (tenant_id, idempotency_key) UNIQUE + Outbox intent in ONE PostgreSQL tx, THEN return
         202 + job_id + a stable status_url. 202 = a durable async commitment exists, NOT that work finished.
STATUS   201 = created (not a redirect); GET a found Job = 200 + its business status (queued/running/...).
ERRORS   4xx = client-contract failure (no Job/Outbox); 409 = same key + different input; 5xx = dependency
         outage (never lie with 404 or 202). Expensive POST without Idempotency-Key -> reject.
IDEMPOTENT  same tenant + same key + same input -> atomically find-or-return the ORIGINAL Job (same job_id +
         status_url, no second Job/Outbox). DB uniqueness is the authority, not SELECT-then-INSERT.
ROUTING  method+path resolves BEFORE the handler/DB: 404 no route, 405 wrong method; static before dynamic.
READ     GET reads committed truth; WHERE tenant = trusted_tenant AND job_id = path; cross-tenant -> 404 (no
         existence oracle); allowlist public fields (no lease/fencing/Outbox/Object-Storage-key internals).
LIFECYCLE HTTP is short; durable work = Relay -> Worker claim -> Provider -> guarded completion. No 8-minute
         wait; an in-process BackgroundTask is NOT a durable Worker.
DUPLICATE at-least-once delivery is normal; the guarded queued->running (1 row winner / 0 rows STOP) is the
         FIRST gate; lease/fencing protects COMPLETION later.
ARTIFACT Artifact existence != success; cancel via POST /cancel (persisted, audited INTENT); cancel requested
         != cancellation completed.
```

---

# Main Concepts

## Concept 1: Commit before `202`

### Tech Lead Question

Where in the request flow do you return `202`, and is "attempt to persist Job + Outbox" enough?

### Student Thinking

The student put the response last, after validating the upload and generating the Job identity, and described
persisting Job + Outbox.

### Student Answer

> "响应应该放在最后，先 validate upload，再generate job_id以及attempt to persist Job + Outbox"

### Tech Lead Review

The ordering instinct is exactly right — validate, obtain Job identity, then persist — and the response goes
last. The one word to sharpen is "attempt": you must return `202` **only after the one PostgreSQL transaction
COMMITS** Job + `(tenant_id, idempotency_key)` uniqueness + the Outbox dispatch intent. "Attempted to persist"
is insufficient, because a crash between the attempt and the commit would have promised a durable Job that does
not exist. `202 Accepted` means a **durable asynchronous commitment exists**, not that Worker/Provider work
finished — the response is a promise about **committed** state.

### Engineering Thinking

The response boundary is the commit boundary. Anything you promise in the HTTP response must already be durable,
or the promise is a lie a client will act on (polling a `status_url` for a Job that was never saved).

## Concept 2: What the status codes actually mean

### Tech Lead Question

What does `202` mean, and is `201` a redirect?

### Student Thinking

The student was mapping the codes and initially treated `202`/`201` as involving a redirect.

### Student Answer

> "5xx，202是成功但是跳转，4xx找不到资源"

> "202表示已收到创建承诺，但是还没有结果。201表示跳转"

### Tech Lead Review

The core meaning of `202` is correct in the second answer — "a creation commitment received, no result yet." Two
corrections. First, **neither `202` nor `201` is a redirect**: `201 Created` means a resource was created
synchronously, and the redirect class is `3xx`. Second, `4xx` is **not** only "resource not found" — it is the
whole **client-contract-failure** class (missing/invalid input, an unusable/expired/unauthorized upload), for
which there is **no Job and no Outbox**. A successful `GET` of a found Job returns `200` with the current
business status in the body, even when that status is `queued` or `running`.

### Engineering Thinking

Status codes are part of the contract, not decoration. `202` = durable async commitment; `201` = synchronous
creation; `200` = a found resource; `4xx` = the client's request was wrong. Precise codes let clients behave
correctly without guessing.

## Concept 3: A database timeout is `5xx`, not `404`

### Tech Lead Question

The route matched and the handler ran, but the PostgreSQL lookup timed out. Is that a `404`?

### Student Thinking

The student reasoned that a matched route proves method+path are fine, so a database timeout is not "not found"
— it is the database failing to confirm.

### Student Answer

> "应该返回5XX，匹配了路由证明method+path都没问题，进入handler之后在数据库查询超时，则说明不是没有找到这个job_id，而是数据库无法确认"

### Tech Lead Review

Exactly right, and this is the subtle one. `404` is a **completed** lookup that found no allowed resource; a
**dependency that cannot complete** the verification or the PostgreSQL lookup/commit is a `5xx`. Returning `404`
(or `202`) on a database outage **lies** about the state of the world — it tells the client "this Job does not
exist" when the truth is "we could not determine anything." Never fake a `404`/`202` to hide a dependency
failure.

### Engineering Thinking

Distinguish "I looked and there is nothing" (`404`) from "I could not look" (`5xx`). Collapsing them corrupts
the client's retry logic and hides real outages.

## Concept 4: Idempotency and the lost response

### Tech Lead Question

A client retries `POST /jobs` with the same idempotency key after a lost response. What do you return, and what
if the input is different this time?

### Student Thinking

The student anchored on the tenant + stable idempotency key being a unique value in the database, and returned
the original Job.

### Student Answer

> "返回原job，因为租户与稳定幂等键已经绑定在数据是唯一值"

### Tech Lead Review

Correct for the **same** logical input: same tenant + same stable key + same input → **atomically find-or-return
the original Job**, with the same `job_id` and `status_url`, and **no** second Job and **no** second Outbox
intent. Two refinements. First, do **not** implement this as `SELECT`-then-`INSERT` — that races under
concurrent retries; the **`(tenant_id, idempotency_key)` uniqueness constraint + an atomic create-or-return** is
the correctness mechanism. Second, bind the key to **request meaning**: if the same key arrives with a
**different** `upload_session_id` or different task parameters, that is an explicit **`409 Conflict`** — never
return the old Job as though it represented the new intent. And API idempotency (no duplicate Job acceptance)
stays separate from Provider idempotency (no duplicate model effect).

### Engineering Thinking

Idempotency converges retries to one durable Job via a database invariant, not application check-then-act. The
key is a promise about *which request*; reusing it for a different request is a conflict, not a match.

## Concept 5: Routing resolves before the handler

### Tech Lead Question

Can database or endpoint validation fix an ambiguity between a static route like `/jobs/health` and a dynamic
route like `/jobs/{job_id}`? And what is `404` vs `405`?

### Student Thinking

The initial classroom model was that database or frontend validation could resolve a dynamic/static routing
ambiguity.

### Student Answer

Initial belief (corrected in class): DB/frontend validation could repair the routing mismatch.

### Tech Lead Review

That belief is the misconception to fix: the **router resolves method + path before the handler or the database
runs**, so neither database nor endpoint validation can repair a routing mismatch — the handler has not run.
Concretely: no matching method+path → `404`; a path pattern that exists but an unsupported method → `405`; a
route match → the handler may run. Because of this ordering, **static routes must be declared before conflicting
dynamic routes** — register `/jobs/health` before `/jobs/{job_id}` (or prefer a separate global `/health`),
otherwise `health` is captured as a `{job_id}`.

### Engineering Thinking

Routing is a phase that happens before your logic. Design the route table so the intended handler is reachable;
you cannot validate your way out of a request that never reached the handler.

## Concept 6: Tenant-scoped reads without an existence oracle

### Tech Lead Question

How do you read a Job's status, and can a tenant read another tenant's Job by its `job_id`?

### Student Thinking

The student chose `GET` because it is a query, and reasoned that a `job_id`-only lookup would pull another
tenant's Job.

### Student Answer

> "使用get，因为get是请求查询"

> (can a tenant read another tenant's Job by id?) "不能，因为会跨租户调取到其他租户的job"

### Tech Lead Review

Both right. `GET /jobs/{job_id}` reads the current **committed** PostgreSQL truth and returns `200` for a found
Job even if the business status is `queued` or `running`. The safe lookup filters by **both** the trusted
authenticated tenant **and** the Job ID (`WHERE tenant_id = trusted_authenticated_tenant AND job_id =
:path_job_id`). A **UUID is not authorization**: return `404` when no Job matches both — **including a
cross-tenant request** — so the API does not become an **existence oracle** that reveals another tenant's Job
exists. (Authentication mechanics are Day51; Day43 records the trusted-tenant requirement as a contract.) Also
**allowlist** the public representation: never expose lease tokens, fencing generations, raw Provider metadata,
raw Object Storage keys, Outbox internals, or unreviewed Attempt fields (Day44 formalizes the response models).

### Engineering Thinking

Isolation is enforced by the query predicate, and a cross-tenant miss must look identical to a genuine miss
(`404`), or the very act of answering leaks existence.

## Concept 7: The HTTP lifecycle is not the durable Job lifecycle

### Tech Lead Question

Should FastAPI wait for the eight-minute Provider call to finish before responding? And is an in-process
Background Task a durable Worker?

### Student Thinking

The student wanted the request to end rather than hold the HTTP connection, and reasoned that an in-process task
holds the process too long.

### Student Answer

> (wait for the long Provider call?) "结束，因为防止http连接被长时间占用"

> (is a Background Task a durable Worker?) "不能，因为会导致进程长时间被占用"

### Tech Lead Review

Correct. The **HTTP lifecycle** (accept/read the Job, return a response) is short and must **not** wait for an
eight-minute Provider call — that ties a durable business commitment to a fragile HTTP connection. The **durable
background lifecycle** is separate: Relay → Worker claim → Provider → guarded completion. And an in-process
FastAPI **Background Task is not a reliable durable Worker**: a deployment or crash can lose or interrupt it, so
it suits only short, disposable, local work. Durable long-running execution is a **Day55** boundary — not a
Day43 feature.

### Engineering Thinking

Return the promise quickly and let durable machinery do the slow work. Anything that must survive a deploy or
crash cannot live inside the request process.

## Concept 8: Outbox delivery and the guarded-claim gate

### Tech Lead Question

The Relay published, crashed before checkpointing, and the message is delivered twice. What stops the Provider
being called twice?

### Student Thinking

The student reasoned that acting on both deliveries would cause a duplicate call.

### Student Answer

> (act on both deliveries?) "不可以，因为会造成重复调用"

### Tech Lead Review

Right — and the precise gate matters. The API may return `202` after Job + Outbox commit even if the Relay has
not published yet; the Relay scans `published_at IS NULL` and a crash **after** publishing but **before** the
checkpoint produces an **expected at-least-once duplicate**. The **first** duplicate-delivery boundary is the
**guarded `queued -> running`**: if it affects **1 row**, that winner may create the Attempt/Event and call the
Provider; if it affects **0 rows**, the Worker **stops** — it does not create Attempt/Event and does not call
the Provider. Lease/fencing (Day41/Day42) protects a stale **completion** later; it is not the first gate.

### Engineering Thinking

Accept that transport duplicates, and put the correctness gate on a durable single-winner transition. "Zero rows
means stop" is the rule that prevents the expensive second Provider call.

## Concept 9: Artifact truth and cancellation intent

### Tech Lead Question

An Artifact is in Object Storage but the Job still reads `running`. What does `GET` return? And how do you
cancel — `DELETE`?

### Student Thinking

The student anchored completion on durable database facts, and rejected `DELETE` because it destroys durable
facts and auditability.

### Student Answer

> "只能依靠持久化数据库事实"

> "POST /jobs/{job_id}/cancel，因为DELETE会在数据库中删除持久化事实，之后无法恢复job，也无法进行审计"

### Tech Lead Review

Both correct. If Object Storage holds an Artifact but the PostgreSQL completion rolled back and the Job is
`running`, `GET` returns `running` — **Artifact existence is not success** (Day42), and only the durable database
fact decides completion. For cancellation, use **`POST /jobs/{job_id}/cancel`**, not destructive `DELETE`
semantics, exactly for the student's reason: a delete erases durable facts and audit history and makes the Job
unrecoverable and un-auditable. Persist the cancellation **intent** and preserve audit history — and note that
**`cancel requested != Job cancellation completed`**: a running Provider call may still be in flight. A retry
returns the current committed representation and must **not** duplicate the same logical cancellation-state
event. (The durable/cooperative cancellation protocol and terminal-transition mechanics are Day54.)

### Engineering Thinking

Completion and cancellation are durable, audited state transitions — not the presence of a file and not a
destructive delete. "Requested" is an intent recorded now; "completed" is a guarded transition that may come
later.

## Concept 10: Integrated failure and rollback

### Tech Lead Question

Walk the sequence: A `POST`s with key K (commit, then the API crashes before `202`); A retries; the Relay
publishes then crashes before checkpoint; the dispatch is delivered again; and B requests A's `job_id`. What
are the outcomes — and what do you roll back if a bad release returned `202` before commit?

### Student Thinking

This composes the whole lesson; the student's final synthesis captured the flow end to end.

### Student Answer

Final Chinese synthesis (student):

> POST creates a Job inside the tenant idempotency boundary and writes the Outbox intent, returns `202` and a
> query URL; retries recover the original Job; GET reads the persisted Job state; Relay scans `published_at IS
> NULL`; Worker claims and executes.

### Tech Lead Review

Correct end to end. The outcomes: **T3** (A retries key K with the same input) → the **original** Job/status_url,
with **no** duplicate Job or Outbox (the durable `(tenant_id, K)` uniqueness + create-or-return converge, even
though the first `202` was lost). **T5** (duplicate dispatch) → normal; **exactly one** guarded-claim winner may
call the Provider. **T6** (B requests A's `job_id`) → **`404`**; do not disclose A's Job existence. For the
senior rollback — a bad release returned `202` **before** Job + Outbox commit — you **contain** admissions/route
traffic, preserve logs/traces, and **roll back the faulty API release** (not "the database transaction");
identify affected requests by release version, tenant, idempotency key, request/trace ID, returned Job ID, and
commit evidence; do **not** fabricate missing Jobs or blindly replay Provider work; use controlled/audited
recovery; and add a regression test for the pre-`COMMIT` response window. Avoiding a second `202` is **not** the
goal — an idempotent retry may correctly return `202` for the **same** durable Job; avoiding a second **durable
Job** is.

### Engineering Thinking

At the boundary, correctness is a database invariant plus honest status codes: retries converge, duplicate
deliveries are gated, cross-tenant reads are hidden, and a broken release is rolled back and reconciled — never
patched by fabricating Jobs or replaying paid work.

---

# Common Misconceptions

`201` is a redirect

❌ "`201` (or `202`) is a redirect."
✅ `201 Created` means a resource was created synchronously; the redirect class is `3xx`. `202 Accepted` is a
durable async commitment.

Why beginners think this: "created/accepted" feels like "sent somewhere else."
How to remember: `3xx` redirects; `201`/`202` do not.

A running Job reads as `202`

❌ "`GET` a running Job returns `202`."
✅ A successful `GET` returns `200`; `running` is the resource's business status in the body. `202` is only the
acceptance response.

Why beginners think this: the Job is still "in progress."
How to remember: `202` is for acceptance; `200` is for a found resource.

`4xx` means only not-found; upload failure is `5xx`

❌ "`4xx` is just not-found, and an invalid upload is `5xx`."
✅ Invalid/unusable client input is `4xx` (the whole client-contract class); an unavailable dependency is `5xx`;
a completed lookup with no allowed resource is `404`.

Why beginners think this: they anchor `4xx` on `404` alone.
How to remember: `4xx` = client's fault; `5xx` = server/dependency's fault.

Same key, different input → old Job

❌ "Same idempotency key with different input should return the old Job."
✅ That is an explicit `409 Conflict`; never misrepresent an old Job as a new intent.

Why beginners think this: the key matched.
How to remember: the key promises *which request*; a different request is a conflict.

Validation can fix routing

❌ "Database or endpoint validation can resolve a static/dynamic route ambiguity."
✅ The router resolves method/path before the handler/DB. Declare static routes before conflicting dynamic ones.

Why beginners think this: validation feels all-powerful.
How to remember: you cannot validate a request that never reached the handler.

Tenant isolation is a path problem

❌ "A cross-tenant read is just a path mismatch."
✅ A missing route gives `404`; a tenant-predicate + Job-ID miss also returns `404` to conceal a cross-tenant
resource. A UUID is not authorization.

Why beginners think this: both end in `404`.
How to remember: filter by tenant + id; a cross-tenant hit must look like a miss.

Cancellation is instant

❌ "`POST /cancel` immediately sets the Job to `cancelled`."
✅ Cancellation intent is durable and audited; `cancel requested != cancellation completed` — a Provider call
may still be in flight. (Terminal mechanics are Day54.)

Why beginners think this: the request "cancels" the Job.
How to remember: requested now, completed later (guarded).

Duplicate delivery needs lease/fencing first

❌ "Duplicate dispatch is handled mainly by lease/fencing."
✅ The first gate is the guarded `queued -> running` (1 row winner / 0 rows stop). Lease/fencing protects a
stale completion later.

Why beginners think this: fencing is the memorable safety net.
How to remember: claim gate first; fencing at completion.

Rollback the database transaction

❌ "A bad release that returned `202` before commit is fixed by rolling back the database transaction."
✅ Roll back the faulty API release; committed facts need reconciliation; an idempotent retry may correctly
return `202` for the same durable Job (avoiding a second durable Job, not a second `202`).

Why beginners think this: the symptom looks like a data problem.
How to remember: roll back the code that lied, then reconcile.

---

# Engineering Trade-offs

## Commit-before-`202` vs respond-early

Committing before `202` guarantees the response is an honest promise, at the cost of the client waiting for one
short transaction. Responding early (before commit) is faster but can promise a Job that does not exist. Always
commit first; the transaction is short and the honesty is non-negotiable.

## Database uniqueness vs `SELECT`-then-`INSERT` idempotency

A `(tenant_id, idempotency_key)` unique constraint + atomic create-or-return converges concurrent retries
correctly; `SELECT`-then-`INSERT` is simpler to read but races (two retries both see "not found" and both
insert). Use the database invariant as the authority.

## Return old Job vs `409` on same-key-different-input

Returning the old Job is convenient but silently runs the wrong task when the input changed; `409 Conflict` is
stricter and forces the client to use a fresh key for a new request. For expensive AI Jobs, prefer the conflict.

## Synchronous work vs durable background lifecycle

Doing the Provider call in-request is simplest but ties a durable commitment to an HTTP connection and a single
process. The durable background lifecycle (Relay/Worker) survives deploys and crashes at the cost of more moving
parts. For anything long or expensive, use the durable path; reserve Background Tasks for short disposable work.

## Cross-tenant `404` vs a distinct `403`

Returning `404` for a cross-tenant Job hides existence (no oracle) but gives the client less information; a `403`
is more informative but confirms the resource exists. For tenant isolation of sensitive resources, prefer the
existence-hiding `404`.

## `POST /cancel` intent vs destructive `DELETE`

A `POST /cancel` records an audited intent and preserves recovery/audit; a `DELETE` is simpler but destroys
durable facts and history and cannot express "requested but a Provider call is still in flight." Use the
intent-based cancel for durable, auditable systems.

---

# Hands-on Exercises

Design/paper only over the one multi-tenant AI Job scenario. Nothing here was executed — no FastAPI app/route,
PostgreSQL query/commit, Relay/Worker, Provider, or Object Storage; every route/status/payload is a static
contract example.

### Exercise 1: Locate the exact commit-before-`202` boundary

Question: mark where in the request flow `202` may be returned.

Expected Output: after the one PostgreSQL transaction commits Job + `(tenant_id, idempotency_key)` uniqueness +
Outbox intent; not after "attempt to persist."

Explanation: the response is a promise about committed state.

Follow-up: what breaks if `202` returns just before COMMIT?

### Exercise 2: Classify the outcomes

Question: assign status codes to — invalid upload, same-key-different-input, missing route, wrong method, a
cross-tenant read, and a database-lookup timeout.

Expected Output: `4xx` (invalid upload) · `409` (same key, different input) · `404` (no route) · `405` (wrong
method) · `404` (cross-tenant, no oracle) · `5xx` (DB timeout, never `404`/`202`).

Explanation: client fault vs dependency outage vs completed-miss are distinct.

Follow-up: why is a DB timeout not a `404`?

### Exercise 3: Lost-response idempotency recovery

Question: design the retry path after a lost `202`.

Expected Output: same tenant + key + input → atomic find-or-return the original Job (same `job_id`/status_url),
no second Job/Outbox; enforced by the unique constraint + create-or-return, not `SELECT`-then-`INSERT`; a
different input with the same key → `409`.

Explanation: the database invariant converges retries.

Follow-up: why is `SELECT`-then-`INSERT` unsafe under concurrency?

### Exercise 4: Route ordering and `404` vs `405`

Question: `/jobs/health` and `/jobs/{job_id}` are both registered. What can go wrong, and what is `404` vs `405`?

Expected Output: register the static `/jobs/health` before the dynamic `/jobs/{job_id}` (or use a global
`/health`) or `health` is captured as a `{job_id}`; `404` = no matching method+path; `405` = path exists, method
unsupported.

Explanation: routing resolves before the handler; validation can't fix it.

Follow-up: why can't DB validation repair a routing mismatch?

### Exercise 5: Tenant-scoped read

Question: design the `GET /jobs/{job_id}` lookup and the cross-tenant response.

Expected Output: `WHERE tenant_id = trusted_authenticated_tenant AND job_id = :path_job_id`; `200` + business
status if found; `404` (not `403`) cross-tenant to avoid an existence oracle; allowlist public fields.

Explanation: a UUID is not authorization.

Follow-up: which internal fields must never appear in the public representation?

### Exercise 6: Reject Artifact existence as completion

Question: an Artifact exists but the Job reads `running`. What does `GET` return, and why?

Expected Output: `running`; Artifact existence is not success — only the committed database fact decides
completion.

Explanation: durable truth over stored bytes.

Follow-up: what must be reconciled before completing such a Job (Day42)?

### Exercise 7: Cancellation intent without destructive delete

Question: design cancellation.

Expected Output: `POST /jobs/{job_id}/cancel` persists an audited cancellation **intent**; not `DELETE`;
`cancel requested != completed` (a Provider call may be in flight); a retry returns current representation and
does not duplicate the cancellation-state event.

Explanation: durable, auditable state transitions, not deletion.

Follow-up: which lesson owns the terminal cancellation mechanics? (Day54.)

### Exercise 8: Integrated failure sequence (reusable artifact)

Question: run T1–T6 (lost `202` retry, duplicate dispatch, cross-tenant read) and the pre-`COMMIT` `202`
rollback.

Expected Output: T3 → original Job, no duplicate; T5 → one guarded-claim winner may call the Provider; T6 →
`404`. Rollback → roll back the faulty API release, reconcile committed facts, add a pre-`COMMIT`-window
regression test; an idempotent retry may return `202` for the same Job. Maps to the artifact's failure/rollback
section.

Explanation: database invariant + honest codes + guarded claim + release rollback.

Follow-up: why is "avoid a second `202`" the wrong goal?

---

# Relevant Framework Connections

## FastAPI

FastAPI provides the request lifecycle this lesson draws the contract on: route matching (method+path before the
handler), the endpoint as the HTTP contract boundary, the short request lifecycle separate from long-running
work, and static-before-dynamic route ordering. Watch that `202` is returned only after the durable commit, that
routing ambiguity is fixed at declaration time, and that no long Provider call or durable Worker lives inside a
request or a Background Task.

## PostgreSQL

PostgreSQL is the durable authority behind every HTTP promise: the Job + Outbox + `(tenant_id, idempotency_key)`
uniqueness commit boundary, tenant-scoped reads, and the guarded `queued -> running` claim. Watch that the commit
precedes the public promise and that reads filter by tenant + Job ID.

## Redis / Relay / Worker

Redis transport is losable; the Relay recovers dispatch from the Outbox (`published_at IS NULL`) and delivers
at-least-once. Watch that duplicate delivery is expected and gated by the guarded claim (1 row / 0 rows), not
treated as an error and not gated first by lease/fencing.

## Object Storage

Object Storage holds result bytes; those bytes do not prove successful Job completion. Watch that `GET` reflects
the committed database status, not the presence of an Artifact.

---

# AI Backend Connections

## Expensive Provider calls make idempotency mandatory

Because a Provider call is expensive and side-effectful, client idempotency is not optional: a lost-response
retry must converge to the same durable Job (API idempotency), and the guarded claim ensures only one winner
ever calls the Provider — so a duplicate dispatch never doubles the model bill.

## HTTP disconnect must not erase a commitment

An HTTP client disconnect or restart must not erase a persisted Job commitment: the `202` promise is durable in
PostgreSQL, and the durable background lifecycle (not the request) carries the work, so a dropped connection
loses nothing.

## Tenant isolation prevents document/result leakage

Tenant-scoped reads and existence-hiding `404`s keep one tenant's uploaded documents, Job status, and generated
results from leaking to another — a UUID is never authorization.

## Cancellation is durable because AI work outlives the request

Because external AI work can outlive the HTTP request, cancellation is a durable, audited intent rather than an
instant delete: `cancel requested` is recorded now, a possibly in-flight Provider call is acknowledged, and the
terminal transition (Day54) is guarded and auditable.

---
# English Interview

## Key Vocabulary

request/response lifecycle, `202 Accepted`, `201 Created`, `200 OK`, `4xx`/`409`/`5xx`, commit boundary,
idempotency key, create-or-return, unique constraint, route matching, `404` vs `405`, static vs dynamic route,
tenant isolation, existence oracle, allowlisted representation, Outbox, at-least-once, guarded claim, Background
Task vs durable Worker, cancellation intent.

## Useful Expressions

"An HTTP response is a promise about committed state." · "Return `202` only after the commit." · "Same key, same
input returns the same Job; different input is a `409`." · "A UUID is not authorization." · "The guarded claim is
the first duplicate gate."

## Beginner Question — What does `202 Accepted` mean for `POST /jobs`, and when may the API return it?

Strong answer:

> "`202 Accepted` means the API has durably accepted an asynchronous Job — a commitment exists — but the work is
> not finished. The API may return it only after one PostgreSQL transaction commits the Job, the tenant-scoped
> idempotency uniqueness, and the Outbox dispatch intent. Before that commit there is no durable Job, so
> returning `202` would be a promise the system cannot keep. The response includes the `job_id` and a stable
> status URL the client can poll."

## Intermediate Question — A client retries `POST /jobs` with the same idempotency key after a lost response. What do you return, and how do you avoid duplicates?

Strong answer:

> "If the tenant, the stable key, and the logical input are the same, I atomically find-or-return the original
> Job — same `job_id` and status URL, with no second Job and no second Outbox intent. I rely on the
> `(tenant_id, idempotency_key)` unique constraint plus an atomic create-or-return rather than
> `SELECT`-then-`INSERT`, because concurrent retries would otherwise both insert. If the same key arrives with a
> different `upload_session_id` or different parameters, that is a `409 Conflict` — I never return the old Job as
> if it were the new request. API idempotency is separate from Provider idempotency."

## Senior Question — Walk through a lost response, a duplicate dispatch, and a cross-tenant read; then a release that returned `202` before commit.

Strong answer:

> "After a lost `202`, the retry with the same key and input returns the original Job via the durable uniqueness
> constraint — no duplicate Job or Outbox. A duplicate dispatch is normal at-least-once behaviour: the guarded
> `queued -> running` is the first gate, so exactly one winner (one row) may create the Attempt and call the
> Provider, and zero rows means stop — lease and fencing only protect a stale completion later. A cross-tenant
> `GET` returns `404`, filtered by tenant plus Job ID, so the API is not an existence oracle. For the bad release
> that returned `202` before Job + Outbox committed, I contain admissions and route traffic, preserve logs and
> traces, and roll back the faulty API release — not 'the database transaction'. I identify affected requests by
> release version, tenant, idempotency key, request/trace ID, returned Job ID, and commit evidence; I don't
> fabricate missing Jobs or blindly replay Provider work; and I add a regression test for the pre-`COMMIT`
> response window. An idempotent retry may correctly return `202` for the same durable Job — avoiding a second
> durable Job is the goal, not avoiding a second `202`. All of this is conceptual: FastAPI, PostgreSQL, and the
> Relay/Worker runtime were NOT RUN."

## Common Weak Answer

"`POST` returns `202` right away, and if the client retries, just make a new Job; if another tenant asks for the
id, return `403` so they know it's not theirs."

## Strong Answer

"`202` comes only after the durable commit; a same-key-same-input retry returns the original Job through the
unique constraint, not a new one; and a cross-tenant read returns `404`, not `403`, so the API never confirms
another tenant's Job exists. Duplicate dispatch is gated by the guarded claim, Artifact existence is not
completion, and cancellation is a durable audited intent — not an instant delete."

---

# Mental Model Summary

```text
1.  An HTTP response is a PROMISE about COMMITTED business state, not a report of an attempt.
2.  Return 202 ONLY after one PostgreSQL tx commits Job + (tenant_id, idempotency_key) UNIQUE + Outbox intent.
3.  202 = durable async commitment (not completion); 201 = created (not a redirect); GET found = 200 + business status.
4.  4xx = client-contract failure (no Job/Outbox); 409 = same key + different input; 5xx = dependency outage.
5.  A DB timeout is 5xx, never a fake 404/202 (a completed miss is 404; an unfinished lookup is 5xx).
6.  Idempotency = (tenant_id, idempotency_key) UNIQUE + atomic create-or-return; NOT SELECT-then-INSERT; key bound to meaning.
7.  Expensive POST /jobs without an Idempotency-Key -> reject.
8.  Routing resolves method+path BEFORE the handler/DB: 404 no route, 405 wrong method; declare static before dynamic.
9.  GET reads committed truth WHERE tenant + job_id; cross-tenant -> 404 (no existence oracle); a UUID is not authorization.
10. Allowlist public fields: never expose lease/fencing/Provider-metadata/Object-Storage-key/Outbox/Attempt internals.
11. HTTP lifecycle is short; durable work = Relay -> Worker claim -> Provider -> guarded completion; no 8-min wait.
12. An in-process Background Task is NOT a durable Worker (a deploy/crash loses it); durable execution is Day55.
13. At-least-once duplicate delivery is normal; the guarded queued->running (1 row winner / 0 rows STOP) is the FIRST gate.
14. Artifact existence != success; cancel via POST /cancel (durable audited INTENT); cancel requested != completed.
15. Rollback a bad pre-COMMIT-202 release: roll back the CODE, reconcile committed facts; an idempotent 202 for the same Job is fine.

Starting model -> reasoning -> correction -> final model:
Initial: 201/202 involve a redirect; a running GET is 202; 4xx is only not-found and an invalid upload is 5xx;
same key + different input returns the old Job; DB/frontend validation fixes routing; a cross-tenant read is a
path problem; cancel is instant; duplicate delivery is handled by lease/fencing; a bad pre-202 release is fixed
by rolling back the database transaction.
Reasoning: the student consistently anchored truth in the committed database, protected the HTTP connection from
long work, and rejected destructive deletion for auditability.
Correction: 202 is after COMMIT and not a redirect; a found GET is 200; 4xx is the client-contract class and a
DB timeout is 5xx; same-key-different-input is 409; routing resolves before the handler (static before dynamic);
a cross-tenant miss is 404 (no oracle); cancellation is a durable audited intent, not completion; the guarded
claim is the first duplicate gate; and you roll back the faulty release, not "the transaction".
Final: the API is an honest promise over the Day42 durable contract -- 202 after commit, retries converging via
the unique constraint, precise status/error codes, routing resolved before logic, tenant-isolated reads with no
existence oracle, a short HTTP lifecycle handing off to durable background work, a guarded-claim duplicate gate,
and durable audited cancellation intent.
```

---

# Today's Takeaway

An HTTP response is a promise about committed business state. Return `202` only after the one PostgreSQL
transaction that commits Job + `(tenant_id, idempotency_key)` uniqueness + the Outbox intent, converge retries
through the unique constraint, tell the truth with status codes, resolve routing before the handler, isolate
tenant reads without an existence oracle, hand long work to the durable background lifecycle, gate duplicates at
the guarded claim, and treat Artifact existence and cancellation as durable audited facts — never as a file's
presence or an instant delete.

Most important mental model: the response boundary is the commit boundary. Most important production risk:
returning `202` before commit (a promised Job that does not exist) or leaking cross-tenant existence via a
`job_id`-only read. Most important trade-off: commit-before-`202` vs respond-early. Most important connection:
Day44 turns these request/response/error decisions into typed Pydantic v2 models. Most important interview
answer: `202` means a durable async commitment exists, only after commit.

Validation status: this lesson is CONCEPTUAL / STATIC CONTRACT REVIEW only. FastAPI runtime: NOT RUN.
PostgreSQL runtime: NOT RUN. Relay/Worker runtime: NOT RUN. Redis/Object Storage/Provider runtime: NOT RUN.
Integration and production validation: NOT RUN. Pydantic v2 (Day44), DI/lifespan/provider adapters (Day45),
SQLAlchemy/Alembic (Day46-48), the durable cancellation protocol (Day54), and Celery (Day55) are future
boundaries, not Day43 content.

---

# Before Next Lesson Checklist

```markdown
- [ ] Can I explain why an HTTP response is a promise about committed state, and place 202 after the commit?
- [ ] Can I classify 202 / 201 / 200 and 4xx / 409 / 5xx correctly, and say why a DB timeout is 5xx not 404?
- [ ] Can I design lost-response idempotency with a unique constraint + create-or-return (not SELECT-then-INSERT)?
- [ ] Can I explain why the same key with different input is a 409?
- [ ] Can I resolve routing before the handler and order static routes before dynamic (404 vs 405)?
- [ ] Can I design a tenant-scoped read that returns 404 cross-tenant and avoids an existence oracle?
- [ ] Can I list internal fields that must never appear in the public representation?
- [ ] Can I separate the HTTP lifecycle from the durable background lifecycle and reject a Background Task as a durable Worker?
- [ ] Can I explain the guarded-claim gate (1 row winner / 0 rows stop) as the first duplicate boundary?
- [ ] Can I reject Artifact existence as completion and design cancellation as a durable audited intent?
- [ ] Can I solve the T1-T6 sequence and the pre-COMMIT-202 release rollback?
- [ ] Can I answer the Beginner/Intermediate/Senior English questions on the AI Job API contract?
```

Preparation for Day44 (Pydantic v2 and Structured AI Input/Output Contracts): review this lesson's request/
response/error decisions and the `api/day43-ai-job-api-contract.md` artifact, then preview how those decisions
become typed Pydantic v2 request/response/error models with allowlisted fields. DI/lifespan/provider adapters
(Day45) and SQLAlchemy/Alembic (Day46-48) remain later boundaries.

---

Engineering Artifact: [projects/ai-backend-data-layer/api/day43-ai-job-api-contract.md](../../projects/ai-backend-data-layer/api/day43-ai-job-api-contract.md)
