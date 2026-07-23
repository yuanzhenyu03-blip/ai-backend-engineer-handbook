# PostgreSQL Cheat Sheet

## Purpose

One-page review notes for PostgreSQL as the durable truth of an AI Backend. Built from Phase 3 lessons
(Day29+). Pair with [`interview/postgresql.md`](../interview/postgresql.md) and the
[data layer project](../projects/ai-backend-data-layer/README.md).

---

## Day29 PostgreSQL Foundations and Durable Relational State

Central rule:

```text
Application object/state = temporary
Database row             = durable business fact
Table schema             = enforceable contract for that fact
```

Ordering (the whole point of the lesson):

```text
WRONG: return 202 -> then write the Job row
RIGHT: write + commit the Job row -> then return 202
202 acknowledges a commitment that ALREADY exists durably.
```

### Hierarchy and session boundary

```text
Server process -> cluster -> database -> schema -> table -> row -> column
```

A `psql` session connects to **one database** (host/port/database/user). It does **not** connect to a
schema — schema resolves via a **qualified name** (`app.jobs`) or `search_path`. `public` is just the
**default namespace**, not "public information". Two senses of the word: PostgreSQL **Schema** = namespace;
**table schema** = the table definition/contract.

Session diagnostics: `\conninfo` · `SELECT current_database()` · `current_user` · `SHOW search_path` ·
`SELECT current_schema()` · `\dn` · `\dt app.*`.

### Job model types and defaults

```text
job_id            uuid        PRIMARY KEY DEFAULT gen_random_uuid()
job_status        text        NOT NULL DEFAULT 'queued'
attempt_count     integer     NOT NULL DEFAULT 0
cancel_requested  boolean     NOT NULL DEFAULT false
provider_metadata jsonb       NOT NULL DEFAULT '{}'::jsonb   -- bounded, auxiliary only
created_at        timestamptz NOT NULL DEFAULT now()
started_at / finished_at        timestamptz NULL
error_message / result_object_key text NULL
```

UUID vs integer is a trade-off, not a ranking: UUID = distributed generation + non-enumerable public
identity, at the cost of size and index locality; integer = compact/index-friendly but centrally
generated and enumerable.

### Typed columns vs JSONB

```text
Typed columns -> identity, state, timestamps, counters, booleans, joins, indexes, integrity
Bounded JSONB -> OPTIONAL, non-authoritative auxiliary metadata
NEVER in JSONB -> large bytes, secrets, signed URLs, the only job_id, the only job_status
```

`integer`/`boolean`/`text`/`uuid`/`jsonb` are **types**. **One-to-many is cardinality**, not a type (Day31).
Large bytes stay in Object Storage; the DB stores a reference (`result_object_key`).

### NULL, DEFAULT, and what NOT NULL does not do

```text
NULL is context-dependent: unknown / not yet occurred / not available / not applicable
  started_at NULL        -> execution has not started (the Job EXISTS)
  finished_at NULL       -> not terminal yet
  error_message NULL     -> no recorded error
  result_object_key NULL -> no result artifact yet (NOT "input not uploaded")

NOT NULL rejects SQL NULL ONLY.
It ACCEPTS '' (empty string) and arbitrary text such as 'banana'.  -> CHECK/enum is Day31.
```

Prove defaults are the database's: `INSERT INTO app.jobs DEFAULT VALUES RETURNING *;`
(the client still sends an INSERT — it just **omits every business field**).

### Identity

```text
Primary key            -> identifies one ROW; prevents duplicate KEY VALUES
Idempotency/business key -> identifies one REQUEST; prevents duplicate OPERATIONS
```

A lost-202 retry creates a second row with a new UUID. The fix is a stored idempotency key + a database
**UNIQUE** rule + an **atomic insert/upsert** (read-before-write is race-prone). Day29 has neither, by design.

### timestamptz

```text
timestamptz -> ONE absolute instant, rendered in the SESSION time zone
timestamp   -> wall-clock fields only; does not identify a real moment
```

Same instant, two renderings, identical epoch. PostgreSQL does **not** preserve the original time-zone
label — store it separately if the business needs it.

### Validation ladder (never claim beyond evidence)

```text
conceptual/manual review
-> parser or PostgreSQL syntax/DDL acceptance (in a specific version)
-> real disposable-PostgreSQL behavior
-> application integration
-> production evidence
```

Reading DDL is not syntax proof. A local run is not integration or production. A process restart proves
process-lifecycle persistence only — not backups, HA, or hardware-failure durability.

### Durability vs integrity, and data repair

```text
Durability without integrity makes WRONG facts durable:
  'queud' is perfectly stored and never claimed by a worker.

Code rollback -> stops FUTURE bad writes
Data repair   -> fixes rows ALREADY persisted

Runbook: contain -> identify the exact affected set -> GUARDED update (narrow WHERE)
         -> capture evidence (row count + RETURNING) -> verify business recovery
```

Real identification needs release/time/tenant/provenance columns — absent from the Day29 minimal schema.

## Day30 SQL Data Manipulation and Query Fundamentals

Clause chain: `SELECT -> FROM -> WHERE -> ORDER BY -> LIMIT`.

Deterministic reads:

```text
Explicit columns (not SELECT *) = a stable query contract
ORDER BY needs a UNIQUE tie-breaker: ORDER BY created_at ASC, job_id ASC
Single quotes = string literal 'queued';  double quotes = IDENTIFIER
A candidate SELECT is NOT a claim — two workers see the same rows (claiming is Day34)
```

Three-valued logic: `WHERE` keeps only **TRUE** and filters both FALSE and UNKNOWN. Any comparison with NULL is UNKNOWN, so `= NULL` never matches — use `IS NULL`. `error_message <> 'timeout'` silently **drops every no-error row**; write `error_message IS NULL OR error_message <> 'timeout'` (or the NULL-safe `IS DISTINCT FROM`, which is easy to invert by accident). A NULL *field* has contextual lifecycle meaning; UNKNOWN is the *logical result* of a comparison.

Writes: `INSERT INTO app.jobs DEFAULT VALUES RETURNING ...`, or name supplied columns and omit the rest so defaults generate. **`RETURNING` returns rows/columns, not a count** — count evidence comes from the driver command result or the number of rows received.

Parameters: `$1` is PostgreSQL/asyncpg style (psycopg `%s`, SQLAlchemy named binds). SQL structure stays fixed; only values bind, and a bound value is never re-parsed as SQL — even if it contains `DELETE FROM app.jobs`. Never f-string client input into SQL. Parameters bind **values only**: identifiers and `ASC`/`DESC` need a strict allowlist. Parameterization does **not** validate business rules, authorize access, enforce tenancy, or prevent logical/concurrency bugs.

Guarded transitions — `WHERE` is the modification boundary and carries identity **plus** required current state:

```sql
UPDATE app.jobs SET job_status='running', started_at=now()
WHERE job_id=$1 AND job_status='queued' RETURNING job_id, job_status, started_at;
```

`IS DISTINCT FROM 'queued'` means **NOT queued** and could restart terminal Jobs. With a primary-key predicate the contract is **1 row = applied, 0 rows = not applied** — 0 rows does **not** prove the Job is absent, so never report success.

Destructive statements: `AND` binds tighter than `OR`, so `date AND empty OR banana` deletes every banana row regardless of date. Use `AND job_status IN ('', 'banana')` or parentheses. A prior `SELECT` is a preview, not proof; `DELETE ... RETURNING` is the evidence (consistent preview+delete needs a transaction, Day33).

Lost update: two workers read 2, both write 3 → one increment lost. Application locks don't span Pods/Workers, and DB row locks need a transaction (Day33/34). Use a database-side computation `SET attempt_count = attempt_count + 1`, or an optimistic guard `... WHERE attempt_count = $2` where 0 rows means the stale expectation failed.

Incident order (a missing `job_id` failed 842 live Jobs):

```text
contain -> preserve evidence -> identify exact affected set -> reconcile actual business state
-> guarded repair by verified subset -> capture RETURNING/row-count -> verify recovery -> prevent recurrence
```

Don't wait first (state diverges, evidence degrades) and don't blanket-restore — some Jobs genuinely succeeded. `RETURNING` IDs prove the affected set, not each Job's real outcome. **Code rollback stops future bad writes; it repairs nothing already persisted.**

## Day31 Relational Modeling and Data Integrity

Key vocabulary:

```text
PRIMARY KEY  = who this row is
FOREIGN KEY  = which parent it belongs to
BUSINESS KEY = which business operation must not repeat
UNIQUE       = the SCOPE in which facts cannot duplicate
CHECK        = which final row states are legal
RESTRICT / CASCADE / SET NULL = deletion lifecycle policy
```

Cardinality: **one-to-many** = FK on the many side. **One-to-one** = FK + `UNIQUE` (nullable FK + UNIQUE = optional one-to-one). **Many-to-many** = junction table referencing both, and the junction may carry its own attributes (`document_role`, `input_order`).

Entity vs columns vs JSONB: a fact that repeats unboundedly, has its own attributes, and must be queried independently is an **entity**. `attempt_1_*`/`attempt_2_*` does not scale; a JSONB array loses typing, uniqueness, joins, and provenance.

Child PK trap: `job_attempts.job_id` as PRIMARY KEY means **at most one Attempt per Job**. Attempt needs its own `attempt_id` PK + `job_id` FK. A duplicate ordinary INSERT does **not** overwrite — it fails `23505 unique_violation`.

**Scope is the rule.** `UNIQUE(attempt_id)` does not stop two rows claiming attempt number 1 for one Job -> `UNIQUE (job_id, attempt_number)`. A global `UNIQUE(attempt_number)` would stop Job B from having its own Attempt 1.

Request identity: a retry gets a **new job_id**, so `UNIQUE(tenant_id, job_id)` can never prevent duplicate business requests. Use `UNIQUE (tenant_id, idempotency_key)`; different tenants may reuse a key. `job_id` = row identity; `(tenant_id, idempotency_key)` = client request identity.

Referential actions are **retention policy**: Attempts/Events/Artifacts hold Provider, cost and audit evidence -> `ON DELETE RESTRICT`. `CASCADE` only when the child has no independent retention value; `SET NULL` only when an orphan is meaningful **and** the FK is nullable (impossible on `NOT NULL job_id`).

`CHECK` closes the Day29 gap: `NOT NULL` still accepts `''` and `banana`. `CHECK (job_status IN ('queued','running','succeeded','failed','cancelled'))` protects **every** write path (migrations, scripts, psql), not just the API. But a row CHECK sees only **this row** — it cannot assert a child Artifact exists (Day33), and it does not replace Day30 transition guards (a legal `queued` row can still be an illegal transition from `succeeded`).

Normalization: `result_artifacts` stores **`attempt_id` only**; `job_id` is derivable via `job_attempts`. Storing both without a composite constraint permits contradictory ownership. Denormalize only for a **measured** problem, then constrain the duplicate.

Three different things:

```text
jobs.job_status = what is true NOW      (fast API read; destroyed by each transition)
job_events      = HOW it got there      (append-oriented history; incident reconstruction)
outbox_events   = what MUST be published (durable intent; PostgreSQL owns it, Queue is transport)
```

Optional event provenance: composite FK `(job_id, attempt_id) -> job_attempts(job_id, attempt_id)` guarantees a non-NULL Attempt belongs to the same Job; under default `MATCH SIMPLE` a NULL `attempt_id` leaves it unenforced.

Same-tenant provenance generalizes: `documents` uses composite FK `(tenant_id, upload_session_id) -> upload_sessions` so a Tenant-B Document cannot claim a Tenant-A Upload Session, while `UNIQUE (upload_session_id)` still gives one-session-one-Document. **A single-column FK only proves the parent exists.**

Tenant isolation — two different questions:

```text
Composite FKs (tenant_id, job_id) / (tenant_id, document_id)
    = relationship INTEGRITY at WRITE time (rejects cross-tenant links)
Tenant-scoped query predicate, tenant_id from AUTHENTICATED server context
    = AUTHORIZATION (who may read). FKs never authorize. RLS/roles = future work.
```

Deploying `UNIQUE` onto committed duplicates: a failed `ALTER TABLE ... ADD CONSTRAINT` protects nothing and decides nothing. Order: contain -> preserve evidence -> reconcile using Attempts/Events/Artifacts/Outbox/Provider/client-visible job_id -> choose canonical (the newer row is **not** automatically the loser) -> guarded repair -> verify no conflicts -> add constraint -> verify both directions.

Rollback boundaries: `ROLLBACK` cancels **uncommitted** changes; committed rows need reconciled repair; application rollback only stops future bad writes.

Testing constraints: assert the **specific** SQLSTATE — `23505` unique_violation, `23514` check_violation, `23503` foreign_key_violation (including RESTRICT) — never "any error".

---

## Day32 SQL Joins, Aggregation, and Operational Queries

Start with the **result grain**: one row = one *what*? Every later choice follows from that sentence, and a query without a stated grain has an unreviewable meaning.

Join choice is driven by what a **missing row means**:

```text
INNER JOIN = only matching combinations   -> absence is DISCARDED
LEFT  JOIN = all left rows preserved      -> absence is EVIDENCE (child columns NULL)
```

A queued Job with no Attempt row vanishes under `INNER JOIN` — which hides exactly the backlog operations needs. NULL Attempt columns mean "no Attempt row exists", not corrupt data.

**Cardinality and row multiplication.** A join returns every matching *combination*, not a step-by-step filter:

```text
Attempts  Events  Rows (Job preserved via LEFT JOIN)
0         0       1    <- NULL-extended row still counts
0         4       4    <- the NULL-extended row matches EVERY Event
3         0       3
3         4       12   <- 3 x 4, NOT 4 and NOT 0
```

Two **independent** one-to-many children must never be joined in one aggregating statement.

`COUNT` semantics after `LEFT JOIN`:

```text
COUNT(*)            = result ROWS, including the NULL-extended row  -> 1 for a zero-Attempt Job
COUNT(a.attempt_id) = non-NULL child identities                     -> 0 for a zero-Attempt Job
```

Conditional aggregation keeps the condition **inside** the aggregate: `COUNT(a.attempt_id) FILTER (WHERE a.error_code IS NOT NULL)`, portably `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`. Moving that predicate into `WHERE` deletes successful Attempts **and** the placeholder row — silently collapsing `LEFT JOIN` into `INNER JOIN`.

```text
WHERE  -> filters INPUT rows BEFORE grouping (tenant, status, raw time)
HAVING -> filters GROUPS AFTER aggregation   (COUNT(...) >= $2)
```

**NULL is unknown, not zero.** `SUM`/`AVG` skip NULL, so they describe **recorded** facts: `AVG` divides only by reporting Attempts. Name columns `recorded_total_cost_micros` / `recorded_average_cost_micros` and publish completeness (`COUNT(cost_micros)` beside `COUNT(attempt_id)`). `COALESCE(SUM(cost_micros), 0)` turns "unknown" into the billing claim "it cost nothing" — reject it.

Queue health: `COUNT(*)`, `MIN(created_at)`, `now() - MIN(created_at)`. Empty queue returns count `0` and **NULL** age — "no backlog" and "no data" must not render identically.

**Name the metric after the clock it uses.** `jobs.created_at` is **acceptance** time, not current queued-stage entry. For `queued -> running -> failed -> queued`, `created_at` charges the earlier lifecycle to the current wait, so the honest names are `oldest_accepted_at` / `accepted_age_of_oldest_currently_queued_job`. For the true stage age, use `job_events` — but **do not pre-filter**. Selecting "the latest event WHERE `to_status = 'queued'`" returns a stale `t1` for a Job that went `queued -> running -> failed -> queued` when the second queued Event was never written, and presents it as a multi-hour stage age. Select each Job's **latest event of any kind**, then accept it only if `to_status = 'queued'`:

```sql
SELECT DISTINCT ON (e.job_id) e.job_id, e.occurred_at, e.to_status, e.event_id
FROM app.job_events AS e
ORDER BY e.job_id, e.occurred_at DESC, e.event_id DESC   -- no to_status filter
```

Three honest outcomes, not one number:

```text
recorded_queued_transition            -> queued_since = latest event; age meaningful
no_event_history_acceptance_fallback  -> no events at all; created_at used; age is an UPPER BOUND
event_history_inconsistent            -> events exist but latest is not queued while job_status is
                                         -> queued_since / queued_stage_age stay NULL
                                         -> never substitute an older queued Event
```

Event-history completeness is a **write-path convention, not a schema guarantee** (no schema change — Day31 already records `to_status` and `occurred_at`). A missing Event is not proof no transition happened.

**CTE pre-aggregation** is the structural fix for two children: collapse each child to one row per `job_id` first, then `LEFT JOIN` the summaries one-to-one. `COUNT(DISTINCT ...)` repairs counts but leaves `SUM` multiplied, and `SUM(DISTINCT ...)` is wrong outright (two Attempts may legitimately cost the same).

**Stage-aware clocks.** `jobs.started_at` = customer-facing elapsed time including retries; the **current Attempt's** `started_at` = the execution hanging now. Select the current Attempt deterministically:

```sql
SELECT DISTINCT ON (a.job_id) ...
FROM app.job_attempts AS a
ORDER BY a.job_id, a.attempt_number DESC, a.attempt_id DESC   -- Day30 tie-breaker rule
```

Anomaly classes are **candidates, not verdicts**: `running_without_attempt`, `running_with_finished_current_attempt`, `running_attempt_over_threshold`, `running_within_threshold`. `running_without_attempt` is a **coherence** anomaly (partial multi-table write, legacy path, repair error), not proof a Worker died — that needs Day34 lease/heartbeat evidence. Thresholds are operational policy reflecting long AI Provider runtimes, never constants.

**Half-open windows** `[start, end)`: `finished_at >= $2 AND finished_at < $3`. `BETWEEN` counts a boundary row in two consecutive windows, so hourly totals exceed the daily total. Also state which timestamp defines membership — `finished_at` = completed in window, `created_at` = arrived (accepted demand) in window.

**A `finished_at` window is not a terminal filter.** A non-terminal row with an anomalous `finished_at` (partial write, repair error, legacy path) lands in the window and is counted as throughput. Add the allowlist explicitly so the arithmetic is true by construction:

```sql
AND j.job_status IN ('succeeded', 'failed', 'cancelled')
-- terminal_jobs = succeeded_jobs + failed_jobs + cancelled_jobs
```

Day31 guarantees only that `succeeded` implies `finished_at IS NOT NULL`; other terminal states may carry NULL finish time, fall outside the window, and need a separate coherence report — never read as zero throughput.

**Provenance beats time correlation.** During a rolling deployment old and new Workers coexist, so a pre-deployment Job may run on the new release and vice versa; one Job's retries may span both. `SELECT DISTINCT e.job_id ... WHERE e.metadata ->> 'worker_release_id' = $2` is the honest interim source. Two limits ship with the result: Day31 does not enforce that every write path records truthful metadata (a missing key is not proof of non-involvement), and typed per-execution provenance is a **Day36** schema-evolution decision, not a silent Day32 alteration.

**Rollback boundaries (restated in SQL):**

```text
Rollback  -> stops FUTURE bad writes
Rollback !-> repairs committed rows
Rollback !-> undoes provider charges, emails, or PUBLISHED outbox events
```

Incident evidence is read-only by design: attempt evidence + artifact existence + outbox publication state + an `evidence_class` classification. `finished_at IS NULL` with zero Artifacts does **not** prove the Provider did nothing — the call may be in flight, may have succeeded with a lost response, or the Worker may have crashed before persisting evidence. `published_at IS NULL` may mean "never sent" **or** "sent, then crashed before write-back". Rollback retries nothing; **blind bulk requeue** is what repeats Provider work and cost.

Real counts may be `COALESCE(..., 0)` — a zero-Attempt Job genuinely has `cost_reported_attempts = 0`. Cost values (`recorded_total_cost_micros`, `recorded_average_cost_micros`) must stay **NULL**, because unknown cost is not zero cost.

Scope note: Day32 queries are written for **meaning only** — no indexes, `EXPLAIN`, transactions, locks or DML. Atomicity is Day33, concurrency Day34, indexes Day35 — and none of them rescue a wrong grain.

---

## Day33 PostgreSQL Transactions and Atomic State Changes

A transaction is **one business commitment**: `BEGIN` ... `COMMIT` makes all related database facts durable together; `ROLLBACK` discards the whole current transaction. `ROLLBACK` never undoes a **prior** COMMIT — "can I roll it back?" means "is it still uncommitted?".

**Accept invariant (creation-time).** At acceptance, create the durable Job together with the durable Outbox intent to **dispatch** it — put both INSERTs in one transaction. This is a creation-time coupling, **not** a permanent `Job <=> Outbox row` equivalence: retention may later archive published rows, and not every future Event needs an Outbox row. The Relay scans `app.outbox_events`, not `app.jobs`, so a Job committed without its dispatch Outbox row sits queued forever (the classic separate-commit stall).

**Return 202 AFTER COMMIT.** `202 + job_id` acknowledges an existing durable commitment. If COMMIT succeeds but the response is lost, the client retry is made safe by `UNIQUE (tenant_id, idempotency_key)` + lookup — the transaction cannot tell the client the outcome.

**Zero affected rows != error.**

```text
SQL / constraint error -> transaction FAILED, must ROLLBACK
zero affected rows     -> NORMAL result; the APPLICATION must gate and stop
```

A guarded `UPDATE ... RETURNING` returning 0 rows is `transition_not_applied`: roll back and stop. If the app runs the next INSERT anyway it creates a duplicate Attempt/Event. `UNIQUE (job_id, attempt_number)` stops a duplicate **number** only; it cannot replace the transition guard. Never claim `BEGIN/COMMIT` alone makes a zero-row UPDATE fail.

**Atomic Start = three facts in one transaction:** guarded `queued -> running` (with `attempt_count = attempt_count + 1` database-side, returned as the new `attempt_number`), the Attempt, and the append-only `job_started` Event. A crash after only the status commit is Day32's `running_without_attempt`.

**ACID from the scenario:** Atomicity = all-or-nothing DB facts; Consistency = constraints hold, but guarded app logic still enforces the business transition (ACID does not invent correct logic); Isolation = concurrent interaction (Day34); Durability = facts survive process crash after COMMIT.

**The external boundary.** PostgreSQL commits/rolls back **only its own rows**. It cannot roll back a Provider call or its cost, Object Storage bytes, a Redis/Queue publish, or a webhook. So:

```text
short START transaction -> COMMIT
external Provider + Object Storage phase   (NO open DB transaction)
short COMPLETE transaction -> COMMIT
```

Never hold a transaction across an eight-minute call: it pins a connection, may hold row locks + an old snapshot, and still cannot undo the external work. After Provider success but before Complete, PostgreSQL proves only the start facts and can prove nothing about the Provider result.

**Two Provider identifiers — do not conflate.** The **pre-call** `provider_idempotency_key`/correlation key is generated *before* the request from an already-durable fact (use `attempt_id`, committed in Transaction B) and is the **recovery anchor** — send it to the Provider if it supports idempotency keys. The Provider-**returned** `provider_request_id` does not exist until the call returns and is persisted only in Transaction C; it is a lookup convenience, **not** the recovery anchor. Transaction B does **not** persist a returned id. A crash after the call but before Transaction C loses `provider_request_id` — but `attempt_id` is already durable, so reconciliation can still find/dedupe the call **provided the Worker actually sent it to a Provider that supports idempotency/lookup** (durability alone proves nothing to the Provider). If the Provider has no such mechanism, PostgreSQL cannot close this window: isolate + reconcile, never blind-retry.

**Do not overwrite a finished Attempt.** Transaction C's Attempt-finish UPDATE guards with `AND finished_at IS NULL`; 0 rows (Attempt missing, wrong Job, or **already finished**) -> ROLLBACK and stop. Never overwrite a finished Attempt's `finished_at`/`provider_request_id`/`cost_micros` — that destroys recorded evidence. An already-finished current Attempt on a still-running Job is `running_with_finished_current_attempt`: isolate + reconcile, never auto-"fix" to succeeded.

**Integrated rollback:** if the Completion transaction rolls back (e.g. Artifact `UNIQUE (attempt_id, object_key)` violation), none of Attempt-finish / Job-succeeded / Event / Artifact / any Outbox row survive — but the **Provider cost and Object Storage bytes remain**. Database rollback is not Object Storage rollback; the object may be orphaned pending reconciliation or an audited compensating delete.

**Job Event vs Outbox Event.** A `job_events` row is **internal business history** (append one per state change). An `app.outbox_events` row is a **pending external integration duty** — create one ONLY when a real downstream consumer must be told (dispatch, notification, webhook, billing, indexing). **Not every Job Event needs an Outbox Event.** `job.accepted` has a real consumer (dispatch); the completion `job.succeeded` Outbox is **conditional** — the artifact leaves it commented out because this project defines no consumer, so it is optional, not mandatory. Outbox **payload** carries stable ids + minimal references only: no result bytes, no secrets, no signed URLs; the consumer fetches the authorized result via a stable reference; `outbox_event_id` is its idempotency key; publication is at-least-once and never proves consumer business success.

**Outbox lifecycle.** The row is durable **publication intent + audit evidence**, created `published_at = NULL`. The Relay polls/claims it, publishes, then sets `published_at = now()` after Queue ack — it does **not** delete the row or reset it to NULL.

```text
published_at IS NULL     -> never attempted, in flight, OR published-then-crashed before write-back
published_at IS NOT NULL -> Relay RECORDED a publish; NOT proof of Queue delivery or consumer success
```

Three distinct checkpoints: Relay recorded publish != Queue delivered != consumer processed. A Relay crash after publish but before write-back republishes the **same** `outbox_event_id`.

**Delivery model.** No retry under uncertainty = **at-most-once** (may lose). Retry = **at-least-once** (may duplicate). Exactly-once is **not** obtained by disabling retries. Practical correctness = at-least-once publication + stable `outbox_event_id` + **idempotent consumer**. The stable id does not stop Relay retransmission; it stops duplicate **business processing**.

**Lost COMMIT response** = unknown outcome. Do not assume rollback — reconnect and read stable ids (`idempotency_key`, `job_id`, `outbox_event_id`). Atomicity prevents partial facts; idempotency makes the retry safe.

**Write-path contract, not a schema guarantee.** The transaction pack binds only writers that use it. A legacy Worker committing separately can still leave partial facts — drain old Workers, centralize write paths, monitor Day32 coherence queries. The schema does not enforce that all child rows are present.

Scope: Day33 has no `FOR UPDATE`/`SKIP LOCKED`/MVCC tuning (Day34), no indexes/`EXPLAIN` (Day35), no migrations (Day36), no ORM. Locks cannot repair a wrongly defined business transaction.

---

## Day34 Concurrency Control, MVCC, and Worker Claims

**Visibility != ownership.** A plain `SELECT` shows candidates; two Read Committed sessions can both see the same queued Job. Ownership is a **lock** (transaction-local) and, once it must survive COMMIT, a **committed lease**. Never treat a candidate SELECT as a claim.

**`FOR UPDATE`** requests a row lock; a conflicting locker **waits**, ordinary MVCC reads are not blocked. The lock is transaction-local (gone at COMMIT/ROLLBACK) and must never span an eight-minute Provider call.

**`FOR UPDATE SKIP LOCKED`** skips rows locked by other claim transactions and takes the next **available** row — Workers spread across the queue instead of convoying on the head. Right for a queue claim, wrong for a complete report.

**The claim transaction** (active `006`, Day31 schema):

```text
BEGIN
  -> SELECT one ELIGIBLE queued candidate FOR UPDATE SKIP LOCKED
       eligibility = tenant_id + job_status = 'queued' + cancel_requested = false, ordered by created_at, job_id
  -> guarded queued->running UPDATE ... RETURNING            (the UNCHANGED Day33 write)
       re-checks the SAME eligibility (queued AND cancel_requested = false)
  -> only on the 1-row path: INSERT Attempt + job_started Event
COMMIT
  -> THEN call the Provider, OUTSIDE any transaction
```

**Eligibility, not just status.** `app.jobs` also has `cancel_requested boolean NOT NULL DEFAULT false`. A committed-cancel Job may still be `queued` briefly; claiming it would run it and cost a Provider call. So BOTH the `FOR UPDATE SKIP LOCKED` candidate SELECT and the guarded UPDATE filter `AND cancel_requested = false`. The UPDATE repeats it **defensively** (direct-update / optimistic / future-refactor paths), **not** because a same-row cancel can commit between the locking SELECT and the UPDATE — the `FOR UPDATE SKIP LOCKED` lock already holds the row until the claim commits, so it cannot. Orderings: cancel commits first -> the candidate SELECT excludes the Job; cancel holds the lock -> `SKIP LOCKED` skips that row and keeps scanning (it may return another eligible Job, or 0 rows if none is available -> back off, no wait); claim locks first -> the cancel transaction waits and, after the claim commits, re-evaluates under its own guarded policy (Day34 does not define that UPDATE). (One predicate, not a cancellation state machine.) 0 rows from the SKIP LOCKED select = no eligible queued Job (locked, cancel-requested, or empty) -> back off, normal. 0 rows from the guarded UPDATE = `transition_not_applied` -> ROLLBACK/stop (Day33 gate).

**`SKIP LOCKED` weakens fairness.** `ORDER BY` sorts only currently-**available** rows, so no strict FIFO and a long-held row can **starve**. Mitigate operationally: short claim transactions; monitor oldest queued age / lock waits / expired leases; a recovery sweeper. (Index proof is Day35.)

**A released lock is not liveness.** After the Start COMMIT the lock is gone but Job/Attempt/Event are durable. A missing lock does not mean the Worker died; blind reclaim duplicates Attempt, Event, and Provider cost.

**Row lock vs committed lease.** Row lock = transaction-local exclusion (gone at COMMIT). Lease = **committed** ownership: `claim_owner` + `lease_token` + `lease_expires_at`. These lease columns are **NOT in the Day31 schema**; adding them is a Day36 migration. In `006` they are commented/conceptual only — never active SQL.

**Lease expiry is a takeover condition, not death.** A paused/partitioned Worker may resume after expiry. **Takeover writes a new `lease_token`; expiry alone does not change the token** — it invalidates ownership via the `lease_expires_at <= now()` time predicate. Completion guards current token + running + unexpired lease; a stale token returns 0 rows and rolls the Completion transaction back.

**Lease duration** comes from heartbeat interval + observed pause, **not** Provider duration. For an 8-min Job with ~45s heartbeat pauses, ~2 min beats 30 s (which would false-take-over during a normal pause). Short lease = faster true-failure recovery, more false takeover; long lease = fewer false takeovers, slower recovery. Renew with PostgreSQL `now()`, not Worker clocks.

**`lease_token` != Provider idempotency key.** `lease_token` = one ownership epoch, **changes on takeover**. The Provider key = the same logical external operation, **stable** (derive from durable `attempt_id`, actually **send** it to a Provider that supports idempotency/lookup). Using a new token as a new Provider key defeats idempotency and can repeat charges. No Provider support -> isolate + reconcile.

**Pessimistic vs optimistic.** `FOR UPDATE SKIP LOCKED` (pessimistic reservation) spreads a **high-contention** queue. Optimistic expected-status/version guard suits **low-contention** edits; 100 Workers on the oldest Job = one winner + a retry storm. More isolation is not automatic work partitioning.

**MVCC / isolation.**

```text
READ UNCOMMITTED -> treated as READ COMMITTED
READ COMMITTED   -> NEW snapshot per statement (100 then 101 = a PHANTOM, allowed, not broken atomicity)
REPEATABLE READ  -> one STABLE txn snapshot; conflicting writer may abort with 40001
SERIALIZABLE     -> outcome == some serial order; also whole-txn retry on 40001
phantom = changed PREDICATE result; non-repeatable = changed VALUE for same row;
dirty read = uncommitted (PostgreSQL disallows); lost update = stale read-compute-write overwrite
```

Stable snapshots do **not** partition work; ownership is always explicit.

**Deadlock & retry.** Reverse-order lock cycle -> PostgreSQL **detects** it, aborts one victim with `40P01` (does not wait forever, does not auto-retry). **Prevent** with a consistent global lock order (e.g. ascending `job_id`, obeyed by every writer). **Bound** ordinary waits with `lock_timeout`/`statement_timeout` (`55P03` on a lock-timeout cancel) — bounds do not replace ordering. **Retry** `40P01`/`40001` from the **application**: ROLLBACK and re-run the whole transaction, finite budget + jitter, reusing idempotent ids. `UNIQUE (job_id, attempt_number)` / `(tenant_id, idempotency_key)` still stop duplicate durable facts.

Scope: Day34 adds no `CREATE INDEX`/`EXPLAIN` (Day35), no `ALTER`/migration (Day36), no ORM/Redis. Locks/leases decide ownership; UNIQUE decides identity; a stable Provider key protects the external call; none replaces another.

---

## Day35 PostgreSQL Indexes and Query Planning

**An index is an ADDITIONAL access structure over the Heap**, not a replacement source of truth. It speeds CANDIDATE lookup; `FOR UPDATE SKIP LOCKED` still visits and locks the real Heap tuple. An index existing is not an Index-Only claim and does not replace Day34's lock/lease/guarded transition.

**Design from the query shape**, not a chosen column: leading EQUALITY predicates -> then RANGE / `ORDER BY` columns. A `job_status`-only index is weak (no tenant narrowing, no ordering, low-cardinality leaves a big set).

**Claim access path (Day34)** -> Partial Composite:

```sql
CREATE INDEX jobs_claim_queue_idx
    ON app.jobs (tenant_id, created_at, job_id)
    WHERE job_status = 'queued' AND cancel_requested = false;
```

`tenant_id` equality -> `created_at, job_id` order; partial predicate keeps only claimable rows (small, hot). Design only — NOT executed / NOT plan-validated.

**Keys serve an access path, not every selected column.** Unindexed returned columns come from the Heap. But a Partial Index that OMITS the target rows cannot answer the query — the claim index fails all-status history because it contains only queued/not-cancelled rows (membership), not because a column is missing.

**History is several paths, measure don't default:** all-status `(tenant_id, created_at DESC, job_id DESC)`; dynamic-status shared composite `(tenant_id, job_status, created_at DESC, job_id DESC)`; or fixed-status Partial Indexes for a few selective/frequent statuses. One general index vs many narrow ones is a trade.

**A UNIQUE constraint is already an index.** Day31's `UNIQUE (tenant_id, idempotency_key)` auto-created a unique B-tree that serves the lookup; a duplicate ordinary index adds storage/write/Vacuum/cache cost and no new capability. Do not add it.

**Outbox poll** -> Partial:

```sql
CREATE INDEX outbox_unpublished_idx
    ON app.outbox_events (created_at, outbox_event_id)
    WHERE published_at IS NULL;
```

`job_id` is SELECTED but neither filtered nor ordered -> NOT a leading key. Almost all rows are published, so the partial set is small.

**`now()` cannot be a Partial Index predicate.** Partial membership only changes on a WRITE; `now()` moves without writes. Use a STABLE predicate (`WHERE job_status = 'running'`) and test expiry as a QUERY-TIME range (`lease_expires_at <= now()` in the query). The lease columns don't exist until Day36 — stale-lease index stays conceptual.

**`EXPLAIN` estimates a plan (no execution). `EXPLAIN ANALYZE` EXECUTES it** — real row locks on `SELECT ... FOR UPDATE`, real changes on DML (wrap in a `ROLLBACK` transaction, disposable cluster only). `EXPLAIN (ANALYZE, BUFFERS)` adds page/cache evidence. A node name is not a conclusion.

**A Seq Scan is a COST-BASED plan and may be OPTIMAL** (small table, high match fraction, cache-hot, or to avoid random Heap reads). Concerning only with evidence: e.g. 8M rows, ~0.2% queued, ~1.6 s, ~7.9M `Rows Removed by Filter`, high Buffer Reads.

**Estimate vs actual divergence** (1 vs 20,000) -> investigate **statistics / data skew / predicate shape / casts / parameter planning** and refresh statistics (`ANALYZE`) BEFORE adding an index. Validation sequence: plain `EXPLAIN` -> controlled `EXPLAIN (ANALYZE, BUFFERS)` -> workload metrics (claim p95/p99, oldest queued age, I/O/CPU, lock impact, write-path latency).

**Index maintenance cost.** An UPDATE maintains only indexes whose key/included values or PARTIAL membership change. `queued -> running`: the claim partial index is MAINTAINED (row leaves it); `(tenant_id, created_at, job_id)` history and the idempotency unique index are UNCHANGED (keys unchanged).

**Keep an index only for NET SYSTEM benefit.** The classroom case: a broad history/status index moved history p95 100->80 ms but Job acceptance p99 50->220 ms, cost +14 GB, no Worker/Outbox gain -> roll back only that index, keep proven claim/Outbox/unique paths. A read win that inflates acceptance p99 is a net loss; check whether the cost merely MOVED.

Scope: Day35 = DESIGN + EVIDENCE only. NOT executed / NOT plan-validated (no server, `EXPLAIN`, benchmark, or DDL). `CREATE INDEX CONCURRENTLY`, DDL-lock windows, and rollout/rollback are Day36.

---

## Interview Phrases

- "The Job row is committed before 202; 202 acknowledges an existing durable commitment."
- "A psql session connects to a database, not a schema; qualify names or set search_path."
- "`public` is a default namespace, not a data classification."
- "Typed columns carry identity, state and time; bounded JSONB carries optional extras."
- "One-to-many is relationship cardinality, not a column type."
- "NOT NULL rejects NULL only — empty string and arbitrary text still pass."
- "A primary key identifies a row; an idempotency key identifies a business request."
- "timestamptz is one absolute instant rendered in the session time zone."
- "Durability is not integrity: a misspelled status is durable and unclaimable."
- "Code rollback stops future bad writes; a guarded UPDATE repairs persisted facts."
- "Never claim validation beyond the level you actually executed."

- "WHERE is the modification boundary; RETURNING and affected rows are the evidence."
- "ORDER BY without a unique tie-breaker returns an unstable page."
- "WHERE keeps only TRUE — NULL comparisons are UNKNOWN, so use IS NULL."
- "`<> 'timeout'` silently drops every row with no error."
- "RETURNING returns rows, not a count."
- "Parameters bind values only; identifiers need an allowlist."
- "Parameterization closes the injection boundary — not authorization or concurrency."
- "Zero rows means the transition did not apply, not that the Job does not exist."
- "AND binds tighter than OR — parenthesize destructive predicates."
- "Fix a lost update inside one statement: SET attempt_count = attempt_count + 1."
- "Contain first, reconcile before repairing; code rollback never repairs persisted rows."

- "A primary key says who the row is; a business key says which operation must not repeat."
- "UNIQUE is only as correct as its scope — unique within what?"
- "A retry brings a new job_id, so only (tenant_id, idempotency_key) stops duplicate requests."
- "One-to-many puts the foreign key on the many side; one-to-one is a foreign key plus UNIQUE."
- "Many-to-many needs a junction table, and the relationship can carry its own attributes."
- "ON DELETE is retention policy: CASCADE on audit-bearing children erases incident evidence."
- "NOT NULL says the state exists; CHECK says it is legal on every write path."
- "A row CHECK sees only this row — it cannot assert that a child row exists."
- "Store attempt_id once and derive job_id; duplicated facts can contradict each other."
- "Composite foreign keys enforce same-tenant relationships; they never authorize a reader."
- "A failed ADD CONSTRAINT protects nothing — reconcile the committed duplicates first."
- "Assert the specific SQLSTATE; 'any error' would pass on a typo."

- "Define the result grain first: one row = one what?"
- "Choose the join from what a MISSING row means — INNER discards absence, LEFT preserves it."
- "A join returns combinations, not a filtered sequence: 3 Attempts x 4 Events = 12 rows."
- "A zero-Attempt Job joined to 4 Events returns 4 rows, not 0 — the NULL-extended row matches all."
- "COUNT(*) counts rows; COUNT(child_pk) counts existence."
- "FILTER narrows an aggregate; WHERE narrows the input set — and collapses LEFT into INNER."
- "WHERE filters rows before grouping; HAVING filters groups after aggregation."
- "NULL is unknown, not zero — SUM and AVG describe records, not reality."
- "COALESCE(SUM(cost), 0) turns 'we do not know' into 'it cost nothing' on a billing page."
- "Pre-aggregate each child in a CTE, then join one-to-one; DISTINCT patches counts, not SUM."
- "Match the clock to the stage: Job clock is the SLA, current-Attempt clock is the hang."
- "Time windows are half-open [start, end) — BETWEEN double-counts boundary rows."
- "Recorded provenance is the affected set; a time window is a proxy you must disclose."
- "No completion recorded is not the same as the provider call being dead."
- "Rollback stops future bad writes; committed rows and published outbox events remain."

- "A transaction is one business commitment: all related DB facts commit together or roll back together."
- "ROLLBACK undoes the current transaction, never a prior COMMIT."
- "At acceptance, create the Job together with its dispatch Outbox intent — a creation-time coupling, not a permanent Job-to-Outbox equivalence."
- "Return 202 after COMMIT; a lost response is resolved by idempotency-key lookup, not the transaction."
- "Zero affected rows is a normal result the app must gate on; a constraint error is what fails a transaction."
- "UNIQUE(job_id, attempt_number) stops a duplicate number, not a missing transition guard."
- "Consistency means constraints hold, not that the business transition was correct."
- "Never hold a transaction across an eight-minute Provider call — split into two short ones."
- "The recovery anchor is the pre-call idempotency key (durable attempt_id) ACTUALLY SENT to the Provider, not the returned provider_request_id (persisted only in C, and losable) — and only if the Provider supports idempotency/lookup."
- "Transaction B persists attempt_id, not a Provider-returned id; guard Attempt-finish with finished_at IS NULL."
- "Not every Job Event needs an Outbox Event; publish only when a real consumer must act."
- "Database rollback is not Object Storage rollback; Provider cost and bytes survive."
- "The Outbox row is durable intent; the Relay does not take it or reset published_at to NULL."
- "published_at NOT NULL proves a recorded publish only — not delivery or consumer success."
- "at-most-once loses, at-least-once duplicates, exactly-once is not disabling retries."
- "The same outbox_event_id stops duplicate processing, not duplicate publication."
- "A lost COMMIT response is unknown — read stable ids, do not assume rollback."
- "A transaction pack is a write-path contract, not a schema guarantee."

- "A SELECT is candidate visibility; ownership is a lock, then a committed lease."
- "FOR UPDATE waits on a conflict; FOR UPDATE SKIP LOCKED takes the next available row."
- "SKIP LOCKED spreads Workers across the queue but gives no strict FIFO and can starve a row."
- "A released row lock is not liveness evidence; blind reclaim duplicates Attempt, Event, and Provider cost."
- "A row lock is transaction-local; a committed lease (owner+token+expiry) survives COMMIT — and is Day36 schema, conceptual today."
- "Lease expiry is a takeover condition, not death; takeover writes the new token, expiry alone does not."
- "lease_token is one ownership epoch; the Provider idempotency key is stable per external operation — never cross them."
- "Read Committed takes a new snapshot per statement; 100 then 101 is an allowed phantom."
- "Stronger isolation prevents anomalies; it does not partition work across Workers."
- "A reverse-order deadlock is detected and one victim aborts with 40P01; the application retries, not PostgreSQL."
- "Consistent lock order prevents the cycle; lock_timeout only bounds the wait (55P03)."
- "Locks/leases decide ownership, UNIQUE decides identity, a stable Provider key protects the external call."

- "An index is an additional access structure over the Heap; the claim still locks the real tuple."
- "Design the index from the real WHERE + ORDER BY + LIMIT, not from a chosen column."
- "B-tree order: leading equality predicates, then range / ORDER BY columns."
- "A Partial Index that omits the target rows can't answer the query — membership, not columns."
- "A UNIQUE constraint already builds a unique B-tree; never duplicate the idempotency index."
- "Outbox = (created_at, outbox_event_id) WHERE published_at IS NULL; job_id is selected, not a key."
- "now() can't define partial membership; use a stable predicate + a query-time range."
- "EXPLAIN estimates; EXPLAIN ANALYZE executes — real row locks and real DML changes."
- "A Seq Scan is a cost-based plan and can be optimal; judge by selectivity, filtered rows, buffers."
- "Estimate vs actual divergence is a statistics/skew investigation before another index."
- "Keep an index only for net system benefit; a read win that inflates acceptance p99 is a loss."
- "Day35 designs and validates evidence; Day36 deploys it safely (CONCURRENTLY, DDL locks)."
