BEGIN;

CREATE SCHEMA IF NOT EXISTS day106_l3;
SET search_path = day106_l3, public;

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
           SELECT 1 FROM unnest(items) AS item
           WHERE item IS NULL OR btrim(item) = ''
       )
       AND items = ARRAY(
           SELECT DISTINCT item FROM unnest(items) AS item ORDER BY item
       );
$$;

CREATE OR REPLACE FUNCTION sha256_digest_is_valid(value text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
STRICT
AS $$
    SELECT value ~ '^sha256:[0-9a-f]{64}$';
$$;

CREATE OR REPLACE FUNCTION sha256_digest_array_is_valid(items text[])
RETURNS boolean
LANGUAGE sql
IMMUTABLE
STRICT
AS $$
    SELECT items IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM unnest(items) AS item
        WHERE NOT day106_l3.sha256_digest_is_valid(item)
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
            FOR item_key, item_value IN SELECT key, value FROM jsonb_each(payload_value)
            LOOP
                IF lower(replace(item_key, '-', '_')) = ANY (ARRAY[
                    'password', 'database_url', 'dsn', 'secret', 'raw_secret',
                    'token', 'access_token', 'api_key', 'raw_content',
                    'protected_content', 'protected_chunk', 'raw_prompt',
                    'prompt', 'system_prompt', 'answer', 'answer_text',
                    'candidate_text', 'model_output', 'provider_response',
                    'attack_payload', 'cross_tenant_content', 'raw_vector',
                    'vector', 'embedding', 'destination', 'egress_url'
                ]) THEN
                    RETURN false;
                END IF;
                IF NOT day106_l3.jsonb_is_content_safe(item_value) THEN
                    RETURN false;
                END IF;
            END LOOP;
        WHEN 'array' THEN
            FOR item_value IN SELECT value FROM jsonb_array_elements(payload_value)
            LOOP
                IF NOT day106_l3.jsonb_is_content_safe(item_value) THEN
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
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = '55000';
END;
$$;

CREATE TABLE IF NOT EXISTS request_bindings (
    request_binding_id text PRIMARY KEY,
    request_attempt_id text NOT NULL UNIQUE,
    request_id text NOT NULL,
    principal_id text NOT NULL,
    tenant_id text NOT NULL,
    purpose text NOT NULL,
    audience text NOT NULL,
    pointer_name text NOT NULL,
    generation_id text NOT NULL,
    generation_artifact_digest text NOT NULL,
    generation_manifest_digest text NOT NULL,
    build_snapshot_fingerprint text NOT NULL,
    pointer_revision bigint NOT NULL CHECK (pointer_revision > 0),
    read_view_id text NOT NULL UNIQUE,
    read_view_fence bigint NOT NULL CHECK (read_view_fence > 0),
    read_view_digest text NOT NULL,
    source_snapshot_id text NOT NULL,
    authorization_snapshot_id text NOT NULL,
    deletion_snapshot_id text NOT NULL,
    policy_fingerprint text NOT NULL,
    security_binding_fingerprint text NOT NULL,
    retrieval_authorization_revision_digest text NOT NULL,
    retrieval_authorization_scope_fingerprint text NOT NULL,
    selected_retrieval_bundle_id text NOT NULL,
    selected_retrieval_bundle_revision bigint NOT NULL
        CHECK (selected_retrieval_bundle_revision > 0),
    selected_retrieval_bundle_fingerprint text NOT NULL,
    identity_digest text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    CONSTRAINT request_bindings_complete CHECK (
        btrim(request_binding_id) <> '' AND btrim(request_attempt_id) <> ''
        AND btrim(request_id) <> '' AND btrim(principal_id) <> ''
        AND btrim(tenant_id) <> '' AND btrim(purpose) <> ''
        AND btrim(audience) <> '' AND btrim(pointer_name) <> ''
        AND btrim(generation_id) <> '' AND btrim(identity_digest) <> ''
    ),
    CONSTRAINT request_bindings_digest_shape CHECK (
        sha256_digest_is_valid(generation_artifact_digest)
        AND sha256_digest_is_valid(generation_manifest_digest)
        AND sha256_digest_is_valid(build_snapshot_fingerprint)
        AND sha256_digest_is_valid(read_view_digest)
        AND sha256_digest_is_valid(policy_fingerprint)
        AND sha256_digest_is_valid(security_binding_fingerprint)
        AND sha256_digest_is_valid(retrieval_authorization_revision_digest)
        AND sha256_digest_is_valid(retrieval_authorization_scope_fingerprint)
        AND sha256_digest_is_valid(selected_retrieval_bundle_fingerprint)
        AND sha256_digest_is_valid(identity_digest)
    )
);

CREATE TABLE IF NOT EXISTS retrieval_context_receipts (
    receipt_id text PRIMARY KEY,
    request_binding_digest text NOT NULL UNIQUE
        REFERENCES request_bindings (identity_digest),
    retrieval_operation_id text NOT NULL,
    retrieval_request_id text NOT NULL,
    day101_execution_receipt_digest text NOT NULL,
    day101_handoff_digest text NOT NULL,
    prompt_authorization_scope_fingerprint text NOT NULL,
    prompt_authorization_revision_digest text NOT NULL,
    retrieval_bundle_id text NOT NULL,
    retrieval_bundle_digest text NOT NULL,
    retrieval_security_decision_digest text NOT NULL,
    bundle_security_decision_digest text NOT NULL,
    exact_occurrence_ids text[] NOT NULL,
    exact_content_digests text[] NOT NULL,
    context_manifest_id text NOT NULL,
    context_manifest_digest text NOT NULL,
    context_occurrence_ids text[] NOT NULL,
    assembled_context_digest text NOT NULL,
    unauthorized_prompt_count bigint NOT NULL CHECK (unauthorized_prompt_count = 0),
    identity_digest text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    CONSTRAINT retrieval_exact_ids_canonical CHECK (
        text_array_is_canonical(exact_occurrence_ids)
    ),
    CONSTRAINT retrieval_context_ids_canonical CHECK (
        text_array_is_canonical(context_occurrence_ids)
    ),
    CONSTRAINT retrieval_id_digest_cardinality CHECK (
        cardinality(exact_occurrence_ids) = cardinality(exact_content_digests)
    ),
    CONSTRAINT retrieval_context_subset CHECK (
        context_occurrence_ids <@ exact_occurrence_ids
    ),
    CONSTRAINT retrieval_receipts_complete CHECK (
        btrim(receipt_id) <> '' AND btrim(request_binding_digest) <> ''
        AND btrim(retrieval_bundle_id) <> ''
        AND btrim(retrieval_bundle_digest) <> ''
        AND btrim(context_manifest_id) <> ''
        AND btrim(context_manifest_digest) <> ''
        AND btrim(identity_digest) <> ''
    ),
    CONSTRAINT retrieval_receipts_digest_shape CHECK (
        sha256_digest_is_valid(request_binding_digest)
        AND sha256_digest_is_valid(day101_execution_receipt_digest)
        AND sha256_digest_is_valid(day101_handoff_digest)
        AND sha256_digest_is_valid(prompt_authorization_scope_fingerprint)
        AND sha256_digest_is_valid(prompt_authorization_revision_digest)
        AND sha256_digest_is_valid(retrieval_bundle_digest)
        AND sha256_digest_is_valid(retrieval_security_decision_digest)
        AND sha256_digest_is_valid(bundle_security_decision_digest)
        AND sha256_digest_array_is_valid(exact_content_digests)
        AND sha256_digest_is_valid(context_manifest_digest)
        AND sha256_digest_is_valid(assembled_context_digest)
        AND sha256_digest_is_valid(identity_digest)
    )
);

CREATE TABLE IF NOT EXISTS model_invocations (
    model_invocation_id text PRIMARY KEY,
    model_invocation_digest text NOT NULL UNIQUE,
    request_binding_digest text NOT NULL
        REFERENCES request_bindings (identity_digest),
    retrieval_context_receipt_digest text NOT NULL
        REFERENCES retrieval_context_receipts (identity_digest),
    retrieval_bundle_digest text NOT NULL,
    context_manifest_digest text NOT NULL,
    provider_mode text NOT NULL CHECK (
        provider_mode IN ('DETERMINISTIC', 'EXTERNAL')
    ),
    provider_identity_digest text NOT NULL,
    model_identity_digest text NOT NULL,
    config_digest text NOT NULL,
    contract_digest text NOT NULL,
    identity_digest text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    CONSTRAINT model_invocations_id_digest_unique UNIQUE (
        model_invocation_id, model_invocation_digest
    ),
    CONSTRAINT model_invocations_complete CHECK (
        btrim(model_invocation_id) <> ''
        AND sha256_digest_is_valid(model_invocation_digest)
        AND sha256_digest_is_valid(request_binding_digest)
        AND sha256_digest_is_valid(retrieval_context_receipt_digest)
        AND sha256_digest_is_valid(retrieval_bundle_digest)
        AND sha256_digest_is_valid(context_manifest_digest)
        AND sha256_digest_is_valid(provider_identity_digest)
        AND sha256_digest_is_valid(model_identity_digest)
        AND sha256_digest_is_valid(config_digest)
        AND sha256_digest_is_valid(contract_digest)
        AND sha256_digest_is_valid(identity_digest)
    )
);

CREATE OR REPLACE FUNCTION validate_model_invocation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    receipt day106_l3.retrieval_context_receipts%ROWTYPE;
BEGIN
    SELECT * INTO receipt FROM day106_l3.retrieval_context_receipts
    WHERE identity_digest = NEW.retrieval_context_receipt_digest FOR SHARE;
    IF NOT FOUND
       OR receipt.request_binding_digest IS DISTINCT FROM NEW.request_binding_digest
       OR receipt.retrieval_bundle_digest IS DISTINCT FROM NEW.retrieval_bundle_digest
       OR receipt.context_manifest_digest IS DISTINCT FROM NEW.context_manifest_digest
    THEN
        RAISE EXCEPTION 'model invocation request/retrieval/RB/CAM binding mismatch'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS model_invocations_validate_insert ON model_invocations;
CREATE TRIGGER model_invocations_validate_insert
BEFORE INSERT ON model_invocations
FOR EACH ROW EXECUTE FUNCTION validate_model_invocation();

CREATE TABLE IF NOT EXISTS provider_call_attempts (
    attempt_id text PRIMARY KEY,
    request_binding_digest text NOT NULL
        REFERENCES request_bindings (identity_digest),
    retrieval_context_receipt_digest text NOT NULL
        REFERENCES retrieval_context_receipts (identity_digest),
    model_invocation_id text NOT NULL,
    model_invocation_digest text NOT NULL,
    call_ordinal bigint NOT NULL CHECK (call_ordinal BETWEEN 1 AND 10),
    provider_request_idempotency_digest text NOT NULL,
    state text NOT NULL CHECK (state = 'RESERVED'),
    identity_digest text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    CONSTRAINT provider_attempt_invocation_fk FOREIGN KEY (
        model_invocation_id, model_invocation_digest
    ) REFERENCES model_invocations (
        model_invocation_id, model_invocation_digest
    ),
    CONSTRAINT provider_attempt_ordinal_unique UNIQUE (
        model_invocation_id, call_ordinal
    ),
    CONSTRAINT provider_attempt_complete CHECK (
        btrim(attempt_id) <> ''
        AND sha256_digest_is_valid(request_binding_digest)
        AND sha256_digest_is_valid(retrieval_context_receipt_digest)
        AND sha256_digest_is_valid(model_invocation_digest)
        AND sha256_digest_is_valid(provider_request_idempotency_digest)
        AND sha256_digest_is_valid(identity_digest)
    )
);

CREATE OR REPLACE FUNCTION validate_provider_call_attempt()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    invocation day106_l3.model_invocations%ROWTYPE;
BEGIN
    SELECT * INTO invocation FROM day106_l3.model_invocations
    WHERE model_invocation_id = NEW.model_invocation_id
      AND model_invocation_digest = NEW.model_invocation_digest FOR SHARE;
    IF NOT FOUND
       OR invocation.request_binding_digest IS DISTINCT FROM NEW.request_binding_digest
       OR invocation.retrieval_context_receipt_digest IS DISTINCT FROM NEW.retrieval_context_receipt_digest
       OR invocation.provider_mode <> 'EXTERNAL'
    THEN
        RAISE EXCEPTION 'provider attempt invocation binding mismatch'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS provider_call_attempts_validate_insert
    ON provider_call_attempts;
CREATE TRIGGER provider_call_attempts_validate_insert
BEFORE INSERT ON provider_call_attempts
FOR EACH ROW EXECUTE FUNCTION validate_provider_call_attempt();

-- L3B may append a real provider receipt, but it must never persist the
-- prompt, answer text, raw response, raw provider response ID, or credentials.
-- The same request/retrieval/model identities therefore close one execution
-- without expanding this content-safe database boundary.
CREATE TABLE IF NOT EXISTS provider_call_receipts (
    receipt_id text PRIMARY KEY,
    provider_attempt_id text NOT NULL UNIQUE
        REFERENCES provider_call_attempts (attempt_id),
    request_binding_digest text NOT NULL
        REFERENCES request_bindings (identity_digest),
    retrieval_context_receipt_digest text NOT NULL
        REFERENCES retrieval_context_receipts (identity_digest),
    model_invocation_id text NOT NULL,
    model_invocation_digest text NOT NULL,
    call_ordinal bigint NOT NULL CHECK (call_ordinal > 0),
    requested_model_id text NOT NULL,
    observed_model_id text,
    provider_response_id_digest text,
    answer_candidate_digest text,
    input_token_count bigint CHECK (input_token_count IS NULL OR input_token_count >= 0),
    output_token_count bigint CHECK (output_token_count IS NULL OR output_token_count >= 0),
    total_token_count bigint CHECK (
        total_token_count IS NULL OR (
            total_token_count >= 0
            AND input_token_count IS NOT NULL
            AND output_token_count IS NOT NULL
            AND total_token_count = input_token_count + output_token_count
        )
    ),
    status text NOT NULL CHECK (status IN ('SUCCEEDED', 'FAILED', 'UNKNOWN')),
    safe_reason_code text NOT NULL,
    identity_digest text NOT NULL UNIQUE,
    observed_at timestamptz NOT NULL,
    CONSTRAINT provider_call_receipt_ordinal_unique UNIQUE (
        request_binding_digest, model_invocation_id, call_ordinal
    ),
    CONSTRAINT provider_call_receipt_status_shape CHECK (
        (status = 'SUCCEEDED'
         AND observed_model_id IS NOT NULL
         AND provider_response_id_digest IS NOT NULL
         AND answer_candidate_digest IS NOT NULL
         AND input_token_count IS NOT NULL
         AND output_token_count IS NOT NULL
         AND total_token_count IS NOT NULL
         AND total_token_count = input_token_count + output_token_count)
        OR
        (status IN ('FAILED', 'UNKNOWN'))
    ),
    CONSTRAINT provider_call_receipts_complete CHECK (
        btrim(receipt_id) <> '' AND btrim(provider_attempt_id) <> ''
        AND btrim(request_binding_digest) <> ''
        AND btrim(retrieval_context_receipt_digest) <> ''
        AND btrim(model_invocation_id) <> ''
        AND btrim(model_invocation_digest) <> ''
        AND btrim(requested_model_id) <> ''
        AND length(requested_model_id) <= 256
        AND (observed_model_id IS NULL OR (
            btrim(observed_model_id) <> '' AND length(observed_model_id) <= 256
        ))
        AND requested_model_id !~* 'postgres(ql)?://|sk-[A-Za-z0-9_-]{12,}'
        AND (observed_model_id IS NULL OR
             observed_model_id !~* 'postgres(ql)?://|sk-[A-Za-z0-9_-]{12,}')
        AND sha256_digest_is_valid(request_binding_digest)
        AND sha256_digest_is_valid(retrieval_context_receipt_digest)
        AND sha256_digest_is_valid(model_invocation_digest)
        AND (provider_response_id_digest IS NULL OR
             sha256_digest_is_valid(provider_response_id_digest))
        AND (answer_candidate_digest IS NULL OR
             sha256_digest_is_valid(answer_candidate_digest))
        AND sha256_digest_is_valid(identity_digest)
        AND btrim(safe_reason_code) <> '' AND btrim(identity_digest) <> ''
    )
);

CREATE OR REPLACE FUNCTION validate_provider_call_receipt()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    attempt day106_l3.provider_call_attempts%ROWTYPE;
BEGIN
    SELECT * INTO attempt FROM day106_l3.provider_call_attempts
    WHERE attempt_id = NEW.provider_attempt_id FOR SHARE;
    IF NOT FOUND
       OR attempt.request_binding_digest IS DISTINCT FROM NEW.request_binding_digest
       OR attempt.retrieval_context_receipt_digest IS DISTINCT FROM NEW.retrieval_context_receipt_digest
       OR attempt.model_invocation_id IS DISTINCT FROM NEW.model_invocation_id
       OR attempt.model_invocation_digest IS DISTINCT FROM NEW.model_invocation_digest
       OR attempt.call_ordinal IS DISTINCT FROM NEW.call_ordinal
    THEN
        RAISE EXCEPTION 'provider call receipt cross-binding mismatch'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS provider_call_receipts_validate_insert
    ON provider_call_receipts;
CREATE TRIGGER provider_call_receipts_validate_insert
BEFORE INSERT ON provider_call_receipts
FOR EACH ROW EXECUTE FUNCTION validate_provider_call_receipt();

CREATE TABLE IF NOT EXISTS answer_release_records (
    record_id text PRIMARY KEY,
    request_binding_digest text NOT NULL
        REFERENCES request_bindings (identity_digest),
    retrieval_context_receipt_digest text NOT NULL
        REFERENCES retrieval_context_receipts (identity_digest),
    model_invocation_id text NOT NULL,
    model_invocation_digest text NOT NULL,
    answer_candidate_id text NOT NULL,
    answer_candidate_digest text NOT NULL,
    release_evidence_id text NOT NULL,
    release_evidence_digest text NOT NULL,
    output_release_decision_id text NOT NULL UNIQUE,
    output_release_decision_digest text NOT NULL UNIQUE,
    disclosure_envelope_digest text NOT NULL,
    tenant_id text NOT NULL,
    principal_id text NOT NULL,
    action text NOT NULL,
    purpose text NOT NULL,
    current_authorization_scope_fingerprint text NOT NULL,
    current_authorization_revision_digest text NOT NULL,
    release_currentness_snapshot_id text NOT NULL,
    release_currentness_snapshot_digest text NOT NULL,
    release_currentness_revision bigint NOT NULL CHECK (release_currentness_revision > 0),
    released_occurrence_ids text[] NOT NULL,
    authorized_destination_digest text,
    dispatch_idempotency_key_digest text,
    result text NOT NULL CHECK (result IN ('PASS', 'FAIL', 'INCONCLUSIVE', 'NOT_RUN')),
    disposition text NOT NULL CHECK (disposition IN ('RELEASE', 'BLOCKED', 'ABSTAIN')),
    safe_reason_codes text[] NOT NULL,
    response_intent_id text UNIQUE,
    response_dispatch_state text NOT NULL CHECK (
        response_dispatch_state IN ('NOT_ATTEMPTED', 'PENDING')
    ),
    identity_digest text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    CONSTRAINT answer_release_invocation_fk FOREIGN KEY (
        model_invocation_id, model_invocation_digest
    ) REFERENCES model_invocations (
        model_invocation_id, model_invocation_digest
    ),
    CONSTRAINT release_occurrences_canonical CHECK (
        text_array_is_canonical(released_occurrence_ids, true)
    ),
    CONSTRAINT release_reasons_canonical CHECK (
        text_array_is_canonical(safe_reason_codes, true)
    ),
    CONSTRAINT release_shape CHECK (
        (result = 'PASS' AND disposition = 'RELEASE'
         AND cardinality(released_occurrence_ids) > 0
         AND authorized_destination_digest IS NOT NULL
         AND dispatch_idempotency_key_digest IS NOT NULL
         AND response_intent_id IS NOT NULL
         AND response_dispatch_state = 'PENDING')
        OR
        (NOT (result = 'PASS' AND disposition = 'RELEASE')
         AND cardinality(released_occurrence_ids) = 0
         AND authorized_destination_digest IS NULL
         AND dispatch_idempotency_key_digest IS NULL
         AND response_intent_id IS NULL
         AND response_dispatch_state = 'NOT_ATTEMPTED')
    ),
    CONSTRAINT release_digest_shape CHECK (
        sha256_digest_is_valid(request_binding_digest)
        AND sha256_digest_is_valid(retrieval_context_receipt_digest)
        AND sha256_digest_is_valid(model_invocation_digest)
        AND sha256_digest_is_valid(answer_candidate_digest)
        AND sha256_digest_is_valid(release_evidence_digest)
        AND sha256_digest_is_valid(output_release_decision_digest)
        AND sha256_digest_is_valid(disclosure_envelope_digest)
        AND sha256_digest_is_valid(current_authorization_scope_fingerprint)
        AND sha256_digest_is_valid(current_authorization_revision_digest)
        AND sha256_digest_is_valid(release_currentness_snapshot_digest)
        AND (authorized_destination_digest IS NULL OR
             sha256_digest_is_valid(authorized_destination_digest))
        AND (dispatch_idempotency_key_digest IS NULL OR
             sha256_digest_is_valid(dispatch_idempotency_key_digest))
        AND sha256_digest_is_valid(identity_digest)
    )
);

CREATE TABLE IF NOT EXISTS response_intents (
    intent_id text PRIMARY KEY,
    release_record_id text NOT NULL UNIQUE
        REFERENCES answer_release_records (record_id),
    request_binding_digest text NOT NULL,
    output_release_decision_digest text NOT NULL,
    candidate_digest text NOT NULL,
    destination_digest text NOT NULL,
    dispatch_idempotency_key_digest text NOT NULL UNIQUE,
    initial_state text NOT NULL CHECK (initial_state = 'PENDING'),
    revision bigint NOT NULL CHECK (revision = 1),
    identity_digest text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    CONSTRAINT response_intents_digest_shape CHECK (
        sha256_digest_is_valid(request_binding_digest)
        AND sha256_digest_is_valid(output_release_decision_digest)
        AND sha256_digest_is_valid(candidate_digest)
        AND sha256_digest_is_valid(destination_digest)
        AND sha256_digest_is_valid(dispatch_idempotency_key_digest)
        AND sha256_digest_is_valid(identity_digest)
    )
);

CREATE OR REPLACE FUNCTION validate_answer_release_record()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    request_row day106_l3.request_bindings%ROWTYPE;
    receipt_binding text;
    invocation day106_l3.model_invocations%ROWTYPE;
BEGIN
    SELECT * INTO request_row FROM day106_l3.request_bindings
    WHERE identity_digest = NEW.request_binding_digest FOR SHARE;
    SELECT request_binding_digest INTO receipt_binding
    FROM day106_l3.retrieval_context_receipts
    WHERE identity_digest = NEW.retrieval_context_receipt_digest FOR SHARE;
    IF NOT FOUND OR receipt_binding IS DISTINCT FROM NEW.request_binding_digest THEN
        RAISE EXCEPTION 'release retrieval/request cross-binding mismatch'
            USING ERRCODE = '23514';
    END IF;
    IF request_row.tenant_id IS DISTINCT FROM NEW.tenant_id
       OR request_row.principal_id IS DISTINCT FROM NEW.principal_id
       OR request_row.purpose IS DISTINCT FROM NEW.purpose
    THEN
        RAISE EXCEPTION 'release request authority binding mismatch'
            USING ERRCODE = '23514';
    END IF;
    SELECT * INTO invocation FROM day106_l3.model_invocations
    WHERE model_invocation_id = NEW.model_invocation_id
      AND model_invocation_digest = NEW.model_invocation_digest
      AND request_binding_digest = NEW.request_binding_digest
      AND retrieval_context_receipt_digest = NEW.retrieval_context_receipt_digest
    FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'release model invocation binding mismatch'
            USING ERRCODE = '23514';
    END IF;
    IF invocation.provider_mode = 'EXTERNAL'
       AND NEW.result = 'PASS' AND NEW.disposition = 'RELEASE'
       AND NOT EXISTS (
        SELECT 1 FROM day106_l3.provider_call_receipts provider
        WHERE provider.request_binding_digest = NEW.request_binding_digest
          AND provider.retrieval_context_receipt_digest = NEW.retrieval_context_receipt_digest
          AND provider.model_invocation_id = NEW.model_invocation_id
          AND provider.model_invocation_digest = NEW.model_invocation_digest
          AND provider.answer_candidate_digest = NEW.answer_candidate_digest
          AND provider.status = 'SUCCEEDED'
    ) THEN
        RAISE EXCEPTION 'external release requires exact successful provider receipt'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS answer_release_records_validate_insert
    ON answer_release_records;
CREATE TRIGGER answer_release_records_validate_insert
BEFORE INSERT ON answer_release_records
FOR EACH ROW EXECUTE FUNCTION validate_answer_release_record();

CREATE OR REPLACE FUNCTION validate_response_intent()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    release_record day106_l3.answer_release_records%ROWTYPE;
BEGIN
    SELECT * INTO release_record FROM day106_l3.answer_release_records
    WHERE record_id = NEW.release_record_id FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'release record does not exist' USING ERRCODE = '23503';
    END IF;
    IF release_record.result <> 'PASS' OR release_record.disposition <> 'RELEASE' THEN
        RAISE EXCEPTION 'non-PASS release cannot create an intent' USING ERRCODE = '23514';
    END IF;
    IF release_record.response_intent_id IS DISTINCT FROM NEW.intent_id
       OR release_record.request_binding_digest IS DISTINCT FROM NEW.request_binding_digest
       OR release_record.output_release_decision_digest IS DISTINCT FROM NEW.output_release_decision_digest
       OR release_record.answer_candidate_digest IS DISTINCT FROM NEW.candidate_digest
       OR release_record.authorized_destination_digest IS DISTINCT FROM NEW.destination_digest
       OR release_record.dispatch_idempotency_key_digest IS DISTINCT FROM NEW.dispatch_idempotency_key_digest
    THEN
        RAISE EXCEPTION 'response intent exact binding mismatch' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS response_intents_validate_insert ON response_intents;
CREATE TRIGGER response_intents_validate_insert
BEFORE INSERT ON response_intents
FOR EACH ROW EXECUTE FUNCTION validate_response_intent();

CREATE TABLE IF NOT EXISTS dispatch_winners (
    response_intent_id text PRIMARY KEY REFERENCES response_intents (intent_id),
    winner_record_id text NOT NULL UNIQUE,
    provider_message_digest text NOT NULL,
    transport_attempt_id text NOT NULL,
    identity_digest text NOT NULL UNIQUE,
    won_at timestamptz NOT NULL,
    CONSTRAINT dispatch_winners_complete CHECK (
        btrim(winner_record_id) <> '' AND btrim(provider_message_digest) <> ''
        AND btrim(transport_attempt_id) <> '' AND btrim(identity_digest) <> ''
        AND sha256_digest_is_valid(provider_message_digest)
        AND sha256_digest_is_valid(identity_digest)
    )
);

CREATE TABLE IF NOT EXISTS dispatch_recovery_delivery_records (
    record_id text PRIMARY KEY,
    response_intent_id text NOT NULL REFERENCES response_intents (intent_id),
    previous_record_id text UNIQUE
        REFERENCES dispatch_recovery_delivery_records (record_id),
    transport_attempt_id text NOT NULL,
    dispatch_idempotency_key_digest text NOT NULL,
    observation text NOT NULL CHECK (observation IN (
        'SEND_STARTED', 'ACCEPTED', 'NOT_FOUND', 'UNKNOWN',
        'DELIVERED', 'DUPLICATE_RECEIPT'
    )),
    safe_reason_code text NOT NULL,
    evidence_digests text[] NOT NULL,
    provider_message_digest text,
    winner_status text NOT NULL CHECK (winner_status IN (
        'NONE', 'WINNER', 'DUPLICATE', 'CONFLICT'
    )),
    identity_digest text NOT NULL UNIQUE,
    observed_at timestamptz NOT NULL,
    CONSTRAINT dispatch_evidence_canonical CHECK (
        text_array_is_canonical(evidence_digests)
    ),
    CONSTRAINT dispatch_provider_shape CHECK (
        (observation IN ('ACCEPTED', 'DELIVERED', 'DUPLICATE_RECEIPT')
         AND provider_message_digest IS NOT NULL)
        OR
        (observation IN ('SEND_STARTED', 'NOT_FOUND', 'UNKNOWN'))
    ),
    CONSTRAINT dispatch_complete CHECK (
        btrim(record_id) <> '' AND btrim(response_intent_id) <> ''
        AND btrim(transport_attempt_id) <> ''
        AND btrim(dispatch_idempotency_key_digest) <> ''
        AND btrim(safe_reason_code) <> '' AND btrim(identity_digest) <> ''
        AND sha256_digest_is_valid(dispatch_idempotency_key_digest)
        AND sha256_digest_array_is_valid(evidence_digests)
        AND (provider_message_digest IS NULL OR
             sha256_digest_is_valid(provider_message_digest))
        AND sha256_digest_is_valid(identity_digest)
    )
);

CREATE OR REPLACE FUNCTION validate_dispatch_record()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    intent_key text;
    previous day106_l3.dispatch_recovery_delivery_records%ROWTYPE;
    winner day106_l3.dispatch_winners%ROWTYPE;
BEGIN
    SELECT dispatch_idempotency_key_digest INTO intent_key
    FROM day106_l3.response_intents
    WHERE intent_id = NEW.response_intent_id FOR SHARE;
    IF NOT FOUND OR intent_key IS DISTINCT FROM NEW.dispatch_idempotency_key_digest THEN
        RAISE EXCEPTION 'dispatch authority mismatch' USING ERRCODE = '23514';
    END IF;

    IF NEW.previous_record_id IS NULL THEN
        IF NEW.observation <> 'SEND_STARTED' OR EXISTS (
            SELECT 1 FROM day106_l3.dispatch_recovery_delivery_records
            WHERE response_intent_id = NEW.response_intent_id
        ) THEN
            RAISE EXCEPTION 'dispatch history requires one SEND_STARTED root'
                USING ERRCODE = '23514';
        END IF;
    ELSE
        SELECT * INTO previous
        FROM day106_l3.dispatch_recovery_delivery_records
        WHERE record_id = NEW.previous_record_id FOR SHARE;
        IF NOT FOUND OR previous.response_intent_id <> NEW.response_intent_id THEN
            RAISE EXCEPTION 'dispatch predecessor mismatch' USING ERRCODE = '23514';
        END IF;
        IF EXISTS (
            SELECT 1 FROM day106_l3.dispatch_recovery_delivery_records
            WHERE previous_record_id = NEW.previous_record_id
        ) THEN
            RAISE EXCEPTION 'dispatch history cannot branch' USING ERRCODE = '23505';
        END IF;
        IF NEW.observation IN ('UNKNOWN', 'ACCEPTED', 'DELIVERED')
           AND NOT EXISTS (
            SELECT 1 FROM day106_l3.dispatch_recovery_delivery_records
            WHERE response_intent_id = NEW.response_intent_id
              AND transport_attempt_id = NEW.transport_attempt_id
              AND observation = 'SEND_STARTED'
              AND observed_at < NEW.observed_at
        ) THEN
            RAISE EXCEPTION 'dispatch outcome requires same-attempt SEND_STARTED'
                USING ERRCODE = '23514';
        END IF;
        IF NEW.observation = 'NOT_FOUND' AND NOT EXISTS (
            SELECT 1 FROM day106_l3.dispatch_recovery_delivery_records
            WHERE response_intent_id = NEW.response_intent_id
              AND observation = 'UNKNOWN'
              AND observed_at < NEW.observed_at
        ) THEN
            RAISE EXCEPTION 'NOT_FOUND requires an earlier UNKNOWN observation'
                USING ERRCODE = '23514';
        END IF;
    END IF;

    SELECT * INTO winner FROM day106_l3.dispatch_winners
    WHERE response_intent_id = NEW.response_intent_id FOR SHARE;
    IF NEW.winner_status = 'WINNER' AND (
        NOT FOUND OR winner.winner_record_id <> NEW.record_id
        OR winner.provider_message_digest <> NEW.provider_message_digest
    ) THEN
        RAISE EXCEPTION 'winner event does not own the winner fence'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.winner_status IN ('DUPLICATE', 'CONFLICT') AND NOT FOUND THEN
        RAISE EXCEPTION 'duplicate/conflict requires an existing winner'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.observation = 'DUPLICATE_RECEIPT' AND (
        NOT FOUND
        OR NEW.winner_status <> 'DUPLICATE'
        OR winner.provider_message_digest IS DISTINCT FROM NEW.provider_message_digest
    ) THEN
        RAISE EXCEPTION 'duplicate receipt must match the existing winner'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS dispatch_records_validate_insert
    ON dispatch_recovery_delivery_records;
CREATE TRIGGER dispatch_records_validate_insert
BEFORE INSERT ON dispatch_recovery_delivery_records
FOR EACH ROW EXECUTE FUNCTION validate_dispatch_record();

CREATE OR REPLACE VIEW current_response_states AS
SELECT intent.intent_id,
       CASE
           WHEN EXISTS (
               SELECT 1 FROM dispatch_recovery_delivery_records item
               WHERE item.response_intent_id = intent.intent_id
                 AND item.winner_status = 'CONFLICT'
           ) THEN 'IDEMPOTENCY_CONFLICT'
           WHEN EXISTS (
               SELECT 1 FROM dispatch_recovery_delivery_records item
               WHERE item.response_intent_id = intent.intent_id
                 AND item.observation = 'DELIVERED'
                 AND item.winner_status IN ('WINNER', 'DUPLICATE')
           ) THEN 'DELIVERED'
           WHEN EXISTS (
               SELECT 1 FROM dispatch_recovery_delivery_records item
               WHERE item.response_intent_id = intent.intent_id
                 AND item.observation = 'ACCEPTED'
                 AND item.winner_status IN ('WINNER', 'DUPLICATE')
           ) THEN 'DISPATCHED'
           WHEN EXISTS (
               SELECT 1 FROM dispatch_recovery_delivery_records item
               WHERE item.response_intent_id = intent.intent_id
                 AND item.observation = 'UNKNOWN'
           ) AND NOT EXISTS (
               SELECT 1 FROM dispatch_recovery_delivery_records item
               WHERE item.response_intent_id = intent.intent_id
                 AND item.observation = 'NOT_FOUND'
                 AND item.observed_at > (
                     SELECT max(unknown_item.observed_at)
                     FROM dispatch_recovery_delivery_records unknown_item
                     WHERE unknown_item.response_intent_id = intent.intent_id
                       AND unknown_item.observation = 'UNKNOWN'
                 )
           ) THEN 'DELIVERY_UNKNOWN'
           ELSE 'PENDING'
       END AS state
FROM response_intents intent;

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'request_bindings', 'retrieval_context_receipts',
        'model_invocations', 'provider_call_attempts',
        'provider_call_receipts',
        'answer_release_records', 'response_intents',
        'dispatch_winners', 'dispatch_recovery_delivery_records'
    ] LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS %I ON day106_l3.%I',
            table_name || '_append_only', table_name
        );
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON day106_l3.%I '
            'FOR EACH ROW EXECUTE FUNCTION day106_l3.reject_row_mutation()',
            table_name || '_append_only', table_name
        );
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION public.reset_day106_l3_schemas(
    integration_flag text,
    confirmation text
) RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    IF current_database() <> 'day106_l3' THEN
        RAISE EXCEPTION 'reset is restricted to day106_l3' USING ERRCODE = '42501';
    END IF;
    IF integration_flag <> '1' OR confirmation <> 'RESET_DAY106_L3_SCHEMAS' THEN
        RAISE EXCEPTION 'Day106 L3 reset confirmation rejected' USING ERRCODE = '42501';
    END IF;
    DROP SCHEMA IF EXISTS day106_l3 CASCADE;
    DROP SCHEMA IF EXISTS day105_l3 CASCADE;
    DROP SCHEMA IF EXISTS day104_l3 CASCADE;
END;
$$;

COMMIT;
