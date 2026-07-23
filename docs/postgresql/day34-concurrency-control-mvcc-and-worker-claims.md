# Lesson 34 — Concurrency Control, MVCC, and Worker Claims

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day33 — PostgreSQL Transactions and Atomic State Changes

Previous Lesson: [Day33 — PostgreSQL Transactions and Atomic State Changes](day33-postgresql-transactions-and-atomic-state-changes.md)

Next Lesson: [Day35 — PostgreSQL Indexes and Query Planning](day35-postgresql-indexes-and-query-planning.md)

Engineering Artifact: The Day34 concurrency claim pack (`sql/006_concurrency_control_mvcc_and_worker_claims.sql`) — an active `FOR UPDATE SKIP LOCKED` claim transaction wrapping the Day33 Start write, plus a fully commented, conceptual lease state machine — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

PostgreSQL Cheat Sheet: [cheat_sheets/postgresql.md](../../cheat_sheets/postgresql.md)

PostgreSQL Interview: [interview/postgresql.md](../../interview/postgresql.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 100-130 minutes
Hands-on claim/lock authoring + disposable-PostgreSQL concurrency checks: 100-130 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Explain why a plain `SELECT` is **candidate visibility, not ownership**, and why two Read Committed sessions can both see the same queued Job.
2. Use `SELECT ... FOR UPDATE` for a transaction-local row lock, and `FOR UPDATE SKIP LOCKED` to build a Worker claim that spreads Workers across available rows instead of convoying on the queue head.
3. Assemble the claim transaction: reserve one queued candidate, reuse the Day33 guarded `queued -> running` write, and gate the Attempt/Event inserts on the affected-row result — all before the Provider call, which stays outside the transaction.
4. State honestly what `SKIP LOCKED` does **not** give you: strict FIFO, a complete snapshot, or a guarantee every row is eventually served.
5. Distinguish a **database row lock** (transaction-local exclusion, gone at COMMIT) from a **committed application lease** (recoverable ownership with an owner, token, and expiry) — and know that the lease columns are a Day36 migration, not in today's schema.
6. Explain that lease expiry is a **takeover condition, not proof of Worker death**, that takeover writes a new token while expiry alone does not, and that completion must guard the current token + running status + unexpired lease.
7. Keep the `lease_token` (one ownership epoch) separate from the **stable Provider idempotency key** (same logical external operation), and explain why conflating them can repeat charges.
8. Read MVCC snapshots correctly (Read Committed vs Repeatable Read vs Serializable), name the dirty-read / non-repeatable-read / phantom / lost-update boundaries, and explain why stronger isolation does not partition work.
9. Diagnose a reverse-order deadlock (`40P01`), prevent it with a consistent lock order, bound waits with `lock_timeout` (`55P03`), and retry `40P01`/`40001` from the **application** with a finite budget — while UNIQUE/idempotency guards still stop duplicate durable facts.

---

# Why This Matters

Day33 gave you one correct business commitment — but it assumed a single writer. Production has hundreds of Workers polling the same queue. The moment two of them read the same queued Job, the Day33 transaction is no longer the whole story: you need a way to decide **who owns the work**, a way to **recover ownership** when a Worker pauses or dies, and a way to survive the **races and deadlocks** that concurrency creates.

The trap is thinking a read is a claim. It is not. Visibility (MVCC) and ownership (locks, then committed leases) are different mechanisms, and confusing them is how you get duplicate Attempts, duplicate Provider charges, and Jobs that two Workers both "own." The second trap is thinking a released lock, or an expired lease, tells you a Worker is dead. It does not — and acting on that belief repeats expensive external work.

This lesson keeps the database boundary honest: PostgreSQL can assign and recover ownership of its own rows, but it cannot revoke a Provider call, and a lock is not a liveness check. Everything hard about many-Worker AI backends lives in that gap.

---

# Roadmap Position

```text
Day31  relational ownership, keys, CHECK/UNIQUE, tenant-aware FKs
Day32  operational EVIDENCE of partial/missing facts
Day33  the atomic write boundary + the external-side-effect boundary (one writer)
Day34  concurrent writers + recoverable ownership   <-- you are here
Day35  measured indexes for the claim / stale-lease / Outbox access paths
Day36  safe schema evolution — where the lease columns actually get added
Day37  lock/deadlock/timeout monitoring, connection limits, operations
Day41  the stronger cross-system fencing-token boundary
```

Day34 sits between "the write is correct" (Day33) and "the write is fast" (Day35). A lock cannot repair a wrongly defined Day33 boundary, so the boundary comes first; an index cannot be chosen until Day34 fixes the real claim predicates and ordering, so measurement comes after.

---

# Lesson Map

```text
1. Visibility != ownership          -> two sessions see the same queued Job
2. FOR UPDATE                       -> a transaction-local row lock; conflicts wait
3. FOR UPDATE SKIP LOCKED           -> skip locked rows, claim the next available
4. The claim transaction            -> reserve + Day33 Start write + gate + COMMIT
5. SKIP LOCKED weakens fairness      -> not FIFO, starvation is possible
6. A released lock != liveness       -> committed facts persist; blind reclaim duplicates
7. Row lock vs application lease      -> transaction-local vs committed ownership
8. Lease expiry != death             -> takeover writes a new token; guard completion
9. Lease policy                      -> duration from heartbeat, not Provider duration
10. lease_token != Provider key      -> ownership epoch vs stable external identity
11. Pessimistic vs optimistic         -> SKIP LOCKED spreads; optimistic can storm
12. MVCC snapshots                   -> 100 then 101; phantom/non-repeatable/dirty/lost
13. Isolation levels                 -> RC vs RR (40001) vs Serializable; not partitioning
14. Deadlock                         -> circular wait, 40P01, one victim
15. Consistent lock order            -> prevents the cycle
16. Prevent / detect / bound / retry -> order + detector + timeouts + app retry
```

---

# Core Mental Model

```text
VISIBILITY (MVCC snapshot) != OWNERSHIP (lock, then committed lease).
    A SELECT shows candidates. A lock reserves a row for one transaction.
    A committed lease makes ownership survive COMMIT and be recoverable.

CLAIM = FOR UPDATE SKIP LOCKED (reserve the next AVAILABLE row)
        + the Day33 guarded queued->running write, gated on affected rows
        + COMMIT, then call the Provider OUTSIDE the transaction.

A released lock proves nothing about Worker liveness.
An expired lease is a TAKEOVER CONDITION, not proof of death; takeover writes a
    NEW token; completion guards token + running + unexpired lease.

lease_token (ownership epoch, changes on takeover)
    != Provider idempotency key (stable per logical external operation).

Concurrency failures (40P01 deadlock / 40001 serialization) are aborted by
    PostgreSQL; the APPLICATION retries the whole transaction with a finite budget.
    UNIQUE/idempotency constraints still stop duplicate durable facts.
```

---

# Main Concepts

## Concept 1: Visibility Is Not Ownership

Tech Lead Question:

Two independent Workers run the same `SELECT ... WHERE job_status = 'queued' LIMIT 1` under Read Committed
and both get job-A. Have both claimed it?

Student Answer:

> "是的，因为两个work独立执行，所以都认领了"

Tech Lead Review:

This is the natural first instinct, and it is the misconception the whole lesson corrects. Both Workers
**selected the same candidate** — but a `SELECT` is *visibility*, not *ownership*. The committed queued row
is visible in each session's snapshot; neither has reserved it.

What saves you is the Day33 guarded UPDATE: only one legal `queued -> running` transition can succeed, and
the losers return zero rows. What breaks you is skipping that gate — then both Workers write an Attempt and
an Event for the same Job. To make ownership **explicit** (not just a lucky race on the UPDATE), you take a
row lock.

Engineering Thinking:

Seeing a row and owning it are different facts. Never treat a candidate `SELECT` as a claim.

## Concept 2: `SELECT ... FOR UPDATE`

Tech Lead Question:

Session A holds a lock on job-A. Session B runs a plain `SELECT ... FOR UPDATE` that also targets job-A.
What happens?

Student Answer:

> "会等待"

Tech Lead Review:

Correct. `FOR UPDATE` requests a row lock, and a conflicting locking read/write **waits** until the holder
commits, rolls back, or loses its session. Two clarifications the class established: ordinary MVCC reads are
**not** blocked (a plain `SELECT` without `FOR UPDATE` still sees the row), and the lock is
**transaction-local** — it lives only until COMMIT/ROLLBACK and must never span the eight-minute Provider
call.

Engineering Thinking:

A row lock is a short reservation, not a durable owner. Hold it only across database work you can finish
fast.

## Concept 3: `FOR UPDATE SKIP LOCKED`

Tech Lead Question:

Same setup — job-A is locked by Session A. Session B runs the ordered queued query with `FOR UPDATE SKIP
LOCKED`. What does it get?

Student Answer:

> "会跳过当前这个锁"

Tech Lead Review:

Correct — it **skips** the locked row and takes the next available one (job-B). This is what makes a queue
claim work: instead of every Worker convoying on the locked queue head, `SKIP LOCKED` distributes them
across unlocked rows. It is the right tool for a queue-like *claim*, and the wrong tool for a complete
reporting snapshot (it deliberately omits locked rows).

Engineering Thinking:

`SKIP LOCKED` trades a complete view for forward progress. That is exactly the trade a claim wants and a
report does not.

## Concept 4: The Claim Transaction

Tech Lead Teaching (assembled progressively in class):

```text
BEGIN
  -> SELECT one ELIGIBLE queued candidate FOR UPDATE SKIP LOCKED
       eligibility = tenant_id + job_status = 'queued' + cancel_requested = false, ordered
  -> guarded queued->running UPDATE ... RETURNING     (Day33 write, unchanged)
       re-checks the SAME eligibility (queued AND cancel_requested = false)
  -> only on the 1-row path: INSERT Attempt + job_started Event
COMMIT
  -> THEN call the Provider, OUTSIDE any transaction
```

The claim reuses the **exact** Day33 Start transaction; Day34 only adds the reservation in front of it. The
affected-row gate is unchanged: zero rows from the UPDATE means `transition_not_applied` — roll back and
stop, never insert the Attempt/Event. The lock is released at COMMIT, well before the long Provider call.

**Eligibility, not just status.** The Day31 `app.jobs` also carries
`cancel_requested boolean NOT NULL DEFAULT false`. A Job whose cancellation was already committed can still
be `job_status = 'queued'` for a moment; claiming it would move it to `running`, write an Attempt/Event, and
incur an unnecessary Provider cost. So both database boundaries — the `FOR UPDATE SKIP LOCKED` candidate
`SELECT` **and** the guarded `UPDATE` — filter `AND cancel_requested = false`. The `UPDATE` repeats it as a
**defensive** final state-transition boundary: it keeps the full eligibility on a direct `UPDATE`, on the
optimistic path, and on any future refactor that splits the `SELECT` from the `UPDATE`.

What it does **not** mean is a race window. Because the `FOR UPDATE SKIP LOCKED` step already holds this
row's exclusive lock until the claim transaction commits, another transaction **cannot** commit a same-row
`cancel_requested` change *between* the locking `SELECT` and the `UPDATE`. The three real orderings are:

```text
cancel commits FIRST            -> the candidate SELECT's predicate excludes the Job; it is never claimed.
cancel currently HOLDS the lock -> SKIP LOCKED skips that row and keeps scanning; it MAY return another
                                   eligible Job, or 0 rows if none is available (then back off, no waiting).
this claim locks FIRST          -> the cancel transaction WAITS; the claim finishes queued->running and
                                   COMMITs, then the cancel path re-evaluates the current state under its
                                   OWN guarded cancellation policy (Day34 does not define that UPDATE).
```

(This is one eligibility predicate, not a cancellation state machine — that is future work.)

Engineering Thinking:

Concurrency is a wrapper around a correct write, not a replacement for it. Reserve, write atomically,
commit, then leave the transaction to do slow external work.

## Concept 5: `SKIP LOCKED` Weakens Fairness

Tech Lead Question:

With `SKIP LOCKED` and `ORDER BY created_at`, is strict FIFO guaranteed? Can a Job starve?

Student Answer:

> "不会，如果最终其他的job都被work处理完了，job A可能最终没有work来处理了"

Tech Lead Review:

Right instinct. `ORDER BY` sorts only the rows **currently available** — a locked row is excluded from that
sort, so strict FIFO is **not** guaranteed, and a row that is repeatedly or long held can be passed over
and **starve**. The mitigations are operational, not a stronger lock: keep claim transactions short; monitor
oldest queued age, lock waits, and expired leases; run a recovery sweeper or an explicit fairness policy.
(Proving the access paths with indexes is Day35.)

Engineering Thinking:

`SKIP LOCKED` optimizes throughput, not fairness. If FIFO matters, you must measure and enforce it, not
assume the queue order provides it.

## Concept 6: A Released Lock Is Not Liveness Evidence

Tech Lead Question:

After the Start COMMIT the row lock is gone. A second Worker sees no lock. Can it reclaim the Job just
because nothing is locked?

Student Answer:

> "不能，因为数据库已经存在之前work的持久化状态了，重新认领会重复写入"

Tech Lead Review:

Exactly right. The lock was transaction-local and vanished at COMMIT, but the Job/Attempt/Event are
**durable**. A missing lock says nothing about whether the first Worker is alive, paused, or dead. Blind
reclaim duplicates the Attempt, the Event, and — worse — the Provider cost and result work. To reclaim
safely you need *committed* ownership you can reason about: a lease.

Engineering Thinking:

Absence of a lock is not absence of an owner. Recoverable ownership must be a committed fact, not the side
effect of a transaction still being open.

## Concept 7: Row Lock vs Application Lease

Tech Lead Teaching:

```text
Database row lock      = transaction-local EXCLUSION. Gone at COMMIT/ROLLBACK.
                         Great for the short claim; useless for recovery after COMMIT.
Application lease      = COMMITTED execution ownership: an owner, a token, and an expiry.
                         Survives COMMIT, so a paused/dead Worker's Job can be taken over.
```

The conceptual fields are `claim_owner`, `lease_token`, and `lease_expires_at`. **They do not exist in the
Day31 schema and were not added or run.** Introducing them is a Day36 expand/backfill/validate/switch/
contract migration. In the `006` artifact they appear only in a commented, conceptual appendix — never as
active SQL against the current schema.

Engineering Thinking:

Choose the ownership mechanism by lifetime. Within one transaction, a lock is enough. Across the Provider
call, you need a committed lease.

## Concept 8: Lease Expiry Is a Takeover Condition, Not Death

Tech Lead Question:

Worker 1's lease expires. Is Worker 1 dead?

Student Answer:

> "不能，因为work1虽然lease过期，但是不代表work1的死亡证明。"

Tech Lead Review:

Correct. Expiry means "ownership **may** be taken over," not "the old Worker died" — a paused or
network-partitioned Worker can resume after expiry. Takeover **writes a new `lease_token`**; expiry alone
does not mutate the token, it only makes the old ownership invalid through the time predicate
(`lease_expires_at <= now()`). Completion must therefore guard the **current token + running status +
unexpired lease**; a stale token returns zero rows and rolls back the entire Completion transaction.

Engineering Thinking:

Expiry is permission to take over, not a death certificate. Two mechanisms cooperate: takeover writes the
new token, and an expiry predicate independently invalidates a late completion.

## Concept 9: Lease Duration Is a Policy

Tech Lead Question:

An eight-minute Job sends heartbeats that can pause up to ~45 seconds. Do you set a 30-second lease or a
two-minute lease?

Student Answer:

> "选择2分钟，避免短lease造成错误接管"

Tech Lead Review:

Correct, and for the right reason. Lease duration is derived from the **heartbeat interval and observed
pauses**, not the whole Provider duration. A 30-second lease would expire during a normal 45-second pause
and trigger a **false takeover** of a healthy Worker; two minutes absorbs the pause. The trade-off is
explicit:

```text
short lease -> faster TRUE-failure recovery, but MORE false takeover
long lease  -> fewer false takeovers, but SLOWER recovery
```

Renewal must be guarded by `job_id`, running status, the current token, and an unexpired lease, and should
use PostgreSQL `now()` rather than inconsistent Worker clocks.

Engineering Thinking:

A lease is tuned to how often you can prove you are alive, not to how long the work takes.

## Concept 10: `lease_token` Is Not the Provider Idempotency Key

Tech Lead Question:

On takeover you mint a new `lease_token`. Should you send that new token to the Provider as its idempotency
key?

Student Answer:

> "不能，要把lease_token与幂等键进行分别，因为每次接管都会生成新的token这样幂等键就不能保障防止重复调用provider"

Tech Lead Review:

Exactly right. They are different identities:

```text
lease_token                 -> one OWNERSHIP EPOCH; CHANGES on every takeover
Provider idempotency key    -> the SAME logical external operation; STABLE across takeover
                               (derive it from the durable attempt_id and actually SEND it
                                to a Provider that supports idempotency/lookup)
```

Using each new lease token as a new Provider key **defeats** idempotency — the Provider sees a "new"
request and can charge again. And if the Provider offers no idempotency/lookup mechanism, the lease cannot
make the external retry safe: isolate and reconcile.

Engineering Thinking:

Ownership changes hands; the external operation does not. Give each its own identifier and never cross them.

## Concept 11: Pessimistic vs Optimistic Concurrency

Tech Lead Question:

100 Workers, 10,000 queued Jobs, high contention. Pessimistic `FOR UPDATE SKIP LOCKED` or optimistic
expected-status guard?

Student Answer (initial):

> "乐观的状态/version guard，如果都使用FOR UPDATE SKIP LOCKED，work会跳过锁去寻找下一个job"

Tech Lead Review:

This answer is backwards, and the reason it is backwards is the key insight. The student noticed that
`SKIP LOCKED` makes Workers "skip the lock and find the next Job" — but described that as a drawback of
pessimistic locking. It is precisely the **advantage**: Workers spread across unlocked rows.

```text
Pessimistic (FOR UPDATE SKIP LOCKED): reserve a candidate; Workers SPREAD.
    -> best fit for a HIGH-contention queue.
Optimistic (expected-status/version guard): try the write; conflicts return 0 rows,
    re-read and retry. Great for LOWER-contention edits.
    -> with 100 Workers all targeting the OLDEST Job: one success, 99 failed retries
       (a retry storm). More isolation is NOT automatic work partitioning.
```

Engineering Thinking:

Match the concurrency style to the contention. Pessimistic reservation spreads a crowd; optimistic retry
shines when collisions are rare.

## Concept 12: MVCC Snapshots

Tech Lead Question:

Under Read Committed a transaction counts 100 queued Jobs; another session inserts and commits one; the
next statement counts 101. Is atomicity broken?

Student Answer:

> "是该隔离级别允许的行为，因为Transaction B提交以后已经变成持久化数据。"

Tech Lead Review:

The conclusion is right — this is **allowed isolation behavior**, not broken atomicity — but the *reason*
needs a correction. A committed row being durable is not by itself why the later statement sees it. Under
**Read Committed, each statement takes a new snapshot**, so the second `COUNT` sees the newly committed row.
The vocabulary:

```text
phantom              -> a changing PREDICATE result (100 then 101 rows)
non-repeatable read  -> a changed VALUE for the SAME row re-read in one transaction
dirty read           -> seeing UNCOMMITTED work; PostgreSQL does NOT allow this
lost update          -> stale read-compute-write overwrites concurrent work
```

Engineering Thinking:

Isolation defines *what a snapshot may change between statements*. A phantom under Read Committed is the
level working as designed, not a bug.

## Concept 13: Isolation Levels

Tech Lead Question:

Two Workers open Repeatable Read transactions. Without any lock, do they automatically pick different Jobs?

Student Answer:

> "不会，因为表示两个work看到的是同一个快照，没有进行行锁，不会自动的领取不同job"

Tech Lead Review:

Correct. Each transaction has its **own stable snapshot** (both can contain the same queued row), and a
stable snapshot does **not** allocate work. The isolation map the class established:

```text
READ UNCOMMITTED -> PostgreSQL treats it as READ COMMITTED
READ COMMITTED   -> a NEW snapshot per statement
REPEATABLE READ  -> one STABLE transaction snapshot; a conflicting writer may abort with 40001
SERIALIZABLE     -> outcome equivalent to some serial order; also needs whole-transaction retry on 40001
```

Stronger isolation prevents anomalies; it does **not** partition Jobs across Workers. Explicit locks/guards
still define ownership.

Engineering Thinking:

Isolation is about the consistency of what you read, not about who gets which row. Ownership is always an
explicit decision.

## Concept 14: Deadlock

Tech Lead Question:

Transaction A locks job-A then requests job-B; Transaction B locks job-B then requests job-A. What does
PostgreSQL do?

Student Answer:

> "互相等待，应该设置超时时间"

Tech Lead Review:

The diagnosis (mutual waiting) is right; the remedy is incomplete. This is a **circular wait**, and
PostgreSQL **detects** it and aborts one victim with `SQLSTATE 40P01 (deadlock_detected)` — it does not let
both wait forever, and it does **not** automatically retry your transaction. A timeout is a useful *bound*,
but it is not the primary fix.

Engineering Thinking:

A timeout limits how long you suffer a cycle; it does not prevent the cycle. Detection handles the cycle you
failed to prevent.

## Concept 15: Consistent Lock Order

Tech Lead Question:

If every writer locks job-A before job-B, does the reverse-order deadlock still happen?

Student Answer:

> "不会，因为这个时候Transaction A先锁了job A，再去锁job B。而transaction B也是按照这个顺序，先锁A，而这个时候A被transaction A锁住了，所以就会等待"

Tech Lead Review:

Exactly right. With one agreed order, the second transaction **waits before it holds** the second row, so
there is waiting but no A-waits-for-B / B-waits-for-A cycle. The requirement is universal: every writer, old
Worker, maintenance script, and repair path must obey the **same** order (for example, ascending `job_id`).

Engineering Thinking:

A deadlock needs two transactions grabbing the same locks in opposite orders. Remove the opposite order and
you remove the deadlock.

## Concept 16: Prevent, Detect, Bound, Retry

Tech Lead Teaching:

```text
PREVENT  -> a consistent global lock order stops the common cycle.
DETECT   -> PostgreSQL aborts a cycle it could not prevent (40P01).
BOUND    -> lock_timeout / statement_timeout limit ordinary waits/work (55P03 on a
            lock-timeout cancel). Bounds do NOT replace ordering.
RETRY    -> the APPLICATION, not PostgreSQL, rolls back and retries the WHOLE
            transaction on 40P01 / 40001, with a FINITE budget, jitter/backoff, and
            idempotent identifiers. Never continue a failed transaction; never retry
            forever.
```

And the guard that outlives all of this: existing **UNIQUE / idempotency** constraints remain required.
Locks and leases decide *current ownership*; `UNIQUE (job_id, attempt_number)` and
`(tenant_id, idempotency_key)` prevent a retry from creating duplicate durable facts; a stable Provider
idempotency key protects a supporting external Provider. None substitutes for the others.

Observability worth emitting: transaction/operation name, `SQLSTATE`, retry count, lock-wait duration,
tenant/job identifiers, and deadlock frequency. The fuller production treatment is Day37.

Engineering Thinking:

Prevention, detection, bounds, and retry are four different jobs. Use all four, and keep the identity
constraints that make a retry safe.

---

# Common Misconceptions

## Mental Model Evolution (Day33 -> Day34)

```text
Starting system limitation (not a student quote):
    Day33 defines ONE correct atomic write, but assumes a single writer. With many Workers polling the
    same queue, nothing yet decides who OWNS a queued Job, nothing recovers ownership when a Worker pauses
    or dies, and concurrent lockers can deadlock.

Correction that Day34 makes:
    Reserve a candidate with FOR UPDATE SKIP LOCKED, run the unchanged Day33 guarded write, commit, then
    call the Provider outside the transaction. For ownership that survives COMMIT, add a committed lease
    (owner + token + expiry) -- a Day36 migration, conceptual today.

Boundaries Day34 cannot cross:
    A released lock is not a liveness check. An expired lease is a takeover condition, not a death
    certificate. A lease cannot revoke a Provider call or make an external retry safe. PostgreSQL does not
    auto-retry a deadlock; the application does, and UNIQUE/idempotency constraints still stop duplicates.

Net division of labour:
    Locks + leases decide OWNERSHIP; UNIQUE constraints decide IDENTITY; a stable Provider key protects the
    EXTERNAL operation. None replaces another, and none of them proves a Worker is alive.
```

## Misconception 1: Both Workers seeing the row means both claimed it

Wrong: two sessions that `SELECT` the same queued Job have both claimed it.

Right: both **selected the same candidate**. Visibility is not ownership. The Day33 guarded UPDATE still
lets only one legal transition succeed; explicit ownership comes from `FOR UPDATE` (transaction-local) and,
across COMMIT, a committed lease.

## Misconception 2: Optimistic concurrency is better because SKIP LOCKED "wastes" work by skipping

Wrong: `SKIP LOCKED` skipping locked rows is a drawback, so prefer optimistic selection.

Right: the skipping **is the point** — it spreads Workers across unlocked rows. Under high contention, pure
optimistic selection creates a retry storm (one winner, many failed retries) around the oldest Job.
Pessimistic `FOR UPDATE SKIP LOCKED` is the better fit for a contended queue.

## Misconception 3: A committed row is durable, so that is why a later statement sees it

Wrong: Read Committed shows the new row because it is now durable.

Right: durability is not the mechanism. **Read Committed takes a new snapshot per statement**, so the second
`COUNT` sees the newly committed row. Repeatable Read would keep a stable snapshot and not expose that later
commit to ordinary reads in the same transaction, even though it is durable.

## Misconception 4: A timeout fixes deadlocks

Wrong: set a timeout and deadlocks are handled.

Right: a timeout is a useful **bound**, but PostgreSQL already **detects** a circular wait and aborts one
victim with `40P01`. **Consistent lock order** is the primary prevention, and the **application** — not
PostgreSQL — retries the aborted transaction.

## Misconception 5: Separate Workers share one snapshot (from the English MVCC answer)

Wrong: "snapshot is same" — the Workers see the same snapshot.

Right: separate Workers have their **own** snapshots; both can *contain* the same committed row. Under Read
Committed, each statement obtains a **new** snapshot. Sharing a row in your snapshot is not sharing
ownership of it.

## Misconception 6: A fresh lease token is enough to stay correct (from the Senior English answer)

Wrong: minting a new `lease_token` on takeover covers correctness.

Right: a fresh token blocks **stale database completion**, but the **stable pre-call Provider idempotency
key** is what protects the same external operation. If the Provider lacks idempotency/lookup, reconciliation
is still required.

## Misconception 7: Lease expiry writes the token / revokes external work / makes retry safe

Wrong (from the final synthesis): expiry invalidates the token by changing it, and the lease handles the
Provider result.

Right: expiry makes ownership invalid through the **time predicate**; **takeover** writes the new token. A
row lock does not block every ordinary reader, only conflicting locking/writing operations. And Provider
idempotency cannot roll back an external result — it deduplicates/reconciles repeated requests **only** when
the Provider supports the contract.

---

# Engineering Trade-offs

## Trade-off 1: Pessimistic `FOR UPDATE SKIP LOCKED` vs optimistic guard

| Aspect | Pessimistic (SKIP LOCKED) | Optimistic (expected-status) |
| --- | --- | --- |
| Behaviour under contention | Workers spread across unlocked rows | Many collide on the same row |
| Best fit | High-contention queue claim | Low-contention edits |
| Failure mode | Starvation of a long-held row | Retry storm around a hot row |
| Cost | A held lock per claim | Wasted re-reads/retries |

## Trade-off 2: Short lease vs long lease

| Aspect | Short lease (e.g. 30s) | Long lease (e.g. 2min) |
| --- | --- | --- |
| True-failure recovery | Faster | Slower |
| False takeover | More (expires during normal pauses) | Fewer |
| Provider cost risk | Higher (repeat calls) | Lower |
| Tuned to | Heartbeat interval + observed pause | Heartbeat interval + observed pause |

## Trade-off 3: Row lock vs committed lease

| Aspect | Row lock (`FOR UPDATE`) | Committed lease |
| --- | --- | --- |
| Lifetime | Transaction-local; gone at COMMIT | Survives COMMIT |
| Recovery after COMMIT | None | Takeover on expiry |
| Cost | Free (existing schema) | New columns + Day36 migration |
| Use | The short claim | Ownership across the Provider call |

## Trade-off 4: Deadlock prevention vs detection vs bounds

| Mechanism | What it does | What it does not do |
| --- | --- | --- |
| Consistent lock order | Prevents the common cycle | Nothing if some writer disobeys |
| PostgreSQL detector | Aborts a cycle (`40P01`) | Prevent it, or retry for you |
| `lock_timeout` (`55P03`) | Bounds an ordinary wait | Replace ordering |
| Application retry | Re-runs the whole txn (finite) | Fix a wrong transaction boundary |

---

# Hands-on Exercises

## Exercise 1: Visibility vs claim (Beginner)

Two Workers `SELECT` the same queued Job. Explain why both seeing it is not both claiming it, and what
actually decides the single winner.

Verification: names Day33's guarded UPDATE (one legal transition) and `FOR UPDATE` for explicit ownership.

## Exercise 2: `FOR UPDATE` vs `SKIP LOCKED` (Beginner)

job-A is locked. Predict what plain `FOR UPDATE` does and what `FOR UPDATE SKIP LOCKED` returns.

Verification: plain waits; `SKIP LOCKED` returns job-B.

## Exercise 3: Released lock is not liveness (Intermediate)

After the Start COMMIT the lock is gone. Explain why a second Worker must not reclaim the Job, and what
reclaim would duplicate.

Verification: committed Job/Attempt/Event persist; blind reclaim duplicates Attempt, Event, Provider cost.

## Exercise 4: Lease/heartbeat policy (Intermediate)

For an eight-minute Job with 45-second heartbeat pauses, choose a lease duration and justify it against
false takeover and recovery speed.

Verification: chooses ~2 minutes over 30 seconds; ties duration to heartbeat + observed pause.

## Exercise 5: Stale-owner completion (Advanced)

Worker 1 is taken over (token-A -> token-B) and then resumes. Write the completion owner guard and state the
result.

Verification: guard requires current token + running + unexpired lease; token-A returns zero rows and the
Completion transaction rolls back.

## Exercise 6: Ownership token vs Provider identity (Advanced)

Explain why the new `lease_token` must not become the new Provider idempotency key across a takeover.

Verification: token changes per epoch; the Provider key must stay stable (derived from `attempt_id`, sent to
a supporting Provider) or charges can repeat.

## Exercise 7: Pessimistic vs optimistic at scale (Advanced)

100 Workers, 10,000 Jobs. Choose the concurrency style and explain the retry-storm failure of the other.

Verification: pessimistic `SKIP LOCKED` spreads Workers; optimistic on the oldest Job storms.

## Exercise 8: Read Committed 100-to-101 (Intermediate)

Explain the phantom, and why Repeatable Read does not partition work.

Verification: new snapshot per statement (RC); stable snapshot (RR) does not allocate Jobs.

## Exercise 9: Deadlock and lock order (Advanced)

Diagnose the reverse-order deadlock, give the `SQLSTATE`, and repair it with a consistent order.

Verification: `40P01`, one victim aborted; consistent ascending-`job_id` order prevents the cycle; the
application retries.

## Exercise 10: Integrated takeover/rollback (Advanced)

Worker 1 commits claim/token-A and calls the Provider; the lease expires; Worker 2 takes over with token-B;
Worker 1 resumes and tries to complete. State what happens in the database and what remains outside it.

Verification: the owner guard returns zero rows and the whole Completion transaction rolls back; Provider
cost and Object Storage bytes remain for reconciliation.

---

# Relevant Framework Connections

## PostgreSQL

MVCC snapshots; Read Committed / Repeatable Read / Serializable boundaries; row locks; `FOR UPDATE SKIP
LOCKED`; `SQLSTATE 55P03` (lock-timeout cancel), `40P01` (deadlock), `40001` (serialization failure); short
transaction ownership and guarded writes. Index and `EXPLAIN` work on these access paths is **Day35**.

## Celery / Workers

Competing consumers claiming queue work; takeover, heartbeat/lease policy, and stale Workers; bounded
transaction retry; fairness monitoring (oldest queued age, lock waits, expired leases). The claim transaction
stays short; the Provider call runs after COMMIT.

## FastAPI / application driver

Inspect `RETURNING`/affected rows; map `SQLSTATE`; roll back a failed transaction and retry the whole unit
with bounded jitter; never treat a candidate `SELECT` as a claim. `tenant_id` stays a server-authenticated
predicate on the claim.

## Object Storage / AI Provider

External effects survive a database rollback; a lease cannot revoke a request; the stable Provider
idempotency identity stays separate from the lease ownership identity. An eight-minute call never sits inside
a transaction or under a held row lock.

## Validation evidence for these exercises

State the level, never the level above it.

```text
1. Conceptual / manual production reasoning        DONE (in class)
   The 18 concepts, the ownership/liveness boundary, the lease state machine, isolation and deadlock.

2. Reduced-schema PostgreSQL 14.18 runtime         DONE (three listed concurrency tests ONLY)
   Environment: PostgreSQL 14.18 (Homebrew), a REDUCED disposable schema
     jobs(job_id text primary key, job_status text, created_at integer)
   -- NOT the full Day31 schema, and NOT the final 006 artifact.
   PASS: Session A held a row lock on job-A; a real concurrent Session B ran the ordered
         queued query with FOR UPDATE SKIP LOCKED and returned job-B.
   PASS: While Session A held job-A, Session B used ordinary FOR UPDATE with lock_timeout=500ms
         and failed with SQLSTATE 55P03 (canceling statement due to lock timeout, while locking
         tuple in relation jobs).
   PASS: Session A locked job-A then requested job-B; Session B locked job-B then requested job-A;
         PostgreSQL detected the circular wait and aborted Session B with SQLSTATE 40P01
         (deadlock detected); Session A then COMMITted.
   An initial restricted-sandbox initdb failed with
     could not create shared memory segment: Operation not permitted / shmget
   -- ENVIRONMENT evidence, not a SQL failure. The temporary server was stopped afterwards.

3. Final repository 006 artifact static review     DONE (repository update)
   Active SQL uses the Day31 columns exactly; the FOR UPDATE SKIP LOCKED claim wraps the unchanged
   Day33 guarded Start write with explicit control-flow gates; the lease state machine
   (claim_owner / lease_token / lease_expires_at) is entirely COMMENTED and conceptual; no
   CREATE INDEX / EXPLAIN / ALTER / migration / ORM / Redis; no credentials.

4. Final repository 006 artifact PostgreSQL runtime  NOT RUN
   No psql/PostgreSQL server was available during the repository update. The reduced-schema
   classroom tests are NOT reused as proof of this file, and they never ran the full Day31 schema,
   the claim's Attempt/Event inserts, or any lease field.

5. Application / external integration               NOT RUN
   No FastAPI/driver/Celery multi-Worker integration, lease heartbeat/renewal/takeover, stale-token
   Completion on a migrated schema, Provider idempotency/lookup, Object Storage, or Redis/Queue.

6. Recovery / fairness / stronger isolation          NOT RUN
   No crash/restart recovery, long-duration fairness/starvation, or SERIALIZABLE workload.

7. Performance / production validation               NOT RUN / OUT OF SCOPE
   No Day35 index plans, no production load/performance, RLS, backups, HA, or deployment.
```

---

# AI Backend Connections

## Connection 1: Long model calls stay outside transactions and locks

An eight-minute Provider call must not sit inside a PostgreSQL transaction or under a held row lock; the
claim commits first, then the call runs (Concepts 2, 4).

## Connection 2: A short lock assigns work; a committed lease makes ownership recoverable

The row lock spreads Workers across the queue; the committed lease is what lets a paused/dead Worker's Job be
taken over after COMMIT (Concepts 6, 7).

## Connection 3: False takeover is a cost problem, not just availability

A too-short lease takes over a healthy Worker and can repeat an expensive model call, so lease duration and
heartbeats are cost and correctness controls (Concepts 8, 9).

## Connection 4: The database boundary can reject a stale Worker; the Provider boundary cannot

A token guard rejects stale database completion, but external Provider work still needs a **stable pre-call
idempotency key** or reconciliation — the lease cannot revoke or dedupe it (Concepts 8, 10).

## Connection 5: `SKIP LOCKED` throughput can cost FIFO fairness

Many-Worker throughput improves, but strict queue order and freedom from starvation are not guaranteed;
monitor oldest queued age and stale/expired ownership instead of assuming queue order provides recovery
(Concept 5).

---

# English Interview

Three questions were answered aloud. The student's real words are preserved verbatim, including grammar,
because the correction targets the content.

## Beginner: what is MVCC?

Student answer (actual):

> "MVCC means multiple version concurrency controle.beacause default config is read commit,snap shot is same"

Correction: MVCC (multi-**version** concurrency control) is right, and Read Committed being the default is
right. Fix the last clause: separate Workers have their **own** snapshots — both can *contain* the same
committed row, but the snapshots are not "the same," and under Read Committed each statement takes a **new**
snapshot.

Strong spoken answer:

> "MVCC is multi-version concurrency control: PostgreSQL keeps multiple row versions and gives each
> transaction a snapshot. Under the default Read Committed, each statement gets a fresh snapshot, so two
> Workers can both see the same committed queued row in their own snapshots — but seeing it is not owning it."

## Intermediate: what does `SKIP LOCKED` do for a queue?

Student answer (actual):

> "beacause it avoid a job get lock,other worker await lock realease.other worker can find other and lock it"

Correction: the idea is right. Sharpen the wording: `FOR UPDATE SKIP LOCKED` does not make a Worker *wait*
for a locked row — it **skips** it and locks the next available Job, so Workers spread across the queue.

Strong spoken answer:

> "`FOR UPDATE SKIP LOCKED` lets a Worker skip rows another claim transaction has locked and reserve the
> next available Job instead of waiting on the queue head. That spreads Workers across the queue and avoids a
> convoy, at the cost of strict FIFO."

## Senior: how does takeover stay correct?

Student answer (actual):

> "everytime the job owener worker changed,generate a new lease token"

Correction: correct as far as it goes — takeover mints a new `lease_token`, which blocks stale database
completion. Add the second half: a **stable pre-call Provider idempotency key** protects the same external
operation, and if the Provider has no idempotency/lookup, reconciliation is required.

Strong spoken answer:

> "Each takeover generates a new `lease_token`, so a stale Worker's completion fails its token guard and
> rolls back. But the lease only controls the database. The external Provider call needs a separate, stable
> idempotency key derived from the durable `attempt_id` and actually sent to the Provider; the changing lease
> token must never be used as that key, or takeovers can repeat charges. Without Provider idempotency, I
> reconcile instead of retrying."

Key vocabulary: `candidate visibility`, `row lock`, `FOR UPDATE SKIP LOCKED`, `committed lease`,
`lease_token`, `lease_expires_at`, `takeover`, `false takeover`, `snapshot`, `phantom`, `deadlock (40P01)`,
`serialization failure (40001)`, `lock timeout (55P03)`, `consistent lock order`, `bounded retry`.

---

# Mental Model Summary

```text
1. Visibility (a SELECT / snapshot) is not ownership (a lock, then a committed lease).
2. FOR UPDATE is a transaction-local row lock; a conflicting locker waits, ordinary reads do not.
3. FOR UPDATE SKIP LOCKED skips locked rows and claims the next available — a queue claim, not a report.
4. The claim = SKIP LOCKED reserve + the unchanged Day33 guarded Start write + gate + COMMIT, then Provider.
5. SKIP LOCKED weakens fairness: ORDER BY sorts only available rows; no strict FIFO, starvation is possible.
6. A released lock proves nothing about liveness; committed Job/Attempt/Event persist; blind reclaim duplicates.
7. Row lock = transaction-local exclusion; committed lease = recoverable ownership (owner + token + expiry).
8. Lease expiry is a takeover condition, not death; takeover WRITES a new token; expiry alone does not.
9. Lease duration comes from heartbeat + observed pause, not Provider duration; short recovers fast but false-takes over.
10. lease_token (ownership epoch) != Provider idempotency key (stable per external operation); never cross them.
11. Pessimistic SKIP LOCKED spreads a contended queue; pure optimistic on a hot row storms.
12. Read Committed takes a new snapshot per statement (100 then 101 is a phantom, allowed, not broken atomicity).
13. Repeatable Read/Serializable keep a stable snapshot and may abort with 40001; isolation does not partition work.
14. A reverse-order deadlock is detected and one victim aborts with 40P01; PostgreSQL does not auto-retry.
15. A consistent global lock order prevents the cycle; every writer must obey it.
16. Prevent (order) + detect (40P01) + bound (lock_timeout/55P03) + application retry (finite, jittered); UNIQUE still required.
```

Final Chinese synthesis (student, verbatim):

> "MVCC是多版本并发控制，意思就是通过快照，每次不同worker查询的时候只要在各自快照的时候已经有当时的数据。都可以查询到相同的行，但是并不代表拥有使用权，这个时候就需要行锁for update，使用行锁的排他性，避免其他的worker继续操作相同的行。而SKIP locked表示当前的job已经被其他worker加了锁，但是又不能等待，所以跳过当前的job去寻找其他的job再加上锁。避免长时间等待。lease 有lease token 以及expire time，表示当一个worker在执行job但是处于长时间没有响应或者暂停时，另外一个work接手后，work重新继续运行避免引起冲突以及重复调用等问题。expire time到期以后lease token就失效了，这个时候在work重新运行的时候会对比lease token发现不一样就进行回滚 ，但是无法解决已经调用的provider和产出的结果。死锁表示两个worker分别等待对方的锁释放而形成锁循环。所以这个时候数据库会让其中一个停止，在另外一个释放以后再重试。provirder幂等键解决lease无法对外部产出结果无法回滚以及重复调用。"

Targeted corrections (Tech Lead):

1. Strong throughout: visibility != ownership, `FOR UPDATE` exclusivity, `SKIP LOCKED` avoids waiting,
   deadlock as a lock cycle, Provider idempotency covering what the lease cannot.
2. Precision: "expire time 到期以后 lease token 就失效了" — expiry does **not** itself change/void the
   token. Expiry makes ownership invalid via the **time predicate**; **takeover** writes the new token, and
   the completion guard compares tokens.
3. Precision: the row lock does not block **every** reader, only conflicting locking/writing operations.
4. Precision: the Provider idempotency key **deduplicates/reconciles** repeated requests at a supporting
   Provider; it cannot **roll back** an external result already produced.

---

# Today's Takeaway

Day33 made one write correct. Day34 makes it correct when a crowd of Workers competes for the same row. The
core discipline is to stop treating a read as a claim: a `SELECT` is visibility, ownership is a `FOR UPDATE`
reservation, and ownership that must survive the Provider call is a **committed lease** with an owner, a
token, and an expiry.

The boundaries are where the care lives. A released lock is not a liveness check, and an expired lease is
permission to take over, not proof of death — so completion guards the current token and an unexpired lease,
and a stale Worker's late write rolls back. Takeover writes a new token, but the **Provider** idempotency key
stays stable and separate, because ownership changes hands while the external operation does not. And when
concurrency does bite — a deadlock — PostgreSQL detects and aborts one victim, a consistent lock order
prevents the cycle in the first place, and the **application** retries the whole transaction with a finite
budget. Through all of it, UNIQUE and idempotency constraints keep a retry from creating duplicate durable
facts.

Locks and leases decide ownership; constraints decide identity; a stable Provider key protects the external
call. None of them proves a Worker is alive — and none of them can be skipped.

---

# Before Next Lesson Checklist

- [ ] I can explain why a candidate `SELECT` is visibility, not a claim, and what actually picks the winner.
- [ ] I can predict plain `FOR UPDATE` waiting vs `FOR UPDATE SKIP LOCKED` selecting the next available Job.
- [ ] I can assemble the claim transaction around the unchanged Day33 Start write and gate the inserts.
- [ ] I can state what `SKIP LOCKED` does not guarantee (strict FIFO, complete snapshot, eventual service).
- [ ] I can explain why a released lock is not liveness evidence and what blind reclaim duplicates.
- [ ] I can distinguish a transaction-local row lock from a committed lease with owner/token/expiry.
- [ ] I can explain why lease expiry is a takeover condition, that takeover writes the token, and the completion guard.
- [ ] I can choose a lease duration from heartbeat + observed pause and justify it against false takeover.
- [ ] I can keep `lease_token` separate from a stable Provider idempotency key and say why.
- [ ] I can read a Read Committed phantom and explain why stronger isolation does not partition work.
- [ ] I can diagnose a reverse-order deadlock (`40P01`), prevent it with lock order, and retry from the app.

Preparation for Day35 (PostgreSQL Indexes and Query Planning):

- [ ] Re-read `projects/ai-backend-data-layer/sql/006_concurrency_control_mvcc_and_worker_claims.sql` and note the exact claim predicates and ordering (`tenant_id`, `job_status = 'queued'`, `cancel_requested = false`, `created_at, job_id`).
- [ ] Note the access paths a busy claim hammers: the queued scan, and (once the lease exists) stale-lease and unpublished-Outbox scans.
- [ ] Be ready to argue why an index is chosen by measurement (`EXPLAIN`), not by guess — and why Day34's correctness must be settled before Day35's speed.
- [ ] Keep `CREATE INDEX`/`EXPLAIN` out of scope until Day35, and lease-column migration out of scope until Day36.
