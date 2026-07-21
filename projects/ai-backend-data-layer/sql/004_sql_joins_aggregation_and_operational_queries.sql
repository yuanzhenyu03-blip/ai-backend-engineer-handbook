-- =============================================================================
-- Production AI Backend Data Layer — 004_sql_joins_aggregation_and_operational_queries.sql
-- Day32: SQL Joins, Aggregation, and Operational Queries
--
-- WHAT THIS FILE IS
--   A read-only operational query pack for the Day31 relational model. It turns
--   the entities created by 003 into evidence an operator can act on.
--
--   Target schema: 001_create_jobs.sql -> 003_relational_modeling_and_data_integrity.sql
--   (002 is the Day30 statement reference pack for the Day29 BASE schema; these
--   queries assume the Day31 model, including jobs.tenant_id.)
--
-- HOW TO READ THIS FILE
--   * Every query states its RESULT GRAIN before the SQL. Grain is the contract:
--     get it wrong and COUNT/SUM/AVG silently lie.
--   * `$1`, `$2`, ... are DRIVER/PREPARE placeholders (asyncpg style), exactly as
--     in 002. They are NOT raw psql variables: pasting them into psql raises
--     "there is no parameter $1". Bind them from an application, or substitute
--     literals when exploring in psql.
--   * Detail queries use DETERMINISTIC ORDER BY so pages are reproducible.
--   * tenant_id is always a predicate. Day31: composite FKs give write-time
--     integrity, NOT authorization. Reads must be tenant-scoped, with tenant_id
--     taken from authenticated server context.
--
-- WHAT THIS FILE IS **NOT**
--   * No indexes, no EXPLAIN, no performance claims — correctness before
--     optimization; measured indexing is Day35.
--   * No transactions or locking — Day33/Day34.
--   * No migrations, no ORM, no repair statements. The incident query CLASSIFIES
--     evidence; it never mutates data.
--   * No query here proves an EXTERNAL outcome (Provider call, Object Storage
--     write, queue delivery). It reports only what was persisted.
--
-- Lesson: docs/postgresql/day32-sql-joins-aggregation-and-operational-queries.md
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Job detail with OPTIONAL Attempt rows.
--
--    GRAIN: one row per Job-Attempt combination.
--      0 Attempts -> ONE row, Attempt columns NULL (the Job is preserved)
--      N Attempts -> N rows
--
--    INNER JOIN would DROP queued Jobs that no Worker has claimed yet — exactly
--    the backlog an operations dashboard must show. The NULL Attempt columns are
--    meaningful evidence ("no Attempt row exists"), not corrupt data.
-- -----------------------------------------------------------------------------
SELECT
    j.job_id,
    j.job_status,
    j.created_at,
    a.attempt_id,
    a.attempt_number,
    a.started_at   AS attempt_started_at,
    a.finished_at  AS attempt_finished_at,
    a.error_code
FROM app.jobs AS j
LEFT JOIN app.job_attempts AS a
       ON a.job_id = j.job_id
WHERE j.tenant_id = $1
ORDER BY j.created_at ASC, j.job_id ASC, a.attempt_number ASC NULLS FIRST;


-- -----------------------------------------------------------------------------
-- 2. Job-Attempt and Job-Event detail as SEPARATE queries.
--
--    Joining BOTH one-to-many children in one statement multiplies rows: three
--    Attempts and four Events produce 3 x 4 = 12 combinations, because the
--    database has no idea which Event belongs to which Attempt. That is a
--    COMBINATION, not an allocation.
--
--      Attempts  Events  Rows
--      0         0       1     (Job preserved, both child sides NULL)
--      0         4       4     (the NULL-extended Job row matches every Event)
--      3         0       3
--      3         4       12
--
--    Keep them separate for detail views. For per-Job METRICS, pre-aggregate
--    (query 6).
-- -----------------------------------------------------------------------------

-- 2a. GRAIN: one row per Job-Attempt combination (0 Attempts -> one NULL row).
SELECT
    j.job_id,
    j.job_status,
    a.attempt_id,
    a.attempt_number,
    a.provider_request_id,
    a.started_at,
    a.finished_at,
    a.error_code,
    a.cost_micros
FROM app.jobs AS j
LEFT JOIN app.job_attempts AS a
       ON a.job_id = j.job_id
WHERE j.tenant_id = $1
  AND j.job_id    = $2
ORDER BY a.attempt_number ASC NULLS FIRST, a.attempt_id ASC;

-- 2b. GRAIN: one row per Job-Event combination (0 Events -> one NULL row).
--     job_events.attempt_id is OPTIONAL provenance (Day31 composite FK keeps a
--     non-NULL Attempt in the SAME Job); NULL means "not attributed to an Attempt".
SELECT
    j.job_id,
    e.event_id,
    e.event_type,
    e.from_status,
    e.to_status,
    e.attempt_id,
    e.actor,
    e.occurred_at
FROM app.jobs AS j
LEFT JOIN app.job_events AS e
       ON e.job_id = j.job_id
WHERE j.tenant_id = $1
  AND j.job_id    = $2
ORDER BY e.occurred_at ASC NULLS FIRST, e.event_id ASC;


-- -----------------------------------------------------------------------------
-- 3. Per-Job Attempt counts with CONDITIONAL aggregation.
--
--    GRAIN: one row per Job (GROUP BY establishes it — not the join).
--
--    COUNT(*) counts RESULT ROWS, including the NULL-extended outer-join row, so
--    a zero-Attempt Job would report 1. COUNT(a.attempt_id) counts only real
--    Attempt identities, so it reports 0. Use the child key.
--
--    The FILTER clause keeps the failed-Attempt condition INSIDE the aggregate.
--    Moving `a.error_code IS NOT NULL` into WHERE would delete successful
--    Attempts AND the zero-Attempt placeholder row, silently collapsing the LEFT
--    JOIN back into an INNER JOIN.
--
--    Portable alternative (same result, older-PostgreSQL friendly):
--      SUM(CASE WHEN a.error_code IS NOT NULL THEN 1 ELSE 0 END)
--
--    HAVING filters GROUPS after aggregation; WHERE filters INPUT rows before it.
--    Tenant/state/raw-time predicates belong in WHERE so irrelevant rows never
--    enter the aggregation.
-- -----------------------------------------------------------------------------
SELECT
    j.job_id,
    j.job_status,
    COUNT(a.attempt_id)                                            AS total_attempts,
    COUNT(a.attempt_id) FILTER (WHERE a.error_code IS NOT NULL)    AS failed_attempts
FROM app.jobs AS j
LEFT JOIN app.job_attempts AS a
       ON a.job_id = j.job_id
WHERE j.tenant_id = $1
GROUP BY j.job_id, j.job_status
HAVING COUNT(a.attempt_id) >= $2          -- e.g. 2: Jobs that retried at least twice
ORDER BY failed_attempts DESC, j.job_id ASC;


-- -----------------------------------------------------------------------------
-- 4. Queue health for one tenant.
--
--    GRAIN: exactly one summary row. COUNT(*) is safe here because the query
--    reads app.jobs only — there is no join and therefore no multiplication.
--
--    An EMPTY queue returns count 0 with NULL oldest/newest/age. A dashboard must
--    render "no backlog" differently from "no data" — they are not the same fact.
-- -----------------------------------------------------------------------------
SELECT
    COUNT(*)                        AS queued_jobs,
    MIN(j.created_at)               AS oldest_queued_at,
    MAX(j.created_at)               AS newest_queued_at,
    now() - MIN(j.created_at)       AS oldest_queued_age
FROM app.jobs AS j
WHERE j.tenant_id  = $1
  AND j.job_status = 'queued';


-- -----------------------------------------------------------------------------
-- 5. Per-Job recorded cost, with COMPLETENESS exposed.
--
--    GRAIN: one row per Job.
--
--    SUM/AVG IGNORE NULL, and NULL is excluded from AVG's denominator. For costs
--    100, 300, NULL: SUM = 400, AVG = 200 (not 133.33).
--
--    NULL means UNKNOWN / NOT RECORDED — never zero. So the partial sum is named
--    recorded_total_cost_micros, never total_job_cost, and the completeness
--    counts travel with it. Do NOT wrap it in COALESCE(..., 0): that conflates a
--    genuine zero cost with absent evidence.
-- -----------------------------------------------------------------------------
SELECT
    j.job_id,
    COUNT(a.attempt_id)                                             AS total_attempts,
    COUNT(a.cost_micros)                                            AS cost_reported_attempts,
    SUM(a.cost_micros)                                              AS recorded_total_cost_micros,
    AVG(a.cost_micros)                                              AS recorded_average_cost_micros,
    MIN(a.started_at)                                               AS first_attempt_started_at,
    MAX(a.finished_at)                                              AS last_attempt_finished_at
FROM app.jobs AS j
LEFT JOIN app.job_attempts AS a
       ON a.job_id = j.job_id
WHERE j.tenant_id = $1
GROUP BY j.job_id
ORDER BY j.job_id ASC;


-- -----------------------------------------------------------------------------
-- 6. One row per Job with BOTH Attempt and Event metrics — the safe composition.
--
--    GRAIN: one row per Job.
--
--    Each child is reduced to its own one-row-per-Job summary FIRST, then the
--    summaries are LEFT JOINed to Jobs. Nothing multiplies because each CTE
--    already has job_id as its grain.
--
--    A CTE is a READABILITY / decomposition tool. It does NOT by itself guarantee
--    one row per Job — the GROUP BY job_id inside each CTE does.
--
--    Do NOT try to patch a multiplied result with DISTINCT:
--      COUNT(DISTINCT attempt_id) can repair a count, but
--      SUM(DISTINCT cost_micros) is WRONG — two legitimate Attempts may cost the
--      same amount, and the duplicate would be discarded.
--    Prefer correct grain over patched aggregates.
-- -----------------------------------------------------------------------------
WITH attempt_summary AS (
    SELECT
        a.job_id,
        COUNT(*)                                              AS attempt_count,
        COUNT(*) FILTER (WHERE a.error_code IS NOT NULL)      AS failed_attempt_count,
        COUNT(a.cost_micros)                                  AS cost_reported_attempts,
        SUM(a.cost_micros)                                    AS recorded_total_cost_micros,
        MAX(a.attempt_number)                                 AS max_attempt_number
    FROM app.job_attempts AS a
    GROUP BY a.job_id
),
event_summary AS (
    SELECT
        e.job_id,
        COUNT(*)                                              AS event_count,
        MAX(e.occurred_at)                                    AS last_event_at
    FROM app.job_events AS e
    GROUP BY e.job_id
)
SELECT
    j.job_id,
    j.job_status,
    j.created_at,
    COALESCE(s.attempt_count, 0)          AS attempt_count,        -- a real count: 0 is true
    COALESCE(s.failed_attempt_count, 0)   AS failed_attempt_count,
    s.cost_reported_attempts,
    s.recorded_total_cost_micros,          -- left NULL when nothing was recorded
    s.max_attempt_number,
    COALESCE(v.event_count, 0)            AS event_count,
    v.last_event_at
FROM app.jobs AS j
LEFT JOIN attempt_summary AS s ON s.job_id = j.job_id
LEFT JOIN event_summary   AS v ON v.job_id = j.job_id
WHERE j.tenant_id = $1
ORDER BY j.created_at ASC, j.job_id ASC;


-- -----------------------------------------------------------------------------
-- 7. Stage-aware "stuck" CANDIDATES for running Jobs.
--
--    GRAIN: one row per running Job.
--
--    Different lifecycle stages need DIFFERENT clocks:
--      queued age  -> jobs.created_at (acceptance/queue entry)
--      running age -> the CURRENT Attempt's started_at (claim/execution)
--      terminal    -> finished_at or a terminal Event
--    A Job accepted two hours ago but claimed 30 seconds ago is NOT a two-hour
--    running Job.
--
--    "Current Attempt" = greatest attempt_number. Day31 enforces
--    attempt_number > 0 and UNIQUE (job_id, attempt_number), but does NOT enforce
--    that higher numbers were created later — the write path must preserve that
--    meaning.
--
--    These are CANDIDATES / anomalies, never proof a Worker died:
--      running_without_attempt            -> a coherence anomaly (possible partial
--                                            multi-table write, legacy path, or a
--                                            repair error). Day33 prevents the
--                                            atomicity gap; Day34 adds claim evidence.
--      running_with_finished_current_attempt -> state/child disagreement
--      running_attempt_over_threshold     -> exceeded an operational SLA threshold
--    $2 is a policy threshold (an interval) and must reflect real AI Provider
--    runtimes, not a guess.
-- -----------------------------------------------------------------------------
WITH current_attempt AS (
    SELECT DISTINCT ON (a.job_id)
        a.job_id,
        a.attempt_id,
        a.attempt_number,
        a.started_at,
        a.finished_at
    FROM app.job_attempts AS a
    ORDER BY a.job_id, a.attempt_number DESC, a.attempt_id DESC
)
SELECT
    j.job_id,
    j.job_status,
    c.attempt_id           AS current_attempt_id,
    c.attempt_number       AS current_attempt_number,
    c.started_at           AS current_attempt_started_at,
    now() - c.started_at   AS running_age,
    CASE
        WHEN c.attempt_id IS NULL                THEN 'running_without_attempt'
        WHEN c.finished_at IS NOT NULL           THEN 'running_with_finished_current_attempt'
        WHEN now() - c.started_at > $2::interval THEN 'running_attempt_over_threshold'
        ELSE 'running_within_threshold'
    END                    AS anomaly_class
FROM app.jobs AS j
LEFT JOIN current_attempt AS c ON c.job_id = j.job_id
WHERE j.tenant_id  = $1
  AND j.job_status = 'running'
ORDER BY c.started_at ASC NULLS FIRST, j.job_id ASC;


-- -----------------------------------------------------------------------------
-- 8. Terminal throughput over an EXPLICIT half-open window [$2, $3).
--
--    GRAIN: exactly one summary row.
--
--    Throughput measures COMPLETION, so it filters on finished_at — not
--    created_at, which measures accepted DEMAND. A Job accepted in the window but
--    still running has not contributed throughput.
--
--    The window is half-open so adjacent windows never double-count a row landing
--    exactly on the boundary.
--
--    Day31 guarantees only that `succeeded` implies finished_at IS NOT NULL.
--    Other terminal states may carry NULL finished_at; those rows simply fall
--    outside this window and MUST be surfaced by a separate coherence report
--    rather than silently read as zero throughput.
-- -----------------------------------------------------------------------------
SELECT
    COUNT(*)                                                          AS terminal_jobs,
    COUNT(*) FILTER (WHERE j.job_status = 'succeeded')                AS succeeded_jobs,
    COUNT(*) FILTER (WHERE j.job_status = 'failed')                   AS failed_jobs,
    COUNT(*) FILTER (WHERE j.job_status = 'cancelled')                AS cancelled_jobs,
    AVG(j.finished_at - j.created_at)
        FILTER (WHERE j.job_status = 'succeeded')                     AS avg_successful_duration
FROM app.jobs AS j
WHERE j.tenant_id    = $1
  AND j.finished_at >= $2::timestamptz      -- inclusive lower bound
  AND j.finished_at <  $3::timestamptz;     -- EXCLUSIVE upper bound


-- -----------------------------------------------------------------------------
-- 9. Affected-Job membership from RECORDED release provenance.
--
--    GRAIN: one row per affected Job (DISTINCT collapses multiple matching events).
--
--    Deployment TIME is correlation, not provenance. During a rolling deployment
--    old and new Workers coexist: a pre-deployment Job may be processed by the new
--    release, a post-deployment Job by the old one, and one Job's retries may span
--    releases. Only a fact recorded AT PROCESSING TIME identifies the release.
--
--    LIMITATION (honest): the Day31 schema has NO typed release/build column, so
--    this reads bounded JSONB, job_events.metadata ->> 'worker_release_id'. Its
--    completeness is NOT enforced by any constraint — a write path that forgot to
--    record it produces a silent gap. Typed per-execution provenance is a future
--    schema-evolution decision (Day36), not a silent Day32 alteration.
-- -----------------------------------------------------------------------------
SELECT DISTINCT
    j.job_id,
    j.job_status,
    j.created_at,
    j.finished_at
FROM app.jobs AS j
JOIN app.job_events AS e
  ON e.job_id = j.job_id
WHERE j.tenant_id = $1
  AND e.metadata ->> 'worker_release_id' = $2
ORDER BY j.created_at ASC, j.job_id ASC;


-- -----------------------------------------------------------------------------
-- 10. Incident evidence summary for an affected release — CLASSIFY, never repair.
--
--     GRAIN: one row per affected Job.
--
--     Each one-to-many child (Attempts, Artifacts, Outbox) is pre-aggregated to
--     job_id BEFORE joining, so no metric is multiplied. Artifacts hang off
--     Attempts (Day31), so they are rolled up through job_attempts.
--
--     This query emits NO repair. It produces the classification an operator needs
--     before deciding anything:
--
--       rollback/contain future bad writes
--       -> identify affected set from explicit provenance (query 9)
--       -> preserve evidence
--       -> pre-aggregate DB evidence without multiplication (this query)
--       -> reconcile Provider status, Worker logs, Object Storage, Outbox,
--          and the client-visible result
--       -> quarantine unknown external outcomes
--       -> guarded repair/requeue of VERIFIED SAFE subsets only
--       -> verify affected rows and downstream behaviour
--
--     CRITICAL: finished_at IS NULL and zero Artifacts do NOT prove the Provider
--     did nothing. The request may be in flight, may have succeeded with a lost
--     response, or the Worker may have crashed before persisting evidence.
--     published_at IS NULL likewise may mean "never sent" OR "sent, then crashed
--     before write-back". A PostgreSQL transaction cannot atomically include an
--     external Provider call — that boundary carries into Day33.
--     Bulk-requeueing this set would repeat Provider work and cost.
-- -----------------------------------------------------------------------------
WITH affected_jobs AS (
    SELECT DISTINCT e.job_id
    FROM app.job_events AS e
    WHERE e.metadata ->> 'worker_release_id' = $2
),
attempt_evidence AS (
    SELECT
        a.job_id,
        COUNT(*)                                           AS attempt_count,
        COUNT(a.provider_request_id)                       AS provider_calls_recorded,
        COUNT(a.cost_micros)                               AS cost_reported_attempts,
        SUM(a.cost_micros)                                 AS recorded_total_cost_micros,
        MAX(a.finished_at)                                 AS last_attempt_finished_at
    FROM app.job_attempts AS a
    GROUP BY a.job_id
),
artifact_evidence AS (
    SELECT
        a.job_id,
        COUNT(r.artifact_id)                               AS artifact_count
    FROM app.job_attempts AS a
    JOIN app.result_artifacts AS r ON r.attempt_id = a.attempt_id
    GROUP BY a.job_id
),
outbox_evidence AS (
    SELECT
        o.job_id,
        COUNT(*)                                           AS outbox_rows,
        COUNT(o.published_at)                              AS outbox_published_rows
    FROM app.outbox_events AS o
    GROUP BY o.job_id
)
SELECT
    j.job_id,
    j.job_status,
    j.finished_at,
    COALESCE(ae.attempt_count, 0)            AS attempt_count,
    COALESCE(ae.provider_calls_recorded, 0)  AS provider_calls_recorded,
    ae.cost_reported_attempts,
    ae.recorded_total_cost_micros,           -- NULL = no cost evidence recorded
    COALESCE(ar.artifact_count, 0)           AS artifact_count,
    COALESCE(ob.outbox_rows, 0)              AS outbox_rows,
    COALESCE(ob.outbox_published_rows, 0)    AS outbox_published_rows,
    CASE
        WHEN j.job_status = 'succeeded'
             AND COALESCE(ar.artifact_count, 0) > 0        THEN 'completed_with_artifact'
        WHEN j.job_status = 'succeeded'                    THEN 'succeeded_without_recorded_artifact'
        WHEN COALESCE(ae.provider_calls_recorded, 0) > 0
             AND j.finished_at IS NULL                     THEN 'provider_called_outcome_unknown'
        WHEN COALESCE(ae.attempt_count, 0) = 0             THEN 'no_recorded_attempt'
        ELSE 'needs_manual_reconciliation'
    END                                       AS evidence_class
FROM app.jobs AS j
JOIN affected_jobs   AS f  ON f.job_id  = j.job_id
LEFT JOIN attempt_evidence  AS ae ON ae.job_id = j.job_id
LEFT JOIN artifact_evidence AS ar ON ar.job_id = j.job_id
LEFT JOIN outbox_evidence   AS ob ON ob.job_id = j.job_id
WHERE j.tenant_id = $1
ORDER BY j.created_at ASC, j.job_id ASC;
