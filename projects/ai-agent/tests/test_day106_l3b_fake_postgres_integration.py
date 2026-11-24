"""Opt-in real PostgreSQL plus deterministic fake-provider L3B chain.

This test never reads ``OPENAI_API_KEY`` and never opens a network transport.
It is skipped unless the caller explicitly supplies the isolated Day106
database URL and enables the fake-provider integration flag.
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from evals.run_day106_l3b_external_integration import (
    DATABASE_URL_ENV,
    EXPECTED_EXTERNAL_CALLS,
    FAKE_EVIDENCE_LEVEL,
    FAKE_SCHEMA_VERSION,
    FAKE_TRANSPORT_BOUNDARY,
    INTEGRATION_FLAG,
    _durable_pre_restart_state,
    _recover_provider_progress,
    run_integration,
)
from evals.run_day106_l3b_restart_replay import (
    _cross_binding_summary,
    _decision_summary,
    _durable_state,
    _provider_summary,
)
from rag_chunking_contracts import stable_hash
from rag_index_lifecycle_postgres import psycopg2_connection_factory
from rag_openai_responses_adapter import (
    OPENAI_RESPONSES_MODEL,
    OpenAIResponsesHTTPResponse,
    OpenAIResponsesRequest,
)


ENABLED = (
    os.environ.get("DAY106_L3B_FAKE_POSTGRES_INTEGRATION") == "1"
)
DATABASE_URL = os.environ.get(DATABASE_URL_ENV, "")


class DeterministicResponsesTransport:
    """Return the exact bounded source-as-data answer without any I/O."""

    def __init__(self) -> None:
        self.requests: list[OpenAIResponsesRequest] = []

    def send(
        self,
        request: OpenAIResponsesRequest,
    ) -> OpenAIResponsesHTTPResponse:
        self.requests.append(request)
        source_values = [
            line.removeprefix("SOURCE_TEXT: ")
            for line in request.prompt.splitlines()
            if line.startswith("SOURCE_TEXT: ")
        ]
        if not source_values:
            raise AssertionError("FAKE_PROVIDER_SOURCE_WINDOWS_MISSING")
        answer = " ".join(source_values)
        ordinal = len(self.requests)
        body = json.dumps({
            "id": f"resp_day106_fake_{ordinal}",
            "status": "completed",
            "model": OPENAI_RESPONSES_MODEL,
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": answer}],
            }],
            "usage": {
                "input_tokens": 32,
                "output_tokens": 16,
                "total_tokens": 48,
            },
        }, separators=(",", ":")).encode("utf-8")
        return OpenAIResponsesHTTPResponse(200, body)


@pytest.mark.skipif(
    not (ENABLED and DATABASE_URL),
    reason="Day106 L3B real-PostgreSQL fake-provider chain is opt-in",
)
def test_real_postgres_fake_provider_runs_exact_five_call_chain() -> None:
    transport = DeterministicResponsesTransport()

    with patch.dict(os.environ, {INTEGRATION_FLAG: "1"}):
        report = run_integration(DATABASE_URL, transport=transport)

    assert report["status"] == "PASS"
    assert report["schema_version"] == FAKE_SCHEMA_VERSION
    assert report["evidence_level"] == FAKE_EVIDENCE_LEVEL
    assert report["transport_boundary"] == FAKE_TRANSPORT_BOUNDARY
    assert report["external_model_boundary"] == "NOT_RUN"
    assert report["external_call_count"] == 5
    assert len(transport.requests) == 5
    external_calls = report["external_calls"]
    assert [item["label"] for item in external_calls] == list(
        EXPECTED_EXTERNAL_CALLS
    )
    assert [item["release_disposition"] for item in external_calls] == [
        "RELEASE",
        "RELEASE",
        "RELEASE",
        "BLOCKED",
        "RELEASE",
    ]
    assert report["pending_g2_after_p2"]["disposition"] == "BLOCKED"
    assert all(
        item["unauthorized_prompt_count"] == 0
        for item in external_calls
    )

    # Append unrelated request identities after the sealed run: one from a
    # different tenant and one from the same tenant but another pointer.  The
    # capstone tenant+pointer digest and summaries must remain unchanged.
    factory = psycopg2_connection_factory(
        DATABASE_URL,
        application_name="day106-l3b-cross-tenant-negative-control",
    )
    connection = factory()
    cursor = connection.cursor()
    try:
        for (
            binding_id,
            attempt_id,
            request_suffix,
            tenant_id,
            pointer_name,
            read_view_id,
        ) in (
            (
                "cross-tenant-request-binding",
                "cross-tenant-request-attempt",
                ":cross-tenant",
                "tenant-cross-negative-control",
                "refund-serving",
                "cross-tenant-read-view",
            ),
            (
                "other-pointer-request-binding",
                "other-pointer-request-attempt",
                ":other-pointer",
                "tenant-refund",
                "other-serving-negative-control",
                "other-pointer-read-view",
            ),
        ):
            cursor.execute(
                """
            INSERT INTO day106_l3.request_bindings (
              request_binding_id, request_attempt_id, request_id,
              principal_id, tenant_id, purpose, audience, pointer_name,
              generation_id, generation_artifact_digest,
              generation_manifest_digest, build_snapshot_fingerprint,
              pointer_revision, read_view_id, read_view_fence,
              read_view_digest, source_snapshot_id,
              authorization_snapshot_id, deletion_snapshot_id,
              policy_fingerprint, security_binding_fingerprint,
              retrieval_authorization_revision_digest,
              retrieval_authorization_scope_fingerprint,
              selected_retrieval_bundle_id,
              selected_retrieval_bundle_revision,
              selected_retrieval_bundle_fingerprint,
              identity_digest, created_at
            )
            SELECT
              %s, %s, request_id || %s, principal_id,
              %s, purpose, audience,
              %s, generation_id, generation_artifact_digest,
              generation_manifest_digest, build_snapshot_fingerprint,
              pointer_revision, %s, read_view_fence, read_view_digest,
              source_snapshot_id, authorization_snapshot_id,
              deletion_snapshot_id, policy_fingerprint,
              security_binding_fingerprint,
              retrieval_authorization_revision_digest,
              retrieval_authorization_scope_fingerprint,
              selected_retrieval_bundle_id,
              selected_retrieval_bundle_revision,
              selected_retrieval_bundle_fingerprint, %s, created_at
            FROM day106_l3.request_bindings
            WHERE tenant_id = 'tenant-refund'
            ORDER BY created_at, request_binding_id
            LIMIT 1
                """,
                (
                    binding_id,
                    attempt_id,
                    request_suffix,
                    tenant_id,
                    pointer_name,
                    read_view_id,
                    stable_hash(binding_id),
                ),
            )
        other_request_digest = stable_hash("other-pointer-request-binding")
        other_receipt_digest = stable_hash("other-pointer-retrieval-receipt")
        other_model_digest = stable_hash("other-pointer-model-invocation")
        cursor.execute(
            """
            INSERT INTO day106_l3.retrieval_context_receipts (
              receipt_id, request_binding_digest, retrieval_operation_id,
              retrieval_request_id, day101_execution_receipt_digest,
              day101_handoff_digest,
              prompt_authorization_scope_fingerprint,
              prompt_authorization_revision_digest, retrieval_bundle_id,
              retrieval_bundle_digest, retrieval_security_decision_digest,
              bundle_security_decision_digest, exact_occurrence_ids,
              exact_content_digests, context_manifest_id,
              context_manifest_digest, context_occurrence_ids,
              assembled_context_digest, unauthorized_prompt_count,
              identity_digest, created_at
            )
            SELECT
              'other-pointer-retrieval-receipt', %s,
              receipt.retrieval_operation_id,
              receipt.retrieval_request_id,
              receipt.day101_execution_receipt_digest,
              receipt.day101_handoff_digest,
              receipt.prompt_authorization_scope_fingerprint,
              receipt.prompt_authorization_revision_digest,
              receipt.retrieval_bundle_id, receipt.retrieval_bundle_digest,
              receipt.retrieval_security_decision_digest,
              receipt.bundle_security_decision_digest,
              receipt.exact_occurrence_ids, receipt.exact_content_digests,
              receipt.context_manifest_id, receipt.context_manifest_digest,
              receipt.context_occurrence_ids,
              receipt.assembled_context_digest,
              receipt.unauthorized_prompt_count, %s, receipt.created_at
            FROM day106_l3.retrieval_context_receipts AS receipt
            JOIN day106_l3.request_bindings AS request
              ON request.identity_digest = receipt.request_binding_digest
            WHERE request.tenant_id = 'tenant-refund'
              AND request.pointer_name = 'refund-serving'
            ORDER BY receipt.created_at, receipt.receipt_id
            LIMIT 1
            """,
            (other_request_digest, other_receipt_digest),
        )
        cursor.execute(
            """
            INSERT INTO day106_l3.model_invocations (
              model_invocation_id, model_invocation_digest,
              request_binding_digest, retrieval_context_receipt_digest,
              retrieval_bundle_digest, context_manifest_digest,
              provider_mode, provider_identity_digest,
              model_identity_digest, config_digest, contract_digest,
              identity_digest, created_at
            )
            SELECT
              'other-pointer-model-invocation', %s, %s, %s,
              invocation.retrieval_bundle_digest,
              invocation.context_manifest_digest, invocation.provider_mode,
              invocation.provider_identity_digest,
              invocation.model_identity_digest, invocation.config_digest,
              invocation.contract_digest, %s, invocation.created_at
            FROM day106_l3.model_invocations AS invocation
            JOIN day106_l3.request_bindings AS request
              ON request.identity_digest = invocation.request_binding_digest
            WHERE request.tenant_id = 'tenant-refund'
              AND request.pointer_name = 'refund-serving'
            ORDER BY invocation.created_at, invocation.model_invocation_id
            LIMIT 1
            """,
            (
                other_model_digest,
                other_request_digest,
                other_receipt_digest,
                stable_hash("other-pointer-model-record"),
            ),
        )
        cursor.execute(
            """
            INSERT INTO day106_l3.provider_call_attempts (
              attempt_id, request_binding_digest,
              retrieval_context_receipt_digest, model_invocation_id,
              model_invocation_digest, call_ordinal,
              provider_request_idempotency_digest, state,
              identity_digest, created_at
            )
            SELECT
              'other-pointer-provider-attempt', %s, %s,
              'other-pointer-model-invocation', %s,
              attempt.call_ordinal, %s, attempt.state, %s,
              attempt.created_at
            FROM day106_l3.provider_call_attempts AS attempt
            JOIN day106_l3.request_bindings AS request
              ON request.identity_digest = attempt.request_binding_digest
            WHERE request.tenant_id = 'tenant-refund'
              AND request.pointer_name = 'refund-serving'
            ORDER BY attempt.call_ordinal, attempt.attempt_id
            LIMIT 1
            """,
            (
                other_request_digest,
                other_receipt_digest,
                other_model_digest,
                stable_hash("other-pointer-idempotency"),
                stable_hash("other-pointer-provider-attempt-record"),
            ),
        )
        cursor.execute(
            """
            INSERT INTO day106_l3.provider_call_receipts (
              receipt_id, provider_attempt_id, request_binding_digest,
              retrieval_context_receipt_digest, model_invocation_id,
              model_invocation_digest, call_ordinal, requested_model_id,
              observed_model_id, provider_response_id_digest,
              answer_candidate_digest, input_token_count,
              output_token_count, total_token_count, status,
              safe_reason_code, identity_digest, observed_at
            )
            SELECT
              'other-pointer-provider-receipt',
              'other-pointer-provider-attempt', %s, %s,
              'other-pointer-model-invocation', %s,
              receipt.call_ordinal, receipt.requested_model_id,
              receipt.observed_model_id, %s,
              receipt.answer_candidate_digest, receipt.input_token_count,
              receipt.output_token_count, receipt.total_token_count,
              receipt.status, receipt.safe_reason_code, %s,
              receipt.observed_at
            FROM day106_l3.provider_call_receipts AS receipt
            JOIN day106_l3.request_bindings AS request
              ON request.identity_digest = receipt.request_binding_digest
            WHERE request.tenant_id = 'tenant-refund'
              AND request.pointer_name = 'refund-serving'
            ORDER BY receipt.call_ordinal, receipt.receipt_id
            LIMIT 1
            """,
            (
                other_request_digest,
                other_receipt_digest,
                other_model_digest,
                stable_hash("other-pointer-provider-response"),
                stable_hash("other-pointer-provider-receipt-record"),
            ),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    after_contamination = _durable_pre_restart_state(factory)
    sealed = report["restart_evidence"]
    assert after_contamination["pre_restart_state_digest"] == (
        sealed["pre_restart_state_digest"]
    )
    assert after_contamination["artifact_counts"] == sealed["artifact_counts"]
    restart_state = _durable_state(factory)
    provider = _provider_summary(factory)
    cross_binding = _cross_binding_summary(factory)
    decisions = _decision_summary(factory)
    assert restart_state["state_digest"] == sealed["pre_restart_state_digest"]
    assert restart_state["artifact_identity_count"] == 34
    assert provider["attempt_count"] == provider["receipt_count"] == 5
    recovered = _recover_provider_progress(DATABASE_URL)
    assert recovered["attempt_count"] == recovered["receipt_count"] == 5
    assert recovered["provider_outcome_state"] == "SUCCEEDED"
    assert not any(cross_binding.values())
    assert decisions["decision_count"] == 5
