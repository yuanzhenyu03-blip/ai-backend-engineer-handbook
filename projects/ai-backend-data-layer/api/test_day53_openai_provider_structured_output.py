"""Day53 — tests for OpenAI SDK, Provider Boundaries and Structured Output.

EVIDENCE LABEL: REAL Pydantic v2 strict validation + an in-memory model of Adapter ->
Validator -> CompletionService control flow with an INJECTED FAKE transport (modeled vendor
exceptions). This proves application control flow + the real validation gate ONLY. NOT the
real openai SDK / network / Provider, NOT real PostgreSQL / Redis / Celery Worker, NOT
FastAPI wire, NOT integration/production. No real api_key, prompt, or Provider response is
persisted or logged.
"""

import json

import pytest

from day53_openai_provider_structured_output import (
    AIProvider,
    CompletionOutcome,
    CompletionService,
    CostState,
    ExecutionContract,
    ExecutionDecision,
    FakeAPIConnectionError,
    FakeAPITimeoutError,
    FakeAuthError,
    FakeBadRequestError,
    FakeOpenAITransport,
    FakeRateLimitError,
    FakeSDKResponse,
    JobExecutionStore,
    JobStatus,
    OpenAICompatibleAdapter,
    ProviderAuthenticationError,
    ProviderCapabilityError,
    ProviderConfig,
    ProviderIncomplete,
    ProviderRateLimited,
    ProviderRefusal,
    ProviderRequest,
    ProviderSuccess,
    ProviderTimeout,
    SchemaRegistry,
    StructuredOutputValidator,
    Usage,
    ValidationOutcome,
    execute_job,
)

PROMPT = "SENSITIVE-PROMPT-do-not-persist-42"
VALID_V1 = {"summary": "Concise findings.", "citations": ["doc-1", "doc-2"], "confidence": 0.9}


def _request(**over):
    base = dict(
        job_id="job-1", tenant_id="tenant-a", task_type="research_summary",
        schema_name="research_summary", schema_version="v1", approved_model="gpt-approved",
        provider_profile_version="pp-1", max_output_tokens=5000, correlation_id="corr-1",
        prompt=PROMPT,
    )
    base.update(over)
    return ProviderRequest(**base)


def _contract(**over):
    base = dict(
        schema_name="research_summary", schema_version="v1", approved_model="gpt-approved",
        provider_profile_version="pp-1", task_type="research_summary", max_output_bound=5000,
        correlation_id="corr-1",
    )
    base.update(over)
    return ExecutionContract(**base)


def _wire(transport, *, job_id="job-1", reserved=5000, contract=None, model="gpt-approved"):
    store = JobExecutionStore()
    store.start_running(job_id, tenant_id="tenant-a", contract=contract or _contract(),
                        reserved_tokens=reserved)
    adapter = OpenAICompatibleAdapter(transport)
    validator = StructuredOutputValidator(SchemaRegistry())
    completion = CompletionService(store)
    cfg = ProviderConfig(approved_model=model, provider_profile_version="pp-1")
    return store, adapter, validator, completion, cfg


def _exec(request, store, adapter, validator, completion, cfg):
    return execute_job(request, adapter=adapter, validator=validator, store=store,
                       completion=completion, provider_config=cfg)


# ===========================================================================
# Adapter boundary: SDK exceptions -> ProviderOutcome union (no SDK leak)
# ===========================================================================
def test_adapter_reuses_one_client_and_passes_the_job_cap():
    t = FakeOpenAITransport(response=FakeSDKResponse(payload=VALID_V1, total_tokens=1200))
    adapter = OpenAICompatibleAdapter(t, default_max_output_tokens=8000)
    req = _request(max_output_tokens=5000)
    adapter.generate(req)
    adapter.generate(req)
    assert t.calls == 2                 # same lifespan-owned client reused, not created per call
    assert t.last_max_tokens == 5000    # Job cap (5000) wins over the 8000 adapter default


def test_adapter_never_enlarges_beyond_job_cap():
    t = FakeOpenAITransport(response=FakeSDKResponse(payload=VALID_V1, total_tokens=10))
    adapter = OpenAICompatibleAdapter(t, default_max_output_tokens=8000)
    adapter.generate(_request(max_output_tokens=3000))
    assert t.last_max_tokens == 3000    # min(3000, 8000); adapter default is a ceiling, not an enlargement


def test_adapter_maps_each_sdk_exception_to_the_union():
    def out(error):
        return OpenAICompatibleAdapter(FakeOpenAITransport(error=error)).generate(_request())
    assert isinstance(out(FakeAuthError(401)), ProviderAuthenticationError)
    assert isinstance(out(FakeRateLimitError(retry_after="12")), ProviderRateLimited)
    assert isinstance(out(FakeBadRequestError(status_code=400)), ProviderCapabilityError)
    assert isinstance(out(FakeAPITimeoutError()), ProviderTimeout)
    assert isinstance(out(FakeAPIConnectionError()), __import__("day53_openai_provider_structured_output").ProviderTransportError)


def test_adapter_unknown_usage_is_not_coerced_to_zero():
    t = FakeOpenAITransport(response=FakeSDKResponse(payload=VALID_V1, total_tokens=None))
    outcome = OpenAICompatibleAdapter(t).generate(_request())
    assert isinstance(outcome, ProviderSuccess)
    assert outcome.usage.total_tokens is None and outcome.usage.is_known is False  # explicit unknown


# ===========================================================================
# Valid structured output -> completion called exactly once
# ===========================================================================
def test_valid_result_completes_once_with_settled_cost():
    t = FakeOpenAITransport(response=FakeSDKResponse(payload=VALID_V1, total_tokens=1200,
                                                     request_id="rq-1"))
    store, adapter, validator, completion, cfg = _wire(t)
    res = _exec(_request(), store, adapter, validator, completion, cfg)
    job = store.jobs["job-1"]
    assert res.decision is ExecutionDecision.SUCCEEDED and res.completion is CompletionOutcome.COMPLETED
    assert job.status is JobStatus.SUCCEEDED
    assert job.cost_state is CostState.SETTLED and job.settled_tokens == 1200
    assert job.result_artifact is not None
    assert [e["type"] for e in job.events] == ["job.succeeded"]  # exactly one success event


def test_guarded_completion_zero_rows_stops_no_double_write():
    t = FakeOpenAITransport(response=FakeSDKResponse(payload=VALID_V1, total_tokens=1200))
    store, adapter, validator, completion, cfg = _wire(t)
    _exec(_request(), store, adapter, validator, completion, cfg)  # succeeds -> now not RUNNING
    artifact_before = store.jobs["job-1"].result_artifact
    # A duplicate/stale completion attempt sees a non-running job -> zero rows -> stop.
    res2 = _exec(_request(), store, adapter, validator, completion, cfg)
    assert res2.decision is ExecutionDecision.COMPLETION_NOOP and res2.completion is CompletionOutcome.NOOP_ZERO_ROWS
    job = store.jobs["job-1"]
    assert job.result_artifact is artifact_before                # not overwritten
    assert [e["type"] for e in job.events] == ["job.succeeded"]  # no second success event


def test_valid_output_with_unknown_usage_succeeds_but_holds_cost_reconciliation():
    # Correction: business execution success and cost settlement are SEPARATE axes.
    t = FakeOpenAITransport(response=FakeSDKResponse(payload=VALID_V1, total_tokens=None))
    store, adapter, validator, completion, cfg = _wire(t)
    res = _exec(_request(), store, adapter, validator, completion, cfg)
    job = store.jobs["job-1"]
    assert res.decision is ExecutionDecision.SUCCEEDED and job.status is JobStatus.SUCCEEDED
    assert job.cost_state is CostState.RECONCILIATION_PENDING   # reservation retained; unknown != zero
    assert job.settled_tokens is None
    assert job.result_artifact["usage_total_tokens"] is None    # explicit unknown, not 0


# ===========================================================================
# Invalid structured output -> NEVER calls completion
# ===========================================================================
def test_missing_required_field_does_not_call_completion():
    bad = {"summary": "x", "confidence": 0.5}  # missing required citations
    t = FakeOpenAITransport(response=FakeSDKResponse(payload=bad, total_tokens=100))
    store, adapter, validator, completion, cfg = _wire(t)
    res = _exec(_request(), store, adapter, validator, completion, cfg)
    job = store.jobs["job-1"]
    assert res.decision is ExecutionDecision.VALIDATION_FAILED
    assert res.validation.outcome is ValidationOutcome.CONTRACT_VIOLATION
    assert "citations" in res.validation.error_fields
    assert job.status is JobStatus.FAILED                       # no success transition
    assert job.result_artifact is None                          # no Result Artifact
    assert "job.succeeded" not in [e["type"] for e in job.events]


def test_forbidden_extra_field_does_not_call_completion():
    bad = dict(VALID_V1, debug_prompt="leak")  # forbidden extra field
    t = FakeOpenAITransport(response=FakeSDKResponse(payload=bad, total_tokens=100))
    store, adapter, validator, completion, cfg = _wire(t)
    res = _exec(_request(), store, adapter, validator, completion, cfg)
    job = store.jobs["job-1"]
    assert res.decision is ExecutionDecision.VALIDATION_FAILED
    assert "debug_prompt" in res.validation.error_fields
    assert job.status is JobStatus.FAILED and job.result_artifact is None


# ===========================================================================
# Non-success Provider outcomes -> classified, no success completion
# ===========================================================================
def test_provider_refusal_is_classified_non_success():
    t = FakeOpenAITransport(response=FakeSDKResponse(payload={}, refusal="policy"))
    store, adapter, validator, completion, cfg = _wire(t)
    res = _exec(_request(), store, adapter, validator, completion, cfg)
    assert res.decision is ExecutionDecision.REFUSED
    assert store.jobs["job-1"].result_artifact is None


def test_provider_incomplete_is_classified_non_success():
    t = FakeOpenAITransport(response=FakeSDKResponse(payload=VALID_V1, finish_reason="length"))
    store, adapter, validator, completion, cfg = _wire(t)
    res = _exec(_request(), store, adapter, validator, completion, cfg)
    assert res.decision is ExecutionDecision.INCOMPLETE
    assert store.jobs["job-1"].result_artifact is None


def test_provider_timeout_retains_reservation_as_reconciliation_pending():
    t = FakeOpenAITransport(error=FakeAPITimeoutError())
    store, adapter, validator, completion, cfg = _wire(t)
    res = _exec(_request(), store, adapter, validator, completion, cfg)
    job = store.jobs["job-1"]
    assert res.decision is ExecutionDecision.TIMEOUT_UNKNOWN_USAGE
    assert job.cost_state is CostState.RECONCILIATION_PENDING   # unknown usage retained, not zeroed
    assert job.result_artifact is None


def test_provider_auth_failure_disables_new_calls_and_keeps_evidence():
    t = FakeOpenAITransport(error=FakeAuthError(401))
    store, adapter, validator, completion, cfg = _wire(t)
    res = _exec(_request(), store, adapter, validator, completion, cfg)
    assert res.decision is ExecutionDecision.AUTH_CONFIG_FAILURE
    assert cfg.disabled is True and "401" in cfg.disabled_reason   # stop NEW calls with this config
    # A subsequent execution is blocked before any new Provider call.
    t2 = FakeOpenAITransport(response=FakeSDKResponse(payload=VALID_V1, total_tokens=1))
    store2, adapter2, validator2, completion2, _ = _wire(t2)
    res2 = execute_job(_request(), adapter=adapter2, validator=validator2, store=store2,
                       completion=completion2, provider_config=cfg)
    assert res2.decision is ExecutionDecision.BLOCKED_CONFIG_DISABLED and t2.calls == 0


def test_provider_429_is_downstream_job_event_not_client_429():
    t = FakeOpenAITransport(error=FakeRateLimitError(retry_after="30", request_id="rq-9"))
    store, adapter, validator, completion, cfg = _wire(t)
    res = _exec(_request(), store, adapter, validator, completion, cfg)
    job = store.jobs["job-1"]
    assert res.decision is ExecutionDecision.RATE_LIMITED
    ev = [e for e in job.events if e["classification"] == "provider_rate_limited"][0]
    assert ev["retry_after"] == "30"        # safe metadata preserved; Day56 owns policy
    assert job.result_artifact is None


# ===========================================================================
# Server-owned versioned schema binding
# ===========================================================================
def test_schema_version_mismatch_v2_payload_fails_a_v1_job():
    v2_payload = dict(VALID_V1, evidence_grade="A")  # valid v2, forbidden-extra for v1
    t = FakeOpenAITransport(response=FakeSDKResponse(payload=v2_payload, total_tokens=100))
    store, adapter, validator, completion, cfg = _wire(t, contract=_contract(schema_version="v1"))
    res = _exec(_request(schema_version="v1"), store, adapter, validator, completion, cfg)
    assert res.decision is ExecutionDecision.VALIDATION_FAILED           # v2 must not satisfy v1
    assert store.jobs["job-1"].result_artifact is None


def test_v2_job_accepts_v2_but_v1_job_rejects_same_payload():
    v2_payload = dict(VALID_V1, evidence_grade="A")
    # A Job contracted v2 accepts the v2 payload.
    t2 = FakeOpenAITransport(response=FakeSDKResponse(payload=v2_payload, total_tokens=50))
    store2, adapter2, validator2, completion2, cfg2 = _wire(t2, contract=_contract(schema_version="v2"))
    r2 = _exec(_request(schema_version="v2"), store2, adapter2, validator2, completion2, cfg2)
    assert r2.decision is ExecutionDecision.SUCCEEDED
    # The same payload against a v1 Job is rejected (no silent cross-version satisfaction).
    t1 = FakeOpenAITransport(response=FakeSDKResponse(payload=v2_payload, total_tokens=50))
    store1, adapter1, validator1, completion1, cfg1 = _wire(t1, contract=_contract(schema_version="v1"))
    r1 = _exec(_request(schema_version="v1"), store1, adapter1, validator1, completion1, cfg1)
    assert r1.decision is ExecutionDecision.VALIDATION_FAILED


def test_unknown_schema_version_is_classified_not_guessed():
    t = FakeOpenAITransport(response=FakeSDKResponse(payload=VALID_V1, total_tokens=10))
    store, adapter, validator, completion, cfg = _wire(t, contract=_contract(schema_version="v9"))
    res = _exec(_request(schema_version="v9"), store, adapter, validator, completion, cfg)
    assert res.decision is ExecutionDecision.VALIDATION_FAILED
    assert res.validation.outcome is ValidationOutcome.SCHEMA_NOT_FOUND   # no guessed downgrade


# ===========================================================================
# Raw-data minimization: no secrets/prompt/raw payload in durable facts or logs
# ===========================================================================
def test_no_raw_prompt_secret_or_debug_fields_in_persistence():
    payload = dict(VALID_V1)  # valid payloads carry no debug field
    t = FakeOpenAITransport(response=FakeSDKResponse(payload=payload, total_tokens=1200))
    store, adapter, validator, completion, cfg = _wire(t)
    _exec(_request(prompt=PROMPT), store, adapter, validator, completion, cfg)
    job = store.jobs["job-1"]
    blob = json.dumps({"artifact": job.result_artifact, "events": job.events})
    assert PROMPT not in blob                 # raw prompt never persisted
    assert "api_key" not in blob and "base_url" not in blob
    assert "debug_prompt" not in blob         # no raw/forbidden Provider fields
    # Only validated domain fields + safe metadata are present.
    assert set(job.result_artifact["domain_result"]) == {"summary", "citations", "confidence"}


# ===========================================================================
# Integrated rollout/rollback exercise: config rollback != business-fact rollback
# ===========================================================================
def test_config_rollback_does_not_invalidate_a_valid_inflight_result():
    # New calls on the bad model get a 400 capability failure...
    bad_new = FakeOpenAITransport(error=FakeBadRequestError(detail="model lacks research_summary.v1", status_code=400))
    store, adapter, validator, completion, cfg = _wire(bad_new, model="bad-model")
    store.start_running("job-new", tenant_id="tenant-a", contract=_contract(correlation_id="c-new"),
                        reserved_tokens=5000)
    r_new = _exec(_request(job_id="job-new"), store, adapter, validator, completion, cfg)
    assert r_new.decision is ExecutionDecision.CAPABILITY_FAILURE
    assert store.jobs["job-new"].result_artifact is None
    # ...but a legitimate OLD in-flight v1 result (distinct call) still validates against its
    # persisted contract and is accepted through guarded completion. Config rollback affects
    # only future calls; it does not roll back an already-earned business fact.
    good_old = FakeOpenAITransport(response=FakeSDKResponse(payload=VALID_V1, total_tokens=900))
    adapter_old = OpenAICompatibleAdapter(good_old)
    store.start_running("job-old", tenant_id="tenant-a", contract=_contract(correlation_id="c-old"),
                        reserved_tokens=5000)
    r_old = execute_job(_request(job_id="job-old"), adapter=adapter_old, validator=validator,
                        store=store, completion=completion,
                        provider_config=ProviderConfig(approved_model="gpt-approved",
                                                       provider_profile_version="pp-1"))
    assert r_old.decision is ExecutionDecision.SUCCEEDED
    assert store.jobs["job-old"].status is JobStatus.SUCCEEDED


# ===========================================================================
# Evidence label present (honesty)
# ===========================================================================
def test_evidence_label_is_validation_control_flow_not_real_provider():
    import day53_openai_provider_structured_output as m
    doc = m.__doc__ or ""
    assert "REAL Pydantic v2" in doc and "NOT RUN" in doc
    assert "real `openai` SDK" in doc and "PostgreSQL" in doc
