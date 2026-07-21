# Lesson 32 — SQL Joins, Aggregation, and Operational Queries

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day31 — Relational Modeling and Data Integrity

Previous Lesson: [Day31 — Relational Modeling and Data Integrity](day31-relational-modeling-and-data-integrity.md)

Next Lesson: Day33 — PostgreSQL Transactions and Atomic State Changes (planned — see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day33 lesson file does not exist yet)

Engineering Artifact: The Day32 operational query pack (`sql/004_sql_joins_aggregation_and_operational_queries.sql`) — ten read-only queries over the Day31 model, each with an explicit result grain — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

PostgreSQL Cheat Sheet: [cheat_sheets/postgresql.md](../../cheat_sheets/postgresql.md)

PostgreSQL Interview: [interview/postgresql.md](../../interview/postgresql.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 100-130 minutes
Hands-on query authoring + disposable-PostgreSQL checks: 100-130 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

After completing this lesson, the student should be able to:

* State a query's **result grain** before writing any aggregate.
* Choose `INNER` vs `LEFT JOIN` from what a missing row *means* operationally.
* Predict join cardinality, including two independent one-to-many children multiplying rows.
* Distinguish `COUNT(*)` from `COUNT(child_pk)` after an outer join.
* Write conditional aggregation with `FILTER` (and its portable `CASE` equivalent) without collapsing the outer join.
* Choose `WHERE` vs `HAVING` from whether the predicate depends on an aggregate.
* Interpret `NULL` in `SUM`/`AVG` as unknown evidence, never zero, and name partial metrics honestly.
* Pre-aggregate each one-to-many child to the intended grain before combining metrics.
* Pick a stage-appropriate clock for queued vs running vs terminal age.
* Define throughput on `finished_at` with an explicit half-open window.
* Identify an affected release from **recorded provenance**, not deployment time.
* Classify incident evidence without claiming proof of an external outcome.

The engineering artifact is a read-only operational query pack, not application code.

---

# Why This Matters

Day31 made the durable facts trustworthy: ownership, cardinality, identity scope, legal states, and
tenant-aware relationships. What it did not provide was a way to **read** those relationships correctly.

An operations dashboard must show every tenant Job — *including queued Jobs that have no Attempt yet* —
reconstruct Attempt/Event detail, report retry/cost/throughput, detect stage-specific stuck candidates,
and identify which Jobs a faulty release actually processed.

Day32's central rule:

```text
Define the result grain FIRST.

JOIN                    = preserve, discard, or MULTIPLY relationship combinations
GROUP BY / pre-aggregate = deliberately turn many child rows into one summary per owner
Operational query        = evidence and candidates from PERSISTED facts
                         != proof of an unrecorded external outcome
```

Why a backend engineer must care:

```text
Visibility  -> an INNER JOIN silently deletes the backlog you are paid to watch.
Correctness -> two one-to-many children produce 3 x 4 = 12 rows and corrupt every COUNT/SUM/AVG.
Honesty     -> NULL cost is unknown, not zero; a partial sum must not be called a total.
Stage       -> a Job accepted 2h ago but claimed 30s ago is not a 2h running Job.
Provenance  -> deployment time is correlation; only a fact recorded at processing time is evidence.
Limits      -> zero artifacts does not prove the Provider did nothing.
```

---

# Roadmap Position

Knowledge continuity chain (v3.2):

```text
Previous Knowledge (Day29-Day31)
        |
        v
Current Concept (Day32: join, aggregate, and interpret those relationships correctly)
        |
        v
Future Usage (Day33 atomic Job+Event+Outbox; Day34 concurrency-safe claims;
              Day35 measure and index the access paths proven useful here)
```

Where Day32 sits:

```text
Day29 durable Job row -> Day30 guarded reads/writes -> Day31 relational ownership and integrity
-> Day32 correct joins, aggregation, and operational evidence   <-- you are here
-> Day33 atomic multi-table changes -> Day34 concurrency-safe worker claims
-> Day35 measured indexes for these access paths
```

Day31 rules reused directly:

```text
- Composite FKs give WRITE-time integrity; reads still need a tenant predicate (integrity != authorization).
- job_events.attempt_id is OPTIONAL provenance; a non-NULL Attempt belongs to the same Job.
- Result Artifacts hang off Attempts, so Job-level artifact counts roll up through job_attempts.
- Only `succeeded` is guaranteed to have a non-NULL finished_at.
- Committed rows have no automatic undo; repair is reconciled and guarded.
```

Future connection only: Day33 will use these queries to verify Job/Event/Outbox facts appear or roll
back together. Day34 adds lease/heartbeat evidence that turns "stuck candidate" into proof. Day35 must
optimize the access paths these queries prove useful — not guessed ones. Day36 owns any typed
release-provenance schema evolution; Day32 must not silently alter populated tables.

---

# Lesson Map

```text
INNER vs LEFT JOIN and what a missing row means
  -> cardinality and row multiplication (two one-to-many children)
  -> COUNT(*) vs COUNT(child_pk); conditional aggregation with FILTER
  -> WHERE vs HAVING
  -> MIN/MAX and oldest queued age
  -> SUM/AVG with NULL: unknown != zero; honest metric names
  -> CTE pre-aggregation and safe grain composition
  -> stage-aware stuck candidates (queued vs running vs terminal clocks)
  -> throughput on finished_at with a half-open window
  -> affected-release provenance
  -> integrated failure/rollback: classify, never bulk-repair
```

---

# Core Mental Model

```text
Define result grain first.

JOIN                     = preserve, discard, or multiply relationship combinations
GROUP BY / pre-aggregation = deliberately change many child rows into one summary row per owner

Operational query = evidence and candidates based on persisted facts
                  != proof of an unrecorded external outcome

Explicit provenance = the authoritative affected-set boundary

Rollback = stop future bad writes
         != repair committed rows or undo external side effects
```

Every aggregate is a claim about a grain. If you cannot say what one row means, the number is not
trustworthy yet.

---

# Main Concepts

## Concept 1: `INNER` vs `LEFT JOIN` and What a Missing Row Means

Tech Lead Question:

The dashboard query uses `INNER JOIN app.job_attempts` and queued Jobs have vanished. Why, and what do
you change?

Student Thinking:

An inner join needs the `job_id` to exist on both sides; a freshly created Job has no Attempt row yet.

Student Answer:

> "因为使用INNER JOIN，所以查询的时候是两个表都存在job_id条件才成立，而刚创建但尚未被 Worker 处理，代表这个时候app.job_attempts还没有数据写入选择left join"

Tech Lead Review:

Exactly right, including the reason. `INNER JOIN` returns only matching **combinations**, so a Job with
zero Attempts is dropped — and that is precisely the backlog operations needs to see.

```text
Query contract (grain):
  One row = one Job-Attempt combination.
  0 Attempts -> ONE row, Attempt columns NULL.
  N Attempts -> N rows.
```

The NULL Attempt columns are **meaningful operational evidence** — "no Attempt row exists" — not
corrupt data. A report that hides zero-Attempt Jobs hides the queue.

Engineering Thinking:

Choose the join from what a missing row *means*. If absence is information, preserve it.

Production Example:

A tenant complains nothing is processing. With `INNER JOIN`, the dashboard shows an empty, healthy-looking
list. With `LEFT JOIN`, it shows 400 queued Jobs and zero Attempts — the actual symptom.

Framework Connection:

FastAPI's operational endpoints must expose evidence without hiding missing relations; `tenant_id`
remains a server-authenticated predicate.

Exercise:

Choose `INNER` vs `LEFT JOIN` for zero-Attempt queued Jobs and state the resulting grain.

## Concept 2: Cardinality and Row Multiplication

Tech Lead Question:

One Job has three Attempts. How many rows? Then add four Job Events joined by `job_id` — now how many?

Student Thinking:

Three Attempts means three rows. Then the Events attach to what is already there.

Student Answers:

> (three attempts) "应该返回三行，因为一条job_id对应的app.job_attempts三条数据，所以需要全部查出来"

> (first attempt at the multi-child case) "返回4行，因为先是查询出来三条job—attempt的结果集。再连接查询，有4过 job events，没查到的Attempts就用null代替"

> (second attempt) "返回0条，因为结果集job- attempt匹配到0条，再用这个结果集去匹配event结果还是0"

Tech Lead Review:

The first answer is correct. The two multi-child answers are both wrong, and the *way* they are wrong is
the important part: they picture a **sequential filter** — as if Events were allocated to Attempts, or as
if an empty intermediate result stays empty.

A join produces **every matching combination**:

```text
3 Attempts x 4 Events = 12 rows.
The database has no idea which Event "belongs to" which Attempt — you never told it.
```

And with the outer join preserved, zero Attempts does **not** mean zero rows:

```text
Attempts  Events  Result rows
0         0       1   (Job preserved; both child sides NULL)
0         4       4   (the NULL-extended Job row matches EVERY Event)
3         0       3
3         4       12
```

Two independent one-to-many children must never be joined in one statement when you intend to aggregate.
The multiplication silently corrupts `COUNT`, `SUM`, and `AVG`.

Engineering Thinking:

Ask "how many rows will one Job produce?" before adding a second child table. If the answer is a product,
you have changed the grain.

Production Example:

A per-Job cost report that joins Attempts and Events together bills each Attempt's cost four times.

Framework Connection:

Day31 made Attempts and Events *separate* one-to-many children on purpose; Day32 must read them that way.

Exercise:

Predict the four-row table above, then correct the zero-Attempt + four-Event case.

## Concept 3: `COUNT` and NULL-aware Aggregation

Tech Lead Question:

After the `LEFT JOIN`, a zero-Attempt Job still produces one row. What do `COUNT(*)` and
`COUNT(a.attempt_id)` return?

Student Thinking:

Grouping by `job_id` turns the joined rows into per-Job groups; the two counts must differ.

Student Answer:

> "做连接以后，应该是生产了job_attempts行数的结果，通过job_id执行进行分组以后。就是根据job_id分组每个job_id对应的job_attempts行数，如果是COUNT(*)统计的就是有多少个job_id。如果使用a.attempt_id进行统计就是具体的行数"

Tech Lead Review:

The instinct — that the two counts differ — is right, and choosing the child key is right. One
correction: `COUNT(*)` does **not** count job IDs. It counts **result rows**, including the
NULL-extended outer-join row.

```text
Zero-Attempt Job after LEFT JOIN:
  COUNT(*)            = 1   (the NULL-extended row is still a row)
  COUNT(a.attempt_id) = 0   (counts only non-NULL real Attempt identities)
```

For "how many Attempts does this Job actually have", always count the child's key.

Conditional aggregation keeps the condition **inside** the aggregate:

```sql
COUNT(a.attempt_id)                                          AS total_attempts,
COUNT(a.attempt_id) FILTER (WHERE a.error_code IS NOT NULL)  AS failed_attempts
```

Asked how to express this, the student answered:

> "不知道"

`FILTER` was then taught directly, along with the portable equivalent
`SUM(CASE WHEN a.error_code IS NOT NULL THEN 1 ELSE 0 END)`.

The trap worth remembering: moving `a.error_code IS NOT NULL` into `WHERE` would delete successful
Attempts **and** the zero-Attempt placeholder row — silently collapsing the `LEFT JOIN` back into an
`INNER JOIN`.

Engineering Thinking:

`WHERE` shapes the input set; `FILTER` shapes one aggregate. Choosing the wrong one changes which rows
exist at all.

Production Example:

"Jobs with failures" written with a `WHERE` filter quietly drops every healthy Job from the denominator
of your failure rate.

Exercise:

Choose `COUNT(*)` vs `COUNT(child_pk)`, then write the failed-Attempt metric with `FILTER`.

## Concept 4: `WHERE` vs `HAVING`

Tech Lead Question:

You want Jobs that retried at least twice — `COUNT(a.attempt_id) >= 2`. `WHERE` or `HAVING`?

Student Answer:

> "HAVING"

Tech Lead Review:

Correct, and for the right reason: the condition depends on an **aggregate**, which does not exist until
after grouping.

```text
WHERE  -> filters INPUT rows BEFORE grouping
HAVING -> filters GROUPS AFTER aggregation
```

Keep tenant, state, and raw time predicates in `WHERE` so irrelevant rows never enter the aggregation at
all — it is both more correct and less work.

Engineering Thinking:

Filter as early as the semantics allow; use `HAVING` only for facts that require the group to exist.

Production Example:

`WHERE j.tenant_id = $1` (early) plus `HAVING COUNT(a.attempt_id) >= 2` (late) reads naturally and keeps
other tenants out of the computation entirely.

Exercise:

Choose `WHERE` vs `HAVING` for a retry-count threshold and justify the placement of the tenant predicate.

## Concept 5: `MIN`/`MAX` and Oldest Queued Age

Tech Lead Question:

Report tenant queue health: how many queued Jobs, and how long has the oldest been waiting?

Student Answer:

> "使用MIN(created_at)，因为要获得最早的时间"

Tech Lead Review:

Correct — the oldest queued Job is the **minimum** `created_at`.

```text
GRAIN: exactly one summary row (no join, so COUNT(*) is safe here).

COUNT(*)         = queued demand count
MIN(created_at)  = oldest queued Job timestamp
MAX(created_at)  = newest queued Job timestamp
now() - MIN(...) = oldest queued age
```

The edge case that matters operationally: with **no** queued Jobs the query returns count `0` and
**NULL** for `MIN`/`MAX`/age. A dashboard must render "no backlog" differently from "no data" — they are
completely different facts, and conflating them hides an outage.

Engineering Thinking:

Always ask what an empty input renders as. NULL-vs-zero is a UI correctness problem, not a cosmetic one.

Production Example:

A panel showing "oldest queued age: —" during a metrics outage looks identical to a healthy empty queue
unless the count is shown beside it.

Framework Connection:

This is Day28's oldest-queued-age SLO signal, now expressed as a real query.

Exercise:

Write the queue-health summary and state what an empty queue returns.

## Concept 6: `SUM`/`AVG` over Incomplete Cost Data

Tech Lead Question:

Finance wants per-Job total and average `cost_micros`. Some Attempts have `cost_micros IS NULL`. What do
`SUM` and `AVG` do, and is the result trustworthy?

Student Answer:

> "SUM(cost_micros)如果有null值就会跳过。AVG(cost_micros)也是同理，跳过null值再进行计算"

Tech Lead Review:

Mechanically correct — SQL aggregates skip NULL. The engineering question is what that *means*.

```text
SUM ignores NULL -> the total is the total of RECORDED costs, not of incurred costs.
AVG ignores NULL in BOTH numerator and denominator
    -> average over ATTEMPTS THAT REPORTED, not over all Attempts.
```

NULL here means **unknown**, not zero. A provider call may well have cost money and simply failed to
report it. So the honest column names are `recorded_total_cost_micros` and
`recorded_average_cost_micros`, published beside a completeness signal:

```sql
COUNT(a.attempt_id)   AS total_attempts,
COUNT(a.cost_micros)  AS cost_reported_attempts,
SUM(a.cost_micros)    AS recorded_total_cost_micros,
AVG(a.cost_micros)    AS recorded_average_cost_micros
```

Asked directly whether wrapping the sum in `COALESCE(SUM(a.cost_micros), 0)` is acceptable for a finance
report, the student answered:

> "不可以"

Correct. `COALESCE(..., 0)` converts "we do not know" into the confident claim "it cost nothing," and
that claim reaches a billing decision. Render the NULL, or render the completeness ratio — do not
manufacture a zero.

Engineering Thinking:

An aggregate over partially recorded data is a statement about your **records**, not about reality. Name
it accordingly.

Production Example:

Two Attempts, one at 1500 micros and one NULL: `SUM` = 1500, `AVG` = 1500, completeness 1/2. Reporting
"average cost 1500" without that 1/2 overstates confidence.

Exercise:

Write the per-Job cost query with completeness columns, and justify rejecting `COALESCE(SUM(...), 0)`.

## Concept 7: CTE Pre-aggregation for Two Independent Children

Tech Lead Question:

One query must return, per Job: Attempt count, Event count, and total recorded cost. Joining both
children multiplies rows. What is the fix?

Student Answer:

> "不知道"

Tech Lead Review:

This is the structural answer to Concept 2. **Aggregate each child to one row per Job first, then join
the already-collapsed summaries.**

```sql
WITH attempt_summary AS (
    SELECT a.job_id,
           COUNT(a.attempt_id) AS attempt_count,
           SUM(a.cost_micros)  AS recorded_total_cost_micros
    FROM app.job_attempts AS a
    GROUP BY a.job_id
),
event_summary AS (
    SELECT e.job_id, COUNT(e.event_id) AS event_count
    FROM app.job_events AS e
    GROUP BY e.job_id
)
SELECT j.job_id, ...
FROM app.jobs AS j
LEFT JOIN attempt_summary AS s ON s.job_id = j.job_id
LEFT JOIN event_summary   AS v ON v.job_id = j.job_id
WHERE j.tenant_id = $1;
```

Because each CTE is already one row per `job_id`, both joins are one-to-one and no multiplication is
possible. Jobs with no children keep their row, with NULL counts — which the report may present as `0`
for a **count** (absence of rows genuinely is zero rows) while still leaving an unknown **cost** as NULL.

The tempting shortcut — `COUNT(DISTINCT a.attempt_id)` and `COUNT(DISTINCT e.event_id)` in one flat
join — does deduplicate the counts, but `SUM(a.cost_micros)` remains multiplied, and `SUM(DISTINCT ...)`
is wrong outright because two Attempts may legitimately cost the same amount.

Engineering Thinking:

Fix the grain, not the symptom. `DISTINCT` patches a count; pre-aggregation removes the multiplication.

Production Example:

The per-Job operations panel is built exactly this way, which is why its cost column can be trusted.

Exercise:

Rewrite a multiplying two-child query using CTE pre-aggregation and explain why `SUM(DISTINCT ...)` is
not a fix.

## Concept 8: Stage-aware "Stuck" Detection

Tech Lead Question:

Find Jobs stuck in `running`. Which clock do you use — `jobs.started_at` or the current Attempt's
`started_at`?

Student Answer:

> "app.job_attempts的started_at"

Tech Lead Review:

Correct, and it is the more subtle choice. `jobs.started_at` measures the whole Job including retries; the
**current Attempt's** `started_at` measures the execution that is actually hanging right now.

Selecting "the current Attempt" needs a deterministic rule, not a guess:

```sql
SELECT DISTINCT ON (a.job_id) a.job_id, a.attempt_id, a.attempt_number, a.started_at, a.finished_at
FROM app.job_attempts AS a
ORDER BY a.job_id, a.attempt_number DESC, a.attempt_id DESC
```

The `attempt_id` tie-breaker is the Day30 determinism rule reappearing: without it, equal
`attempt_number` values make the chosen row arbitrary.

The result is deliberately **not** a verdict. It is a classified candidate list:

```text
running_without_attempt                -> status says running, no Attempt row exists
running_with_finished_current_attempt  -> Attempt finished, Job status never advanced
running_attempt_over_threshold         -> Attempt exceeds the threshold interval
running_within_threshold               -> normal
```

Asked whether a long-running Attempt proves the provider call is dead, the student answered:

> "不能"

Correct. The row proves only that **no completion has been recorded**. The worker may be alive, the
provider may be slow, or the completion write may have failed. Only external verification distinguishes
these — which is the Day28 boundary restated in SQL.

Engineering Thinking:

Choose the clock that matches the stage you are diagnosing, and label output as candidates, not facts.

Production Example:

A `running_with_finished_current_attempt` cluster after a deploy points at a failed status-write path,
not at a slow provider.

Framework Connection:

Feeds the Day28 stuck-Job runbook; the threshold is a parameter, never a hardcoded constant.

Exercise:

Write the stage-aware stuck query with `DISTINCT ON` and classify the four anomaly cases.

## Concept 9: Throughput Windows and Half-open Boundaries

Tech Lead Question:

Report Jobs completed in a time window. What boundary convention do you use?

Student Answer:

> "使用左闭右开的窗口"

Tech Lead Review:

Correct — half-open `[start, end)`.

```sql
AND j.finished_at >= $2::timestamptz      -- inclusive lower bound
AND j.finished_at <  $3::timestamptz      -- EXCLUSIVE upper bound
```

With `BETWEEN` (inclusive on both ends), a Job finishing exactly at the boundary instant is counted in
**two** consecutive windows. Daily totals then exceed the true total, and the discrepancy is small enough
to survive review for months.

The other half of correctness is which timestamp defines membership. `finished_at` answers "completed in
this window"; `created_at` answers "arrived in this window." They are different reports and must not be
mixed under one label.

Engineering Thinking:

Boundary conventions are a correctness contract between adjacent reports, not a style preference.

Production Example:

Hourly throughput panels summing to more than the daily total is the classic `BETWEEN` double-count
signature.

Exercise:

Write the completed-in-window query with half-open bounds and state which timestamp defines membership.

## Concept 10: Release Provenance and the Affected Set

Tech Lead Question:

A bad worker release ran for 90 minutes. How do you find exactly the Jobs it touched?

Student Answer:

> "使用job_events的metadata去查询"

Tech Lead Review:

Correct, and it is the strongest available answer because it uses **recorded provenance** rather than
inference:

```sql
AND e.metadata ->> 'worker_release_id' = $2
```

The alternative — a time window over `started_at` — is only a proxy. It sweeps in Jobs that overlapped
the window but ran on the previous release, and misses Jobs whose provenance is real but whose timestamps
fall outside your assumed boundary. Time correlation is not causation.

This works only if the worker actually writes `worker_release_id` into event metadata. If provenance was
never recorded, no query can recover it — you fall back to the time window and must state the imprecision
explicitly in the incident record.

Engineering Thinking:

Provenance is a design decision made **before** the incident. Queries can only read what was written.

Production Example:

"Release `2026-07-20.3` touched 1,204 Jobs" is actionable; "roughly the Jobs from 14:00-15:30" is a guess
that will be wrong at both edges.

Framework Connection:

Day31 defined `metadata` as a JSONB column; Day32 turns it into an audit capability.

Exercise:

Write the affected-set query keyed on release provenance and explain why a time window is weaker.

## Concept 11: Integrated Failure Analysis — Rollback Is Not Repair

Tech Lead Question:

A release was rolled back. Are the Jobs it already processed now correct?

Student Answer:

> "回滚只是把版本还原到之前的版本，并没有修复已经处理的数据"

Tech Lead Review:

Exactly right, and this is the sentence the whole day builds toward.

```text
Rollback  -> stops FUTURE bad writes
Rollback !-> repairs committed rows
Rollback !-> undoes external side effects (provider charges, emails, webhooks)
```

Committed rows stay committed. Money already spent stays spent. Repair is a **separate, deliberate,
audited operation** — and Day32 does not perform it. The Day32 artifact is read-only by design; it
produces evidence:

```text
attempt_evidence  -> per-Job Attempt counts, failure counts, recorded cost
artifact_evidence -> whether result artifacts exist
outbox_evidence   -> whether downstream notifications were published
evidence_class    -> classification, NOT a repair instruction
```

The `outbox_evidence` piece matters most: if a Job produced a wrong result **and** its outbox row was
already published, downstream systems have consumed bad data. Fixing the database alone leaves the
consumers wrong.

Engineering Thinking:

Separate three questions and never let them collapse: what happened, what is affected, what to do. Day32
answers the first two only.

Production Example:

A rollback with 1,204 affected Jobs, 900 published outbox events, and 300 artifacts still referenced by
users requires three different remediation tracks — none of which are "redeploy and move on."

Framework Connection:

Day28's incident response now has a query layer; the repair layer belongs to later transaction and
migration lessons.

Exercise:

Write the read-only incident evidence query and explain why it deliberately contains no `UPDATE`.

---

# Common Misconceptions

## Mental Model Evolution (Day31 -> Day32)

Day29 established that a Job must exist as a durable row with an enforced table contract.

Day30 established that `WHERE` is a modification boundary, `ORDER BY` needs a deterministic tie-breaker,
and NULL propagates through three-valued logic.

Day31 established that entities, cardinality, and constraints define what combinations of rows may
legally exist — one Job to many Attempts, one Job to many Events, as **independent** relationships.

Day32 changes what you do with those relationships:

```text
Before Day32: "I have tables with correct constraints, so my queries return correct answers."
After  Day32: "Correct constraints permit MANY result shapes. The grain I choose IS the answer's meaning."
```

Three shifts specifically:

1. **From "join to get data" to "join to choose a grain."** The join is not retrieval; it decides whether
   relationships are preserved, discarded, or multiplied. Day31's independent one-to-many children are
   exactly why a single flat join multiplies — the correctness of the model is what makes the naive query
   wrong.

2. **From "aggregate functions compute totals" to "aggregates describe my records."** NULL is unknown, so
   `SUM` and `AVG` report what was recorded. Day30's three-valued logic, previously a filtering concern,
   now determines what a finance number is entitled to claim.

3. **From "the query tells me what happened" to "the query gives me candidates and evidence."** A stuck
   row, an affected set, an incident classification — each is a statement about persisted facts. Day28's
   "compute rollback is not data repair" is no longer an architectural slogan; it is the reason the Day32
   artifact contains no `UPDATE`.

Carried forward: this reasoning is about **meaning**, and nothing else. Day33 asks whether the facts
these queries read were written **atomically**; Day35 asks what they **cost**. Neither can rescue a wrong
grain — a fast query over an atomically written database is still the wrong answer if it counts the wrong
rows.

## Misconception list

## Misconception 1: "A join filters rows step by step"

Wrong: joining a 3-row Attempt result with 4 Events gives 4 rows, or 0 rows if the first join matched
nothing.

Right: a join produces **every matching combination** — 3 x 4 = 12. And with `LEFT JOIN` preserved, a
zero-Attempt Job joined to 4 Events yields 4 rows, because the NULL-extended row matches every Event.

Why it matters: this silently multiplies `COUNT` and `SUM` in exactly the reports finance and operations
trust.

## Misconception 2: "`COUNT(*)` counts entities"

Wrong: `COUNT(*)` after `GROUP BY j.job_id` counts Jobs.

Right: `COUNT(*)` counts **result rows**, including the NULL-extended outer-join row. A zero-Attempt Job
returns `COUNT(*) = 1` and `COUNT(a.attempt_id) = 0`.

Why it matters: an inflated retry metric makes a healthy queue look like it is thrashing.

## Misconception 3: "NULL in an aggregate is basically zero"

Wrong: `SUM(cost_micros)` gives the total cost; NULL contributes nothing, which is the same as zero.

Right: NULL means **unknown**. The sum is the total of *recorded* cost, and `AVG` divides only by
reporting Attempts. `COALESCE(SUM(...), 0)` upgrades ignorance into a false claim.

Why it matters: it is a billing statement. Say "recorded," or publish the completeness ratio.

## Misconception 4: "Filtering in `WHERE` is always equivalent"

Wrong: moving `a.error_code IS NOT NULL` from `FILTER` into `WHERE` is a harmless simplification.

Right: `WHERE` removes input rows — deleting successful Attempts and the zero-Attempt placeholder, which
collapses the `LEFT JOIN` into an `INNER JOIN`.

Why it matters: your failure-rate denominator quietly loses every healthy Job.

## Misconception 5: "A long-running Attempt proves the provider call is dead"

Wrong: no completion after 30 minutes means the call failed.

Right: it proves only that **no completion has been recorded**. Worker alive, provider slow, or the
completion write failed — all produce the identical row.

Why it matters: acting on the wrong branch double-charges the customer or cancels healthy work.

## Misconception 6: "Rollback fixes the data"

Wrong: reverting the release restores correctness.

Right: rollback stops future bad writes. Committed rows, provider charges, and published outbox events
all persist.

Why it matters: teams close incidents that are still actively wrong downstream.

---

# Engineering Trade-offs

## Trade-off 1: `INNER JOIN` vs `LEFT JOIN`

| Aspect | `INNER JOIN` | `LEFT JOIN` |
| --- | --- | --- |
| Rows returned | Matching combinations only | All left rows preserved |
| Missing child | Row disappears | Row kept, columns NULL |
| Operational meaning | Assumes the relationship exists | Treats absence as evidence |
| Downstream burden | None | Consumer must handle NULL |

Choose `LEFT JOIN` whenever absence is a fact operations needs to see — queued Jobs, unretried failures,
Jobs without artifacts.

## Trade-off 2: Flat join + `DISTINCT` vs CTE pre-aggregation

| Aspect | Flat join with `COUNT(DISTINCT ...)` | CTE pre-aggregation |
| --- | --- | --- |
| Counts | Correct | Correct |
| `SUM` / `AVG` | **Still multiplied** | Correct |
| Readability | Hidden multiplication | Explicit one-row-per-owner |
| Failure mode | Silently wrong money | Structurally prevented |

`DISTINCT` treats a symptom. Pre-aggregation removes the cause and is the only safe option when any
additive measure is involved.

## Trade-off 3: `jobs.started_at` vs current Attempt `started_at`

| Aspect | Job clock | Current Attempt clock |
| --- | --- | --- |
| Measures | Total elapsed including retries | The execution hanging now |
| Retry sensitivity | A retried Job looks stuck | Reflects the live attempt |
| Query cost | Simple predicate | Requires `DISTINCT ON` selection |
| Best for | SLA against the customer | Diagnosing a hang |

Both are legitimate; publishing one under the other's label is not.

## Trade-off 4: Release provenance vs time-window proxy

| Aspect | `metadata ->> 'worker_release_id'` | Time window |
| --- | --- | --- |
| Precision | Exact affected set | Approximate at both edges |
| Prerequisite | Worker must record it | None |
| False positives | None | Jobs from the prior release |
| Incident value | Actionable list | Estimate requiring disclosure |

Provenance must be designed in before the incident; the fallback is legitimate only when its imprecision
is stated.

---

# Hands-on Exercises

## Exercise 1: Preserve zero-Attempt Jobs (Beginner)

Rewrite an `INNER JOIN` dashboard query so queued Jobs with no Attempts remain visible. State the result
grain and what the NULL Attempt columns mean.

Verification: a Job with zero Attempts returns exactly one row with NULL Attempt columns.

## Exercise 2: Predict row multiplication (Beginner)

For one Job, complete the table for (0,0), (0,4), (3,0), (3,4) Attempts and Events under a preserved
outer join. Explain why (0,4) is not zero.

Verification: answers are 1, 4, 3, 12.

## Exercise 3: NULL-aware counting with `FILTER` (Intermediate)

Write per-Job `total_attempts` and `failed_attempts` using `COUNT(child_pk)` and `FILTER`. Then explain
what breaks if the condition moves into `WHERE`.

Verification: healthy Jobs appear with `failed_attempts = 0`; zero-Attempt Jobs still appear.

## Exercise 4: Honest cost reporting (Intermediate)

Report per-Job recorded total and average cost alongside `total_attempts` and `cost_reported_attempts`.
Justify in one sentence why `COALESCE(SUM(...), 0)` is rejected.

Verification: an all-NULL-cost Job shows NULL cost with a completeness of 0 / N — never `0` micros.

## Exercise 5: CTE pre-aggregation (Advanced)

Return per-Job Attempt count, Event count, and recorded cost in one statement without multiplication.
Explain why `SUM(DISTINCT ...)` is not an alternative.

Verification: a Job with 3 Attempts and 4 Events returns one row with counts 3 and 4 and an unmultiplied
cost.

## Exercise 6: Stage-aware stuck candidates (Advanced)

Select each Job's current Attempt with `DISTINCT ON` and a deterministic tie-breaker, then classify the
four anomaly cases. State why the output is candidates, not a verdict.

Verification: a `running` Job whose latest Attempt has `finished_at` set is classified
`running_with_finished_current_attempt`.

## Exercise 7: Incident evidence without repair (Advanced)

Given a release identifier, produce per-Job evidence covering Attempts, artifacts, and outbox
publication. Explain why the query contains no `UPDATE`.

Verification: Jobs whose outbox events are already published are visibly distinguished from those that
are not.

---

# Relevant Framework Connections

## FastAPI

Operational endpoints returning these aggregates must keep `tenant_id` a server-authenticated predicate,
never a client-supplied parameter. Response models must represent NULL as null — not as `0` — so an
unknown cost cannot be silently rendered as free.

## SQLAlchemy

Written as raw parameterized SQL today because the grain must be explicit. ORM relationship loading hides
exactly the multiplication Concept 2 exposes: a naive eager load across two collections produces the same
3 x 4 = 12 problem, with the corruption buried under object mapping.

## Pydantic

Response schemas for these reports need `Optional[int]` for recorded cost and required `int` for counts.
That type distinction is the completeness contract, enforced at the API boundary.

---

# AI Backend Connections

## Connection 1: Queue health is a query, not a feeling

Day28 defined oldest-queued-age as an SLO signal. Concept 5 makes it a real statement — and forces the
empty-queue NULL case to be rendered distinctly from a metrics outage.

## Connection 2: Cost attribution needs completeness, not confidence

AI workloads bill per provider call. Concept 6's `recorded_*` naming plus `cost_reported_attempts` is what
makes a per-tenant cost report defensible when providers fail to report usage.

## Connection 3: Stuck detection must be stage-aware

Long-running inference is normal; a hung worker is not. Concept 8's current-Attempt clock distinguishes
"this Attempt is slow" from "this Job has been retried five times," which are different incidents.

## Connection 4: Incident response reads, it does not repair

Day28 established that compute rollback is not data repair. Concept 11 turns that into a read-only
evidence query — including outbox publication state, because downstream consumers of bad results are the
part teams forget.

---

# English Interview

## Q1: Explain the difference between `INNER JOIN` and `LEFT JOIN` in an operational dashboard.

Student Answer (recorded):

> "INNER JOIN only returns rows when both tables have a matching job_id. So a job that was just created
> and has no attempt row will disappear from the dashboard. LEFT JOIN keeps every job and fills the
> attempt columns with NULL. For a queue dashboard we need LEFT JOIN, because a job with no attempts is
> exactly the problem we want to see."

Feedback: technically accurate and correctly framed around operational meaning. Strengthen it by naming
the grain explicitly — "one row per Job-Attempt combination, and NULL means no Attempt row exists."

## Q2: Why can joining two child tables in one query corrupt an aggregate?

Model answer:

> "A join returns every matching combination. If a job has three attempts and four events, joining both
> in one statement returns twelve rows, so `COUNT` and `SUM` are multiplied. The fix is to aggregate each
> child to one row per job in a CTE first, then join those summaries — one-to-one joins cannot multiply.
> `COUNT(DISTINCT ...)` repairs the counts but leaves `SUM` wrong."

## Q3: A finance report sums `cost_micros` and some values are NULL. Is the total correct?

Model answer:

> "It is the total of recorded costs, not of incurred costs. NULL means unknown, not zero. I would name
> the column `recorded_total_cost_micros` and publish `COUNT(cost_micros)` beside `COUNT(attempt_id)` so
> the reader sees completeness. I would not wrap it in `COALESCE(..., 0)`, because that turns unknown
> into a confident claim that it cost nothing."

## Q4: After rolling back a bad release, is the data correct?

Model answer:

> "No. Rollback stops future bad writes. It does not repair committed rows and cannot undo external side
> effects like provider charges or published outbox events. I would first identify the affected set using
> recorded release provenance in event metadata, then produce read-only evidence per job — attempts,
> artifacts, and whether outbox events were already published — and treat repair as a separate audited
> operation."

Key vocabulary: `result grain`, `row multiplication`, `conditional aggregation`, `completeness`,
`half-open window`, `provenance`, `affected set`, `evidence versus verdict`.

---

# Mental Model Summary

```text
1. Define the result grain BEFORE writing the query.
   One row = one what? Every later decision follows from this answer.

2. Choose the join from what a MISSING row means.
   INNER discards absence. LEFT preserves it as evidence.

3. A join returns COMBINATIONS, not a filtered sequence.
   3 Attempts x 4 Events = 12 rows. Two independent children multiply.

4. COUNT(*) counts ROWS. COUNT(child_pk) counts EXISTENCE.
   After LEFT JOIN, a zero-child owner gives 1 and 0 respectively.

5. FILTER narrows an AGGREGATE. WHERE narrows the INPUT SET.
   Moving a child condition into WHERE silently collapses LEFT into INNER.

6. NULL is UNKNOWN, not zero.
   SUM/AVG describe RECORDED facts. Publish completeness; never COALESCE money to 0.

7. Pre-aggregate each child in a CTE, then join one-to-one.
   DISTINCT patches counts; it does not fix SUM.

8. Match the CLOCK to the STAGE you are diagnosing.
   Job clock = customer SLA. Current-Attempt clock = the hang happening now.

9. Time windows are half-open [start, end).
   BETWEEN double-counts boundary rows across adjacent windows.

10. Recorded PROVENANCE beats time correlation.
    A release id in metadata is the affected set. A time window is a proxy you must disclose.

11. Queries produce EVIDENCE and CANDIDATES, not verdicts.
    "No completion recorded" != "the provider call is dead."

12. Rollback stops FUTURE bad writes.
    It does not repair committed rows or undo provider charges and published outbox events.
```

Chinese synthesis (student, end of session):

> "JOIN是用于表与表之间的连接，如果使用INNER JOIN那么就是要求两张表都存在同样的数据才行，LEFT
> JOIN是以左表为准，右表没有的就用NULL填充。所以要看缺失的行代表什么意思，如果缺失本身就是需要看到的信息就要用
> LEFT JOIN。聚合函数遇到NULL会跳过，所以SUM和AVG算出来的是已经记录的数据，不是真实发生的全部数据。查询只
> 能告诉我数据库里记录了什么，不能证明外部真实发生了什么，回滚也只是停止后面的错误写入，已经提交的数据和已经
> 花掉的钱都还在。"

Targeted corrections applied during review:

1. "两张表都存在同样的数据" is imprecise — `INNER JOIN` matches on the **join predicate**, and returns every
   matching combination, not one row per match.
2. The synthesis omits **row multiplication**, which is the day's most expensive failure mode. Add: two
   independent one-to-many children in one statement multiply the result.
3. "跳过NULL" is mechanically right but should carry the engineering consequence: the number is a claim
   about your **records**, so it must be named and published as such.

---

# Today's Takeaway

Correct constraints do not produce correct answers. Day31 guaranteed which rows may legally exist; Day32
showed that the same legal rows support many different result shapes, and that **the grain you choose is
the meaning of the answer**.

Three things carry forward. First, a join is a decision about whether absence is preserved, discarded, or
multiplied — and two independent children joined in one statement corrupt every additive measure silently.
Second, aggregates over partially recorded data describe your records, not reality; `COALESCE(SUM(...), 0)`
is how "we do not know" becomes "it cost nothing" on a billing page. Third, an operational query yields
evidence and candidates. A row proves that no completion was recorded — never that a provider call is dead,
and never that a rollback repaired anything.

That is why the Day32 artifact is read-only by design. Knowing what happened and knowing what is affected
are prerequisites for repair, not substitutes for it.

---

# Before Next Lesson Checklist

- [ ] I can state the result grain of a query before writing it.
- [ ] I can explain why a zero-Attempt Job disappears under `INNER JOIN` and what its NULL columns mean
      under `LEFT JOIN`.
- [ ] I can predict row counts for (0,0), (0,4), (3,0), (3,4) Attempts and Events.
- [ ] I can explain why `COUNT(*)` = 1 and `COUNT(a.attempt_id)` = 0 for a zero-Attempt Job.
- [ ] I can write conditional aggregation with `FILTER` and say what breaks if the condition moves to
      `WHERE`.
- [ ] I can justify rejecting `COALESCE(SUM(cost_micros), 0)` in a finance report.
- [ ] I can rewrite a multiplying two-child query using CTE pre-aggregation.
- [ ] I can select a current Attempt deterministically with `DISTINCT ON` and a tie-breaker.
- [ ] I can explain why `BETWEEN` double-counts across adjacent windows.
- [ ] I can explain why release provenance beats a time-window proxy for an affected set.
- [ ] I can explain why rollback does not repair committed rows or external side effects.

Preparation for Day33 (PostgreSQL Transactions and Atomic State Changes):

- [ ] Re-read `projects/ai-backend-data-layer/sql/004_sql_joins_aggregation_and_operational_queries.sql`
      and note which evidence each query depends on being written at all.
- [ ] Note that Day32 reads facts but never asks whether a Job row, its Event, and its Outbox row were
      committed **together** — that is the Day33 question.
- [ ] Be ready to explain why `running_with_finished_current_attempt` may be a partially committed write
      rather than a slow worker.
- [ ] Keep indexes and execution plans out of scope; those are Day35.
