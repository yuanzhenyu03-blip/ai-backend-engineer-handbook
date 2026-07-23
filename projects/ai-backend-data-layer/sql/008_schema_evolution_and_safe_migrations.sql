-- =============================================================================
-- Production AI Backend Data Layer — 008_schema_evolution_and_safe_migrations.sql
-- Day36: Schema Evolution and Safe Migrations
--
-- WHAT THIS FILE IS
--   A safe-migration DESIGN + EVIDENCE reference pack that evolves the populated
--   Day31/Day34 app.jobs table into a recoverable, Lease-aware model WITHOUT
--   breaking old code, inventing historical ownership, blocking a live table
--   unnecessarily, or treating a successful DDL statement as a completed
--   migration. It turns the Day34 conceptual Lease and the Day35 conceptual
--   stale-lease index into a compatible, versioned transition.
--
--   Target schema: 001 -> 003 (+ 004/005/006/007 as reference packs). BEFORE this
--   migration, app.jobs has NO claim_owner / lease_token / lease_expires_at. This
--   file is the DESIGN for adding them safely.
--
-- VALIDATION LEVEL FOR THE WHOLE FILE  ==>  NOT executed / NOT RUN.
--   Nothing here was run in class or during the repository update: no PostgreSQL
--   server, no ALTER, no constraint, no index build, no EXPLAIN, no backfill, no
--   benchmark, no Provider/Object Storage integration, no production DDL, no
--   rollback command. Treat every statement as a design to be applied by a real
--   migration runner in a controlled, lock-aware window (Day37 operations), not as
--   a script to run top to bottom.
--
-- THIS IS NOT ONE RUNNABLE SCRIPT
--   * A migration is a VERSIONED STATE TRANSITION across schema, existing DATA, and
--     multiple deployed APPLICATION versions. A valid ALTER alone proves none of
--     that. Each phase below is a separate, sequenced step with preconditions.
--   * CREATE INDEX CONCURRENTLY and the batched Backfill are intentionally
--     NON-TRANSACTIONAL / application-driven and CANNOT run inside one BEGIN/COMMIT.
--
-- HARD RULES (Day34/Day35 carried forward)
--   * Do NOT invent a trustworthy historical owner/token/expiry for legacy running
--     Jobs. Terminal/queued Jobs do NOT receive a Lease merely to fill NULL. NULL
--     honestly means "no proved Lease ownership."
--   * Backfill NEVER calls the Provider or writes Object Storage; migration/DB
--     rollback cannot undo Provider cost or Object Storage bytes.
--   * SQLAlchemy/Alembic are Phase 4; Day37 owns live operations; Day41 owns
--     cross-system fencing tokens. None are Day36.
--
-- Lesson: docs/postgresql/day36-schema-evolution-and-safe-migrations.md
-- =============================================================================


-- #############################################################################
-- PRECONDITIONS (verify before ANY phase)
-- #############################################################################
--   * app.jobs is populated; some rows are job_status = 'running'.
--   * Old application/Worker code is live and does NOT know the Lease columns.
--   * There is NO trustworthy in-schema source of a legacy running Job's owner or
--     token today; backfill values must come from an audited reconciliation input,
--     never be fabricated.
--   * A lock-aware maintenance window / migration runner is available.


-- #############################################################################
-- COMPATIBILITY MATRIX (why the ordering below is safe)
-- #############################################################################
--   Phase                         Old code            New code
--   Expand (nullable columns)     ignores new columns tolerates NULL
--   NOT VALID constraint          unaffected on legacy enforced on new writes
--   Backfill/recovery             must be DRAINED     runs the recovery policy
--   Validate                      unaffected          invariant proven table-wide
--   Switch (token guard)          CANNOT coexist      universal Lease protocol
--   Contract (drop temp compat)   must be gone        only path remaining
--   Old and new writers MUST NOT both write once the token protocol is switched on.


-- #############################################################################
-- PHASE 1 — EXPAND: add NULLABLE Lease columns, no fabricated default
-- #############################################################################
--   Old code ignores them; new code tolerates NULL while data/writers transition.
--   Even a nullable ADD COLUMN takes a lock, so it still needs an assessed window.
--   (In modern PostgreSQL a nullable ADD COLUMN with no volatile default is a fast
--   catalog-only change, but it still acquires a brief ACCESS EXCLUSIVE lock.)
ALTER TABLE app.jobs
    ADD COLUMN claim_owner      text,
    ADD COLUMN lease_token      uuid,
    ADD COLUMN lease_expires_at timestamptz;

-- UNSAFE COUNTER-EXAMPLES — never run these on the populated table:
--   -- ADD COLUMN lease_token uuid NOT NULL;
--      Existing rows have no value, so PostgreSQL REJECTS the migration ATOMICALLY
--      (it does not partially corrupt rows). Forcing required writes also breaks old
--      code that does not set the column. (Student: "不安全，会直接破坏已有历史行、旧版应用".)
--   -- ADD COLUMN lease_token uuid NOT NULL DEFAULT gen_random_uuid();
--      A volatile per-row default FABRICATES an ownership epoch with no real Worker,
--      no expiry, and no proof the Worker is alive, and gives queued/terminal Jobs a
--      Lease they must not have. It can also force a full table rewrite (heavy
--      DDL/I/O). NULL honestly means "no proved Lease ownership".
--
-- Contrast — a boolean default is safe ONLY as a verified BUSINESS fact:
--   -- ADD COLUMN is_archived boolean NOT NULL DEFAULT false;
--      allowed ONLY after proving EVERY historical (and future) row is genuinely
--      unarchived. It is a lifecycle business fact, not a technical convenience.


-- #############################################################################
-- PHASE 2 — COMPATIBLE NEW CODE (application step, not SQL)
-- #############################################################################
--   Deploy new code that WRITES the Lease columns on the new paths and TOLERATES
--   NULL on legacy rows. Old code keeps running and ignoring the columns. Deploying
--   a new binary is NOT the Switch; both versions still exist here.


-- #############################################################################
-- PHASE 3 — DRAIN / ISOLATE OLD WORKERS (operational step, not SQL)
-- #############################################################################
--   Old Workers do NOT enforce the token guard. If a legacy running Job is handed to
--   the new Lease protocol while an old Worker still executes it, both can complete
--   it -> double execution, conflicting state, repeated Provider cost (Day34).
--   Drain or isolate old Workers BEFORE any legacy recovery/backfill. An old Worker
--   that is merely "still running" (not paused) is the dangerous case.


-- #############################################################################
-- PHASE 4 — NOT VALID CONSTRAINT: protect NEW writes immediately
-- #############################################################################
--   Invariant: job_status = 'running' implies non-NULL claim_owner + lease_token +
--   lease_expires_at. Add it NOT VALID first: it enforces the rule on every new
--   INSERT/UPDATE at once, but does NOT scan or claim anything about historical
--   rows. (NOT VALID applies to CHECK/FK constraints -- NOT NULL cannot be NOT VALID.)
ALTER TABLE app.jobs
    ADD CONSTRAINT jobs_running_requires_lease
    CHECK (
        job_status <> 'running'
        OR (claim_owner IS NOT NULL
            AND lease_token IS NOT NULL
            AND lease_expires_at IS NOT NULL)
    ) NOT VALID;


-- #############################################################################
-- PHASE 5 — BOUNDED LEGACY RECOVERY / BACKFILL (application-driven loop)
-- #############################################################################
--   TARGET PREDICATE (idempotent): job_status = 'running' AND lease_token IS NULL.
--   Repeating the SAME predicate in selection and guarded write means committed rows
--   naturally stop matching after a restart -- the DURABLE DB state is the checkpoint,
--   NOT an in-memory processed counter.
--
--   Backfill is small-batch, short-transaction, idempotent, restartable, observable,
--   and calls NO Provider / NO Object Storage. Several migration Workers may take
--   DISTINCT batches with FOR UPDATE SKIP LOCKED. A crash before COMMIT releases
--   locks and rolls the batch back; a committed row no longer matches the predicate.
--
--   CRITICAL: values come ONLY from an AUDITED reconciliation source ($owner,$token,
--   $expiry). There is NO in-schema source today, so most legacy running Jobs are
--   NOT auto-backfillable -- they are routed to an exception/isolation queue for
--   reconciliation, human review, or a dedicated recovery policy. NEVER fabricate a
--   token (Student: "不能，因为还需要隔离、对账、人工或专门恢复流程").
--
-- Per-batch pattern (one short transaction per batch, run by the migration app):
--   BEGIN;
--   -- claim a small batch of legacy targets:
--   SELECT job_id
--     FROM app.jobs
--    WHERE job_status = 'running' AND lease_token IS NULL
--    ORDER BY created_at ASC, job_id ASC
--    FOR UPDATE SKIP LOCKED
--    LIMIT $batch;   -- small, e.g. 100
--   -- ONLY for job_ids whose owner/token were established by AUDITED reconciliation,
--   -- guarded + idempotent (re-check lease_token IS NULL so a re-run is a no-op):
--   UPDATE app.jobs
--      SET claim_owner = $owner, lease_token = $token, lease_expires_at = $expiry
--    WHERE job_id = $1 AND job_status = 'running' AND lease_token IS NULL;
--   -- job_ids WITHOUT a trustworthy source: do NOT update; record them in the
--   -- exception/isolation queue for reconciliation. NO Provider call here.
--   COMMIT;
--
-- Progress / observability (DB-backed, not a process counter):
--   SELECT count(*) AS remaining_targets
--     FROM app.jobs WHERE job_status = 'running' AND lease_token IS NULL;
--   -- plus: batch timings/errors, size of the exception queue, new-write protection.


-- #############################################################################
-- PHASE 6 — VALIDATE CONSTRAINT: prove the table-wide invariant
-- #############################################################################
--   Run ONLY after every legacy running Job is repaired/reconciled or isolated so no
--   row violates the invariant. VALIDATE scans the table and has resource/lock/DDL
--   interactions (SHARE UPDATE EXCLUSIVE), even though it separates historic
--   verification from the new-write enforcement Phase 4 already provided.
ALTER TABLE app.jobs VALIDATE CONSTRAINT jobs_running_requires_lease;


-- #############################################################################
-- PHASE 7 — SWITCH: every writer uses the token guard (application step)
-- #############################################################################
--   Claim, renewal, and Completion all perform the Lease token guard (Day34). The
--   hard precondition is that NO old Worker can execute or complete legacy Jobs
--   outside the protocol. Switch is NOT "a new binary is deployed" -- it is "the old
--   path can no longer write." (Student on the precondition: "A，因为这样会继续扩大影响范围".)


-- #############################################################################
-- PHASE 8 — CONTRACT: remove temporary compatibility (destructive; evidence-gated)
-- #############################################################################
--   Only after evidence: no old Worker version can write; no unresolved legacy
--   running Job remains; token guards are universal; the constraint is VALIDATED; and
--   an OBSERVATION PERIOD shows no old-path traffic or errors. Contract is often
--   destructive and makes rollback harder, so it is shown COMMENTED:
--   -- ALTER TABLE app.jobs DROP COLUMN <temporary_compat_column>;
--   (This pack adds no temporary compat column, so there is nothing to drop here; the
--   step is shown for completeness of the phased model.)


-- #############################################################################
-- INDEX DEPLOYMENT — the Day35 stale-lease index, now that the columns exist
-- #############################################################################
--   Day35 DESIGNED this index but kept it conceptual because the columns were absent.
--   After Phase 1 they exist, so it can be BUILT -- but CREATE INDEX CONCURRENTLY is
--   NON-TRANSACTIONAL: it CANNOT run inside an explicit BEGIN/COMMIT and needs its own
--   migration step. It permits normal DML while building, but is longer-running and
--   still takes brief stage locks. It uses a STABLE predicate (job_status='running');
--   the expiry test stays a QUERY-TIME range (Day35), never now() in the predicate.
--
--   Run OUTSIDE any transaction (its own step):
--     CREATE INDEX CONCURRENTLY jobs_running_lease_idx
--         ON app.jobs (lease_expires_at, job_id)
--         WHERE job_status = 'running';
--
--   INVALID-INDEX HANDLING: a failed concurrent build can leave an INVALID index.
--   Invalid does NOT mean "usable but slow" -- it is unusable. Diagnose it, do not
--   claim success, and clean up + retry only after deciding scope:
--     -- SELECT c.relname, i.indisvalid
--     --   FROM pg_class c JOIN pg_index i ON i.indexrelid = c.oid
--     --  WHERE c.relname = 'jobs_running_lease_idx';
--     -- (if indisvalid = false) DROP INDEX CONCURRENTLY jobs_running_lease_idx;  -- then rebuild
--   Net-benefit measurement (Day35) happens ONLY after a valid build + representative
--   workload evidence.


-- #############################################################################
-- VERIFICATION / COMPLETION EVIDENCE (queries only; nothing executed here)
-- #############################################################################
--   Backfill is complete when the DATABASE shows the target state -- not when a
--   process counter says so:
--     * remaining targets = 0:
--         SELECT count(*) FROM app.jobs WHERE job_status='running' AND lease_token IS NULL;
--     * exception/isolation queue accounted for (explained failures, not silent gaps);
--     * batch timing/error metrics recorded;
--     * new-write protection confirmed (Phase 4 constraint present);
--     * constraint validated:
--         SELECT conname, convalidated FROM pg_constraint
--          WHERE conname = 'jobs_running_requires_lease';


-- #############################################################################
-- ROLLBACK vs FORWARD FIX (decide by durable state, not by preference)
-- #############################################################################
--   * If new schema/data has NOT become durable and no downstream side effect exists,
--     a rollback (e.g. dropping the just-added nullable columns) may be practical.
--   * If real Lease data, Job transitions, Provider calls, or Object Storage artifacts
--     already exist, removing columns CANNOT undo them -> preserve compatibility,
--     repair/reconcile, and FORWARD FIX.
--   * The classroom false-takeover case: a TOO-SHORT Lease duration after THOUSANDS of
--     real tokens were written -> the fix is FORWARD FIX (tune the duration config,
--     reconcile affected Jobs), NOT DROP COLUMN. (Student: "我会保留schema做forward fix,
--     因为只是 Lease duration配置过短造成的".)
