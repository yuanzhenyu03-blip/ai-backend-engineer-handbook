"""Day53 — OpenAI SDK, Provider Boundaries and Structured Output.

Put an OpenAI-compatible Provider behind an APPLICATION-OWNED boundary so SDK behavior,
untrusted outputs, cost evidence, and configuration changes cannot corrupt durable AI Job
facts. Day52 accepted an authorized, budget-reserved Job; Day53 executes it against a
Provider without leaking SDK types, secrets, or unvalidated output into the business layer.

Layering (SDK types stop at the Adapter):
  Router/Dependency -> Application Service -> AIProvider (generate) ->
  OpenAICompatibleAdapter (owns ALL SDK objects/exceptions) -> structured validation
  (Day44, server-owned versioned schema) -> CompletionService (guarded running->succeeded)
  -> Repository/UoW -> PostgreSQL.

EVIDENCE LABEL (do not conflate tiers):
  * CONCEPTUAL DESIGN: the boundary described here + in the design doc.
  * LOCAL CONTROL-FLOW + REAL PYDANTIC VALIDATION RUNTIME: what the pytest suite executes —
    REAL Pydantic v2 strict structured-output validation, plus an in-memory model of
    Adapter -> Validator -> CompletionService control flow with an INJECTED FAKE transport
    that raises modeled vendor exceptions. This proves application control flow + the real
    validation gate.
  * NOT RUN (no such claim): the real `openai` SDK / real network / real Provider; real
    PostgreSQL, Redis, Celery Worker; FastAPI wire; integration; production. Day54
    streaming/disconnect/cancellation, Day55 Celery, Day56 retry/backoff/degradation are
    NOT implemented here.

SECURITY: no real api_key, base_url secret, raw prompt, Document content, or Provider
response is persisted or logged. `ProviderRequest.prompt` is used by the Adapter only and
never copied into durable facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError


# ===========================================================================
# 1. Application-owned Provider contract (NO SDK types cross this line)
# ===========================================================================
@dataclass(frozen=True)
class Usage:
    """Provider cost evidence. `total_tokens is None` means EXPLICIT UNKNOWN — never
    represent unknown usage as zero (that would fabricate a zero-cost fact)."""

    total_tokens: Optional[int]

    @classmethod
    def unknown(cls) -> "Usage":
        return cls(total_tokens=None)

    @property
    def is_known(self) -> bool:
        return self.total_tokens is not None


@dataclass(frozen=True)
class ProviderRequest:
    """Application-owned request. `prompt` is transport input for the Adapter ONLY; it is
    never persisted or logged. The bound schema name/version + approved model come from the
    persisted Job execution contract / validated Settings, never raw client input."""

    job_id: str
    tenant_id: str
    task_type: str
    schema_name: str
    schema_version: str
    approved_model: str
    provider_profile_version: str
    max_output_tokens: int
    correlation_id: str
    prompt: str = field(repr=False, default="")  # transport-only; never persisted/logged


class ProviderOutcome:
    """Base of the typed ProviderOutcome union — the ONLY thing the Adapter returns. No raw
    SDK response/exception, prompt, secret, or debug field ever escapes as an SDK object."""


@dataclass(frozen=True)
class ProviderSuccess(ProviderOutcome):
    raw_payload: dict  # UNTRUSTED until application validation
    usage: Usage
    provider_request_id: Optional[str] = None


@dataclass(frozen=True)
class ProviderRefusal(ProviderOutcome):
    reason_code: str
    provider_request_id: Optional[str] = None


@dataclass(frozen=True)
class ProviderIncomplete(ProviderOutcome):
    reason: str  # e.g. length/content_filter finish reason
    usage: Usage = field(default_factory=Usage.unknown)
    provider_request_id: Optional[str] = None


@dataclass(frozen=True)
class ProviderTimeout(ProviderOutcome):
    usage: Usage = field(default_factory=Usage.unknown)  # unknown, NOT zero


@dataclass(frozen=True)
class ProviderAuthenticationError(ProviderOutcome):
    status_code: int  # 401/403 — a configuration/authentication failure, not user input error


@dataclass(frozen=True)
class ProviderRateLimited(ProviderOutcome):
    retry_after: Optional[str] = None       # safe metadata; Day56 owns retry/backoff policy
    provider_request_id: Optional[str] = None


@dataclass(frozen=True)
class ProviderCapabilityError(ProviderOutcome):
    status_code: int  # e.g. 400 unsupported model/schema — a capability/config failure
    detail: str = ""


@dataclass(frozen=True)
class ProviderTransportError(ProviderOutcome):
    detail: str = ""


# ===========================================================================
# 2. Fake OpenAI-compatible SDK (kept ENTIRELY inside the Adapter boundary)
# ===========================================================================
class _FakeSDKError(Exception):
    """Base of the modeled vendor SDK exceptions. These never escape the Adapter."""


class FakeAuthError(_FakeSDKError):
    def __init__(self, status_code: int = 401) -> None:
        self.status_code = status_code


class FakeRateLimitError(_FakeSDKError):
    def __init__(self, retry_after: Optional[str] = None, request_id: Optional[str] = None) -> None:
        self.retry_after = retry_after
        self.request_id = request_id


class FakeBadRequestError(_FakeSDKError):
    def __init__(self, detail: str = "", status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code


class FakeAPITimeoutError(_FakeSDKError):
    pass


class FakeAPIConnectionError(_FakeSDKError):
    pass


@dataclass
class FakeSDKResponse:
    """Shape mimicking an SDK response object (stays inside the Adapter)."""

    payload: dict
    finish_reason: str = "stop"          # "stop" | "length" | "content_filter"
    refusal: Optional[str] = None
    total_tokens: Optional[int] = None   # None models an SDK that did not report usage
    request_id: Optional[str] = None
    reported_max_tokens: Optional[int] = None  # what the transport was asked to cap at


class FakeOpenAITransport:
    """A lifespan-owned, process-scoped client stand-in. Scripted to return a response or
    raise a modeled SDK exception. Records how many times it was called and the last
    max_tokens it received (to prove the Adapter reuses one client and passes the Job cap)."""

    def __init__(self, *, response: Optional[FakeSDKResponse] = None,
                 error: Optional[_FakeSDKError] = None) -> None:
        self._response = response
        self._error = error
        self.calls = 0
        self.last_max_tokens: Optional[int] = None
        self.closed = False

    def create(self, *, model: str, max_tokens: int, prompt: str) -> FakeSDKResponse:
        self.calls += 1
        self.last_max_tokens = max_tokens
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response

    def close(self) -> None:
        self.closed = True  # drain-before-close boundary (Day45)


# ===========================================================================
# 3. OpenAICompatibleAdapter — translates SDK -> ProviderOutcome, owns SDK errors
# ===========================================================================
class AIProvider(Protocol):
    def generate(self, request: ProviderRequest) -> ProviderOutcome: ...


class OpenAICompatibleAdapter:
    """Owns ALL SDK objects/exceptions. `generate` returns a ProviderOutcome and NEVER
    completes Jobs or writes databases. Reuses one lifespan-owned client per process (no
    client per call). Enforces the effective output cap = min(Job cap, adapter/model
    ceiling) — it never ENLARGES the per-Job limit — and only REPORTS usage (no second
    reservation; Day52 already reserved)."""

    def __init__(self, client: FakeOpenAITransport, *, default_max_output_tokens: int = 8000) -> None:
        self._client = client  # process-scoped; NOT created per generate()
        self._default_max_output_tokens = default_max_output_tokens

    def generate(self, request: ProviderRequest) -> ProviderOutcome:
        # The Job's cap wins; the adapter default is only a ceiling, never an enlargement.
        effective_max = min(request.max_output_tokens, self._default_max_output_tokens)
        try:
            resp = self._client.create(
                model=request.approved_model, max_tokens=effective_max, prompt=request.prompt
            )
        except FakeAuthError as e:
            return ProviderAuthenticationError(status_code=e.status_code)
        except FakeRateLimitError as e:
            return ProviderRateLimited(retry_after=e.retry_after, provider_request_id=e.request_id)
        except FakeBadRequestError as e:
            return ProviderCapabilityError(status_code=e.status_code, detail=e.detail)
        except FakeAPITimeoutError:
            return ProviderTimeout()  # unknown usage
        except FakeAPIConnectionError as e:
            return ProviderTransportError(detail=str(e) or "connection error")
        # Successful SDK response -> classify into the application union.
        usage = Usage(total_tokens=resp.total_tokens)  # None stays UNKNOWN, never coerced to 0
        if resp.refusal is not None:
            return ProviderRefusal(reason_code=resp.refusal, provider_request_id=resp.request_id)
        if resp.finish_reason != "stop":
            return ProviderIncomplete(reason=resp.finish_reason, usage=usage,
                                      provider_request_id=resp.request_id)
        return ProviderSuccess(raw_payload=resp.payload, usage=usage,
                               provider_request_id=resp.request_id)


# ===========================================================================
# 4. Server-owned, versioned Schema Registry + Day44 strict validation
# ===========================================================================
class ResearchSummaryV1(BaseModel):
    """research_summary.v1 — strict application contract. Extra fields (e.g. debug_prompt)
    are FORBIDDEN; missing required fields (e.g. citations) fail. Citation SHAPE is not
    citation grounding — grounding is not claimed here."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    citations: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class ResearchSummaryV2(BaseModel):
    """research_summary.v2 — a DIFFERENT contract (adds required evidence_grade). A v2 output
    must not silently satisfy a v1-contracted Job, and vice versa."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    citations: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_grade: str = Field(min_length=1)


class SchemaRegistry:
    """Server-owned mapping of (schema_name, version) -> a strict Pydantic model. A Job binds
    a name+version at acceptance; there is NO implicit truncation/downgrade/guessed mapping.
    Client `output_schema` never becomes arbitrary forwarded JSON Schema — only an approved
    (name, version) is accepted here."""

    def __init__(self) -> None:
        self._models: dict[tuple[str, str], type[BaseModel]] = {
            ("research_summary", "v1"): ResearchSummaryV1,
            ("research_summary", "v2"): ResearchSummaryV2,
        }

    def model_for(self, schema_name: str, schema_version: str) -> Optional[type[BaseModel]]:
        return self._models.get((schema_name, schema_version))


class ValidationOutcome(str, Enum):
    VALID = "valid"
    SCHEMA_NOT_FOUND = "schema_not_found"      # unknown/unsupported (name, version)
    CONTRACT_VIOLATION = "contract_violation"  # missing required / forbidden extra / bad value


@dataclass(frozen=True)
class ValidationResult:
    outcome: ValidationOutcome
    domain_result: Optional[dict] = None    # the validated, safe domain dict (no raw payload)
    error_fields: tuple[str, ...] = ()      # SAFE field-level classification (no values/payload)


class StructuredOutputValidator:
    """Application-owned validation gate (Day44). Validates an UNTRUSTED Provider payload
    against the Job's BOUND server-owned schema BEFORE any side effect. Never leaks the raw
    payload or field values into the classification."""

    def __init__(self, registry: SchemaRegistry) -> None:
        self._registry = registry

    def validate(self, schema_name: str, schema_version: str, raw_payload: dict) -> ValidationResult:
        model = self._registry.model_for(schema_name, schema_version)
        if model is None:
            return ValidationResult(ValidationOutcome.SCHEMA_NOT_FOUND)
        try:
            obj = model.model_validate(raw_payload)
        except ValidationError as e:
            # Safe classification: field locations only, never values or the raw payload.
            fields = tuple(sorted({str(err["loc"][0]) for err in e.errors() if err.get("loc")}))
            return ValidationResult(ValidationOutcome.CONTRACT_VIOLATION, error_fields=fields)
        return ValidationResult(ValidationOutcome.VALID, domain_result=obj.model_dump())


# ===========================================================================
# 5. Persisted Job execution contract + guarded CompletionService
# ===========================================================================
class JobStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CostState(str, Enum):
    RESERVED = "reserved"
    SETTLED = "settled"
    RECONCILIATION_PENDING = "reconciliation_pending"  # unknown usage: reservation retained


@dataclass(frozen=True)
class ExecutionContract:
    """Non-secret execution-contract facts persisted at acceptance. Governs in-flight result
    acceptance (current Settings governs NEW calls; this governs accepting a result)."""

    schema_name: str
    schema_version: str
    approved_model: str
    provider_profile_version: str
    task_type: str
    max_output_bound: int
    correlation_id: str


@dataclass
class ExecutionJob:
    job_id: str
    tenant_id: str
    contract: ExecutionContract
    reserved_tokens: int
    status: JobStatus = JobStatus.RUNNING
    cost_state: CostState = CostState.RESERVED
    settled_tokens: Optional[int] = None
    result_artifact: Optional[dict] = None
    events: list[dict] = field(default_factory=list)


class CompletionOutcome(str, Enum):
    COMPLETED = "completed"
    NOOP_ZERO_ROWS = "noop_zero_rows"  # guarded transition saw non-running -> stop, do not overwrite


class JobExecutionStore:
    """In-memory model of the durable Job facts + a guarded completion transaction. Only the
    CompletionService may run `running -> succeeded`, persist a Result Artifact/usage/Event,
    and commit a short UoW."""

    def __init__(self) -> None:
        self.jobs: dict[str, ExecutionJob] = {}

    def start_running(self, job_id: str, *, tenant_id: str, contract: ExecutionContract,
                      reserved_tokens: int) -> ExecutionJob:
        job = ExecutionJob(job_id=job_id, tenant_id=tenant_id, contract=contract,
                           reserved_tokens=reserved_tokens)
        self.jobs[job_id] = job
        return job


class CompletionService:
    """Owns the guarded `running -> succeeded` transition + short UoW. Business execution
    success and COST settlement are SEPARATE axes: a valid result may succeed even when usage
    is unknown (retain the reservation, hold reconciliation_pending)."""

    def __init__(self, store: JobExecutionStore) -> None:
        self._store = store

    def complete_success(self, job_id: str, *, domain_result: dict, usage: Usage,
                         provider_request_id: Optional[str]) -> CompletionOutcome:
        job = self._store.jobs.get(job_id)
        # Guarded transition: only a RUNNING job may complete. Zero rows -> STOP (duplicate/
        # stale/cancelled/retry/changed facts); inspect + reconcile, never overwrite.
        if job is None or job.status is not JobStatus.RUNNING:
            return CompletionOutcome.NOOP_ZERO_ROWS
        job.status = JobStatus.SUCCEEDED
        # Cost axis: unknown usage is retained as reconciliation_pending, never zeroed.
        if usage.is_known:
            job.cost_state = CostState.SETTLED
            job.settled_tokens = usage.total_tokens
        else:
            job.cost_state = CostState.RECONCILIATION_PENDING
        # Result Artifact: validated domain result + safe metadata ONLY (raw minimization —
        # no raw Provider payload, no prompt, no secrets).
        job.result_artifact = {
            "domain_result": domain_result,
            "schema_name": job.contract.schema_name,
            "schema_version": job.contract.schema_version,
            "approved_model": job.contract.approved_model,
            "provider_profile_version": job.contract.provider_profile_version,
            "provider_request_id": provider_request_id,
            "correlation_id": job.contract.correlation_id,
            "usage_total_tokens": usage.total_tokens,   # may be None (explicit unknown)
            "cost_state": job.cost_state.value,
        }
        job.events.append({"type": "job.succeeded", "job_id": job_id,
                           "correlation_id": job.contract.correlation_id})
        return CompletionOutcome.COMPLETED

    def record_non_success(self, job_id: str, *, classification: str,
                           provider_request_id: Optional[str] = None,
                           retry_after: Optional[str] = None,
                           mark_failed: bool = True) -> None:
        """Record a classified non-success Attempt/Event WITHOUT a success transition, Result
        Artifact, or success write. Safe metadata only."""
        job = self._store.jobs.get(job_id)
        if job is None:
            return
        if mark_failed and job.status is JobStatus.RUNNING:
            job.status = JobStatus.FAILED
        event = {"type": "job.attempt_failed", "job_id": job_id,
                 "classification": classification,
                 "correlation_id": job.contract.correlation_id}
        if provider_request_id is not None:
            event["provider_request_id"] = provider_request_id
        if retry_after is not None:
            event["retry_after"] = retry_after  # safe downstream metadata; Day56 owns policy
        job.events.append(event)

    def hold_cost_reconciliation(self, job_id: str) -> None:
        """Unknown usage on a non-success path: retain the reservation + record
        reconciliation_pending; never release, never fabricate zero cost."""
        job = self._store.jobs.get(job_id)
        if job is not None:
            job.cost_state = CostState.RECONCILIATION_PENDING


# ===========================================================================
# 6. Provider configuration (current Settings governs NEW calls; can be disabled)
# ===========================================================================
@dataclass
class ProviderConfig:
    """Models Day45 validated Settings for the Provider: the approved model + profile version.
    A 401/403 or capability failure disables NEW calls with this configuration; it does NOT
    invalidate an already-issued call that satisfies its persisted contract."""

    approved_model: str
    provider_profile_version: str
    disabled: bool = False
    disabled_reason: Optional[str] = None

    def disable(self, reason: str) -> None:
        self.disabled = True
        self.disabled_reason = reason


class ExecutionDecision(str, Enum):
    SUCCEEDED = "succeeded"
    VALIDATION_FAILED = "validation_failed"
    REFUSED = "refused"
    INCOMPLETE = "incomplete"
    TIMEOUT_UNKNOWN_USAGE = "timeout_unknown_usage"
    AUTH_CONFIG_FAILURE = "auth_config_failure"
    RATE_LIMITED = "rate_limited"
    CAPABILITY_FAILURE = "capability_failure"
    TRANSPORT_ERROR = "transport_error"
    BLOCKED_CONFIG_DISABLED = "blocked_config_disabled"
    COMPLETION_NOOP = "completion_noop"


@dataclass(frozen=True)
class ExecutionResult:
    decision: ExecutionDecision
    completion: Optional[CompletionOutcome] = None
    validation: Optional[ValidationResult] = None


# ===========================================================================
# 7. Application Service — orchestrates generate -> validate -> guarded completion
# ===========================================================================
def execute_job(
    request: ProviderRequest,
    *,
    adapter: AIProvider,
    validator: StructuredOutputValidator,
    store: JobExecutionStore,
    completion: CompletionService,
    provider_config: ProviderConfig,
) -> ExecutionResult:
    """Execute an already-authorized, budget-reserved, RUNNING Job. The PERSISTED Job
    execution contract governs result acceptance; a valid result is accepted only through
    guarded completion. Configuration rollback affects only NEW calls, never a durable fact."""
    if provider_config.disabled:
        # Current Settings govern NEW calls: refuse to start one with a disabled config.
        return ExecutionResult(ExecutionDecision.BLOCKED_CONFIG_DISABLED)

    outcome = adapter.generate(request)
    job = store.jobs[request.job_id]
    contract = job.contract  # authoritative: validate the result against the JOB's contract

    if isinstance(outcome, ProviderSuccess):
        result = validator.validate(contract.schema_name, contract.schema_version, outcome.raw_payload)
        if result.outcome is ValidationOutcome.VALID:
            assert result.domain_result is not None
            co = completion.complete_success(
                request.job_id, domain_result=result.domain_result, usage=outcome.usage,
                provider_request_id=outcome.provider_request_id,
            )
            decision = (ExecutionDecision.SUCCEEDED if co is CompletionOutcome.COMPLETED
                        else ExecutionDecision.COMPLETION_NOOP)
            return ExecutionResult(decision, completion=co, validation=result)
        # Invalid output NEVER calls completion success — record a classified failure only.
        completion.record_non_success(request.job_id, classification=f"validation:{result.outcome.value}",
                                      provider_request_id=outcome.provider_request_id)
        return ExecutionResult(ExecutionDecision.VALIDATION_FAILED, validation=result)

    if isinstance(outcome, ProviderRefusal):
        completion.record_non_success(request.job_id, classification="provider_refusal",
                                      provider_request_id=outcome.provider_request_id)
        return ExecutionResult(ExecutionDecision.REFUSED)

    if isinstance(outcome, ProviderIncomplete):
        completion.record_non_success(request.job_id, classification=f"provider_incomplete:{outcome.reason}",
                                      provider_request_id=outcome.provider_request_id)
        if not outcome.usage.is_known:
            completion.hold_cost_reconciliation(request.job_id)
        return ExecutionResult(ExecutionDecision.INCOMPLETE)

    if isinstance(outcome, ProviderTimeout):
        completion.record_non_success(request.job_id, classification="provider_timeout_unknown_usage")
        completion.hold_cost_reconciliation(request.job_id)  # retain reservation; unknown != zero
        return ExecutionResult(ExecutionDecision.TIMEOUT_UNKNOWN_USAGE)

    if isinstance(outcome, ProviderAuthenticationError):
        # Configuration/authentication failure: STOP new calls with this config; keep evidence.
        provider_config.disable(f"provider_auth_{outcome.status_code}")
        completion.record_non_success(request.job_id,
                                      classification=f"provider_auth_config_failure:{outcome.status_code}")
        return ExecutionResult(ExecutionDecision.AUTH_CONFIG_FAILURE)

    if isinstance(outcome, ProviderRateLimited):
        # A downstream Provider 429 for this Job/Attempt — NOT a retroactive client 429.
        completion.record_non_success(request.job_id, classification="provider_rate_limited",
                                      provider_request_id=outcome.provider_request_id,
                                      retry_after=outcome.retry_after)
        return ExecutionResult(ExecutionDecision.RATE_LIMITED)

    if isinstance(outcome, ProviderCapabilityError):
        # e.g. 400 unsupported model/schema — capability/config failure, not user input error.
        completion.record_non_success(request.job_id,
                                      classification=f"provider_capability_failure:{outcome.status_code}")
        return ExecutionResult(ExecutionDecision.CAPABILITY_FAILURE)

    if isinstance(outcome, ProviderTransportError):
        completion.record_non_success(request.job_id, classification="provider_transport_error")
        return ExecutionResult(ExecutionDecision.TRANSPORT_ERROR)

    raise AssertionError(f"unhandled ProviderOutcome: {type(outcome).__name__}")
