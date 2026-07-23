# Lesson 35 — PostgreSQL Indexes and Query Planning

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day34 — Concurrency Control, MVCC, and Worker Claims

Previous Lesson: [Day34 — Concurrency Control, MVCC, and Worker Claims](day34-concurrency-control-mvcc-and-worker-claims.md)

Next Lesson: [Day36 — Schema Evolution and Safe Migrations](day36-schema-evolution-and-safe-migrations.md)

Engineering Artifact: The Day35 index/EXPLAIN reference pack (`sql/007_postgresql_indexes_and_query_planning.sql`) — candidate B-tree index designs for the real Day33/Day34 access paths, parameterized `EXPLAIN` templates, and a stale-lease design kept conceptual — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

PostgreSQL Cheat Sheet: [cheat_sheets/postgresql.md](../../cheat_sheets/postgresql.md)

PostgreSQL Interview: [interview/postgresql.md](../../interview/postgresql.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 100-130 minutes
Hands-on index design + disposable-PostgreSQL EXPLAIN practice: 100-130 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Explain that an index is an **additional access structure** over Heap rows, not a replacement source of truth, and that a locking claim still visits and locks the real Heap tuple.
2. Derive a **Partial Composite B-tree** for the Day34 claim from its real predicate and ordering: `(tenant_id, created_at, job_id) WHERE job_status = 'queued' AND cancel_requested = false`.
3. Order composite columns by the access path — leading equality predicates first, then range/`ORDER BY` columns — and say why a `job_status`-only index is weak.
4. Separate the claim path from all-status history, dynamic status-filtered history, and fixed-status Partial Index candidates, and choose among them by **measured** workload, not by default.
5. Explain why the Day31 `UNIQUE (tenant_id, idempotency_key)` already provides a unique B-tree access path, so a duplicate ordinary index is pure cost.
6. Design the unpublished-Outbox Partial Index `(created_at, outbox_event_id) WHERE published_at IS NULL`, and say why a selected-but-unfiltered column (`job_id`) is not a leading key.
7. Reject a `now()`-based Partial Index predicate and instead design a stable running-job Partial Index with a **query-time** range test — kept conceptual until Day36 adds the lease columns.
8. Use `EXPLAIN` (plan-only) vs `EXPLAIN ANALYZE` (real execution, with row-lock and DML side effects) honestly, and read estimates vs actual rows, `Rows Removed by Filter`, and buffers.
9. Judge a Sequential Scan as a **cost-based** choice, and treat estimate-vs-actual divergence as a statistics/skew investigation before adding indexes.
10. Decide to keep or roll back an index by **net system benefit** — read gain vs write/storage/Vacuum/cache cost and whether cost merely moved elsewhere.

---

# Why This Matters

Day34 made the Worker claim correct under concurrency. Day35 asks the next question: is it **fast**, and at what cost? Hundreds of Workers hammer one access path — `tenant_id + job_status = 'queued' + cancel_requested = false` ordered by `created_at, job_id` — and without the right index that claim degrades into a sequential scan over millions of rows to find a handful of queued ones.

But indexing is not "add an index to every slow query." Every index is a standing tax on every write, on storage, on cache, and on Vacuum. The dangerous move is optimizing one dashboard while quietly inflating the p99 of Job acceptance — the `202` your whole system depends on. So Day35 is really about **evidence**: design an index from the real query shape, prove it with honest `EXPLAIN` output on representative data, and keep it only if the whole system is better off.

And the discipline that carries from Day34 holds here: an index speeds *candidate lookup* only. It does not replace the lock, the lease, or the guarded transition. Correctness and ownership come first; performance is measured on top of them.

---

# Roadmap Position

```text
Day31  durable state, constraints, identity (incl. UNIQUE (tenant_id, idempotency_key))
Day32  operational reads
Day33  atomic multi-table writes
Day34  concurrency-correct claims (the exact predicate + ordering Day35 indexes)
Day35  measured, cost-aware access paths for those predicates   <-- you are here
Day36  safely DEPLOY schema/index changes on populated data (CONCURRENTLY, rollout)
Day37  monitor slow queries, lock/connection pressure, Vacuum, capacity
```

Day35 designs and validates; it does **not** deploy. The safe online build (`CREATE INDEX CONCURRENTLY`), DDL-lock windows, and rollout/rollback mechanics are Day36. Day35 decides *which* index and *whether the evidence justifies it*.

---

# Lesson Map

```text
1. Index over Heap, not instead of it   -> the claim still locks the real tuple
2. The claim access path                -> why job_status-only is weak
3. The claim Partial Composite index     -> (tenant_id, created_at, job_id) WHERE ...
4. Keys serve an access path             -> not every SELECT-list column
5. History is a different path            -> all-status vs dynamic-status vs partial
6. Unique constraint = an index           -> do not duplicate the idempotency index
7. Outbox partial index                   -> (created_at, outbox_event_id) WHERE unsent
8. now() cannot be a partial predicate     -> query-time range; stale-lease is Day36
9. B-tree column order                     -> equality first, then range/ORDER BY
10. EXPLAIN vs EXPLAIN ANALYZE             -> plan vs real execution + side effects
11. Seq Scan is cost-based                 -> healthy vs harmful, by evidence
12. Estimate vs actual                     -> statistics/skew before more indexes
13. Validation sequence                    -> EXPLAIN -> ANALYZE,BUFFERS -> workload
14. Index maintenance cost                 -> what queued->running actually touches
15. Net-benefit keep/rollback decision      -> the 100->80 / 50->220 / +14GB case
```

---

# Core Mental Model

```text
An index is an ADDITIONAL access structure over Heap rows, never the source of truth.
    It speeds CANDIDATE lookup. FOR UPDATE SKIP LOCKED still visits and locks the Heap tuple.

Design the index from the REAL query shape:
    leading EQUALITY predicates -> then RANGE / ORDER BY columns.
    A Partial predicate keeps only the rows a path needs (small, hot).

A UNIQUE constraint is already an index. Do not duplicate it.
A now()-based predicate cannot define partial membership (no write moves the row); test time at QUERY time.

EXPLAIN estimates a plan (no execution). EXPLAIN ANALYZE EXECUTES it (real locks / real DML changes).
A Seq Scan is a COST-BASED choice and may be optimal. A node name is not a conclusion.
Estimate vs actual divergence -> investigate statistics/skew FIRST, not "add another index".

Keep an index only for NET SYSTEM benefit:
    read gain weighed against write amplification + storage + cache + Vacuum, and whether cost just MOVED.
```

---

# Main Concepts

## Concept 1: An Index Is Over the Heap, Not Instead of It

Tech Lead Question:

If a claim query has an index, does the Worker still touch the actual row?

Tech Lead Teaching:

Yes. An index is an **additional access structure** over the Heap tuples — it navigates you to a
candidate quickly, but `FOR UPDATE SKIP LOCKED` still visits and **locks the real Heap tuple**. An index
existing does not make a locking claim an Index-Only Scan, and it does not replace the Day34 lock, lease, or
guarded transition. Candidate lookup gets faster; ownership is unchanged.

Engineering Thinking:

Speed and correctness live in different layers. The index is a shortcut to the row, not a substitute for
locking it.

## Concept 2: The Claim Access Path (and Why `job_status`-only Is Weak)

Tech Lead Question:

The Day34 claim is `WHERE tenant_id = $1 AND job_status = 'queued' AND cancel_requested = false ORDER BY
created_at, job_id LIMIT 1 FOR UPDATE SKIP LOCKED`. What index would you add?

Student Answer:

> "我不知道加什么索引"

Tech Lead Review:

Honest, and the right place to start — because the answer is not guessed, it is **derived from the query
shape**. Start from the real `WHERE`, `ORDER BY`, and `LIMIT`, not an arbitrary column. A `job_status`-only
index is weak: it cannot first narrow by `tenant_id`, it cannot supply the `(created_at, job_id)` order, and
`'queued'` is low-cardinality, so it can still hand back a large set to sort and filter.

Engineering Thinking:

An index is designed backward from the query it must serve. "Which column?" is the wrong question;
"which predicate and ordering?" is the right one.

## Concept 3: The Claim Partial Composite Index

Tech Lead Teaching:

```sql
CREATE INDEX jobs_claim_queue_idx
    ON app.jobs (tenant_id, created_at, job_id)
    WHERE job_status = 'queued' AND cancel_requested = false;
```

The **partial predicate** keeps only claimable Jobs (small, hot); `tenant_id` equality locates one tenant;
`created_at, job_id` supply the deterministic queue order. This is conceptual **design** only — not executed
or plan-validated in class. It serves *finding candidates*, not lock ownership, and it is not an Index-Only
claim.

Engineering Thinking:

A partial composite index is the query shape written as a data structure: filter to the relevant rows, then
order them the way the reader reads them.

## Concept 4: Keys Serve an Access Path, Not Every Column

Tech Lead Question:

Does the claim's Partial Index support an all-status tenant **history** query?

Student Answer:

> "不支持，因为索引里不包含event列。所以需要重新维护"

Tech Lead Review:

Correct conclusion, wrong reason. An index key serves an **access path**, not every returned column — a
column missing from the index can usually be fetched from the Heap. The claim Partial Index fails the
all-status history query not because some column is absent, but because it **omits the rows**: it contains
only `queued` + not-cancelled Jobs, so it cannot answer a query that needs *all* statuses. A partial index
that does not contain the target rows cannot serve them.

Engineering Thinking:

Ask "does this index contain the rows and the order I need?" — not "does it list every column I select?"

## Concept 5: History Is a Different Access Path

Tech Lead Question:

For a dynamic status-filtered history endpoint, do you build one shared Composite index or many fixed-status
Partial Indexes?

Student Answer:

> "Composite Index，可以避免创建多个Partial Index"

Tech Lead Review:

A sound **default** for one endpoint that accepts many statuses: a shared composite
`(tenant_id, job_status, created_at DESC, job_id DESC)` serves the filter and the order. But it is not
automatically best. A **selective, frequent, fixed-status** workload can justify a narrow Partial Index
instead. The all-status history path is different again: `(tenant_id, created_at DESC, job_id DESC)` with no
status column. Choose by measured workload and total cost — one general index versus several narrow ones is
a trade, not a rule.

Engineering Thinking:

"History" is not one query. Separate all-status, dynamic-status, and fixed-status paths, then index the ones
the workload actually pays for.

## Concept 6: A Unique Constraint Is Already an Index

Tech Lead Question:

Day31 has `UNIQUE (tenant_id, idempotency_key)`. Should you add an ordinary index on the same columns for
the idempotency lookup?

Student Answer:

> "不会，因为本身这就表示这个组合在表中是唯一的。"

Tech Lead Review:

Correct, and here is the mechanism to add to it: PostgreSQL **automatically creates a unique B-tree index**
to enforce that constraint, and that same index serves `WHERE tenant_id = $1 AND idempotency_key = $2`. An
identical ordinary index is **redundant** — same key, no new lookup capability, only extra storage, write
amplification, Vacuum, and cache cost. A unique constraint is also an access-path fact.

Engineering Thinking:

Constraints often come with indexes for free. Read the schema before adding an index that already exists.

## Concept 7: The Outbox Partial Index

Tech Lead Question:

The Relay polls `WHERE published_at IS NULL ORDER BY created_at, outbox_event_id LIMIT 100`, and almost
everything is already published. What index?

Student Answer:

> "create index on（job_ID，create_at，outbox_event_id，） where publish is null。应该使用partial index，因为只有少数没有发布了"

Tech Lead Review:

The instinct is right — a **Partial Index** on the tiny unpublished set — but two fixes. First, the correct
field names and predicate: `WHERE published_at IS NULL`. Second, `job_id` is **selected** but is neither a
filter nor an ordering key, so it must **not** be a leading key. The design is:

```sql
CREATE INDEX outbox_unpublished_idx
    ON app.outbox_events (created_at, outbox_event_id)
    WHERE published_at IS NULL;
```

Because almost all rows are published, the partial set is small and hot; a row leaves the index when
`published_at` is written.

Engineering Thinking:

Do not put a column before the ordering keys just because it appears in the `SELECT` list. Index keys follow
predicate and order.

## Concept 8: `now()` Cannot Be a Partial Index Predicate

Tech Lead Question:

For stale-lease recovery you want rows where `lease_expires_at <= now()`. Can you make that a Partial Index?

Student Answer:

> "不可以，因为now是一直变化的"

Tech Lead Review:

Correct. A Partial Index's membership is fixed **at write time** — a row only enters or leaves the index when
it is written. `now()` moves continuously, so `WHERE lease_expires_at <= now()` would need rows to change
membership as time passes *without any write*, which PostgreSQL cannot do. The durable design instead uses a
**stable** partial predicate — "still running" — and applies the expiry test as a **query-time** B-tree
range condition:

```sql
-- CONCEPTUAL (Day36 adds the columns):
--   CREATE INDEX jobs_running_lease_idx ON app.jobs (lease_expires_at, job_id)
--       WHERE job_status = 'running';
--   -- query: WHERE job_status = 'running' AND lease_expires_at <= now() ORDER BY lease_expires_at, job_id
```

The lease columns (`claim_owner`, `lease_token`, `lease_expires_at`) do not exist in the Day31 schema, so
this stays conceptual until Day36.

Engineering Thinking:

A partial predicate must be a fact a write can set. Anything that changes with the clock belongs in the
query, not the index membership.

## Concept 9: B-tree Column Order Follows the Access Path

Tech Lead Teaching:

```text
Leading EQUALITY predicates first, then RANGE or ORDER BY columns.
(tenant_id, created_at, job_id) serves: tenant_id equality -> a time range -> ordered read.
Putting an unrelated key BEFORE the ordering keys can stop the index from providing the required order.
```

This is why the claim index leads with `tenant_id` (equality) and then carries `created_at, job_id` (the
order), and why `job_id` must not lead the Outbox index.

Engineering Thinking:

Column order is not cosmetic. Equality narrows, range/order reads — put them in that sequence or the index
cannot deliver the ordering for free.

## Concept 10: `EXPLAIN` vs `EXPLAIN ANALYZE`

Tech Lead Question:

What is the difference between `EXPLAIN` and `EXPLAIN ANALYZE`?

Student Answer:

> "不会因为数量太大了，这个时候建立专门的Partial index速度更快。explan应该是执行计划，EXPLAIN ANALYZE应该是执行计划分析"

Tech Lead Review:

The core distinction is right — `EXPLAIN` is the plan, `EXPLAIN ANALYZE` runs and analyzes it — but the
first clause's reasoning (about table size) is not the point, and the honesty caveat matters:

```text
EXPLAIN                       -> asks the Planner for an ESTIMATED plan; does NOT execute.
EXPLAIN ANALYZE               -> actually EXECUTES and reports real rows / time / loops.
EXPLAIN (ANALYZE, BUFFERS)    -> adds page/cache (shared hit/read) evidence.
```

`EXPLAIN ANALYZE` is **not a harmless viewer**: on a `SELECT ... FOR UPDATE SKIP LOCKED` claim it really runs
the query and takes **row locks**; on DML it makes **real changes** (wrap it in a transaction you `ROLLBACK`,
on a disposable cluster only). Run `ANALYZE` evidence in a controlled, representative environment.

Engineering Thinking:

`EXPLAIN` is safe to run anywhere; `EXPLAIN ANALYZE` is a real execution with real effects. Know which one
you are pointing at your production database.

## Concept 11: A Sequential Scan Is Not Automatically a Failure

Tech Lead Question:

You see a Seq Scan in a plan. Does that prove the index failed?

Student Answer:

> "是的，因为代表还是全表扫描没有走索引扫描"

Tech Lead Review:

This is the most common indexing misconception, and it is wrong. A Sequential Scan is a **cost-based** plan
and can be the *cheapest* choice: a small table, a high match fraction, cache-resident data, or an access
pattern where an index scan would cause expensive **random Heap reads**. The Planner picks it because it
estimated it to be cheaper, not because it "gave up."

When the student was shown two scenarios and asked which Seq Scan is a problem:

> "第二个，大表，小比例，真实时间1.6秒"

That is exactly right. The concerning case has **evidence**: ~8,000,000 rows, ~0.2% queued, ~1.6 s, with
~7,900,000 `Rows Removed by Filter` and high disk Buffer Reads. Low selectivity + huge filtered work + poor
latency is the signal to investigate — the node name alone is not.

Engineering Thinking:

Judge a scan by its cost and evidence, not its name. Seq Scan on a tiny hot table is healthy; Seq Scan
throwing away 99.8% of eight million rows is a lead.

## Concept 12: Estimate vs Actual — Investigate Statistics First

Tech Lead Question:

A plan estimates 1 row but the query actually returns 20,000. What is your first move?

Student Answer:

> "怀疑统计信息"

Tech Lead Review:

Correct. A large estimate-vs-actual gap first suggests **stale or inadequate statistics**, or data skew —
not "the Planner needs another index." Asked for the concrete next step, the student answered:

> "先调查统计信息、数据倾斜、谓词形状、参数计划，用新比较计划查看估算与真实的差异"

Exactly the right sequence: investigate statistics, data skew, predicate shape (type casts), and parameter
planning, then compare a fresh plan's estimate against actual. Refresh statistics (`ANALYZE`) before blindly
adding an index — a new index built on wrong estimates can be the wrong index.

Engineering Thinking:

A bad estimate is a data problem before it is an index problem. Fix what the Planner *knows* before you
change what it *has*.

## Concept 13: The Validation Sequence

Tech Lead Teaching:

```text
1. plain EXPLAIN                          -> is the intended plan even chosen?
2. controlled EXPLAIN (ANALYZE, BUFFERS)  -> real rows/time/loops + page/cache evidence,
                                             on representative data, disposable environment
3. workload metrics                        -> Worker claim p95/p99, oldest queued age,
                                             DB I/O/CPU, lock impact, write-path latency
```

A node name alone is never the conclusion. You compare estimated vs actual rows, actual time, loops,
`Rows Removed by Filter`, buffers, and sorting against representative data distribution, and only then judge.

Engineering Thinking:

Evidence is staged: plan, then measured execution, then system workload. Skipping to "add the index" skips
the part that tells you if it helps.

## Concept 14: Index Maintenance Cost of `queued -> running`

Tech Lead Question:

The Day34 claim UPDATE moves a Job `queued -> running`. Which indexes does it maintain?

Student Answer:

> "A，C需要维护 b不需要。ac要插入行，b是queued到running不会插入行"

Tech Lead Review:

The instinct — that not every index is touched — is right, though the specific labels came out mixed. The
rule: an UPDATE maintains **only** indexes whose key/included values change, or whose **partial predicate
membership** changes.

```text
jobs_claim_queue_idx  (ACTIVE partial, WHERE job_status='queued' ...) -> MAINTAINED: the row LEAVES the
                                                                         partial index (membership changes).
outbox_unpublished_idx (ACTIVE, on app.outbox_events)                -> not touched: a different table.
UNIQUE (tenant_id, idempotency_key) index (implicit, Day31)          -> unchanged: neither key changed.
```

So among the indexes the `007` pack actually creates, the transition maintains the claim partial index only.
The history designs in `007` are commented mutually-exclusive candidates (none is created), but the cost is
**conditional** if one is ever retained: an all-status `(tenant_id, created_at DESC, job_id DESC)` index would
be **unchanged** (no key column changed), whereas a dynamic-status
`(tenant_id, job_status, created_at DESC, job_id DESC)` index **includes `job_status`**, so `queued -> running`
**would maintain it**. Every index you add is write amplification on every qualifying write — this is the
standing cost side of the ledger, and it must be counted before retaining a history index.

Engineering Thinking:

An index is not free at write time. Count which indexes each hot write must maintain before you add another.

## Concept 15: The Net-Benefit Keep/Rollback Decision

Tech Lead Question:

A broad history/status index improves the history page but you must decide whether to keep it. What do you
weigh?

Student Answer (first instinct):

> "不会立刻回滚，应该比较无关页面是否减少，延迟比较，是否延迟转入另外的一处"

Then, shown the evidence, the final decision:

> "最终决策是回滚，因为只有history页面的P95的延迟减小但是提升不大，其他的影响增大，且没有额外收益"

Tech Lead Review:

Both answers are strong. The first is the right *method* — do not roll back on reflex; check whether other
pages improved, compare latency, and ask whether the cost merely **moved elsewhere**. The evidence then makes
the call:

```text
history page p95:   100 ms -> 80 ms    (small read win)
Job acceptance p99:  50 ms -> 220 ms   (write path much worse)
storage:            +14 GB
Worker / Outbox:    no extra benefit
```

Decision: roll back **only** that new broad index; keep the evidence-backed claim / Outbox / unique paths;
consider a narrower alternative later only if the history workload becomes important. Retain an index by
**net system benefit**, not a single page's win. (The classroom did **not** execute any DDL or rollback —
this is a design decision on stated evidence. The safe operational mechanics of building/removing an index
are Day36.)

Engineering Thinking:

An index that speeds one page while inflating acceptance p99 and burning 14 GB is negative overall. Optimize
the system, not the dashboard.

---

# Common Misconceptions

## Mental Model Evolution (Day34 -> Day35)

```text
Starting system limitation (not a student quote):
    Day34 made the concurrent Worker claim CORRECT -- tenant_id + job_status = 'queued' +
    cancel_requested = false, ordered by created_at, job_id -- but deliberately added no index or
    EXPLAIN. On a large table that claim, the Outbox poll, and history reads can be slow.

Correction that Day35 makes:
    Design indexes from the REAL predicate and ordering, and PROVE them with EXPLAIN evidence on
    representative data. A partial composite for the claim, a partial for the Outbox, and history paths
    kept separate and measured.

Boundaries Day35 cannot cross:
    An index speeds candidate lookup only -- not the lock, lease, or guarded transition. now() cannot be a
    partial predicate. The lease columns do not exist yet (Day36). And the SAFE deployment of any index
    (CREATE INDEX CONCURRENTLY, DDL-lock windows, rollout/rollback) is Day36, not Day35.

Net division of labour:
    Day34 decides ownership CORRECTNESS; Day35 decides access-path DESIGN + EVIDENCE; Day36 deploys it
    safely. Keep an index only for NET SYSTEM benefit, never to win one page.
```

## Misconception 1: Pick an index by choosing a column

Wrong: decide which column to index and add it.

Right: derive the index from the real `WHERE` + `ORDER BY` + `LIMIT`. A `job_status`-only index cannot
narrow by tenant or supply the order; the claim needs `(tenant_id, created_at, job_id)` with a partial
predicate.

## Misconception 2: An index must contain every column the query returns

Wrong: the claim Partial Index can't serve history because it lacks a returned column.

Right: unindexed returned columns are fetched from the Heap. The claim index fails history because it
**omits the rows** (only queued/not-cancelled), not because a column is missing.

## Misconception 3: A shared Composite index is always better than Partial Indexes

Wrong: one composite avoids making several partial indexes, so it always wins.

Right: it is a sound default for a many-status endpoint, but a selective, frequent fixed-status workload can
justify a narrow Partial Index. Choose by measured workload and total cost.

## Misconception 4: `EXPLAIN ANALYZE` is a harmless way to look at a query

Wrong: it just shows more detail than `EXPLAIN`.

Right: it **executes** the query — real row locks on `SELECT ... FOR UPDATE`, real changes on DML. Use a
staged, controlled sequence, and never casually run it against production DML.

## Misconception 5: A Sequential Scan proves the index failed

Wrong: seeing Seq Scan means the query "did not use the index," so the index is broken.

Right: Seq Scan is a **cost-based** choice and can be optimal (small table, high match fraction, cache-hot,
or to avoid random Heap reads). It is concerning only with evidence: low selectivity, large `Rows Removed by
Filter`, poor latency, high Buffer Reads.

## Misconception 6: `job_id` should lead the Outbox index because it is selected

Wrong: it appears in the `SELECT`, so put it first.

Right: index keys follow **predicate and order**, not the select list. `job_id` is neither filtered nor
ordered on, so the keys are `(created_at, outbox_event_id) WHERE published_at IS NULL`.

## Misconception 7: A duplicate index on the unique key is fine "for lookups"

Wrong: add an ordinary index on `(tenant_id, idempotency_key)` for reads.

Right: the `UNIQUE` constraint already created a unique B-tree that serves the lookup. A duplicate adds cost
and no capability.

## Misconception 8: `WHERE lease_expires_at <= now()` can be a Partial Index predicate

Wrong: index the expired rows directly.

Right: partial membership only changes on a write; `now()` moves without writes. Use a stable "running"
partial predicate and test expiry at query time. (And the columns don't exist until Day36.)

## Misconception 9: A big estimate-vs-actual gap means "add an index"

Wrong: estimate 1 vs actual 20,000 means the Planner needs another index.

Right: it first means **stale/inadequate statistics or skew**. Investigate statistics, predicate shape,
casts, and parameter planning, and refresh statistics before adding an index.

## Misconception 10: If a query got faster, keep the index

Wrong: the history page improved, so the index is good.

Right: keep by **net system benefit**. A read win that inflates acceptance p99, adds 14 GB, and helps
nothing else is negative overall — and the cost may have merely moved elsewhere.

---

# Engineering Trade-offs

## Trade-off 1: Partial index vs full index

| Aspect | Partial (`WHERE ...`) | Full |
| --- | --- | --- |
| Size / cache | Small, hot (only relevant rows) | Larger, colder |
| Serves | One predicate's rows only | Any query on the keys |
| Maintenance | Only when membership changes | On every qualifying write |
| Best for | Claim (queued), Outbox (unsent) | General history on the keys |

## Trade-off 2: One shared Composite vs many fixed-status Partial Indexes

| Aspect | Shared composite | Fixed-status partials |
| --- | --- | --- |
| Coverage | Any status filter | Only the chosen statuses |
| Count | One index | Several to maintain |
| Size | Larger (all rows) | Each small |
| Best for | Dynamic status endpoint | A few selective, frequent statuses |

## Trade-off 3: Add an index vs fix statistics

| Aspect | Add an index | Refresh statistics / investigate |
| --- | --- | --- |
| Addresses | A genuinely missing access path | A wrong estimate / skew / cast |
| Risk | Wrong index on bad estimates | None (cheap) |
| Order | After statistics are trusted | First |

## Trade-off 4: Read benefit vs system cost (keep/rollback)

| Aspect | Read benefit | System cost |
| --- | --- | --- |
| Measures | Target page p95/p99 | Write p99, storage, Vacuum, cache |
| Trap | Optimizing one dashboard | Inflating Job acceptance p99 |
| Decision | Net system benefit | Reject if cost just moved elsewhere |

---

# Hands-on Exercises

## Exercise 1: Derive the claim index (Beginner)

From the Day34 claim predicate and ordering, write the Partial Composite B-tree and explain each key's role.

Verification: `(tenant_id, created_at, job_id) WHERE job_status = 'queued' AND cancel_requested = false`;
tenant equality, then queue order; partial keeps claimable rows.

## Exercise 2: Why not `job_status`-only (Beginner)

Explain three reasons a `job_status`-only index is weak for the claim.

Verification: no tenant narrowing, no ordering, low-cardinality leaves a large set.

## Exercise 3: History vs claim path (Intermediate)

Explain why the claim Partial Index cannot serve an all-status history query, using the correct reason.

Verification: it omits non-queued rows (membership), not "a column is missing."

## Exercise 4: Composite vs partials (Intermediate)

Choose between a shared status Composite index and fixed-status Partial Indexes for a history endpoint, and
state the deciding factor.

Verification: composite as default; a selective frequent fixed status can justify a partial; decide by
measured workload.

## Exercise 5: Do not duplicate the unique index (Beginner)

Explain why no new index is added for `UNIQUE (tenant_id, idempotency_key)`.

Verification: the constraint already created a unique B-tree that serves the lookup; a duplicate is pure
cost.

## Exercise 6: Outbox partial index (Intermediate)

Design the unpublished-Outbox index and justify excluding `job_id` from the keys.

Verification: `(created_at, outbox_event_id) WHERE published_at IS NULL`; `job_id` is selected, not filtered
or ordered.

## Exercise 7: Reject the `now()` predicate (Advanced)

Explain why `WHERE lease_expires_at <= now()` cannot be a Partial Index, and give the durable design.

Verification: partial membership changes only on writes; use a stable "running" partial + query-time range;
columns are Day36.

## Exercise 8: EXPLAIN vs EXPLAIN ANALYZE (Intermediate)

State the difference and the side effects of `EXPLAIN ANALYZE` on a `SELECT ... FOR UPDATE` and on DML.

Verification: plan vs real execution; real row locks; real DML changes; run controlled/disposable only.

## Exercise 9: Healthy vs harmful Seq Scan (Advanced)

Given two scenarios, decide which Seq Scan warrants investigation and cite the evidence.

Verification: the 8M-row, 0.2%-match, 1.6 s, ~7.9M `Rows Removed by Filter`, high-Buffer-Reads case.

## Exercise 10: Estimate vs actual (Advanced)

For estimate 1 vs actual 20,000, give the first investigation, not the first index.

Verification: statistics/skew/predicate/cast/parameter-plan investigation; refresh statistics first.

## Exercise 11: Maintenance of `queued -> running` (Advanced)

State which indexes the claim UPDATE maintains and why.

Verification: the claim partial index (membership leaves); history and idempotency unchanged (keys
unchanged).

## Exercise 12: Keep/rollback decision (Advanced)

Given the 100->80 ms / 50->220 ms / +14 GB / no-other-benefit evidence, decide and justify on net system
benefit.

Verification: roll back only the broad index; keep proven paths; net-benefit reasoning; note deployment
mechanics are Day36.

---

# Relevant Framework Connections

## PostgreSQL

Heap tuples and B-tree traversal; Partial / Composite / Unique indexes; `FOR UPDATE SKIP LOCKED` still
locking the Heap tuple; `EXPLAIN`, `EXPLAIN ANALYZE`, `BUFFERS`; cost estimates and statistics; index
maintenance and Vacuum. The safe online build (`CREATE INDEX CONCURRENTLY`) and DDL-lock mechanics are
**Day36**.

## FastAPI / application acceptance

An index decision must not harm `202`/Job acceptance p99 while improving a secondary operations page. The
keep/rollback case is decided against acceptance latency, not the dashboard alone.

## Celery / Workers

Claim latency, oldest queued age, and high-concurrency queue polling depend on the Day34 claim access path;
candidate selection (the index's job) stays separate from ownership correctness (the lock's job).

## Outbox Relay

High-frequency `published_at IS NULL` scans need a small ordered Partial Index. Relay semantics and consumer
idempotency remain Day33/Day40 boundaries.

## Validation evidence for these exercises

State the level, never the level above it. **Day35 has no runtime evidence — everything is conceptual and
static.**

```text
1. Conceptual / manual production reasoning        DONE (in class)
   The 15 concepts, query-shape index derivation, EXPLAIN semantics, Seq-Scan judgement, and the
   net-benefit keep/rollback decision.

2. Repository artifact static review                DONE (repository update)
   007 uses the Day31 columns exactly; the claim Partial Composite is
   (tenant_id, created_at, job_id) WHERE job_status='queued' AND cancel_requested=false; the Outbox
   Partial is (created_at, outbox_event_id) WHERE published_at IS NULL; NO duplicate index for the
   UNIQUE (tenant_id, idempotency_key) constraint; the stale-lease design and its now()-avoidance are
   commented/conceptual; no CREATE INDEX CONCURRENTLY / ALTER / migration / ORM; no credentials.

3. PostgreSQL runtime (EXPLAIN / EXPLAIN ANALYZE)   NOT RUN
   No Day35 SQL file, PostgreSQL server, EXPLAIN, EXPLAIN ANALYZE, statistics refresh, or representative
   data was executed in class or during the repository update. Every plan number quoted (the 8M-row Seq
   Scan, estimate-1-vs-actual-20,000, and the 100->80 / 50->220 / +14 GB case) is a CLASSROOM SCENARIO for
   reasoning, NOT a measured result and NOT the output of any executed plan.

4. Application / benchmark integration              NOT RUN
   No FastAPI/driver/Celery workload, no p95/p99 benchmark, no representative-data load.

5. Production DDL / deployment / rollback           NOT RUN / OUT OF SCOPE
   No index was built, deployed, or rolled back. CREATE INDEX CONCURRENTLY, DDL-lock windows, and
   rollout/rollback are Day36. No production load test, RLS, backups, HA, or deployment.
```

---

# AI Backend Connections

## Connection 1: A fast claim path speeds lookup, not ownership

Many Workers polling long-running AI Jobs need a fast, ordered claim path, but the B-tree only speeds
**candidate lookup** — it does not replace locks, leases, or guarded transitions (Concepts 1, 3).

## Connection 2: The stale-lease scan waits for Day36

A late/stale Worker and an expensive Provider call remain Day34 correctness/cost boundaries; the future
stale-lease recovery scan can be indexed only **after** Day36 adds the real lease schema (Concept 8).

## Connection 3: Outbox polling is a realistic Partial Index workload

Durable intent around AI Job lifecycle events is polled frequently, and the unpublished set is small — a
textbook case for a small ordered Partial Index (Concept 7).

## Connection 4: Protect acceptance latency, not a dashboard

Production index decisions must preserve FastAPI acceptance latency and Worker throughput; optimizing an
isolated dashboard while inflating model-Job initiation cost is a net loss (Concept 15).

---

# English Interview

Three questions were answered aloud. The student's real words are preserved verbatim, including grammar,
because the correction targets the content.

## Beginner: `EXPLAIN` vs `EXPLAIN ANALYZE`

Student answer (actual):

> "explain is 是execute plan，it's not a realy exection only a estimated result.EXPLAIN ANALYZE is real execute result."

Correction: correct. `EXPLAIN` returns an estimated plan without executing; `EXPLAIN ANALYZE` actually runs
the query and returns real metrics. Add the honesty caveat: running it really executes — row locks on
`SELECT ... FOR UPDATE`, real changes on DML.

Strong spoken answer:

> "`EXPLAIN` shows the planner's estimated plan without running the query. `EXPLAIN ANALYZE` executes the
> query and reports actual rows, time, and loops, and `BUFFERS` adds cache evidence. Because it really runs,
> on a `SELECT ... FOR UPDATE` it takes row locks and on DML it makes changes, so I only run it on a
> disposable, representative environment."

## Intermediate: what is a Partial Index for?

Student answer (actual):

> "Partial Index can establish a faster querry path."

Correction: true but incomplete. A Partial Index indexes only the rows matching its predicate, so it is
small and hot — ideal when the target set is a tiny fraction (queued Jobs, unpublished Outbox rows). It is
faster *because* it is smaller and only maintained when predicate membership changes.

Strong spoken answer:

> "A Partial Index only covers rows matching a `WHERE` predicate, so for a small hot subset — queued Jobs or
> unpublished Outbox events out of millions — it is tiny, cache-friendly, and cheap to maintain, and it is
> only updated when a row enters or leaves the predicate."

## Senior: keep or roll back the broad history index?

Student answer (actual):

> "we need to compare extral profit,the first operations history page get less improve,and job acceptance p99 increase too much,the index consumes too much.so compare extral profit,we would choose roll back the inedx"

Correction: the decision and reasoning are right — compare the benefit against the whole-system cost. Sharpen
the term: it is **net system benefit**, not just "extra profit," and note the write-path harm and storage are
the deciding costs, with no benefit to Worker/Outbox.

Strong spoken answer:

> "The broad index only moved history p95 from 100 to 80 ms but pushed Job acceptance p99 from 50 to 220 ms,
> cost 14 GB, and helped neither Workers nor the Outbox. On net system benefit it is negative, so I roll back
> only that index and keep the evidence-backed claim, Outbox, and unique paths — and I'd consider a narrower
> alternative only if the history workload became important. The safe way to build or drop it in production
> is Day36."

Key vocabulary: `access path`, `Heap`, `B-tree`, `Partial Index`, `Composite Index`, `unique B-tree`,
`query shape`, `EXPLAIN` / `EXPLAIN ANALYZE` / `BUFFERS`, `Sequential Scan`, `Rows Removed by Filter`,
`selectivity`, `statistics`, `write amplification`, `net system benefit`.

---

# Mental Model Summary

```text
1. An index is an ADDITIONAL access structure over the Heap; the claim still locks the real tuple.
2. Design the index from the real WHERE + ORDER BY + LIMIT, not from a chosen column.
3. Claim path = (tenant_id, created_at, job_id) WHERE job_status='queued' AND cancel_requested=false.
4. B-tree order: leading EQUALITY predicates, then RANGE / ORDER BY columns.
5. An index key serves an access path, not every selected column; the Heap supplies unindexed columns.
6. A Partial Index that omits the target rows cannot answer the query (membership, not columns).
7. History is several paths: all-status, dynamic-status composite, fixed-status partial -- measure, don't default.
8. A UNIQUE constraint already creates a unique B-tree; never duplicate it.
9. Outbox = (created_at, outbox_event_id) WHERE published_at IS NULL; job_id is selected, not a key.
10. now() cannot define partial membership; use a stable predicate + a query-time range (lease is Day36).
11. EXPLAIN estimates; EXPLAIN ANALYZE EXECUTES (row locks / real DML). A node name is not a conclusion.
12. Seq Scan is cost-based and can be optimal; judge by selectivity, filtered rows, latency, buffers.
13. Estimate vs actual divergence -> statistics/skew investigation BEFORE another index.
14. Among 007's active indexes, queued->running maintains only the claim Partial Index; the idempotency Unique Index is unchanged. If retained later, an all-status history index stays unchanged, while a dynamic-status history index must be maintained because job_status changes.
15. Keep an index only for NET SYSTEM benefit; a read win that inflates acceptance p99 is a net loss.
16. Day35 designs + validates evidence; Day36 safely deploys (CONCURRENTLY, DDL locks, rollout/rollback).
```

Final Chinese synthesis (student, verbatim):

> "B-tree是数据库的内部索引结构，composite index里面没有做限制，可以包含更多的行，Partial Index是给了限定的索引，Unique Index已经包含了隐式B- tree，所以不需要再建立显式的。EXPLAIN 与 EXPLAIN ANALYZE的区别是一个只是计划，一个要确实执行，并返回执行的结果指标。Seq Scan 与统计信息，通过统计信息判断开销是否需要优化路径，是继续使用seq scan还是使用index scan。写入、缓存、Vacuum 成本这三个方向可以作为收益的判断方向。生产保留或回滚决策是根据额外收益来判断的。查询更快，如果收益为负就不应该保留这个索引。"

Targeted corrections (Tech Lead):

1. Strong overall: unique index implies an implicit B-tree (so no explicit duplicate), `EXPLAIN` vs
   `EXPLAIN ANALYZE`, statistics-driven cost judgement, and the write/cache/Vacuum cost axes.
2. Precision: a **Composite Index** means multiple ordered key columns — not "no restriction." A non-partial
   composite includes all table rows; a Partial Index includes only rows satisfying its predicate.
3. Precision: Planner statistics **estimate** cardinality/cost; they do not mechanically decide that
   optimization is required — the engineer decides on evidence.
4. Precision: the keep/rollback decision is **net system benefit**, not merely "extra profit" (查询更快):
   a faster query with negative overall benefit must not be kept.

---

# Today's Takeaway

Day34 made the claim correct; Day35 makes it fast **on evidence**. The method is always the same: read the
real query — `WHERE`, `ORDER BY`, `LIMIT` — and build the index that contains exactly those rows in exactly
that order. The claim gets a partial composite `(tenant_id, created_at, job_id)` over claimable Jobs; the
Outbox gets a partial `(created_at, outbox_event_id)` over unpublished rows; the idempotency lookup gets
nothing new, because its `UNIQUE` constraint already built the index.

The harder half is restraint. Every index taxes every write, storage, cache, and Vacuum, so an index is
justified only by **net system benefit** — a read win that pushes Job acceptance p99 from 50 to 220 ms is a
loss no matter how good the dashboard looks. And the tools are honest tools: `EXPLAIN` estimates, `EXPLAIN
ANALYZE` actually executes and locks, a Sequential Scan is often the right plan, and a wild estimate is a
statistics problem before it is an index problem.

Everything here is **design and evidence**. Nothing was executed — no server, no `EXPLAIN`, no benchmark, no
DDL. And the safe way to actually build or drop these indexes on populated data, online and reversibly, is
Day36. Correctness (Day34), then design (Day35), then safe deployment (Day36) — in that order.

---

# Before Next Lesson Checklist

- [ ] I can derive the claim Partial Composite index from the Day34 predicate and ordering.
- [ ] I can explain why a `job_status`-only index is weak and why B-tree order is equality-then-range/order.
- [ ] I can explain why the claim index cannot serve all-status history (membership, not a missing column).
- [ ] I can choose between a shared status Composite and fixed-status Partial Indexes on measured workload.
- [ ] I can explain why the `UNIQUE (tenant_id, idempotency_key)` index must not be duplicated.
- [ ] I can design the Outbox Partial Index and say why `job_id` is not a leading key.
- [ ] I can reject a `now()` Partial predicate and give the stable-predicate + query-time-range design.
- [ ] I can state the difference and side effects of `EXPLAIN` vs `EXPLAIN ANALYZE`.
- [ ] I can judge a Seq Scan by selectivity/filtered rows/latency/buffers, not by its name.
- [ ] I can treat estimate-vs-actual divergence as a statistics investigation before adding an index.
- [ ] I can decide keep/rollback on net system benefit using read gain vs write/storage/Vacuum/cache cost.

Preparation for Day36 (Schema Evolution and Safe Migrations):

- [ ] Re-read `projects/ai-backend-data-layer/sql/007_postgresql_indexes_and_query_planning.sql` and note which designs need safe online deployment.
- [ ] Note that `CREATE INDEX CONCURRENTLY`, `DROP INDEX CONCURRENTLY`, and DDL-lock windows are the Day36 mechanics for the Day35 designs.
- [ ] Note that the conceptual lease columns (`claim_owner`, `lease_token`, `lease_expires_at`) and the stale-lease index are added and deployed in Day36, with an expand/backfill/validate/switch/contract migration.
- [ ] Be ready to argue why a design (Day35) and its safe rollout (Day36) are different decisions.
