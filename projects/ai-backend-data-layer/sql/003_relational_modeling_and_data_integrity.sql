-- =============================================================================
-- Production AI Backend Data Layer — 003_relational_modeling_and_data_integrity.sql
-- Day31: Relational Modeling and Data Integrity
--
-- WHAT THIS FILE IS
--   A TARGET/REFERENCE schema increment that turns the Day29 Job row into a
--   relational model whose ownership, cardinality, identity, tenant boundaries,
--   provenance, and legal states are enforced by PostgreSQL.
--
--   It is written to run on a FRESH, EMPTY database, immediately after
--   001_create_jobs.sql. Apply order:
--       001_create_jobs.sql   -> 003_relational_modeling_and_data_integrity.sql
--   (002_job_crud_and_guarded_transitions.sql is a statement reference pack, not
--   DDL, so it is not part of the apply order.)
--
-- WHAT THIS FILE IS **NOT**
--   * NOT a production-safe migration. The ALTER TABLE statements below add
--     NOT NULL columns (tenant_id, idempotency_key) WITHOUT defaults, so they
--     succeed only while app.jobs is EMPTY. Against existing rows they fail
--     (23502 not_null_violation) and would require an expand -> backfill ->
--     validate -> switch -> contract sequence. That safe-evolution mechanic is
--     Day36 and is deliberately NOT attempted here. Do not invent tenant or
--     idempotency values for historical rows.
--   * NOT transactional, concurrency-safe, or performance-tuned. Transactions are
--     Day33, locking/MVCC/SKIP LOCKED are Day34, and measured indexes are Day35.
--     Only the indexes PostgreSQL creates implicitly for PRIMARY KEY/UNIQUE
--     constraints exist here.
--   * NOT row-level security. RLS, production roles, and permission hardening are
--     future production security work and were not taught or validated in Day31.
--
-- LEGACY COLUMN NOTE
--   app.jobs.result_object_key (from 001) predates the normalized
--   app.result_artifacts table. In the target model an Attempt owns its Artifacts,
--   so result_object_key becomes a legacy single-artifact pointer. This file does
--   NOT drop it: removing a column that applications still read requires the
--   compatible sequence owned by Day36. A row-level CHECK also cannot assert that
--   a child Artifact row exists, so the "succeeded implies an artifact" rule is
--   only partially expressible here (see jobs_succeeded_has_finished_at) and must
--   be completed by the Day33 transactional workflow plus operational verification.
--
-- Object Storage boundary: this schema stores REFERENCES, checksums, sizes and
-- provenance only. Large source/result bytes never enter PostgreSQL. No secrets,
-- signed URLs, or credentials appear in this file.
--
-- Lesson: docs/postgresql/day31-relational-modeling-and-data-integrity.md
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Tenants — the ownership root.
--    A tenant_id column records WHO owns a row. It does not by itself authorize
--    a caller (authorization is a query/session concern, see the lesson).
-- -----------------------------------------------------------------------------
CREATE TABLE app.tenants (
    tenant_id   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_slug text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT tenants_slug_unique UNIQUE (tenant_slug)
);


-- -----------------------------------------------------------------------------
-- 2. Upload Sessions — the pre-Document lifecycle.
--    A session may EXPIRE without ever producing a Document.
--    The (tenant_id, upload_session_id) candidate key is not required by the
--    current relationships, but it keeps tenant-aware composite references
--    available if a later lesson needs them.
-- -----------------------------------------------------------------------------
CREATE TABLE app.upload_sessions (
    upload_session_id uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid        NOT NULL
                                  REFERENCES app.tenants(tenant_id)
                                  ON DELETE RESTRICT,
    session_status    text        NOT NULL DEFAULT 'initiated',
    object_key        text        NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    expires_at        timestamptz,

    CONSTRAINT upload_sessions_tenant_id_unique
        UNIQUE (tenant_id, upload_session_id),

    CONSTRAINT upload_sessions_status_allowed
        CHECK (session_status IN ('initiated', 'uploading', 'verified', 'failed', 'expired'))
);


-- -----------------------------------------------------------------------------
-- 3. Documents — a verified upload.
--    Optional one-to-one from the Upload Session's perspective:
--      FOREIGN KEY            -> many-to-one
--      FOREIGN KEY + UNIQUE   -> one-to-one
--    The FK lives on the LATER-created row (Document), which records the
--    Document's provenance naturally instead of putting a future reverse pointer
--    on the earlier Upload Session.
-- -----------------------------------------------------------------------------
CREATE TABLE app.documents (
    document_id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid        NOT NULL
                                  REFERENCES app.tenants(tenant_id)
                                  ON DELETE RESTRICT,
    -- No single-column FK here: it would only prove the session EXISTS. The
    -- tenant-aware composite FK below additionally proves the Document and its
    -- Upload Session belong to the SAME tenant.
    upload_session_id uuid        NOT NULL,
    object_key        text        NOT NULL,
    content_type      text,
    size_bytes        bigint,
    checksum          text,
    created_at        timestamptz NOT NULL DEFAULT now(),

    -- One Upload Session produces AT MOST ONE Document.
    CONSTRAINT documents_upload_session_unique
        UNIQUE (upload_session_id),

    -- Same-tenant provenance: rejects a Tenant-B Document claiming a Tenant-A
    -- Upload Session (23503 foreign_key_violation). Requires the
    -- upload_sessions_tenant_id_unique candidate key.
    CONSTRAINT documents_upload_session_same_tenant_fk
        FOREIGN KEY (tenant_id, upload_session_id)
        REFERENCES app.upload_sessions(tenant_id, upload_session_id)
        ON DELETE RESTRICT,

    -- Candidate key enabling tenant-aware composite foreign keys (section 9).
    CONSTRAINT documents_tenant_id_unique
        UNIQUE (tenant_id, document_id),

    CONSTRAINT documents_size_non_negative
        CHECK (size_bytes IS NULL OR size_bytes >= 0)
);


-- -----------------------------------------------------------------------------
-- 4. Extend app.jobs with ownership, business identity, and legal states.
--
--    IMPORTANT: these ADD COLUMN ... NOT NULL statements have no DEFAULT, so they
--    succeed only on an EMPTY app.jobs. On a table with existing rows they raise
--    23502 not_null_violation. Safe evolution for populated tables is Day36.
-- -----------------------------------------------------------------------------
ALTER TABLE app.jobs
    ADD COLUMN tenant_id uuid NOT NULL,
    ADD COLUMN idempotency_key text NOT NULL;

ALTER TABLE app.jobs
    ADD CONSTRAINT jobs_tenant_fk
        FOREIGN KEY (tenant_id)
        REFERENCES app.tenants(tenant_id)
        ON DELETE RESTRICT;

-- Business key: one client request per tenant may create only ONE Job.
-- A retry produces a NEW job_id, so a job_id-based rule cannot prevent duplicate
-- business requests. Different tenants MAY reuse the same idempotency key.
ALTER TABLE app.jobs
    ADD CONSTRAINT jobs_tenant_idempotency_unique
        UNIQUE (tenant_id, idempotency_key);

-- Candidate key enabling tenant-aware composite foreign keys (section 9).
ALTER TABLE app.jobs
    ADD CONSTRAINT jobs_tenant_id_unique
        UNIQUE (tenant_id, job_id);

-- NOT NULL rejects NULL only; it still accepts '' and 'banana' (Day29/Day30).
-- CHECK restricts the value to the legal state set on EVERY write path.
ALTER TABLE app.jobs
    ADD CONSTRAINT jobs_status_allowed
        CHECK (job_status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled'));

ALTER TABLE app.jobs
    ADD CONSTRAINT jobs_attempt_count_non_negative
        CHECK (attempt_count >= 0);

-- Row-level cross-column invariant. A CHECK can only inspect THIS row, so it can
-- assert "succeeded implies a finish time" but CANNOT assert that a child
-- result_artifacts row exists. That coherence is a Day33 transactional concern.
ALTER TABLE app.jobs
    ADD CONSTRAINT jobs_succeeded_has_finished_at
        CHECK (job_status <> 'succeeded' OR finished_at IS NOT NULL);


-- -----------------------------------------------------------------------------
-- 5. Job Attempts — one Job may call the Provider several times.
--    job_id must NOT be the primary key: that would mean "at most one Attempt
--    per Job". Attempt needs its own identity plus a scoped business rule.
--
--    ON DELETE RESTRICT: Attempts carry Provider request IDs, errors and cost
--    evidence. CASCADE would silently erase incident/audit evidence with the
--    parent. CASCADE is reasonable only when a child has no independent
--    retention value; SET NULL only when an orphan is meaningful and the column
--    is nullable (job_id here is NOT NULL, so SET NULL is impossible).
-- -----------------------------------------------------------------------------
CREATE TABLE app.job_attempts (
    attempt_id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              uuid        NOT NULL
                                    REFERENCES app.jobs(job_id)
                                    ON DELETE RESTRICT,
    attempt_number      integer     NOT NULL,
    provider_request_id text,
    started_at          timestamptz NOT NULL DEFAULT now(),
    finished_at         timestamptz,
    error_code          text,
    cost_micros         bigint,

    -- Business uniqueness is SCOPED to the Job. A global UNIQUE(attempt_number)
    -- would wrongly stop Job B from having its own Attempt 1.
    CONSTRAINT job_attempts_job_number_unique
        UNIQUE (job_id, attempt_number),

    -- Candidate key so job_events can prove an Attempt belongs to the SAME Job.
    CONSTRAINT job_attempts_job_attempt_unique
        UNIQUE (job_id, attempt_id),

    CONSTRAINT job_attempts_number_positive
        CHECK (attempt_number > 0),

    CONSTRAINT job_attempts_cost_non_negative
        CHECK (cost_micros IS NULL OR cost_micros >= 0)
);


-- -----------------------------------------------------------------------------
-- 6. Job Events — append-oriented lifecycle history.
--      jobs.job_status = what is true NOW
--      job_events      = HOW the Job reached that state
--    Current status alone cannot reconstruct
--    queued -> running -> failed -> queued -> running -> succeeded.
--
--    The composite foreign key guarantees that a non-NULL attempt provenance
--    belongs to the SAME Job. With the default MATCH SIMPLE, a NULL attempt_id
--    makes the composite reference unenforced — which is exactly the desired
--    "optional provenance" behaviour.
-- -----------------------------------------------------------------------------
CREATE TABLE app.job_events (
    event_id    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id      uuid        NOT NULL
                            REFERENCES app.jobs(job_id)
                            ON DELETE RESTRICT,
    attempt_id  uuid,
    event_type  text        NOT NULL,
    from_status text,
    to_status   text,
    actor       text,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    metadata    jsonb       NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT job_events_attempt_same_job_fk
        FOREIGN KEY (job_id, attempt_id)
        REFERENCES app.job_attempts(job_id, attempt_id)
        ON DELETE RESTRICT
);


-- -----------------------------------------------------------------------------
-- 7. Outbox Events — durable publication INTENT.
--      job_events    = business history (what happened)
--      outbox_events = integration duty (what must be published)
--    PostgreSQL owns the durable Outbox row; Redis/Queue is transport, not the
--    authoritative record that a message must be sent. Day33 inserts the Job
--    change and the Outbox row atomically. A relay that crashes after publishing
--    but before setting published_at may publish twice, so consumers must stay
--    idempotent — that messaging design is a later lesson.
-- -----------------------------------------------------------------------------
CREATE TABLE app.outbox_events (
    outbox_event_id uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          uuid        NOT NULL
                                REFERENCES app.jobs(job_id)
                                ON DELETE RESTRICT,
    event_type      text        NOT NULL,
    payload         jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    published_at    timestamptz
);


-- -----------------------------------------------------------------------------
-- 8. Result Artifacts — one Attempt may produce several Object Storage objects
--    (summary JSON, embedding manifest, audit PDF). Repeating columns
--    (result_object_key_2, _3, ...) are an unbounded design.
--
--    Stores attempt_id ONLY. job_id is DERIVABLE through job_attempts; storing
--    both without a composite constraint would permit contradictory ownership
--    (artifact.job_id = A while the attempt belongs to Job B). Denormalize only
--    for a MEASURED access problem, and then constrain the duplicated fact.
-- -----------------------------------------------------------------------------
CREATE TABLE app.result_artifacts (
    artifact_id   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id    uuid        NOT NULL
                              REFERENCES app.job_attempts(attempt_id)
                              ON DELETE RESTRICT,
    artifact_type text        NOT NULL,
    object_key    text        NOT NULL,
    content_type  text,
    size_bytes    bigint,
    checksum      text,
    created_at    timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT result_artifacts_attempt_key_unique
        UNIQUE (attempt_id, object_key),

    CONSTRAINT result_artifacts_size_non_negative
        CHECK (size_bytes IS NULL OR size_bytes >= 0)
);


-- -----------------------------------------------------------------------------
-- 9. Job <-> Document many-to-many, with SAME-TENANT enforcement.
--    A comparison/RAG Job consumes many Documents; a Document is reused by many
--    Jobs. The junction table carries the relationship's own attributes.
--
--    Plain separate FKs would only prove that the Job and the Document EXIST.
--    The tenant-aware COMPOSITE foreign keys additionally prove they belong to
--    the SAME tenant, so PostgreSQL rejects a cross-tenant link.
--
--    This is relationship INTEGRITY during writes. It is NOT authorization:
--    reads must still be scoped with a trusted, server-derived tenant predicate.
-- -----------------------------------------------------------------------------
CREATE TABLE app.job_documents (
    tenant_id     uuid    NOT NULL,
    job_id        uuid    NOT NULL,
    document_id   uuid    NOT NULL,
    document_role text    NOT NULL DEFAULT 'input',
    input_order   integer,

    CONSTRAINT job_documents_pkey
        PRIMARY KEY (job_id, document_id),

    CONSTRAINT job_documents_job_same_tenant_fk
        FOREIGN KEY (tenant_id, job_id)
        REFERENCES app.jobs(tenant_id, job_id)
        ON DELETE RESTRICT,

    CONSTRAINT job_documents_document_same_tenant_fk
        FOREIGN KEY (tenant_id, document_id)
        REFERENCES app.documents(tenant_id, document_id)
        ON DELETE RESTRICT,

    CONSTRAINT job_documents_input_order_positive
        CHECK (input_order IS NULL OR input_order > 0)
);


-- =============================================================================
-- Relationship summary
--
--   tenants        1 -> N upload_sessions, documents, jobs
--   upload_sessions 1 -> 0..1 documents          (composite FK + UNIQUE = same-tenant one-to-one)
--   jobs           1 -> N job_attempts, job_events, outbox_events
--   job_attempts   1 -> N result_artifacts
--   jobs           N <-> N documents             (via job_documents)
--
--   PRIMARY KEY  = who this row is
--   FOREIGN KEY  = which parent it belongs to
--   BUSINESS KEY = which business operation must not repeat
--                  (tenant_id, idempotency_key)
--   UNIQUE       = the scope in which facts cannot duplicate
--                  (job_id, attempt_number)
--   CHECK        = which final row states are legal
--   RESTRICT     = deletion lifecycle policy protecting audit/cost evidence
-- =============================================================================
