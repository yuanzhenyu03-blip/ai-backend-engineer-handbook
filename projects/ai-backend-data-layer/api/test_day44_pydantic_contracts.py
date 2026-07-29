"""Day44 — negative and positive pytest cases for the Pydantic v2 contracts.

Real Pydantic v2 runtime tests. The completion target is an in-memory list, NOT
PostgreSQL: these tests prove structural validation and the validation-before-
side-effects gate, not authorization, a database commit, or any FastAPI/Provider
integration (see the Day44 validation matrix).

Run:
    python3 -m py_compile day44_pydantic_contracts.py test_day44_pydantic_contracts.py
    python3 -m pytest -q test_day44_pydantic_contracts.py
"""

from __future__ import annotations

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


# 1. A valid summarize request parses through the discriminated union.
def test_valid_summarize_request():
    req = JobRequestAdapter.validate_python(
        {"task_type": "summarize", "upload_session_id": "u1", "max_tokens": 2000}
    )
    assert isinstance(req, SummarizeRequest)
    assert req.max_tokens == 2000


# 2. A body-level tenant_id is rejected (tenant is trusted context, not input).
def test_body_tenant_id_rejected():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(
            {"task_type": "summarize", "upload_session_id": "u1", "tenant_id": "t2"}
        )


# 3. A client-supplied job_status is rejected (server-owned lifecycle state).
def test_body_job_status_rejected():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(
            {"task_type": "summarize", "upload_session_id": "u1", "job_status": "succeeded"}
        )


# 4. An undeclared debug field is rejected by extra="forbid".
def test_unexpected_debug_field_rejected():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(
            {"task_type": "summarize", "upload_session_id": "u1", "unexpected_debug": True}
        )


# 5. A string max_tokens ("2000") is rejected (strict int; no silent coercion).
def test_string_max_tokens_rejected():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(
            {"task_type": "summarize", "upload_session_id": "u1", "max_tokens": "2000"}
        )


# 6. summarize forbids output_schema (cross-field / variant rule).
def test_summarize_forbids_output_schema():
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(
            {"task_type": "summarize", "upload_session_id": "u1", "output_schema": {"a": 1}}
        )


# 7. extract_structured requires a non-empty output_schema.
def test_extract_requires_nonempty_output_schema():
    ok = JobRequestAdapter.validate_python(
        {"task_type": "extract_structured", "upload_session_id": "u1", "output_schema": {"a": 1}}
    )
    assert isinstance(ok, ExtractStructuredRequest)
    with pytest.raises(ValidationError):
        JobRequestAdapter.validate_python(
            {"task_type": "extract_structured", "upload_session_id": "u1", "output_schema": {}}
        )


# 8. A succeeded response requires a result.
def test_succeeded_requires_result():
    ok = SucceededJobResponse.model_validate(
        {
            "job_id": "j1",
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
        SucceededJobResponse.model_validate({"job_id": "j1", "job_status": "succeeded"})


# 9. A queued response rejects an early result field.
def test_queued_rejects_early_result():
    ok = QueuedJobResponse.model_validate({"job_id": "j1", "job_status": "queued"})
    assert ok.job_status == "queued"
    with pytest.raises(ValidationError):
        QueuedJobResponse.model_validate(
            {"job_id": "j1", "job_status": "queued", "result": {"summary": "s"}}
        )


# 10. Invalid Provider output raises BEFORE the fake completion callback runs.
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


# 11. Valid Provider output reaches the completion callback exactly once.
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
