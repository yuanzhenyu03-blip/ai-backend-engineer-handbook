"""Day44 — negative and positive pytest cases for the Pydantic v2 contracts.

Real Pydantic v2 runtime tests. The completion target is an in-memory list, NOT
PostgreSQL: these tests prove structural validation and the validation-before-
side-effects gate, not authentication, authorization, application invariants, or
a database commit (see the Day44 validation matrix).

Each negative test keeps every field valid EXCEPT the one under test, so a test
never passes for an unrelated reason (e.g. a missing max_tokens).

Run (see requirements.txt in this directory):
    python3 -m pip install -r requirements.txt
    python3 -m py_compile day44_pydantic_contracts.py test_day44_pydantic_contracts.py
    python3 -m pytest -q test_day44_pydantic_contracts.py
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from day44_pydantic_contracts import (
    ExtractStructuredRequest,
    JobRequestAdapter,
    QueuedJobResponse,
    StructuredAIResult,
    SucceededJobResponse,
    SummarizeRequest,
    validate_provider_output_before_completion,
)

# Real but fictional UUIDs (not "u1"/"j1").
UPLOAD_ID = "0f9b0e3a-6a1e-4c2b-9c1f-2b7a4d5e6f70"
JOB_ID = "3b2f1c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"


def summarize_payload(**overrides):
    """A fully valid summarize request; override exactly one field per test."""
    payload = {
        "task_type": "summarize",
        "upload_session_id": UPLOAD_ID,
        "max_tokens": 2000,
    }
    payload.update(overrides)
    return payload


def extract_payload(**overrides):
    """A fully valid extract_structured request; override one field per test."""
    payload = {
        "task_type": "extract_structured",
        "upload_session_id": UPLOAD_ID,
        "max_tokens": 2000,
        "output_schema": {"company": "string", "revenue": "number"},
    }
    payload.update(overrides)
    return payload


# 1. Valid summarize request.
def test_valid_summarize_request():
    req = JobRequestAdapter.validate_python(summarize_payload())
    assert isinstance(req, SummarizeRequest)
    assert req.max_tokens == 2000
    assert str(req.upload_session_id) == UPLOAD_ID


# 2. Valid extract_structured request.
def test_valid_extract_structured_request():
    req = JobRequestAdapter.validate_python(extract_payload())
    assert isinstance(req, ExtractStructuredRequest)
    assert req.output_schema == {"company": "string", "revenue": "number"}


# 3. Body-level tenant_id is rejected (tenant is trusted context, not input).
def test_body_tenant_id_rejected():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(summarize_payload(tenant_id=str(uuid.uuid4())))


# 4. A client-supplied job_status is rejected (server-owned lifecycle state).
def test_body_job_status_rejected():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(summarize_payload(job_status="succeeded"))


# 5. An undeclared debug field is rejected by extra="forbid".
def test_unexpected_debug_field_rejected():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(summarize_payload(unexpected_debug=True))


# 6. A string max_tokens ("2000") is rejected (strict int; no silent coercion).
def test_string_max_tokens_rejected():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(summarize_payload(max_tokens="2000"))


# 7. max_tokens above the 1..8000 bound is rejected.
def test_max_tokens_above_bound_rejected():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(summarize_payload(max_tokens=8001))


# 8. A missing max_tokens is rejected (required field).
def test_missing_max_tokens_rejected():
    payload = summarize_payload()
    del payload["max_tokens"]
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(payload)


# 9. summarize forbids output_schema (variant rule + extra="forbid").
def test_summarize_forbids_output_schema():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(summarize_payload(output_schema={"company": "string"}))


# 10. extract_structured rejects an empty output_schema.
def test_empty_output_schema_rejected():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(extract_payload(output_schema={}))


# 11. extract_structured rejects an unsupported output_schema value / a non-dict.
def test_unsupported_output_schema_value_rejected():
    # An unsupported type name.
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(extract_payload(output_schema={"company": "integer"}))
    # A non-string (int) value.
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(extract_payload(output_schema={"company": 1}))
    # A non-mapping (int) schema.
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(extract_payload(output_schema=5))


# 12. A malformed upload_session_id (not a UUID) is rejected at the boundary.
def test_malformed_upload_session_id_rejected():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(summarize_payload(upload_session_id="u1"))


# 13. A malformed job_id (not a UUID) is rejected in a public response.
def test_malformed_job_id_rejected():
    with pytest.raises(ValidationError):
        QueuedJobResponse.model_validate({"job_id": "j1", "job_status": "queued"})


# 14. A succeeded response requires a result.
def test_succeeded_requires_result():
    ok = SucceededJobResponse.model_validate(
        {
            "job_id": JOB_ID,
            "job_status": "succeeded",
            "result": {
                "summary": "s",
                "confidence": 0.9,
                "citations": [{"source_id": "c1", "url": "https://example.com/a"}],
            },
        }
    )
    assert ok.result.confidence == 0.9
    with pytest.raises(ValidationError):
        SucceededJobResponse.model_validate({"job_id": JOB_ID, "job_status": "succeeded"})


# 15. A queued response rejects an early result field.
def test_queued_rejects_early_result():
    ok = QueuedJobResponse.model_validate({"job_id": JOB_ID, "job_status": "queued"})
    assert ok.job_status == "queued"
    with pytest.raises(ValidationError):
        QueuedJobResponse.model_validate(
            {"job_id": JOB_ID, "job_status": "queued", "result": {"summary": "s"}}
        )


# 16. An invalid citation URL is rejected ("https://", plain string, non-http).
def test_invalid_citation_url_rejected():
    # Full HTTP/HTTPS URLs pass.
    StructuredAIResult.model_validate(
        {
            "summary": "s",
            "confidence": 0.5,
            "citations": [{"source_id": "c1", "url": "http://example.com/a"}],
        }
    )
    for bad_url in ("https://", "not-a-url", "ftp://example.com/a"):
        with pytest.raises(ValidationError):
            StructuredAIResult.model_validate(
                {
                    "summary": "s",
                    "confidence": 0.5,
                    "citations": [{"source_id": "c1", "url": bad_url}],
                }
            )


# 17. Invalid Provider output raises BEFORE the fake completion callback runs.
def test_invalid_provider_output_blocks_completion():
    completion_calls: list[StructuredAIResult] = []
    # Provider-controlled job_status, string confidence, and a single-string
    # citations field: legal JSON, invalid contract.
    bad = (
        '{"summary": "s", "confidence": "very sure", '
        '"citations": "one-source", "job_status": "succeeded"}'
    )
    with pytest.raises(ValidationError):
        validate_provider_output_before_completion(bad, completion_calls.append)
    # The empty list proves the side effect was blocked, not merely that an
    # exception occurred (a dangerous impl might complete before validating).
    assert completion_calls == []


# 18. Valid Provider output reaches the completion callback exactly once.
def test_valid_provider_output_completes_once():
    completion_calls: list[StructuredAIResult] = []
    good = (
        '{"summary": "s", "confidence": 0.8, '
        '"citations": [{"source_id": "c1", "url": "https://example.com/a"}]}'
    )
    result = validate_provider_output_before_completion(good, completion_calls.append)
    assert isinstance(result, StructuredAIResult)
    assert len(completion_calls) == 1
    assert completion_calls[0] is result
