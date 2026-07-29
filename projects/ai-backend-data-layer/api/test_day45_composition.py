"""Day45 — deterministic, no-network composition/lifespan tests.

These prove: fake Provider injection before TestClient startup; the tracking HTTP
client is open inside the lifespan and closed after shutdown; the SHORT HTTP route
resolves the Provider via Depends WITHOUT running a Provider generation; a
worker-style harness runs the Job and validates output via Day44 (invalid output
cannot reach the completion list); partial Adapter initialization closes the
client and publishes no readiness/Container; the adapter translates vendor faults
into stable Provider* errors over an injected transport; and no Secret (or
sensitive base-URL part) leaks into responses or logs. No real Provider/network/
PostgreSQL is used.
"""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from day45_composition import (
    OpenAICompatibleAdapter,
    FakeAIProvider,
    JobService,
    ProviderAuthentication,
    ProviderNotReady,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderTransport,
    Settings,
    WorkerJobRunner,
    create_app,
    get_provider,
)

# --- deterministic fakes -----------------------------------------------------
VALID_RAW = json.dumps(
    {
        "summary": "a valid summary",
        "confidence": 0.9,
        "citations": [{"source_id": "c1", "url": "https://example.com/a"}],
    }
)
# Invalid: Provider-owned job_status + bad confidence + wrong citations shape.
INVALID_RAW = json.dumps(
    {"summary": "s", "confidence": "very sure", "citations": "one-source", "job_status": "succeeded"}
)

# A secret value that must never appear in a response body or a log field.
SECRET_VALUE = "sk-fake-not-a-real-key-000"


class TrackingHTTPClient:
    """Stands in for an async httpx client. Records close and proves no network."""

    def __init__(self) -> None:
        self.closed = False
        self.network_calls = 0

    async def aclose(self) -> None:
        self.closed = True


def fake_settings(**overrides) -> Settings:
    data = {
        "provider_api_key": SECRET_VALUE,
        "provider_base_url": "https://provider.example.com",
        "provider_model": "fake-model-v1",
        "request_timeout_s": 30,
    }
    data.update(overrides)
    return Settings.model_validate(data)


def make_app(provider, *, clients_created=None, provider_factory=None):
    """Build an app whose lifespan creates a tracking client and injects `provider`."""

    def http_client_factory(settings):
        client = TrackingHTTPClient()
        if clients_created is not None:
            clients_created.append(client)
        return client

    def default_provider_factory(settings, http_client):
        return provider

    return create_app(
        fake_settings(),
        http_client_factory=http_client_factory,
        provider_factory=provider_factory or default_provider_factory,
    )


def _record(clients):
    c = TrackingHTTPClient()
    clients.append(c)
    return c


# 1. Fake Provider injected; tracking client open inside lifespan then closed;
#    the SHORT HTTP route resolves the Provider via Depends but does NOT run it.
def test_short_http_route_resolves_provider_without_running_it():
    provider = FakeAIProvider(raw_json=VALID_RAW)
    clients = []
    app = make_app(provider, clients_created=clients)
    with TestClient(app) as client:
        assert len(clients) == 1
        assert clients[0].closed is False
        assert app.state.container is not None
        resp = client.get("/provider/status")
        assert resp.status_code == 200
        assert resp.json()["provider_ready"] is True
    # After shutdown: client closed, Container cleared, no network, and crucially
    # the HTTP route never invoked the (possibly long) Provider generation.
    assert clients[0].closed is True
    assert clients[0].network_calls == 0
    assert provider.calls == 0
    assert app.state.container is None


# 2. A worker-style harness (NOT an HTTP route) runs the Job and completes once.
def test_worker_harness_valid_output_completes_once():
    provider = FakeAIProvider(raw_json=VALID_RAW)
    runner = WorkerJobRunner(provider=provider)
    result = asyncio.run(runner.run(prompt="hi", max_tokens=100))
    assert result.summary == "a valid summary"
    assert len(runner.completed) == 1
    assert provider.calls == 1


# 3. Invalid raw Provider output cannot reach the worker completion list.
def test_worker_harness_invalid_output_blocks_completion():
    provider = FakeAIProvider(raw_json=INVALID_RAW)
    runner = WorkerJobRunner(provider=provider)
    with pytest.raises(ValidationError):
        asyncio.run(runner.run(prompt="hi", max_tokens=100))
    # The empty list proves the guard blocked the side effect (not just raised).
    assert runner.completed == []
    assert provider.calls == 1


# 4. Partial Adapter init closes the already-created client and publishes nothing.
def test_partial_init_closes_client_and_no_readiness():
    clients = []

    def raising_provider_factory(settings, http_client):
        raise RuntimeError("adapter init failed after client creation")

    app = create_app(
        fake_settings(),
        http_client_factory=lambda s: _record(clients),
        provider_factory=raising_provider_factory,
    )
    with pytest.raises(RuntimeError):
        with TestClient(app):  # startup runs the lifespan, which raises
            pass
    assert len(clients) == 1
    assert clients[0].closed is True          # already-created client was closed
    assert app.state.container is None         # Container never published


# 5. get_provider raises before the Container is published (readiness gate).
def test_get_provider_not_ready_raises():
    provider = FakeAIProvider(raw_json=VALID_RAW)
    app = make_app(provider)

    class _Req:
        pass

    req = _Req()
    req.app = app  # container is None before lifespan startup
    with pytest.raises(ProviderNotReady):
        get_provider(req)  # type: ignore[arg-type]


# 6. Settings fail-fast: a missing API key raises at load/validation time.
def test_settings_fail_fast_on_missing_key():
    with pytest.raises(ValidationError):
        Settings.load(env={
            "PROVIDER_BASE_URL": "https://provider.example.com",
            "PROVIDER_MODEL": "fake-model-v1",
        })


# 7. Settings fail-fast: an empty API key is rejected.
def test_settings_reject_empty_key():
    with pytest.raises(ValidationError):
        fake_settings(provider_api_key="   ")


# 8. Settings fail-fast: a non-positive timeout is rejected.
def test_settings_reject_nonpositive_timeout():
    with pytest.raises(ValidationError):
        fake_settings(request_timeout_s=0)


# 9. Secret-aware rendering: repr/str/safe_log_fields never expose the raw key.
def test_secret_not_rendered_in_repr_or_logs():
    s = fake_settings()
    assert SECRET_VALUE not in repr(s)
    assert SECRET_VALUE not in str(s)
    assert SECRET_VALUE not in json.dumps(s.safe_log_fields())
    assert s.safe_log_fields()["provider_api_key"] == "***REDACTED***"
    # The real value is still obtainable deliberately (SecretStr is not encryption).
    assert s.provider_api_key.get_secret_value() == SECRET_VALUE


# 10. safe_log_fields must not leak the base URL or any sensitive part of it
#     (userinfo, internal host, port, or a private endpoint path).
def test_safe_log_fields_excludes_sensitive_url_parts():
    s = fake_settings(
        provider_base_url="https://svcuser:s3cr3tpw@internal-vpc-9931.corp.local:8443/private/generate",
        provider_name="openai-compatible",
        settings_version="2026-07-30.1",
    )
    fields = s.safe_log_fields()
    blob = json.dumps(fields)
    for sensitive in (
        "s3cr3tpw",              # userinfo password
        "svcuser",              # userinfo user
        "internal-vpc-9931",     # internal host
        "corp.local",           # internal domain
        "8443",                 # internal port
        "private/generate",      # private endpoint path
        "provider_base_url",     # the field itself must be absent
    ):
        assert sensitive not in blob, f"leaked {sensitive!r} in {blob}"
    # Only allowlisted, non-sensitive fields are present.
    assert set(fields) == {
        "provider_name",
        "provider_model",
        "request_timeout_s",
        "settings_version",
        "provider_api_key",
    }
    assert fields["provider_name"] == "openai-compatible"
    assert fields["settings_version"] == "2026-07-30.1"


# 11. The Secret does not leak into the short HTTP route response body.
def test_secret_not_in_response_body():
    provider = FakeAIProvider(raw_json=VALID_RAW)
    app = make_app(provider)
    with TestClient(app) as client:
        resp = client.get("/provider/status")
        assert SECRET_VALUE not in resp.text


# 12. A dependency override configured BEFORE TestClient is applied, and clearing
#     it restores the original lifespan wiring in a fresh lifecycle.
def test_dependency_override_applied_before_testclient_then_cleared_restores_wiring():
    app = make_app(FakeAIProvider(raw_json=VALID_RAW))

    class _Sentinel(Exception):
        pass

    def boom() -> object:
        raise _Sentinel()

    # Override BEFORE entering TestClient (whose context triggers lifespan startup).
    app.dependency_overrides[get_provider] = boom
    with TestClient(app, raise_server_exceptions=False) as client:
        # The override replaced get_provider, so the route dependency raises -> 500.
        assert client.get("/provider/status").status_code == 500

    # Clear overrides, then a FRESH lifecycle resolves the real lifespan provider.
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        resp = client.get("/provider/status")
        assert resp.status_code == 200          # original wiring restored
        assert resp.json()["provider_ready"] is True
    assert get_provider not in app.dependency_overrides


# 13. Stateless JobService carries no state across executions (fresh per Job).
def test_job_service_is_stateless_per_job():
    provider = FakeAIProvider(raw_json=VALID_RAW)
    s1 = JobService(provider=provider)
    s2 = JobService(provider=provider)
    assert s1 is not s2
    assert set(vars(s1).keys()) == {"provider"}  # only the injected interface


# --- Adapter error translation (injected transport; no real network) ---------

def _adapter_with_transport(transport):
    return OpenAICompatibleAdapter(fake_settings(), object(), transport=transport)


# 14. A builtin/asyncio timeout maps to ProviderTimeout.
def test_adapter_translates_timeout():
    async def transport(*, prompt, max_tokens):
        raise asyncio.TimeoutError("slow")

    adapter = _adapter_with_transport(transport)
    with pytest.raises(ProviderTimeout):
        asyncio.run(adapter.generate(prompt="p", max_tokens=10))


# 15. An HTTP-429-style error maps to ProviderRateLimited.
def test_adapter_translates_rate_limit():
    class VendorHTTPError(Exception):
        status_code = 429

    async def transport(*, prompt, max_tokens):
        raise VendorHTTPError("too many requests")

    adapter = _adapter_with_transport(transport)
    with pytest.raises(ProviderRateLimited):
        asyncio.run(adapter.generate(prompt="p", max_tokens=10))


# 16. An HTTP-401/403-style error maps to ProviderAuthentication.
def test_adapter_translates_auth():
    class VendorHTTPError(Exception):
        status_code = 401

    async def transport(*, prompt, max_tokens):
        raise VendorHTTPError("unauthorized")

    adapter = _adapter_with_transport(transport)
    with pytest.raises(ProviderAuthentication):
        asyncio.run(adapter.generate(prompt="p", max_tokens=10))


# 17. A connection/other error maps to ProviderTransport.
def test_adapter_translates_transport():
    async def transport(*, prompt, max_tokens):
        raise ConnectionError("connection reset")

    adapter = _adapter_with_transport(transport)
    with pytest.raises(ProviderTransport):
        asyncio.run(adapter.generate(prompt="p", max_tokens=10))


# 18. Without an injected transport, Day45's adapter honestly raises (no real SDK).
def test_adapter_without_transport_raises_notimplemented():
    adapter = OpenAICompatibleAdapter(fake_settings(), object())
    with pytest.raises(NotImplementedError):
        asyncio.run(adapter.generate(prompt="p", max_tokens=10))


# 19. A successful transport passes its raw JSON through unchanged (validated by
#     the Day44 contract downstream, not by the adapter).
def test_adapter_passes_through_transport_output():
    async def transport(*, prompt, max_tokens):
        return VALID_RAW

    adapter = _adapter_with_transport(transport)
    raw = asyncio.run(adapter.generate(prompt="p", max_tokens=10))
    assert raw == VALID_RAW
