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
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day47-async-sessions-transactions-repository-and-unit-of-work.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day47-async-persistence-boundary-design.md` with runnable `day47_async_uow.py` + `test_day47_async_uow.py` (process-scoped AsyncEngine/async_sessionmaker helpers, a request/Job-scoped AsyncSession, repositories that never commit, a UnitOfWork with explicit commit/rollback/close, the guarded `UPDATE ... WHERE job_status='queued' RETURNING` claim with zero-row stale/no-op, flush-before-dependent-write, a second guarded completion UoW, correlation-key-before-the-Provider-call recovery, and the integrated success/crash recovery drill; reuses the Day46 mapping, no schema redefinition, no global Session, no repo-owned commit, no Provider call inside a DB transaction). REAL fake-session control-flow tests executed (Python 3.10.12, SQLAlchemy 2.0.29, greenlet 3.5.4, pytest 7.4.3 -> 23 passed). PostgreSQL runtime NOT RUN (no server/driver; a mock is not database proof; SQLite is not PostgreSQL evidence). Alembic (Day48), the upload workflow (Day49), idempotent acceptance/Outbox (Day50), real Provider SDK (Day53), and FastAPI/Worker integration/production are not taught here.
- Day48 — Alembic and Safe AI Backend Schema Evolution.
  Scope: Alembic migrations enforcing the Day36 Expand/Backfill/Validate/Switch/Contract discipline.
  Connection: brings the Day36 safe-migration discipline to the Day46/47 SQLAlchemy schema via Alembic; Day49 adds the upload and Object-Storage boundary on top.
  Status: ✅ Completed. Released Lesson: `docs/fastapi/day48-alembic-and-safe-ai-backend-schema-evolution.md`; Engineering Artifact: `projects/ai-backend-data-layer/api/day48-alembic-safe-schema-evolution-design.md` with a runnable Alembic control plane `day48_alembic/` (minimal `env.py` + gated Expand/Validate/Contract revisions for the Lease evolution of `app.jobs`), an operational restartable `FOR UPDATE SKIP LOCKED` backfill `day48_lease_backfill.py` (kept off the migration), and `test_day48_alembic.py` (a SPLIT linear chain (pure Expand columns `0002` = old/new compatibility window; a SEPARATE constraint revision `0003` adds the triple-coherence + Day36 core `jobs_running_requires_lease` `NOT VALID` only after old Writers are drained/isolated, since `NOT VALID` enforces every future write by any Writer version; `0004` validates; `0005` contracts); the backfill routes unknown-ownership Jobs into an independent queue table `app.job_lease_reconciliation` (`INSERT ... ON CONFLICT DO NOTHING`, no `app.jobs` write, no fabrication; created additively in Expand) so the automatic loop terminates (excluded via `NOT EXISTS`) and is restart-safe — routing writes only the queue so it is legal after the strict constraint (a marker UPDATE that left the row running+NULL-Lease would be rejected) — but queuing is triage not resolution — such a row still violates `jobs_running_requires_lease` and still counts in `unresolved_running_without_lease` (the hard VALIDATE precondition, reached only by a trusted Lease backfill or an audited real recovery routed by `classify_unknown_running_recovery` — verified `succeeded` to the Day47 completion UoW, `failed`/`cancelled` to guarded terminal-recovery, unknown kept as reconciliation, a `queued` requeue or bare status flip refused); `env.py` resolves the DB URL by `-x db_url` > env `DAY48_ALEMBIC_DATABASE_URL` with the ini placeholder offline-render only (online fails fast); separate `VALIDATE CONSTRAINT` of both constraints; destructive gated Contract; single-head linear revision graph; minimal control-plane `env.py`; no long loop in any `upgrade()`; classify/backfill/reconcile without fabrication; forward-fix vs downgrade; baseline/`stamp`; autogenerate review; `CREATE INDEX CONCURRENTLY` non-transactional). REAL static/offline evidence executed (Alembic revision-graph + migration-source inspection and fake-session backfill control flow -> 24 passed; Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3) plus an offline `alembic upgrade --sql` DDL render. PostgreSQL runtime NOT RUN (no server; SQLite/fake/`upgrade`-success are not PostgreSQL proof; a real `NOT VALID`/`VALIDATE`/backfill test would apply the Day42 raw SQL and prove behavior). The Day49 upload workflow, Day50 Outbox/Celery delivery, Day53 Provider SDK, Day55 worker runtime, FastAPI/Worker integration, and production migration are not implemented here.
- Day49 — Upload Sessions, Object Storage and Artifact Verification.
  Scope: presigned upload sessions, Object Storage boundary, deterministic artifact reference/verification.
  Connection: adds presigned uploads and Object-Storage artifact verification to the persisted model; Day50 makes Job acceptance idempotent with the Outbox.
- Day50 — Idempotent AI Job API and Transactional Outbox Integration.
  Scope: the client-idempotency-key + `(tenant_id, idempotency_key)` boundary and the Outbox dispatch intent end to end.
  Connection: makes Job acceptance idempotent (client key + PostgreSQL uniqueness) and wires the Outbox dispatch intent; Day51 secures who may call it.
  Implementation boundary: see "Future Lesson Implementation Boundaries" (Day50) below.
- Day51 — Authentication, Password Security and JWT.
  Scope: password hashing, JWT issuance/verification, session/token boundaries.
  Connection: adds authentication (passwords + JWT) to the Day43-50 API; Day52 turns identity into tenant isolation and authorization.
- Day52 — Authorization, Tenant Isolation, Quotas and API Security.
  Scope: tenant isolation, per-tenant quotas/rate limits, authorization and API security boundaries.
  Connection: enforces tenant isolation, quotas, and authorization over the authenticated API; Day53 connects the real AI provider behind that boundary.
- Day53 — OpenAI SDK, Provider Boundaries and Structured Output.
  Scope: OpenAI-compatible SDK usage, provider boundary, structured-output parsing and validation.
  Connection: introduces the OpenAI-compatible provider and structured output behind the Day45 adapter seam; Day54 handles its streaming and cancellation.
- Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation.
  Scope: streaming responses, disconnect/timeout handling, cooperative cancellation.
  Connection: adds streaming, disconnects, timeouts, and cancellation to the provider calls; Day55 moves long-running Provider work to background workers.
  Implementation boundary: see "Future Lesson Implementation Boundaries" (Day54) below.
- Day55 — Celery, Worker Execution and Long-running AI Jobs.
  Scope: reuses the Day40 delivery-semantics mental model (at-least-once delivery, redelivery, ACK timing, idempotency, poison-message handling) while running long-running Provider work on a SUPPORTED Celery broker transport. Do not equate Celery's broker implementation with the Day40 custom Redis Streams / Consumer Group design, and do not hand-build a Celery replacement.
  Connection: moves long-running Provider jobs to Celery workers, reusing the Day40 delivery-semantics mental model on a supported Celery broker (not the custom Streams design); Day56 hardens provider resilience and cost.
- Day56 — Provider Resilience, Rate Limits, Token Cost and Backpressure.
  Scope: retries/backoff, provider rate limits, token-cost control, backpressure and degradation.
  Connection: adds retries/backoff, provider rate limits, token-cost control, and backpressure to the worker path; Day57 verifies all of it with tests and failure injection.
- Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection.
  Scope: fake/deterministic providers, contract tests, failure injection, runtime evidence.
  Connection: advances the Day43-baseline test suite into fake-provider, contract, integration, and failure-injection tests with recovery verification; Day58 integrates and verifies observability to close the phase.
- Day58 — Production AI API Capstone, Observability and English Interview.
  Scope: integrate the phase into a runnable API with observability; phase-level English interview.
  Connection: integrates and verifies observability (structured logs, job_id/trace_id/attempt_id correlation, metrics, traces, runtime evidence) into the runnable API and runs the phase English interview; Phase 5 (Day59) makes this backend a callable browser-automation capability.

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
