BEGIN;

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
CREATE SCHEMA IF NOT EXISTS day104_l3;
SET search_path = day104_l3, public;

CREATE OR REPLACE FUNCTION text_array_is_canonical(
    items text[],
    allow_empty boolean DEFAULT false
) RETURNS boolean
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT items IS NOT NULL
       AND (allow_empty OR cardinality(items) > 0)
       AND NOT EXISTS (
           SELECT 1
           FROM unnest(items) AS item
           WHERE item IS NULL OR btrim(item) = ''
       )
       AND items = ARRAY(
           SELECT DISTINCT item
           FROM unnest(items) AS item
           ORDER BY item
       );
$$;

CREATE OR REPLACE FUNCTION reject_row_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME
        USING ERRCODE = '55000';
END;
$$;

CREATE TABLE IF NOT EXISTS source_snapshots (
    snapshot_id text PRIMARY KEY,
    scope_id text NOT NULL,
    source_version text NOT NULL,
    source_digest text NOT NULL,
    received_at timestamptz NOT NULL,
    CONSTRAINT source_snapshots_complete CHECK (
        btrim(snapshot_id) <> ''
        AND btrim(scope_id) <> ''
        AND btrim(source_version) <> ''
        AND btrim(source_digest) <> ''
    ),
    CONSTRAINT source_snapshots_scope_version_unique
        UNIQUE (scope_id, source_version),
    CONSTRAINT source_snapshots_scope_identity_unique
        UNIQUE (scope_id, snapshot_id),
    CONSTRAINT source_snapshots_version_binding_unique
        UNIQUE (scope_id, snapshot_id, source_version),
    CONSTRAINT source_snapshots_digest_binding_unique
        UNIQUE (scope_id, snapshot_id, source_digest),
    CONSTRAINT source_snapshots_bound_identity_unique
        UNIQUE (scope_id, snapshot_id, source_version, source_digest)
);

CREATE TABLE IF NOT EXISTS source_occurrences (
    scope_id text NOT NULL,
    snapshot_id text NOT NULL,
    occurrence_id text NOT NULL,
    logical_id text NOT NULL,
    source_version text NOT NULL,
    tenant_id text NOT NULL,
    content_digest text NOT NULL,
    metadata_digest text NOT NULL,
    provenance_digest text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (scope_id, occurrence_id),
    CONSTRAINT source_occurrences_snapshot_fk
        FOREIGN KEY (scope_id, snapshot_id, source_version)
        REFERENCES source_snapshots (scope_id, snapshot_id, source_version),
    CONSTRAINT source_occurrences_version_identity_unique
        UNIQUE (scope_id, logical_id, source_version),
    CONSTRAINT source_occurrences_bound_version_unique
        UNIQUE (scope_id, occurrence_id, source_version),
    CONSTRAINT source_occurrences_complete CHECK (
        btrim(scope_id) <> ''
        AND btrim(snapshot_id) <> ''
        AND btrim(occurrence_id) <> ''
        AND btrim(logical_id) <> ''
        AND btrim(source_version) <> ''
        AND btrim(tenant_id) <> ''
        AND btrim(content_digest) <> ''
        AND btrim(metadata_digest) <> ''
        AND btrim(provenance_digest) <> ''
    )
);

CREATE TABLE IF NOT EXISTS deletion_snapshots (
    snapshot_id text PRIMARY KEY,
    scope_id text NOT NULL,
    deletion_digest text NOT NULL,
    occurrence_ids text[] NOT NULL,
    ledger_revision bigint NOT NULL,
    received_at timestamptz NOT NULL,
    CONSTRAINT deletion_snapshots_scope_revision_unique
        UNIQUE (scope_id, ledger_revision),
    CONSTRAINT deletion_snapshots_scope_identity_unique
        UNIQUE (scope_id, snapshot_id),
    CONSTRAINT deletion_snapshots_bound_identity_unique
        UNIQUE (scope_id, snapshot_id, deletion_digest),
    CONSTRAINT deletion_snapshots_revision_nonnegative
        CHECK (ledger_revision >= 0),
    CONSTRAINT deletion_snapshots_occurrences_canonical
        CHECK (text_array_is_canonical(occurrence_ids, true)),
    CONSTRAINT deletion_snapshots_complete CHECK (
        btrim(snapshot_id) <> ''
        AND btrim(scope_id) <> ''
        AND btrim(deletion_digest) <> ''
    )
);

CREATE TABLE IF NOT EXISTS build_snapshots (
    build_snapshot_id text PRIMARY KEY,
    scope_id text NOT NULL,
    source_snapshot_id text NOT NULL,
    source_snapshot_digest text NOT NULL,
    authorization_snapshot_id text NOT NULL,
    authorization_snapshot_digest text NOT NULL,
    embedding_contract_id text NOT NULL,
    embedding_contract_digest text NOT NULL,
    index_schema_id text NOT NULL,
    index_schema_digest text NOT NULL,
    source_watermark text NOT NULL,
    deletion_snapshot_id text NOT NULL,
    deletion_snapshot_digest text NOT NULL,
    snapshot_fingerprint text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT build_snapshots_source_fk
        FOREIGN KEY (
            scope_id,
            source_snapshot_id,
            source_snapshot_digest
        ) REFERENCES source_snapshots (
            scope_id,
            snapshot_id,
            source_digest
        ),
    CONSTRAINT build_snapshots_deletion_fk
        FOREIGN KEY (
            scope_id,
            deletion_snapshot_id,
            deletion_snapshot_digest
        ) REFERENCES deletion_snapshots (
            scope_id,
            snapshot_id,
            deletion_digest
        ),
    CONSTRAINT build_snapshots_scope_identity_unique
        UNIQUE (scope_id, build_snapshot_id),
    CONSTRAINT build_snapshots_bound_identity_unique
        UNIQUE (scope_id, build_snapshot_id, snapshot_fingerprint),
    CONSTRAINT build_snapshots_complete CHECK (
        btrim(build_snapshot_id) <> ''
        AND btrim(scope_id) <> ''
        AND btrim(source_snapshot_digest) <> ''
        AND btrim(authorization_snapshot_id) <> ''
        AND btrim(authorization_snapshot_digest) <> ''
        AND btrim(embedding_contract_id) <> ''
        AND btrim(embedding_contract_digest) <> ''
        AND btrim(index_schema_id) <> ''
        AND btrim(index_schema_digest) <> ''
        AND btrim(source_watermark) <> ''
        AND btrim(deletion_snapshot_digest) <> ''
        AND btrim(snapshot_fingerprint) <> ''
    )
);

CREATE TABLE IF NOT EXISTS current_build_snapshots (
    scope_id text PRIMARY KEY,
    build_snapshot_id text NOT NULL,
    revision bigint NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT current_build_snapshots_build_fk
        FOREIGN KEY (scope_id, build_snapshot_id)
        REFERENCES build_snapshots (scope_id, build_snapshot_id),
    CONSTRAINT current_build_snapshots_revision_positive CHECK (revision > 0)
);

CREATE TABLE IF NOT EXISTS ingest_operations (
    operation_id text PRIMARY KEY,
    scope_id text NOT NULL,
    idempotency_key text NOT NULL,
    identity_digest text NOT NULL,
    result_digest text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ingest_operations_scope_key_unique
        UNIQUE (scope_id, idempotency_key),
    CONSTRAINT ingest_operations_complete CHECK (
        btrim(operation_id) <> ''
        AND btrim(scope_id) <> ''
        AND btrim(idempotency_key) <> ''
        AND btrim(identity_digest) <> ''
        AND (result_digest IS NULL OR btrim(result_digest) <> '')
    )
);

CREATE TABLE IF NOT EXISTS generations (
    generation_id text PRIMARY KEY,
    scope_id text NOT NULL,
    build_snapshot_id text NOT NULL,
    build_snapshot_fingerprint text NOT NULL,
    evaluation_ruler_fingerprint text NOT NULL,
    expected_manifest_digest text NOT NULL,
    actual_manifest_digest text,
    manifest_digest text,
    validation_record_digest text,
    evaluation_evidence_digest text,
    evaluation_report_digest text,
    physical_namespace text NOT NULL UNIQUE,
    provider_write_fence bigint NOT NULL,
    state text NOT NULL,
    state_version bigint NOT NULL,
    transition_fence bigint NOT NULL,
    active_readers bigint NOT NULL DEFAULT 0,
    checkpoint text,
    sealed_at timestamptz,
    retire_after timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT generations_build_snapshot_fk
        FOREIGN KEY (
            scope_id,
            build_snapshot_id,
            build_snapshot_fingerprint
        ) REFERENCES build_snapshots (
            scope_id,
            build_snapshot_id,
            snapshot_fingerprint
        ),
    CONSTRAINT generations_scope_identity_unique
        UNIQUE (scope_id, generation_id),
    CONSTRAINT generations_state_allowed CHECK (
        state IN (
            'BUILDING',
            'VALIDATING',
            'READY',
            'ACTIVE',
            'DRAINING',
            'RETIRED',
            'FAILED'
        )
    ),
    CONSTRAINT generations_versions_valid CHECK (
        provider_write_fence > 0
        AND state_version > 0
        AND transition_fence >= 0
        AND active_readers >= 0
    ),
    CONSTRAINT generations_nonserving_has_no_readers CHECK (
        state IN ('ACTIVE', 'DRAINING') OR active_readers = 0
    ),
    CONSTRAINT generations_retirement_deadline_valid CHECK (
        retire_after IS NULL OR state IN ('DRAINING', 'RETIRED')
    ),
    CONSTRAINT generations_complete CHECK (
        btrim(generation_id) <> ''
        AND btrim(scope_id) <> ''
        AND btrim(build_snapshot_id) <> ''
        AND btrim(build_snapshot_fingerprint) <> ''
        AND btrim(evaluation_ruler_fingerprint) <> ''
        AND btrim(expected_manifest_digest) <> ''
        AND btrim(physical_namespace) <> ''
    )
);

CREATE TABLE IF NOT EXISTS index_points (
    generation_id text NOT NULL
        REFERENCES generations (generation_id),
    point_id text NOT NULL,
    occurrence_id text NOT NULL,
    tenant_id text NOT NULL,
    content_digest text NOT NULL,
    metadata_digest text NOT NULL,
    provenance_digest text NOT NULL,
    vector_digest text NOT NULL,
    embedding vector(3) NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (generation_id, point_id),
    CONSTRAINT index_points_occurrence_unique
        UNIQUE (generation_id, occurrence_id),
    CONSTRAINT index_points_metadata_object CHECK (
        jsonb_typeof(metadata) = 'object'
    ),
    CONSTRAINT index_points_complete CHECK (
        btrim(point_id) <> ''
        AND btrim(occurrence_id) <> ''
        AND btrim(tenant_id) <> ''
        AND btrim(content_digest) <> ''
        AND btrim(metadata_digest) <> ''
        AND btrim(provenance_digest) <> ''
        AND btrim(vector_digest) <> ''
    )
);

CREATE INDEX IF NOT EXISTS index_points_generation_occurrence_idx
    ON index_points (generation_id, occurrence_id);

CREATE INDEX IF NOT EXISTS index_points_embedding_hnsw_cosine_idx
    ON index_points USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS active_pointers (
    pointer_name text PRIMARY KEY,
    scope_id text NOT NULL UNIQUE,
    generation_id text NOT NULL,
    revision bigint NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT active_pointers_generation_fk
        FOREIGN KEY (scope_id, generation_id)
        REFERENCES generations (scope_id, generation_id),
    CONSTRAINT active_pointers_revision_positive CHECK (revision > 0),
    CONSTRAINT active_pointers_name_nonempty CHECK (btrim(pointer_name) <> '')
);

CREATE TABLE IF NOT EXISTS activation_leases (
    pointer_name text PRIMARY KEY
        REFERENCES active_pointers (pointer_name),
    committer_id text NOT NULL,
    fencing_token bigint NOT NULL,
    issued_at timestamptz NOT NULL,
    lease_expires_at timestamptz NOT NULL,
    CONSTRAINT activation_leases_fence_positive CHECK (fencing_token > 0),
    CONSTRAINT activation_leases_window_valid CHECK (
        lease_expires_at > issued_at
    ),
    CONSTRAINT activation_leases_committer_nonempty CHECK (
        btrim(committer_id) <> ''
    )
);

CREATE TABLE IF NOT EXISTS activation_records (
    activation_id text PRIMARY KEY,
    pointer_name text NOT NULL
        REFERENCES active_pointers (pointer_name),
    from_generation_id text NOT NULL
        REFERENCES generations (generation_id),
    to_generation_id text NOT NULL
        REFERENCES generations (generation_id),
    from_revision bigint NOT NULL,
    to_revision bigint NOT NULL,
    committer_id text NOT NULL,
    committer_fence bigint NOT NULL,
    record_digest text NOT NULL UNIQUE,
    committed_at timestamptz NOT NULL,
    CONSTRAINT activation_records_from_unique
        UNIQUE (pointer_name, from_revision),
    CONSTRAINT activation_records_to_unique
        UNIQUE (pointer_name, to_revision),
    CONSTRAINT activation_records_revision_step CHECK (
        from_revision > 0 AND to_revision = from_revision + 1
    ),
    CONSTRAINT activation_records_generation_changes CHECK (
        from_generation_id <> to_generation_id
    ),
    CONSTRAINT activation_records_complete CHECK (
        btrim(activation_id) <> ''
        AND btrim(committer_id) <> ''
        AND committer_fence > 0
        AND btrim(record_digest) <> ''
    )
);

CREATE TABLE IF NOT EXISTS read_views (
    view_id text PRIMARY KEY,
    pointer_name text NOT NULL
        REFERENCES active_pointers (pointer_name),
    generation_id text NOT NULL
        REFERENCES generations (generation_id),
    pointer_revision bigint NOT NULL,
    owner_id text NOT NULL,
    build_snapshot_fingerprint text NOT NULL,
    authorization_snapshot_id text NOT NULL,
    status text NOT NULL DEFAULT 'OPEN',
    fencing_token bigint NOT NULL DEFAULT 1,
    lease_expires_at timestamptz NOT NULL,
    last_heartbeat_at timestamptz NOT NULL,
    acquired_at timestamptz NOT NULL,
    closed_at timestamptz,
    CONSTRAINT read_views_status_allowed CHECK (
        status IN ('OPEN', 'CLOSED', 'EXPIRED')
    ),
    CONSTRAINT read_views_fence_positive CHECK (fencing_token > 0),
    CONSTRAINT read_views_pointer_revision_positive CHECK (pointer_revision > 0),
    CONSTRAINT read_views_lease_window_valid CHECK (
        lease_expires_at > acquired_at
        AND last_heartbeat_at >= acquired_at
    ),
    CONSTRAINT read_views_terminal_time_valid CHECK (
        (status = 'OPEN' AND closed_at IS NULL)
        OR (status IN ('CLOSED', 'EXPIRED') AND closed_at IS NOT NULL)
    ),
    CONSTRAINT read_views_complete CHECK (
        btrim(view_id) <> ''
        AND btrim(owner_id) <> ''
        AND btrim(build_snapshot_fingerprint) <> ''
        AND btrim(authorization_snapshot_id) <> ''
    )
);

CREATE INDEX IF NOT EXISTS read_views_open_generation_idx
    ON read_views (generation_id, lease_expires_at)
    WHERE status = 'OPEN';

CREATE TABLE IF NOT EXISTS deletion_intents (
    deletion_id text PRIMARY KEY,
    operation_id text NOT NULL UNIQUE,
    scope_id text NOT NULL,
    idempotency_key text NOT NULL,
    occurrence_id text NOT NULL,
    source_version text NOT NULL,
    intent_digest text NOT NULL,
    verification_policy_id text NOT NULL,
    required_evidence_scopes text[] NOT NULL,
    state text NOT NULL DEFAULT 'ACCEPTED',
    accepted_at timestamptz NOT NULL,
    verified_deletion_snapshot_id text,
    verified_evidence_ids text[] NOT NULL DEFAULT '{}'::text[],
    verified_evidence_digest text,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT deletion_intents_source_fk
        FOREIGN KEY (scope_id, occurrence_id, source_version)
        REFERENCES source_occurrences (
            scope_id,
            occurrence_id,
            source_version
        ),
    CONSTRAINT deletion_intents_verified_snapshot_fk
        FOREIGN KEY (scope_id, verified_deletion_snapshot_id)
        REFERENCES deletion_snapshots (scope_id, snapshot_id),
    CONSTRAINT deletion_intents_scope_key_unique
        UNIQUE (scope_id, idempotency_key),
    CONSTRAINT deletion_intents_state_allowed CHECK (
        state IN ('ACCEPTED', 'DISPATCHED', 'VERIFIED')
    ),
    CONSTRAINT deletion_intents_scopes_allowed CHECK (
        text_array_is_canonical(required_evidence_scopes)
        AND required_evidence_scopes <@ ARRAY[
            'LOGICAL_RELEASE',
            'PHYSICAL_PURGE',
            'SERVING_INDEX_ABSENCE'
        ]::text[]
    ),
    CONSTRAINT deletion_intents_evidence_ids_canonical CHECK (
        text_array_is_canonical(verified_evidence_ids, true)
    ),
    CONSTRAINT deletion_intents_verification_binding CHECK (
        (
            state <> 'VERIFIED'
            AND verified_deletion_snapshot_id IS NULL
            AND cardinality(verified_evidence_ids) = 0
            AND verified_evidence_digest IS NULL
        )
        OR (
            state = 'VERIFIED'
            AND verified_deletion_snapshot_id IS NOT NULL
            AND cardinality(verified_evidence_ids) > 0
            AND verified_evidence_digest IS NOT NULL
            AND btrim(verified_evidence_digest) <> ''
        )
    ),
    CONSTRAINT deletion_intents_complete CHECK (
        btrim(deletion_id) <> ''
        AND btrim(operation_id) <> ''
        AND btrim(scope_id) <> ''
        AND btrim(idempotency_key) <> ''
        AND btrim(occurrence_id) <> ''
        AND btrim(source_version) <> ''
        AND btrim(intent_digest) <> ''
        AND btrim(verification_policy_id) <> ''
    )
);

CREATE TABLE IF NOT EXISTS tombstones (
    scope_id text NOT NULL,
    occurrence_id text NOT NULL,
    deletion_id text NOT NULL UNIQUE
        REFERENCES deletion_intents (deletion_id),
    ledger_revision bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (scope_id, occurrence_id),
    CONSTRAINT tombstones_source_fk
        FOREIGN KEY (scope_id, occurrence_id)
        REFERENCES source_occurrences (scope_id, occurrence_id),
    CONSTRAINT tombstones_revision_positive CHECK (ledger_revision > 0)
);

CREATE TABLE IF NOT EXISTS deletion_evidence (
    evidence_id text PRIMARY KEY,
    deletion_snapshot_id text NOT NULL
        REFERENCES deletion_snapshots (snapshot_id),
    verification_policy_id text NOT NULL,
    validator_id text NOT NULL,
    validator_version text NOT NULL,
    evidence_scope text NOT NULL,
    status text NOT NULL,
    pointer_name text NOT NULL,
    pointer_revision bigint NOT NULL,
    generation_ids text[] NOT NULL,
    tombstoned_occurrence_ids text[] NOT NULL,
    readback_digest text NOT NULL,
    observed_at timestamptz NOT NULL,
    CONSTRAINT deletion_evidence_identity_unique UNIQUE (
        deletion_snapshot_id,
        verification_policy_id,
        validator_id,
        validator_version,
        evidence_scope
    ),
    CONSTRAINT deletion_evidence_scope_allowed CHECK (
        evidence_scope IN (
            'LOGICAL_RELEASE',
            'SERVING_INDEX_ABSENCE',
            'PHYSICAL_PURGE'
        )
    ),
    CONSTRAINT deletion_evidence_status_allowed CHECK (
        status IN ('PASS', 'FAIL', 'NOT_RUN')
    ),
    CONSTRAINT deletion_evidence_generations_canonical CHECK (
        text_array_is_canonical(generation_ids, true)
    ),
    CONSTRAINT deletion_evidence_tombstones_canonical CHECK (
        text_array_is_canonical(tombstoned_occurrence_ids)
    ),
    CONSTRAINT deletion_evidence_pointer_revision_positive CHECK (
        pointer_revision > 0
    ),
    CONSTRAINT deletion_evidence_complete CHECK (
        btrim(evidence_id) <> ''
        AND btrim(verification_policy_id) <> ''
        AND btrim(validator_id) <> ''
        AND btrim(validator_version) <> ''
        AND btrim(pointer_name) <> ''
        AND btrim(readback_digest) <> ''
    )
);

CREATE TABLE IF NOT EXISTS outbox_events (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    aggregate_id text NOT NULL,
    aggregate_revision bigint NOT NULL,
    payload_digest text NOT NULL,
    state text NOT NULL DEFAULT 'PENDING',
    claim_owner text,
    claim_fence bigint,
    claimed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    published_at timestamptz,
    CONSTRAINT outbox_events_identity_unique
        UNIQUE (event_type, aggregate_id, aggregate_revision),
    CONSTRAINT outbox_events_state_allowed CHECK (
        state IN ('PENDING', 'PROCESSING', 'DISPATCHED', 'FAILED')
    ),
    CONSTRAINT outbox_events_revision_nonnegative
        CHECK (aggregate_revision >= 0),
    CONSTRAINT outbox_events_claim_complete CHECK (
        (
            claim_owner IS NULL
            AND claim_fence IS NULL
            AND claimed_at IS NULL
        )
        OR (
            btrim(claim_owner) <> ''
            AND claim_fence IS NOT NULL
            AND claim_fence > 0
            AND claimed_at IS NOT NULL
        )
    ),
    CONSTRAINT outbox_events_publish_state_valid CHECK (
        (state = 'DISPATCHED' AND published_at IS NOT NULL)
        OR (state <> 'DISPATCHED' AND published_at IS NULL)
    ),
    CONSTRAINT outbox_events_complete CHECK (
        btrim(event_id) <> ''
        AND btrim(event_type) <> ''
        AND btrim(aggregate_id) <> ''
        AND btrim(payload_digest) <> ''
    )
);

CREATE INDEX IF NOT EXISTS outbox_events_pending_idx
    ON outbox_events (created_at, event_id)
    WHERE state IN ('PENDING', 'FAILED');

CREATE TABLE IF NOT EXISTS inbox_records (
    event_id text PRIMARY KEY,
    payload_digest text NOT NULL,
    source_stream text NOT NULL,
    state text NOT NULL DEFAULT 'APPLIED',
    result_id text NOT NULL,
    result_digest text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT inbox_records_state_applied CHECK (state = 'APPLIED'),
    CONSTRAINT inbox_records_complete CHECK (
        btrim(event_id) <> ''
        AND btrim(payload_digest) <> ''
        AND btrim(source_stream) <> ''
        AND btrim(result_id) <> ''
        AND btrim(result_digest) <> ''
    )
);

CREATE TABLE IF NOT EXISTS lifecycle_transitions (
    transition_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generation_id text NOT NULL
        REFERENCES generations (generation_id),
    from_state text NOT NULL,
    to_state text NOT NULL,
    from_state_version bigint NOT NULL,
    to_state_version bigint NOT NULL,
    transition_fence bigint NOT NULL,
    reason text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT lifecycle_transitions_version_step CHECK (
        to_state_version = from_state_version + 1
    ),
    CONSTRAINT lifecycle_transitions_state_changes CHECK (
        from_state <> to_state
    ),
    CONSTRAINT lifecycle_transitions_reason_nonempty CHECK (btrim(reason) <> '')
);

CREATE OR REPLACE FUNCTION enforce_current_snapshot_revision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.scope_id IS DISTINCT FROM OLD.scope_id THEN
        RAISE EXCEPTION 'current BuildSnapshot scope identity is immutable'
            USING ERRCODE = '55000';
    END IF;
    IF NEW.revision <> OLD.revision + 1 THEN
        RAISE EXCEPTION 'current BuildSnapshot revision must advance by one'
            USING ERRCODE = '40001';
    END IF;
    IF NEW.build_snapshot_id = OLD.build_snapshot_id THEN
        RAISE EXCEPTION 'current BuildSnapshot update requires a new identity'
            USING ERRCODE = '23514';
    END IF;
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_ingest_operation_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF ROW(
        NEW.operation_id,
        NEW.scope_id,
        NEW.idempotency_key,
        NEW.identity_digest,
        NEW.created_at
    ) IS DISTINCT FROM ROW(
        OLD.operation_id,
        OLD.scope_id,
        OLD.idempotency_key,
        OLD.identity_digest,
        OLD.created_at
    ) THEN
        RAISE EXCEPTION 'ingest operation identity is immutable'
            USING ERRCODE = '55000';
    END IF;
    IF OLD.result_digest IS NOT NULL
       AND NEW.result_digest IS DISTINCT FROM OLD.result_digest THEN
        RAISE EXCEPTION 'ingest operation result binding is set-once'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_generation_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    transition_is_allowed boolean;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.state NOT IN ('BUILDING', 'VALIDATING') THEN
            RAISE EXCEPTION 'new Generation must start BUILDING or VALIDATING'
                USING ERRCODE = '23514';
        END IF;
    ELSE
        IF ROW(
            NEW.generation_id,
            NEW.scope_id,
            NEW.build_snapshot_id,
            NEW.build_snapshot_fingerprint,
            NEW.evaluation_ruler_fingerprint,
            NEW.expected_manifest_digest,
            NEW.physical_namespace,
            NEW.provider_write_fence,
            NEW.created_at
        ) IS DISTINCT FROM ROW(
            OLD.generation_id,
            OLD.scope_id,
            OLD.build_snapshot_id,
            OLD.build_snapshot_fingerprint,
            OLD.evaluation_ruler_fingerprint,
            OLD.expected_manifest_digest,
            OLD.physical_namespace,
            OLD.provider_write_fence,
            OLD.created_at
        ) THEN
            RAISE EXCEPTION 'Generation build identity is immutable'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.state_version <> OLD.state_version + 1 THEN
            RAISE EXCEPTION 'Generation state_version must advance by one'
                USING ERRCODE = '40001';
        END IF;
        IF NEW.transition_fence < OLD.transition_fence THEN
            RAISE EXCEPTION 'Generation transition fence cannot decrease'
                USING ERRCODE = '40001';
        END IF;
        IF OLD.sealed_at IS NOT NULL AND ROW(
            NEW.actual_manifest_digest,
            NEW.manifest_digest,
            NEW.checkpoint,
            NEW.sealed_at
        ) IS DISTINCT FROM ROW(
            OLD.actual_manifest_digest,
            OLD.manifest_digest,
            OLD.checkpoint,
            OLD.sealed_at
        ) THEN
            RAISE EXCEPTION 'sealed Generation artifact binding is immutable'
                USING ERRCODE = '55000';
        END IF;
        IF (OLD.validation_record_digest IS NOT NULL
            AND NEW.validation_record_digest IS DISTINCT FROM
                OLD.validation_record_digest)
           OR (OLD.evaluation_evidence_digest IS NOT NULL
               AND NEW.evaluation_evidence_digest IS DISTINCT FROM
                   OLD.evaluation_evidence_digest)
           OR (OLD.evaluation_report_digest IS NOT NULL
               AND NEW.evaluation_report_digest IS DISTINCT FROM
                   OLD.evaluation_report_digest) THEN
            RAISE EXCEPTION 'Generation release evidence binding is set-once'
                USING ERRCODE = '55000';
        END IF;

        transition_is_allowed := NEW.state = OLD.state OR (
            (OLD.state = 'BUILDING' AND NEW.state IN ('VALIDATING', 'FAILED'))
            OR (OLD.state = 'VALIDATING' AND NEW.state IN ('READY', 'FAILED'))
            OR (OLD.state = 'READY' AND NEW.state = 'ACTIVE')
            OR (OLD.state = 'ACTIVE' AND NEW.state = 'DRAINING')
            OR (OLD.state = 'DRAINING' AND NEW.state = 'RETIRED')
            OR (OLD.state = 'FAILED' AND NEW.state = 'BUILDING')
        );
        IF NOT transition_is_allowed THEN
            RAISE EXCEPTION 'illegal Generation transition % -> %',
                OLD.state,
                NEW.state
                USING ERRCODE = '23514';
        END IF;
    END IF;

    IF NEW.state IN ('READY', 'ACTIVE', 'DRAINING', 'RETIRED') THEN
        IF NEW.sealed_at IS NULL
           OR NEW.checkpoint IS NULL
           OR btrim(NEW.checkpoint) = ''
           OR NEW.actual_manifest_digest IS NULL
           OR NEW.actual_manifest_digest <> NEW.expected_manifest_digest
           OR NEW.manifest_digest IS NULL
           OR NEW.validation_record_digest IS NULL
           OR NEW.evaluation_evidence_digest IS NULL
           OR NEW.evaluation_report_digest IS NULL THEN
            RAISE EXCEPTION 'serving-eligible Generation requires matching sealed evidence'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION reject_sealed_index_point_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_generation_id text;
    original_generation_id text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        target_generation_id := OLD.generation_id;
    ELSE
        target_generation_id := NEW.generation_id;
    END IF;
    IF TG_OP = 'UPDATE' THEN
        original_generation_id := OLD.generation_id;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM day104_l3.generations
        WHERE generation_id IN (
            target_generation_id,
            COALESCE(original_generation_id, target_generation_id)
        )
          AND (
              sealed_at IS NOT NULL
              OR state IN ('READY', 'ACTIVE', 'DRAINING', 'RETIRED')
          )
    ) THEN
        RAISE EXCEPTION 'sealed Generation index points are immutable'
            USING ERRCODE = '55000';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_active_pointer_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.pointer_name IS DISTINCT FROM OLD.pointer_name
           OR NEW.scope_id IS DISTINCT FROM OLD.scope_id THEN
            RAISE EXCEPTION 'active pointer identity is immutable'
                USING ERRCODE = '55000';
        END IF;
        IF NEW.revision <> OLD.revision + 1 THEN
            RAISE EXCEPTION 'active pointer revision must advance by one'
                USING ERRCODE = '40001';
        END IF;
        IF NEW.generation_id = OLD.generation_id THEN
            RAISE EXCEPTION 'active pointer update requires a new Generation identity'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM day104_l3.generations
        WHERE generation_id = NEW.generation_id
          AND scope_id = NEW.scope_id
          AND state = 'ACTIVE'
    ) THEN
        RAISE EXCEPTION 'active pointer must reference an ACTIVE Generation in the same scope'
            USING ERRCODE = '23514';
    END IF;
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_activation_lease_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.pointer_name IS DISTINCT FROM OLD.pointer_name THEN
        RAISE EXCEPTION 'activation lease pointer identity is immutable'
            USING ERRCODE = '55000';
    END IF;
    IF NEW.fencing_token <> OLD.fencing_token + 1 THEN
        RAISE EXCEPTION 'activation fencing token must advance by one'
            USING ERRCODE = '40001';
    END IF;
    IF NEW.issued_at <= OLD.issued_at THEN
        RAISE EXCEPTION 'activation lease issued_at must advance'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_read_view_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF ROW(
        NEW.view_id,
        NEW.pointer_name,
        NEW.generation_id,
        NEW.pointer_revision,
        NEW.owner_id,
        NEW.build_snapshot_fingerprint,
        NEW.authorization_snapshot_id,
        NEW.acquired_at
    ) IS DISTINCT FROM ROW(
        OLD.view_id,
        OLD.pointer_name,
        OLD.generation_id,
        OLD.pointer_revision,
        OLD.owner_id,
        OLD.build_snapshot_fingerprint,
        OLD.authorization_snapshot_id,
        OLD.acquired_at
    ) THEN
        RAISE EXCEPTION 'ReadView identity is immutable'
            USING ERRCODE = '55000';
    END IF;
    IF OLD.status <> 'OPEN' THEN
        RAISE EXCEPTION 'terminal ReadView is immutable'
            USING ERRCODE = '55000';
    END IF;
    IF NEW.status = 'OPEN' THEN
        IF NEW.fencing_token <> OLD.fencing_token
           OR NEW.lease_expires_at <= OLD.lease_expires_at
           OR NEW.last_heartbeat_at <= OLD.last_heartbeat_at THEN
            RAISE EXCEPTION 'ReadView heartbeat must extend the existing lease'
                USING ERRCODE = '23514';
        END IF;
    ELSIF NEW.status IN ('CLOSED', 'EXPIRED') THEN
        IF NEW.fencing_token <> OLD.fencing_token + 1
           OR NEW.closed_at IS NULL THEN
            RAISE EXCEPTION 'terminal ReadView transition requires the next fence and close time'
                USING ERRCODE = '23514';
        END IF;
    ELSE
        RAISE EXCEPTION 'illegal ReadView transition'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_deletion_intent_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF ROW(
        NEW.deletion_id,
        NEW.operation_id,
        NEW.scope_id,
        NEW.idempotency_key,
        NEW.occurrence_id,
        NEW.source_version,
        NEW.intent_digest,
        NEW.verification_policy_id,
        NEW.required_evidence_scopes,
        NEW.accepted_at
    ) IS DISTINCT FROM ROW(
        OLD.deletion_id,
        OLD.operation_id,
        OLD.scope_id,
        OLD.idempotency_key,
        OLD.occurrence_id,
        OLD.source_version,
        OLD.intent_digest,
        OLD.verification_policy_id,
        OLD.required_evidence_scopes,
        OLD.accepted_at
    ) THEN
        RAISE EXCEPTION 'deletion Intent identity is immutable'
            USING ERRCODE = '55000';
    END IF;
    IF NOT (
        NEW.state = OLD.state
        OR (OLD.state = 'ACCEPTED' AND NEW.state = 'DISPATCHED')
        OR (OLD.state = 'DISPATCHED' AND NEW.state = 'VERIFIED')
    ) THEN
        RAISE EXCEPTION 'illegal deletion Intent transition % -> %',
            OLD.state,
            NEW.state
            USING ERRCODE = '23514';
    END IF;
    IF OLD.state = 'VERIFIED' AND ROW(
        NEW.verified_deletion_snapshot_id,
        NEW.verified_evidence_ids,
        NEW.verified_evidence_digest
    ) IS DISTINCT FROM ROW(
        OLD.verified_deletion_snapshot_id,
        OLD.verified_evidence_ids,
        OLD.verified_evidence_digest
    ) THEN
        RAISE EXCEPTION 'verified deletion evidence binding is immutable'
            USING ERRCODE = '55000';
    END IF;
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_outbox_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    transition_is_allowed boolean;
BEGIN
    IF ROW(
        NEW.event_id,
        NEW.event_type,
        NEW.aggregate_id,
        NEW.aggregate_revision,
        NEW.payload_digest,
        NEW.created_at
    ) IS DISTINCT FROM ROW(
        OLD.event_id,
        OLD.event_type,
        OLD.aggregate_id,
        OLD.aggregate_revision,
        OLD.payload_digest,
        OLD.created_at
    ) THEN
        RAISE EXCEPTION 'Outbox event identity is immutable'
            USING ERRCODE = '55000';
    END IF;
    transition_is_allowed := NEW.state = OLD.state OR (
        (OLD.state = 'PENDING' AND NEW.state IN ('PROCESSING', 'DISPATCHED', 'FAILED'))
        OR (OLD.state = 'PROCESSING' AND NEW.state IN ('PENDING', 'DISPATCHED', 'FAILED'))
        OR (OLD.state = 'FAILED' AND NEW.state IN ('PENDING', 'PROCESSING'))
    );
    IF NOT transition_is_allowed THEN
        RAISE EXCEPTION 'illegal Outbox transition % -> %', OLD.state, NEW.state
            USING ERRCODE = '23514';
    END IF;
    IF OLD.claim_fence IS NOT NULL
       AND NEW.claim_fence IS NOT NULL
       AND NEW.claim_fence < OLD.claim_fence THEN
        RAISE EXCEPTION 'Outbox claim fence cannot decrease'
            USING ERRCODE = '40001';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION record_generation_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    transition_reason text;
BEGIN
    IF NEW.state = OLD.state THEN
        RETURN NEW;
    END IF;
    transition_reason := NULLIF(
        current_setting('day104_l3.transition_reason', true),
        ''
    );
    INSERT INTO day104_l3.lifecycle_transitions (
        generation_id,
        from_state,
        to_state,
        from_state_version,
        to_state_version,
        transition_fence,
        reason,
        recorded_at
    ) VALUES (
        NEW.generation_id,
        OLD.state,
        NEW.state,
        OLD.state_version,
        NEW.state_version,
        NEW.transition_fence,
        COALESCE(transition_reason, 'database_enforced_transition'),
        NEW.updated_at
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS source_snapshots_append_only ON source_snapshots;
CREATE TRIGGER source_snapshots_append_only
    BEFORE UPDATE OR DELETE ON source_snapshots
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS source_occurrences_append_only ON source_occurrences;
CREATE TRIGGER source_occurrences_append_only
    BEFORE UPDATE OR DELETE ON source_occurrences
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS deletion_snapshots_append_only ON deletion_snapshots;
CREATE TRIGGER deletion_snapshots_append_only
    BEFORE UPDATE OR DELETE ON deletion_snapshots
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS build_snapshots_append_only ON build_snapshots;
CREATE TRIGGER build_snapshots_append_only
    BEFORE UPDATE OR DELETE ON build_snapshots
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS current_build_snapshots_revisioned
    ON current_build_snapshots;
CREATE TRIGGER current_build_snapshots_revisioned
    BEFORE UPDATE ON current_build_snapshots
    FOR EACH ROW EXECUTE FUNCTION enforce_current_snapshot_revision();

DROP TRIGGER IF EXISTS current_build_snapshots_no_delete
    ON current_build_snapshots;
CREATE TRIGGER current_build_snapshots_no_delete
    BEFORE DELETE ON current_build_snapshots
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS ingest_operations_set_once ON ingest_operations;
CREATE TRIGGER ingest_operations_set_once
    BEFORE UPDATE ON ingest_operations
    FOR EACH ROW EXECUTE FUNCTION enforce_ingest_operation_mutation();

DROP TRIGGER IF EXISTS ingest_operations_no_delete ON ingest_operations;
CREATE TRIGGER ingest_operations_no_delete
    BEFORE DELETE ON ingest_operations
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS generations_enforce_mutation ON generations;
CREATE TRIGGER generations_enforce_mutation
    BEFORE INSERT OR UPDATE ON generations
    FOR EACH ROW EXECUTE FUNCTION enforce_generation_mutation();

DROP TRIGGER IF EXISTS generations_no_delete ON generations;
CREATE TRIGGER generations_no_delete
    BEFORE DELETE ON generations
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS generations_record_transition ON generations;
CREATE TRIGGER generations_record_transition
    AFTER UPDATE ON generations
    FOR EACH ROW EXECUTE FUNCTION record_generation_transition();

DROP TRIGGER IF EXISTS index_points_guard_sealed ON index_points;
CREATE TRIGGER index_points_guard_sealed
    BEFORE INSERT OR UPDATE OR DELETE ON index_points
    FOR EACH ROW EXECUTE FUNCTION reject_sealed_index_point_mutation();

DROP TRIGGER IF EXISTS active_pointers_enforce_mutation ON active_pointers;
CREATE TRIGGER active_pointers_enforce_mutation
    BEFORE INSERT OR UPDATE ON active_pointers
    FOR EACH ROW EXECUTE FUNCTION enforce_active_pointer_mutation();

DROP TRIGGER IF EXISTS active_pointers_no_delete ON active_pointers;
CREATE TRIGGER active_pointers_no_delete
    BEFORE DELETE ON active_pointers
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS activation_leases_enforce_rotation ON activation_leases;
CREATE TRIGGER activation_leases_enforce_rotation
    BEFORE UPDATE ON activation_leases
    FOR EACH ROW EXECUTE FUNCTION enforce_activation_lease_mutation();

DROP TRIGGER IF EXISTS activation_leases_no_delete ON activation_leases;
CREATE TRIGGER activation_leases_no_delete
    BEFORE DELETE ON activation_leases
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS activation_records_append_only ON activation_records;
CREATE TRIGGER activation_records_append_only
    BEFORE UPDATE OR DELETE ON activation_records
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS read_views_enforce_mutation ON read_views;
CREATE TRIGGER read_views_enforce_mutation
    BEFORE UPDATE ON read_views
    FOR EACH ROW EXECUTE FUNCTION enforce_read_view_mutation();

DROP TRIGGER IF EXISTS read_views_no_delete ON read_views;
CREATE TRIGGER read_views_no_delete
    BEFORE DELETE ON read_views
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS deletion_intents_enforce_mutation ON deletion_intents;
CREATE TRIGGER deletion_intents_enforce_mutation
    BEFORE UPDATE ON deletion_intents
    FOR EACH ROW EXECUTE FUNCTION enforce_deletion_intent_mutation();

DROP TRIGGER IF EXISTS deletion_intents_no_delete ON deletion_intents;
CREATE TRIGGER deletion_intents_no_delete
    BEFORE DELETE ON deletion_intents
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS tombstones_append_only ON tombstones;
CREATE TRIGGER tombstones_append_only
    BEFORE UPDATE OR DELETE ON tombstones
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS deletion_evidence_append_only ON deletion_evidence;
CREATE TRIGGER deletion_evidence_append_only
    BEFORE UPDATE OR DELETE ON deletion_evidence
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS outbox_events_enforce_mutation ON outbox_events;
CREATE TRIGGER outbox_events_enforce_mutation
    BEFORE UPDATE ON outbox_events
    FOR EACH ROW EXECUTE FUNCTION enforce_outbox_mutation();

DROP TRIGGER IF EXISTS outbox_events_no_delete ON outbox_events;
CREATE TRIGGER outbox_events_no_delete
    BEFORE DELETE ON outbox_events
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS inbox_records_append_only ON inbox_records;
CREATE TRIGGER inbox_records_append_only
    BEFORE UPDATE OR DELETE ON inbox_records
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS lifecycle_transitions_append_only
    ON lifecycle_transitions;
CREATE TRIGGER lifecycle_transitions_append_only
    BEFORE UPDATE OR DELETE ON lifecycle_transitions
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

COMMIT;
