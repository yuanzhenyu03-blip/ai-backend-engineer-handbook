# Lesson 33 — PostgreSQL Transactions and Atomic State Changes

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day32 — SQL Joins, Aggregation, and Operational Queries

Previous Lesson: [Day32 — SQL Joins, Aggregation, and Operational Queries](day32-sql-joins-aggregation-and-operational-queries.md)

Next Lesson: Day34 — Concurrency Control, MVCC, and Worker Claims (planned — see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day34 lesson file does not exist yet)

Engineering Artifact: The Day33 transactional write pack (`sql/005_postgresql_transactions_and_atomic_state_changes.sql`) — three short transactions (Accept / Start / Complete) around one external phase, plus the Relay checkpoint — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

PostgreSQL Cheat Sheet: [cheat_sheets/postgresql.md](../../cheat_sheets/postgresql.md)

PostgreSQL Interview: [interview/postgresql.md](../../interview/postgresql.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 100-130 minutes
Hands-on transaction authoring + disposable-PostgreSQL checks: 100-130 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Use `BEGIN` / `COMMIT` / `ROLLBACK` to define **one business-change boundary** — all related database facts commit together or none do.
2. Write the Accept transaction so that, **at acceptance**, a durable Job is created together with the durable Outbox intent to dispatch it (a creation-time coupling, not a permanent equivalence — retention may later archive published rows), and return `202 + job_id` only after it commits.
3. Write the guarded Start transition (`queued -> running`), Attempt, and `job_started` Event as one atomic unit, and gate the following inserts on the affected-row result.
4. Explain why **zero affected rows is a normal result, not a transaction failure**, and why a `SQL`/constraint error is the opposite.
5. Keep the AI Provider call and Object Storage write **outside** any open transaction, and say precisely what PostgreSQL can and cannot prove across that gap.
6. Describe the Transactional Outbox lifecycle and the exact meaning of `published_at` being NULL vs a timestamp.
7. State the delivery model correctly: at-most-once loses, at-least-once duplicates, and **exactly-once is not created by disabling retries** — practical correctness is at-least-once publication plus an idempotent consumer keyed on `outbox_event_id`.
8. Explain why a correct transaction pack is a **write-path contract**, not a schema guarantee, when legacy writers still commit separately.

---

# Why This Matters

Day32 gave you queries that can *see* trouble: a `running_without_attempt` Job, a missing Event, an Outbox row that never appeared, an ambiguous `published_at`. Every one of those is a symptom of the same disease — related facts that were written **separately** and then diverged when something crashed in between.

Day33 removes the disease at the source. A Job that is accepted without its publication intent is stuck forever; a Job marked `running` without its Attempt is a coherence anomaly; a completion that writes the Job state but not the Result Artifact is a lie the dashboard will repeat. The fix is not more queries — it is committing the related facts **together**.

But atomicity has a hard edge that production teaches painfully: PostgreSQL can only commit or roll back **its own rows**. It cannot un-charge an AI Provider, un-write an Object Storage object, or un-publish a message. So the second half of this lesson is about the boundary — where the transaction ends and the external, un-rollbackable world begins — and how to stay correct across a gap you cannot make atomic.

---

# Roadmap Position

```text
Day29  durable Job row (write + commit before 202)
Day30  guarded writes; WHERE as the modification boundary; affected-row evidence
Day31  relational ownership, keys, CHECK/UNIQUE, tenant-aware FKs
Day32  correct joins/aggregation; operational EVIDENCE of partial/missing facts
Day33  atomic multi-table writes + the external-side-effect boundary   <-- you are here
Day34  MVCC, FOR UPDATE, SKIP LOCKED, leases, concurrency-safe claims
Day35  measured indexes for the claim / Outbox / query access paths
Day36  safe schema evolution of populated tables
```

Day33 sits exactly on the seam between "the facts are correct" (Day31/Day32) and "concurrent workers touch them safely" (Day34). Locks cannot repair a wrongly defined business transaction, so the transaction boundary must be right **first**.

---

# Lesson Map

```text
1. Job committed without Outbox        -> the atomic Accept commitment
2. Constraint failure and ROLLBACK     -> uncommitted work vanishes; committed work does not
3. When FastAPI may return 202         -> after COMMIT, never before
4. Atomic Start transition             -> guarded UPDATE + Attempt + Event as one unit
5. Zero affected rows is not an error  -> the control-flow gate
6. ACID in this scenario               -> taught from failures, not as trivia
7. No transaction across an 8-min call -> two short transactions around an external phase
8. Provider succeeds before Complete   -> what PostgreSQL can and cannot prove
9. Outbox lifecycle                    -> published_at, and "does Relay take the row?"
10. Relay crash + stable identity      -> at-least-once, outbox_event_id
11. published_at != consumer success   -> three distinct checkpoints
12. Integrated rollback                -> external side effects survive DB rollback
13. Lost COMMIT response               -> unknown outcome; reconcile by stable id
14. Legacy writer bypass               -> the pack is a contract, not a schema guarantee
```

---

# Core Mental Model

```text
A transaction = ONE complete PostgreSQL business commitment.
    All related database facts commit together, or all roll back together.

It does NOT include Provider, Object Storage, Redis, Celery, or any external effect.
    Those cannot be rolled back, so long external work sits BETWEEN two short
    transactions, guarded by stable ids, checkpoints, idempotency, and reconciliation.

Zero affected rows  = a normal SQL result the APPLICATION must interpret.
SQL / constraint error = a failed transaction that MUST roll back.

The Outbox prevents lost publication intent — but Relay publish and the
published_at write-back are NOT one atomic step. A crash in that gap means
re-publication. So: at-least-once publication + stable outbox_event_id + idempotent
consumer. Disabling retry is at-most-once and can LOSE messages; it is not exactly-once.
```

---

# Main Concepts

## Concept 1: A Job Committed Without Its Outbox

Tech Lead Question:

The Accept path does this:

```sql
INSERT INTO app.jobs (...);
COMMIT;
-- process crashes here
INSERT INTO app.outbox_events (...);
COMMIT;
```

The process crashes between the two commits. What state is the system in?

Student Answer:

> "，PostgreSQL 中会留下queue状态，会造成虽然显示持久化状态是在队列中，实际relay并没有在outbox找到job，所以状态一直在queue，而不会转化为running"

Tech Lead Review:

Exactly right. PostgreSQL holds a committed **queued** Job, but no publication intent. The Relay scans
`app.outbox_events`, not `app.jobs`, so it never learns the Job exists — and the Job sits queued with zero
Attempts forever. Day32 can *surface* the symptom (a queued Job with no Outbox row), but it cannot repair
it or prove the cause.

The rule the artifact encodes (a **creation-time** coupling, not a permanent equivalence — a retention
policy may later archive published Outbox rows, and not every future Event needs an Outbox row):

```text
At ACCEPTANCE: create the durable Job together with the durable intent to dispatch it.
Put both INSERTs in ONE transaction.
```

Engineering Thinking:

If two facts must always be true together, they must commit together. Two commits are two chances to
crash in between.

Production Example:

A tenant reports "nothing is processing." The Jobs table looks healthy — hundreds of queued rows — but the
Outbox is empty for them. Separate commits, a crash, and a silent backlog.

## Concept 2: Constraint Failure and ROLLBACK

Tech Lead Question:

Now both writes are in one transaction. The Job INSERT succeeds, the Outbox INSERT violates a constraint,
and the transaction rolls back. Does the Job remain?

Student Answer:

> "不会，因为原子性证明要么一起成功要么一起失败"

Tech Lead Review:

Correct direction. The precise mechanism: the Job INSERT was **uncommitted** inside the same transaction,
so `ROLLBACK` discards it along with everything else. Atomicity is "all or nothing" — but note *what*
nothing means here.

```text
Uncommitted work in this transaction -> ROLLBACK removes it.
Work COMMITTED by an earlier transaction -> ROLLBACK cannot touch it.
```

That second line is the whole reason Concept 1's bug was possible: the first `COMMIT` had already made the
Job permanent before the crash.

Engineering Thinking:

`ROLLBACK` undoes the current transaction, never a prior commit. "Can I roll this back?" always means "is
it still uncommitted?"

## Concept 3: When FastAPI May Return 202

Tech Lead Question:

Does FastAPI return `202 + job_id` before or after the Accept `COMMIT`?

Student Answer:

> "应该在commit之后，因为如果commit之前就已经返回202，如果发生回滚，而数据库没有业务承诺"

Tech Lead Review:

Correct. `202 + job_id` **acknowledges an existing durable commitment**, so it must follow a successful
`COMMIT`. Return it early and a subsequent rollback leaves you having promised a Job that does not exist.

The subtle case: `COMMIT` succeeds but the HTTP response is lost in transit. The client retries. The
transaction did not — and cannot — tell the client the outcome. What protects you is Day31's
`UNIQUE (tenant_id, idempotency_key)` plus a lookup: the retry either finds the committed Job or is
rejected as a duplicate. Atomicity prevents partial facts; **idempotency** makes the uncertain retry safe.

Engineering Thinking:

An acknowledgement is a claim about durable state. Never emit it before the state is durable.

## Concept 4: The Atomic Start Transition

Tech Lead Question:

A Worker claims a Job: it commits `job_status = 'running'`, then crashes before inserting the Attempt and
Event. What does Day32 see, and what should the write path have done?

Student Answer:

> "jobs的状态变成running，但是尝试次数为0，job事件也不存在。应该放在同一个事务保持原子性"

Tech Lead Review:

Correct. Day32 classifies this as `running_without_attempt` — a coherence anomaly, **not** proof the Worker
is merely slow. The guarded `queued -> running` update, the Attempt insert, and the append-only
`job_started` Event must share one transaction:

```sql
UPDATE app.jobs SET job_status='running', started_at=now(), attempt_count = attempt_count + 1
 WHERE job_id=$1 AND tenant_id=$2 AND job_status='queued'
RETURNING job_id, attempt_count;
-- then, only if 1 row returned: INSERT the Attempt (attempt_number = returned attempt_count)
--                               INSERT the job_started Event
```

The `attempt_count` increment happens **in the UPDATE** (database-side, not read-modify-write) and is
returned so the Attempt can use it as `attempt_number` without a client recompute.

There is one more durable fact this transaction quietly establishes: the `attempt_id`. It is the **stable,
pre-call correlation / provider-idempotency key** — it exists *before* the Provider is ever called, so it
survives a crash in the external phase. That is what makes the Provider call recoverable (Concept 8). Note
what this transaction does **not** write: any Provider-returned `provider_request_id` — that id does not
exist yet.

Engineering Thinking:

"The Worker started" is not one fact — it is three (state, attempt, event) plus one durable anchor (the
`attempt_id`) that later reconciliation will depend on. Commit them together or a crash splits them.

## Concept 5: Zero Affected Rows Is Not an Error

Tech Lead Question:

The guarded `queued -> running` UPDATE affects **zero** rows because the Job is already running. Does the
transaction abort? What happens if the code runs the Attempt/Event inserts anyway?

Student Answer:

> "不会终止事务，会发生重复插入attempt与event"

Tech Lead Review:

Correct, and this is the most important operational subtlety in the lesson. PostgreSQL treats zero affected
rows as a **normal statement result**. The transaction stays healthy and the next statement runs. If the
application does not *gate* on the affected-row count, it inserts a second Attempt and Event for a Job it
never legally claimed.

```text
SQL error / constraint error  -> transaction is FAILED, must ROLLBACK
zero affected rows            -> NORMAL result; the APPLICATION must interpret and stop
```

The guard is `UPDATE ... RETURNING`: one row means continue; zero rows means `transition_not_applied` —
roll back and stop. And note what does **not** save you: `UNIQUE (job_id, attempt_number)` stops a
conflicting *number*, but a fresh Attempt with a new number, and a new Event with a new id, would both be
accepted. The constraint cannot replace the transition guard.

Engineering Thinking:

"It ran without error" is not "it did what I meant." A guarded write needs an application decision, not just
a successful statement.

## Concept 6: ACID, Read From the Scenario

Tech Lead Question:

Explain ACID using this exact workflow — not the textbook definitions.

Tech Lead Teaching (this was taught directly, not quizzed as an acronym):

```text
Atomicity   -> the related database facts all commit or all roll back
               (Concepts 1, 4, 12).
Consistency -> constraints enforce database rules, but GUARDED application logic
               still enforces the cross-table/business transition. ACID does not
               invent correct business logic (Concept 5).
Isolation   -> how this transaction interacts with CONCURRENT transactions.
               MVCC, locks, and anomalies are Day34 — deferred on purpose.
Durability  -> after COMMIT, the facts survive a Worker process crash (Concept 2).
```

The trap is Consistency. It guarantees your *constraints* hold, not that your *business rule* was correct.
A perfectly consistent database will happily let a zero-row guarded update be followed by a wrong insert if
the application does not gate it.

Engineering Thinking:

ACID protects the shape of your data. It does not write your business logic for you.

## Concept 7: Never Hold a Transaction During an Eight-Minute Provider Call

Tech Lead Question:

Can you keep one transaction open across the whole Job — `BEGIN`, claim the Job, call the Provider for eight
minutes, write the result, `COMMIT`?

Student Answer:

> "不能这样做，因为可能八分钟中间还会有其他的事务操作数据库"

Tech Lead Review:

Right conclusion, incomplete mechanism. Other transactions are not all blocked — but the long transaction
holds a **connection** for eight minutes, may retain **row locks** and an **old snapshot** (which makes
conflicting work wait and pressures vacuum), and stresses the connection pool. And the decisive reason is
simpler: PostgreSQL **cannot roll back the Provider call or its cost** anyway, so there is nothing to gain
by holding the transaction open across it.

The structure the artifact uses:

```text
short START transaction    -> COMMIT
external Provider + Object Storage phase   (NO open DB transaction)
short COMPLETE transaction  -> COMMIT
```

Engineering Thinking:

A transaction is a lock on a moment of database state. Never hold that lock across work the database cannot
control.

## Concept 8: Provider Succeeds Before the Completion Transaction

Tech Lead Question:

The Provider call returned successfully, but the Completion transaction has not run yet. What can PostgreSQL
prove, and what can it not?

Student Answer:

> "PostgreSQL 能证明states是running，以及attempt和event。无法证明provider生成了结果。job重新排队执行不知道是否产生结果"

Tech Lead Review:

Correct. PostgreSQL proves only the persisted **start** facts: the Job is running, an Attempt and Event
exist. It cannot prove the Provider produced a result. So a blind requeue here can repeat the Provider's
cost, its result, and its side effects — quarantine the unknown outcome and reconcile instead.

There is a design subtlety the review surfaced: **do not conflate two different identifiers.**

```text
provider_idempotency_key / correlation key
    - generated BEFORE the request, from an ALREADY-DURABLE fact (use attempt_id, or a
      value derived from it, committed in Transaction B)
    - if the Provider supports idempotency keys, the Worker SENDS this key with the request
    - this is the RECOVERY ANCHOR

provider_request_id
    - the id the Provider RETURNS after accepting the call
    - does not exist until the call returns; persisted only in Transaction C
    - a convenience for lookup, NOT the recovery anchor
```

Why the split matters — the failure window:

```text
Provider accepts request -> Worker receives provider_request_id
-> Worker CRASHES before Transaction C -> provider_request_id is NEVER persisted
```

If your only handle were the returned `provider_request_id`, recovery would be blind. But because the
pre-call key is `attempt_id` — already durable after Transaction B — reconciliation can still find or
deduplicate the Provider call. Transaction B does **not** persist a Provider-returned id; it persists
`attempt_id`, and that is sufficient *only if* the pre-call key is derived from it and actually sent to the
Provider.

And if the Provider has **no** idempotency support? Then PostgreSQL cannot eliminate this unknown-outcome
window at all. Such an Attempt must be **isolated and reconciled** — query the Provider, inspect Object
Storage, or reconcile by hand — never blindly retried.

Engineering Thinking:

A returned id is a receipt that you *asked*, and it may be lost. The recoverable anchor must be a key you
made durable *before* you asked.

## Concept 9: The Outbox Lifecycle — Does the Relay "Take" the Row?

Student Question (asked spontaneously, preserved):

> "我有一个问题为什么Outbox row，published_at = NULL，outbox row是被relay取走了吗，取走了的话，published_at就会变为null吗。"

Tech Lead Teaching:

A good question because it exposes a queue-shaped assumption that does not apply here.

```text
- The Outbox row is CREATED with published_at = NULL (Transactions A and C).
- The Relay does NOT set published_at back to NULL, and does NOT delete/"take" the row.
- The row is durable PUBLICATION INTENT + audit evidence, not a queue item that must
  disappear when read.
- The Relay polls/claims it, publishes externally, then UPDATEs published_at = now().
- A retention policy may later archive/delete old rows — that is not the publish lifecycle.
```

So `published_at IS NULL` does not mean "the Relay took it." It means never attempted, in flight, or
published-before-a-crash-prevented-write-back.

A second question the artifact forced open: **should every completion write an Outbox row at all?** No.

```text
Job Event   = INTERNAL business history. Append one for every state change.
Outbox Event = a PENDING EXTERNAL INTEGRATION DUTY. Create one ONLY when a real
               downstream consumer must be told (dispatch, notification, webhook,
               billing, search indexing).
Not every Job Event needs an Outbox Event. An Outbox row with no consumer is
unpublishable noise the Relay will carry forever.
```

The Accept `job.accepted` row has a real consumer — the dispatch path that hands the queued Job to a Worker —
which is exactly why Accept couples the two writes. The Completion `job.succeeded` row is **conditional**:
the artifact leaves it commented out because this project defines no downstream consumer, and it must be
enabled only alongside a concrete one. Describing it as a mandatory part of completion would be wrong.

Payload discipline, whichever events you publish:

```text
Outbox payload = STABLE identifiers + minimal references ONLY.
  - NO result bytes            (the bytes live in Object Storage)
  - NO secrets
  - NO short-lived signed URLs (they expire; the row is durable)
The consumer fetches the authorized result later via a stable reference.
outbox_event_id is the consumer's idempotency key.
Publication is at-least-once; it never proves the consumer completed its business work.
```

Engineering Thinking:

An Outbox is a durable log of intent, not a mailbox that empties when read — and not a mirror of internal
history. Publish a row only when someone outside must act on it, and put only stable references in it.

## Concept 10: Relay Crash and Stable Event Identity

Tech Lead Question:

The Relay publishes the message successfully, then crashes **before** the `published_at` write-back commits.
What happens on restart?

Student Answer:

> "也就是说relay发布成功后崩溃，就是说out box的published_at是null。使用outbox_event_id进行标识"

Tech Lead Review:

Correct — provided the crash is *after* the external publish and *before* the `published_at` UPDATE commits.
The row is still NULL, so the restarted Relay may publish the **same** message again, reusing the stable
`outbox_event_id`. That is expected under at-least-once delivery.

```text
publish OK -> crash before write-back -> published_at still NULL
           -> restart republishes the SAME outbox_event_id
```

Engineering Thinking:

If a step and its acknowledgement are not atomic, assume the step can repeat. Design the identity so a
repeat is recognizable.

## Concept 11: `published_at` Does Not Prove Consumer Success

Tech Lead Question:

Does `published_at IS NOT NULL` prove the message was delivered and the business effect happened?

Student Answer:

> "不能证明，只能证明relay已经将消息发布到了queue。不能证明redis后续传递了信息，Clery work正确执行了后面的业务动作"

Tech Lead Review:

Correct (the polished prose says *Celery Worker*, but the answer's meaning is exactly right). There are three
distinct checkpoints, and `published_at` only marks the first:

```text
Relay recorded a successful publish   (published_at = now())
        != Queue delivered the message
        != Consumer processed it successfully
```

Engineering Thinking:

Each hop in a pipeline needs its own evidence. One system's "I sent it" is never another system's "I did
it."

## Concept 12: Integrated Rollback — External Effects Survive

Tech Lead Question:

The Provider already succeeded and charged you; the Object Storage object already exists. In one Completion
transaction, the Attempt-finish and Job-success updates run, then the Artifact INSERT violates a constraint,
and the application rolls back. What survives?

Student Answer:

> "都不存在在了，在同一个事务中还没提交的状态下，任何的回滚之前的操作都不奏效。provider费用已经开销了是无法回滚的，写入object storage的对象也是无法回滚的"

Tech Lead Review:

Correct boundary. Sharper wording: the statements *executed* inside the transaction, but after `ROLLBACK`
none becomes a **committed final fact** — Attempt finish, Job succeeded, the success Event, the Artifact
reference, and any Outbox intent all vanish. What remains is everything the database never controlled: the
**Provider cost** and the **Object Storage bytes**. The object may be an orphan until reconciliation or a
separately audited compensating delete. Database rollback is not Object Storage rollback.

One further guard the Completion transaction must carry — the Attempt-finish UPDATE finishes only an Attempt
that has **not** already finished:

```sql
UPDATE app.job_attempts
   SET finished_at = now(), provider_request_id = $3, cost_micros = $4
 WHERE attempt_id = $2 AND job_id = $1 AND finished_at IS NULL   -- the guard
RETURNING attempt_id;
```

Zero rows here can mean the Attempt does not exist, does not belong to this Job, **or is already finished**.
In every case: ROLLBACK and stop. Overwriting a finished Attempt's `finished_at`, `provider_request_id`, or
`cost_micros` would destroy the evidence of the outcome already recorded. An already-finished current
Attempt on a still-running Job is Day32's `running_with_finished_current_attempt`: it goes to **isolation and
reconciliation**, and is never auto-"fixed" to succeeded by this transaction.

Engineering Thinking:

Rollback is total inside the transaction and powerless outside it. And a completion write must never
overwrite an outcome already recorded — recorded evidence is the thing reconciliation depends on.

## Concept 13: The Lost COMMIT Response

Tech Lead Question:

The connection breaks after the client sends `COMMIT` but before it receives the response. Can you assume the
transaction rolled back?

Student Answer:

> "不能，因为已经提交的持久化数据是无法进行回滚的，不能直接认定事务已经回滚"

Tech Lead Review:

Correct. The outcome is genuinely **unknown**: PostgreSQL may have committed and the acknowledgement was
lost, or it may have rolled back. You cannot assume either. Reconnect and inspect **stable identifiers** —
the `idempotency_key`, the `job_id`, the `outbox_event_id` — to discover what actually happened. Atomicity
prevented partial facts; idempotency makes the retry safe.

Engineering Thinking:

A lost acknowledgement is not a known failure. Resolve uncertainty by reading durable state, not by
guessing.

## Concept 14: A Legacy Writer That Bypasses the Pack

Tech Lead Question:

You ship the correct transaction pack. An old Worker version still writes the Job, Attempt, and Event as
three separate commits. Is the system now atomic?

Student Answer:

> "不能保证，因为三个写入都是独立的事务，只新增正确的事务，就会有可能发生有的写入了，其他的没写入，就失去了原子性"

Tech Lead Review:

Correct. The transaction pack protects only the writers that **use** it. A legacy writer with three separate
commits can still crash between them and leave partial facts. The remedy is operational, not schema-level:
drain/stop old Workers, centralize the write paths, verify every version uses the new boundary, and keep
watching the Day32 coherence queries. Crucially — do **not** claim the schema itself enforces that all child
rows are present. It does not.

```text
A transaction pack is a WRITE-PATH CONTRACT, not a schema guarantee.
It binds participants only.
```

Engineering Thinking:

A convention that some code ignores is not an invariant. Enforcement lives where every writer must pass, or
it does not exist.

---

# Common Misconceptions

## Mental Model Evolution (Day32 -> Day33)

The line below is the *starting system limitation* Day33 inherits — a description of where the design
stood after Day32, not a student quote. (Day32 already established that queries provide repair **evidence**
but never auto-repair; nothing here contradicts that.)

```text
Starting system limitation (not a student quote):
    Day32 queries can OBSERVE and CLASSIFY partial or missing related facts and hand an operator the
    evidence to repair them -- but detection is not prevention. Those gaps exist because related facts
    were written in SEPARATE commits and a crash split them. A read query classifies the wreck; it
    cannot stop the crash from producing it, and it never repairs anything on its own.

Correction that Day33 makes:
    Make one business change commit all related DATABASE facts together or none. That removes the
    database half of the problem at the source.

Boundary Day33 cannot cross:
    A PostgreSQL transaction cannot roll back Provider calls/cost, Object Storage bytes, or Redis
    publication. So the un-rollbackable external work sits BETWEEN two short transactions, guarded by
    stable ids, checkpoints, idempotency, and reconciliation.

Net division of labour:
    Day32 = observe / classify / supply repair evidence.
    Day33 = prevent partial commits INSIDE the database.
    Neither one can undo an external side effect -- only reconciliation can.
```

## Misconception 1: Zero affected rows aborts the transaction

Wrong: a guarded UPDATE that matches nothing fails the transaction.

Right: zero affected rows is a **normal** result; the transaction stays healthy and the next statement runs.
Only a SQL/constraint error fails a transaction. The application must read the affected-row count and stop.

```text
SQL error / constraint error -> transaction FAILED, requires ROLLBACK
zero affected rows           -> normal result; application must interpret and stop
```

## Misconception 2: A transaction means the statements happen at the same time

Actual phrase: `job and outbox event occure same time`.

Right: statements execute **in order**. Atomicity is about final commit visibility and rollback, not
simultaneous execution. The Job INSERT runs, then the Outbox INSERT runs; they simply share one commit
boundary.

## Misconception 3: A stable Outbox id prevents Relay retransmission

Actual phrase: `outbox_event_id ... avoid relay publish twice`.

Right: the Relay may publish again under uncertainty — the id does not stop that. The same stable
`outbox_event_id` lets the **consumer** deduplicate and process the business event once. It prevents
duplicate *processing*, not duplicate *publication*.

## Misconception 4: A PostgreSQL transaction controls the external Provider

From the final Chinese synthesis, preserved verbatim (not silently rewritten):

> "因为数据库事务是控制外部的供应商的业务的。"

This is wrong — very likely a missing 「不能」. PostgreSQL transactions **cannot** control
Provider / Object Storage / Redis / Celery side effects. That inability is precisely why the Provider phase
sits *between* two short transactions rather than inside one.

## Misconception 5: Not retrying after an uncertain publish is exactly-once

From the final synthesis, preserved verbatim:

> "如果设计为exactly-once，恰好一次，如果出现故障就不会进行重新发送"

After correction, the student's verification answer was:

> "这更接近 exactly-once，最大的生产风险是应该发布的消息也丢了"

The **risk diagnosis is correct** — the real danger is losing a message that should have been published —
but the delivery **label stayed wrong after two corrections**. This was the main unresolved terminology
misconception at the end of the session. The complete model, taught directly (this is Tech Lead synthesis,
not a student conclusion):

```text
No retry under uncertainty -> 0 or 1 delivery -> AT-MOST-ONCE  -> may LOSE the message.
Retry under uncertainty    -> 1 or more       -> AT-LEAST-ONCE -> may DUPLICATE.
Exactly-once is NOT obtained by disabling retries.
Practical business correctness = at-least-once publication + stable event id + idempotent consumer.
```

---

# Engineering Trade-offs

## Trade-off 1: Separate commits vs one transaction

| Aspect | Separate commits | One transaction |
| --- | --- | --- |
| Code shape | Simpler, statement-local | Must handle error + zero-row control flow |
| Crash behaviour | Partial business facts survive | All-or-nothing |
| Coherence | Day32 anomalies appear | The anomaly source is removed |
| Requirement | None | Every writer must participate |

## Trade-off 2: One long transaction vs two short transactions

| Aspect | One long transaction | Two short transactions |
| --- | --- | --- |
| Looks like | One tidy workflow | Two units + an external gap |
| Cost | Holds connection, locks, old snapshot for minutes | Healthy resource lifecycle |
| External work | Still cannot be rolled back | Explicit un-rollbackable boundary |
| New problem | Pool/vacuum/lock pressure | An unknown-outcome gap needing reconciliation/idempotency |

Two short transactions win — the long one pays every cost and still cannot undo the Provider call.

## Trade-off 3: At-most-once vs at-least-once publication

| Aspect | At-most-once (no retry) | At-least-once (retry) |
| --- | --- | --- |
| Duplicates | Fewer | Expected |
| Loss | **Can silently lose messages** | Never silently lost |
| Consumer burden | None | Must be idempotent on `outbox_event_id` |

Choose at-least-once plus an idempotent consumer. Silent loss is almost always worse than a handled
duplicate.

## Trade-off 4: Application contract vs centralized enforcement

| Aspect | Application/repository boundary | Restricted permissions / DB function |
| --- | --- | --- |
| Simplicity | Straightforward, current scope | More operational/schema/permission complexity |
| Coverage | Legacy/bypass writers can violate it | Stronger centralization |
| Day | Day33 | Future connection (Day37 roles), not now |

---

# Hands-on Exercises

## Exercise 1: Diagnose the Job-without-Outbox stall (Beginner)

Given a queued Job with no Outbox row after separate commits, explain why it never advances and which single
change fixes it. State the invariant in one line.

Verification: your answer names the Relay scanning `outbox_events` and the acceptance-time rule (create the
Job together with its dispatch Outbox intent), not a permanent Job-to-Outbox equivalence.

## Exercise 2: Predict the constraint-failure rollback (Beginner)

Job INSERT succeeds, Outbox INSERT violates a constraint in the same transaction, ROLLBACK. Does the Job
remain? Explain using "uncommitted vs committed."

Verification: Job does not remain; it was uncommitted in the rolled-back transaction.

## Exercise 3: Place the 202 (Beginner)

Decide whether `202 + job_id` is returned before or after COMMIT, and describe the lost-response case.

Verification: after COMMIT; the lost response is handled by idempotency-key lookup, not the transaction.

## Exercise 4: Gate the zero-row transition (Intermediate)

Write the guarded `queued -> running` UPDATE with RETURNING, then state exactly what the application does on
1 row vs 0 rows, and what corrupts if it does not gate.

Verification: 0 rows -> ROLLBACK/stop; ungated -> duplicate Attempt/Event.

## Exercise 5: Split the eight-minute call (Intermediate)

Restructure a single long transaction into start / external / complete, and list two concrete costs of the
long form beyond "it is slow."

Verification: names connection hold + lock/old-snapshot, and the un-rollbackable Provider call.

## Exercise 6: State the proof boundary (Advanced)

After Provider success but before the Completion transaction, list what PostgreSQL can and cannot prove, and
why blind requeue is unsafe.

Verification: proves start facts + a recorded `provider_request_id`; cannot prove the external result;
requeue may repeat cost.

## Exercise 7: Explain `published_at` (Advanced)

Enumerate the meanings of `published_at IS NULL` and `IS NOT NULL`, and the three delivery checkpoints.

Verification: NULL = never/in-flight/crashed-before-write-back; NOT NULL = Relay recorded publish only.

## Exercise 8: Fix the delivery label (Advanced)

Correct the claim "disabling retries gives exactly-once," and give the practical correctness model.

Verification: disabling retry = at-most-once (may lose); use at-least-once + idempotent consumer.

## Exercise 9: Legacy-writer coherence (Advanced)

A new pack ships while old Workers still commit separately. Argue why the system is not yet atomic and list
the operational steps to converge.

Verification: the pack binds only participants; drain old Workers, centralize writes, monitor Day32 queries.

---

# Relevant Framework Connections

## PostgreSQL

`BEGIN` / `COMMIT` / `ROLLBACK` as one business boundary; constraint failures that fail a transaction;
guarded `UPDATE ... RETURNING` with an application affected-row gate; short transactions; durable Outbox
rows. Concurrency mechanics (`FOR UPDATE`, `SKIP LOCKED`, MVCC anomalies, deadlocks) are deliberately
**Day34** and appear nowhere in the artifact.

## FastAPI

Return `202 + job_id` only after the Accept `COMMIT`. A lost HTTP/COMMIT response is resolved by an
idempotency-key lookup, never by blind replay. `tenant_id` remains a server-authenticated predicate on every
guarded write.

## Celery / Workers

Start and completion facts each use one short transaction. Old Workers that commit separately remain unsafe
until drained. `published_at` does not prove Celery business processing.

## Redis / Queue

External publication is not part of any PostgreSQL COMMIT. The Relay-crash gap yields at-least-once
retransmission, so the consumer must be idempotent on `outbox_event_id`.

## AI Provider

An eight-minute call must never hold a DB transaction. The Provider request and its cost cannot be rolled
back, so they sit in the external phase between the two short transactions.

## Object Storage

Bytes written before the Completion transaction may be orphaned if that transaction rolls back. Reconcile, or
perform a separately audited compensation — database rollback is not Object Storage rollback.

## Validation evidence for these exercises

State the level, never the level above it.

```text
1. Conceptual / manual production reasoning        DONE (in class)
   The 14 failure scenarios, the external boundary, and the delivery model.

2. Static scope check of the local transaction draft   DONE (in class)
   A local classroom draft (day33/day33_transactional_write_pack.sql) was reviewed
   for scope. This is teaching-session input, NOT the repository artifact.

3. Reduced-schema PostgreSQL 14.18 runtime         DONE (listed tests ONLY)
   A disposable cluster ran a REDUCED validation schema and PASSED:
     Test 1: Job + Outbox committed together
     Test 2: duplicate Outbox id -> unique_violation rolled the preceding Job insert back
     Test 3: running Job + Attempt + job_started Event committed coherently
     Test 4: duplicate Artifact key -> unique_violation rolled Attempt-finish + Job-success
             + success Event + success Outbox back (the classroom draft wrote an
             unconditional success Outbox; the final artifact makes that row conditional)
     Test 5: Outbox published_at checkpoint changed from NULL to a timestamp
     Final marker: DAY33_REDUCED_RUNTIME_VALIDATION_PASS
   An earlier restricted-sandbox bootstrap failed at cluster start with
     FATAL: could not create shared memory segment: Operation not permitted / shmget
   which is ENVIRONMENT evidence, not a SQL failure. Both temporary clusters were deleted.
   Test 5 validated ONLY PostgreSQL's NULL-to-timestamp checkpoint; it did NOT validate
   Redis publication.

4. Final repository artifact static review          DONE (repository update + review round)
   005_...sql uses the Day31 columns exactly (no schema change); three short transactions;
   guarded UPDATE ... RETURNING with explicit control-flow contracts; Attempt-finish guarded
   by finished_at IS NULL; attempt_id documented as the pre-call recovery anchor and
   provider_request_id as returned/persisted-in-C only; conditional (commented) job.succeeded
   Outbox with a stable-ids-only payload rule; external phase outside any transaction;
   no FOR UPDATE/SKIP LOCKED/index/EXPLAIN/migration/ORM; no credentials.

5. Final repository artifact PostgreSQL runtime      NOT RUN
   No psql/PostgreSQL server was available during the repository update or this review round.
   The review-round guards (finished_at IS NULL, conditional Outbox, Provider-identity split)
   are static-only. The reduced classroom run is NOT reused as proof of this file.

6. Application / external integration                NOT RUN
   No FastAPI affected-row + COMMIT-unknown path, Provider, Object Storage, Redis,
   Celery, real Relay crash/restart, or consumer idempotency test was executed.

7. Concurrency / production validation               NOT RUN / OUT OF SCOPE
   Day34 concurrent claims, MVCC, locks, SKIP LOCKED; performance, RLS, backups, HA,
   deployment.
```

---

# AI Backend Connections

## Connection 1: Durable acceptance needs Job + intent

A `202` that promises processing requires both the Job row and the publication intent, committed together —
not a Job row alone (Concept 1).

## Connection 2: Long model calls force an external window

An eight-minute Provider call cannot live inside a transaction, so there is always a gap between the two
short transactions where the external outcome is momentarily unknown (Concepts 7, 8).

## Connection 3: Duplicate Provider work is a cost problem

Because a requeue can repeat a paid Provider call, stable `provider_request_id`, a deterministic object key,
and reconciliation are correctness *and* cost controls (Concept 8, 12).

## Connection 4: Completion is one atomic bundle

Attempt finish, guarded Job terminal state, Result Artifact reference, success Event, and Outbox intent
commit together or not at all (Concept 12).

## Connection 5: The Outbox bounds what you can claim

It prevents lost publication intent but proves nothing about Queue delivery or consumer success; stable
`outbox_event_id` plus an idempotent consumer is what makes at-least-once safe (Concepts 9-11).

---

# English Interview

Three questions were answered aloud. The student's real words are preserved verbatim, including grammar,
because the correction targets the content.

## Beginner: what is a transaction, and why Job + Outbox together?

Student answer (actual):

> "a database transaction is a database atomicity operation.beacuse job and outbox event occure same time,both of them get success together or both of them get faild"

Correction: the all-or-nothing direction is right. Fix "occur at the same time": SQL executes in sequence;
the records share one atomic **commit** boundary rather than happening simultaneously.

Strong spoken answer:

> "A database transaction groups related operations into one atomic unit. Creating the Job and its Outbox
> event must happen in the same transaction because they represent one business commitment. Either both
> records are committed, or neither is. This prevents a durable queued Job from existing without a durable
> publication intent."

## Intermediate: why not hold a transaction across an eight-minute Provider call?

Student answer (actual):

> "beacause postgresql can't control extra provider job. put the use of AI Provider in two short transaction"

Correction: right direction. Fix "extra provider" to "external provider"; the call belongs *between*, not
inside, the two transactions. Add the connection, lock, and old-snapshot costs.

Strong spoken answer:

> "PostgreSQL cannot include an external AI Provider call in its transaction, so a rollback cannot undo the
> request or its cost. Holding the transaction open for eight minutes would also pin a database connection
> and potentially hold locks and an old snapshot. I would use one short transaction to record the claim,
> Attempt, and start Event, commit it, call the Provider outside any transaction, and then use a second short
> transaction for the completion state, result reference, Event, and Outbox intent."

## Senior: Relay publishes, then crashes before `published_at` — what now?

Student answer (actual):

> "the outbox relay would retry published same message.we need to add outbox_event_id that it is a idempotent key avoid relay publish twice"

Correction: the first half is correct. The mechanism in the second half is wrong — `outbox_event_id` does
**not** avoid Relay retransmission. It lets the consumer recognize the repeated event and avoid repeated
business processing.

Strong spoken answer:

> "After restart the Relay still sees `published_at` as null, so it may publish the same message again — that
> is expected under at-least-once delivery. The Relay reuses the same stable `outbox_event_id`, and the
> consumer treats that id as an idempotency key. The id does not prevent duplicate publication; it prevents
> duplicate business processing. And `published_at` proves only that the Relay recorded a publish, not that
> the consumer completed its work."

Key vocabulary: `transaction boundary`, `atomic commitment`, `guarded transition`, `affected-row gate`,
`external side-effect boundary`, `Transactional Outbox`, `publication intent`, `at-least-once`,
`idempotency key`, `reconciliation`.

---

# Mental Model Summary

```text
1. A transaction is ONE business commitment: all related DB facts commit or none do.
2. ROLLBACK undoes the current transaction only — never a prior COMMIT.
3. Return 202 AFTER the Accept COMMIT; a lost response is resolved by idempotency-key lookup.
4. "The Worker started" is three facts (state + Attempt + Event) — commit them together.
5. Zero affected rows is a NORMAL result; the application must gate on it. A SQL error is not.
6. ACID protects data shape, not business logic; Consistency != correct transition.
7. Never hold a transaction across an eight-minute Provider call — split into two short ones.
8. A recorded provider_request_id proves you asked, not what happened.
9. The Outbox is durable intent; the Relay does not delete it or reset published_at to NULL.
10. published_at NULL = never/in-flight/crashed-before-write-back; NOT NULL = Relay recorded a publish only.
11. at-most-once loses; at-least-once duplicates; exactly-once is NOT disabling retries.
12. External effects (Provider cost, Object Storage bytes) survive DB rollback — reconcile them.
13. A lost COMMIT response is UNKNOWN — read stable ids, do not assume rollback.
14. A transaction pack is a write-path contract, not a schema guarantee.
```

Student final Chinese synthesis (verbatim):

> "短的事务应该保证数据库操作的原子性与完整性。因为数据库事务是控制外部的供应商的业务的。所以先用短事物开启业务，中间进行第三方供应商调用生成了结果后，再使用短事务写入结果。outbox的机制是保障至少发送一次，当published_at为null时，relay就会自动获取行并传递消息到queue。保障出现故障没有调用时，重启后能再继续发送，如果设计为exactly-once，恰好一次，如果出现故障就不会进行重新发送"

Targeted corrections (Tech Lead):

1. Correct: short transactions protect atomic database operations, and the start -> external -> complete
   structure is right.
2. Wrong phrase: PostgreSQL transactions **cannot** — not can — control the external Provider.
3. Incomplete: `published_at IS NULL` may also mean already published before a write-back crash.
4. Wrong label: disabling retry is **at-most-once**, not exactly-once.

Final durable interpretation (Tech Lead synthesis, explicitly not a student quote):

```text
A transaction protects one complete PostgreSQL business commitment: all related database facts commit
together or roll back together. It does not include Provider, Object Storage, Redis, Celery, or other
external side effects. Long external work therefore sits between two short database transactions and uses
stable identifiers, checkpoints, idempotency, and reconciliation for unknown outcomes.

The Outbox prevents publication intent from being lost, but Relay publish and the PostgreSQL write-back are
not one atomic operation. A crash in that gap can cause retransmission. The reliable model is at-least-once
publication with the same stable outbox_event_id and an idempotent consumer. Disabling retry produces
at-most-once delivery and risks losing messages; it is not exactly-once.
```

---

# Today's Takeaway

Day32 taught you to *see* partial facts. Day33 teaches you to stop producing them: group the related
database writes into one transaction so they commit together or not at all, and return the `202` only once
that commit is durable.

The harder half is the boundary. PostgreSQL can roll back only its own rows, so the AI Provider call and the
Object Storage write live **outside** the transaction, between one short Start transaction and one short
Complete transaction. Across that gap the external outcome can be momentarily unknown — which is why stable
identifiers, checkpoints, idempotency, and reconciliation are not optional extras but the design itself.

And two guardrails carry into every future lesson. Zero affected rows is a normal result the application must
interpret, not a transaction failure. And the Outbox gives you at-least-once publication, not exactly-once —
so the consumer must be idempotent on a stable `outbox_event_id`. Atomicity prevents partial database facts;
idempotency makes uncertain retries safe. You need both.

---

# Before Next Lesson Checklist

- [ ] I can state the Accept invariant: at acceptance the durable Job is created with its durable dispatch Outbox intent (creation-time, not a permanent Job-to-Outbox equivalence).
- [ ] I can explain why `ROLLBACK` removes an uncommitted Job but cannot undo a prior COMMIT.
- [ ] I can justify returning `202` after COMMIT and handle the lost-response case with idempotency.
- [ ] I can write the guarded `queued -> running` transition + Attempt + Event as one transaction.
- [ ] I can explain why zero affected rows does not abort a transaction and what corrupts if it is not gated.
- [ ] I can restructure a long transaction into two short ones around the external phase, and name the costs.
- [ ] I can state what PostgreSQL can and cannot prove after Provider success.
- [ ] I can explain the Outbox lifecycle and why the Relay does not "take" the row.
- [ ] I can enumerate the meanings of `published_at` and the three delivery checkpoints.
- [ ] I can correct "disabling retries gives exactly-once" and give the practical model.
- [ ] I can explain why the transaction pack does not protect legacy separate-commit writers.

Preparation for Day34 (Concurrency Control, MVCC, and Worker Claims):

- [ ] Re-read `projects/ai-backend-data-layer/sql/005_postgresql_transactions_and_atomic_state_changes.sql`
      and note where the Relay checkpoint says concurrent claiming is deferred.
- [ ] Note that Day33 assumes one writer at a time; Day34 adds concurrent sessions.
- [ ] Be ready to explain why a lock cannot repair a wrongly defined business transaction.
- [ ] Keep `FOR UPDATE`, `SKIP LOCKED`, and MVCC anomalies out of scope until Day34.
