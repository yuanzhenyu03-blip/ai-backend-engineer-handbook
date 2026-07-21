# Lesson 30 — SQL Data Manipulation and Query Fundamentals

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Intermediate

Estimated Time: 6-7 hours

Prerequisite: Day29 — PostgreSQL Foundations and Durable Relational State

Previous Lesson: [Day29 — PostgreSQL Foundations and Durable Relational State](day29-postgresql-foundations-and-durable-relational-state.md)

Next Lesson: [Day31 — Relational Modeling and Data Integrity](day31-relational-modeling-and-data-integrity.md)

Engineering Artifact: The Day30 increment of the Production AI Backend Data Layer — a raw, parameterized SQL operations pack (`sql/002_job_crud_and_guarded_transitions.sql`) with explicit affected-row contracts — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

PostgreSQL Cheat Sheet: [cheat_sheets/postgresql.md](../../cheat_sheets/postgresql.md)

PostgreSQL Interview: [interview/postgresql.md](../../interview/postgresql.md)

Estimated Study Time:

```text
Reading: 120-150 minutes
Exercises: 90-120 minutes
Hands-on SQL authoring / static review: 90-120 minutes
Review: 30-45 minutes

Total: 6-7 hours
```

---

# Learning Objectives

After completing this lesson, the student should be able to:

* Write a deterministic `SELECT` with explicit columns, a filter, a stable `ORDER BY` tie-breaker, and `LIMIT`.
* Explain SQL three-valued logic and why `WHERE` discards both `FALSE` and `UNKNOWN`.
* Use `IS NULL` correctly and include no-error rows explicitly instead of losing them to `<>`.
* Insert a Job that lets PostgreSQL generate its defaults, and return the generated facts with `RETURNING`.
* Explain parameterized SQL, what the code/data boundary does prevent, and what it does **not** prevent.
* Treat `WHERE` as the modification boundary and write guarded state transitions with current-state predicates.
* Interpret zero returned rows honestly — the transition did not apply, not "the Job does not exist".
* Fix `AND`/`OR` precedence in a guarded `DELETE` and use `RETURNING` as evidence of what was actually removed.
* Recognize a lost update and prefer a database-side increment or an expected-old-value predicate.
* Order a production incident response: contain, preserve evidence, identify, reconcile, repair, verify.

The engineering artifact is a parameterized SQL operations pack, not application code.

---

# Why This Matters

Day29 created a durable Job row and an enforceable table contract. What it did not provide was a
systematic way to **read, insert, modify, delete, parameterize, and verify** changes to those facts.

Day30's central rule:

```text
WHERE is the modification boundary.
RETURNING and affected rows are the evidence that a guarded operation actually occurred.
```

Why a backend engineer must care:

```text
Determinism -> ORDER BY without a unique tie-breaker returns an unstable page.
NULL logic  -> `<> 'timeout'` silently drops every no-error row (UNKNOWN is filtered out).
Safety      -> parameter binding separates SQL structure from client values (injection boundary).
Guarding    -> a current-state predicate stops a worker from restarting a terminal Job.
Evidence    -> "one row" vs "zero rows" is the durable proof a transition applied.
Blast radius-> one missing `job_id` in a WHERE turned a 1-row fix into 842 wrongly failed Jobs.
```

The sharpest production moment: a broad `UPDATE` marked 842 live Jobs as `failed`. Code rollback
stopped future bad writes; it repaired nothing already persisted.

---

# Roadmap Position

Knowledge continuity chain (v3.2):

```text
Previous Knowledge (Day29)
        |
        v
Current Concept (Day30: precise reads and guarded writes on durable Job facts)
        |
        v
Future Usage (Day31 relationships/integrity; Day32 joins/aggregation; Day33 transactions;
              Day34 concurrency control and worker claims)
```

Where Day30 sits:

```text
Day28 state ownership -> Day29 durable Job row + table contract
-> Day30 precise SQL reads and guarded writes   <-- you are here
-> Day31 relational modeling and enforceable integrity
-> Day32 joins, aggregation, operational queries
-> Day33 transactions -> Day34 MVCC, locking, SKIP LOCKED, worker claims
```

Day29 rules reused directly:

```text
- The Job row is committed BEFORE FastAPI returns 202.
- The table definition is an enforceable contract; NOT NULL is not business integrity.
- result_object_key is a reference; large bytes stay in Object Storage.
- Durability is not integrity, and code rollback does not repair persisted facts.
```

Future connection only: Day31 moves rules that Day30 expresses through careful `WHERE` predicates into
`CHECK`/`UNIQUE`/foreign keys. Day33 makes multi-step changes atomic. Day34 adds locking and
`SKIP LOCKED` for real worker claims. SQLAlchemy/Alembic remain Phase 4.

---

# Lesson Map

```text
Deterministic SELECT (explicit columns, filter, tie-breaker, LIMIT)
  -> NULL and three-valued logic (IS NULL; why <> drops NULL rows)
  -> INSERT with defaults + RETURNING generated facts
  -> Parameterized SQL and the injection boundary (and its limits)
  -> WHERE as a guarded state-transition boundary (queued -> running)
  -> running -> succeeded with an Object Storage reference
  -> Guarded DELETE and AND/OR precedence
  -> Rows affected and lost-update awareness
  -> The 842-row incident: contain -> evidence -> identify -> reconcile -> repair -> verify
```

---

# Core Mental Model

```text
SELECT -> FROM -> WHERE -> ORDER BY -> LIMIT     (the clause chain)

WHERE      = the modification boundary
ORDER BY   = part of the query contract (needs a unique tie-breaker to be deterministic)
RETURNING  = the actual rows produced by the statement
rows affected = the evidence that the guarded operation occurred

Parameters bind VALUES. They never build SQL structure.
Zero rows means "the transition did not apply" — not "the Job does not exist".
```

---

# Main Concepts

## Concept 1: A Deterministic `SELECT` for Queued Jobs

Tech Lead Question:

`app.jobs` has 10,000 rows. Operations needs the 20 **oldest queued** Jobs. Write the query.

Student Thinking:

Filter by status, order by creation time, take 20.

Student Answer:

> "select * from app.jobs where status=\"queued\" order by create_at limit 20"

Tech Lead Review:

The shape is right — clause chain `SELECT -> FROM -> WHERE -> ORDER BY -> LIMIT`. Four corrections:

```text
status / create_at  -> the real columns are job_status / created_at
"queued"            -> double quotes identify an IDENTIFIER; string literals use SINGLE quotes
SELECT *            -> use explicit columns for a stable query contract
ORDER BY created_at -> not deterministic when timestamps tie; add a unique tie-breaker
```

```sql
SELECT job_id, job_status, attempt_count, created_at
FROM app.jobs
WHERE job_status = 'queued'
ORDER BY created_at ASC, job_id ASC
LIMIT 20;
```

Critical scope statement: this is a **candidate list only**, not a concurrency-safe worker claim. Two
workers running this query see the same 20 rows. Claiming is Day34 (`FOR UPDATE`, `SKIP LOCKED`).

Engineering Thinking:

`SELECT *` couples your code to column order/additions. A non-unique `ORDER BY` gives an unstable page —
the same query can return different rows across calls.

Production Example:

Two identical "oldest queued" pages can disagree if `created_at` ties and no tie-breaker exists; adding
`job_id ASC` makes the ordering total.

Framework Connection:

FastAPI can serve this list to an operations dashboard; a Celery worker must **not** treat it as a claim.

Exercise:

Write the deterministic query for the 20 oldest queued Jobs.

## Concept 2: `NULL` and SQL Three-valued Logic

Tech Lead Question:

Find Jobs that have not finished. Then explain why `error_message <> 'timeout'` loses rows.

Student Thinking:

Unfinished means `finished_at` has no value, so `IS NULL`.

Student Answer:

> "select job_id,job_status,attempt_count,finished_at where finished_at is null"

Tech Lead Review:

The NULL mental model is **correct** — only the `FROM` clause is missing (a syntax slip, not a
conceptual error):

```sql
SELECT job_id, job_status, attempt_count, finished_at
FROM app.jobs
WHERE finished_at IS NULL;
```

`finished_at IS NULL` means the lifecycle event has not occurred — the Job is not terminal. Note that
`= NULL` is **not** the correct predicate: any comparison with NULL yields `UNKNOWN`.

Then the subtle one. Asked why NULL rows vanish from `error_message <> 'timeout'`:

> "我猜测<> 代表布尔判断，判断error_message筛选非timeout的行，<>是只针对文本类型进行识别，而没有is null 无法识别为true可能返回的是unknown所以数据库不会返回为false和unknown的行"

The reasoning is largely right — `WHERE` keeps only `TRUE` and filters both `FALSE` and `UNKNOWN`. One
correction: `<>` is **not** text-only; it is a comparison operator for comparable types. Comparing NULL
with anything still yields `UNKNOWN`.

To include rows with no recorded error, say so explicitly:

```sql
WHERE error_message IS NULL
   OR error_message <> 'timeout';
```

PostgreSQL's `IS DISTINCT FROM 'timeout'` is a NULL-safe alternative, but the explicit `IS NULL OR`
form often makes the business intent easier to review.

Vocabulary boundary:

```text
A NULL FIELD has contextual meaning (unknown / not yet occurred / unavailable / not applicable).
UNKNOWN is specifically the logical result of a three-valued SQL expression.
```

Engineering Thinking:

NULL is not "empty" — it is the absence of a value, and it makes ordinary comparisons non-boolean.

Production Example:

An operations query for "errors other than timeout" silently hides every healthy Job unless the NULL
case is stated.

Framework Connection:

Day29's nullable lifecycle fields (`started_at`, `finished_at`, `error_message`, `result_object_key`)
are exactly the columns this logic applies to.

Exercise:

Query unfinished Jobs, then explain why NULL rows disappear from `error_message <> 'timeout'`.

## Concept 3: `INSERT`, Explicit Columns, Defaults, and `RETURNING`

Tech Lead Question:

The application supplies only `provider_metadata` and lets PostgreSQL generate everything else. Write
the INSERT and return the generated facts.

Student Thinking:

There is a "default" form of INSERT.

Student Answer:

> "insert default into app.jobs returning job_id,ob_status,attempt_count,cancel_requested,created_at"

Tech Lead Review:

The intent is right; the syntax is inverted. The correct all-defaults form is:

```sql
INSERT INTO app.jobs DEFAULT VALUES
RETURNING job_id, job_status, attempt_count, cancel_requested, created_at;
```

But the production scenario supplies one column. Name it explicitly and omit the rest so PostgreSQL
generates their defaults:

```sql
INSERT INTO app.jobs (provider_metadata)
VALUES ($1::jsonb)
RETURNING job_id, job_status, attempt_count, cancel_requested, provider_metadata, created_at;
```

An important correction to a common belief: `RETURNING` does **not** return a count. It returns the
actual rows/columns the statement produced. Affected-row **count** evidence comes from the driver's
command result (or the number of rows you received).

Engineering Thinking:

Let the database own initial facts; return them in the same round trip so the API can answer with a
`job_id` immediately (Day29's write-before-202 rule).

Production Example:

FastAPI inserts the Job, gets `job_id` + `created_at` back from `RETURNING`, and only then returns
`202 Accepted`.

Framework Connection:

`provider_metadata` stays bounded JSONB (Day29); large bytes never enter PostgreSQL.

Exercise:

Insert `provider_metadata` while leaving the Job defaults to PostgreSQL, and return the generated facts.

## Concept 4: Parameterized SQL and the Injection Boundary

Tech Lead Question:

What is `$1`? If the client JSON changes every call, do you rebuild the SQL string?

Student Thinking:

Unfamiliar syntax — maybe you concatenate the changing value into the statement.

Student Answer:

> "我不知道这种写法，也不清楚$1的含义，我猜测应该是如果每次客户端传递的json变动都需要使用python f-string进行拼接吧？"

Tech Lead Review:

This is the single most important safety correction of the day.

```text
$1  = PostgreSQL/asyncpg-style POSITIONAL PARAMETER 1
::jsonb = a cast requesting JSONB conversion

The SQL STRUCTURE stays fixed. Only the bound VALUES change between calls.
NEVER build SQL with Python f-strings from client input.
```

After teaching, the student stated the boundary correctly:

> "普通 JSON 数据，因为参数只作为值处理，不重新解释为 SQL 结构"

Exactly: even if the JSON contains quotes or the text `DELETE FROM app.jobs`, a bound value is treated
as **data** and never re-parsed as SQL structure.

Two limits that matter as much as the protection:

```text
1. Placeholders differ by driver:
   asyncpg / PostgreSQL PREPARE -> $1, $2
   psycopg                      -> %s
   SQLAlchemy                   -> named binds
   Preserve the PRINCIPLE (code/data separation), not one spelling.

2. Parameters bind VALUES ONLY.
   They cannot bind table names, column names, or ASC/DESC.
   Dynamic identifiers/keywords require a strict ALLOWLIST.
```

And what parameterization does **not** do:

```text
It does not validate business rules.
It does not authorize access or enforce tenant ownership.
It does not prevent logical bugs or concurrency bugs.
```

Engineering Thinking:

Injection safety is a *structural* guarantee. Correctness, authorization, and concurrency are separate
problems you still must solve.

Production Example:

A malicious `provider_metadata` payload containing SQL keywords is stored as ordinary JSON — it never
executes.

Framework Connection:

No Python application or driver was executed in class; the invariant is the code/data separation itself.

Exercise:

Explain why malicious-looking text remains JSON data under parameter binding, and name two things
parameterization does not solve.

## Concept 5: `WHERE` as a Guarded State-transition Boundary

Tech Lead Question:

A worker moves one Job `queued -> running`. Write it so a terminal Job can never be restarted.

Student Thinking:

Match the `job_id` and require the current state.

Student Answer:

> "update app.jobs set job_status='running', started_at=now() where job_id=$1 and job_status is distinct from 'queued' returning job_id,job_status,started_at"

Tech Lead Review:

The structure is right, but `IS DISTINCT FROM 'queued'` means **NOT queued** — the exact opposite of the
guard. It would match `running`/`succeeded`/`failed` and *reject* `queued`, potentially restarting
terminal Jobs. The guard must require the current state:

```sql
UPDATE app.jobs
SET job_status = 'running',
    started_at = now()
WHERE job_id = $1
  AND job_status = 'queued'
RETURNING job_id, job_status, started_at;
```

Because `job_id` is a primary key, the result is either **one row** (transition applied) or **zero rows**
(precondition did not match).

The student read zero rows correctly:

> "不能直接断言，因为有可能这个job_id已经是running状态"

Right. The durable conclusion is only: **the transition was not applied.** The Job may still exist in
another state. A follow-up `SELECT` can diagnose the current row, but concurrent changes can occur
between two statements — exact transactional classification is Day33/Day34.

Engineering Thinking:

Put the precondition in the `WHERE`, not in application code. The database then enforces the transition
atomically for that single statement.

Production Example:

Two workers racing on the same Job: one gets one row, the other gets zero and must not report success.

Framework Connection:

FastAPI/Celery must never claim success after a zero-row transition.

Exercise:

Write `queued -> running` with `job_id` and current-state guards, then interpret a zero-row result
without falsely claiming the Job does not exist.

## Concept 6: Successful Completion — `running -> succeeded`

Tech Lead Question:

The worker finished and produced a result artifact. Write the completion transition.

Student Thinking:

Same guarded pattern: require the current state, set the terminal fields, return evidence.

Student Answer (correct, integrated):

> "update app.jobs set job_status = 'succeeded', finished_at = now(),result_object_key = $2 where job_id=$1 and job_status = 'running' returning job_id,job_status,finished_at,result_object_key"

Tech Lead Review:

Correct on the first attempt — the guard, the terminal timestamp, the parameterized reference, and the
evidence are all present:

```sql
UPDATE app.jobs
SET job_status = 'succeeded',
    finished_at = now(),
    result_object_key = $2
WHERE job_id = $1
  AND job_status = 'running'
RETURNING job_id, job_status, finished_at, result_object_key;
```

```text
$2 is an Object Storage REFERENCE, never the result bytes.
One returned row -> running -> succeeded actually occurred.
Zero returned rows -> it did not occur (the Job was not in `running`).
```

Engineering Thinking:

Every state transition follows one shape: identity + current-state guard + new facts + `RETURNING`.

Production Example:

A worker that crashed and retried cannot double-complete: the second attempt finds no `running` row.

Framework Connection:

Day28/Day29's boundary holds — PostgreSQL keeps the reference, Object Storage keeps the bytes.

Exercise:

Write `running -> succeeded` with `result_object_key` and `RETURNING`.

## Concept 7: Guarded `DELETE` and `AND`/`OR` Precedence

Tech Lead Question:

Remove only the Day29 test rows — status empty or `banana`, created before cutoff `$1`. Write it.

Student Thinking:

Filter by date and by the two bad statuses.

Student Answer:

> "delete from app.jobs where createdd_at<$1 and job_status=''  or job_status='banana'  returning job_id,job_status、created_at"

Tech Lead Review:

Besides the typos (`createdd_at`, a Chinese comma), there is a **dangerous logic bug**: SQL `AND` binds
more tightly than `OR`.

```text
WHERE date AND empty OR banana
parses as
WHERE (date AND empty) OR (banana)
-> deletes EVERY banana row regardless of date.
```

Correct forms — parenthesize, or use `IN`:

```sql
DELETE FROM app.jobs
WHERE created_at < $1::timestamptz
  AND job_status IN ('', 'banana')
RETURNING job_id, job_status, created_at;
```

A `SELECT` with the same predicate can **preview** the candidate set, but it is not proof of the final
deletion set — rows may change between statements. `DELETE ... RETURNING` is the evidence of what was
actually deleted. Making preview and delete consistent requires a transaction (Day33).

Engineering Thinking:

Operator precedence is a production hazard in destructive statements. Parenthesize intent explicitly.

Production Example:

The unparenthesized version silently deletes `banana` rows from any date — including rows a later test
depended on.

Framework Connection:

This is the same "guarded, evidence-capturing repair" discipline as Day29's `queud` drill.

Exercise:

Write a cutoff- and status-guarded `DELETE`, and correct the `AND`/`OR` precedence.

## Concept 8: Rows Affected and Lost-update Awareness

Tech Lead Question:

`attempt_count` is 2. Worker A and Worker B both read 2, both compute 3 in application code, both write
3. Two attempts happened. What does the database say, and how do you fix it?

Student Thinking:

It is a concurrency problem — lock so only one worker computes at a time.

Student Answer:

> "涉及到并发问题，加锁每次只能由一个work先读取并计算数据"

Tech Lead Review:

Correct diagnosis: this is a **Lost Update** — two attempts occurred but only one increment survives.
The proposed fix needs two corrections:

```text
An APPLICATION lock does not protect across multiple Pods/Workers.
A DATABASE row lock must be held inside a TRANSACTION — SELECT FOR UPDATE is Day33/Day34 scope.
```

For a simple counter, keep the computation **inside one database statement** so no read-compute-write
window exists:

```sql
UPDATE app.jobs
SET attempt_count = attempt_count + 1
WHERE job_id = $1
RETURNING job_id, attempt_count;
```

For optimistic awareness, include the expected old value:

```sql
UPDATE app.jobs
SET attempt_count = $3
WHERE job_id = $1
  AND attempt_count = $2
RETURNING job_id, attempt_count;
```

```text
Zero rows -> the stale expectation did not match.
The application MUST NOT report success; it must decide whether to reread/retry.
This is AWARENESS, not the full Day34 concurrency design.
```

Engineering Thinking:

Every application-side read-compute-write is a race window. Push the computation into the statement, or
make the old value part of the predicate.

Production Example:

Lost `attempt_count` increments hide retries and distort cost/reliability evidence for AI provider calls.

Framework Connection:

Day34 will add MVCC, `SELECT FOR UPDATE`, and `SKIP LOCKED` for real worker claims.

Exercise:

Diagnose the two-worker `attempt_count` lost update and compare the database-side increment, the
optimistic expected-value guard, and the future transaction/locking approach.

## Concept 9: The 842-Row Incident — Contain, Reconcile, Repair

Tech Lead Question:

A query meant to fail **one** timed-out Job omitted `job_id`:

```sql
UPDATE app.jobs
SET job_status = 'failed',
    finished_at = now()
WHERE job_status = 'running'
RETURNING job_id;
```

It returned **842** Job IDs. What do you do?

Student Thinking:

Let the running Jobs finish first, roll back the app, keep the intended failure, put the others back to
`running`.

Student Answer:

> "先等待正在正常运行的job运行结束，因为运行结束后运行成功的会更新状态。而失败的会标记为faild，里面有error信息，将失败的job筛选出来，回滚应用代码，除了那个超时的单独标记为failed，其他的数据库状态回滚到running"

Tech Lead Review:

Two corrections, both important.

**Waiting first is unsafe.** The bad persisted states may already be altering workers, schedulers,
retries, clients, and monitoring — and normal workers may subsequently write `succeeded`/`failed`,
making the evidence *more* ambiguous. Contain first.

**Do not blanket-restore all 841 rows to `running`.** Some may have genuinely succeeded or failed after
the incident. Reconcile before repairing.

Final incident order:

```text
contain
-> preserve evidence
-> identify exact affected set
-> reconcile actual business state
-> guarded data repair by verified subset
-> capture RETURNING / row-count evidence
-> verify worker / API / queue / Object Storage recovery
-> prevent recurrence
```

The student stated the reconstruction boundary correctly:

> "不能，需要结合 Worker 日志、结果对象、provider 状态或 Job Event/Attempt 历史判断真实业务状态"

Exactly. The 842 `RETURNING` IDs are evidence of the **affected set**, not of each Job's real business
outcome. Honest limitation: the current Day29/Day30 schema has **no Job Event/Attempt history and no
release/tenant/provenance model**, so exact reconstruction may be impossible. Day31/Day32 make those
relationships and query paths possible.

```text
Code rollback stops FUTURE bad writes. It never repairs already-persisted facts.
```

An automatic "expected exactly one row or roll back" boundary requires a transaction — that is Day33.
Day30 establishes the *requirement* to check rows affected.

Engineering Thinking:

In an incident, the first action is to stop the damage, not to wait for it to settle.

Production Example:

842 live AI Jobs marked `failed` can trigger incorrect retries and alerts, and split PostgreSQL truth
from Worker/provider/Object Storage reality.

Framework Connection:

Same shape as Day28's compute-rollback-vs-data-repair rule and Day29's guarded `queud` repair.

Exercise:

Solve the 842-row accidental UPDATE incident and distinguish code rollback from data repair.

---

# Common Misconceptions

## Mental Model Evolution (Day29 -> Day30)

```text
Initial: "Day29 gave a durable row and a table contract, so the data layer is usable."
Reasoning: The schema exists, defaults work, and the row survives restarts.
Correction: Reading and changing those facts safely is a separate skill. A missing tie-breaker returns
            unstable pages; `<>` silently drops NULL rows; an inverted guard restarts terminal Jobs; a
            missing WHERE clause falsely failed 842 live Jobs.
Final: WHERE is the modification boundary, deterministic ordering is part of the query contract, and
       RETURNING plus rows-affected is the durable evidence that a guarded operation occurred —
       while code rollback still repairs nothing already persisted.
```

## Misconception list

```text
SELECT * and unstable ordering
❌ `SELECT * ... ORDER BY created_at` is a fine "oldest 20" query.
✅ Use explicit columns for a stable contract, and add a unique tie-breaker
   (`ORDER BY created_at ASC, job_id ASC`) or the page is non-deterministic on ties.
```

```text
Quoting
❌ `WHERE job_status = "queued"`.
✅ Double quotes identify an IDENTIFIER; string literals use SINGLE quotes: `'queued'`.
```

```text
`<>` is text-only
❌ `<>` only compares text, so NULL is unrelated.
✅ `<>` compares any comparable types; comparing NULL yields UNKNOWN, and WHERE keeps only TRUE —
   so `error_message <> 'timeout'` drops every no-error row.
```

```text
Comparing to NULL
❌ `WHERE finished_at = NULL`.
✅ `WHERE finished_at IS NULL`. Any comparison with NULL is UNKNOWN, never TRUE.
```

```text
INSERT default syntax
❌ `INSERT DEFAULT INTO app.jobs ...`.
✅ `INSERT INTO app.jobs DEFAULT VALUES ...`, or name the supplied columns explicitly and omit the rest.
```

```text
Parameterization requires string building
❌ Changing client JSON means rebuilding the SQL with an f-string.
✅ The SQL structure stays fixed; only bound values change. Never f-string client input into SQL.
   Placeholders differ by driver ($1 / %s / named binds) — preserve the principle, not the spelling.
```

```text
What parameters can bind
❌ Parameters can also carry table names, column names, or ASC/DESC.
✅ Parameters bind VALUES only. Dynamic identifiers/keywords require a strict allowlist.
```

```text
Parameterization solves security
❌ Bound parameters make the query safe.
✅ It closes the injection/structure boundary only. It does not validate business rules, authorize
   access, enforce tenant ownership, or prevent logical/concurrency bugs.
```

```text
Transition guard direction
❌ `WHERE job_id = $1 AND job_status IS DISTINCT FROM 'queued'`.
✅ That means NOT queued — it would restart terminal Jobs. The guard must be `job_status = 'queued'`.
```

```text
RETURNING semantics
❌ RETURNING gives the affected-row count.
✅ RETURNING gives the actual rows/columns produced; count evidence comes from the driver command
   result or the number of rows returned.
```

```text
Zero rows means the Job does not exist
❌ A zero-row guarded UPDATE proves the Job is missing.
✅ It proves only that the transition was not applied; the Job may exist in another state.
```

```text
AND/OR precedence in DELETE
❌ `WHERE created_at < $1 AND job_status = '' OR job_status = 'banana'`.
✅ AND binds tighter than OR, so every banana row is deleted regardless of date. Parenthesize or use
   `AND job_status IN ('', 'banana')`.
```

```text
SELECT preview proves the delete set
❌ A prior SELECT with the same predicate proves what DELETE will remove.
✅ Rows can change between statements; `DELETE ... RETURNING` is the evidence. Consistency needs a
   transaction (Day33).
```

```text
Locking is the first answer to lost updates
❌ Add an application lock so only one worker reads and computes.
✅ Application locks do not span Pods/Workers, and database row locks require a transaction (Day33/34).
   For a counter, use `SET attempt_count = attempt_count + 1` in one statement, or an expected-old-value
   predicate.
```

```text
"One SQL that first queries then modifies" (final synthesis wording)
❌ Phrasing the fix as a single SQL that queries and then modifies.
✅ Preserve the intent — avoid application read-compute-write — but state it correctly: let one UPDATE
   compute from the current database value, or include the expected old value in the predicate.
```

```text
Incident response order
❌ Wait for running Jobs to finish, then roll back and restore states.
✅ Contain first. Waiting allows state divergence and evidence loss, because normal workers keep writing.
```

```text
Blanket restore after a bad UPDATE
❌ Set all 841 unintended rows back to `running`.
✅ Some may have genuinely succeeded or failed. Reconcile Worker logs, provider status, result objects,
   queue data, and Job Event/Attempt history before repairing verified subsets.
```

```text
NULL means "unknown" (final synthesis wording)
❌ NULL simply means unknown.
✅ A NULL FIELD has contextual lifecycle meaning; UNKNOWN is specifically the logical result of a
   three-valued comparison.
```

---

# Engineering Trade-offs

```text
SELECT * vs explicit columns
+ SELECT *: quick to write during exploration.
- SELECT *: unstable contract; new/reordered columns silently change results.
+ Explicit: stable contract and clear intent.
```

```text
ORDER BY one column vs adding a unique tie-breaker
+ One column: simpler, slightly cheaper.
- One column: non-deterministic pages when values tie.
+ Tie-breaker: total order and reproducible pagination.
```

```text
`IS NULL OR <>` vs `IS DISTINCT FROM`
+ Explicit IS NULL OR: business intent is obvious to a reviewer.
- Explicit: more verbose.
+ IS DISTINCT FROM: concise and NULL-safe.
- IS DISTINCT FROM: easy to invert by accident (as the transition guard showed).
```

```text
Database-side expression vs application computation
+ DB-side (`attempt_count + 1`): no read-compute-write window; no lost update for that counter.
- DB-side: the logic lives in SQL, less visible in application code.
+ Application-side: familiar and testable in one language.
- Application-side: introduces a race window across Pods/Workers.
```

```text
Optimistic expected-value guard vs future locking
+ Optimistic: no transaction/lock needed; zero rows signals a stale read.
- Optimistic: the caller must handle reread/retry; not a full concurrency design.
+ Locking (Day33/34): stronger guarantees.
- Locking: needs transactions, adds contention and deadlock considerations.
```

```text
Candidate SELECT vs concurrency-safe claim
+ Candidate list: simple and useful for operations visibility.
- Candidate list: two workers see the same rows; it is not a claim (Day34).
```

```text
SELECT preview before DELETE vs RETURNING evidence
+ Preview: helps a human sanity-check the predicate.
- Preview: not proof; rows can change before the DELETE runs.
+ RETURNING: authoritative record of what was actually removed.
```

```text
Parameterized SQL vs dynamic identifiers
+ Parameters: close the injection boundary for values.
- Parameters: cannot bind identifiers/keywords; those need strict allowlists.
```

---

# Hands-on Exercises

The engineering artifact is a parameterized SQL operations pack (see
[projects/ai-backend-data-layer/](../../projects/ai-backend-data-layer/README.md)).

## Exercise 1: Deterministic Candidate Query
Question: Return the 20 oldest queued Jobs deterministically.
Expected Output: Explicit columns, `WHERE job_status = 'queued'`, `ORDER BY created_at ASC, job_id ASC`,
`LIMIT 20`.
Follow-up: Why is this not a worker claim?

## Exercise 2: Unfinished Jobs
Question: Query Jobs that have not finished.
Expected Output: `WHERE finished_at IS NULL` (with the `FROM` clause present).

## Exercise 3: Why NULL Rows Disappear
Question: Explain why `error_message <> 'timeout'` loses rows with no error.
Expected Output: NULL comparison yields UNKNOWN; WHERE keeps only TRUE. Fix with
`error_message IS NULL OR error_message <> 'timeout'`.

## Exercise 4: INSERT with Defaults + RETURNING
Question: Insert only `provider_metadata`; return the generated Job facts.
Expected Output: Explicit column list, `VALUES ($1::jsonb)`, `RETURNING` the generated columns.

## Exercise 5: Parameter Boundary
Question: Why does malicious-looking text stay JSON data? Name two things parameterization does not fix.
Expected Output: Values are never re-parsed as SQL structure; it does not authorize, validate business
rules, or prevent concurrency bugs.

## Exercise 6: Guarded `queued -> running`
Question: Write the transition so a terminal Job can never be restarted.
Expected Output: `WHERE job_id = $1 AND job_status = 'queued'` + `RETURNING`.
Follow-up: What does zero rows prove — and not prove?

## Exercise 7: Guarded `running -> succeeded`
Question: Complete the Job with a result reference.
Expected Output: `WHERE job_id = $1 AND job_status = 'running'`, `result_object_key = $2`, `RETURNING`.

## Exercise 8: Guarded DELETE and Precedence
Question: Delete only pre-cutoff test rows with status `''` or `banana`.
Expected Output: `AND job_status IN ('', 'banana')` (or parentheses), plus `RETURNING` as evidence.

## Exercise 9: Lost Update
Question: Two workers both write `attempt_count = 3`. Diagnose and fix.
Expected Output: Lost Update; use `attempt_count = attempt_count + 1` in one statement, or an
expected-old-value predicate; application locks do not span Pods and DB locks need a transaction.

## Exercise 10: The 842-Row Incident
Question: Order the response and distinguish rollback from repair.
Expected Output: contain -> preserve evidence -> identify -> reconcile -> guarded repair -> capture
evidence -> verify -> prevent recurrence. Code rollback repairs nothing already persisted.

## Exercise 11: English Interview
Question: Answer the Beginner, Intermediate, and Senior questions.

## Exercise 12: Final Chinese Mental Model
Question: Synthesize the day across reads, writes, NULL, parameters, evidence, and incident recovery.

---

# Relevant Framework Connections

## PostgreSQL
Raw SQL, three-valued logic, positional parameters, explicit column lists, deterministic ordering,
database-side expressions, guarded DML, `RETURNING`, and rows-affected evidence.

## FastAPI
Persist and return the Job before sending `202` (Day29's rule). Bind request values rather than
concatenating them. Interpret zero/one returned rows honestly, and never report success after a failed
state transition.

## Queue / Celery Worker boundary
The candidate `SELECT` is a **list, not a claim** — two workers see the same rows. Worker status
transitions need current-state guards. Complete claims (`FOR UPDATE`, `SKIP LOCKED`) are Day34.

## Object Storage
`result_object_key` is a parameterized **reference**. Large result bytes remain outside PostgreSQL.

## Python DB drivers
Placeholder spelling differs (`$1` for asyncpg/PostgreSQL `PREPARE`, `%s` for psycopg, named binds for
SQLAlchemy), but code/data separation is invariant. **No Python application or driver was executed in
class.**

---

# AI Backend Connections

```text
- A long-running RAG/embedding Job is inserted and returned before FastAPI sends 202.
- Operations lists the oldest queued candidates deterministically without pretending to claim them.
- Workers transition queued -> running -> succeeded through guarded current-state predicates.
- attempt_count must reflect every model/provider attempt; lost updates hide retries and distort
  cost/reliability evidence.
- provider_metadata stays bounded JSONB; result_object_key points to Object Storage.
- A broad UPDATE can falsely fail hundreds of live AI Jobs, trigger incorrect retries and alerts, and
  split PostgreSQL truth from Worker/provider/Object Storage reality.
- Accurate recovery may require Job Attempt/Event history and provenance, which the current schema lacks.
```

---

# English Interview

Key vocabulary: modification boundary, affected rows, deterministic ordering, tie-breaker, three-valued
logic, `IS NULL`, parameterized query, bind value, injection, guarded transition, current-state
predicate, lost update, optimistic concurrency, reconcile, data repair.

## Beginner

Question:

Why does the `WHERE` clause matter in an `UPDATE` or `DELETE`, and how do you verify what happened?

Actual student attempt (preserved):

> "the where define bondary of modify,because the affected rows is durable state and backend engineer could compare the diffrent between expended result and fact result by check the affect rows."

Technical review: the idea is correct — `WHERE` defines the modification boundary and affected rows are
the evidence. Tighten the English (`bondary` -> boundary, `diffrent` -> difference, `expended` ->
expected, `affect` -> affected).

Strong Answer:

> The `WHERE` clause defines the boundary of the modification: it decides exactly which rows are
> changed. Because those changes are durable, I verify the result by checking the number of affected
> rows and by using `RETURNING` to see the rows the statement actually produced. If the affected-row
> count does not match what I expected — for example one row for a primary-key transition — I treat it
> as a failure and do not report success.

## Intermediate

Question:

What does parameterized SQL protect against, and what does it **not** solve?

Actual student attempt (preserved):

> "it help to avoid affect use sql injection and parameterized SQL is bonded values,it can not effect the structure of sql.it also can resolve these problems,for example,parameterized sql can't constrait input"

Technical review: the core is right — bound values cannot change SQL structure, which is the injection
boundary. The last clause is garbled but points at the right limitation: it does not constrain input.

Strong Answer:

> Parameterized SQL keeps the statement structure fixed and sends the client values separately, so a
> value is never re-parsed as SQL. That closes the injection boundary. It does not validate business
> rules, authorize the request, enforce tenant ownership, or prevent logical and concurrency bugs.
> Parameters also bind values only — table names, column names, and sort direction need a strict
> allowlist instead.

## Senior

Question:

Write a guarded `running -> succeeded` transition. What does zero rows mean, and what concurrency
limitation remains?

Actual student attempt (preserved):

> "where is the most important endpoint,the first need to limit job_id,and limit  job_status equal running.if the result return zero rows,it means all rows is not modify. i think the concurrency limitation is probobly two work concurrency modify the same row."

Technical review: the guard and the zero-row reading are correct, and the concurrency instinct (two
workers on one row) is right. Sharpen the conclusion: zero rows proves only that the transition did not
apply — not that the Job is absent.

Strong Answer:

> I would guard the update with both the identity and the current state: `WHERE job_id = $1 AND
> job_status = 'running'`, set `finished_at = now()` and the result reference, and use `RETURNING` as
> evidence. Since `job_id` is the primary key, I get one row if the transition applied and zero rows if
> it did not. Zero rows does not prove the Job is missing — it may exist in another state, so I would
> not report success. The remaining limitation is concurrency: two workers can act on the same Job, and
> a follow-up `SELECT` can be stale because the row may change between statements. Making that
> classification exact requires a transaction and row locking, which is a later topic.

---

# Mental Model Summary

```text
Clause chain     : SELECT -> FROM -> WHERE -> ORDER BY -> LIMIT
Explicit columns : a stable query contract (not SELECT *)
Deterministic    : ORDER BY needs a unique tie-breaker (created_at, job_id)
NULL             : use IS NULL; comparisons with NULL are UNKNOWN; WHERE keeps only TRUE
Defaults         : INSERT ... DEFAULT VALUES, or name supplied columns and omit the rest
RETURNING        : the actual rows produced (count evidence comes from the driver/rows received)
Parameters       : bind VALUES only; structure stays fixed; no f-strings; allowlist identifiers
WHERE            : the modification boundary and the state-transition guard
Zero rows        : the transition did not apply — NOT "the Job does not exist"
AND/OR           : AND binds tighter; parenthesize or use IN (...) in destructive statements
Lost update      : compute in one statement (col = col + 1) or guard on the expected old value
Incident         : contain -> evidence -> identify -> reconcile -> guarded repair -> verify -> prevent
Code rollback    : stops future bad writes; repairs nothing already persisted
```

Preserve the student's actual final synthesis:

> "我认为应该使用update set returning的一句sql形式代替先查询再修改的模式。null在sql中代表未知unknown，使用is null而不是=null使用参数化sql只是绑定值，不参与构建sql语句，避免sql注入。where明确修改边界，returning返回最终结果的影响的行数。lost update可以使用计数的方式或者进行一句sql的先查询再修改。代码回滚不代码持久化数据也进行了修改，一般来说需要停掉应用避免扩大影响，再进行受影响的内容收集，结合其他的业务结果再进行区分，分别做不同处理。最终再认证修复后的数据应用是否正常"

Narrow corrections to that synthesis:

```text
1. "一句sql的先查询再修改" — keep the intent (avoid application read-compute-write), but state it
   correctly: let ONE UPDATE compute from the current DB value (`attempt_count = attempt_count + 1`),
   or include the expected old value in the WHERE predicate.
2. "returning返回最终结果的影响的行数" — RETURNING returns the actual ROWS/COLUMNS produced; the COUNT
   comes from the driver command result or the number of rows received.
3. "null在sql中代表未知unknown" — a NULL FIELD has contextual lifecycle meaning (not yet occurred /
   unavailable / not applicable); UNKNOWN is specifically the logical result of a three-valued comparison.
4. The incident ordering is right in spirit; the precise order is contain -> preserve evidence ->
   identify exact affected set -> reconcile actual business state -> guarded repair by verified subset
   -> capture evidence -> verify recovery -> prevent recurrence.
```

---

# Today's Takeaway

```text
Most important mental model:
WHERE is the modification boundary; deterministic ordering is part of the query contract; and
RETURNING plus affected rows is the durable evidence that a guarded operation actually occurred.

Most important production risk:
Once committed, a broad `UPDATE` has no automatic undo. Inside an open transaction an erroneous
statement can still be rolled back with `ROLLBACK` (transaction boundaries are Day33), but after
`COMMIT` nothing reverses it automatically — and rolling back application code only stops future bad
writes, it does not repair committed rows. One absent `job_id` turned a 1-row fix into 842 wrongly
failed Jobs, and only a guarded data repair fixes them. Reconcile before repairing — some Jobs
genuinely succeeded.

Most important framework/AI connection:
Workers move Jobs queued -> running -> succeeded through guarded current-state predicates, with
result_object_key as an Object Storage reference and attempt_count incremented inside one statement so
retries are not lost.

Most important interview answer:
Zero rows from a guarded transition proves the transition did not apply — it does not prove the Job
does not exist, so never report success.
```

Scope honesty: Day30 stops before Day31 constraints/relationships, Day33 transactions, and Day34
locking/MVCC/`SKIP LOCKED`. The candidate `SELECT` is not a concurrency-safe claim. In class the Day30
SQL was reviewed manually only — **no PostgreSQL parser/runtime, no Python driver, and no
FastAPI/Celery/Object Storage integration were executed** (see
[the project README](../../projects/ai-backend-data-layer/README.md) for the exact validation matrix).

---

# Before Next Lesson Checklist

- [ ] Can I write a deterministic candidate query and explain why it is not a claim?
- [ ] Can I explain three-valued logic and why `<> 'timeout'` drops no-error rows?
- [ ] Can I insert with database defaults and return the generated facts?
- [ ] Can I explain what parameter binding prevents — and the three things it does not?
- [ ] Can I write a guarded transition and interpret zero rows without overclaiming?
- [ ] Can I spot the `AND`/`OR` precedence bug in a destructive statement?
- [ ] Can I fix a lost update without reaching for an application lock?
- [ ] Can I order an incident response and explain why waiting first is unsafe?
- [ ] Can I state which validation levels Day30 actually reached?
