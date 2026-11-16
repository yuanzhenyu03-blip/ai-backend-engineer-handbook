BEGIN;

CREATE SCHEMA IF NOT EXISTS day105_l3;
SET search_path = day105_l3, public;

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

CREATE OR REPLACE FUNCTION jsonb_is_content_safe(payload_value jsonb)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
STRICT
AS $$
DECLARE
    item_key text;
    item_value jsonb;
BEGIN
    CASE jsonb_typeof(payload_value)
        WHEN 'object' THEN
            FOR item_key, item_value IN
                SELECT key, value FROM jsonb_each(payload_value)
            LOOP
                IF lower(replace(item_key, '-', '_')) = ANY (ARRAY[
                    'password',
                    'database_url',
                    'dsn',
                    'secret',
                    'raw_secret',
                    'token',
                    'access_token',
                    'api_key',
                    'raw_content',
                    'protected_content',
                    'protected_chunk',
                    'raw_prompt',
                    'prompt',
                    'system_prompt',
                    'answer_text',
                    'candidate_text',
                    'attack_payload',
                    'cross_tenant_content',
                    'raw_vector',
                    'vector',
                    'embedding',
                    'destination',
                    'egress_url'
                ]) THEN
                    RETURN false;
                END IF;
                IF NOT day105_l3.jsonb_is_content_safe(item_value) THEN
                    RETURN false;
                END IF;
            END LOOP;
        WHEN 'array' THEN
            FOR item_value IN SELECT value FROM jsonb_array_elements(payload_value)
            LOOP
                IF NOT day105_l3.jsonb_is_content_safe(item_value) THEN
                    RETURN false;
                END IF;
            END LOOP;
        WHEN 'string' THEN
            IF length(payload_value #>> '{}') > 1024
               OR (payload_value #>> '{}') ~* 'postgres(ql)?://'
               OR (payload_value #>> '{}') ~* '-----BEGIN [A-Z ]+PRIVATE KEY-----'
               OR (payload_value #>> '{}') ~* '(^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{12,}'
            THEN
                RETURN false;
            END IF;
        ELSE
            NULL;
    END CASE;
    RETURN true;
END;
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

CREATE TABLE IF NOT EXISTS security_snapshots (
    snapshot_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    revision bigint NOT NULL,
    authorization_snapshot_id text NOT NULL,
    authorization_snapshot_digest text NOT NULL,
    provenance_revision text NOT NULL,
    provenance_digest text NOT NULL,
    tombstone_revision text NOT NULL,
    tombstone_digest text NOT NULL,
    content_security_policy_version text NOT NULL,
    content_security_digest text NOT NULL,
    security_policy_version text NOT NULL,
    security_policy_digest text NOT NULL,
    occurrence_ids text[] NOT NULL,
    identity_digest text NOT NULL UNIQUE,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT security_snapshots_tenant_revision_unique
        UNIQUE (tenant_id, revision),
    CONSTRAINT security_snapshots_bound_identity_unique
        UNIQUE (tenant_id, snapshot_id, revision),
    CONSTRAINT security_snapshots_revision_positive CHECK (revision > 0),
    CONSTRAINT security_snapshots_occurrences_canonical
        CHECK (text_array_is_canonical(occurrence_ids, true)),
    CONSTRAINT security_snapshots_payload_safe CHECK (
        jsonb_typeof(payload) = 'object'
        AND jsonb_is_content_safe(payload)
    ),
    CONSTRAINT security_snapshots_complete CHECK (
        btrim(snapshot_id) <> ''
        AND btrim(tenant_id) <> ''
        AND btrim(authorization_snapshot_id) <> ''
        AND btrim(authorization_snapshot_digest) <> ''
        AND btrim(provenance_revision) <> ''
        AND btrim(provenance_digest) <> ''
        AND btrim(tombstone_revision) <> ''
        AND btrim(tombstone_digest) <> ''
        AND btrim(content_security_policy_version) <> ''
        AND btrim(content_security_digest) <> ''
        AND btrim(security_policy_version) <> ''
        AND btrim(security_policy_digest) <> ''
        AND btrim(identity_digest) <> ''
    )
);

CREATE TABLE IF NOT EXISTS current_security_snapshots (
    tenant_id text PRIMARY KEY,
    snapshot_id text NOT NULL,
    revision bigint NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT current_security_snapshots_snapshot_fk
        FOREIGN KEY (tenant_id, snapshot_id, revision)
        REFERENCES security_snapshots (tenant_id, snapshot_id, revision),
    CONSTRAINT current_security_snapshots_revision_positive CHECK (revision > 0),
    CONSTRAINT current_security_snapshots_complete CHECK (
        btrim(tenant_id) <> '' AND btrim(snapshot_id) <> ''
    )
);

CREATE OR REPLACE FUNCTION validate_current_security_snapshot_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'current_security_snapshots cannot be deleted'
            USING ERRCODE = '55000';
    END IF;
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
        RAISE EXCEPTION 'current security snapshot tenant identity is immutable'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.revision <> OLD.revision + 1 THEN
        RAISE EXCEPTION 'current security snapshot revision must advance by one'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.snapshot_id = OLD.snapshot_id THEN
        RAISE EXCEPTION 'current security snapshot must advance to a new snapshot'
            USING ERRCODE = '23514';
    END IF;
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS security_artifacts (
    artifact_id text PRIMARY KEY,
    artifact_type text NOT NULL,
    request_id text,
    identity_digest text NOT NULL UNIQUE,
    parent_digests text[] NOT NULL DEFAULT ARRAY[]::text[],
    result text NOT NULL,
    disposition text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT security_artifacts_result_allowed CHECK (
        result IN ('PASS', 'FAIL', 'INCONCLUSIVE', 'NOT_RUN')
    ),
    CONSTRAINT security_artifacts_parents_canonical CHECK (
        text_array_is_canonical(parent_digests, true)
    ),
    CONSTRAINT security_artifacts_payload_safe CHECK (
        jsonb_typeof(payload) = 'object'
        AND jsonb_is_content_safe(payload)
    ),
    CONSTRAINT security_artifacts_complete CHECK (
        btrim(artifact_id) <> ''
        AND btrim(artifact_type) <> ''
        AND (request_id IS NULL OR btrim(request_id) <> '')
        AND btrim(identity_digest) <> ''
        AND btrim(disposition) <> ''
    )
);

CREATE TABLE IF NOT EXISTS response_intents (
    intent_id text PRIMARY KEY,
    request_id text NOT NULL,
    release_decision_id text NOT NULL UNIQUE
        REFERENCES security_artifacts (artifact_id),
    release_decision_digest text NOT NULL,
    candidate_digest text NOT NULL,
    destination_digest text NOT NULL,
    action text NOT NULL,
    identity_digest text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT response_intents_action_allowed CHECK (
        action IN ('RELEASE', 'BLOCKED', 'ABSTAIN')
    ),
    CONSTRAINT response_intents_complete CHECK (
        btrim(intent_id) <> ''
        AND btrim(request_id) <> ''
        AND btrim(release_decision_id) <> ''
        AND btrim(release_decision_digest) <> ''
        AND btrim(candidate_digest) <> ''
        AND btrim(destination_digest) <> ''
        AND btrim(identity_digest) <> ''
    )
);

CREATE OR REPLACE FUNCTION validate_response_intent()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    decision day105_l3.security_artifacts%ROWTYPE;
BEGIN
    SELECT * INTO decision
    FROM day105_l3.security_artifacts
    WHERE artifact_id = NEW.release_decision_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'release decision artifact does not exist'
            USING ERRCODE = '23503';
    END IF;
    IF decision.artifact_type <> 'OUTPUT_RELEASE_DECISION' THEN
        RAISE EXCEPTION 'response intent must reference an output release decision'
            USING ERRCODE = '23514';
    END IF;
    IF decision.request_id IS DISTINCT FROM NEW.request_id THEN
        RAISE EXCEPTION 'response intent request identity mismatch'
            USING ERRCODE = '23514';
    END IF;
    IF decision.identity_digest IS DISTINCT FROM NEW.release_decision_digest THEN
        RAISE EXCEPTION 'response intent release decision digest mismatch'
            USING ERRCODE = '23514';
    END IF;
    IF decision.disposition IS DISTINCT FROM NEW.action THEN
        RAISE EXCEPTION 'response intent action must match release disposition'
            USING ERRCODE = '23514';
    END IF;
    IF decision.payload ->> 'candidate_digest'
       IS DISTINCT FROM NEW.candidate_digest THEN
        RAISE EXCEPTION 'response intent candidate digest mismatch'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.action = 'RELEASE'
       AND (decision.result <> 'PASS' OR decision.disposition <> 'RELEASE') THEN
        RAISE EXCEPTION 'non-PASS release decision cannot create RELEASE intent'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS incident_records (
    record_id text PRIMARY KEY,
    incident_id text NOT NULL,
    previous_record_id text UNIQUE,
    identity_digest text NOT NULL UNIQUE,
    state text NOT NULL,
    scope_digest text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT incident_records_previous_fk
        FOREIGN KEY (previous_record_id) REFERENCES incident_records (record_id),
    CONSTRAINT incident_records_payload_safe CHECK (
        jsonb_typeof(payload) = 'object'
        AND jsonb_is_content_safe(payload)
    ),
    CONSTRAINT incident_records_complete CHECK (
        btrim(record_id) <> ''
        AND btrim(incident_id) <> ''
        AND (previous_record_id IS NULL OR btrim(previous_record_id) <> '')
        AND btrim(identity_digest) <> ''
        AND btrim(state) <> ''
        AND btrim(scope_digest) <> ''
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS incident_records_one_root_idx
    ON incident_records (incident_id)
    WHERE previous_record_id IS NULL;

CREATE OR REPLACE FUNCTION validate_incident_chain()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    previous_incident_id text;
BEGIN
    IF NEW.previous_record_id IS NULL THEN
        IF EXISTS (
            SELECT 1 FROM day105_l3.incident_records
            WHERE incident_id = NEW.incident_id
        ) THEN
            RAISE EXCEPTION 'incident already has history; a second root is forbidden'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;

    SELECT incident_id INTO previous_incident_id
    FROM day105_l3.incident_records
    WHERE record_id = NEW.previous_record_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'previous incident record does not exist'
            USING ERRCODE = '23503';
    END IF;
    IF previous_incident_id IS DISTINCT FROM NEW.incident_id THEN
        RAISE EXCEPTION 'incident correction cannot cross incident identity'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS security_snapshots_append_only
    ON security_snapshots;
CREATE TRIGGER security_snapshots_append_only
    BEFORE UPDATE OR DELETE ON security_snapshots
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS current_security_snapshots_revision_guard
    ON current_security_snapshots;
CREATE TRIGGER current_security_snapshots_revision_guard
    BEFORE UPDATE OR DELETE ON current_security_snapshots
    FOR EACH ROW EXECUTE FUNCTION validate_current_security_snapshot_mutation();

DROP TRIGGER IF EXISTS security_artifacts_append_only
    ON security_artifacts;
CREATE TRIGGER security_artifacts_append_only
    BEFORE UPDATE OR DELETE ON security_artifacts
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS response_intents_validate
    ON response_intents;
CREATE TRIGGER response_intents_validate
    BEFORE INSERT ON response_intents
    FOR EACH ROW EXECUTE FUNCTION validate_response_intent();

DROP TRIGGER IF EXISTS response_intents_append_only
    ON response_intents;
CREATE TRIGGER response_intents_append_only
    BEFORE UPDATE OR DELETE ON response_intents
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

DROP TRIGGER IF EXISTS incident_records_validate_chain
    ON incident_records;
CREATE TRIGGER incident_records_validate_chain
    BEFORE INSERT ON incident_records
    FOR EACH ROW EXECUTE FUNCTION validate_incident_chain();

DROP TRIGGER IF EXISTS incident_records_append_only
    ON incident_records;
CREATE TRIGGER incident_records_append_only
    BEFORE UPDATE OR DELETE ON incident_records
    FOR EACH ROW EXECUTE FUNCTION reject_row_mutation();

COMMIT;

CREATE OR REPLACE FUNCTION public.reset_day105_l3_schemas(
    integration_enabled text,
    confirmation text
) RETURNS void
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF current_database() <> 'day105_l3' THEN
        RAISE EXCEPTION 'refusing reset outside day105_l3 database'
            USING ERRCODE = '55000';
    END IF;
    IF integration_enabled IS DISTINCT FROM '1' THEN
        RAISE EXCEPTION 'DAY105_L3_INTEGRATION=1 is required for reset'
            USING ERRCODE = '55000';
    END IF;
    IF confirmation IS DISTINCT FROM 'RESET_DAY105_L3_SCHEMAS' THEN
        RAISE EXCEPTION 'exact reset confirmation is required'
            USING ERRCODE = '55000';
    END IF;

    EXECUTE 'DROP SCHEMA IF EXISTS day105_l3 CASCADE';
    EXECUTE 'DROP SCHEMA IF EXISTS day104_l3 CASCADE';
END;
$$;
