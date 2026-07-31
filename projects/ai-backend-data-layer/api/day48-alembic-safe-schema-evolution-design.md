# Day48 — Alembic and Safe AI Backend Schema Evolution (Design + Runbook)

Makes Day36's safe-schema-evolution discipline **executable** with Alembic over the
Day46 SQLAlchemy mapping and the Day47 persistence boundary. A migration is a
**versioned state transition across schema, existing rows, and every deployed
writer** — successful DDL is **not** completion. Runnable artifact:
[`day48_alembic/`](day48_alembic/) (env + revisions), operational backfill:
[`day48_lease_backfill.py`](day48_lease_backfill.py), tests:
[`test_day48_alembic.py`](test_day48_alembic.py), pinned deps:
[`requirements-day48.txt`](requirements-day48.txt).

> Scope honesty: Alembic is a **deployment control plane**, distinct from a Day47
> request/Job UoW and from FastAPI startup (the app must never self-run
> migrations). Day46 `Base.metadata` is autogenerate **input**, not the database
> authority; PostgreSQL / the Day42 raw SQL remain authoritative. **No PostgreSQL
> runtime, integration, or production migration was executed** — see the evidence
> matrix. The evolving scenario is the Day36 **Lease** feature only; Day49 upload,
> Day50 real Outbox/Celery delivery, Day53 Provider SDK, and Day55 worker runtime
> are NOT implemented.

---

## 1. Mental model: a migration is more than DDL

```text
`alembic upgrade head` success = DDL executed on ONE database. It does NOT prove:
  historical rows are compatible, old Workers can coexist, external Provider side effects are safe, or production is safe.
Safe evolution = Day36's phases, each SEPARATELY GATED by different evidence:
  EXPAND (add nullable, no fabricated default) -> BACKFILL (operational, off the migration) -> VALIDATE (prove history)
  -> SWITCH (every Writer uses the new protocol; old path cannot write) -> CONTRACT (destructive; last, after observation).
alembic_version records a version DECLARATION, not a schema PROOF.
```

Evolving scenario: a populated multi-tenant `app.jobs` with **old and new Workers
running concurrently**; the team adds **Lease ownership** (`lease_owner`,
`lease_token`, `lease_expires_at`) to stop stale ownership and double execution of
long paid Provider calls.

---

## 2. Expand (revision `0002_expand_lease`) — columns ONLY (compatibility window)

```text
ALTER TABLE app.jobs ADD COLUMN lease_owner text, ADD COLUMN lease_token uuid, ADD COLUMN lease_expires_at timestamptz;
  -> ALL NULLABLE, NO fabricated default. NULL honestly means "no PROVED Lease ownership".
  -> NO constraint on app.jobs here. This is a PURE Expand -> the OLD/NEW code COMPATIBILITY WINDOW: while only this
     revision is applied an OLD Writer can still update a legacy running Job that has a NULL Lease (no constraint rejects it).
  -> Do NOT generate tokens for queued, terminal, or unprovable running Jobs (fabrication is forbidden).

CREATE TABLE app.job_lease_reconciliation (        -- INDEPENDENT triage queue (Day42 conventions), NOT a column on app.jobs
  reconciliation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id            uuid NOT NULL REFERENCES app.jobs(job_id) ON DELETE RESTRICT,
  reason            text NOT NULL,                 -- CHECK reason IN ('unknown_ownership')
  routed_at         timestamptz NOT NULL DEFAULT now(),
  resolution_status text NOT NULL DEFAULT 'open',  -- CHECK resolution_status IN ('open','resolved')
  resolved_at       timestamptz,
  CONSTRAINT job_lease_reconciliation_job_unique UNIQUE (job_id)  -- one triage row per Job -> idempotent routing
);
  -- NOTE: the reconciliation POLLING/BACKOFF columns (next_attempt_at / last_checked_at / check_attempts) are added by
  --       the SEPARATE additive BRANCH revision 0006 (section 2c), merged back via 0007. This revision stays IMMUTABLE.
  -> WHY a separate table and NOT a marker column on app.jobs: after 0003 the strict jobs_running_requires_lease CHECK
     rejects ANY UPDATE that leaves a row running with a NULL Lease. A "reconcile" marker column would require exactly
     such an UPDATE, so real PostgreSQL would REJECT it (23514) — fake-session tests could not see that. Triage MUST live
     off the business row. This table records "ownership could not be proved" WITHOUT touching app.jobs and WITHOUT
     fabricating any Lease/owner/token/expiry or terminal status.
```

The strict Lease constraints are a SEPARATE later revision (section 2b), so old and new code truly coexist here; the
reconciliation queue is created additively in Expand so routing (section 3) has its target before constraints land.

---

## 2b. Constraints (revision `0003_add_lease_constraints`) — closes the compatibility window

```text
PRECONDITIONS (operator MUST ensure, Alembic cannot): new code deployed & tolerates NULL Lease; OLD Writers DRAINED/ISOLATED.
ALTER TABLE app.jobs ADD CONSTRAINT jobs_lease_triple_coherent CHECK (all-three-NULL OR all-three-NOT-NULL) NOT VALID;
ALTER TABLE app.jobs ADD CONSTRAINT jobs_running_requires_lease CHECK (job_status <> 'running' OR (lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)) NOT VALID;
  -> jobs_running_requires_lease is the Day36 CORE invariant (Day48 field names): a running Job MUST carry a complete Lease.
     A Job ROUTED to the reconciliation queue but still running with a NULL Lease STILL VIOLATES it (triage, not resolution).
  -> No constraint touches app.job_lease_reconciliation here; that table is independent triage, not part of the Lease invariant.
  -> NOT VALID does NOT mean "old Writers unaffected": it skips only the one-time SCAN of legacy rows, but ENFORCES the rule
     on EVERY future INSERT/UPDATE by ANY writer version. An OLD Worker updating a running-without-Lease Job is REJECTED
     (23514). THAT is why this revision must land ONLY after the old write path is drained/isolated. Pure Expand = compat
     window; the strict NOT VALID Lease constraint = old Writers can no longer write a running-without-Lease Job.
  -> NOT validated here (0004 VALIDATEs it). No Backfill loop, no Provider call, no long transaction.
```

---

## 2c. Reconciliation polling columns (revision `0006_add_reconciliation_polling`, merged by `0007`) — ADDITIVE BRANCH

```text
ALTER TABLE app.job_lease_reconciliation
  ADD COLUMN next_attempt_at timestamptz NOT NULL DEFAULT now(),  -- POLLING clock; DDL default makes existing OPEN rows due now
  ADD COLUMN last_checked_at timestamptz,                          -- audit: last evidence check (NULL = not checked yet)
  ADD COLUMN check_attempts  integer NOT NULL DEFAULT 0;           -- audit/backoff counter (existing rows start at 0)
ALTER TABLE app.job_lease_reconciliation
  ADD CONSTRAINT job_lease_reconciliation_check_attempts_nonneg CHECK (check_attempts >= 0);
CREATE INDEX IF NOT EXISTS ix_job_lease_reconciliation_due
  ON app.job_lease_reconciliation (next_attempt_at) WHERE resolution_status = 'open';  -- partial index for the due-scan
  -> WHY A SEPARATE, FORWARD BRANCH (not an edit of any published revision, and not a linear append after 0005): an
     applied Alembic revision is IMMUTABLE, and we have NO verifiable evidence that 0004/0005 were never applied. Editing
     0002/0003 or rewriting 0004/0005.down_revision would leave an already-applied database inconsistent (it would never
     auto-run the new revision) and the resolver would fail on undefined columns. A pure LINEAR append after 0005 would
     also be wrong: a database still at 0003 would then have to run Validate (0004) + Contract (0005) BEFORE reaching the
     polling columns — but the resolver runs in the Backfill phase, BEFORE Validate. Forcing Validate first is the exact
     ordering bug to avoid.
  -> PLACEMENT: down_revision = 0003_add_lease_constraints — an INTENTIONAL BRANCH off 0003 so a 0003-stage database can
     reach the polling schema WITHOUT Validate/Contract, while 0004/0005 databases can also apply it (their applied set
     already contains 0003). This creates a second head (0005 vs 0006); the merge revision 0007_merge_reconciliation_polling
     (down_revision = (0005, 0006), NO DDL) re-unifies to a SINGLE head. This revision only touches the INDEPENDENT queue
     table, never app.jobs, so it neither depends on nor affects the strict jobs_running_requires_lease CHECK.
  -> EXISTING ROWS: the DDL DEFAULT now() gives every historical OPEN record next_attempt_at = migration time, so it is
     immediately DUE for the next reconciliation scan. This is a DDL default applied by ADD COLUMN — NOT a fabricated
     Lease/owner/token/terminal/Provider outcome, and NOT a separate data-backfill loop (none is needed; now() IS the
     correct initial value). DDL default vs historical rows vs data backfill are three distinct things; here only the DDL
     default is needed.
  -> INDEX: a plain CREATE INDEX inside the migration briefly locks writes on this SMALL triage table (only unknown-
     ownership running Jobs), which is acceptable. If the queue were ever large, build it CREATE INDEX CONCURRENTLY OUTSIDE
     a migration transaction (it cannot run inside one). No long data-backfill loop lives in this upgrade().
```

---

## 3. Backfill (operational script, NOT an Alembic `upgrade()`)

```text
day48_lease_backfill.py (operator-run, restartable): SHORT tx + FOR UPDATE SKIP LOCKED batches, idempotent predicates,
  DB state = the recovery checkpoint. Candidate query (excludes already-routed Jobs via the INDEPENDENT queue, NOT a marker):
    SELECT j.job_id FROM app.jobs j
     WHERE j.job_status='running' AND j.lease_owner IS NULL
       AND NOT EXISTS (SELECT 1 FROM app.job_lease_reconciliation r WHERE r.job_id=j.job_id)
     ORDER BY j.created_at FOR UPDATE SKIP LOCKED LIMIT :n
  automatic_backfill_candidates = running AND lease_owner IS NULL AND NOT already in the reconciliation queue (auto-loop fillable).
  A PROVED Job gets its Lease (apply_lease_evidence: guarded UPDATE app.jobs SET lease-triple WHERE running AND lease_owner IS NULL
    RETURNING — single responsibility, writes ONLY app.jobs, sets NO marker).
  An UNKNOWN-ownership Job is ROUTED to the INDEPENDENT reconciliation queue (route_to_reconciliation:
    INSERT INTO app.job_lease_reconciliation (job_id, reason) VALUES (:job_id,'unknown_ownership') ON CONFLICT (job_id) DO NOTHING
    RETURNING reconciliation_id) — this NEVER touches app.jobs (so it is LEGAL after the strict 0003 constraint: no UPDATE that
    leaves the row running+NULL-Lease) and fabricates NO Lease owner/token/expiry. Because a proved Job gets its Lease and a
    routed Job is excluded by the NOT EXISTS join, the auto-loop TERMINATES (even with max_batches=None) and a RESTART never
    re-selects the same unknown Job. close_reconciliation_record(job_id) is a SEPARATE audited step (marks a queue row
    'resolved' AFTER the Job is truthfully resolved) — it too never mutates app.jobs.
  BUT routing is TRIAGE, not RESOLUTION:
    unresolved_running_without_lease = ALL running app.jobs rows with a NULL Lease, INCLUDING Jobs routed to the queue
      (count_unresolved_running_without_lease: SELECT count(*) FROM app.jobs WHERE job_status='running' AND lease_owner IS NULL;
       no join/anti-join against the queue — routing did not change app.jobs).
      This is the Day36 remaining_targets and the HARD VALIDATE/Switch/Contract precondition (must be 0). The
      automatic loop stopping does NOT reduce it and does NOT mean the history is compliant.
  RESOLVING A QUEUED ROW IS A SEPARATE PATH — the AUTOMATIC loop never re-selects it (select_backfill_batch excludes
    queued Jobs via NOT EXISTS, exactly as real SQL requires; a re-run selects nothing). When trusted evidence appears
    LATER, run_reconciliation_resolution drives SHORT restartable batches over DUE resolution_status='open' records whose
    Job is still running+unowned (select_open_reconciliation_batch: JOIN app.jobs, WHERE r.resolution_status='open' AND
    r.next_attempt_at <= now() AND j.job_status='running' AND j.lease_owner IS NULL, ORDER BY r.next_attempt_at,
    FOR UPDATE OF r SKIP LOCKED). For each, in ONE short tx: (1) guarded UPDATE app.jobs writes the full Lease triple
    (apply_lease_evidence); (2) ONLY if that UPDATE actually affected the row is the queue record marked
    resolved+resolved_at (close_reconciliation_record).
  NO EVIDENCE YET -> the record stays OPEN and is DEFERRED (defer_reconciliation_record): a QUEUE-ONLY, short, audited
    UPDATE bumps check_attempts + last_checked_at and pushes next_attempt_at into the FUTURE by an exponential, capped
    backoff (base 60s, doubling, cap 3600s). It NEVER fabricates a Lease, NEVER requeues, NEVER touches app.jobs /
    job_status, NEVER calls a Provider. Because the selector only returns DUE records, deferring means the SAME record is
    not re-selected in this loop, so run_reconciliation_resolution TERMINATES in real PostgreSQL even with max_batches=None
    — termination rests on the due-filter + forward backoff, NOT on a fake session returning an empty batch. This is
    reconciliation POLLING/BACKOFF, explicitly NOT Job retry and NOT Provider retry (no external call is repeated; we only
    re-check whether trusted ownership evidence has appeared). If the guarded UPDATE hits 0 rows (the Job no longer matches
    running+unowned), the record is NOT closed by that attempt — closing is gated on this UoW's own successful write,
    keeping the pass idempotent + restartable.
  A routed row is resolved ONLY by (a) a TRUSTED Lease backfill via run_reconciliation_resolution (apply_lease_evidence
    sets the Lease triple on app.jobs, then close_reconciliation_record closes the record)
    or (b) an AUDITED real recovery ROUTED by classify_unknown_running_recovery (a NON-mutating classifier) to a FULL
    boundary: verified 'succeeded' -> the Day47 GUARDED COMPLETION UoW (finished_at + ResultArtifact + job_succeeded
    Event together); verified 'failed'/'cancelled' -> the guarded terminal-recovery path (state machine + Event + audit);
    an UNVERIFIED outcome -> KEEP_UNKNOWN (stay unknown/reconciliation, NEVER requeue, NEVER blind Provider retry);
    'queued'/'running'/any other status -> UnsafeRecoveryError. Day48 CLASSIFIES/ROUTES and NEVER bare-flips a status
    (a bare UPDATE would bypass the Day47 completion contract). run_backfill exposes unresolved_running_without_lease so
    "the loop stopped" is never reported as "done".
  Calls NO Provider; holds NO long transaction. NOT the Day47 Lease runtime protocol and NOT a Lease-expiry batch claim.
```

Long Backfill/reconciliation loops must **never** live in a migration `upgrade()`.

---

## 4. Validate (revision `0004_validate_lease`) and NOT VALID vs VALIDATE

```text
ALTER TABLE app.jobs VALIDATE CONSTRAINT jobs_lease_triple_coherent;
ALTER TABLE app.jobs VALIDATE CONSTRAINT jobs_running_requires_lease;   -- Day36 CORE: every running row has a complete Lease
  -> Proves HISTORICAL rows also satisfy the already-enforced future rules; lighter lock, no re-scan of enforced rows.
  -> jobs_running_requires_lease FAILS while any running-without-Lease row remains (queue-routed rows INCLUDED),
     i.e. while unresolved_running_without_lease > 0. Run ONLY after Backfill/reconciliation TRULY resolved every
     violation via (a) a trusted Lease backfill or (b) an audited real recovery — an exception queue is NOT resolution.
NOT VALID (Expand)  = protect the FUTURE now (new writes checked; legacy tolerated).
VALIDATE (here)     = prove the PAST is compliant. Fails if any legacy violation remains -> that is the signal to finish
                      Backfill/reconciliation, not to exclude rows.
```

Expand and Validate are **separate revisions**: the phases are gated by
deployment, data, Writer-protocol, and observation evidence — not merely to avoid
one long transaction.

---

## 5. Switch and Contract (revision `0005_contract_legacy`)

```text
SWITCH (operational gate, not a single DDL): EVERY Writer -- Workers, recovery, admin/scripts, completion/failure paths --
  uses the Lease-token protocol and the OLD path can no longer write. It is NOT merely deploying a new binary.
CONTRACT is DESTRUCTIVE and LAST. Preconditions (Alembic cannot check them; an operator must):
  Validate succeeded + Switch complete + evidence + an observation period with healthy signals.
  Example contraction: DROP COLUMN app.jobs.result_object_key (the Day42 legacy single-artifact pointer, superseded by
  result_artifacts; Day42/003 deliberately deferred the drop to this safe sequence).
Once real Lease data or Provider side effects exist: FORWARD-FIX + reconciliation, NOT a destructive downgrade
  (a downgrade is not a time machine; dropped bytes/history do not return).
```

---

## 6. Alembic specifics and the control-plane boundary

```text
revision + down_revision define the upgrade/downgrade GRAPH and the required predecessor state (downgrade is the reverse
  traversal of the same graph). Parallel revisions create MULTIPLE HEADS -> need an Alembic MERGE revision.
Baseline (0001) = a STAMP TARGET: `alembic stamp 0001_baseline` writes alembic_version and does NO DDL -- only after an
  existing DB is INDEPENDENTLY proven to match the Day42 baseline exactly. New/empty DB: apply the Day42 raw SQL, stamp
  0001, then upgrade to 0002+. The Day42 raw SQL (sql/001 + sql/003) stays the schema authority.
autogenerate emits a CANDIDATE diff, not an approved migration -> review DDL, data semantics, locks, multi-version
  compatibility, operational work, and downgrade/forward-fix conditions.
env.py stays MINIMAL: migration DB config + target Base.metadata + Alembic execution. It does NOT build the FastAPI app
  or share a business Session. Alembic != FastAPI startup != a Day47 request/Job UoW.
Database URL resolution (env.py, highest priority first): `alembic -x db_url=<url>` > env `DAY48_ALEMBIC_DATABASE_URL`
  > [`alembic.ini` sqlalchemy.url, OFFLINE ONLY]. The ini value is a NON-CREDENTIAL PLACEHOLDER used ONLY for offline
  `--sql` rendering (dialect selection; it never connects and is NOT a production connection). It is NOT an online
  connection fallback: ONLINE mode REQUIRES a real external URL (`-x db_url` or `DAY48_ALEMBIC_DATABASE_URL`) and
  FAILS FAST otherwise (no credential printed). env.py is import-safe so the pure resolve_database_url(...,
  allow_placeholder=...) is unit-testable; NEVER commit a real connection string/username/password/token.
CREATE INDEX CONCURRENTLY is NON-transactional -> never inside a normal migration transaction; a failed concurrent build
  can leave an INVALID index that must be inspected and repaired/removed before retry. (Not used in this Lease chain.)
Keep Expand, Validate, Contract as SEPARATELY gated revisions; no long Backfill/reconciliation loop in upgrade().
```

---

## 7. Integrated failure / recovery drill (conceptual)

```text
State: Expand deployed, REAL Lease tokens exist, the token guard is FAULTY, an old Worker may still write, and some
       Provider outcomes are UNKNOWN.
Do: stop old claims + faulty paths; prevent bypass Writers; PRESERVE Lease data; drain/isolate old Workers; load
    Job/Attempt/Event/correlation evidence in a NEW UoW; verify Provider/Artifact; run a new guarded completion ONLY when
    confirmed, else PRESERVE unknown/recovery state; FORWARD-FIX; then Backfill/reconcile, Validate, observe, Contract.
Never: fabricate Lease ownership, call the Provider in Backfill, blindly repeat an interrupted paid call, put a long
    Backfill loop in upgrade(), auto-migrate on FastAPI startup, or destructively downgrade past real data/side effects.
```

---

## Deployment assumption, revision immutability, and rollout matrix

```text
DEPLOYMENT ASSUMPTION (explicit, and NOT written as fact): an applied Alembic revision is IMMUTABLE, and we have NO
  verifiable evidence about how far any real database was migrated. We therefore do NOT assume "the last applied revision
  can only be 0003". We design so that a database recorded at ANY of 0003 / 0004 / 0005 is upgraded correctly. (Evidence
  boundary: within THIS repository no PostgreSQL server was ever available and the offline `--sql` render never connects,
  so nothing here was applied to a real DB — but the repo models correct production practice, so we take the safe path.)

WHY WE NO LONGER REWRITE HISTORY:
  A previous attempt rewrote 0004_validate_lease.down_revision to point at the new polling revision. That is only correct
  if 0004/0005 were never applied — which we cannot prove. If a database is already recorded at 0004 or 0005, changing a
  historical down_revision does NOT make Alembic go back and run the inserted revision; the polling columns would never be
  added and run_reconciliation_resolution() would fail on undefined columns. So we keep EVERY published revision's
  parentage intact and add the columns via a FORWARD, additive BRANCH + MERGE.

REVISION GRAPH (single head via intentional branch + merge):

    0001 -> 0002 -> 0003 --> 0004 -> 0005 ----\
                        \                        >--> 0007_merge_reconciliation_polling  (single head)
                         --> 0006_add_reconciliation_polling ---------/

  * 0006_add_reconciliation_polling: down_revision = 0003 (BRANCH). Additive ADD COLUMN + partial index only.
  * 0007_merge_reconciliation_polling: down_revision = (0005_contract_legacy, 0006_add_reconciliation_polling). NO DDL.
  Published parentage of 0002/0003/0004/0005 is UNCHANGED. The branch off 0003 lets a 0003-stage DB obtain polling
  columns WITHOUT running Validate/Contract; the merge restores a single head.

UPGRADE MATRIX (operator order matters — see the WARNING):

  | Current alembic_version        | Steps                                                                            |
  |--------------------------------|----------------------------------------------------------------------------------|
  | NEW / empty DB                 | apply Day42 baseline SQL; `alembic stamp 0001_baseline`; `alembic upgrade head`.  |
  |                                | (No legacy running-without-Lease rows exist, so there is nothing to reconcile —   |
  |                                |  running Validate/Contract as part of `upgrade head` is safe.)                    |
  | 0003_add_lease_constraints     | 1) `alembic upgrade 0006_add_reconciliation_polling`  (gets polling schema, does  |
  | (strict-constraint stage)      |    NOT run Validate/Contract). 2) deploy the resolver. 3) run reconciliation until |
  |                                |    count_unresolved_running_without_lease() == 0. 4) THEN `alembic upgrade head`  |
  |                                |    (runs 0004 Validate, 0005 Contract, 0007 merge).                               |
  | 0004_validate_lease            | `alembic upgrade head` (applies 0006 then 0007). Validate already passed, so      |
  | (already validated)            | unresolved == 0 and there is NO legacy reconciliation to do; the columns are added |
  |                                | for SCHEMA COMPATIBILITY with the resolver code / any future routed records.       |
  | 0005_contract_legacy           | `alembic upgrade head` (applies 0006 then 0007). Same as 0004: schema-compat only; |
  | (already contracted)           | no legacy reconciliation. Do NOT try to add columns by editing a historical revision. |

  WARNING — DO NOT blindly `alembic upgrade head` on a 0003-stage DB: that would run 0004 (Validate) and 0005 (Contract)
  BEFORE reconciliation, and Validate would (correctly) FAIL while running-without-Lease rows remain. Upgrade to 0006
  first, reconcile to unresolved == 0, THEN `upgrade head`.

RUNTIME DEPLOYMENT ORDER: the resolver (run_reconciliation_resolution) references the polling columns, so it must be
  deployed/started ONLY AFTER 0006 is applied on its target database (verify the columns exist first). Never deploy the
  polling runtime against a database that has not yet applied 0006.

VERIFY IN REAL POSTGRESQL (NOT RUN here — no server):
  * current revision:      `alembic -c day48_alembic/alembic.ini current`  and  `SELECT version_num FROM alembic_version;`
  * polling columns exist:  `\d+ app.job_lease_reconciliation`  (expect next_attempt_at NOT NULL DEFAULT now(),
                            last_checked_at, check_attempts NOT NULL DEFAULT 0, and index ix_job_lease_reconciliation_due)
                            or:  SELECT column_name FROM information_schema.columns
                                 WHERE table_schema='app' AND table_name='job_lease_reconciliation'
                                   AND column_name IN ('next_attempt_at','last_checked_at','check_attempts');
  * revision graph:        `alembic -c day48_alembic/alembic.ini heads`    (expect single head 0007_merge_reconciliation_polling)
                           `alembic -c day48_alembic/alembic.ini history`  (expect the 0003->0006 branch + the 0007 merge)
```

---

## Run instructions

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day48.txt
python3 -m py_compile day48_lease_backfill.py test_day48_alembic.py
python3 -m pytest -q test_day48_alembic.py
# optional OFFLINE DDL render (no DB connection; static evidence only):
python3 -m alembic -c day48_alembic/alembic.ini upgrade 0001_baseline:head --sql
```

---

## Validation and evidence classification

```text
CONCEPTUAL / STATIC REVIEW : the runbook mirrors Day36's phases and the classroom trajectory.
STATIC ALEMBIC (RUN)       : 40 pytest cases inspect the revision graph + migration source via Alembic's ScriptDirectory
                             (single head 0007_merge_reconciliation_polling via an intentional BRANCH + MERGE: 0006_add_reconciliation_polling branches off 0003 and is merged with the 0005 Contract head by 0007 — every PUBLISHED revision (0002/0003/0004/0005) keeps its ORIGINAL parentage (no history rewrite), the polling columns are added FORWARD/additively, and a 0003-stage DB can reach polling BEFORE Validate; PURE Expand (Lease columns +
                             the INDEPENDENT app.job_lease_reconciliation queue table, NO constraint on app.jobs = the
                             compatibility window); a SEPARATE constraint revision adds the triple + Day36
                             jobs_running_requires_lease NOT VALID with a drain/isolate precondition; Validate validates
                             BOTH constraints; Contract destructive+gated; no loop in any upgrade()/downgrade(); minimal
                             env.py) plus FAKE-SESSION backfill control flow (SKIP LOCKED automatic-candidate batch
                             excluding queue-routed rows via NOT EXISTS; fills known by setting the Lease triple on app.jobs
                             only; ROUTES unknown by INSERT into the queue (ON CONFLICT DO NOTHING) with NO app.jobs write
                             and no fabrication; close_reconciliation_record audits the queue only; TERMINATES when all
                             candidates are unknown; restart does not re-select a routed Job BUT it STILL counts in
                             unresolved_running_without_lease (triage != resolution); the DEDICATED
                             run_reconciliation_resolution path selects DUE OPEN records (next_attempt_at <= now(),
                             FOR UPDATE OF r SKIP LOCKED) and, when trusted evidence appears LATER, writes the Lease triple on
                             app.jobs THEN closes the record in one tx — only a real Lease write drives unresolved -> 0; no
                             evidence -> the record stays OPEN and is DEFERRED (queue-only backoff pushing next_attempt_at
                             forward with check_attempts/last_checked_at), so the loop TERMINATES via the due-filter + backoff
                             (NOT via a mocked empty batch) — reconciliation POLLING, not Job/Provider retry; a 0-row UPDATE
                             does not close the record; recovery ROUTING (non-mutating): unknown -> KEEP_UNKNOWN, verified
                             succeeded -> Day47 completion UoW, failed/cancelled -> guarded terminal-recovery, a 'queued'
                             requeue / 'running' / bad status -> UnsafeRecoveryError; the VALIDATE precondition
                             unresolved==0 is reached only after real resolution; idempotent guarded writes; no Provider) and the database-URL resolution (`-x db_url` > env DAY48_ALEMBIC_DATABASE_URL; ini
                             placeholder is OFFLINE-only and online FAILS FAST without an external URL). No database connection.
OFFLINE ALEMBIC SQL (RUN)  : `alembic upgrade 0001_baseline:head --sql` RENDERS the Expand/Validate/Contract DDL text using
                             the PostgreSQL dialect and NEVER connects -> static/offline evidence, NOT PostgreSQL proof.
                             Executed: Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3 -> 40 passed.
POSTGRESQL RUNTIME         : NOT RUN. No PostgreSQL server was available. A real test would apply the Day42 raw SQL, create
                             a legacy row that violates the future rule, apply Expand, prove the old row survives, prove a
                             NEW illegal write is rejected, and prove VALIDATE FAILS until the legacy violation is repaired/
                             reconciled. SQLite/fake-session/static checks are NOT PostgreSQL proof; `alembic upgrade`
                             success alone does not prove Backfill/Switch/Contract or production safety.
INTEGRATION / PRODUCTION   : NOT RUN. No FastAPI/Worker drain runtime, real Provider, Object Storage, Day49 upload, Day50
                             Outbox/Celery delivery, or production migration was executed.
```

---

Lesson: [`docs/fastapi/day48-alembic-and-safe-ai-backend-schema-evolution.md`](../../../docs/fastapi/day48-alembic-and-safe-ai-backend-schema-evolution.md)
· Day46 metadata (autogenerate input): [`day46_orm_mapping.py`](day46_orm_mapping.py) · Day42 schema authority: [`../sql/003_relational_modeling_and_data_integrity.sql`](../sql/003_relational_modeling_and_data_integrity.sql)
