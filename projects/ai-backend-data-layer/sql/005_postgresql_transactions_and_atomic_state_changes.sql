-- =============================================================================
-- Production AI Backend Data Layer — 005_postgresql_transactions_and_atomic_state_changes.sql
-- Day33: PostgreSQL Transactions and Atomic State Changes
--
-- WHAT THIS FILE IS
--   A read-and-write TRANSACTION reference pack for the Day31 relational model.
--   It turns the Day32 read-side coherence rules ("detect partial/missing related
--   facts") into write-side atomic commitments ("commit all related facts or
--   none"). It is a WRITE-PATH CONTRACT, not a schema-level guarantee: it protects
--   only the writers that use it (see Boundary note at the end).
--
--   Target schema: 001_create_jobs.sql -> 003_relational_modeling_and_data_integrity.sql
--   (002 is the Day30 statement reference pack. This file uses the Day31 columns
--   exactly -- tenant_id, idempotency_key, job_attempts, job_events, outbox_events,
--   result_artifacts -- and invents no new columns.)
--
-- HOW TO READ THIS FILE
--   * `$1`, `$2`, ... are DRIVER/PREPARE placeholders (asyncpg style). They are NOT
--     psql variables: pasting a `$1` statement into psql raises
--     "there is no parameter $1". Bind them from the application, or substitute
--     literals when exploring on a DISPOSABLE cluster.
--   * BEGIN / COMMIT / ROLLBACK below mark ONE business-change boundary each. A
--     driver issues them; this file shows where they belong.
--   * Every guarded UPDATE is followed by a CONTROL-FLOW CONTRACT block. This is
--     the most important idea in the file: PostgreSQL does NOT abort a transaction
--     just because an UPDATE matched zero rows (that is a normal result). The
--     APPLICATION must read RETURNING / the affected-row count and decide to
--     continue or ROLLBACK. A SQL comment that says "zero rows" and then runs the
--     next INSERT anyway is exactly the bug this pack prevents.
--   * Appendix A is a self-contained anonymous block (no placeholders) that
--     ENFORCES the zero-row gate in pure SQL via RAISE, so the gate's behaviour is
--     actually runnable/validatable on a disposable cluster.
--
-- THE EXTERNAL BOUNDARY (the reason the pack is split into A / B / C)
--   PostgreSQL can commit or roll back only its OWN rows. It CANNOT roll back:
--     - an AI Provider request or its cost
--     - Object Storage bytes already written
--     - a Redis / Queue publication
--     - a webhook, email, or downstream consumer's work
--   So the long external phase sits BETWEEN two short transactions, never inside
--   one. Holding a transaction open across an eight-minute Provider call would pin
--   a connection, may retain row locks and an old snapshot, and still could not
--   undo the external call.
--
-- WHAT THIS FILE IS **NOT**
--   * No locking, no FOR UPDATE, no SKIP LOCKED, no MVCC isolation tuning -- Day34.
--     Concurrent Relay/Worker CLAIM selection is explicitly Day34 (see Relay note).
--   * No indexes, no EXPLAIN -- Day35. No migrations / ALTER of populated tables --
--     Day36. No ORM / SQLAlchemy / Alembic.
--   * No claim of distributed exactly-once delivery, and no claim that a COMMIT
--     proves any external effect happened.
--
-- Lesson: docs/postgresql/day33-postgresql-transactions-and-atomic-state-changes.md
-- =============================================================================


-- -----------------------------------------------------------------------------
-- TRANSACTION A -- ACCEPT.  One commitment: "a durable Job EXISTS if and only if a
-- durable Outbox publication intent exists."
--
--   Failure mode this closes (classroom incident #1): Job committed, process
--   crashes, Outbox never written -> the Job sits queued forever because the Relay
--   scans app.outbox_events, not app.jobs. Day32 can surface the symptom; it
--   cannot repair it.
--
--   FastAPI returns `202 + job_id` ONLY AFTER this COMMIT succeeds -- 202
--   acknowledges an existing durable commitment. If COMMIT succeeds but the HTTP
--   response is lost, the client's retry is made safe by Day31's
--   UNIQUE (tenant_id, idempotency_key) plus a lookup -- not by the transaction.
-- -----------------------------------------------------------------------------
BEGIN;

INSERT INTO app.jobs (job_id, tenant_id, idempotency_key, provider_metadata)
VALUES ($1, $2, $3, $4);
-- job_status defaults to 'queued', attempt_count to 0 (001 defaults).

INSERT INTO app.outbox_events (outbox_event_id, job_id, event_type, payload)
VALUES ($5, $1, 'job.accepted', $6);
-- outbox_event_id is the STABLE identifier the consumer will deduplicate on. A
-- duplicate value raises 23505 unique_violation, which fails the transaction and
-- rolls the Job INSERT above back with it (classroom test 2).

COMMIT;
-- Only now may FastAPI return 202 + job_id.


-- -----------------------------------------------------------------------------
-- TRANSACTION B -- START.  Atomically claim the Job and record that the claim
-- happened: guarded queued -> running, a new Attempt, and an append-only
-- job_started Event, all or nothing.
--
--   Failure mode this closes (classroom incident #4): status committed to running
--   in one transaction, Worker crashes before the Attempt/Event insert -> Day32
--   reports running_without_attempt, a coherence anomaly.
-- -----------------------------------------------------------------------------
BEGIN;

-- Guarded transition. The WHERE clause is the transition boundary: it matches only
-- a Job that is CURRENTLY queued for THIS tenant. attempt_count is incremented in
-- the same statement (database-side increment, not read-modify-write) and returned
-- so the Attempt below can use it as attempt_number.
UPDATE app.jobs
   SET job_status    = 'running',
       started_at    = now(),
       attempt_count = attempt_count + 1
 WHERE job_id     = $1
   AND tenant_id  = $2
   AND job_status = 'queued'
RETURNING job_id, attempt_count;

-- CONTROL-FLOW CONTRACT (application, not PostgreSQL):
--   RETURNING produced 1 row -> bind attempt_count as $4 and CONTINUE.
--   RETURNING produced 0 rows -> the Job was NOT queued (already running, already
--     terminal, wrong tenant, or gone). This is transition_not_applied. The
--     application MUST ROLLBACK and STOP. It must NOT run the inserts below, or it
--     creates a duplicate Attempt/Event for a Job it never legally claimed
--     (classroom incident #5). Zero rows is a NORMAL result, NOT a SQL error, so
--     PostgreSQL will happily run the next statement if the app does not gate it.
--   The UNIQUE (job_id, attempt_number) constraint stops a duplicate NUMBER only;
--   it cannot replace this guard, and a fresh Event would still get a unique id.

INSERT INTO app.job_attempts (attempt_id, job_id, attempt_number, started_at)
VALUES ($3, $1, $4, now());
-- provider_request_id / cost_micros / finished_at stay NULL until Transaction C.
-- $4 is the attempt_count RETURNED above -- do not recompute it on the client.

INSERT INTO app.job_events (job_id, attempt_id, event_type, from_status, to_status, actor)
VALUES ($1, $3, 'job_started', 'queued', 'running', $5);

COMMIT;


-- -----------------------------------------------------------------------------
-- EXTERNAL PHASE -- **NO OPEN POSTGRESQL TRANSACTION**.
--
--   With Transaction B committed and Transaction C not yet begun, the Worker calls
--   the AI Provider and writes Object Storage. These are the operations PostgreSQL
--   cannot roll back, so they must not run inside a transaction.
--
--   Carry forward two STABLE identifiers for later reconciliation:
--     - provider_request_id  (deduplicate Provider work / find the external call)
--     - a deterministic object key (find or overwrite the same Object Storage byte)
--
--   What PostgreSQL can prove right now: the Job is running and an Attempt/Event
--   exist. What it CANNOT prove: that the Provider produced a result. A persisted
--   provider_request_id proves an id was recorded, not the external outcome. Blind
--   requeue here can repeat Provider cost and side effects (classroom incident #8).
-- -----------------------------------------------------------------------------
-- (no SQL -- external Provider request + Object Storage write happen here)


-- -----------------------------------------------------------------------------
-- TRANSACTION C -- COMPLETE.  Atomically persist the finished Attempt, the guarded
-- terminal Job state, the Result Artifact reference, the append-only success
-- Event, and the Outbox publication intent -- all or nothing.
--
--   Integrated rollback case (classroom incident #12): if the Artifact INSERT
--   violates a constraint, the whole transaction rolls back. None of Attempt
--   finish, Job succeeded, success Event, or Outbox intent become committed facts.
--   The Provider cost and the Object Storage bytes REMAIN -- they were never in the
--   transaction. The object may be an orphan until reconciliation or a separately
--   audited compensating delete. Database rollback is not Object Storage rollback.
-- -----------------------------------------------------------------------------
BEGIN;

-- Finish the current Attempt and record the external identifiers gathered above.
UPDATE app.job_attempts
   SET finished_at         = now(),
       provider_request_id = $3,
       cost_micros         = $4
 WHERE attempt_id = $2
   AND job_id     = $1
RETURNING attempt_id;
-- CONTROL-FLOW CONTRACT: 0 rows -> wrong attempt_id/job_id pairing. ROLLBACK, stop.

-- Guarded terminal transition. Matches only a Job that is CURRENTLY running for
-- THIS tenant. finished_at is set in the same statement so the Day31 CHECK
-- (job_status <> 'succeeded' OR finished_at IS NOT NULL) is satisfied atomically.
UPDATE app.jobs
   SET job_status  = 'succeeded',
       finished_at = now()
 WHERE job_id     = $1
   AND tenant_id  = $5
   AND job_status = 'running'
RETURNING job_id;
-- CONTROL-FLOW CONTRACT: 0 rows -> the Job was not running (already terminal,
--   cancelled, wrong tenant). transition_not_applied -> ROLLBACK and STOP. Do not
--   write the Artifact/Event/Outbox rows for a completion that did not apply.

INSERT INTO app.result_artifacts (artifact_id, attempt_id, artifact_type, object_key, content_type, size_bytes, checksum)
VALUES ($6, $2, $7, $8, $9, $10, $11);
-- References the Object Storage object by KEY; the bytes live in Object Storage,
-- not PostgreSQL. UNIQUE (attempt_id, object_key) makes a duplicate reference raise
-- 23505 and roll the whole completion back (classroom test 4).

INSERT INTO app.job_events (job_id, attempt_id, event_type, from_status, to_status, actor)
VALUES ($1, $2, 'job_succeeded', 'running', 'succeeded', $12);

INSERT INTO app.outbox_events (outbox_event_id, job_id, event_type, payload)
VALUES ($13, $1, 'job.succeeded', $14);
-- Same STABLE outbox_event_id contract as Transaction A.

COMMIT;


-- -----------------------------------------------------------------------------
-- RELAY CHECKPOINT -- publish durable intent, then record success.  NOT part of any
-- business transaction above.
--
--   The Outbox row is durable PUBLICATION INTENT and AUDIT evidence. The Relay
--   does NOT delete or "consume" it and does NOT set published_at back to NULL -- it
--   is created NULL (Transactions A and C) and moves to a timestamp once, after the
--   Queue acknowledges. A later retention policy may archive old rows; that is not
--   the publish lifecycle.
--
--   CONCURRENCY NOTE: selecting/claiming unpublished rows safely under MULTIPLE
--   concurrent Relays needs FOR UPDATE / SKIP LOCKED -- that is Day34 and is
--   deliberately absent here. This single-reader form only shows the checkpoint.
-- -----------------------------------------------------------------------------
-- 1. Read unpublished intent (deterministic order for reproducibility).
SELECT outbox_event_id, job_id, event_type, payload
  FROM app.outbox_events
 WHERE published_at IS NULL
 ORDER BY created_at ASC, outbox_event_id ASC;

-- 2. Publish externally using the SAME outbox_event_id (no SQL here).

-- 3. Record publish success ONLY after the Queue acknowledges.
UPDATE app.outbox_events
   SET published_at = now()
 WHERE outbox_event_id = $1
   AND published_at IS NULL
RETURNING outbox_event_id, published_at;
-- MEANING OF published_at:
--   NULL     -> never attempted, in flight, OR published-then-crashed before this
--               write-back. It does NOT prove no external publish happened.
--   NOT NULL -> the Relay RECORDED a successful publish. It does NOT prove Queue
--               delivery, Celery execution, or consumer business success.
--   A Relay crash AFTER external publish but BEFORE this UPDATE commits leaves the
--   row NULL, so restart may republish the SAME outbox_event_id. That is expected
--   under AT-LEAST-ONCE delivery; the consumer uses outbox_event_id as an
--   idempotency key to avoid repeating business processing. Disabling retry does
--   NOT create exactly-once -- it creates at-most-once and can LOSE messages.


-- =============================================================================
-- Appendix A -- RUNNABLE zero-row gate demonstration (no placeholders).
--
--   This anonymous block enforces the Transaction B guard in PURE SQL so the gate's
--   behaviour is concrete and testable on a DISPOSABLE cluster: it RAISES on a
--   zero-row transition, which fails the surrounding transaction instead of letting
--   a blind INSERT proceed. Substitute real disposable UUIDs before running. This
--   is a validation aid, not the production write path (drivers gate in app code).
-- =============================================================================
-- DO $$
-- DECLARE
--     v_job_id     uuid := '00000000-0000-0000-0000-000000000000';  -- disposable
--     v_tenant_id  uuid := '00000000-0000-0000-0000-000000000000';  -- disposable
--     v_rows       integer;
-- BEGIN
--     UPDATE app.jobs
--        SET job_status = 'running', started_at = now(), attempt_count = attempt_count + 1
--      WHERE job_id = v_job_id AND tenant_id = v_tenant_id AND job_status = 'queued';
--     GET DIAGNOSTICS v_rows = ROW_COUNT;
--     IF v_rows = 0 THEN
--         RAISE EXCEPTION 'transition_not_applied: job % was not queued', v_job_id
--             USING ERRCODE = 'P0001';
--     END IF;
--     -- ... Attempt/Event inserts would follow only on the 1-row path ...
-- END $$;
