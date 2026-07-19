-- =============================================================================
-- Production AI Backend Data Layer — 001_create_jobs.sql
-- Day29: PostgreSQL Foundations and Durable Relational State
--
-- Purpose: persist the accepted Job BEFORE FastAPI returns "202 Accepted".
--          The row is the durable business fact; this file is its contract.
--
-- SCOPE (deliberately minimal — see README.md "Known gaps"):
--   This is NOT a complete production Job model. It has no CHECK constraints,
--   no business/idempotency key, no UNIQUE rule beyond the primary key, no
--   tenant ownership, no Documents/Attempts/Events/Outbox tables, no foreign
--   keys, no indexes beyond the primary key, and no migration framework.
--   Those arrive in Day31+ (relationships/integrity), Day33 (transactions),
--   Day34 (concurrency/idempotency), Day35 (indexes), Day36 (migrations).
--
-- Executed in class against PostgreSQL 14.18 (Homebrew) in a disposable cluster.
-- Large bytes (the 500 MB source document, large derived artifacts) live in
-- Object Storage; result_object_key below is a REFERENCE only.
-- =============================================================================

-- Explicit namespace so nothing depends on a session's search_path.
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE app.jobs (
    -- Stable row identity. UUID chosen for distributed generation and a
    -- non-enumerable public identifier (cost: larger + weaker index locality).
    job_id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Evolving lifecycle state.
    -- NOTE: NOT NULL rejects SQL NULL only. Empty string and arbitrary text
    -- (e.g. 'banana') are still ACCEPTED. A CHECK/enum rule is Day31 work.
    job_status        text        NOT NULL DEFAULT 'queued',

    -- Retry bookkeeping. A CHECK (attempt_count >= 0) is Day31 work.
    attempt_count     integer     NOT NULL DEFAULT 0,

    -- Cooperative cancellation request flag.
    cancel_requested  boolean     NOT NULL DEFAULT false,

    -- BOUNDED auxiliary metadata only. Never store large bytes, secrets,
    -- signed URLs, the only job_id, or the only job_status here. A frequently
    -- queried field (e.g. provider_request_id) should become a typed column.
    provider_metadata jsonb       NOT NULL DEFAULT '{}'::jsonb,

    -- Immutable acceptance instant. timestamptz = one absolute instant,
    -- rendered in the session time zone.
    created_at        timestamptz NOT NULL DEFAULT now(),

    -- Lifecycle timestamps: NULL means "has not occurred yet".
    started_at        timestamptz,          -- NULL -> execution has not started
    finished_at       timestamptz,          -- NULL -> not terminal yet

    -- NULL -> no recorded error.
    error_message     text,

    -- NULL -> no result artifact yet. Reference into Object Storage, not bytes.
    result_object_key text
);
