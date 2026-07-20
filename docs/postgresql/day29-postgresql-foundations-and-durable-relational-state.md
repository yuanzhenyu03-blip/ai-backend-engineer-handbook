# Lesson 29 — PostgreSQL Foundations and Durable Relational State

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Intermediate

Estimated Time: 6-7 hours

Prerequisite: Day28 — AI Backend Production Architecture

Previous Lesson: [Day28 — AI Backend Production Architecture](../devops/day28-ai-backend-production-architecture.md)

Next Lesson: [Day30 — SQL Data Manipulation and Query Fundamentals](day30-sql-data-manipulation-and-query-fundamentals.md)

Engineering Artifact: The first increment of the Production AI Backend Data Layer — a minimal raw SQL Job schema plus an honest validation/limitations README — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

PostgreSQL Cheat Sheet: [cheat_sheets/postgresql.md](../../cheat_sheets/postgresql.md)

PostgreSQL Interview: [interview/postgresql.md](../../interview/postgresql.md)

Estimated Study Time:

```text
Reading: 120-150 minutes
Exercises: 90-120 minutes
Hands-on schema authoring + disposable PostgreSQL validation: 90-120 minutes
Review: 30-45 minutes

Total: 6-7 hours
```

This is the first Phase 3 lesson. It turns Day28's conceptual ownership rule into an executable table.

---

# Learning Objectives

After completing this lesson, the student should be able to:

* Explain why a durable relational database must hold the accepted Job **before** FastAPI returns `202`.
* Distinguish PostgreSQL server/cluster/database/schema/table/row/column, and explain what a `psql` session actually connects to.
* Distinguish the two senses of "schema": a PostgreSQL namespace vs a table definition/contract.
* Choose PostgreSQL types and defaults for the Job model (uuid, text, integer, boolean, `timestamptz`, bounded jsonb) and defend UUID vs integer identity.
* Explain why core Job facts belong in typed columns while JSONB stays bounded auxiliary metadata.
* Interpret `NULL` per field lifecycle, and explain what `NOT NULL` does and does NOT enforce.
* Distinguish a primary key (row identity) from a business/idempotency key (request identity).
* Explain `timestamptz` as one absolute instant rendered in the session time zone.
* Separate conceptual review, SQL/runtime acceptance, application integration, and production evidence.
* Repair already-persisted wrong facts with a guarded UPDATE, and explain why code rollback cannot.

The engineering artifact is a raw SQL schema and an honest README, not application code.

---

# Why This Matters

Day28 ended with a conceptual blueprint: PostgreSQL owns durable Job truth. Nothing was executable —
no schema, no SQL, no database runtime, no test.

Day29 starts exactly where that leaves the system exposed:

```text
A verified 500 MB RAG document is ready. FastAPI is about to return 202 + job_id.
If the accepted Job exists only in API Pod memory, Pod replacement destroys the commitment.
```

Why a backend engineer must care:

```text
Durability  -> the Job row must be persisted BEFORE 202 is returned; 202 acknowledges an existing fact.
Contract    -> the table definition is an executable contract (types, NOT NULL, defaults, primary key).
Boundaries  -> database vs schema vs table vs row; a session connects to a database, not a schema.
Modeling    -> typed columns for identity/state/time/counters; bounded JSONB for optional extras.
Honesty     -> NOT NULL is not business integrity; durability without integrity makes WRONG facts durable.
Repair      -> code rollback stops future bad writes; only guarded SQL fixes rows already persisted.
```

The lesson's sharpest production moment: a misspelled `queud` status is perfectly durable and perfectly
unclaimable. Persistence is not correctness.

---

# Roadmap Position

Knowledge continuity chain (v3.2):

```text
Previous Knowledge (Day28)
        |
        v
Current Concept (Day29: a durable, typed PostgreSQL row + an enforceable table contract)
        |
        v
Future Usage (Day30 SQL manipulation; Day31 relationships/integrity; Day33 transactions;
              Day34 concurrency-safe claims and idempotency enforcement)
```

Where Day29 sits:

```text
Day28 state ownership (conceptual)
-> Day29 durable typed row + table contract  <-- you are here
-> Day30 SQL data manipulation and guarded Job queries
-> Day31 relationships, business keys, CHECK/UNIQUE/foreign keys
-> Day33 transactions -> Day34 concurrency + idempotency enforcement
```

Day28 rules reused directly:

```text
- FastAPI accepts/exposes; Celery executes; Queue/Redis transports; PostgreSQL owns durable truth.
- Object Storage owns large bytes; the database keeps references.
- 202 + job_id is a durable business commitment.
- Compute rollback does not repair persisted data.
```

Future connection only: SQLAlchemy and Alembic are Phase 4. Day29 teaches raw PostgreSQL behavior first,
so the ORM later maps onto an understood model rather than hiding it.

---

# Lesson Map

```text
Durable facts before 202 (job_id, job_status, created_at)
  -> PostgreSQL hierarchy + psql session boundary (database vs schema; public vs app; search_path)
  -> Types and defaults for the Job model (uuid/text/integer/boolean/timestamptz/bounded jsonb)
  -> Typed columns vs a JSONB-only Job document (and type vs relationship cardinality)
  -> NULL per lifecycle, NOT NULL limits, DEFAULT-generated facts (DEFAULT VALUES + RETURNING)
  -> Primary key vs business/idempotency identity
  -> timestamptz as one absolute instant
  -> Validation levels + durable-but-wrong facts: the `queud` incident and guarded data repair
```

---

# Core Mental Model

```text
Application object/state is temporary.
Database row is a durable business fact.
Table schema is an enforceable contract for those facts.
```

```text
Before FastAPI returns 202, PostgreSQL must ALREADY contain the durable Job row.
202 is the acknowledgement of a commitment that already exists — not the trigger that creates it.
```

Persistence and integrity are different guarantees: a row can be perfectly durable and still wrong.

---

# Main Concepts

## Concept 1: The Minimum Durable Facts Before `202`

Tech Lead Question:

A verified 500 MB document is ready and FastAPI is about to return `202 + job_id`. What is the minimum
set of facts that must already be durable, and when must they be written?

Student Thinking:

The client needs an identifier to poll with, the system needs to know the job's state, and you need to
know when it was accepted.

Student Answer:

> "记录job_id,job_status,以及创建的时间"

Tech Lead Review:

Correct minimum set. The critical correction is **ordering**:

```text
WRONG: return 202 -> then write the Job row
RIGHT: write (and commit) the Job row -> then return 202
```

`202` is the external acknowledgement of a commitment that already exists durably. If the API Pod dies
one millisecond after responding, the system must still be able to find and process that Job.

Three fields, three different lifecycles:

```text
job_id     -> stable identity, never changes
job_status -> evolves (queued -> running -> ... -> terminal)
created_at -> immutable historical time
```

Engineering Thinking:

An accepted request is a promise. A promise that exists only in process memory is not a promise — it is
a hope that the Pod survives.

Production Example:

Kubernetes replaces the API Pod during a rolling update. With the row in PostgreSQL, a worker still
claims the Job. With the Job only in memory, the client holds a `job_id` that refers to nothing.

Framework Connection:

Day28 said "PostgreSQL owns durable truth"; this is the first row that actually implements it.

Exercise:

Identify the minimum durable facts required before `202`, and state whether the write happens before or
after the response.

## Concept 2: PostgreSQL Hierarchy and the `psql` Session Boundary

Tech Lead Question:

You run `INSERT INTO jobs ...` and PostgreSQL says the relation does not exist — but you created it.
Which boundary did you actually cross, and what does a `psql` session connect to?

Student Thinking:

You must first connect to something larger than the table.

Student Answers:

> "先连接到某个更大的 PostgreSQL 边界，应该是先连接的数据库"

> "INSERT INTO app.jobs，因为publidc.job，scheme命名空间一般是记录的数据库的公共信息而不是具体业务表信息"

> (diagnosis) "是否连接的正确的scheme app"

Tech Lead Review:

The first answer is right: you connect to a **database**. Two corrections follow.

```text
Server process -> cluster -> database -> schema -> table -> row -> column

A psql session connects to ONE database using host/port/database/user.
It does NOT "connect to a schema".
Schema resolution happens via a qualified name (app.jobs) or via search_path.
```

Correction to the `public` belief: `public` is **not** a store for "public database information". It is
simply a **default namespace** that may contain any permitted objects, including business tables. `app`
is just an explicitly chosen namespace.

Also note the overloaded word "schema":

```text
PostgreSQL Schema  = a namespace / permission-organization boundary inside one database
"table schema"     = the table definition/contract (columns, types, constraints, defaults)
```

That is why the artifact uses the fully qualified `app.jobs` — it removes hidden `search_path`
assumptions.

Session diagnostic checklist taught in class:

```text
\conninfo
SELECT current_database();
SELECT current_user;
SHOW search_path;
SELECT current_schema();
\dn
\dt app.*
SELECT * FROM app.jobs;
```

Engineering Thinking:

"Not found" is usually a namespace/resolution question, not a missing-object question. Qualify explicitly
in artifacts; use `search_path` deliberately, never accidentally.

Production Example:

In class, `search_path` was `"$user", public` and `current_schema()` was `public`, so an unqualified
`jobs` would not resolve — while explicit `app.jobs` succeeded.

Framework Connection:

An application connection string selects host/port/database/user; the schema is chosen by the SQL you
write (or by an explicit `search_path` setting), not by the connection.

Exercise:

Diagnose `app.jobs` not found through the database/schema/`search_path` boundaries, and distinguish
`public` from `app` without treating `public` as a data classification.

## Concept 3: Types and Defaults for the Job Model

Tech Lead Question:

Give each Job field a PostgreSQL type and a default. Which identity type do you choose, and why?

Student Thinking:

Integer auto-increment is the familiar primary key; status is a string; created_at is a time value.

Student Answer:

> "job_id使用int 类型并且禁止为空使用自增，job status使用 字符串类型描述当前job事实状态，不能使用任意的字符串不能使用空字符串，created_at是用时间类型，放入时间戳"

Tech Lead Review:

The instinct is sound and the "not any arbitrary string, not empty" wish is exactly right — but note
that this lesson does **not** yet enforce it (see Concept 5).

Integer vs UUID is a real trade-off, not a ranking:

```text
integer (auto-increment): compact, index-friendly, sequential locality
                          BUT centrally generated and publicly enumerable
uuid: generated anywhere (client/app/DB), non-enumerable public identity
      BUT larger and less index-local
```

Day29's scenario/Curriculum chooses **UUID**: the identity is handed to an external client and may be
generated in a distributed system. Do not present UUID as universally superior.

The agreed shape:

```text
job_id            uuid        PRIMARY KEY DEFAULT gen_random_uuid()
job_status        text        NOT NULL DEFAULT 'queued'
attempt_count     integer     NOT NULL DEFAULT 0
cancel_requested  boolean     NOT NULL DEFAULT false
provider_metadata jsonb       NOT NULL DEFAULT '{}'::jsonb   (bounded, auxiliary only)
created_at        timestamptz NOT NULL DEFAULT now()
started_at        timestamptz NULL
finished_at       timestamptz NULL
error_message     text        NULL
result_object_key text        NULL
```

Engineering Thinking:

Types encode meaning and enable the database to generate consistent initial facts. `DEFAULT` moves
"what a new Job looks like" out of every client and into one contract.

Production Example:

`gen_random_uuid()` and `now()` mean an accepted Job gets a valid identity and an accurate acceptance
time even if the application forgets to send them.

Framework Connection:

`result_object_key` is a **reference** to Object Storage (Day28), never the bytes themselves.

Exercise:

Choose and defend PostgreSQL types/defaults for the Job model, including the UUID-vs-integer trade-off.

## Concept 4: Typed Columns vs a JSONB-only Job Document

Tech Lead Question:

Why not store the entire Job as one JSONB document? And classify `attempt_count`,
`cancel_requested`, `provider_metadata`.

Student Thinking:

Putting everything in JSON loses the database's ability to generate values automatically.

Student Answers:

> "失去job_id自带生成UUID的能力，created_at失去timeastapzt生成时间戳的能力"

> "provider_metadata，另外两个使用一对多关系型类型"

Tech Lead Review:

Two corrections.

First, JSONB does not make generation *mathematically impossible* — but it removes simple, first-class
column defaults/types/constraints and complicates queries, indexes, relationships, statistics, and
integrity.

```text
Typed columns  -> identity, state, timestamps, counters, booleans, joins, indexes, integrity
Bounded JSONB  -> OPTIONAL, non-authoritative auxiliary metadata only
NEVER in JSONB -> large bytes, secrets, signed URLs, the only job_id, the only job_status
```

Second — the classification mixes two different concepts:

```text
attempt_count     -> integer   (a scalar TYPE)
cancel_requested  -> boolean   (a scalar TYPE)
provider_metadata -> jsonb     (a scalar TYPE holding a document)

"one-to-many" is NOT a column type. It is relationship CARDINALITY between rows/tables — Day31 scope.
```

Engineering Thinking:

Choose typed columns for anything you must query, constrain, index, join, or trust. Keep JSONB as a
deliberately bounded escape hatch.

Production Example:

`provider_metadata` may hold assorted provider fields today, but a frequently queried
`provider_request_id` should be promoted to a typed column in a later model.

Framework Connection:

Day28 assigned the 500 MB document and large derived artifacts to Object Storage; PostgreSQL stores
metadata and references.

Exercise:

Compare typed columns with a JSONB-only Job document, then classify `attempt_count`,
`cancel_requested`, and `provider_metadata`.

## Concept 5: `NULL` per Lifecycle, `NOT NULL` Limits, and Database-generated Defaults

Tech Lead Question:

`started_at`, `finished_at`, `error_message`, `result_object_key` are nullable. What does `NULL` mean
for each? And what exactly does `NOT NULL` protect?

Student Thinking:

Each null field means that stage has not happened yet.

Student Answer:

> "允许，第一个代表还没生成job任务，第二个代表job还没结束，第三个代表没有错误信息，第四个代表还没上传文件"

Tech Lead Review:

Three of four are right; two wordings need correction. `NULL` is **context-dependent** — unknown, not yet
occurred, not available, or not applicable:

```text
started_at        NULL -> execution has NOT STARTED   (not "the Job was not created" — it exists)
finished_at       NULL -> the Job is NOT TERMINAL yet
error_message     NULL -> no recorded error
result_object_key NULL -> no result artifact yet
                          (NOT "the input file has not been uploaded" — the input was already verified)
```

Then the sharp limit of `NOT NULL`:

```text
NOT NULL rejects SQL NULL.
NOT NULL does NOT reject an empty string, and does NOT reject arbitrary text.
```

Runtime evidence from class confirmed both: an **empty** `job_status` and `'banana'` were **accepted**.
The student's earlier wish ("不能使用任意的字符串不能使用空字符串") is correct engineering — it just
requires `CHECK`/enum-style integrity, which is **Day31 scope**, deliberately not added today.

Proving the defaults are the database's, not the client's — `DEFAULT VALUES` + `RETURNING`:

```sql
INSERT INTO app.jobs DEFAULT VALUES RETURNING *;
```

Student first answer: "不知道". After direct teaching, the student explained it correctly:

> "因为没有没有与客户端进行任何交互，全程是数据库自己设置的默认值"

Precise wording correction: the client still sends an `INSERT`; it just **omits every business field**,
so every returned value is demonstrably database-generated.

Engineering Thinking:

`NULL` is a lifecycle statement, not a generic "empty". `DEFAULT` centralizes what a new fact looks
like. Neither one gives you business integrity.

Production Example:

`DEFAULT VALUES RETURNING *` returned `queued`, `0`, `false`, `{}`, and a `created_at`, with the four
lifecycle fields `NULL` — exactly the accepted-Job shape.

Framework Connection:

An application that forgets to set `job_status` still produces a valid `queued` Job — but an application
that sends `'queud'` also produces a "valid" row (Concept 8).

Exercise:

Interpret each nullable lifecycle field, and use `DEFAULT VALUES` + `RETURNING` to verify defaults.

## Concept 6: Primary Key vs Business / Idempotency Identity

Tech Lead Question:

The `202` response is lost and the client retries the same request. Does the UUID primary key prevent a
duplicate Job?

Student Thinking:

The primary key only guarantees the row is unique in the table.

Student Answer:

> "job_id只是数据库的主键与唯一值，不代表可以判断下次job与这次是否一样"

Tech Lead Review:

Exactly right, and this is the key boundary of the day:

```text
Primary key  -> identifies ONE ROW. Prevents duplicate KEY VALUES.
Business/idempotency key -> identifies ONE BUSINESS REQUEST. Prevents duplicate OPERATIONS.
```

A retried request simply produces a *second row with a different UUID*. Both rows are perfectly valid;
the business has been executed twice.

The real fix (taught conceptually, implemented later):

```text
Store a request idempotency key with the Job
+ enforce it with a DATABASE UNIQUE rule
+ use an atomic insert/upsert (read-before-write is race-prone: two concurrent requests can both see
  the key as missing)
+ on conflict, return the existing Job after verifying the payload matches
```

Honest scope statement: **the Day29 schema has no idempotency key and no uniqueness rule**, so it cannot
prevent duplicate business Jobs. That is Day31 (constraints) and Day34 (concurrency) work.

Engineering Thinking:

Uniqueness must be enforced by the database on the *business* identity. Application-side checking loses
the race.

Production Example:

Two retries arrive concurrently; both `SELECT` and see nothing; both `INSERT`; two Jobs, two eight-minute
embeddings, double provider cost.

Framework Connection:

This is Day28's at-least-once + idempotency rule, now expressed as a concrete missing database constraint.

Exercise:

Distinguish row identity from request/idempotency identity and name the missing enforcement.

## Concept 7: `timestamptz` Is One Absolute Instant

Tech Lead Question:

The same `created_at` prints as `...12:32:00.454132+00` and `...20:32:00.454132+08`. Are these two
different times?

Student Thinking:

Same moment, different display.

Student Answer:

> "表示同一个时间点的两种显示方式，应该是时区不同"

Tech Lead Review:

Correct. Runtime evidence: both renderings had the identical Unix epoch `1784464320.454132`.

```text
timestamptz  -> ONE absolute instant, displayed in the SESSION time zone
timestamp    -> wall-clock fields only; does NOT identify an absolute moment
```

Important nuance: PostgreSQL does **not** preserve the original time-zone *label*. If "which time zone
the user was in" is a business requirement, store it separately as its own column.

Engineering Thinking:

Store instants, render locally. Ambiguous local wall-clock time is a source of real production incidents.

Production Example:

Job acceptance time compared across regions must be one instant; otherwise "oldest queued age" (Day28
monitoring) is meaningless.

Framework Connection:

Day28's SLO signals (oldest queued-job age, end-to-end latency) require a real absolute instant.

Exercise:

Compare the same `timestamptz` under UTC and Asia/Shanghai and confirm the epoch is identical.

## Concept 8: Validation Levels, and Repairing Durable-but-Wrong Facts

Tech Lead Question:

You read the DDL carefully and it looked right. What have you actually proven? Then: API v2 wrote
`queud` while workers only claim `queued`. Is rolling back the API enough?

Student Thinking:

Reading proves the syntax; and rolled-back code does not change rows already stored.

Student Answers:

> (validation) "完成了语法验证，声称完成生产验证"

> (repair) "不够，之前的数据库数据已经持久化，对于错误的JOB只能使用sql进行update"

Tech Lead Review:

The validation answer overclaimed at both ends — correction:

```text
Human reading            -> conceptual/manual review. NOT parser proof.
Executed DDL in PostgreSQL -> syntax + runtime acceptance IN THAT VERSION (class: 14.18).
Local runtime success    -> NOT application integration, NOT production validation.
```

The repair answer is right in direction. The `queud` incident is the day's most important production
lesson:

```text
A misspelled status is perfectly DURABLE and perfectly UNCLAIMABLE.
Persistence without integrity makes WRONG facts durable.
```

```text
Code rollback  -> stops FUTURE bad writes. It does not mutate rows already persisted.
Data repair    -> a guarded UPDATE fixes the facts already stored.
```

But a bare `UPDATE` is not a production runbook. The complete order:

```text
1. Contain (stop the bad writer / roll back the release).
2. Identify the EXACT affected set (release/time/tenant/provenance).
3. Execute a GUARDED repair (narrow WHERE), never a blanket update.
4. Capture evidence (affected row count + RETURNING the repaired ids).
5. Verify business recovery (workers can now claim the Jobs).
```

Runtime evidence from class: three `queud` rows were inserted; the guarded
`UPDATE ... WHERE job_status = 'queud'` reported `UPDATE 3` and returned the three repaired `job_id`s;
post-repair counts were `empty=1, banana=1, queued=4`.

Honest limitation: this minimal schema has **no release/time/tenant/provenance columns**, so real
production identification of "which rows did v2 write" would not be possible yet.

Engineering Thinking:

Never claim validation beyond your evidence, and never repair data with an unguarded statement.

Production Example:

Restarting the PostgreSQL process left all 6 rows intact — proving local process-lifecycle persistence,
and **nothing** about backups, HA, or hardware-failure durability.

Framework Connection:

This is Day28's "compute rollback does not repair data" rule executed with real SQL for the first time.

Exercise:

Classify the validation levels, then simulate `queud`, perform a guarded repair, and verify counts.

---

# Common Misconceptions

## Mental Model Evolution (Day28 -> Day29)

```text
Initial: "Day28 decided PostgreSQL owns durable Job truth, so the ownership problem is solved."
Reasoning: The architecture blueprint assigned every component a clear responsibility.
Correction: The blueprint was conceptual — no schema, no types, no defaults, no executed SQL. And once
            the row exists, durability alone still permits WRONG facts (`queud`) to be stored forever.
Final: Before 202 the Job row must already be committed; the table definition is an executable contract
       for that fact; typed columns hold identity/state/time while bounded JSONB holds extras; NOT NULL
       is not business integrity; a primary key is not a business identity; and code rollback cannot
       repair rows that are already persisted.
```

## Misconception list

```text
Timing of 202
❌ FastAPI returns 202 and then PostgreSQL creates the Job row.
✅ The durable Job row is written (and committed) BEFORE 202; 202 acknowledges an existing commitment.
```

```text
Integer auto-increment vs UUID
❌ One of them is simply the correct primary key.
✅ Integer is compact/index-friendly but centrally generated and enumerable; UUID suits distributed,
   non-enumerable public identity at a storage/index-locality cost. Day29 chooses UUID for this scenario.
```

```text
The word "schema"
❌ "Schema" has one meaning.
✅ PostgreSQL Schema = a namespace/permission boundary inside a database. "Table schema" = the table
   definition/contract. Keep the two senses explicit.
```

```text
The public schema
❌ `public` stores "public database information".
✅ `public` is just a DEFAULT namespace that may contain any permitted objects, including business tables.
```

```text
psql connects to a schema
❌ A session connects to a schema.
✅ A session connects to ONE DATABASE (host/port/database/user); schema resolution happens via qualified
   names or `search_path`.
```

```text
JSONB-only Job document
❌ Putting the Job in one JSONB blob loses nothing essential / makes generation impossible.
✅ Generation is not impossible, but you lose first-class defaults/types/constraints and complicate
   queries, indexes, relationships, statistics, and integrity. JSONB is bounded auxiliary metadata.
```

```text
One-to-many as a column type
❌ `attempt_count` / `cancel_requested` are "one-to-many relational types".
✅ They are integer and boolean SCALAR types. One-to-many is relationship CARDINALITY — Day31 scope.
```

```text
NULL meanings
❌ `started_at` NULL means the Job was not created; `result_object_key` NULL means the input was not uploaded.
✅ The accepted Job exists and its input was already verified. NULL is per-field lifecycle: not started /
   not terminal / no recorded error / no result artifact yet.
```

```text
NOT NULL is integrity
❌ `text NOT NULL` guarantees a valid status.
✅ It only rejects SQL NULL. Empty string and `banana` were both ACCEPTED at runtime. CHECK/enum-style
   integrity is Day31 work.
```

```text
Primary key prevents duplicate business operations
❌ A UUID primary key stops a retried request from creating a second Job.
✅ It prevents duplicate KEY VALUES only. A retry just creates another row with a new UUID. Business
   retry identity needs a stored idempotency key + a database UNIQUE rule + atomic insert/upsert.
```

```text
DEFAULT VALUES means "no client interaction"
❌ Nothing was sent from the client.
✅ The client still sends an INSERT; it OMITS every business field, so returned values are demonstrably
   database-generated.
```

```text
Validation overclaim
❌ Reading the DDL proves syntax; a successful local run proves production readiness.
✅ Reading is conceptual/manual review; executed DDL proves acceptance in that PostgreSQL version;
   local runtime is neither application integration nor production evidence.
```

```text
Data repair by plain UPDATE
❌ A single UPDATE is the fix.
✅ Contain -> identify the exact affected set -> guarded UPDATE -> capture counts/RETURNING -> verify
   business recovery. And this schema lacks release/time/tenant/provenance columns for real identification.
```

```text
Type list / storage boundary (final synthesis)
❌ "jsob"; and large binary/text bytes belong in PostgreSQL.
✅ JSONB — plus uuid and timestamptz. Day28 assigns 500 MB documents and large artifacts to Object
   Storage; PostgreSQL keeps metadata and references.
```

```text
Validation ladder unknown (final synthesis said "验证等级不知道")
✅ conceptual/manual review -> tool/parser or PostgreSQL syntax acceptance -> real disposable PostgreSQL
   behavior -> application integration -> production evidence. Only the first three (plus selected
   runtime behaviors) were completed today.
```

---

# Engineering Trade-offs

```text
Write-before-202 vs respond-fast-then-write
+ Write first: 202 is a real, recoverable commitment.
- Write first: the accept path depends on database availability/latency.
- Respond first: fast, but a crash silently loses an acknowledged Job. Not acceptable.
```

```text
UUID vs integer identity
+ UUID: distributed generation, non-enumerable public identity.
- UUID: larger, weaker index locality.
+ integer: compact, sequential, index-friendly.
- integer: central generation, enumerable in public APIs.
```

```text
Typed columns vs bounded JSONB
+ Typed: defaults, constraints, indexes, joins, statistics, integrity.
- Typed: every new field is a schema change (Day36).
+ JSONB: flexible optional metadata without migrations.
- JSONB: weak integrity, awkward queries/indexes; must stay auxiliary and bounded.
```

```text
NOT NULL only vs NOT NULL + CHECK
+ NOT NULL only: simple, ships today.
- NOT NULL only: accepts empty string and `banana` -> durable garbage.
+ Adding CHECK/enum: real status integrity.
- Adding CHECK: constrains future states and needs migration discipline (Day31/Day36).
```

```text
Database defaults vs application-supplied values
+ DB defaults: one consistent contract; works even if a client forgets a field.
- DB defaults: behavior lives in the schema and is easy to overlook when reading app code.
```

```text
timestamptz vs timestamp
+ timestamptz: one absolute instant, correct across regions.
- timestamptz: does not preserve the original time-zone label (store separately if required).
- timestamp: wall-clock only; cannot identify a real moment.
```

```text
Schema qualification vs search_path
+ Qualified `app.jobs`: explicit, portable, no hidden assumptions.
- Qualified: more verbose.
+ search_path: shorter SQL.
- search_path: session-dependent and a classic "table not found" trap.
```

```text
Fast local validation vs strong evidence
+ Disposable PostgreSQL: quick, real syntax/runtime acceptance.
- Disposable PostgreSQL: proves nothing about integration, HA, backups, or production.
```

---

# Hands-on Exercises

The engineering artifact is a raw SQL schema and an honest README (see
[projects/ai-backend-data-layer/](../../projects/ai-backend-data-layer/README.md)).

## Exercise 1: Minimum Durable Facts
Question: What must be durable before `202`, and when is it written?
Expected Output: `job_id`, `job_status`, `created_at`, committed BEFORE the response.

## Exercise 2: Types and Defaults
Question: Assign PostgreSQL types/defaults to the Job model and defend UUID vs integer.
Expected Output: The Concept 3 table; UUID chosen for distributed/non-enumerable identity, with costs named.

## Exercise 3: Diagnose `app.jobs` Not Found
Question: Walk the database/schema/`search_path` boundaries.
Expected Output: `\conninfo`, `current_database()`, `SHOW search_path`, `current_schema()`, `\dn`,
`\dt app.*`, then explicit `app.jobs`.

## Exercise 4: `public` vs `app`
Question: Distinguish them without treating `public` as a data classification.
Expected Output: Both are namespaces; `public` is merely the default.

## Exercise 5: Typed Columns vs JSONB-only
Question: Compare, then classify `attempt_count`, `cancel_requested`, `provider_metadata`.
Expected Output: integer / boolean / jsonb — and "one-to-many" is cardinality, not a type (Day31).

## Exercise 6: Nullable Lifecycle Fields
Question: Interpret each NULL.
Expected Output: not started / not terminal / no recorded error / no result artifact yet.

## Exercise 7: Row Identity vs Request Identity
Question: Does the UUID primary key stop a retried request creating a second Job?
Expected Output: No — needs a stored idempotency key + DB UNIQUE + atomic upsert (Day31/Day34).

## Exercise 8: psql Session Diagnostic Checklist
Question: Build the evidence list a session must produce.
Expected Output: The Concept 2 checklist.

## Exercise 9: Validation Levels
Question: Classify conceptual / static / runtime / integration / production evidence.
Expected Output: Reading != syntax proof; executed DDL = acceptance in that version; local run !=
integration or production.

## Exercise 10: `DEFAULT VALUES` + `RETURNING`
Question: Prove the defaults came from the database.
Expected Output: `INSERT INTO app.jobs DEFAULT VALUES RETURNING *;` — every business field omitted.

## Exercise 11: `timestamptz` Across Zones
Question: Compare the same instant under UTC and Asia/Shanghai.
Expected Output: Different rendering, identical epoch.

## Exercise 12: `queud` Guarded Data Repair
Question: Simulate the misspelling, repair it safely, and verify.
Expected Output: Contain -> identify -> `UPDATE ... WHERE job_status = 'queud'` -> capture count +
RETURNING -> verify counts.

## Exercise 13: Restart Persistence
Question: Restart PostgreSQL and check the rows.
Expected Output: Rows remain — proving process-lifecycle persistence only, NOT backups/HA/production.

## Exercise 14: English Interview
Question: Answer the Beginner, Intermediate, and Senior questions.
Expected Output: See the English Interview section.

## Exercise 15: Final Chinese Mental Model
Question: Synthesize the day.
Expected Output: See Mental Model Summary, with the recorded corrections applied.

---

# Relevant Framework Connections

## PostgreSQL / psql
The core of the lesson: durable rows, a typed table contract, database-generated defaults, namespaces,
the session model, and real runtime evidence from a disposable PostgreSQL 14.18 cluster.

## FastAPI
Must persist the accepted Job **before** returning `202`. Process memory is not durable truth. FastAPI
later reads Job status/result from this table (Day30 query work).

## Kubernetes
The replaceable API Pod lifecycle is shorter than the durable Job lifecycle — the exact reason the row
must exist before the response (Day26/Day27 replaceable-compute rule).

## Redis
Transient broker/cache only, never authoritative Job state. Reused from Day28 as a boundary; **no Redis
was run in this lesson**.

## Object Storage
Owns the verified input document and large result bytes. `result_object_key` is a **reference**, not the
bytes.

## Celery
The future consumer that will claim `queued` Jobs. **Not implemented or run in Day29** — which is why the
`queud` misspelling mattered: no worker would ever claim it.

Playwright and unrelated technologies are intentionally absent.

---

# AI Backend Connections

```text
- A verified 500 MB RAG document creates an eight-minute asynchronous processing Job.
- 202 + job_id is a durable business commitment, now backed by a real PostgreSQL row.
- Core Job facts live in PostgreSQL; original and large derived bytes stay in Object Storage.
- provider_metadata may use bounded JSONB, but a frequently queried provider_request_id should be
  promoted to a typed column in a later model.
- A misspelled `queud` state produces a durable but UNCLAIMABLE Job: durability alone is insufficient
  without integrity.
- Code rollback vs persisted Job repair reuses the Day28 production-recovery model, now executed in SQL.
- The schema still cannot prevent duplicate business Jobs on a lost-202 retry (no idempotency key yet).
```

---

# English Interview

Key vocabulary: durable commitment, persist, primary key, unique identifier, idempotency key, atomic
insert/upsert, unique constraint, namespace, `search_path`, qualified name, default value, nullable,
absolute instant, guarded update, data repair.

## Beginner

Question:

Why must FastAPI persist a Job row in PostgreSQL before returning `202 Accepted`?

Actual student attempt (preserved):

> "because the durable state in postgresql,it help work to avoid repeate run job."

Correction: durable state was the right idea, but a database row alone does **not** prevent duplicate
execution.

Strong Answer:

> FastAPI must persist the Job in PostgreSQL before returning 202 Accepted because 202 represents a
> durable business commitment. If the API Pod crashes afterward, the system can still find, recover, and
> process the Job. The database row alone does not prevent duplicate execution, so idempotency controls
> are still required.

## Intermediate

Question:

What is the difference between a primary key and an idempotency key in the Job model?

Actual student attempt (preserved):

> "the primary key is produced by postgresql,and it is a only job certification. an indempotency key is produced by provider."

Correction: generation is not the definition; say "unique identifier", not "certification". A **request**
idempotency key normally comes from the client/application — provider idempotency is a separate scope.

Strong Answer:

> A primary key uniquely identifies one Job row in PostgreSQL. In our schema, PostgreSQL generates it as
> a UUID. An idempotency key identifies one business request and is usually supplied by the client or
> derived by the application. If the client retries the same request, the system uses the idempotency key
> to return the existing Job instead of creating another one.

## Senior

Question:

PostgreSQL creates a Job, the `202` response is lost, and the client retries. How do you prevent a
duplicate Job, and what limitation remains in Day29?

Actual student attempts (preserved):

> "client produce idempotency key"

> "我忘了"

Teaching note: after two attempts, the complete answer was taught directly.

Strong Answer:

> The client should provide the same idempotency key when it retries the request. I would store that key
> with the Job and enforce it with a PostgreSQL unique constraint. I would use an atomic insert or upsert
> instead of relying on a separate read-before-write check, because two concurrent requests can both
> observe that the key is missing. The request that encounters the conflict should return the existing
> Job ID after verifying that the request payload matches. Our current Day29 schema does not yet contain
> an idempotency key or a uniqueness rule, so it cannot prevent duplicate business Jobs even though every
> row has a unique primary key.

---

# Mental Model Summary

```text
Application object/state = temporary
Database row             = durable business fact
Table schema             = enforceable contract for that fact

Write the Job row BEFORE returning 202 (202 acknowledges an existing commitment)
Session connects to a DATABASE; schema resolves via qualified name or search_path
PostgreSQL Schema = namespace;  "table schema" = table definition
Typed columns = identity/state/time/counters;  bounded JSONB = optional extras;  Object Storage = bytes
UUID primary key = one ROW, not one retried business OPERATION
NULL = per-field lifecycle meaning;  DEFAULT = database-generated initial facts
NOT NULL rejects NULL only — empty string and `banana` still pass (CHECK is Day31)
timestamptz = one absolute instant, rendered in the session time zone
Durability without integrity makes WRONG facts durable
Code rollback stops future bad writes; guarded data repair fixes persisted facts
Validation claims must never exceed evidence
```

Preserve the student's actual final synthesis:

> "当客户端返回202业务承诺以后，postgresql里就生成了一个唯一的主键job_id，生成了一条postgre row。table schema对命名空间做了划分。可以让相同名字的表存在不同的命名空间中，通过设置search_path，先进行解析设置的，再一个一个寻找table。或者直接显式搜寻在查询的时候将scheme代入。数据库字段类型有文本类型、数字类型、布尔类型、jsob、还有二进制大文本等类型。null是代表未知的结果，default代表设置默认值。primary key是主键防止重复生产相同的值。database的边界是数据库名，schema是命名空间名，session边界是用户、连接的数据库等。验证等级不知道。 代码回滚不代表修复了已持久化的数据，还需要在数据库中针对数据值进行修复"

Narrow corrections to that synthesis:

```text
1. Ordering: the row is written BEFORE 202 is returned, not "after 202 the row is generated".
2. Wording: it is the PostgreSQL SCHEMA that divides namespaces; "table schema" means the table
   definition/contract. Keep the two senses separate.
3. Types: `jsob` -> JSONB; also include uuid and timestamptz. Do NOT imply large binary/text bytes belong
   in PostgreSQL — Day28 assigns 500 MB documents and large artifacts to Object Storage.
4. NULL is context-dependent (unknown / not yet occurred / not available / not applicable), not simply
   "unknown result".
5. Primary key prevents duplicate KEY VALUES, not duplicate business operations.
6. Validation ladder ("验证等级不知道"): conceptual/manual review -> parser or PostgreSQL syntax
   acceptance -> real disposable PostgreSQL behavior -> application integration -> production evidence.
   Only the first three plus selected runtime behaviors were completed.
7. Data repair is correct in direction, but production requires contain -> identify the exact affected
   set -> guarded UPDATE -> capture counts/RETURNING -> verify recovery.
```

---

# Today's Takeaway

```text
Most important mental model:
Before FastAPI returns 202, PostgreSQL must already hold the Job row. The row is a durable business
fact; the table definition is an executable contract for that fact.

Most important production risk:
Durability is not integrity. `text NOT NULL` accepted an empty string and `banana`; a `queud` row is
perfectly durable and perfectly unclaimable. Code rollback stops future bad writes but cannot repair
rows already persisted — only a guarded, evidence-capturing UPDATE can.

Most important framework/AI connection:
The accepted 500 MB RAG ingestion Job lives as a typed row (uuid/text/integer/boolean/timestamptz/bounded
jsonb) with database-generated defaults, while the document and large artifacts stay in Object Storage
behind a reference.

Most important interview answer:
A primary key identifies one row; an idempotency key identifies one business request. Day29 has the
former and not the latter, so it cannot prevent a duplicate Job on a lost-202 retry.
```

Scope honesty: Day29 deliberately stops before CHECK/UNIQUE constraints, business idempotency keys,
tenant ownership, Documents/Attempts/Events/Outbox tables, foreign keys, transactions, concurrency
control, indexes, migrations, roles, backup/restore, and operations. Those are Day31+ topics. Classroom
runtime evidence came from a disposable PostgreSQL 14.18 cluster; nothing about application integration,
high availability, backups, or production was proven. SQLAlchemy/Alembic remain Phase 4.

---

# Before Next Lesson Checklist

- [ ] Can I explain why the Job row must be committed before `202`, and what `202` actually acknowledges?
- [ ] Can I name the PostgreSQL hierarchy and say what a `psql` session connects to?
- [ ] Can I distinguish a PostgreSQL Schema (namespace) from a "table schema" (definition)?
- [ ] Can I justify UUID vs integer identity with real trade-offs, not preference?
- [ ] Can I explain which facts belong in typed columns and what bounded JSONB is for?
- [ ] Can I state what `NOT NULL` does NOT enforce, and why `banana` was accepted?
- [ ] Can I explain the difference between a primary key and an idempotency key?
- [ ] Can I explain `timestamptz` as one absolute instant and what PostgreSQL does not preserve?
- [ ] Can I list the validation ladder and say exactly which levels I have evidence for?
- [ ] Can I order a guarded data repair and explain why code rollback is insufficient?
