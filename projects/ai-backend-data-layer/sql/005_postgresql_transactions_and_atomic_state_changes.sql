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
-- JOB EVENT vs OUTBOX EVENT (read before the transactions)
--   app.job_events   = INTERNAL business history. Append one for every state change.
--   app.outbox_events = a PENDING EXTERNAL INTEGRATION DUTY. Create one ONLY when a real
--                       downstream consumer must be told (dispatch, notification, webhook,
--                       billing, search indexing, ...). NOT every Job Event needs an Outbox
--                       Event. An Outbox row with no consumer is unpublishable noise.
--   Outbox payload = STABLE identifiers + minimal references ONLY. Never result bytes,
--                    never secrets, never short-lived signed URLs. The consumer fetches the
--                    authorized result later via a stable reference. outbox_event_id is the
--                    consumer's idempotency key. Publication is at-least-once; it never
--                    proves the consumer completed its business work.
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
-- This Outbox row has a REAL consumer: the dispatch path that hands the queued Job to a
-- Worker. That is why Accept couples the two writes -- at CREATION time a durable Job must
-- come with the durable intent to dispatch it. (This is the creation-time rule, not a
-- permanent "a Job row always has an Outbox row": a retention policy may later archive
-- published rows.)
-- payload ($6) carries STABLE ids + minimal references only -- no bytes, secrets, or signed
-- URLs. outbox_event_id is the STABLE key the consumer deduplicates on; a duplicate value
-- raises 23505 unique_violation, failing the transaction and rolling the Job INSERT back
-- with it (classroom test 2).

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
-- $4 is the attempt_count RETURNED above -- do not recompute it on the client.
--
-- provider_request_id / cost_micros / finished_at stay NULL here: none of them is
-- known yet. But the DURABLE fact that recovery depends on -- attempt_id ($3) -- is
-- committed by this transaction. attempt_id is the STABLE, pre-call correlation /
-- provider-idempotency key: it exists before the Provider is ever called, so a crash
-- during the external phase cannot lose it. See the External phase for how it is used.

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
--   TWO DIFFERENT IDENTIFIERS -- do not conflate them:
--     - provider_idempotency_key / correlation key: generated BEFORE the request,
--       from an ALREADY-DURABLE fact. Use attempt_id (committed in Transaction B) or
--       a value deterministically derived from it. If the Provider supports
--       idempotency keys, the Worker SENDS this key with the request.
--     - provider_request_id: the id the Provider RETURNS after accepting the call.
--       It does not exist until the call returns and is persisted only in
--       Transaction C. It is a convenience for lookup, NOT the recovery anchor.
--
--   Why this split matters (the failure window this closes):
--     Provider accepts request -> Worker receives provider_request_id
--     -> Worker CRASHES before Transaction C -> provider_request_id is NOT persisted.
--   Because the pre-call key is attempt_id (already durable after Transaction B),
--   reconciliation can still find/deduplicate the Provider call by that stable key.
--   Transaction B does NOT persist a Provider-returned id -- it persists attempt_id,
--   which is enough only IF the pre-call key is derived from it and sent to the Provider.
--
--   If the Provider has NO idempotency support, PostgreSQL CANNOT eliminate this
--   unknown-outcome window: such an Attempt must be ISOLATED and reconciled (query the
--   Provider, inspect Object Storage, or reconcile manually) -- never blindly retried,
--   which can repeat Provider cost and side effects (classroom incident #8).
--
--   What PostgreSQL can prove right now: the Job is running and an Attempt/Event
--   exist. What it CANNOT prove: that the Provider produced a result, or even that
--   any provider_request_id exists yet. A recorded id (once Transaction C runs) proves
--   an id was recorded, never the external outcome.
-- -----------------------------------------------------------------------------
-- (no SQL -- external Provider request + Object Storage write happen here)


-- -----------------------------------------------------------------------------
-- TRANSACTION C -- COMPLETE.  Atomically persist the finished Attempt, the guarded
-- terminal Job state, the Result Artifact reference, the append-only success
-- Event, and -- ONLY WHEN a concrete downstream integration contract is configured
-- -- the corresponding Outbox publication intent, all or nothing.
--
--   Fixed members of this atomic bundle: Attempt finish, guarded Job succeeded,
--   Result Artifact reference, and the append-only success Event. The success Outbox
--   intent is CONDITIONAL -- it joins the same transaction (and rolls back with it)
--   ONLY if a real downstream consumer is configured (see the conditional INSERT
--   below). With no consumer, no success Outbox row is created at all.
--
--   Integrated rollback case (classroom incident #12): if the Artifact INSERT
--   violates a constraint, the whole transaction rolls back. None of Attempt finish,
--   Job succeeded, or the success Event become committed facts; the conditional
--   Outbox intent, IF enabled, rolls back with them. The Provider cost and the
--   Object Storage bytes REMAIN -- they were never in the transaction. The object may
--   be an orphan until reconciliation or a separately audited compensating delete.
--   Database rollback is not Object Storage rollback.
-- -----------------------------------------------------------------------------
BEGIN;

-- Finish the current Attempt and record the Provider-RETURNED id ($3) and cost ($4).
-- finished_at IS NULL in the WHERE clause is a GUARD, not decoration: it finishes only
-- an Attempt that has NOT already finished, so an already-recorded outcome is never
-- overwritten.
UPDATE app.job_attempts
   SET finished_at         = now(),
       provider_request_id = $3,
       cost_micros         = $4
 WHERE attempt_id   = $2
   AND job_id       = $1
   AND finished_at IS NULL
RETURNING attempt_id;
-- CONTROL-FLOW CONTRACT: 0 rows can mean the Attempt does not exist, does not belong to
--   this Job, OR is ALREADY FINISHED. In every case: ROLLBACK and STOP. Do NOT overwrite
--   a finished Attempt's finished_at / provider_request_id / cost_micros -- that would
--   destroy the evidence of the outcome already recorded. An already-finished current
--   Attempt on a still-running Job is Day32's running_with_finished_current_attempt: it
--   goes to ISOLATION and reconciliation, and is NEVER auto-"fixed" to succeeded here.

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
--   write the Artifact / success Event (or any conditional Outbox) rows for a
--   completion that did not apply.

INSERT INTO app.result_artifacts (artifact_id, attempt_id, artifact_type, object_key, content_type, size_bytes, checksum)
VALUES ($6, $2, $7, $8, $9, $10, $11);
-- References the Object Storage object by KEY; the bytes live in Object Storage,
-- not PostgreSQL. UNIQUE (attempt_id, object_key) makes a duplicate reference raise
-- 23505 and roll the whole completion back (classroom test 4).

-- The success Job EVENT is ALWAYS written: it is internal business history.
INSERT INTO app.job_events (job_id, attempt_id, event_type, from_status, to_status, actor)
VALUES ($1, $2, 'job_succeeded', 'running', 'succeeded', $12);

-- The success OUTBOX row is CONDITIONAL. Write it ONLY when a real downstream contract
-- exists that must learn the Job succeeded -- a notification, webhook, billing meter, or
-- search-index update. This project defines NO such consumer, so the statement is shown
-- commented out: it is OPTIONAL, not a mandatory part of completion. Uncomment it only
-- alongside a concrete consumer. (Not every Job Event needs an Outbox Event.)
-- payload ($14) carries STABLE ids + minimal references only -- no result bytes, no
-- secrets, no signed URLs; the consumer fetches the authorized result via a stable
-- reference. outbox_event_id ($13) is the consumer idempotency key. Publication is
-- at-least-once and does NOT prove the consumer completed its business work.
--
-- INSERT INTO app.outbox_events (outbox_event_id, job_id, event_type, payload)
-- VALUES ($13, $1, 'job.succeeded', $14);

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
