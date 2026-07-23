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
In Progress

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
Planned

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
Planned

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
Planned

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
Planned

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
Planned

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
Planned

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
