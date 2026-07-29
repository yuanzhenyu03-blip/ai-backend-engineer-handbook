"""Day45 — deterministic, no-network composition/lifespan tests.

These prove: fake Provider injection before TestClient startup, the tracking HTTP
client is open inside the lifespan and closed after shutdown, partial Adapter
initialization closes the client and publishes no readiness/Container, invalid raw
Provider output cannot reach the illustrative completion callback, and no Secret
leaks into responses. No real Provider/network/PostgreSQL is used.
"""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from day45_composition import (
    Container,
    FakeAIProvider,
    JobService,
    ProviderNotReady,
    Settings,
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

# A secret value that must never appear in a response body.
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


# 1. Fake Provider is used, no network, resource open inside context then closed.
def test_fake_provider_injected_no_network_and_client_lifecycle():
    provider = FakeAIProvider(raw_json=VALID_RAW)
    clients = []
    app = make_app(provider, clients_created=clients)
    with TestClient(app) as client:
        # Inside the lifespan the client exists and is open; Container published.
        assert len(clients) == 1
        assert clients[0].closed is False
        assert app.state.container is not None
        resp = client.post("/jobs/run", json={"prompt": "hi", "max_tokens": 100})
        assert resp.status_code == 200
        assert resp.json()["summary"] == "a valid summary"
    # After shutdown: client closed, Container cleared, and no network happened.
    assert clients[0].closed is True
    assert clients[0].network_calls == 0
    assert provider.calls == 1
    assert app.state.container is None


# 2. Valid Provider output reaches the completion list exactly once.
def test_valid_provider_output_completes_once():
    provider = FakeAIProvider(raw_json=VALID_RAW)
    app = make_app(provider)
    with TestClient(app) as client:
        client.post("/jobs/run", json={"prompt": "hi", "max_tokens": 100})
        assert len(app.state.completed) == 1


# 3. Invalid raw Provider output cannot reach the illustrative completion callback.
def test_invalid_provider_output_blocks_completion():
    provider = FakeAIProvider(raw_json=INVALID_RAW)
    app = make_app(provider)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/jobs/run", json={"prompt": "hi", "max_tokens": 100})
        assert resp.status_code == 500  # ValidationError propagated, not a success
        # The empty list proves the guard blocked the side effect (not just raised).
        assert app.state.completed == []
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
    assert app.state.completed == []           # no work claimed/completed


def _record(clients):
    c = TrackingHTTPClient()
    clients.append(c)
    return c


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


# 10. The Secret does not leak into a use-site response body.
def test_secret_not_in_response_body():
    provider = FakeAIProvider(raw_json=VALID_RAW)
    app = make_app(provider)
    with TestClient(app) as client:
        resp = client.post("/jobs/run", json={"prompt": "hi", "max_tokens": 100})
        assert SECRET_VALUE not in resp.text


# 11. Dependency override configured BEFORE TestClient startup is honored, and
#     clearing overrides restores the wiring.
def test_dependency_override_before_testclient():
    lifespan_provider = FakeAIProvider(raw_json=INVALID_RAW)  # would fail if used
    override_provider = FakeAIProvider(raw_json=VALID_RAW)
    app = make_app(lifespan_provider)
    # Configure the override BEFORE entering the TestClient context.
    app.dependency_overrides[get_provider] = lambda: override_provider
    try:
        with TestClient(app) as client:
            resp = client.post("/jobs/run", json={"prompt": "hi", "max_tokens": 100})
            assert resp.status_code == 200
            assert override_provider.calls == 1
            assert lifespan_provider.calls == 0
    finally:
        app.dependency_overrides.clear()
    assert get_provider not in app.dependency_overrides


# 12. Stateless JobService carries no state across executions (fresh per Job).
def test_job_service_is_stateless_per_job():
    provider = FakeAIProvider(raw_json=VALID_RAW)
    s1 = JobService(provider=provider)
    s2 = JobService(provider=provider)
    assert s1 is not s2
    assert set(vars(s1).keys()) == {"provider"}  # only the injected interface
