# Lesson 37 — PostgreSQL Production Reliability

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day36 — Schema Evolution and Safe Migrations

Previous Lesson: [Day36 — Schema Evolution and Safe Migrations](day36-schema-evolution-and-safe-migrations.md)

Next Lesson: Day38 — Redis Foundations and Data Structures (planned — see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day38 lesson file does not exist yet)

Engineering Artifact: The Day37 production reliability runbook (`projects/ai-backend-data-layer/runbooks/postgresql-production-reliability.md`) — connection-capacity worksheet, transaction boundaries, timeout/health/monitoring matrices, long-transaction/Vacuum + credential-rotation + backup/PITR procedures, replica-promotion gate, and the 420-vs-300 incident, all labelled conceptual/static — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

PostgreSQL Cheat Sheet: [cheat_sheets/postgresql.md](../../cheat_sheets/postgresql.md)

PostgreSQL Interview: [interview/postgresql.md](../../interview/postgresql.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 100-130 minutes
Hands-on runbook design + disposable-PostgreSQL reliability practice: 100-130 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Explain why a reachable database with low CPU is not a reliable system, and reason about **bounded** capacity for API acceptance, Worker claims, Attempt writes, and Outbox checkpoints.
2. Size connection pools by **aggregate demand across every process** (`(4 API + 12 Worker) * 10 = 160`), reserve capacity for migrations/monitoring/admin/recovery, and keep `global demand < safe connection budget`.
3. Keep the eight-minute Provider call outside the database transaction, and reconstruct the Accept -> Claim/Start -> External -> Complete boundaries with the full completion guard (`job_status = 'running'` AND `lease_token` = current token AND `lease_expires_at > now()`).
4. Distinguish Provider success, Object Storage Artifact existence, and committed PostgreSQL business success, and reconcile a deterministic Artifact before any second Provider call.
5. Apply the layered timeout model (pool acquisition, `lock_timeout`, `statement_timeout`, `idle_in_transaction_session_timeout`, application deadline) with the ordering `lock_timeout < statement_timeout < application deadline`.
6. Separate liveness, readiness, and business success, and prevent a shared-outage restart storm by dropping readiness rather than failing all liveness.
7. Reason about MVCC row versions, long/idle transactions retaining snapshots, and evidence-based per-table autovacuum tuning (never a casual `VACUUM FULL`).
8. Design least-privilege roles and a safe credential-rotation procedure, and diagnose a partial rotation from existing-success/new-auth-failure behaviour.
9. Explain that replication is not backup, and that recoverability requires an isolated restore + PITR + integrity/business checks + measured RPO/RTO — not a successful backup job.
10. Make the 420-vs-300 incident decision: contain demand and roll back the pool configuration, reconcile irreversible external effects, and resize the database only on evidence.

---

# Why This Matters

Day36 made the Lease-aware schema safely deployable. Day37 keeps it **running** in production — and the
failure that opens this lesson is the one that fools everyone: a slowing AI Job system while database CPU
stays modest. Low CPU said "healthy"; the truth was exhausted connection pools, a session stuck `idle in
transaction`, and growing pool waits. Every business operation — accepting a `202`, claiming a Job,
finishing an Attempt, checkpointing the Outbox — depends on **bounded** database capacity, not on CPU.

Reliability is a different discipline from correctness. A transaction can be perfectly correct and still take
down the system if it is held for eight minutes, if pools are sized past the connection budget, if a long
snapshot blocks Vacuum, if the runtime role can `DROP TABLE`, or if "backup succeeded" is mistaken for
"recovery works." Day37 is the set of operational boundaries — connections, timeouts, health, Vacuum,
privilege, and recovery evidence — that keep the durable truth available, secure, and recoverable.

And the honesty carries through: this is a reasoning and design lesson. Nothing was executed — no server, no
pool, no Vacuum, no restore. The runbook is a design and evidence plan, clearly marked, not a benchmark.

---

# Roadmap Position

```text
Day31  relational integrity        Day34  concurrency + Lease reasoning
Day33  short atomic writes         Day35  measured access paths
Day36  safe schema evolution
Day37  production reliability: connections, timeouts, health, Vacuum, privilege, recovery   <-- you are here
Day38  Redis Foundations (transient acceleration; PostgreSQL stays the durable source of truth)
```

Day36 deployed the schema; Day37 operates it. Day38 then adds Redis as **transient** state, judged for
correctness against the authoritative, recoverable PostgreSQL truth this lesson protects.

---

# Lesson Map

```text
1. Reliability boundary            -> reachable/low-CPU != reliable
2. Connection pools are finite      -> aggregate demand < safe budget; reserve capacity
3. Short transactions               -> the 8-minute call stays outside the DB transaction
4. Artifact != success              -> reconcile deterministic Artifact before a second call
5. Lease expiry + takeover           -> eligibility, not proof of no side effects
6. Layered timeouts                  -> pool/lock/statement/idle-in-tx/deadline
7. Liveness vs readiness vs business -> drop readiness, do not storm-restart
8. MVCC, long tx, Vacuum, autovacuum -> snapshots, dead tuples, per-table tuning
9. Roles + least privilege           -> runtime cannot DDL; credential rotation lifecycle
10. Replication is not backup         -> it copies bad writes too
11. Base backup + WAL + PITR          -> restore evidence, RPO/RTO
12. Monitoring                        -> low CPU proves nothing; capacity/age/growth/recovery
13. Replica promotion                 -> replay position, RPO decision, split-brain
14. Managed vs self-operated          -> what the team still owns
15. The 420-vs-300 incident           -> contain + roll back config; reconcile external effects
```

---

# Core Mental Model

```text
Reachable / low-CPU  !=  RELIABLE. Business operations depend on BOUNDED capacity, not CPU.

Connections are finite: sum EVERY process's pool + reserve  <  safe connection budget  <  max_connections.
Transactions are SHORT: the 8-minute Provider call runs OUTSIDE the DB transaction (Accept/Claim/External/Complete).
Provider success != Artifact bytes != committed PostgreSQL success. Reconcile the deterministic Artifact first.

Timeouts CONTAIN failure, they do not repair it: lock_timeout < statement_timeout < application deadline;
idle_in_transaction_session_timeout kills stuck transactions; SKIP LOCKED is claim selection, not a timeout.

Liveness = restart-fixes-local?  Readiness = safe-for-new-traffic?  Business success = a real operation.
A shared DB outage drops READINESS + backs off; it must NOT fail every liveness (restart storm).

Long/idle transactions retain snapshots -> block Vacuum -> dead-tuple bloat. Fix the source first; tune autovacuum per-table on evidence; never casual VACUUM FULL.
Least privilege: runtime cannot DDL. Rotation = load new -> verify all switched -> recycle -> revoke old.
Replication != backup (it copies bad writes). Recovery EVIDENCE = isolated restore + PITR + integrity/business checks + measured RPO/RTO.
RPO/RTO are RECOVERY objectives, NOT health probes.
```

---

# Main Concepts

## Concept 1: Reachable Is Not Reliable

Tech Lead Question:

A post-release AI Job system slows down, but database CPU stays modest. Is the database healthy?

Student Answer:

> "不知道"

Tech Lead Review:

Honest, and the right starting point — because the answer is not "yes." A reachable database with low CPU is
**not** a reliable system. Here connection count and pool waits were growing and a session sat `idle in
transaction`. API acceptance, Worker claim/completion, Attempt writes, and Outbox checkpoints all depend on
**bounded database capacity**, and none of that shows up as CPU. Reliability is about capacity, waiting, age,
and recovery — not a single utilization number.

Engineering Thinking:

"Up" and "low CPU" are the least informative health signals you have. Ask what is *waiting*, how *old* the
oldest transaction is, and whether you could *recover*.

## Concept 2: Connection Pools Are Finite Capacity

Tech Lead Question:

Four API processes and twelve Workers each own a pool with limit 10. What is the total possible application
connection demand?

Student Answer:

> "160"

Tech Lead Review:

Correct: `(4 + 12) * 10 = 160`. The key insight is that total demand is the **sum across every process**, not
one pool setting. Asked whether all nominal database connections should be handed to applications:

> "不会，因为要按照具体需求进行分配，如果全部按照最大进行分配，很快连接池就被耗尽了"

Right conclusion — reserve capacity — though sharpen the reason: a pool maximum is an **upper bound on
potential demand**, not connections opened immediately, and the database budget must reserve connections for
migrations, monitoring, administration, recovery, and margin. And raising pool sizes can **move queuing from
the application into PostgreSQL** and add memory/CPU/I/O/cache pressure. The model is `global application
connection demand < PostgreSQL safe connection budget`.

Engineering Thinking:

A pool limit is a promise the whole fleet can call in at once. Add up every process's promise before you
compare it to the database budget.

## Concept 3: Short Transactions Around External AI Work

Tech Lead Question:

Should an eight-minute Provider call be inside a PostgreSQL transaction?

Student Answer:

> "不能，因为长事务，会造成连接池被更快耗尽"

Tech Lead Review:

Correct. A long transaction holds a connection (and possibly locks and an old snapshot) and exhausts the pool
faster. The class then reconstructed the full lifecycle after a student-initiated question:

```text
Accept:    queued Job + dispatch Outbox intent -> COMMIT -> return 202 + job_id
Claim:     reserve queued Job, write Lease, queued -> running, Attempt + job_started Event -> COMMIT
External:  Provider call + Object Storage upload OUTSIDE any transaction; Lease renewal via SHORT txns
Complete:  guard by job_id AND job_status = 'running' AND lease_token = current token AND
           lease_expires_at > now(); finish Attempt + Result Artifact + success Event,
           running -> succeeded -> COMMIT
```

Engineering Thinking:

Hold a database transaction only across database work you can finish fast. The slow external world lives
between short transactions.

## Concept 4: Artifact Existence Is Not Job Success

Tech Lead Question (from the student's own question):

The student asked, in effect: if the model produced an Artifact after eight minutes, shouldn't the Job
already be `succeeded`?

Student Answer (preserved):

> "不会知道，因为事物没有跨越provider调用，我还有一个问题就是调用模型8分钟以后不久生成了artifact了吗，下面的使用 job_id + lease_token 守卫这是放在runner状态下的。但是既然都有成果了，不应该是success吗"

Tech Lead Review:

A sharp question, and the correction is central: Provider success, Object Storage Artifact **bytes**, and a
**committed** PostgreSQL business state are three different facts. If an Artifact exists but the Complete
transaction never committed, the database **truthfully** still shows `running`. Asked what to do first, the
student answered:

> "先对账，避免二次调用provider。我还有一个问题就是那事务1的时候不就是queue吗，那个时候并没有转化为running呢，事务2就直接变成running了，是在哪里转换的"

Exactly right on reconciliation — reconcile the deterministic Artifact first to avoid a second paid Provider
call. And the transaction-numbering question is answered by Concept 3: **Accept** creates `queued`;
**Claim/Start** atomically writes the Lease and transitions `queued -> running`; **Complete** transitions
`running -> succeeded`.

Engineering Thinking:

A result in Object Storage is evidence the Provider ran, not proof the database committed success. Recovery
reconciles the durable Artifact; it does not re-call the Provider on a guess.

## Concept 5: Lease Expiry and Takeover

Tech Lead Question:

What makes an expired Lease owner eligible for takeover, and what does expiry *not* prove?

Student Answer:

> "根据lease_expaire_at根据过期时间"

Tech Lead Review:

Correct that `lease_expires_at` is the eligibility signal. The precision to add: expiry permits an **atomic
takeover**, but it does **not** prove the former Worker died before doing external work. Takeover therefore
requires an atomic new token, stale-token rejection on completion, Provider idempotency, a deterministic
Artifact key, and reconciliation. The current Lease token is a **database ownership epoch** — it is not the
same as a stable external idempotency key (Day34).

Engineering Thinking:

Expiry says "you may take over," not "the old owner is gone." Idempotency and reconciliation cover the gap
expiry cannot.

## Concept 6: The Layered Timeout Model

Tech Lead Questions (three cases):

Protect an `UPDATE` from waiting forever on a lock? Protect a slow **non-locking** query? Protect against an
idle-open transaction?

Student Answers:

> (lock wait) "skip lock"

> (slow non-locking SQL) "statement_timeout"

> (idle transaction) "应该使用Pool acquisition timeout"

Tech Lead Review:

One correct, two corrected. `statement_timeout` for the slow non-locking query is right. But `SKIP LOCKED`
is **not** a timeout — it skips already-locked claim candidates; the tool that bounds **lock acquisition** is
`lock_timeout`. And **pool acquisition timeout** applies *before* you obtain a connection; the tool for a
transaction that is already open and idle is `idle_in_transaction_session_timeout`.

```text
Pool acquisition timeout            -> waiting for an application connection
lock_timeout                        -> waiting to ACQUIRE a lock (55P03 on cancel)
statement_timeout                   -> total SQL execution time
idle_in_transaction_session_timeout -> a transaction opened then left idle
application deadline                -> the whole business operation
Ordering: lock_timeout < statement_timeout < application deadline
```

Timeout is **failure containment, not root-cause repair** — every timeout must be observable and routed to
bounded retry, immediate failure, or investigation.

Engineering Thinking:

Each timeout guards a different stage. Point the right one at the right wait, and treat every fire as a
signal, not a fix.

## Concept 7: Liveness, Readiness, and Business Success

Tech Lead Question:

Under pool saturation, should the instance report ready? And during a shared PostgreSQL outage, should every
Pod fail liveness?

Student Answers:

> (readiness under saturation) "不能，这个时候已经有连接池已被耗尽"

> (not failing all liveness) "PostgreSQL暂时不可达，可能是连接池被耗尽，但是里面有pod正常连接了postgresql.所以如果重启又需要重新建立连接"

Tech Lead Review:

Both correct. `SELECT 1` proves only that one simple query can run through one connection — not pool
capacity, lock freedom, critical Job transactions, disk/WAL health, transaction age, or recovery readiness.
**Liveness** asks whether restarting this instance would fix a *local* failure; **readiness** asks whether it
can safely take new traffic; **business success** is a real operation's result and equals neither probe. A
shared PostgreSQL outage should **drop readiness and back off/degrade** — not fail every Pod's liveness and
cause a simultaneous restart/reconnection storm.

Engineering Thinking:

Restart fixes *me*; readiness protects *the fleet from me*. A shared dependency failure is a readiness event,
not a reason for everyone to restart at once.

## Concept 8: MVCC, Long Transactions, Vacuum, and Autovacuum

Tech Lead Question:

Why do old row versions accumulate, and what do you do first when Vacuum cannot keep up?

Student Answers:

> (MVCC/Vacuum) "因为mcvv使用的是快照的形式，再使用vacuum清楚垃圾"

> (root cause first) "还是先调查并结束这个长期事务，因为长期事务会一直保留旧快照，先停止长期事物。再通过autovacuum进行垃圾回收"

> (per-table tuning) "针对这张表调低触发阈值并监控 I/O，因为问题就是autovacuum触发频率跟不上job表的更新频率"

Tech Lead Review:

The model is right; the terminology needed a fix — it is **MVCC** (not "mcvv") and the reclaimable old row
versions are **dead tuples** (not "trash"). An `UPDATE` writes a new version so older snapshots still see an
older one; Vacuum can reclaim a version only after **no active snapshot** can see it. A long or
idle-in-transaction session retains an old snapshot, can retain locks, blocks cleanup, and grows dead-tuple /
table / index bloat. Root-cause-first is exactly right: identify and stop the long transaction, then let
autovacuum reclaim; verify transaction-age and dead-tuple trends; fix the application boundary. Do **not**
casually run `VACUUM FULL` (it rewrites the table under a strong lock). And per-table autovacuum tuning is
correct **with I/O observation** — the settings shown were design syntax only, not production
recommendations without measurement.

Engineering Thinking:

Dead tuples are a symptom; the retained snapshot is the cause. Remove the cause first, then tune Vacuum on
evidence — never with a table-rewriting sledgehammer by reflex.

## Concept 9: Roles, Least Privilege, and Credential Lifecycle

Tech Lead Question:

Should the API/Worker runtime identity be able to run DDL? Where do credentials live?

Student Answers:

> (runtime DDL) "不能，因为API与work会引起安全问题"

> (secret storage) "不应该，应该使用secrets或者secrets manager"

> (rotation diagnosis) "先检查是否所有实例都切换了，新建连接使用新凭证，逐个体寒"

Tech Lead Review:

Correct throughout. Runtime DML identities must **not** own `ALTER TABLE`, `DROP TABLE`, index creation, or
role management; separate runtime, migration, monitoring, and — as distinct identities — a backup/replication database role (`pg_basebackup`/replication only), a WAL-archive storage identity (archiver write-only, not an application account), and a restore operator/control-plane identity used only in an isolated recovery environment, so least
privilege limits the blast radius of bugs, injection, leaks, and operator error. Credentials never belong in
images or Git history — use Kubernetes Secrets, a cloud Secrets Manager, Vault, or managed short-lived
identity — and **storage alone is insufficient**: creation, distribution, rotation, revocation, and audit are
all required. The rotation answer (last phrase read as a likely typo for *gradual switching*, preserved as
written) has the right shape: verify all instances switched to the new credential before revoking the old.

```text
Rotation: load new -> establish new connections -> verify EVERY instance switched
          -> recycle pools -> ONLY THEN revoke old.
```

Diagnostic: existing sessions continuing while **new** authentication fails often indicates an **incomplete
rotation**, not total database failure.

Engineering Thinking:

Give each identity only what it needs, and treat a credential as a lifecycle, not a stored string. Revoke
last, after you have proven the new one works everywhere.

## Concept 10: Replication Is Not Backup

Tech Lead Question:

Is a replica a backup?

Student Answer:

> "不能，因为只是备份了删除部分"

Tech Lead Review:

Correct conclusion, imprecise reason. Replication improves **availability** by keeping a near-current copy —
but it also **copies harmful logical changes**: a mistaken `DELETE`/`DROP` replicates to the replica.
**Backup** protects **recoverability** by retaining **independent historical** recovery material. A replica
is therefore not a complete backup.

Engineering Thinking:

A replica follows your mistakes; a backup remembers the state before them. You need the one that can go
*back*.

## Concept 11: Base Backup, WAL, PITR, and Restore Evidence

Tech Lead Question:

What are base backup and WAL, and does a successful backup job prove you can recover?

Student Answers:

> (base backup + WAL) "基础备份是误操作恢复，wal是记录详细数据库操作日志"

> (restore testing) "不能，因为没有进行真正的恢复测试"

Tech Lead Review:

The restore-testing answer is exactly right; the base-backup/WAL description needed precision. A **base
backup** is the consistent recovery **starting point**; **archived WAL** is ordered **physical redo**
information (not a readable SQL history) replayed after that point. **PITR** restores the base backup and
replays WAL up to a chosen target *before* the bad change — e.g. target `10:36:59` to recover from a `10:37`
delete. **RPO** is the max acceptable data-loss window; **RTO** is the max acceptable recovery duration — both
**recovery objectives, not health probes**. A successful backup **job** is only backup evidence.
**Recoverability** requires an **isolated** restore, PITR, PostgreSQL startup, schema/constraint/key-row
checks, business-query validation, measured RPO/RTO, and recorded limitations — and you never overwrite
production to test recovery.

Engineering Thinking:

"Backup succeeded" is a hopeful log line. "We restored it in isolation and the business queries passed" is
the only recovery evidence.

## Concept 12: Monitoring — Low CPU Proves Nothing

Tech Lead Question:

The database shows low CPU. Can you conclude it is healthy?

Student Answer:

> "不能判断，暴露了连接池超时，长事务保留旧快照、恢复测试缺失等风险"

Tech Lead Review:

Correct. Low CPU can coexist with pool-acquisition timeouts, long transactions retaining old snapshots, WAL
growth, replication lag, and missing restore evidence. Reliability monitoring must cover **connections** (active/
idle/idle-in-transaction, pool waits), **queries** (latency, timeout rate, slow plans), **locks** (waiters,
blockers, deadlocks), **transactions/Vacuum** (oldest transaction, dead tuples, autovacuum keeping pace),
**storage/WAL** (disk growth, WAL, archive failures), **replication** (lag, replay position), and
**recovery** (latest backup evidence, latest *tested* restore, measured RPO/RTO).

Engineering Thinking:

Monitor what fails you — waiting, age, growth, and recovery readiness — not the one number that stays calm
while the system starves.

## Concept 13: Replica Promotion Decision

Tech Lead Question:

A replica is ten minutes behind. Do you promote it during a primary failure?

Student Answer:

> "不能，因为副本的复制延迟有10分钟，在故障进行切换时，副本数据可能与主库有很大差异"

Tech Lead Review:

Correct. Promoting a lagging replica may **exclude acknowledged primary transactions**. Promotion needs a
known replication/replay **position**, an estimated **data-loss window**, an explicit **RPO decision**,
**split-brain** prevention (the old primary must stop accepting writes), and a **reconciliation** plan.
Immediate promotion improves RTO but may violate RPO; waiting for the primary or remaining WAL preserves more
data but lengthens the outage.

Engineering Thinking:

Promotion is an RPO-versus-RTO trade made on evidence, not a reflex. Know exactly how far behind you are
before you accept that loss.

## Concept 14: Managed vs Self-Operated

Tech Lead Question:

Does a managed PostgreSQL service mean you no longer own reliability?

Student Answer:

> "不是，因为云厂商只是方便扩容，实际还是需要根据业务进行自定义配置"

Tech Lead Review:

Correct, with scope added. Managed services may automate infrastructure, patching, availability, backup
mechanisms, and scaling per the contract — but the team **still owns** connection budgets, transaction/query
behaviour, roles, credentials, schema, migrations, recovery objectives, retention, **restore testing**,
business validation, and incident response. Managed reduces burden but can raise cost, restrictions, and
vendor dependence; self-operation increases control but transfers patching, HA, backup, monitoring, on-call,
and recovery to the team.

Engineering Thinking:

A provider can run the machine; it cannot own your capacity, access design, or whether your restore actually
works. Those stay yours.

## Concept 15: The 420-vs-300 Incident

Tech Lead Question:

After a bad rollout the fleet can request 420 connections but PostgreSQL allows 300. New connections fail
while Workers run costly Provider calls. What do you do?

Student Answer (initial):

> "提高 PostgreSQL max_connections，同时重启会造成已经实现的调用断线。回滚无法回滚provider的副作用"

Then, after correction:

> "连接池容量配置，因为已经发生的provider是无法进行回滚的，二次调用会浪费成本"

Tech Lead Review:

The instinct to protect in-flight Provider calls and to notice irreversible effects is good; the initial fix
was wrong. Do **not** blindly move overload into PostgreSQL by raising `max_connections`.

```text
Before:  4 API * 10 + 12 Worker * 10 = 160
After:   12 API * 25 = 300 + 12 Worker * 10 = 120 = 420  vs  max_connections = 300
```

Contain: stop further scaling/new demand, rate-limit or degrade, roll back/tighten the API pool
configuration through a **gradual** rollout, **preserve/drain** Workers with in-flight calls (no mass restart
-> reconnection storm), observe recovery, and resize the database **only with capacity evidence**. The
rollback target is the **connection-pool/instance capacity configuration** — configuration rollback is
**independent** of external-effect rollback. Existing Provider calls, cost, and Artifacts are irreversible
and must be **reconciled** (idempotency keys, deterministic Artifact identifiers).

Engineering Thinking:

When overload appears, contain demand and roll back the config that caused it — do not pour the flood into
the database, and do not pretend a config rollback undoes a paid Provider call.

---

# Common Misconceptions

## Mental Model Evolution (Day36 -> Day37)

```text
Starting system limitation (not a student quote):
    Day36 made the Lease-aware schema safely DEPLOYABLE, but a deployable schema is not an operated system.
    The opening incident -- a slowing AI Job system at low CPU with pool waits and an idle-in-transaction
    session -- shows correctness does not imply reliability.

Correction that Day37 makes:
    Operate the durable truth with explicit boundaries: bounded connections (aggregate demand < safe budget),
    short transactions around the external Provider call, layered timeouts, readiness/liveness that avoid
    restart storms, root-cause-first Vacuum, least-privilege roles + credential rotation, and recovery
    EVIDENCE (isolated restore + PITR + business checks + measured RPO/RTO).

Boundaries Day37 cannot cross:
    Low CPU is not health. A pool max is potential demand, not opened connections. Replication is not backup.
    A successful backup job is not recoverability. PostgreSQL cannot roll back Provider cost or Object
    Storage bytes -- external effects are reconciled, not undone. RPO/RTO are recovery objectives, not probes.

Net division of labour:
    Day36 DEPLOYS the schema; Day37 OPERATES + RECOVERS it. Day38 adds Redis as TRANSIENT acceleration judged
    against this authoritative, recoverable PostgreSQL truth. Nothing in Day37 was executed -- design + evidence only.
```

## Misconception 1: A high pool maximum itself exhausts the pool

Wrong: setting a large pool max immediately consumes connections.

Right: a pool max is **potential** demand. The production problem is **aggregate** demand across all
instances, long hold times, and insufficient database/operational reserve.

## Misconception 2: An Artifact means the Job is `succeeded`

Wrong: the model produced a result, so the Job is done.

Right: Provider success, Artifact bytes, and committed PostgreSQL business state are separate. Only the
current Lease owner committing the guarded Complete transaction makes `succeeded` durable. That guard is the full Day34 condition — `job_status = 'running'` AND `lease_token` = the current token AND `lease_expires_at > now()` — not the token alone: expiry does not change the token, so a stale-but-still-matching token must be rejected by the running + unexpired-lease checks. Reconcile the
Artifact first.

## Misconception 3: `queued -> running` happens in the Accept transaction

Wrong: accepting the Job moves it to running.

Right: **Accept** creates `queued`; **Claim/Start** atomically writes the Lease and transitions
`queued -> running`; **Complete** transitions `running -> succeeded`.

## Misconception 4: Lease expiry proves the old Worker did nothing external

Wrong: expiry means the former owner is gone and did no external work.

Right: expiry permits an **atomic takeover** but cannot prove the former Worker did not call the Provider.
Idempotency and reconciliation remain required.

## Misconception 5: `SKIP LOCKED` is how you stop an UPDATE waiting forever

Wrong: use `SKIP LOCKED` to bound a lock wait.

Right: `SKIP LOCKED` **skips** already-locked claim candidates (selection). `lock_timeout` bounds **lock
acquisition** waiting.

## Misconception 6: Pool acquisition timeout protects against an idle-open transaction

Wrong: pool acquisition timeout handles an already-open idle transaction.

Right: pool acquisition applies **before** obtaining a connection;
`idle_in_transaction_session_timeout` applies **after** a transaction is open and idle.

## Misconception 7: MVCC bloat is "trash"; you clear it with `VACUUM FULL`

Wrong: dead versions are trash; run `VACUUM FULL` to clean them.

Right: they are **dead tuples**; the cause is a retained snapshot (a long/idle transaction). Fix the source
first, let autovacuum reclaim, tune per-table on evidence — `VACUUM FULL` rewrites the table under a strong
lock and is not a casual tool.

## Misconception 8: Managed PostgreSQL means easier scaling and little else

Wrong: managed mainly means scaling is easier.

Right: it may also transfer patching, HA, and backup mechanisms, but never application correctness,
capacity, access design, RPO/RTO, restore validation, or incident accountability.

## Misconception 9: A base backup is "for mistaken-operation recovery" and WAL is a readable log

Wrong: base backup handles mistakes; WAL is a human-readable SQL log.

Right: base backup is the consistent **starting point**; WAL is **physical redo** replayed to a target time
during PITR — not a readable SQL history.

## Misconception 10: RPO/RTO are health-check indicators

Wrong: use RPO/RTO as liveness/readiness signals.

Right: liveness/readiness are **runtime health** boundaries; RPO/RTO are **recovery objectives**. (The
student corrected this in the accepted final synthesis.)

## Misconception 11: A successful backup job proves recoverability

Wrong: the backup job passed, so we can recover.

Right: that is only backup evidence. Recoverability needs an **isolated restore + PITR + integrity/business
checks + measured RPO/RTO** — never overwriting production to test.

## Misconception 12: Raise `max_connections` to fix connection overload

Wrong: the fleet wants 420 vs 300, so raise `max_connections`.

Right: contain demand and roll back the **pool configuration**; do not move overload into PostgreSQL.
Reconcile irreversible Provider effects; resize the DB only on evidence.

## Misconception 13: Low CPU means the database is healthy

Wrong: CPU is low, so nothing is wrong.

Right: low CPU can hide pool waits, long transactions, WAL growth, replication lag, and missing restore
evidence. Monitor capacity, waiting, age, growth, and recovery.

---

# Engineering Trade-offs

## Trade-off 1: Bigger pools vs bounded capacity

| Aspect | Bigger pools | Bounded to the budget |
| --- | --- | --- |
| Under load | queuing moves into PostgreSQL | queuing stays visible in the app |
| DB pressure | more memory/CPU/I/O/cache | reserved headroom preserved |
| Reserve | eaten by apps | kept for migration/monitoring/recovery |
| Correct when | never as a reflex | aggregate demand < safe budget |

## Trade-off 2: Long transaction vs short transactions + external phase

| Aspect | One long transaction | Short txns around the call |
| --- | --- | --- |
| Connection hold | 8 minutes | seconds |
| Vacuum impact | retains snapshot, blocks cleanup | none |
| External rollback | impossible anyway | reconcile via idempotency |
| Result | pool exhaustion | healthy resource lifecycle |

## Trade-off 3: Immediate promotion vs waiting (RTO vs RPO)

| Aspect | Promote lagging replica now | Wait for primary/WAL |
| --- | --- | --- |
| RTO | better (fast) | worse (longer outage) |
| RPO | may violate (data loss) | preserves more data |
| Risk | split-brain if unguarded | prolonged unavailability |
| Needs | replay position + RPO decision + reconciliation | patience + a recovering primary |

## Trade-off 4: Managed vs self-operated

| Aspect | Managed | Self-operated |
| --- | --- | --- |
| Burden | lower (patching/HA/backup mechanisms) | higher (all of it) |
| Control | more restricted | full |
| Cost / lock-in | higher / vendor dependence | lower / more work |
| Still yours | capacity, roles, RPO/RTO, restore tests, correctness | everything |

---

# Hands-on Exercises

## Exercise 1: Aggregate pool demand (Beginner)

Compute total possible application connections for 4 API + 12 Workers at pool 10, and state why it is a sum.

Verification: `(4 + 12) * 10 = 160`; total is the sum across every process.

## Exercise 2: Reserve capacity (Beginner)

Explain why not all nominal database connections should be assigned to applications.

Verification: reserve for migrations/monitoring/admin/recovery + margin; a pool max is potential demand.

## Exercise 3: Place the 8-minute call (Intermediate)

Put an eight-minute Provider call outside the DB transaction and name the four boundaries.

Verification: Accept / Claim-Start / External / Complete; call is in External, outside any transaction.

## Exercise 4: Artifact but no commit (Advanced)

Diagnose a crash after Provider/Artifact but before the committed Complete, and state the first recovery
step.

Verification: DB truthfully shows `running`; reconcile the deterministic Artifact before any second Provider
call.

## Exercise 5: Reconstruct the transitions (Intermediate)

State where `queued -> running` and `running -> succeeded` happen.

Verification: Claim/Start and Complete respectively; Accept only creates `queued`.

## Exercise 6: Timeout selection (Intermediate)

Match `SKIP LOCKED`, `lock_timeout`, `statement_timeout`, `idle_in_transaction_session_timeout`, pool
acquisition timeout, and application deadline to their scopes.

Verification: `SKIP LOCKED` is selection; the ordering is `lock_timeout < statement_timeout < deadline`.

## Exercise 7: Readiness and restart storm (Advanced)

Decide readiness under pool saturation and liveness during a shared PostgreSQL outage.

Verification: drop readiness + back off; do not fail all liveness (avoid a restart storm).

## Exercise 8: Vacuum root cause (Advanced)

For Vacuum falling behind, choose the first action and justify per-table autovacuum tuning.

Verification: stop the long/idle transaction first; tune per-table on I/O evidence; no casual `VACUUM FULL`.

## Exercise 9: Least privilege + rotation (Advanced)

Design runtime / migration / monitoring / backup-replication / WAL-archive / restore identity separation and a safe rotation order.

Verification: runtime cannot DDL; rotate load-new -> verify-all-switched -> recycle -> revoke-old.

## Exercise 10: Replica is not backup + PITR (Advanced)

Explain why a replica is not a backup and reconstruct base backup + WAL -> PITR to `10:36:59` before a
`10:37` delete.

Verification: replication copies bad writes; base backup + WAL replay to a target before the change.

## Exercise 11: Restore evidence (Intermediate)

State what a successful backup job proves and what recoverability actually requires.

Verification: only backup evidence; recovery needs isolated restore + PITR + integrity/business checks +
measured RPO/RTO.

## Exercise 12: The 420-vs-300 incident (Advanced)

Given 420 potential vs 300 `max_connections` with Provider calls in flight, give the containment and the
rollback target.

Verification: contain + roll back pool config; reconcile external effects; resize DB only on evidence.

---

# Relevant Framework Connections

## PostgreSQL

Connection budgets and `max_connections`; `lock_timeout` / `statement_timeout` /
`idle_in_transaction_session_timeout`; MVCC, dead tuples, autovacuum and per-table settings; roles and
least privilege; base backup, WAL, PITR; replication and lag; monitoring views.

## FastAPI / API processes and queue Workers

Per-process pools sum to the fleet's demand; `202` acceptance and Worker claim/complete depend on bounded
capacity; short transactions around the Provider call; timeouts mapped to bounded retry / fail / investigate.

## Kubernetes liveness / readiness and rolling replacement

Liveness restarts a locally-broken instance; readiness removes a saturated/degraded one; a shared outage
drops readiness rather than storming restarts; rolling replacement drains Workers with in-flight calls.

## Secrets and Object Storage

Credentials live in Kubernetes Secrets / a Secrets Manager / Vault / managed identity, never in images or
Git; Object Storage Artifacts are deterministic-key references reconciled during recovery, never re-called
on a guess.

## Managed PostgreSQL

The provider may run infrastructure/patching/HA/backup mechanisms; the team still owns capacity, roles,
RPO/RTO, restore testing, and incident response.

## Validation evidence for these exercises

State the level, never the level above it. **Day37 classroom status is conceptual reasoning and static
review only — nothing was executed.**

```text
1. Conceptual classroom validation                 COMPLETED
   One continuously evolving AI Job production scenario; all 15 concepts reasoned end to end.

2. Static reasoning review                          COMPLETED
   Static arithmetic ((4+12)*10 = 160; 12*25 + 12*10 = 420 vs 300); static review of transaction
   boundaries, timeout scope, readiness/liveness, MVCC/Vacuum, least privilege, rotation,
   replication-vs-backup, PITR, RPO/RTO, monitoring, promotion, and incident rollback reasoning.

3. Artifact syntax / runtime validation             NOT RUN
   No PostgreSQL server or disposable cluster started; no psql/SQL/configuration statement executed.

4. Disposable PostgreSQL validation                 NOT RUN
   No pool configured/saturated/measured; no real lock wait/timeout/deadlock/idle transaction/cancel;
   no Vacuum/autovacuum/dead-tuple/bloat/table-setting/VACUUM FULL behaviour run.

5. Application integration validation                NOT RUN
   No role/grant/credential/Secret/TLS/rotation configured; no Kubernetes probe or rolling drain deployed;
   no application/Worker/Provider/Object Storage integration run.

6. Backup / restore drill                            NOT RUN
   No base backup, WAL archive, PITR, isolated restore, integrity check, or business restore test; no
   replica lag/promotion/split-brain/reconciliation; no runtime RPO or RTO measured.

7. Production validation                             NOT RUN
   No managed PostgreSQL inspected/changed; no production environment accessed. Every number (160, 420,
   300, the autovacuum settings) is classroom arithmetic/design, not a measured result.
```

---

# AI Backend Connections

## Connection 1: Bounded capacity is the real health signal

Long-running model Provider calls make bounded connection capacity and short transactions the difference
between a reliable Job system and a slow one at low CPU (Concepts 1-3).

## Connection 2: External effects are reconciled, not rolled back

Provider cost and Object Storage bytes are irreversible; recovery reconciles deterministic Artifact keys and
uses idempotency, never a second guessed Provider call (Concepts 4, 5, 15).

## Connection 3: Health signals must protect the fleet

A shared PostgreSQL outage is a readiness/degradation event; failing every Worker's liveness would storm
restarts and worsen the incident (Concept 7).

## Connection 4: Recovery evidence protects the durable Job truth

The authoritative Job/Attempt/Event/Outbox state is only as safe as a *tested* restore; replication and a
successful backup job are not recovery evidence (Concepts 10-11).

## Connection 5: PostgreSQL stays the source of truth for Day38

Redis (Day38/39) is transient acceleration/messaging judged against this recoverable PostgreSQL truth; the
reliability boundary here is what makes that separation safe.

---

# English Interview

Three questions were answered aloud. The student's real words are preserved verbatim, including grammar,
because the correction targets the content.

## Beginner: what is a connection pool and why use one?

Student answer (actual):

> "API and work both of them all need to connect database by connction pool"

Correction: the idea — APIs and Workers use a pool — is right. Fix the wording (`workers`, `connect to the
database`, drop `both of them all`) and add **reuse** and **bounded concurrency**: a pool keeps a limited set
of reusable connections, cutting setup cost and preventing an uncontrolled number of connections.

Strong spoken answer:

> "A database connection pool maintains a limited set of reusable database connections. APIs and workers
> borrow a connection to run queries and return it afterward. This reduces connection setup cost and prevents
> the application from opening an uncontrolled number of connections."

## Intermediate: why is an `idle in transaction` connection dangerous?

Student answer (actual):

> "it means transaction don't commit,long transaction meade legacy snapchat increase.vacuum can't recycle trash"

Correction: the technical core is right; fix `legacy snapchat` -> **old MVCC snapshot** and `trash` -> **dead
tuples**, and add the connection/lock risk. An idle-in-transaction connection holds a connection, can retain
locks, and keeps an old snapshot alive so Vacuum cannot reclaim dead tuples.

Strong spoken answer:

> "An idle-in-transaction connection has an open transaction but is doing no work. It can occupy a
> connection, retain locks, and keep an old MVCC snapshot alive, which prevents Vacuum from reclaiming dead
> tuples. I keep transactions short, commit or roll back on every code path, set
> `idle_in_transaction_session_timeout`, and monitor the oldest transaction."

## Senior: contain the 420-vs-300 connection incident

Student answer (actual):

> "我不知道"

The complete incident-containment answer was taught immediately, and is the model answer:

> "First, stop further scaling and reduce new traffic so connection demand does not keep growing. Then roll
> back the excessive pool configuration through a gradual rollout, while letting Workers with in-flight model
> calls drain safely. I would not restart every Worker or blindly raise `max_connections`, because that could
> create a reconnection storm or move the bottleneck into PostgreSQL. The rollback target is the
> connection-pool configuration, not the completed Provider calls; external side effects must be reconciled
> using idempotency keys and deterministic Artifact identifiers. Finally, I verify connection pressure,
> transaction age, lock waits, and business-operation recovery before declaring the incident resolved."

Key vocabulary: `connection pool`, `aggregate demand`, `safe connection budget`, `short transaction`,
`idle in transaction`, `lock_timeout` / `statement_timeout` / `idle_in_transaction_session_timeout`,
`liveness` / `readiness`, `MVCC` / `dead tuples` / `autovacuum`, `least privilege`, `credential rotation`,
`replication is not backup`, `base backup` / `WAL` / `PITR`, `RPO` / `RTO`, `split-brain`, `reconciliation`.

---

# Mental Model Summary

```text
1. Reachable / low-CPU is NOT reliable; business ops depend on bounded capacity, not CPU.
2. Sum EVERY process's pool + reserve < safe connection budget < max_connections; a pool max is potential demand.
3. Raising pools moves queuing INTO PostgreSQL; more pool is not more capacity.
4. The 8-minute Provider call runs OUTSIDE the DB transaction: Accept / Claim-Start / External / Complete; Complete guards job_status='running' AND current lease_token AND lease_expires_at > now() (not the token alone).
5. Provider success != Artifact bytes != committed PostgreSQL success; reconcile the deterministic Artifact first.
6. queued->running is in Claim/Start; running->succeeded is in Complete; Accept only creates queued.
7. Lease expiry = takeover ELIGIBILITY, not proof the old Worker did no external work; keep idempotency + reconciliation.
8. Timeouts CONTAIN failure: lock_timeout < statement_timeout < application deadline; SKIP LOCKED is claim selection.
9. idle_in_transaction_session_timeout kills stuck open transactions; pool acquisition timeout bounds getting a connection.
10. Liveness = restart-fixes-local? Readiness = safe for new traffic? Business success = a real operation.
11. A shared DB outage DROPS READINESS + backs off; it must NOT fail every liveness (restart storm).
12. Long/idle txns retain snapshots -> block Vacuum -> dead-tuple bloat; fix the source first, tune autovacuum per-table on evidence, no casual VACUUM FULL.
13. Runtime identities cannot DDL; rotate credentials load-new -> verify-all -> recycle -> revoke-old.
14. Replication is NOT backup (it copies bad writes); recovery EVIDENCE = isolated restore + PITR + integrity/business checks + measured RPO/RTO.
15. RPO/RTO are recovery objectives, not health probes; promote a lagging replica only with a replay position + explicit RPO decision + split-brain prevention.
16. In the 420-vs-300 incident: contain demand + roll back the POOL CONFIG; reconcile irreversible Provider effects; resize the DB only on evidence.
```

First final Chinese synthesis (student, verbatim):

> "设置合理的最大数据库连接池，设置长事物连接超时，避免旧快照继续存在，vacuum进行死元祖的回收。给予最低安全权限，通过RPO与RTO进行健康检查，备份恢复要结合基础备份与wal。"

Accepted revised final Chinese synthesis (student, verbatim):

> "设置合理的PostgreSQL 安全连接预算要大于API 实例池 + Worker 实例池 + 其他客户端，设置长事物连接超时，避免旧快照继续存在，vacuum进行死元祖的回收。给予最低安全权限，通过Liveness：重启实例是否可能解决本地故障与Readiness：当前实例是否适合接收新流量两个是进行健康检查的指标，RPO = 最多允许丢失多少数据 RTO = 最多允许花多少时间恢复是恢复的指标，备份恢复要结合基础备份与wal完成隔离恢复、PITR 和业务验证，才能形成恢复证据。复制副本也不能替代备份，监控连接等待、慢查询、锁与死锁、最老事务、dead tuples、磁盘/WAL、复制延迟，以及备份和恢复演练证据。"

Targeted correction between the two passes (Tech Lead):

The **first** synthesis used RPO/RTO as health-check indicators. The correction — carried into the accepted
**revised** synthesis — is that **liveness/readiness are runtime health boundaries** while **RPO/RTO are
recovery objectives**, and that recovery evidence requires isolated restore + PITR + business validation, not
just base backup + WAL. The revised synthesis also correctly reframes the connection model as a **safe
connection budget greater than the sum of the instance pools plus other clients**.

---

# Today's Takeaway

Day36 made the schema deployable; Day37 keeps it alive in production. The lesson opens on the trap that fools
everyone — a slowing system at low CPU — and the fix is a set of boundaries, not a single dial. Bound
connections to the aggregate demand across every process plus reserve; keep the eight-minute Provider call
outside the transaction; point the right timeout at each wait; drop readiness (not liveness) when a shared
dependency fails; remove the long transaction before you tune Vacuum; give the runtime role no DDL; and treat
recovery as **evidence** — an isolated restore that actually passes business checks — not a green backup job.

The hard truths are about honesty. Low CPU is not health. A pool maximum is potential demand, not opened
connections. Replication is not backup. A successful backup job is not recoverability. And PostgreSQL cannot
roll back a Provider charge or Object Storage bytes — external effects are reconciled with idempotency and
deterministic keys, never undone by a configuration rollback.

Everything here is design and reasoning. Nothing was executed — no server, pool, Vacuum, restore, or
promotion — and the runbook is labelled that way. Day38 adds Redis as transient acceleration, judged for
correctness against exactly this durable, recoverable PostgreSQL truth.

---

# Before Next Lesson Checklist

- [ ] I can explain why a reachable, low-CPU database is not necessarily reliable.
- [ ] I can size pools by aggregate demand across processes and keep demand under the safe budget.
- [ ] I can place the eight-minute Provider call outside the transaction and name the four boundaries.
- [ ] I can distinguish Provider success, Artifact bytes, and committed PostgreSQL success, and reconcile first.
- [ ] I can map each timeout to its scope and order `lock_timeout < statement_timeout < deadline`.
- [ ] I can separate liveness, readiness, and business success and avoid a shared-outage restart storm.
- [ ] I can explain MVCC dead tuples, remove the long transaction first, and tune autovacuum per-table on evidence.
- [ ] I can design least-privilege roles and a safe credential-rotation order.
- [ ] I can explain why replication is not backup and reconstruct base backup + WAL -> PITR.
- [ ] I can state what recoverability evidence requires beyond a successful backup job.
- [ ] I can contain the 420-vs-300 incident and name the rollback target vs the irreversible external effects.

Preparation for Day38 (Redis Foundations and Data Structures):

- [ ] Re-read `projects/ai-backend-data-layer/runbooks/postgresql-production-reliability.md` and note the boundary that PostgreSQL stays the durable, recoverable Job source of truth.
- [ ] Note that Redis is transient acceleration/messaging/coordination — not the authoritative Job lifecycle.
- [ ] Be ready to judge Redis use (ephemeral progress, cache, broker transport, rate-limit counters) against the durable PostgreSQL truth, not as a replacement for it.
- [ ] Keep SQLAlchemy/Alembic (Phase 4) out of scope.
