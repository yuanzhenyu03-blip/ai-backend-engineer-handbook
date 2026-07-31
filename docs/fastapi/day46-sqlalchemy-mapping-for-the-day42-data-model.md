# Lesson 46 — SQLAlchemy 2.0 Mapping for the Day42 Data Model

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 6-7 hours

Prerequisite: Day45 — Dependency Injection, Lifespan, Configuration and AI Provider Adapters

Previous Lesson: [Day45 — Dependency Injection, Lifespan, Configuration and AI Provider Adapters](day45-dependency-injection-lifespan-configuration-and-ai-provider-adapters.md)

Next Lesson: [Day47 — Async Sessions, Transactions, Repository and Unit of Work](day47-async-sessions-transactions-repository-and-unit-of-work.md)

Phase: Phase 4 — Production AI API Engineering

Engineering Artifact: The Day46 SQLAlchemy mapping design ([`projects/ai-backend-data-layer/api/day46-sqlalchemy-mapping-for-the-day42-data-model-design.md`](../../projects/ai-backend-data-layer/api/day46-sqlalchemy-mapping-for-the-day42-data-model-design.md)) with runnable code [`day46_orm_mapping.py`](../../projects/ai-backend-data-layer/api/day46_orm_mapping.py) and static metadata tests [`test_day46_orm_mapping.py`](../../projects/ai-backend-data-layer/api/test_day46_orm_mapping.py) — a faithful SQLAlchemy 2.0 typed declarative mapping of the Day42 `app`-schema durable contract (Job/JobAttempt/JobEvent/OutboxEvent/UploadSession/ResultArtifact + a minimal Tenant stub), preserving server defaults, named UNIQUE/CHECK/FK constraints, ON DELETE RESTRICT, TEXT+CHECK status, and the same-Job composite provenance FK. Static metadata contract tests were executed (20 passed; Python 3.10.12, SQLAlchemy 2.0.29, pytest 7.4.3); PostgreSQL runtime, sessions/transactions, migrations, and integration are NOT RUN — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

FastAPI Cheat Sheet: [cheat_sheets/fastapi.md](../../cheat_sheets/fastapi.md)

FastAPI Interview: [interview/fastapi.md](../../interview/fastapi.md)

Estimated Study Time:

```text
Reading: 130-160 minutes
Exercises + running the tests: 90-120 minutes
Hands-on mapping design: 80-110 minutes
Review: 30-45 minutes

Total: 6-7 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Explain why the Day46 ORM is an executable REPRESENTATION of the existing PostgreSQL contract, not a new schema authority.
2. Map existing columns, server-generated values, nullable lifecycle state, and named constraints with SQLAlchemy 2.0 `Mapped[...] = mapped_column(...)`.
3. Preserve `UNIQUE (tenant_id, idempotency_key)` and other named UNIQUE/CHECK/FK constraints exactly, without redesigning them.
4. Explain why a nullable column and Optional typing do not replace a PostgreSQL CHECK, and keep TEXT + CHECK status instead of a native enum.
5. Encode JobAttempt Job-scoped retry uniqueness and the JobEvent composite same-Job provenance FK, and explain a NULL-attempt Job-level Event.
6. Reject destructive cascade semantics (keep ON DELETE RESTRICT) for durable audit/recovery facts, and use `relationship()` for navigation only.
7. Keep Pydantic public models and ORM persistence models separate, and explain why neither Pydantic nor the ORM classes prove PostgreSQL constraint behavior.
8. Classify Outbox durable-dispatch authority and its nullable published checkpoint; derive ResultArtifact ownership through the Attempt; bound UploadSession storage to references.
9. Distinguish static metadata evidence from real PostgreSQL runtime evidence, and explain why `create_all()` success is not schema-compatibility proof.
10. Keep Engine/Session out of Day46 (one Engine per process and one session per request/Job are Day47), and state the Tenant/Document scope limitation honestly.
11. Diagnose a wrong-schema deployment and produce a contain / preserve / classify / reconcile / verify recovery path where code rollback is not durable-data rollback.

---

# Why This Matters

Day45 wired the Day44 contracts through a composition boundary, but its completion target was an in-memory list —
it deliberately never touched PostgreSQL. Day46 is where the durable Day42 model becomes an **executable ORM
mapping** your application code can use. The central risk this lesson removes is the tempting belief that
**writing ORM classes redefines the schema**. It does not. The Day42 raw SQL — the `app` schema, its server
defaults, its named `UNIQUE`/`CHECK`/`FOREIGN KEY` constraints, `ON DELETE RESTRICT`, tenant-scoped uniqueness,
and same-Job composite provenance — **is** the durable authority. Day46 must mirror those facts faithfully; a
"cleanup" that silently swaps a `TEXT + CHECK` status for a native enum, or adds `cascade="all, delete-orphan"`,
or drops a tenant column as "derivable," is not a mapping — it is an unreviewed schema change that corrupts
integrity, retention, and audit.

The scenario stays concrete and multi-tenant: Jobs owned by a tenant, retried through Attempts, tracked by
append-only Events, dispatched through a PostgreSQL Outbox, producing Object-Storage-referenced Artifacts. Each
of those carries a Day42 rule that must survive the mapping — `UNIQUE (tenant_id, idempotency_key)` so one
client request per tenant creates one Job; `UNIQUE (job_id, attempt_number)` so retry ordinals are Job-scoped;
a composite FK so a non-NULL Attempt provenance belongs to the same Job; `ON DELETE RESTRICT` so incident
evidence is never erased by object-graph cleanup. And the lesson's incident is exactly what happens when the
mapping is unfaithful: a release that **omitted the `app` schema** wrote three accepted Jobs to `public.jobs`,
and the recovery is audited reconciliation — because code rollback is not durable-data rollback.

This lesson has **real static evidence**: **20 metadata-contract tests passed** (Python 3.10.12, SQLAlchemy
2.0.29, pytest 7.4.3) asserting the declared mapping structure against the Day42 facts. But **no PostgreSQL
runtime** was executed — static metadata proves the mapping's declared shape, not that it behaves correctly
against the real database. Sessions/transactions (Day47), Alembic (Day48), and integration/production are all
**NOT RUN**.

---

# Roadmap Position

```text
Day42 raw PostgreSQL durable ownership + failure contract
Day43 HTTP product contract
Day44 Pydantic v2 boundary contracts
Day45 composition / lifespan / provider seam
Day46 SQLAlchemy 2.0 faithful persistence mapping   <-- you are here
Day47 AsyncSession, transactions, Repository and Unit of Work
Day48 Alembic safe schema evolution
```

Knowledge continuity:

```text
Previous knowledge
  Day42 durable schema (app-schema tables, server defaults, named UNIQUE/CHECK/FK, RESTRICT, scoped uniqueness,
  composite provenance); Day44 public Pydantic contracts; Day45 process- vs request-scope boundary
        |
        v
Current lesson
  represent the Day42 contract as SQLAlchemy 2.0 typed declarative models WITHOUT changing ownership, integrity,
  retention, public boundaries, or schema authority; static metadata tests prove the declared structure
        |
        v
Future production usage
  Day47 drives these mappings with an app/process-scoped Engine and a request/Job-scoped AsyncSession +
  transactions + repository/UoW; Day48 evolves the mapped schema with Alembic (Expand -> Backfill -> Validate ->
  Switch -> Contract); Day50 uses the mapped Job/Outbox boundary for idempotent Job acceptance; Day55 adds a
  Celery Worker/broker delivery chain without changing the Outbox's PostgreSQL authority
```

Day46 does **not** implement Day47 sessions/transactions/repository/UoW, Day48 Alembic migrations, Day50 Outbox
acceptance, Day55 Celery, native-enum changes, or any public API endpoint. They are named only as future
connections.

---

# Lesson Map

```text
1.  ORM = mapping, not new authority     -> PostgreSQL stays durable authority; Day46 maps it faithfully
2.  Preserve idempotency uniqueness        -> keep UNIQUE(tenant_id, idempotency_key); defer Day50 behavior
3.  Server-generated values                -> gen_random_uuid()/now()/defaults are SERVER-side, not app-side
4.  Typed declarative mapping              -> Mapped[T] = mapped_column(...); a plain annotation is not mapping
5.  Nullable column vs CHECK invariant     -> Mapped[datetime | None] != the succeeded-implies-finished_at CHECK
6.  TEXT + CHECK, not native enum          -> an enum change is Day48 schema evolution
7.  Attempt Job-scoped uniqueness          -> UNIQUE(job_id, attempt_number), not tenant-scoped, not global
8.  JobEvent composite provenance          -> (job_id, attempt_id) FK; NULL attempt = Job-level event
9.  RESTRICT, not cascade                   -> audit/recovery facts survive; relationship() is navigation only
10. Pydantic API vs ORM persistence         -> separate models; neither proves PostgreSQL constraints
11. Outbox authority + Artifact/Upload      -> published_at NULL != never sent; ownership via Attempt; refs not bytes
12. Static vs real PostgreSQL evidence      -> create_all() success is not schema compatibility
13. Engine/Session scope + wrong-schema     -> no global session (Day47); contain/preserve/reconcile the incident
```

---

# Core Mental Model

```text
ORM mapping REPRESENTS the database contract; it does not silently REPLACE it.

  PostgreSQL (Day42 raw SQL)         = durable authority (PK/UNIQUE/CHECK/FK/RESTRICT enforce integrity)
  SQLAlchemy 2.0 declarative models  = faithful executable REPRESENTATION (Mapped[T] = mapped_column(...))
  Base.metadata schema="app"          = exact existing table identity (no search_path dependence)
  server_default=text(...)            = database-GENERATED values (gen_random_uuid()/now()/defaults)
  TEXT + named CHECK                   = legal states (NOT a native enum — that is Day48)
  UNIQUE(tenant_id, idempotency_key)   = one client request per tenant = one Job
  UNIQUE(job_id, attempt_number)       = retry ordinal scoped to the JOB
  FK (job_id, attempt_id) composite    = same-Job Attempt provenance (NULL attempt_id = Job-level event)
  ON DELETE RESTRICT + relationship()  = retention protected; relationship() is NAVIGATION, not integrity
  Pydantic public model != ORM model   = separate; ORM/Pydantic classes do NOT prove PostgreSQL behavior
  static metadata != PostgreSQL runtime = declared shape proven; DB behavior NOT proven (create_all() != compat)

Day46 MAPS it  ->  Day47 DRIVES it (sessions/tx/repo/UoW)  ->  Day48 EVOLVES it (Alembic).
```

---

# Main Concepts

## Concept 1: ORM mapping is not a new schema authority

### Tech Lead Question

You are adding SQLAlchemy models over the existing Day42 PostgreSQL schema. Should the ORM become the new
schema authority?

### Student Thinking

The student's first instinct was that defining ORM classes establishes a new source of truth for the schema.

### Student Answer

> "应该成为一套新的 schema authority"

### Tech Lead Review

This is the key correction of the day. In this **existing** system the ORM is an **executable representation**
of the durable PostgreSQL contract — **not** a new authority. PostgreSQL still owns durable truth; its
constraints still enforce integrity on every write path. Day46 maps existing columns, server generation,
nullable lifecycle state, constraints, foreign keys, relationship cardinality, provenance, and retention rules
— it does **not** redesign them. A deliberate schema change (say, a native enum) is **migration/compatibility
work owned by Day48**, not something an ORM class silently imposes. The durable line: **ORM mapping represents
the database contract; it does not silently replace it. PostgreSQL is durable authority; Day46 maps it
faithfully; Day47 drives it transactionally; Day48 evolves it safely.**

### Engineering Thinking

When a schema already exists and holds real rows, "the code defines the schema" is how you get silent drift and
corrupted data. The mapping's job is fidelity; change goes through a reviewed migration.

### Production Example

A team regenerates models from an ORM and "helpfully" renames a column and swaps a CHECK for an enum; the next
deploy's `create_all()` on a fresh test DB looks fine, but against production the mapping no longer matches the
real table. Faithful mapping + Day48 migrations prevent this.

### Framework Connection

SQLAlchemy 2.0 `DeclarativeBase` with `MetaData(schema="app")`; the Day42 raw SQL remains the source of truth.

## Concept 2: Preserve tenant-scoped idempotency uniqueness

### Tech Lead Question

The Job carries `UNIQUE (tenant_id, idempotency_key)`. Do you keep it as-is now, or fold in the Day50 acceptance
workflow while you are here?

### Student Answer

> (multiple-choice) "B" — preserve `UNIQUE (tenant_id, idempotency_key)` while deferring the Day50 workflow.

### Tech Lead Review

Correct. The mapping **preserves** the business key exactly — one client request per tenant creates only one
Job, a retry produces a new `job_id`, and different tenants may reuse the same key. The **idempotent acceptance
behavior** that uses this constraint is Day50; Day46 only maps the constraint faithfully (named
`jobs_tenant_idempotency_unique`). Mapping a constraint is not the same as implementing the workflow that relies
on it.

### Engineering Thinking

Keep the durable invariant intact and resist scope creep; the behavior that leans on it arrives in its own
lesson, tested in its own right.

### Production Example

The mapped `UNIQUE (tenant_id, idempotency_key)` is what later lets Day50 do atomic create-or-return instead of
a race-prone SELECT-then-INSERT.

### Framework Connection

`UniqueConstraint("tenant_id", "idempotency_key", name="jobs_tenant_idempotency_unique")` in `__table_args__`.

## Concept 3: Database-generated values are server-side defaults

### Tech Lead Question

`job_id` is a UUID and `created_at` is a timestamp, both generated by the database. Where does that generation
live in the mapping?

### Student Answer

> "database server_default / database generation"

### Tech Lead Review

Correct. These are **server-side** defaults, mapped with `server_default=text("gen_random_uuid()")` and
`server_default=text("now()")` — the **database** generates them, not Python. The same holds for
`server_default=text("'queued'")`, `text("0")`, `text("false")`, and `text("'{}'::jsonb")`. Using a Python-side
`default=` would move generation into the application and diverge from the Day42 fact that the database owns it.

### Engineering Thinking

Where a value is generated is part of the contract. Server defaults keep generation authoritative and identical
across every writer, including non-ORM ones.

### Production Example

A second service inserts a Job with raw SQL and still gets a server-generated `job_id`/`created_at`; if the
default lived only in Python, that writer would break the invariant.

### Framework Connection

`mapped_column(..., server_default=text("gen_random_uuid()"))`; contrast with a Python `default=`.

## Concept 4: Typed declarative mapping

### Tech Lead Question

In SQLAlchemy 2.0, how do you declare an ORM-managed typed column?

### Student Answer

> "Mapped[...] = mapped_column(...)"

### Tech Lead Review

Exactly. `Mapped[T]` marks an **ORM-managed typed attribute** and `mapped_column(...)` supplies the column
metadata (type, nullability, defaults, constraints). A plain annotation without `mapped_column` is **not** the
same mapping. Types mirror Day42 precisely: `UUID(as_uuid=True)`, `Text`, `Integer`, `BigInteger`, `Boolean`,
`TIMESTAMP(timezone=True)`, and `JSONB`.

### Engineering Thinking

The typed declarative form gives static typing and one explicit place for each column's database facts, which is
exactly what a faithful mapping needs.

### Production Example

`job_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'queued'"))` — the type,
nullability, and server default are all visible and checked.

### Framework Connection

SQLAlchemy 2.0 `Mapped`, `mapped_column`; the PostgreSQL dialect `UUID`/`JSONB`.

## Concept 5: A nullable column is not a conditional CHECK

### Tech Lead Question

`finished_at` is nullable. If you map it `Mapped[datetime | None]`, does that enforce "a succeeded Job must have
a finish time"? And how would you TEST the CHECK?

### Student Thinking

The student mapped the nullable timestamp correctly but initially expected a constraint violation to show up as
an empty query result.

### Student Answer

> (nullable timestamp) "Mapped[datetime | None]"

> (how the CHECK behaves in a test) "finished_at is null,返回为空"

### Tech Lead Review

The mapping is right — `Mapped[datetime | None]` with `nullable=True` — but the CHECK expectation needs
correcting. Optional Python typing and a nullable column describe that the column **may** be NULL; they do
**not** enforce the conditional rule. The Day42 CHECK `jobs_succeeded_has_finished_at`
(`job_status <> 'succeeded' OR finished_at IS NOT NULL`) is what enforces it on every write path, and it stays
in the mapping. And a negative constraint test expects a **rejected write** — a PostgreSQL **CHECK violation /
SQLAlchemy `IntegrityError`** — **not** an empty query result. "Returns empty" is a query outcome; a violated
CHECK is a refused INSERT/UPDATE.

### Engineering Thinking

Nullability and business invariants are different layers. The column says "NULL is structurally allowed"; the
CHECK says "this specific combination is illegal." Only the CHECK refuses the bad write.

### Production Example

Marking a Job `succeeded` with `finished_at = NULL` raises a CHECK violation at write time — so a partial
success can never be committed as a finished one.

### Framework Connection

`CheckConstraint("job_status <> 'succeeded' OR finished_at IS NOT NULL", name="jobs_succeeded_has_finished_at")`;
a real runtime test would assert an `IntegrityError` (NOT RUN here — see the validation matrix).

## Concept 6: TEXT + CHECK, not a native enum

### Tech Lead Question

`job_status` is `TEXT` with a CHECK. Map it as-is, or "improve" it to a native PostgreSQL enum?

### Student Answer

> "把它映射为 String/Text + 原有 CHECK，应该直接映射数据库事实"

### Tech Lead Review

Correct — map the **database fact**: `Text` plus the existing named `CHECK` (`jobs_status_allowed`). Replacing
`TEXT + CHECK` with a native database enum would be **schema evolution**, which belongs to **Day48**, not a
Day46 mapping. Faithful mapping means the ORM's declared storage matches the real column type and constraint,
not a "nicer" alternative.

### Engineering Thinking

An enum migration changes on-disk representation and rollout risk; sneaking it into a mapping bypasses the
compatibility discipline that a schema change requires.

### Production Example

A "clean up the enum" ORM edit would generate a different DDL than the live table; keeping `TEXT + CHECK` keeps
the mapping and the database identical until Day48 chooses to evolve it.

### Framework Connection

`mapped_column(Text, ...)` + `CheckConstraint(... , name="jobs_status_allowed")`; deliberately **not**
`mapped_column(Enum(...))`.

## Concept 7: JobAttempt identity is Job-scoped, not tenant-scoped

### Tech Lead Question

What makes an Attempt unique? A student proposed `UNIQUE(tenant_id, attempt_id)`. Also: may Job B have its own
Attempt number 1 when Job A already has one?

### Student Thinking

The student first scoped Attempt uniqueness by tenant, then reasoned correctly that a different Job may reuse an
ordinal.

### Student Answer

> (Attempt scope, incorrect) "uniquee(tenant_id,attemp_id)"

> (different-Job retry, correct) "应该运行，因为属于不同job"

### Tech Lead Review

The scope correction: `attempt_id` is **globally** primary-key unique, but the **business** uniqueness is
`UNIQUE(job_id, attempt_number)` — the retry ordinal is unique **within one Job**, not tenant-scoped and not
global. So "应该运行，因为属于不同 job" is exactly right: Job B may have its own Attempt 1, because the scope is the
Job. A global `UNIQUE(attempt_number)` would wrongly stop Job B from having Attempt 1; a tenant scope is simply
the wrong axis. There is also a second candidate key, `UNIQUE(job_id, attempt_id)`, which exists so JobEvent can
prove same-Job provenance (Concept 8).

### Engineering Thinking

Uniqueness must be scoped to the entity the rule is about. Retry ordinals belong to a Job's own timeline;
scoping them by tenant or globally breaks legitimate retries across Jobs.

### Production Example

Two Jobs each retry once; both correctly hold `attempt_number = 1` because the unique scope is `(job_id,
attempt_number)`.

### Framework Connection

`UniqueConstraint("job_id", "attempt_number", name="job_attempts_job_number_unique")` and
`UniqueConstraint("job_id", "attempt_id", name="job_attempts_job_attempt_unique")`.

## Concept 8: JobEvent composite provenance (and the Job-level event)

### Tech Lead Question

A JobEvent references an Attempt. How do you guarantee that a non-NULL Attempt belongs to the SAME Job — and
what does a NULL `attempt_id` mean?

### Student Thinking

The student first explained the provenance guarantee by single-column reasoning, then correctly described the
Job-level event case.

### Student Answer

> (initial provenance mechanism) "因为只依靠单列只能出现attempt_id一次"

> (Job-level event, correct) "job_id 是job A，attempt_id是null，这代表Job-level event"

### Tech Lead Review

The mechanism correction: same-Job provenance is guaranteed by a **composite foreign key** `(job_id, attempt_id)
-> job_attempts(job_id, attempt_id)`, not by single-column reasoning. A single Attempt FK would permit a valid
Job plus a valid **but unrelated** Attempt; the composite FK proves the Attempt belongs to that Job. And the
Job-level event answer is exactly right — with the default `MATCH SIMPLE`, a **NULL `attempt_id`** leaves the
composite reference unenforced, which is the intended "optional provenance": `job_id = Job A`, `attempt_id =
NULL` records a **Job-level** Event. Note the composite FK protects provenance; it does **not** limit an Attempt
to one Event (an Attempt can have many Events).

### Engineering Thinking

Cross-row integrity that "must be the same parent" needs a composite key, not an application assumption. NULL,
under MATCH SIMPLE, is the clean way to express "no Attempt provenance for this event."

### Production Example

An event claiming Job A but Attempt-of-Job-B is rejected by the composite FK; a `queued -> running` Job-level
transition records `attempt_id = NULL`.

### Framework Connection

`ForeignKeyConstraint(["job_id","attempt_id"], ["app.job_attempts.job_id","app.job_attempts.attempt_id"],
ondelete="RESTRICT", name="job_events_attempt_same_job_fk")`; `relationship()` is navigation, not this integrity.

## Concept 9: RESTRICT, not cascade — protect audit/recovery facts

### Tech Lead Question

Should the ORM relationships use `cascade="all, delete-orphan"` so deleting a Job cleans up its Attempts,
Events, Outbox rows, and Artifacts?

### Student Answer

> (does cascade deletion fit the retention rule?) "不符合"

### Tech Lead Review

Correct — cascade deletion does **not** fit. Day42 uses `ON DELETE RESTRICT` because Attempts, Events, Outbox
rows, and Artifact references carry **audit/recovery value** (Provider request IDs, errors, cost evidence,
dispatch intent). `cascade="all, delete-orphan"` would let an object-graph cleanup **silently erase** that
evidence, so the mapping must **not** introduce it. `relationship()` here is **navigation only** — it is not
durable integrity enforcement, and it must not carry a destructive cascade. RESTRICT stays the deletion policy.
There is one further subtlety about how the ORM behaves at parent-delete time. By default SQLAlchemy, seeing a
loaded child collection, tries to be "helpful" and emits a pre-delete `UPDATE` that sets each child's foreign
key to `NULL` before deleting the parent — but these child FKs are `NOT NULL`, so that UPDATE would itself fail,
and worse, it moves the decision out of the database. Setting **`passive_deletes="all"`** on the parent-side
relationships (`Job.attempts`/`events`/`outbox_events`, `JobAttempt.result_artifacts`) tells the ORM to emit
**no** pre-delete UPDATE/DELETE on the children at all, so **PostgreSQL's `ON DELETE RESTRICT` makes the final
decision** and rejects the parent delete. Importantly, `passive_deletes="all"` is **not** a cascade — it adds no
`delete`/`delete-orphan` (the cascade stays `save-update, merge`) and it does not change the raw SQL; it simply
lets the database's RESTRICT be the authority instead of the ORM's default NULL-ing behavior.

### Engineering Thinking

Retention is a durable decision. An ORM convenience that deletes children by default is exactly the kind of
silent behavior that destroys the evidence you need after an incident.

### Production Example

An attempt to delete a Job with Attempts is refused by RESTRICT; the audit trail survives for reconciliation
rather than vanishing with an object-graph cascade.

### Framework Connection

`relationship(back_populates=..., passive_deletes="all")` with **no** `cascade="all, delete-orphan"`; FKs
mapped with `ondelete="RESTRICT"`. `passive_deletes="all"` keeps PostgreSQL's `ON DELETE RESTRICT` as the final
delete authority (no ORM pre-delete NULL-ing of a `NOT NULL` child FK).

## Concept 10: Pydantic API models and ORM persistence models stay separate

### Tech Lead Question

Should the public API response reuse the ORM model? And does a Pydantic model prove the database's constraints?

### Student Thinking

The student separated the public response from the database image and distinguished format validation from
database constraints.

### Student Answer

> (public boundary) "不能，公开的响应应该与数据库实际的返回进行区分，避免暴露其他数据库信息"

> (does Pydantic check DB constraints?) "不能，Pydantic只是检查格式，并不会检查实际的约束关系"

### Tech Lead Review

Both correct. Pydantic public HTTP contracts and SQLAlchemy persistence models remain **separate** — they may
translate explicitly, but they must **not** be merged or inherited into a single model that leaks
tenant/audit/persistence fields (this is the Day44 allowlisted-response rule, now on the persistence side). And
Pydantic validates **structure/format**; it does **not** check the actual database constraint relationships
(UNIQUE/CHECK/FK). Those are enforced by PostgreSQL, proven by real database behavior — not by an ORM class or a
Pydantic model.

### Engineering Thinking

Two boundaries, two responsibilities: Pydantic guards the public shape; PostgreSQL guards durable integrity.
Merging them leaks internals and pretends format checks are integrity checks.

### Production Example

A `GET /jobs/{id}` response is a small allowlisted Pydantic model, not the ORM row — so lease/fencing/provider
metadata never leak, and the tenant/idempotency constraints stay a database concern.

### Framework Connection

Day44 public Pydantic models vs the Day46 ORM models; the persistence layer never imports the public models.

## Concept 11: Outbox authority, Artifact ownership, Upload boundary

### Tech Lead Question

Who owns the Outbox row, and what does `published_at IS NULL` mean? Where does a ResultArtifact's Job ownership
come from? What does an UploadSession store?

### Student Thinking

The student placed Outbox authority in PostgreSQL, was unsure about Artifact ownership, and bounded upload
storage to references.

### Student Answer

> (Outbox) PostgreSQL owns it; `published_at = NULL` waits for later dispatch (corrected below).

> (ResultArtifact ownership) "不知道"

> (Upload) save Object Storage reference / lifecycle metadata; the database should not store large files.

### Tech Lead Review

Outbox: PostgreSQL owns the durable **dispatch intent**; the correction is the nuance — `published_at IS NULL`
means the **publish checkpoint is not recorded**, **not** proof the message has never been sent. A crash between
transport publish and checkpoint permits **at-least-once redelivery**, so consumers must be idempotent; Day46
only **maps** it. ResultArtifact ("不知道" is an honest start): it stores **`attempt_id` only**, and Job
ownership is **derived through the Attempt** — do not duplicate `job_id` without a measured need **and** a
constraint preventing contradictory ownership; it stores Object Storage **references/metadata**, not large
bytes. UploadSession: exactly right — Object Storage **reference + lifecycle metadata** only, never large upload
bytes, signed URLs, or credentials.

### Engineering Thinking

Durability lives in PostgreSQL (the Outbox intent); large bytes live in Object Storage (referenced, not stored);
derived ownership avoids contradictory duplicates. Each boundary keeps its own single source of truth.

### Production Example

A relay crashes after publishing but before stamping `published_at`; redelivery is expected and consumers
dedupe. An Artifact row points at an Object Storage key and derives its Job through its Attempt.

### Framework Connection

`outbox_events.published_at` nullable; `result_artifacts.attempt_id` FK (no `job_id` column);
`upload_sessions.object_key` reference.

## Concept 12: Static metadata evidence vs real PostgreSQL evidence

### Tech Lead Question

You run `Base.metadata.create_all()` and it succeeds. Does that prove the mapping is compatible with the existing
schema? What does a static test actually prove?

### Student Thinking

The student distinguished static structural validation from real database behavior and refused to treat creation
success as proof.

### Student Answer

> (what static validation proves) "属于静态验证，能证明ORM classes的语法没有错误，不能证明实际orm映射的PostgreSQL事实"

> (does create_all() success prove compatibility?) "不能，还需要进行验证"

### Tech Lead Review

Exactly. Static metadata tests prove the **declared mapping structure** (syntax, types, names, constraints on
`Base.metadata`); they do **not** prove the mapping matches the **actual** PostgreSQL facts. And
`create_all()` **success is not schema-drift evidence** — it can happily create a *fresh* schema that differs
from the live one. Real behavior requires an **isolated PostgreSQL runtime test**: apply the independent Day42
raw SQL (`001` + `003`) to a fresh database, then assert actual behavior — a duplicate `(tenant_id,
idempotency_key)` rejected, a succeeded Job without `finished_at` rejected, Job B reusing `attempt_number = 1`
accepted. Neither static nor isolated runtime is Day47 integration evidence.

### Engineering Thinking

"It imported / it created" is not "it matches production." Separate the evidence levels honestly, and never let
a green `create_all()` masquerade as compatibility.

### Production Example

In this repository the 20 tests assert declared structure only; a real CHECK/UNIQUE rejection test against
PostgreSQL is **NOT RUN** (no server was available) and is labeled as such.

### Framework Connection

`Base.metadata` introspection (static, executed here) vs a psql/SQLAlchemy runtime test after applying the Day42
SQL (NOT RUN).

## Concept 13: Engine/Session scope, Tenant/Document limits, and the wrong-schema incident

### Tech Lead Question

Does Day46 create a global `AsyncSession`? Is a full Tenant model required? And if a bad release wrote Jobs to
`public.jobs` instead of `app.jobs`, how do you recover — and what is the single most important piece of
evidence?

### Student Thinking

The student first accepted a global session, then corrected the scope; treated tenant as derivable, then
accepted it as a real column; and reasoned clearly about the incident.

### Student Answer

> (create a global Engine/Session?) "是的" — then corrected to "request/Job scope" for both.

> (correct scope) one Engine per process and an independent session per request/Job operation.

> (is a full Tenant model needed?) "不需要，tenant_id可以进行推导" (corrected below).

> (scope of Document/job_documents) "明确保留为未实现的 scope limitation".

> (may you ignore the mis-placed rows?) "不能"; most important evidence: "是否已响应客户端".

> (mapping-incident rollback) "是回滚ORM mapping代码，最终进行测试".

### Tech Lead Review

Session scope: Day46 must **not** create a global `AsyncSession` — mapping metadata needs **no** production
connection. The corrected model is **one Engine per process** (Day47 owns the Engine lifecycle) and **one
session per request/Job unit of work** — never a global session. Tenant: no full Tenant aggregate/relationship
is required for Day46 scope, but the correction to "tenant_id 可以推导" is important — **`tenant_id` must not
disappear as a derived field**; it is an actual **mapped column / FK** on Job and UploadSession (Day46 uses a
minimal Tenant support stub only to preserve those FKs/candidate keys). Document/`job_documents`: correctly kept
as an **explicit, stated unimplemented limitation** — not a half-built `Job.documents` relationship. The
incident: rolling back the ORM mapping/release is right to protect **future** writes, but code rollback is **not
durable-data rollback** — you must **not** blindly ignore, copy, or delete the three mis-placed rows. Preserve
and classify correlation evidence, and the **single most important signal is whether the client was already
responded to** ("是否已响应客户端"), because that determines what a safe, audited, idempotent reconciliation may do.

### Engineering Thinking

Scope discipline (process Engine vs request session) and honest limitations keep the mapping small and correct;
incident recovery separates "stop the bleeding in code" from "repair committed facts with evidence."

### Production Example

A missing-`app`-schema release writes three Jobs to `public.jobs`; the fix rolls back the release, checks
whether each Job's client already got a response, and reconciles the rows into the durable `app` truth under
audit — never a blind delete.

### Framework Connection

Day47 `AsyncEngine`/`AsyncSession` scope (future); the Day45 process-vs-request scope discipline reused here;
`ForeignKey("app.tenants.tenant_id", ondelete="RESTRICT", name="jobs_tenant_fk")` keeping tenant_id explicit.

---

# Common Misconceptions

ORM defines the schema

❌ "Writing ORM classes makes the ORM the schema authority."
✅ In an existing system the ORM is a faithful executable mapping; PostgreSQL stays the durable authority and
deliberate changes go through Day48 migrations.

Why beginners think this: models look like the schema.
How to remember: Day46 maps, Day47 drives, Day48 evolves.

A nullable column enforces the business rule

❌ "`Mapped[datetime | None]` / `nullable=True` enforces 'succeeded implies finished_at'."
✅ Optional typing/nullability only allow NULL; the PostgreSQL CHECK is the cross-write-path invariant.

Why beginners think this: Optional feels like a rule.
How to remember: nullable = allowed to be NULL; CHECK = which combinations are illegal.

A constraint test expects an empty result

❌ "A violated constraint shows up as an empty query."
✅ A negative constraint test expects a REJECTED write — a CHECK violation / `IntegrityError` — not an empty
result set.

Why beginners think this: they picture a SELECT.
How to remember: constraints refuse writes; they don't filter reads.

Attempt uniqueness is tenant-scoped or global

❌ "`UNIQUE(tenant_id, attempt_id)` or a global `UNIQUE(attempt_number)`."
✅ Retry ordinal is Job-scoped: `UNIQUE(job_id, attempt_number)`; Job B may have its own Attempt 1.

Why beginners think this: tenant isolation feels like the scope for everything.
How to remember: the ordinal belongs to the Job's timeline.

A single Attempt FK proves same-Job provenance

❌ "One `attempt_id` FK guarantees the Attempt belongs to the Job."
✅ A single FK permits a valid Job plus an unrelated valid Attempt; the composite `(job_id, attempt_id)` FK
proves same-Job provenance. NULL attempt_id = Job-level event.

Why beginners think this: the FK "points at an attempt."
How to remember: same-parent integrity needs a composite key.

Cascade delete is fine

❌ "Use `cascade='all, delete-orphan'` to clean up children."
✅ Day42 requires ON DELETE RESTRICT; Attempts/Events/Outbox/Artifacts carry audit/recovery value and must not be
erased by object-graph cleanup. `relationship()` is navigation only.

Why beginners think this: cascade is convenient.
How to remember: RESTRICT protects evidence; relationship() ≠ integrity.

`create_all()` success proves compatibility

❌ "It created the tables, so the mapping matches the existing schema."
✅ `create_all()` can build a fresh schema that differs from the live one; only an isolated PostgreSQL runtime
test (after applying the Day42 SQL) proves behavior. Static tests prove declared structure.

Why beginners think this: no error means correct.
How to remember: created ≠ compatible.

tenant_id can be derived away

❌ "No full Tenant model is needed, so tenant_id can be derived and dropped from rows."
✅ No Tenant aggregate is needed for scope, but tenant_id is an actual mapped column/FK and must not disappear.

Why beginners think this: "derivable" sounds like "removable."
How to remember: ownership columns stay explicit.

Code rollback repairs the wrong rows

❌ "Roll back the bad mapping and the mis-placed rows are fixed."
✅ Code rollback protects future writes; the committed wrong-schema rows need audited, idempotent reconciliation
— never a blind ignore/copy/delete. The key signal is whether the client was already responded to.

Why beginners think this: rollback sounds total.
How to remember: roll back code for the future; reconcile facts for the past.

---

# Engineering Trade-offs

## Faithful mapping vs "improving" the schema

Faithful mapping preserves integrity, retention, and compatibility but forbids "nice" cleanups (enum, cascade)
inside the mapping; improving-in-place is tempting but silently diverges from the durable schema and skips
migration review. In an existing system, map faithfully and evolve via Day48.

## TEXT + CHECK vs native enum

`TEXT + CHECK` matches the live column and is trivially extensible via a constraint change; a native enum is
tidier and self-documenting but changes on-disk representation and rollout risk. Keep TEXT + CHECK until a Day48
migration deliberately evolves it.

## ON DELETE RESTRICT vs cascade delete

RESTRICT protects audit/recovery evidence but requires explicit lifecycle handling; cascade is convenient but
can erase incident evidence with a parent delete. For durable audit facts, choose RESTRICT.

## Derive ownership vs denormalize job_id onto Artifact

Deriving Job ownership through the Attempt avoids contradictory duplicates but costs a join; denormalizing
`job_id` is faster to read but permits `artifact.job_id = A` while the Attempt belongs to Job B. Denormalize
only for a measured access problem, and then constrain the duplicated fact.

## Static metadata tests vs isolated PostgreSQL runtime tests

Static tests are fast, deterministic, and need no database, but prove only declared structure; isolated runtime
tests prove real CHECK/UNIQUE/FK behavior but need a server and the applied Day42 SQL. Use static tests as the
baseline; add runtime tests where real behavior must be proven (NOT RUN here).

## Minimal Tenant stub vs full Tenant aggregate

A minimal stub preserves the tenant FKs/candidate keys with the least surface; a full Tenant aggregate models
behavior but is out of Day46 scope and risks scope creep. Map the stub, keep tenant_id explicit, defer the
aggregate.

---

# Hands-on Exercises

These map to the runnable artifact and its **static** tests, which **were executed** (Python 3.10.12, SQLAlchemy
2.0.29, pytest 7.4.3 → **20 passed**; install via `requirements-day46.txt`). They assert the **declared mapping
structure** only; a real PostgreSQL runtime test (apply the Day42 SQL, assert CHECK/UNIQUE/FK rejection) is
**NOT RUN**, and `create_all()` success would not be compatibility evidence.

Run the tests:

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day46.txt
python3 -m py_compile day46_orm_mapping.py test_day46_orm_mapping.py
python3 -m pytest -q test_day46_orm_mapping.py
```

### Exercise 1: Authority or mapping?

Question: is the Day46 ORM the new schema authority or a mapping of the existing contract?

Expected Output: a faithful executable mapping; PostgreSQL stays the durable authority; deliberate change is
Day48.

Follow-up: what silently breaks if you "improve" a column in the mapping?

### Exercise 2: Preserve the business key

Question: how do you map `UNIQUE (tenant_id, idempotency_key)` and what do you defer?

Expected Output: `UniqueConstraint("tenant_id","idempotency_key", name="jobs_tenant_idempotency_unique")`; defer
the Day50 acceptance workflow.

Follow-up: why can't a `job_id`-based rule prevent duplicate business requests?

### Exercise 3: Server-side defaults

Question: where do `job_id` and `created_at` get generated?

Expected Output: server-side — `server_default=text("gen_random_uuid()")` / `text("now()")`.

Follow-up: why is a Python `default=` the wrong choice here?

### Exercise 4: Nullable vs CHECK

Question: does `Mapped[datetime | None]` enforce "succeeded implies finished_at"? How do you test the CHECK?

Expected Output: no — the `jobs_succeeded_has_finished_at` CHECK enforces it; a negative test expects a rejected
write (`IntegrityError`), not an empty result.

Follow-up: which layer owns the conditional invariant?

### Exercise 5: TEXT + CHECK vs enum

Question: map `job_status` — TEXT+CHECK or native enum?

Expected Output: `Text` + `jobs_status_allowed` CHECK; an enum is Day48 evolution.

Follow-up: what changes on disk if you switch to an enum?

### Exercise 6: Attempt scope

Question: what makes an Attempt unique, and may Job B reuse `attempt_number = 1`?

Expected Output: `UNIQUE(job_id, attempt_number)` (Job-scoped); yes, Job B may reuse 1. Not tenant-scoped, not
global.

Follow-up: why does `UNIQUE(job_id, attempt_id)` also exist?

### Exercise 7: Composite provenance

Question: guarantee a non-NULL Attempt belongs to the same Job; explain NULL attempt_id.

Expected Output: composite FK `(job_id, attempt_id) -> job_attempts(job_id, attempt_id)`; NULL = Job-level event.

Follow-up: does the composite FK limit an Attempt to one Event? (No.)

### Exercise 8: Reject cascade

Question: should relationships use `cascade="all, delete-orphan"`?

Expected Output: no — keep ON DELETE RESTRICT; relationships are navigation only (add `passive_deletes="all"`,
not a delete cascade, so the ORM does not pre-NULL a `NOT NULL` child FK and PostgreSQL RESTRICT decides);
audit/recovery evidence must survive.

Follow-up: what evidence would a cascade erase?

### Exercise 9: Separate API and ORM models

Question: reuse the ORM model for the public response? Does Pydantic prove DB constraints?

Expected Output: no and no — separate models; PostgreSQL enforces constraints, Pydantic checks format.

Follow-up: what leaks if you merge them?

### Exercise 10: Evidence levels

Question: classify `create_all()` success, static metadata tests, and an isolated PostgreSQL runtime test.

Expected Output: creation success is not compatibility; static tests prove declared structure; a runtime test
(after applying Day42 SQL) proves behavior. None is Day47 integration.

Follow-up: what exact rejection would a runtime test assert?

### Exercise 11: The wrong-schema incident

Question: a release omitted the `app` schema and wrote three Jobs to `public.jobs`. Recover.

Expected Output: roll back the mapping/release (protect future writes), preserve/classify correlation evidence —
most importantly whether the client was already responded to — then audited idempotent reconciliation; never
blindly ignore/copy/delete. Code rollback ≠ durable-data rollback.

Follow-up: why is "whether the client was responded to" the key signal?

---

# Relevant Framework Connections

## SQLAlchemy 2.0

The lesson's core: `DeclarativeBase` with `MetaData(schema="app")`, `Mapped[T] = mapped_column(...)`, the
PostgreSQL dialect `UUID`/`JSONB`, `server_default=text(...)`, and named `UniqueConstraint`/`CheckConstraint`/
`ForeignKeyConstraint` (including the composite provenance FK with `ondelete="RESTRICT"`). `relationship()` is
navigation only — no `cascade="all, delete-orphan"`, and the parent-side relationships set
`passive_deletes="all"` so PostgreSQL's `ON DELETE RESTRICT` (not an ORM pre-delete NULL-ing of a `NOT NULL`
child FK) makes the final parent-delete decision. No Engine/Session is created (Day47).

## PostgreSQL

PostgreSQL remains the durable authority: the `app` schema, server defaults, named constraints, `ON DELETE
RESTRICT`, scoped uniqueness, and composite provenance are its facts. The mapping declares them; only the
database enforces them. Real runtime behavior is NOT RUN here.

## FastAPI / Pydantic

The Day44 public Pydantic models stay separate from these ORM persistence models — they may translate explicitly
but must not merge, so tenant/audit/persistence fields never leak into a public response.

## Day45 composition boundary

The process-vs-request scope discipline from Day45 carries over: Day47 will own one Engine per process and one
`AsyncSession` per request/Job unit of work — Day46 creates neither.

---

# AI Backend Connections

## Durable multi-tenant Job lifecycle

The mapped Job/Attempt/Event model is the durable backbone of a multi-tenant AI Job API: tenant-owned Jobs,
retried Attempts (paid Provider calls), and append-only lifecycle Events — all with integrity enforced by
PostgreSQL, not by application hope.

## Outbox and at-least-once delivery

The mapped Outbox is PostgreSQL-owned dispatch intent; `published_at IS NULL` is a missing checkpoint, not proof
of "never sent," so downstream Provider/queue consumers must stay idempotent against at-least-once redelivery.

## Object Storage provenance

ResultArtifacts and UploadSessions store Object Storage **references** and provenance metadata (keys, checksums,
sizes), never large bytes — keeping paid artifact bytes out of the durable database while preserving audit
provenance.

## Incident reconciliation

When an unfaithful mapping mis-writes durable facts, recovery is evidence-based reconciliation — correlated,
idempotent, audited — because the durable record (and paid Provider work behind it) cannot be fixed by a code
rollback alone.

---

# English Interview

## Key Vocabulary

SQLAlchemy 2.0, `DeclarativeBase`, `Mapped`, `mapped_column`, declarative mapping, schema authority, server-side
default, named constraint, `CheckConstraint`, composite foreign key, `ON DELETE RESTRICT`, cascade, provenance,
Outbox, at-least-once, idempotency key, static metadata vs runtime evidence, migration (Alembic).

## Useful Expressions

"The ORM maps the contract; it doesn't replace it." · "PostgreSQL is the durable authority." · "A nullable
column is not a CHECK." · "Retry ordinal is Job-scoped." · "The composite FK proves same-Job provenance." ·
"RESTRICT protects audit evidence." · "`create_all()` success is not compatibility." · "Code rollback is not
durable-data rollback."

## Beginner Question — What does it mean to map an existing database schema with an ORM, and is the ORM the schema authority?

Student answer (verbatim):

> "不知道"

Strong spoken answer taught:

> "Mapping means writing ORM models that faithfully represent an existing database schema — its tables, columns,
> types, defaults, and constraints — so application code can work with typed objects. In a system that already
> has a schema, the database remains the authority; the ORM is a representation, not a redefinition. Deliberate
> schema changes go through a migration tool like Alembic, not by editing the models."

Assessment: an honest "不知道"; the taught answer covers faithful representation, the database staying
authoritative, and migrations for change.

## Intermediate Question — Why keep `TEXT + CHECK` for status instead of a native enum, and why doesn't a nullable column enforce a conditional rule?

Student answer (verbatim):

> "不知道"

Strong spoken answer taught:

> "I keep `TEXT + CHECK` because that is the existing database fact; switching to a native enum changes the
> on-disk representation and is a migration, not a mapping. And a nullable column only means NULL is allowed —
> it does not enforce a conditional business rule like 'a succeeded Job must have a finish time.' That rule is a
> CHECK constraint, enforced by PostgreSQL on every write path, and a negative test for it expects a rejected
> write, not an empty result."

Assessment: an honest "不知道"; the taught answer separates mapping from migration and nullability from the CHECK.

## Senior Question — A release omitted the `app` schema and wrote accepted Jobs to `public.jobs`. How do you recover, and what evidence matters most?

Student answer (verbatim):

> "不知道"

Strong spoken answer taught:

> "First I roll back the bad mapping or release to protect future writes, remembering that a code rollback does
> not undo the committed rows. I preserve and classify correlation evidence — release version, job, tenant,
> request and trace IDs — and the single most important signal is whether the client was already responded to,
> because that constrains what a safe reconciliation may do. Then I reconcile the mis-placed rows into the
> durable `app`-schema truth through an idempotent, audited process — never blindly ignoring, copying, or
> deleting them."

Assessment: an honest "不知道"; the taught answer is the full contain → preserve/classify → reconcile arc with the
client-response signal and the code-vs-data rollback boundary.

## Common Weak Answer

"I'll define the ORM models, run `create_all()`, and since it succeeds the mapping matches the database; I'll add
`cascade='all, delete-orphan'` so cleanup is easy."

## Strong Answer

"The ORM faithfully maps the existing PostgreSQL contract — app schema, server defaults, named UNIQUE/CHECK/FK
constraints, ON DELETE RESTRICT, Job-scoped attempt uniqueness, and a composite same-Job provenance FK — without
redesigning it. `create_all()` success is not compatibility evidence; static tests prove declared structure and
a real runtime test would apply the Day42 SQL and assert rejected writes. I keep TEXT+CHECK (an enum is a Day48
migration), never add a destructive cascade (RESTRICT protects audit evidence), and keep Pydantic public models
separate from the ORM. Day47 owns the Engine and per-request sessions."

---

# Mental Model Summary

```text
1.  ORM mapping REPRESENTS the database contract; it does not silently REPLACE it (Day46 maps / Day47 drives / Day48 evolves).
2.  PostgreSQL is the durable authority; its PK/UNIQUE/CHECK/FK/RESTRICT enforce integrity, not the ORM class.
3.  Base.metadata schema="app" = exact existing table identity; no search_path dependence.
4.  Mapped[T] = mapped_column(...) is the typed declarative mapping; a plain annotation is not a mapping.
5.  Database-generated values are SERVER defaults: gen_random_uuid()/now()/'queued'/0/false/'{}'::jsonb.
6.  Mapped[datetime | None] + nullable=True allow NULL; they do NOT enforce jobs_succeeded_has_finished_at (a CHECK does).
7.  A negative constraint test expects a REJECTED write (CHECK violation / IntegrityError), not an empty result.
8.  Status stays TEXT + named CHECK (jobs_status_allowed); a native enum is Day48 schema evolution.
9.  Attempt retry ordinal is JOB-scoped: UNIQUE(job_id, attempt_number); also UNIQUE(job_id, attempt_id) for provenance.
10. JobEvent same-Job provenance = composite FK (job_id, attempt_id) -> job_attempts; NULL attempt_id = Job-level event.
11. ON DELETE RESTRICT everywhere; NO cascade/delete-orphan; relationship() is NAVIGATION, not integrity; parent-side relationships set passive_deletes="all" so PostgreSQL RESTRICT (not an ORM NULL-ing of a NOT NULL child FK) is the final delete authority.
12. Pydantic public models != ORM persistence models (never merged); neither proves PostgreSQL constraint behavior.
13. Outbox is PostgreSQL-owned dispatch intent; published_at NULL = checkpoint not recorded, not "never sent" (at-least-once).
14. ResultArtifact stores attempt_id ONLY (job ownership derived); UploadSession stores references/metadata, not bytes.
15. Static metadata proves declared STRUCTURE; create_all() success != compatibility; real PostgreSQL runtime is separate.
16. No global AsyncSession in Day46 (Day47: one Engine/process, one session/request-Job); tenant_id stays an explicit column/FK.
17. Document/job_documents = stated unimplemented limitation (not a half-built relationship).
18. Wrong-schema incident: roll back code for the future; reconcile committed rows with evidence (client-responded?) and audit.

Starting model -> reasoning -> correction -> final model:
Initial: the ORM becomes the schema authority; Attempt uniqueness is tenant-scoped; a single FK proves same-Job
provenance; a global Engine/Session is fine; a CHECK test returns empty; tenant_id is derivable; the three
English answers were "不知道".
Reasoning: chose to preserve UNIQUE(tenant_id, idempotency_key), mapped server defaults, mapped Text+CHECK, saw a
different Job may reuse attempt_number 1, described the Job-level NULL-attempt event, kept ORM/Pydantic separate,
bounded upload storage to references, refused cascade deletion, and refused to ignore mis-placed rows.
Correction: the ORM maps (does not replace); Attempt uniqueness is Job-scoped; a composite FK proves provenance;
one Engine per process + one session per request/Job; a CHECK test expects a rejected write; tenant_id stays an
explicit column/FK; static evidence != PostgreSQL runtime evidence; code rollback != durable-data rollback.
Final: ORM mapping represents the database contract; PostgreSQL is durable authority; Day46 maps it faithfully,
Day47 drives it transactionally, Day48 evolves it safely.
```

---

# Today's Takeaway

Day46 turns the Day42 durable PostgreSQL contract into a faithful SQLAlchemy 2.0 mapping — same `app` schema,
same server defaults, same named UNIQUE/CHECK/FK constraints, same `ON DELETE RESTRICT`, same TEXT+CHECK status,
same Job-scoped attempt uniqueness, and the same composite same-Job provenance FK — without changing ownership,
integrity, retention, public boundaries, or schema authority. The ORM represents the database contract; it does
not silently replace it. PostgreSQL is the durable authority; Day46 maps it faithfully; Day47 drives it
transactionally; Day48 evolves it safely.

Most important mental model: mapping, not authority — the database enforces integrity; the ORM declares it. Most
important production risk: an unfaithful mapping (enum swap, cascade delete, dropped tenant column, missing
schema) silently corrupting integrity, retention, or durable data. Most important trade-off: faithful mapping
vs "improving" the schema in place. Most important connection: Day47 drives these mappings with an
Engine/AsyncSession and transactions. Most important interview answer: `create_all()` success is not
compatibility, and code rollback is not durable-data rollback.

Validation status: **20 static metadata-contract tests** are **real executed evidence** of the declared mapping
structure — executed here on Python 3.10.12 / SQLAlchemy 2.0.29 / pytest 7.4.3 (pinned in
`requirements-day46.txt`) → **20 passed** — asserting app-schema identity, typed columns, server defaults, named
constraints, ON DELETE RESTRICT, the composite provenance FK, TEXT+CHECK (not enum), no cascade delete,
ORM/Pydantic separation, and the documents/job_documents limitation. But **PostgreSQL runtime is NOT RUN** (no
server was available; `create_all()` was not used and would not be compatibility evidence). AsyncSession/
transactions/repository/UoW (Day47), Alembic migrations (Day48), Celery/Provider/Object-Storage runtime, and
integration/production are all **NOT RUN**.

---

# Before Next Lesson Checklist

```markdown
- [ ] Can I explain why the Day46 ORM maps the existing contract rather than becoming a new schema authority?
- [ ] Can I map a column with `Mapped[T] = mapped_column(...)` and a server-side default?
- [ ] Can I explain why a nullable column and Optional typing do not replace the `jobs_succeeded_has_finished_at` CHECK?
- [ ] Can I say why status stays TEXT + CHECK instead of a native enum?
- [ ] Can I encode Job-scoped attempt uniqueness and the JobEvent composite provenance FK (and the NULL-attempt event)?
- [ ] Can I explain why relationships must not use `cascade="all, delete-orphan"` (ON DELETE RESTRICT)?
- [ ] Can I keep Pydantic public models separate from ORM models and say why neither proves DB constraints?
- [ ] Can I classify Outbox authority, ResultArtifact ownership-via-Attempt, and the UploadSession storage boundary?
- [ ] Can I distinguish static metadata evidence from real PostgreSQL runtime evidence, and why `create_all()` proves neither compatibility?
- [ ] Can I run the static tests (`pytest -q test_day46_orm_mapping.py`) and read the 20-passed evidence honestly?
- [ ] Can I diagnose the wrong-schema incident and recover without treating code rollback as durable-data rollback?
```

Preparation for Day47 (Async Sessions, Transactions, Repository and Unit of Work): review this mapping, then
preview how an app/process-scoped `AsyncEngine` and a request/Job-scoped `AsyncSession` drive these models
through transaction boundaries, a repository, and a unit of work — the runtime behavior Day46 deliberately did
not implement. Alembic safe evolution (Day48) remains a later boundary.

---

Engineering Artifact: [projects/ai-backend-data-layer/api/day46-sqlalchemy-mapping-for-the-day42-data-model-design.md](../../projects/ai-backend-data-layer/api/day46-sqlalchemy-mapping-for-the-day42-data-model-design.md) · Code: [`day46_orm_mapping.py`](../../projects/ai-backend-data-layer/api/day46_orm_mapping.py) · Tests: [`test_day46_orm_mapping.py`](../../projects/ai-backend-data-layer/api/test_day46_orm_mapping.py)
