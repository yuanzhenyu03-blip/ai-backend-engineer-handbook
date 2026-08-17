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
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day56-provider-resilience-rate-limits-token-cost-and-backpressure.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day56-provider-resilience-rate-limits-token-cost-and-backpressure-design.md` with a runnable provider-neutral in-memory model `day56_provider_resilience.py` + `test_day56_provider_resilience.py` (standard-library control flow; imports Day54's `IntentKind`). It adds the ADMISSION-TO-PROVIDER control plane on top of Day55 execution: even a Job holding the guarded claim still needs current Provider capacity, an intact cost reservation, and a healthy Provider path before an actual paid call. FOUR authorities are kept distinct — the PostgreSQL GUARDED CLAIM (execution authority for ONE durable Job, Day55), a shared/distributed RATE PERMIT (fleet-wide Provider capacity to call now; a claim is not a permit), a durable RESERVATION (tenant affordability; a limiter is not the budget ledger), and a CIRCUIT (Provider failure-domain containment keyed `circuit:{provider}:{account}:{model}:{region}`, no secrets) — and FIVE dispatch outcomes are executable via `evaluate_dispatch`: CALL (all four agree), DEFER (no permit / circuit OPEN / limiter outage / no reservation and NO call made -> persist `retry_reason`/`next_attempt_at`/`defer_count`/`deadline`, release the Worker, NO sleep), RECONCILE (external execution unknown or Attempt evidence -> never blind retry), TERMINAL (durable cancellation/deadline intent -> guarded CANCELLED/EXPIRED), NOOP (already terminal); durable terminal/cancellation facts and execution evidence OUTRANK capacity retry. Retry is bounded exponential backoff with FULL jitter and `Retry-After` treated as an EARLIEST floor (a synchronized retry storm / thundering herd is NOT a cache avalanche). A shared-limiter OUTAGE fails CLOSED for new paid calls by default (reads/cancellation/completed-result reads/reconciliation still work); a tightly bounded emergency fail-open is an EXPLICIT policy, never a default bypass. A no-permit-before-call is a durable DEFER (not FAILED, not PENDING_RECONCILIATION) that consumes NO execution-retry budget, uses a separate bounded `defer_count`, and never schedules past the business deadline. Cost control is distinct from capacity: `reserve_worst_case` reserves the BOUNDED WORST-CASE cost from the persisted contract (`max_tokens/1000 * price_per_1k_tokens`), NOT the remaining balance; if the tenant cannot cover it, do not call; success settles actual use and RELEASES the unused remainder back to the durable tenant ledger, not the rate limiter; unknown execution HOLDS the reservation for reconciliation. Backpressure lives BEFORE the durable Job + Outbox commit (`admit_job`: tenant over its own quota -> 429, system-wide capacity/dependency unavailable -> 503 which dominates; never 202 for a commitment that cannot be kept; an accepted Job is NEVER retroactively converted to 429/503). A Worker NEVER silently reduces persisted `model`/`max_tokens`; degradation is allowed only when the persisted, product-authorized contract permits it, down to `min_model`/`min_max_tokens`. A Provider 429 alone is not universal proof nothing executed: `classify_execution_certainty` returns DEFINITELY_NOT_ACCEPTED (safe ordinary-defer/retry) vs MAY_HAVE_EXECUTED / UNKNOWN (RECONCILE), and any Attempt evidence (a `provider_request_id` or the Day55 conservative dispatch marker) forces RECONCILE before capacity gating. The circuit breaker CLOSED allows, OPEN durably defers new calls, and HALF_OPEN permits only a small bounded PROGRESSIVE probe set — one successful probe does not close the circuit or release the herd. Deadline expiry performs a guarded EXPIRED + reservation RELEASE only with proof of no external execution; any evidence -> PENDING_RECONCILIATION with the reservation HELD. The zero-defer incident (a bad release set max defer duration to zero, prematurely expiring capacity-deferred Jobs) is contained by rolling the configuration back FIRST (future harm only, NOT a business-fact rollback), building a bounded affected set from release + a time window + the expiry reason + Attempt/Event evidence + deadline (`build_capacity_expiry_affected_set`, preserving expired history, never a bulk flip), and re-dispatching ONLY Jobs with proof of no Provider execution and a still-valid contract/deadline via a guarded, audited `repair_redispatch` that writes a NEW durable `OutboxDispatchIntent` for the Relay to publish after commit (never a direct queue call); Jobs with Provider evidence are RECONCILE_ONLY. In-memory control-flow tests executed (Python 3.10.12, pytest 7.4.3 -> 34 passed; full api suite 419) — APPLICATION CONTROL FLOW ONLY. A real Celery broker/Worker, a real Redis distributed limiter/circuit store, real PostgreSQL transactions/isolation, real Provider traffic/rate limits/costs, load tests, and Worker-kill/fault-injection integration are NOT RUN; Day57 owns integration + failure injection and Day58 owns observability/runtime evidence — neither is implemented here. Schema honesty: a `deferred` status, a durable defer record (`retry_reason`/`next_attempt_at`/`defer_count`/`deadline`), the per-Job `execution_retry_count` vs `defer_count`, and a tenant cost-reservation ledger (reserved/settled/held) are new facts MODELED in-memory; the real schema needs a Day48-safe FORWARD additive migration (new status allowlist value + defer/reservation columns via a gated revision), never a rewrite of published history; the rate limiter and circuit state are TRANSIENT coordination (Redis-like), not durable tenant truth. Day55 guarded claim/Outbox/P1 dispatch marker and Day54 durable intents are reused. No real credentials, raw prompts, Document content, raw Provider payloads, or secrets are persisted or logged.
- Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection.
  Scope: fake/deterministic providers, contract tests, failure injection, runtime evidence.
  Connection: advances the Day43-baseline test suite into fake-provider, contract, integration, and failure-injection tests with recovery verification; Day58 integrates and verifies observability to close the phase.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day57-ai-backend-testing-fake-providers-contract-tests-and-failure-injection.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day57-ai-backend-testing-fake-providers-contract-tests-and-failure-injection-design.md` with a runnable deterministic verification harness `day57_testing_harness.py` + `test_day57_testing_harness.py` (standard-library control flow driving the REAL Day56 policy functions + Day53's real pydantic validator). It turns the Day43–Day56 reliability policies into REPEATABLE EVIDENCE and injects failures, keeping FOUR evidence tiers explicit (conceptual/static design; executed local runtime; integration runtime; production) and marking real infrastructure NOT RUN — real PostgreSQL, a real Celery broker/Worker-kill/redelivery, and a real Redis limiter/circuit are the INTEGRATION RUNTIME tier (NOT RUN, and NOT production), while real Provider traffic/production validation are the PRODUCTION tier (NOT RUN). The harness provides a controllable Fake Provider (`ControllableFakeProvider`: scripted `ScriptedResponse` outcomes, a cross-call `calls` count, an independent `ProviderCallLog` that survives "Worker loss", and `request_received`/`release_response` gates via `threading.Event` so timeout/kill windows are CONTROLLED not timed), a `FakeClock` + `DeterministicRandom` for reproducible backoff/jitter, an application-owned `ProviderAdapter`/`ProviderOutcome` (failure kind, execution certainty, optional request id, safe retry info, safe metadata — never SDK exception classes/HTTP codes/private fields, and never writing Job state or cost), a strict `attempt_late_completion` late-result contract, and an explicit `VALIDATION_MATRIX`/`not_run_claims()` evidence taxonomy. Executed scenarios (EXECUTED LOCAL RUNTIME): a bare Provider 429 -> durable `PENDING_RECONCILIATION` with the Provider call count still ONE, no ordinary retry granted a new rate permit, reservation HELD, redelivery reconcile-only (a durable status alone is insufficient); a missing `provider_request_id` is NOT proof of no execution — a Worker can crash after the request leaves the process, so Day55's conservative `provider_dispatch_started_at` marker forces RECONCILE (an idempotency key mitigates risk but is not proof/permission); the Adapter delivers an application-owned typed outcome + execution-certainty classification (DEFINITELY_NOT_ACCEPTED may ordinary-defer/retry, MAY_HAVE_EXECUTED/UNKNOWN reconcile); a syntactically valid Provider JSON that violates the persisted `(schema_name, schema_version)` is a CONTRACT_VIOLATION (Day53 real validator), not business success (no Result Artifact, not succeeded, no blind second call; current Provider config governs new calls only); deterministic backoff/jitter with Retry-After as an EARLIEST floor (every wake at/after it, controlled draws spread, never a wake-all); a controlled timeout window with no sleeps and a timeout-after-receipt that is not proof of no execution (`PENDING_RECONCILIATION` + reservation HELD); late-result completion ONLY if the Job is non-terminal AND awaiting reconciliation AND the payload strictly validates AND `job_id` + `attempt_id` + `correlation_id` + `provider_request_id` all match durable evidence (a terminal CANCELLED Job rejects even a fully matching late result without overwriting state); limiter outage fails CLOSED (DEFER, zero Provider calls, bounded `next_attempt_at` + separate `defer_count`, `execution_retry_count` unchanged); deadline behavior with no evidence (guarded EXPIRED + reservation release) vs with marker/request evidence (`PENDING_RECONCILIATION` + reservation held); admission backpressure where system-wide 503 dominates a tenant 429; and a guarded, IDEMPOTENT repair under concurrency (a unique `repair:{job_id}:{release_version}:defer_deadline_expired` claimed atomically -> exactly one new Outbox intent even under duplicate/concurrent repair, `ALREADY_APPLIED` thereafter; a Job with Provider evidence is RECONCILE_ONLY). Executed: `python3 -m pytest -q test_day57_testing_harness.py` -> 23 passed (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3); full `projects/ai-backend-data-layer/api/` suite -> 465 passed. NOT RUN (explicitly not claimed): real PostgreSQL transaction/rollback/isolation and guarded concurrent terminal transitions (an ORM mock cannot prove committed facts); a real Celery broker + Worker process + redelivery + Worker-kill recovery; a real Redis limiter/circuit outage + restored-capacity no-herd; and any real Provider traffic/rate limits/cost. `pytest passed` alone is NOT audit-grade runtime evidence — a real integration run must also preserve the exact command/revision, the fault point, committed-DB-state queries via a NEW connection, the Fake Provider cross-process call log, and broker/Worker lifecycle evidence. A real `job_repair_history` table + migration is a FORWARD-ADDITIVE design only, not migrated or tested. Day56 policy functions, Day55 dispatch marker, Day54 durable cancellation, and Day53 strict validation are reused. Day58 owns structured observability (structured logs, `job_id`/`trace_id`/`attempt_id` correlation, metrics, traces, runtime evidence) and the Phase 4 capstone — not implemented here. No secrets, raw prompts, or raw Provider payloads are persisted or logged; repair/audit records carry only safe decision evidence.
- Day58 — Production AI API Capstone, Observability and English Interview.
  Scope: integrate the phase into a runnable API with observability; phase-level English interview.
  Connection: integrates and verifies observability (structured logs, job_id/trace_id/attempt_id correlation, metrics, traces, runtime evidence) into the runnable API and runs the phase English interview; Phase 5 (Day59) then begins running this same backend as a real FastAPI + PostgreSQL + Alembic INTEGRATION_RUNTIME (the Day59–61 Production Integration Gate), turning this deterministic in-process capstone into real local integration evidence — Playwright browser automation begins only at Day62.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day58-production-ai-api-capstone-observability-and-english-interview.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day58-production-ai-api-capstone-observability-and-english-interview-design.md` with a runnable deterministic in-process observability model `day58_observability_capstone.py` + `test_day58_observability_capstone.py` (standard-library control flow; imports Day57's `EvidenceTier`/`MatrixRow`/`RunStatus` and Day56's `ExecutionCertainty`). Phase 4 capstone: it makes the distributed AI Job execution EXPLAINABLE and AUDITABLE across API -> Outbox Relay -> Worker Attempt -> Provider Adapter -> completion/reconciliation, keeping the core principle that observability is a correlated, safe, aggregatable, reviewable EVIDENCE system AROUND durable state — it does NOT replace the durable state machine and does NOT grant permission to retry unknown external work; missing telemetry is an observability GAP, never proof of no execution. The model covers: the identity contract with SEPARATE contexts (a durable Worker Attempt `IdentityLifecycle` — `job_id` = durable business identity and `correlation_id` = business-chain association both STABLE across retries, with a NEW `attempt_id` and normally a NEW `trace_id` per Attempt and NO `request_id`; and a distinct `HttpRequestContext` for one inbound HTTP request — `job_id`/`correlation_id` plus a NEW `request_id` AND a NEW `trace_id`, NO `attempt_id`, so a status/poll never masquerades as a Worker Attempt or silently reuses its trace, with an EXPLICIT `parent_trace` for legit traceparent continuity; `trace_id` is one distributed trace, NOT business truth); a safe `StructuredEvent` contract that carries only safe fields (event_name/job_id/correlation_id/attempt_id/trace_id/provider/model/outcome/bounded duration_ms/request_id_present/dispatch_marker_present/reason) and REJECTS raw prompts, raw Provider responses, api keys, secrets, tenant documents, and unknown fields (`UnsafeTelemetryError`), emitting `provider.call.timeout` (the application's OBSERVED timeout/unknown outcome, NOT proof of non-execution) vs `provider.call.suppressed` (a later reconciliation Attempt that refused a second Provider call, `reason=prior_attempt_may_have_executed`, `dispatch_marker_present=True`); a `MetricRegistry` enforcing a LOW-CARDINALITY label contract — Counter `provider_call_total{provider,model,outcome}` (query its RATE, not the raw cumulative total), Histogram `provider_call_duration_seconds{provider,model}` (distribution/tail latency), Gauges `provider_calls_in_flight{provider,model}` (rises at call start, falls at completion/timeout) and `jobs_pending_reconciliation{provider,model}` (backlog) — that raises `HighCardinalityLabelError` if `job_id`/`attempt_id`/`trace_id` are used as labels (they belong in logs/traces), rejects uncontrolled label VALUES (`validate_label_values`) and requires `model` to come from a FINITE controlled registry (`ALLOWED_MODEL_VALUES`) or be normalized to a bounded bucket (`normalize_model_label`) since a regex alone allows unbounded distinct models, and validates every canonical StructuredEvent VALUE (bounded id/event_name shapes, provider/model/outcome allowlists, a finite `reason` enum, secret/overlong rejection) rather than trusting the caller, with alerting that COMBINES timeout rate + in-flight saturation + a sustained reconciliation backlog; trace/span-link modeling where API acceptance, the Relay, Worker Attempt A, and later Attempt B are SEPARATE traces across durable asynchronous boundaries, a Provider Adapter call is a CHILD span of the current Attempt trace (`child_span` shares the trace_id), and a later async Attempt uses a SPAN LINK (`linked_trace`) to the IMMEDIATE preceding causal trace (not a child of an already-ended HTTP span, not fake synchronous nesting; link only the immediate prior since `job_id`+`correlation_id` carry stable end-to-end continuity); the durable-correctness-vs-observability boundary (`provider_dispatch_started_at` persisted BEFORE the external call; a missing `provider_request_id` or missing telemetry is NOT proof no call happened; PostgreSQL Job/Attempt/marker/reservation facts determine retry/reconciliation safety while logs/traces/metrics explain but never AUTHORIZE a repeat Provider call); a telemetry-exporter-failure policy (`TelemetryPipeline` — an exporter outage must NOT turn an accepted Job into FAILED or permit unsafe retry: keep core processing, bounded buffering then drop, and expose `telemetry_export_failures_total`/`telemetry_events_dropped_total`/`telemetry_export_queue_depth`; a stricter regulatory/product availability trade-off must be an EXPLICIT policy, never an accidental exporter-failure side effect); and the bad-observability-release rollback drill (a release removed `attempt_id` from Worker logs and added `job_id` to `provider_call_total` labels — FIRST roll back the observability release/config to stop further correlation loss + high-cardinality damage, NEVER roll back or overwrite valid Job/Attempt/dispatch-marker/reservation/Outbox facts because this is an observability failure not a business-state failure; bound the affected set by release version + time window; reconstruct affected Jobs from durable PostgreSQL facts; MARK telemetry gaps honestly and never fabricate missing logs/traces; a `PENDING_RECONCILIATION` Job whose telemetry is incomplete but whose database has a dispatch marker remains reconciliation-only and must NOT be requeued for an ordinary Provider call). Executed: `python3 -m pytest -q test_day58_observability_capstone.py` -> 38 passed (Python 3.10.12, pytest 7.4.3); full `projects/ai-backend-data-layer/api/` suite -> 503 passed. This proves EXECUTED_LOCAL_RUNTIME identity/event/metric/trace/telemetry-policy/rollback control flow ONLY. NOT RUN (explicitly not claimed): a real FastAPI runtime + a real OpenTelemetry exporter pipeline; real PostgreSQL/Redis/Celery integration with committed correlation evidence (including redelivery/Worker-kill); and real Provider traffic / production observability validation — these are INTEGRATION_RUNTIME and PRODUCTION tiers recorded NOT RUN. A reviewable runtime-evidence pack requires the exact command/revision/config/time window, the fault point, structured logs/traces/metrics, committed database queries from a NEW connection, independent Provider call evidence, Worker/Relay/broker lifecycle evidence, the actual result, and the explicit validation tier plus NOT RUN limits; `pytest passed` alone is not a reviewable pack. Day57's `EvidenceTier`/`RunStatus` taxonomy, Day56 `ExecutionCertainty`, and the Day55 `provider_dispatch_started_at` marker are reused. No secrets, raw prompts, raw Provider responses, or tenant documents are persisted or logged.

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

## Phase 5 — Production Runtime Integration and Browser Tool Engineering (Day59–Day66)

Status:
Complete (Day59–Day66 Completed). Day67 begins Phase 6.

Objective:
Close the Phase 4 evidence gap first, then add a browser capability. Day59–Day61 are a **Production
Integration Gate**: they inherit the Phase 4 models and tests and turn the deterministic in-process
EXECUTED_LOCAL_RUNTIME evidence into real local INTEGRATION_RUNTIME evidence (real FastAPI process, real
PostgreSQL/Alembic, real Redis/Celery broker and Worker, real Object Storage, a real OpenTelemetry exporter, and the
Provider adapter exercised over real HTTP by a separate deterministic fake HTTP Provider — a real/paid model
Provider is called only with explicit user authorization and otherwise stays NOT RUN). Day62–Day66 then build Playwright into an isolated, recoverable, auditable browser
worker exposed as a permissioned AI tool — not a fragile click script. Phase 4 still ends at Day58; Day59–61
do not retcon into Phase 4.

Knowledge connection:

```text
Day58 deterministic local Phase 4 evidence (real integration honestly NOT RUN)
    -> Day59–61 real local integration gate (FastAPI + PostgreSQL + Redis/Celery + Object Storage + OpenTelemetry + Provider adapter over real HTTP against a deterministic fake HTTP Provider)
    -> Day62–66 Playwright as a permissioned, queue-backed AI browser tool
```

Reused project directories: `projects/ai-backend-data-layer/` (the Phase 4 backend now run for real),
`projects/playwright-login/`, `projects/playwright-scraper/`, and `projects/fastapi-playwright/` (the browser
worker integrated with the Phase 4 API).

Per-day topics (Topic + concise scope; each Status: Planned):

- Day59 — Real FastAPI Runtime, PostgreSQL and Alembic Integration.
  Scope: run the Phase 4 API as a real FastAPI process against a real PostgreSQL database with real Alembic
  migrations; capture committed-DB evidence read back from a new connection.
  Connection: Day58 proved the Job state machine only in-process (real FastAPI/PostgreSQL integration was
  honestly NOT RUN); Day59 executes that first real local integration and produces committed-DB runtime
  evidence; Day60 extends the real run to the Outbox/broker/Worker path.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day59-real-fastapi-runtime-postgresql-and-alembic-integration.md`; Engineering Artifacts: `projects/ai-backend-data-layer/api/day59_runtime_app.py` (local-only FastAPI composition), `day59_acceptance_logic.py` + `test_day59_acceptance_logic.py` (7 passed, EXECUTED_LOCAL_RUNTIME), `day48_alembic/versions/0008_day59_acceptance.py` (forward additive migration), `day48_alembic/env.py` (controlled version-table width repair), `requirements-day59.txt`, and the design/runbook. Core rule: `202` = ONE committed acceptance bundle (queued Job + `request_fingerprint` + one `job.dispatch_requested` Outbox intent + Document links) verified from a NEW connection; the HTTP transaction never calls a Broker/Worker/Provider/Object Storage. Real local INTEGRATION_RUNTIME (Uvicorn + PostgreSQL 16 + Alembic through 0008) was executed in a disposable local environment during class; the updating agent re-ran only `py_compile` + the stdlib tests. NOT RUN: real Redis/Celery broker/Relay/Worker (Day60); real Object Storage/Provider HTTP/OpenTelemetry exporter (Day61); real JWT/JWKS/production secret manager, zero-downtime migration, multi-replica, load, production. No secrets/local URLs/passwords/tokens/tenant fixtures are committed.
- Day60 — Outbox, Redis/Celery Broker and Worker Recovery Integration.
  Scope: run the Day50 Outbox relay with a real Redis/Celery broker and a real Worker process; prove
  redelivery, idempotent processing, and Worker-kill recovery.
  Connection: Day59 gave a real API+DB runtime but the broker/Worker path was still NOT RUN; Day60 executes
  the real Outbox -> broker -> Worker chain with redelivery/recovery evidence; Day61 completes the gate with
  storage, provider, and telemetry.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day60-outbox-redis-celery-broker-and-worker-recovery-integration.md`; Engineering Artifacts: `projects/ai-backend-data-layer/api/day60_delivery_runtime.py` (the REAL Relay/Worker/recovery/repair runtime — SQLAlchemy Core + a Celery-injected publish), `day60_delivery_recovery_logic.py` (pure decision core) + `test_day60_delivery_recovery_logic.py` + `test_day60_runtime_schema_contract.py` (34 passed, EXECUTED_LOCAL_RUNTIME), `day60_runtime_app.py` (readiness app-factory, explicit `expected_revision`), `day60_celery_config.py` (late-ACK delivery settings), `day48_alembic/versions/0009_day60_delivery_runtime.py` + `0010_day60_runtime_schema.py` (forward-additive migrations: Relay claim fields, `job_repair_history` + its `redispatch_outbox_event_id` UNIQUE link, jobs lease/marker/`release_version` columns, and a widened status CHECK adding `pending_reconciliation`), `requirements-day60.txt`, and the design/runbook. Relay publishes BEFORE checkpointing `published_at` (at-least-once); the Worker takes authority via a guarded `UPDATE ... WHERE status='queued' RETURNING` + lease token/owner/expiry fencing; late ACK is transport, not a commit; expired lease + external evidence -> `PENDING_RECONCILIATION`, else the sweep atomically `running -> queued` + one `job.redispatch_requested` intent; bounded early-ACK repair uses an idempotent `repair_id` and never `.delay()`. A REAL Relay/Worker/recovery/repair runtime (`day60_delivery_runtime.py`) that uses the EXISTING Day48 lease TRIPLE `lease_owner`/`lease_token`/`lease_expires_at`, plus a real Celery app (`day60_celery_app.py`) and Relay/sweeper entrypoints (`day60_relay.py`/`day60_sweeper.py`), the CORRECTIVE (non-additive, drop-column) `0011_day60_lease_realign` migration (removes the never-written parallel `lease_expiry` that `0010` added), and the additive `0012_day60_repair_audit_attestation` migration (persists the repair incident window + operator attestations, written in the repair tx; the `IntegrityError` handler re-reads and returns `already_applied` only for a true duplicate, else `repair_failed`), were added in review; the updating agent executed only `py_compile` + the stdlib pure-logic + static-contract tests (34 passed) and has no Docker/PostgreSQL/Redis/Celery — INTEGRATION_RUNTIME NOT RERUN (no integration result claimed; see the runbook's Required rerun matrix). NOT RUN: real Provider HTTP/Object Storage/OpenTelemetry (Day61); production load/security/zero-downtime/multi-replica. No secrets/local URLs/passwords/tokens/fixture ids committed.
- Day61 — Object Storage, Provider Adapter and OpenTelemetry End-to-End Evidence.
  Scope: run a real FastAPI/Worker app end-to-end against real Object Storage and a real OpenTelemetry
  exporter, with the Provider adapter driven over REAL HTTP by a SEPARATE deterministic fake HTTP Provider
  process — verifying Provider-adapter / HTTP / timeout / correlation / response-handling integration across
  process boundaries (local `INTEGRATION_RUNTIME`); capture correlated logs/metrics/traces for one real Job.
  A deterministic fake HTTP Provider is NOT a real model Provider and does NOT validate real Provider
  traffic, rate limits, cost, or production behavior. A real or paid model Provider call runs ONLY with
  explicit user authorization, user-supplied credentials kept out of the repo/logs/evidence pack, a defined
  cost and call scope, results marked separately, and is never called Production Validation; without
  authorization the real model Provider stays `NOT RUN`.
  Connection: Day60 closed the broker/Worker gap but storage/exporter and Provider-adapter HTTP integration
  were still NOT RUN; Day61 finishes the Production Integration Gate by proving the adapter over real HTTP
  against a deterministic fake HTTP Provider (the real model Provider remains NOT RUN unless the user
  authorizes it); Day62 begins adding the browser as a new callable capability.
  Status: ✅ Completed. 66 local Day61 tests pass and a disposable PostgreSQL + Redis/Celery + MinIO + OTel Collector run verified the full success chain and timeout-after-receipt recovery. Success had a guarded Job completion, finished Attempt, persisted provider identity, matching MinIO HEAD metadata, fenced Outbox checkpoint and correlated acceptance/Relay/Worker spans. Timeout reached `pending_reconciliation`, created no success Artifact and cleared the full lease triple. Day61 uses only the deterministic fake Provider; real/paid Provider traffic and production-scale/multi-replica validation remain NOT RUN. No secrets committed.
- Day62 — Playwright Runtime, Locators and Reliable Async Interaction.
  Scope: the Playwright runtime object model (Browser/Context/Page), async lifecycle, locators and
  auto-waiting for deterministic interaction over brittle selectors.
  Connection: the Day59–61 gate proved the backend runs for real but it has no browser capability; Day62 adds
  a reliable Playwright runtime as a new tool surface; Day63 isolates authenticated browser contexts per
  tenant.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day62-playwright-runtime-locators-and-reliable-async-interaction.md`; Engineering Artifacts under `projects/fastapi-playwright/`: `src/day62_interaction_logic.py` (pure outcome/cleanup/locator rules), `src/day62_research_page.py` (a controlled localhost HTTP research page whose OWN JS clears a bounded `overlay_delay_ms` overlay, handles the click, and async-renders `Results for <query>`), `src/day62_browser_task.py` (async task: reused Browser, ONE Context per task, scoped role/`data-testid` Locators, actionability wait + business assertion, no fixed sleep, no `force=True`, `finally` Context cleanup preserving the primary operation error), `tests/` (pure-logic + real HTTP-loopback + a Playwright-gated real-Chromium suite), `requirements-day62.txt`, and the design/runbook. Core rule (reusing Day61): actionability is not business completion, and timeout/login-redirect/Page-crash are UNKNOWN or a FAILED precondition — never business `no result` and never blind-retry permission. Evidence: `python3 -m pytest -q tests/` = 13 passed, 1 skipped (the real-Chromium suite is gated on the `playwright` package), EXECUTED_LOCAL_RUNTIME; in class a real Chromium rendered `Results for Acme` from `/research?overlay_delay_ms=800` (EXECUTED_LOCAL_RUNTIME). NOT RUN by the updating agent: Python `finally` cleanup + the action-timeout case against a live browser; Day63 auth/session isolation; Day64 network/download/artifact flow; Day65 recovery/security policy; Day66 queue-backed integration; production. No secrets, login state, tenant data, real URLs/tokens, or screenshots committed.
- Day63 — Browser Authentication, Storage State and Tenant Isolation.
  Scope: login flows, storage state, and per-tenant/session `BrowserContext` isolation.
  Connection: Day62's runtime can interact but has no authenticated, isolated sessions; Day63 adds
  storage-state and per-tenant context isolation reusing the Phase 4 tenant boundary; Day64 extracts
  structured data and evidence from those sessions.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day63-browser-authentication-storage-state-and-tenant-isolation.md`; Engineering Artifacts under `projects/fastapi-playwright/`: `src/day63_session_gate.py` (pure authorization/claim decision core — Job-binding validation, atomic-claim classifier with `UPDATE ... RETURNING` semantics, credential-load gating, positive-identity verification, Origin/security check, final fence, storage-state Origin/Cookie-domain allowlist filtering, connection-flow persist classifier, and an orchestrator that proves the NEGATIVE effects), `src/day63_controlled_login_page.py` (a synthetic loopback account page with account/login_redirect/unapproved_origin modes), `tests/` (pure-logic + negative-effect + static gate-source contract + real HTTP-loopback + a Playwright-gated real-Chromium isolation suite), and the design/runbook (validation matrix + threat boundaries). Core model: Tenant = business authorization scope; BrowserContext = runtime isolation; BrowserSession = revocable authorization capability; storage_state = protected credential material; every non-AUTHORIZED outcome (AUTHENTICATION_PRECONDITION_FAILED / AUTHORIZATION_SESSION_FAILURE / UNKNOWN_AUTHORIZATION_STATE / SECURITY_FAILURE) blocks publication and is never a business `no result` or a blind retry. Evidence: the LIVE classroom artifact was CONCEPTUAL_STATIC; the updating agent authored and ran `python3 -m pytest -q tests/test_day63_session_gate.py tests/test_day63_controlled_login_page_http.py tests/test_day63_playwright_isolation.py` = 36 passed, 1 skipped (the real-Chromium isolation suite is gated on the `playwright` package), EXECUTED_LOCAL_RUNTIME. NOT RUN: real Chromium BrowserContext isolation / redirect-popup observation; real PostgreSQL `UPDATE ... RETURNING` atomic claim; real credential encryption/KMS/Object Storage; a real Worker; queue integration (Day66); production. Async fix (v0.1.157): the real-Chromium tests now use one async event loop (run_task_authorization_async + AsyncTaskDeps) with no nested run_until_complete; 8 async-path pure tests added (28->36 passed). The real-browser suite was ATTEMPTED but Chromium could not be downloaded in the sandbox, so it remains NOT RUN. Review fixes (v0.1.156): the final fence now requires lease_owner==attempt_id + lease_expires_at>now (an old/expired-lease Attempt can never publish); the Cookie allowlist default is the Origin's host-only hostname (not the full Origin string); a published result whose Context cleanup failed is reported INCOMPLETE (TaskCompletion), never SUCCESS; classify_login_persist treats only state-saved+metadata-failed as ORPHAN_INACTIVE and state-not-saved as PERSIST_CONSISTENCY_FAILED; and the gated real-Chromium suite adds popup/unapproved-origin and login-redirect-no-auto-login tests (still NOT RUN). Day62's `13 passed, 1 skipped` is NOT reused as Day63 evidence. No secrets, real credentials, real target URLs, tenant data, cookies, tokens, or storage-state exports committed.
- Day64 — Dynamic Extraction, Network Events and Artifact Evidence.
  Scope: structured extraction from dynamic pages, network interception, downloads/uploads, and artifacts
  saved into the real Day61 Object-Storage boundary.
  Connection: Day63 gave isolated authenticated sessions but no captured output; Day64 turns them into
  structured extraction and artifact evidence in Object Storage; Day65 hardens the browser against failures
  and abuse.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day64-dynamic-extraction-network-events-and-artifact-evidence.md`; Engineering Artifacts under `projects/fastapi-playwright/`: `src/day64_extraction_contract.py` (pure Extraction/Artifact decision core — task-contract readiness, DOM/network source roles, STRICT network correlation with client_request_id/export_id + safe/redacted metadata, Extraction Contract schema-drift classification, download/upload validation + precise `source_/artifact_/accepted_/rejected_count`, Object Storage HEAD verification, persist/candidate-retention + forward-repair, the final-fence-still-controls-publish rule reusing `day63_session_gate.final_fence`, the `assemble_trusted_artifact` orchestrator that publishes ONLY if the whole chain passes, and a broad-listener rollback classification), `src/day64_controlled_report_page.py` (a synthetic SPA + `/api/reports/{id}` + `/api/exports`), `tests/` (pure failure-path + real HTTP-loopback), and the design/runbook. Core model: `page lifecycle signal != extraction readiness != valid Artifact != published business success`; a trusted Artifact requires the whole evidence chain. Evidence: the LIVE classroom artifact was CONCEPTUAL_STATIC; the updating agent authored and ran `python3 -m pytest -q tests/test_day64_extraction_contract.py tests/test_day64_report_page_http.py` = 25 passed, EXECUTED_LOCAL_RUNTIME (23 pure decision-core failure-path + 2 controlled report/export page over a REAL HTTP loopback). NOT RUN: real Playwright extraction/network interception/download-upload; the REAL Day61 Object Storage HEAD; a real PostgreSQL Artifact-reference transaction; a real Worker; queue integration (Day66); production. Review fix (v0.1.160): download validation now uses the ACTUAL parsed rows validated against the same TaskContract (DownloadCandidate.parsed_records; no forgeable schema_valid/business_valid booleans; distinct SCHEMA_FIELD_MISSING/TYPE_MISMATCH/VALUE_INVALID/CONTRACT_MISMATCH + BUSINESS_INVALID), so the network JSON and the downloaded artifact are validated independently. Tests 18 -> 25 passed. Review fixes (v0.1.159): export_id can no longer bypass the initial client_request_id match (strict correlate_export + extract_export_id/correlate_followup); the final fence sits at the guarded durable-write boundary (HEAD -> final fence -> guarded txn), so a fence failure commits nothing; the Extraction Contract validates field types/values (FIELD_MISSING/TYPE_MISMATCH/VALUE_INVALID/CONTRACT_MISMATCH); network metadata is an allow-list; and the controlled page is now a genuinely dynamic synthetic SPA for a FUTURE real-Playwright test (still NOT RUN). Tests 16 -> 25 passed. Day63's test results are NOT reused as Day64 evidence. No secrets, real credentials, Cookies, storage-state exports, real target URLs, customer data, raw sensitive payloads, or screenshots committed.
- Day65 — Browser Failure Recovery and Security Boundaries.
  Scope: timeout/retry policy, diagnostics, screenshots/traces, SSRF/credential handling, website
  policy/authorization, and prompt-injection boundaries (no bypass of security controls, captchas, or
  anti-automation).
  Connection: Day64 could extract but was fragile and unbounded; Day65 adds failure recovery and security
  boundaries; Day66 runs it as a durable, permissioned worker on the job lifecycle.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day65-browser-failure-recovery-and-security-boundaries.md`; Engineering Artifacts under `projects/fastapi-playwright/`: `src/day65_recovery_security_policy.py` (pure recovery/security decision core — timeout classification UNKNOWN_OUTCOME vs SAFE_TO_RETRY, unknown-outcome reconciliation by the FULL strict Day64 action identity (allowed_origin + method + normalized_endpoint + report_id + client_request_id, with a verified export_id bound to that same initial identity and never substituting for the client_request_id match) + server audit, distinguishing terminal completed/imported (CONFIRMED_COMPLETED, may publish) from accepted/pending/running (CONFIRMED_ACCEPTED_OR_IN_FLIGHT — 202 accepted != completed != published Artifact: no replay, no publication, keep reconciling) and only authoritative not_found/never_started (CONFIRMED_NOT_STARTED, may enter bounded retry), diagnostics policy private/redacted/access-controlled/retention-bounded/audited-only, navigation/redirect SSRF gate by scheme + exact Origin + resolved IP blocking loopback/private/link-local/cloud-metadata, scoped credential release with no cross-Origin storage-state forwarding, instruction authority -> PROMPT_INJECTION_BLOCKED, CAPTCHA -> HUMAN_VERIFICATION_REQUIRED, bounded retry eligibility (proven non-start OR usable idempotency key, and the conservative next wait + one per-attempt timeout fitting BOTH remaining deadline and total budget) + Retry-After-vs-deadline, and incident classification), with RETRY and credential RELEASE ENFORCED through `day63_session_gate.final_fence` (recomputed by `authorize_retry`/`authorize_credential_release`, never a caller-supplied authorized/session_valid flag), plus `tests/` and the design/runbook. Core rule: `no observed completion != proven operation failure`; page content is untrusted input, not authorization; a security control is a STOP, not a retry. Evidence: the LIVE classroom artifact was CONCEPTUAL_STATIC; the updating agent authored and ran `python3 -m pytest -q tests/test_day65_recovery_security_policy.py` = 20 passed, EXECUTED_LOCAL_RUNTIME. NOT RUN: real Playwright timeout/reconciliation; real trace/screenshot redaction; real redirect/DNS/IP enforcement; real storage-state/Cookie behaviour; real CAPTCHA handling; a real audit lookup; a real Worker/queue (Day66); integration; production. Day64's `25 passed` is Day64-only evidence and is NOT reused as Day65 validation. No secrets, real credentials, real target URLs, Cookies, tokens, customer data, raw sensitive payloads, screenshots, or CAPTCHA-bypass logic committed.
- Day66 — Queue-backed Playwright Worker as a Permissioned AI Tool.
  Scope: run the browser as a durable, queue-backed worker on the Day50/Day60 job lifecycle, exposed as a
  constrained, permissioned AI tool.
  Connection: Day65 secured the browser but not as a durable backend capability; Day66 makes it a
  queue-backed, permissioned tool the AI backend can call; Phase 6 (Day67) orchestrates these backends with
  n8n.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day66-queue-backed-playwright-worker-as-a-permissioned-ai-tool.md`; Engineering Artifacts under `projects/fastapi-playwright/`: `src/day66_queue_backed_permissioned_worker.py` (pure queue-backed permissioned-worker decision/orchestration core — tool-call proposal validation with idempotency bound to a request fingerprint (tenant + operation + exact Origin + report scope; same key + different fingerprint rejected; user approval necessary but not sufficient; backend policy is the enforceable authority); the acceptance lifecycle boundary (Provider response = proposal/step 3, then validation, then durable acceptance only at the committed transaction); atomic Browser Task + Permissioned Tool Contract + Outbox dispatch intent acceptance -> 202 + task_id, dispatched by an independent Outbox Relay AFTER commit (never a direct in-request publish); a minimal versioned Queue Envelope carrying identity only (envelope_version/event_id/task_id/trace_id/event_type) and never Cookies/storage state/Authorization/Provider keys/raw diagnostics, with an unsupported version dead-lettered + ACKed without loading a Job; a guarded PostgreSQL claim + lease for execution ownership (one winner; queue delivery is only a notification); stale-write rejection via the Day63 `final_fence`; commit-before-ACK terminal dedupe (a redelivered Worker reads terminal state, does not re-run Playwright, and ACKs the duplicate); Day65 UNKNOWN_OUTCOME reconciliation hand-off (lease expiry != no external effect); a fenced bounded-retry gate reusing `day65_recovery_security_policy.authorize_retry` where a retry is a NEW auditable Attempt; durable cooperative cancellation (cancellation_requested, not immediate cancelled) with fence revalidation checkpoints; a safe Tool Result boundary (verified safe summary + protected Artifact reference only, never raw CSV/trace/Cookie/DOM/network); task/attempt/event/lease/trace identity + safe audit; and stale-Worker fence-removal incident classification), reusing the Day63 fence and the Day65 recovery core rather than re-implementing security rules, plus `tests/` and the design/runbook. Core model: the LLM proposes; the backend owns authorization, durable truth, dispatch, execution authority, recovery, and audit; `accepted != running != succeeded != published Artifact`. Evidence: the LIVE classroom artifact was CONCEPTUAL_STATIC; the updating agent authored and ran `python3 -m pytest -q tests/test_day66_queue_backed_permissioned_worker.py` = 14 passed, EXECUTED_LOCAL_RUNTIME. NOT RUN: a real Provider/LLM tool loop; real guarded PostgreSQL concurrent claims; a real Outbox Relay/Broker duplicate delivery; real Celery ACK/redelivery; real lease expiry/recovery; real Playwright BrowserContext execution; real Session revocation/cancellation; real Object Storage Artifact publication; integration; production. Day65's `20 passed` and prior Day59–Day61 evidence are NOT reused as Day66 validation. No secrets, real credentials, real URLs, Cookies, storage state, Authorization headers, Provider keys, customer data, raw traces/screenshots/DOM/network payloads, or real Provider calls committed.

Phase deliverable:

```text
Real local INTEGRATION_RUNTIME evidence for the Phase 4 backend
(FastAPI + PostgreSQL + Redis/Celery + Object Storage + OpenTelemetry
 + Provider adapter driven over real HTTP by a separate deterministic fake HTTP Provider;
 real/paid model Provider NOT RUN unless explicitly authorized by the user)
+ an isolated, recoverable, auditable Playwright browser worker exposed as a permissioned AI tool.
```

Validation requirement:
Day59–61 produce EXECUTED local `INTEGRATION_RUNTIME` evidence (real processes / DB / broker / storage /
exporter, plus the Provider adapter over real HTTP), not `PRODUCTION` validation. These are FUTURE
requirements: no Day59–61 integration run, no real Provider call, and no production validation has been
performed or is claimed here.

Four-tier evidence taxonomy (use these exact, searchable names):

```text
CONCEPTUAL_STATIC
EXECUTED_LOCAL_RUNTIME
INTEGRATION_RUNTIME
PRODUCTION
```

- `CONCEPTUAL_STATIC` — design, documentation, schema shape, and static configuration checks, with the target
  runtime NOT executed.
- `EXECUTED_LOCAL_RUNTIME` — executed local Python control flow, unit tests, and fake / in-memory doubles that
  do NOT cross a real external process or infrastructure boundary. An in-process fake / mock / double is
  ALWAYS `EXECUTED_LOCAL_RUNTIME` and NEVER `INTEGRATION_RUNTIME`.
- `INTEGRATION_RUNTIME` — real disposable / local processes or infrastructure participate, for example:
  FastAPI/Uvicorn, PostgreSQL, Alembic, a Redis/Celery broker, a Celery Worker process, Object Storage, an
  OpenTelemetry Collector/Exporter, and a separate deterministic fake HTTP Provider process. Reproducible
  evidence must be saved. A separate fake HTTP Provider can prove Provider-adapter / HTTP / correlation
  integration but CANNOT prove real model Provider behavior.
- `PRODUCTION` — claimed only for a real production environment or an explicitly approved production-grade
  environment.

Provider boundary: a real or paid model Provider request runs ONLY when ALL of these hold — the user
explicitly authorizes it; the user actively and securely supplies credentials; credentials are never written
to the repo, logs, or the evidence pack; cost and call scope are defined; a Provider sandbox or real-call
result is marked separately; and a single real call is never called Production Validation. Without
authorization, Day61 completes the network / adapter integration with the deterministic fake HTTP Provider
and marks the real model Provider `NOT RUN`. "Independent Provider evidence" may be the safe request log, call
count, idempotency keys, and response results saved by the separate fake HTTP Provider process — never
prompts, full Provider responses, API keys, `Authorization` headers, or tenant-sensitive data.

A real `INTEGRATION_RUNTIME` run must save the exact command/revision/config/time window, the fault point,
committed-DB queries from a NEW connection, broker/Worker lifecycle, and independent (fake-HTTP-Provider)
evidence. Do not teach bypassing website security controls, captchas, or anti-automation. Claim
runtime / integration / production evidence only when actually executed and saved.

---

## Phase 6 — n8n AI Workflow Integration (Day67–Day70)

Status:
Planned

Objective:
Use n8n to orchestrate the now-real API, the permissioned browser tool, and AI capabilities as an
integration/workflow layer — not a low-code replacement for backend correctness. Durable truth stays in
PostgreSQL.

Knowledge connection:

```text
Real backend + permissioned browser tool (Phase 5)
    -> n8n workflow integration (orchestration over correct backends, idempotent long jobs, human approval, audit)
```

Reused project directory: `projects/n8n-workflows/` (workflow-integration evidence).

Per-day topics (Topic + concise scope; each Status: Planned):

- Day67 — n8n Workflow Model, Triggers, FastAPI Integration and Responsibility Boundaries.
  Scope: workflow model, triggers/nodes, authenticated FastAPI integration, and where responsibility stays in
  the backend rather than the low-code layer.
  Connection: Phase 5 produced real backends and a browser tool but no orchestration across them; Day67 adds
  n8n as an orchestration layer with clear responsibility boundaries; Day68 handles long-running AI jobs.
- Day68 — Long-running AI Jobs: Polling, Callback, Correlation and Idempotency.
  Scope: polling/callback patterns, correlation-ID propagation, and idempotency for long AI jobs.
  Connection: Day67 could trigger the backend but not manage long async jobs safely; Day68 adds
  polling/callback correlation and idempotency reusing the Phase 4/5 job lifecycle; Day69 adds human approval
  and hardening.
- Day69 — Human Approval, Retry, Secrets, Audit and Error Workflows.
  Scope: human-in-the-loop approval, retry/error workflows, secrets handling, and audit.
  Connection: Day68 handled long jobs but had no human gate or hardening; Day69 adds approval, retry/error
  workflows, secrets, and audit; Day70 integrates it all into a workflow capstone.
- Day70 — n8n + FastAPI + AI Tool Integration Capstone and Interview.
  Scope: integrate workflows with the real backend and browser tool; phase-level English interview.
  Connection: Day69 completed workflow hardening; Day70 integrates n8n + FastAPI + AI tools into a capstone
  and runs the phase interview; Phase 7 (Day71) builds the AI agent backend these workflows will call.

Phase deliverable:

```text
n8n workflows orchestrating the real FastAPI AI backend and permissioned browser tool, with idempotent
long-job handling, human approval, and audit.
```

Validation requirement:
n8n must not replace backend correctness; durable truth stays in PostgreSQL. Claim runtime/production
evidence only when executed and saved.

---

## Planning Horizon and Completion Model (Day71 onward)

```text
The roadmap is competency-gated, not day-count-gated.
The published lesson numbers are planning coordinates, not a promise that the course must end at a fixed number.
```

From Day71 onward the AI Backend track is an **AI Backend Employment Track**. Completion is defined by passing
the **Employment Readiness Gate** (see below), not by reaching a fixed final day. The current planning horizon
runs to **Day130**, but Day130 is only the present planning coordinate — NOT a permanent cap. If the
Employment Readiness Gate is not yet met, Planned lessons may be added, split, merged, or renumbered based on
real job requirements, AI ecosystem changes, a learner's real weak points, and project/interview feedback.
Completed lessons (Day01–Day58) stay stable; only `Planned` lessons may be renumbered or adjusted. The AI core
(LLM Application, Agent Runtime, MCP, Production RAG, Evaluation, AI Safety, AI Operations) must not be
compressed just to keep a tidy final number. The agent runtime framework is not pre-locked; it is chosen only
after an explicit Framework / Job-Market Refresh and always lives behind a replaceable adapter boundary.

---

## Mandatory Runnable Checkpoint Cadence

This is a normative execution constraint for the AI phases (Day71 onward). It does not change any Day Topic;
it constrains how the Engineering Artifact is exercised.

Rules:

1. Never go more than **4–6 consecutive lessons** without running the cumulative Engineering Artifact at a
   Runnable Checkpoint.
2. A Checkpoint is **not** pure review, a documentation summary, or static design — it is an actual run.
3. It must run the **same Artifact that has been evolving since the start of that Phase**, not a fresh demo.
4. Every implementation day incrementally modifies that one Artifact; days do not create unrelated,
   throwaway demos.
5. Each Checkpoint must save reproducible evidence:

```text
exact command
revision / commit
relevant config
runtime boundary
evidence tier
actual result
tests
safe logs / traces / metrics (when applicable)
failure point (when applicable)
NOT RUN limitations
```

6. `pytest passed` does NOT auto-upgrade to `INTEGRATION_RUNTIME` or `PRODUCTION`; it is
   `EXECUTED_LOCAL_RUNTIME` unless real external processes/infrastructure actually participated with saved
   evidence.
7. Anything not actually executed must be marked `NOT RUN`.

Checkpoint plan for Day71–Day130 (planning coordinates; each runs the evolving Phase Artifact, max gap ≤ 6
lessons):

```text
Phase 7A (Day71–78):
- Day74  — runnable contract / tool-calling checkpoint
- Day78  — LLM Application Runtime capstone checkpoint

Phase 7B (Day79–94):
- Day83  — framework-agnostic durable Agent checkpoint
- Day88  — selected-framework adapter checkpoint
- Day94  — Agent + MCP integration capstone checkpoint

Phase 7C (Day95–106):
- Day99  — ingestion / embedding / vector-index checkpoint
- Day103 — retrieval + citation + evaluation checkpoint
- Day106 — Production RAG capstone checkpoint

Phase 7D (Day107–116):
- Day110 — dataset + grader + retrieval/answer evaluation checkpoint
- Day113 — regression + release-gate checkpoint
- Day116 — incident / rollback / repair capstone checkpoint

Phase 8 (Day117–130):
- Day120 — backend + Agent/MCP integration checkpoint
- Day124 — thin vertical path + evaluation-gate checkpoint
- Day127 — deployed observability / runbook checkpoint
- Day130 — portfolio and Employment Readiness Gate review
```

No new lesson numbers are added for Checkpoints; they run on the listed existing Days. This cadence is
mirrored in summary form in `ROADMAP.md` so CURRICULUM and ROADMAP agree on execution requirements.

---

## Phase 7A — LLM Application Engineering (Day71–Day78)

Status:
Planned

Objective:
Evolve a single Provider call (Day53–58) into a complete, testable LLM Application Runtime: architecture,
token/context/sampling limits and failure modes, a replaceable Provider Adapter, prompt contracts and
versioning, structured output and function calling, streaming/caching/batching, model routing/fallback with
latency and cost engineering, and fake-Provider contract/regression tests.

Knowledge connection:

```text
Day53–58 Provider call + Streaming + Resilience + Testing + Observability
    -> a complete LLM Application Runtime (contracts, routing, cost, tests) behind a replaceable Provider Adapter
```

Reused project directory: `projects/ai-agent/` (LLM application runtime foundations).

Per-day topics (Topic + concise scope; each Status: Planned):

- Day71 — LLM Application Architecture, Tokens, Context, Sampling and Model Failure Modes.
  Scope: application architecture, token/context windows, sampling, and model failure modes.
  Connection: Phase 6 orchestrated backends but had no LLM application layer; Day71 frames the architecture
  and failure modes on top of the Day53 Provider boundary; Day72 makes the Provider itself replaceable.
- Day72 — Provider Capabilities and the Replaceable Provider Adapter.
  Scope: provider capability differences behind one stable, replaceable Provider Adapter contract.
  Connection: Day71 named the failure modes; Day72 hides provider differences behind a replaceable adapter
  (extending Day53); Day73 makes the prompt a versioned contract.
- Day73 — Prompt Contracts, Prompt Versioning and Compatibility.
  Scope: prompt-as-contract, versioning, and backward/forward compatibility.
  Connection: Day72 stabilized the provider surface; Day73 makes prompts versioned contracts; Day74 makes the
  model's output a validated structure.
- Day74 — Structured Output, JSON Schema and Function/Tool Calling.
  Scope: structured output, JSON Schema validation, function/tool-calling schemas. Runnable checkpoint: run the evolving Phase Artifact and save evidence (see Mandatory Runnable Checkpoint Cadence).
  Connection: Day73 versioned the input; Day74 constrains the output with schema and tool calls (reusing Day44
  Pydantic contracts); Day75 makes delivery efficient with streaming/caching/batching.
- Day75 — Streaming, Caching and Batching for LLM Applications.
  Scope: token/progress streaming, response caching, request batching.
  Connection: Day74 fixed output shape; Day75 adds streaming/caching/batching (extending Day54 streaming);
  Day76 chooses between models under latency/cost pressure.
- Day76 — Model Routing, Fallback, Latency and Cost Engineering.
  Scope: model routing, fallback policy, latency and cost engineering.
  Connection: Day75 optimized one path; Day76 routes across models with fallback and cost/latency budgets
  (reusing Day56 resilience); Day77 proves all of it with deterministic tests.
- Day77 — Fake Provider, Contract Tests and LLM Regression Tests.
  Scope: fake-Provider contract tests and LLM regression tests (deterministic, no real Provider calls).
  Connection: Day76 built routing/cost behavior; Day77 pins it with fake-Provider contract and regression
  tests (extending Day57); Day78 integrates the phase into an LLM Application Runtime.
- Day78 — LLM Application Runtime Capstone, Checkpoint and English Interview.
  Scope: integrate the LLM application runtime; runnable checkpoint; phase-level English interview.
  Connection: Day77 completed the tests; Day78 integrates the LLM Application Runtime as a runnable checkpoint
  and runs the phase interview; Phase 7B builds the agent runtime that drives this application.

Phase deliverable:

```text
A testable LLM Application Runtime: replaceable Provider Adapter + prompt contracts/versioning
+ structured output/function calling + streaming/caching/batching + model routing/fallback/cost
+ fake-Provider contract and regression tests.
```

Validation requirement:
Deterministic fake-Provider tests are `EXECUTED_LOCAL_RUNTIME`, not real Provider or `PRODUCTION` evidence. A
real or paid Provider call runs only with explicit user authorization, securely supplied credentials kept out
of the repo/logs/evidence pack, and a defined cost/scope; otherwise it stays `NOT RUN`. Claim
runtime/integration/production evidence only when actually executed and saved.

---

## Phase 7B — Agent Runtime and MCP Engineering (Day79–Day94)

Status:
Planned

Objective:
Build a framework-agnostic Agent Runtime — agent loop, tool registry/permissions, state machine, termination
and budgets, durable jobs with checkpoint/resume/recovery, human approval, memory vs business-state
boundaries, multi-agent coordination, and agent security — then run a Framework / Job-Market Refresh, choose
an Agent Runtime Framework, and implement it behind a replaceable adapter. Then engineer MCP client/server,
resource/tool/prompt boundaries, authentication/authorization/tenant isolation, and remote-MCP lifecycle.

```text
First understand and implement the stable Agent Runtime contracts.
Then choose a framework based on current ecosystem and job evidence.
The framework is replaceable infrastructure, not the business model.
```

Knowledge connection:

```text
LLM Application Runtime (Phase 7A)
    -> framework-agnostic Agent Runtime (loop, tools, state, durability, memory, security)
    -> Framework/Job-Market Refresh -> chosen framework behind a replaceable adapter
    -> MCP client/server + auth + tenant isolation + remote lifecycle
```

Reused project directory: `projects/ai-agent/` (agent runtime, tools, MCP).

Per-day topics (Topic + concise scope; each Status: Planned):

- Day79 — Framework-agnostic Agent Loop and Control Flow.
  Scope: a minimal, framework-agnostic agent loop and control flow.
  Connection: Phase 7A produced a reliable LLM application but no autonomous controller; Day79 builds the
  framework-agnostic loop; Day80 gives it a governed tool registry.
- Day80 — Tool Registry, Tool Schema and Permission Model.
  Scope: tool registry, tool schemas, and a permission model.
  Connection: Day79 had a loop but ungoverned tools; Day80 adds a permissioned tool registry (reusing the
  Day66 permissioned browser tool); Day81 bounds the loop with a state machine and budgets.
- Day81 — Agent State Machine, Termination, Loop Detection and Step/Token/Cost Budgets.
  Scope: agent state machine, termination, loop detection, step/token/cost budgets.
  Connection: Day80 governed tools; Day81 bounds the loop with termination/loop-detection and budgets; Day82
  makes agent jobs durable and recoverable.
- Day82 — Durable Agent Jobs, Checkpoint, Resume and Recovery.
  Scope: durable agent jobs, checkpoints, resume, recovery.
  Connection: Day81 bounded a single run; Day82 makes agent jobs durable with checkpoint/resume/recovery
  (reusing the Phase 4/5 job lifecycle); Day83 adds human interrupt/approval.
- Day83 — Human Approval, Interrupt and Escalation Boundaries.
  Scope: human approval, interrupt, escalation boundaries. Runnable checkpoint: run the evolving Phase Artifact and save evidence (see Mandatory Runnable Checkpoint Cadence).
  Connection: Day82 made runs durable; Day83 adds human approval/interrupt/escalation; Day84 separates memory
  from durable business truth.
- Day84 — Conversation Memory vs Durable Business-state Boundaries.
  Scope: conversation/durable memory vs business-state boundaries (durable truth stays in PostgreSQL).
  Connection: Day83 added human control; Day84 draws the memory-vs-business-state boundary; Day85 coordinates
  multiple agents.
- Day85 — Multi-agent Handoff and Coordination Boundaries.
  Scope: multi-agent handoff and coordination boundaries.
  Connection: Day84 bounded one agent's memory; Day85 adds multi-agent handoff/coordination; Day86 secures the
  whole agent surface.
- Day86 — Agent Security: Prompt Injection, Tool Abuse, Data Exfiltration and Sandboxing.
  Scope: prompt injection, tool abuse, data exfiltration, sandboxing.
  Connection: Day85 widened the surface; Day86 adds agent security defenses; Day87 refreshes framework and
  job-market evidence before any framework is chosen.
- Day87 — Agent Framework and Job-Market Refresh Checkpoint.
  Scope: refresh the current Agent framework ecosystem and real job-market requirements before committing.
  Connection: Days 79–86 defined stable contracts; Day87 refreshes ecosystem/job evidence so the choice is
  current, not pre-locked; Day88 selects a framework behind a replaceable adapter.
- Day88 — Agent Runtime Framework Selection Behind a Replaceable Adapter.
  Scope: choose an Agent Runtime Framework (candidates include LangGraph / OpenAI Agents SDK / PydanticAI) and
  implement it behind a replaceable adapter; record the choice as a new Decision. Runnable checkpoint: run the evolving Phase Artifact and save evidence (see Mandatory Runnable Checkpoint Cadence).
  Connection: Day87 refreshed the evidence; Day88 selects and adapter-wraps a framework without locking the
  contracts (recorded as a Decision); Day89 standardizes external tools/resources via MCP.
- Day89 — MCP Foundations and Protocol Model.
  Scope: MCP protocol model and responsibilities.
  Connection: Day88 fixed the runtime; Day89 introduces MCP as the standard tool/resource boundary; Day90
  builds the MCP client.
- Day90 — MCP Client Engineering.
  Scope: MCP client engineering and integration with the agent runtime.
  Connection: Day89 modeled the protocol; Day90 builds the MCP client; Day91 builds the MCP server side.
- Day91 — MCP Server Engineering: Resources, Tools and Prompts Responsibility Boundaries.
  Scope: MCP server; Resources/Tools/Prompts responsibility boundaries.
  Connection: Day90 built the client; Day91 builds the server with clear Resource/Tool/Prompt boundaries;
  Day92 secures it with auth and tenant isolation.
- Day92 — MCP Authentication, Authorization and Tenant Isolation.
  Scope: MCP authentication, authorization, tenant isolation.
  Connection: Day91 exposed server capabilities; Day92 adds MCP auth/authorization/tenant isolation (reusing
  Day51/Day52); Day93 hardens the remote lifecycle.
- Day93 — Remote MCP Lifecycle: Timeout, Retry, Versioning and Observability.
  Scope: remote MCP lifecycle — timeout, retry, versioning, observability.
  Connection: Day92 secured MCP; Day93 hardens the remote lifecycle (timeout/retry/versioning/observability);
  Day94 integrates agent + MCP into a capstone.
- Day94 — Agent + MCP Integration Capstone and English Interview.
  Scope: integrate the agent runtime with MCP client/server; runnable checkpoint; phase-level English
  interview.
  Connection: Day93 completed remote MCP; Day94 integrates agent + MCP into a runnable capstone and runs the
  phase interview; Phase 7C grounds the agent with a Production RAG subsystem.

Phase deliverable:

```text
A framework-agnostic Agent Runtime (loop, tools, state, budgets, durability, human approval, memory boundary,
multi-agent, security) + a chosen framework behind a replaceable adapter + MCP client/server with auth,
tenant isolation, and a hardened remote lifecycle.
```

Validation requirement:
Understand and implement the stable Agent Runtime contracts BEFORE choosing a framework; do not pre-lock
LangGraph or any single framework — the Day88 choice follows the Day87 refresh and lives behind a replaceable
adapter (recorded as a Decision). Avoid framework-API tutorialization; teach durable state, tool contracts,
permissions, termination/budgets, and security. Do not claim Agent/MCP are integration- or production-
validated without executed, saved evidence; an in-process fake/mock/double is never `INTEGRATION_RUNTIME`.

---

## Phase 7C — Production RAG Engineering (Day95–Day106)

Status:
Planned

Objective:
Build a runnable, evaluable Production RAG subsystem with permissions and citations — ingestion/parsing,
chunking experiments, metadata/tenant/ACL/provenance, embedding selection/versioning, vector index design,
hybrid retrieval/filtering, query rewriting/re-ranking, grounding/citations/source verification, retrieval and
answer evaluation, index update/delete/rebuild/migration, and RAG security — not a "chunk + vector search"
demo.

Knowledge connection:

```text
Agent Runtime + MCP (Phase 7B)
    -> Production RAG subsystem (ACL + provenance + hybrid retrieval + grounding + citations + evaluation)
    -> grounded, permission-filtered, evaluable knowledge for the agent
```

Reused project directory: `projects/ai-agent/` (RAG subsystem).

Per-day topics (Topic + concise scope; each Status: Planned):

- Day95 — RAG Ingestion Pipeline, Parsing and Document Lifecycle.
  Scope: ingestion pipeline, parsing, document lifecycle.
  Connection: Phase 7B gave the agent tools but no grounded knowledge; Day95 builds ingestion/parsing and the
  document lifecycle; Day96 experiments with chunking.
- Day96 — Chunking Strategy and Experiments.
  Scope: chunking strategies and measurable experiments.
  Connection: Day95 ingested documents; Day96 experiments with chunking strategies; Day97 attaches
  metadata/tenant/ACL/provenance.
- Day97 — Metadata, Tenant, ACL and Provenance.
  Scope: metadata, tenant scoping, ACL, provenance.
  Connection: Day96 produced chunks; Day97 adds metadata/tenant/ACL/provenance (reusing Day52 tenant
  boundaries); Day98 selects and versions embeddings.
- Day98 — Embedding Model Selection and Versioning.
  Scope: embedding model selection and versioning.
  Connection: Day97 scoped and labeled chunks; Day98 selects/version embeddings; Day99 designs the vector
  database and index.
- Day99 — Vector Database and Vector Index Design.
  Scope: vector database and index design. Runnable checkpoint: run the evolving Phase Artifact and save evidence (see Mandatory Runnable Checkpoint Cadence).
  Connection: Day98 produced embeddings; Day99 designs the vector store/index; Day100 adds hybrid retrieval
  and filtering.
- Day100 — Hybrid Retrieval and Filtering.
  Scope: hybrid (dense + lexical) retrieval and metadata/ACL filtering.
  Connection: Day99 built the index; Day100 adds hybrid retrieval with ACL filtering; Day101 improves ordering
  with query rewriting and re-ranking.
- Day101 — Query Rewriting and Re-ranking.
  Scope: query rewriting and re-ranking.
  Connection: Day100 retrieved candidates; Day101 rewrites queries and re-ranks; Day102 grounds answers with
  citations.
- Day102 — Grounding, Citations and Source Verification.
  Scope: grounding, citations, source verification.
  Connection: Day101 improved relevance; Day102 grounds answers with citations and source verification; Day103
  measures retrieval and answer quality.
- Day103 — Retrieval Evaluation and RAG Answer Evaluation.
  Scope: retrieval evaluation and RAG answer evaluation. Runnable checkpoint: run the evolving Phase Artifact and save evidence (see Mandatory Runnable Checkpoint Cadence).
  Connection: Day102 grounded answers; Day103 evaluates retrieval and answer quality; Day104 keeps the index
  correct over time.
- Day104 — Index Update, Delete, Rebuild and Migration.
  Scope: index update, delete, rebuild, migration.
  Connection: Day103 measured quality; Day104 adds index update/delete/rebuild/migration; Day105 defends RAG
  against injection and leakage.
- Day105 — RAG Security: Prompt Injection, Poisoned Documents and Data-leakage Boundaries.
  Scope: prompt injection via documents, poisoned documents, data-leakage boundaries.
  Connection: Day104 kept the index correct; Day105 adds RAG security boundaries; Day106 integrates the
  Production RAG subsystem.
- Day106 — Production RAG Capstone and English Interview.
  Scope: integrate the RAG subsystem; runnable checkpoint; phase-level English interview.
  Connection: Day105 secured RAG; Day106 integrates the Production RAG subsystem as a runnable checkpoint and
  runs the phase interview; Phase 7D makes evaluation, safety, and operations an engineering system.

Phase deliverable:

```text
A runnable, evaluable Production RAG subsystem: ingestion/parsing + chunking + metadata/tenant/ACL/provenance
+ embeddings/index + hybrid retrieval/filtering + query rewriting/re-ranking + grounding/citations
+ retrieval/answer evaluation + index migration + RAG security boundaries.
```

Validation requirement:
RAG must enforce tenant/ACL filtering and provenance; answers must be grounded with verifiable citations. A
RAG run over local/disposable infrastructure is `INTEGRATION_RUNTIME` only when real processes/stores
participate with saved, reproducible evidence; an in-process fake/mock is `EXECUTED_LOCAL_RUNTIME`. No
production claim without executed evidence.

---

## Phase 7D — AI Evaluation, Safety and Operations (Day107–Day116)

Status:
Planned

Objective:
Turn evaluation, safety, and operations into an executable engineering system: datasets/golden sets,
deterministic and model-based graders (and their limits), retrieval/answer/trajectory/tool-use evaluation,
adversarial and failure-mode evaluation, regression and release gates, AI observability with cost/latency/
quality trade-offs and model-routing evidence, load and security testing, and a production incident/rollback/
repair exercise.

Knowledge connection:

```text
LLM App + Agent + RAG capabilities
    -> executable Evaluation + Safety + Operations (graders, release gates, observability, incident drills)
    -> release decisions backed by runtime evidence
```

Reused project directory: `projects/ai-agent/` (evaluation, safety, operations).

Per-day topics (Topic + concise scope; each Status: Planned):

- Day107 — Evaluation Datasets and Golden Sets.
  Scope: evaluation datasets and golden sets.
  Connection: Phase 7C could answer but not prove quality at scale; Day107 builds datasets/golden sets; Day108
  scores them with deterministic graders.
- Day108 — Deterministic Graders.
  Scope: deterministic, reproducible graders.
  Connection: Day107 built datasets; Day108 adds deterministic graders; Day109 adds model-based graders and
  their limits.
- Day109 — Model-based Graders and Their Limits.
  Scope: model-based graders and their failure modes/limits.
  Connection: Day108 gave exact grading; Day109 adds model-based graders with explicit limits; Day110 applies
  grading to retrieval and answers.
- Day110 — Retrieval and Answer-quality Evaluation.
  Scope: retrieval-quality and answer-quality evaluation. Runnable checkpoint: run the evolving Phase Artifact and save evidence (see Mandatory Runnable Checkpoint Cadence).
  Connection: Day109 fixed grader trust; Day110 evaluates retrieval/answer quality (reusing Day103); Day111
  evaluates the agent's process.
- Day111 — Agent Trajectory and Tool-use Correctness Evaluation.
  Scope: agent trajectory evaluation and tool-use correctness.
  Connection: Day110 graded outputs; Day111 evaluates trajectory and tool-use correctness; Day112 probes
  adversarial and failure modes.
- Day112 — Adversarial and Failure-mode Evaluation.
  Scope: adversarial and failure-mode evaluation.
  Connection: Day111 graded normal behavior; Day112 adds adversarial/failure-mode evaluation; Day113 turns
  evaluations into regression and release gates.
- Day113 — Prompt/Model/Tool Regression and Release Gates.
  Scope: prompt/model/tool regression suites and release gates. Runnable checkpoint: run the evolving Phase Artifact and save evidence (see Mandatory Runnable Checkpoint Cadence).
  Connection: Day112 stressed the system; Day113 adds regression and release gates; Day114 makes cost/latency/
  quality observable in production.
- Day114 — AI Observability: Cost, Latency, Quality Trade-offs and Model-routing Evidence.
  Scope: AI observability, cost/latency/quality trade-offs, model-routing evidence.
  Connection: Day113 gated releases; Day114 adds AI observability and routing evidence (reusing the Day61
  telemetry pipeline); Day115 tests load and security.
- Day115 — Load Testing and AI Security Testing.
  Scope: load testing and AI security testing.
  Connection: Day114 gave live signals; Day115 adds load and AI security testing; Day116 rehearses production
  incidents and repair.
- Day116 — Production Incident, Rollback and Repair Exercise, Capstone and English Interview.
  Scope: production incident/rollback/repair exercise; runnable checkpoint; phase-level English interview.
  Connection: Day115 found limits; Day116 rehearses incident/rollback/repair and runs the phase interview;
  Phase 8 assembles everything into the Final Employment Capstone.

Phase deliverable:

```text
An executable AI Evaluation/Safety/Operations system: datasets/golden sets + deterministic and model-based
graders + retrieval/answer/trajectory/tool-use evaluation + adversarial/failure-mode evaluation
+ regression/release gates + AI observability (cost/latency/quality, routing evidence) + load/security testing
+ an incident/rollback/repair exercise.
```

Validation requirement:
Evaluation is an executable engineering system, not a concept overview; graders/gates must run and save
evidence. Distinguish `EXECUTED_LOCAL_RUNTIME` grader runs from real `INTEGRATION_RUNTIME`/`PRODUCTION`
evidence; `pytest passed` is not integration or production evidence. No production claim without executed,
saved evidence.

---

## Phase 8 — Final Employment Capstone (Day117–Day130)

Status:
Planned

Objective:
Assemble all capabilities into one deployable, demonstrable AI Backend and convert it into employment
evidence, then review readiness against the Employment Readiness Gate. The capstone is a thin vertical loop
integrating existing components — not a one-day re-implementation of everything.

Knowledge connection:

```text
LLM App + Agent + MCP + Production RAG + Evaluation/Safety/Ops + Phase 4/5/6 backend
    -> Final Employment Capstone (thin vertical loop, deployed, evaluated, observable)
    -> Portfolio + interviews + real job applications (Employment Readiness Gate)
```

Reused project directory: `projects/final-capstone/` (the final integrated project).

Per-day topics (Topic + concise scope; each Status: Planned):

- Day117 — Product Requirements, Architecture Review and Scope Control.
  Scope: product requirements, architecture review, scope control.
  Connection: builds on the Phase 7D capstone by defining final-capstone requirements, architecture, and
  scope; Day118 turns them into a skeleton, contracts, and threat model.
  Implementation boundary: see "Future Lesson Implementation Boundaries" (Day117) below.
- Day118 — Final Capstone Skeleton, Contracts and Threat Model.
  Scope: skeleton, contracts, threat model.
  Connection: Day117 set scope; Day118 adds the skeleton, contracts, and threat model; Day119 integrates the
  core backend stack.
- Day119 — FastAPI + PostgreSQL + Redis/Celery + Object Storage Integration.
  Scope: integrate the core backend stack.
  Connection: Day118 defined contracts; Day119 integrates the Phase 4/5 core backend stack; Day120 adds the
  agent runtime and MCP.
- Day120 — Agent Runtime and MCP Integration.
  Scope: integrate the agent runtime and MCP client/server. Runnable checkpoint: run the evolving Phase Artifact and save evidence (see Mandatory Runnable Checkpoint Cadence).
  Connection: Day119 gave the backend; Day120 integrates the Phase 7B agent runtime and MCP; Day121 grounds it
  with Production RAG.
- Day121 — Production RAG Integration (ACL, Citations, Retrieval Evaluation).
  Scope: integrate the Production RAG subsystem with ACL, citations, and retrieval evaluation.
  Connection: Day120 added the agent; Day121 integrates Phase 7C RAG with ACL/citations/evaluation; Day122
  adds the permissioned browser tool and human-approval workflow.
- Day122 — Playwright Permissioned Tool and n8n Human-approval Integration.
  Scope: integrate the Phase 5 permissioned browser tool and Phase 6 n8n human-approval workflow.
  Connection: Day121 grounded the agent; Day122 integrates the browser tool and n8n approval; Day123 runs one
  thin end-to-end vertical loop.
- Day123 — Thin Vertical Integration Loop (End-to-end).
  Scope: one bounded, complete vertical user path across all integrated components.
  Connection: Day122 wired the components; Day123 runs one thin end-to-end vertical loop with preserved
  correlation IDs; Day124 gates release on evaluation.
  Implementation boundary: see "Future Lesson Implementation Boundaries" (Day123) below.
- Day124 — Evaluation Gate and Release Decision Integration.
  Scope: integrate the Phase 7D evaluation gate into the release decision. Runnable checkpoint: run the evolving Phase Artifact and save evidence (see Mandatory Runnable Checkpoint Cadence).
  Connection: Day123 proved one path runs; Day124 integrates the evaluation gate into release decisions;
  Day125 proves resilience under drills.
- Day125 — Failure Recovery, Load, Security and Data-repair Drills.
  Scope: representative failure-recovery, load, security, and data-repair drills.
  Connection: Day124 gated releases; Day125 runs representative resilience drills; Day126 deploys to the cloud.
  Implementation boundary: see "Future Lesson Implementation Boundaries" (Day125) below.
- Day126 — Cloud Deployment, Managed Services, Production Configuration and SLOs.
  Scope: cloud deployment, managed services, production configuration, SLOs.
  Connection: Day125 proved resilience; Day126 deploys with production config and SLOs; Day127 adds
  observability and the operational runbook.
- Day127 — Observability, Operational Runbook and Cost/Quality Evidence.
  Scope: observability, operational runbook, cost/quality evidence. Runnable checkpoint: run the evolving Phase Artifact and save evidence (see Mandatory Runnable Checkpoint Cadence).
  Connection: Day126 deployed the system; Day127 adds observability, a runbook, and cost/quality evidence;
  Day128 practices system-design and coding interviews on it.
- Day128 — AI Backend System Design and Python/SQL Coding Interview.
  Scope: AI backend system-design + Python/SQL coding interview practice.
  Connection: Day127 finished operations; Day128 turns the system into system-design and Python/SQL interview
  practice; Day129 builds the English story, behavioral answers, and resume.
- Day129 — English Project Story, Behavioral Interview, Resume and Open-source Evidence.
  Scope: project story, behavioral interview, resume, open-source evidence.
  Connection: Day128 built interview skills; Day129 builds the English story, behavioral answers, resume, and
  open-source evidence; Day130 reviews overall employment readiness.
- Day130 — Final Mock Interview, Portfolio Review and Employment Readiness Gate Review.
  Scope: final mock interview, portfolio review, and an Employment Readiness Gate review.
  Connection: consolidates everything into a final mock interview, portfolio review, and an Employment
  Readiness Gate review; if the Gate is not yet met, additional Planned lessons are added rather than declaring
  completion at a fixed day. (Note: real trial job applications may begin earlier — see the Employment
  Readiness Gate — once the Agent + MCP evidence in Phase 7B is complete.)

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
system-design/behavioral/resume readiness, reviewed against the Employment Readiness Gate for
Junior/Developing AI Backend Engineer, AI Startup Backend Engineer, and LLM/RAG/Agent-product Backend roles.
```

Validation requirement:
Portfolio and capstone completion require real, saved evidence (runnable code, tests, evaluation report,
failure/recovery drills, deployment and observability evidence). No production-grade claim without executed
evidence. Reaching Day130 does not by itself mean "complete" — completion is passing the Employment Readiness
Gate.

---

## Employment Readiness Gate

Completion of the AI Backend Employment Track is defined by passing this Gate, NOT by reaching a fixed final
day. At minimum the Gate requires:

```text
1.  A real, runnable, deployable AI Backend.
2.  Real FastAPI / PostgreSQL / Redis-Celery / Object Storage integration evidence.
3.  An Agent Runtime with explicit state, termination, permission, checkpoint and recovery semantics.
4.  A run MCP Client/Server integration.
5.  A Production RAG with ACL, citations and retrieval evaluation.
6.  Tool permissions and prompt-injection defenses.
7.  Evaluation datasets, graders and a release gate.
8.  AI latency / cost / quality evidence.
9.  Observability, failure, rollback and repair evidence.
10. A reproducible README and run commands.
11. Python and SQL interview capability.
12. Backend / AI system-design capability.
13. English project explanation and behavioral interview stories.
14. Portfolio and resume evidence.
15. Real job applications submitted, with Planned lessons added based on feedback.
```

Trial application checkpoint: once the Agent + MCP evidence in Phase 7B is complete (the first sufficiently
complete project evidence), the learner MAY begin trial job applications — they need not wait for the Final
Capstone to touch the market. Feedback then feeds back into Planned lessons.

Honesty boundary: the curriculum improves job competitiveness but does not promise an offer; target roles are
Junior / Developing AI Backend Engineer, AI Startup Backend Engineer, and Backend Engineer on LLM/RAG/Agent
products; completing the curriculum is not fabricated as Senior/Staff production experience.

---

## Employment-Readiness Boundary (Day43 onward, competency-gated)

This curriculum builds the core capabilities and portfolio evidence of an AI Backend Engineer, but it does
not guarantee a job, and this training is not equivalent to years of production experience.

Target roles:

```text
Junior / Developing AI Backend Engineer
AI Startup Backend Engineer
Backend Engineer working on LLM / RAG / Agent products
```

Completing the curriculum does not by itself demonstrate Senior or Staff level.

## Cross-cutting Employment Training (Day43 onward)

Phases 4–8 carry a continuous employment-readiness thread (integrated, not mechanical per-day inflation):
Python coding practice, SQL practice, English technical explanation, system-design communication, runtime
validation evidence, a weekly project README update, and a weekly interview review. A typical week includes
at least 2–3 Python/SQL coding exercises, one English project explanation, one production failure scenario,
and one artifact/runtime-evidence review. The goal is accumulated capability evidence, not a "problem-count
guarantees an offer" model.

---

## Cross-cutting Engineering Discipline (Day43 onward)

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

## Future Lesson Implementation Boundaries (Day50, Day54, Day117, Day123, Day125)

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

### Day123 — a thin end-to-end vertical integration loop

Day123 is an **integration day** for components already built in Phases 5–7D, not a development day that
re-implements Agent, RAG, MCP, Playwright, or n8n.

Day123 integrates and validates one bounded but complete vertical user path, e.g.:

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
chase five disconnected demos, and do not re-implement previously completed components in Day123. Day123 Topic
is unchanged.

### Day125 — representative drills, not exhaustive failure enumeration

Day125 still covers `failure recovery`, `load`, `security`, and `data repair`, but with a **limited,
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

A limited scope must not be described as "comprehensive production validation." Day125 Topic is unchanged.

### Day117 — when the Final Capstone README is updated

`projects/final-capstone/README.md` may remain an early placeholder until Day117. It must **not** be rewritten
into a fictional completed capstone before then.

```text
When Day117 confirms the formal Product Requirements, Architecture, and Scope,
it must simultaneously update projects/final-capstone/README.md so the README becomes the entry point to the
final Capstone's real scope, run instructions, validation evidence, and limitations.
```

Before Day117, that README is a placeholder and must not be treated as the latest complete implementation
evidence. Day117 Topic is unchanged.

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
