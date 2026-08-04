# Day52 — Authorization, Tenant Isolation, Quotas and API Security (Design + Runbook)

Turns Day51's trusted identity into current, tenant-scoped, action-specific, cost-aware API authority. Day51 proved
WHO the caller is (a verified JWT `sub` -> `AuthenticatedIdentity(user_id)`); Day52 decides whether **this**
authenticated user, in **this** tenant, may perform **this** action on **this** resource, and whether the tenant may
consume this rate/budget. It binds identity, Membership, resource scope, rate limiting, quota reservation, and
idempotency into one admission boundary.

Runnable model: [`day52_authorization_tenant_quota_security.py`](day52_authorization_tenant_quota_security.py) +
[`test_day52_authorization_tenant_quota_security.py`](test_day52_authorization_tenant_quota_security.py).

---

## 0. Evidence label (read first)

```text
CONCEPTUAL DESIGN                         : COMPLETED (this runbook + lesson)
LOCAL PYTHON IN-MEMORY CONTROL-FLOW       : RUN (pytest, standard-library only)
REAL PostgreSQL (constraint/tx/isolation/UPDATE ... RETURNING / SQLAlchemy / migration / RLS) : NOT RUN
REAL Redis (distributed limiter atomics / TTL / failover / multi-process)                     : NOT RUN
REAL FastAPI / proxy / browser (Dependency / CORS / cookie / CSRF / Header / routes)          : NOT RUN
Provider / Worker / Outbox transport / integration / production                               : NOT RUN
```

Executed: `python3 -m pytest -q test_day52_authorization_tenant_quota_security.py` -> **16 passed**
(Python 3.10.12, pytest 7.4.3; module + tests are Python-standard-library only). The suite proves APPLICATION CONTROL
FLOW over an in-memory model; it does not prove PostgreSQL constraints/transactions/isolation, real Redis limiter
atomics, FastAPI/CORS/route behavior, or production. Day50 evidence is not inherited.

SECURITY: no real JWT, Provider key, password, raw prompt, Document content, database URL, or user data is used or
logged. Public errors never reveal that another tenant's resource exists.

---

## 1. Core mental model

```text
Authentication (Day51)   = a trusted user_id (verified `sub`)                     -> WHO
Authorization (Day52)    = active Membership + role action + resource scope       -> MAY THIS USER, IN THIS TENANT, DO THIS
Tenant isolation         = tenant_id (+ owner) predicates carried into every query -> WHICH DATA
Rate limit               = requests/second (shared, ephemeral, fail-closed)        -> HOW FAST
Quota / budget           = accumulated tokens/cost (PostgreSQL, durable, reserved) -> HOW MUCH SPEND
Idempotency              = one logical command accepted once (Day50), after authz   -> HOW MANY TIMES
```

A client-supplied `tenant_id` is a **selector**, never authority. Authority is the server-built
`AuthorizedTenantContext(user_id, tenant_id, permissions)`.

---

## 2. Authentication vs authorization

- Day51 JWT verification proves a trusted `user_id`; it does NOT grant tenant authority. The client can change a
  requested `tenant_id`, so it is a tenant selector, never authority (student: "因为请求中的tenant可以被修改。").
- JWT role claims cannot be the SOLE long-lived authority: a Membership removal or role downgrade would remain stale
  until token expiry. Check current active Membership + role per protected request, or under an explicit
  cache/revocation trade-off.

---

## 3. User / Tenant / Membership / role / action

- User = actor identity; Tenant = organization/team/customer isolation space.
- `tenant_memberships(user_id, tenant_id, role, status, ...)` is the many-to-many authority relation. Tenant-A admin
  authority never becomes Tenant-B admin authority.
- A role is a maintainable SET OF ACTIONS whose names match the business effect: `job.create`, `job.read_own`,
  `job.read_all`, `job.cancel`, `job.retry`. `POST /jobs/{id}/cancel` is `job.cancel` (NOT `job.create`); retry is
  `job.retry`.
- `authorize(identity, requested_tenant_id, action)`: find the active Membership -> resolve role permissions ->
  require the action. Every failure is a GENERIC `AuthorizationError` (anti-enumeration), never a message that reveals
  a resource, tenant, or role.

---

## 4. Tenant and resource isolation (IDOR/BOLA safe)

- Build `AuthorizedTenantContext(user_id, tenant_id, permissions)` ONLY after verified identity + active Membership +
  required action.
- Tenant-scoped Job lookup: `WHERE tenant_id = :authorized_tenant_id AND job_id = :job_id`.
- For `job.read_own`, ALSO require `created_by_user_id = :authenticated_user_id` — same-Tenant Membership alone cannot
  read a colleague's Job. Role selects the rule; `created_by_user_id == authenticated_user_id` proves ownership.
- A tenant-scoped miss returns a public **404** (no existence oracle). A missing action can yield a generic **403**
  without revealing a particular resource.
- FastAPI Dependencies centralize policy enforcement but do NOT constrain SQL automatically. Repositories must carry
  the authorized context and predicates. PostgreSQL RLS may be defense in depth, but its transaction-local tenant
  context must come from `AuthorizedTenantContext`, never Header/Body; pooled connections and bypass roles need review.

---

## 5. Safe API boundary

- Public errors do not reveal that another-Tenant Job exists, its tenant, or the required role.
- Protected audit evidence includes request/trace ID, verified actor, authorized tenant scope, requested resource,
  action, decision, timestamp, and policy version where applicable. NEVER log raw JWTs, Refresh Tokens, passwords,
  Provider keys, full prompts, or Document content.
- CORS is a browser-origin policy, not authentication or tenant authorization. The Day51 cookie + Origin + CSRF
  requirements are separate.

---

## 6. Rate limit, quota, concurrency (three different controls)

- Rate limit controls request speed; quota controls accumulated tokens/cost; concurrency limit controls in-flight /
  Worker pressure.
- Local process counters fail with multiple FastAPI instances: four instances each allowing 100 can admit ~400. Use
  shared low-latency atomic coordination (Redis) for rate limiting — but NOT as the durable budget truth.
- Keys: `tenant + action` (tenant capacity), `tenant + user + action` (member abuse), IP only as an auxiliary
  anti-abuse signal. Client `X-Forwarded-For` cannot replace JWT identity; trusted-proxy handling needs deliberate
  configuration.
- Limiter unavailable on paid `POST /jobs` is **fail-closed**: return dependency-unavailable 5xx/503, NOT 429 (429
  means a healthy limiter confirmed an exceeded limit).
- Fixed windows allow edge bursts; sliding windows smooth them at tracking cost; token bucket expresses bounded burst
  (capacity 20) + sustained refill (100/min) and fits Job creation.
- Normal 429 includes `Retry-After` + a stable error code. Clients obey it or use jittered exponential backoff and
  keep the SAME Idempotency-Key for the same command.

---

## 7. Durable token/cost quota + atomic Reservation + Job + Outbox

- Request count cannot protect Provider cost. Validate per-Job `max_tokens` and atomically reserve tenant budget.
- PostgreSQL is the durable concurrent arbiter (conceptual SQL):

```sql
UPDATE tenant_budgets
   SET reserved_tokens = reserved_tokens + :amount
 WHERE tenant_id = :authorized_tenant_id
   AND token_limit - used_tokens - reserved_tokens >= :amount
RETURNING tenant_id;
```

  One returned row -> reservation succeeds; zero rows -> no reservation and no new command acceptance.
- Reservation + Job + Outbox dispatch intent commit in ONE short transaction. Failure rolls all three back; otherwise
  ghost reservations or unfunded Jobs appear (`test_rollback_after_reservation_leaves_no_ghost_reservation_or_job`).
- Reconcile actual Provider usage: move actual cost to `used_tokens` and release the unused reservation. On unknown
  Provider timeout/usage, do NOT release the reservation — preserve evidence and hold `reconciliation_pending`.
  Day53/54/55 own the concrete Provider/streaming/Worker protocols.

```text
reserve_and_create(ctx, key, fingerprint, max_tokens): one guarded critical section
  same (tenant, key), same fingerprint   -> IDEMPOTENT_REPLAY: original Job, NO second reservation
  same (tenant, key), changed fingerprint-> FINGERPRINT_CONFLICT (409): no new facts
  new command, available >= amount       -> reserve + Job + Outbox in ONE tx (fail -> roll all back) -> CREATED
  new command, available <  amount       -> QUOTA_EXCEEDED (zero rows), issue nothing
reconcile(job_id, actual_tokens):
  actual known   -> SETTLED (used += actual, release the rest)
  actual unknown -> RECONCILIATION_PENDING (keep reservation, preserve evidence)
```

---

## 8. Idempotency ordering (admission boundary)

The `admit_job` order: **authorize job.create** -> **same-command recovery FIRST** (tenant-scoped, no new cost, no
rate-limit charge; a removed Membership already blocked it at authorization) -> **rate-limit NEW commands only**
(fail-closed if the limiter is down) -> **guarded reservation + Job + Outbox**.

- Same Tenant + same key + same fingerprint returns the original Job without a second reservation, Job, or Outbox.
- Same key with changed meaning is 409 and creates no new facts.
- A separate low read limit can protect recovery lookups.
- Idempotency is NOT an authz bypass: removed Membership blocks old-Key recovery/read
  (`test_idempotent_recovery_is_not_an_authz_bypass`).

Trade-off correction: "always rate-limit before idempotency recovery" is defensible for abuse control but harms a
lost-202 recovery. Recommended: current authz -> same-command tenant-scoped recovery with no new cost -> rate-limit
new commands; optionally rate-limit recovery reads separately.

---

## 9. Production failure / rollback exercise (erroneous cancel grant)

- Bad policy release: `member -> {job.read_own}` was incorrectly expanded to include `job.cancel`.
- Contain it by rolling back / disabling the erroneous centralized `job.cancel` grant (or fail closed for member
  cancellation), NOT by unnecessarily stopping safe Job creation.
- Policy rollback protects FUTURE traffic only. Classify historical cancel intents by actor, tenant, Job, policy
  version, time, Membership/role facts, state, and whether Worker/Provider work occurred.
- Preserve legitimate cancels and audit evidence. Never delete bad intents. A pending bad-policy intent may be
  invalidated ONLY through a guarded repair targeted by stable intent ID + policy version. Zero
  `UPDATE ... RETURNING` rows means facts changed: stop automatic repair and reconcile; never overwrite a later
  legitimate cancel or blindly re-run paid Provider work (`test_guarded_repair_of_bad_intent_stops_and_reconciles_on_fact_change`).

---

## 10. Validation / evidence matrix

| Claim | Status | How |
|---|---|---|
| Conceptual design | COMPLETED | this runbook + lesson |
| Membership/action authorization; client tenant is a selector | RUN (in-memory) | `authorize`; removal revokes; generic 403 |
| Tenant + owner scoped reads; cross-tenant 404 (no oracle) | RUN (in-memory) | `JobRepository.read_job` predicates |
| Guarded quota reservation; concurrency single winner | RUN (in-memory) | lock-modeled `UPDATE ... WHERE available >= amt RETURNING` |
| Atomic Reservation + Job + Outbox; rollback | RUN (in-memory) | injected post-reserve failure leaves no facts |
| Actual-usage reconcile; unknown-cost retention | RUN (in-memory) | `reconcile` SETTLED vs RECONCILIATION_PENDING |
| Fail-closed limiter outage (503, not 429); healthy 429 | RUN (in-memory) | `LimiterUnavailable`; token-bucket exhaustion |
| Idempotent recovery, no second reservation; 409; not an authz bypass | RUN (in-memory) | `admit_job` ordering; removed Membership blocks recovery |
| Guarded cancel-policy repair; zero rows -> reconcile | RUN (in-memory) | `repair_bad_intent`; retained audit |
| Real PostgreSQL constraint/tx/isolation/`RETURNING`/RLS | NOT RUN | needs a server + async driver + Day48-safe additive migration |
| Real Redis distributed limiter atomics/TTL/failover | NOT RUN | needs a real shared coordinator |
| Real FastAPI/proxy/browser (Dependency/CORS/cookie/CSRF/routes) | NOT RUN | HTTP-layer runtime |
| Provider / Worker / integration / production | NOT RUN | Day53/54/55 own the real protocols |

`In-memory control-flow tests do not prove PostgreSQL constraints/transactions/isolation, real Redis limiter atomics,
FastAPI/CORS/route behavior, real Provider/Worker delivery, integration, or production.`

---

## 11. Schema honesty

New facts MODELED in-memory here: `tenant_memberships(user_id, tenant_id, role, status)`, `tenant_budgets(tenant_id,
token_limit, used_tokens, reserved_tokens)`, per-Job `max_tokens`, a cancel-intent audit ledger with `policy_version`,
and (optionally) PostgreSQL RLS. A real deployment adds these via a **Day48-safe FORWARD additive migration** (new
tables + indexes / a guarded unique via a branch revision) — NOT implemented here, and no published Alembic revision
is rewritten. The Day50 Job + Outbox commitment is reused; the quota reservation is funded in that same transaction.

---

## 12. Boundaries preserved (not implemented here)

Authentication establishes a trusted `user_id` (Day51). Day52 authority is the server-built
`AuthorizedTenantContext`; a client `tenant_id` is never authority. Day53 puts the real OpenAI-compatible Provider
behind this boundary; Day54 uses the same authorized tenant/resource boundary for streaming reads + durable
cancellation (a disconnect is neither authorization nor cancellation); Day55+ retains tenant, budget, idempotency, and
audit invariants. No exactly-once is claimed across PostgreSQL + Redis + broker + Worker + Provider.
