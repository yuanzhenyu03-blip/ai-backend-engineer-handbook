# Production AI Backend Data Layer

The evolving Phase 3 engineering artifact. It turns the Day28 conceptual ownership rule —
**PostgreSQL owns durable Job truth** — into an executable, failure-aware data layer, one lesson at a
time (Day29-Day42).

Current increment: **Day39 — a Redis cache consistency design** that turns the Day38 ownership boundary
into an explicit per-endpoint cache contract: cache-aside reads, commit-before-invalidate ordering (with the
pre-commit re-cache race), cache key versioning, TTL + jitter, stampede/single-flight/stale-while-revalidate,
a fail-open vs fail-closed table, negative caching, correctness metrics, Outbox invalidation recovery, and the
v2 cache-contract incident — design and evidence only, nothing executed. (See the Day38 note below for the
prior increment.)

Prior increment (Day38): **a Redis acceleration-layer design** that adds Redis as *transient* state around
the durable PostgreSQL truth: the ownership model (PostgreSQL truth / Object Storage bytes / Redis rebuildable
acceleration), a tenant-scoped versioned key contract, a data-structure decision table, TTL and multi-command
boundaries, memory/eviction as correctness, RDB/AOF loss windows, Redis-outage degradation, and the
missing-TTL incident — design and evidence only, nothing executed.

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

---

## Structure (grows with real lessons only)

```text
projects/ai-backend-data-layer/
├── README.md
├── redis/
│   ├── redis-acceleration-layer-design.md             # Day38: Redis acceleration-layer design (design + evidence, not executed)
│   └── redis-cache-consistency-design.md              # Day39: Redis cache consistency design (design + evidence, not executed)
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
