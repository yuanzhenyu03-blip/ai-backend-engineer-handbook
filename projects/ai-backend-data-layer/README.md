# Production AI Backend Data Layer

The evolving Phase 3 engineering artifact, reused by Phase 4 as the durable foundation the API is built on.
It turns the Day28 conceptual ownership rule — **PostgreSQL owns durable Job truth** — into a failure-aware
data layer (Day29-Day42) and, from Day43, the HTTP API contract that exposes it — one lesson at a time.

Current increment: **Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection** that turns the Day43–Day56 reliability POLICIES into REPEATABLE EVIDENCE. A deterministic verification harness (`day57_testing_harness.py`; standard-library control flow driving the REAL Day56 functions + Day53's real pydantic validator) provides a controllable Fake Provider (scripted outcomes, an independent call log that survives "Worker loss", `request_received`/`release_response` gates via `threading.Event`, execution-certainty evidence), a `FakeClock` + `DeterministicRandom` for reproducible backoff/jitter, an application-owned `ProviderAdapter`/`ProviderOutcome` (no SDK leakage; never writes Job state or cost), a strict `attempt_late_completion` contract, and an explicit three-tier `VALIDATION_MATRIX`. The scenarios prove: a bare-429 -> `PENDING_RECONCILIATION` with the call count still one and no new rate permit; a missing `provider_request_id` is not proof of no execution (Day55 dispatch marker forces RECONCILE); the Adapter delivers a typed outcome + execution certainty (DEFINITELY_NOT_ACCEPTED / MAY_HAVE_EXECUTED / UNKNOWN); a valid-JSON schema violation is a contract violation, not success; deterministic backoff with Retry-After as an earliest floor (no wake-all); a controlled timeout window without sleeps; late-result completion only on full identity + schema match (terminal CANCELLED rejects a matching result); limiter outage fails closed (DEFER, zero calls, execution-retry unchanged); deadline with/without evidence (EXPIRED+release vs PENDING_RECONCILIATION+held); admission 503 dominates 429; and a guarded, idempotent repair under concurrency (a unique `repair_id` -> exactly one Outbox intent; provider-evidence -> RECONCILE_ONLY). **The tests were executed** (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3 -> 21 passed; full api suite 463) proving EXECUTED LOCAL RUNTIME application state-machine / Adapter-contract / failure-injection control flow ONLY: **real PostgreSQL transaction/rollback/isolation, a real Celery broker + Worker-kill/redelivery, a real Redis limiter/circuit, and real Provider traffic are NOT RUN** (encoded in `VALIDATION_MATRIX`/`not_run_claims()`); a real `job_repair_history` table/migration is forward-additive DESIGN only. Day58 owns observability + the Phase 4 capstone. No secrets, raw prompts, or raw Provider payloads are used.
(See the Day50 note below for the prior increment.)

Prior increment (Day43): **the AI Job API contract** (Phase 4 opens) that exposes the Day42 durable
data-ownership/failure model as a precise multi-tenant AI Job HTTP API: the commit-before-`202` acceptance
boundary, the route/method/error/status matrix, the idempotency decision table (unique constraint + atomic
create-or-return), tenant isolation at the read boundary (cross-tenant `404`, no existence oracle, allowlisted
fields), the HTTP-vs-durable lifecycle boundary + the guarded-claim duplicate gate, the cancellation-intent
boundary, and the integrated failure/rollback exercise — contract and design only, nothing executed; an HTTP
response is a promise about committed state and PostgreSQL stays the durable authority.

Prior increment (Day42): **the Backend Data Design Capstone** that closes Phase 3 by integrating the durable
PostgreSQL truth (Day29-Day37) with the transient Redis coordination (Day38-Day41) and the Object Storage
artifact boundary into one failure-aware ownership/recovery/verification contract: the ownership/lifecycle map,
the acceptance contract (durable-at-202), dispatch and at-least-once duplicate handling, the short guarded
completion transaction and Artifact reconciliation, the failure/degraded matrix, the Upload Session
verification contract, tenant isolation + append-only audit + tombstoned retention, the disposable
`EXPLAIN ANALYZE` performance-evidence method, the fencing-generation Expand->Contract migration, and the
integrated recovery runbook — design and evidence only, nothing executed; PostgreSQL stays the single source of
durable truth and SQLAlchemy/Alembic remain Phase 4.

Prior increment (Day41): **a Redis coordination and production-safety design** that uses Redis for narrow,
bounded coordination/protection (atomic rate-limit admission and short leases; the fencing generation itself is
durable in PostgreSQL) while PostgreSQL stays the durable business authority: the atomic admission contract, the
algorithm decision table (fixed/first-write-TTL/sliding/token-bucket), the API idempotency boundary, the lease
safety model (token/expiry/renew/atomic compare-and-delete release + paused-owner timeline), the fencing model,
the PostgreSQL completion guard (extending Day34/Day37), the Redis loss/capacity matrix, the security matrix,
and the integrated failure runbook — design and evidence only, nothing executed; Redis is not promoted to
business truth and no exactly-once is claimed.

Prior increment (Day40): **a Redis messaging and queue semantics design** that uses Redis Lists, Pub/Sub, and
Streams by their delivery/failure semantics while PostgreSQL stays durable Job truth: the List/Pub-Sub/Streams
decision table, a small Stream payload contract, the event lifecycle and Consumer Group topology, the
PEL/ACK/Claim/redelivery lifecycle, the delivery-vs-durable-completion boundary, per-side-effect
idempotency/reconciliation, retry/quarantine/dead-letter, a safe trim/retention contract, and the integrated
failure/recovery matrix — design and evidence only, nothing executed; Redis is not claimed to give exactly-once
and no Celery replacement is built.

Lessons:
- Day29 (schema): [`docs/postgresql/day29-postgresql-foundations-and-durable-relational-state.md`](../../docs/postgresql/day29-postgresql-foundations-and-durable-relational-state.md)
- Day30 (operations): [`docs/postgresql/day30-sql-data-manipulation-and-query-fundamentals.md`](../../docs/postgresql/day30-sql-data-manipulation-and-query-fundamentals.md)
- Day31 (relational model): [`docs/postgresql/day31-relational-modeling-and-data-integrity.md`](../../docs/postgresql/day31-relational-modeling-and-data-integrity.md)
- Day32 (operational queries): [`docs/postgresql/day32-sql-joins-aggregation-and-operational-queries.md`](../../docs/postgresql/day32-sql-joins-aggregation-and-operational-queries.md)
- Day33 (transactions): [`docs/postgresql/day33-postgresql-transactions-and-atomic-state-changes.md`](../../docs/postgresql/day33-postgresql-transactions-and-atomic-state-changes.md)
- Day34 (concurrency): [`docs/postgresql/day34-concurrency-control-mvcc-and-worker-claims.md`](../../docs/postgresql/day34-concurrency-control-mvcc-and-worker-claims.md)
- Day35 (indexes): [`docs/postgresql/day35-postgresql-indexes-and-query-planning.md`](../../docs/postgresql/day35-postgresql-indexes-and-query-planning.md)
- Day36 (migrations): [`docs/postgresql/day36-schema-evolution-and-safe-migrations.md`](../../docs/postgresql/day36-schema-evolution-and-safe-migrations.md)
- Day37 (production reliability): [`docs/postgresql/day37-postgresql-production-reliability.md`](../../docs/postgresql/day37-postgresql-production-reliability.md)
- Day38 (Redis foundations): [`docs/redis/day38-redis-foundations-and-data-structures.md`](../../docs/redis/day38-redis-foundations-and-data-structures.md)
- Day39 (Redis cache consistency): [`docs/redis/day39-redis-cache-design-and-consistency.md`](../../docs/redis/day39-redis-cache-design-and-consistency.md)
- Day40 (Redis messaging): [`docs/redis/day40-redis-messaging-and-queue-semantics.md`](../../docs/redis/day40-redis-messaging-and-queue-semantics.md)
- Day41 (Redis coordination): [`docs/redis/day41-redis-coordination-and-production-safety.md`](../../docs/redis/day41-redis-coordination-and-production-safety.md)
- Day42 (capstone): [`docs/redis/day42-backend-data-design-capstone.md`](../../docs/redis/day42-backend-data-design-capstone.md)
- Day43 (API contract): [`docs/fastapi/day43-ai-backend-product-contract-and-fastapi-request-lifecycle.md`](../../docs/fastapi/day43-ai-backend-product-contract-and-fastapi-request-lifecycle.md)
- Day44 (Pydantic contracts): [`docs/fastapi/day44-pydantic-v2-and-structured-ai-input-output-contracts.md`](../../docs/fastapi/day44-pydantic-v2-and-structured-ai-input-output-contracts.md)
- Day45 (DI/lifespan/config/adapters): [`docs/fastapi/day45-dependency-injection-lifespan-configuration-and-ai-provider-adapters.md`](../../docs/fastapi/day45-dependency-injection-lifespan-configuration-and-ai-provider-adapters.md)
- Day46 (SQLAlchemy mapping): [`docs/fastapi/day46-sqlalchemy-mapping-for-the-day42-data-model.md`](../../docs/fastapi/day46-sqlalchemy-mapping-for-the-day42-data-model.md)
- Day47 (async sessions/tx/UoW): [`docs/fastapi/day47-async-sessions-transactions-repository-and-unit-of-work.md`](../../docs/fastapi/day47-async-sessions-transactions-repository-and-unit-of-work.md)
- Day48 (Alembic safe evolution): [`docs/fastapi/day48-alembic-and-safe-ai-backend-schema-evolution.md`](../../docs/fastapi/day48-alembic-and-safe-ai-backend-schema-evolution.md)
- Day49 (verified upload boundary): [`docs/fastapi/day49-upload-sessions-object-storage-and-artifact-verification.md`](../../docs/fastapi/day49-upload-sessions-object-storage-and-artifact-verification.md)
- Day50 (idempotent acceptance + outbox): [`docs/fastapi/day50-idempotent-ai-job-api-and-transactional-outbox-integration.md`](../../docs/fastapi/day50-idempotent-ai-job-api-and-transactional-outbox-integration.md)
- Day51 (authentication + JWT): [`docs/fastapi/day51-authentication-password-security-and-jwt.md`](../../docs/fastapi/day51-authentication-password-security-and-jwt.md)
- Day52 (authorization + tenant isolation + quotas): [`docs/fastapi/day52-authorization-tenant-isolation-quotas-and-api-security.md`](../../docs/fastapi/day52-authorization-tenant-isolation-quotas-and-api-security.md)
- Day53 (OpenAI SDK provider boundary + structured output): [`docs/fastapi/day53-openai-sdk-provider-boundaries-and-structured-output.md`](../../docs/fastapi/day53-openai-sdk-provider-boundaries-and-structured-output.md)
- Day54 (streaming, disconnects, timeouts, cancellation): [`docs/fastapi/day54-ai-streaming-client-disconnects-timeouts-and-cancellation.md`](../../docs/fastapi/day54-ai-streaming-client-disconnects-timeouts-and-cancellation.md)

---

## Structure (grows with real lessons only)

```text
projects/ai-backend-data-layer/
├── README.md
├── capstone-backend-data-design.md                    # Day42: Phase 3 capstone design (PostgreSQL + Redis + Object Storage; design + evidence, not executed)
├── api/
│   ├── day43-ai-job-api-contract.md                   # Day43: AI Job API contract over the Day42 model (contract + design, not executed)
│   ├── day44-pydantic-contracts-design.md             # Day44: Pydantic v2 API + AI output contracts (design)
│   ├── day44_pydantic_contracts.py                    # Day44: runnable Pydantic v2 models (real; tests pass)
│   ├── test_day44_pydantic_contracts.py               # Day44: pytest cases (executed: 24 passed)
│   ├── requirements.txt                                # Day44: pinned deps (pydantic==2.5.0, pytest==7.4.3)
│   ├── day45-di-lifespan-configuration-and-ai-provider-adapters-design.md  # Day45: composition/lifespan design
│   ├── day45_composition.py                           # Day45: runnable FastAPI composition (real; fake-Provider tests pass)
│   ├── test_day45_composition.py                      # Day45: pytest cases (executed: 20 passed, fake no-network Provider)
│   ├── requirements-day45.txt                          # Day45: pinned deps (pydantic, pytest, fastapi, httpx)
│   ├── day46-sqlalchemy-mapping-for-the-day42-data-model-design.md  # Day46: SQLAlchemy 2.0 mapping design
│   ├── day46_orm_mapping.py                            # Day46: faithful SQLAlchemy 2.0 mapping of the Day42 app schema
│   ├── test_day46_orm_mapping.py                       # Day46: static metadata-contract tests (executed: 20 passed)
│   ├── requirements-day46.txt                          # Day46: pinned deps (sqlalchemy==2.0.29, pytest==7.4.3)
│   ├── day47-async-persistence-boundary-design.md      # Day47: async session/UoW design
│   ├── day47_async_uow.py                              # Day47: async Engine/session-factory + repos + UnitOfWork
│   ├── test_day47_async_uow.py                         # Day47: fake-session control-flow tests (executed: 29 passed)
│   ├── requirements-day47.txt                          # Day47: pinned deps (sqlalchemy[asyncio]==2.0.29, pytest==7.4.3)
│   ├── day48-alembic-safe-schema-evolution-design.md   # Day48: Alembic safe-evolution design/runbook
│   ├── day48_alembic/                                  # Day48: Alembic control plane (env.py + gated Expand/Validate/Contract revisions)
│   ├── day48_lease_backfill.py                         # Day48: operational restartable FOR UPDATE SKIP LOCKED backfill (off the migration)
│   ├── test_day48_alembic.py                           # Day48: static Alembic + fake-session backfill tests (executed: 44 passed)
│   ├── requirements-day48.txt                          # Day48: pinned deps (alembic==1.13.1, sqlalchemy[asyncio]==2.0.29, pytest==7.4.3, psycopg2-binary)
│   ├── day49-upload-object-storage-and-artifact-verification-design.md  # Day49: verified upload boundary design/runbook
│   ├── day49_upload_verification.py                    # Day49: provider-neutral upload/verify control-flow model + fake in-memory adapter
│   ├── test_day49_upload_verification.py               # Day49: fake-adapter tests (executed: 44 passed)
│   ├── requirements-day49.txt                          # Day49: pinned deps (pytest==7.4.3; module + tests are stdlib-only)
│   ├── day50-idempotent-job-acceptance-and-transactional-outbox-design.md  # Day50: idempotent acceptance + outbox design/runbook
│   ├── day50_job_acceptance_outbox.py                  # Day50: provider-neutral acceptance/outbox control-flow model + fake store/transport
│   ├── test_day50_job_acceptance_outbox.py             # Day50: fake-adapter tests (executed: 29 passed)
│   ├── requirements-day50.txt                          # Day50: pinned deps (pytest==7.4.3; module + tests are stdlib-only)
│   ├── day51-authentication-password-security-and-jwt-design.md  # Day51: auth (password/JWT/refresh) design/runbook
│   ├── day51_authentication_jwt.py                     # Day51: real Argon2id + real RS256 JWT + guarded refresh model
│   ├── test_day51_authentication_jwt.py                # Day51: real-crypto tests (executed: 37 passed)
│   ├── requirements-day51.txt                          # Day51: pinned deps (argon2-cffi, PyJWT[crypto], cryptography, pytest)
│   ├── day52-authorization-tenant-isolation-quotas-and-api-security-design.md  # Day52: authz/tenant/quota design/runbook
│   ├── day52_authorization_tenant_quota_security.py    # Day52: authz + tenant isolation + guarded quota reservation model (stdlib-only)
│   ├── test_day52_authorization_tenant_quota_security.py  # Day52: in-memory tests (executed: 32 passed)
│   ├── day53-openai-sdk-provider-boundaries-and-structured-output-design.md  # Day53: provider boundary + structured output design/runbook
│   ├── day53_openai_provider_structured_output.py      # Day53: OpenAI-compatible adapter boundary + Pydantic v2 validation model
│   ├── test_day53_openai_provider_structured_output.py # Day53: real-Pydantic + fake-transport tests (executed: 48 passed)
│   ├── requirements-day53.txt                          # Day53: pinned deps (pydantic==2.5.0, pytest==7.4.3; fake transport, no openai dep)
│   ├── day54-ai-streaming-client-disconnects-timeouts-and-cancellation-design.md  # Day54: streaming/lifecycles/cancellation design/runbook
│   ├── day54_streaming_disconnects_timeouts_cancellation.py  # Day54: three-lifecycle + durable cancellation model (stdlib-only)
│   ├── test_day54_streaming_disconnects_timeouts_cancellation.py  # Day54: in-memory tests (executed: 27 passed)
│   └── requirements-day54.txt                          # Day54: pinned deps (pydantic==2.5.0, pytest==7.4.3; late-result path reuses Day53's gate)
├── redis/
│   ├── redis-acceleration-layer-design.md             # Day38: Redis acceleration-layer design (design + evidence, not executed)
│   ├── redis-cache-consistency-design.md              # Day39: Redis cache consistency design (design + evidence, not executed)
│   ├── redis-messaging-and-queue-semantics-design.md  # Day40: Redis messaging and queue semantics design (design + evidence, not executed)
│   └── redis-coordination-and-production-safety-design.md  # Day41: Redis coordination and production-safety design (design + evidence, not executed)
├── runbooks/
│   └── postgresql-production-reliability.md            # Day37: production reliability runbook (design + evidence, not executed)
└── sql/
    ├── 001_create_jobs.sql                              # Day29: the durable Job schema
    ├── 002_job_crud_and_guarded_transitions.sql         # Day30: parameterized reads + guarded writes (reference pack, not DDL)
    ├── 003_relational_modeling_and_data_integrity.sql   # Day31: relational target schema + constraints
    ├── 004_sql_joins_aggregation_and_operational_queries.sql  # Day32: read-only operational query pack (not DDL)
    ├── 005_postgresql_transactions_and_atomic_state_changes.sql  # Day33: transactional write pack (driver-bound, not DDL)
    ├── 006_concurrency_control_mvcc_and_worker_claims.sql        # Day34: concurrency claim pack (active claim + conceptual lease)
    ├── 007_postgresql_indexes_and_query_planning.sql            # Day35: index/EXPLAIN design pack (designs + evidence, not a migration)
    └── 008_schema_evolution_and_safe_migrations.sql            # Day36: safe-migration design pack (phased plan, not executed)
```

> **Deviation from `projects/README.md` (stated honestly):** the generic project template lists
> `requirements.txt`, `Dockerfile`, `src/`, `tests/`, and `docs/`. Day29 produced only a README and one
> raw SQL file, so nothing else exists yet. Empty folders and placeholder executables are deliberately
> **not** created; the structure will grow as later Phase 3 lessons produce real content. No ORM is
> used — SQLAlchemy/Alembic are Phase 4.

---

## What this schema is for

```text
Client uploads a verified 500 MB document
-> FastAPI writes (and commits) the Job row      <-- THIS FILE
-> FastAPI returns 202 + job_id
-> a worker later claims the queued Job
```

The row must exist **before** `202` is returned. `202` acknowledges a commitment that already exists
durably; if the API Pod is replaced a millisecond later, the Job is still recoverable.

## Ownership decisions

```text
PostgreSQL     -> the Job row: identity, state, timestamps, counters, flags, references (durable truth)
Object Storage -> the 500 MB source document and large derived artifacts (result_object_key is a REFERENCE)
Redis / Queue  -> transient transport/cache only (not modeled here, not run in Day29)
Process memory -> request-local only; never durable truth
```

Column intent:

| Column | Type | Intent |
|---|---|---|
| `job_id` | `uuid` PK, `DEFAULT gen_random_uuid()` | stable row identity; distributed + non-enumerable |
| `job_status` | `text NOT NULL DEFAULT 'queued'` | evolving lifecycle state |
| `attempt_count` | `integer NOT NULL DEFAULT 0` | retry bookkeeping |
| `cancel_requested` | `boolean NOT NULL DEFAULT false` | cooperative cancellation flag |
| `provider_metadata` | `jsonb NOT NULL DEFAULT '{}'::jsonb` | **bounded** auxiliary metadata only |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | immutable acceptance instant |
| `started_at` | `timestamptz` NULL | NULL -> execution has not started |
| `finished_at` | `timestamptz` NULL | NULL -> not terminal yet |
| `error_message` | `text` NULL | NULL -> no recorded error |
| `result_object_key` | `text` NULL | NULL -> no result artifact yet (Object Storage reference) |

---

## Day51 increment — authentication (password security + JWT + refresh sessions)

`api/day51-authentication-password-security-and-jwt-design.md` (with a runnable `day51_authentication_jwt.py` and
`test_day51_authentication_jwt.py`) establishes a trusted caller identity. The tests are **real, executed** using
**real crypto** (Argon2id + RS256 JWT) with ephemeral in-process keys: **Python 3.10.12; argon2-cffi 23.1.0,
PyJWT 2.8.0, cryptography 48.0.0, pytest 7.4.3 -> `37 passed`** (deps pinned in `api/requirements-day51.txt`).

### What the model contains

| Concern | Contents |
| --- | --- |
| Passwords | real Argon2id `PasswordService` (hash starts `$argon2id$`); library `verify`; one generic `authenticate` failure + decoy verify; `needs_rehash`; a fast digest is used ONLY for a high-entropy refresh secret. |
| JWT verification | `verify_access_token` full contract: `ALLOWED_ALGS=("RS256",)`, trusted key by allowlisted `kid`, signature + iss + aud + exp + nbf + required `sub` -> `AuthenticatedIdentity(user_id=sub)`; rejects `alg=none`/HS256-confusion/wrong-iss/aud/expired/nbf/missing-sub/tamper. |
| Keys | `KeyRing`: private held by the Auth Service, public allowlist for verifiers; `revoke_key` (emergency — blocks BOTH verify and signing; revoking the current signer fails closed until `set_current_signing_kid(K2)`), `drop_key` (post-overlap), `refresh_unknown_kid` (trusted-source, else reject); K1->K2 overlap. |
| Refresh sessions | per-device `AuthSession` storing only `refresh_token_hash`; guarded `rotate_refresh` models `UPDATE ... RETURNING` single winner + all-or-nothing rollback; bounded one-time grace (`GRACE_RETRY` recovers the SAME usable B once from a short-TTL ENCRYPTED recovery slot, never A->C) vs `REPLAY_DETECTED` on ANY used family token via a per-family used-hash ledger -> revoke + RETAIN family + isolate other devices; `sweep_expired_recovery_material` enforces minimum-retention (destroys recovery ciphertext + grace hash once past grace even if the old token never returns; fail-closed on time; ledger/audit retained; a real deployment runs it as a scheduled job); all revoke paths (`revoke_session`, family revoke, `revoke_all_user_sessions`) destroy recovery material immediately via a shared `_clear_recovery_material` helper, so the sweep is only the abandoned-token fallback. |
| Browser/CSRF | `evaluate_state_change_request`: cookie-only cross-site without valid Origin + CSRF -> reject (HttpOnly is not CSRF defense). |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day51.txt   # argon2-cffi, PyJWT[crypto], cryptography, pytest
python3 -m py_compile day51_authentication_jwt.py test_day51_authentication_jwt.py
python3 -m pytest -q test_day51_authentication_jwt.py
```

> **What this increment deliberately does not do:** it proves crypto primitives + application control flow only.
> **NOT RUN:** real PostgreSQL (UNIQUE/constraint/transaction/isolation or `UPDATE ... WHERE ... RETURNING`), real
> FastAPI/browser (cookies/SameSite/Origin/CSRF at the wire), a real JWKS endpoint, integration, and production. JWE
> (encrypted JWT) is out of scope — a normal signed JWT is readable. Authentication establishes a trusted `user_id`;
> a client-supplied `tenant_id` is not authority — Day52 owns tenant membership/authorization/quota; Day53 the real
> Provider; Day55 real Celery. Schema honesty: a `password_hash` column and the per-device `AuthSession` table are
> new facts modeled in-memory; the real schema needs a Day48-safe forward additive migration (not implemented here).
> No plaintext passwords, refresh tokens, JWTs, or operational signing keys are committed.

---

## Day57 increment — AI backend testing, fake providers, contract tests and failure injection

`api/day57-ai-backend-testing-fake-providers-contract-tests-and-failure-injection-design.md` (with a runnable
`day57_testing_harness.py` and `test_day57_testing_harness.py`) turns the Day43–Day56 policies into repeatable evidence.
The tests are **executed**, deterministic control flow driving Day56 + Day53's real validator: **Python 3.10.12,
pydantic 2.5.0, pytest 7.4.3 -> `21 passed`**.

### What the harness contains

| Concern | Contents |
| --- | --- |
| Determinism | `FakeClock` + `DeterministicRandom` (reproducible backoff/jitter; Retry-After is an earliest floor, no wake-all). |
| Fake Provider | `ControllableFakeProvider` (scripted `ScriptedResponse`, `calls` count, `request_received`/`release_response` gates, execution evidence) + an independent `ProviderCallLog` that survives "Worker loss". |
| Adapter contract | `ProviderAdapter.to_outcome` -> application-owned `ProviderOutcome` (failure kind, execution certainty, request id, safe retry/metadata); no SDK leakage; never writes Job/cost. |
| Late result | `attempt_late_completion` -> COMPLETED only on non-terminal + awaiting + strict schema + all four ids match; terminal CANCELLED -> `REFUSED_TERMINAL`. |
| Evidence taxonomy | `EvidenceTier` + `VALIDATION_MATRIX` + `not_run_claims()` — conceptual/static vs executed-local vs production (real infra NOT RUN). |
| Drives Day56 | dispatch-evidence RECONCILE, limiter-outage fail-closed DEFER, `process_deadline` with/without evidence, `admit_job` 503>429, guarded idempotent `repair_redispatch`. |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day57.txt   # pydantic==2.5.0, pytest==7.4.3 (drives Day56 + Day53 validator)
python3 -m pytest -q test_day57_testing_harness.py   # 21 passed
```

Not run (and not claimed): real PostgreSQL transaction/rollback/isolation, a real Celery broker + Worker
process/redelivery, real Worker-kill fault injection, a real Redis limiter/circuit, and real Provider traffic/cost. A
real `job_repair_history` table + migration is a forward-additive design, not implemented. Day58 owns structured
observability + the Phase 4 capstone; neither is implemented here.

---

## Day56 increment — Provider resilience, rate limits, token cost and backpressure

`api/day56-provider-resilience-rate-limits-token-cost-and-backpressure-design.md` (with a runnable
`day56_provider_resilience.py` and `test_day56_provider_resilience.py`) adds the admission-to-Provider control plane on
top of Day55 execution. The tests are **executed**, standard-library control flow (imports Day54 `IntentKind`):
**Python 3.10.12, pytest 7.4.3 -> `54 passed`**.

### What the model contains

| Concern | Contents |
| --- | --- |
| Four authorities | guarded claim (execution, Day55) vs `SharedRateLimiter` (fleet capacity) vs `TenantBudgetLedger` (affordability) vs `CircuitBreaker` (Provider health). A claim is not a permit; a limiter is not the ledger. |
| Five outcomes | `evaluate_dispatch` -> CALL / DEFER / RECONCILE / TERMINAL / NOOP; facts (terminal, intent, evidence, deadline) outrank capacity retry. |
| Retry | `backoff_delay_seconds` (bounded + full jitter); `compute_next_attempt_at` = max(jittered backoff, Retry-After floor). Retry storm != cache avalanche. |
| Limiter outage | fails CLOSED by default (`limiter_unavailable_fail_closed`); `emergency_fail_open` is an explicit policy. |
| Defer | durable `DeferRecord` (reason/next_attempt_at/defer_count/deadline); no Worker sleep; `defer_count` != `execution_retry_count`; never past the deadline. |
| Cost | `reserve_worst_case` (contract max_tokens x price, not remaining balance); `settle_actual` releases unused money to the ledger; unknown -> `hold_for_reconciliation`. |
| Backpressure | `admit_job` -> ACCEPT / REJECT_429_TENANT / REJECT_503_SYSTEM (system dominates); before the durable commit. |
| Degradation | `apply_authorized_degradation` only if the persisted contract allows it, down to `min_model`/`min_max_tokens`. |
| Certainty | `classify_execution_certainty` (DEFINITELY_NOT_ACCEPTED / MAY_HAVE_EXECUTED / UNKNOWN); evidence/marker -> RECONCILE. |
| Circuit | CLOSED/OPEN/HALF_OPEN; bounded progressive probes; one success does not close; key `circuit:{provider}:{account}:{model}:{region}` (no secrets). |
| Deadline / incident | `process_deadline` (release only w/o evidence); `ReleaseConfig.rollback` + `build_capacity_expiry_affected_set` + `classify_incident_repair` + `repair_redispatch` (new `OutboxDispatchIntent`, evidence -> RECONCILE_ONLY). |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pytest -q test_day56_provider_resilience.py   # 31 passed
```

Not run (and not claimed): a real Celery broker/Worker, a real Redis distributed limiter/circuit, real PostgreSQL,
real Provider traffic/rate limits/costs, load tests, and Worker-kill fault injection. Day57 owns integration + failure
injection; Day58 owns observability/runtime evidence — neither is implemented here.

---

## Day55 increment — Celery, Worker execution and long-running AI Jobs

`api/day55-celery-worker-execution-and-long-running-ai-jobs-design.md` (with a runnable
`day55_celery_worker_execution.py` and `test_day55_celery_worker_execution.py`) moves long-running Provider work onto a
supported Celery broker transport + Workers while PostgreSQL stays the source of business truth. The tests are
**executed**, standard-library control flow reusing Day53's pydantic gate: **Python 3.10.12, pydantic 2.5.0, pytest
7.4.3 -> `27 passed`**.

### What the model contains

| Concern | Contents |
| --- | --- |
| Outbox ordering | `OutboxRelay.relay` publishes to the broker BEFORE the `published` checkpoint; a crash-between re-publishes (absorbed), checkpoint-first would strand the Job. |
| Broker | `CeleryBrokerSim` (publish/deliver/redeliver via `visibility_timeout`/ack/dead-letter) — supported Celery semantics only, NOT the Day40 Streams design. |
| Guarded claim | `JobStore.claim_execution` = the first duplicate-call gate (`UPDATE ... WHERE status IN ('queued','running') RETURNING`): GRANTED / CONFLICT / ALREADY_TERMINAL / RECONCILE_ONLY. A lease/fencing token is secondary. |
| Identity | eight layers; redelivery/new Worker retains the open `Attempt` + `provider_idempotency_key`; `provider_request_id` recorded at request open. |
| ACK timing | `AckMode.LATE` (default) redelivers on crash + absorbs duplicates; `AckMode.EARLY` silently loses the delivery. ACK/`SUCCESS` != Job succeeded. |
| Timeout / OOM | `ProviderResultKind.TIMEOUT` -> `PENDING_RECONCILIATION`, reservation retained (never 0), no blind re-call; a redelivered pending Job -> `RECONCILE_NO_RECALL`, 0 Provider calls. A conservative `provider_dispatch_started_at` marker persisted BEFORE the call (P1) means an OOM after dispatch but before recording `provider_request_id` still reconciles (missing id != not executed). |
| Poison | envelope poison (`envelope_version` unsupported) -> dead-letter+ACK BEFORE Job load; execution-contract poison -> `QUARANTINED`+ACK AFTER Job load; both 0 calls; version spaces disjoint. |
| Cancellation | `request_cancellation` persists a durable intent FIRST, optional best-effort `revoke` after; `run_worker` checks it pre-call (0 calls) and final-pre-completion (no `succeeded`); `terminal_for_intent`: user cancel -> CANCELLED, deadline -> EXPIRED; one guarded winner. |
| Drain / incident | `graceful_drain` (stop new claims, drain bounded, checkpoint); `ReleaseConfig.rollback` (future harm only) + `build_affected_set` (no bulk flip) + `classify_repair` (RECONCILE_ONLY where `provider_request_id` exists, else guarded redispatch). |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day55.txt   # pydantic==2.5.0, pytest==7.4.3 (reuses Day53 gate; no Celery/broker/PostgreSQL invoked)
python3 -m pytest -q test_day55_celery_worker_execution.py   # 27 passed
```

Not run (and not claimed): a real Celery broker (Redis/RabbitMQ) transport + Worker process, real
ACK/redelivery/visibility-timeout, Worker-loss/OOM fault injection, real PostgreSQL/Redis, and the real Provider. Day56
(retry/backoff, rate limits, token cost, backpressure) and Day57 (integration/failure-injection/recovery verification)
consume this execution/recovery contract rather than being implemented here.

---

## Day54 increment — AI streaming, client disconnects, timeouts and cancellation

`api/day54-ai-streaming-client-disconnects-timeouts-and-cancellation-design.md` (with a runnable
`day54_streaming_disconnects_timeouts_cancellation.py` and `test_day54_streaming_disconnects_timeouts_cancellation.py`)
separates two kinds of streaming and three independent lifecycles. The tests are **executed**, **standard-library
only**: **Python 3.10.12, pytest 7.4.3 -> `27 passed`**.

### What the model contains

| Concern | Contents |
| --- | --- |
| Three lifecycles | `SubscriptionRegistry` (HTTP connection) vs the Provider token stream vs the durable `JobStore`; an SSE `disconnect` ends only the subscription and never touches the Job. |
| Two streams | transient `FakeProviderStream` tokens vs durable `JobStore` events + `reconnect_view` (safe milestones only; raw tokens never persisted). |
| Timeout | `record_timeout_pending` -> `PENDING_RECONCILIATION`, reservation retained, unknown usage (never 0); the 202 is not retro-504. |
| Cancellation | `request_cancellation` persists a durable auditable intent only; `run_worker` cooperatively checks it (pre-call -> no Provider call; mid-stream -> best-effort abort + `reconciliation_pending`) then a `guarded_terminal_transition`. |
| Concurrency | completion vs cancellation each guarded (`UPDATE ... WHERE status IN (live) RETURNING`); exactly one WON, the loser ZERO_ROWS; a late result after terminal -> `REFUSED_TERMINAL`. |
| Crash recovery | `scan_open_intents` + `apply_cancellation`; at-least-once re-observation, guarded transition absorbs repeats. |
| Incident recovery | `DisconnectPolicy.rollback` (stop new harm) + `build_affected_set` (version + time window) + `classify_recovery` (evidence-based; no blind flip/re-call). |
| Terminal mapping | `terminal_for_intent`: user cancel -> `CANCELLED`, deadline -> `EXPIRED`, consistent across pre-call / mid-stream / pre-completion / crash re-observation. |
| Late result | `ingest_late_provider_result` reuses Day53 identity binding (job_id + attempt_id + correlation_id + provider_request_id) + strict validation gate; mismatch/missing/not-awaiting/terminal/invalid -> side-effect-free refusal; matched completes at most once; 0 Provider calls. |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pytest -q test_day54_streaming_disconnects_timeouts_cancellation.py   # 27 passed
```

Not run (and not claimed): real FastAPI/SSE wire behavior, the real OpenAI SDK/network/Provider token stream, real
PostgreSQL/Redis/Celery, integration, production. Day55 (Celery Worker execution) consumes this cancellation/lifecycle
contract; Day56 owns retry/backoff/backpressure — neither is implemented here.

---

## Day53 increment — OpenAI SDK, provider boundaries and structured output

`api/day53-openai-sdk-provider-boundaries-and-structured-output-design.md` (with a runnable
`day53_openai_provider_structured_output.py` and `test_day53_openai_provider_structured_output.py`) puts an
OpenAI-compatible Provider behind an application-owned boundary. The tests are **executed** using **real Pydantic v2**
validation + an **injected fake transport**: **Python 3.10.12, pydantic 2.5.0, pytest 7.4.3 -> `20 passed`**.

### What the model contains

| Concern | Contents |
| --- | --- |
| Adapter boundary | `OpenAICompatibleAdapter.generate(request) -> ProviderOutcome` owns ALL SDK objects/exceptions, reuses one lifespan-owned client, enforces `effective_max = min(Job cap, ceiling)` (5000 wins over 8000), reports usage (no second reservation), and never completes Jobs / writes DBs. |
| Outcome union | `ProviderSuccess` (untrusted payload) / `ProviderRefusal` / `ProviderIncomplete` / `ProviderTimeout` / `ProviderAuthenticationError` / `ProviderRateLimited` / `ProviderCapabilityError` / `ProviderTransportError`. |
| Validation gate | `StructuredOutputValidator` + a server-owned `SchemaRegistry` (`research_summary.v1/v2`); real Pydantic v2 `extra="forbid"`; missing `citations` / forbidden `debug_prompt` -> CONTRACT_VIOLATION; unknown version -> SCHEMA_NOT_FOUND; no cross-version satisfaction. |
| Completion | `CompletionService` runs the ONLY guarded `running -> succeeded` + short UoW; zero rows -> NOOP (stop, no overwrite); Result Artifact = validated domain result + safe metadata only (raw minimization). |
| Cost axes | business success vs cost settlement separate; valid output with unknown usage -> SUCCEEDED + `reconciliation_pending` (reservation retained, never zero). |
| Errors + rollback | 401/403 disables the Provider config (stop new calls, keep evidence); 429 = downstream Job event with safe Retry-After (not a client 429); config rollback != business-fact rollback (a valid old in-flight v1 result is still accepted against its persisted contract). |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day53.txt   # pydantic==2.5.0, pytest==7.4.3 (fake transport; no openai dependency)
python3 -m pytest -q test_day53_openai_provider_structured_output.py   # 48 passed
```

Not run (and not claimed): the real `openai` SDK / network / Provider, real PostgreSQL / Redis / Celery Worker,
FastAPI wire, integration, production. Day54 streaming/disconnect/cancellation, Day55 Celery, and Day56
retry/backoff/degradation consume this boundary rather than being implemented here.

---

## Day52 increment — authorization, tenant isolation, quotas and API security

`api/day52-authorization-tenant-isolation-quotas-and-api-security-design.md` (with a runnable
`day52_authorization_tenant_quota_security.py` and `test_day52_authorization_tenant_quota_security.py`) turns Day51's
trusted `user_id` into current, tenant-scoped, action-specific, cost-aware authority. The tests are **executed**,
**standard-library only**: **Python 3.10.12, pytest 7.4.3 -> `32 passed`**.

### What the model contains

| Concern | Contents |
| --- | --- |
| Authorization | `authorize(identity, requested_tenant_id, action)` -> active Membership + role action -> `AuthorizedTenantContext(user_id, tenant_id, permissions)`; a client `tenant_id` is only a selector; every failure is a generic 403; Membership removal revokes authority immediately. |
| Tenant/owner scope | `JobRepository.read_job(ctx, job_id)` scopes `WHERE tenant_id = authorized AND job_id`; `job.read_own` also requires `created_by_user_id == user`; a cross-tenant miss is a public 404 (no existence oracle). |
| Rate limit | `TokenBucketRateLimiter` (shared model; bounded burst + refill); healthy breach -> `RATE_LIMITED` (429 + Retry-After); outage on a paid path -> `LimiterUnavailable` (fail-closed 503, never 429). |
| Durable quota | guarded `UPDATE tenant_budgets ... WHERE token_limit - used - reserved >= amount RETURNING` single winner; Reservation + Job + Outbox commit in one tx (rollback all on failure); `reconcile` settles actual usage or holds `reconciliation_pending` on unknown Provider cost. |
| Idempotency | `admit_job` order: authorize -> same-command recovery (no new cost) -> rate-limit new commands -> reserve + create; same key+fingerprint -> original Job, no second reservation; changed fingerprint -> 409; removed Membership blocks old-Key recovery. |
| Policy repair | `CancelIntentLedger.repair_bad_intent` guarded by intent ID + `policy_version`; zero rows -> reconcile; bad intents invalidated, never deleted; a legitimate later cancel is never overwritten. |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pytest -q test_day52_authorization_tenant_quota_security.py   # 32 passed (standard-library only)
```

Not run (and not claimed): real PostgreSQL (constraint/tx/isolation/`UPDATE ... RETURNING`/RLS), real Redis
(distributed limiter atomics/TTL/failover), real FastAPI/proxy/browser (Dependency/CORS/cookie/CSRF/routes),
Provider/Worker/Outbox transport, integration, production. Day53 real Provider, Day54 streaming/cancellation, and
Day55 Workers consume this authorized context rather than bypassing it.

---

## Day50 increment — idempotent Job acceptance + transactional Outbox

`api/day50-idempotent-job-acceptance-and-transactional-outbox-design.md` (with a runnable
`day50_job_acceptance_outbox.py` and `test_day50_job_acceptance_outbox.py`) accepts one logical AI Job exactly once
at the API boundary and persists its dispatch intent atomically with the Job. The tests are **real, executed**
against a **fake in-memory store + TransportAdapter** — **application control flow only**: **Python 3.10.12,
pytest 7.4.3 -> `29 passed`** (the module + tests are Python-standard-library only; deps pinned in
`api/requirements-day50.txt`).

### What the model contains

| Concern | Contents |
| --- | --- |
| Acceptance identity | `Idempotency-Key` = one logical command; `compute_request_fingerprint` = evidence semantics didn't change (key not included); missing key rejected before writes; every Document must be Day49-verified + tenant-owned. |
| DB arbitration | `upsert_job_on_conflict` models `INSERT ... ON CONFLICT (tenant_id, idempotency_key)`; same key+fingerprint -> `RETURNED_EXISTING`; changed fingerprint -> `CONFLICT` (no durable facts). |
| Atomic UoW | Job(queued) + exactly one `job.dispatch_requested` Outbox intent commit together (mid-tx failure leaves neither); at-most-one dispatch intent (`DispatchIntentExists`). |
| Outbox Relay | `run_relay_once`: claim (`FOR UPDATE SKIP LOCKED` + lease/owner) -> publish OUTSIDE the DB lock via `TransportAdapter.publish` -> fenced checkpoint (`published_at`). Envelope is small (`outbox_event_id`/`event_type`/`job_id`/correlation) — no prompt/secret. |
| Failure/recovery | unknown publish (crash before checkpoint) -> retain + republish (at-least-once); transient -> attempt++/redacted error/`next_attempt_at` backoff+jitter; exhausted -> `QUARANTINED` (Job stays `queued`, never failed). |
| Concurrency | `claim_outbox_batch` skip-locked; `checkpoint_published_if_owner` raises `FencingError` for a superseded relay; no DB lock over transport I/O; `worker_claim` = one guarded `queued -> running` winner. |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day50.txt   # pytest==7.4.3 (module + tests are stdlib-only)
python3 -m py_compile day50_job_acceptance_outbox.py test_day50_job_acceptance_outbox.py
python3 -m pytest -q test_day50_job_acceptance_outbox.py
```

> **What this increment deliberately does not do:** it uses a **fake in-memory** store + transport, so it proves
> application control flow only. **NOT RUN:** real PostgreSQL UNIQUE/constraint/transaction/isolation or
> `INSERT ... ON CONFLICT`/`FOR UPDATE SKIP LOCKED`, a real broker/Celery (ACK/redelivery/poison), Worker/Provider
> runtime, integration, and production. It is not a Celery replacement and claims **no exactly-once** across
> PostgreSQL + broker + Worker + Provider. Day51 auth, Day52 authorization/quota, Day53 real Provider, and Day55
> real Celery are not implemented. Schema honesty: the published schema has `UNIQUE(tenant_id, idempotency_key)` but
> lacks a request-fingerprint column, `UNIQUE(job_id, event_type)`, and relay ops columns — all modeled in-memory;
> the real schema needs a Day48-safe forward additive migration (not implemented here).

---

## Day49 increment — verified Object Storage upload boundary

`api/day49-upload-object-storage-and-artifact-verification-design.md` (with a runnable
`day49_upload_verification.py` and `test_day49_upload_verification.py`) turns large external bytes into
deterministic, verified, recoverable database references. The tests are **real, executed** against a **fake
in-memory Object Storage adapter** — **application control flow only**: **Python 3.10.12, pytest 7.4.3 ->
`44 passed`** (hardened after Codex review rounds 1-2; the module + tests are Python-standard-library only; deps pinned in `api/requirements-day49.txt`).

### What the model contains

| Concern | Contents |
| --- | --- |
| Mental model | upload success = storage-layer fact; verified = business fact + evidence. Presigned URL = scoped bearer credential (replayable until expiry, not identity, not one-time). `bucket + key + immutable version` = deterministic identity. Document = verified INPUT reference; ResultArtifact = verified OUTPUT reference (neither is the bytes). |
| Server-owned identity | `derive_object_key(tenant_id, upload_session_id)`; the filename is untrusted; `finalize_upload` returns `REJECTED_KEY` if the client key != the persisted key. |
| Verification | `verify_object(expected, observed)` compares a **frozen** expected contract with **trusted observed** evidence; never rewrites the expectation; requires an immutable version + size + a trustworthy full-object SHA-256; **ETag is not accepted as SHA-256**. |
| Security gate | separate from byte integrity; a mandatory scanner outage is **fail-closed** (`SCAN_RETRY_LATER`, session -> `verifying` with a `verification_hold_until` deadline, no Document) so cleanup cannot delete a retrying object; unsafe content -> `SCAN_FAILED`/quarantine. |
| State/expiry guard | finalize proceeds only from `uploading`/`verifying`; `INITIATED`/`FAILED`/`EXPIRED` and cleanup-claimed rows are rejected (`ILLEGAL_STATE`); session/credential expiry re-checked (`SESSION_EXPIRED`). |
| Lease + atomic commit | `claim_verification` takes an owner/fencing-token lease + `verification_hold_until` and binds the exact version BEFORE scanning; `commit_document_if_owner` guarded-CAS creates the Document + flips `verified` only if still verifying + our token + not expired + cleanup hasn't won (MODELED; not real tx/fencing). Interleaving tests prove cleanup-wins vs completion-wins. |
| Adapter | create-only writes (replay -> `ObjectAlreadyExistsError`) + per-`(bucket,key)` version history with exact-version inspect/delete. |
| Identity | server owns bucket+key (+ bound version); completion rejects client-supplied identity (`REJECTED_IDENTITY`); verify compares observed bucket/key/version/size/sha256/content-type. |
| Finalization UoW | inspect + verify + scan OUTSIDE a DB tx -> short guarded UoW creates exactly one Document + flips the session `verified` atomically; already verified -> return the existing Document; a lost race hitting `UNIQUE(upload_session_id)` collapses to `ALREADY_VERIFIED`. |
| Completion vs cleanup | `classify_cleanup` keeps a verified/documented session (`KEEP_VERIFIED`/`KEEP_HAS_DOCUMENT`) and is `KEEP_TOO_EARLY` before `cleanup_not_before = credential_expiry + clock_skew + safety_buffer` (12:00 + 2m + 1m = 12:03). Never hold a DB lock across storage I/O. |
| Multipart recovery | `classify_multipart_completion` -> `COMPLETE_SUCCEEDED` / `FINAL_OBJECT_MISMATCH` / `RECOVER_FROM_PARTS` / `PARTS_NOT_ASSEMBLED`; parts are transport progress, not a Document; a timed-out Complete inspects the deterministic final object before any retry. |
| Output recovery | `classify_result_recovery` -> `COMPLETE_IDEMPOTENT_NO_PROVIDER` / `PRESERVE_UNKNOWN` / `ALREADY_COMPLETED`; never re-call a paid Provider on recovery. |
| Provenance | modeled `UNIQUE(upload_session_id)` (`DuplicateDocumentError`) + composite FK `(tenant_id, upload_session_id)` (`ProvenanceError`); authorization is Day52, not here. |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day49.txt   # pytest==7.4.3 (module + tests are stdlib-only)
python3 -m py_compile day49_upload_verification.py test_day49_upload_verification.py
python3 -m pytest -q test_day49_upload_verification.py
```

> **What this increment deliberately does not do:** it uses a **fake in-memory** adapter, so it proves application
> control flow only. **NOT RUN:** real PostgreSQL FK/constraint runtime, real Object Storage
> (presign/checksum/multipart/versioning) semantics, FastAPI/scanner integration, and production. It does not
> implement Day50 Outbox, Day51 JWT, Day52 authorization, Day55 Celery, or a real Provider, and uses no real
> credentials/buckets/tokens/signed URLs. Schema honesty: the published `upload_sessions` allowlist has no
> `verifying`, so the hold is **modeled in-memory** (`verifying` + `verification_hold_until`); the real schema needs a Day48-safe **forward** migration (a `verifying` status via a branch revision, or a hold/lease table) — not implemented here, never a rewrite of published history.

---

## Day48 increment — Alembic and safe AI backend schema evolution

`api/day48-alembic-safe-schema-evolution-design.md` (with a runnable `day48_alembic/` control plane, an
operational `day48_lease_backfill.py`, and `test_day48_alembic.py`) makes Day36's Expand -> Backfill -> Validate
-> Switch -> Contract discipline executable with Alembic for a Lease-ownership evolution of `app.jobs`. The
artifact and its **static/offline** tests are **real, executed**: **Python 3.10.12, Alembic 1.13.1, SQLAlchemy
2.0.29, pytest 7.4.3 -> `20 passed`** (deps pinned in `api/requirements-day48.txt`), plus an offline `alembic
upgrade --sql` DDL render. These prove the migration **text/structure and control flow** only; **PostgreSQL
runtime is NOT RUN**.

### What the control plane contains

| Section | Contents |
| --- | --- |
| Mental model | a migration is a versioned transition across schema + historical rows + every writer; `alembic upgrade head` success is DDL-only evidence; safe evolution = Expand/Backfill/Validate/Switch/Contract, each separately gated |
| Expand (0002) | `ADD COLUMN` lease_owner/lease_token/lease_expires_at (all **nullable, no fabricated default**, **no constraint** — the OLD/NEW compatibility window, old Writers can still write a running-without-Lease row) **and** additively `CREATE TABLE app.job_lease_reconciliation` (an **independent** triage queue: job_id FK, reason, routed_at, resolution_status, `UNIQUE(job_id)`) — triage lives here, **never** as a column on app.jobs; deploy first |
| Constraints (0003) | **separate** revision: `CHECK ... NOT VALID` for triple coherence **and** the Day36 core `jobs_running_requires_lease`, applied **only after old Writers are drained/isolated** — `NOT VALID` skips the legacy scan but enforces every future write by **any** Writer version (an old Worker writing a running-without-Lease row is rejected), so it is not a "no-op for old code" |
| Backfill | operational, restartable `FOR UPDATE SKIP LOCKED` script **off the migration** (automatic candidate = running + `lease_owner IS NULL` + `NOT EXISTS` a row in `app.job_lease_reconciliation`); fills only running Jobs with trusted ownership (sets the Lease triple on app.jobs only); unknown -> `INSERT INTO app.job_lease_reconciliation ... ON CONFLICT (job_id) DO NOTHING` (guarded/idempotent, **no app.jobs write**, no fabricated lease) so the **automatic loop terminates** and a restart never re-selects it. Routing writes only the independent queue, so it is **legal after the strict 0003 constraint** (a marker UPDATE that left the row running+NULL-Lease would be rejected). Queuing is **triage, not resolution**: such a row still violates `jobs_running_requires_lease` and still counts in `unresolved_running_without_lease` (the count joins no queue table). `unresolved==0` is reached only by (a) a trusted Lease backfill or (b) an audited real recovery **routed** by `classify_unknown_running_recovery` (verified `succeeded` -> Day47 completion UoW; `failed`/`cancelled` -> guarded terminal-recovery; unknown -> stay reconciliation; a `queued` requeue / bare status flip is refused); no Provider; DB state = checkpoint |
| Validate (0004) | `VALIDATE CONSTRAINT` (both `jobs_lease_triple_coherent` and the Day36 core `jobs_running_requires_lease`) in a **separate** revision proves history; fails until every running-without-Lease row (queue-routed included) is truly resolved |
| Switch / Contract (0005) | Switch = every Writer on the token protocol, old path can't write; Contract destructive + last, after evidence + observation; forward-fix (not destructive downgrade) once real data/side effects exist |
| Alembic specifics | revision graph / `down_revision` / merge heads; autogenerate is a candidate diff to review; baseline/`stamp` writes `alembic_version` and does no DDL; minimal `env.py` (no FastAPI, no UoW) with DB-URL resolution `-x db_url` > env `DAY48_ALEMBIC_DATABASE_URL` (ini placeholder is **offline-render only**, never an online fallback -> online **fails fast** without an external URL; no credentials committed); `CREATE INDEX CONCURRENTLY` is non-transactional |
| Evidence | 10 **static/offline** tests (`ScriptDirectory` graph/source + fake-session backfill) + offline `--sql` render; **PostgreSQL runtime NOT RUN**; SQLite/fake/`upgrade`-success are not PostgreSQL proof |

### Run the tests / render DDL

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day48.txt   # alembic==1.13.1, sqlalchemy[asyncio]==2.0.29, pytest==7.4.3, psycopg2-binary
python3 -m py_compile day48_lease_backfill.py test_day48_alembic.py
python3 -m pytest -q test_day48_alembic.py
python3 -m alembic -c day48_alembic/alembic.ini upgrade 0001_baseline:head --sql   # offline DDL render, no DB
```

> **What this increment deliberately does not do:** it does **not** connect to a database — the tests inspect the
> Alembic revision graph/source and a fake backfill session, and the offline `--sql` render never connects.
> **PostgreSQL runtime is NOT RUN** (a real `NOT VALID`/`VALIDATE`/backfill test applies the Day42 raw SQL,
> creates a violating legacy row, and proves the old row survives, a new illegal write is rejected, and `VALIDATE`
> fails until repaired). **SQLite/fake sessions are not PostgreSQL evidence**, and `alembic upgrade` success alone
> does not prove Backfill/Switch/Contract or production safety. It does not migrate on FastAPI startup, run no
> Provider in Backfill, put no long Backfill loop in `upgrade()`, and does not implement the Day49 upload workflow
> or Day50 Outbox/Celery delivery. Routing a Job to `'reconcile'` is **triage, not resolution** — it never makes a
> running-without-Lease Job compliant and never satisfies the `VALIDATE` precondition. No secrets or real database
> URLs: the `alembic.ini` URL is a non-credential **offline-render placeholder only** (online mode **requires**
> `-x db_url=...` or `DAY48_ALEMBIC_DATABASE_URL` and **fails fast** otherwise).

### Day48 known gaps (deliberate)

```text
runtime    isolated PostgreSQL NOT VALID / VALIDATE / backfill test (apply Day42 SQL, prove behavior) — NOT RUN here
Day49      Upload Sessions / Object Storage / Artifact verification on the safely evolved model
Day50      tenant-scoped idempotency + atomic Job + Outbox intent over the same boundary (intent != Provider proof)
Day55      real supported-broker/Celery delivery semantics
scope      real Provider SDK/network (Day53), FastAPI/Worker drain integration, and production migration remain future
```

---

## Day47 increment — async sessions, transactions, repository and unit of work

`api/day47-async-persistence-boundary-design.md` (with runnable `day47_async_uow.py` + `test_day47_async_uow.py`)
drives the faithful Day46 mapping through short, isolated async units of work. The code and its **fake-session**
tests are **real, executed**: **Python 3.10.12, SQLAlchemy 2.0.29, greenlet 3.5.4, pytest 7.4.3 -> `29 passed`**
(deps pinned in `api/requirements-day47.txt`). These prove UoW/repository **control flow** only; a **mock is not
database proof**, so **PostgreSQL runtime is NOT RUN**.

### What the boundary contains

| Section | Contents |
| --- | --- |
| Scope/ownership | process-scoped `AsyncEngine` + `async_sessionmaker` (one per process, not per deployment); a fresh request/Job-scoped `AsyncSession`; **no** global Session |
| Repository/UoW | repositories receive the UoW-injected Session and never commit/close; the `UnitOfWork` owns one Session, exposes repos, does **explicit** `await commit()`, rolls back on exception/uncommitted exit, and always closes |
| Guarded claim | single `UPDATE ... WHERE job_id AND tenant_id AND job_status='queued' RETURNING` (not SELECT-then-UPDATE); every guarded `app.jobs` mutation binds `tenant_id` as a durable ownership predicate (trusted context, not derived from job_id); 1 row = claimed, 0 rows (incl. wrong tenant) = normal stale/no-op |
| Flush vs commit | `flush` executes SQL in the current tx (server ids usable) but is not durable/cross-session visible; `IntegrityError` aborts the tx (integrity protected) and needs rollback; a commit exception is an unknown outcome |
| Short tx vs Provider | the long/paid Provider call runs **outside** any DB transaction; commit an app-generated correlation/idempotency key **before** it (in the `job_started` Event metadata); completion is a **second** short guarded UoW that records the available Provider evidence (`provider_request_id`, `cost_micros`, may be None) in the guarded Attempt finish |
| Failure vs unknown | definitive failure -> `failed`; timeout/unknown remote outcome -> a first-class recovery state, never blindly requeued |
| Reads | build an allowlisted Day44 Pydantic DTO **inside** the UoW; never return a detached ORM object for lazy serialization |
| Evidence | 13 **fake-session** control-flow tests (code-path intent); **PostgreSQL runtime NOT RUN**; SQLite is not PostgreSQL evidence |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day47.txt   # sqlalchemy[asyncio]==2.0.29, pytest==7.4.3
python3 -m py_compile day47_async_uow.py test_day47_async_uow.py
python3 -m pytest -q test_day47_async_uow.py
```

> **What this increment deliberately does not do:** it reuses the Day46 mapping and does **not** redefine Day42
> schema authority, use `create_all()` as compatibility proof, change TEXT+CHECK to enum, or add a destructive
> cascade. It creates **no** global AsyncSession and no repository-owned commit, and it runs **no** long Provider
> call inside a DB transaction (the Provider is a fake seam). It does **not** implement the Day49 upload workflow
> or the Day50 idempotent acceptance/Outbox API. The tests use a **fake AsyncSession** (control flow only);
> **PostgreSQL runtime is NOT RUN** (no server/driver — a real test applies the Day42 raw SQL, forces a failure,
> and proves via a **new** Session that the Job stays queued with no Attempt/Event), and **SQLite is not
> PostgreSQL evidence**. No secrets, real database URLs, provider keys, or signed URLs.

### Day47 known gaps (deliberate)

```text
runtime    isolated PostgreSQL rollback/transaction test (apply Day42 SQL, verify via a fresh Session) — NOT RUN here
Day48      Alembic safe schema evolution on top of these Engine/session/repository boundaries
Day49      UploadSession/Artifact persistence with Object Storage I/O OUTSIDE the transaction
Day50      idempotent Job acceptance + Outbox over this same transactional boundary
scope      real Provider SDK/network (Day53), FastAPI/Worker concurrent integration, and production remain future
```

---

## Day46 increment — SQLAlchemy 2.0 mapping for the Day42 data model

`api/day46-sqlalchemy-mapping-for-the-day42-data-model-design.md` (with runnable `day46_orm_mapping.py` +
`test_day46_orm_mapping.py`) faithfully maps the existing Day42 PostgreSQL durable contract into SQLAlchemy 2.0
typed declarative models. The mapping and its **static** tests are **real, executed code**: **Python 3.10.12,
SQLAlchemy 2.0.29, pytest 7.4.3 -> `20 passed`** (deps pinned in `api/requirements-day46.txt`). But these assert
the **declared mapping structure only**; the ORM is a representation of the contract, **not** a new schema
authority, and **PostgreSQL runtime behavior is NOT RUN**.

### What the mapping contains

| Section | Contents |
| --- | --- |
| Authority | ORM MAPS the existing contract (it does not replace it); PostgreSQL stays durable authority. Day46 maps -> Day47 drives -> Day48 evolves |
| Typed mapping | `DeclarativeBase` + `MetaData(schema="app")`; `Mapped[T] = mapped_column(...)`; PostgreSQL `UUID`/`JSONB`, `TIMESTAMP(timezone=True)`, `Text`; server-side defaults (`gen_random_uuid()`/`now()`/…) |
| Constraints | named `UNIQUE`/`CHECK`/`FK` preserved exactly (`jobs_tenant_idempotency_unique`, `jobs_succeeded_has_finished_at`, `job_attempts_job_number_unique`, `job_events_attempt_same_job_fk`, …); `TEXT + CHECK` status, not a native enum (that is Day48) |
| Attempt/Event | Job-scoped retry uniqueness `UNIQUE(job_id, attempt_number)`; composite same-Job provenance FK `(job_id, attempt_id)`; NULL attempt_id = Job-level event |
| Retention | `ON DELETE RESTRICT` everywhere; **no** cascade/delete-orphan; `relationship()` is navigation only, with `passive_deletes="all"` on the parent-side relationships so the ORM never pre-NULLs a `NOT NULL` child FK and PostgreSQL RESTRICT makes the final delete decision |
| Boundaries | Pydantic public models kept separate from ORM models; Outbox `published_at` NULL = checkpoint not recorded (not "never sent"); ResultArtifact owns via `attempt_id` (no denormalized `job_id`); UploadSession stores references, not bytes |
| Scope | minimal Tenant support stub (tenant_id stays explicit); Document/`job_documents` = stated unimplemented limitation; **no** Engine/AsyncSession/transaction/UoW (Day47) |
| Evidence | 19 **static metadata** tests (declared structure); `create_all()` success is **not** compatibility; PostgreSQL runtime **NOT RUN** |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day46.txt   # sqlalchemy==2.0.29, pytest==7.4.3
python3 -m py_compile day46_orm_mapping.py test_day46_orm_mapping.py
python3 -m pytest -q test_day46_orm_mapping.py
```

> **What this increment deliberately does not do:** it creates **no** Engine, AsyncSession, transaction,
> repository, or unit of work (Day47), runs **no** Alembic/migration (Day48), and does **not** connect to a
> database — the tests introspect `Base.metadata` only and **never call `create_all()`** (whose success would
> not prove schema compatibility). Real PostgreSQL runtime behavior (apply the independent Day42 raw SQL, then
> assert a CHECK/UNIQUE/FK **rejection**) is **NOT RUN** (no server was available). No native-enum change, no
> Celery/Provider/Object-Storage runtime, no public API endpoint. Pydantic and ORM models stay separate; no fake
> secrets, credentialed URLs, or large bytes.

### Day46 known gaps (deliberate)

```text
Day47      AsyncEngine/AsyncSession lifecycle, transactions, repository, unit of work (drives these mappings)
Day48      Alembic safe schema evolution (Expand -> Backfill -> Validate -> Switch -> Contract); native-enum change if chosen
Day50      idempotent Job + Outbox acceptance over the mapped durable boundary
Day55      Celery Worker/broker delivery chain without changing the Outbox's PostgreSQL authority
runtime    isolated PostgreSQL test (apply Day42 SQL, assert rejected writes) — NOT RUN here
limitation app.documents + app.job_documents are NOT mapped (real Day42 schema, future scope)
```

---

## Day45 increment — DI, lifespan, configuration and AI provider adapters

`api/day45-di-lifespan-configuration-and-ai-provider-adapters-design.md` (with runnable `day45_composition.py`
+ `test_day45_composition.py`) composes the Day44 typed contracts into a runnable FastAPI/Worker where Routers
and business services never own infrastructure. The composition and tests are **real, executed code** with a
**fake, no-network Provider**: **Python 3.10.12, fastapi 0.110.0, httpx 0.27.0, pydantic 2.5.0, pytest 7.4.3 ->
`20 passed`** (deps pinned in `api/requirements-day45.txt`). But the completion target is an **in-memory list,
not PostgreSQL**, and a real Provider SDK/network, PostgreSQL/SQLAlchemy, Celery/Redis, Secret rotation/drain,
and production are **NOT RUN**.

### What the composition contains

| Section | Contents |
| --- | --- |
| Ownership | per-process: only processes that call the Provider create a client (8 Workers = 8 clients); a Provider client owns HTTP pools, not DB connections (Day47) |
| DI + scopes | lifespan owns app-scoped Settings/HTTP-client/ProviderAdapter; `Depends` supplies them (request-local cache, not a singleton); the short `GET /provider/status` route only resolves the Provider (a long Provider call belongs to a Worker); `JobService` is stateless per request/Job |
| Settings + secrets | validated `Settings` (`extra="forbid"`, `frozen`) with `SecretStr`; key from Settings, never a Router or Job payload; `safe_log_fields()` emits only allowlisted labels (`provider_name`/model/timeout/`settings_version`), never the `provider_base_url`; `SecretStr` hides display, is not encryption |
| Fail-fast startup | invalid local config -> `ValidationError` -> not ready, no claim; local validity != external availability; no paid generation call at startup |
| Lifespan + partial init | `create_app` + `asynccontextmanager`; publish `Container` only after full init; partial init closes the created client, publishes no readiness, claims no Job (reverse-order close) |
| Provider seam | small `AIProvider` protocol; `OpenAICompatibleAdapter` translates timeout/429/401-403/connection faults to stable `Provider*` errors over an injected transport (no real network; raises `NotImplementedError` without one — real SDK is Day53); `FakeAIProvider` for no-network/no-cost tests |
| Validation gate | a worker-style harness (not the HTTP route) validates raw Provider JSON via Day44 `StructuredAIResult.model_validate_json` before an in-memory completion; invalid output -> empty completion list |
| Rotation / drain / rollback | verify new Workers ready before draining old; shutdown = stop claims -> drain -> close; no blind requeue; code/config rollback != DB rollback |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day45.txt   # pydantic==2.5.0, pytest==7.4.3, fastapi==0.110.0, httpx==0.27.0
python3 -m py_compile day45_composition.py test_day45_composition.py
python3 -m pytest -q test_day45_composition.py
```

> **What this increment deliberately does not do:** the Provider call runs only in a worker-style harness (the
> HTTP route just resolves the Provider via `Depends`), and its completion target is an in-memory list, not a
> guarded PostgreSQL completion; it makes no real Provider/network call (a `FakeAIProvider` is injected, and the
> adapter's vendor-error translation is exercised over an injected transport — the real SDK is Day53), and runs
> no PostgreSQL/SQLAlchemy transactions, Celery/Redis Worker behavior, or deployment/Secret rotation/drain/
> production. `SecretStr` reduces accidental display but is not encryption. No real secrets, API keys,
> connection strings, or client data; the test key is an obviously-fake `sk-fake-...` placeholder that the
> tests assert is redacted/absent. Dependencies are pinned in `api/requirements-day45.txt`.

### Day45 known gaps (deliberate)

```text
Day46-48  SQLAlchemy mapping / transactional persistence / Alembic evolution (no ORM/public-model merge)
Day47     request-scoped AsyncSession/transaction/unit-of-work, distinct from the app-scoped Provider
Day50     idempotent Job + Outbox acceptance path attached to this composition
Day53     real OpenAI-compatible SDK behind this AIProvider seam
Day54-56  streaming/cancellation, Celery drain/ACK/recovery, retries/rate-limits/cost/backpressure
```

---

## Day44 increment — Pydantic v2 API and AI output contracts

`api/day44-pydantic-contracts-design.md` (with runnable `day44_pydantic_contracts.py` +
`test_day44_pydantic_contracts.py`) turns the Day43 static HTTP contract into **executable, typed** validation/
serialization boundaries. Unlike the earlier design-only artifacts, the Pydantic models and tests are **real,
executed code**: **Pydantic 2.5.0, pytest 7.4.3 -> `24 passed`** (deps pinned in `api/requirements.txt`). But structural validation is **not** authorization
and **not** a durable commit; the completion target in the tests is an **in-memory callback, not PostgreSQL**,
and FastAPI/auth/PostgreSQL/SQLAlchemy/real-Provider/integration/production are **NOT RUN**.

### What the contract contains

| Section | Contents |
| --- | --- |
| Boundary ladder | JSON-valid -> Pydantic-valid structure -> authenticated -> authorized -> app invariants -> PostgreSQL constraint + tx -> committed truth (Pydantic proves one rung) |
| Request models | `tenant_id` is trusted auth context (not a body field); `extra="forbid"`; discriminated union on `task_type` (summarize forbids / extract_structured requires `output_schema`) |
| Strict aliases | `MaxTokens`/`Confidence` strict + bounded (no `"2000"`/`"very sure"` coercion); no global strictness; conversions in a tested adapter |
| Provider output | fully untrusted `StructuredAIResult` (no Provider-owned `job_status`); shape validation != grounding |
| Public responses | allowlisted, status-discriminated (queued/running vs succeeded[result] vs failed[failure]); a failed Job is HTTP 200 |
| Public error envelope | `error.code`/`message`/`field_errors?`/`request_id?`; HTTP status is the class; never leak internals |
| Validation entry points | `model_validate`/`model_validate_json` for untrusted; `model_dump` to serialize; **never** `model_construct` on untrusted |
| Validate-before-side-effects | `validate_provider_output_before_completion` raises before the callback; the negative test asserts a `ValidationError` **and** no completion call |
| Incident runbook | the 37-Job `model_construct()` incident: contain / preserve evidence / roll back code / classify / audited repair; code rollback != DB rollback |

### Run the tests

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements.txt        # pydantic==2.5.0, pytest==7.4.3
python3 -m py_compile day44_pydantic_contracts.py test_day44_pydantic_contracts.py
python3 -m pytest -q test_day44_pydantic_contracts.py
```

> **What this increment deliberately does not do:** the completion target is an in-memory list, not a guarded
> PostgreSQL completion; it starts no FastAPI app/routing/serialization/exception handlers, runs no
> authentication/authorization, PostgreSQL uniqueness/transaction/commit/rollback/repair, SQLAlchemy/Alembic,
> real Provider SDK, or Relay/Worker/Redis/Object Storage. No real secrets, connection strings, or client data;
> identifiers are placeholders. Dependencies are pinned in `api/requirements.txt` (pydantic==2.5.0, pytest==7.4.3); the tested Pydantic version is 2.5.0 (not all Pydantic v2 releases were tested).

### Day44 known gaps (deliberate)

```text
Day45     DI, lifespan, settings/secrets boundary, and a Provider-adapter seam wire these models
Day46-48  SQLAlchemy mapping / transactional persistence / Alembic evolution (no ORM/public-model merge)
Day53     real Provider SDK structured-output parsing and validation
Day57-58  contract/integration/failure-injection tests + runtime observability
```

---

## Day43 increment — AI Job API contract (Phase 4 open)

`api/day43-ai-job-api-contract.md` exposes the Day42 durable data-ownership/failure model as a precise
multi-tenant AI Job HTTP API — as a **contract**, not a running application. It is a design pack: **every
route, status code, and payload is CONCEPTUAL / STATICALLY REVIEWED only — FastAPI / PostgreSQL / Relay-Worker /
Redis-Object-Storage-Provider / integration / production runtime NOT RUN.** Pydantic v2 (Day44),
DI/lifespan/provider adapters (Day45), SQLAlchemy/Alembic (Day46-48), durable cancellation (Day54), and Celery
(Day55) are not implemented here.

### What the contract contains

| Section | Contents |
| --- | --- |
| Commit-before-`202` boundary | return `202` only after one PostgreSQL tx commits Job + `(tenant_id, idempotency_key)` uniqueness + Outbox intent |
| Route / method / error / status matrix | `202`/`201`/`200`; `4xx` client contract; `409` same-key-different-input; `5xx` dependency outage; `404` vs `405` |
| Idempotency decision table | unique constraint + atomic create-or-return (not `SELECT`-then-`INSERT`); key bound to meaning; API vs Provider idempotency |
| Tenant isolation | `WHERE tenant + job_id`; cross-tenant `404` (no existence oracle); allowlisted public fields; a UUID is not authorization |
| HTTP vs durable lifecycle | short HTTP response vs Relay -> Worker claim -> Provider -> guarded completion; no 8-min wait; BackgroundTask != durable Worker |
| Outbox + guarded-claim gate | at-least-once duplicate delivery is normal; guarded `queued -> running` (1 row winner / 0 rows stop) is the first gate |
| Cancellation-intent boundary | `POST /cancel` durable audited intent ("requested, terminal outcome pending", a semantic `DELETE` does not express); `cancel requested != completed` |
| Integrated failure / rollback | T1-T6 sequence + the pre-`COMMIT`-`202` release rollback |

### Rules encoded

```text
an HTTP response is a PROMISE about COMMITTED business state; return 202 only after the Job + Outbox COMMIT
202 = durable async commitment (not completion); 201 = created (not a redirect); GET found = 200 + business status
4xx = client-contract failure; 409 = same key + different input; 5xx = dependency outage (never fake 404/202)
idempotency = (tenant_id, idempotency_key) UNIQUE + atomic create-or-return (NOT SELECT-then-INSERT); key bound to meaning
routing resolves method+path BEFORE handler/DB: 404 no route, 405 wrong method; static routes before dynamic
GET reads committed truth WHERE tenant + job_id; cross-tenant -> 404 (no existence oracle); allowlist public fields
HTTP lifecycle is short; durable work = Relay -> Worker claim -> Provider -> guarded completion; BackgroundTask != durable Worker
at-least-once duplicate is normal; guarded queued->running (1 row winner / 0 rows STOP) is the FIRST gate; fencing protects completion later
Artifact existence != success; cancel via POST /cancel (durable audited INTENT; semantics = "cancel requested, terminal outcome pending", not a resource DELETE); cancel requested != completed
rollback a pre-COMMIT-202 release: roll back the CODE + reconcile committed facts; an idempotent 202 for the SAME Job is fine
```

> **What this contract deliberately does not do:** it starts no FastAPI app/route, runs no PostgreSQL query/
> commit, Relay/Worker, Provider call, Object Storage access, or migration, and measures nothing. It does not
> implement Pydantic v2, DI/lifespan/provider adapters, SQLAlchemy/Alembic, the durable cancellation protocol,
> or Celery. No real secrets, connection strings, or client data; routes/IDs/status codes are static examples.

### Day43 known gaps (deliberate)

```text
Day44     typed Pydantic v2 request/response/error models formalize today's decisions
Day45     DI, lifespan, settings/secrets boundary, provider-adapter seam
Day46-48  SQLAlchemy mapping / transactional persistence / Alembic evolution (no ownership change)
Day54     durable cooperative cancellation protocol and terminal-transition mechanics
Day55     long-running durable Workers on a supported Celery broker transport
```

---

## Day42 increment — Backend Data Design Capstone (Phase 3 close)

`capstone-backend-data-design.md` closes Phase 3 by integrating the durable PostgreSQL truth (Day29-Day37),
the transient Redis coordination (Day38-Day41), and the Object Storage artifact boundary into **one**
failure-aware ownership, recovery, and verification contract for a multi-tenant AI Research and Automation
Platform. It is a design / evidence pack, not a running system: **every contract, key, and threshold is
CONCEPTUAL / STATICALLY REVIEWED only — RUNTIME NOT RUN, PRODUCTION NOT VALIDATED. `EXPLAIN ANALYZE` and
disposable-environment measurement are a described future method, not a performed result. SQLAlchemy/Alembic
are Phase 4 and are not implemented here.**

### What the capstone contains

| Section | Contents |
| --- | --- |
| Ownership + lifecycle map | PostgreSQL durable truth / Object Storage bytes / Redis losable coordination, per entity (Upload Session, Document, Job, Attempt, Event, Outbox, Result Artifact, cache/messages/counters/leases) |
| Acceptance contract | durable-at-202 = Job + `(tenant_id, idempotency_key)` uniqueness + Outbox intent in one transaction; Attempt/Event/lease/fencing appear later |
| Dispatch + duplicate | Relay publishes unpublished Outbox intents; at-least-once duplicates are normal; guarded `queued -> running` rejects the duplicate effect |
| Completion + reconciliation | short guarded transaction; verify identity/integrity/ownership + fencing equality + result before completing; Artifact-first + rollback -> reconcile, never blind delete/re-call |
| Failure / degraded matrix | Redis unhealthy / PostgreSQL down / input Object Storage down — scoped fail-closed |
| Upload contract | verify tenant ownership, verified state, non-expiry, registered key, hash/size, content-type/scan |
| Tenant / audit / retention | authenticated tenant predicate + composite tenant-aware FKs; append-only Events; tombstoned Artifact references |
| Performance evidence | disposable `EXPLAIN ANALYZE` method (not run); not production validation |
| Fencing migration | Expand -> Contract; strictly greater durable generation; drain/upgrade old Workers |
| Integrated recovery | failover + paused-Worker + Artifact reconciliation; contain + reconcile + guarded completion |

### Rules encoded

```text
PostgreSQL = single source of durable truth; Object Storage = verified bytes; Redis = transient, losable coordination
durable at 202 = Job + (tenant_id, idempotency_key) UNIQUE + Outbox intent (one tx); Attempt/Event/lease/fencing come later
dispatch = publish UNPUBLISHED Outbox intents; at-least-once duplicates normal; guarded queued->running rejects the effect
completion = short guarded tx guarded by running + current lease token + unexpired lease + fencing_generation = current PERSISTED generation
Artifact existence != success -> verify identity/integrity/ownership + fencing + Provider/result; reconcile on rollback, never blind delete/re-call
degrade by boundary: Redis unhealthy=fail-closed admission; PostgreSQL down=no new accepts; input Object Storage down=fail-closed THAT admission only
tenant safety = authenticated predicate + Job ID + composite tenant-aware FKs; a cache key is not authorization
audit = append-only; retention = tombstone Artifact reference + append artifact_expired/deleted; never edit history
performance = disposable EXPLAIN ANALYZE evidence (a method here, NOT run) != production validation
fencing = durable generation via Expand->Contract; drain/upgrade old Workers; lease expiry != a stop
recovery = contain + reconcile (Job/Attempt/Provider idempotency/Artifact) + guarded completion; never blind re-call, never Artifact-as-ownership
```

> **What this capstone deliberately does not do:** it starts no PostgreSQL/Redis/Object Storage/Provider/
> Celery/Relay/Worker/FastAPI, runs no migration and no `EXPLAIN ANALYZE`, and performs no failover/load/
> security/data-repair test. It does not implement SQLAlchemy/Alembic (Phase 4), a runnable rate limiter, a
> real Worker, real Object Storage integration, a real schema change, a real queue, a real Provider call, or a
> runtime test. No real secrets, connection strings, or client data. Every key/ID/threshold is a static example.

### Day42 known gaps (deliberate)

```text
Day43-58 (Phase 4)  turn this contract into a runnable FastAPI AI backend (SQLAlchemy/Alembic at Day46-48)
Phase 5-8           Playwright/n8n/agent/RAG/MCP/evaluation and the final capstone + portfolio
```

---

## Day41 increment — Redis coordination and production-safety design

`redis/redis-coordination-and-production-safety-design.md` uses Redis for **narrow, explicitly bounded**
coordination and protection (atomic admission, leases, stale-owner protection, failure windows, capacity
isolation, security) while **PostgreSQL remains the durable business authority**. It is a design / evidence
pack, not a running system and not an executed procedure: **every contract, command, limit, and threshold is
CONCEPTUAL / STATICALLY REVIEWED only — RUNTIME NOT RUN, PRODUCTION NOT VALIDATED. Redis is not promoted to
business truth and no exactly-once is claimed.**

### What the design contains

| Section | Contents |
| --- | --- |
| Ownership recap | PostgreSQL owns Job/Attempt/Event/Outbox truth; Redis coordination (admission/lease/fencing) is losable and not business truth |
| Rate-limit admission contract | atomic read -> limit decision -> INCR-if-allowed -> TTL -> allow/reject (one Lua step); admission != durable Job success; Lua vs MULTI/EXEC/WATCH |
| Algorithm decision table | clock-aligned fixed / first-write TTL / sliding window / token bucket by burst, fairness, cost, use case (token-bucket cap 10 refill 1/s example) |
| API idempotency boundary | client key + PostgreSQL `(tenant_id, idempotency_key)` uniqueness; separate API / Provider / notification identities |
| Lease safety model | `SET NX PX` + opaque token, renew, atomic compare-and-delete release, paused-owner timeline; expiry does not stop external work |
| Fencing model | a monotonic generation minted durably in a PostgreSQL claim/takeover tx (NOT a rollback-able Redis INCR); durable downstream rejects stale writes; generic rule `last_accepted_fence < incoming_fence`; distinct from an opaque lease token and from Provider idempotency |
| PostgreSQL completion guard | running + current lease token + unexpired lease + `fencing_generation` = the current persisted generation (equality); the generation is advanced/persisted in a PostgreSQL claim/takeover tx, extending Day34/Day37 |
| Redis loss/capacity matrix | RDB / AOF / async replication / failover / eviction / TTL as bounded protection degradation; isolate coordination capacity from cache |
| Security matrix | network boundary, auth, ACL command + `ratelimit:*` prefix least privilege, TLS, dangerous-command restriction, audit/monitoring |
| Integrated failure runbook | Redis unavailable vs recovered-with-lost-counters; API fail-closed admission; no Worker mass restart; drain/reconcile |

### Rules encoded

```text
Redis coordinates/protects; PostgreSQL Job/Attempt/Event/Outbox is the durable business authority
rate-limit decision = atomic read-modify-write (short Lua); NOT GET->check->SET, NOT INCR-then-DECR compensate
Lua is the atomic boundary; MULTI/EXEC can't decide from a prior external GET; don't nest MULTI/EXEC or wrap one command
Redis admission = an ALLOWED ATTEMPT, not durable Job success; don't compensate the counter (TTL resets)
durable acceptance = INSERT Job(queued) + INSERT Outbox(dispatch intent) -> COMMIT -> 202 + job_id
API idempotency = client key + PG UNIQUE (tenant_id, idempotency_key); API/Provider/notification identities are SEPARATE
a Redis lock reduces optional duplicate work; the PG unique constraint is the final Job-identity authority
lease expiry permits TAKEOVER; it does NOT stop a paused owner or an in-flight Provider call
safe release = atomic compare-and-delete (delete only if the stored token is mine); it cannot stop external work
fencing = MONOTONIC generation minted/persisted in a PostgreSQL claim/takeover tx (NEVER a rollback-able Redis INCR); a UUID token cannot fence
Job Complete guard = running + current lease token + unexpired lease + fencing_generation = the current PERSISTED generation (EQUALITY)
generic downstream fence (separate model): accept only last_accepted_fence < incoming_fence, then persist it
RDB/AOF/replication/failover/eviction can lose counters = TEMPORARY protection degradation; isolate from evictable cache
security = private net (necessary, not sufficient) + auth + ACL (command + ratelimit:* prefix) + TLS + deny FLUSHALL/CONFIG + audit
managed Redis runs infra, NOT business responsibility
outage: API fail-closed on new expensive admission; no Worker mass-restart; bounded backoff; drain + reconcile durable facts
```

> **What this design deliberately does not do:** it starts no Redis/Sentinel/Cluster/managed Redis, runs no
> `redis-cli`, Lua, `MULTI/EXEC`, `WATCH`, ACL, TLS, persistence, eviction, failover, rate limiter, FastAPI
> endpoint, PostgreSQL SQL, Provider, or Object Storage, and measures nothing. It does **not** promote Redis to
> business truth, does **not** claim exactly-once, and does **not** hand-build a broker or rate limiter. It
> contains no real secrets, connection strings, certificates, or client data. Every number (60/min, 30s,
> capacity 10, refill 1/s) is a static design example. PostgreSQL stays the durable source of truth.

### Day41 known gaps (deliberate)

```text
Day42        the integrated data ownership + failure + recovery + verification capstone
Phase 4      SQLAlchemy / Alembic; a real rate-limiter / broker / managed Redis is operated, not hand-rebuilt
```

---

## Day40 increment — Redis messaging and queue semantics design

`redis/redis-messaging-and-queue-semantics-design.md` defines how Redis **Lists**, **Pub/Sub**, and
**Streams** are used by their delivery/failure semantics for recoverable Job dispatch and notification
delivery, while PostgreSQL stays durable Job truth and idempotency makes redelivery safe. It is a design /
evidence pack, not a running queue and not an executed procedure: **every model, command, and contract is
CONCEPTUAL / STATICALLY REVIEWED only — RUNTIME NOT RUN, PRODUCTION NOT VALIDATED. Redis is not claimed to
provide exactly-once, and this is not a Celery replacement.**

### What the design contains

| Section | Contents |
| --- | --- |
| Ownership recap | PostgreSQL owns Job/Attempt/Event/Outbox/Notification truth; a Stream delivery (even an `XACK`) is transport state, not business completion |
| List vs Pub/Sub vs Streams | decision table by retained backlog (subject to Redis persistence/failover loss windows, Day38) / PEL / ACK / Claim / replay; Pub/Sub only for loss-tolerant notifications; Streams+Groups for recoverable dispatch |
| Small payload contract | references only (`tenant_id`, `job_id`, `event_id`, trace); Object Storage owns bytes; PostgreSQL owns references/provenance |
| Event lifecycle & topology | distinct committed events on distinct streams: Accept -> `job-dispatch` Outbox -> `ai:stream:job-dispatch:v1` -> `g:job-exec`; Complete -> `job.completed` Outbox -> `ai:stream:job-events:v1` -> `g:notify-delivery`; completion email driven only by a committed `job.completed` event, never a dispatch entry |
| PEL/ACK/Claim lifecycle | `XREADGROUP` -> PEL -> persist durable decision -> `XACK`; crash pre-ACK -> Pending -> `XCLAIM`/`XAUTOCLAIM` -> reconcile -> ACK |
| Delivery vs completion | at-most-once (early ACK, loses work) vs at-least-once (delayed ACK + idempotency); no exactly-once across ACK + commit + Provider |
| Per-side-effect idempotency | `job:{job_id}:notification:completion:v1`; completion/failure/admin are distinct; `job_id` alone is insufficient |
| Retry / quarantine | bounded retry -> durable quarantine/dead-letter -> alert -> repair producer -> controlled replay; ACK only after quarantine evidence; never silent delete |
| Safe trim / retention | trim is a retention/capacity contract; never trim Pending or recovery/quarantine evidence |
| Failure / recovery matrix | dual-crash recovery: preserve evidence -> inspect PostgreSQL -> reconcile -> per-group Claim -> ACK after durable decision |

### Rules encoded

```text
PostgreSQL owns Job/Attempt/Event/Outbox/Notification truth; a Redis delivery/ACK is transport, not completion
persist a durable, recoverable decision BEFORE XACK; early ACK = at-most-once = silent loss
at-least-once + idempotency is the default; Redis alone gives NO exactly-once across ACK + commit + Provider
Pub/Sub has no backlog/ACK/PEL/Claim/replay -> loss-tolerant notifications only; Streams+Groups are recoverable
Streams/Lists RETAIN a backlog subject to Redis persistence (RDB/AOF) + replication/failover loss windows (Day38);
  persistence reduces loss windows but Redis is NOT durable business truth -- PostgreSQL is authoritative
dispatch vs completion are DISTINCT committed events: Accept -> job-dispatch -> g:job-exec; Complete -> job.completed
  events -> g:notify-delivery; completion email is driven ONLY by a committed job.completed event, never a dispatch
  entry; one group -> one consumer per message, each group with its own PEL/ACK/Claim
stream append order = transport order; concurrent consumers != business-completion order (guard + idempotency)
Lists may persist but lack Consumer Group/PEL/ACK/Claim/redelivery; do NOT hand-build a Celery replacement
payloads carry small references; Object Storage owns bytes; PostgreSQL owns references/provenance
retry limit = capacity policy, NOT an error classifier; a bad immutable contract cannot self-heal
poison path: bounded retry -> durable quarantine/dead-letter -> alert -> repair producer -> controlled replay
trim = retention contract; NEVER trim Pending or recovery/quarantine evidence
each side effect (completion/failure/admin) needs its OWN delivery identity; job_id alone is insufficient
dual-crash recovery: preserve evidence -> inspect PostgreSQL -> reconcile -> per-group Claim -> ACK after decision
```

> **What this design deliberately does not do:** it starts no Redis or PostgreSQL, runs no Stream, Consumer
> Group, `XACK`, Claim, trim, Pub/Sub, List, Celery, Worker, Provider, or email integration, and measures
> nothing. It does **not** claim Redis provides exactly-once processing and does **not** hand-build a Celery
> replacement. It contains no real secrets, connection strings, tenant identifiers, or production data.
> PostgreSQL stays the durable source of truth.

### Day40 known gaps (deliberate)

```text
Day41        atomic composition (MULTI/EXEC, Lua), coordination, locks/leases + fencing, full rate limiting
Day42        the complete data ownership + failure + recovery/verification model
Phase 4      SQLAlchemy / Alembic; a production broker (e.g. Celery) is used as a broker, not hand-rebuilt
```

---

## Day39 increment — Redis cache consistency design

`redis/redis-cache-consistency-design.md` turns the Day38 ownership boundary into an explicit **per-endpoint
cache consistency contract**. It is a design / evidence pack, not a running cache and not an executed
procedure: **every contract, key, TTL, and threshold is CONCEPTUAL / STATICALLY REVIEWED only — RUNTIME NOT
RUN, PRODUCTION NOT VALIDATED.**

### What the design contains

| Section | Contents |
| --- | --- |
| Ownership recap | PostgreSQL COMMIT = authority; the cache is a rebuildable projection that may be stale/absent; a hit is not truth, a miss is not a Job failure |
| Cache-aside read | hit-if-tolerable / miss -> PostgreSQL + best-effort repopulate; a cache write failure never invalidates a correct response |
| Invalidation | commit FIRST, then invalidate EVERY affected view; the pre-commit re-cache race; invalidate-after-commit (not write-through guessed values) |
| Representation / versioning | incompatible change (progress 42 [0-100] -> 0.42 [0-1]) = new v-key; additive optional field = same version |
| TTL + jitter | fixed synchronized TTL = avalanche; jitter distributes expiry; single-flight is one hot key, not synchronized expiry |
| Stampede / single-flight / SWR | one leader + bounded followers + backoff/jitter; SWR for tolerant reads only |
| Fail-open vs fail-closed | `GET /progress` open; `POST /cancel` closed on PostgreSQL authorization + guarded write |
| Negative caching | short tenant-scoped; invalidate on creation; load protection, not a security control |
| Correctness metrics | commit->invalidation delay/failure/backlog, cache age, stale-terminal, Redis-vs-PostgreSQL agreement (not hit ratio alone) |
| Invalidation recovery | Outbox invalidation intent + retryable idempotent DEL; never redo a transition or Provider call |
| v2 incident | reconcile first; roll back the cache contract only on proven incompatibility; never PostgreSQL truth or Provider |

### Rules encoded

```text
PostgreSQL COMMIT = authority; the Redis cache is a rebuildable projection that may be stale or absent
a cache hit is not truth; a cache miss is not a Job failure
cache-aside: hit if tolerable; miss -> PostgreSQL + best-effort repopulate; a failed SET never fails a correct response
COMMIT first, then invalidate EVERY affected view (job-detail AND recent-completed); pre-commit delete re-caches stale
incompatible representation = new versioned key; additive optional field = same version
TTL + jitter prevents avalanche; single-flight protects ONE hot key, not a million distinct keys expiring together
hot reads: one single-flight leader + bounded followers + backoff/jitter; SWR for tolerant reads only
GET may fail open; sensitive POST fails closed on the guarded PostgreSQL write; a cache never authorizes
short tenant-scoped negative caching stops penetration; it is load protection, not a security control
a high hit ratio is not health; measure freshness/correctness, not hit ratio alone
invalidation recovery = Outbox intent + retryable idempotent DEL; never redo a transition or re-call the Provider
roll back the CACHE contract only on proven incompatibility; never committed PostgreSQL truth or Provider work
```

> **What this design deliberately does not do:** it starts no Redis or PostgreSQL, runs no cache API, Outbox
> Relay, Worker, Provider, or benchmark, and measures no latency, hit ratio, eviction, stampede, or hot key.
> It contains no real secrets, connection strings, tenant identifiers, or production data. Numbers (10s,
> 50,000, TTL/jitter ranges) are illustrative. PostgreSQL stays the durable source of truth.

### Day39 known gaps (deliberate)

```text
Day40        Redis messaging / queue semantics (Lists / Pub-Sub / Streams, consumer groups, redelivery)
Day41        atomic multi-command composition (MULTI/EXEC, Lua), coordination, full rate-limiting algorithms
Day42        the complete data ownership + failure + recovery/verification model
Phase 4      SQLAlchemy / Alembic
```

---

## Day38 increment — Redis acceleration-layer design

`redis/redis-acceleration-layer-design.md` adds Redis as *transient* acceleration around the durable
PostgreSQL truth. It is a design / evidence pack, not a runnable service and not an executed procedure:
**every key, command, structure, and threshold is CONCEPTUAL / STATICALLY REVIEWED only — RUNTIME NOT RUN,
PRODUCTION NOT VALIDATED.**

### What the design contains

| Section | Contents |
| --- | --- |
| Ownership model | PostgreSQL owns durable Job truth; Object Storage owns large bytes; Redis owns small, temporary, rebuildable acceleration + lightweight transport; a missing key is a cache-miss, not missing truth |
| Key contract | `ai:tenant:{tenant_id}:job-progress:v1:{job_id}` — tenant namespace + version; a version marks an incompatible change, not an additive field; logical DBs are a namespace, not isolation |
| Data-structure decision table | String / Hash / List / Set / Sorted Set chosen by access pattern; Hash vs JSON String for concurrent field updates; `INCR`/`HINCRBY` |
| TTL + multi-command boundary | TTL is a contract that a key may disappear; `HSET`+`EXPIRE` crash window; two-Worker `percent` race; single-command atomicity vs composition (Day41) |
| Memory / eviction | `maxmemory`/eviction as a correctness boundary — only rebuildable keys may be evicted |
| RDB / AOF | snapshot vs append loss windows; neither confers ownership |
| Redis-outage degradation | bounded PostgreSQL fallback within Day37 budgets; 202 still returned after the durable Accept |
| Missing-TTL incident | detect -> contain -> prefix-scoped SCAN -> TTL/cleanup -> verify; never `FLUSHALL`/`FLUSHDB` |

### Rules encoded

```text
PostgreSQL owns durable Job truth; Object Storage owns bytes; Redis owns rebuildable acceleration + transport
a missing Redis key is a cache-miss -> fall back to PostgreSQL, never fail the Job or re-call the Provider
no authoritative Job lifecycle under a TTL (a 24h TTL loses the Job at hour 25)
choose String/Hash/List/Set/Sorted Set by access pattern; a Hash beats a JSON String for concurrent fields
keys are tenant-namespaced + versioned; a version = an incompatible change, not an additive field
a single command is atomic; HSET+EXPIRE and a two-command read-modify-write are NOT (use HINCRBY / Day41 composition)
maxmemory/eviction is a correctness boundary: only rebuildable keys may be evicted
RDB/AOF shrink the loss window but never confer ownership
broker messages carry job_id + tenant_id + trace metadata, never truth and never large bytes; 202 after the durable Accept
a Redis outage degrades via a BOUNDED PostgreSQL fallback that protects the database
fix a missing-TTL leak with a config rollback + prefix-scoped cleanup, NEVER FLUSHALL
```

> **What this design deliberately does not do:** it starts no Redis server, runs no `redis-cli`, command,
> config, RDB/AOF file, cluster, or workload, and measures no latency, memory, throughput, or eviction. It
> contains no real secrets, connection strings, tenant identifiers, or production data, and invents no Redis
> version or benchmark. PostgreSQL stays the durable source of truth.

### Day38 known gaps (deliberate)

```text
Day39        Redis cache design and consistency (cache-aside, invalidation, stampede, fail-open/closed)
Day40        Redis messaging / queue semantics (Lists / Pub-Sub / Streams)
Day41        atomic multi-command composition (MULTI/EXEC, Lua), coordination, full rate limiting
Day42        capstone integrating PostgreSQL operation/recovery with Redis failure boundaries
Phase 4      SQLAlchemy/Alembic
```

---

## Day37 increment — production reliability runbook

`runbooks/postgresql-production-reliability.md` operates the durable PostgreSQL truth after Day36 made the
Lease-aware schema deployable. It is an operational **runbook / evidence pack**, not a SQL file and not an
executed procedure: **every command, number, and threshold is CONCEPTUAL / STATICALLY REVIEWED only —
RUNTIME NOT RUN, PRODUCTION NOT VALIDATED.**

### What the runbook contains

| Section | Contents |
| --- | --- |
| Connection-capacity worksheet | `sum(process pools) + reserve < safe budget < max_connections`; the `(4+12)*10 = 160` baseline; reserve for migration/monitoring/admin/recovery |
| Three Job transaction boundaries | Accept / Claim-Start / External (Provider outside any tx) / Complete guarded by job_status='running' AND current lease_token AND lease_expires_at > now() (not the token alone) |
| Timeout matrix | pool acquisition, `lock_timeout`, `statement_timeout`, `idle_in_transaction_session_timeout`, application deadline — scope, on-expiry, retry, observe |
| Health matrix | liveness vs readiness vs business success; shared-outage readiness drop + restart-storm prevention |
| Long-transaction / Vacuum procedure | root-cause-first incident order; evidence-based per-table autovacuum review; no casual `VACUUM FULL` |
| Least-privilege roles + rotation | runtime cannot DDL; separate runtime / migration / monitoring / backup-replication / WAL-archive / restore identities; load-new -> verify-all -> recycle -> revoke-old |
| Backup / PITR / restore drill | replication != backup; base backup + WAL -> PITR; RPO/RTO; isolated-restore recovery evidence |
| Monitoring matrix | connections/pool waits, queries, locks/deadlocks, transaction age/dead tuples, disk/WAL, replication lag, backup + tested-restore evidence |
| Replica-promotion gate | replay position + data-loss estimate + explicit RPO decision + split-brain prevention + reconciliation |
| 420-vs-300 incident | `12*25 + 12*10 = 420` vs `max_connections = 300`; contain + roll back pool config; reconcile irreversible Provider effects |

### Rules encoded

```text
reachable / low-CPU is NOT reliable; business ops depend on bounded capacity
sum every process's pool + reserve < safe connection budget < max_connections (a pool max is potential demand)
the 8-minute Provider call runs OUTSIDE the DB transaction; reconcile the deterministic Artifact before any re-call
timeouts contain failure: lock_timeout < statement_timeout < application deadline; SKIP LOCKED is claim selection
a shared DB outage drops READINESS + backs off; it must NOT fail every liveness (restart storm)
long/idle transactions retain snapshots -> block Vacuum -> dead-tuple bloat; fix the source first, no casual VACUUM FULL
runtime identities cannot DDL; rotate load-new -> verify-all -> recycle -> revoke-old
replication is NOT backup; recovery EVIDENCE = isolated restore + PITR + integrity/business checks + measured RPO/RTO
RPO/RTO are recovery objectives, not health probes
420-vs-300: contain demand + roll back the POOL CONFIG; reconcile irreversible Provider effects; resize the DB only on evidence
```

> **What this runbook deliberately does not do:** it does not pretend to be an automated executable, it
> contains no real secrets or connection strings, and it invents no command output, PostgreSQL version,
> managed-service behaviour, benchmark, plan, restore time, or RPO/RTO achievement. PostgreSQL stays the
> durable source of truth; Redis (Day38) is a future transient-state boundary. SQLAlchemy/Alembic are Phase 4.

### Day37 known gaps (deliberate)

```text
Day38-Day41  Redis foundations, cache consistency, messaging/queue semantics, and coordination — transient
             acceleration judged against this recoverable PostgreSQL truth
Day42        capstone integrating PostgreSQL operation/recovery evidence with Redis failure boundaries
Phase 4      SQLAlchemy/Alembic
```

---

## Day36 increment — safe-migration design pack

`sql/008_schema_evolution_and_safe_migrations.sql` evolves the **populated** Day31/Day34 `app.jobs` into a
recoverable, Lease-aware model. It is a migration **DESIGN + EVIDENCE** reference pack, not a runnable
script and not an executed migration: a migration is a versioned state transition across schema, existing
data, and every deployed application version, and a successful `ALTER` is not a completed migration.

### Phased plan (Expand -> Backfill -> Validate -> Switch -> Contract)

| Phase | What it does | Safety note |
| --- | --- | --- |
| 1. Expand | `ADD COLUMN claim_owner text, lease_token uuid, lease_expires_at timestamptz` — **nullable, no default** | old code ignores, new code tolerates NULL; even nullable `ADD COLUMN` is lock-aware; `NOT NULL` / `DEFAULT gen_random_uuid()` shown as commented **unsafe counter-examples** |
| 2. Compatible code | deploy new code that writes the columns and tolerates NULL (application step) | deploying a binary is **not** the Switch |
| 3. Drain old Workers | drain/isolate old Workers (operational step) | they bypass the token guard -> double execution / repeated Provider cost |
| 4. `NOT VALID` constraint | `CHECK (job_status <> 'running' OR all three Lease fields NOT NULL) NOT VALID` | enforces **new** writes immediately; historical rows unverified (`NOT NULL` itself cannot be `NOT VALID`) |
| 5. Backfill / recovery | bounded, idempotent, `SKIP LOCKED`, DB-checkpointed; target `job_status = 'running' AND lease_token IS NULL` | **trusted source only**; unknown ownership -> the exception/isolation queue is **triage, not resolution** (a parked row is still `running` + NULL, still counts in `remaining_targets`, still violates the invariant); it must be truthfully resolved by a trusted backfill or a real recovery, never a fake token/status; **no Provider calls** |
| 6. Validate | `VALIDATE CONSTRAINT jobs_running_requires_lease` after remediation | **precondition:** every legacy `running` row already has a trusted Lease, or was moved by a real recovery to a non-violating state — otherwise `VALIDATE` fails; scans the table; resource/lock-aware |
| 7. Switch | every writer uses the token guard | precondition: **old path can no longer write** |
| 8. Contract | remove temporary compatibility (commented; destructive) | only on evidence + observation period |
| Index | Day35 stale-lease index via `CREATE INDEX CONCURRENTLY` (commented) | **non-transactional** (no `BEGIN/COMMIT`); a failed build leaves an **invalid** (unusable) index |

### Rules encoded

```text
a migration is a versioned state transition; a successful ALTER is NOT a completed migration
Expand nullable, NO fabricated default; NULL honestly means "no proved Lease ownership"
a default is a business fact for every row; lease_token DEFAULT gen_random_uuid() fabricates ownership + rewrite risk
Backfill is running-only, but scope does NOT certify ownership; unknowable -> reconcile, never a fake token
the exception/isolation queue is TRIAGE, not resolution: a parked row still counts + still violates until truly resolved
remaining_targets = 0 counts only when every violating running row is truthfully resolved (trusted backfill or real recovery)
VALIDATE precondition: no violating running row remains; a queued-but-unresolved row would make VALIDATE fail
Backfill NEVER calls the Provider; migration/DB rollback cannot undo Provider cost or Object Storage bytes
drain old Workers BEFORE recovery/switch (they bypass the token guard)
target predicate repeated in selection + guarded write -> DB state is the checkpoint, not a process counter
CHECK ... NOT VALID protects new writes now; VALIDATE CONSTRAINT proves history after remediation
CREATE INDEX CONCURRENTLY is non-transactional and can leave an unusable invalid index; validity before net benefit
Switch = universal token guard AND the old path can no longer write; Contract is destructive, evidence-gated
rollback vs forward fix is decided by durable state; after real Lease data/external effects -> forward fix
```

> **What this pack deliberately does not contain:** no executed DDL, no `SQLAlchemy`/`Alembic` (Phase 4), no
> live operations (long transactions, Vacuum, pooling, backup/recovery — Day37), no cross-system fencing
> tokens (Day41). The safe DDL statements (nullable expand, `NOT VALID` constraint, `VALIDATE`) are design
> statements; `CREATE INDEX CONCURRENTLY`, the batched backfill, and the destructive Contract are commented
> because they are non-transactional / application-driven / evidence-gated.

### Validation reproduction (**NOT executed — Day36 has no runtime evidence**)

```bash
# NOTHING here was run in class or during the repository update: no PostgreSQL server, no ALTER, no
# constraint, no index build, no EXPLAIN, no backfill, no benchmark, no production DDL, no rollback.
# On a DISPOSABLE cluster, the phases would be applied by a migration runner in controlled windows,
# NOT as one transaction (CREATE INDEX CONCURRENTLY and the batched backfill are non-transactional).
```

### Day36 known gaps (deliberate)

```text
Day37   live operation of these boundaries: DDL locks, long transactions, WAL/transaction age, Vacuum,
        connection pooling, backup/recovery, slow-query and lock/connection monitoring, capacity
Day41   cross-system fencing tokens (stronger than the Lease token guard)
Phase 4 SQLAlchemy/Alembic migration tooling
```

---

## Day35 increment — index/EXPLAIN design pack

`sql/007_postgresql_indexes_and_query_planning.sql` turns the real Day33/Day34 access paths into candidate
B-tree index **designs** plus honest `EXPLAIN` evidence templates. It decides *which* index and *whether the
evidence justifies it*; it does **not** deploy a migration and makes **no runtime claims**.

### Index candidates (design only — NOT executed, NOT plan-validated)

The claim Partial Composite and the Outbox Partial are the two **active** `CREATE INDEX` design statements
(independent access paths on different tables). The three tenant-history candidates are **mutually
exclusive** and all **commented** in `007`: running the pack creates neither, and at most one is retained,
only after representative `EXPLAIN (ANALYZE, BUFFERS)` and net-benefit evidence (Section 8 rolls a broad
history index back).

| Access path | Candidate design | Notes |
| --- | --- | --- |
| Day34 Worker claim | `(tenant_id, created_at, job_id) WHERE job_status = 'queued' AND cancel_requested = false` | Partial Composite; tenant equality -> queue order; a `job_status`-only index is weak; speeds candidate lookup, not lock ownership |
| All-status tenant history | `(tenant_id, created_at DESC, job_id DESC)` | **commented candidate**; non-partial; a different path from the claim; `queued -> running` would NOT maintain it (keys unchanged) |
| Dynamic status-filtered history | `(tenant_id, job_status, created_at DESC, job_id DESC)` | **commented candidate**; shared composite vs several fixed-status partials — a trade, not a rule; measure. Its key includes `job_status`, so if retained, `queued -> running` MUST maintain it |
| Idempotency lookup | **none added** | Day31's `UNIQUE (tenant_id, idempotency_key)` already created a unique B-tree; a duplicate is pure cost |
| Unpublished Outbox poll | `(created_at, outbox_event_id) WHERE published_at IS NULL` | Partial on the tiny unsent set; `job_id` is selected but not a key |
| Stale-lease recovery | **conceptual/commented only** | `claim_owner`/`lease_token`/`lease_expires_at` do not exist (Day36); `now()` cannot be a partial predicate — stable "running" partial + query-time range |

### Rules encoded

```text
index = ADDITIONAL access structure over the Heap; FOR UPDATE SKIP LOCKED still locks the real tuple
design from the real WHERE + ORDER BY + LIMIT; B-tree order = equality predicates, then range / ORDER BY
a key serves an access path, not every SELECT-list column; the Heap supplies unindexed columns
a Partial Index that OMITS the target rows cannot answer the query (membership, not columns)
a UNIQUE constraint already builds a unique B-tree -> never duplicate the idempotency index
now() cannot be a partial predicate (membership changes only on a write) -> query-time range test
EXPLAIN estimates a plan; EXPLAIN ANALYZE EXECUTES it (row locks on SELECT FOR UPDATE, real DML changes)
Seq Scan is a cost-based plan and may be optimal; judge by selectivity / Rows Removed by Filter / buffers
estimate vs actual divergence -> statistics/skew investigation BEFORE another index
queued->running maintains only the claim partial index; history/idempotency keys unchanged
keep an index only for NET SYSTEM benefit; a read win that inflates acceptance p99 is a net loss
```

> **What this pack deliberately does not contain:** no `CREATE INDEX CONCURRENTLY`, no `ALTER`, no
> `DROP`/rollout mechanics, no migration, no ORM. The active `CREATE INDEX` statements are candidate
> **designs**; on a populated table a plain build takes a write-blocking lock, so the safe online build and
> rollout/rollback are **Day36**.

### Validation reproduction (**NOT executed — Day35 has no runtime evidence**)

```bash
# NOTHING here was run in class or during the repository update: no PostgreSQL server, no EXPLAIN,
# no EXPLAIN ANALYZE, no statistics refresh, no representative data, no benchmark, no DDL, no rollback.
# On a DISPOSABLE cluster you would inspect plans like this (EXPLAIN is plan-only and safe;
# EXPLAIN ANALYZE really executes and, on FOR UPDATE, takes row locks):
#
#   EXPLAIN
#   SELECT j.job_id FROM app.jobs AS j
#    WHERE j.tenant_id = $1 AND j.job_status = 'queued' AND j.cancel_requested = false
#    ORDER BY j.created_at ASC, j.job_id ASC
#    FOR UPDATE SKIP LOCKED LIMIT 1;
#
# Every plan number in the lesson (8M-row Seq Scan; estimate 1 vs actual 20,000; 100->80 / 50->220 / +14 GB)
# is a CLASSROOM SCENARIO for reasoning, not a measured result.
```

### Day35 known gaps (deliberate)

```text
Day36  safe online build/removal (CREATE INDEX CONCURRENTLY, DROP INDEX CONCURRENTLY), DDL-lock windows,
       rollout/rollback, and the migration that adds the conceptual lease columns
Day37  slow-query / lock / connection / Vacuum monitoring and production capacity
Day40+ Redis and the capstone reuse the measure-before-optimizing discipline
```

---

## Day34 increment — concurrency claim pack

`sql/006_concurrency_control_mvcc_and_worker_claims.sql` makes the Day33 atomic Start write safe under many
competing Workers. It is split into an **active** part and a **conceptual** part, and the split is the most
important thing to understand before running anything.

### Active (Day31 schema) vs conceptual (Day36 migration)

| Part | Status | Contents |
| --- | --- | --- |
| Part 1 — claim transaction | **ACTIVE** (driver-bound, Day31 columns only) | plain candidate `SELECT` (visibility); `FOR UPDATE SKIP LOCKED` reservation filtering `tenant_id` + `job_status = 'queued'` + `cancel_requested = false`; the unchanged Day33 guarded `queued->running` UPDATE that **re-checks** `cancel_requested = false` (the UPDATE is the final transition boundary); Attempt + `job_started` Event on the 1-row path; COMMIT before the Provider call; an optimistic alternative; consistent-lock-order + retry guidance |
| Part 2 — lease state machine | **CONCEPTUAL ONLY (commented, not runnable)** | `claim_owner` / `lease_token` / `lease_expires_at` claim/renew/takeover/completion pseudocode. These columns **do not exist** in the Day31 schema; adding them is a Day36 migration |

Do not uncomment Part 2 against the current schema — it will fail with "column does not exist." The lease
design is taught in comments precisely because no migration was performed.

### Rules encoded

```text
visibility (SELECT) != ownership (lock, then committed lease)
FOR UPDATE                     -> transaction-local row lock; a conflicting locker WAITS
FOR UPDATE SKIP LOCKED         -> skip locked rows, reserve the next AVAILABLE; Workers spread
claim eligibility = tenant_id + job_status = 'queued' + cancel_requested = false, ordered by created_at, job_id
  -> BOTH the FOR UPDATE SKIP LOCKED candidate SELECT and the guarded UPDATE filter cancel_requested = false
  -> the UPDATE repeats it DEFENSIVELY (direct-update / optimistic / future-refactor paths), NOT because a
     same-row cancel can commit between the locking SELECT and the UPDATE -- the SKIP LOCKED lock prevents that
  -> a committed-cancel queued Job must NOT be claimed by a new Worker
  -> cancel vs claim orderings:
       cancel commits first      -> the candidate SELECT excludes the Job (never claimed)
       cancel holds the lock      -> SKIP LOCKED skips that row and keeps scanning; MAY return another
                                     eligible Job, or 0 rows if none is available (then back off, no wait)
       claim locks first          -> the cancel transaction waits; after the claim COMMITs it re-evaluates
                                     under its own guarded policy (Day34 does not define that UPDATE)
claim = SKIP LOCKED reserve + unchanged Day33 guarded write + gate + COMMIT, THEN Provider (outside tx)
0 rows from SKIP LOCKED select -> no ELIGIBLE queued Job (locked, cancel-requested, or empty) -> back off (normal)
0 rows from guarded UPDATE      -> transition_not_applied -> ROLLBACK/stop (Day33 gate)
SKIP LOCKED weakens fairness     -> ORDER BY sorts only AVAILABLE rows; no strict FIFO; starvation possible
released lock != liveness        -> committed Job/Attempt/Event persist; blind reclaim duplicates
row lock (transaction-local)     != committed lease (owner + token + expiry; survives COMMIT; Day36 columns)
lease expiry = takeover condition (not death); takeover WRITES a new token; expiry alone does not
lease_token (ownership epoch)    != Provider idempotency key (stable per external operation)
40P01 deadlock / 40001 serialization -> PostgreSQL aborts one victim; the APPLICATION retries (finite, jittered)
consistent lock order prevents the cycle; lock_timeout bounds the wait (55P03); UNIQUE still stops duplicates
```

> **What this pack deliberately does not contain:** no `CREATE INDEX` or `EXPLAIN` (Day35); no `ALTER` or
> migration (Day36); no ORM / SQLAlchemy / Alembic; no Redis locking. It does **not** claim `SKIP LOCKED`
> gives strict FIFO, a complete snapshot, or eventual service of every row; it does **not** claim lease
> expiry proves a Worker died, changes its own token, revokes external work, or makes a Provider retry safe.

### Scope honesty

The claim reuses the exact Day33 write; concurrency is a wrapper, not a replacement. Locks and leases decide
**ownership**, `UNIQUE (job_id, attempt_number)` / `(tenant_id, idempotency_key)` decide **identity**, and a
stable Provider idempotency key protects the **external** call — none substitutes for another, and none
proves a Worker is alive.

### Validation reproduction (**final 006 NOT executed during this repository update**)

```bash
# The CLASSROOM concurrency tests used a REDUCED disposable schema, NOT the Day31 schema and NOT this file:
#   jobs(job_id text primary key, job_status text, created_at integer)
# Two real concurrent psql sessions on a disposable PostgreSQL 14.18 cluster reproduced:
#   1) Session A locks job-A; Session B runs the ordered queued query FOR UPDATE SKIP LOCKED -> returns job-B
#   2) Session B ordinary FOR UPDATE with lock_timeout=500ms while A holds job-A -> SQLSTATE 55P03
#   3) reverse-order lock A->B vs B->A -> SQLSTATE 40P01 deadlock; one victim aborted
#
# Illustrative SKIP LOCKED claim shape on the Day31 schema (bind $1; run on a DISPOSABLE cluster):
#   BEGIN;
#   SELECT job_id FROM app.jobs
#    WHERE tenant_id = $1 AND job_status = 'queued' AND cancel_requested = false
#    ORDER BY created_at ASC, job_id ASC
#    FOR UPDATE SKIP LOCKED LIMIT 1;
#   -- then the Day33 guarded UPDATE ... RETURNING (also re-checking cancel_requested = false),
#   -- gated on affected rows
#   COMMIT;
```

### Day34 known gaps (deliberate)

```text
Day35  measured indexes + EXPLAIN for the queued-claim / stale-lease / unpublished-Outbox access paths
Day36  the expand/backfill/validate/switch/contract migration that actually adds the lease columns
Day37  lock/deadlock/timeout monitoring, connection limits, production operations
Day41  the stronger cross-system fencing-token boundary
```

---

## Day33 increment — transactional write pack

`sql/005_postgresql_transactions_and_atomic_state_changes.sql` is a **driver-bound transaction reference
pack**, not DDL and not a runnable script: `$1`/`$2`/... are `PREPARE`/driver placeholders, not psql
variables. It reads and writes the Day31 model, so the apply order is `001_create_jobs.sql` ->
`003_...sql`, then bind and execute these transactions from an application.

It turns the Day32 read-side rule ("detect partial/missing related facts") into a write-side rule
("commit all related facts or none"), and it is a **write-path contract, not a schema guarantee**: it
protects only writers that use it.

### The three transactions and the external boundary

| Unit | Writes (all-or-nothing) | Boundary |
| --- | --- | --- |
| Transaction A — Accept | `app.jobs` INSERT + `app.outbox_events` **dispatch** intent (payload = stable ids/minimal refs only) | COMMIT **before** FastAPI returns `202 + job_id` |
| Transaction B — Start | guarded `queued -> running` UPDATE (with `attempt_count + 1`) + `app.job_attempts` + append-only `job_started` `app.job_events` | zero-row guard -> ROLLBACK / `transition_not_applied` |
| External phase | AI Provider request + Object Storage write | **NO open transaction**; the recovery anchor is the **pre-call** key = `attempt_id` (durable after B), sent to the Provider as its idempotency key; the Provider-**returned** `provider_request_id` is persisted only in C |
| Transaction C — Complete | Attempt finish **guarded by `finished_at IS NULL`** (records `provider_request_id`/cost) + guarded `running -> succeeded` UPDATE (sets `finished_at`) + `app.result_artifacts` + `job_succeeded` Event + **conditional** `job.succeeded` Outbox | any zero-row guard or constraint error -> ROLLBACK |
| Relay checkpoint | read `published_at IS NULL`, publish externally with the same `outbox_event_id`, then UPDATE `published_at = now()` after Queue ack | NOT a business transaction; concurrent claim is Day34 |

### Rules encoded

```text
Accept creates Job + dispatch Outbox together      -> creation-time coupling in Transaction A,
                                                      NOT a permanent Job<=>Outbox equivalence (retention archives)
202 acknowledges a durable commit                 -> return only AFTER COMMIT
guarded UPDATE ... RETURNING + control-flow gate   -> 0 rows is NORMAL; app must ROLLBACK and stop
attempt_count = attempt_count + 1 in the UPDATE    -> database-side increment, RETURNED as attempt_number
attempt_id is the pre-call recovery anchor         -> durable in B; provider_request_id (returned) only in C
Attempt-finish guarded by finished_at IS NULL      -> never overwrite a finished Attempt's recorded evidence
short transactions only                            -> never hold one across an 8-minute Provider call
external Provider / Object Storage OUTSIDE any tx  -> PostgreSQL cannot roll them back
Job Event = internal history; Outbox = external duty -> not every Event needs an Outbox row
Outbox row = durable intent + audit               -> Relay does not delete it or reset published_at to NULL
Outbox payload = stable ids + minimal refs only   -> no bytes, no secrets, no signed URLs
published_at NULL != no external publish           -> may be in-flight or crashed-before-write-back
at-least-once + stable outbox_event_id + idempotent consumer   -> exactly-once is NOT disabling retries
```

> **What this pack deliberately does not contain:** no `FOR UPDATE`, `SKIP LOCKED`, or MVCC isolation
> tuning (Day34); no indexes or `EXPLAIN` (Day35); no migrations / `ALTER` of populated tables (Day36);
> no ORM. The concurrent selection of unpublished Outbox rows is explicitly Day34.

### The zero-row control-flow contract

A SQL file cannot enforce "stop on zero rows" by comment alone. Each guarded `UPDATE ... RETURNING` in
`005` is followed by an explicit **CONTROL-FLOW CONTRACT** the driver must honour: 1 row returned means
continue; 0 rows means `transition_not_applied` — ROLLBACK and stop, because PostgreSQL treats zero
affected rows as a normal result and will otherwise run the next INSERT and corrupt the child rows.
Appendix A of the file gives a runnable pure-SQL demonstration (a `DO` block that `RAISE`s on a zero-row
transition) so the gate's behaviour is concrete on a disposable cluster.

### Correctness guards

- **Do not overwrite a finished Attempt.** Transaction C's Attempt-finish `UPDATE` carries
  `AND finished_at IS NULL`. Zero rows means the Attempt is missing, belongs to another Job, **or is
  already finished** — ROLLBACK and stop in every case. Overwriting a finished Attempt's `finished_at`,
  `provider_request_id`, or `cost_micros` would destroy recorded evidence. An already-finished current
  Attempt on a still-running Job is Day32's `running_with_finished_current_attempt`: it is **isolated and
  reconciled**, never auto-"fixed" to succeeded.
- **Recoverable Provider identity (two distinct ids).** The **pre-call** `provider_idempotency_key` /
  correlation key is generated before the request from an already-durable fact — use `attempt_id`
  (committed in Transaction B) — and, when the Provider supports idempotency keys, is sent with the
  request. It is the recovery anchor. The Provider-**returned** `provider_request_id` does not exist until
  the call returns and is persisted only in Transaction C; it is a lookup convenience. Transaction B does
  **not** persist a returned id. A crash after the call but before Transaction C loses `provider_request_id`,
  but `attempt_id` is already durable, so reconciliation can still find/deduplicate the call. If the
  Provider has no idempotency support, PostgreSQL cannot close this unknown-outcome window — isolate and
  reconcile, never blind-retry. **No schema change** is introduced: `attempt_id` already exists.
- **Job Event vs Outbox Event.** A `job_events` row is internal business history (one per state change). An
  `app.outbox_events` row is a pending external integration duty — created **only** when a real downstream
  consumer must be told. `job.accepted` has a real consumer (dispatch). The completion `job.succeeded`
  Outbox is **conditional**: `005` leaves it commented out because this project defines no consumer, and it
  must be enabled only alongside a concrete one. Outbox payload carries stable ids + minimal references
  only — no result bytes, no secrets, no signed URLs; the consumer fetches the authorized result via a
  stable reference; `outbox_event_id` is its idempotency key; publication is at-least-once and never proves
  consumer business success.

### Validation reproduction (**NOT executed during this repository update**)

```bash
# Requires the Day29 disposable cluster (see "Reproduce the Day29 validation" below) and
# 001 -> 003 applied to the FRESH, EMPTY disposable database.
# These are TEMPLATES: bind $1/$2/... with a driver, or wrap them in PREPARE/EXECUTE.
# The reduced CLASSROOM run (separate from this file) checked: Job+Outbox atomic commit;
# duplicate Outbox id rolling the Job back; running Job + Attempt + Event coherence;
# duplicate Artifact key rolling the completion back; the published_at NULL->timestamp checkpoint.

# Illustrative Accept transaction with fixed disposable UUIDs (NOT a psql copy-paste of $1):
psql -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
INSERT INTO app.jobs (job_id, tenant_id, idempotency_key, provider_metadata)
VALUES ('11111111-1111-1111-1111-111111111111',
        '22222222-2222-2222-2222-222222222222', 'idem-key-1', '{}'::jsonb);
INSERT INTO app.outbox_events (outbox_event_id, job_id, event_type, payload)
VALUES ('33333333-3333-3333-3333-333333333333',
        '11111111-1111-1111-1111-111111111111', 'job.accepted', '{}'::jsonb);
COMMIT;
SQL
```

### Day33 known gaps (deliberate)

```text
Day34  concurrent Worker/Relay claims: FOR UPDATE, SKIP LOCKED, MVCC, leases, deadlocks, fairness
Day35  measured indexes and execution plans for the claim / Outbox / query access paths
Day36  safe schema evolution (e.g. typed release/build provenance) of populated tables
Day37  roles/permissions that could restrict direct table writers (stronger than a write-path contract)
Future distributed delivery semantics beyond the at-least-once Outbox boundary
```

---

## Day32 increment — read-only operational queries

`sql/004_sql_joins_aggregation_and_operational_queries.sql` is a **read-only reference pack of
parameterized query templates**, not DDL and not a runnable script: `$1`/`$2`/`$3` are driver or
`PREPARE` placeholders, **not** psql `\set` variables. It reads the Day31 model, so the apply order is
`001_create_jobs.sql` -> `003_...sql`, then bind and execute these queries.

Every statement declares its **result grain** in a comment before the SQL, because the grain is the
meaning of the answer:

| # | Query | Grain | Notes |
|---|---|---|---|
| 1 | Job detail with optional Attempt rows | one row per Job-Attempt combination (0 Attempts -> one row, Attempt columns NULL) | Operational Job-Attempt view that preserves Jobs with no Attempt. `LEFT JOIN` keeps zero-Attempt Jobs visible; NULL Attempt columns mean "no Attempt row exists". **Filters on `tenant_id` only**, so it returns queued, running, succeeded, failed and cancelled Jobs — it is *not* backlog-only. A caller building a queue-only backlog view adds `AND j.job_status = 'queued'` explicitly. |
| 2a | Job-Attempt detail | one row per Job-Attempt combination | kept **separate** from 2b on purpose — joining both children in one statement multiplies rows |
| 2b | Job-Event detail | one row per Job-Event combination | same reason; combine only via pre-aggregated summaries (query 6) |
| 3 | Per-Job Attempt counts with conditional aggregation | one row per Job | `COUNT(a.attempt_id)` + `FILTER (WHERE a.error_code IS NOT NULL)`; `HAVING` applies the retry threshold |
| 4 | Tenant queue health by **acceptance** time | exactly one row | `COUNT(*)`, `MIN`/`MAX(created_at)`, `now() - MIN(created_at)` named `oldest_accepted_at` / `accepted_age_of_oldest_currently_queued_job`. `created_at` is acceptance, **not** current queued-stage entry. Empty queue returns count `0` and **NULL** age. |
| 4b | Current queued-**stage** age, with evidence state | one row per currently-queued Job | selects each Job's **latest event of any kind** (never pre-filtered to `queued`) and accepts it as the stage start only when `to_status = 'queued'`. `event_history_status` classifies: `recorded_queued_transition` (age meaningful), `no_event_history_acceptance_fallback` (no events at all — `jobs.created_at` used, age is an **upper bound**), `event_history_inconsistent` (events exist but the latest is not `queued` while the Job is — `queued_since` and `queued_stage_age` stay **NULL**, and no older queued event is substituted). Event-history completeness is a write-path convention, **not** a schema guarantee. |
| 5 | Per-Job recorded cost with completeness | one row per Job | `recorded_total_cost_micros` / `recorded_average_cost_micros` beside `cost_reported_attempts`; cost values deliberately **not** `COALESCE(..., 0)` |
| 6 | Per-Job Attempt + Event + cost summary | one row per Job | two CTEs pre-aggregate each child, so both joins are one-to-one and cannot multiply. Real **counts** are `COALESCE(..., 0)`; **cost** stays NULL. |
| 7 | Stage-aware stuck **candidates** | one row per `running` Job | current-Attempt clock selected with `DISTINCT ON (job_id) ... ORDER BY job_id, attempt_number DESC, attempt_id DESC`; `anomaly_class` classifies, it does not conclude |
| 8 | Terminal throughput in a half-open window | **exactly one summary row** | half-open `[start, end)` on `finished_at`, **plus** `job_status IN ('succeeded','failed','cancelled')` so that `terminal_jobs = succeeded_jobs + failed_jobs + cancelled_jobs` by construction |
| 9 | Affected set by release provenance | one row per Job | `SELECT DISTINCT e.job_id ... WHERE e.metadata ->> 'worker_release_id' = $2`; not a time-window proxy, and completeness is not schema-enforced |
| 10 | Incident evidence per Job | one row per Job | read-only **classification**: Attempt + artifact + outbox-publication evidence with an `evidence_class`. Real counts `COALESCE` to 0; cost stays NULL. Contains **no** repair. |

### Rules encoded

```text
LEFT JOIN where absence is evidence      -> a queued Job with no Attempt is the backlog, not noise
COUNT(child_pk), never COUNT(*)          -> COUNT(*) counts rows including the NULL-extended one
FILTER inside the aggregate              -> a WHERE predicate on a child collapses LEFT into INNER
WHERE before grouping / HAVING after     -> tenant + status in WHERE, thresholds in HAVING
recorded_* naming + completeness columns -> SUM/AVG describe RECORDS; NULL is unknown, not zero
CTE pre-aggregation per child            -> two independent 1:N children otherwise multiply (3 x 4 = 12)
DISTINCT ON + attempt_id tie-breaker     -> Day30 determinism rule; ties must not pick arbitrarily
half-open [start, end)                   -> BETWEEN double-counts boundary rows across windows
metadata ->> 'worker_release_id'         -> recorded provenance beats time correlation
deterministic ORDER BY on every query    -> stable, reviewable, paginable output
tenant_id = $1 on every tenant-scoped read -> AUTHORIZATION comes from server context, never the client
```

> **What this pack deliberately does not contain:** no `INSERT`/`UPDATE`/`DELETE`, no transactions, no
> locks (`FOR UPDATE`/`SKIP LOCKED`), no indexes, no `EXPLAIN`, no migrations, and no ORM. Those are
> Day33-Day36 and Phase 4. It is written for **meaning**, with no consideration of execution cost.

### Scope honesty

These queries produce **evidence and candidates, never verdicts**. Query 7 shows that no completion has
been *recorded* — not that a Provider call is dead. Query 10 classifies incident evidence and performs no
repair, because rollback stops future bad writes and does not undo committed rows, Provider charges, or
**already-published** outbox events.

### Validation reproduction (**NOT executed during this repository update**)

```bash
# Requires the Day29 disposable cluster (see "Reproduce the Day29 validation" below) and
# 001 -> 003 applied to the FRESH, EMPTY disposable database.
# These are TEMPLATES: bind $1/$2/$3 with a driver, or wrap them in PREPARE/EXECUTE.
# Pasting them straight into psql yields: ERROR: there is no parameter $1

day29psql -c "PREPARE backlog (uuid) AS
  SELECT j.job_id, a.attempt_id
  FROM app.jobs AS j
  LEFT JOIN app.job_attempts AS a ON a.job_id = j.job_id
  WHERE j.tenant_id = \$1
  ORDER BY j.created_at ASC, j.job_id ASC, a.attempt_number ASC;
EXECUTE backlog ('11111111-1111-1111-1111-111111111111');"
```

### Day32 known gaps (deliberate)

```text
Day33  were these facts written ATOMICALLY? (Job + Event + Outbox in one transaction)
Day34  MVCC, locking, SKIP LOCKED, leases -> turns a stuck CANDIDATE into proof
Day35  measured indexes and execution plans for exactly these access paths
Day36  safe schema evolution under these queries
Future RLS/roles as real authorization, backups, HA, performance, deployment
```

---

## Day31 increment — relational model and enforceable integrity

`sql/003_relational_modeling_and_data_integrity.sql` turns the single Day29 Job row into a relational
model. **Apply order on a fresh, empty database:** `001_create_jobs.sql` -> `003_...sql`
(`002_...sql` is a statement reference pack, not DDL).

> **Not a production migration.** The `ALTER TABLE app.jobs ADD COLUMN ... NOT NULL` statements have no
> default, so they succeed only while `app.jobs` is **empty**. Against existing rows they raise
> `23502 not_null_violation` and would need an expand -> backfill -> validate -> switch -> contract
> sequence. That mechanic is **Day36** and is deliberately not attempted here; no tenant or idempotency
> values are invented for historical rows.

### Entities and relationships

```text
tenants          1 -> N  upload_sessions, documents, jobs
upload_sessions  1 -> 0..1 documents        (FK + UNIQUE = optional one-to-one)
jobs             1 -> N  job_attempts, job_events, outbox_events
job_attempts     1 -> N  result_artifacts
jobs             N <-> N documents          (via job_documents, tenant-aware)
```

### Key rules encoded

| Rule | Constraint | Why |
|---|---|---|
| Request identity | `UNIQUE (tenant_id, idempotency_key)` on `jobs` | a retry gets a **new** `job_id`, so a `job_id` rule cannot stop duplicate business requests; different tenants may reuse a key |
| Attempt numbering | `UNIQUE (job_id, attempt_number)` | scoped to the Job — a global `UNIQUE(attempt_number)` would stop Job B from having its own Attempt 1 |
| Attempt sanity | `CHECK (attempt_number > 0)` | positive ordinals only |
| Legal states | `CHECK (job_status IN ('queued','running','succeeded','failed','cancelled'))` | `NOT NULL` accepts `''` and `banana`; `CHECK` guards every write path |
| Counter sanity | `CHECK (attempt_count >= 0)` | — |
| Terminal coherence | `CHECK (job_status <> 'succeeded' OR finished_at IS NOT NULL)` | a row CHECK sees only **this row**; it cannot assert a child Artifact exists (Day33) |
| One Document per session | `UNIQUE (upload_session_id)` on `documents` | FK + UNIQUE = one-to-one, recorded on the later-created row |
| Same-tenant Document provenance | composite FK `(tenant_id, upload_session_id)` -> `upload_sessions` | a single-column FK would only prove the session **exists**; this proves Document and session share a tenant |
| Same-tenant links | composite FKs `(tenant_id, job_id)` / `(tenant_id, document_id)` | plain FKs prove existence only, not shared ownership |
| Event provenance | composite FK `(job_id, attempt_id)` -> `job_attempts` | a non-NULL Attempt must belong to the **same** Job; NULL stays optional under MATCH SIMPLE |
| Evidence retention | `ON DELETE RESTRICT` everywhere | Attempts/Events/Artifacts hold audit and cost evidence that `CASCADE` would erase |

`result_artifacts` stores **`attempt_id` only** — `job_id` is derivable through `job_attempts`. Storing
both without a composite constraint would allow contradictory ownership. Denormalize only for a
**measured** problem, and then constrain the duplicate.

`jobs.result_object_key` (Day29) is now a **legacy** single-artifact pointer superseded by
`result_artifacts`. This file does **not** drop it — removing a column applications still read is Day36.

### Validation script (runnable in psql; **NOT executed during this repository update**)

No `psql` or PostgreSQL server was available in the repository-update environment, so the script below
was **authored, not run**. It is written to be **copy-paste runnable** against a **disposable** cluster
(see the Day29 reproduction section for a guarded disposable-cluster setup).

Two rules make it a real test rather than a decorative one:

- **Fixed test UUIDs**, not driver placeholders. `$1`/`$2` are *driver* parameters; pasting them into
  `psql` produces `ERROR: there is no parameter $1`.
- **Each expected failure asserts its specific condition.** A nested `EXCEPTION` block catches only the
  expected `unique_violation` / `check_violation` / `foreign_key_violation`. If the illegal statement
  unexpectedly **succeeds**, the block raises its own `P0001` and the script fails. Any other error
  (missing table, typo, wrong database) propagates and fails. "Any error = pass" would hide real bugs.

**Connect through the Day29 disposable helper — never a bare `psql`.** Complete the Day29
disposable-cluster startup first (section "Reproduce the Day29 validation"), which defines:

```text
day29psql() { psql -v ON_ERROR_STOP=1 -p "$DAY29_PGPORT" -h "$DAY29_PGHOST" -d ai_backend "$@"; }
```

That helper already carries the disposable **socket** (`$DAY29_PGHOST`), the disposable **port**
(`$DAY29_PGPORT`), the database **`ai_backend`**, and **`ON_ERROR_STOP=1`**. A bare `psql` does **not**
read `DAY29_PGHOST`/`DAY29_PGPORT`, so it would either fail to connect or silently connect to your
default PostgreSQL — never run these against a shared, development, or production database.

```bash
# Run from projects/ai-backend-data-layer/ AFTER the Day29 disposable cluster is running.
# Apply order on the FRESH, EMPTY disposable database:
day29psql -f sql/001_create_jobs.sql
day29psql -f sql/003_relational_modeling_and_data_integrity.sql

# Then run the validation script below (save it as /tmp/day31_validate.sql):
day29psql -f /tmp/day31_validate.sql
```

If you deliberately do **not** use `day29psql`, pass the disposable host, port and database explicitly on
every command (`psql -v ON_ERROR_STOP=1 -h <disposable-socket> -p <disposable-port> -d ai_backend -f ...`).
Never rely on the default connection.

#### Positive path — fixed UUIDs, all statements must succeed

```sql
-- Tenants
INSERT INTO app.tenants (tenant_id, tenant_slug) VALUES
    ('11111111-1111-1111-1111-111111111111', 'tenant-a'),
    ('22222222-2222-2222-2222-222222222222', 'tenant-b');

-- Upload sessions.
--   3333... Tenant A -> WILL receive a Document below (used by Test 10)
--   4444... Tenant B -> WILL receive a Document below
--   aaaa... Tenant A -> intentionally left WITHOUT a Document, reserved for Test 9 so the
--                       cross-tenant case is rejected by the composite FK (23503) and NOT by
--                       documents_upload_session_unique (23505).
INSERT INTO app.upload_sessions (upload_session_id, tenant_id, object_key) VALUES
    ('33333333-3333-3333-3333-333333333333',
     '11111111-1111-1111-1111-111111111111', 'tenant-a/uploads/doc-1'),
    ('44444444-4444-4444-4444-444444444444',
     '22222222-2222-2222-2222-222222222222', 'tenant-b/uploads/doc-1'),
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
     '11111111-1111-1111-1111-111111111111', 'tenant-a/uploads/doc-2-unused');

-- Documents (each bound to its OWN tenant's session)
INSERT INTO app.documents (document_id, tenant_id, upload_session_id, object_key) VALUES
    ('55555555-5555-5555-5555-555555555555',
     '11111111-1111-1111-1111-111111111111',
     '33333333-3333-3333-3333-333333333333', 'tenant-a/documents/doc-1'),
    ('66666666-6666-6666-6666-666666666666',
     '22222222-2222-2222-2222-222222222222',
     '44444444-4444-4444-4444-444444444444', 'tenant-b/documents/doc-1');

-- Jobs (Day31-compatible: tenant + client request identity are REQUIRED)
INSERT INTO app.jobs (job_id, tenant_id, idempotency_key) VALUES
    ('77777777-7777-7777-7777-777777777777',
     '11111111-1111-1111-1111-111111111111', 'req-001'),
    ('88888888-8888-8888-8888-888888888888',
     '22222222-2222-2222-2222-222222222222', 'req-002');

-- Attempt 1 of Tenant-A's Job
INSERT INTO app.job_attempts (attempt_id, job_id, attempt_number) VALUES
    ('99999999-9999-9999-9999-999999999999',
     '77777777-7777-7777-7777-777777777777', 1);

-- Same-tenant Job <-> Document link
INSERT INTO app.job_documents (tenant_id, job_id, document_id) VALUES
    ('11111111-1111-1111-1111-111111111111',
     '77777777-7777-7777-7777-777777777777',
     '55555555-5555-5555-5555-555555555555');

-- A DIFFERENT tenant may reuse the same idempotency key (scope includes tenant_id)
INSERT INTO app.jobs (tenant_id, idempotency_key) VALUES
    ('22222222-2222-2222-2222-222222222222', 'req-001');
```

#### Expected-failure cases — each asserts its own SQLSTATE

```sql
-- 1. Duplicate (job_id, attempt_number) -> 23505 unique_violation
DO $$
BEGIN
    BEGIN
        INSERT INTO app.job_attempts (job_id, attempt_number)
        VALUES ('77777777-7777-7777-7777-777777777777', 1);
        RAISE EXCEPTION 'VALIDATION FAILED: duplicate attempt_number was accepted';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'PASS: duplicate (job_id, attempt_number) rejected (23505)';
    END;
END $$;

-- 2. Non-positive attempt_number -> 23514 check_violation
DO $$
BEGIN
    BEGIN
        INSERT INTO app.job_attempts (job_id, attempt_number)
        VALUES ('77777777-7777-7777-7777-777777777777', 0);
        RAISE EXCEPTION 'VALIDATION FAILED: attempt_number = 0 was accepted';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'PASS: non-positive attempt_number rejected (23514)';
    END;
END $$;

-- 3. Attempt for a non-existent Job -> 23503 foreign_key_violation
DO $$
BEGIN
    BEGIN
        INSERT INTO app.job_attempts (job_id, attempt_number)
        VALUES ('00000000-0000-0000-0000-0000000000ff', 1);
        RAISE EXCEPTION 'VALIDATION FAILED: attempt for a missing Job was accepted';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'PASS: missing parent Job rejected (23503)';
    END;
END $$;

-- 4. Deleting a Job that still has an Attempt -> 23503 (ON DELETE RESTRICT)
DO $$
BEGIN
    BEGIN
        DELETE FROM app.jobs WHERE job_id = '77777777-7777-7777-7777-777777777777';
        RAISE EXCEPTION 'VALIDATION FAILED: deleting a Job with an Attempt was accepted';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'PASS: deleting a Job with Attempts restricted (23503)';
    END;
END $$;

-- 5. Same-tenant duplicate idempotency key -> 23505 unique_violation
DO $$
BEGIN
    BEGIN
        INSERT INTO app.jobs (tenant_id, idempotency_key)
        VALUES ('11111111-1111-1111-1111-111111111111', 'req-001');
        RAISE EXCEPTION 'VALIDATION FAILED: duplicate tenant idempotency key was accepted';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'PASS: same-tenant duplicate idempotency key rejected (23505)';
    END;
END $$;

-- 6. Illegal job_status -> 23514 check_violation
DO $$
BEGIN
    BEGIN
        UPDATE app.jobs SET job_status = 'banana'
        WHERE job_id = '77777777-7777-7777-7777-777777777777';
        RAISE EXCEPTION 'VALIDATION FAILED: job_status = banana was accepted';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'PASS: illegal job_status rejected (23514)';
    END;
END $$;

-- 7. Cross-tenant Job <-> Document link -> 23503 foreign_key_violation
DO $$
BEGIN
    BEGIN
        INSERT INTO app.job_documents (tenant_id, job_id, document_id)
        VALUES ('11111111-1111-1111-1111-111111111111',
                '77777777-7777-7777-7777-777777777777',
                '66666666-6666-6666-6666-666666666666');   -- Tenant B's Document
        RAISE EXCEPTION 'VALIDATION FAILED: cross-tenant Job-Document link was accepted';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'PASS: cross-tenant Job-Document link rejected (23503)';
    END;
END $$;

-- 8. Event pointing at ANOTHER Job's Attempt -> 23503 foreign_key_violation
DO $$
BEGIN
    BEGIN
        INSERT INTO app.job_events (job_id, attempt_id, event_type)
        VALUES ('88888888-8888-8888-8888-888888888888',   -- Tenant B's Job
                '99999999-9999-9999-9999-999999999999',   -- Tenant A's Job's Attempt
                'status_changed');
        RAISE EXCEPTION 'VALIDATION FAILED: event referencing another Job''s Attempt was accepted';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'PASS: event -> foreign Job Attempt rejected (23503)';
    END;
END $$;

-- 9. Cross-tenant Upload Session -> Document -> 23503 foreign_key_violation
--    (Tenant B Document claiming Tenant A's Upload Session.)
--    Uses the UNUSED Tenant-A session aaaa... on purpose: session 3333... already has a
--    Document, so PostgreSQL would raise documents_upload_session_unique (23505) during the
--    index insert BEFORE the foreign-key trigger ran. That would escape this handler, abort
--    the script, and silently skip Tests 10 and 11. With an unused session, the ONLY rule that
--    can reject this row is documents_upload_session_same_tenant_fk.
DO $$
BEGIN
    BEGIN
        INSERT INTO app.documents (tenant_id, upload_session_id, object_key)
        VALUES ('22222222-2222-2222-2222-222222222222',   -- Tenant B
                'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',   -- Tenant A's UNUSED session
                'tenant-b/documents/stolen');
        RAISE EXCEPTION 'VALIDATION FAILED: cross-tenant Upload Session -> Document was accepted';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'PASS: cross-tenant Upload Session -> Document rejected by documents_upload_session_same_tenant_fk (23503)';
    END;
END $$;

-- 10. A second Document for the SAME Upload Session -> 23505 unique_violation
--     Deliberately uses session 3333..., which ALREADY has a Document, and stays within
--     Tenant A so the composite FK is satisfied and documents_upload_session_unique is the
--     rule under test.
DO $$
BEGIN
    BEGIN
        INSERT INTO app.documents (tenant_id, upload_session_id, object_key)
        VALUES ('11111111-1111-1111-1111-111111111111',   -- same tenant: composite FK satisfied
                '33333333-3333-3333-3333-333333333333',   -- session that already has a Document
                'tenant-a/documents/second');
        RAISE EXCEPTION 'VALIDATION FAILED: a second Document for one Upload Session was accepted';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'PASS: one Upload Session -> at most one Document (23505)';
    END;
END $$;

-- 11. The ORIGINAL Day30 INSERT is incompatible after 003 -> 23502 not_null_violation
--     This asserts the documented incompatibility rather than advertising it as current usage.
DO $$
BEGIN
    BEGIN
        INSERT INTO app.jobs (provider_metadata) VALUES ('{}'::jsonb);
        RAISE EXCEPTION 'VALIDATION FAILED: pre-Day31 Job INSERT was accepted after 003';
    EXCEPTION WHEN not_null_violation THEN
        RAISE NOTICE 'PASS: pre-Day31 Job INSERT rejected after 003 (23502); use statement 1c';
    END;
END $$;
```

Every block prints `PASS: ...` on the expected outcome. Because `day29psql` carries `ON_ERROR_STOP=1` and no
trailing `echo` follows, the script's exit status **is** the validation result: a mis-typed table, a
missing constraint, or an illegal statement that unexpectedly succeeds all make it exit non-zero.

### Day31 known gaps (deliberate)

```text
Day32  joins/aggregation over these relationships (delivered: sql/004_...sql)
Day33  atomic Job + Event + Outbox changes in one transaction
Day34  MVCC, locking, SKIP LOCKED, leases, concurrency-safe claims
Day35  measured indexes for these access paths
Day36  safe evolution/backfill/removal of the legacy result_object_key column
Future RLS, production roles/permissions, backups, HA, performance, deployment
```

---

## Day30 increment — parameterized reads and guarded writes

`sql/002_job_crud_and_guarded_transitions.sql` is a **reference pack of statement templates**, not a
migration and not a runnable script: `$1`/`$2`/`$3` must be bound by an application or driver.

> **Schema compatibility (added by the Day31 update).** Statements **1** and **1b** create a Job
> without a tenant or a client request identity. They are valid only against the **Day29 base
> schema**; after `003` they fail with `23502 not_null_violation`. Statement **1c** is the
> Day31-compatible form — it supplies `tenant_id` and `idempotency_key` explicitly. After Day31
> there is **no** legal `DEFAULT VALUES` way to create a Job, because tenant ownership and request
> identity cannot be defaulted by the database. Statements 1/1b are preserved as the real Day30
> classroom record, not advertised as current usage; 1c is a **Day31 compatibility increment**, not
> something taught in the Day30 class.

A `SELECT` returns **result rows** and does not affect rows; only `INSERT`/`UPDATE`/`DELETE` carry an
**affected-row** contract. The table states which applies to each statement.

| # | Statement | Purpose | Expected row contract |
|---|---|---|---|
| 1 | `INSERT ... (provider_metadata) VALUES ($1::jsonb) RETURNING ...` | create a Job (**Day29 schema only**; `23502` after `003`) | **affected rows: exactly 1** |
| 1b | `INSERT ... DEFAULT VALUES RETURNING ...` | all-defaults variant (**Day29 schema only**; `23502` after `003`) | **affected rows: exactly 1** |
| 1c | `INSERT ... (tenant_id, idempotency_key, provider_metadata) ... RETURNING ...` | **Day31-compatible** Job creation (added by the Day31 update) | **affected rows: exactly 1** (or `23505` on a duplicate request) |
| 2 | deterministic queued `SELECT` | 20 oldest queued candidates | result rows: 0..20 |
| 3a | `WHERE finished_at IS NULL` | unfinished Jobs | result rows: 0..N |
| 3b | `WHERE error_message IS NULL OR error_message <> 'timeout'` | errors other than timeout, keeping no-error rows | result rows: 0..N |
| 3c | `WHERE error_message IS DISTINCT FROM 'timeout'` | NULL-safe alternative | result rows: 0..N |
| 4a | guarded `queued -> running` | worker start | **affected rows: 0 or 1** |
| 4b | guarded `running -> succeeded` (+ `result_object_key`) | worker completion | **affected rows: 0 or 1** |
| 5a | `SET attempt_count = attempt_count + 1` | database-side increment (no lost update) | **affected rows: 0 or 1** |
| 5b | `... WHERE attempt_count = $2` | optimistic expected-value guard | **affected rows: 0 or 1** |
| 6 | guarded cleanup `DELETE ... IN ('', 'banana')` | remove pre-cutoff test rows | **affected rows: 0..N** (reconcile first) |

Contracts and boundaries encoded in the file:

- **`WHERE` is the modification boundary.** Every transition carries both the identity (`$1`) and the
  required current state, so a terminal Job can never be restarted.
- **Zero rows means the transition did not apply** — it does **not** prove the Job is absent. The caller
  must not report success.
- **`RETURNING` returns rows, not a count.** Affected-row count evidence comes from the driver's command
  result or the number of rows received. A `SELECT` result count is **not** evidence of a data change —
  only `INSERT`/`UPDATE`/`DELETE` affect rows.
- **The candidate `SELECT` is not a claim.** Two workers see the same rows; concurrency-safe claiming
  (`FOR UPDATE`, `SKIP LOCKED`) is Day34 and is deliberately absent.
- **`$1` is PostgreSQL/asyncpg-style.** psycopg uses `%s`, SQLAlchemy uses named binds. Adapt the
  placeholder spelling; never build SQL from client input with string formatting.
- **Parameters bind values only** — identifiers and `ASC`/`DESC` require a strict allowlist.
- **`AND` binds tighter than `OR`**, so the cleanup uses `IN ('', 'banana')` instead of an
  unparenthesized chain that would delete every `banana` row regardless of date.

Deliberately **not** in this file: transactions, locking, `CHECK`/`UNIQUE`/foreign keys, indexes, Job
Event/Attempt tables, ORM, and any migration framework (Day31-Day35 and Phase 4).

---

## Reproduce the Day29 validation (disposable PostgreSQL)

These commands recreate **every** validation performed in class, in a **throwaway local cluster**.
No credentials, no shared database, no production connection string, no Docker.

> **Status of this section:** the commands below were **authored, not executed, during the repository
> update** — no `psql`, PostgreSQL server, or Docker daemon was available in that environment. They are
> a **static** reproduction procedure. The results quoted under "Verified in class" came from the live
> lesson (PostgreSQL 14.18) and are **classroom evidence only**. Run the steps yourself to reproduce them.

Run from this directory:

```bash
cd projects/ai-backend-data-layer
```

(Or run from the repository root and replace `sql/001_create_jobs.sql` with
`projects/ai-backend-data-layer/sql/001_create_jobs.sql`.)

### 1. Start a disposable cluster

The temporary directory uses a **task-specific fixed prefix** (`day29-pg.XXXXXX`) so cleanup can later
prove the path was created by this procedure. An existing `PGDATA` is never reused or overwritten.

```bash
# Fixed, identifiable prefix. This mktemp template form works on both macOS and Linux.
export DAY29_PG_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/day29-pg.XXXXXX")"
export DAY29_PGDATA="$DAY29_PG_ROOT/data"
export DAY29_PGPORT=5433
export DAY29_PGHOST="$DAY29_PG_ROOT/sock"
mkdir -p "$DAY29_PGHOST"
echo "Disposable cluster root: $DAY29_PG_ROOT"

initdb -D "$DAY29_PGDATA" >/dev/null
pg_ctl -D "$DAY29_PGDATA" -o "-p $DAY29_PGPORT -k $DAY29_PGHOST" -l "$DAY29_PG_ROOT/server.log" start

# A shell FUNCTION (not an alias) so it also works in non-interactive shells/scripts.
# ON_ERROR_STOP=1 makes any SQL error produce a reliable non-zero exit status.
day29psql() { psql -v ON_ERROR_STOP=1 -p "$DAY29_PGPORT" -h "$DAY29_PGHOST" -d ai_backend "$@"; }

createdb -p "$DAY29_PGPORT" -h "$DAY29_PGHOST" ai_backend
```

### 2. Apply the schema

```bash
day29psql -f sql/001_create_jobs.sql
```

### 3. Database-generated defaults

```bash
day29psql -c "INSERT INTO app.jobs DEFAULT VALUES RETURNING *;"
```

Expect `queued`, `0`, `false`, `{}`, a `created_at`, and NULL for `started_at`, `finished_at`,
`error_message`, `result_object_key`.

### 4. Session / namespace diagnostics

```bash
day29psql -c "\conninfo"
day29psql -c "SELECT current_database(), current_user, current_schema();"
day29psql -c "SHOW search_path;"
day29psql -c "\dn"
day29psql -c "\dt app.*"
```

The session connects to the **database**; `app.jobs` resolves through explicit qualification even though
`app` is not in `search_path`.

### 5. NOT NULL rejects NULL — precise assertion of the expected error

This step **asserts a specific PostgreSQL error condition**, `not_null_violation` (SQLSTATE 23502). It is
**not** "any non-zero exit counts as a pass". A nested `EXCEPTION` block catches only that one condition:

- expected `not_null_violation` -> `NOTICE: PASS` and the command exits **0**;
- the INSERT unexpectedly **succeeding** -> the block raises its own exception, so the step **fails**;
- any other failure (missing table `undefined_table`, syntax error, connection refused, wrong database)
  is **not** caught, propagates, and the step **fails** — it is never reported as a pass.

```bash
day29psql <<'SQL'
DO $$
BEGIN
    BEGIN
        INSERT INTO app.jobs (job_status) VALUES (NULL);
        -- Reached only if the NOT NULL constraint did NOT reject the row.
        RAISE EXCEPTION
            'VALIDATION FAILED: NULL job_status was accepted; the NOT NULL constraint is missing';
    EXCEPTION
        WHEN not_null_violation THEN
            RAISE NOTICE 'PASS: NULL job_status rejected with not_null_violation (SQLSTATE 23502)';
    END;
END
$$;
SQL
```

`day29psql` is deliberately the **last command in the block**, so the block's exit status *is* the
verification result — nothing after it can mask a failure:

| Outcome | Exit status |
|---|---|
| Expected `not_null_violation` (SQLSTATE 23502) | **0** |
| NULL unexpectedly accepted (`P0001` raised by the block) | non-zero |
| Missing table, syntax error, wrong database, connection refused | non-zero |

The custom `RAISE EXCEPTION` uses SQLSTATE `P0001`, which the handler does **not** catch, so an
unexpectedly successful INSERT reliably fails the step. Because the exception aborts the block, no row is
left behind. (Do **not** append `echo "exit status: $?"` here: `echo` returns 0 and would overwrite the
real status. If you must print it, capture `rc=$?` first, print, then `return`/`exit "$rc"` explicitly —
never an unconditional `exit` in an interactive shell.)

### 6. NOT NULL does NOT enforce business validity — these SUCCEED (the known gap)

```bash
day29psql -c "INSERT INTO app.jobs (job_status) VALUES ('') RETURNING job_id, job_status;"
day29psql -c "INSERT INTO app.jobs (job_status) VALUES ('banana') RETURNING job_id, job_status;"
```

Both are accepted — durability is not integrity. A `CHECK`/enum rule is Day31 work.

### 7. timestamptz is one absolute instant

```bash
day29psql -c "SET TIME ZONE 'UTC';           SELECT job_id, created_at, extract(epoch FROM created_at) AS epoch FROM app.jobs ORDER BY created_at LIMIT 1;"
day29psql -c "SET TIME ZONE 'Asia/Shanghai'; SELECT job_id, created_at, extract(epoch FROM created_at) AS epoch FROM app.jobs ORDER BY created_at LIMIT 1;"
```

Different rendering, identical `epoch`.

### 8. Guarded data repair (the `queud` drill)

```bash
# Simulate the bad release writing a misspelled status.
day29psql -c "INSERT INTO app.jobs (job_status) SELECT 'queud' FROM generate_series(1,3);"

# Baseline counts.
day29psql -c "SELECT job_status, count(*) FROM app.jobs GROUP BY job_status ORDER BY job_status;"

# GUARDED repair: narrow WHERE, and capture evidence via RETURNING.
day29psql -c "UPDATE app.jobs SET job_status = 'queued' WHERE job_status = 'queud' RETURNING job_id;"

# Post-repair counts (verify the repair scope).
day29psql -c "SELECT job_status, count(*) FROM app.jobs GROUP BY job_status ORDER BY job_status;"
```

The reported row count plus `RETURNING` are the evidence. Never run an unguarded `UPDATE`.

### 9. Restart persistence

```bash
day29psql -c "SELECT count(*) AS before_restart FROM app.jobs;"
pg_ctl -D "$DAY29_PGDATA" -m fast restart -l "$DAY29_PG_ROOT/server.log"
day29psql -c "SELECT count(*) AS after_restart FROM app.jobs;"
day29psql -c "SELECT job_status, count(*) FROM app.jobs GROUP BY job_status ORDER BY job_status;"
```

This proves **local process-lifecycle persistence only** — not backup recovery, high availability, or
crash durability under hardware failure.

### 10. Clean up (identity-verified before any recursive delete)

A non-empty variable pointing at an existing directory is **not** proof that the path belongs to this
procedure — an overwritten variable could still name something important. The guard below therefore
**verifies the identity of the path** before `pg_ctl stop` or `rm -rf` touches anything:

1. `DAY29_PG_ROOT` matches the task-specific `day29-pg.XXXXXX` prefix created in step 1;
2. it is not `/`, `$HOME`, or the current working directory;
3. `DAY29_PGDATA` is exactly `$DAY29_PG_ROOT/data`;
4. `$DAY29_PGDATA/PG_VERSION` exists (i.e. it really is a PostgreSQL data directory).

If **any** check fails, cleanup is refused with a clear message and nothing is deleted or stopped.

Deletion is additionally gated on PostgreSQL having actually stopped. The shell does **not** abort on a
non-zero `pg_ctl` status by default, so the steps are chained with explicit `if`/`else` rather than
sequential commands — a stop failure or timeout must never be followed by `rm -rf` on a data directory
that may still be in use. Diagnostic variables are cleared **only** on full success.

```bash
day29_cleanup_guard() {
    [ -n "${DAY29_PG_ROOT:-}" ]  || { echo "REFUSING cleanup: DAY29_PG_ROOT is unset/empty." >&2; return 1; }
    [ -n "${DAY29_PGDATA:-}" ]   || { echo "REFUSING cleanup: DAY29_PGDATA is unset/empty." >&2; return 1; }
    case "$DAY29_PG_ROOT" in
        */day29-pg.??????) : ;;
        *) echo "REFUSING cleanup: '$DAY29_PG_ROOT' does not match the day29-pg.XXXXXX prefix." >&2; return 1 ;;
    esac
    [ "$DAY29_PG_ROOT" != "/" ] && [ "$DAY29_PG_ROOT" != "$HOME" ] && [ "$DAY29_PG_ROOT" != "$PWD" ] \
        || { echo "REFUSING cleanup: '$DAY29_PG_ROOT' is /, \$HOME, or the current directory." >&2; return 1; }
    [ -d "$DAY29_PG_ROOT" ] || { echo "REFUSING cleanup: '$DAY29_PG_ROOT' is not a directory." >&2; return 1; }
    [ "$DAY29_PGDATA" = "$DAY29_PG_ROOT/data" ] \
        || { echo "REFUSING cleanup: DAY29_PGDATA is not \$DAY29_PG_ROOT/data." >&2; return 1; }
    [ -f "$DAY29_PGDATA/PG_VERSION" ] \
        || { echo "REFUSING cleanup: no PG_VERSION in '$DAY29_PGDATA' — not a cluster made by this procedure." >&2; return 1; }
    return 0
}

# Printed on every refusal so the cluster can be inspected and removed by hand.
day29_report_vars() {
    {
        echo "  Preserved for diagnosis (NOT unset):"
        echo "    DAY29_PG_ROOT=${DAY29_PG_ROOT:-<unset>}"
        echo "    DAY29_PGDATA=${DAY29_PGDATA:-<unset>}"
        echo "    DAY29_PGPORT=${DAY29_PGPORT:-<unset>}"
        echo "    DAY29_PGHOST=${DAY29_PGHOST:-<unset>}"
        echo "    server log:   ${DAY29_PG_ROOT:-<unset>}/server.log"
    } >&2
}

day29_cleanup() {
    # Gate 1: path identity.
    if ! day29_cleanup_guard; then
        echo "REFUSING cleanup: guard failed. Nothing was stopped or deleted." >&2
        day29_report_vars
        return 1
    fi

    # Gate 2: PostgreSQL must actually stop before anything is removed.
    if ! pg_ctl -D "$DAY29_PGDATA" -m fast stop; then
        echo "REFUSING delete: pg_ctl stop failed or timed out." >&2
        echo "  The data directory may still be in use; it was NOT removed." >&2
        day29_report_vars
        return 1
    fi

    # Gate 3: the delete itself must succeed (and the directory must really be gone).
    rm -rf -- "$DAY29_PG_ROOT"
    rc=$?
    if [ "$rc" -ne 0 ] || [ -e "$DAY29_PG_ROOT" ]; then
        echo "REFUSING to report success: rm -rf failed (status $rc) or the path still exists." >&2
        day29_report_vars
        return 1
    fi

    # Only now is it true that the cluster is stopped and the directory is gone.
    echo "Removed disposable cluster: $DAY29_PG_ROOT"
    unset DAY29_PG_ROOT DAY29_PGDATA DAY29_PGPORT DAY29_PGHOST
    # Remove every helper, including this function itself. Both bash and zsh allow a
    # running function to unset its own definition; the current call still completes.
    unset -f day29psql day29_cleanup_guard day29_report_vars day29_cleanup 2>/dev/null
    return 0
}

day29_cleanup
```

Cleanup outcomes:

| Branch | `pg_ctl stop` | `rm -rf` | Message | Variables + helpers | Exit status |
|---|---|---|---|---|---|
| Guard failed | not run | not run | `REFUSING cleanup` | **preserved + printed** | non-zero |
| Stop failed/timed out | failed | **not run** | `REFUSING delete` | **preserved + printed** | non-zero |
| Delete failed | ok | failed / path remains | `REFUSING to report success` | **preserved + printed** | non-zero |
| Full success | ok | ok, path gone | `Removed disposable cluster: ...` | **all cleared** (vars + 4 helpers) | 0 |

Success is reported **only** after the directory is verifiably gone. On full success the shell is left
clean: all four `DAY29_*` variables and **all four helper functions** (`day29psql`,
`day29_cleanup_guard`, `day29_report_vars`, and `day29_cleanup` itself) are removed — no manual
follow-up step is needed. On any failure the variables **and** the helpers are kept so you can inspect
the cluster and re-run `day29_cleanup` after fixing the cause.

Docker was **not** used and is **not** validated: the Docker CLI existed during class but the daemon was
not running. Do not present a Docker workflow as verified.

---

## Validation matrix

| Level | Day29 status | Evidence |
|---|---|---|
| Conceptual / manual review | **Done** | Responsibility, type, NULL/DEFAULT, identity, and repair reasoning reviewed in class |
| SQL syntax / DDL acceptance | **Done (PostgreSQL 14.18)** | `CREATE SCHEMA` + `CREATE TABLE app.jobs` executed successfully |
| Real disposable-PostgreSQL behavior | **Done (selected behaviors)** | defaults, NOT NULL rejection, timestamptz rendering, guarded repair, restart persistence (below) |
| Re-run during this repository update | **NOT RUN** | no `psql`/PostgreSQL server/Docker daemon was available in the repository-update environment |
| Application integration (FastAPI/Celery) | **NOT DONE** | no service was created or connected |
| Production validation | **NOT DONE** | no deployment, HA, backup/restore, or load evidence |

### Day30 (`002_job_crud_and_guarded_transitions.sql`)

| Level | Day30 status | Evidence |
|---|---|---|
| Conceptual / manual review | **Done (in class)** | clause chain, NULL logic, parameter boundary, guarded transitions, affected rows, lost update, incident order |
| Static file review | **Done (repository update)** | balanced parens/quotes; 11 statements; every DML has `RETURNING`; guards use `= 'queued'` / `= 'running'`; `DELETE` uses `IN (...)`; only `$1`/`$2`/`$3` parameters; no transactions, locks, constraints, indexes, or DDL; no credentials |
| PostgreSQL parser / syntax execution | **NOT RUN** | no `psql`/PostgreSQL server was available in class or in the repository-update environment |
| Real disposable-PostgreSQL behavior | **NOT RUN** | — |
| Python-driver parameter binding | **NOT RUN** | no application or driver was executed |
| FastAPI / Celery / Object Storage integration | **NOT RUN** | — |
| Transaction / concurrency runtime test | **NOT RUN** | outside Day30 scope (Day33/Day34) |
| Production validation | **NOT RUN** | — |

> The Day29 PostgreSQL 14.18 classroom evidence below belongs to `001_create_jobs.sql` only. It is
> **not** evidence for the Day30 statements.

### Day44 (`api/day44-pydantic-contracts-design.md` + code/tests)

| Level | Day44 status | Evidence |
|---|---|---|
| Conceptual classroom validation | **Completed** | the boundary ladder, request/response/error/Provider contracts, strict types, discriminated unions, validation entry points, validate-before-side-effects, and the 37-Job incident reasoned end to end |
| Static contract review | **Completed** | static review of the model map and the boundary separation (structure vs authorization vs durable commit) |
| **Pydantic v2 runtime (executed)** | **RUN — 24 passed** | after tightening per review (restricted output_schema, UUID upload_session_id/job_id, AnyHttpUrl citation, strict required MaxTokens 1..8000, and a shared summary contract min_length=1/max_length=10_000 reused by the public result), the suite grew from the classroom's 11 to 24: `pip install -r requirements.txt` then `py_compile` passed and `pytest -q` -> **24 passed** (Python 3.10.12, Pydantic 2.5.0, pytest 7.4.3, pinned in requirements.txt) |
| Completion target | **IN-MEMORY ONLY** | the tests use an in-memory list callback, **not** a guarded PostgreSQL completion |
| FastAPI / auth / integration runtime | **NOT RUN** | no FastAPI app/routing/serialization/exception handlers; no authentication/tenant authorization; no integration |
| PostgreSQL / SQLAlchemy / Provider runtime | **NOT RUN** | no PostgreSQL uniqueness/transaction/commit/rollback/repair; no SQLAlchemy/Alembic; no real Provider SDK; no Relay/Worker/Redis/Object Storage |
| Production validation | **NOT RUN** | not deployed; no production accessed; the tested Pydantic version is 2.5.0 (not all v2 releases) |

### Day43 (`api/day43-ai-job-api-contract.md`)

| Level | Day43 status | Evidence |
|---|---|---|
| Conceptual classroom validation | **Completed** | one multi-tenant AI Job scenario reasoned end to end: commit-before-202, status/error classification, idempotent create-or-return, routing, tenant reads, HTTP-vs-durable lifecycle, the guarded-claim gate, cancellation intent, and the integrated failure/rollback |
| Static contract review | **Completed** | static review of the acceptance boundary, the route/error/status matrix, the idempotency table, tenant isolation + allowlist, the lifecycle boundary, the guarded-claim gate, the cancellation-intent boundary, and the T1-T6 + rollback exercise over the Day42 model |
| FastAPI runtime | **NOT RUN** | no FastAPI app, route, endpoint, or TestClient was executed; routes/status codes are static examples |
| PostgreSQL runtime | **NOT RUN** | no query, commit, uniqueness, or Outbox write executed |
| Relay / Worker runtime | **NOT RUN** | no Relay scan, guarded claim, or Worker execution |
| Redis / Object Storage / Provider runtime | **NOT RUN** | no cache, queue, Object Storage access, or Provider call |
| Integration / production validation | **NOT RUN** | not deployed; no production accessed; Pydantic v2/DI/SQLAlchemy/Alembic/cancellation/Celery are future boundaries |

### Day42 (`capstone-backend-data-design.md`)

| Level | Day42 status | Evidence |
|---|---|---|
| Conceptual classroom validation | **Completed** | one evolving multi-tenant AI Job scenario reasoned end to end: ownership/acceptance, dispatch/duplicate, completion/Artifact reconciliation, degraded modes, upload contract, tenant/audit/retention, performance-evidence method, fencing migration, and integrated recovery |
| Static reasoning review | **Completed** | static review of the durable-at-202 anchor, the guarded transition, the short guarded completion + fencing-equality guard, the scoped fail-closed degraded modes, composite tenant-aware FKs, append-only audit/tombstone retention, and the Expand->Contract fencing rollout, integrating Day29-Day41 |
| Artifact syntax / runtime validation | **NOT RUN** | no PostgreSQL, Redis, Object Storage, Provider, Celery/Relay/Worker, or FastAPI command was executed; SQL-shaped and key-shaped examples are read for shape and naming only |
| Disposable PostgreSQL/Redis validation | **NOT RUN** | no migration and no `EXPLAIN ANALYZE` were run; the performance-evidence method is described, not performed |
| Failover / load / security / data-repair drill | **NOT RUN** | no failover, load, security, or data-repair test was executed |
| Application / integration validation | **NOT RUN** | no queue, Worker, Provider call, Object Storage integration, or FastAPI endpoint; SQLAlchemy/Alembic are Phase 4 |
| Production validation | **NOT RUN** | no production accessed; every key/ID/threshold is a static design example |

### Day41 (`redis/redis-coordination-and-production-safety-design.md`)

| Level | Day41 status | Evidence |
|---|---|---|
| Conceptual classroom validation | **Completed** | one evolving multi-Pod AI Job admission + Worker lease + Redis-failure scenario reasoned end to end: admission race, atomic Lua, admission-vs-success, algorithms, API idempotency, lease/safe-release, fencing, loss/capacity, security/ACL, managed responsibility, and integrated failure |
| Static reasoning review | **Completed** | static review of atomicity vs Lua/MULTI/EXEC/WATCH scope, rate-limit algorithm semantics (incl. the 120-request boundary burst and the capacity-10/refill-1/s rejection), API idempotency, safe release, fencing, the PostgreSQL guard, RDB/AOF/replication/failover/eviction effects, security/ACL isolation, monitoring, and managed responsibility |
| Artifact syntax / runtime validation | **NOT RUN** | no Redis, Sentinel, Cluster, managed Redis, `redis-cli`, Lua, `MULTI/EXEC`, `WATCH`, ACL, TLS, persistence, or eviction command was executed; the Lua/compare-and-delete/`SET NX PX`/ACL examples are read for shape and naming only |
| Disposable Redis/PostgreSQL validation | **NOT RUN** | no rate limiter, connection pool, FastAPI endpoint, API idempotency implementation, or PostgreSQL Job/Attempt/Event/Outbox/lease/fencing SQL was run |
| Failover / eviction / security drill | **NOT RUN** | no RDB/AOF/replication/failover/data-loss measurement, eviction test, ACL/TLS/Secret/certificate, or dangerous-command policy was applied |
| Application integration validation | **NOT RUN** | no Provider/Object Storage request, idempotency query, Artifact reconciliation, notification delivery, Worker drain/handoff, or fail-closed endpoint |
| Production validation | **NOT RUN** | no production accessed; every number (60/min, 30s, capacity 10, refill 1/s) is a static design example; the Day42 capstone is a future boundary |

### Day40 (`redis/redis-messaging-and-queue-semantics-design.md`)

| Level | Day40 status | Evidence |
|---|---|---|
| Conceptual classroom validation | **Completed** | one AI Job messaging scenario reasoned end to end: crash-before-ACK, at-least-once/idempotency, Pub/Sub-vs-Streams, Consumer Groups/ordering, Lists/payload/Celery boundary, poison messages/retry, safe trim, notification identities, and dual-crash recovery |
| Static reasoning review | **Completed** | static review of the List/Pub-Sub/Streams decision table, the payload contract, the group topology, the PEL/ACK/Claim lifecycle, the delivery-vs-completion boundary, per-side-effect idempotency, the retry/quarantine path, the trim/retention contract, and the recovery matrix |
| Artifact syntax / runtime validation | **NOT RUN** | no Redis, `redis-cli`, Stream, Consumer Group, `XACK`, `XCLAIM`/`XAUTOCLAIM`, `XTRIM`, Pub/Sub, or List command was executed; the `XADD`/`XREADGROUP`/`XACK`/`XCLAIM`/`XTRIM` examples are read for shape and naming only |
| Disposable-Redis / PostgreSQL validation | **NOT RUN** | no Stream/Group/PEL/Claim/redelivery/trim behaviour and no PostgreSQL commit/reconciliation was run or measured |
| Application integration validation | **NOT RUN** | no Celery/Worker/Provider/email/Object Storage integration; no Claim/ACK/redelivery/Trim runtime; no dispatch, quarantine, or notification path exercised |
| Production validation | **NOT RUN** | no production message loss, redelivery, poison message, or trim incident observed; Redis is not claimed to provide exactly-once; composition is Day41 |

### Day39 (`redis/redis-cache-consistency-design.md`)

| Level | Day39 status | Evidence |
|---|---|---|
| Conceptual classroom validation | **Completed** | one AI Job cache scenario reasoned end to end: stale-vs-committed, cache-aside, commit-then-invalidate, affected views, representation versioning, TTL/jitter, stampede/single-flight/SWR, fail-open/closed, negative caching, hot key, correctness metrics, Outbox recovery, and the v2 incident |
| Static reasoning review | **Completed** | static review of every cache contract, the commit-before-invalidate ordering and pre-commit race, the versioning rule, TTL/jitter vs single-flight, the fail-open/closed table, negative-caching constraints, the correctness-metric list, the Outbox + idempotent DEL recovery, and the v2 rollback target |
| Artifact syntax / runtime validation | **NOT RUN** | no Redis, `redis-cli`, cache API, or command was executed; key patterns and the DEL/Outbox flow are read for shape and naming only |
| Disposable-Redis / PostgreSQL validation | **NOT RUN** | no cache stampede, avalanche, eviction, hot key, TTL, jitter, or PostgreSQL commit/invalidation was run or measured |
| Application integration validation | **NOT RUN** | no FastAPI/Worker/Relay/Outbox/Provider/Object Storage integration; no cache-aside, invalidation, or negative-cache path exercised |
| Production validation | **NOT RUN** | no production cache inspected/changed; no production accessed; numbers (10s, 50,000, TTL/jitter) are illustrative, not measured; messaging/composition are Day40-41 |

### Day38 (`redis/redis-acceleration-layer-design.md`)

| Level | Day38 status | Evidence |
|---|---|---|
| Conceptual classroom validation | **Completed** | one AI Job scenario reasoned end to end: ownership, missing-key fallback, Redis-only-lifecycle rejection, structure-by-access-pattern, key/versioning, atomicity, eviction, RDB/AOF, broker payload, outage degradation, missing-TTL incident |
| Static reasoning review | **Completed** | static review of the ownership boundary, the key contract and versioning rule, the data-structure decision table, the TTL/multi-command boundaries (`HSET`+`EXPIRE`, two-Worker race, `HINCRBY`), eviction-as-correctness, RDB/AOF loss windows, the broker-payload rule, bounded outage degradation, and the prefix-scoped (not `FLUSHALL`) incident recovery |
| Artifact syntax / runtime validation | **NOT RUN** | no Redis server, `redis-cli`, config, or command (`String`/`Hash`/`List`/`Set`/`Sorted Set`, `INCR`/`HINCRBY`/`HSET`/`EXPIRE`/`SCAN`) was executed; the command snippets are read for shape and naming only |
| Disposable-Redis validation | **NOT RUN** | no key/TTL/expiry, eviction under `maxmemory`, RDB/AOF file, or cluster behaviour was run or measured |
| Application integration validation | **NOT RUN** | no application/Worker/Provider/Object Storage/broker integration; no progress projection, cache, or rate-limit path exercised |
| Production validation | **NOT RUN** | no production Redis inspected/changed; no production accessed; any figure reused from Day37 is a placeholder, not a measurement; cache consistency/messaging/composition are Day39-41 |

### Day37 (`runbooks/postgresql-production-reliability.md`)

| Level | Day37 status | Evidence |
|---|---|---|
| Conceptual classroom validation | **Completed** | one continuously evolving AI Job production scenario; all 15 concepts reasoned end to end |
| Static reasoning review | **Completed** | static arithmetic (`(4+12)*10 = 160`; `12*25 + 12*10 = 420` vs `300`); static review of transaction boundaries, timeout scope, readiness/liveness, MVCC/Vacuum, least privilege, rotation, replication-vs-backup, PITR, RPO/RTO, monitoring, promotion, and incident rollback reasoning |
| Artifact syntax / runtime validation | **NOT RUN** | no PostgreSQL server or disposable cluster started; no `psql`/SQL/configuration statement executed |
| Disposable PostgreSQL validation | **NOT RUN** | no pool configured/saturated/measured; no real lock wait/timeout/deadlock/idle transaction/cancel; no Vacuum/autovacuum/dead-tuple/`VACUUM FULL` behaviour run |
| Application integration validation | **NOT RUN** | no role/grant/credential/Secret/TLS/rotation configured; no Kubernetes probe/drain deployed; no application/Worker/Provider/Object Storage integration run |
| Backup / restore drill | **NOT RUN** | no base backup, WAL archive, PITR, isolated restore, integrity/business check, replica lag/promotion, or measured RPO/RTO |
| Production validation | **NOT RUN** | no managed PostgreSQL inspected/changed; no production accessed; every number is classroom arithmetic/design, not a measured result |

### Day36 (`008_schema_evolution_and_safe_migrations.sql`)

| Level | Day36 status | Evidence |
|---|---|---|
| Conceptual / manual review | **Done (in class)** | migration as a versioned state transition; the phased plan; the compatibility matrix; nullable expand vs the unsafe counter-examples; backfill scope/mechanics; `NOT VALID`/`VALIDATE`; `CONCURRENTLY`/invalid index; switch/contract; the false-takeover forward-fix decision |
| Final artifact static review | **Done (repository update)** | adds the Lease columns as **NULLABLE** with no fabricated default; the `NOT NULL` and `DEFAULT gen_random_uuid()` forms are **commented** counter-examples; the `CHECK` is `NOT VALID` then `VALIDATE`; the backfill is a bounded idempotent `SKIP LOCKED` template that calls **no Provider** and never fabricates a token; `CREATE INDEX CONCURRENTLY` is a **commented** non-transactional step with invalid-index handling; the destructive Contract `DROP` is commented; no `SQLAlchemy`/`Alembic`; no credentials |
| **Disposable-PostgreSQL runtime (ALTER / constraint / index / backfill)** | **NOT RUN** | no Day36 SQL file, PostgreSQL server, `ALTER`, constraint, index build, `EXPLAIN`, or backfill was executed in class or during the repository update; the lock/rewrite/rollout behaviours are reasoned about, not measured |
| Application / Worker integration | **NOT RUN** | no old/new application compatibility test, old-Worker drain, token-guard Switch, or Provider/Object Storage integration |
| Production DDL / deployment / rollback | **NOT RUN / OUT OF SCOPE** | no production migration, index build, backfill, benchmark, or rollback; live operation is Day37; `SQLAlchemy`/`Alembic` are Phase 4; fencing is Day41 |

### Day35 (`007_postgresql_indexes_and_query_planning.sql`)

| Level | Day35 status | Evidence |
|---|---|---|
| Conceptual / manual review | **Done (in class)** | index-from-query-shape derivation; the claim Partial Composite; history paths; no-duplicate-unique; Outbox Partial; `now()` rejection; `EXPLAIN` vs `EXPLAIN ANALYZE`; Seq-Scan judgement; estimate-vs-actual; index maintenance; the net-benefit keep/rollback decision |
| Final artifact static review | **Done (repository update)** | uses the Day31 columns exactly; claim Partial Composite is `(tenant_id, created_at, job_id) WHERE job_status='queued' AND cancel_requested=false`; Outbox Partial is `(created_at, outbox_event_id) WHERE published_at IS NULL`; **no** duplicate index for `UNIQUE (tenant_id, idempotency_key)`; the stale-lease design and its `now()`-avoidance are commented/conceptual (lease columns absent); no `CREATE INDEX CONCURRENTLY`/`ALTER`/`DROP`/migration/ORM; no credentials |
| **PostgreSQL runtime (EXPLAIN / EXPLAIN ANALYZE)** | **NOT RUN** | no Day35 SQL file, PostgreSQL server, `EXPLAIN`, `EXPLAIN ANALYZE`, statistics refresh, or representative data was executed in class or during the repository update. Every plan number quoted (8M-row Seq Scan; estimate 1 vs actual 20,000; 100->80 / 50->220 / +14 GB) is a **classroom scenario** for reasoning, not a measured result |
| Application / benchmark integration | **NOT RUN** | no FastAPI/driver/Celery workload, p95/p99 benchmark, or representative-data load |
| Production DDL / deployment / rollback | **NOT RUN / OUT OF SCOPE** | no index was built, deployed, or rolled back; `CREATE INDEX CONCURRENTLY`, DDL-lock windows, and rollout/rollback are Day36; no production load test, RLS, backups, HA, or deployment |

### Day34 (`006_concurrency_control_mvcc_and_worker_claims.sql`)

| Level | Day34 status | Evidence |
|---|---|---|
| Conceptual / manual review | **Done (in class)** | visibility vs ownership; `FOR UPDATE`/`SKIP LOCKED`; the claim transaction; fairness/starvation; released lock vs liveness; row lock vs committed lease; lease expiry/takeover/token; `lease_token` vs Provider key; MVCC/isolation; deadlock prevention/detection/bounds/retry |
| Reduced classroom PostgreSQL runtime | **Done (PostgreSQL 14.18, three concurrency tests)** | on a **reduced** disposable `jobs(job_id text, job_status text, created_at integer)` schema (NOT Day31, NOT this file): (1) Session A locked job-A, concurrent Session B ran the ordered queued query `FOR UPDATE SKIP LOCKED` and returned job-B; (2) Session B's ordinary `FOR UPDATE` under `lock_timeout=500ms` failed with `SQLSTATE 55P03`; (3) a reverse-order A->B / B->A deadlock was detected and Session B aborted with `SQLSTATE 40P01`, then Session A COMMITted. An initial restricted-sandbox `initdb` failed with `shmget: Operation not permitted` (environment evidence, not a SQL result). The temporary server was stopped afterwards. |
| Reduced-run coverage limits | **Explicit** | The reduced run used a 3-column text schema and did **not** execute the final 006 file, the full Day31 schema, the claim's Attempt/Event inserts, or any lease field (`claim_owner`/`lease_token`/`lease_expires_at`). |
| Final artifact static review | **Done (repository update)** | active SQL uses the Day31 columns exactly (no invented columns); one balanced `BEGIN`/`COMMIT` claim transaction; `FOR UPDATE SKIP LOCKED` reservation + the unchanged Day33 guarded `UPDATE ... RETURNING` with control-flow contracts; the lease state machine is **entirely commented/conceptual**; no `CREATE INDEX`/`EXPLAIN`/`ALTER`/`DROP`/migration/ORM/Redis; SQLSTATEs `55P03`/`40P01`/`40001` documented; no credentials |
| **Final artifact PostgreSQL runtime** | **NOT RUN** | no `psql`/PostgreSQL server was available during the repository update, so no statement in `006` was parsed or executed by PostgreSQL. The reduced-schema classroom run is **not** reused as proof of this file. |
| Application / external integration | **NOT RUN** | no FastAPI/driver/Celery multi-Worker, lease heartbeat/renewal/takeover, stale-token Completion on a migrated schema, Provider idempotency/lookup, Object Storage, or Redis/Queue |
| Recovery / fairness / stronger isolation | **NOT RUN** | no crash/restart recovery, long-duration fairness/starvation, or SERIALIZABLE workload |
| Performance / production validation | **NOT RUN / OUT OF SCOPE** | Day35 index plans; production load/performance, RLS, backups, HA, deployment |

### Day33 (`005_postgresql_transactions_and_atomic_state_changes.sql`)

| Level | Day33 status | Evidence |
|---|---|---|
| Conceptual / manual review | **Done (in class)** | the 14 failure scenarios, the external-side-effect boundary, ACID from the scenario, the Outbox lifecycle, and the at-least-once delivery model |
| Local draft static scope check | **Done (in class)** | a local classroom draft (`day33/day33_transactional_write_pack.sql`) was scope-reviewed; it is teaching-session input, **not** this repository artifact |
| Reduced classroom PostgreSQL runtime | **Done (PostgreSQL 14.18, five listed tests)** | a **reduced** validation schema PASSED: (1) Job + Outbox committed together; (2) a duplicate Outbox id raised `unique_violation` and rolled the preceding Job insert back; (3) running Job + Attempt + `job_started` Event committed coherently; (4) a duplicate Artifact key raised `unique_violation` and rolled Attempt-finish + Job-success + success Event + success Outbox back; (5) the Outbox `published_at` checkpoint changed from NULL to a timestamp. Final marker `DAY33_REDUCED_RUNTIME_VALIDATION_PASS`. An earlier restricted-sandbox bootstrap failed at cluster start with `shmget: Operation not permitted` (environment evidence, not a SQL result). Both temporary clusters were deleted. |
| Reduced-run coverage limits | **Explicit** | Test 5 validated only PostgreSQL's NULL->timestamp checkpoint, **not** Redis publication. Test 4's classroom draft wrote an unconditional success Outbox; the final artifact makes that row conditional. The reduced run did **not** exercise the review-round guards (the `finished_at IS NULL` Attempt-finish guard, the conditional `job.succeeded` Outbox, or the pre-call vs returned Provider-identity split), the final repository file, the FastAPI affected-row / lost-COMMIT integration, a real Relay crash/restart, or consumer idempotency. |
| Final artifact static review | **Done (repository update + review round)** | uses the Day31 columns exactly (no invented columns, **no schema change**); three short transactions with balanced `BEGIN`/`COMMIT`; guarded `UPDATE ... RETURNING` each followed by an explicit control-flow contract; Attempt-finish guarded by `finished_at IS NULL`; `attempt_id` documented as the pre-call recovery anchor and `provider_request_id` as returned/persisted-in-C only; `job.succeeded` Outbox left conditional (commented) with a stable-ids-only payload rule; external phase outside any transaction; `attempt_count` incremented database-side; no `FOR UPDATE`/`SKIP LOCKED`/`CREATE INDEX`/`EXPLAIN`/`DROP`/`ALTER`/ORM; no credentials |
| **Final artifact PostgreSQL runtime** | **NOT RUN** | no `psql`/PostgreSQL server was available during the repository update, so no statement in `005` was parsed or executed by PostgreSQL. The reduced classroom run is **not** reused as proof of this file. |
| Application / external integration | **NOT RUN** | no FastAPI affected-row + COMMIT-unknown path, Provider, Object Storage, Redis, Celery, real Relay crash/restart, or consumer idempotency test |
| Concurrency / production validation | **NOT RUN** | Day34 concurrent claims/MVCC/locks/`SKIP LOCKED` (out of scope); performance, RLS/roles, backups, HA, deployment |

### Day32 (`004_sql_joins_aggregation_and_operational_queries.sql`)

| Level | Day32 status | Evidence |
|---|---|---|
| Conceptual / manual review | **Done (in class)** | result grain, join choice from missing-row meaning, cardinality and multiplication, NULL-aware counting, `FILTER` vs `WHERE`, `WHERE` vs `HAVING`, incomplete-cost honesty, CTE pre-aggregation, stage-aware clocks, half-open windows, provenance, evidence vs verdict |
| Student SQL static review | **Done (in class)** | student join/aggregate answers reviewed; the row-multiplication misconception (answered as 4 rows, then 0 rows) corrected to 12, and the zero-Attempt + 4-Event case corrected to 4 |
| Reduced classroom PostgreSQL runtime | **Done (PostgreSQL 14.18, listed checks only)** | a **reduced** validation schema — not this full file — executed a **reduced** Day32 validation schema with representative data and PASSED exactly these checks: LEFT JOIN zero-Attempt placeholder row; `COUNT(*)` vs `COUNT(attempt_id)` for a zero-Attempt Job; 3 Attempts x 4 Events = 12 rows; conditional aggregation 3 total / 2 failed; cost evidence 2 reported / SUM 400 / AVG 200; independent Attempt/Event CTE pre-aggregation; `running_attempt_over_threshold` classification; `running_without_attempt` classification; one succeeded Job in the last-hour throughput window; release-provenance `DISTINCT` affected set; final marker `DAY32_RUNTIME_VALIDATION_PASS`. An earlier bootstrap failed at cluster start with `shmget: Operation not permitted` (environment evidence, not a SQL result). Cluster stopped and the temporary directory removed. |
| Reduced-run coverage limits | **Explicit** | **Not** executed or proven by that run: `HAVING` group filtering; `DISTINCT ON` selection of the current Attempt — the classroom used the greatest `attempt_number` path, **not** the artifact's `DISTINCT ON` form; a half-open window excluding a row placed exactly on the upper bound — only a single last-hour succeeded throughput sample was run, with no boundary row created or asserted; the explicit terminal-status allowlist; queries 4b, 5 and 10; and execution against the full Day31 `001` + `003` schema. Release provenance **was** covered representatively, which still does not prove the final repository query 9 as written. |
| Final artifact static review | **Done (repository update + review)** | balanced parentheses (69/69); 12 statements; every aliased column present in `001` + `003`; a `GRAIN` contract declared per statement; a deterministic `ORDER BY` on every result-returning query; `tenant_id` predicate on every tenant-scoped read; query 8 restricted to terminal states; real count columns `COALESCE`d to 0 in queries 6 and 10 while cost stays NULL; no `INSERT`/`UPDATE`/`DELETE`/`BEGIN`/`COMMIT`/`FOR UPDATE`/`CREATE INDEX`/`EXPLAIN`/`DROP`; no `SUM(DISTINCT ...)`; no credentials |
| **Final artifact PostgreSQL runtime** | **NOT RUN** | no `psql`/PostgreSQL server was available in the repository-update environment or during this review, so no statement in this file has been parsed or executed by PostgreSQL. The reduced classroom evidence is **not** reused as proof of this file. |
| Application integration | **NOT RUN** | no FastAPI/Celery/driver/Redis/Provider/Object Storage was exercised |
| Atomicity / concurrency / performance | **NOT RUN** | Day33/Day34/Day35 |
| Production validation | **NOT RUN** | no RLS, roles, backups, HA, performance, or deployment evidence; release-metadata completeness is unproven |

### Day31 (`003_relational_modeling_and_data_integrity.sql`)

| Level | Day31 status | Evidence |
|---|---|---|
| Conceptual / manual review | **Done (in class)** | entities, cardinality, identity vs business key, referential actions, normalization, tenant integrity, incident reconciliation |
| Student SQL static review | **Done (in class)** | minimum `job_attempts` DDL reviewed; syntax corrections recorded |
| Reduced classroom PostgreSQL runtime | **Done (PostgreSQL 14.18, selected tests)** | a **reduced** validation schema — not this full file — accepted the core DDL and rejected duplicate `(job_id, attempt_number)`, non-positive `attempt_number`, a missing parent Job, deleting a Job with an Attempt, a same-tenant duplicate idempotency key, an invalid `job_status`, and a cross-tenant Job-Document link; a different tenant reused the key successfully; one valid Attempt remained. Cluster stopped and the temporary directory removed. |
| Final artifact static review | **Done (repository update)** | balanced syntax; DDL dependency order valid after `001`; every composite FK has a matching candidate key (including `documents` -> `upload_sessions` on `(tenant_id, upload_session_id)`); `result_artifacts` has no `job_id` column; all FKs use `ON DELETE RESTRICT`; named constraints throughout; no transactions/locks/explicit indexes/DROP/RLS/roles; legacy `result_object_key` retained; no credentials |
| **Final artifact PostgreSQL runtime** | **NOT RUN** | no `psql`/PostgreSQL server was available in the repository-update environment, including for the tenant-aware `documents` composite FK and the corrected Test 9/Test 10 isolation. The reduced classroom test is **not** proof that every table applies cleanly, and it never covered the cross-tenant Upload Session -> Document case. Tests 1-11 have been reviewed statically (constraint targeting, single-condition handlers, ordering) but **not executed**. |
| Application integration | **NOT DONE** | no FastAPI/Celery/driver/Redis/Provider/Object Storage was exercised |
| Transactions / concurrency / migration safety | **NOT DONE** | Day33/Day34/Day36 |
| Production validation | **NOT DONE** | no RLS, roles, backups, HA, performance, or deployment evidence |

### Verified in class (PostgreSQL 14.18, disposable cluster)

```text
- CREATE SCHEMA and CREATE TABLE succeeded.
- gen_random_uuid() was available and produced a UUID.
- INSERT ... DEFAULT VALUES RETURNING * produced queued / 0 / false / {} / created_at,
  with started_at, finished_at, error_message, result_object_key returned as NULL.
- Explicit job_status NULL failed with a not-null constraint violation.
- Empty job_status AND 'banana' were both ACCEPTED  -> the known missing business constraint.
- The same created_at rendered as 2026-07-19 12:32:00.454132+00 (UTC) and
  2026-07-19 20:32:00.454132+08 (Asia/Shanghai); both had epoch 1784464320.454132.
- Guarded repair drill: three 'queud' rows inserted (baseline empty=1, banana=1, queud=3, queued=1);
  UPDATE ... WHERE job_status = 'queud' reported UPDATE 3 and RETURNING listed the three repaired
  job_ids; post-repair counts were empty=1, banana=1, queued=4.
- PostgreSQL was stopped and restarted; all 6 rows remained (queued=4, banana=1, empty=1).

Session context:
- The session connected to database ai_backend as user yuanzhenyu.
- The target relation was app.jobs.
- search_path was "$user", public.
- current_schema() returned public.
- Explicit qualification allowed app.jobs to resolve even though app was not in search_path.
- Session timezone was Asia/Shanghai.

(A session connects to a DATABASE, never to a schema. `app` is the namespace of the target relation,
not "the schema the session is connected to".)
```

**Not proven by the restart test:** backup recovery, high availability, crash durability under hardware
failure, or production reliability. It showed local process-lifecycle persistence only.

---

## Known gaps (deliberate — future lessons)

```text
Day30  SELECT/INSERT/UPDATE/DELETE/RETURNING, NULL logic, parameterized SQL, guarded transitions
Day31  CHECK (valid job_status, attempt_count >= 0), UNIQUE business/idempotency key, tenant ownership,
       Documents / Job Attempts / Job Events / Outbox Events / Result Artifact refs, foreign keys
Day32  joins/aggregation and operational queries (delivered: sql/004_...sql)
Day33  transactions (atomic Job + Outbox insert) (delivered: sql/005_...sql)
Day34  concurrency-safe claims (FOR UPDATE / SKIP LOCKED), leases, idempotency enforcement (delivered: sql/006_...sql)
Day35  indexes and query plans (delivered: sql/007_...sql)
Day36  versioned migrations (this file is a starting point, not a migration framework) (delivered: sql/008_...sql)
Day37  pooling, roles/least privilege, timeouts, vacuum, backup/PITR, operations
```

Today's schema is durable but **not yet correct-by-construction**: a misspelled `queud` status is
accepted, stored forever, and never claimed by a worker. Durability is not integrity.

Related: [PostgreSQL cheat sheet](../../cheat_sheets/postgresql.md) ·
[PostgreSQL interview](../../interview/postgresql.md) ·
[Day28 architecture blueprint](../../examples/ai-backend-architecture/README.md)
