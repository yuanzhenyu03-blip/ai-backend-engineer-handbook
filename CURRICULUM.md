# Curriculum

This file defines the official curriculum for the AI Backend Engineer Training Camp.

The curriculum is not a list of topics.

It is an engineering training plan. Every lesson must connect concept understanding, production risk, framework usage, coding practice, interview readiness, and repository updates.

---

## Phase 1 — Python Foundations

### Day01

Topic:
Python Object Model

Status:
✅ Completed

Released Lesson:
`docs/python/day01-object-model.md`

---

### Day02

Topic:
Mutable vs Immutable

Status:
✅ Completed

Difficulty:
Foundation

Estimated Study Time:
4-5 hours

Prerequisites:

- Day01 — Python Object Model
- Names, references, and object identity
- `==` vs `is`
- Mutable default argument bug

Learning Objectives:

- Understand mutable and immutable objects.
- Learn how object identity connects to mutability.
- Understand shallow copy vs deep copy.
- Explain why mutable default arguments are dangerous.
- Connect the concept to FastAPI and Playwright.

Key Concepts:

- Mutable objects
- Immutable objects
- Object identity
- Shared references
- Copy
- Deep copy
- Hashability

Engineering Thinking:

- Which objects are safe to share?
- Which objects should be copied?
- Which objects should be isolated per request or per job?
- How can hidden mutation create production bugs?

Deliverables:

- Day02 lesson document
- Python cheat sheet update
- Python interview notes update
- Coding exercises

Homework:

- Copy exercises
- `id()` experiments
- Memory diagrams

Mini Project:

Implement a simple object inspector.

Interview Focus:

- Explain mutable vs immutable objects.
- Explain shallow copy vs deep copy.
- Explain why tuple can be hashable but list cannot.
- Explain how shared mutable state causes backend bugs.

Repository Updates:

- `docs/python/day02-mutable-vs-immutable.md`
- `cheat_sheets/python.md`
- `interview/python.md`
- `PROJECT_STATUS.md`
- `TASKS.md`
- `CHANGELOG.md`

Related Lessons:

- Previous: Day01 — Python Object Model
- Next: Day03 — Functions & Parameter Passing

---

### Future Lesson Template

Every future lesson should follow this structure.

#### Day XX

Topic:

Difficulty:

Estimated Study Time:

Prerequisites:

Learning Objectives:

Key Concepts:

Engineering Thinking:

Deliverables:

Homework:

Mini Project:

Interview Focus:

Repository Updates:

Related Lessons:

---

### Day03

Topic:
Functions & Parameter Passing

Status:
✅ Completed

---

### Day04

Topic:
Scope & LEGB

Status:
✅ Completed

Difficulty:
Foundation

Estimated Study Time:
4-5 hours

Prerequisites:

- Day01 — Python Object Model
- Day02 — Mutable vs Immutable
- Day03 — Functions & Parameter Passing

Learning Objectives:

- Understand Python name lookup.
- Explain Local, Enclosing, Global, and Built-in scopes.
- Explain why scope matters in function design.
- Connect scope behavior to FastAPI, Playwright, and AI backend systems.

Key Concepts:

- Local scope
- Enclosing scope
- Global scope
- Built-in scope
- Name lookup
- Shadowing

Repository Updates:

- `docs/python/day04-scope-legb.md`
- `cheat_sheets/python.md`
- `interview/python.md`
- `PROJECT_STATUS.md`
- `TASKS.md`
- `CHANGELOG.md`

---

### Day05

Topic:
Closures

Status:
✅ Completed

Difficulty:
Foundation

Estimated Study Time:
4-5 hours

Prerequisites:

- Day01 — Python Object Model
- Day03 — Functions & Parameter Passing
- Day04 — Scope & LEGB

Learning Objectives:

- Understand closures as function objects with captured environments.
- Explain closure use cases in production Python.
- Connect closures to decorators, dependency factories, and AI backend prompt builders.

Key Concepts:

- Closure
- Captured environment
- Factory function
- State preservation
- Late binding review

Repository Updates:

- `docs/python/day05-closures.md`
- `cheat_sheets/python.md`
- `interview/python.md`
- `PROJECT_STATUS.md`
- `TASKS.md`
- `CHANGELOG.md`

---

### Day06

Topic:
Decorators

Status:
✅ Completed

---

### Day07

Topic:
Iterators & Generators

Status:
✅ Completed

---

### Day08

Topic:
Exception Handling

Status:
✅ Completed

---

### Day09

Topic:
Modules & Packages

Status:
✅ Completed

---

### Day10

Topic:
Type Hints

Status:
✅ Completed

---

### Day11

Topic:
Object-Oriented Programming

Status:
✅ Completed

---

### Day12

Topic:
Context Managers

Status:
✅ Completed

---

### Day13

Topic:
Async Programming

Status:
✅ Completed

---

### Day14

Topic:
Mini Project & Backend Architecture

Status:
✅ Completed

Released Lesson:
`docs/python/day14-mini-project.md`

---

## Phase 1 — Complete

All Day01–Day14 Python foundation lessons are completed.

---

## Phase 2 — Engineering Foundations

### Day15

Topic:
Git Fundamentals

Status:
✅ Completed

Released Lesson:
`docs/git/day15-git-fundamentals.md`

---

### Day16

Topic:
Git Branch & Merge

Status:
✅ Completed

Released Lesson:
`docs/git/day16-branch-and-merge.md`

---

### Day17

Topic:
GitHub Workflow & Collaboration

Status:
✅ Completed

Released Lesson:
`docs/git/day17-github-workflow.md`

---

### Day18

Topic:
Merge Strategy & Code Review

Status:
✅ Completed

Released Lesson:
`docs/git/day18-merge-strategy-and-code-review.md`

---

### Day19

Topic:
GitHub Project Management

Status:
✅ Completed

Released Lesson:
`docs/github/day19-project-management.md`

---

### Day20

Topic:
CI/CD Foundations

Status:
✅ Completed

Released Lesson:
`docs/devops/day20-ci-cd-foundations.md`

---

## DevOps Foundations (continued)

### Day21

Topic:
GitHub Actions Fundamentals

Topics:
Workflow, Trigger, Runner, GitHub-hosted Runner, Self-hosted Runner, Job, Step, Action
Marketplace, `uses`, `run`, Secrets, Environment Variables, Basic FastAPI CI

Status:
✅ Completed

Released Lesson:
`docs/devops/day21-github-actions-fundamentals.md`

Template:
LESSON_TEMPLATE_v2

---

### Day22

Topic:
GitHub Actions Advanced

Topics:
Matrix Build, Cache, Artifacts, Reusable Workflow, Composite Actions, Conditional Jobs,
Deployment Pipeline

Status:
✅ Completed

Released Lesson:
`docs/devops/day22-github-actions-advanced.md`

Template:
LESSON_TEMPLATE_v2

---

## Container Engineering

### Day23

Topic:
Docker Fundamentals

Topics:
Container, Image, Layer, Dockerfile, Build, Run, Volume, Network

Status:
✅ Completed

Released Lesson:
`docs/devops/day23-docker-fundamentals.md`

Template:
LESSON_TEMPLATE_v2

---

### Day24

Topic:
Docker Compose

Topics:
Multi-service, FastAPI + Redis, PostgreSQL, Environment, Local Development

Status:
✅ Completed

Released Lesson:
`docs/devops/day24-docker-compose.md`

Template:
LESSON_TEMPLATE_v2

---

## Production Engineering

### Day25

Topic:
Deployment Foundations

Topics:
Reverse Proxy, Nginx, SSL, Domain, CI/CD Deployment, Zero Downtime

Status:
✅ Completed

Released Lesson:
`docs/devops/day25-deployment-foundations.md`

Template:
LESSON_TEMPLATE_v2

---

### Day26

Topic:
Kubernetes Foundations

Topics:
Pod, Deployment, Service, ConfigMap, Secret

Status:
✅ Completed

Released Lesson:
`docs/devops/day26-kubernetes-foundations.md`

Template:
LESSON_TEMPLATE_v2

---

### Day27

Topic:
Kubernetes Workloads

Topics:
Ingress, Autoscaling, Rolling Update, StatefulSet, Helm

Status:
✅ Completed

Released Lesson:
`docs/devops/day27-kubernetes-workloads.md`

Template:
LESSON_TEMPLATE_v2

---

### Day28

Topic:
AI Backend Production Architecture

Topics:
FastAPI, Celery, Redis, PostgreSQL, Object Storage, Queue, Monitoring, Observability

Status:
✅ Completed

Released Lesson:
`docs/devops/day28-ai-backend-production-architecture.md`

Template:
LESSON_TEMPLATE_v2

---

## Phase 3 — Backend Foundations (Day29-Day42)

Status:
Complete

Objective:
Turn the conceptual state ownership established in Day28 into an executable, failure-aware data layer.
Model durable business truth in PostgreSQL, express and verify it with SQL, preserve correctness under
transactions and concurrency, evolve and operate the database safely, and use Redis only for transient
caching, messaging, rate limiting, and coordination.

Phase mental model:

```text
PostgreSQL = durable business truth and enforceable integrity
SQL        = language for expressing, changing, joining, and verifying that truth
Redis      = transient acceleration, messaging, and coordination
DB Design  = ownership + relationships + constraints + access paths + failure behavior
```

Evolving artifact (created only by future live lessons, starting Day29): `projects/ai-backend-data-layer/`.
SQLAlchemy and Alembic are Phase 4 topics; Phase 3 teaches raw PostgreSQL/SQL mental models first. Do
not fully expand distant future lessons until they become the current lesson.

---

### Day29

Topic:
PostgreSQL Foundations and Durable Relational State

Topics:
Why a durable relational database exists in the Day28 architecture; PostgreSQL server/cluster/database/
schema/table/row/column boundaries; relational state vs process memory / Redis / Object Storage / JSON-
only storage; core types for the Job model (UUID, text, integer, boolean, `timestamptz`, bounded JSONB);
primary key and stable business identity; `NULL` vs `NOT NULL`, defaults, DB-generated timestamps/IDs;
`psql` connection/session model; a minimal `jobs` table for an accepted `202 + job_id`; conceptual vs
SQL-syntax vs real PostgreSQL runtime validation.

Status:
✅ Completed

Previous Lesson:
Day28 — AI Backend Production Architecture

Next Lesson:
Day30 — SQL Data Manipulation and Query Fundamentals

Released Lesson:
`docs/postgresql/day29-postgresql-foundations-and-durable-relational-state.md`

Template:
LESSON_TEMPLATE_v2

Released Engineering Artifact:
`projects/ai-backend-data-layer/` — the first minimal raw SQL Job schema (`sql/001_create_jobs.sql`) plus
a README stating ownership decisions, reproducible disposable-PostgreSQL commands, a validation matrix,
and explicit limitations. Classroom runtime evidence came from PostgreSQL 14.18; integration and
production validation were not performed.

Core mental model:

```text
Application object/state is temporary.
Database row is durable business fact.
Table schema is an enforceable contract for those facts.
```

---

### Day30

Topic:
SQL Data Manipulation and Query Fundamentals

Topics:
`SELECT/FROM/WHERE/ORDER BY/LIMIT`; `INSERT/UPDATE/DELETE` and `RETURNING`; `NULL`/`IS NULL`/three-valued
logic; explicit column lists and deterministic ordering; parameterized SQL vs injection; rows-affected
and lost-update awareness; Job CRUD and guarded status-transition queries.

Status:
✅ Completed

Released Lesson:
`docs/postgresql/day30-sql-data-manipulation-and-query-fundamentals.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day29 — PostgreSQL Foundations and Durable Relational State

Next Lesson:
Day31 — Relational Modeling and Data Integrity

Released Engineering Artifact:
`projects/ai-backend-data-layer/sql/002_job_crud_and_guarded_transitions.sql` — a raw, parameterized SQL
operations pack (INSERT with defaults + RETURNING, deterministic candidate SELECT, NULL-aware reads,
guarded queued->running and running->succeeded transitions, database-side and optimistic attempt_count
updates, guarded cleanup DELETE) with explicit affected-row contracts. No transactions, locks,
constraints, or indexes (Day31-Day35)

---

### Day31

Topic:
Relational Modeling and Data Integrity

Topics:
Entities/attributes/relationships/ownership; one-to-one/one-to-many/many-to-many; primary key vs
business key; `NOT NULL`/`UNIQUE`/`CHECK`/foreign-key constraints; referential actions
(`RESTRICT`/`CASCADE`/`SET NULL`); normalization vs measured denormalization; model Upload Sessions,
Documents, Jobs, Job Attempts, Job Events, Outbox Events, and Result Artifact references (no large
Object Storage bytes in PostgreSQL); tenant/owner and provenance boundaries.

Status:
✅ Completed

Released Lesson:
`docs/postgresql/day31-relational-modeling-and-data-integrity.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day30 — SQL Data Manipulation and Query Fundamentals

Next Lesson:
Day32 — SQL Joins, Aggregation, and Operational Queries

Released Engineering Artifact:
`projects/ai-backend-data-layer/sql/003_relational_modeling_and_data_integrity.sql` — the relational
target schema (tenants, upload_sessions, documents, extended jobs, job_attempts, job_events,
outbox_events, result_artifacts, job_documents) with scoped uniqueness, CHECK allowlists,
`ON DELETE RESTRICT`, and tenant-aware composite foreign keys. Runnable after `001_create_jobs.sql` on a
fresh empty database; it is NOT a safe migration for populated tables (Day36)

---

### Day32

Topic:
SQL Joins, Aggregation, and Operational Queries

Topics:
`INNER` vs `LEFT JOIN` and missing-row meaning; join cardinality and row multiplication; `COUNT/SUM/MIN/
MAX/AVG/GROUP BY/HAVING`; conditional aggregation; CTEs as readable decomposition; operational queries
(Job detail, attempts/events, stuck Jobs by stage, oldest queued age, throughput, retry/terminal counts,
affected-release provenance); correctness before optimization.

Status:
✅ Completed

Released Lesson:
`docs/postgresql/day32-sql-joins-aggregation-and-operational-queries.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day31 — Relational Modeling and Data Integrity

Next Lesson:
Day33 — PostgreSQL Transactions and Atomic State Changes

Released Engineering Artifact:
`projects/ai-backend-data-layer/sql/004_sql_joins_aggregation_and_operational_queries.sql` — a read-only
operational query pack over the Day31 model (twelve parameterized statements in ten query groups, each with an explicit result
grain contract, deterministic `ORDER BY`, and a tenant predicate): an operational Job-Attempt view that
preserves zero-Attempt Jobs, per-Job Attempt/Event summaries via CTE pre-aggregation, conditional aggregation with `FILTER`,
NULL-aware recorded-cost reporting with completeness columns, stage-aware stuck candidates via
`DISTINCT ON`, half-open throughput windows, release-provenance affected sets, and read-only incident
evidence. Contains no DML, transactions, locks, indexes, `EXPLAIN`, or migrations (Day33-Day36)

Validation Limits:
Reduced-schema PostgreSQL 14.18 classroom runtime covered only the listed checks (LEFT JOIN placeholder
row, COUNT(*) vs COUNT(child pk), 3x4=12, conditional aggregation, cost completeness, CTE
pre-aggregation, two running-anomaly classifications, one last-hour succeeded throughput sample, and a
release-provenance DISTINCT set). It did NOT cover HAVING group filtering, DISTINCT ON current-Attempt
selection (the classroom used the greatest attempt_number path), an exact upper-bound boundary row, the
terminal-status allowlist, or queries 4b/5/10. Final 004 file PostgreSQL runtime: NOT RUN. Application
integration: NOT RUN. Production validation: NOT RUN.

---

### Day33

Topic:
PostgreSQL Transactions and Atomic State Changes

Topics:
Transaction boundary (`BEGIN/COMMIT/ROLLBACK`); ACID from production failures; atomic Job + Outbox
insert; atomic multi-table transition + append-only event; DB transaction vs external provider/Object
Storage/Redis side effect; constraint failure and rollback; transaction size/duration (never hold one
open during an eight-minute model call); Outbox remains at-least-once after relay publish.

Status:
✅ Completed

Released Lesson:
`docs/postgresql/day33-postgresql-transactions-and-atomic-state-changes.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day32 — SQL Joins, Aggregation, and Operational Queries

Next Lesson:
Day34 — Concurrency Control, MVCC, and Worker Claims

Released Engineering Artifact:
`projects/ai-backend-data-layer/sql/005_postgresql_transactions_and_atomic_state_changes.sql` — a
read-and-write transaction reference pack over the Day31 model: three short transactions (Accept =
Job + dispatch Outbox intent before 202; Start = guarded queued->running + Attempt + job_started Event;
Complete = Attempt finish guarded by finished_at IS NULL + guarded running->succeeded + Result Artifact +
job_succeeded Event + a CONDITIONAL job.succeeded Outbox)
around one external Provider/Object Storage phase held OUTSIDE any transaction, plus the Relay checkpoint.
Every guarded `UPDATE ... RETURNING` carries an explicit application control-flow contract. Contains no
locks, `FOR UPDATE`, `SKIP LOCKED`, indexes, `EXPLAIN`, migrations, or ORM (Day34-Day36)

Validation Limits:
Reduced-schema PostgreSQL 14.18 classroom runtime covered only five listed tests (Job+Outbox atomic
commit; duplicate Outbox id rolling the Job back; running Job + Attempt + Event coherence; duplicate
Artifact key rolling the completion back; the Outbox published_at NULL->timestamp checkpoint). Test 5
validated only PostgreSQL's checkpoint, NOT Redis publication. Final repository 005 file PostgreSQL
runtime: NOT RUN. Application/Provider/Object Storage/Redis/Celery integration: NOT RUN. Real Relay
crash/restart and consumer idempotency: NOT RUN. Day34 concurrency, production validation: NOT RUN.

---

### Day34

Topic:
Concurrency Control, MVCC, and Worker Claims

Topics:
Concurrent sessions and races; MVCC and snapshot visibility; isolation levels and dirty/non-repeatable/
phantom/lost-update boundaries; `SELECT ... FOR UPDATE`; `SKIP LOCKED` worker claiming and fairness/
starvation; optimistic vs pessimistic concurrency; DB lock vs application lease with expiry; deadlocks,
lock ordering, timeout, retry, observability; idempotency unique constraints still required.

Status:
✅ Completed

Released Lesson:
`docs/postgresql/day34-concurrency-control-mvcc-and-worker-claims.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day33 — PostgreSQL Transactions and Atomic State Changes

Next Lesson:
Day35 — PostgreSQL Indexes and Query Planning

Released Engineering Artifact:
`projects/ai-backend-data-layer/sql/006_concurrency_control_mvcc_and_worker_claims.sql` — a concurrency
claim pack over the Day31 model. ACTIVE: a `FOR UPDATE SKIP LOCKED` claim transaction that reserves one
queued candidate (tenant/status/order), reuses the unchanged Day33 guarded `queued->running` write with
explicit control-flow gates, inserts the Attempt + `job_started` Event, and commits before the Provider
call; plus an optimistic alternative and consistent-lock-order / retry guidance. CONCEPTUAL ONLY (commented,
not runnable): the application lease state machine (`claim_owner`/`lease_token`/`lease_expires_at`), whose
columns do not exist in the Day31 schema. Contains no `CREATE INDEX`, `EXPLAIN`, `ALTER`, migration, ORM, or
Redis (Day35-Day36)

Validation Limits:
Reduced-schema PostgreSQL 14.18 classroom runtime covered only three concurrency tests on a disposable
`jobs(job_id text, job_status text, created_at integer)` schema (FOR UPDATE SKIP LOCKED returning job-B while
job-A is locked; ordinary FOR UPDATE cancelled with `55P03` under `lock_timeout`; a reverse-order deadlock
aborted with `40P01`). That was NOT the full Day31 schema and did NOT run the final 006 artifact, the claim's
Attempt/Event inserts, or any lease field. Final 006 file PostgreSQL runtime: NOT RUN. Application/driver/
Celery multi-Worker, lease heartbeat/renewal/takeover, stale-token Completion, Provider idempotency, Object
Storage, Redis: NOT RUN. Day35 index plans and production validation: NOT RUN.

---

### Day35

Topic:
PostgreSQL Indexes and Query Planning

Topics:
Heap access and indexes as additional access structures; B-tree fundamentals; unique/composite/partial
indexes; composite-column order by predicate/order; index support for queued claims, stale leases,
idempotency keys, owner/history queries, unsent Outbox events; `EXPLAIN` vs `EXPLAIN ANALYZE`; sequential
scan is not automatically wrong; index costs (writes/storage/vacuum/cache); measure with representative
data when runtime is available.

Status:
✅ Completed

Released Lesson:
`docs/postgresql/day35-postgresql-indexes-and-query-planning.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day34 — Concurrency Control, MVCC, and Worker Claims

Next Lesson:
Day36 — Schema Evolution and Safe Migrations

Released Engineering Artifact:
`projects/ai-backend-data-layer/sql/007_postgresql_indexes_and_query_planning.sql` — an index/EXPLAIN DESIGN
reference pack over the Day31/Day34 access paths: the claim Partial Composite
`(tenant_id, created_at, job_id) WHERE job_status = 'queued' AND cancel_requested = false`, tenant history
candidates (all-status, dynamic-status composite, fixed-status partial alternative), the Outbox Partial
`(created_at, outbox_event_id) WHERE published_at IS NULL`, a deliberate NO-duplicate note for the Day31
`UNIQUE (tenant_id, idempotency_key)` index, parameterized `EXPLAIN` / `EXPLAIN ANALYZE` templates with
honest side-effect labels, and a conceptual-only stale-lease design that avoids a `now()` predicate.
Contains no `CREATE INDEX CONCURRENTLY`, `ALTER`, migration, or ORM (Day36)

Validation Limits:
Day35 has NO runtime evidence — everything is conceptual reasoning and static review. No Day35 SQL file,
PostgreSQL server, `EXPLAIN`, `EXPLAIN ANALYZE`, statistics refresh, representative data, benchmark,
application integration, production DDL, or rollback was run in class or during the repository update. Every
plan number (the 8M-row Seq Scan, estimate-1-vs-actual-20,000, and the 100->80 / 50->220 / +14 GB decision
case) is a classroom scenario for reasoning, not a measured result. Final 007 file PostgreSQL runtime: NOT
RUN. Safe index deployment (`CREATE INDEX CONCURRENTLY`, DDL-lock windows, rollout/rollback) is Day36.

---

### Day36

Topic:
Schema Evolution and Safe Migrations

Topics:
Migration as versioned state transition; forward/backward application compatibility; expand -> backfill
-> validate -> switch -> contract; DDL/table-lock/rewrite risks; safe nullable columns/defaults/
constraints; `NOT VALID`/validation and `CREATE INDEX CONCURRENTLY` boundaries; backfill batching/
progress/restartability/observability; rollback vs forward fix when data changed. SQLAlchemy/Alembic
deferred to Phase 4.

Status:
✅ Completed

Released Lesson:
`docs/postgresql/day36-schema-evolution-and-safe-migrations.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day35 — PostgreSQL Indexes and Query Planning

Next Lesson:
Day37 — PostgreSQL Production Reliability

Released Engineering Artifact:
`projects/ai-backend-data-layer/sql/008_schema_evolution_and_safe_migrations.sql` — a safe-migration DESIGN
reference pack that evolves the populated Day31/Day34 `app.jobs` into a Lease-aware model: preconditions and
a compatibility matrix; the phased Expand (nullable `claim_owner`/`lease_token`/`lease_expires_at`, no
fabricated default) -> compatible code -> drain old Workers -> `CHECK ... NOT VALID` -> bounded idempotent
`SKIP LOCKED` recovery/backfill (trusted source only, unknown ownership reconciled, no Provider calls) ->
`VALIDATE CONSTRAINT` -> Switch -> Contract; commented UNSAFE counter-examples (`NOT NULL`, `DEFAULT
gen_random_uuid()`); the Day35 stale-lease index as a commented non-transactional `CREATE INDEX
CONCURRENTLY` step with invalid-index handling; verification queries; and rollback-vs-forward-fix
boundaries. No SQLAlchemy/Alembic (Phase 4)

Validation Limits:
Day36 classroom status is conceptual reasoning and static review only. No Day36 SQL file, PostgreSQL server,
`ALTER`, constraint, index build, `EXPLAIN`, backfill, benchmark, Provider/Object Storage integration,
production DDL, or rollback command was run in class or during the repository update. Final 008 file
PostgreSQL runtime: NOT RUN. Application/Worker compatibility, old-Worker drain, token-guard Switch,
disposable-cluster DDL/backfill: NOT RUN. Live operation is Day37; SQLAlchemy/Alembic are Phase 4.

---

### Day37

Topic:
PostgreSQL Production Reliability

Topics:
Connection/session cost and pooling; pool sizing vs capacity; statement/lock/idle-transaction/application
timeouts; long transactions and vacuum/autovacuum mental model; roles/least privilege/credentials;
health/readiness vs successful business queries; backup vs replication (replication is not backup); base
backup/WAL/PITR and restore testing; core monitoring (connections, slow queries, locks/deadlocks,
transaction age, disk/WAL, replication lag, backup/restore evidence); managed vs self-operated.

Status:
✅ Completed

Released Lesson:
`docs/postgresql/day37-postgresql-production-reliability.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day36 — Schema Evolution and Safe Migrations

Next Lesson:
Day38 — Redis Foundations and Data Structures

Released Engineering Artifact:
`projects/ai-backend-data-layer/runbooks/postgresql-production-reliability.md` — an operational runbook /
evidence pack: a connection-capacity worksheet, the three short Job transaction boundaries, timeout / health
/ monitoring matrices, a long-transaction+Vacuum incident procedure with evidence-based per-table autovacuum
review, a least-privilege role matrix + credential-rotation procedure, a backup/PITR/restore drill with
RPO/RTO and explicit limitations, a replica-promotion gate, and the integrated 420-vs-300 connection incident
— every section labelled CONCEPTUAL / STATICALLY REVIEWED / RUNTIME NOT RUN / PRODUCTION NOT VALIDATED. No
SQLAlchemy/Alembic (Phase 4)

Validation Limits:
Day37 classroom status is conceptual reasoning and static review only — nothing was executed. No PostgreSQL
server or disposable cluster was started; no `psql`/SQL/configuration statement, connection pool, lock/
timeout/deadlock, idle transaction, Vacuum/autovacuum/`VACUUM FULL`, role/grant/credential/Secret/rotation,
Kubernetes probe/drain, base backup/WAL/PITR/isolated restore/integrity or business check, replica lag/
promotion/split-brain, or managed service was run, measured, or inspected. Every number (`160`, `420`, `300`,
the autovacuum settings, any RPO/RTO) is classroom arithmetic/design, not a measured result. RUNTIME NOT RUN;
PRODUCTION NOT VALIDATED.

---

### Day38

Topic:
Redis Foundations and Data Structures

Topics:
Redis server/database/key/value model and single-command atomicity; strings/hashes/lists/sets/sorted
sets by access pattern; key naming/versioning/tenant namespace; TTL/expiration; memory limits and
eviction as correctness concerns; RDB/AOF overview (Redis is not the Job source of truth); appropriate
Day28 uses (ephemeral progress, cache, broker transport, rate-limit counters) vs inappropriate ones
(authoritative Job lifecycle, large documents).

Status:
✅ Completed

Released Lesson:
`docs/redis/day38-redis-foundations-and-data-structures.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day37 — PostgreSQL Production Reliability

Next Lesson:
Day39 — Redis Cache Design and Consistency

Released Engineering Artifact:
`projects/ai-backend-data-layer/redis/redis-acceleration-layer-design.md` — a design/evidence pack: the
ownership model (PostgreSQL truth / Object Storage bytes / Redis rebuildable acceleration), the
tenant-scoped versioned key contract, a data-structure decision table, TTL and multi-command boundaries,
memory/eviction as a correctness concern, RDB/AOF loss windows, Redis-outage degradation, and the
missing-TTL incident with prefix-scoped recovery — every section labelled CONCEPTUAL / STATICALLY REVIEWED
/ RUNTIME NOT RUN / PRODUCTION NOT VALIDATED. No cache-consistency, messaging, or composition (Day39-41)

Validation Limits:
Day38 classroom status is conceptual reasoning and static review only — nothing was executed. No Redis
server, `redis-cli`, configuration, key/command, RDB/AOF file, cluster, workload, benchmark, eviction, or
integration was run, measured, or inspected. Any figure reused from Day37 is a placeholder, not a
measurement. Redis transactions/Lua, cache invalidation/stampede, Streams/Pub-Sub, and full rate-limiting
algorithms are Day39-41. RUNTIME NOT RUN; PRODUCTION NOT VALIDATED.

---

### Day39

Topic:
Redis Cache Design and Consistency

Topics:
Cache-aside read/write; cache key/version and serialization; TTL selection and jitter; invalidation on
durable-state change; stampede/single-flight/stale-while-revalidate; negative caching risk; cache
penetration and hot keys; stale cache vs PostgreSQL source of truth; hit ratio/latency/evictions/memory/
correctness metrics; fail-open vs fail-closed by sensitivity.

Status:
✅ Completed

Released Lesson:
`docs/redis/day39-redis-cache-design-and-consistency.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day38 — Redis Foundations and Data Structures

Next Lesson:
Day40 — Redis Messaging and Queue Semantics

Released Engineering Artifact:
`projects/ai-backend-data-layer/redis/redis-cache-consistency-design.md` — a design/evidence pack: the
per-endpoint cache-aside/invalidation contracts, commit-before-invalidate ordering with the pre-commit race,
cache key versioning, TTL and jitter, stampede/single-flight/stale-while-revalidate, the fail-open vs
fail-closed table, negative caching, correctness metrics, Outbox invalidation recovery, and the v2
cache-contract incident — every section labelled CONCEPTUAL / STATICALLY REVIEWED / RUNTIME NOT RUN /
PRODUCTION NOT VALIDATED. No messaging or composition (Day40-41)

Validation Limits:
Day39 classroom status is conceptual reasoning and static review only — nothing was executed. No Redis
server, `redis-cli`, cache API, PostgreSQL integration, Outbox Relay, Worker, Provider, Object Storage,
benchmark, cache stampede, eviction, hot key, TTL, or jitter was run, measured, or inspected. Numbers (10s,
50,000, TTL/jitter ranges) are illustrative, not measured. Redis messaging/Streams (Day40), transactions/Lua
and full rate limiting (Day41) are future boundaries. RUNTIME NOT RUN; PRODUCTION NOT VALIDATED.

---

### Day40

Topic:
Redis Messaging and Queue Semantics

Topics:
Lists/Pub-Sub/Streams as different models; Pub/Sub has no durable backlog/replay; Streams consumer
groups, pending entries, ack, claim/redelivery, trimming; ordering scope and consumer concurrency;
at-most-once vs at-least-once (idempotent consumers still required); queue transport vs durable Job
truth; Celery broker boundary (do not hand-build a Celery replacement); poison messages, retry/dead-
letter/quarantine at a conceptual boundary.

Status:
✅ Completed

Released Lesson:
`docs/redis/day40-redis-messaging-and-queue-semantics.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day39 — Redis Cache Design and Consistency

Next Lesson:
Day41 — Redis Coordination and Production Safety

Released Engineering Artifact:
`projects/ai-backend-data-layer/redis/redis-messaging-and-queue-semantics-design.md` — a design/evidence
pack: the List/Pub-Sub/Streams decision table, the small Stream payload contract, the Job-Worker and
notification Consumer Group topology, the PEL/ACK/Claim/redelivery lifecycle, the delivery-vs-durable-
completion boundary, per-side-effect idempotency/reconciliation, the retry classification and
quarantine/dead-letter boundary, the safe trim/retention contract, and the integrated failure/recovery
matrix — every section labelled CONCEPTUAL / STATICALLY REVIEWED / RUNTIME NOT RUN / PRODUCTION NOT
VALIDATED. Redis is not claimed to provide exactly-once, and no Celery replacement is built. No composition
(Day41)

Validation Limits:
Day40 classroom status is conceptual reasoning and static review only — nothing was executed. No Redis
server, `redis-cli`, Stream, Consumer Group, PEL, `XACK`, `XCLAIM`/`XAUTOCLAIM`, trim, Pub/Sub, List, or
PostgreSQL/Celery/Worker/Provider/email/Object Storage integration was run, measured, or inspected. Redis is
not claimed to provide exactly-once processing across Redis ACK + PostgreSQL commit + external Provider call.
Atomic composition/coordination/locks-leases/rate limiting are Day41. RUNTIME NOT RUN; PRODUCTION NOT
VALIDATED.

---

### Day41

Topic:
Redis Coordination and Production Safety

Topics:
Atomic command vs multi-command race; transactions and Lua only where atomic composition is required;
fixed/sliding-window/token-bucket rate limits; lock vs lease, ownership token, expiry, safe release,
fencing-token boundary; why a Redis lock alone cannot protect an external system from a paused/expired
owner; idempotency and PostgreSQL constraints as the final durable-write protection; eviction/RDB/AOF/
replication/failover data-loss windows; Redis security/isolation/auth/TLS/dangerous commands/monitoring/
capacity; managed vs self-operated.

Status:
✅ Completed

Released Lesson:
`docs/redis/day41-redis-coordination-and-production-safety.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day40 — Redis Messaging and Queue Semantics

Next Lesson:
Day42 — Backend Data Design Capstone

Released Engineering Artifact:
`projects/ai-backend-data-layer/redis/redis-coordination-and-production-safety-design.md` — a design/evidence
pack: the atomic rate-limit admission contract, the algorithm decision table (fixed/first-write-TTL/sliding/
token-bucket), the API idempotency boundary, the lease safety model (acquire/token/expiry/renew/atomic
compare-and-delete release + paused-owner timeline), the fencing model, the PostgreSQL completion guard
(running + current token + unexpired lease + fencing generation, extending Day34/Day37), the Redis loss/
capacity matrix (RDB/AOF/replication/failover/eviction), the security matrix (network/auth/ACL/TLS/dangerous-
command), and the integrated failure runbook — every section labelled CONCEPTUAL / STATICALLY REVIEWED /
RUNTIME NOT RUN / PRODUCTION NOT VALIDATED. Redis is not promoted to business truth; no exactly-once is
claimed. No capstone integration (Day42)

Validation Limits:
Day41 classroom status is conceptual reasoning and static review only — nothing was executed. No Redis server,
Sentinel, Cluster, managed Redis, `redis-cli`, Lua, `MULTI`/`EXEC`/`WATCH`, ACL, TLS, persistence, eviction,
failover, rate limiter, FastAPI endpoint, PostgreSQL Job/Attempt/Event/Outbox/lease/fencing SQL, Provider,
Object Storage, or Worker drain/handoff was run, measured, or inspected. Every number (60/min, 30s, capacity
10, refill 1/s) is a static design example. Redis remains a coordination/protection control; PostgreSQL stays
the durable business authority. The Day42 capstone is a future boundary. RUNTIME NOT RUN; PRODUCTION NOT
VALIDATED.

---

### Day42

Topic:
Backend Data Design Capstone

Topics:
Integrate PostgreSQL schema/constraints/queries/transactions/concurrency/indexes/migrations/operations
with Redis cache/messaging/rate-limit/lease boundaries (durable truth stays in PostgreSQL); final data
ownership/lifecycle map (Upload Session, Document, Job, Attempt, Event, Outbox, Result Artifact, cache
entries, messages, large Object Storage bytes); failure matrix and recovery priority/degraded modes/
reconciliation/data repair/verification; performance from measured plans; security/tenant/retention/
audit; phase-level Beginner/Intermediate/Senior English system-design interview; explicit validation
results and limitations.

Status:
✅ Completed

Released Lesson:
`docs/redis/day42-backend-data-design-capstone.md`

Template:
LESSON_TEMPLATE_v2

Previous Lesson:
Day41 — Redis Coordination and Production Safety

Next Lesson:
Day43 — AI Backend Product Contract and FastAPI Request Lifecycle (Phase 4)

Released Engineering Artifact:
`projects/ai-backend-data-layer/capstone-backend-data-design.md` — the Phase 3 capstone design/evidence pack
integrating Day29-Day41: the ownership/lifecycle map, the acceptance contract (durable-at-202), dispatch and
at-least-once duplicate handling, the short guarded completion transaction and Artifact reconciliation, the
failure/degraded matrix (Redis/PostgreSQL/Object Storage), the Upload Session verification contract, tenant
isolation (authenticated predicate + composite tenant-aware FKs) with append-only audit and tombstoned
retention, the disposable `EXPLAIN ANALYZE` performance-evidence method, the fencing-generation
Expand->Contract migration, and the integrated failover/paused-Worker/Artifact recovery runbook — every
section labelled CONCEPTUAL / STATICALLY REVIEWED / RUNTIME NOT RUN / PRODUCTION NOT VALIDATED

Validation Limits:
Day42 classroom status is conceptual reasoning and static review only — nothing was executed. No PostgreSQL,
Redis, Object Storage, Provider, Celery/Relay/Worker, or FastAPI command was run; no migration and no
`EXPLAIN ANALYZE` were executed; no failover/load/security/data-repair test was performed. `EXPLAIN ANALYZE`
and disposable-environment measurement are described as a future validation method only. Every key/ID/threshold
is a static design example. SQLAlchemy/Alembic are Phase 4 and are not implemented or taught here. This closes
Phase 3; Phase 4 begins at Day43. RUNTIME NOT RUN; PRODUCTION NOT VALIDATED.

---

## Phase 4 — Production AI API Engineering (Day43–Day58)

Status:
In Progress (Day43 completed)

Objective:
Turn the Day28–Day42 conceptual architecture and data contracts into a runnable, testable Production AI
Backend API. This is where the data-ownership and failure model becomes executable FastAPI + SQLAlchemy +
Alembic + Redis/Outbox/Worker + Object Storage + an OpenAI-compatible provider, with authentication and
tenant isolation.

Knowledge connection:

```text
Day42 Data Ownership and Failure Contracts
    -> FastAPI Production AI API (runnable, tested, deployable)
```

Unified production scenario (Phase 4 onward): a **Multi-tenant AI Research and Automation Platform**.
Reused project directories (no new duplicates): `projects/fastapi-todo/` (small warm-up only, not a portfolio
centerpiece), `projects/fastapi-auth/` (auth + tenant module), and `projects/ai-backend-data-layer/` (the
durable data foundation from Phase 3). SQLAlchemy/Alembic are introduced here on top of the raw
PostgreSQL/SQL mental models from Phase 3.

Per-day topics (Topic + concise scope; each Status: Planned, no lesson generated yet):

- Day43 — AI Backend Product Contract and FastAPI Request Lifecycle.
  Scope: request/response lifecycle, routing, the AI Job API product contract over the Day42 model.
  Connection: turns the Day42 data-ownership and failure contracts into an HTTP API boundary; Day44 formalizes its typed request/response contracts.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day43-ai-backend-product-contract-and-fastapi-request-lifecycle.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day43-ai-job-api-contract.md` (commit-before-202 boundary, route/error/status matrix, idempotency decision table, tenant isolation, HTTP-vs-durable lifecycle + guarded-claim gate, cancellation-intent boundary, integrated failure/rollback). Conceptual/static contract review only — FastAPI / PostgreSQL / Relay-Worker / Redis-Object-Storage-Provider / integration / production runtime NOT RUN. Pydantic v2 (Day44), DI/lifespan/adapters (Day45), SQLAlchemy/Alembic (Day46-48), durable cancellation (Day54), Celery (Day55) are not taught here.
- Day44 — Pydantic v2 and Structured AI Input/Output Contracts.
  Scope: validation, typed request/response, structured AI output contracts and error shapes.
  Connection: takes the Day43 API boundary and adds validated, typed AI input/output contracts; Day45 wires them through dependency injection and provider adapters.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day44-pydantic-v2-and-structured-ai-input-output-contracts.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day44-pydantic-contracts-design.md` with runnable `day44_pydantic_contracts.py` + `test_day44_pydantic_contracts.py` (boundary ladder, request discriminated union, strict MaxTokens/Confidence, untrusted-Provider StructuredAIResult, status-discriminated public responses, public error envelope, validate-before-side-effects gate, 37-Job model_construct incident). REAL Pydantic v2 tests executed (Pydantic 2.5.0, pytest -> 24 passed; completion target is an in-memory callback, not PostgreSQL). FastAPI/auth/PostgreSQL/SQLAlchemy/real-Provider/integration/production NOT RUN. DI/lifespan/adapters (Day45), SQLAlchemy (Day46-48), real Provider SDK (Day53) are not taught here.
- Day45 — Dependency Injection, Lifespan, Configuration and AI Provider Adapters.
  Scope: DI, app lifespan, settings/secrets boundary, a provider-adapter seam.
  Connection: gives the Day44 contracts their runtime wiring (DI, lifespan, config, provider seam); Day46 persists them through SQLAlchemy over the Day42 model.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day45-dependency-injection-lifespan-configuration-and-ai-provider-adapters.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day45-di-lifespan-configuration-and-ai-provider-adapters-design.md` with runnable `day45_composition.py` + `test_day45_composition.py` (per-process ownership, lifespan-owned Settings/HTTP-client/ProviderAdapter Container with reverse-order close, `Depends`-supplied `get_provider`, stateless `JobService`, validated secret-aware `Settings` with `SecretStr`, small `AIProvider` seam + `FakeAIProvider`, partial-init cleanup, Day44 Provider-output validation before an in-memory completion, rotation/drain/rollback + invalid-Provider-output incident). REAL local FastAPI composition tests executed with a FAKE no-network Provider (Python 3.10.12, fastapi 0.110.0, httpx 0.27.0, pydantic 2.5.0, pytest 7.4.3 -> 20 passed; completion target is an in-memory list, not PostgreSQL). Real Provider SDK/network, PostgreSQL/SQLAlchemy, Celery/Redis, Secret rotation/drain, integration/production NOT RUN. SQLAlchemy mapping (Day46), async sessions/transactions (Day47), Outbox acceptance (Day50), real Provider SDK (Day53), streaming/cancellation (Day54), Celery (Day55), retries/backpressure (Day56) are not taught here.
- Day46 — SQLAlchemy 2.0 Mapping for the Day42 Data Model.
  Scope: map Job/Attempt/Event/Outbox/Upload Session/Artifact to the durable schema without changing ownership.
  Connection: maps the Day42 durable model into SQLAlchemy without changing ownership; Day47 drives it with async sessions, transactions, and a repository/unit-of-work.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day46-sqlalchemy-mapping-for-the-day42-data-model.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day46-sqlalchemy-mapping-for-the-day42-data-model-design.md` with runnable `day46_orm_mapping.py` + `test_day46_orm_mapping.py` (faithful SQLAlchemy 2.0 typed declarative mapping of the Day42 `app`-schema durable contract — Job/JobAttempt/JobEvent/OutboxEvent/UploadSession/ResultArtifact + a minimal Tenant support stub — preserving server defaults, named UNIQUE/CHECK/FK constraints, ON DELETE RESTRICT, TEXT+CHECK status (not a native enum), Job-scoped attempt uniqueness, and the same-Job composite provenance FK; `relationship()` navigation only; ORM/Pydantic separation; wrong-schema failure/reconciliation drill). REAL static metadata-contract tests executed (Python 3.10.12, SQLAlchemy 2.0.29, pytest 7.4.3 -> 20 passed; declared STRUCTURE only). PostgreSQL runtime NOT RUN (no server; `create_all()` not used and not compatibility evidence). AsyncSession/transactions/repository/UoW (Day47), Alembic migrations (Day48), Outbox acceptance (Day50), Celery (Day55) are not taught here; Document/job_documents remain a stated unimplemented mapping limitation.
- Day47 — Async Sessions, Transactions, Repository and Unit of Work.
  Scope: async session lifecycle, transaction boundaries, repository + unit-of-work over the Day33 guarantees.
  Connection: adds transactional persistence over the Day33 guarantees behind the Day46 mapping; Day48 evolves that schema safely with Alembic.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day47-async-sessions-transactions-repository-and-unit-of-work.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day47-async-persistence-boundary-design.md` with runnable `day47_async_uow.py` + `test_day47_async_uow.py` (process-scoped AsyncEngine/async_sessionmaker helpers, a request/Job-scoped AsyncSession, repositories that never commit, a UnitOfWork with explicit commit/rollback/close, the guarded `UPDATE ... WHERE job_status='queued' RETURNING` claim with zero-row stale/no-op, flush-before-dependent-write, a second guarded completion UoW, correlation-key-before-the-Provider-call recovery, and the integrated success/crash recovery drill; reuses the Day46 mapping, no schema redefinition, no global Session, no repo-owned commit, no Provider call inside a DB transaction). REAL fake-session control-flow tests executed (Python 3.10.12, SQLAlchemy 2.0.29, greenlet 3.5.4, pytest 7.4.3 -> 29 passed). PostgreSQL runtime NOT RUN (no server/driver; a mock is not database proof; SQLite is not PostgreSQL evidence). Alembic (Day48), the upload workflow (Day49), idempotent acceptance/Outbox (Day50), real Provider SDK (Day53), and FastAPI/Worker integration/production are not taught here.
- Day48 — Alembic and Safe AI Backend Schema Evolution.
  Scope: Alembic migrations enforcing the Day36 Expand/Backfill/Validate/Switch/Contract discipline.
  Connection: brings the Day36 safe-migration discipline to the Day46/47 SQLAlchemy schema via Alembic; Day49 adds the upload and Object-Storage boundary on top.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day48-alembic-and-safe-ai-backend-schema-evolution.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day48-alembic-safe-schema-evolution-design.md` with a runnable Alembic control plane `day48_alembic/` (minimal `env.py` + gated Expand/Validate/Contract revisions for the Lease evolution of `app.jobs`), an operational restartable `FOR UPDATE SKIP LOCKED` backfill `day48_lease_backfill.py` (kept off the migration), and `test_day48_alembic.py` (a SPLIT linear chain (pure Expand columns `0002` = old/new compatibility window; a SEPARATE constraint revision `0003` adds the triple-coherence + Day36 core `jobs_running_requires_lease` `NOT VALID` only after old Writers are drained/isolated, since `NOT VALID` enforces every future write by any Writer version; `0004` validates; `0005` contracts); the backfill routes unknown-ownership Jobs into an independent queue table `app.job_lease_reconciliation` (`INSERT ... ON CONFLICT DO NOTHING`, no `app.jobs` write, no fabrication; created additively in Expand, with the reconciliation polling/backoff columns `next_attempt_at`/`last_checked_at`/`check_attempts` added forward by a SEPARATE additive BRANCH revision `0006_add_reconciliation_polling` off `0003`, merged back to a single head by `0007_merge_reconciliation_polling` — revision immutability, since `0002`/`0003`/`0004`/`0005` may already be applied and their parentage must not be rewritten) so the automatic loop terminates (excluded via `NOT EXISTS`) and is restart-safe — routing writes only the queue so it is legal after the strict constraint (a marker UPDATE that left the row running+NULL-Lease would be rejected) — but queuing is triage not resolution — such a row still violates `jobs_running_requires_lease` and still counts in `unresolved_running_without_lease` (the hard VALIDATE precondition, reached only by a trusted Lease backfill or an audited real recovery routed by `classify_unknown_running_recovery` — verified `succeeded` to the Day47 completion UoW, `failed`/`cancelled` to guarded terminal-recovery, unknown kept as reconciliation, a `queued` requeue or bare status flip refused); `env.py` resolves the DB URL by `-x db_url` > env `DAY48_ALEMBIC_DATABASE_URL` with the ini placeholder offline-render only (online fails fast); separate `VALIDATE CONSTRAINT` of both constraints; destructive gated Contract; single-head linear revision graph; minimal control-plane `env.py`; no long loop in any `upgrade()`; classify/backfill/reconcile without fabrication; forward-fix vs downgrade; baseline/`stamp`; autogenerate review; `CREATE INDEX CONCURRENTLY` non-transactional). REAL static/offline evidence executed (Alembic revision-graph + migration-source inspection and fake-session backfill control flow -> 44 passed; Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3) plus an offline `alembic upgrade --sql` DDL render. PostgreSQL runtime NOT RUN (no server; SQLite/fake/`upgrade`-success are not PostgreSQL proof; a real `NOT VALID`/`VALIDATE`/backfill test would apply the Day42 raw SQL and prove behavior). The Day49 upload workflow, Day50 Outbox/Celery delivery, Day53 Provider SDK, Day55 worker runtime, FastAPI/Worker integration, and production migration are not implemented here.
- Day49 — Upload Sessions, Object Storage and Artifact Verification.
  Scope: presigned upload sessions, Object Storage boundary, deterministic artifact reference/verification.
  Connection: adds presigned uploads and Object-Storage artifact verification to the persisted model; Day50 makes Job acceptance idempotent with the Outbox.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day49-upload-sessions-object-storage-and-artifact-verification.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day49-upload-object-storage-and-artifact-verification-design.md` with a runnable provider-neutral control-flow model `day49_upload_verification.py` + `test_day49_upload_verification.py` (fake in-memory Object Storage adapter): server-owned deterministic key identity (client key cannot override the persisted key), expected-vs-observed verification that never rewrites the frozen expectation and never accepts an ETag as a SHA-256, a fail-closed content/security gate with a persistent verification hold (modeled `verifying` + `verification_hold_until` so a transient scanner outage is not deleted by cleanup), legal-state + expiry-guarded finalization (INITIATED/FAILED/EXPIRED and cleanup-claimed rows rejected), a create-only + version-history object adapter (exact-version inspect/delete), a MODELED atomic Document+verify Unit of Work (mid-transaction failure leaves neither fact), server-owned full identity (bucket+key + bound version; completion rejects client-supplied identity; observed bucket/key/version/size/sha256/content-type verified), idempotent Document finalization (external verification outside the DB tx -> short guarded UoW creates exactly one Document via the modeled `UNIQUE(documents.upload_session_id)` + guarded transition, already-verified retry returns the same Document), completion-vs-cleanup concurrency made deterministic via a verification LEASE (owner/fencing token + `verification_hold_until`) taken and an exact version bound BEFORE scanning, with a guarded compare-and-set commit (`commit_document_if_owner`) that refuses a stale-lease or cleanup-won row (never flips EXPIRED back to VERIFIED) and a `claim_cleanup` that returns an exact-version reference (or NO_OBJECT_PRESENT) with an `execute_cleanup_delete` that reports DELETED vs VERSION_ABSENT_RECONCILE — proven by interleaving fake-adapter tests; credential expiry is distinguished from session expiry (an object uploaded before credential expiry still completes before session expiry; absent -> UPLOAD_WINDOW_EXPIRED) — with the three expiry lifecycles (`cleanup_not_before = credential_expiry + clock_skew + safety_buffer`, e.g. 12:03) and never a DB lock over storage I/O, multipart unknown-completion recovery (parts are transport progress not a Document; a timed-out Complete inspects the deterministic final object first), output ResultArtifact ordering + crash recovery without re-calling a paid Provider, and tenant provenance modeled by the composite FK `(tenant_id, upload_session_id)` (distinct from `UNIQUE`). Schema honesty: the published `upload_sessions` allowlist has no `verifying` status, no owner/lease token, no `verification_hold_until`, and no bound-version column — all MODELED in-memory; the real schema needs a Day48-safe FORWARD migration (a `verifying` status + owner/hold columns via a branch revision, or a verification-lease table, plus a bound-version column) — not implemented here, never a rewrite of published history. REAL fake-adapter tests executed — application control flow only, hardened after Codex review rounds 1-2 (Python 3.10.12, pytest 7.4.3 -> 44 passed; module + tests are Python-standard-library only). PostgreSQL runtime, real Object Storage (presign/checksum/multipart/versioning) semantics, FastAPI/scanner integration, and production are NOT RUN; Day50 Outbox, Day51 JWT, Day52 authorization, Day55 Celery, and a real Provider are not implemented here.
- Day50 — Idempotent AI Job API and Transactional Outbox Integration.
  Scope: the client-idempotency-key + `(tenant_id, idempotency_key)` boundary and the Outbox dispatch intent end to end.
  Connection: makes Job acceptance idempotent (client key + PostgreSQL uniqueness) and wires the Outbox dispatch intent; Day51 secures who may call it.
  Implementation boundary: see "Future Lesson Implementation Boundaries" (Day50) below.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day50-idempotent-ai-job-api-and-transactional-outbox-integration.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day50-idempotent-job-acceptance-and-transactional-outbox-design.md` with a runnable provider-neutral control-flow model `day50_job_acceptance_outbox.py` + `test_day50_job_acceptance_outbox.py` (fake in-memory store + `TransportAdapter`): client `Idempotency-Key` = identity of one logical command and `compute_request_fingerprint` = evidence the semantics did not change (the key is not fingerprint material; Document order preserved unless an explicitly unordered contract); `UNIQUE(tenant_id, idempotency_key)` as the concurrent DB arbiter modeled by `upsert_job_on_conflict` (`INSERT ... ON CONFLICT ... RETURNING`) — same key+fingerprint returns the original Job, a changed fingerprint is 409 with no durable facts, a missing key is rejected before writes, and every referenced Document must be Day49-verified + tenant-owned; one short atomic UoW creates the Job + exactly one `job.dispatch_requested` Outbox intent (mid-transaction failure leaves neither; at-most-one dispatch intent = logical `UNIQUE(job_id, event_type)`); an Outbox Relay that never publishes inside the DB tx — claim (`FOR UPDATE SKIP LOCKED` + lease/owner) -> publish OUTSIDE the lock via a small `TransportAdapter.publish(envelope)` (small stable envelope: outbox_event_id/event_type/job_id/correlation, no prompt/secret) -> fenced checkpoint sets `published_at` (only a publication checkpoint, not Job success); at-least-once recovery (publish-then-crash-before-checkpoint retains the intent and republishes as a duplicate; transient failure increments attempt_count, stores a redacted error, computes `next_attempt_at` with bounded exponential backoff + jitter; exhausted -> QUARANTINED retention that never marks the Job failed); relay concurrency via short claim + lease + fencing token (a stale relay cannot checkpoint after takeover) with no DB lock over transport I/O; and a Worker guarded `UPDATE ... WHERE job_status='queued' RETURNING` claim that absorbs duplicate delivery into a single Provider-eligible winner. No exactly-once is claimed across PostgreSQL + broker + Worker + Provider. Schema honesty: the published schema HAS `UNIQUE(tenant_id, idempotency_key)` but LACKS a request-fingerprint column, `UNIQUE(job_id, event_type)`, and relay ops columns (attempt_count/last_error/next_attempt_at/dispatch-quarantine state/relay owner+lease+fencing token) — all MODELED in-memory; the real schema needs a Day48-safe FORWARD additive migration (new nullable columns + a partial/logical unique index via a branch revision), not implemented here, never a rewrite of published history. REAL fake-adapter tests executed — application control flow only (Python 3.10.12, pytest 7.4.3 -> 29 passed; module + tests are Python-standard-library only). Real PostgreSQL UNIQUE/tx/isolation/`ON CONFLICT`/`SKIP LOCKED`, a real broker/Celery (ACK/redelivery/poison), Worker/Provider runtime, integration, and production are NOT RUN; Day51 authentication, Day52 authorization/quota, Day53 real Provider, and Day55 real Celery are not implemented here.
- Day51 — Authentication, Password Security and JWT.
  Scope: password hashing, JWT issuance/verification, session/token boundaries.
  Connection: adds authentication (passwords + JWT) to the Day43-50 API; Day52 turns identity into tenant isolation and authorization.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day51-authentication-password-security-and-jwt.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day51-authentication-password-security-and-jwt-design.md` with a runnable provider-neutral control-flow model `day51_authentication_jwt.py` + `test_day51_authentication_jwt.py` using REAL crypto (Argon2id via argon2-cffi; asymmetric RS256 JWT via PyJWT + cryptography) with EPHEMERAL in-process keys and an in-memory user + `AuthSession` store: adaptive Argon2id password hash/verify (`PasswordService` — SECURE production default cost tuned per deployment hardware, weak params injected only in tests; hash encodes algo/salt/cost, one generic `authenticate` failure + decoy verify for anti-enumeration, `needs_rehash` upgrade; a fast SHA-256 digest is used only for a high-entropy refresh secret, never a password); minimal non-secret JWT claims (`sub/iss/aud/iat/exp/jti`, never a password hash/provider key/prompt/Document content/secret/client tenant); a full verification contract (`verify_access_token` pins `ALLOWED_ALGS=("RS256",)`, resolves a trusted key by an allowlisted `kid`, verifies signature + iss + aud + exp + nbf + required `sub` -> `AuthenticatedIdentity(user_id=sub)`, rejecting `alg=none`, HS256 algorithm-confusion, wrong iss/aud, expired, not-yet-valid, missing sub, and tampered signatures); `kid` allowlist with a trusted-source unknown-kid refresh (else reject), emergency `revoke_key` that ALSO blocks signing (revoking the current signing key fails closed until a prepared K2 is promoted via `set_current_signing_kid`) before expiry, and a planned K1->K2 rotation overlap then `drop_key`; a per-device Refresh `AuthSession` storing only `refresh_token_hash` with a guarded `rotate_refresh` modeling `UPDATE ... WHERE current_hash + active + not-expired RETURNING` (single winner; all-or-nothing rollback keeps A on partial-persistence failure), a bounded one-time retry-grace (`GRACE_RETRY` recovers the SAME usable replacement token B once from a short-TTL encrypted recovery slot, never an A->C branch) vs a `REPLAY_DETECTED` on ANY used family token (a per-family used-hash ledger detects replay of any earlier token, not just the latest) that revokes and RETAINS the `token_family_id` audit evidence and isolates other devices, a minimum-retention `sweep_expired_recovery_material` that destroys the recovery ciphertext + grace hash once past `retry_grace_expires_at` even if the old token is never resubmitted (fail-closed on time; used-token ledger + audit retained so post-grace replay stays `REPLAY_DETECTED`, not `INVALID`; a real deployment runs it as a reliable scheduled cleanup job), and `revoke_session` (current device) vs `revoke_all_user_sessions` (all revoke paths destroy recovery material immediately via a shared `_clear_recovery_material` helper; the sweep is only the abandoned-token expiry fallback); and a browser cookie/Origin/CSRF decision contract (`evaluate_state_change_request` — HttpOnly is not CSRF defense; reject cookie-only cross-site without a valid Origin + CSRF token). Authentication establishes a trusted `user_id`; a client-supplied `tenant_id` is not authority (Day52). REAL crypto + control-flow tests executed (Python 3.10.12; argon2-cffi 23.1.0, PyJWT 2.8.0, cryptography 48.0.0, pytest 7.4.3 -> 37 passed) — proving the crypto primitives + application control flow ONLY. Real PostgreSQL (UNIQUE/constraint/transaction/isolation or `UPDATE ... RETURNING`), real FastAPI/browser (cookies/SameSite/Origin/CSRF at the wire), a real JWKS endpoint, integration, and production are NOT RUN; JWE is out of scope; Day52 authorization/quota, Day53 real Provider, and Day55 real Celery are not implemented. Schema honesty: a `password_hash` column and the per-device `AuthSession` table are new facts MODELED in-memory; the real schema needs a Day48-safe FORWARD additive migration (new table + unique/index via a branch revision), not implemented here, never a rewrite of published history. No plaintext passwords, refresh tokens, JWTs, or operational signing keys are committed.
- Day52 — Authorization, Tenant Isolation, Quotas and API Security.
  Scope: tenant isolation, per-tenant quotas/rate limits, authorization and API security boundaries.
  Connection: enforces tenant isolation, quotas, and authorization over the authenticated API; Day53 connects the real AI provider behind that boundary.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day52-authorization-tenant-isolation-quotas-and-api-security.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day52-authorization-tenant-isolation-quotas-and-api-security-design.md` with a runnable provider-neutral, standard-library-only in-memory model `day52_authorization_tenant_quota_security.py` + `test_day52_authorization_tenant_quota_security.py`: turns Day51's trusted `user_id` into current, tenant-scoped, action-specific, cost-aware authority. A client-supplied `tenant_id` is only a SELECTOR; authority is the server-built `AuthorizedTenantContext(user_id, tenant_id, permissions)` produced by `authorize` only after verified identity + active `tenant_memberships(user_id, tenant_id, role, status)` + the required action (effect-named `job.create`/`job.read_own`/`job.read_all`/`job.cancel`/`job.retry`; every failure a generic 403; Membership removal/role downgrade revokes authority per request, so a JWT role claim is not sole long-lived authority). Tenant + owner scoped reads (`JobRepository.read_job` -> `WHERE tenant_id = authorized AND job_id`, `job.read_own` also requires `created_by_user_id == authenticated_user_id`) return a public 404 on a cross-tenant miss (no existence oracle); FastAPI Dependencies centralize policy but repositories must carry the context (RLS is optional defense-in-depth whose tenant context comes from `AuthorizedTenantContext`, never Header/Body). Three distinct controls: a shared, fail-closed `TokenBucketRateLimiter` (speed; multi-instance local counters undercount ~4×100=400; outage on a paid path -> 503 not 429; healthy breach -> 429 + `Retry-After`); a durable PostgreSQL token/cost quota via a guarded `UPDATE tenant_budgets SET reserved_tokens = reserved_tokens + :amt WHERE token_limit - used_tokens - reserved_tokens >= :amt RETURNING` single winner with Reservation + Job + Outbox committed in ONE transaction (all-or-nothing rollback -> no ghost reservation / unfunded Job), plus `reconcile` that safely settles actual usage: `actual <= reserved` records the exact actual and releases the remainder, `actual is None` holds `reconciliation_pending`, a negative actual is rejected, and `actual > reserved` returns `OVERAGE_RECONCILIATION_REQUIRED` (keep reservation, record the exact observed usage + reason, never `min()`-truncate or release as settled — a real system reserves the total billable cost, not only `max_tokens`, and Day53's Provider adapter owns the estimate/headroom + overage policy) — and `reconcile` is IDEMPOTENT via a per-job lifecycle status (`RESERVED -> {RECONCILIATION_PENDING} -> SETTLED | OVERAGE_RECONCILIATION_REQUIRED`): an at-least-once repeat of the same actual is a no-op, a different actual after `SETTLED` returns `RECONCILIATION_CONFLICT` (no re-settle, no fake overage), a post-overage plain reconcile stays in overage, and only an explicit `settle_overage` may change the fact — and it never bypasses the hard quota (it settles the full observed usage only when `available` stays >= 0 via tenant headroom or a trusted ops-approved `granted_extra_tokens` credit, else stays in overage; idempotent; the exact usage + credit are retained as audit); and a concurrency limit (in-flight pressure). Idempotency runs AFTER authorization (`admit_job`: authorize -> same-command tenant-scoped recovery with no new cost/no rate-limit charge -> rate-limit new commands -> reserve + create): the request fingerprint is COMPUTED SERVER-SIDE (`compute_request_fingerprint` = SHA-256 of canonical JSON of the behavior-relevant fields `max_tokens`/`document_id`/`task_type`, never Python `hash()`, never a client-asserted value): same tenant+key+same SERVER fingerprint returns the original Job with no second reservation, any changed behavior-relevant field yields a different fingerprint -> 409 with no new facts, and a removed Membership blocks old-Key recovery (not an authz bypass). Production exercise: an erroneous `member -> job.cancel` grant is contained by rolling back the bad grant (future traffic only), then a guarded `repair_bad_intent` targeted by stable intent ID + `policy_version` invalidates pending bad intents (zero `UPDATE ... RETURNING` rows -> stop and reconcile; a legitimate later cancel is never overwritten; intents are retained as audit evidence, never deleted). In-memory control-flow tests executed (Python 3.10.12, pytest 7.4.3 -> 32 passed; standard-library only) — application control flow ONLY. Real PostgreSQL (constraint/transaction/isolation/`UPDATE ... RETURNING`/RLS), real Redis (distributed limiter atomics/TTL/failover), real FastAPI/proxy/browser (Dependency/CORS/cookie/CSRF/routes), Provider/Worker, integration, and production are NOT RUN; Day53 real Provider, Day54 streaming/cancellation, and Day55 real Celery are not implemented. Schema honesty: `tenant_memberships`, `tenant_budgets(token_limit/used_tokens/reserved_tokens)`, per-Job `max_tokens`, and a cancel-intent audit ledger with `policy_version` are new facts MODELED in-memory; the real schema needs a Day48-safe FORWARD additive migration (new tables + indexes via a branch revision), not implemented here, never a rewrite of published history. No real JWT, Provider key, password, raw prompt, Document content, or user data is used or logged.
- Day53 — OpenAI SDK, Provider Boundaries and Structured Output.
  Scope: OpenAI-compatible SDK usage, provider boundary, structured-output parsing and validation.
  Connection: introduces the OpenAI-compatible provider and structured output behind the Day45 adapter seam; Day54 handles its streaming and cancellation.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day53-openai-sdk-provider-boundaries-and-structured-output.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day53-openai-sdk-provider-boundaries-and-structured-output-design.md` with a runnable provider-neutral model `day53_openai_provider_structured_output.py` + `test_day53_openai_provider_structured_output.py` using REAL Pydantic v2 validation + an INJECTED FAKE transport (the real `openai` SDK is intentionally not a dependency; all SDK objects/exceptions are modeled inside the Adapter): puts an OpenAI-compatible Provider behind an application-owned boundary so SDK behavior, untrusted output, cost evidence, and configuration changes cannot corrupt durable Job facts. Layering keeps SDK types inside `OpenAICompatibleAdapter` (Router/Dependency -> Application Service -> `AIProvider.generate(request: ProviderRequest) -> ProviderOutcome` -> Adapter -> Day44 validation -> `CompletionService` -> Repository), where the Adapter translates SDK responses/vendor exceptions into a typed `ProviderOutcome` union (`ProviderSuccess`/`ProviderRefusal`/`ProviderIncomplete`/`ProviderTimeout`/`ProviderAuthenticationError`/`ProviderRateLimited`/`ProviderCapabilityError`/`ProviderTransportError`) and NEVER completes Jobs or writes DBs; a `ProviderSuccess` payload is UNTRUSTED until a strict Day44 `StructuredOutputValidator` (`extra="forbid"`) validates it against the Job's bound server-owned versioned `SchemaRegistry` schema (`research_summary.v1/v2`; missing `citations`/forbidden `debug_prompt` -> CONTRACT_VIOLATION; unknown version -> SCHEMA_NOT_FOUND; a v2 output never silently satisfies a v1 Job — no implicit truncation/downgrade/guess), and only then does the `CompletionService` run the ONLY guarded `running -> succeeded` short UoW (zero rows -> stop, inspect + reconcile, never overwrite) persisting a Result Artifact of the validated domain result + safe metadata ONLY (raw minimization — no raw payload/prompt/secret). Business execution success and cost settlement are SEPARATE axes: a valid output can be `succeeded` even when usage is UNKNOWN, retaining the Day52 reservation as `reconciliation_pending` (never zero); refusal/incomplete/timeout(unknown-usage)/401-403(disable the Provider config + keep evidence)/429(downstream Job event + safe Retry-After, not a client 429)/400(capability/config failure) are classified without fabricating success or cost; Day45 validated Settings + Adapter own `api_key`/`base_url`/model policy (never request payloads; client model choice is only a constrained selector -> allowlisted model), only non-secret execution-contract facts are persisted, the Job-controlled 5,000 output cap wins over an 8,000 adapter default (`effective = min(Job cap, ceiling)`, never enlarged; usage reported, no second reservation), and one lifespan-owned client is reused per process (drain before close). Integrated exercise: a rollout to a model lacking `research_summary.v1` gives NEW calls a 400, but a legitimate OLD in-flight v1 result (a distinct call) still validates against its PERSISTED execution contract and is accepted via guarded completion — configuration rollback governs NEW calls and is NOT a rollback of durable business facts. The outgoing Provider call is bound to the persisted execution contract (`bind_request_to_contract` derives model/schema/version/task/profile from the contract; a mismatch is `CONTRACT_MISMATCH` before any transport call; the token budget is tightened, never enlarged); an ATOMIC pre-call claim creates exactly one in-flight `Attempt` BEFORE any paid Provider call (only a RUNNING Job with no open Attempt wins; a terminal/pending Job re-execute OR a concurrent caller is `PRECALL_BLOCKED` with zero transport calls, so two Workers cannot both issue a paid call) and a late result after a timeout is handled by a no-adapter `ingest_late_outcome` path that validates the PERSISTED `Attempt` (attempt_id + correlation + provider request id — correlation alone is not proof) -> guarded completion (wrong attempt/correlation/request-id -> `LATE_OUTCOME_REJECTED`; ANY late outcome on a terminal Job -> `COMPLETION_NOOP` with no Event/cost/result/status change) and Path B consumption is CONCURRENCY-SAFE + IDEMPOTENT (an atomic `claim_late_outcome` flips the Attempt `AWAITING_LATE_OUTCOME -> PROCESSING_LATE_OUTCOME` in one critical section, so at-least-once duplicate/concurrent late deliveries dispatch AT MOST ONCE — one Event + one cost record, settled once — then the Attempt is `CONSUMED`; a recorded `provider_request_id` must be matched exactly, a MISSING incoming id is rejected; and the winner's dispatch is one UoW that snapshots pre-dispatch facts and rolls ANY partial write back on a dispatch failure before reopening the Attempt), never a second `execute_job`; a Provider timeout is a NON-terminal `PENDING_RECONCILIATION` lifecycle (not a terminal `FAILED`, reservation retained, no auto-retry); every known-usage non-success (validation failure/refusal/incomplete) settles the exact usage via a Day52-compatible `record_cost` (unknown -> `reconciliation_pending`, refusal usage never dropped); and a config-wide capability 400 fails the `ProviderConfig` closed while a single-request 400 does not. REAL Pydantic v2 + control-flow tests executed (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3 -> 48 passed) — proving the validation gate + application control flow ONLY. The real `openai` SDK/network/Provider, real PostgreSQL/Redis/Celery Worker, FastAPI wire, integration, and production are NOT RUN; Day54 streaming/disconnect/cancellation, Day55 Celery, and Day56 retry/backoff/degradation are not implemented. Schema honesty: the persisted execution-contract facts, Result Artifact shape, and per-Job cost-reconciliation state are MODELED in-memory; a real deployment adds any new columns via a Day48-safe FORWARD additive migration, never a rewrite of published history. No real `api_key`, `base_url` secret, raw prompt, Document content, or Provider response is persisted or logged.
- Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation.
  Scope: streaming responses, disconnect/timeout handling, cooperative cancellation.
  Connection: adds streaming, disconnects, timeouts, and cancellation to the provider calls; Day55 moves long-running Provider work to background workers.
  Implementation boundary: see "Future Lesson Implementation Boundaries" (Day54) below.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day54-ai-streaming-client-disconnects-timeouts-and-cancellation.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day54-ai-streaming-client-disconnects-timeouts-and-cancellation-design.md` with a runnable provider-neutral in-memory model `day54_streaming_disconnects_timeouts_cancellation.py` + `test_day54_streaming_disconnects_timeouts_cancellation.py` (standard-library control flow; the late-result path reuses Day53's pydantic-backed strict validation gate): separates TWO streaming kinds (transient Provider token streaming vs durable Job progress/event streaming — never one as the other's durable truth) and THREE independent lifecycles (HTTP client connection / Provider request / durable Job), with the explicit boundary HTTP disconnect != the Provider call necessarily stops != the persisted Job auto-cancels != the accepted business commitment disappears. An SSE `disconnect` (`SubscriptionRegistry`) ends ONLY that subscription and never touches the durable `JobStore` (the Job stays `running`); a reconnecting browser reads durable state + safe milestone events via `reconnect_view`, not a Provider token replay, and raw Provider tokens are never default-persisted as JobEvents (Day53 raw minimization). A Provider timeout is a NON-terminal `PENDING_RECONCILIATION` (`record_timeout_pending`) with the Day52 reservation retained, unknown usage never fabricated as 0, no blind re-call, and the original 202 is not retroactively a 504 (the Provider may have raw output but does NOT create the application Result Artifact — only Day53 validation + guarded completion does). Cancellation/deadline is a DURABLE, auditable, cooperative, guarded protocol: the Router (`request_cancellation`) persists a durable intent FIRST (reason/actor/timestamp/version) and never writes `cancelled` merely because HTTP arrived; a cooperative Worker (`run_worker`) observes the intent at safe points — before the Provider call it does NOT call the Provider (zero Provider calls) and takes a `guarded_terminal_transition`; mid-stream it best-effort aborts the Provider stream, stops publishing tokens, records safe correlation, holds `reconciliation_pending` (never fabricating remote stop or zero cost) and takes a guarded transition; the terminal fact is DERIVED from the intent kind (`terminal_for_intent`: user cancellation -> `CANCELLED`, deadline -> `EXPIRED`) consistently across the pre-call, mid-stream, final-pre-completion, and crash-re-observation paths; the `provider_request_id` is persisted to protected Job evidence as soon as the Provider request is opened (so a later mid-stream cancel or timeout reconciles as `RECONCILE_UNKNOWN_EXTERNAL`, not `NO_PROVIDER_EXECUTION_EVIDENCE`); and a durable intent written AFTER the last token but BEFORE completion is caught by a FINAL cooperative check that does NOT write `succeeded` but takes the guarded cancel/expiry path. Completion and cancellation/expiry each use a guarded terminal write (`UPDATE ... WHERE status IN (live) RETURNING`), so exactly ONE wins and the loser sees zero rows and stops/reconciles; a late Provider result reuses Day53's identity-binding + strict validation boundary (`ingest_late_provider_result` — the equivalent minimal abstraction of Day53's `ingest_late_outcome`): it completes the Job only when non-terminal AND awaiting reconciliation AND `job_id` + `attempt_id` + `correlation_id` + `provider_request_id` match the persisted evidence (a missing id == mismatch) AND the payload passes the Day53 strict gate for the bound `(schema_name, schema_version)` contract; any mismatch/missing-id/not-awaiting/terminal/invalid payload is a side-effect-free refusal (a terminal Job -> `REFUSED_TERMINAL`), duplicate/concurrent matched deliveries complete AT MOST ONCE, and no Provider call is made. A Scheduler/Worker crash after intent persistence is recoverable: `scan_open_intents` + `apply_cancellation` re-observe at-least-once and the guarded transition absorbs repeats. Integrated exercise: an erroneous deployment that turned every SSE disconnect into a cancellation intent is contained by rolling the policy back FIRST (`DisconnectPolicy.rollback` — future harm only, NOT a business-fact rollback), building the affected set from release version + a bounded time window + stable intent IDs (`build_affected_set`), retaining audit history, and classifying recovery from evidence (`classify_recovery`: a client idempotency key proves acceptance only, not Provider execution; request id + unknown usage -> retain reservation + reconcile, never a blind state flip or Provider re-call). In-memory control-flow tests executed (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3 -> 27 passed) — application control flow ONLY. Real FastAPI/SSE wire behavior, the real OpenAI SDK/network/Provider token stream, real PostgreSQL transactions/isolation, Redis, and Celery are NOT RUN; Day55 Celery Worker execution and Day56 retry/backoff/backpressure are not implemented. Schema honesty: the `cancelled`/`expired`/`pending_reconciliation` statuses, a durable cancellation/expiry intent table (reason/actor/timestamp/version), and the per-Job `attempt_id` + bound `(schema_name, schema_version)` execution-contract fields (for late-result identity binding) are new facts MODELED in-memory; the real schema needs a Day48-safe FORWARD additive migration (new intent table + any new status allowlist value via a gated revision), not implemented here, never a rewrite of published history. Day52 reservation/reconciliation and the Day53 guarded completion / Provider boundary are reused. No real credentials, raw prompts, Document content, or raw Provider payloads/tokens are persisted or logged.
- Day55 — Celery, Worker Execution and Long-running AI Jobs.
  Scope: reuses the Day40 delivery-semantics mental model (at-least-once delivery, redelivery, ACK timing, idempotency, poison-message handling) while running long-running Provider work on a SUPPORTED Celery broker transport. Do not equate Celery's broker implementation with the Day40 custom Redis Streams / Consumer Group design, and do not hand-build a Celery replacement.
  Connection: moves long-running Provider jobs to Celery workers, reusing the Day40 delivery-semantics mental model on a supported Celery broker (not the custom Streams design); Day56 hardens provider resilience and cost.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day55-celery-worker-execution-and-long-running-ai-jobs.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day55-celery-worker-execution-and-long-running-ai-jobs-design.md` with a runnable provider-neutral in-memory model `day55_celery_worker_execution.py` + `test_day55_celery_worker_execution.py` (standard-library delivery/execution/recovery control flow; the guarded completion reuses Day53's pydantic-backed strict validation gate and the Day54 durable-cancellation terminal mapping). It moves accepted long-running AI Jobs from the Day50 Outbox Relay onto a SUPPORTED Celery broker transport (`CeleryBrokerSim` models publish/deliver/redeliver-via-visibility-timeout/ack/dead-letter only — NOT the Day40 custom Redis Streams / Consumer Group design, and NOT a hand-built Celery replacement) and Celery Workers, keeping PostgreSQL the single source of business truth. The Outbox Relay publishes the Celery task BEFORE writing the `published` checkpoint (a crash-between duplicates the publish, absorbed by the guarded claim; checkpoint-first would strand a queued Job with no message; an ambiguous publish outcome != success). The FIRST duplicate-call gate is an atomic PostgreSQL-owned GUARDED CLAIM (`claim_execution` models `UPDATE jobs SET status='running',open_attempt_id=:a WHERE job_id=:j AND status IN ('queued','running') AND (lease_owner IS NULL OR lease_expiry<now) RETURNING *`): one row = Provider execution authority, zero rows = STOP before the Provider call — a lease is temporary ownership and a fencing token rejects stale durable writes but cannot undo an already-issued Provider request, so neither is the first gate. ClaimStatus routes GRANTED / CONFLICT (another live Worker -> redeliver, don't ACK) / ALREADY_TERMINAL (duplicate of a finished Job -> safe no-op ACK, zero calls) / RECONCILE_ONLY (a `PENDING_RECONCILIATION` redelivery -> reconcile from the existing Attempt evidence, zero re-calls). Eight identity layers are kept distinct (client idempotency key / job_id / Celery delivery / worker_id / attempt_id / provider_request_id / provider idempotency key / correlation_id); redelivery or a new Worker retains the open `Attempt` + `provider_idempotency_key` (only an explicit, durable, authorized A2 gets a new key), and `provider_request_id` is recorded as external execution evidence at Provider-request open. ACK timing is modeled (`AckMode.EARLY` silently LOSES a delivery on crash; `AckMode.LATE` (default) REDELIVERS and the app absorbs duplicates via the guarded claim); Celery `ACK`/`SUCCESS` means delivery reliably handled, NOT that the business Job is `succeeded` (`GET /jobs/{id}` reads the durable `JobStore`, never the Celery result backend). A Provider timeout or Worker OOM (Out Of Memory: the OS/container may kill a Worker with no cleanup, so try/except alone is insufficient) -> non-terminal `PENDING_RECONCILIATION` with the reservation retained (`RECONCILIATION_PENDING`, unknown usage never fabricated as 0) and NO blind re-call; the long Provider call stays OUTSIDE any DB transaction. Poison is classified durably and never ordinary-requeued: an unsupported `envelope_version` (`job.dispatch.v2`) is transport/message compatibility detected BEFORE Job loading -> dead-letter + ACK, zero Provider calls, the Job untouched; an unsupported persisted execution-contract is detected AFTER Job loading -> durable `QUARANTINED` + ACK, zero Provider calls (the envelope and execution-contract version spaces are disjoint); a transient transport failure retains the Attempt/evidence and redelivers for a bounded retry whose backoff/jitter DEPTH is Day56. The Day54 durable, auditable, cooperative, guarded cancellation protocol is preserved inside Celery: `request_cancellation` commits a durable intent FIRST (reason/actor/timestamp/version), an optional Celery `revoke` is best-effort delivery control AFTER the commit (never the authority; it may fail or race), and the cooperative Worker checks the intent at safe points (pre-call -> zero Provider calls + guarded terminal; final pre-completion -> a durable intent after the last token still prevents `succeeded`); the terminal is kind-derived (`terminal_for_intent`: user cancellation -> `CANCELLED`, deadline -> `EXPIRED`), completion and cancellation each take a guarded terminal write so exactly ONE wins (loser -> zero rows -> stop/reconcile), and a crash after intent persistence is re-observed at-least-once with repeats absorbed. Graceful drain (`graceful_drain`) starts verified new Workers, stops old Workers from taking NEW claims, drains in-flight within a bound, checkpoints, ACKs and exits (abandoned in-flight work redelivers, not lost); force-killing Workers is never business cancellation. The integrated incident — an erroneous early-ACK release that can silently lose deliveries — is contained by rolling the configuration back FIRST (`ReleaseConfig.rollback`, future harm only, NOT a business-fact rollback — it does not repair Jobs already committed `running`), building the affected set from release version + a bounded time window + Worker/Attempt/Event evidence (`build_affected_set`, no bulk flip of `running`->`queued`), and classifying repair from evidence (`classify_repair`: a Job whose Attempt has a `provider_request_id` may have executed -> `RECONCILE_ONLY`, never a blind re-dispatch; only Jobs with NO Provider-execution evidence are safe under an explicit, guarded, audited `RECONCILE_THEN_GUARDED_REDISPATCH`; a client idempotency key proves acceptance only, not Provider execution). In-memory control-flow tests executed (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3 -> 27 passed; full api suite 375) — APPLICATION CONTROL FLOW ONLY. A real Celery broker (Redis/RabbitMQ) transport + Worker process, real ACK/redelivery/visibility timeouts, Worker-loss/OOM/redelivery fault injection, real PostgreSQL transactions/isolation, Redis, and the real OpenAI SDK/network/Provider are NOT RUN; Day56 retry/backoff/rate-limit/token-cost/backpressure and Day57 integration/failure-injection/recovery verification are not implemented. Boundaries preserved verbatim: `Celery ACK/SUCCESS != Job succeeded`, `broker redelivery != permission to call the Provider again`, `Worker identity != durable Attempt identity`, `Provider timeout/Worker loss != proof of no Provider execution or zero cost`, `Celery revoke != durable cancellation authority`, `configuration rollback != business-fact rollback`. Schema honesty: the `cancelled`/`expired`/`pending_reconciliation`/`quarantined` statuses, a durable cancellation/expiry intent table (reason/actor/timestamp/version), the per-Job `open_attempt_id`, and the per-Attempt `provider_idempotency_key` / `provider_request_id` / bound `(schema_name, schema_version)` fields are new facts MODELED in-memory; the real schema needs a Day48-safe FORWARD additive migration (new intent + attempt columns/tables and any new status allowlist value via a gated revision), not implemented here, never a rewrite of published history. Day50 Job/Outbox/Relay, Day53 guarded completion / Provider boundary / strict validation, and the Day54 cancellation protocol are reused. No real credentials, raw prompts, Document content, or raw Provider payloads/tokens are persisted or logged.
- Day56 — Provider Resilience, Rate Limits, Token Cost and Backpressure.
  Scope: retries/backoff, provider rate limits, token-cost control, backpressure and degradation.
  Connection: adds retries/backoff, provider rate limits, token-cost control, and backpressure to the worker path; Day57 verifies all of it with tests and failure injection.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day56-provider-resilience-rate-limits-token-cost-and-backpressure.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day56-provider-resilience-rate-limits-token-cost-and-backpressure-design.md` with a runnable provider-neutral in-memory model `day56_provider_resilience.py` + `test_day56_provider_resilience.py` (standard-library control flow; imports Day54's `IntentKind`). It adds the ADMISSION-TO-PROVIDER control plane on top of Day55 execution: even a Job holding the guarded claim still needs current Provider capacity, an intact cost reservation, and a healthy Provider path before an actual paid call. FOUR authorities are kept distinct — the PostgreSQL GUARDED CLAIM (execution authority for ONE durable Job, Day55), a shared/distributed RATE PERMIT (fleet-wide Provider capacity to call now; a claim is not a permit), a durable RESERVATION (tenant affordability; a limiter is not the budget ledger), and a CIRCUIT (Provider failure-domain containment keyed `circuit:{provider}:{account}:{model}:{region}`, no secrets) — and FIVE dispatch outcomes are executable via `evaluate_dispatch`: CALL (all four agree), DEFER (no permit / circuit OPEN / limiter outage / no reservation and NO call made -> persist `retry_reason`/`next_attempt_at`/`defer_count`/`deadline`, release the Worker, NO sleep), RECONCILE (external execution unknown or Attempt evidence -> never blind retry), TERMINAL (durable cancellation/deadline intent -> guarded CANCELLED/EXPIRED), NOOP (already terminal); durable terminal/cancellation facts and execution evidence OUTRANK capacity retry. Retry is bounded exponential backoff with FULL jitter and `Retry-After` treated as an EARLIEST floor (a synchronized retry storm / thundering herd is NOT a cache avalanche). A shared-limiter OUTAGE fails CLOSED for new paid calls by default (reads/cancellation/completed-result reads/reconciliation still work); a tightly bounded emergency fail-open is an EXPLICIT policy, never a default bypass. A no-permit-before-call is a durable DEFER (not FAILED, not PENDING_RECONCILIATION) that consumes NO execution-retry budget, uses a separate bounded `defer_count`, and never schedules past the business deadline. Cost control is distinct from capacity: `reserve_worst_case` reserves the BOUNDED WORST-CASE cost from the persisted contract (`max_tokens/1000 * price_per_1k_tokens`), NOT the remaining balance; if the tenant cannot cover it, do not call; success settles actual use and RELEASES the unused remainder back to the durable tenant ledger, not the rate limiter; unknown execution HOLDS the reservation for reconciliation. Backpressure lives BEFORE the durable Job + Outbox commit (`admit_job`: tenant over its own quota -> 429, system-wide capacity/dependency unavailable -> 503 which dominates; never 202 for a commitment that cannot be kept; an accepted Job is NEVER retroactively converted to 429/503). A Worker NEVER silently reduces persisted `model`/`max_tokens`; degradation is allowed only when the persisted, product-authorized contract permits it, down to `min_model`/`min_max_tokens`. A Provider 429 alone is not universal proof nothing executed: `classify_execution_certainty` returns DEFINITELY_NOT_ACCEPTED (safe ordinary-defer/retry) vs MAY_HAVE_EXECUTED / UNKNOWN (RECONCILE), and any Attempt evidence (a `provider_request_id` or the Day55 conservative dispatch marker) forces RECONCILE before capacity gating. The circuit breaker CLOSED allows, OPEN durably defers new calls, and HALF_OPEN permits only a small bounded PROGRESSIVE probe set — one successful probe does not close the circuit or release the herd. Deadline expiry performs a guarded EXPIRED + reservation RELEASE only with proof of no external execution; any evidence -> PENDING_RECONCILIATION with the reservation HELD. The zero-defer incident (a bad release set max defer duration to zero, prematurely expiring capacity-deferred Jobs) is contained by rolling the configuration back FIRST (future harm only, NOT a business-fact rollback), building a bounded affected set from release + a time window + the expiry reason + Attempt/Event evidence + deadline (`build_capacity_expiry_affected_set`, preserving expired history, never a bulk flip), and re-dispatching ONLY Jobs with proof of no Provider execution and a still-valid contract/deadline via a guarded, audited `repair_redispatch` that writes a NEW durable `OutboxDispatchIntent` for the Relay to publish after commit (never a direct queue call); Jobs with Provider evidence are RECONCILE_ONLY. In-memory control-flow tests executed (Python 3.10.12, pytest 7.4.3 -> 31 passed; full api suite 419) — APPLICATION CONTROL FLOW ONLY. A real Celery broker/Worker, a real Redis distributed limiter/circuit store, real PostgreSQL transactions/isolation, real Provider traffic/rate limits/costs, load tests, and Worker-kill/fault-injection integration are NOT RUN; Day57 owns integration + failure injection and Day58 owns observability/runtime evidence — neither is implemented here. Schema honesty: a `deferred` status, a durable defer record (`retry_reason`/`next_attempt_at`/`defer_count`/`deadline`), the per-Job `execution_retry_count` vs `defer_count`, and a tenant cost-reservation ledger (reserved/settled/held) are new facts MODELED in-memory; the real schema needs a Day48-safe FORWARD additive migration (new status allowlist value + defer/reservation columns via a gated revision), never a rewrite of published history; the rate limiter and circuit state are TRANSIENT coordination (Redis-like), not durable tenant truth. Day55 guarded claim/Outbox/P1 dispatch marker and Day54 durable intents are reused. No real credentials, raw prompts, Document content, raw Provider payloads, or secrets are persisted or logged.
- Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection.
  Scope: fake/deterministic providers, contract tests, failure injection, runtime evidence.
  Connection: advances the Day43-baseline test suite into fake-provider, contract, integration, and failure-injection tests with recovery verification; Day58 integrates and verifies observability to close the phase.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day57-ai-backend-testing-fake-providers-contract-tests-and-failure-injection.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day57-ai-backend-testing-fake-providers-contract-tests-and-failure-injection-design.md` with a runnable deterministic verification harness `day57_testing_harness.py` + `test_day57_testing_harness.py` (standard-library control flow driving the REAL Day56 policy functions + Day53's real pydantic validator). It turns the Day43–Day56 reliability policies into REPEATABLE EVIDENCE and injects failures, keeping FOUR evidence tiers explicit (conceptual/static design; executed local runtime; integration runtime; production) and marking real infrastructure NOT RUN — real PostgreSQL, a real Celery broker/Worker-kill/redelivery, and a real Redis limiter/circuit are the INTEGRATION RUNTIME tier (NOT RUN, and NOT production), while real Provider traffic/production validation are the PRODUCTION tier (NOT RUN). The harness provides a controllable Fake Provider (`ControllableFakeProvider`: scripted `ScriptedResponse` outcomes, a cross-call `calls` count, an independent `ProviderCallLog` that survives "Worker loss", and `request_received`/`release_response` gates via `threading.Event` so timeout/kill windows are CONTROLLED not timed), a `FakeClock` + `DeterministicRandom` for reproducible backoff/jitter, an application-owned `ProviderAdapter`/`ProviderOutcome` (failure kind, execution certainty, optional request id, safe retry info, safe metadata — never SDK exception classes/HTTP codes/private fields, and never writing Job state or cost), a strict `attempt_late_completion` late-result contract, and an explicit `VALIDATION_MATRIX`/`not_run_claims()` evidence taxonomy. Executed scenarios (EXECUTED LOCAL RUNTIME): a bare Provider 429 -> durable `PENDING_RECONCILIATION` with the Provider call count still ONE, no ordinary retry granted a new rate permit, reservation HELD, redelivery reconcile-only (a durable status alone is insufficient); a missing `provider_request_id` is NOT proof of no execution — a Worker can crash after the request leaves the process, so Day55's conservative `provider_dispatch_started_at` marker forces RECONCILE (an idempotency key mitigates risk but is not proof/permission); the Adapter delivers an application-owned typed outcome + execution-certainty classification (DEFINITELY_NOT_ACCEPTED may ordinary-defer/retry, MAY_HAVE_EXECUTED/UNKNOWN reconcile); a syntactically valid Provider JSON that violates the persisted `(schema_name, schema_version)` is a CONTRACT_VIOLATION (Day53 real validator), not business success (no Result Artifact, not succeeded, no blind second call; current Provider config governs new calls only); deterministic backoff/jitter with Retry-After as an EARLIEST floor (every wake at/after it, controlled draws spread, never a wake-all); a controlled timeout window with no sleeps and a timeout-after-receipt that is not proof of no execution (`PENDING_RECONCILIATION` + reservation HELD); late-result completion ONLY if the Job is non-terminal AND awaiting reconciliation AND the payload strictly validates AND `job_id` + `attempt_id` + `correlation_id` + `provider_request_id` all match durable evidence (a terminal CANCELLED Job rejects even a fully matching late result without overwriting state); limiter outage fails CLOSED (DEFER, zero Provider calls, bounded `next_attempt_at` + separate `defer_count`, `execution_retry_count` unchanged); deadline behavior with no evidence (guarded EXPIRED + reservation release) vs with marker/request evidence (`PENDING_RECONCILIATION` + reservation held); admission backpressure where system-wide 503 dominates a tenant 429; and a guarded, IDEMPOTENT repair under concurrency (a unique `repair:{job_id}:{release_version}:defer_deadline_expired` claimed atomically -> exactly one new Outbox intent even under duplicate/concurrent repair, `ALREADY_APPLIED` thereafter; a Job with Provider evidence is RECONCILE_ONLY). Executed: `python3 -m pytest -q test_day57_testing_harness.py` -> 23 passed (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3); full `projects/ai-backend-data-layer/api/` suite -> 465 passed. NOT RUN (explicitly not claimed): real PostgreSQL transaction/rollback/isolation and guarded concurrent terminal transitions (an ORM mock cannot prove committed facts); a real Celery broker + Worker process + redelivery + Worker-kill recovery; a real Redis limiter/circuit outage + restored-capacity no-herd; and any real Provider traffic/rate limits/cost. `pytest passed` alone is NOT audit-grade runtime evidence — a real integration run must also preserve the exact command/revision, the fault point, committed-DB-state queries via a NEW connection, the Fake Provider cross-process call log, and broker/Worker lifecycle evidence. A real `job_repair_history` table + migration is a FORWARD-ADDITIVE design only, not migrated or tested. Day56 policy functions, Day55 dispatch marker, Day54 durable cancellation, and Day53 strict validation are reused. Day58 owns structured observability (structured logs, `job_id`/`trace_id`/`attempt_id` correlation, metrics, traces, runtime evidence) and the Phase 4 capstone — not implemented here. No secrets, raw prompts, or raw Provider payloads are persisted or logged; repair/audit records carry only safe decision evidence.
- Day58 — Production AI API Capstone, Observability and English Interview.
  Scope: integrate the phase into a runnable API with observability; phase-level English interview.
  Connection: integrates and verifies observability (structured logs, job_id/trace_id/attempt_id correlation, metrics, traces, runtime evidence) into the runnable API and runs the phase English interview; Phase 5 (Day59) makes this backend a callable browser-automation capability.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day58-production-ai-api-capstone-observability-and-english-interview.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day58-production-ai-api-capstone-observability-and-english-interview-design.md` with a runnable deterministic in-process observability model `day58_observability_capstone.py` + `test_day58_observability_capstone.py` (standard-library control flow; imports Day57's `EvidenceTier`/`MatrixRow`/`RunStatus` and Day56's `ExecutionCertainty`). Phase 4 capstone: it makes the distributed AI Job execution EXPLAINABLE and AUDITABLE across API -> Outbox Relay -> Worker Attempt -> Provider Adapter -> completion/reconciliation, keeping the core principle that observability is a correlated, safe, aggregatable, reviewable EVIDENCE system AROUND durable state — it does NOT replace the durable state machine and does NOT grant permission to retry unknown external work; missing telemetry is an observability GAP, never proof of no execution. The model covers: the identity contract with SEPARATE contexts (a durable Worker Attempt `IdentityLifecycle` — `job_id` = durable business identity and `correlation_id` = business-chain association both STABLE across retries, with a NEW `attempt_id` and normally a NEW `trace_id` per Attempt and NO `request_id`; and a distinct `HttpRequestContext` for one inbound HTTP request — `job_id`/`correlation_id` plus a NEW `request_id` AND a NEW `trace_id`, NO `attempt_id`, so a status/poll never masquerades as a Worker Attempt or silently reuses its trace, with an EXPLICIT `parent_trace` for legit traceparent continuity; `trace_id` is one distributed trace, NOT business truth); a safe `StructuredEvent` contract that carries only safe fields (event_name/job_id/correlation_id/attempt_id/trace_id/provider/model/outcome/bounded duration_ms/request_id_present/dispatch_marker_present/reason) and REJECTS raw prompts, raw Provider responses, api keys, secrets, tenant documents, and unknown fields (`UnsafeTelemetryError`), emitting `provider.call.timeout` (the application's OBSERVED timeout/unknown outcome, NOT proof of non-execution) vs `provider.call.suppressed` (a later reconciliation Attempt that refused a second Provider call, `reason=prior_attempt_may_have_executed`, `dispatch_marker_present=True`); a `MetricRegistry` enforcing a LOW-CARDINALITY label contract — Counter `provider_call_total{provider,model,outcome}` (query its RATE, not the raw cumulative total), Histogram `provider_call_duration_seconds{provider,model}` (distribution/tail latency), Gauges `provider_calls_in_flight{provider,model}` (rises at call start, falls at completion/timeout) and `jobs_pending_reconciliation{provider,model}` (backlog) — that raises `HighCardinalityLabelError` if `job_id`/`attempt_id`/`trace_id` are used as labels (they belong in logs/traces), rejects uncontrolled label VALUES (`validate_label_values`) and requires `model` to come from a FINITE controlled registry (`ALLOWED_MODEL_VALUES`) or be normalized to a bounded bucket (`normalize_model_label`) since a regex alone allows unbounded distinct models, and validates every canonical StructuredEvent VALUE (bounded id/event_name shapes, provider/model/outcome allowlists, a finite `reason` enum, secret/overlong rejection) rather than trusting the caller, with alerting that COMBINES timeout rate + in-flight saturation + a sustained reconciliation backlog; trace/span-link modeling where API acceptance, the Relay, Worker Attempt A, and later Attempt B are SEPARATE traces across durable asynchronous boundaries, a Provider Adapter call is a CHILD span of the current Attempt trace (`child_span` shares the trace_id), and a later async Attempt uses a SPAN LINK (`linked_trace`) to the IMMEDIATE preceding causal trace (not a child of an already-ended HTTP span, not fake synchronous nesting; link only the immediate prior since `job_id`+`correlation_id` carry stable end-to-end continuity); the durable-correctness-vs-observability boundary (`provider_dispatch_started_at` persisted BEFORE the external call; a missing `provider_request_id` or missing telemetry is NOT proof no call happened; PostgreSQL Job/Attempt/marker/reservation facts determine retry/reconciliation safety while logs/traces/metrics explain but never AUTHORIZE a repeat Provider call); a telemetry-exporter-failure policy (`TelemetryPipeline` — an exporter outage must NOT turn an accepted Job into FAILED or permit unsafe retry: keep core processing, bounded buffering then drop, and expose `telemetry_export_failures_total`/`telemetry_events_dropped_total`/`telemetry_export_queue_depth`; a stricter regulatory/product availability trade-off must be an EXPLICIT policy, never an accidental exporter-failure side effect); and the bad-observability-release rollback drill (a release removed `attempt_id` from Worker logs and added `job_id` to `provider_call_total` labels — FIRST roll back the observability release/config to stop further correlation loss + high-cardinality damage, NEVER roll back or overwrite valid Job/Attempt/dispatch-marker/reservation/Outbox facts because this is an observability failure not a business-state failure; bound the affected set by release version + time window; reconstruct affected Jobs from durable PostgreSQL facts; MARK telemetry gaps honestly and never fabricate missing logs/traces; a `PENDING_RECONCILIATION` Job whose telemetry is incomplete but whose database has a dispatch marker remains reconciliation-only and must NOT be requeued for an ordinary Provider call). Executed: `python3 -m pytest -q test_day58_observability_capstone.py` -> 37 passed (Python 3.10.12, pytest 7.4.3); full `projects/ai-backend-data-layer/api/` suite -> 502 passed. This proves EXECUTED_LOCAL_RUNTIME identity/event/metric/trace/telemetry-policy/rollback control flow ONLY. NOT RUN (explicitly not claimed): a real FastAPI runtime + a real OpenTelemetry exporter pipeline; real PostgreSQL/Redis/Celery integration with committed correlation evidence (including redelivery/Worker-kill); and real Provider traffic / production observability validation — these are INTEGRATION_RUNTIME and PRODUCTION tiers recorded NOT RUN. A reviewable runtime-evidence pack requires the exact command/revision/config/time window, the fault point, structured logs/traces/metrics, committed database queries from a NEW connection, independent Provider call evidence, Worker/Relay/broker lifecycle evidence, the actual result, and the explicit validation tier plus NOT RUN limits; `pytest passed` alone is not a reviewable pack. Day57's `EvidenceTier`/`RunStatus` taxonomy, Day56 `ExecutionCertainty`, and the Day55 `provider_dispatch_started_at` marker are reused. No secrets, raw prompts, raw Provider responses, or tenant documents are persisted or logged.

Phase deliverable:

```text
A runnable FastAPI AI Job backend
+ PostgreSQL / SQLAlchemy / Alembic
+ Redis / Outbox / Worker
+ Object Storage boundary
+ OpenAI-compatible provider adapter
+ auth / tenant isolation
+ tests and runtime evidence
```

Validation requirement:
Each Phase 4 lesson must distinguish conceptual/static review from executed runtime evidence, and must not
claim production validation without saved, reproducible evidence. Runtime, integration, and production
validation are only claimed when actually run and recorded.

---

## Phase 5 — Playwright Browser Automation and Agent Tools (Day59–Day68)

Status:
Planned

Objective:
Build Playwright into an isolated, recoverable, auditable Browser Worker and Agent Tool — not a fragile
click script. It becomes a durable, queue-backed capability the AI backend can call as a tool.

Knowledge connection:

```text
FastAPI Production AI API
    -> Playwright Browser Automation / Agent Tool (isolated, recoverable, auditable)
```

Reused project directories: `projects/playwright-login/`, `projects/playwright-scraper/`, and
`projects/fastapi-playwright/` (the Browser Automation Worker integrated with the Phase 4 API).

Per-day topics (Topic + concise scope; each Status: Planned):

- Day59 — Playwright Runtime Model: Browser, Context, Page and Async Lifecycle.
  Scope: the runtime object model and async lifecycle.
  Connection: builds on the Day58 Production AI API capstone by adding a Playwright runtime model as a callable capability; Day60 makes its interactions reliable.
- Day60 — Locator, Auto-waiting and Reliable Interaction.
  Scope: locators, auto-waiting, deterministic interaction over brittle selectors.
  Connection: adds reliable locator/auto-waiting interaction to the Day59 runtime; Day61 isolates authenticated browser contexts per tenant/session.
- Day61 — Authentication, Storage State and Browser Context Isolation.
  Scope: storage state, per-tenant/session context isolation.
  Connection: adds storage-state and per-tenant context isolation to reliable interaction; Day62 extracts structured output from dynamic pages.
- Day62 — Dynamic-page Extraction and Structured Output.
  Scope: extracting structured output from dynamic pages.
  Connection: turns isolated browsing into structured extraction; Day63 captures network events, downloads/uploads, and artifact evidence.
- Day63 — Network Events, Downloads, Uploads and Artifact Evidence.
  Scope: network interception, downloads/uploads, artifact evidence into Object Storage.
  Connection: adds network/download/upload artifact evidence into the Day49 Object-Storage boundary; Day64 makes it robust with timeouts, retries, and diagnostics.
- Day64 — Timeouts, Retries, Diagnostics, Screenshots and Error Recovery.
  Scope: timeout/retry policy, diagnostics, screenshots/traces, recovery.
  Connection: adds timeout/retry/diagnostic/screenshot recovery to extraction and evidence; Day65 secures the browser against SSRF, credential, and prompt-injection risks.
- Day65 — Browser Security, SSRF, Credentials, Website Policy and Prompt-injection Boundaries.
  Scope: SSRF/credential handling, website policy/authorization, prompt-injection boundaries (no bypass of security controls, captchas, or anti-automation).
  Connection: adds browser security, website-policy authorization, and prompt-injection boundaries; Day66 runs it as a durable, queue-backed worker.
- Day66 — Queue-backed Browser Worker and Durable Job Integration.
  Scope: a durable, queue-backed browser worker integrated with the Day40/Day55 job lifecycle.
  Connection: turns the secured browser into a durable, queue-backed worker on the Day40/Day55 job lifecycle; Day67 exposes it as a permissioned agent tool.
- Day67 — Playwright as an AI Agent Tool.
  Scope: expose browser automation as a constrained, permissioned agent tool.
  Connection: exposes the browser worker as a constrained, permissioned agent tool; Day68 integrates it with the FastAPI backend and closes the phase.
- Day68 — FastAPI + Playwright Production Capstone and English Interview.
  Scope: integrate API + browser worker; phase-level English interview.
  Connection: integrates the API and browser worker into a capstone and runs the phase English interview; Phase 6 (Day69) orchestrates these backends with n8n.

Phase deliverable:

```text
An isolated, recoverable, auditable Playwright Browser Worker + Agent Tool integrated with the FastAPI backend.
```

Validation requirement:
Do not teach bypassing website security controls, captchas, or anti-automation protection. Emphasize
authorization, website policy, security, and isolation. Runtime/production evidence is claimed only when
actually executed and saved.

---

## Phase 6 — n8n AI Workflow Orchestration (Day69–Day74)

Status:
Planned

Objective:
Use n8n to orchestrate the existing API and AI capabilities — as an integration/workflow layer, not a
low-code replacement for backend correctness.

Knowledge connection:

```text
Playwright Browser Automation / Agent Tool
    -> n8n Workflow Integration (orchestration over correct backends)
```

Reused project directory: `projects/n8n-workflows/` (workflow-integration evidence).

Per-day topics (Topic + concise scope; each Status: Planned):

- Day69 — n8n Workflow Model, Triggers, Nodes and Responsibility Boundaries.
  Scope: workflow model and where responsibility stays in the backend, not the low-code layer.
  Connection: builds on the Day68 FastAPI+Playwright capstone by adding n8n as an orchestration layer with clear responsibility boundaries; Day70 wires triggers and authenticated integration.
- Day70 — Webhooks, Schedules, FastAPI Integration and Authentication.
  Scope: webhook/schedule triggers, authenticated FastAPI integration.
  Connection: adds webhook/schedule triggers and authenticated FastAPI integration to the workflow model; Day71 handles long-running AI jobs via polling/callback correlation.
- Day71 — Long-running AI Jobs: Polling, Callback, Correlation and Idempotency.
  Scope: polling/callback correlation and idempotency for long AI jobs.
  Connection: adds polling/callback correlation and idempotency for long AI jobs; Day72 inserts human approval and AI-assisted steps.
- Day72 — Human Approval and AI-assisted Business Workflows.
  Scope: human-in-the-loop approval and AI-assisted workflows.
  Connection: adds human-in-the-loop approval and AI-assisted workflows; Day73 hardens retry, error workflows, secrets, and audit.
- Day73 — Retry, Error Workflow, Secrets, Audit and Production Operations.
  Scope: retry/error workflows, secrets handling, audit, operations.
  Connection: adds retry/error workflows, secrets handling, and audit/operations; Day74 integrates the workflow layer into a capstone.
- Day74 — n8n + FastAPI + AI Workflow Capstone and Interview.
  Scope: integrate workflows with the backend; phase-level interview.
  Connection: integrates n8n + FastAPI + AI workflows into a capstone and runs the phase interview; Phase 7 (Day75) builds the AI agent backend these workflows will call.

Phase deliverable:

```text
n8n workflows that orchestrate the FastAPI AI backend and browser tools, with idempotent long-job handling and audit.
```

Validation requirement:
n8n must not replace backend correctness; durable truth stays in PostgreSQL. Claim runtime/production
evidence only when executed and saved.

---

## Phase 7 — AI Agent, RAG, MCP and Evaluation Engineering (Day75–Day90)

Status:
Planned

Objective:
Build a testable, constrained, recoverable Production AI Agent Backend: tool calling, MCP, RAG, vector
retrieval, memory, security boundaries, and automated evaluation with runtime traces.

Knowledge connection:

```text
n8n Workflow Integration
    -> AI Agent + Tool Calling + MCP + RAG + Memory + Evaluation (production-grade, evaluated)
```

Reused project directory: `projects/ai-agent/` (Agent, RAG, Tool Calling, MCP, Memory, Evaluation).

Per-day topics (Topic + concise scope; each Status: Planned):

- Day75 — LLM Application Architecture, Tokens, Context and Model Failure Modes.
  Scope: architecture, token/context limits, model failure modes.
  Connection: builds on the Day74 workflow capstone by establishing LLM application architecture, token/context limits, and model failure modes; Day76 formalizes prompt contracts and function calling.
- Day76 — Prompt Contracts, Structured Output and Function Calling.
  Scope: prompt contracts, structured output, function calling.
  Connection: adds prompt contracts, structured output, and function calling; Day77 builds the tool registry, schemas, and permission boundaries.
- Day77 — Tool Registry, Tool Schemas, Permissions and Execution Boundaries.
  Scope: tool registry/schemas, permissions, execution sandboxing boundaries.
  Connection: adds a permissioned tool registry with execution boundaries; Day78 drives it with an agent loop, state, and termination/retry.
- Day78 — Agent Loop, State, Termination, Retry and Error Handling.
  Scope: agent loop, state, termination/retry, error handling.
  Connection: adds the agent loop, state, termination, and error handling; Day79 introduces MCP as a standard tool/resource boundary.
- Day79 — MCP Foundations: Client, Server, Resources and Tools.
  Scope: MCP client/server, resources, tools.
  Connection: adds MCP client/server, resources, and tools; Day80 secures MCP with auth, authorization, and operations.
- Day80 — MCP Authentication, Authorization, Security and Production Operations.
  Scope: MCP auth/authorization, security, operations.
  Connection: adds MCP authentication, authorization, and production operations; Day81 begins RAG ingestion with provenance.
- Day81 — RAG Ingestion: Parsing, Chunking, Metadata and Provenance.
  Scope: ingestion, chunking, metadata, provenance.
  Connection: adds RAG ingestion, chunking, metadata, and provenance; Day82 builds embeddings and the vector index.
- Day82 — Embeddings, Vector Database and Index Design.
  Scope: embeddings, vector store, index design.
  Connection: adds embeddings, the vector database, and index design; Day83 improves retrieval quality.
- Day83 — Retrieval Quality: Hybrid Search, Filtering and Re-ranking.
  Scope: hybrid search, filtering, re-ranking.
  Connection: adds hybrid search, filtering, and re-ranking; Day84 grounds answers with citations and hallucination boundaries.
- Day84 — Grounding, Citations, Hallucination Boundaries and Source Verification.
  Scope: grounding, citations, hallucination boundaries, source verification.
  Connection: adds grounding, citations, and source verification; Day85 adds conversation and durable memory boundaries.
- Day85 — Conversation Memory and Durable Memory Boundaries.
  Scope: conversation vs durable memory boundaries.
  Connection: adds conversation vs durable memory boundaries; Day86 secures the agent against injection, tool abuse, and exfiltration.
- Day86 — Prompt Injection, Tool Abuse, Data Exfiltration and Sandboxing.
  Scope: prompt injection, tool abuse, exfiltration, sandboxing.
  Connection: adds prompt-injection, tool-abuse, exfiltration, and sandboxing defenses; Day87 makes agent jobs durable and recoverable.
- Day87 — Durable Agent Jobs, Checkpoints, Recovery and Human Escalation.
  Scope: durable agent jobs, checkpoints, recovery, human escalation.
  Connection: adds durable agent jobs, checkpoints, recovery, and human escalation; Day88 measures quality with evaluation datasets and graders.
- Day88 — Evaluation Datasets, Golden Sets, Graders, Trials and Traces.
  Scope: eval datasets/golden sets, graders, trials, traces.
  Connection: adds evaluation datasets, golden sets, graders, trials, and traces; Day89 turns evaluation into observability and release gates.
- Day89 — AI Observability, Cost, Model Routing, Regression and Release Gates.
  Scope: observability, cost, model routing, regression, release gates.
  Connection: adds AI observability, cost/model routing, regression, and release gates; Day90 integrates the agent backend and closes the phase.
- Day90 — Production AI Agent Backend Capstone and English Interview.
  Scope: integrate the agent backend; phase-level English interview.
  Connection: integrates the AI agent backend into a capstone and runs the phase English interview; Phase 8 (Day91) assembles everything into the final capstone and portfolio.

Phase deliverable:

```text
AI Agent Backend
+ Tool Calling + MCP + RAG + Vector Retrieval + Memory
+ Security Boundaries + Automated Evaluation + Runtime traces
```

Validation requirement:
Do not claim Agent, RAG, or MCP are production-validated unless actually executed with saved evidence and
evaluation traces. Distinguish conceptual/static review from runtime evidence.

---

## Phase 8 — Final Capstone, Portfolio and Overseas Interview (Day91–Day100)

Status:
Planned

Objective:
Convert all capabilities into deployable, demonstrable, interview-ready employment evidence.

Knowledge connection:

```text
AI Agent Backend
    -> Final Production Capstone
    -> Portfolio + Overseas Interview
```

Reused project directory: `projects/final-capstone/` (the final integrated project).

Per-day topics (Topic + concise scope; each Status: Planned):

- Day91 — Product Requirements, Architecture Review and Scope Control.
  Scope: requirements, architecture review, scope control.
  Connection: builds on the Day90 agent-backend capstone by defining final-capstone product requirements, architecture review, and scope control; Day92 turns them into a skeleton, contracts, and threat model.
  Implementation boundary: see "Future Lesson Implementation Boundaries" (Day91) below.
- Day92 — Final Capstone Skeleton, Contracts and Threat Model.
  Scope: skeleton, contracts, threat model.
  Connection: adds the capstone skeleton, contracts, and threat model; Day93 integrates the core FastAPI+PostgreSQL+Redis+Object-Storage stack.
- Day93 — FastAPI + PostgreSQL + Redis + Object Storage Integration.
  Scope: integrate the core backend stack.
  Connection: integrates the core backend stack from Phases 3-4; Day94 adds the agent, retrieval, tools, browser worker, and workflows from Phases 5-7.
- Day94 — Agent + RAG + MCP + Playwright + n8n Integration.
  Scope: integrate agent, retrieval, tools, browser worker, workflows.
  Connection: integrates agent + RAG + MCP + Playwright + n8n; Day95 proves it under failure, load, security, and data-repair drills.
  Implementation boundary: see "Future Lesson Implementation Boundaries" (Day94) below.
- Day95 — Failure Recovery, Load, Security and Data-repair Drills.
  Scope: failure recovery, load, security, data-repair drills.
  Connection: adds failure-recovery, load, security, and data-repair drills; Day96 deploys to the cloud with managed services and production config.
  Implementation boundary: see "Future Lesson Implementation Boundaries" (Day95) below.
- Day96 — Cloud Deployment, Managed Services and Production Configuration.
  Scope: cloud deployment, managed services, production config.
  Connection: adds cloud deployment, managed services, and production configuration; Day97 produces the evaluation report, observability, SLOs, and runbook.
- Day97 — Evaluation Report, Observability, SLO and Operational Runbook.
  Scope: evaluation report, observability, SLOs, runbook.
  Connection: adds the evaluation report, observability, SLOs, and operational runbook; Day98 practices system-design and coding interviews on the finished system.
- Day98 — AI Backend System Design and Python/SQL Coding Interview.
  Scope: system-design + Python/SQL coding interview practice.
  Connection: turns the finished system into AI backend system-design and Python/SQL coding interview practice; Day99 builds the English project story, behavioral answers, and resume.
- Day99 — English Project Story, Behavioral Interview, Resume and Open-source Evidence.
  Scope: project story, behavioral interview, resume, open-source evidence.
  Connection: builds the English project story, behavioral interview, resume, and open-source evidence; Day100 runs the final mock interview and portfolio review.
- Day100 — Final Mock Interview, Portfolio Review and Job-application Readiness.
  Scope: final mock interview, portfolio review, application readiness.
  Connection: consolidates everything into a final mock interview, portfolio review, and job-application readiness for overseas AI Backend Engineer roles — the endpoint is the portfolio and the job application itself, not a Day101.

Final Capstone must include:

```text
Problem statement · Architecture diagram · Runnable source code · Tests
Evaluation dataset and report · Failure/recovery evidence · Security threat model
Deployment evidence · Monitoring/observability · README and demo instructions
English project explanation · System-design discussion · Resume bullets
```

Phase deliverable:

```text
A deployable, demonstrable Production AI Backend capstone + a complete GitHub portfolio + English
system-design/behavioral/resume readiness for overseas AI Backend Engineer applications.
```

Validation requirement:
Portfolio and capstone completion require real, saved evidence (runnable code, tests, evaluation report,
failure/recovery drills, deployment and observability evidence). No production-grade claim without executed
evidence.

---

## Employment-Readiness Boundary (Day43–Day100)

This curriculum builds the core capabilities and portfolio evidence of an AI Backend Engineer, but it does
not guarantee a job, and 100 days of training is not equivalent to years of production experience.

Target roles:

```text
Junior / Developing AI Backend Engineer
AI Startup Backend Engineer
Backend Engineer working on LLM / RAG / Agent products
```

Completing the curriculum does not by itself demonstrate Senior or Staff level.

## Cross-cutting Employment Training (Day43–Day100)

Phases 4–8 carry a continuous employment-readiness thread (integrated, not mechanical per-day inflation):
Python coding practice, SQL practice, English technical explanation, system-design communication, runtime
validation evidence, a weekly project README update, and a weekly interview review. A typical week includes
at least 2–3 Python/SQL coding exercises, one English project explanation, one production failure scenario,
and one artifact/runtime-evidence review. The goal is accumulated capability evidence, not a "problem-count
guarantees an offer" model.

---

## Cross-cutting Engineering Discipline (Day43–Day100)

Baseline tests, structured logging, correlation IDs (`job_id` / `trace_id` / `attempt_id`), and validation
evidence begin on **Day43** and evolve with **every** Engineering Artifact. Testing and observability are
continuous engineering disciplines, not end-of-phase add-ons.

Day57 is **not** the first testing lesson. Day57 advances the existing test suite into:

```text
- fake / deterministic provider tests
- contract tests
- integration tests
- failure injection
- recovery verification
```

Day58 is **not** the first observability lesson. Day58 integrates and verifies:

```text
- structured logs
- job_id / trace_id / attempt_id correlation
- metrics
- traces
- runtime evidence
```

Every implementation day must add proportionate tests and validation evidence. No phase may accumulate
untested code and postpone correctness until its Capstone. (This applies to every phase's implementation
days, not only Phase 4.)

---

## Future Lesson Implementation Boundaries (Day50, Day54, Day91, Day94, Day95)

These are confirmed implementation boundaries recorded ahead of time so a future teaching chat, lacking the
current context, does not mis-scope, over-implement, or over-claim validation. They constrain scope and
validation honesty only; they do not lock a specific implementation and do not change any Day Topic. Future
days remain `Planned`; no lesson or code is generated here.

### Day50 — Transactional Outbox scope (vs Day55 Celery)

Day50 should complete:

```text
Job + Outbox committed in ONE PostgreSQL transaction
-> Outbox Relay contract
-> Transport Adapter boundary
-> executable tests against a fake / in-memory transport
-> idempotent dispatch intent and failure retention
```

Validation honesty: tests against a fake / in-memory transport MAY be real, executed runtime tests, but they
do **not** mean a real broker, a Celery worker, or the production delivery chain has been validated.

Day50 must NOT: claim Celery runtime is done; treat the Day40 custom Redis Streams / Consumer Group design as
Celery's internal implementation; hand-build a Celery replacement; or claim exactly-once across PostgreSQL,
broker, and worker.

Day55 (not Day50) completes:

```text
Outbox Relay -> a supported Celery broker transport -> Celery Worker
-> ACK timing -> redelivery -> idempotent processing -> poison-task handling -> recovery validation
```

Day50 and Day55 Topics are unchanged.

### Day54 — two kinds of streaming and three lifecycles

Distinguish two streaming kinds:

```text
A. token streaming of a synchronous Provider call
B. progress / event streaming of an already-persisted background Job
```

Distinguish three lifecycles:

```text
HTTP client connection lifecycle
Provider request lifecycle
durable background Job lifecycle
```

Production boundary to state explicitly:

```text
HTTP client disconnect
  != the Provider call necessarily stops
  != an already-persisted background Job auto-cancels
  != an already-accepted business commitment disappears
```

A background Job is cancelled only through an explicit, durable, auditable cancellation protocol, e.g.:

```text
cancel request
-> PostgreSQL durable cancellation state / intent
-> Worker cooperative cancellation check
-> guarded terminal transition
-> observable result
```

Do not lock a specific implementation, but keep the **durable, auditable, guarded, cooperative** constraints.
Day54 Topic is unchanged.

### Day94 — a thin end-to-end vertical integration loop

Day94 is an **integration day** for components already built in Phases 5–7, not a development day that
re-implements Agent, RAG, MCP, Playwright, or n8n.

Day94 integrates and validates one bounded but complete vertical user path, e.g.:

```text
user submits a research task
-> FastAPI persists and accepts the Job
-> Agent retrieves with RAG
-> a permissioned tool is called via MCP
-> a Playwright Worker fetches authorized data
-> n8n triggers human approval
-> result, citations, Artifact, and audit evidence are persisted
```

Acceptance focus: one full path really runs; correlation IDs are preserved; component failures have a clear
state and recovery path; result / citations / Artifact / audit evidence are traceable; and mock vs static
validation vs local runtime vs integration runtime vs production validation are clearly distinguished. Do not
chase five disconnected demos, and do not re-implement previously completed components in Day94. Day94 Topic
is unchanged.

### Day95 — representative drills, not exhaustive failure enumeration

Day95 still covers `failure recovery`, `load`, `security`, and `data repair`, but with a **limited,
representative** drill set — it does not exhaustively enumerate every production failure in one day. Each
category picks representative scenarios that prove the core mental model, and preferentially saves:

```text
failure-injection condition
expected behavior
actual command / test executed
log / trace / metric / database evidence
recovery steps
data-repair steps
unvalidated limitations
which class it is: static / local runtime / integration runtime / production validation
```

A limited scope must not be described as "comprehensive production validation." Day95 Topic is unchanged.

### Day91 — when the Final Capstone README is updated

`projects/final-capstone/README.md` may remain an early placeholder until Day91. It must **not** be rewritten
into a fictional completed capstone before then.

```text
When Day91 confirms the formal Product Requirements, Architecture, and Scope,
it must simultaneously update projects/final-capstone/README.md so the README becomes the entry point to the
final Capstone's real scope, run instructions, validation evidence, and limitations.
```

Before Day91, that README is a placeholder and must not be treated as the latest complete implementation
evidence. Day91 Topic is unchanged.

---

## Why This Curriculum

Phase 2 follows the Software Delivery Lifecycle, not a list of tools:

```text
Git -> GitHub -> Project Management -> CI/CD -> GitHub Actions
    -> Docker -> Deployment -> Kubernetes -> Production AI Backend
```

Students first understand WHY before HOW. Every tool solves an engineering problem introduced in
previous lessons: Git manages code history, GitHub adds collaboration, project management makes
work visible, CI/CD automates quality and delivery, GitHub Actions implements the pipeline as
code, Docker makes environments reproducible, deployment and Kubernetes run it reliably in
production, and the final lesson assembles a production AI backend architecture.

Follow `ROADMAP.md` for the official learning order.

Do not fully expand future days until they become the current lesson.
