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
Planned / Ready (not started)

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
Planned

Previous Lesson:
Day28 — AI Backend Production Architecture

Next Lesson:
Day30 — SQL Data Manipulation and Query Fundamentals

Planned Engineering Artifact:
Begin `projects/ai-backend-data-layer/` (only after the live lesson) with the first minimal raw SQL Job
schema and a README stating ownership/validation boundaries; execute in a disposable PostgreSQL only if
actually available, otherwise report static/conceptual validation only.

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
Planned

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
Planned

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
Planned

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
Planned

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
Planned

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
Planned

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
Planned

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
