# Day47 — Async Sessions, Transactions, Repository and Unit of Work (Design)

Drives the faithful Day46 SQLAlchemy mapping through SHORT, isolated async
database units of work — without treating a long external AI-Provider call as
transactional database work. Runnable code:
[`day47_async_uow.py`](day47_async_uow.py); executed fake-session tests:
[`test_day47_async_uow.py`](test_day47_async_uow.py); pinned deps:
[`requirements-day47.txt`](requirements-day47.txt); persistence model reused:
[`day46_orm_mapping.py`](day46_orm_mapping.py).

> Scope honesty: PostgreSQL stays the durable authority — **Day46 maps it, Day47
> drives it transactionally, Day48 evolves it.** This artifact adds the runtime
> persistence boundary (Engine/session-factory helpers, per-UoW Session,
> repositories, explicit commit/rollback/close, guarded claim/completion) and a
> **fake** Provider seam. It does NOT redefine Day42 schema authority, use
> `create_all()` as compatibility proof, change TEXT+CHECK to enum, add a
> destructive cascade, or implement the Day50 idempotent acceptance/Outbox
> workflow or the Day49 upload workflow. **Real PostgreSQL runtime is NOT RUN.**

---

## 1. Scope and ownership (process vs request/Job)

```text
AsyncEngine            = PROCESS-scoped (one per process, via lifespan / Worker composition root; NOT one per deployment).
                         API and Worker are separate processes, each owns its own Engine + connection pool.
async_sessionmaker     = PROCESS-scoped factory; creates a NEW AsyncSession on demand (NOT a shared batch of live Sessions).
AsyncSession           = request/Job-scoped; carries identity-map + pending-change + transaction context; NEVER global/shared
                         (concurrent Jobs would pollute each other's state).
Unit of Work           = one fresh UoW per HTTP request (FastAPI dependency) or per Worker Job; the same FACTORY is shared,
                         not the same Session.
```

---

## 2. Repository and Unit of Work responsibility

```text
Repository -> receives the UoW-injected Session; expresses DB operations; does NOT create Engines/Sessions and does NOT
              commit or close.
UnitOfWork -> owns ONE Session, exposes repositories, controls EXPLICIT commit, rolls back on exception / uncommitted exit,
              and ALWAYS closes the Session.
Explicit `await uow.commit()` was chosen over silent auto-commit on context exit: the durable decision stays reviewable, and
a normal branch (e.g. a failed/stale claim) can never accidentally commit work. Atomicity comes from the UoW's ONE
transaction + explicit commit, not from repositories committing independently.
```

---

## 3. Atomic start flow and the guarded claim

```text
UoW 1 (short): guarded claim -> Attempt 1 (flush) -> job_started Event -> commit ONLY if all three succeed.
Guarded claim = a SINGLE `UPDATE app.jobs SET job_status='running' WHERE job_id=:id AND job_status='queued' RETURNING job_id`
  (NOT SELECT-then-UPDATE, which races). One returned row = this Worker claimed the Job; ZERO rows = a NORMAL stale/no-op
  miss -> create NO Attempt/Event, do NOT treat it as a retryable database failure (ending/rolling back an empty UoW is
  harmless). A Repository must NOT commit after one substep: if Attempt succeeds but Event fails, the UoW rolls back ALL
  uncommitted work.
```

---

## 4. Flush, commit, rollback, and Session lifecycle

```text
await session.flush()  -> executes SQL in the CURRENT transaction so a server-generated Attempt id is usable to write a
                          dependent Event WITHOUT committing. It does NOT make a durable committed fact visible to other
                          Sessions.
IntegrityError on flush -> PostgreSQL correctly REJECTED an illegal write; its current transaction is ABORTED and must be
                          rolled back before the Session can do normal work again (durable integrity is NOT broken).
abnormal / uncommitted exit -> roll back any pending transaction, then close the Session. close() ends the Session and
                          returns its connection to the pool; it is NOT a substitute for rollback and does NOT dispose the
                          process Engine.
commit exception       -> an UNKNOWN commit outcome (the DB may have committed before the response was lost). Roll back/close
                          local state, then RELOAD durable truth by stable identifier — do NOT blindly replay the write.
```

---

## 5. Short DB transactions vs external side effects

```text
A Provider call that may take minutes stays OUTSIDE any open DB transaction (holding one exhausts the pool and cannot make
  Provider execution/charges/results roll back with PostgreSQL).
BEFORE an irreversible Provider call: commit a durable Attempt + an APPLICATION-generated correlation/idempotency key
  written into the job_started Event metadata (Day46 defines NO correlation column on JobAttempt; Day47 invents none,
  and AttemptRepository.create() does NOT accept a correlation_key).
  A Provider-returned request ID is persisted LATER when available — too late to be the only recovery identity.
Completion = a SECOND short guarded UoW persisting the Day33 atomic completion pack in ONE commit:
  1) guarded finish Attempt: UPDATE app.job_attempts SET finished_at=now() WHERE attempt_id AND job_id AND finished_at IS NULL
     RETURNING attempt_id -> 0 rows (missing / wrong Job / ALREADY finished) = ROLLBACK + stale/no-op (never overwrite a finished Attempt);
  2) guarded terminal Job: UPDATE ... WHERE job_status='running' RETURNING -> 0 rows = ROLLBACK, write NO Artifact and NO success Event;
  3) create ResultArtifact durable reference (Day46 mapping; Object Storage object_key + metadata, NEVER bytes);
  4) append the job_succeeded Event; 5) COMMIT.
  If the Artifact insert or the Event append fails, the WHOLE UoW rolls back -> no partial PostgreSQL durable state. The external
  Artifact bytes are NOT part of the transaction; a DB rollback does NOT delete the external object.")
Definitive non-retryable failure (e.g. 401 / rejected request) -> `failed`. A timeout with UNKNOWN remote execution stays
  unknown/recoverable: never blindly requeue or re-call the Provider.
Note: the Day46 jobs_succeeded_has_finished_at CHECK is a STATE invariant; guarded completion is CONCURRENCY control
  (exactly one still-valid running Attempt/Job records terminal facts; later writers are stale/no-op) — they are different.
```

---

## 6. Read boundary and evidence

```text
Do NOT return a detached ORM object and let response serialization lazily load relations AFTER UoW close (an unloaded lazy
  relation needs DB I/O; a detached object raises DetachedInstanceError, or MissingGreenlet in an invalid async context).
  Load what you need INSIDE the UoW and build an allowlisted Day44 Pydantic response/DTO.
A mock asserting rollback() was called proves only code-path INTENT. A PostgreSQL runtime test must use a NEW Session after
  failure and prove committed truth: the Job remains queued and NO Attempt/Event remains.
SQLite is NOT PostgreSQL runtime evidence for this system (app schema, PostgreSQL types/defaults/constraints, and PostgreSQL
  transaction/concurrency behavior).
```

Executed fake-session tests in `test_day47_async_uow.py` (17 cases):

```text
1  claimed start flow: guarded claim (1 row) -> Attempt (flush) -> Event -> commit exactly once; always closes
2  zero-row guarded claim = stale/no-op: no Attempt/Event, no commit, rollback + close
3  flush happens BEFORE the dependent Event write; the Event uses the flush-assigned attempt_id
4  UoW rolls back + closes on an exception inside the block (no commit)
5  UoW does NOT auto-commit on an uncommitted normal exit (rollback + close)
6  a repository method alone does NOT commit or close (only the UoW decides)
7  commit exception -> rollback + close, then propagate (unknown outcome -> caller reloads durable truth)
8  one UoW shares ONE Session across all repositories
9  no global Session: each UoW gets a FRESH Session from the factory
10 completion persists the Day33 atomic pack in ONE commit: guarded Attempt finish + guarded Job transition + ResultArtifact + job_succeeded Event
11 stale/already-finished Attempt (finish guard 0 rows): no Job success, no Artifact, no Event; rollback + close
12 stale Job (Attempt finished, Job transition 0 rows): no Artifact, no Event; rollback + close
13 Artifact insert failure inside the pack: rollback + close, no commit (fake-session control flow only)
14 success Event append failure inside the pack: rollback + close, no commit
15 the correlation/idempotency key lives in the job_started Event metadata; AttemptRepository.create() no longer accepts it
16 Provider seam is outside the DB tx; an unknown outcome propagates and is not fabricated / not blindly re-called
17 guarded mark_failed records 'failed' on a still-running Job (1 row); a zero-row guard is stale/no-op
```

---

## 7. Integrated failure / rollback recovery exercise (conceptual)

```text
UoW 1 committed: running + Attempt 1 (with correlation/idempotency key) + job_started Event.
Provider produced an external Artifact.
UoW 2 wrote success state + ResultArtifact reference but CRASHED before job_succeeded Event and commit.
-> After rollback, PostgreSQL retains ONLY UoW 1 facts. The external Artifact may exist, but its DB reference, the succeeded
   state, and the completion Event do NOT (code rollback != durable-data rollback != external-side-effect rollback).
Restart recovery: a NEW UoW inspects Job/Attempt/Event durable truth, verifies Provider/Artifact evidence via correlation/
   idempotency, then runs a NEW guarded completion transaction. If the external outcome cannot be verified, PRESERVE
   unknown/recovery state — do NOT fabricate success/failure or blindly re-call the Provider.
```

---

## Run instructions

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day47.txt   # sqlalchemy[asyncio]==2.0.29, pytest==7.4.3
python3 -m py_compile day47_async_uow.py test_day47_async_uow.py
python3 -m pytest -q test_day47_async_uow.py
```

---

## Validation and evidence classification

```text
CONCEPTUAL              : the design mirrors the Day47 classroom process (scope/ownership, UoW/repo, guarded claim/
                          completion, short-tx vs external side effects, unknown-outcome recovery).
SYNTAX / STATIC (RUN)   : python3 -m py_compile of day47_async_uow.py + test_day47_async_uow.py passed.
FAKE-SESSION UNIT (RUN) : 17 pytest cases verify UoW/repository CONTROL FLOW with a FAKE AsyncSession (no DB). Executed:
                          Python 3.10.12, SQLAlchemy 2.0.29, greenlet 3.5.4, pytest 7.4.3 -> 17 passed. These prove code-path
                          intent (explicit commit, rollback+close, stale/no-op, flush-before-write, repos never commit,
                          one shared Session per UoW, a fresh Session per UoW), NOT database behavior.
POSTGRESQL RUNTIME      : NOT RUN. No PostgreSQL server / async driver was available. A real test would apply the independent
                          Day42 raw SQL (sql/001 + sql/003) to a disposable PostgreSQL, run a failing UoW, then open a NEW
                          verification Session and assert the Job stays queued with no Attempt/Event. A mock rollback() call
                          is NOT this proof; SQLite is NOT PostgreSQL evidence.
INTEGRATION / PRODUCTION: NOT RUN. No FastAPI/Worker concurrent run, real Provider SDK/network, Object Storage, Day50
                          acceptance/Outbox, Day49 upload, or production validation.
```

---

Lesson: [`docs/fastapi/day47-async-sessions-transactions-repository-and-unit-of-work.md`](../../../docs/fastapi/day47-async-sessions-transactions-repository-and-unit-of-work.md)
· Day46 mapping: [`day46_orm_mapping.py`](day46_orm_mapping.py) · Day42 schema: [`../sql/003_relational_modeling_and_data_integrity.sql`](../sql/003_relational_modeling_and_data_integrity.sql)
