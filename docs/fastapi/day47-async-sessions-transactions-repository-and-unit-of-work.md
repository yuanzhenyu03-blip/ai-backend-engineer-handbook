# Lesson 47 — Async Sessions, Transactions, Repository and Unit of Work

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day46 — SQLAlchemy 2.0 Mapping for the Day42 Data Model

Previous Lesson: [Day46 — SQLAlchemy 2.0 Mapping for the Day42 Data Model](day46-sqlalchemy-mapping-for-the-day42-data-model.md)

Next Lesson: Day48 — Alembic and Safe AI Backend Schema Evolution (planned — Phase 4; see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day48 lesson file does not exist yet)

Phase: Phase 4 — Production AI API Engineering

Engineering Artifact: The Day47 async persistence boundary ([`projects/ai-backend-data-layer/api/day47-async-persistence-boundary-design.md`](../../projects/ai-backend-data-layer/api/day47-async-persistence-boundary-design.md)) with runnable code [`day47_async_uow.py`](../../projects/ai-backend-data-layer/api/day47_async_uow.py) and fake-session tests [`test_day47_async_uow.py`](../../projects/ai-backend-data-layer/api/test_day47_async_uow.py) — process-scoped `AsyncEngine`/`async_sessionmaker` helpers, a request/Job-scoped `AsyncSession`, repositories, a `UnitOfWork` with explicit commit/rollback/close, the guarded `UPDATE ... WHERE job_status='queued' RETURNING` claim, flush-before-dependent-write, a second guarded completion UoW, and a fake Provider seam. Fake-session control-flow tests were executed (23 passed; Python 3.10.12, SQLAlchemy 2.0.29, greenlet 3.5.4, pytest 7.4.3); **PostgreSQL runtime is NOT RUN** (no server/driver) — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

FastAPI Cheat Sheet: [cheat_sheets/fastapi.md](../../cheat_sheets/fastapi.md)

FastAPI Interview: [interview/fastapi.md](../../interview/fastapi.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises + running the tests: 100-130 minutes
Hands-on UoW/transaction design: 90-120 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Explain why an `AsyncSession` cannot be a global shared object and how process-scoped Engine/factory differ from a request/Job-scoped Session.
2. Assign commit/rollback/close ownership to the Unit of Work, and keep repositories free of commit/close.
3. Choose explicit `await uow.commit()` over silent auto-commit and explain why.
4. Implement a guarded `UPDATE ... WHERE job_status='queued' RETURNING` claim and treat a zero-row result as a normal stale/no-op, not a database error.
5. Distinguish `flush` from `commit`, including cross-session visibility, and use flush to obtain a server-generated id for a dependent write.
6. Explain that an `IntegrityError` aborts the current transaction (integrity protected, not broken) and requires rollback.
7. Treat a commit exception as an unknown outcome — roll back/close local state and reload durable truth by stable id rather than replaying.
8. Keep a long/paid Provider call outside any DB transaction, and commit an application-generated correlation/idempotency key before it.
9. Run completion as a second short guarded UoW, and distinguish guarded completion (concurrency) from the `finished_at` CHECK (state invariant).
10. Classify a definitive Provider failure as `failed` and a timeout with unknown remote outcome as a first-class recovery state (never blindly requeue).
11. Avoid detached-ORM lazy loading by building an allowlisted Pydantic DTO inside the UoW, and distinguish mock, PostgreSQL-runtime, and SQLite evidence.

---

# Why This Matters

Day46 mapped the Day42 durable contract into SQLAlchemy models but deliberately created **no** Engine, Session,
transaction, repository, or Unit of Work — its only evidence was static metadata tests. Day47 supplies that
missing **runtime persistence boundary**: how a real request or Worker Job opens a database transaction, does a
small amount of work, and commits or rolls back — safely, under concurrency, and around an external AI-Provider
call that must **not** live inside a database transaction.

The central risk this lesson removes is treating the database Session like a stateless helper and the Provider
call like ordinary database work. An `AsyncSession` carries an identity map, pending changes, and transaction
context; sharing it across concurrent Jobs corrupts state. And a Provider call that takes minutes, held inside
an open transaction, exhausts the connection pool and still cannot make the Provider's execution, charges, or
network side effects roll back with PostgreSQL. So Day47 draws two short transactions around the long external
call: a guarded **start** UoW (claim → Attempt → `job_started`) that commits durable correlation evidence
**before** the call, and a guarded **completion** UoW (terminal state + Artifact reference + `job_succeeded`)
**after** it — with a zero-row guard treated as a normal stale/no-op, and an unknown outcome treated as a
first-class recovery state.

This lesson has **real fake-session evidence**: **23 control-flow tests passed** (Python 3.10.12, SQLAlchemy
2.0.29, greenlet 3.5.4, pytest 7.4.3) proving the UoW/repository code paths — explicit commit, rollback+close on
failure, stale/no-op handling, flush-before-write, repos never commit. But a **mock is not database proof**:
**PostgreSQL runtime is NOT RUN** (no server/driver available), and SQLite would not be valid evidence for this
`app`-schema, PostgreSQL-typed contract. FastAPI/Worker integration, real Provider, Object Storage, and
production are all **NOT RUN**.

---

# Roadmap Position

```text
Day33 raw-SQL atomic Job/Attempt/Event state changes
Day46 faithful SQLAlchemy mapping of the Day42 durable contract
Day47 async sessions, transactions, repository and unit of work   <-- you are here
Day48 Alembic safe schema evolution (Expand -> Backfill -> Validate -> Switch -> Contract)
Day49 UploadSession/Artifact persistence with Object Storage I/O OUTSIDE the transaction
Day50 idempotent Job acceptance + Outbox over this same transactional boundary
```

Knowledge continuity:

```text
Previous knowledge
  Day33 atomic guarded state changes; Day46 mapping (app schema, server defaults, TEXT+CHECK, RESTRICT, composite
  provenance) with NO runtime; Day45 process-vs-request scope discipline
        |
        v
Current lesson
  drive the mapping through ONE process-owned Engine, a request/Job-owned AsyncSession, short transactions,
  repositories, and a Unit of Work; keep long Provider/Object-Storage work OUTSIDE the transaction and recover
  unknown outcomes through a new guarded UoW
        |
        v
Future production usage
  Day48 evolves the schema safely on top of known Engine/session/repository boundaries; Day49 persists verified
  upload/artifact references in a new guarded UoW without holding a transaction over Object Storage I/O; Day50
  uses this boundary for idempotent Job acceptance + Outbox integration
```

Day47 does **not** implement Alembic (Day48), the Day49 upload workflow, or the Day50 acceptance/Outbox
workflow, and it runs no real Provider/Object-Storage/integration/production. They are named only as future
connections.

---

# Lesson Map

```text
1.  Scope/ownership            -> process Engine + factory; request/Job Session; no global AsyncSession
2.  Repository vs UoW commit    -> repos express DB ops; the UoW alone commits/rolls back/closes
3.  Explicit commit             -> await uow.commit(); no silent auto-commit
4.  Guarded claim               -> UPDATE ... WHERE queued RETURNING; zero rows = stale/no-op, not an error
5.  Flush vs commit             -> flush executes SQL in the tx (no cross-session visibility); commit is durable
6.  IntegrityError              -> tx aborted (integrity protected), must roll back before reuse
7.  Commit exception            -> unknown outcome; roll back/close, reload by stable id, don't replay
8.  Short tx vs Provider call    -> long/paid call OUTSIDE the transaction
9.  Correlation key first        -> commit an app-generated idempotency key BEFORE the call
10. Guarded completion           -> a second short UoW; guard (concurrency) != finished_at CHECK (state)
11. Failure vs unknown outcome   -> definitive -> failed; timeout/unknown -> recover, never blind retry
12. Detached reads -> DTO        -> build an allowlisted Pydantic DTO inside the UoW
13. Evidence levels              -> mock != PostgreSQL runtime; SQLite != PostgreSQL evidence
```

---

# Core Mental Model

```text
One process owns ONE Engine + a session factory. Each request/Job gets a FRESH Unit of Work = one isolated
AsyncSession + repositories. The UoW runs ONE short transaction and EXPLICITLY commits only a complete fact set;
otherwise it rolls back pending work and closes the Session. The long/paid Provider call happens BETWEEN two
short UoWs, never inside one.

  AsyncEngine (process)  ->  async_sessionmaker (process)  ->  UnitOfWork(request/Job) { one AsyncSession + repos }

  UoW 1 (short, guarded):  UPDATE ... WHERE job_id AND tenant_id AND job_status='queued' RETURNING  (1=claimed / 0=stale-noop)
                           -> Attempt 1  -> flush  -> job_started Event (carries the app correlation key in metadata)  -> COMMIT
                                              |
                                              v
              Provider call OUTSIDE any DB transaction  (success / definitive failure / UNKNOWN)
                                              |
                                              v
  UoW 2 (short, guarded, Day33 atomic completion pack, ONE commit):
      finish Attempt (SET finished_at, provider_request_id, cost_micros WHERE finished_at IS NULL RETURNING; 0=stale-noop, never overwrite a finished Attempt)
      -> guarded Job running->succeeded (WHERE job_id AND tenant_id AND job_status='running' RETURNING; 0=stale-noop incl. wrong tenant, no Artifact/Event)
      -> ResultArtifact reference (Object Storage key, NOT bytes) -> job_succeeded Event -> COMMIT
      (any step fails -> rollback the WHOLE UoW; no partial durable state)

  flush != commit (no cross-session visibility). IntegrityError aborts the tx -> rollback. commit exception =
  UNKNOWN outcome -> roll back/close, reload by id. Repos never commit. Build a Day44 DTO INSIDE the UoW.
  code rollback != durable-data rollback != external-side-effect rollback.
```

---

# Main Concepts

## Concept 1: An AsyncSession cannot be global

### Tech Lead Question

Can a single `AsyncSession` be a global object shared across concurrent Jobs? Where do the Engine, the factory,
and the Session each live?

### Student Thinking

The student reasoned about shared mutable Session state across Jobs and about per-request UoW creation and
per-process Engines.

### Student Answer

> "AsyncSession不能被共享，因为可能job之间的状态会互相污染"

> "request 创建一个新的 Uow,一个uow就是一个session"

> (API/Worker Engines) "各自创建实例" · "在 API lifespan / Worker startup 的显式 composition root 中创建"

### Tech Lead Review

Correct throughout. An `AsyncSession` carries **identity-map, pending-change, and transaction context**, so it
**cannot safely serve concurrent Jobs** — sharing it lets Jobs pollute each other's state. The right scoping:
the **`AsyncEngine` is process-scoped** (API and Worker are separate processes, each owning its own Engine and
connection pool through its own lifespan / Worker startup composition root — one Engine per **process**, not one
per deployment), the **`async_sessionmaker` is process-scoped** and creates a **new** `AsyncSession` on demand,
and each request/Job gets a **fresh UoW with one Session**. The same **factory** is shared, never the same
Session. One clarification on "一个 uow 就是一个 session": yes — one UoW owns exactly one Session for its lifetime;
the factory is a Session **producer**, not a shared batch of live Sessions.

### Engineering Thinking

Match lifetime to scope: expensive, poolable infrastructure (Engine, factory) is created once per process; the
stateful, single-threaded-by-nature Session is created fresh per unit of work.

### Production Example

Eight Worker replicas each build their own Engine at startup; each claimed Job gets its own UoW/Session, so 200
concurrent Jobs never share one Session's identity map.

### Framework Connection

`create_async_engine` (process), `async_sessionmaker(engine, expire_on_commit=False)` (process), a fresh
`AsyncSession` per UoW; FastAPI dependency / Worker orchestration creates one UoW per request/Job.

## Concept 2: Repository expresses; the Unit of Work decides commit

### Tech Lead Question

Job → Attempt → Event is one atomic set. If the third insert fails, who rolls back — the repository, or an outer
owner? Who injects the Session?

### Student Answer

> "这是一个原子事务，既然第三个失败了应该是回滚整个事务，我觉得应该是Unit of Work外层统一决定"

> (who gives the repo its Session?) "由 Unit of Work 把同一个 Session 注入给它"

### Tech Lead Review

Exactly right. The three writes are **one atomic transaction**; if any step fails, the **UoW** (the outer owner)
rolls back **all** uncommitted work — a repository must **not** commit after one substep (if Attempt creation
succeeds but Event insertion fails, committing mid-way would persist a partial fact set). Repositories **receive
the single Session injected by the UoW** and express database operations only; they do **not** create
Engines/Sessions and do **not** call commit or close. Atomicity comes from the UoW's **one transaction + one
explicit commit**, not from repositories committing independently.

### Engineering Thinking

Separate "what database operation" (repository) from "when the durable decision is made" (UoW). One owner of the
transaction boundary means one place to reason about atomicity.

### Production Example

`uow.jobs`, `uow.attempts`, `uow.events` all share `uow.session`; only `await uow.commit()` makes the set
durable, and any exception rolls the whole set back.

### Framework Connection

Repositories take an `AsyncSession` in their constructor; `UnitOfWork` owns the Session and exposes the repos.

## Concept 3: Explicit commit, not silent auto-commit

### Tech Lead Question

Should the UoW auto-commit when its context exits normally, or require an explicit commit? What must the UoW
guarantee on exit?

### Student Answer

> "await uow.commit()，uow可能不会自动commit"

> (what the UoW guarantees) "保证session关闭，以及事务原子性保证没有部分产出"

### Tech Lead Review

Correct — **explicit `await uow.commit()`**, chosen over silent auto-commit on normal context exit. This keeps
the durable decision **reviewable** and prevents a normal branch — such as a **failed/stale claim** — from
**accidentally committing** work. And the UoW's guarantees on exit are exactly as stated: it **always closes the
Session**, and it preserves atomicity so there is **no partial output** — on any exception or any exit **without
an explicit commit**, it rolls back pending work first, then closes.

### Engineering Thinking

Durable writes should be a deliberate statement in the code, not a side effect of leaving a block. Explicitness
is what makes "we did not claim, so we committed nothing" true by construction.

### Production Example

A stale-claim branch returns early without calling `commit()`; the UoW's `__aexit__` rolls back the empty
transaction and closes — nothing is persisted.

### Framework Connection

`UnitOfWork.__aexit__` rolls back if `exc` or not `self._committed`, then `await session.close()`.

## Concept 4: The guarded claim — `UPDATE ... RETURNING`, and zero rows is normal

### Tech Lead Question

How do you claim a queued Job without a race — SELECT-then-UPDATE or a single guarded UPDATE? And what does zero
rows returned mean?

### Student Thinking

The student first treated a zero-row claim as something to roll back, then reframed it as a normal outcome, and
chose a single-statement guarded update.

### Student Answer

> (why a single guarded UPDATE) "因为最好放在一条命令执行"

> (zero-row claim, initial) "我觉得应该直接直接 rollback"

> (zero-row claim, corrected) "正常的 stale/no-op 结果"

### Tech Lead Review

The guarded claim is a **single** `UPDATE app.jobs SET job_status='running' WHERE job_id=:id AND
tenant_id=:tenant_id AND job_status='queued' RETURNING job_id` — **not** SELECT-then-UPDATE, which races (two
Workers could both read `queued` and both proceed). Note the **`tenant_id` predicate**: every guarded `app.jobs`
mutation (claim, complete, fail) carries `tenant_id` as a **required durable ownership predicate** (Day42/Day46)
— it is **trusted context passed from the orchestration, never derived from the `job_id`** (a `job_id` alone is
not an authorization boundary), so a wrong tenant simply matches **0 rows** and claims nothing. This is the
existing durable tenant predicate, not Day52 authentication/authorization. "放在一条命令执行" is the right instinct: one atomic statement, and **one returned row
means this Worker claimed the Job**. The correction on zero rows is the key learning: **zero returned rows is a
normal stale/no-op** — another Worker already changed the state — so this Worker must **not** create
Attempt/Event and must **not** treat it as a retryable database failure or an endless DB retry. Rolling back /
ending the empty UoW is harmless, but the **business meaning is stale/no-op**, not an error.

### Engineering Thinking

Make the winner unambiguous at the database level (one row returned = one winner), and give the losing path a
clear, boring meaning (nothing to do) rather than an error to retry.

### Production Example

Two Workers race for the same queued Job; the guarded UPDATE returns one row to the winner and zero to the
loser, who quietly stops — no duplicate Attempt.

### Framework Connection

`JobRepository.guarded_claim` returns the RETURNING row count; `start_job` returns `ClaimOutcome.STALE_NOOP`
when it is zero.

## Concept 5: Flush is not commit

### Tech Lead Question

After creating an Attempt, how do you get its server-generated id to write a dependent Event — without
committing? Can another Session see that row yet?

### Student Answer

> (how) "flush，因为没有提交为数据库事实"

> (cross-session visibility) "不可以，因为没有成为数据库事实"

### Tech Lead Review

Correct. `await session.flush()` makes the SQL **execute in the current transaction**, so the
**server-generated `attempt_id`** becomes available to write the dependent Event — **without committing**. And
it is **not** yet visible to other Sessions: a flushed-but-uncommitted row is not a durable committed fact, so
another Session cannot see it. Flush moves work into the transaction; **commit** is what makes it durable and
visible.

### Engineering Thinking

Flush and commit are different points on the same transaction: flush = "run the SQL now (get ids, trigger
constraints)"; commit = "make it durable and visible." Using flush lets you build a dependent graph atomically
before the single commit.

### Production Example

Attempt is added and flushed to get `attempt_id`; the `job_started` Event references it; both become durable
together at `await uow.commit()`.

### Framework Connection

`AttemptRepository.create` calls `session.add(...)` then `await session.flush()`; the Event uses
`attempt.attempt_id`.

## Concept 6: IntegrityError aborts the transaction (integrity is protected, not broken)

### Tech Lead Question

A flush raises `IntegrityError`. Can the Session keep working in the same transaction? Does this mean durable
integrity is broken?

### Student Answer

> "不能，表示事务的完整性有问题"

### Tech Lead Review

Half right, with an important reframing. You are correct that the Session **cannot continue normally** — after
an `IntegrityError` during flush, **PostgreSQL has aborted the current transaction**, and it must be **rolled
back** before the Session can do normal work again. But it does **not** mean "事务的完整性有问题" in the sense of
durable integrity being broken — the opposite: PostgreSQL **correctly rejected an illegal write**. That is the
database **protecting** integrity, not integrity failing. The fix is a rollback (then the Session is usable
again), not a conclusion that the data is corrupt.

### Engineering Thinking

A rejected write is the constraint doing its job. Treat `IntegrityError` as "the DB refused an illegal change;
roll back and decide," not as "the database is damaged."

### Production Example

A duplicate `(tenant_id, idempotency_key)` insert raises `IntegrityError`; the transaction aborts, the UoW rolls
back, and the caller re-reads the existing Job by its business key.

### Framework Connection

SQLAlchemy raises `IntegrityError` on the PostgreSQL constraint violation; the UoW's rollback restores a usable
Session.

## Concept 7: A commit exception is an unknown outcome

### Tech Lead Question

`await uow.commit()` raises. What do you do — and why can't you just assume it failed? Why re-open a new Session
to re-read?

### Student Thinking

The student's first instinct was to roll back and close, then recognized the outcome may be unknown and that the
old Session may hold stale in-memory objects.

### Student Answer

> (commit error) "uow回滚事务，关闭session"

> (why a new Session to reload) "因为原 Session 可能仍保留 identity map 中的内存对象"

### Tech Lead Review

Rolling back and closing local state is right, but the crucial nuance is that a **commit exception can be an
unknown commit outcome**: the database **may have committed** before the network response was lost. So you
cannot assume it failed. Roll back/close the **local** state, then **reload durable truth by a stable
identifier** rather than blindly replaying the write — and the student's reason for a **new** Session is exactly
right: the original Session may still hold **stale in-memory objects in its identity map**, so a fresh Session is
needed to read the actual committed truth.

### Engineering Thinking

"The commit call raised" ≠ "the commit did not happen." Recover by observing durable state through a clean
Session, not by re-issuing a write that might duplicate a committed one.

### Production Example

A commit times out at the network layer after PostgreSQL committed; a new Session reads the Job by id, sees it
is already `running` with Attempt 1, and does not create a second Attempt.

### Framework Connection

`UnitOfWork.commit` propagates the exception; `__aexit__` still rolls back and closes; recovery opens a new UoW
and re-reads by id.

## Concept 8: Short DB transactions vs the long Provider call

### Tech Lead Question

The Provider call may take minutes. Can it happen inside the open database transaction?

### Student Answer

> "不能，因为数据库事务无法控制外部调用"

### Tech Lead Review

Correct. A Provider call that may take minutes must remain **outside** any open database transaction. Holding a
DB transaction across it **exhausts connections** and — the deeper reason the student named — the **database
transaction cannot control the external call**: it cannot make the Provider's execution, its charges, its
network results, or its side effects roll back with PostgreSQL. So the pattern is two **short** transactions (a
guarded start UoW and a guarded completion UoW) with the long call **between** them, holding no connection.

### Engineering Thinking

A transaction's power ends at the database boundary. Keep transactions short and local; treat the external world
as something you record evidence about, not something you can atomically undo.

### Production Example

A Worker commits `running` + Attempt, closes the transaction, calls the Provider for 4 minutes holding no DB
connection, then opens a fresh UoW to record the result.

### Framework Connection

`start_job` commits and closes UoW 1 before any Provider call; `complete_job` is a separate UoW after it.

## Concept 9: Commit correlation evidence before the irreversible call

### Tech Lead Question

When do you persist the identity you will use to recover this Provider call — after you get the Provider's
request ID?

### Student Thinking

The student first chose to persist the Provider's request ID after the response, then accepted committing an
application-generated key beforehand.

### Student Answer

> "获得 Provider 响应后"

### Tech Lead Review

This is the correction. Persisting **only** the Provider-returned request ID is **too late for recovery**: a
crash can occur **after** the remote call begins but **before** the response (and its request ID) is persisted.
So **before** the irreversible Provider call, commit a durable **Attempt** plus an **application-generated
correlation/idempotency key**. Because Day46 defines **no** correlation column on `JobAttempt` (and Day47 invents
none), that key is written into the **`job_started` Event metadata** by the higher-level start flow in the same
UoW — `AttemptRepository.create()` does **not** accept or persist it. The Provider's own request ID is persisted
**later**, when available, as **additional** evidence — but it cannot be the **only** recovery identity.

### Engineering Thinking

You must own a recovery identity that exists **before** the side effect. An id you only learn from the response
is worthless if you never receive the response.

### Production Example

The Attempt commits with `correlation_key = "corr-…"` before the call; after a lost response, recovery queries
the Provider by that key to learn whether the call actually ran.

### Framework Connection

`AttemptRepository.create(..., correlation_key=...)` committed in UoW 1; `provider_request_id` filled later.

## Concept 10: Guarded completion is concurrency control, not the `finished_at` CHECK

### Tech Lead Question

Why is completion "guarded"? Isn't the Day46 rule just "succeeded means `finished_at` is not NULL"?

### Student Answer

> "只要成功finished_at就不能为null"

### Tech Lead Review

That Day46 CHECK (`jobs_succeeded_has_finished_at`) is a **state invariant** — it protects a single row's legal
shape. **Guarded completion is different**: it protects **ownership/concurrency**, allowing **exactly one
still-valid running Attempt/Job** to record terminal facts and treating **later writers as stale/no-op**.
Completion is a **second short guarded UoW** that persists the **Day33 atomic completion pack** in **one
commit**: (1) a **guarded finish of the Attempt** — `UPDATE app.job_attempts SET finished_at=now(),
provider_request_id=:prid, cost_micros=:cost WHERE attempt_id AND job_id AND finished_at IS NULL RETURNING` —
which records the **available Provider evidence** (`provider_request_id`, `cost_micros`) in the **same** guarded
statement (either may be `None` when not yet known — written as NULL, which does **not** assert a verified
value), and where **zero rows** (missing / wrong Job / **already finished**) means **roll back and stop**, never
overwriting a finished Attempt's outcome; (2) the **guarded, tenant-scoped `running -> succeeded` Job
transition** (`WHERE job_id AND tenant_id AND job_status='running'`; zero rows — not running **or wrong tenant**
— roll back, write **no** Artifact and **no** success Event);
(3) the **ResultArtifact** durable reference (Day46 mapping — an Object Storage key, **never** bytes); and (4)
the **job_succeeded Event**. If the Artifact insert or the Event append fails, the **whole UoW rolls back** —
no partial PostgreSQL durable state — and the external Artifact bytes are **not** part of the transaction (a DB
rollback does not delete the external object). A **zero-row** guard at either step is a **normal stale/no-op** —
do **not** overwrite or duplicate Event/Artifact facts. The CHECK says "this row is shaped legally"; the guard says
"only the rightful, still-running writer may finish this Job."

### Engineering Thinking

State invariants and concurrency control answer different questions ("is this row legal?" vs "is this writer
still the owner?"). You need both; one does not replace the other.

### Production Example

A slow first Worker and a recovery Worker both try to complete; the guarded UPDATE gives one row to whichever is
still `running` and zero to the other, which quietly stops.

### Framework Connection

`JobRepository.guarded_complete` guards on `job_status='running' RETURNING`; `complete_job` returns
`CompletionOutcome.STALE_NOOP` on zero rows.

## Concept 11: Definitive failure vs unknown outcome

### Tech Lead Question

A Provider returns a definitive 401 vs a timeout with unknown remote execution. What state does each become? May
you blindly retry?

### Student Answer

> (definitive failure) "记录 failed"

> (timeout/unknown) "保留为待恢复的未知状态"

> (blind Provider retry) "不能，多出成本开销"

### Tech Lead Review

All correct. A **definitive, non-retryable** failure (for example a 401 or a rejected request) becomes
**`failed`**. A **timeout with unknown remote execution** stays **unknown/recoverable** — a first-class recovery
state, not `failed` and not `succeeded`. And you must **never blindly requeue or call the Provider again**: as
the student noted, it adds **cost**, and — extending that — it risks **duplicate side effects** because the
first call may already have executed (and charged). Unknown means local code cannot prove what the remote system
did, including the case where the Provider completed and charged but the Worker lost the response.

### Engineering Thinking

Encode "we don't know" as its own state. Collapsing unknown into failed (or retrying it into success) either
loses a completed result or double-spends on a paid call.

### Production Example

A 4-minute call times out; the Job is left in an unknown/recovery state, and a recovery UoW later verifies via
the correlation key before deciding — no second paid call is issued blindly.

### Framework Connection

`JobRepository.mark_failed` (guarded) for definitive failures; `ProviderUnknownOutcome` models the recovery
state; `FakeProvider(raises=...)` exercises both in tests.

## Concept 12: Detached ORM reads → build a DTO inside the UoW

### Tech Lead Question

After the UoW closes, can response serialization lazily load a relation from the returned ORM object because it
is "still in the identity map"?

### Student Thinking

The student first thought an in-identity-map object stays accessible, then accepted that an unloaded lazy
relation needs I/O and that a DTO should be built inside the UoW.

### Student Answer

> (lazy access after close, initial) "还是可以访问到，因可能还在 identity map 中"

> (the fix) "UoW 内显式构造一个只包含允许字段的 Pydantic response/DTO"

### Tech Lead Review

The correction: already-**loaded** scalar attributes can remain in memory, but an **unloaded lazy relation needs
database I/O**, and after the Session closes the ORM object is **detached** — accessing that relation can raise
`DetachedInstanceError` (or `MissingGreenlet` in an invalid async I/O context). So do **not** return a detached
ORM object and let response serialization lazily load relations after UoW close. Instead, **explicitly load the
data you need inside the UoW** and build an **allowlisted Day44 Pydantic response/DTO** — which the student's
second answer states exactly. This also reuses the Day44/Day46 rule that public models stay separate from
persistence models.

### Engineering Thinking

The Session's lifetime bounds safe ORM access. Cross that boundary with plain data (a DTO), not with a live
object that still expects a database behind it.

### Production Example

`GET /jobs/{id}` loads the fields it needs inside the UoW, builds a small `JobStatusResponse` DTO, and returns
that — no lazy load fires during serialization after the Session closed.

### Framework Connection

Build a Day44 Pydantic DTO inside the UoW (optionally `expire_on_commit=False` for already-loaded fields); never
serialize a detached ORM object.

## Concept 13: Evidence — mock vs PostgreSQL runtime vs SQLite

### Tech Lead Question

A test mocks the Session and asserts `rollback()` was called. Does that prove the database rolled back? Is SQLite
acceptable evidence here? And how would you prove real rollback?

### Student Answer

> (SQLite / mock rollback as DB proof) "不能"

> (what a rollback test does) "数据库事务进行回滚，session断开"

### Tech Lead Review

Correct. A mock that asserts `rollback()` was called proves only **code-path intent**, not database behavior. A
**PostgreSQL runtime test** must use a **new Session after failure** and prove **committed truth**: the Job
**remains queued** and **no Attempt/Event remains**. And **SQLite is not PostgreSQL runtime evidence** for this
system, because the contract uses the **`app` schema**, PostgreSQL **types/defaults/constraints**, and
PostgreSQL **transaction/concurrency** behavior. The student's description of a rollback test — the transaction
rolls back and the Session disconnects — is the shape; the proof is re-reading durable truth through a fresh
Session. In this repository the Day47 tests are **fake-session** control-flow tests, and **PostgreSQL runtime is
NOT RUN** (no server/driver), stated honestly rather than faked.

### Engineering Thinking

Evidence must match the claim. "The code called rollback" and "the database has no partial rows" are different
statements; only a real PostgreSQL read proves the second.

### Production Example

The integrated recovery exercise: after UoW 2 crashes pre-commit, a fresh Session shows only UoW 1's committed
facts (running + Attempt + `job_started`) — the succeeded state, ResultArtifact reference, and completion Event
are absent, even though the external Artifact may exist.

### Framework Connection

Fake-session unit tests (executed here) vs an isolated PostgreSQL runtime test after applying the Day42 raw SQL
(NOT RUN); SQLite explicitly excluded.

---

# Common Misconceptions

Global AsyncSession

❌ "Share one `AsyncSession` across concurrent Jobs."
✅ A Session carries identity-map/pending-change/transaction state; use a fresh Session per UoW. Only the
Engine/factory are process-scoped.

Why beginners think this: a Session looks like a connection helper.
How to remember: one UoW = one Session; the factory is shared, not the Session.

Repository commits

❌ "Each repository commits its own step."
✅ Repositories express DB ops; the UoW owns commit/rollback/close. Atomicity is the UoW's one transaction.

Why beginners think this: the write happens in the repository.
How to remember: repos express, the UoW decides.

Auto-commit on exit

❌ "Let the UoW commit when the block exits."
✅ Explicit `await uow.commit()`; a normal/stale branch must be able to exit committing nothing.

Why beginners think this: exiting cleanly feels like success.
How to remember: commit is a statement, not a side effect of leaving.

Zero-row claim is an error

❌ "A guarded UPDATE returning zero rows is a failure to retry."
✅ Zero rows is a normal stale/no-op — another Worker changed the state; create no Attempt/Event, don't retry.

Why beginners think this: zero looks like failure.
How to remember: one row = winner; zero rows = nothing to do.

Flush is commit

❌ "Flush makes the row a durable, visible fact."
✅ Flush executes SQL in the current transaction (ids/constraints); commit makes it durable and cross-session
visible.

Why beginners think this: flush "sends it to the DB."
How to remember: flush = in the transaction; commit = durable + visible.

IntegrityError means corruption

❌ "An `IntegrityError` means durable integrity is broken."
✅ PostgreSQL correctly rejected an illegal write; the transaction is aborted and must be rolled back before reuse.

Why beginners think this: an error sounds like damage.
How to remember: the constraint did its job; roll back and decide.

Commit exception = commit failed

❌ "If `commit()` raised, the write did not happen."
✅ It may be unknown — the DB might have committed before the response was lost. Roll back/close, reload by id,
don't replay.

Why beginners think this: an exception means failure.
How to remember: raised ≠ not committed; re-read the truth.

Provider call inside the transaction

❌ "Wrap the Provider call in the DB transaction for consistency."
✅ Keep long/paid calls outside the transaction; the DB cannot roll back external execution/charges, and holding
a connection exhausts the pool.

Why beginners think this: one transaction feels safer.
How to remember: transactions end at the database boundary.

Provider request ID is enough for recovery

❌ "Persist the Provider's request ID after the response."
✅ Commit an application-generated correlation/idempotency key before the call; the Provider ID comes later and
can't be the only recovery identity.

Why beginners think this: the Provider gives you an id.
How to remember: own a recovery id before the side effect.

Unknown outcome = failed (or retry)

❌ "A timeout means failed — or just retry."
✅ Unknown is its own recovery state; never blindly requeue (cost + duplicate side effects). Verify by correlation.

Why beginners think this: no success means failure.
How to remember: "we don't know" is a state, not a retry.

Detached ORM is safe via identity map

❌ "A returned ORM object can lazy-load relations after close because it's cached."
✅ An unloaded lazy relation needs I/O; a detached object raises `DetachedInstanceError`. Build a DTO inside the
UoW.

Why beginners think this: loaded scalars persist in memory.
How to remember: cross the Session boundary with data, not live objects.

Mock/SQLite proves the database

❌ "A mocked `rollback()` (or a SQLite run) proves PostgreSQL behavior."
✅ A mock proves code-path intent; SQLite isn't this contract. Real proof re-reads committed truth via a new
PostgreSQL Session.

Why beginners think this: the test passed.
How to remember: evidence must match the claim.

---

# Engineering Trade-offs

## Explicit commit vs auto-commit-on-exit

Explicit commit keeps the durable decision reviewable and prevents accidental commits on normal/stale branches,
at the cost of one more line; auto-commit is terser but can persist a partial or unintended fact set. For a
durable Job boundary, commit explicitly.

## Guarded UPDATE ... RETURNING vs SELECT-then-UPDATE

The single guarded UPDATE is race-free and names one winner per returned row; SELECT-then-UPDATE reads and
writes in two steps and lets two Workers both proceed. For claiming/completing, use the guarded UPDATE.

## Two short transactions vs one long transaction across the Provider call

Two short transactions keep connections free and localize failure, at the cost of an unknown-outcome window that
needs correlation-based recovery; one long transaction is simpler to picture but exhausts the pool and still
cannot roll back external effects. Split the transactions.

## Commit correlation key before vs after the call

Committing an app-generated key first guarantees a recovery identity even if the response is lost, at the cost of
one extra pre-call commit; persisting only the Provider ID afterward is simpler but leaves a crash window with no
recovery identity. Commit the key first.

## DTO inside the UoW vs returning the ORM object

Building a DTO inside the UoW is safe after close and allowlists public fields, at the cost of explicit mapping;
returning the ORM object is less code but risks detached lazy loads and field leakage. Return a DTO.

## Fake-session tests vs PostgreSQL runtime tests

Fake-session tests are fast, deterministic, and need no server but prove only control flow; PostgreSQL runtime
tests prove real rollback/constraint/concurrency behavior but need a disposable server + async driver + the
applied Day42 SQL. Use fake-session tests as the baseline; add PostgreSQL runtime where DB behavior must be
proven (NOT RUN here).

---

# Hands-on Exercises

These map to the runnable artifact and its **fake-session** tests, which **were executed** (Python 3.10.12,
SQLAlchemy 2.0.29, greenlet 3.5.4, pytest 7.4.3 → **23 passed**; install via `requirements-day47.txt`). They
prove UoW/repository **control flow** only; a real **PostgreSQL runtime** rollback test is **NOT RUN** (no
server/driver), and SQLite is not valid evidence for this `app`-schema/PostgreSQL-typed contract.

Run the tests:

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day47.txt
python3 -m py_compile day47_async_uow.py test_day47_async_uow.py
python3 -m pytest -q test_day47_async_uow.py
```

### Exercise 1: Scope the Engine, factory, and Session

Question: which is process-scoped and which is request/Job-scoped?

Expected Output: Engine + `async_sessionmaker` = process; `AsyncSession` = request/Job (fresh per UoW); no global
Session.

Follow-up: why does one deployment with 8 processes have 8 Engines?

### Exercise 2: Who commits Job → Attempt → Event?

Question: the third insert fails — who rolls back?

Expected Output: the UoW (outer owner) rolls back all uncommitted work; repositories never commit.

Follow-up: what breaks if a repository commits after step two?

### Exercise 3: Distinguish a zero-row claim from a DB error

Question: the guarded UPDATE returns zero rows. What does it mean?

Expected Output: a normal stale/no-op — another Worker claimed it; create no Attempt/Event, do not retry.

Follow-up: is ending the empty UoW harmful? (No.)

### Exercise 4: Why guarded UPDATE beats SELECT-then-UPDATE

Question: explain the race.

Expected Output: SELECT-then-UPDATE lets two Workers both read `queued` and proceed; the guarded UPDATE ...
RETURNING names one winner atomically.

Follow-up: what does one returned row prove?

### Exercise 5: Split short transactions from the Provider call

Question: where does the minutes-long Provider call go?

Expected Output: outside any DB transaction, between a guarded start UoW and a guarded completion UoW.

Follow-up: what two things go wrong if it runs inside the transaction?

### Exercise 6: Correlation evidence for recovery

Question: when do you persist the recovery identity?

Expected Output: commit an application-generated correlation/idempotency key with the Attempt before the call;
persist the Provider request ID later.

Follow-up: why is the Provider request ID alone too late?

### Exercise 7: Flush vs commit

Question: how do you get the Attempt id for a dependent Event without committing, and can another Session see it?

Expected Output: `flush` executes SQL in the transaction and yields the id; another Session cannot see it until
commit.

Follow-up: what does commit add that flush does not?

### Exercise 8: PostgreSQL rollback runtime test (design)

Question: design a test that proves rollback.

Expected Output: after a failing UoW, open a NEW Session and assert the Job is still queued with no Attempt/Event;
a mocked `rollback()` is not this proof; SQLite is not valid evidence. (NOT RUN here.)

Follow-up: why a new Session rather than the same one?

### Exercise 9: Detached ORM lazy loading

Question: why can serialization fail after UoW close, and what is the fix?

Expected Output: an unloaded lazy relation needs I/O on a detached object (`DetachedInstanceError`); build an
allowlisted Pydantic DTO inside the UoW.

Follow-up: which already-in-memory data is still safe?

### Exercise 10: API/Worker Engine ownership and shutdown

Question: who owns each Engine, and how does a Worker shut down?

Expected Output: each process owns its own Engine/pool via lifespan/startup; a Worker stops new claims, handles
in-flight under a bound, then disposes the Engine.

Follow-up: does closing a Session dispose the Engine? (No.)

### Exercise 11: Integrated success/crash recovery

Question: UoW 1 committed start facts, the Provider produced an Artifact, UoW 2 crashed before commit. Recover.

Expected Output: PostgreSQL retains only UoW 1 facts; a new UoW verifies Provider/Artifact via correlation, then
runs a new guarded completion — or preserves unknown state. Code rollback ≠ durable-data/external-side-effect
rollback.

Follow-up: what do you do if the external outcome cannot be verified?

---

# Relevant Framework Connections

## SQLAlchemy 2.0 async

The lesson's core: `create_async_engine` (process), `async_sessionmaker(expire_on_commit=False)` (process), a
fresh `AsyncSession` per UoW, `flush` vs `commit`, `rollback`, `close`, `IntegrityError` semantics, and detached
ORM objects. A guarded `UPDATE ... WHERE ... RETURNING` expresses the atomic claim/completion. Real PostgreSQL
runtime validation is NOT RUN.

## FastAPI

The API-process Engine is owned by the lifespan/composition root; a dependency creates a fresh UoW per request;
responses are allowlisted Pydantic DTOs built **before** Session close. No FastAPI runtime was executed in Day47.

## Worker process

A Worker owns a separate Engine/pool, creates one UoW per Job, and on shutdown stops new claims before bounded
in-flight handling and Engine disposal. No concurrent Worker runtime was executed.

## PostgreSQL

PostgreSQL is the durable authority: guarded `UPDATE ... RETURNING`, rollback semantics, constraints, and
new-Session runtime verification. Its runtime behavior is NOT RUN here; a real test applies the Day42 raw SQL
first.

---

# AI Backend Connections

## Multi-tenant AI Job lifecycle

`queued -> running -> terminal` with Attempt/Event evidence is driven by two short guarded UoWs around the
Provider call — the transactional backbone of the AI Job lifecycle.

## Long paid Provider calls stay outside transactions

A minutes-long, paid Provider call never holds a DB connection; correlation/idempotency evidence committed before
it is what makes recovery possible without duplicate charges.

## External Artifact can outlive a failed completion

The Provider's external Artifact may exist even though the completion transaction rolled back; recovery verifies
it and persists its reference in a new guarded completion UoW — never fabricating success.

## Unknown outcome is a first-class state

A timeout with unknown remote execution is neither failed nor succeeded; it is a recovery state resolved by
correlation evidence, not by a blind retry that risks double-spending.

---

# English Interview

## Key Vocabulary

AsyncEngine, `async_sessionmaker`, AsyncSession, Unit of Work, repository, transaction boundary, flush vs commit,
rollback, close, guarded `UPDATE ... RETURNING`, stale/no-op, correlation/idempotency key, unknown outcome,
detached ORM object, DTO, PostgreSQL runtime evidence.

## Useful Expressions

"The Engine is process-scoped; the Session is per unit of work." · "Repositories express; the UoW commits." ·
"Zero rows is a stale/no-op, not an error." · "Flush is not commit." · "Keep the Provider call outside the
transaction." · "A commit exception is an unknown outcome." · "A mock isn't database proof."

## Beginner Question — What is a database Unit of Work, and why not share one AsyncSession across concurrent Jobs?

Student answer (verbatim):

> "不知道"

Strong spoken answer taught:

> "A Unit of Work groups a set of database operations into one transaction with a single commit or rollback and
> owns exactly one Session for its lifetime. You cannot share one AsyncSession across concurrent Jobs because a
> Session holds an identity map, pending changes, and transaction state, so concurrent Jobs would pollute each
> other. The Engine and session factory are process-scoped and shared; each request or Job gets a fresh Unit of
> Work with its own Session."

Assessment: an honest "不知道"; the taught answer covers the UoW's single-transaction ownership and why the Session
is per-unit-of-work while the Engine/factory are process-scoped.

## Intermediate Question — Explain flush versus commit, and why a guarded UPDATE ... RETURNING avoids the race that SELECT-then-UPDATE has.

Student answer (verbatim):

> "不知道"

Strong spoken answer taught:

> "Flush sends the pending SQL to the database inside the current transaction — so a server-generated id becomes
> available for a dependent write — but it is not durable and other Sessions cannot see it; commit makes the work
> durable and visible. A guarded claim is a single UPDATE ... WHERE job_status='queued' RETURNING, so exactly one
> Worker's statement changes the row and gets a row back; SELECT-then-UPDATE reads first and then writes, so two
> Workers can both read 'queued' and both proceed. Zero rows returned just means another Worker already claimed
> it — a normal stale/no-op, not an error."

Assessment: an honest "不知道"; the taught answer separates flush from commit and explains the atomic single-winner
claim.

## Senior Question — UoW 1 committed start facts, the Provider produced an Artifact, but UoW 2 crashed before commit. How do you recover, and what evidence matters?

Student answer (verbatim):

> "不知道"

Strong spoken answer taught:

> "After the crash, PostgreSQL retains only UoW 1's committed facts — running, Attempt 1 with its
> correlation/idempotency key, and the job_started Event. The external Artifact may exist, but its database
> reference, the succeeded state, and the completion Event do not, because code rollback is not durable-data or
> external-side-effect rollback. On restart I open a new Unit of Work, inspect the durable Job/Attempt/Event
> truth, and verify the Provider and Artifact using the correlation key. If the external outcome is confirmed, I
> run a new guarded completion transaction; if it cannot be verified, I preserve an unknown/recovery state rather
> than fabricating success or blindly re-calling the Provider."

Assessment: an honest "不知道"; the taught answer is the full evidence-based recovery arc with the code-vs-data
rollback boundary and the unknown-outcome state.

## Common Weak Answer

"I'll keep one shared AsyncSession, wrap the Provider call in the transaction so everything commits or rolls back
together, and let each repository commit its own step."

## Strong Answer

"The Engine and session factory are process-scoped; each request or Job gets a fresh Unit of Work with one
AsyncSession, and repositories share that Session but never commit — the UoW commits explicitly or rolls back and
closes. The Job is claimed with a guarded UPDATE ... RETURNING (zero rows is a stale/no-op), an
application-generated correlation key is committed before the Provider call, and that call runs outside any
transaction. Completion is a second short guarded UoW; an unknown outcome is preserved and recovered by
correlation, never retried blindly. I return a DTO built inside the UoW, and I prove rollback with a new
PostgreSQL Session, not a mock."

---

# Mental Model Summary

```text
1.  AsyncEngine + session factory = PROCESS-scoped (one Engine per process, not per deployment); AsyncSession = per UoW.
2.  An AsyncSession is NEVER global/shared (identity-map/pending/transaction state would pollute concurrent Jobs).
3.  One UoW = one Session + repositories; the FACTORY is shared, not the Session.
4.  Repositories EXPRESS DB ops (receive the injected Session); they NEVER create Engines/Sessions and NEVER commit/close.
5.  The UoW owns the transaction: EXPLICIT await uow.commit() (no auto-commit); rollback on exception/uncommitted exit; ALWAYS close.
6.  Guarded claim = single UPDATE ... WHERE job_status='queued' RETURNING (not SELECT-then-UPDATE). 1 row=claimed / 0=stale-noop.
7.  A zero-row guarded claim/completion is a NORMAL stale/no-op: no Attempt/Event, no overwrite/duplicate, not a retryable DB error.
8.  flush executes SQL in the current transaction (server ids available) but is NOT durable and NOT cross-session visible; commit is.
9.  IntegrityError = PostgreSQL rejected an illegal write and ABORTED the tx (integrity protected, not broken); roll back before reuse.
10. A commit exception is an UNKNOWN outcome: roll back/close local state, reload by stable id via a NEW Session; do not replay.
11. A long/paid Provider call runs OUTSIDE any DB transaction (the DB can't roll back its execution/charges/side effects).
12. Commit an APPLICATION-generated correlation/idempotency key with the Attempt BEFORE the call; persist the Provider ID later.
13. Completion is a SECOND short guarded UoW; guarded completion (concurrency) != jobs_succeeded_has_finished_at CHECK (state invariant).
14. Definitive failure -> failed; timeout/unknown -> a first-class recovery state; NEVER blindly requeue/re-call (cost + duplicate effects).
15. Don't return a detached ORM object for lazy serialization (DetachedInstanceError); build an allowlisted Day44 Pydantic DTO INSIDE the UoW.
16. A mock rollback proves code-path intent only; PostgreSQL runtime proof re-reads committed truth via a NEW Session; SQLite != PostgreSQL evidence.
17. code rollback != durable-data rollback != external-side-effect rollback.

Starting model -> reasoning -> correction -> final model:
Initial: AsyncSession sharing/rollback/close were recognized, but the lines between a normal stale outcome, a DB
transaction error, an external unknown outcome, flush, commit, and detached ORM reads were not yet precise (a
zero-row claim looked like a rollback; the Provider request ID looked sufficient; finished_at CHECK looked like
guarded completion; identity map looked like it made detached reads safe; commit error looked like a definite fail).
Reasoning: the student saw Session state pollution, put commit at the UoW, chose a single guarded UPDATE, kept the
Provider call out of the transaction, refused blind retries, and chose a DTO built in the UoW.
Correction: zero rows = stale/no-op; commit a correlation key BEFORE the call; guarded completion is concurrency
control, not the CHECK; detached lazy reads need a DTO; IntegrityError aborts (protects) the tx; a commit exception
is an unknown outcome resolved by re-reading durable truth.
Final: process-owned Engine/factory; one fresh isolated UoW/Session per request/Job; repositories share the Session
but never commit; one short explicit-commit transaction; Provider/Object-Storage work outside it with correlation
evidence committed first; unknown outcomes verified and completed through a new guarded UoW, never blindly replayed.
```

---

# Today's Takeaway

Day47 drives the faithful Day46 mapping through short, isolated async units of work. One process owns one Engine
and a session factory; each request or Worker Job gets a fresh Unit of Work with one isolated `AsyncSession`.
Repositories share that Session but never decide commit; the UoW runs one short transaction, explicitly commits
only a complete database fact set, and rolls back and closes on any abnormal or uncommitted exit. The long, paid
Provider call happens outside that transaction, durable correlation evidence is committed first, and unknown
external outcomes are verified and completed through a new guarded UoW rather than blindly replayed.

Most important mental model: two short guarded transactions around a Provider call that lives outside the
transaction. Most important production risk: a shared Session or a Provider call held inside a transaction —
state pollution and pool exhaustion, with no external rollback. Most important trade-off: two short transactions
+ correlation-based recovery vs one long transaction. Most important connection: Day48 evolves this schema safely
on top of these boundaries. Most important interview answer: the Engine is process-scoped, the Session is per
unit of work, and a commit exception is an unknown outcome.

Validation status: **23 fake-session control-flow tests** are **real executed evidence** of the UoW/repository
code paths — executed here on Python 3.10.12 / SQLAlchemy 2.0.29 / greenlet 3.5.4 / pytest 7.4.3 (pinned in
`requirements-day47.txt`) → **23 passed**. But a **mock is not database proof**: **PostgreSQL runtime is NOT
RUN** (no server/driver; a real test would apply the Day42 raw SQL, force a failure, and prove via a new Session
that the Job stays queued with no Attempt/Event), and **SQLite is not PostgreSQL evidence** for this
`app`-schema/PostgreSQL-typed contract. FastAPI/Worker integration, concurrent Workers, real Provider, Object
Storage, and production are all **NOT RUN**.

---

# Before Next Lesson Checklist

```markdown
- [ ] Can I explain why an AsyncSession can't be global, and scope the Engine/factory vs the Session?
- [ ] Can I assign commit/rollback/close to the UoW and keep repositories free of them?
- [ ] Can I justify explicit commit over auto-commit-on-exit?
- [ ] Can I write a guarded UPDATE ... RETURNING claim and treat zero rows as a stale/no-op?
- [ ] Can I explain flush vs commit and cross-session visibility?
- [ ] Can I explain why an IntegrityError aborts (protects) the transaction and needs a rollback?
- [ ] Can I treat a commit exception as an unknown outcome and reload durable truth by id?
- [ ] Can I keep the Provider call outside the transaction and commit a correlation key before it?
- [ ] Can I run completion as a second guarded UoW and distinguish it from the finished_at CHECK?
- [ ] Can I classify definitive failure vs unknown outcome and avoid blind retries?
- [ ] Can I avoid detached-ORM lazy loading by building a DTO inside the UoW?
- [ ] Can I run the fake-session tests (`pytest -q test_day47_async_uow.py`) and state why PostgreSQL runtime is NOT RUN?
```

Preparation for Day48 (Alembic and Safe AI Backend Schema Evolution): review this Engine/session/repository/UoW
boundary, then preview how Alembic evolves the mapped schema through the Expand → Backfill → Validate → Switch →
Contract discipline on top of known runtime persistence boundaries. The Day49 upload workflow and the Day50
acceptance/Outbox workflow remain later boundaries.

---

Engineering Artifact: [projects/ai-backend-data-layer/api/day47-async-persistence-boundary-design.md](../../projects/ai-backend-data-layer/api/day47-async-persistence-boundary-design.md) · Code: [`day47_async_uow.py`](../../projects/ai-backend-data-layer/api/day47_async_uow.py) · Tests: [`test_day47_async_uow.py`](../../projects/ai-backend-data-layer/api/test_day47_async_uow.py)
