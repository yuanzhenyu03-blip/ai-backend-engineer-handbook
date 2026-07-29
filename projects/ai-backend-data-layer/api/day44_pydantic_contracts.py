"""Day44 — Pydantic v2 API and AI output contracts.

Executable, typed validation/serialization boundaries for the Day43 AI Job HTTP
product contract: client request models, public response models, a public error
envelope, and untrusted AI Provider output.

Scope and honesty (see the Day44 lesson and validation matrix):
    * These are REAL Pydantic v2 runtime contracts, tested by
      ``test_day44_pydantic_contracts.py``.
    * ``tenant_id`` is trusted authentication context, NOT a request-body field.
    * Structural validation is NOT authorization and NOT a durable database commit.
    * The completion target here is an in-memory callback, NOT PostgreSQL.
    * No FastAPI app/routing, PostgreSQL, SQLAlchemy/Alembic, real Provider SDK,
      Relay/Worker/Redis/Object Storage, DI/lifespan, integration, or production
      was implemented or run. Those are later-lesson boundaries (Day45-58).

Tested with: Python 3.10+ and Pydantic v2 (pinned in the repository; the
classroom and the repository evidence used Pydantic 2.5.0). Do not claim every
Pydantic v2 release was tested.
"""

from __future__ import annotations

from typing import Annotated, Callable, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)

# ---------------------------------------------------------------------------
# Strict, field-specific aliases (deliberate strictness where cost/audit risk)
# ---------------------------------------------------------------------------
# Strict so a JSON string like "2000" is NOT silently coerced to 2000.
MaxTokens = Annotated[int, Field(strict=True, ge=1, le=200_000)]
# Strict float in [0, 1]; a string like "very sure" is rejected.
Confidence = Annotated[float, Field(strict=True, ge=0.0, le=1.0)]


# ---------------------------------------------------------------------------
# Client request models (discriminated union on task_type)
# ---------------------------------------------------------------------------
# tenant_id is NOT here: it comes from trusted authentication context, never the
# request body. extra="forbid" rejects undeclared input (e.g. a client-supplied
# job_status, tenant_id, or unexpected_debug) instead of silently ignoring it.
class _RequestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_session_id: str = Field(min_length=1)
    max_tokens: Optional[MaxTokens] = None


class SummarizeRequest(_RequestBase):
    task_type: Literal["summarize"]
    # summarize FORBIDS output_schema (enforced structurally: field not declared,
    # and extra="forbid" rejects it if supplied).


class ExtractStructuredRequest(_RequestBase):
    task_type: Literal["extract_structured"]
    # extract_structured REQUIRES a non-empty output_schema.
    output_schema: dict = Field(min_length=1)


JobRequest = Annotated[
    Union[SummarizeRequest, ExtractStructuredRequest],
    Field(discriminator="task_type"),
]
JobRequestAdapter: TypeAdapter[JobRequest] = TypeAdapter(JobRequest)


# ---------------------------------------------------------------------------
# Untrusted Provider output (validated before any completion)
# ---------------------------------------------------------------------------
# The Provider CANNOT own the Job lifecycle, so no job_status field exists here;
# extra="forbid" rejects a Provider-supplied job_status. Pydantic can validate
# citation/URL SHAPE; it cannot prove the citations are true or grounded.
class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    url: str = Field(pattern=r"^https?://")


class StructuredAIResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    confidence: Confidence
    citations: list[Citation]


# ---------------------------------------------------------------------------
# Public response models (allowlisted; status-discriminated)
# ---------------------------------------------------------------------------
# Persistence / internal / public representations are SEPARATE. Internal fields
# (lease token, fencing generation, raw Provider metadata, raw Object Storage
# key, Outbox id, unreviewed Attempt fields) never appear here.
class PublicResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    confidence: Confidence
    citations: list[Citation]


class PublicFailure(BaseModel):
    """Business failure of the Job (distinct from an HTTP/request error)."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class QueuedJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    job_status: Literal["queued", "running"]
    # queued/running: no terminal result and no failure (no such fields exist).


class SucceededJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    job_status: Literal["succeeded"]
    result: PublicResult  # required; failure absent (no such field).


class FailedJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    job_status: Literal["failed"]
    failure: PublicFailure  # required; result absent (no such field).


# A found Job is a successfully read resource: GET returns HTTP 200 + one of
# these, discriminated by job_status. (HTTP status is separate; see the error
# envelope below.)
JobStatusResponse = Annotated[
    Union[QueuedJobResponse, SucceededJobResponse, FailedJobResponse],
    Field(discriminator="job_status"),
]
JobStatusResponseAdapter: TypeAdapter[JobStatusResponse] = TypeAdapter(JobStatusResponse)


# ---------------------------------------------------------------------------
# Stable public HTTP error envelope (for request/HTTP failures, not Job state)
# ---------------------------------------------------------------------------
# HTTP status remains the error CLASS; error.code is stable machine semantics a
# client may branch on; message is safe public text; field_errors/request_id are
# optional. Never expose SQL, tracebacks, credentials, raw Provider errors, raw
# storage keys, or cross-tenant existence.
class FieldError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    code: str
    message: str


class PublicError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    field_errors: Optional[list[FieldError]] = None
    request_id: Optional[str] = None


class PublicErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: PublicError


# ---------------------------------------------------------------------------
# Validation-before-side-effects gate
# ---------------------------------------------------------------------------
def validate_provider_output_before_completion(
    raw_provider_json: str,
    on_completion: Callable[[StructuredAIResult], None],
) -> StructuredAIResult:
    """Validate untrusted Provider output, THEN run the completion callback.

    Raises ``pydantic.ValidationError`` before ``on_completion`` is ever called
    when the Provider output is invalid, so a fake/invalid result can never
    reach guarded completion. Uses ``model_validate_json`` (validating) — never
    ``model_construct`` (which skips validation) for untrusted input.
    """
    result = StructuredAIResult.model_validate_json(raw_provider_json)
    # Only a validated result reaches the (here in-memory) completion callback.
    # Real guarded PostgreSQL completion + application checks are later lessons.
    on_completion(result)
    return result


__all__ = [
    "MaxTokens",
    "Confidence",
    "SummarizeRequest",
    "ExtractStructuredRequest",
    "JobRequest",
    "JobRequestAdapter",
    "Citation",
    "StructuredAIResult",
    "PublicResult",
    "PublicFailure",
    "QueuedJobResponse",
    "SucceededJobResponse",
    "FailedJobResponse",
    "JobStatusResponse",
    "JobStatusResponseAdapter",
    "FieldError",
    "PublicError",
    "PublicErrorResponse",
    "validate_provider_output_before_completion",
    "ValidationError",
]
