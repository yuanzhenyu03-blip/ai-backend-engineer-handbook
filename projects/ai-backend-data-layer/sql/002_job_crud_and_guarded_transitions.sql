-- =============================================================================
-- Production AI Backend Data Layer — 002_job_crud_and_guarded_transitions.sql
-- Day30: SQL Data Manipulation and Query Fundamentals
--
-- A reference pack of raw, PARAMETERIZED statements for reading and changing the
-- durable Job facts created by 001_create_jobs.sql.
--
-- HOW TO READ THIS FILE
--   * These are TEMPLATES for an application/driver to execute with bound values.
--     They are not a migration and not a runnable script: $1/$2/$3 must be bound.
--   * `$1` is PostgreSQL/asyncpg-style positional parameter syntax (also used by
--     PostgreSQL PREPARE). psycopg normally uses %s and SQLAlchemy uses named
--     binds. Adapt the PLACEHOLDER SPELLING to your driver; the invariant is
--     code/data separation, never string-building SQL from client input.
--   * Every statement states its EXPECTED AFFECTED ROWS contract. If the real
--     count differs, the caller must treat it as a failure and must NOT report
--     success.
--
-- DELIBERATE DAY30 SCOPE (NOT added here):
--   no transactions, no locking (SELECT FOR UPDATE / SKIP LOCKED), no CHECK /
--   UNIQUE / foreign keys, no indexes, no Job Event or Attempt tables, no ORM,
--   no migration framework. Those are Day31-Day35 and Phase 4 topics.
--
-- Lesson: docs/postgresql/day30-sql-data-manipulation-and-query-fundamentals.md
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. INSERT a Job, letting PostgreSQL generate every other fact.
--    The application supplies only provider_metadata; job_id, job_status,
--    attempt_count, cancel_requested and created_at come from the table defaults.
--    Expected affected rows: exactly 1.
-- -----------------------------------------------------------------------------
INSERT INTO app.jobs (provider_metadata)
VALUES ($1::jsonb)
RETURNING job_id, job_status, attempt_count, cancel_requested, provider_metadata, created_at;

-- 1b. All-defaults variant (no business field supplied at all).
--     Expected affected rows: exactly 1.
INSERT INTO app.jobs DEFAULT VALUES
RETURNING job_id, job_status, attempt_count, cancel_requested, created_at;


-- -----------------------------------------------------------------------------
-- 2. Deterministic candidate list: the 20 oldest queued Jobs.
--    Explicit columns give a stable contract; job_id breaks created_at ties so
--    the page is reproducible.
--
--    NOT A CLAIM: two workers running this see the SAME rows. A concurrency-safe
--    claim needs locking (Day34), which is intentionally absent here.
--    Expected affected rows: 0..20 (a read).
-- -----------------------------------------------------------------------------
SELECT job_id, job_status, attempt_count, created_at
FROM app.jobs
WHERE job_status = 'queued'
ORDER BY created_at ASC, job_id ASC
LIMIT 20;


-- -----------------------------------------------------------------------------
-- 3. NULL-aware reads (SQL three-valued logic).
--    A comparison with NULL yields UNKNOWN, and WHERE keeps only TRUE.
-- -----------------------------------------------------------------------------

-- 3a. Jobs that have not finished. Expected affected rows: 0..N (a read).
SELECT job_id, job_status, attempt_count, finished_at
FROM app.jobs
WHERE finished_at IS NULL;

-- 3b. Errors other than 'timeout', INCLUDING rows with no recorded error.
--     Without the IS NULL branch, every no-error row would be filtered out,
--     because NULL <> 'timeout' is UNKNOWN (not TRUE).
--     Expected affected rows: 0..N (a read).
SELECT job_id, job_status, error_message
FROM app.jobs
WHERE error_message IS NULL
   OR error_message <> 'timeout';

-- 3c. NULL-safe alternative. Equivalent to 3b for this predicate, but easier to
--     invert by mistake — see the transition guard in section 4.
SELECT job_id, job_status, error_message
FROM app.jobs
WHERE error_message IS DISTINCT FROM 'timeout';


-- -----------------------------------------------------------------------------
-- 4. Guarded state transitions. WHERE is the modification boundary: it carries
--    BOTH the identity ($1) and the required CURRENT state.
--
--    Because job_id is the primary key, the contract is:
--      1 row  -> the transition applied
--      0 rows -> the transition did NOT apply. This does NOT prove the Job is
--                absent; it may exist in another state. Do not report success.
-- -----------------------------------------------------------------------------

-- 4a. queued -> running. Expected affected rows: 0 or 1.
--     NOTE: a guard of `job_status IS DISTINCT FROM 'queued'` would mean NOT
--     queued and could restart terminal Jobs. Require the state explicitly.
UPDATE app.jobs
SET job_status = 'running',
    started_at = now()
WHERE job_id = $1
  AND job_status = 'queued'
RETURNING job_id, job_status, started_at;

-- 4b. running -> succeeded. $2 is an Object Storage REFERENCE, never the bytes.
--     Expected affected rows: 0 or 1.
UPDATE app.jobs
SET job_status = 'succeeded',
    finished_at = now(),
    result_object_key = $2
WHERE job_id = $1
  AND job_status = 'running'
RETURNING job_id, job_status, finished_at, result_object_key;


-- -----------------------------------------------------------------------------
-- 5. attempt_count without a lost update.
-- -----------------------------------------------------------------------------

-- 5a. Database-side increment: the computation happens inside ONE statement, so
--     there is no application read-compute-write window.
--     Expected affected rows: 0 or 1.
UPDATE app.jobs
SET attempt_count = attempt_count + 1
WHERE job_id = $1
RETURNING job_id, attempt_count;

-- 5b. Optimistic expected-value guard: $2 is the value the caller last read,
--     $3 is the value it wants to write.
--     0 rows -> the stale expectation did not match; the caller must NOT report
--     success and must decide whether to reread/retry.
--     This is AWARENESS only; full concurrency design is Day34.
--     Expected affected rows: 0 or 1.
UPDATE app.jobs
SET attempt_count = $3
WHERE job_id = $1
  AND attempt_count = $2
RETURNING job_id, attempt_count;


-- -----------------------------------------------------------------------------
-- 6. Guarded cleanup DELETE.
--    SQL AND binds more tightly than OR, so
--        WHERE created_at < $1 AND job_status = '' OR job_status = 'banana'
--    would parse as (date AND empty) OR (banana) and delete EVERY banana row
--    regardless of date. Use IN (...) — or explicit parentheses.
--
--    A prior SELECT with the same predicate is only a PREVIEW; rows can change
--    between statements. DELETE ... RETURNING is the evidence of what was
--    actually removed. Making preview and delete consistent needs a transaction
--    (Day33).
--    Expected affected rows: 0..N — compare against the reconciled expectation
--    before treating the cleanup as correct.
-- -----------------------------------------------------------------------------
DELETE FROM app.jobs
WHERE created_at < $1::timestamptz
  AND job_status IN ('', 'banana')
RETURNING job_id, job_status, created_at;
