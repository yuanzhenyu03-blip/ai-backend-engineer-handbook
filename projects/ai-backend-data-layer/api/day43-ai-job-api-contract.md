# AI Job API Contract and FastAPI Request Lifecycle (Day43)

The Phase 4 opening artifact for the AI Backend Data Layer. It exposes the **Day42 durable data-ownership and
failure contract** through a precise multi-tenant AI Job HTTP API and FastAPI request/response lifecycle — as a
**contract**, not a running application. PostgreSQL stays the durable business authority; the HTTP response is a
promise about **committed** business state.

> **Validation status of this whole document.** Everything below is **CONCEPTUAL / STATICALLY REVIEWED**
> only. **FastAPI runtime: NOT RUN. PostgreSQL runtime: NOT RUN. Relay/Worker runtime: NOT RUN. Redis/Object
> Storage/Provider runtime: NOT RUN. Integration and production validation: NOT RUN.** No FastAPI app,
> endpoint, route, PostgreSQL query/commit, Relay, Worker, Provider call, Object Storage access, or migration
> was executed or measured. Routes, status codes, and payload shapes are **static contract examples**. Pydantic
> v2 models (Day44), dependency injection / lifespan / provider adapters (Day45), SQLAlchemy/Alembic (Day46-48),
> the durable cooperative cancellation protocol (Day54), and Celery workers (Day55) are **future** boundaries
> and are **not** implemented here. Contains **no secrets, real connection strings, or client data**.

Related: [Day43 lesson](../../../docs/fastapi/day43-ai-backend-product-contract-and-fastapi-request-lifecycle.md) ·
[Day42 capstone design](../capstone-backend-data-design.md) ·
[project README](../README.md)

---

## 1. The acceptance boundary: commit before `202`

```text
request
 -> FastAPI route match
 -> validate input / Upload Session
 -> create or obtain Job identity
 -> ONE PostgreSQL transaction:
        Job
      + tenant-scoped (tenant_id, idempotency_key) uniqueness
      + Outbox dispatch intent
    COMMIT
 -> return 202 + job_id + a stable status_url
```

Return `202` **only after COMMIT**. "Attempt to persist" is insufficient — a crash before commit must not have
returned `202`. `202 Accepted` means a **durable asynchronous commitment exists**, not that Worker/Provider work
finished. The response is a promise about committed state.

---

## 2. Route / method / error / status matrix

| Situation | Status | Body / effect | Why |
| --- | --- | --- | --- |
| Job + Outbox committed | `202 Accepted` | `job_id` + stable `status_url` | a durable async commitment exists (not completion) |
| Resource created synchronously | `201 Created` | the created resource (NOT a redirect) | `201` is creation, not `3xx` redirect |
| `GET` a found Job | `200 OK` | current business status (`queued`/`running`/…) in the body | a found resource is `200`; `running` is its business state |
| Missing/invalid input, unusable/expired/unauthorized upload | `4xx` | no Job, no Outbox | a client-contract failure |
| Same tenant + same idempotency key + **different** logical request | `409 Conflict` | explicit conflict | never misrepresent an old Job as new intent |
| Dependency cannot verify or PostgreSQL lookup/commit fails | `5xx` | error | never lie with `404` or `202` about a dependency outage |
| Expensive `POST /jobs` without `Idempotency-Key` | reject (`4xx`) | no Job | do not allow unbounded duplicate acceptance |
| No matching method+path | `404` | — | the router found no route |
| Path pattern exists but method unsupported | `405` | — | route path exists, method does not |

```text
Routing resolves method+path BEFORE the handler or the database runs. Database/endpoint validation cannot
repair a routing mismatch because the handler has not run. Declare STATIC routes before conflicting DYNAMIC
routes: register /jobs/health before /jobs/{job_id}, or prefer a separate global /health.
```

---

## 3. Idempotency decision table (lost-response safe retries)

```text
same tenant + same stable idempotency key + same logical input
  -> atomically find-or-return the ORIGINAL Job
  -> same job_id + same status_url
  -> NO second Job and NO second Outbox intent
```

| Case | Outcome |
| --- | --- |
| Retry after a lost `202` (key K, same input) | return the original Job/status_url; no duplicate Job/Outbox |
| Same key K, **different** `upload_session_id` or task parameters | `409 Conflict` — do not return the old Job as if it changed |
| Expensive `POST /jobs` with **no** `Idempotency-Key` | reject; unbounded duplicate acceptance is not allowed |
| Concurrent retries of key K | database uniqueness + atomic create-or-return converge to one Job |

```text
Do NOT use SELECT-then-INSERT as the correctness mechanism (it races). The (tenant_id, idempotency_key)
UNIQUE constraint + an atomic create-or-return is the authority. Bind the key to REQUEST MEANING.
API idempotency (no duplicate Job acceptance) is SEPARATE from Provider idempotency (no duplicate model effect).
```

---

## 4. Tenant isolation at the read boundary

```text
GET /jobs/{job_id} reads current COMMITTED PostgreSQL truth (200 for a found Job, even if queued/running).

safe lookup:
  WHERE tenant_id = trusted_authenticated_tenant
    AND job_id = :path_job_id
```

A UUID is **not** authorization. Return `404` when no Job matches **both** tenant and Job ID — **including a
cross-tenant request** — so the API is not an existence oracle (a cross-tenant `job_id` must not reveal that the
Job exists for another tenant). Authentication mechanics are Day51; Day43 records the **trusted-tenant
requirement** as a contract.

```text
Public representation is ALLOWLISTED. Do NOT expose: lease tokens, fencing generations, raw Provider metadata,
raw Object Storage keys, Outbox internals, or unreviewed Attempt fields. (Day44 formalizes the response models.)
```

---

## 5. HTTP lifecycle vs durable Job lifecycle (Outbox/Worker boundary)

```text
HTTP lifecycle      = accept / read the Job and return an HTTP response (short)
background lifecycle = Relay -> Worker claim -> Provider -> guarded completion (may take minutes)

FastAPI must NOT wait for an eight-minute Provider call.
An in-process Background Task is NOT a reliable durable Worker: a deploy/crash can lose or interrupt it. It may
suit only short, disposable, local work. Durable long-running execution is a Day55 boundary.
```

Duplicate dispatch and the first guard:

```text
The API may return 202 after Job + Outbox commit even if the Relay has not published yet.
Relay scans published_at IS NULL; a crash AFTER publish but BEFORE the checkpoint -> expected at-least-once duplicate.

guarded queued -> running affects 1 row  -> winner may create Attempt/Event and call the Provider
guarded queued -> running affects 0 rows -> STOP; do not create Attempt/Event; do not call the Provider

The FIRST duplicate-delivery boundary is the guarded claim. Lease/fencing (Day41/Day42) protects stale
COMPLETION later; it is not the first gate.
```

---

## 6. Artifact truth and cancellation intent

```text
If Object Storage holds an Artifact but the PostgreSQL completion rolled back and the Job is running,
GET returns running. Artifact existence is NOT success (Day42).

Cancellation:
  use POST /jobs/{job_id}/cancel -- NOT a destructive DELETE (DELETE would erase durable facts + audit and
  make the Job unrecoverable and un-auditable).
  persist cancellation INTENT and preserve audit history.
  cancel requested != Job cancellation completed -- a running Provider call may still be in flight.
  a retry returns the current committed representation and must NOT duplicate the same logical
  cancellation-state event.
  (Day54 owns the durable/cooperative cancellation protocol and terminal-transition mechanics.)
```

---

## 7. Integrated failure / rollback exercise

```text
T1  Tenant A POST /jobs with key K and valid input
T2  Job + Outbox COMMIT; API crashes BEFORE returning 202
T3  Tenant A retries same key K and same input
T4  Relay publishes then crashes BEFORE the published_at checkpoint
T5  dispatch is delivered again
T6  Tenant B requests Tenant A's job_id
```

| Step | Expected outcome | Why |
| --- | --- | --- |
| T3 | original Job / status_url; **no** duplicate Job or Outbox | the durable `(tenant_id, K)` uniqueness + create-or-return converge |
| T5 | duplicate delivery is normal; **exactly one** guarded claim winner may call the Provider | the guarded `queued -> running` is the first gate |
| T6 | `404`; do **not** disclose Tenant A's Job existence | tenant predicate + Job ID; no existence oracle |

Senior rollback scenario (a bad release returned `202` **before** Job + Outbox commit):

```text
contain admissions / route traffic away from the faulty release; preserve logs/traces;
roll back the FAULTY API RELEASE (not "the database transaction"); identify affected requests by
release version, tenant, idempotency key, request/trace ID, returned Job ID, and commit evidence;
do NOT fabricate missing Jobs and do NOT blindly replay Provider work; use controlled/audited recovery;
add a regression test for the pre-COMMIT response window. Idempotent retries may correctly return 202 for the
SAME durable Job -- avoiding a second 202 is not the goal; avoiding a second durable Job is.
```

---

## Contract one-screen summary

```text
accept      -> commit Job + (tenant_id, idempotency_key) UNIQUE + Outbox in ONE tx, THEN 202 + job_id + status_url
status      -> 202 async accepted; 201 created (not redirect); GET found = 200 + business status
errors      -> 4xx client contract; 409 same-key-different-input; 5xx dependency outage (never fake 404/202)
idempotency -> DB uniqueness + atomic create-or-return; bind key to meaning; API key != Provider key
routing     -> method+path resolves before handler/DB; 404 no route, 405 wrong method; static before dynamic
tenant read -> GET reads committed truth; WHERE tenant + job_id; cross-tenant = 404 (no existence oracle); allowlist fields
lifecycle   -> HTTP short; durable work = Relay->Worker claim->Provider->guarded completion; no 8-min wait; BackgroundTask != durable Worker
duplicate   -> at-least-once normal; guarded queued->running (1 row winner / 0 rows stop) is the first gate
artifact    -> Artifact existence != success; cancel via POST cancel (intent, audited); cancel requested != completed
rollback    -> roll back the faulty API release; reconcile committed facts; idempotent 202 for the same Job is fine
```

---

## Future boundaries (not implemented here)

```text
Day44   Pydantic v2 typed input/output/error models formalize today's request/response/error decisions
Day45   dependency injection, lifespan, settings/secrets boundary, and a provider-adapter seam
Day46-48 SQLAlchemy mapping, transactional persistence, and Alembic evolution of the Day42 model (no ownership change)
Day51-52 authentication and tenant authorization mechanics (Day43 records only the trusted-tenant contract)
Day54   the durable, cooperative cancellation protocol and terminal-transition mechanics
Day55   long-running durable Workers on a supported Celery broker transport
```

---

## Validation and evidence classification

```text
CONCEPTUAL / DESIGN     : the acceptance boundary, the route/error/status matrix, the idempotency decision
                          table, tenant isolation, the HTTP-vs-durable lifecycle boundary, the Outbox/guarded-
                          claim gate, the cancellation-intent boundary, and the failure/rollback exercise are
                          contract decisions over the Day42 model.
STATICALLY REVIEWED     : route/status/SQL-shaped examples are read for shape and naming only.
FastAPI runtime          : NOT RUN -- no app, route, endpoint, or TestClient was executed.
PostgreSQL runtime        : NOT RUN -- no query, commit, uniqueness, or Outbox write was executed.
Relay/Worker runtime      : NOT RUN -- no Relay scan, guarded claim, or Worker execution.
Redis/Object Storage/Provider runtime : NOT RUN.
Integration / production  : NOT RUN -- not deployed; no production accessed; every route/status is a static example.
SECURITY                 : no secrets, credentials, connection strings, or client data; identifiers are placeholders.
SCOPE                    : Pydantic v2 (Day44), DI/lifespan/provider adapters (Day45), SQLAlchemy/Alembic
                          (Day46-48), durable cancellation (Day54), and Celery (Day55) are NOT implemented or
                          taught here.
```
