# Lesson 31 — Relational Modeling and Data Integrity

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day30 — SQL Data Manipulation and Query Fundamentals

Previous Lesson: [Day30 — SQL Data Manipulation and Query Fundamentals](day30-sql-data-manipulation-and-query-fundamentals.md)

Next Lesson: Day32 — SQL Joins, Aggregation, and Operational Queries (planned — see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day32 lesson file does not exist yet)

Engineering Artifact: The Day31 relational target schema (`sql/003_relational_modeling_and_data_integrity.sql`) — tenants, upload sessions, documents, extended jobs, attempts, events, outbox, artifacts, and a tenant-aware junction table — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

PostgreSQL Cheat Sheet: [cheat_sheets/postgresql.md](../../cheat_sheets/postgresql.md)

PostgreSQL Interview: [interview/postgresql.md](../../interview/postgresql.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 100-130 minutes
Hands-on DDL authoring + disposable-PostgreSQL constraint tests: 100-130 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

After completing this lesson, the student should be able to:

* Decide when a repeated fact becomes its own entity instead of columns or a JSONB array.
* Distinguish primary key (row identity), foreign key (parent), and business key (operation identity).
* Design **scoped** uniqueness — `UNIQUE (job_id, attempt_number)`, `UNIQUE (tenant_id, idempotency_key)`.
* Choose a referential action (`RESTRICT`/`CASCADE`/`SET NULL`) as a lifecycle and retention decision.
* Place a foreign key on the correct side for one-to-many, and use FK + `UNIQUE` for one-to-one.
* Model many-to-many with a junction table that can carry its own attributes.
* Enforce same-tenant relationships with tenant-aware composite foreign keys.
* Explain why foreign keys are relationship integrity and **not** authorization.
* Separate current state, append-oriented history, and durable publication intent.
* Order a failed-constraint-deployment incident: contain, reconcile, choose canonical, repair, re-validate.

The engineering artifact is a relational target schema, not application code.

---

# Why This Matters

Day30 made every read deterministic and every write guarded. It still could not stop invalid durable
facts, missing history, weak ownership, duplicate business requests, or cross-table inconsistency.

The 842-row incident proved it: reconstruction needed Attempts, Events, Artifacts, Provider state,
Outbox state, and the client-visible `job_id` — **none of which the Day29/Day30 schema modelled**.

Day31's shift:

```text
Day30: a careful WHERE predicate expresses a rule in ONE statement.
Day31: a constraint enforces that rule on EVERY write path, forever.
```

Why a backend engineer must care:

```text
Identity   -> a retry gets a NEW job_id, so job_id can never prevent duplicate business requests.
Scope      -> UNIQUE is only as correct as the columns you scope it to.
Lifecycle  -> CASCADE quietly deletes the audit and cost evidence an incident needs.
Ownership  -> tenant_id records who owns a row; composite FKs stop cross-tenant links.
Authority  -> foreign keys never authorize a reader. That is a query/session concern.
History    -> current status cannot reconstruct queued -> running -> failed -> queued -> succeeded.
Honesty    -> a passing constraint test proves that invariant, not "the system is correct".
```

---

# Roadmap Position

Knowledge continuity chain (v3.2):

```text
Previous Knowledge (Day29-Day30)
        |
        v
Current Concept (Day31: relational ownership + enforceable integrity)
        |
        v
Future Usage (Day32 joins/aggregation; Day33 atomic multi-table changes;
              Day34 concurrency-safe claims; Day35 indexes; Day36 safe migration)
```

Where Day31 sits:

```text
Day28 state ownership -> Day29 durable Job row + table contract
-> Day30 deterministic reads and guarded writes
-> Day31 relational ownership and enforceable integrity   <-- you are here
-> Day32 joins, aggregation, operational queries
-> Day33 atomic Job + Event + Outbox changes
-> Day34 concurrency-safe claims and idempotent workers
```

Day29/Day30 rules reused directly:

```text
- The Job row is committed before FastAPI returns 202.
- NOT NULL rejects NULL only; '' and 'banana' still pass without a CHECK.
- WHERE is the modification boundary; RETURNING returns rows, not a count.
- Committed rows have no automatic undo; only guarded repair fixes them.
- Large bytes stay in Object Storage; PostgreSQL holds references and provenance.
```

Future connection only: Day32 queries these relationships, Day33 makes multi-table changes atomic,
Day34 adds locking and claims, Day35 measures indexes, and **Day36 owns safe evolution of existing
data** — this lesson's DDL targets a fresh database, not a populated one.

---

# Lesson Map

```text
When a repeated fact becomes an entity (job_attempts)
  -> PK vs FK vs business key, and the SCOPE of UNIQUE
  -> Referential actions as lifecycle/retention policy
  -> One-to-many FK placement; optional one-to-one via FK + UNIQUE
  -> CHECK as the legal-state boundary (and what a row CHECK cannot see)
  -> Normalizing Result Artifacts and keeping provenance derivable
  -> Current state vs Job Events vs Outbox intent
  -> Many-to-many via a junction table with its own attributes
  -> Tenant ownership, composite FKs, and why FKs are not authorization
  -> Deploying a UNIQUE constraint onto committed duplicates
```

---

# Core Mental Model

```text
Entity       = a durable business thing with its own identity and lifecycle
Attribute    = a typed fact about that entity
Relationship = ownership/cardinality expressed by keys

PRIMARY KEY  = who this row is
FOREIGN KEY  = which parent it belongs to
BUSINESS KEY = which business operation must not repeat
UNIQUE       = the SCOPE in which facts cannot duplicate
CHECK        = which final row states are legal
RESTRICT / CASCADE / SET NULL = deletion lifecycle policy

One-to-many  = foreign key on the many side
One-to-one   = foreign key + UNIQUE
Many-to-many = junction table referencing both entities
```

A constraint is a rule the database enforces on every write path — including the paths you forget.

---

# Main Concepts

## Concept 1: When a Repeated Fact Becomes Its Own Entity

Tech Lead Question:

One Job may call an AI provider up to three times. Operations must query each Provider request ID,
start/end time, error, and cost. Columns (`attempt_1_*`, `attempt_2_*`), a JSONB array, or a new table?

Student Thinking:

A separate table can be joined back to the Job and queried in a structured way.

Student Answer:

> "建立独立的job_attempts表，因为之后可以通过primary key job_id进行关联查询，并且可以结构化的查询想查询的信息。"

Tech Lead Review:

Correct, and for the right reasons. Repeating columns do not scale (what about attempt 4?), and a JSONB
array weakens typed constraints, uniqueness, joins, and provenance.

```text
jobs 1 -> N job_attempts
```

But there is a trap in "通过 primary key job_id 进行关联查询". Asked what happens if the same Job is
inserted twice into a child table whose `job_id` **is** the primary key:

> "会覆盖之前的attempt数据"

Two corrections:

```text
1. An ordinary INSERT never overwrites. A duplicate key fails with
   23505 unique_violation. Only an explicit UPDATE or an upsert modifies a row.
2. If job_id were the child's PRIMARY KEY, it would mean "one Job has AT MOST ONE Attempt" —
   which destroys the whole point of the entity.
```

So the Attempt needs its own identity plus a scoped business rule:

```text
job_attempts.attempt_id   = the Attempt row's primary key
job_attempts.job_id       = foreign key to jobs.job_id
(job_id, attempt_number)  = the business-unique combination
attempt_number > 0        = CHECK invariant
```

Engineering Thinking:

A fact that repeats an unbounded number of times, needs its own attributes, and must be queried
independently is an **entity**, not a column family.

Production Example:

Retry #2's provider request ID and cost are queryable rows, not string surgery inside a JSONB blob.

Framework Connection:

Attempts preserve the Provider evidence the Day30 incident needed for reconciliation.

Exercise:

Decide between columns/JSONB and a separate Job Attempt entity, then predict what a duplicate insert
does when `job_id` is the child's primary key.

## Concept 2: Primary Key vs Foreign Key vs Business Key, and the Scope of `UNIQUE`

Tech Lead Question:

`attempt_id` is unique. Does that stop two Attempt rows from both claiming `attempt_number = 1` for the
same Job?

Student Thinking:

Uniqueness on the identifier should prevent duplicates.

Student Answer:

> "attempt_id设置不能重复"

Tech Lead Review:

`attempt_id` uniqueness only guarantees the two rows are **different rows**. Both can still say
"attempt number 1" for the same Job. The rule must be scoped:

```sql
UNIQUE (job_id, attempt_number)
```

Then the follow-up: could a global `UNIQUE(attempt_number)` work?

> "不能，因为就表示正列就只能出现一次。"

Correct instinct. A global rule would mean attempt number 1 may exist **once in the entire table**, so
Job B could never have its own Attempt 1 after Job A took it.

```text
Primary key  = who this row is
Foreign key  = which parent this row belongs to
Business key = which business operation must not be duplicated
UNIQUE       = the SCOPE in which a value/combination cannot repeat
```

The same distinction decides request identity. Asked which combination prevents a duplicate client
request:

> "work_id与job_id"

Correction — and this is the day's most important identity lesson:

```text
A retry receives a NEW job_id.
Therefore UNIQUE(tenant_id, job_id) can NEVER prevent duplicate business requests.

job_id                       = database ROW identity
(tenant_id, idempotency_key) = tenant-scoped client REQUEST identity
```

Different tenants may legitimately reuse the same idempotency key, which is exactly why `tenant_id` is
part of the scope.

Engineering Thinking:

Ask "unique *within what*?" before writing `UNIQUE`. The scope is the rule.

Production Example:

A client retries `POST /documents` after a lost `202`. Only `UNIQUE (tenant_id, idempotency_key)` stops
a second Job — and only if the application actually sends the key.

Framework Connection:

Day28's at-least-once + idempotency rule finally becomes a database-enforced constraint.

Exercise:

Design scoped uniqueness for Attempt numbers and for tenant-scoped idempotency.

## Concept 3: Referential Actions Are Lifecycle Policy

Tech Lead Question:

Deleting a Job that has Attempts — `RESTRICT`, `CASCADE`, or `SET NULL`?

Student Thinking:

`RESTRICT` makes the delete fail, and `SET NULL` conflicts with a `NOT NULL` `job_id`, so cascade.

Student Answer:

> "CASCADE，因为RESTRICT会直接导致这次删除job失败。set null与现在的已经job_id冲突"

Tech Lead Review:

The SQL mechanics are exactly right — `SET NULL` is impossible on a `NOT NULL` column, and `RESTRICT`
does block the delete. But the **lifecycle** conclusion is risky.

```text
Attempts hold Provider request IDs, errors, and cost evidence.
CASCADE means one accidental parent delete reliably ERASES the evidence an audit or
incident reconstruction depends on.
```

Classroom decision for this model:

```text
Job     -> Attempt          : ON DELETE RESTRICT
Job     -> Event            : ON DELETE RESTRICT
Job     -> Outbox           : ON DELETE RESTRICT
Attempt -> Result Artifact  : ON DELETE RESTRICT
```

No action is universally best:

```text
CASCADE  is right when the child has no independent retention/audit value and an explicit
         business lifecycle deletes the whole aggregate.
SET NULL is right only when an orphaned child still has real business meaning AND the
         foreign-key column is nullable.
RESTRICT is right when the child is evidence.
```

Engineering Thinking:

`ON DELETE` is not a convenience setting — it encodes what your organization is allowed to lose.

Production Example:

"We deleted a test Job" quietly removing three Provider charge records is a compliance problem, not a
tidy database.

Framework Connection:

This protects exactly the Attempts/Events the Day30 incident required.

Exercise:

Choose and defend a referential action for audit- and cost-bearing Attempts.

## Concept 4: Foreign-key Placement, and Optional One-to-one

Tech Lead Question:

One Document can initially create several Jobs. Which side holds the foreign key? And an Upload Session
may expire without producing a Document — how do you model that?

Student Thinking:

The Job refers to the Document it processes.

Student Answers:

> "job表，应该引用Document_id"

> (one-to-one direction) "外键放在Upload Session"

Tech Lead Review:

The first answer is right: for one-to-many, the foreign key goes **on the many side**.

```text
documents 1 -> N jobs
jobs.document_id -> documents.document_id
```

(That interim model is later replaced by `job_documents` in Concept 8, once Jobs may consume multiple
Documents. Do not silently drop a legacy column — Day36 owns the compatible removal sequence.)

The one-to-one direction needs a correction. Putting `document_id` on the Upload Session *can* express
the cardinality with a nullable unique reference, but it makes the **earlier** entity hold a
**forward/reverse pointer to a future row**. Recording the FK on the later-created Document captures
provenance naturally:

```sql
documents.upload_session_id NOT NULL
    REFERENCES upload_sessions(upload_session_id)
UNIQUE (upload_session_id)
```

Cardinality mental model:

```text
FOREIGN KEY alone          = many-to-one
FOREIGN KEY + UNIQUE       = one-to-one
nullable FK + UNIQUE       = optional one-to-one from the referencing row's perspective
```

Here every Document must have a source session (`NOT NULL`), while a session may still expire with no
Document — the optionality lives on the session side by simply having no child row.

Engineering Thinking:

Place the foreign key where the fact is *learned*. The Document learns its origin; the session does not
know its future.

Production Example:

An abandoned 500 MB upload leaves an `expired` Upload Session and no Document — no nullable pointer to
clean up.

Framework Connection:

This is Day28's Upload Session vs Job lifecycle separation, now expressed as keys.

Exercise:

Place a Document foreign key on the correct side, and model optional one-to-one Upload Session ->
Document.

## Concept 5: `CHECK` — the Legal-state Boundary (and What a Row `CHECK` Cannot See)

Tech Lead Question:

Day29 proved `NOT NULL` accepts `''` and `banana`. How do you make the database reject them?

Student Thinking:

Keep a list of legal statuses and test membership.

Student Answer:

> "我会使用allowlist，比如说将合法状态做成一个列表，判断参数表示的状态是否在这个列表里"

Tech Lead Review:

Right idea. The correction is **where** the allowlist lives:

```text
Application allowlist -> better error messages, one code path
Database CHECK        -> enforced on EVERY write path, including migrations, scripts,
                         psql sessions, and code you have not written yet
```

```sql
CHECK (job_status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled'))
```

```text
NOT NULL          -> the state EXISTS
NOT NULL + CHECK  -> the state exists AND belongs to the legal set
```

Then the cross-column rule. Asked what must be true when a Job is `succeeded`:

> "可以像上面的一样设置约束条件，比如为succeed的job_status,finished_atfinished_at与finished_at不能为null"

(The repeated field is read as the intended `finished_at` + `result_object_key` non-NULL rule.) The
interim teaching example was:

```sql
CHECK (
    job_status <> 'succeeded'
    OR (finished_at IS NOT NULL AND result_object_key IS NOT NULL)
)
```

**Important final-model correction.** After normalization (Concept 6), Result Artifacts live in a child
table and `jobs.result_object_key` is no longer the canonical target. And a row-level `CHECK` can only
inspect **this row** — it cannot assert that a child Artifact row exists. So the target keeps only:

```sql
CHECK (job_status <> 'succeeded' OR finished_at IS NOT NULL)
```

The "succeeded implies an artifact exists" coherence must come from the Day33 transactional workflow
plus operational verification.

Finally, a `CHECK` validates whether a **final row** is self-consistent. It does not replace Day30's
transition guards: a legal `queued` row could still be an illegal transition **from** `succeeded`
unless the current state is part of the guarded `UPDATE`.

Engineering Thinking:

Constraints answer "is this row legal?"; guarded predicates answer "was this change legal?" You need both.

Production Example:

A one-off migration script bypasses the API but cannot bypass the `CHECK`.

Framework Connection:

This closes the `banana` gap Day29 documented and Day30 could only work around.

Exercise:

Translate a status allowlist into a PostgreSQL `CHECK`, then describe a succeeded-state cross-field
invariant and its limits.

## Concept 6: Normalizing Result Artifacts and Keeping Provenance Derivable

Tech Lead Question:

One successful Job generates summary JSON, an embedding manifest, and an audit PDF. Do you add
`result_object_key_2`, `_3`? And which parent should an Artifact reference?

Student Thinking:

Multiple results means a separate table; the Attempt produced them.

Student Answers:

> "建立独立的result_artifacts，一对多，一个job对应多个result_object_key"

> (provenance) "Attempts的Attempts_id"

> (normalization) "只保存attempt_id，因为job_id可以推导"

Tech Lead Review:

All three correct — the third one especially. Unbounded repeating columns are the same anti-pattern as
`attempt_1_*`. The final chain is:

```text
Job 1 -> N Attempts
Attempt 1 -> N Result Artifacts
```

And the normalization decision is exactly right:

```text
Store attempt_id ONCE
-> derive job_id through job_attempts
-> accept the JOIN until representative measurements prove it is a real problem
```

Why storing both `job_id` and `attempt_id` without a composite constraint is worse: it permits
**contradictory ownership** — `artifact.job_id = A` while `artifact.attempt_id` belongs to Job B. A
duplicated fact that can disagree with itself is a bug generator.

```text
Denormalize only for a MEASURED access problem,
and then add an invariant that keeps the duplicated facts consistent.
```

`result_artifacts` stores Artifact identity, type, Object Storage key, content type, size/checksum, and
creation time. PostgreSQL keeps references and provenance; Object Storage keeps the bytes.

Engineering Thinking:

Normalize by default. Denormalization is a purchase you make with measurement, and the price is an
extra invariant.

Production Example:

Three artifacts from retry #3 are three rows, each traceable to the exact Provider call that produced it.

Framework Connection:

Day28's Object Storage boundary holds: no large bytes in PostgreSQL, ever.

Exercise:

Normalize multiple Result Artifacts, preserve Attempt provenance, and justify `attempt_id` alone over
redundant `job_id + attempt_id`.

## Concept 7: Current State, Lifecycle History, and Outbox Intent

Tech Lead Question:

`jobs.job_status` is fast to read. Can it reconstruct
`queued -> running -> failed -> queued -> running -> succeeded`? And who owns the duty to publish a
queue message?

Student Thinking:

History needs its own table; the outbox belongs to the database.

Student Answers:

> "建立独立的job_events，根据生命周期记录status的变化"

> (outbox) "发件箱，由postgresql持有"

Tech Lead Review:

Both correct. Three **different** things are easy to conflate:

```text
jobs.job_status = what is true NOW          (fast API reads)
job_events      = HOW the Job got there     (append-oriented business history)
outbox_events   = what MUST be published    (durable integration intent)
```

A current-state snapshot is destroyed by every transition; only an append-oriented history can replay
the path.

`job_events` holds event identity, Job, **optional** Attempt provenance, event type, from/to status,
actor, time, and bounded metadata. If it stores both `job_id` and an optional `attempt_id`, the model
must guarantee a non-NULL Attempt belongs to that **same** Job — via a composite candidate key on
Attempts plus a composite foreign key:

```sql
FOREIGN KEY (job_id, attempt_id)
    REFERENCES app.job_attempts(job_id, attempt_id)
```

(With the default `MATCH SIMPLE`, a NULL `attempt_id` leaves the reference unenforced — exactly the
"optional provenance" behaviour wanted.)

And the Outbox boundary:

```text
job_events    = business lifecycle history: what happened
outbox_events = durable integration intent: what must be published
PostgreSQL owns the durable Outbox row. Redis/Queue is TRANSPORT, not the authoritative
record that a message must be sent.
```

Day33 will change Job state and insert Job/Outbox Events atomically. A relay that crashes after
publishing but before setting `published_at` may publish twice, so consumers stay idempotent — that
messaging design belongs to a later lesson and is not expanded here.

Engineering Thinking:

Separate "now", "how", and "must tell others". Collapsing them is how systems lose their audit trail.

Production Example:

Reconstructing the 842-row incident requires `job_events`; `jobs.job_status` alone shows only the damage.

Framework Connection:

This is Day28's Transactional Outbox, now with a real table and a real owner.

Exercise:

Separate current Job state, append-oriented Job history, and durable Outbox intent.

## Concept 8: Many-to-many Job Inputs

Tech Lead Question:

A comparison Job consumes multiple Documents, and one Document is reused by many Jobs. Model it.

Student Thinking:

A correspondence table between the two IDs.

Student Answer:

> "需要document_id与job_id.中间表是document_id与job_id的对应关系的表"

Tech Lead Review:

Correct. A many-to-many relationship becomes a **junction table**, which decomposes into two
one-to-many relationships:

```text
jobs      1 -> N job_documents
documents 1 -> N job_documents
```

Minimum key:

```sql
PRIMARY KEY (job_id, document_id)
```

The important addition: a relationship can carry its **own** business attributes. `document_role`
(`input`, `reference`, `baseline`) and `input_order` describe the *link*, not the Job and not the
Document — so they belong on the junction table.

This also supersedes the earlier direct `jobs.document_id` model from Concept 4. That legacy column is
**not** silently dropped; the compatible removal sequence is Day36.

Engineering Thinking:

When a fact belongs to neither entity alone, it belongs to the relationship.

Production Example:

"Compare document A (baseline) against B and C (candidates), in that order" is fully expressible.

Framework Connection:

A RAG comparison Job is the concrete AI-backend case for many-to-many inputs.

Exercise:

Model many-to-many Job <-> Document with a junction table, and place relationship attributes correctly.

## Concept 9: Tenant Ownership, Composite Foreign Keys, and Why FKs Are Not Authorization

Tech Lead Question:

Is a `tenant_id` column on Jobs and Documents enough to guarantee a Job never links to another tenant's
Document?

Student Thinking:

Add a Tenant table and tenant foreign keys on both sides.

Student Answer:

> "不够，生成一个包含一个tenant表，并且job表和Document表包含外键tenant_id"

Tech Lead Review:

Right that it is not enough, and the Tenant table is correct — but tenant columns alone still permit a
junction row linking a **valid** Tenant-A Job to a **valid** Tenant-B Document. Both foreign keys pass;
neither checks that the two agree.

Database-enforced same-tenant relationship:

```text
Parent candidate keys:
    UNIQUE (tenant_id, job_id)
    UNIQUE (tenant_id, document_id)

job_documents carries tenant_id and uses COMPOSITE foreign keys:
    FOREIGN KEY (tenant_id, job_id)      -> jobs(tenant_id, job_id)
    FOREIGN KEY (tenant_id, document_id) -> documents(tenant_id, document_id)
```

Now a cross-tenant link is rejected by PostgreSQL, because one `tenant_id` value must satisfy both
references simultaneously.

Then the sharpest correction of the day. Asked whether those composite foreign keys also prevent
cross-tenant **reads**:

> "能阻止，因为作为外键已经对租户与document进行绑定了"

No:

```text
Composite foreign keys = relationship INTEGRITY during WRITES
Authorization          = whether the CURRENT CALLER may read/write this tenant's rows
```

A `SELECT` with no tenant predicate happily returns another tenant's rows — the foreign keys were
satisfied when the data was written, and they say nothing about who is asking now.

The student corrected this immediately when pushed:

> "不安全，还缺少tenant_id"

Tenant-scoped queries need both the resource and the tenant predicate, with `tenant_id` derived from
**authenticated server-side context** — never blindly from client input:

```sql
WHERE tenant_id = $1 AND document_id = $2
```

And note the layering: Day30 proved parameterized SQL stops a value from changing SQL **structure**; it
does not authorize. PostgreSQL RLS or restricted roles can add defense in depth, but RLS/role operations
were **not taught or validated** in Day31 and remain future production security work.

Engineering Thinking:

Integrity answers "may these rows be related?" Authorization answers "may this caller see them?" Two
different questions, two different mechanisms.

Production Example:

A tenant-scoped list endpoint that forgets `tenant_id = $1` leaks across tenants even with perfect
foreign keys.

Framework Connection:

FastAPI must derive `tenant_id` from the authenticated session, not from a request body field.

Exercise:

Prevent cross-tenant Job-Document relationships with composite foreign keys, then distinguish relational
integrity from query authorization.

## Concept 10: Deploying a `UNIQUE` Constraint onto Committed Duplicates

Tech Lead Question:

Production already contains two Jobs for the same `(T1, K1)`. `ALTER TABLE ... ADD CONSTRAINT
UNIQUE(tenant_id, idempotency_key)` fails. What now?

Student Thinking:

Do not blindly delete — undo the second one.

Student Answer:

> "不会，J2进行回滚"

Tech Lead Review:

Rejecting blind deletion is right. But "roll back J2" is the wrong instrument:

```text
Uncommitted INSERT   -> a transaction ROLLBACK can cancel it
Already committed J2 -> CANNOT be rolled back; it requires explicit, reconciled data repair
```

And J2 is **not automatically the loser**. J1 may be an empty shell while J2 carries the Provider calls,
cost, Artifacts, and the `job_id` the client actually received.

Asked what evidence decides which Job is canonical, the student answered correctly:

> "Job Attempts, Job Events, Result Artifacts, Outbox 发布状态, Provider request/status, 客户端实际看到的 job_id"

Final incident order:

```text
contain new duplicate creation
-> preserve the conflict and constraint-failure evidence
-> reconcile J1/J2 using Attempts, Events, Artifacts, Outbox state, Provider state,
   and the client-visible job_id
-> choose the canonical Job from business evidence
-> guarded repair/cancel/archive/delete of verified subsets, preserving required evidence
-> verify no conflicting pairs remain
-> add the UNIQUE constraint
-> verify same-tenant duplicates fail and different-tenant key reuse succeeds
```

Two honest boundaries:

```text
A failed ALTER TABLE ... ADD CONSTRAINT does NOT partially protect the table, and it does not
decide which historical row is correct.

Application rollback stops future bad writes; it does not repair committed rows.
```

Engineering Thinking:

A constraint is a promise about the future. Deploying it onto a populated table is a **data** problem
first and a DDL problem second.

Production Example:

This is why the Day31 artifact targets a fresh database — applying it to existing rows is Day36's
expand/backfill/validate/switch/contract work, not an `ALTER TABLE` away.

Framework Connection:

Same discipline as Day29's `queud` repair and Day30's 842-row incident: contain, reconcile, repair,
verify.

Exercise:

Solve a failed `UNIQUE` deployment against committed duplicate Jobs using containment, reconciliation,
canonical selection, guarded repair, and re-validation.

## Concept 11: Writing the `job_attempts` DDL

Tech Lead Question:

Write the minimum `app.job_attempts` table.

Student Answer (preserved exactly):

```sql
create table app.job_attempts attempt_id uuid primary key gen_random_uuid,job_id uuid reference on (app.jobs.job_id) on delete restrict,attempt_number integer,uniq(job_id,attempt_number) check(attempt_number>0);
```

Tech Lead Review:

**The relationship model is complete and correct.** The student selected every required kind of rule:
a primary key, a foreign key, `RESTRICT`, composite uniqueness, and a positive-number `CHECK`. The
errors were pure SQL syntax, not modelling:

```text
missing table parentheses           -> CREATE TABLE app.job_attempts ( ... )
gen_random_uuid                     -> DEFAULT gen_random_uuid()
reference on (app.jobs.job_id)      -> REFERENCES app.jobs(job_id)
job_id had no NOT NULL              -> NOT NULL
uniq(...)                           -> UNIQUE (...)
missing commas between definitions  -> comma-separate columns and table constraints
```

Corrected minimum artifact:

```sql
CREATE TABLE app.job_attempts (
    attempt_id uuid
        PRIMARY KEY
        DEFAULT gen_random_uuid(),

    job_id uuid
        NOT NULL
        REFERENCES app.jobs(job_id)
        ON DELETE RESTRICT,

    attempt_number integer
        NOT NULL,

    CONSTRAINT job_attempts_job_number_unique
        UNIQUE (job_id, attempt_number),

    CONSTRAINT job_attempts_number_positive
        CHECK (attempt_number > 0)
);
```

Engineering Thinking:

Getting the *model* right is the hard part; syntax is mechanical and the parser will tell you.

Exercise:

Write the minimum `app.job_attempts` DDL and review its exact syntax.

---

# Common Misconceptions

## Mental Model Evolution (Day30 -> Day31)

```text
Initial: "Day30 gave safe parameterized reads and guarded writes, so the data layer is safe."
Reasoning: WHERE bounds every modification and RETURNING proves what happened.
Correction: A careful predicate expresses a rule in ONE statement. It cannot stop invalid states,
            duplicate business requests, cross-tenant links, missing history, or contradictory
            ownership on the write paths you did not write. The 842-row incident needed Attempts,
            Events, Artifacts, Outbox and Provider evidence that the schema never modelled.
Final: Model entities, cardinality and ownership with keys; let PostgreSQL enforce identity scope,
       legal states and same-tenant relationships on EVERY write path — while remembering that
       constraints are integrity, not authorization, and that a passing constraint test proves only
       that invariant.
```

## Misconception list

```text
Child primary key
❌ job_attempts.job_id can be the primary key.
✅ That means "at most one Attempt per Job". Attempt needs its own attempt_id PK plus a job_id FK.
```

```text
Duplicate insert behaviour
❌ Re-inserting the same primary key overwrites the old row.
✅ An ordinary INSERT fails with 23505 unique_violation; only UPDATE/upsert modifies a row.
```

```text
Identity uniqueness vs business uniqueness
❌ A unique attempt_id prevents duplicate attempt numbers.
✅ Use UNIQUE(job_id, attempt_number). Row identity and business identity are different rules.
```

```text
Uniqueness scope
❌ UNIQUE(attempt_number) is fine.
✅ That is global — Job B could never have its own Attempt 1. Always ask "unique within what?".
```

```text
Request identity
❌ tenant/work id + job_id prevents duplicate requests.
✅ A retry generates a NEW job_id. Use UNIQUE(tenant_id, idempotency_key); different tenants may
   reuse the same key.
```

```text
Referential action
❌ CASCADE is preferable because RESTRICT makes the delete fail.
✅ The action encodes lifecycle/retention. CASCADE on audit/cost-bearing children reliably erases
   the evidence incidents need. RESTRICT here; CASCADE/SET NULL only where genuinely appropriate.
```

```text
Status integrity
❌ An application allowlist is enough.
✅ Application validation improves errors; a database CHECK protects every write path, including
   migrations, scripts and psql sessions.
```

```text
Row CHECK reach
❌ A CHECK can assert that a succeeded Job has a Result Artifact row.
✅ A row CHECK sees only THIS row. Child-row coherence is Day33 transactional work plus operational
   verification.
```

```text
Artifact provenance
❌ Storing job_id and attempt_id on an Artifact is automatically better for querying.
✅ It repeats a derivable fact and permits contradictory ownership. Normalize until measurement
   justifies denormalization, then constrain the duplicate.
```

```text
One-to-one direction
❌ Put the optional Document pointer on the earlier Upload Session.
✅ Possible, but documents.upload_session_id NOT NULL UNIQUE records provenance on the row that
   actually learns it.
```

```text
Tenant columns
❌ tenant_id on parent tables stops cross-tenant junction rows.
✅ Both plain FKs pass independently. Use tenant-aware composite candidate keys and composite FKs.
```

```text
Foreign keys and access
❌ Composite foreign keys prevent cross-tenant SELECT.
✅ Foreign keys enforce relationship integrity during writes, never authorization. Reads need a
   trusted, server-derived tenant predicate (RLS/roles are future work).
```

```text
Committed duplicates
❌ An already committed duplicate Job can be "rolled back".
✅ ROLLBACK applies only before COMMIT. Committed rows need reconciliation and explicit guarded
   repair — and the newer row is not automatically the loser.
```

```text
Validation scope
❌ Passing constraint tests prove the system's integrity.
✅ They prove the executed invariants in the executed schema at the executed level — not atomicity,
   concurrency, integration, migration safety, performance, or production correctness.
```

---

# Engineering Trade-offs

```text
Separate entity vs columns vs JSONB array
+ Entity: typed constraints, scoped uniqueness, joins, per-row provenance.
- Entity: more tables and joins.
- Columns: unbounded repetition (attempt_4_*), impossible to constrain.
- JSONB array: flexible, but weak typing/uniqueness/joins/provenance.
```

```text
RESTRICT vs CASCADE vs SET NULL
+ RESTRICT: protects audit/cost evidence; forces an explicit lifecycle decision.
- RESTRICT: deletes fail until children are handled.
+ CASCADE: clean aggregate deletion.
- CASCADE: silently destroys evidence on an accidental parent delete.
+ SET NULL: keeps a meaningful orphan.
- SET NULL: requires a nullable FK and an orphan that actually means something.
```

```text
Normalized attempt_id vs redundant job_id + attempt_id
+ Normalized: one authoritative fact; ownership cannot contradict itself.
- Normalized: an extra JOIN to reach the Job.
+ Redundant: fewer joins for Job-scoped artifact queries.
- Redundant: two facts that can disagree unless a composite constraint forbids it — and you owe
  measurement before paying that price.
```

```text
Current status column vs event history
+ Status column: O(1) API reads.
- Status column: destroyed on every transition; cannot replay a path.
+ Events: full reconstruction and incident evidence.
- Events: more writes and storage; needs its own retention policy.
```

```text
Row CHECK vs transactional invariant
+ CHECK: enforced on every write path, cheap, always on.
- CHECK: cannot see other rows or tables.
+ Transaction (Day33): can make multi-table facts coherent.
- Transaction: only as good as the code paths that use it.
```

```text
Composite tenant FKs vs application-only tenant checks
+ Composite FKs: the database rejects cross-tenant links unconditionally.
- Composite FKs: wider keys and an extra tenant column on junction tables.
+ Application checks: flexible.
- Application checks: every forgotten code path is a data-integrity hole.
```

```text
Constraints vs authorization
+ Constraints: absolute, write-time integrity.
- Constraints: say nothing about who may read.
+ Tenant-scoped queries / RLS: control access.
- Application-only scoping: one missing predicate leaks data.
```

```text
Target schema vs safe migration
+ Target schema: expresses the correct end state clearly.
- Target schema: NOT NULL additions fail on populated tables; needs Day36's expand/backfill/
  validate/switch/contract sequence for real data.
```

---

# Hands-on Exercises

The engineering artifact is the relational target schema (see
[projects/ai-backend-data-layer/](../../projects/ai-backend-data-layer/README.md)).

## Exercise 1: Entity or Columns?
Question: Model up to three Provider attempts per Job.
Expected Output: A `job_attempts` entity; repeating columns and JSONB arrays lose typing, uniqueness,
joins and provenance.

## Exercise 2: Duplicate Child Insert
Question: What happens when the same Job is inserted twice into a child whose `job_id` is the PK?
Expected Output: `23505 unique_violation` — no overwrite; and `job_id` as PK wrongly caps the Job at one
Attempt.

## Exercise 3: Scoped Attempt Uniqueness
Question: Stop two Attempts claiming number 1 for the same Job.
Expected Output: `UNIQUE (job_id, attempt_number)`; a global `UNIQUE(attempt_number)` is wrong.

## Exercise 4: Referential Action
Question: Choose and defend `ON DELETE` for audit/cost-bearing Attempts.
Expected Output: `RESTRICT`; `SET NULL` impossible on a `NOT NULL` FK; `CASCADE` erases evidence.

## Exercise 5: One-to-many FK Placement
Question: One Document, many Jobs — which side holds the key?
Expected Output: The many side (`jobs.document_id`), later superseded by `job_documents`.

## Exercise 6: Tenant-scoped Idempotency
Question: Prevent a retried client request from creating two Jobs.
Expected Output: `UNIQUE (tenant_id, idempotency_key)`; `job_id` changes on retry; different tenants may
reuse a key.

## Exercise 7: Status Allowlist as a CHECK
Question: Reject `''` and `banana` at the database.
Expected Output: `CHECK (job_status IN ('queued','running','succeeded','failed','cancelled'))`.

## Exercise 8: Succeeded Cross-field Invariant
Question: What must be true for a succeeded Job, and what can a row CHECK not assert?
Expected Output: `finished_at IS NOT NULL`; a row CHECK cannot require a child Artifact row (Day33).

## Exercise 9: Normalize Result Artifacts
Question: Model several artifacts per Attempt with provenance.
Expected Output: `result_artifacts` referencing `attempt_id`; Object Storage keeps the bytes.

## Exercise 10: attempt_id Only vs job_id + attempt_id
Question: Justify the normalized choice without performance evidence.
Expected Output: `job_id` is derivable; storing both can contradict; denormalize only on measurement,
then constrain.

## Exercise 11: State vs History vs Intent
Question: Separate `jobs.job_status`, `job_events`, and `outbox_events`.
Expected Output: now / how / must-publish; PostgreSQL owns the Outbox row, the Queue is transport.

## Exercise 12: Optional One-to-one
Question: Model Upload Session -> Document.
Expected Output: `documents.upload_session_id NOT NULL` + `UNIQUE`; an expired session simply has no
child.

## Exercise 13: Many-to-many
Question: Model a comparison Job consuming several Documents.
Expected Output: `job_documents` with `PRIMARY KEY (job_id, document_id)` plus relationship attributes.

## Exercise 14: Cross-tenant Prevention
Question: Stop a Tenant-A Job linking a Tenant-B Document.
Expected Output: Parent candidate keys `(tenant_id, job_id)` / `(tenant_id, document_id)` and composite
FKs from the junction table.

## Exercise 15: Integrity vs Authorization
Question: Do those composite FKs prevent cross-tenant reads?
Expected Output: No — FKs are write-time integrity; reads need a trusted tenant predicate.

## Exercise 16: Failed UNIQUE Deployment
Question: Two committed Jobs share `(T1, K1)`. Deploy the constraint.
Expected Output: contain -> preserve evidence -> reconcile -> choose canonical -> guarded repair ->
verify -> add constraint -> re-validate both directions.

## Exercise 17: Write the DDL
Question: Write the minimum `app.job_attempts` table.
Expected Output: PK + `NOT NULL` FK with `RESTRICT` + `UNIQUE (job_id, attempt_number)` +
`CHECK (attempt_number > 0)`.

## Exercise 18: Constraint Tests
Question: Run selected positive and negative cases in disposable PostgreSQL.
Expected Output: Assert the **specific** SQLSTATE (`23505`, `23514`, `23503`), never "any error".

## Exercise 19: English Interview
Question: Answer the Beginner, Intermediate, and Senior questions.

## Exercise 20: Final Chinese Mental Model
Question: Synthesize entities, keys, cardinality, tenancy, rollback boundaries, and validation scope.

---

# Relevant Framework Connections

## PostgreSQL
Primary keys, foreign keys, candidate keys, `NOT NULL`, `UNIQUE`, `CHECK`, composite foreign keys,
referential actions, DDL failure behaviour, constraint runtime behaviour, normalized relations, and
tenant integrity. Only the indexes implied by PK/UNIQUE exist — measured indexing is Day35.

## FastAPI
`tenant_id` must come from **authenticated server-side context**, never a client-supplied body field.
Tenant-scoped query predicates are an authorization boundary. The API still writes a durable Job before
`202` and supplies a client idempotency key so `UNIQUE (tenant_id, idempotency_key)` can do its work.

## Celery / Queue
The Queue is transport. It does not own durable Job or Outbox truth. A relay publishes unsent Outbox
rows; duplicate delivery remains possible, so consumers require the idempotency design of a later lesson.

## Object Storage
Large source and result bytes stay outside PostgreSQL. Document and Result Artifact rows hold typed
references, checksums, sizes, and provenance.

## AI Provider
Job Attempts preserve Provider request/status/cost evidence needed for retries, reconciliation, and
incident response — which is precisely why those rows are protected by `ON DELETE RESTRICT`.

PostgreSQL runtime in class was local and disposable; no container was used. No Playwright, GitHub
Actions, Docker, or Kubernetes content belongs in this lesson.

---

# AI Backend Connections

```text
- A 500 MB upload has its own Upload Session lifecycle before it becomes a verified Document.
- One Document can feed many Jobs; a comparison/RAG Job can consume many Documents.
- A Job may call the Provider several times; Attempts preserve exact retry/cost/error provenance.
- One Attempt may produce several Object Storage Artifacts without putting large bytes in PostgreSQL.
- Job Event history supports incident reconstruction; current status alone cannot.
- Outbox rows preserve the duty to publish queue messages when Redis/Queue or the API process fails.
- Tenant-aware composite foreign keys prevent cross-tenant relationships; authorization still scopes reads.
- Idempotency uses tenant + client request identity, never database row identity.
```

---

# English Interview

Key vocabulary: entity, attribute, relationship, cardinality, primary key, foreign key, candidate key,
business key, composite key, junction/association table, referential integrity, referential action,
normalization, denormalization, tenant isolation, provenance, authorization.

## Beginner

Question:

What is the difference between a primary key and a foreign key in a relational database?

Actual student attempt (preserved):

> "primary key means same value can't insert twice,foreign key means column comes from othrer schema"

Technical review: primary-key uniqueness was recognized, but a primary key also cannot be NULL and
**identifies** the row. A foreign key references a primary or unique candidate key in another table — or
the same table — and enforces referential integrity; it does not mean "another schema".

Strong Answer:

> A primary key uniquely identifies each row in a table. Its values must be unique and cannot be null.
> A foreign key references a primary or unique key in another table and enforces referential integrity,
> so a child row cannot reference a parent row that does not exist.

## Intermediate

Question:

Why do we need both `UNIQUE(tenant_id, idempotency_key)` and a primary key on `job_id`?

Actual student attempt (preserved):

> "because UNIQUE (tenant_id, idempotency_key) means tenant_id bond on idempotency_key,the consist can't appear more than once in table.the truth is that a tenant can't request twice in same job_id.there are some problems,for example,different tenant_id also could bond idempotency_key."

Technical review: scoped combination uniqueness and cross-tenant key reuse were both recognized. The
correction is the key one: a duplicate request produces a **different** `job_id`, which is exactly why a
separate business-key constraint is required.

Strong Answer:

> The primary key on `job_id` uniquely identifies one database row. It does not prevent duplicate
> business requests because each retry can generate a new `job_id`. The unique constraint on
> `(tenant_id, idempotency_key)` identifies a client request within one tenant and prevents that request
> from creating multiple Jobs. Different tenants may reuse the same idempotency key because the
> uniqueness scope includes `tenant_id`.

## Senior

Question:

Why are separate Job and Document foreign keys insufficient for tenant isolation, and how would you
enforce the rule in PostgreSQL?

Actual student attempt (preserved):

> "it must add some constraint about uniquely identifies (Tenant_id,job_id),(Tenant_id,document_id) on sperate table,we can create a inner table"

Technical review: the technical direction was correct. Vocabulary corrections: "junction/association
table" (not "inner table"), "separate" (not "sperate"), parent **composite candidate keys**, and
**tenant-aware composite foreign keys**.

Strong Answer:

> Separate foreign keys only prove that the Job and Document exist. They do not prove that both rows
> belong to the same tenant. I would add `tenant_id` to the junction table, define unique
> tenant-and-resource keys on the parent tables, and use composite foreign keys from
> `(tenant_id, job_id)` and `(tenant_id, document_id)`. PostgreSQL will then reject any cross-tenant
> relationship. This enforces relational integrity, but request authorization still requires
> tenant-scoped queries or database row-level security.

---

# Mental Model Summary

```text
Entity          = a durable business thing with its own identity and lifecycle
Attribute       = a typed fact about that entity
Relationship    = ownership/cardinality expressed by keys

PRIMARY KEY     = who this row is
FOREIGN KEY     = which parent it belongs to
BUSINESS KEY    = which business operation must not repeat
UNIQUE          = the scope in which facts cannot duplicate
CHECK           = which final row states are legal
RESTRICT / CASCADE / SET NULL = deletion lifecycle policy

One-to-many     = foreign key on the many side
One-to-one      = foreign key + UNIQUE
Many-to-many    = junction table with foreign keys to both entities

Normalization   = store one authoritative fact and derive relationships through joins
Denormalization = duplicate only for measured need, and constrain the duplicate

Tenant column   = records ownership
Composite FK    = enforces same-tenant relationships
Authorization   = decides whether the current caller may access the tenant's rows

Job status      = current snapshot
Job Event       = append-oriented business history
Outbox Event    = durable publication intent
Queue           = transport
Result Artifact = Object Storage reference + provenance, never the large bytes

Application rollback = stops future writes from the reverted code
Transaction rollback = cancels UNCOMMITTED transaction changes
Committed repair     = reconcile evidence, then explicitly repair verified rows

Constraint success proves only the executed invariant at the executed validation level.
```

Preserve the student's actual final synthesis:

> "Day30的安全sql只是概念没有实际验证，实体之间可以通过设置各自的PK，并使用其他表的FK，并在实体中设置unique，将当前的PK与FK进行组合绑定。使用CHECK检查数据是否合理。一对多表示一个表中的一行数据，是另外一张表里面多行的共同来源。多对多，表示实体之间互相为多对多，一个表中的一行数据是另外一个表的多行来源，另外一个表的一行数据是这个表的多行来源。租户隔离的意思是不能跨租户去插入数据，以及查询的时候还需要设置查询条件限制读取。区别在于代码回滚，只是回滚应用的代码，一般可以停止当前的代码防止错误影响扩大，事物回滚是在没有commit的时候未成为state，如果成为state则事务回滚就没意义。已提交数据修复需要结合其他的业务结果、状态、还有queue的推送状态等综合判断分析再做具体的修复。本次实际证明了完整性没有证明原子性"

Narrow corrections to that synthesis:

```text
1. Day30 was not "only conceptual": it had classroom/manual review and static file review. What it
   lacked was PostgreSQL or Python-driver EXECUTION of its operations pack. Day29's DDL did have
   separate PostgreSQL 14.18 runtime evidence.
2. Do not describe UNIQUE as generally combining "the current PK and FK". Each constraint expresses a
   specific invariant. Composite candidate keys and composite foreign keys are used when the invariant
   spans tenant + resource identity.
3. Uncommitted changes DO exist inside their own transaction — they are simply not committed durable
   facts for other transactions. ROLLBACK cancels them; after COMMIT, use explicit reconciled repair.
4. The runtime proved SELECTED integrity rules in a REDUCED schema — not all integrity, and not
   atomicity, integration, migration safety, concurrency, performance, or production correctness.
   ("证明了完整性" overstates it; "证明了所执行的那些完整性规则" is accurate.)
```

---

# Today's Takeaway

```text
Most important mental model:
A guarded predicate expresses a rule in one statement; a constraint enforces it on every write path,
forever. Model entities, cardinality and ownership with keys, and let PostgreSQL reject what must never
become durable.

Most important production risk:
Uniqueness is only as correct as its SCOPE, and a retry always brings a new job_id — so only
(tenant_id, idempotency_key) stops duplicate business requests. Meanwhile CASCADE on audit-bearing
children silently destroys the evidence an incident needs.

Most important framework/AI connection:
Tenant-aware composite foreign keys stop a Tenant-A Job from linking a Tenant-B Document, while
Attempts/Events/Artifacts preserve the Provider, history and Object Storage provenance that
reconciliation depends on.

Most important interview answer:
Foreign keys enforce relationship integrity during writes; they never authorize a reader. Tenant-scoped
queries — with tenant_id from authenticated server context — do that.
```

Scope honesty: the Day31 artifact is a **target schema for a fresh database** applied after
`001_create_jobs.sql`. Its `ADD COLUMN ... NOT NULL` statements succeed only while `app.jobs` is empty;
safe evolution of populated tables is **Day36**. In class, a **reduced** validation schema was executed
on PostgreSQL 14.18 and selected constraints behaved correctly (a first attempt failed earlier at
cluster start with `shmget: Operation not permitted` — environment evidence, not a SQL result). **The
full Day31 artifact in this repository was NOT executed** — no `psql` or PostgreSQL server was available
during the repository update. Transactions (Day33), locking/MVCC (Day34), indexes (Day35), safe
migration (Day36), RLS/roles, backups, HA, performance, and production deployment remain unproven.

---

# Before Next Lesson Checklist

- [ ] Can I explain when a repeated fact must become its own entity?
- [ ] Can I distinguish primary key, foreign key, and business key — and name the scope of each `UNIQUE`?
- [ ] Can I explain why a retry's new `job_id` makes tenant + idempotency key the only workable rule?
- [ ] Can I defend a referential action as a retention decision rather than a convenience?
- [ ] Can I place a foreign key correctly for one-to-many, and express one-to-one with FK + `UNIQUE`?
- [ ] Can I model many-to-many and put relationship attributes on the junction table?
- [ ] Can I state what a row `CHECK` can and cannot see?
- [ ] Can I enforce same-tenant relationships and still explain why that is not authorization?
- [ ] Can I separate current state, event history, and outbox intent?
- [ ] Can I order the deployment of a `UNIQUE` constraint onto committed duplicates?
- [ ] Can I state exactly which validation level Day31 reached — and which it did not?
