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
ALTER TABLE app.jobs ADD COLUMN lease_owner text, ADD COLUMN lease_token uuid, ADD COLUMN lease_expires_at timestamptz,
                      ADD COLUMN lease_backfill_state text;
  -> ALL NULLABLE, NO fabricated default. NULL honestly means "no PROVED Lease ownership".
  -> NO constraint here. This is a PURE Expand -> the OLD/NEW code COMPATIBILITY WINDOW: while only this revision
     is applied an OLD Writer can still update a legacy running Job that has a NULL Lease (no constraint rejects it).
  -> Do NOT generate tokens for queued, terminal, or unprovable running Jobs (fabrication is forbidden).
  -> lease_backfill_state is a PERSISTENT reconciliation marker (see section 3); it fabricates NO Lease field.
```

The strict Lease constraints are a SEPARATE later revision (section 2b), so old and new code truly coexist here.

---

## 2b. Constraints (revision `0003_add_lease_constraints`) — closes the compatibility window

```text
PRECONDITIONS (operator MUST ensure, Alembic cannot): new code deployed & tolerates NULL Lease; OLD Writers DRAINED/ISOLATED.
ALTER TABLE app.jobs ADD CONSTRAINT jobs_lease_triple_coherent CHECK (all-three-NULL OR all-three-NOT-NULL) NOT VALID;
ALTER TABLE app.jobs ADD CONSTRAINT jobs_running_requires_lease CHECK (job_status <> 'running' OR (lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)) NOT VALID;
ALTER TABLE app.jobs ADD CONSTRAINT jobs_lease_backfill_state_allowed CHECK (lease_backfill_state IS NULL OR lease_backfill_state = 'reconcile') NOT VALID;
  -> jobs_running_requires_lease is the Day36 CORE invariant (Day48 field names): a running Job MUST carry a complete Lease.
     A reconcile-marked running Job with a NULL Lease STILL VIOLATES it (reconcile is TRIAGE, not RESOLUTION).
  -> NOT VALID does NOT mean "old Writers unaffected": it skips only the one-time SCAN of legacy rows, but ENFORCES the rule
     on EVERY future INSERT/UPDATE by ANY writer version. An OLD Worker updating a running-without-Lease Job is REJECTED
     (23514). THAT is why this revision must land ONLY after the old write path is drained/isolated. Pure Expand = compat
     window; the strict NOT VALID Lease constraint = old Writers can no longer write a running-without-Lease Job.
  -> NOT validated here (0004 VALIDATEs it). No Backfill loop, no Provider call, no long transaction.
```

---

## 3. Backfill (operational script, NOT an Alembic `upgrade()`)

```text
day48_lease_backfill.py (operator-run, restartable): SHORT tx + FOR UPDATE SKIP LOCKED batches, idempotent predicates,
  DB state = the recovery checkpoint. Candidate query:
    SELECT ... WHERE job_status='running' AND lease_owner IS NULL AND lease_backfill_state IS NULL FOR UPDATE SKIP LOCKED
  automatic_backfill_candidates = running AND lease_owner IS NULL AND lease_backfill_state IS NULL (what the auto-loop may fill).
  A PROVED Job gets its Lease (apply_lease_evidence: guarded UPDATE ... SET lease..., lease_backfill_state=NULL WHERE running AND lease_owner IS NULL RETURNING).
  An UNKNOWN-ownership Job is ROUTED to a PERSISTENT reconciliation marker (route_to_reconciliation:
    UPDATE ... SET lease_backfill_state='reconcile' WHERE running AND lease_owner IS NULL AND lease_backfill_state IS NULL RETURNING),
  which fabricates NO Lease owner/token/expiry. Because both outcomes remove the Job from the AUTOMATIC candidate
  query, the auto-loop TERMINATES (even with max_batches=None) and a RESTART never re-selects the same unknown Job.
  BUT reconcile is TRIAGE, not RESOLUTION:
    unresolved_running_without_lease = ALL running rows with a NULL Lease, INCLUDING reconcile-marked ones
      (count_unresolved_running_without_lease: SELECT count(*) ... WHERE job_status='running' AND lease_owner IS NULL).
      This is the Day36 remaining_targets and the HARD VALIDATE/Switch/Contract precondition (must be 0). The
      automatic loop stopping does NOT reduce it and does NOT mean the history is compliant.
  A parked row is resolved ONLY by (a) a TRUSTED Lease backfill (apply_lease_evidence, which also clears the marker)
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
  -> jobs_running_requires_lease FAILS while any running-without-Lease row remains (reconcile-marked rows INCLUDED),
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
STATIC ALEMBIC (RUN)       : 22 pytest cases inspect the revision graph + migration source via Alembic's ScriptDirectory
                             (single head 0005; linear 0005->0004->0003->0002->0001->None; PURE Expand (columns only, NO
                             constraint = the compatibility window); a SEPARATE constraint revision adds the triple +
                             Day36 jobs_running_requires_lease NOT VALID with a drain/isolate precondition; Validate
                             validates BOTH constraints; Contract destructive+gated; no loop in any upgrade()/downgrade();
                             minimal env.py) plus FAKE-SESSION backfill control flow (SKIP LOCKED automatic-candidate batch
                             excluding reconciliation-routed rows; fills known and CLEARS the marker; ROUTES unknown to a
                             persistent 'reconcile' marker with no fabrication; TERMINATES when all candidates are unknown;
                             restart does not re-select a routed Job BUT it STILL counts in unresolved_running_without_lease
                             (reconcile != resolution); recovery ROUTING (non-mutating): unknown -> KEEP_UNKNOWN, verified
                             succeeded -> Day47 completion UoW, failed/cancelled -> guarded terminal-recovery, a 'queued'
                             requeue / 'running' / bad status -> UnsafeRecoveryError; the VALIDATE precondition
                             unresolved==0 is reached only after real resolution; idempotent guarded writes; no Provider) and the database-URL resolution (`-x db_url` > env DAY48_ALEMBIC_DATABASE_URL; ini
                             placeholder is OFFLINE-only and online FAILS FAST without an external URL). No database connection.
OFFLINE ALEMBIC SQL (RUN)  : `alembic upgrade 0001_baseline:head --sql` RENDERS the Expand/Validate/Contract DDL text using
                             the PostgreSQL dialect and NEVER connects -> static/offline evidence, NOT PostgreSQL proof.
                             Executed: Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3 -> 22 passed.
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
