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

## 2. Expand (revision `0002_expand_lease`)

```text
ALTER TABLE app.jobs ADD COLUMN lease_owner text, ADD COLUMN lease_token uuid, ADD COLUMN lease_expires_at timestamptz;
  -> ALL NULLABLE, NO fabricated default. NULL honestly means "no PROVED Lease ownership".
  -> Do NOT generate tokens for queued, terminal, or unprovable running Jobs (fabrication is forbidden).
ALTER TABLE app.jobs ADD CONSTRAINT jobs_lease_triple_coherent CHECK (all-three-NULL OR all-three-NOT-NULL) NOT VALID;
  -> NOT VALID protects EVERY future INSERT/UPDATE immediately while TEMPORARILY tolerating legacy rows.
  -> NOT validated here. No Backfill loop, no Provider call, no long transaction in upgrade().
```

Old Workers keep working because the new columns are nullable and old code ignores
them — this is why Expand must be deployed **first** and alone.

---

## 3. Backfill (operational script, NOT an Alembic `upgrade()`)

```text
day48_lease_backfill.py (operator-run, restartable): SHORT tx + FOR UPDATE SKIP LOCKED batches, idempotent predicates,
  DB state = the recovery checkpoint. Fills ONLY running Jobs with Lease NULL AND trusted ownership evidence.
  Unknown-ownership running Jobs -> reconciliation/recovery, NEVER fabricated.
  UPDATE ... WHERE job_id=... AND job_status='running' AND lease_owner IS NULL RETURNING  (guarded, idempotent, re-runnable).
  Calls NO Provider; holds NO long transaction. NOT the Day47 Lease runtime protocol and NOT a Lease-expiry batch claim.
```

Long Backfill/reconciliation loops must **never** live in a migration `upgrade()`.

---

## 4. Validate (revision `0003_validate_lease`) and NOT VALID vs VALIDATE

```text
ALTER TABLE app.jobs VALIDATE CONSTRAINT jobs_lease_triple_coherent;
  -> Proves HISTORICAL rows also satisfy the already-enforced future rule; lighter lock, no re-scan of enforced rows.
  -> Run ONLY after Backfill/reconciliation TRULY resolved every violation (an exception queue is NOT resolution).
NOT VALID (Expand)  = protect the FUTURE now (new writes checked; legacy tolerated).
VALIDATE (here)     = prove the PAST is compliant. Fails if any legacy violation remains -> that is the signal to finish
                      Backfill/reconciliation, not to exclude rows.
```

Expand and Validate are **separate revisions**: the phases are gated by
deployment, data, Writer-protocol, and observation evidence — not merely to avoid
one long transaction.

---

## 5. Switch and Contract (revision `0004_contract_legacy`)

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
STATIC ALEMBIC (RUN)       : 10 pytest cases inspect the revision graph + migration source via Alembic's ScriptDirectory
                             (single head 0004; linear 0004->0003->0002->0001->None; Expand nullable/no-default/NOT VALID;
                             Validate separate; Contract destructive+gated; no loop in any upgrade()/downgrade(); minimal
                             env.py) plus FAKE-SESSION backfill control flow (SKIP LOCKED batch; fills known, skips unknown
                             for reconciliation; idempotent guarded write; no Provider). No database connection.
OFFLINE ALEMBIC SQL (RUN)  : `alembic upgrade 0001_baseline:head --sql` RENDERS the Expand/Validate/Contract DDL text using
                             the PostgreSQL dialect and NEVER connects -> static/offline evidence, NOT PostgreSQL proof.
                             Executed: Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3 -> 10 passed.
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
