"""Deterministic contract tests for the optional Day106 L3B adapter."""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from urllib.error import URLError
from urllib.request import Request

import pytest

from examples.day106_capstone_support import (
    build_canonical_day101_fixture,
    execute_day101_query,
    execute_grounding_from_day101,
    refund_window_claim,
)
from rag_chunking_contracts import stable_hash
from rag_grounding_adapters import GroundingProviderError
from rag_grounding_contracts import (
    Day102FailureReason,
    GeneratedAnswer,
    GroundingBundle,
    GroundingContract,
    SourceWindow,
)
from rag_openai_responses_adapter import (
    MAX_OUTPUT_TOKENS,
    OPENAI_RESPONSES_ENDPOINT,
    OPENAI_RESPONSES_MODEL,
    OPENAI_REASONING_EFFORT,
    OpenAIInvocationBinding,
    OpenAIResponseTooLarge,
    OpenAIResponsesAnswerProvider,
    OpenAIResponsesHTTPResponse,
    OpenAIResponsesRequest,
    OpenAIResponsesTransport,
    OpenAITransportError,
    OpenAITransportNotSent,
    OpenAITransportTimeout,
    ProviderCallBudget,
    UrllibOpenAIResponsesTransport,
    day106_openai_grounding_contract,
    openai_model_config_digest,
    provider_request_idempotency_digest,
)
from rag_retrieval_contracts import CandidateIdentity


ANSWER = "Synthetic refund evidence."
RAW_PROVIDER_ID = "resp_sensitive_provider_identifier"


class FakeHTTPTransport:
    def __init__(
        self,
        *,
        response: OpenAIResponsesHTTPResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.requests: list[OpenAIResponsesRequest] = []

    def send(
        self,
        request: OpenAIResponsesRequest,
    ) -> OpenAIResponsesHTTPResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("fake response is required")
        return self.response


def _contract() -> GroundingContract:
    return day106_openai_grounding_contract()


def _bundle(contract: GroundingContract) -> GroundingBundle:
    identity = CandidateIdentity(
        tenant_id="tenant-l3b",
        document_id="document:refund",
        document_version_id="document:refund:v1",
        chunk_set_id="chunk-set:l3b:v1",
        chunk_id="chunk:refund",
        occurrence_id="occurrence:refund",
        provenance_fingerprint=stable_hash("l3b-provenance"),
        content_hash=stable_hash(ANSWER),
    )
    window = SourceWindow(
        window_id="window:refund",
        identity=identity,
        source_reference="synthetic:refund",
        exact_span="complete",
        day101_rank=1,
        window_policy_version=contract.source_window_policy_version,
        text_digest=stable_hash(ANSWER),
        protected_text=ANSWER,
    )
    return GroundingBundle(
        operation_id="grounding-operation-l3b",
        original_query_digest=stable_hash("synthetic-query"),
        request_items_digest=stable_hash("synthetic-items"),
        day101_handoff_digest=stable_hash("day101-handoff"),
        authorization_scope_fingerprint=stable_hash("authorization-scope"),
        contract_fingerprint=contract.fingerprint,
        upstream_outcome="FULL",
        upstream_reranking_mode="RERANKED_SUCCESS",
        upstream_safe_reason="FULL_REWRITTEN_RERANKED_SUCCESS",
        windows=(window,),
    )


def _binding(
    contract: GroundingContract,
    bundle: GroundingBundle,
) -> OpenAIInvocationBinding:
    provider_attempt_id = stable_hash("provider-attempt")
    return OpenAIInvocationBinding(
        invocation_envelope_digest=stable_hash("invocation-envelope"),
        provider_invocation_attempt_id=provider_attempt_id,
        provider_invocation_reservation_digest=stable_hash(
            "provider-reservation"
        ),
        provider_request_idempotency_digest=(
            provider_request_idempotency_digest(provider_attempt_id)
        ),
        context_manifest_digest=stable_hash("context-manifest"),
        retrieval_bundle_digest=stable_hash("retrieval-bundle"),
        model_config_digest=openai_model_config_digest(MAX_OUTPUT_TOKENS),
        expected_operation_id=bundle.operation_id,
        expected_day101_handoff_digest=bundle.day101_handoff_digest,
        expected_contract_fingerprint=contract.fingerprint,
    )


def _success_response(answer: str = ANSWER) -> OpenAIResponsesHTTPResponse:
    return OpenAIResponsesHTTPResponse(
        200,
        json.dumps({
            "id": RAW_PROVIDER_ID,
            "status": "completed",
            "model": OPENAI_RESPONSES_MODEL,
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": answer}],
            }],
            "usage": {
                "input_tokens": 20,
                "output_tokens": 5,
                "total_tokens": 25,
            },
        }).encode("utf-8"),
    )


def _provider(
    transport: OpenAIResponsesTransport,
    *,
    budget: ProviderCallBudget | None = None,
) -> tuple[
    OpenAIResponsesAnswerProvider,
    GroundingContract,
    GroundingBundle,
    str,
]:
    contract = _contract()
    bundle = _bundle(contract)
    attempt_id = stable_hash((
        "DAY102_GENERATION_ATTEMPT_V1",
        bundle.operation_id,
        bundle.digest,
    ))
    provider = OpenAIResponsesAnswerProvider(
        transport=transport,
        budget=budget or ProviderCallBudget(10),
        binding=_binding(contract, bundle),
    )
    return provider, contract, bundle, attempt_id


def _generate(
    provider: OpenAIResponsesAnswerProvider,
    contract: GroundingContract,
    bundle: GroundingBundle,
    attempt_id: str,
) -> GeneratedAnswer:
    return provider.generate(
        attempt_id=attempt_id,
        bundle=bundle,
        contract=contract,
    )


def test_success_binds_identity_and_retains_only_content_safe_observation() -> None:
    transport = FakeHTTPTransport(response=_success_response())
    provider, contract, bundle, attempt_id = _provider(transport)

    answer = _generate(provider, contract, bundle, attempt_id)

    assert answer.answer_text == ANSWER
    assert answer.answer_digest == stable_hash(ANSWER)
    assert provider.calls == 1
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request.endpoint == OPENAI_RESPONSES_ENDPOINT
    assert request.model == OPENAI_RESPONSES_MODEL
    assert request.max_output_tokens == 64
    assert request.idempotency_key == stable_hash("provider-attempt")
    assert request.idempotency_key not in repr(request)
    assert request.payload()["store"] is False
    assert request.payload()["reasoning"] == {
        "effort": OPENAI_REASONING_EFFORT
    }
    assert "tools" not in request.payload()
    observation = provider.observations()[0]
    assert observation.outcome == "SUCCEEDED"
    assert observation.bundle_digest == bundle.digest
    assert observation.retrieval_bundle_digest == stable_hash(
        "retrieval-bundle"
    )
    assert observation.requested_model == OPENAI_RESPONSES_MODEL
    assert observation.observed_model == OPENAI_RESPONSES_MODEL
    assert observation.provider_response_id_digest == stable_hash((
        "OPENAI_RESPONSE_ID_V1",
        RAW_PROVIDER_ID,
    ))
    serialized = json.dumps(asdict(observation), sort_keys=True)
    assert ANSWER not in serialized
    assert RAW_PROVIDER_ID not in serialized
    assert all((
        not observation.raw_prompt_persisted,
        not observation.raw_response_persisted,
        not observation.raw_answer_persisted,
        not observation.secret_persisted,
    ))


def test_day106_support_seam_injects_provider_without_changing_default_path() -> None:
    fixture = build_canonical_day101_fixture(
        generation_id="G-l3b-test",
        pointer_revision=1,
        generation_artifact_fingerprint=stable_hash("G-l3b-artifact"),
        manifest_occurrence_ids=("A@v1", "C@v1"),
        authorization_revision=1,
    )
    claim = refund_window_claim()
    retrieval = execute_day101_query(
        fixture,
        query_id="L3B",
        query_text=claim.question,
        request_attempt_id="R-l3b",
    )
    contract = _contract()
    operation_id = f"grounding-{retrieval.retrieval_request.operation_id}"
    binding = OpenAIInvocationBinding(
        invocation_envelope_digest=stable_hash("injected-envelope"),
        provider_invocation_attempt_id=stable_hash("injected-attempt"),
        provider_invocation_reservation_digest=stable_hash(
            "injected-reservation"
        ),
        provider_request_idempotency_digest=(
            provider_request_idempotency_digest(
                stable_hash("injected-attempt")
            )
        ),
        context_manifest_digest=stable_hash("injected-context"),
        retrieval_bundle_digest=stable_hash("injected-retrieval-bundle"),
        model_config_digest=openai_model_config_digest(MAX_OUTPUT_TOKENS),
        expected_operation_id=operation_id,
        expected_day101_handoff_digest=(
            retrieval.day101_response.handoff_digest or "MISSING"
        ),
        expected_contract_fingerprint=contract.fingerprint,
    )
    transport = FakeHTTPTransport(
        response=_success_response(claim.answer_text),
    )
    provider = OpenAIResponsesAnswerProvider(
        transport=transport,
        budget=ProviderCallBudget(1),
        binding=binding,
    )

    result = execute_grounding_from_day101(
        fixture,
        retrieval=retrieval,
        claims=(claim,),
        grounding_contract=contract,
        answer_provider=provider,
    )

    assert result.day102_response.outcome.value == "FULL"
    assert provider.calls == 1
    assert len(transport.requests) == 1


@pytest.mark.parametrize("status", (401, 403, 429))
def test_auth_and_rate_fail_closed_without_retry(status: int) -> None:
    transport = FakeHTTPTransport(
        response=OpenAIResponsesHTTPResponse(status, b"sensitive-error"),
    )
    provider, contract, bundle, attempt_id = _provider(transport)

    with pytest.raises(GroundingProviderError) as caught:
        _generate(provider, contract, bundle, attempt_id)

    assert caught.value.reason is Day102FailureReason.GENERATOR_FAILED
    assert len(transport.requests) == 1
    observation = provider.observations()[0]
    assert observation.http_status == status
    assert observation.outcome == "FAILED"
    assert not observation.reconciliation_required
    assert "sensitive-error" not in repr(provider.observations())


def test_timeout_is_unknown_and_is_not_retried() -> None:
    transport = FakeHTTPTransport(error=OpenAITransportTimeout("timeout"))
    provider, contract, bundle, attempt_id = _provider(transport)

    with pytest.raises(GroundingProviderError) as caught:
        _generate(provider, contract, bundle, attempt_id)

    assert caught.value.reason is Day102FailureReason.GENERATOR_TIMEOUT
    assert len(transport.requests) == 1
    assert provider.observations()[0].outcome == "TIMEOUT_UNKNOWN"
    assert provider.observations()[0].reconciliation_required


def test_unknown_transport_is_unknown_and_requires_reconciliation() -> None:
    transport = FakeHTTPTransport(
        error=OpenAITransportError("ordinary URLError equivalent"),
    )
    provider, contract, bundle, attempt_id = _provider(transport)

    with pytest.raises(GroundingProviderError) as caught:
        _generate(provider, contract, bundle, attempt_id)

    assert caught.value.reason is Day102FailureReason.GENERATOR_TIMEOUT
    assert len(transport.requests) == 1
    observation = provider.observations()[0]
    assert observation.outcome == "TIMEOUT_UNKNOWN"
    assert observation.reconciliation_required


def test_urllib_urlerror_maps_to_unknown_and_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_urlopen(*args: object, **kwargs: object) -> None:
        raise URLError("synthetic network ambiguity")

    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-never-logged")
    monkeypatch.setattr(
        "rag_openai_responses_adapter.urlopen",
        fail_urlopen,
    )
    transport = UrllibOpenAIResponsesTransport()
    provider, contract, bundle, attempt_id = _provider(transport)

    with pytest.raises(GroundingProviderError) as caught:
        _generate(provider, contract, bundle, attempt_id)

    assert caught.value.reason is Day102FailureReason.GENERATOR_TIMEOUT
    observation = provider.observations()[0]
    assert observation.outcome == "TIMEOUT_UNKNOWN"
    assert observation.reconciliation_required


def test_urllib_sends_exact_attempt_idempotency_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str | None] = {}

    class FakeResponse:
        status = 200

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int) -> bytes:
            return b"{}"

    def fake_urlopen(request: Request, *, timeout: float) -> FakeResponse:
        captured["idempotency_key"] = request.get_header(
            "Idempotency-key"
        )
        return FakeResponse()

    attempt_id = stable_hash("header-attempt")
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-never-logged")
    monkeypatch.setattr(
        "rag_openai_responses_adapter.urlopen",
        fake_urlopen,
    )
    transport = UrllibOpenAIResponsesTransport()

    transport.send(OpenAIResponsesRequest(
        prompt="synthetic",
        idempotency_key=attempt_id,
    ))

    assert captured["idempotency_key"] == attempt_id


def test_explicit_not_sent_transport_evidence_is_failed() -> None:
    transport = FakeHTTPTransport(
        error=OpenAITransportNotSent("explicit pre-send failure"),
    )
    provider, contract, bundle, attempt_id = _provider(transport)

    with pytest.raises(GroundingProviderError) as caught:
        _generate(provider, contract, bundle, attempt_id)

    assert caught.value.reason is Day102FailureReason.GENERATOR_FAILED
    assert len(transport.requests) == 1
    observation = provider.observations()[0]
    assert observation.outcome == "FAILED"
    assert not observation.reconciliation_required


@pytest.mark.parametrize("status", (408, 409, 500, 503))
def test_ambiguous_http_status_is_unknown_and_requires_reconciliation(
    status: int,
) -> None:
    transport = FakeHTTPTransport(
        response=OpenAIResponsesHTTPResponse(status, b"sensitive-error"),
    )
    provider, contract, bundle, attempt_id = _provider(transport)

    with pytest.raises(GroundingProviderError) as caught:
        _generate(provider, contract, bundle, attempt_id)

    assert caught.value.reason is Day102FailureReason.GENERATOR_TIMEOUT
    assert len(transport.requests) == 1
    observation = provider.observations()[0]
    assert observation.http_status == status
    assert observation.outcome == "TIMEOUT_UNKNOWN"
    assert observation.reconciliation_required
    assert "sensitive-error" not in repr(observation)


def test_oversize_response_is_unknown_without_retry() -> None:
    transport = FakeHTTPTransport(
        error=OpenAIResponseTooLarge("response exceeded limit"),
    )
    provider, contract, bundle, attempt_id = _provider(transport)

    with pytest.raises(GroundingProviderError) as caught:
        _generate(provider, contract, bundle, attempt_id)

    assert caught.value.reason is Day102FailureReason.GENERATOR_TIMEOUT
    assert len(transport.requests) == 1
    observation = provider.observations()[0]
    assert observation.outcome == "TIMEOUT_UNKNOWN"
    assert observation.reconciliation_required


@pytest.mark.parametrize(
    "body",
    (
        b"not-json",
        b"{}",
        json.dumps({
            "id": RAW_PROVIDER_ID,
            "status": "incomplete",
            "model": OPENAI_RESPONSES_MODEL,
            "output": [],
            "usage": {
                "input_tokens": 1,
                "output_tokens": 0,
                "total_tokens": 1,
            },
        }).encode("utf-8"),
    ),
)
def test_malformed_or_incomplete_response_fails_closed(body: bytes) -> None:
    transport = FakeHTTPTransport(
        response=OpenAIResponsesHTTPResponse(200, body),
    )
    provider, contract, bundle, attempt_id = _provider(transport)

    with pytest.raises(GroundingProviderError) as caught:
        _generate(provider, contract, bundle, attempt_id)

    assert caught.value.reason is Day102FailureReason.GENERATOR_OUTPUT_INVALID
    assert len(transport.requests) == 1


def test_observed_output_tokens_cannot_exceed_requested_cap() -> None:
    payload = json.loads(_success_response().body)
    payload["usage"] = {
        "input_tokens": 20,
        "output_tokens": 65,
        "total_tokens": 85,
    }
    transport = FakeHTTPTransport(response=OpenAIResponsesHTTPResponse(
        200,
        json.dumps(payload).encode("utf-8"),
    ))
    provider, contract, bundle, attempt_id = _provider(transport)

    with pytest.raises(GroundingProviderError) as caught:
        _generate(provider, contract, bundle, attempt_id)

    assert caught.value.reason is Day102FailureReason.GENERATOR_OUTPUT_INVALID
    observation = provider.observations()[0]
    assert observation.output_tokens == 65
    assert observation.outcome == "FAILED"


def test_shared_call_budget_is_strict_and_rejects_eleventh_call() -> None:
    budget = ProviderCallBudget(10)
    transport = FakeHTTPTransport(response=_success_response())
    provider, contract, bundle, attempt_id = _provider(
        transport,
        budget=budget,
    )

    for _ in range(10):
        _generate(provider, contract, bundle, attempt_id)
    with pytest.raises(GroundingProviderError) as caught:
        _generate(provider, contract, bundle, attempt_id)

    assert caught.value.reason is Day102FailureReason.GENERATOR_FAILED
    assert budget.used == 10
    assert provider.calls == 10
    assert len(transport.requests) == 10
    with pytest.raises(ValueError):
        ProviderCallBudget(11)


def test_identity_drift_is_rejected_before_budget_or_transport() -> None:
    budget = ProviderCallBudget(10)
    transport = FakeHTTPTransport(response=_success_response())
    provider, contract, bundle, attempt_id = _provider(
        transport,
        budget=budget,
    )

    with pytest.raises(ValueError, match="attempt identity drift"):
        _generate(provider, contract, bundle, "wrong-attempt")

    drifted = replace(bundle, operation_id="different-operation")
    drifted_attempt = stable_hash((
        "DAY102_GENERATION_ATTEMPT_V1",
        drifted.operation_id,
        drifted.digest,
    ))
    with pytest.raises(ValueError, match="operation identity drift"):
        _generate(provider, contract, drifted, drifted_attempt)

    assert budget.used == 0
    assert provider.calls == 0
    assert transport.requests == []


def test_fixed_output_cap_and_environment_only_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract()
    bundle = _bundle(contract)
    binding = _binding(contract, bundle)
    transport = FakeHTTPTransport(response=_success_response())

    with pytest.raises(ValueError, match="between 1 and 64"):
        OpenAIResponsesAnswerProvider(
            transport=transport,
            budget=ProviderCallBudget(1),
            binding=binding,
            max_output_tokens=65,
        )
    with pytest.raises(ValueError, match="idempotency identity drift"):
        OpenAIResponsesAnswerProvider(
            transport=transport,
            budget=ProviderCallBudget(1),
            binding=replace(
                binding,
                provider_request_idempotency_digest=stable_hash("wrong"),
            ),
        )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        UrllibOpenAIResponsesTransport()
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-never-logged")
    real_transport = UrllibOpenAIResponsesTransport()
    assert "test-secret-never-logged" not in repr(real_transport)
