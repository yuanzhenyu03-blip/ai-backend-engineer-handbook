# Lesson 48 — Alembic and Safe AI Backend Schema Evolution

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day47 — Async Sessions, Transactions, Repository and Unit of Work

Previous Lesson: [Day47 — Async Sessions, Transactions, Repository and Unit of Work](day47-async-sessions-transactions-repository-and-unit-of-work.md)

Next Lesson: Day49 — Upload Sessions, Object Storage and Artifact Verification (planned — Phase 4; see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day49 lesson file does not exist yet)

Phase: Phase 4 — Production AI API Engineering

Engineering Artifact: The Day48 Alembic control plane ([`projects/ai-backend-data-layer/api/day48-alembic-safe-schema-evolution-design.md`](../../projects/ai-backend-data-layer/api/day48-alembic-safe-schema-evolution-design.md)) with a runnable Alembic package [`day48_alembic/`](../../projects/ai-backend-data-layer/api/day48_alembic) (minimal `env.py` + gated Expand/Validate/Contract revisions for the Lease evolution of `app.jobs`), an operational backfill script [`day48_lease_backfill.py`](../../projects/ai-backend-data-layer/api/day48_lease_backfill.py) (restartable `FOR UPDATE SKIP LOCKED`, off the migration), and tests [`test_day48_alembic.py`](../../projects/ai-backend-data-layer/api/test_day48_alembic.py). Static Alembic + fake-session tests were executed (16 passed) and the offline `alembic upgrade --sql` rendered the DDL (Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3); **PostgreSQL runtime, integration, and production migration are NOT RUN** — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

FastAPI Cheat Sheet: [cheat_sheets/fastapi.md](../../cheat_sheets/fastapi.md)

FastAPI Interview: [interview/fastapi.md](../../interview/fastapi.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises + running the tests / offline SQL: 100-130 minutes
Hands-on migration/runbook design: 90-120 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Explain why `alembic upgrade head` success is only DDL-on-one-database evidence, not production safety.
2. Sequence Day36's Expand -> Backfill -> Validate -> Switch -> Contract as separately gated Alembic revisions/operations.
3. Write an Expand migration that adds nullable compatibility columns with no fabricated default, plus a `CHECK ... NOT VALID`.
4. Explain `NOT VALID` (protect future writes) versus `VALIDATE CONSTRAINT` (prove corrected history) and why they are separate revisions.
5. Classify queued, terminal, trusted-running, and unknown-running Jobs for Backfill vs reconciliation, and never fabricate ownership.
6. Design a restartable, batched `FOR UPDATE SKIP LOCKED` backfill that lives outside the migration and calls no Provider.
7. Define the Switch gate (every Writer on the new protocol; the old path cannot write) and the Contract observation gate.
8. Choose forward-fix + reconciliation over a destructive downgrade once real Lease data or Provider side effects exist.
9. Reason about the Alembic revision graph, `down_revision`, merge revisions, `autogenerate` review, and baseline/`stamp`.
10. Keep Alembic a minimal deployment control plane (no FastAPI startup migration, no request/Job UoW) and handle `CREATE INDEX CONCURRENTLY`.
11. Design real PostgreSQL validation for `NOT VALID`/`VALIDATE` and distinguish static/offline evidence from PostgreSQL runtime proof.

---

# Why This Matters

Day47 operates the current schema safely, but it never **evolves** it. In production the schema changes while a
populated, multi-tenant `app.jobs` table is live and **old and new Workers run concurrently** — and a careless
`ALTER TABLE` can break old code, corrupt historical rows, or trigger double execution of long **paid** Provider
calls. Day48 makes Day36's safe-migration discipline **executable with Alembic**: a migration is a **versioned
state transition across schema, existing data, and every deployed writer**, and successful DDL is emphatically
**not** completion.

The evolving scenario is concrete: the team introduces **Lease ownership** (`lease_owner`, `lease_token`,
`lease_expires_at`) to stop stale ownership and double execution. Doing it all at once — add NOT NULL columns
with fabricated defaults, flip every Worker, drop the old path in one release — breaks old Workers, invents
ownership history that never existed, and gives no way back. Instead you **Expand** (nullable, no fabricated
default; NULL honestly means "no proved ownership"), **Backfill** only running Jobs with trusted evidence in a
restartable operational step (unknown ownership goes to reconciliation, never invention), **Validate** the
history with `VALIDATE CONSTRAINT` after `NOT VALID` has already protected new writes, **Switch** every writer
onto the token protocol so the old path can no longer write, and only then — after evidence and an observation
period — **Contract** destructively.

This lesson has **real static/offline evidence**: **16 tests passed** (Alembic revision-graph + migration-source
inspection via `ScriptDirectory`, plus fake-session backfill control flow), and the offline `alembic upgrade
--sql` **rendered** the Expand/Validate/Contract DDL — all with **no database connection**. But that is **not**
PostgreSQL proof: **PostgreSQL runtime is NOT RUN** (no server), and `alembic upgrade` success alone does not
prove Backfill, Switch, Contract, or production safety. FastAPI/Worker integration, real Provider, Object
Storage, and production migration are all **NOT RUN**.

---

# Roadmap Position

```text
Day36 raw-PostgreSQL safe-migration discipline
Day46 faithful SQLAlchemy mapping of the Day42 contract
Day47 async UoW / runtime persistence boundary
Day48 Alembic versioned schema evolution (Expand/Backfill/Validate/Switch/Contract)   <-- you are here
Day49 Upload Sessions / Object Storage / Artifact verification on the evolved model
Day50 tenant-scoped idempotency + atomic Job + Outbox intent over the same boundary
```

Knowledge continuity:

```text
Previous knowledge
  Day36 Expand/Backfill/Validate/Switch/Contract in raw SQL; Day46 mapping (Base.metadata as autogenerate input,
  not authority); Day47 UoW/short-transaction boundary and correlation-based recovery
        |
        v
Current lesson
  make that discipline executable with Alembic as a DEPLOYMENT CONTROL PLANE (revision graph, NOT VALID/VALIDATE,
  restartable off-migration backfill, Switch/Contract gates), distinct from a request/Job UoW and FastAPI startup
        |
        v
Future production usage
  Day49 persists Upload/Artifact references on the safely evolved schema (Object Storage I/O outside DB tx);
  Day50 uses the same schema/UoW boundary for tenant-scoped idempotency + atomic Job + Outbox intent (intent is
  not Provider-success proof; Day55 later provides real broker/Celery delivery)
```

Day48 does **not** implement the Day49 upload workflow, Day50 real Outbox/Celery delivery, Day53 Provider SDK, or
Day55 worker runtime, and runs no PostgreSQL/integration/production migration. They are named only as future
connections.

---

# Lesson Map

```text
1.  Migration > DDL              -> upgrade success != history/old-Worker/Provider safety
2.  Expand                        -> nullable, NO fabricated default; NULL = no proved ownership
3.  NOT VALID vs VALIDATE          -> protect the future now; prove the past later (separate revisions)
4.  Classify Jobs                  -> queued/terminal/trusted-running=backfill; unknown-running=reconcile
5.  Backfill (operational)         -> restartable FOR UPDATE SKIP LOCKED, off the migration, no Provider
6.  Drain / Switch                 -> stop old claims + drain; every Writer on the token protocol
7.  Contract / forward-fix         -> destructive + gated; forward-fix once real data/side effects exist
8.  Alembic graph                  -> revision/down_revision, merge heads, autogenerate review
9.  Baseline / stamp               -> stamp does no DDL; new vs existing database entry paths
10. Control-plane boundary          -> minimal env.py; no startup migration; CREATE INDEX CONCURRENTLY
11. Evidence levels                 -> static/offline vs real PostgreSQL runtime; design a NOT VALID test
```

---

# Core Mental Model

```text
Alembic records SCHEMA CHANGE as a reviewable, versioned revision GRAPH; it does NOT auto-apply ORM drift, and
`upgrade` success only means DDL ran on ONE database.

Safe evolution = Day36's phases, each SEPARATELY GATED by different evidence:

  EXPAND    add nullable cols, NO fabricated default; CHECK ... NOT VALID (protect FUTURE writes, tolerate legacy)
     |      old Workers coexist (they ignore nullable cols) -> deploy Expand FIRST and alone
     v
  BACKFILL  operational, restartable, FOR UPDATE SKIP LOCKED, idempotent; fill ONLY running+trusted-evidence Jobs;
     |      unknown -> reconciliation, NEVER fabricate; NOT in upgrade(); no Provider; DB state = checkpoint
     v
  VALIDATE  VALIDATE CONSTRAINT proves HISTORY (fails until legacy truly resolved; an exception queue != resolution)
     |
     v
  SWITCH    EVERY Writer (Workers, recovery, admin/scripts, completion/failure) uses the token protocol; old path
     |      cannot write. NOT merely deploying a new binary.
     v
  CONTRACT  destructive; LAST; only after Validate + Switch + evidence + observation. Once real Lease data or Provider
            side effects exist -> FORWARD-FIX + reconcile, NOT a destructive downgrade (a downgrade is not a time machine).

Alembic control plane != FastAPI startup != Day47 request/Job UoW. alembic_version = a version DECLARATION, not a proof.
Provider/Object Storage are outside DB transactions; interrupted calls are UNKNOWN outcomes recovered by
Job/Attempt/Event + correlation/idempotency evidence (Outbox intent is NOT Provider-success proof).
```

---

# Main Concepts

## Concept 1: A migration is more than DDL

### Tech Lead Question

A populated `app.jobs` has old and new Workers running. Can you add the Lease feature in one all-at-once
migration that adds NOT NULL columns and flips everyone?

### Student Answer

> "不会，旧的worker与新增的列不兼容"

### Tech Lead Review

Exactly the instinct that matters: an all-at-once change is unsafe because **old Workers are incompatible with
the new columns** — an old Worker doesn't set them, so NOT-NULL-without-a-safe-default rejects its writes, and
fabricated defaults invent state. A migration is a **versioned transition across schema + historical rows +
every deployed application/Worker version**, so `alembic upgrade head` succeeding is only **DDL-execution
evidence on one database** — not proof that history, old Workers, or external Provider side effects are safe.
That is why the change is split into separately gated phases.

### Engineering Thinking

Deploying schema and code together, in one step, assumes a single writer and no history. Production has neither.
Compatibility windows exist precisely so old and new code can coexist during the change.

### Production Example

Expand ships first and alone: old Workers keep running because the new columns are nullable and their code
ignores them; only later do new Workers start using the Lease protocol.

### Framework Connection

Alembic revisions as discrete, deployable steps; Day46 nullable columns keep old code compatible.

## Concept 2: Expand — nullable, no fabricated default (and never fabricate history)

### Tech Lead Question

For the Expand step, do you add the Lease columns NOT NULL with a default? And should you generate a token for
an old running Job whose ownership you cannot prove?

### Student Answer

> (fabricated historic Lease) "不会，历史job不能伪造，追溯困难"

### Tech Lead Review

Correct, and this is the ethical core of Expand. Add the Lease columns **nullable with no fabricated default**,
so a `NULL` honestly means **"no proved Lease ownership."** You must **not** generate tokens for queued,
terminal, or **unprovable running** Jobs — as the student said, historical Jobs **cannot be fabricated**, and
invented ownership is **untraceable** and corrupts audit. Unknown running ownership goes to
**reconciliation/recovery**, never to invented data. Expand also adds the coherence rule as `CHECK ... NOT
VALID` (Concept 3) and runs **no** Backfill loop, **no** Provider call, and **no** long transaction.

### Engineering Thinking

A default is a claim about every existing row. If you cannot honestly make that claim, the column must be
nullable and the truth ("we don't know yet") must be representable.

### Production Example

`ALTER TABLE app.jobs ADD COLUMN lease_owner text, lease_token uuid, lease_expires_at timestamptz` — all
nullable; the three-column `jobs_lease_triple_coherent` CHECK is added `NOT VALID`.

### Framework Connection

An Alembic Expand revision with `op.execute("ALTER TABLE ... ADD COLUMN ...")` and no default; the offline
`--sql` render shows the exact DDL.

## Concept 3: `NOT VALID` protects the future; `VALIDATE` proves the past

### Tech Lead Question

How do you enforce the new Lease coherence rule on **future** writes immediately, while a populated table still
has legacy rows that would violate it?

### Student Thinking

The student first reached for the Day47 runtime mechanism, then learned the migration mechanism.

### Student Answer

> (initial) `UPDATE ... RETURNING`

> (VALIDATE, correct) "证明并纳入历史数据也符合已经上线的规则"

### Tech Lead Review

The correction is the heart of the day. `UPDATE ... RETURNING` is the **Day47 concurrency/ownership** mechanism
(guarded claims/completions) — it is **not** the Day48 historical-compatibility mechanism. The right tool is
**`CHECK ... NOT VALID`**: it **protects every future INSERT/UPDATE immediately** while **temporarily tolerating
legacy violations**. Then, only after those violations are truly resolved, **`VALIDATE CONSTRAINT`** proves — as
the student put it — that the **historical data also complies with the already-live rule**. `NOT VALID` = guard
the future now; `VALIDATE` = prove the past later. They are **separate revisions**, and `VALIDATE` **fails** if
any legacy violation remains — which is the signal to finish Backfill/reconciliation, not to exclude rows (an
exception queue is not resolution).

### Engineering Thinking

Splitting "enforce for new writes" from "prove old rows comply" lets you protect production the moment you
deploy, without a giant blocking table scan or a lie about historical rows.

### Production Example

`ADD CONSTRAINT jobs_lease_triple_coherent CHECK (...) NOT VALID` (Expand) then, after Backfill,
`VALIDATE CONSTRAINT jobs_lease_triple_coherent` (a separate Validate revision).

### Framework Connection

PostgreSQL `CHECK ... NOT VALID` + `VALIDATE CONSTRAINT`; two gated Alembic revisions (`0002_expand_lease`,
`0003_validate_lease`).

## Concept 4: Classify Jobs for Backfill vs reconciliation

### Tech Lead Question

Which Jobs get a backfilled Lease, and which do not?

### Student Answer

> "C backfill D reconciliation"

### Tech Lead Review

Correct classification. **Queued** and **terminal** Jobs get **no** Lease (they hold none), an **unknown-running**
Job goes to **reconciliation** (its ownership cannot be proved), and only a **running Job with trusted ownership
evidence** is **backfilled**. The dividing line is *provable ownership*: backfill fills only what you can prove;
everything unprovable is reconciled or recovered, never invented.

### Engineering Thinking

Backfill is not "fill every row"; it is "record the ownership you can honestly prove." The unknown set is a
first-class recovery population, not a nuisance to default away.

### Production Example

Of 10,000 running Jobs, the 9,800 with a still-valid trusted evidence source are backfilled; the 200 unknown go
to a reconciliation queue.

### Framework Connection

The backfill selection predicate (`running AND lease_owner IS NULL`) plus a trusted `EvidenceSource` that returns
`None` for unknown ownership.

## Concept 5: Backfill is a restartable operational step, off the migration

### Tech Lead Question

How do you run Backfill safely and restartably — and where does it live? And how do you handle old Workers first?

### Student Thinking

The student described the restart predicate and the drain of old Workers.

### Student Answer

> (restartable selection) "依赖仍是 running 且 Lease 字段仍为空、且可信来源仍存在的行"

> (draining) "停止旧worker接收新的job，in-flight的worker进行 brain"

### Tech Lead Review

Right on both. Backfill selects **rows still running, with Lease fields still NULL, and a trusted source still
present** — an **idempotent, restartable** predicate, so an interrupted run resumes cleanly (the **database
state is the checkpoint**). Run it in **short transactions with `FOR UPDATE SKIP LOCKED`** batches (concurrent-
safe, no long lock), calling **no Provider** and holding **no long transaction** — and it must **not** be a long
loop inside an Alembic `upgrade()`. On draining (your "brain" = drain): **stop old Workers from taking new
claims** and **boundedly drain in-flight work**; interrupted Provider calls are **unknown outcomes** recovered
with durable correlation evidence, **never blindly repeated**. Two mechanism corrections: Lease **expiry** is a
runtime ownership protocol, **not** a migration-batch claiming mechanism; and Backfill is a **controlled
operational data-migration step**, not an ordinary business operation and not an Alembic `upgrade()` loop.

There is one termination subtlety the artifact makes explicit. An unknown-ownership running Job stays
`lease_owner IS NULL`, so if you only *count* it and move on, it re-matches the candidate query forever — an
**infinite loop**. The fix is a **persistent reconciliation marker**: a nullable `lease_backfill_state` column
(added in Expand, no fabricated default) that the backfill sets to `'reconcile'` for an unprovable Job via a
guarded, idempotent `UPDATE ... SET lease_backfill_state='reconcile' WHERE running AND lease_owner IS NULL AND
lease_backfill_state IS NULL RETURNING` — which fabricates **no** Lease owner/token/expiry. The candidate query
then excludes routed rows (`AND lease_backfill_state IS NULL`), so **every** selected Job leaves the candidate
set within its batch (proved -> `lease_owner` set; unknown -> marker set), the loop **terminates**, and a
**restart** never re-selects the same unknown Job (the database state is the durable checkpoint).

### Engineering Thinking

Long data motion belongs in a restartable operator script whose progress is durable in the database — not in a
migration transaction that must succeed atomically or roll back the world. And "we couldn't prove ownership"
must be a **persisted** state, not an in-memory count, or the work never ends.

### Production Example

`day48_lease_backfill.py` selects a `FOR UPDATE SKIP LOCKED` batch (excluding reconciliation-routed rows),
applies trusted evidence with a guarded `UPDATE ... WHERE running AND lease_owner IS NULL RETURNING` and routes
unknowns to `lease_backfill_state='reconcile'`, commits per batch, terminates, and resumes after a crash.

### Framework Connection

`FOR UPDATE SKIP LOCKED` + short `AsyncSession` transactions (Day47 boundary), an idempotent guarded update, and
a separate operator entrypoint (not an Alembic revision).

## Concept 6: The Switch gate

### Tech Lead Question

Once the new binary is deployed and Backfill is done, is the Switch complete?

### Student Answer

> "不能，还缺少旧的work限制"

### Tech Lead Review

Correct — Switch is **not** merely deploying a new binary; it is still missing the **old-Worker restriction**.
Switch means **every Writer** — Workers, recovery jobs, admin/scripts, and the completion/failure paths — uses
the **Lease-token protocol**, and the **old path can no longer write**. Until the old write path is actually
closed off, a stale old Worker can still corrupt ownership, so Switch is an **operational gate**, not a deploy
event.

### Engineering Thinking

A migration is not switched until no writer can bypass the new rule. "We shipped the new code" is necessary but
not sufficient; the old door must be locked.

### Production Example

Old Workers are drained and their write path is disabled; an admin repair script is updated to hold a Lease
token before writing — only then is Switch complete.

### Framework Connection

Operational Writer-protocol enforcement across all write paths; the token guard from the Day47 guarded-mutation
boundary.

## Concept 7: Contract is destructive — forward-fix, not downgrade, after real data exists

### Tech Lead Question

After real Lease tokens exist and Providers have run, a problem appears. Do you destructively downgrade to undo
the migration?

### Student Answer

> "保留已写入的 durable state 做 forward-fix，防止二次provider调用"

### Tech Lead Review

Exactly right. Once **real Lease data or Provider side effects exist**, you **preserve the written durable
state and forward-fix**, precisely to **prevent a second Provider call** (and the duplicate charge / unknown
outcome it creates). **Contract is destructive and last** — only after Validate, Switch, evidence, and an
**observation period**. A destructive `downgrade()` (dropping columns/history) is **not a time machine**: the
dropped bytes and history do not return, and pretending to "go back" past real side effects is how you
double-execute. `down_revision` primarily establishes the **revision graph and required predecessor state**;
downgrade is just the reverse traversal of that same graph, safe only before real data/side effects exist.

### Engineering Thinking

Rolling code back is easy; rolling **facts and external side effects** back is impossible. After real data,
recovery is always forward: fix the code, reconcile the data, never re-run the paid call blindly.

### Production Example

A faulty token guard is found post-Expand; the team forward-fixes the guard and reconciles affected Jobs rather
than dropping the Lease columns and losing the ownership evidence.

### Framework Connection

The Contract revision (`0004_contract_legacy`) drops the Day42 legacy `result_object_key` only under explicit
preconditions; its `downgrade()` re-adds a nullable column but cannot restore data.

## Concept 8: The Alembic revision graph and autogenerate review

### Tech Lead Question

What do `revision`/`down_revision` define, what creates multiple heads, and is an `autogenerate` diff a migration?

### Student Thinking

The student correctly required autogenerate review and Expand-first deployment, and initially justified
`down_revision` only via downgrade.

### Student Answer

> (autogenerate) required review; (Expand) deploy first; (`down_revision`) initially justified only through
> downgrade.

### Tech Lead Review

The corrections: `revision` + `down_revision` define the **upgrade/downgrade graph** and each revision's
**required predecessor state** — downgrade is the **reverse traversal** of that graph, not the sole reason
`down_revision` exists. **Parallel revisions create multiple heads** and need an Alembic **merge revision**.
And **`autogenerate` emits a candidate diff, not an approved migration** — you must review DDL, data semantics,
locks, multi-version compatibility, operational work, and downgrade/forward-fix conditions. Day46 `Base.metadata`
is autogenerate **input**; **PostgreSQL remains the authority**.

### Engineering Thinking

The revision graph is the migration's version-control DAG; treat autogenerate like a draft PR that a human must
review for locks, data, and multi-version safety.

### Production Example

Two feature branches each add a revision on the same parent -> two heads -> an `alembic merge` revision joins
them before deploy.

### Framework Connection

Alembic `revision`/`down_revision`/`branch_labels`, `alembic merge`, `alembic history`/`heads`, and
`autogenerate` review discipline.

## Concept 9: Baseline and `stamp` — new vs existing databases

### Tech Lead Question

How do you bring an existing Day42 database under Alembic, and how does that differ from a new empty database?
(Taught directly — the student said "不知道.")

### Student Answer

> "不知道"

### Tech Lead Review

An honest "不知道" — here is the model. **`alembic stamp <baseline>` writes `alembic_version` and performs NO
DDL**; you may stamp an **existing** database to the baseline **only after it is independently proven to match
that baseline exactly**. A **new/empty** database instead runs the chain from empty (apply the Day42 raw SQL,
then `stamp` the baseline, then `upgrade` to the later Lease revisions). In this repo the baseline
(`0001_baseline`) is a **stamp target** whose `upgrade()` does no DDL — the **Day42 raw SQL (`sql/001` +
`sql/003`) is the schema authority**. And `alembic_version` records a **version declaration, not a schema
proof**: stamping does not verify the schema; you must prove the match first.

### Engineering Thinking

`stamp` is a bookkeeping assertion ("this database is at version X"). It's only safe when that assertion is
already independently true, or you create drift that later migrations assume away.

### Production Example

An existing Day42 production DB is proven to match `0001_baseline`, stamped, and then upgraded to `0002+`; a
fresh CI database applies the raw SQL, is stamped, and upgraded identically.

### Framework Connection

`alembic stamp`, `alembic_version`, and the new-vs-existing entry paths; the Day42 raw SQL as authority.

## Concept 10: Alembic is a minimal deployment control plane

### Tech Lead Question

Should `env.py` build the FastAPI app or share a Session? Should the app run migrations on startup? What about
`CREATE INDEX CONCURRENTLY`?

### Student Answer

> (required) a separate Alembic control plane, no long Backfill in `upgrade()`, no unsafe `downgrade()`.

### Tech Lead Review

Correct requirements. Alembic is a **deployment control plane**, **not** FastAPI startup and **not** a Day47
request/Job UoW. `env.py` stays **minimal**: migration DB configuration, the target `Base.metadata`, and Alembic
execution — it must **not** create the whole FastAPI app or share a business Session, and the app must **never**
self-run migrations on startup. The `env.py` resolves the migration database URL by an explicit priority —
**`alembic -x db_url=<url>` > env `DAY48_ALEMBIC_DATABASE_URL` > the `alembic.ini` `sqlalchemy.url`** — where the
ini value is a **non-credential placeholder** used **only** for offline `--sql` rendering (it selects the dialect
and never connects; it is **not** a production connection), and no real connection string is ever committed. Two
operational specifics: **`CREATE INDEX CONCURRENTLY` is non-transactional**, so it must **not** sit inside a
normal migration transaction — a failed concurrent build can leave an **invalid/unusable index** that must be
inspected and repaired/removed before retry; and Expand, Validate, and Contract stay **separately gated**
revisions with **no long Backfill/reconciliation loop in `upgrade()`**.

### Engineering Thinking

Mixing the migration control plane with the running app couples deploy-time schema changes to request-time
behavior, and hides destructive DDL behind an innocent startup. Keep them separate and boring.

### Production Example

`env.py` imports only `Base.metadata`; migrations run as a deploy step (`alembic upgrade`), never from the API
process; a concurrent index build is its own out-of-transaction operation with an invalid-index cleanup plan.

### Framework Connection

A minimal `env.py`; `CREATE INDEX CONCURRENTLY` handled outside a migration transaction; separated revisions.

## Concept 11: Evidence — static/offline vs real PostgreSQL runtime

### Tech Lead Question

You ran `alembic upgrade head --sql` and it rendered the DDL. Does that prove the migration is safe? How would
you actually prove `NOT VALID`/`VALIDATE` behavior?

### Student Answer

> (runtime evidence) "不能，因为还需要看实际运行"

### Tech Lead Review

Correct — **you still need to see it actually run** on PostgreSQL. Offline `--sql` rendering and static
graph/source checks prove the migration **text and structure**, not database **behavior**, and **`alembic
upgrade` success alone does not prove Backfill, Switch, Contract, or production safety**. A **real PostgreSQL
runtime test** for `NOT VALID`/`VALIDATE`: create a **legacy row that would violate the future rule**; apply
Expand; prove the **old row survives**; prove a **new illegal write is rejected**; and prove **`VALIDATE` fails
until the legacy violation is repaired/reconciled**. **SQLite, fake sessions, and static checks are not
PostgreSQL proof.** In this repo the Day48 tests are static/offline and PostgreSQL runtime is honestly **NOT
RUN**.

### Engineering Thinking

Match the evidence to the claim. "The DDL text is correct" and "the constraint behaves correctly on real rows
under real locks" are different statements; only a PostgreSQL run proves the second.

### Production Example

A disposable PostgreSQL applies the Day42 raw SQL, inserts a violating legacy row, runs Expand, confirms a new
bad write is rejected while the legacy row survives, then confirms `VALIDATE` fails until that row is fixed.

### Framework Connection

Static `ScriptDirectory` + offline `--sql` (executed here) vs a real PostgreSQL `NOT VALID`/`VALIDATE` test
(NOT RUN); SQLite explicitly excluded.

## Concept 12: Provider recovery evidence — Outbox intent is not proof

### Tech Lead Question

After an interrupted Provider call during the migration window, what evidence proves whether the Provider
actually ran?

### Student Answer

> "job status、attempt、event、 outbox intent,结合idepmontency key进行判断"

### Tech Lead Review

Good direction with one correction. Use **Job status, Attempt, Event, and the application-generated
correlation/idempotency key** — but **Outbox intent is not Provider-success proof**: it records **dispatch
intent**, not remote execution. Day50 does not yet validate real delivery, and **external** results require
**correlation plus Provider/Artifact verification**, never a blind re-call. An interrupted paid call is an
**unknown outcome**: verify it against durable correlation evidence and the Provider/Artifact before completing,
or preserve the unknown/recovery state.

### Engineering Thinking

Durable *intent* to publish is not evidence that the remote system *did* the work. Recovery reads what the
database can prove and verifies the external world; it never assumes an interrupted paid call didn't happen.

### Production Example

A Worker crashes mid-migration after calling the Provider; recovery reads the Attempt + correlation key, queries
the Provider/Artifact to confirm, and only then records completion — the Outbox row is not treated as proof.

### Framework Connection

Day47 Job/Attempt/Event + correlation/idempotency recovery; the Day46 Outbox as dispatch intent (Day50/Day55 are
future).

## Concept 13: The integrated failure drill and the final synthesis

### Tech Lead Question

Expand has deployed, real Lease tokens exist, the token guard is faulty, an old Worker may still write, and some
Provider outcomes are unknown. What do you do? (The student then requested a direct synthesis.)

### Student Answer

> (final synthesis) "你帮我回答吧" — the student asked the Tech Lead to answer directly; the synthesis below is
> the taught answer, not an independently authored student answer.

### Tech Lead Review

The drill: **stop old claims and faulty paths; prevent bypass Writers; preserve Lease data; drain/isolate old
Workers; load Job/Attempt/Event/correlation evidence in a new UoW; verify Provider/Artifact; run a new guarded
completion only when confirmed, otherwise preserve unknown/recovery state; forward-fix; then Backfill/reconcile,
Validate, observe, Contract.** The taught synthesis: Alembic's job is not to auto-apply ORM drift but to record
schema change as a **reviewable, trackable revision graph**; `upgrade` success proves DDL ran on one database,
not that history, old Workers, or external Provider calls are safe. Follow **Expand -> Backfill -> Validate ->
Switch -> Contract**: add nullable fields with no fabricated default; backfill only running Jobs with trusted
ownership, sending unknowns to reconciliation; use `NOT VALID` to protect the future and `VALIDATE` after fixing
history; call it Switched only when every Writer uses the token guard and the old path cannot write; and Contract
only after an observation period. The Day47 UoW manages **one short business transaction**; **Alembic manages
deploy-time schema evolution** — never mix them. Provider and Object Storage are outside DB transactions;
interrupted calls are verified with Job/Attempt/Event and the application correlation/idempotency key. Once real
Lease data or Provider side effects exist, **preserve durable evidence and forward-fix/reconcile — never a
DROP-COLUMN downgrade pretending to return to the past.**

### Engineering Thinking

The whole lesson is one idea: schema change is a controlled, evidence-gated transition across data, code, and
external effects — and "the DDL ran" is the smallest part of it.

### Framework Connection

The full Alembic chain + operational backfill + the Day47 recovery boundary, gated by real PostgreSQL evidence
(NOT RUN here).

---

# Common Misconceptions

`upgrade head` success means it's safe

❌ "The migration ran, so the change is done and safe."
✅ That is DDL-on-one-database evidence only — not history, old-Worker, or Provider safety. Safe evolution needs
gated phases and real evidence.

Why beginners think this: no error means success.
How to remember: DDL executed ≠ migration complete.

Add NOT NULL with a default to be safe

❌ "Give the new columns a default so old rows are valid."
✅ A default is a claim about every existing row; if you can't prove it, add nullable with no fabricated default —
NULL means "no proved ownership."

Why beginners think this: NOT NULL feels cleaner.
How to remember: don't fabricate history.

`UPDATE ... RETURNING` enforces the new rule

❌ "Use a guarded UPDATE to enforce future Lease validity."
✅ That's the Day47 runtime mechanism. Migration compatibility uses `CHECK ... NOT VALID` (future) + `VALIDATE`
(past).

Why beginners think this: they know the runtime guard.
How to remember: NOT VALID protects the future; VALIDATE proves the past.

`VALIDATE` can skip stubborn rows

❌ "Exclude the violating rows so VALIDATE passes."
✅ VALIDATE failing means Backfill/reconciliation isn't done; an exception queue is not resolution. Fix the rows.

Why beginners think this: they want a green run.
How to remember: VALIDATE proves the whole history.

Backfill belongs in `upgrade()`

❌ "Loop over rows in the migration to fill data."
✅ Backfill is a restartable operational step with FOR UPDATE SKIP LOCKED, off the migration; no long loop in
`upgrade()`, no Provider.

Why beginners think this: it's a data change, so it feels like a migration.
How to remember: migrations do DDL; operators do data motion.

Switch = deploy the new binary

❌ "New code is out, so we've switched."
✅ Switch requires the old write path to be closed for every Writer; deploying the binary is necessary, not
sufficient.

Why beginners think this: the code is the change.
How to remember: lock the old door, not just open the new one.

Downgrade undoes a real migration

❌ "If something breaks, downgrade to go back."
✅ After real Lease data / Provider side effects, downgrade is not a time machine — forward-fix and reconcile;
Contract is destructive and last.

Why beginners think this: downgrade sounds like undo.
How to remember: roll back code; you cannot roll back facts or paid calls.

`stamp` proves the schema

❌ "Stamp the database and it's at that version."
✅ `stamp` writes `alembic_version` and does no DDL; only stamp after independently proving the schema matches.

Why beginners think this: the version row looks authoritative.
How to remember: `alembic_version` is a declaration, not a proof.

Migrate on app startup

❌ "Run `alembic upgrade` when the FastAPI app boots."
✅ Alembic is a deployment control plane, separate from FastAPI startup and the request/Job UoW; the app must not
self-migrate.

Why beginners think this: it's convenient.
How to remember: deploy-time schema ≠ request-time app.

Offline `--sql` (or SQLite) proves behavior

❌ "The DDL rendered / SQLite passed, so it works."
✅ Offline render and SQLite/fake sessions are not PostgreSQL runtime proof; real `NOT VALID`/`VALIDATE`/lock
behavior needs PostgreSQL.

Why beginners think this: it produced SQL / a test passed.
How to remember: evidence must match the claim.

Outbox intent proves the Provider ran

❌ "There's an Outbox row, so the Provider succeeded."
✅ Outbox is dispatch intent, not remote-effect proof; verify with Job/Attempt/Event + correlation and
Provider/Artifact.

Why beginners think this: the row exists.
How to remember: intent to send ≠ proof it happened.

---

# Engineering Trade-offs

## Phased Expand/Contract vs one all-at-once migration

Phasing costs multiple deploys and a compatibility window but lets old and new Workers coexist and keeps every
step reversible-until-Contract; all-at-once is one step but breaks old writers, fabricates history, and has no
safe back-out. For a populated, multi-writer table, phase it.

## `NOT VALID` then `VALIDATE` vs a plain validating CHECK

`NOT VALID` protects new writes instantly and defers the full-table validation, then `VALIDATE` proves history
under a lighter lock; a plain `ADD CONSTRAINT CHECK` scans and locks the whole table up front and fails the whole
migration on any legacy violation. On a large live table, split them.

## Backfill as an operator script vs in `upgrade()`

An operator script is restartable, batched, and cancellable with the database as checkpoint, at the cost of a
separate runbook; a `upgrade()` loop is "one command" but holds a long transaction, isn't restartable, and blocks
the deploy. Keep Backfill out of the migration.

## Forward-fix vs destructive downgrade after real data

Forward-fix preserves durable evidence and avoids duplicate paid calls, at the cost of writing a corrective
migration; a destructive downgrade "feels" like undo but loses data/history and can double-execute Providers.
Once real data/side effects exist, forward-fix.

## Autogenerate vs hand-written migrations

Autogenerate is fast for column/constraint diffs but must be reviewed for locks, data semantics, and
multi-version safety; hand-written migrations are more work but explicit about operational risk. Use autogenerate
as a draft, review always, and hand-write anything with data motion or lock risk.

## Alembic control plane vs app-managed migrations

A separate control plane keeps deploy-time schema changes explicit and auditable, at the cost of a deploy step;
app-startup migration is convenient but hides destructive DDL and couples schema to request traffic. Keep the
control plane separate.

---

# Hands-on Exercises

These map to the runnable artifact and its tests, which **were executed** (Python 3.10.12, Alembic 1.13.1,
SQLAlchemy 2.0.29, pytest 7.4.3 → **16 passed**; install via `requirements-day48.txt`), plus an offline `alembic
upgrade --sql` render. All of this is **static/offline evidence** with **no database connection**; a real
**PostgreSQL runtime** `NOT VALID`/`VALIDATE`/backfill test is **NOT RUN**, and SQLite/fake sessions are not
PostgreSQL proof.

Run the tests / render DDL:

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day48.txt
python3 -m py_compile day48_lease_backfill.py test_day48_alembic.py
python3 -m pytest -q test_day48_alembic.py
python3 -m alembic -c day48_alembic/alembic.ini upgrade 0001_baseline:head --sql   # offline DDL render, no DB
```

### Exercise 1: Why all-at-once is unsafe

Question: with old Workers on a populated table, why can't you add NOT NULL Lease columns and flip everyone in
one migration?

Expected Output: old Workers don't set the new columns (rejected/fabricated), and history can't be defaulted;
split into Expand/Backfill/Validate/Switch/Contract.

Follow-up: what does `alembic upgrade head` success actually prove?

### Exercise 2: Expand safely

Question: write the Expand DDL and say what a NULL means.

Expected Output: nullable `lease_owner`/`lease_token`/`lease_expires_at`, no default; NULL = no proved ownership;
add the coherence CHECK `NOT VALID`.

Follow-up: why must you not generate tokens for unknown running Jobs?

### Exercise 3: `NOT VALID` vs `VALIDATE`

Question: how do you protect future writes now but prove history later?

Expected Output: `CHECK ... NOT VALID` protects new writes immediately; `VALIDATE CONSTRAINT` (a separate
revision) proves history after violations are resolved.

Follow-up: what does a failing `VALIDATE` tell you?

### Exercise 4: Classify Jobs

Question: for queued, terminal, trusted-running, and unknown-running Jobs, which are backfilled?

Expected Output: only trusted-running; queued/terminal get none; unknown-running goes to reconciliation (never
fabricated).

Follow-up: what is the dividing line? (Provable ownership.)

### Exercise 5: Restartable Backfill

Question: design the backfill selection and batching.

Expected Output: `running AND lease_owner IS NULL AND lease_backfill_state IS NULL` (+ trusted evidence), short
tx, `FOR UPDATE SKIP LOCKED` batches, idempotent, DB state = checkpoint, no Provider, not in `upgrade()`; unknown
ownership is routed to a persistent `lease_backfill_state='reconcile'` marker (no fabrication) so the loop
terminates and a restart never re-selects it.

Follow-up: why is Lease expiry the wrong batching mechanism, and why must the reconciliation state be persisted
rather than counted in memory?

### Exercise 6: The Switch gate

Question: is deploying the new binary a completed Switch?

Expected Output: no — every Writer must use the token protocol and the old write path must be closed.

Follow-up: which writers are easy to forget? (Recovery, admin scripts, completion/failure paths.)

### Exercise 7: Contract vs forward-fix

Question: after real Lease data and Provider side effects, do you downgrade to fix a problem?

Expected Output: no — forward-fix and reconcile; Contract is destructive and last, after observation.

Follow-up: why is a destructive downgrade dangerous here? (Lost data + duplicate paid calls.)

### Exercise 8: Alembic graph and baseline

Question: what makes multiple heads, and how do you onboard an existing Day42 DB vs a new one?

Expected Output: parallel revisions -> merge revision; existing DB proven-then-`stamp`ed (no DDL); new DB applies
raw SQL, stamps, upgrades. `alembic_version` is a declaration.

Follow-up: is an autogenerate diff a migration? (No — a candidate to review.)

### Exercise 9: Control-plane boundary

Question: what belongs in `env.py`, and where does `CREATE INDEX CONCURRENTLY` go?

Expected Output: minimal `env.py` (DB config + `Base.metadata` + execution), no FastAPI app, no startup
migration; concurrent index outside a migration transaction with invalid-index cleanup.

Follow-up: why must the app not self-migrate on startup?

### Exercise 10: Real PostgreSQL `NOT VALID` test

Question: design a runtime test proving `NOT VALID`/`VALIDATE`.

Expected Output: create a legacy violating row; apply Expand; prove the old row survives; prove a new illegal
write is rejected; prove `VALIDATE` fails until the row is repaired. (NOT RUN here; SQLite is not proof.)

Follow-up: why isn't offline `--sql` or a fake session enough?

### Exercise 11: The integrated failure drill

Question: Expand deployed, real tokens exist, faulty guard, old Worker may write, unknown Provider outcomes.
Recover.

Expected Output: stop old claims/faulty paths; prevent bypass writers; preserve Lease data; drain/isolate; load
evidence in a new UoW; verify Provider/Artifact; guarded completion only if confirmed else preserve unknown;
forward-fix; then Backfill/Validate/observe/Contract.

Follow-up: why is Outbox intent not Provider-success proof?

---

# Relevant Framework Connections

## Alembic

The lesson's core: the `revision`/`down_revision` graph, `alembic history`/`heads`, merge revisions,
`autogenerate` review, baseline/`stamp`, a minimal `env.py`, offline `--sql` rendering, and separated
Expand/Validate/Contract revisions. Alembic is a deployment control plane, not FastAPI startup or a Day47 UoW.

## PostgreSQL

`CHECK ... NOT VALID` + `VALIDATE CONSTRAINT`, `FOR UPDATE SKIP LOCKED`, transactional/locking boundaries, and
`CREATE INDEX CONCURRENTLY` (non-transactional, invalid-index cleanup). Real runtime behavior is the authority
and is NOT RUN here.

## SQLAlchemy 2.0

Day46 `Base.metadata` is autogenerate **input**, not the database authority; the async application sessions/UoWs
(Day47) stay separate from migration execution.

## FastAPI / Worker processes

The app must not self-run migrations on startup; old/new Worker drain and the Writer-protocol Switch are
operational gates, not deploy events. No FastAPI/Worker runtime was executed in Day48.

---

# AI Backend Connections

## Lease ownership protects paid Provider calls

Multi-tenant long-running AI Jobs use Lease ownership to prevent stale/double execution of expensive Provider
calls — which is exactly why the Lease columns must be evolved in safely without fabricating ownership.

## Paid Provider calls stay outside migrations and Backfill

A Provider call is never made inside Backfill or a migration; an interrupted call is an **unknown outcome**
recovered with Job/Attempt/Event + correlation/idempotency evidence, never a blind re-call.

## Object Storage and Outbox are outside DB rollback

Artifact references and external bytes live outside database rollback (Day49 is a future connection), and the
Outbox row is dispatch **intent**, not proof the remote effect happened (Day50/Day55 are future boundaries and
must not be claimed as implemented).

## Recovery is evidence-based

Migration-window recovery loads durable Job/Attempt/Event/correlation evidence and verifies Provider/Artifact
before completing — the same discipline as Day47, now under a schema change.

---

# English Interview

The student requested a direct synthesis ("你帮我回答吧") for the final answer; the model answers below are the
Tech-Lead-taught responses, recorded as such rather than as independently authored student answers.

## Key Vocabulary

Alembic, revision, `down_revision`, merge revision, `alembic_version`, baseline, `stamp`, `autogenerate`, Expand/
Backfill/Validate/Switch/Contract, `CHECK ... NOT VALID`, `VALIDATE CONSTRAINT`, `FOR UPDATE SKIP LOCKED`, forward-
fix vs downgrade, `CREATE INDEX CONCURRENTLY`, control plane.

## Useful Expressions

"A migration is a versioned transition across schema, data, and every writer." · "`upgrade` success is only DDL
evidence." · "`NOT VALID` protects the future; `VALIDATE` proves the past." · "Backfill is operational, not a
migration loop." · "Switch closes the old write path." · "After real data, forward-fix, don't downgrade." ·
"`stamp` does no DDL."

## Beginner Question — What is Alembic, and why is `alembic upgrade head` succeeding not the same as a safe migration?

Model answer:

> "Alembic is a database migration tool that records schema changes as a versioned graph of revisions, each with
> a `down_revision` linking it to its predecessor. `alembic upgrade head` running successfully only means the DDL
> executed on one database; it does not prove that existing rows are compatible, that old and new application
> versions can coexist, or that external side effects are safe. Safe migration is a phased, evidence-gated
> process, not a single command."

## Intermediate Question — Explain `NOT VALID` versus `VALIDATE`, and why they are separate steps on a populated table.

Model answer:

> "On a large, populated table you add the new rule as `CHECK ... NOT VALID`: it immediately enforces the rule on
> every new INSERT and UPDATE while temporarily tolerating pre-existing violating rows, and it avoids a big
> blocking full-table scan. After you have backfilled and reconciled the legacy rows, you run `VALIDATE
> CONSTRAINT` in a separate step to prove the historical rows also comply. They're separate because the future
> protection and the historical proof are gated by different work — you protect new writes immediately but only
> validate the past once it's actually fixed, and a failing `VALIDATE` tells you the backfill isn't done."

## Senior Question — Expand has deployed, real Lease tokens exist, the token guard is faulty, an old Worker may still write, and some Provider outcomes are unknown. How do you recover?

Model answer:

> "I stop old claims and the faulty paths and prevent any bypass writer, while preserving the real Lease data —
> I do not destructively downgrade, because real data and Provider side effects exist. I drain and isolate old
> Workers, then in a new Unit of Work I load the durable Job, Attempt, Event, and correlation evidence and verify
> the Provider and Artifact; I run a new guarded completion only when the external outcome is confirmed,
> otherwise I preserve an unknown/recovery state rather than re-calling the Provider. Then I forward-fix the
> guard, reconcile affected rows, complete the backfill, run `VALIDATE`, observe, and only then Contract. The
> Outbox row is dispatch intent, not proof the Provider ran."

## Common Weak Answer

"I autogenerate a migration that adds the Lease columns NOT NULL with defaults, run `alembic upgrade head` on
startup, and downgrade if anything breaks."

## Strong Answer

"I Expand with nullable columns and no fabricated default plus a `CHECK ... NOT VALID`, deploy it first so old
Workers coexist, then run a restartable `FOR UPDATE SKIP LOCKED` backfill outside the migration that fills only
running Jobs with trusted ownership and sends unknowns to reconciliation. I `VALIDATE` in a separate revision
after the history is fixed, Switch every writer onto the token protocol so the old path can't write, and Contract
destructively only after evidence and an observation period. Alembic is a separate deployment control plane, not
FastAPI startup; `stamp` does no DDL and is only safe after proving the schema matches; and once real data or
Provider side effects exist I forward-fix rather than downgrade."

---

# Mental Model Summary

```text
1.  A migration = a versioned transition across SCHEMA + HISTORICAL ROWS + EVERY deployed writer; `upgrade` success is DDL-only evidence.
2.  Safe evolution = Expand -> Backfill -> Validate -> Switch -> Contract, each SEPARATELY GATED by different evidence.
3.  EXPAND: add nullable cols, NO fabricated default (NULL = no proved ownership); never fabricate historical Lease.
4.  Coherence rule via CHECK ... NOT VALID protects EVERY future write NOW while tolerating legacy rows.
5.  VALIDATE CONSTRAINT (a SEPARATE revision) proves HISTORY; it FAILS until Backfill/reconciliation truly resolves violations (an exception queue != resolution).
6.  Classify: queued/terminal = no Lease; trusted-running = backfill; unknown-running = reconciliation (never invented).
7.  BACKFILL is operational + restartable (short tx, FOR UPDATE SKIP LOCKED, idempotent, DB state = checkpoint); NO Provider, NO long loop in upgrade(). Unknown ownership is PERSISTED as lease_backfill_state='reconcile' (no fabrication) so it leaves the candidate set -> the loop TERMINATES and a restart never re-selects it.
8.  Lease EXPIRY is a runtime protocol, not a migration-batch claim; UPDATE ... RETURNING is the Day47 guard, not the compatibility mechanism.
9.  SWITCH = every Writer (Workers/recovery/admin/completion-failure) on the token protocol; the OLD path cannot write. Not merely a new binary.
10. CONTRACT is destructive + LAST (after Validate + Switch + evidence + observation). Once real data/side effects exist -> FORWARD-FIX, not a destructive downgrade.
11. revision/down_revision = the graph + required predecessor (downgrade = reverse traversal); parallel revisions -> multiple heads -> merge revision.
12. autogenerate = a CANDIDATE diff to review (DDL/data/locks/multi-version); Day46 metadata is INPUT, PostgreSQL is authority.
13. BASELINE/stamp: `alembic stamp` writes alembic_version, does NO DDL, safe only after PROVEN match; new DB upgrades from empty, existing DB is stamped then upgraded.
14. env.py stays MINIMAL (DB config + Base.metadata + execution); Alembic control plane != FastAPI startup != Day47 UoW; app never self-migrates. DB URL resolves `-x db_url` > env DAY48_ALEMBIC_DATABASE_URL > ini placeholder (offline-only, no credentials committed).
15. CREATE INDEX CONCURRENTLY is NON-transactional; never inside a migration tx; a failed build leaves an invalid index to inspect/repair before retry.
16. EVIDENCE: static/offline (ScriptDirectory + `--sql` render) proves TEXT/STRUCTURE; real PostgreSQL proves BEHAVIOR (NOT VALID/VALIDATE/locks). SQLite/fake/`upgrade`-success are NOT PostgreSQL proof.
17. Provider/Object Storage are outside DB tx; interrupted calls are UNKNOWN outcomes; Outbox intent != Provider-success proof; recover via Job/Attempt/Event + correlation/idempotency.

Starting model -> reasoning -> correction -> final model:
Initial: an all-at-once Lease revision felt reasonable; UPDATE...RETURNING was proposed for future enforcement;
Lease expiry for backfill batching; Outbox intent as Provider-success proof; stamp/new-vs-existing DB and the full
failure drill were "不知道".
Reasoning: the student saw old Workers are incompatible, refused to fabricate historical Lease, chose forward-fix,
required autogenerate review + Expand-first + a separate control plane + NOT VALID history verification + no long
backfill in upgrade() + an observation period, and knew runtime evidence needs a real run.
Correction: NOT VALID (future) + VALIDATE (past) instead of a runtime guard; FOR UPDATE SKIP LOCKED backfill off the
migration; Switch closes the old write path; stamp does no DDL and needs a proven match; Outbox intent is not proof.
Final: Alembic records schema change as a reviewable revision graph; safe evolution is Expand/Backfill/Validate/
Switch/Contract gated by real evidence; the Day47 UoW handles one short business transaction while Alembic handles
deploy-time schema evolution; Provider/Object Storage side effects are recovered with durable correlation evidence;
after real data, forward-fix and reconcile rather than pretend a destructive downgrade returns to the past.
```

---

# Today's Takeaway

Day48 makes Day36's safe-migration discipline executable with Alembic over the Day46 mapping and Day47 boundary.
A migration is a versioned transition across schema, existing data, and every deployed writer, so successful DDL
is not completion. Expand with nullable columns and no fabricated default plus `CHECK ... NOT VALID`; backfill
only provable running ownership in a restartable operation off the migration; `VALIDATE` the history in a
separate revision; Switch every writer onto the token protocol so the old path can't write; and Contract
destructively only after evidence and an observation period. Alembic is a deployment control plane, distinct
from FastAPI startup and the Day47 request/Job UoW; `stamp` does no DDL; and once real Lease data or Provider
side effects exist you forward-fix and reconcile rather than destructively downgrade.

Most important mental model: Expand -> Backfill -> Validate -> Switch -> Contract, each gated by its own
evidence. Most important production risk: an all-at-once migration (fabricated defaults, no old-Worker window,
destructive downgrade) corrupting history or double-executing paid Provider calls. Most important trade-off:
`NOT VALID` + `VALIDATE` vs a plain validating CHECK on a live table. Most important connection: Day49 persists
Upload/Artifact references on the safely evolved schema. Most important interview answer: `NOT VALID` protects
the future, `VALIDATE` proves the past, and `upgrade` success is only DDL evidence.

Validation status: **16 static/offline tests** are **real executed evidence** — the Alembic revision graph +
migration source were inspected via `ScriptDirectory`, the fake-session backfill control flow was exercised, and
the offline `alembic upgrade --sql` **rendered** the Expand/Validate/Contract DDL, all on Python 3.10.12 / Alembic
1.13.1 / SQLAlchemy 2.0.29 / pytest 7.4.3 → **16 passed** with **no database connection**. But offline render and
static checks are **not** PostgreSQL proof: **PostgreSQL runtime is NOT RUN** (no server; a real `NOT VALID`/
`VALIDATE`/backfill test would apply the Day42 raw SQL and prove behavior), **SQLite/fake sessions are not
PostgreSQL evidence**, and `alembic upgrade` success alone does not prove Backfill/Switch/Contract or production
safety. FastAPI/Worker integration, real Provider, Object Storage, and production migration are all **NOT RUN**.

---

# Before Next Lesson Checklist

```markdown
- [ ] Can I explain why `alembic upgrade head` success is not migration completion?
- [ ] Can I write an Expand migration (nullable, no fabricated default) plus a `CHECK ... NOT VALID`?
- [ ] Can I explain `NOT VALID` vs `VALIDATE` and why they are separate revisions?
- [ ] Can I classify queued/terminal/trusted-running/unknown-running Jobs for backfill vs reconciliation?
- [ ] Can I design a restartable `FOR UPDATE SKIP LOCKED` backfill that lives outside the migration and calls no Provider?
- [ ] Can I define the Switch gate (old write path closed) and the Contract observation gate?
- [ ] Can I justify forward-fix over a destructive downgrade after real Lease data/Provider side effects exist?
- [ ] Can I reason about the revision graph, merge heads, autogenerate review, and baseline/`stamp` (no DDL)?
- [ ] Can I keep Alembic a minimal control plane (no startup migration, no UoW) and handle `CREATE INDEX CONCURRENTLY`?
- [ ] Can I design a real PostgreSQL `NOT VALID`/`VALIDATE` test and say why static/offline/SQLite is not proof?
- [ ] Can I run the Day48 tests + offline `--sql` and state honestly that PostgreSQL runtime is NOT RUN?
```

Preparation for Day49 (Upload Sessions, Object Storage and Artifact Verification): review this safe-evolution
discipline, then preview how verified Upload Sessions and Artifact references are persisted on the safely evolved
model while Object Storage I/O stays outside DB transactions. Day50 (tenant-scoped idempotency + atomic Job +
Outbox intent) remains a later boundary.

---

Engineering Artifact: [projects/ai-backend-data-layer/api/day48-alembic-safe-schema-evolution-design.md](../../projects/ai-backend-data-layer/api/day48-alembic-safe-schema-evolution-design.md) · Alembic: [`day48_alembic/`](../../projects/ai-backend-data-layer/api/day48_alembic) · Backfill: [`day48_lease_backfill.py`](../../projects/ai-backend-data-layer/api/day48_lease_backfill.py) · Tests: [`test_day48_alembic.py`](../../projects/ai-backend-data-layer/api/test_day48_alembic.py)
