-- =============================================================================
-- Production AI Backend Data Layer — 006_concurrency_control_mvcc_and_worker_claims.sql
-- Day34: Concurrency Control, MVCC, and Worker Claims
--
-- WHAT THIS FILE IS
--   A concurrency reference pack that makes the Day33 atomic Start transaction
--   safe when MANY PostgreSQL sessions and Workers compete for the same queued
--   work. It reuses the exact Day33 guarded queued->running write and adds only
--   the CLAIM mechanism (FOR UPDATE SKIP LOCKED) around it. A lock cannot repair a
--   wrongly defined Day33 boundary -- get the boundary right first.
--
--   Target schema: 001_create_jobs.sql -> 003_relational_modeling_and_data_integrity.sql
--   The ACTIVE SQL below uses the Day31 columns EXACTLY and invents no columns.
--
-- WHAT IS ACTIVE vs CONCEPTUAL (read this before running anything)
--   * Part 1 (the claim transaction) is ACTIVE, driver-bound SQL against the
--     current schema.
--   * Part 2 (the application LEASE state machine: claim_owner / lease_token /
--     lease_expires_at) is CONCEPTUAL and fully COMMENTED. Those columns DO NOT
--     EXIST in the Day31 schema and were NOT added or run. Adding them is a Day36
--     expand/backfill/validate/switch/contract migration. Do not uncomment Part 2
--     against the current schema -- it will fail with "column does not exist".
--
-- HOW TO READ THIS FILE
--   * `$1`, `$2`, ... are DRIVER/PREPARE placeholders (asyncpg style), not psql
--     variables. Bind them from the application, or substitute literals on a
--     DISPOSABLE cluster.
--   * A plain SELECT is CANDIDATE VISIBILITY, not ownership. Ownership is decided
--     by a lock (transaction-local) plus the guarded UPDATE, and -- once you need
--     it to survive COMMIT -- by a committed lease (Part 2, conceptual).
--   * Every guarded UPDATE is followed by a CONTROL-FLOW CONTRACT: 0 rows is a
--     NORMAL result the application must gate on (Day33), not a SQL error.
--
-- WHAT THIS FILE IS **NOT**
--   * No CREATE INDEX, no EXPLAIN -- measuring these access paths is Day35.
--   * No ALTER TABLE, no migration -- adding lease columns is Day36.
--   * No ORM / SQLAlchemy / Alembic, no Redis locking.
--   * SKIP LOCKED does NOT guarantee strict FIFO, a complete snapshot, or that
--     every row is eventually served. A lease does NOT prove a Worker died, does
--     NOT change its own token, does NOT revoke external work, and does NOT make a
--     Provider retry safe. A lease_token is NOT a Provider idempotency key.
--
-- Lesson: docs/postgresql/day34-concurrency-control-mvcc-and-worker-claims.md
-- =============================================================================


-- #############################################################################
-- PART 1 — ACTIVE: the FOR UPDATE SKIP LOCKED claim transaction (Day31 schema)
-- #############################################################################

-- -----------------------------------------------------------------------------
-- 1. Candidate visibility is NOT ownership (the starting misconception).
--
--    Two independent Read Committed sessions can BOTH see the same committed
--    queued Job with this plain SELECT. Seeing a row is not claiming it. If both
--    Workers then ran the Day33 guarded UPDATE, only ONE legal queued->running
--    transition would succeed; the others would return zero rows (Day33's gate).
--    Without that gate, duplicate Attempt/Event facts get written.
-- -----------------------------------------------------------------------------
SELECT j.job_id, j.job_status, j.created_at
  FROM app.jobs AS j
 WHERE j.tenant_id  = $1
   AND j.job_status = 'queued'
 ORDER BY j.created_at ASC, j.job_id ASC
 LIMIT 1;
-- ^ visibility only. No lock, no ownership.


-- -----------------------------------------------------------------------------
-- 2. The CLAIM transaction: reserve one queued Job with FOR UPDATE SKIP LOCKED,
--    then reuse the exact Day33 Start write. All ACTIVE against the Day31 schema.
--
--    FOR UPDATE requests a row lock; a conflicting locking read/write WAITS.
--    SKIP LOCKED makes this claim skip rows already locked by other claim
--    transactions and take the next AVAILABLE one -- so N Workers spread across N
--    rows instead of convoying on the queue head.
--
--    The row lock is TRANSACTION-LOCAL: it lives only until COMMIT/ROLLBACK (or
--    session loss) and MUST NOT span the eight-minute Provider call. The Provider
--    call happens AFTER this COMMIT (Day33), outside any transaction.
-- -----------------------------------------------------------------------------
BEGIN;

-- Reserve exactly one available queued candidate, deterministically ordered.
-- SKIP LOCKED excludes rows other claim txns hold; ORDER BY sorts only the rows
-- STILL AVAILABLE, so this is NOT strict FIFO and a long-locked row can be passed
-- over (starvation risk -- see the lesson; monitor oldest queued age).
SELECT j.job_id
  FROM app.jobs AS j
 WHERE j.tenant_id  = $1
   AND j.job_status = 'queued'
 ORDER BY j.created_at ASC, j.job_id ASC
 FOR UPDATE SKIP LOCKED
 LIMIT 1;
-- CONTROL-FLOW CONTRACT: 0 rows -> no AVAILABLE queued Job right now (all queued
--   rows are locked by peers, or the queue is empty). COMMIT/ROLLBACK and back
--   off; this is normal, not an error. 1 row -> bind its job_id as $2 and continue.

-- Guarded Day33 Start transition on the reserved row. The WHERE re-checks
-- job_status = 'queued' even though we hold the lock: the lock serializes access,
-- and the guard keeps the transition legal (belt and suspenders, and correct if
-- the claim SELECT is ever changed).
UPDATE app.jobs
   SET job_status    = 'running',
       started_at    = now(),
       attempt_count = attempt_count + 1
 WHERE job_id     = $2
   AND tenant_id  = $1
   AND job_status = 'queued'
RETURNING job_id, attempt_count;
-- CONTROL-FLOW CONTRACT: 0 rows -> transition_not_applied. ROLLBACK and STOP.
--   Do NOT insert the Attempt/Event below (Day33 incident #5).

INSERT INTO app.job_attempts (attempt_id, job_id, attempt_number, started_at)
VALUES ($3, $2, $4, now());
-- $4 is the attempt_count RETURNED above. attempt_id ($3) is the durable pre-call
-- Provider idempotency/correlation anchor (Day33): it must be SENT to the Provider
-- and stays STABLE across any later lease takeover.

INSERT INTO app.job_events (job_id, attempt_id, event_type, from_status, to_status, actor)
VALUES ($2, $3, 'job_started', 'queued', 'running', $5);

COMMIT;
-- Only AFTER this COMMIT does the Worker call the Provider, OUTSIDE any
-- transaction (Day33). The row lock is already gone; a released lock is NOT
-- evidence the Worker is alive or dead, and the Job/Attempt/Event are durable.
-- Blind reclaim here can duplicate Attempt, Event, Provider cost, and result work.


-- -----------------------------------------------------------------------------
-- 3. Optimistic alternative (also ACTIVE, Day31 schema): an expected-status guard.
--
--    Good for LOWER-contention edits. Under high contention (100 Workers all
--    targeting the OLDEST Job) pure optimistic selection yields one winner and
--    many zero-row losers that must re-read and retry -- a retry storm. That is
--    exactly why the pessimistic FOR UPDATE SKIP LOCKED claim above suits a
--    high-contention queue: Workers spread instead of colliding. More isolation
--    is not automatic work partitioning.
-- -----------------------------------------------------------------------------
-- UPDATE app.jobs
--    SET job_status = 'running', started_at = now(), attempt_count = attempt_count + 1
--  WHERE job_id = $1 AND tenant_id = $2 AND job_status = 'queued'
-- RETURNING job_id;
-- (0 rows -> another session already moved it; re-read and pick a different Job.)


-- -----------------------------------------------------------------------------
-- 4. Deadlock avoidance: consistent global lock ORDER (ACTIVE guidance).
--
--    Deadlock: txn A locks job-A then wants job-B; txn B locks job-B then wants
--    job-A -> circular wait. PostgreSQL DETECTS it and aborts ONE victim with
--    SQLSTATE 40P01 (deadlock_detected); it does NOT let both wait forever and
--    does NOT auto-retry your transaction.
--
--    PREVENTION: every writer that locks multiple Jobs must lock them in ONE
--    agreed order (e.g. ascending job_id). Then the second txn waits before it
--    holds the second row -- waiting, but no cycle. Every writer, old Worker,
--    maintenance script, and repair path must obey the same order.
-- -----------------------------------------------------------------------------
-- Multi-row lock in a fixed order (illustrative; bind a real id array):
--   SELECT job_id FROM app.jobs
--    WHERE tenant_id = $1 AND job_id = ANY($2::uuid[])
--    ORDER BY job_id ASC            -- the ONE agreed order
--    FOR UPDATE;
--
-- BOUNDS vs PREVENTION vs DETECTION (do not confuse them):
--   * consistent ORDER      -> PREVENTS the common cycle
--   * PostgreSQL detector    -> aborts a cycle it could not prevent (40P01)
--   * lock_timeout / statement_timeout -> BOUND ordinary waits/work; they do NOT
--     replace ordering. An ordinary FOR UPDATE that waits past lock_timeout is
--     cancelled with SQLSTATE 55P03 (lock_not_available).
--
-- RETRY (application, not PostgreSQL): on 40P01 or 40001 (serialization_failure),
-- ROLLBACK and retry the WHOLE transaction with a FINITE budget and jitter/backoff,
-- reusing the same idempotent identifiers (attempt_id, outbox_event_id). Never
-- continue a failed transaction and never retry forever. UNIQUE (job_id,
-- attempt_number) and (tenant_id, idempotency_key) still stop duplicate durable
-- facts a retry might otherwise create -- locks/leases decide ownership, UNIQUE
-- constraints decide identity, and neither substitutes for the other.


-- #############################################################################
-- PART 2 — CONCEPTUAL ONLY (DO NOT RUN): committed application LEASE ownership.
--
--   Everything below references claim_owner / lease_token / lease_expires_at,
--   which are NOT in the Day31 schema. This is the design, expressed as comments.
--   A row lock is transaction-local exclusion and vanishes at COMMIT; a LEASE is
--   COMMITTED execution ownership that survives COMMIT, so a takeover after a
--   stale/paused Worker is possible and recoverable. Introducing these columns is
--   a Day36 expand/backfill/validate/switch/contract migration -- not done here.
-- #############################################################################
--
-- Conceptual columns (Day36 migration, NOT created here):
--   claim_owner        text        -- which Worker currently owns execution
--   lease_token        uuid        -- ONE ownership epoch; changes on takeover
--   lease_expires_at   timestamptz -- when ownership may be taken over
--
-- CLAIM (conceptual): inside the Part 1 claim transaction, also stamp ownership:
--   UPDATE app.jobs
--      SET job_status = 'running', started_at = now(), attempt_count = attempt_count + 1,
--          claim_owner = $worker, lease_token = $new_token,
--          lease_expires_at = now() + $lease_interval   -- PostgreSQL now(), not Worker clock
--    WHERE job_id = $job AND tenant_id = $tenant AND job_status = 'queued'
--   RETURNING job_id, lease_token;
--
-- RENEW / HEARTBEAT (conceptual): guard on ownership AND an unexpired lease:
--   UPDATE app.jobs
--      SET lease_expires_at = now() + $lease_interval
--    WHERE job_id = $job AND job_status = 'running'
--      AND lease_token = $my_token AND lease_expires_at > now()
--   RETURNING job_id;
--   -- 0 rows -> you no longer own it (expired and taken over, or wrong token). Stop.
--
-- TAKEOVER (conceptual): only when the current lease has EXPIRED. Takeover WRITES
--   a NEW lease_token; expiry ALONE does not mutate the token, it only makes the
--   old ownership invalid via the time predicate:
--   UPDATE app.jobs
--      SET claim_owner = $new_worker, lease_token = $new_token,
--          lease_expires_at = now() + $lease_interval
--    WHERE job_id = $job AND job_status = 'running' AND lease_expires_at <= now()
--   RETURNING job_id, lease_token;
--
-- COMPLETION guard (conceptual): the Day33 Complete transaction additionally
--   guards current token + running status + UNEXPIRED lease. A STALE Worker that
--   resumes after takeover returns ZERO rows here and the ENTIRE Completion
--   transaction rolls back -- but the Provider cost and Object Storage bytes it
--   already produced REMAIN and need reconciliation (Day33):
--   UPDATE app.jobs
--      SET job_status = 'succeeded', finished_at = now()
--    WHERE job_id = $job AND tenant_id = $tenant AND job_status = 'running'
--      AND lease_token = $my_token AND lease_expires_at > now()
--   RETURNING job_id;
--
-- LEASE POLICY (conceptual): lease duration comes from the HEARTBEAT interval and
--   observed pauses, NOT the whole Provider duration. For an eight-minute Job whose
--   heartbeats may pause ~45s, a ~2-minute lease was chosen over 30s to avoid false
--   takeover. Short lease = faster true-failure recovery but MORE false takeover;
--   long lease = fewer false takeovers but SLOWER recovery. Expiry is a TAKEOVER
--   CONDITION, never proof the old Worker died (it may be paused/partitioned).
--
-- LEASE TOKEN vs PROVIDER IDEMPOTENCY KEY (conceptual, critical):
--   lease_token identifies one OWNERSHIP EPOCH and CHANGES on every takeover.
--   The Provider idempotency/correlation key identifies the SAME logical external
--   operation and must stay STABLE across takeover (derive it from the durable
--   attempt_id and actually SEND it to a Provider that supports idempotency/lookup).
--   Using each new lease_token as a new Provider key DEFEATS idempotency and can
--   repeat charges. If the Provider offers no idempotency/lookup, the lease cannot
--   make the external retry safe: isolate and reconcile.
