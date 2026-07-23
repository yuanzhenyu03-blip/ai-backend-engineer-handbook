# Lesson 36 — Schema Evolution and Safe Migrations

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day35 — PostgreSQL Indexes and Query Planning

Previous Lesson: [Day35 — PostgreSQL Indexes and Query Planning](day35-postgresql-indexes-and-query-planning.md)

Next Lesson: Day37 — PostgreSQL Production Reliability (planned — see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day37 lesson file does not exist yet)

Engineering Artifact: The Day36 safe-migration design pack (`sql/008_schema_evolution_and_safe_migrations.sql`) — a phased Expand -> Backfill -> Validate -> Switch -> Contract design for adding the Lease columns to a populated table, with safe/unsafe DDL, a bounded recovery template, and rollback-vs-forward-fix boundaries — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

PostgreSQL Cheat Sheet: [cheat_sheets/postgresql.md](../../cheat_sheets/postgresql.md)

PostgreSQL Interview: [interview/postgresql.md](../../interview/postgresql.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 100-130 minutes
Hands-on migration design + disposable-PostgreSQL DDL/backfill practice: 100-130 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Define a migration as a **versioned state transition** across schema, existing data, and multiple deployed application versions — and explain why a valid `ALTER` alone proves none of that.
2. Explain why `ADD COLUMN lease_token uuid NOT NULL` is rejected **atomically** on a populated table, and why forcing required writes also breaks old code.
3. Expand with **nullable** Lease columns and **no fabricated default**, and treat even a nullable `ADD COLUMN` as a lock-aware operation.
4. Judge a database default as a **business fact** (`is_archived DEFAULT false` only if verified) and reject `lease_token DEFAULT gen_random_uuid()` as fabricated ownership plus rewrite risk.
5. Scope a Backfill to a trusted target predicate (`job_status = 'running' AND lease_token IS NULL`), route unknowable rows to reconciliation, and never fabricate a token or call the Provider.
6. Drain/isolate old Workers **before** legacy recovery, because they do not enforce the token guard and can cause double execution.
7. Build a Backfill that is small-batch, short-transaction, idempotent, restartable, and observable, using `SELECT ... FOR UPDATE SKIP LOCKED` and a **database-backed** checkpoint.
8. Add the running-requires-Lease invariant as `CHECK ... NOT VALID` (protects new writes immediately, historical rows unverified), then `VALIDATE CONSTRAINT` after remediation.
9. Deploy the Day35 stale-lease index with `CREATE INDEX CONCURRENTLY` (non-transactional, can leave an invalid index), and complete the Switch/Contract phases only on evidence.
10. Decide **rollback vs forward fix** by durable state, and use forward fix once real Lease data or external side effects exist.

---

# Why This Matters

Day34 said ownership must be a committed Lease, and Day35 designed the index for it — but both stopped at the schema boundary, because `claim_owner`, `lease_token`, and `lease_expires_at` do not exist on the Day31 table. Day36 is where that conceptual future becomes real, and it is the most dangerous kind of change: a live, populated table serving old code and new code at the same time.

The trap is treating a migration as a single `ALTER` statement. It is not. It is a transition that must keep old data valid, old code running, and new code correct **simultaneously**, and it spans schema, data, and every deployed application version. Get the ordering wrong and you either block a production table, break old workers, invent ownership that was never real, or trigger duplicate Provider charges by handing a running Job to a new protocol while an old Worker still executes it.

So Day36 is a discipline: expand compatibly, backfill only what you can prove, validate honestly, switch every writer, and contract only on evidence — and know that once real Lease data exists, you forward-fix rather than roll back.

---

# Roadmap Position

```text
Day31  schema / integrity
Day33  atomic durable writes
Day34  concurrent ownership + the conceptual Lease
Day35  query-shape index design + evidence (stale-lease index kept conceptual)
Day36  safe schema/data/application transition — where the Lease becomes real   <-- you are here
Day37  production reliability: DDL locks, long transactions, Vacuum, pooling, backup/recovery
```

Day35 decided *which* index; Day36 owns *how to deploy schema and index changes safely*. Day37 then operates the result. And the whole chain rests on one rule: durable state changes require an explicit ownership, lifecycle, compatibility, and recovery plan.

---

# Lesson Map

```text
1. A migration is a versioned state transition   -> a valid ALTER is not a migration
2. Direct NOT NULL on a populated table          -> rejected atomically; breaks old code
3. Expand with nullable columns                   -> old code ignores, new code tolerates NULL
4. Defaults are business facts                    -> is_archived maybe; lease_token UUID never
5. Backfill scope                                 -> running-only; unknowable -> reconcile
6. Drain old Workers first                        -> they bypass the token guard
7. Backfill mechanics                             -> batched, idempotent, restartable, DB checkpoint
8. FOR UPDATE SKIP LOCKED batches                 -> parallel, distinct, no external calls
9. Completion evidence                            -> remaining targets = 0, not a process counter
10. NOT VALID then VALIDATE                        -> protect new writes, verify history later
11. CREATE INDEX CONCURRENTLY                      -> non-transactional; can leave invalid index
12. Switch                                         -> every writer guards the token; old path gone
13. Contract                                       -> destructive; only on evidence + observation
14. Rollback vs forward fix                        -> decided by durable state
```

---

# Core Mental Model

```text
A migration is a VERSIONED STATE TRANSITION across schema + existing data + every deployed app version.
    A successful DDL statement is NOT a completed migration.

EXPAND -> BACKFILL -> VALIDATE -> SWITCH -> CONTRACT
    Expand: nullable columns, NO fabricated default (old code ignores, new code tolerates NULL).
    Backfill: only where a TRUSTED source exists; unknowable ownership is reconciled, never faked;
              NEVER call the Provider.
    Validate: NOT VALID protects NEW writes now; VALIDATE CONSTRAINT proves history AFTER remediation.
    Switch: every writer uses the token guard; old writers CANNOT coexist.
    Contract: remove temporary compatibility only on evidence + observation (destructive).

NULL honestly means "no proved Lease ownership." Terminal/queued Jobs get no Lease to fill a NULL.
Drain old Workers BEFORE recovery; they don't enforce the token guard.
Rollback vs forward fix is decided by DURABLE STATE, not preference: once real Lease data or external
    side effects exist, forward-fix and reconcile.
```

---

# Main Concepts

## Concept 1: A Migration Is a Versioned State Transition

Tech Lead Teaching:

A migration is not one `ALTER` — it is a **versioned state transition** across three things at once: the
schema, the existing data, and the multiple application versions deployed during the rollout. A valid
`ALTER` statement proves the schema changed; it proves nothing about whether old data, old code, and new
code can coexist safely. That coexistence is the whole job.

Engineering Thinking:

"The DDL succeeded" is a statement about the catalog, not about the system. Ask whether every version of
your data and code is still correct after it.

## Concept 2: Direct `NOT NULL` on a Populated Table

Tech Lead Question:

The Day34 Lease scenario starts from a populated `app.jobs` with no Lease columns. Is `ADD COLUMN
lease_token uuid NOT NULL` safe?

Student Answer:

> "不安全，会直接破坏已有历史行、旧版应用"

Tech Lead Review:

Correct, with one precision. Existing rows have no value for the new required column, so PostgreSQL
**rejects the migration atomically** — it does not silently, partially corrupt rows. And forcing an
immediately-required write would break old application paths that do not set the column. The safe move is
to expand with a **nullable** column first and enforce the required state later.

Engineering Thinking:

A required column on a populated table is a contradiction: the rows that already exist cannot satisfy it.
Nullable first, required later.

## Concept 3: Expand With Nullable Columns

Tech Lead Teaching:

```sql
ALTER TABLE app.jobs
    ADD COLUMN claim_owner      text,
    ADD COLUMN lease_token      uuid,
    ADD COLUMN lease_expires_at timestamptz;
```

Nullable and with **no fabricated business default**. This lets old code ignore the new columns and new
code tolerate `NULL` while data and writers transition. And even a nullable `ADD COLUMN` still takes a
lock, so it remains a **lock-aware** operation that needs an assessed window — a fast catalog change is
still a change on a live table.

Engineering Thinking:

Expand is about making room without making demands. Add the columns; require nothing yet.

## Concept 4: Defaults Are Business Facts

Tech Lead Question:

Is `is_archived boolean NOT NULL DEFAULT false` a safe default? And `lease_token DEFAULT
gen_random_uuid()`?

Student Answers:

> (is_archived) "这个不涉及业务事实"

> (UUID default) "因为旧引用同样不能识别这些列，而历史数据默认值并没有参与，新应用也不能识别默认值"

Tech Lead Review:

Two corrections. `is_archived DEFAULT false` **is** a business fact — a lifecycle fact — and it is safe
*only if* you have proven every historical and future row is genuinely unarchived; it is not "not a
business fact," it is a business fact you must verify. And the real problem with `lease_token DEFAULT
gen_random_uuid()` is not that old code cannot recognize the column (old code can simply ignore a
defaulted column). The real problems are that it **fabricates an ownership epoch** with no real Worker
owner, no expiry, and no proof the Worker is alive; it hands a Lease to queued/terminal Jobs that must not
have one; and a **volatile per-row default** can force a heavy table rewrite. `NULL` honestly means "no
proved Lease ownership."

Engineering Thinking:

A default is a claim that a value is true for every row. Only set one when the claim is a verified business
fact — never to make the migration convenient.

## Concept 5: Backfill Scope

Tech Lead Question:

Which Jobs does the Lease Backfill target?

Student Answer:

> "只是处理running job，因为其他状态不需要lease"

Tech Lead Review:

Correct on scope — only `running` Jobs are candidates; queued and terminal Jobs do not receive a Lease.
But status scope alone does **not** prove ownership. A running Job with no trustworthy owner/token/Provider
outcome is **not** automatically backfillable. Asked about exactly that case:

> "不能，因为还需要隔离、对账、人工或专门恢复流程"

Exactly. An unknown running Job goes to isolation, reconciliation, human review, or a dedicated recovery
policy — never a fabricated token and never a migration-triggered Provider call. And "sent to the exception
queue" is **triage, not resolution**: the row is still `running` with a NULL Lease, so it still violates the
invariant and still blocks completion until a **trusted source** backfills its Lease, or a **real recovery
process** establishes its truthful current state so it is no longer a running-without-Lease row (never a
faked status). Until then, the migration is simply not finished.

Engineering Thinking:

Scope narrows the candidates; it does not certify them. Backfill only what you can prove, and route the
rest to reconciliation.

## Concept 6: Drain Old Workers First

Tech Lead Question:

Can you hand a legacy running Job to the new Lease protocol while an old Worker is still running it?

Student Answer:

> "不安全，因为旧版work还在运行，而不是处于暂停状态"

Tech Lead Review:

Right, and here is the deeper reason. An old Worker does not know the token guard, so it can keep
completing the Job while a new Worker thinks it has taken over — **double execution, conflicting state, and
repeated Provider cost**. The danger is not that the old Worker is paused; it is that it is *still
executing* without enforcing the new ownership rule. So old Workers must be **drained or isolated before**
any legacy recovery or the token-guard Switch.

Engineering Thinking:

Two writers that obey different ownership rules are not concurrent — they are colliding. Remove the old
rule before you rely on the new one.

## Concept 7: Backfill Mechanics

Tech Lead Question:

How do you make the Backfill safe to restart after a crash?

Student Answer (on restart):

> "依赖数据库的安全条件继续，因为重头再做会出发大量两次调用provider"

Tech Lead Review:

Correct instinct, with the mechanism made precise. The Backfill must be small-batch, short-transaction,
idempotent, restartable, and observable, and it must call **no Provider**. The target predicate is
`job_status = 'running' AND lease_token IS NULL`, and repeating that **same** predicate in both selection
and the guarded write means committed rows naturally stop matching after a restart. The **durable database
state is the checkpoint** — not an in-memory processed counter. (And a Backfill never calls the Provider,
so "re-run causes duplicate Provider calls" is avoided by design: external recovery is a separate concern.)

Engineering Thinking:

Idempotency is a predicate, not a counter. If the same query that selects work also proves the work is
undone, a restart is automatically safe.

## Concept 8: `FOR UPDATE SKIP LOCKED` Batches

Tech Lead Question:

How do several migration Workers take distinct batches without stepping on each other?

Student Answer:

> "加for update skip"

Tech Lead Review:

Correct. `SELECT ... FOR UPDATE SKIP LOCKED` lets each migration Worker take a distinct small batch (Day34
carried into migration). The transaction holds locks only around **database state** — never around a
Provider call or a manual reconciliation. A crash before COMMIT releases the locks and rolls the batch
back; a committed row no longer matches the idempotent target predicate, so it is naturally skipped.

Engineering Thinking:

`SKIP LOCKED` parallelizes the safe part (claiming DB rows) and keeps the unsafe part (external work) out
of the transaction entirely.

## Concept 9: Completion Evidence

Tech Lead Question:

What proves the Backfill is complete — a process counter, or something else?

Student Answer:

> "B"

(chosen from options where "B" is the database-backed evidence, not the process counter)

Tech Lead Review:

Correct. Completion evidence is `remaining target rows = 0` **plus** an exception/isolation queue that is
accounted for **by resolution** (each entry actually resolved, or explicitly still blocking — not silent
gaps), batch timing/errors, and confirmed new-write protection. The crucial subtlety: the exception queue is
**triage, not resolution**. A Job merely recorded there is still `running` with a NULL Lease, so it still
counts in `remaining_targets` and still violates the invariant — being queued is not being done.

```sql
SELECT count(*) AS remaining_targets
  FROM app.jobs WHERE job_status = 'running' AND lease_token IS NULL;
```

So `remaining_targets = 0` is a completion condition only when it reaches zero for the **right reason**:
every violating running row was truthfully resolved — either a trusted source completed its Lease backfill,
or a real recovery moved it to a semantically correct, non-violating state — never by parking it in the queue
while it stays NULL, and never by faking a status. A process counter alone proves even less: it can be wrong,
the process can restart, and rows can be added.

Engineering Thinking:

The database is the source of truth about the database. Prove completion by querying state — and check *why*
the count is zero, not just *that* it is.

## Concept 10: `NOT VALID`, Then `VALIDATE`

Tech Lead Question:

You want the invariant "`running` implies non-NULL `claim_owner`, `lease_token`, `lease_expires_at`." Add it
straight, or `NOT VALID` first?

Student Answer:

> "先使用NOT VALID，因为可能会导致阻塞"

Tech Lead Review:

Right direction, with the semantics made precise. `NOT VALID` is **not** an inactive constraint: it
immediately enforces the rule on every new `INSERT`/`UPDATE`, while explicitly **not** claiming that
historical rows have been checked.

```sql
ALTER TABLE app.jobs
    ADD CONSTRAINT jobs_running_requires_lease
    CHECK (job_status <> 'running'
           OR (claim_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL))
    NOT VALID;
```

You then repair/reconcile the legacy rows and run `VALIDATE CONSTRAINT` in a controlled window — but only
once its hard precondition holds: **every** legacy `running` row already has a trusted Lease, or has been
moved by a real recovery process to a state that no longer violates the invariant. A row merely parked in
the exception queue still violates it, so `VALIDATE` would **fail** — you do not run it (and do not proceed
to Switch/Contract) while any violating running row remains. `VALIDATE` scans the data and has
resource/lock/DDL interactions, even though it separates historic verification from the new-write
enforcement you already have. (Note: `NOT VALID` applies to `CHECK`/foreign-key constraints;
`NOT NULL` itself cannot be `NOT VALID`.)

Engineering Thinking:

`NOT VALID` splits "stop new violations" from "prove old rows are clean." Get the first immediately; earn
the second after remediation.

## Concept 11: `CREATE INDEX CONCURRENTLY`

Tech Lead Question:

Day35 designed the stale-lease index. Now that the columns exist, how do you build it on a live table?

Student Answer (on an invalid concurrent index):

> "不能，因为不能假装索引成功，如果这个索引的额外收益为负就需要清理"

Tech Lead Review:

`CREATE INDEX CONCURRENTLY` allows normal DML while it builds, but it is longer-running, still takes brief
stage locks, and — crucially — **cannot run inside an explicit `BEGIN/COMMIT` block**. It needs its own
non-transactional migration step. And the student's point is exactly right: a failed concurrent build can
leave an **invalid** index. Invalid does not mean "usable but slow" — it is **unusable**. Diagnose it, do
not pretend success, and clean up/retry only after deciding scope. Index **validity** is separate from
**net benefit**: an invalid index is useless regardless of its potential benefit, and only a valid, built
index may be measured for retention (Day35).

Engineering Thinking:

An index build is an operation that can fail halfway. Check validity before you measure value, and never
report a build you did not confirm.

## Concept 12: Switch

Tech Lead Question:

Is the Switch complete once the new binary is deployed?

Student Answer (on the precondition):

> "A，因为这样会继续扩大影响范围"

Tech Lead Review:

Correct. Switch means **every** remaining writer uses the same new protocol — new claim, renewal, and
Completion all perform the Lease token guard. Deploying a new binary is not enough: the hard precondition
is that **old Workers can no longer execute or complete legacy Jobs outside the protocol**. Until the old
path is gone, both protocols coexist and the ownership guarantee does not hold.

Engineering Thinking:

A guard that only some writers obey is not a guarantee. Switch is finished when the unguarded path cannot
run.

## Concept 13: Contract

Tech Lead Question:

When can you remove the temporary compatibility code and columns?

Student Answer:

> "不同意，旧路径真正不再被使用后"

Tech Lead Review:

Correct — do not agree to contract early. Contract removes temporary compatibility **only after evidence**:
no old Worker version can write, no unresolved legacy running Job remains, token guards are universal, the
constraint is validated, and an **observation period** shows no old-path traffic or errors. Contract is
often destructive and makes rollback harder, so it is the last step and the most gated.

Engineering Thinking:

Contract trades safety margin for cleanliness. Only spend that margin once the evidence says you no longer
need it.

## Concept 14: Rollback vs Forward Fix

Tech Lead Question:

After a bad Lease rollout, do you roll back the schema or forward-fix?

Student Answer:

> "我会保留schema做forward fix，因为只是 Lease duration配置过短造成的"

Tech Lead Review:

Correct, and the reasoning is the rule. The decision is determined by **durable state**. If the new
schema/data has not become durable and no downstream side effect exists, a rollback may be practical. But
once **real Lease data, Job transitions, Provider calls, or Object Storage artifacts** exist, removing
columns cannot undo them — you preserve compatibility, repair/reconcile, and **forward fix**. The classroom
false-takeover case used a too-short Lease duration *after thousands of real tokens were written*, so the
decision was forward fix (tune the duration, reconcile affected Jobs), **not** `DROP COLUMN`.

Engineering Thinking:

Rollback is only honest while nothing durable depends on the change. After that, the truthful path is
forward.

## Student-initiated question (preserved)

Mid-lesson the student asked whether detailed Backfill mechanics were out of scope:

> "这节课是不是还没讲如何进行详细的Backfill操作是吧，这是之后的课程类容是吧"

Resolution: detailed batching, progress, restartability, and observability are **Day36 scope, not
deferred**. The class then covered the target predicate, short batches, database-backed checkpoints,
`SKIP LOCKED`, no external calls in the backfill, exception/reconciliation handling, and completion
evidence — i.e. Concepts 5-9 above.

---

# Common Misconceptions

## Mental Model Evolution (Day35 -> Day36)

```text
Starting system limitation (not a student quote):
    Day34 defined a committed Lease as the ownership mechanism, and Day35 designed the stale-lease index,
    but both kept claim_owner/lease_token/lease_expires_at CONCEPTUAL because they do not exist on the
    populated Day31 table. There is no safe path yet from "conceptual future state" to real columns.

Correction that Day36 makes:
    Treat the change as a VERSIONED STATE TRANSITION, not one ALTER. Expand nullable -> compatible code ->
    drain old Workers -> NOT VALID constraint -> bounded trusted Backfill (unknowable -> reconcile) ->
    VALIDATE -> Switch every writer to the token guard -> Contract on evidence.

Boundaries Day36 cannot cross:
    Backfill cannot invent ownership or call the Provider. Migration/DB rollback cannot undo Provider cost
    or Object Storage bytes. A successful DDL statement is not a completed migration. CREATE INDEX
    CONCURRENTLY is a separate non-transactional step that can fail to an invalid index.

Net division of labour:
    Day35 decided WHICH index; Day36 safely DEPLOYS schema + index + data + application transition; Day37
    OPERATES the result (locks, long transactions, Vacuum, pooling, backup/recovery). Once real Lease data
    exists, forward-fix, never pretend a rollback undoes it.
```

## Misconception 1: A successful `ALTER` is a completed migration

Wrong: the DDL ran, so the migration is done.

Right: a migration is a versioned transition across schema, data, and every deployed app version. A valid
`ALTER` proves the catalog changed, not that old data, old code, and new code coexist safely.

## Misconception 2: You can just `ADD COLUMN ... NOT NULL`

Wrong: add the required column directly.

Right: on a populated table PostgreSQL **rejects it atomically** (existing rows have no value), and it
breaks old code that does not set it. Expand nullable first, enforce required later.

## Misconception 3: A default is a technical convenience

Wrong: default the new column to make the migration easy.

Right: a default is a **business fact** claimed for every row. `is_archived DEFAULT false` is safe only if
verified true for all rows; `lease_token DEFAULT gen_random_uuid()` fabricates ownership and risks a table
rewrite.

## Misconception 4: Running-only scope means running Jobs are backfillable

Wrong: all running Jobs get a Lease in the Backfill.

Right: status scope narrows candidates but does not certify ownership. A running Job with no trustworthy
source is isolated/reconciled, never assigned a fabricated token.

## Misconception 5: A new token protects a Job even if an old Worker still runs

Wrong: once a new Lease token exists, the Job is safe.

Right: old Workers do not enforce the token guard, so they bypass ownership protection and can double-execute.
Drain/isolate old Workers before recovery and Switch.

## Misconception 6: `NOT VALID` means the constraint is off until you validate

Wrong: `NOT VALID` is an inactive constraint.

Right: it enforces the rule on every new `INSERT`/`UPDATE` immediately; it only defers the historical scan.
`VALIDATE CONSTRAINT` later proves the existing rows.

## Misconception 7: An invalid concurrent index is just a slower index

Wrong: an invalid index still works, just not optimally.

Right: an invalid index is **unusable**. Diagnose and clean up; do not claim success. Validity is separate
from net benefit, and only a valid build may be measured.

## Misconception 8: A Backfill can call the Provider to recover a Job

Wrong: recover ownership by re-running the Provider inside the Backfill.

Right: the Backfill only reads/reconciles **database** state with an idempotent guarded write. External
recovery (Provider/Object Storage) is a separate concern; a restart must never trigger duplicate Provider
calls.

## Misconception 9: Deploying the new binary completes the Switch

Wrong: new code is out, so the token guard is universal.

Right: Switch is complete only when the **old path can no longer write**. Coexisting old and new protocols
mean the ownership guarantee does not hold.

## Misconception 10: Rollback is always available

Wrong: if the rollout goes wrong, drop the columns.

Right: rollback is honest only before durable new data/dependencies exist. After real Lease data, Job
transitions, or external side effects, forward-fix and reconcile — a `DROP COLUMN` cannot undo them.

---

# Engineering Trade-offs

## Trade-off 1: Direct required column vs Expand-then-enforce

| Aspect | Direct `NOT NULL` | Expand nullable, enforce later |
| --- | --- | --- |
| Populated table | Rejected atomically | Succeeds |
| Old code | Breaks (must set column) | Ignores the column |
| Enforcement | Immediate but impossible | `NOT VALID` now, `VALIDATE` after backfill |
| Safety | None | Compatible transition |

## Trade-off 2: Fabricated default vs honest NULL

| Aspect | `DEFAULT gen_random_uuid()` | `NULL` |
| --- | --- | --- |
| Historical meaning | Invents ownership | "No proved Lease ownership" |
| Non-running Jobs | Wrongly Leased | Correctly none |
| DDL cost | Possible table rewrite | Cheap catalog change |
| Honesty | False | True |

## Trade-off 3: Backfill automatable vs reconcile

| Aspect | Automatable Backfill | Reconciliation queue |
| --- | --- | --- |
| Applies to | Rows with a trusted source | Unknown ownership |
| Mechanism | Idempotent guarded `UPDATE` | Isolation, human/recovery policy |
| Provider | Never called | Handled separately, audited |
| Risk of faking | None (guarded) | None (never assign a fake token) |

## Trade-off 4: Rollback vs forward fix

| Aspect | Rollback | Forward fix |
| --- | --- | --- |
| Valid when | No durable new data/side effect | Real Lease data / external effects exist |
| Mechanism | Drop the added columns | Preserve schema, reconcile, tune |
| External effects | Cannot undo Provider/Object Storage | Reconcile them explicitly |
| Contract | N/A | Only after evidence + observation |

---

# Hands-on Exercises

## Exercise 1: Why direct `NOT NULL` fails (Beginner)

Explain why `ADD COLUMN lease_token uuid NOT NULL` cannot be added to a populated `app.jobs`, and how the
failure behaves.

Verification: existing rows have no value; PostgreSQL rejects the migration atomically; old code breaks.

## Exercise 2: Default as a business fact (Beginner)

Compare `is_archived DEFAULT false` with `lease_token DEFAULT gen_random_uuid()` and state when each is
acceptable.

Verification: boolean default only if verified for all rows; UUID default fabricates ownership + rewrite
risk — never.

## Exercise 3: Backfill scope and reconciliation (Intermediate)

Choose the Backfill target scope and explain what happens to a running Job with no trustworthy owner.

Verification: `running` only; unknown ownership goes to isolation/reconciliation, never a fake token.

## Exercise 4: Order the phases (Intermediate)

Order Expand, compatible release, old-Worker drain, `NOT VALID`, backfill/recovery, `VALIDATE`, Switch, and
Contract, and justify each precondition.

Verification: nullable expand first; drain before recovery/switch; `NOT VALID` before backfill; `VALIDATE`
after remediation; Contract last on evidence.

## Exercise 5: Drain before recovery (Intermediate)

Explain why old Workers must be drained before legacy recovery and the token-guard Switch.

Verification: old Workers bypass the token guard -> double execution, conflicting state, repeated Provider
cost.

## Exercise 6: Idempotent Backfill (Advanced)

Write the target predicate and the guarded idempotent `UPDATE`, and explain why a restart is safe.

Verification: `job_status = 'running' AND lease_token IS NULL` in selection and the `UPDATE` guard;
committed rows stop matching; DB state is the checkpoint.

## Exercise 7: Parallel batches (Advanced)

Use `FOR UPDATE SKIP LOCKED` for parallel batches and state what the transaction must never hold locks
around.

Verification: distinct batches per Worker; never lock around Provider calls or manual reconciliation.

## Exercise 8: Completion evidence (Intermediate)

State what proves the Backfill is complete instead of a process counter.

Verification: `remaining targets = 0` **for the right reason** (every violating running row truly resolved, not merely parked in the queue) + an exception queue accounted for by resolution + batch metrics + new-write protection.

## Exercise 9: `NOT VALID` vs `VALIDATE` (Advanced)

Explain what `CHECK ... NOT VALID` enforces immediately and what `VALIDATE CONSTRAINT` adds.

Verification: `NOT VALID` protects new writes now; `VALIDATE` scans and proves historical rows after
remediation.

## Exercise 10: Concurrent index + invalid state (Advanced)

Explain why `CREATE INDEX CONCURRENTLY` cannot run in a transaction and how you handle an invalid index.

Verification: non-transactional separate step; invalid = unusable; diagnose, clean up/retry; validity before
net-benefit measurement.

## Exercise 11: Forward fix the false takeover (Advanced)

For a too-short Lease duration after thousands of real tokens, decide rollback vs forward fix and justify.

Verification: forward fix — durable Lease data exists; tune duration, reconcile; do not `DROP COLUMN`.

## Exercise 12: When to Contract (Advanced)

List the evidence required before Contract and why it is last.

Verification: no old writer can write, no unresolved legacy running Job, universal token guards, validated
constraint, observation period; Contract is destructive.

---

# Relevant Framework Connections

## PostgreSQL

`ALTER TABLE` nullable expansion; defaults as semantic truth; `CHECK ... NOT VALID` / `VALIDATE
CONSTRAINT`; DDL locks and table-rewrite risk; `CREATE INDEX CONCURRENTLY` and invalid indexes; short
transactions; `SELECT ... FOR UPDATE SKIP LOCKED`; bounded Backfill with database-backed progress. Live
operation of these (long transactions, Vacuum, pooling, backup/recovery) is **Day37**.

## FastAPI / application driver

Old and new deployed versions must be compatible: new code tolerates `NULL` during transition; Switch
requires every write path to use the Lease token guard. Deploying a binary is not the Switch.

## Celery / Workers

Drain/isolate old Worker versions; avoid mixed ownership protocols; process legacy running Jobs with a
recovery policy; monitor batch/recovery progress. An old Worker that still runs is the dangerous case.

## Object Storage / AI Provider

Migration/database rollback cannot undo Provider cost or Object Storage bytes. Unknown legacy execution
requires reconciliation, not blind retry or fabricated ownership. The Backfill never calls the Provider.

## Validation evidence for these exercises

State the level, never the level above it. **Day36 classroom status is conceptual only — nothing was
executed.**

```text
1. Conceptual / manual production reasoning        DONE (in class)
   The 14 concepts, the phased plan, the compatibility matrix, the false-takeover forward-fix decision.

2. Repository artifact static review                DONE (repository update)
   008 uses the Day31 columns exactly and adds the Lease columns as NULLABLE (no fabricated default);
   the UNSAFE forms (NOT NULL, DEFAULT gen_random_uuid()) are commented counter-examples; the CHECK is
   added NOT VALID then VALIDATE; the Backfill is a bounded, idempotent, SKIP LOCKED template that calls
   NO Provider and never fabricates a token; CREATE INDEX CONCURRENTLY is a commented non-transactional
   step with an invalid-index note; no SQLAlchemy/Alembic; no credentials.

3. Disposable-PostgreSQL runtime (ALTER / constraint / index / backfill)   NOT RUN
   No Day36 SQL file, PostgreSQL server, ALTER, constraint, index build, EXPLAIN, or backfill was executed
   in class or during the repository update. The lock/rewrite/rollout behaviours are reasoned about, not
   measured.

4. Application / Worker integration                 NOT RUN
   No old/new application compatibility test, no old-Worker drain, no token-guard Switch, no Provider or
   Object Storage integration was executed.

5. Production DDL / deployment / rollback           NOT RUN / OUT OF SCOPE
   No production migration, index build, backfill, benchmark, or rollback ran. Live operation is Day37;
   SQLAlchemy/Alembic are Phase 4; cross-system fencing is Day41.
```

---

# AI Backend Connections

## Connection 1: Long AI Jobs cross deployment versions

Long-running AI Jobs span rollouts, so Lease schema evolution must not create dual execution or duplicate
model-provider charges (Concepts 6, 12).

## Connection 2: Lease fields are correctness/cost controls

`lease_token`, `claim_owner`, and `lease_expires_at` are business correctness and cost controls, not just
nullable columns — which is why a fabricated default is wrong (Concept 4).

## Connection 3: Backfill never calls the Provider

The Backfill identifies and reconciles legacy database state; external effects stay separate evidence, and a
restart never triggers duplicate Provider calls (Concepts 7, 8).

## Connection 4: A false takeover is a cost incident

A too-short Lease after real tokens exist is a production AI cost incident — preserve durable facts, tune the
policy, reconcile affected Jobs, and forward-fix (Concept 14).

## Connection 5: Fast indexes only after safe deployment

The Day35 claim/stale-lease indexes are useful only after safe schema deployment, and must not degrade
acceptance/Worker availability during migration (Concept 11).

---

# English Interview

Three questions were answered aloud. The student's real words are preserved verbatim, including grammar,
because the correction targets the content.

## Beginner: why can't you add the required Lease column directly?

Student answer (actual):

> "beacause the old legacy job can't math new columns"

Correction: the intent is right — old/legacy rows cannot satisfy a new required column. Sharpen it:
existing rows have **no value** for `NOT NULL lease_token`, so PostgreSQL rejects the migration atomically,
and old code that does not set the column also breaks. Expand nullable first.

Strong spoken answer:

> "A populated table can't take `ADD COLUMN ... NOT NULL` with no default, because existing rows have no
> value and PostgreSQL rejects the whole migration atomically. Old code that doesn't set the column would
> also break. I add the column nullable first, backfill and reconcile, then enforce the required state."

## Intermediate: how do old and new code coexist during the transition?

Student answer (actual):

> "because new job can use new role,old legacy job is not influenced ,database constraint is not valid right now"

Correction: correct shape. Precision: the columns are nullable so old code ignores them and new code
tolerates `NULL`; and `NOT VALID` is not "the constraint is off" — it enforces new writes immediately while
deferring the historical scan to `VALIDATE CONSTRAINT`.

Strong spoken answer:

> "During Expand the columns are nullable, so old code ignores them and new code tolerates NULL. I add the
> running-requires-Lease `CHECK` as `NOT VALID`, which enforces the rule on all new writes right away while
> leaving historical rows unverified. After I've drained old Workers and reconciled legacy rows, I run
> `VALIDATE CONSTRAINT` to prove the whole table."

## Senior: rollback or forward fix after a bad Lease rollout?

Student answer (actual):

> "i think forward fix is a better choose,bacause some job status had transit success,may be it has already produce artifact."

Correction: correct decision and the key reason — some Jobs already transitioned and may have produced real
artifacts (and Provider charges). Add: once durable Lease data or external side effects exist, a `DROP
COLUMN` cannot undo them, so you forward-fix and reconcile.

Strong spoken answer:

> "Forward fix. Some Jobs have already transitioned and may have produced Result Artifacts and Provider
> charges, so real durable state and external side effects exist. Dropping the columns can't undo those. I
> preserve the compatible schema, tune the too-short Lease duration, reconcile the affected Jobs, and only
> Contract later once evidence and an observation period say it's safe."

Key vocabulary: `versioned state transition`, `expand`, `backfill`, `validate`, `switch`, `contract`,
`nullable expand`, `NOT VALID` / `VALIDATE CONSTRAINT`, `CREATE INDEX CONCURRENTLY`, `invalid index`,
`idempotent guarded backfill`, `SKIP LOCKED`, `drain`, `reconciliation`, `rollback vs forward fix`.

---

# Mental Model Summary

```text
1. A migration is a versioned state transition across schema + data + every deployed app version.
2. A successful DDL statement is NOT a completed migration.
3. Direct ADD COLUMN ... NOT NULL on a populated table is rejected atomically and breaks old code.
4. Expand with nullable columns and no fabricated default; even a nullable ADD COLUMN is lock-aware.
5. A default is a business fact for every row; is_archived maybe (if verified), lease_token UUID never.
6. NULL honestly means "no proved Lease ownership"; terminal/queued Jobs get no Lease.
7. Backfill scope is running-only; a running Job with no trusted source is reconciled, never faked.
8. Drain/isolate old Workers before recovery/switch; they bypass the token guard -> double execution.
9. Backfill is batched, short-tx, idempotent, restartable, observable; the DB state is the checkpoint.
10. FOR UPDATE SKIP LOCKED takes distinct batches; never hold locks around Provider calls; no Provider in backfill.
11. Completion = remaining targets 0 FOR THE RIGHT REASON (every violating running row truly resolved), not a counter; the exception queue is triage, not resolution, and a parked row still blocks VALIDATE.
12. CHECK ... NOT VALID protects new writes now; VALIDATE CONSTRAINT proves history after remediation.
13. CREATE INDEX CONCURRENTLY is non-transactional (no BEGIN/COMMIT); a failed build leaves an unusable invalid index.
14. Switch = every writer guards the token AND the old path can no longer write; a new binary alone is not Switch.
15. Contract removes temporary compatibility only on evidence + observation; it is destructive.
16. Rollback vs forward fix is decided by durable state; after real Lease data/external effects, forward fix.
```

Final Chinese synthesis (student, verbatim):

> "expand首先扩展nullable列，back fill是在旧的work已经停止以后再做回填，back fill需要进行分批次的回填，还要区分是否可以批量回填还是说需要进行隔离，这都取决于row里面是否包含明确的状态、token、owner等信息。validate是在所有的legacy数据都没问题后整体进行验证。switch是所有新的renew/complete等操作需要新的协议 contract要删除旧状态 rollback与forward fix取决于是否已经生产了额外的artifact以及provider副作用。"

Targeted corrections (Tech Lead):

1. Strong overall: nullable Expand first, drain old Workers before Backfill, batched backfill with
   isolate-vs-batch decided by whether the row carries trustworthy status/token/owner, `VALIDATE` after
   legacy data is clean, Switch requires the new protocol on all renew/complete paths, Contract removes old
   state, and rollback-vs-forward-fix turns on real artifacts/Provider side effects.
2. Precision: `VALIDATE` follows repaired/reconciled legacy data, but `NOT VALID` already protects new
   writes **beforehand** — enforcement is not delayed to `VALIDATE`.
3. Precision: rollback vs forward fix depends on durable schema/data compatibility too, not only on visible
   artifacts or Provider side effects — if real Lease columns/rows are already depended upon, forward-fix.

---

# Today's Takeaway

Day34 named the Lease and Day35 designed its index, but both stopped at the schema line because the columns
did not exist. Day36 crosses that line safely, and the core idea is that a migration is a **versioned state
transition**, not an `ALTER`: schema, data, and every deployed application version must stay correct at the
same time. Expand with nullable columns and no fabricated default; backfill only what a trusted source
proves and reconcile the rest; add the invariant `NOT VALID` to protect new writes and `VALIDATE` it after
remediation; switch every writer to the token guard; and contract only on evidence.

The boundaries are where the discipline shows. `NULL` honestly means "no proved ownership," so terminal and
queued Jobs get no Lease and unknown running Jobs go to reconciliation — never a fabricated token and never a
Provider call inside the Backfill. Old Workers must be drained first, because a writer that ignores the token
guard double-executes. And once real Lease data or Provider side effects exist, a `DROP COLUMN` cannot undo
them: you forward-fix.

Everything here is **design and evidence**. Nothing was executed — no server, no `ALTER`, no constraint, no
index build, no backfill. Day35 decided which index; Day36 designs its safe deployment; Day37 will operate
it. Correctness, then design, then safe evolution, then operations — in that order.

---

# Before Next Lesson Checklist

- [ ] I can explain why a migration is a versioned state transition, not a single `ALTER`.
- [ ] I can explain why `ADD COLUMN ... NOT NULL` is rejected atomically on a populated table.
- [ ] I can expand with nullable columns and justify no fabricated default (and the lock-awareness).
- [ ] I can judge a default as a business fact and reject `lease_token DEFAULT gen_random_uuid()`.
- [ ] I can scope a Backfill to running-only and route unknown ownership to reconciliation.
- [ ] I can explain why old Workers must drain before recovery and the token-guard Switch.
- [ ] I can write an idempotent, restartable, `SKIP LOCKED` Backfill with a database-backed checkpoint.
- [ ] I can explain what `CHECK ... NOT VALID` enforces now and what `VALIDATE CONSTRAINT` adds later.
- [ ] I can explain why `CREATE INDEX CONCURRENTLY` is non-transactional and how to handle an invalid index.
- [ ] I can define the Switch precondition (old path can no longer write) and the Contract evidence.
- [ ] I can decide rollback vs forward fix by durable state and forward-fix the false-takeover case.

Preparation for Day37 (PostgreSQL Production Reliability):

- [ ] Re-read `projects/ai-backend-data-layer/sql/008_schema_evolution_and_safe_migrations.sql` and note the DDL-lock, batch, and index-build boundaries that become live operational concerns.
- [ ] Note that long transactions, WAL/transaction age, Vacuum, connection pooling, and backup/recovery are the Day37 operational lens on Day36's design.
- [ ] Be ready to argue why a safe migration DESIGN (Day36) still needs live operational guardrails (Day37).
- [ ] Keep SQLAlchemy/Alembic (Phase 4) and cross-system fencing tokens (Day41) out of scope.
