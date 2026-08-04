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

import threading
import uuid
from dataclasses import dataclass, field, replace
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
    usage: Usage = field(default_factory=Usage.unknown)  # a refusal may still have billed usage
    provider_request_id: Optional[str] = None


@dataclass(frozen=True)
class ProviderIncomplete(ProviderOutcome):
    reason: str  # e.g. length/content_filter finish reason
    usage: Usage = field(default_factory=Usage.unknown)
    provider_request_id: Optional[str] = None


@dataclass(frozen=True)
class ProviderTimeout(ProviderOutcome):
    usage: Usage = field(default_factory=Usage.unknown)  # unknown, NOT zero
    provider_request_id: Optional[str] = None  # the SDK may know the sent request id even on timeout


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
    config_scope: bool = False  # True: the CURRENT model/profile cannot honor the controlled schema
    provider_request_id: Optional[str] = None


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
    def __init__(self, detail: str = "", status_code: int = 400, *, config_scope: bool = False,
                 request_id: Optional[str] = None) -> None:
        self.detail = detail
        self.status_code = status_code
        self.config_scope = config_scope   # True models "this model/profile lacks the schema capability"
        self.request_id = request_id


class FakeAPITimeoutError(_FakeSDKError):
    def __init__(self, request_id: Optional[str] = None) -> None:
        self.request_id = request_id  # the sent request may already have an id even on timeout


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
        self.last_correlation_id: Optional[str] = None
        self.closed = False

    def create(self, *, model: str, max_tokens: int, prompt: str,
               correlation_id: Optional[str] = None) -> FakeSDKResponse:
        self.calls += 1
        self.last_max_tokens = max_tokens
        self.last_correlation_id = correlation_id
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
                model=request.approved_model, max_tokens=effective_max, prompt=request.prompt,
                correlation_id=request.correlation_id,  # safe correlation metadata sent to the Provider
            )
        except FakeAuthError as e:
            return ProviderAuthenticationError(status_code=e.status_code)
        except FakeRateLimitError as e:
            return ProviderRateLimited(retry_after=e.retry_after, provider_request_id=e.request_id)
        except FakeBadRequestError as e:
            return ProviderCapabilityError(status_code=e.status_code, detail=e.detail,
                                           config_scope=e.config_scope,
                                           provider_request_id=e.request_id)
        except FakeAPITimeoutError as e:
            return ProviderTimeout(provider_request_id=e.request_id)  # unknown usage; id preserved if any
        except FakeAPIConnectionError as e:
            return ProviderTransportError(detail=str(e) or "connection error")
        # Successful SDK response -> classify into the application union.
        usage = Usage(total_tokens=resp.total_tokens)  # None stays UNKNOWN, never coerced to 0
        if resp.refusal is not None:
            return ProviderRefusal(reason_code=resp.refusal, usage=usage,
                                   provider_request_id=resp.request_id)
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
    FAILED = "failed"                       # definite terminal business failure
    PENDING_RECONCILIATION = "pending_reconciliation"  # timeout/unknown execution: NOT terminal; a
    # matching late result may still be accepted through guarded completion (never auto-retried here)


class CostState(str, Enum):
    RESERVED = "reserved"
    SETTLED = "settled"
    RECONCILIATION_PENDING = "reconciliation_pending"  # unknown usage: reservation retained


class AttemptStatus(str, Enum):
    IN_FLIGHT = "in_flight"                    # claimed; Provider call issued; awaiting the outcome
    AWAITING_LATE_OUTCOME = "awaiting_late_outcome"  # timed out; the sent request may still return a late result
    CLOSED = "closed"                          # a terminal outcome was bound; no further outcome accepted


@dataclass
class Attempt:
    """A persisted, per-execution Attempt fact. A new Provider call is issued only after an
    ATOMIC claim creates exactly one IN_FLIGHT Attempt; the Provider outcome is then bound back
    to THIS Attempt (attempt_id + correlation_id, and provider_request_id when available)."""

    attempt_id: str
    job_id: str
    correlation_id: str
    status: AttemptStatus = AttemptStatus.IN_FLIGHT
    provider_request_id: Optional[str] = None


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
    attempts: dict[str, Attempt] = field(default_factory=dict)
    open_attempt_id: Optional[str] = None  # the single IN_FLIGHT/AWAITING attempt, if any


class CompletionOutcome(str, Enum):
    COMPLETED = "completed"
    NOOP_ZERO_ROWS = "noop_zero_rows"  # guarded transition saw non-running -> stop, do not overwrite


class JobExecutionStore:
    """In-memory model of the durable Job facts + a guarded completion transaction. Only the
    CompletionService may run `running -> succeeded`, persist a Result Artifact/usage/Event,
    and commit a short UoW."""

    def __init__(self) -> None:
        self.jobs: dict[str, ExecutionJob] = {}
        self._lock = threading.Lock()  # models the atomic pre-call claim (a guarded UPDATE)

    def start_running(self, job_id: str, *, tenant_id: str, contract: ExecutionContract,
                      reserved_tokens: int) -> ExecutionJob:
        job = ExecutionJob(job_id=job_id, tenant_id=tenant_id, contract=contract,
                           reserved_tokens=reserved_tokens)
        self.jobs[job_id] = job
        return job

    def claim_for_new_call(self, job_id: str, *, correlation_id: str) -> Optional[Attempt]:
        """ATOMIC pre-call claim: exactly ONE caller may acquire execution rights to START a
        new (paid) Provider call. Under the lock, a claim succeeds ONLY if the Job is RUNNING
        and there is no already-open Attempt; it then creates and persists exactly one
        IN_FLIGHT Attempt (attempt_id + correlation_id). Concurrent/re-entrant callers get
        `None` (a claim conflict) and must NOT call the Adapter/transport. Models a guarded
        `UPDATE ... WHERE status='running' AND open_attempt IS NULL RETURNING` so two Workers
        cannot both issue a paid call."""
        with self._lock:
            job = self.jobs.get(job_id)
            if job is None or job.status is not JobStatus.RUNNING:
                return None
            if job.open_attempt_id is not None:
                return None  # an Attempt is already IN_FLIGHT/AWAITING -> claim conflict
            attempt = Attempt(attempt_id=str(uuid.uuid4()), job_id=job_id, correlation_id=correlation_id)
            job.attempts[attempt.attempt_id] = attempt
            job.open_attempt_id = attempt.attempt_id
            return attempt

    def get_attempt(self, job_id: str, attempt_id: str) -> Optional[Attempt]:
        job = self.jobs.get(job_id)
        return None if job is None else job.attempts.get(attempt_id)

    def attach_provider_request_id(self, job_id: str, attempt_id: str, provider_request_id: str) -> None:
        """Record the Provider request id on the Attempt the FIRST time it is known (at send
        time or when a late outcome arrives). Never overwrites an already-recorded id."""
        attempt = self.get_attempt(job_id, attempt_id)
        if attempt is not None and attempt.provider_request_id is None:
            attempt.provider_request_id = provider_request_id

    def mark_attempt_awaiting_late(self, job_id: str, attempt_id: str) -> None:
        """Timeout: the sent request may still return a LATE result -> keep the Attempt OPEN
        (AWAITING_LATE_OUTCOME). It is NOT a retriable new call."""
        attempt = self.get_attempt(job_id, attempt_id)
        if attempt is not None:
            attempt.status = AttemptStatus.AWAITING_LATE_OUTCOME

    def close_attempt(self, job_id: str, attempt_id: str) -> None:
        """A terminal outcome was bound to the Attempt -> CLOSED; it accepts no further outcome."""
        job = self.jobs.get(job_id)
        if job is None:
            return
        attempt = job.attempts.get(attempt_id)
        if attempt is not None:
            attempt.status = AttemptStatus.CLOSED
        if job.open_attempt_id == attempt_id:
            job.open_attempt_id = None


class CompletionService:
    """Owns the guarded `running -> succeeded` transition + short UoW. Business execution
    success and COST settlement are SEPARATE axes: a valid result may succeed even when usage
    is unknown (retain the reservation, hold reconciliation_pending)."""

    def __init__(self, store: JobExecutionStore) -> None:
        self._store = store

    def complete_success(self, job_id: str, *, domain_result: dict, usage: Usage,
                         provider_request_id: Optional[str]) -> CompletionOutcome:
        job = self._store.jobs.get(job_id)
        # Guarded transition: only a still-completable job may complete — RUNNING, or a
        # PENDING_RECONCILIATION job whose real outcome/usage was unknown (e.g. after a
        # timeout) and for which a matching late result now arrives. A terminal SUCCEEDED/
        # FAILED job yields zero rows -> STOP (duplicate/stale/cancelled/changed), never overwrite.
        if job is None or job.status not in (JobStatus.RUNNING, JobStatus.PENDING_RECONCILIATION):
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
                           evidence: Optional[dict] = None,
                           mark_failed: bool = True) -> None:
        """Record a classified non-success Attempt/Event WITHOUT a success transition, Result
        Artifact, or success write. Safe metadata only (no raw payload/prompt/secret)."""
        job = self._store.jobs.get(job_id)
        if job is None:
            return
        if mark_failed and job.status in (JobStatus.RUNNING, JobStatus.PENDING_RECONCILIATION):
            job.status = JobStatus.FAILED
        event = {"type": "job.attempt_failed", "job_id": job_id,
                 "classification": classification,
                 "correlation_id": job.contract.correlation_id}
        if provider_request_id is not None:
            event["provider_request_id"] = provider_request_id
        if retry_after is not None:
            event["retry_after"] = retry_after  # safe downstream metadata; Day56 owns policy
        if evidence is not None:
            event["evidence"] = dict(evidence)  # safe config/schema/model/profile facts only
        job.events.append(event)

    def record_cost(self, job_id: str, usage: Usage) -> None:
        """Day52-compatible cost handling for a NON-success Outcome: an invalid/refused/
        incomplete result does NOT mean the Provider did not charge. Known usage is retained
        as the EXACT settled amount; unknown usage holds reconciliation_pending (reservation
        retained, never released, never fabricated as zero). Never a success Artifact."""
        job = self._store.jobs.get(job_id)
        if job is None:
            return
        if usage.is_known:
            job.cost_state = CostState.SETTLED
            job.settled_tokens = usage.total_tokens
        else:
            job.cost_state = CostState.RECONCILIATION_PENDING
        job.events.append({"type": "job.cost_recorded", "job_id": job_id,
                           "usage_total_tokens": usage.total_tokens,  # may be None (explicit unknown)
                           "cost_state": job.cost_state.value,
                           "correlation_id": job.contract.correlation_id})

    def record_timeout_pending(self, job_id: str, *, provider_request_id: Optional[str] = None) -> None:
        """A Provider timeout means whether the Provider ran, its result, and its usage are all
        UNKNOWN. Do NOT write a definite terminal FAILED (that would block a legitimate late
        result and invite an unprotected re-run). Move to the non-terminal PENDING_RECONCILIATION
        lifecycle, retain the reservation (unknown usage held reconciliation_pending, never zero,
        never auto-released), and record safe correlation evidence. No Day56 retry is triggered."""
        job = self._store.jobs.get(job_id)
        if job is None:
            return
        if job.status in (JobStatus.RUNNING, JobStatus.PENDING_RECONCILIATION):
            job.status = JobStatus.PENDING_RECONCILIATION
        job.cost_state = CostState.RECONCILIATION_PENDING
        event = {"type": "job.provider_timeout_pending_reconciliation", "job_id": job_id,
                 "classification": "provider_timeout_unknown_execution_and_usage",
                 "correlation_id": job.contract.correlation_id}
        if provider_request_id is not None:
            event["provider_request_id"] = provider_request_id
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
    model_max_output_tokens: Optional[int] = None  # model/server hard cap; effective max never exceeds it
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
    CONTRACT_MISMATCH = "contract_mismatch"  # request inconsistent with the persisted contract; no call made
    PRECALL_BLOCKED = "precall_blocked"      # Job not eligible to START a new Provider call; transport NOT called
    LATE_OUTCOME_REJECTED = "late_outcome_rejected"  # ingested late outcome failed job/correlation/contract checks
    COMPLETION_NOOP = "completion_noop"


@dataclass(frozen=True)
class ExecutionResult:
    decision: ExecutionDecision
    completion: Optional[CompletionOutcome] = None
    validation: Optional[ValidationResult] = None
    reason: str = ""
    attempt_id: Optional[str] = None


# ===========================================================================
# 7. Application Service — orchestrates generate -> validate -> guarded completion
# ===========================================================================
def bind_request_to_contract(
    request: ProviderRequest, contract: ExecutionContract, *, model_hard_cap: Optional[int] = None,
) -> tuple[Optional[ProviderRequest], Optional[str]]:
    """Constrain the outgoing Provider call to the PERSISTED Job execution contract. A caller
    must not pick the model, schema, task type, provider profile, or an enlarged token budget.
    Any inconsistency on an authoritative field is a pre-call SAFE REJECTION (no transport call).
    The token budget is SAFELY TIGHTENED to `min(request, contract bound, model/server hard cap)`
    — never enlarged. Returns `(bound_request, None)` or `(None, mismatch_reason)`."""
    for field_name, req_val, con_val in (
        ("approved_model", request.approved_model, contract.approved_model),
        ("schema_name", request.schema_name, contract.schema_name),
        ("schema_version", request.schema_version, contract.schema_version),
        ("task_type", request.task_type, contract.task_type),
        ("provider_profile_version", request.provider_profile_version, contract.provider_profile_version),
    ):
        if req_val != con_val:
            return None, f"contract_mismatch:{field_name}"  # reject BEFORE any Provider call
    caps = [request.max_output_tokens, contract.max_output_bound]
    if model_hard_cap is not None:
        caps.append(model_hard_cap)
    effective_max = min(caps)  # tighten only; the client can never enlarge the per-Job bound
    if effective_max <= 0:
        return None, "contract_mismatch:max_output_bound"
    bound = ProviderRequest(
        job_id=request.job_id, tenant_id=request.tenant_id, task_type=contract.task_type,
        schema_name=contract.schema_name, schema_version=contract.schema_version,
        approved_model=contract.approved_model, provider_profile_version=contract.provider_profile_version,
        max_output_tokens=effective_max, correlation_id=contract.correlation_id, prompt=request.prompt,
    )
    return bound, None


def _dispatch_outcome(
    outcome: ProviderOutcome,
    *,
    job_id: str,
    contract: ExecutionContract,
    validator: StructuredOutputValidator,
    completion: CompletionService,
    provider_config: ProviderConfig,
) -> ExecutionResult:
    """Process a ProviderOutcome (from a fresh call OR an ingested late result). Validates the
    payload against the PERSISTED contract and routes to guarded completion / classification.
    Never calls the Adapter or any transport itself."""

    def _evidence(request_id: Optional[str]) -> dict:
        ev = {"schema_name": contract.schema_name, "schema_version": contract.schema_version,
              "approved_model": contract.approved_model,
              "provider_profile_version": contract.provider_profile_version}
        if request_id is not None:
            ev["provider_request_id"] = request_id
        return ev

    if isinstance(outcome, ProviderSuccess):
        result = validator.validate(contract.schema_name, contract.schema_version, outcome.raw_payload)
        if result.outcome is ValidationOutcome.VALID:
            assert result.domain_result is not None
            co = completion.complete_success(
                job_id, domain_result=result.domain_result, usage=outcome.usage,
                provider_request_id=outcome.provider_request_id,
            )
            decision = (ExecutionDecision.SUCCEEDED if co is CompletionOutcome.COMPLETED
                        else ExecutionDecision.COMPLETION_NOOP)
            return ExecutionResult(decision, completion=co, validation=result)
        # Invalid output NEVER calls completion success — but the Provider still CHARGED, so the
        # exact (known) usage is settled/reconciled, never dropped, never fabricated as zero.
        completion.record_non_success(job_id, classification=f"validation:{result.outcome.value}",
                                      provider_request_id=outcome.provider_request_id)
        completion.record_cost(job_id, outcome.usage)
        return ExecutionResult(ExecutionDecision.VALIDATION_FAILED, validation=result)

    if isinstance(outcome, ProviderRefusal):
        completion.record_non_success(job_id, classification=f"provider_refusal:{outcome.reason_code}",
                                      provider_request_id=outcome.provider_request_id)
        completion.record_cost(job_id, outcome.usage)  # refusal usage is never dropped
        return ExecutionResult(ExecutionDecision.REFUSED)

    if isinstance(outcome, ProviderIncomplete):
        completion.record_non_success(job_id, classification=f"provider_incomplete:{outcome.reason}",
                                      provider_request_id=outcome.provider_request_id)
        completion.record_cost(job_id, outcome.usage)  # known -> settle; unknown -> reconciliation_pending
        return ExecutionResult(ExecutionDecision.INCOMPLETE)

    if isinstance(outcome, ProviderTimeout):
        # NOT a terminal FAILED: whether the Provider ran, its result, and usage are unknown.
        completion.record_timeout_pending(job_id)
        return ExecutionResult(ExecutionDecision.TIMEOUT_UNKNOWN_USAGE)

    if isinstance(outcome, ProviderAuthenticationError):
        # Configuration/authentication failure: STOP new calls with this config; keep evidence.
        provider_config.disable(f"provider_auth_{outcome.status_code}")
        completion.record_non_success(job_id,
                                      classification=f"provider_auth_config_failure:{outcome.status_code}",
                                      evidence=_evidence(None))
        return ExecutionResult(ExecutionDecision.AUTH_CONFIG_FAILURE)

    if isinstance(outcome, ProviderRateLimited):
        # A downstream Provider 429 for this Job/Attempt — NOT a retroactive client 429.
        completion.record_non_success(job_id, classification="provider_rate_limited",
                                      provider_request_id=outcome.provider_request_id,
                                      retry_after=outcome.retry_after)
        return ExecutionResult(ExecutionDecision.RATE_LIMITED)

    if isinstance(outcome, ProviderCapabilityError):
        # Distinguish a CONFIG-WIDE capability failure (this model/profile cannot honor the
        # controlled schema) from a single-request 400. A config-wide failure fails the config
        # CLOSED so no further NEW call uses it; a single-request 400 does not close the config.
        # Neither is a user-input error; both keep safe schema/model/profile/correlation evidence.
        if outcome.config_scope:
            provider_config.disable(f"provider_capability_config_{outcome.status_code}")
            classification = f"provider_capability_config_failure:{outcome.status_code}"
        else:
            classification = f"provider_capability_request_failure:{outcome.status_code}"
        completion.record_non_success(job_id, classification=classification,
                                      provider_request_id=outcome.provider_request_id,
                                      evidence=_evidence(outcome.provider_request_id))
        return ExecutionResult(ExecutionDecision.CAPABILITY_FAILURE)

    if isinstance(outcome, ProviderTransportError):
        completion.record_non_success(job_id, classification="provider_transport_error")
        return ExecutionResult(ExecutionDecision.TRANSPORT_ERROR)

    raise AssertionError(f"unhandled ProviderOutcome: {type(outcome).__name__}")


def execute_job(
    request: ProviderRequest,
    *,
    adapter: AIProvider,
    validator: StructuredOutputValidator,
    store: JobExecutionStore,
    completion: CompletionService,
    provider_config: ProviderConfig,
) -> ExecutionResult:
    """PATH A — START a new authorized Provider call. Order: ATOMICALLY claim execution rights
    (create the IN_FLIGHT Attempt) -> (only then) make the external Provider call -> bind the
    outcome to that Attempt -> guarded completion. The atomic claim runs BEFORE `adapter.generate`,
    so (a) a terminal (SUCCEEDED/FAILED) or PENDING_RECONCILIATION Job never re-triggers a paid
    call, and (b) two concurrent/re-entrant callers cannot both issue a paid call — the loser gets
    PRECALL_BLOCKED with transport calls == 0. A late result for an already-issued request must use
    `ingest_late_outcome` (PATH B), which does NOT call the Adapter."""
    if provider_config.disabled:
        # Current Settings govern NEW calls: refuse to start one with a disabled config.
        return ExecutionResult(ExecutionDecision.BLOCKED_CONFIG_DISABLED)

    job = store.jobs.get(request.job_id)
    if job is None:
        return ExecutionResult(ExecutionDecision.PRECALL_BLOCKED, reason="unknown_job")

    # ATOMIC PRE-CALL CLAIM — BEFORE any transport/Provider call. Exactly one caller wins.
    attempt = store.claim_for_new_call(request.job_id, correlation_id=job.contract.correlation_id)
    if attempt is None:
        # Not RUNNING (terminal/pending) OR another Attempt is already in flight -> claim conflict.
        reason = "claim_conflict" if job.status is JobStatus.RUNNING else job.status.value
        return ExecutionResult(ExecutionDecision.PRECALL_BLOCKED, reason=reason)

    contract = job.contract
    bound, mismatch = bind_request_to_contract(
        request, contract, model_hard_cap=provider_config.model_max_output_tokens
    )
    if bound is None:
        # Inconsistent request -> release the claim; no transport/network call was made.
        store.close_attempt(request.job_id, attempt.attempt_id)
        completion.record_non_success(request.job_id, classification=mismatch or "contract_mismatch",
                                      mark_failed=False)
        return ExecutionResult(ExecutionDecision.CONTRACT_MISMATCH, reason=mismatch or "contract_mismatch",
                               attempt_id=attempt.attempt_id)

    outcome = adapter.generate(bound)  # reached ONLY by the claim winner, after contract binding
    outcome_request_id = getattr(outcome, "provider_request_id", None)
    if outcome_request_id is not None:
        store.attach_provider_request_id(request.job_id, attempt.attempt_id, outcome_request_id)

    result = _dispatch_outcome(outcome, job_id=request.job_id, contract=contract,
                               validator=validator, completion=completion, provider_config=provider_config)

    # Bind the outcome to the Attempt: a timeout keeps it OPEN (awaiting a late result); every
    # other outcome CLOSES it (a terminal fact was bound).
    if isinstance(outcome, ProviderTimeout):
        store.mark_attempt_awaiting_late(request.job_id, attempt.attempt_id)
    else:
        store.close_attempt(request.job_id, attempt.attempt_id)
    return replace(result, attempt_id=attempt.attempt_id)


def ingest_late_outcome(
    outcome: ProviderOutcome,
    *,
    job_id: str,
    attempt_id: str,
    correlation_id: str,
    store: JobExecutionStore,
    validator: StructuredOutputValidator,
    completion: CompletionService,
    provider_config: ProviderConfig,
    provider_request_id: Optional[str] = None,
) -> ExecutionResult:
    """PATH B — ingest an ALREADY-ISSUED Provider outcome (a callback-like late result) for a
    prior request. This does NOT call the Adapter or any transport. It locates the PERSISTED
    Attempt the outcome claims to belong to and verifies the association before touching any
    fact:

      * a TERMINAL Job (SUCCEEDED/FAILED) -> guarded no-op (COMPLETION_NOOP): no Event, cost,
        Result Artifact, status, or reservation change (a separate idempotent reconciliation
        ledger would be required for post-terminal cost settlement — not modeled here);
      * the Attempt must exist, be OPEN (IN_FLIGHT/AWAITING_LATE_OUTCOME), and match this Job;
      * `attempt_id` + `correlation_id` must match the persisted Attempt (and the contract);
      * `provider_request_id`: if the Attempt already recorded one, the incoming id must match;
        if none was recorded yet (e.g. after a timeout), the incoming id is recorded ONCE
        (controlled first-record) — a DIFFERENT Attempt's result is never accepted;
      * only then does it route through the SAME guarded completion path.

    A mismatch is `LATE_OUTCOME_REJECTED` with no completion/overwrite/transport. This is the
    correct 'late result after a timeout' flow — NOT a second `execute_job` (which would issue a
    second paid Provider call). Day54 owns the real callback/streaming/cancellation protocol."""
    job = store.jobs.get(job_id)
    if job is None:
        return ExecutionResult(ExecutionDecision.LATE_OUTCOME_REJECTED, reason="unknown_job")

    # P1-3: ANY late outcome on a TERMINAL Job is a guarded no-op — never rewrite durable facts.
    if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
        return ExecutionResult(ExecutionDecision.COMPLETION_NOOP, reason="terminal_job", attempt_id=attempt_id)

    contract = job.contract
    attempt = job.attempts.get(attempt_id)
    if attempt is None:
        return ExecutionResult(ExecutionDecision.LATE_OUTCOME_REJECTED, reason="attempt_not_found",
                               attempt_id=attempt_id)
    if attempt.status is AttemptStatus.CLOSED:
        return ExecutionResult(ExecutionDecision.LATE_OUTCOME_REJECTED, reason="attempt_closed",
                               attempt_id=attempt_id)
    if attempt.correlation_id != correlation_id or correlation_id != contract.correlation_id:
        return ExecutionResult(ExecutionDecision.LATE_OUTCOME_REJECTED, reason="correlation_mismatch",
                               attempt_id=attempt_id)

    incoming_prid = provider_request_id if provider_request_id is not None \
        else getattr(outcome, "provider_request_id", None)
    if attempt.provider_request_id is not None:
        if incoming_prid is not None and incoming_prid != attempt.provider_request_id:
            return ExecutionResult(ExecutionDecision.LATE_OUTCOME_REJECTED,
                                   reason="provider_request_id_mismatch", attempt_id=attempt_id)
    elif incoming_prid is not None:
        attempt.provider_request_id = incoming_prid  # controlled first-record of the request id

    # Associated + contract-known -> guarded completion (no Adapter/transport call).
    result = _dispatch_outcome(outcome, job_id=job_id, contract=contract, validator=validator,
                               completion=completion, provider_config=provider_config)
    # If the Job resolved to a terminal state, CLOSE the Attempt (no further outcome accepted).
    if store.jobs[job_id].status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
        store.close_attempt(job_id, attempt_id)
    return replace(result, attempt_id=attempt_id)
