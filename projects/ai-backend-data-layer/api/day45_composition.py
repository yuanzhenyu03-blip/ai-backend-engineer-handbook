"""Day45 — Dependency Injection, Lifespan, Configuration and AI Provider Adapters.

A MINIMAL, runnable composition root that wires the Day44 typed contracts into a
testable FastAPI runtime WITHOUT letting Routers or business services own
infrastructure. The composition boundary owns expensive, closeable, app/process-
scoped resources (validated Settings, an async HTTP client, and a concrete
Provider adapter); ``Depends`` supplies already-created interfaces; a stateless
``JobService`` is created per request/Job.

HTTP acceptance stays SHORT: the FastAPI route only demonstrates dependency
resolution and the short request lifecycle. A (possibly long, e.g. eight-minute)
Provider generation belongs to a WORKER, not an HTTP Router, so the actual
Provider call + Day44 validation + illustrative completion live in an explicit
worker-style harness (``WorkerJobRunner``), not in a route handler.

Scope and honesty (see the Day45 lesson and design doc):
    * This example is executed locally with FastAPI's ``TestClient`` and a FAKE,
      no-network Provider. Real Provider authentication/network/SDK compatibility,
      PostgreSQL, SQLAlchemy/Alembic, Celery/Redis/Object Storage, Secret
      rotation/drain, and production are NOT implemented and NOT run. Those are
      later lessons (Day46/47/50/53/54/55/56).
    * ``OpenAICompatibleAdapter`` demonstrates ONLY the seam shape and the
      vendor-error -> stable-error translation boundary, over an INJECTED
      transport callable and with no real network. The real OpenAI-compatible SDK
      call and response parsing are Day53.
    * The completion target is an in-memory list owned by the worker harness, NOT
      a PostgreSQL guarded completion.
    * ``SecretStr`` reduces accidental printing/repr/serialization exposure; it is
      NOT encryption in process memory and does not replace permissions, rotation,
      or secure logging.
    * Local Settings validation proves local configuration is well-formed; it does
      NOT prove the external Provider is currently reachable or authenticated.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Awaitable, Callable, List, Mapping, Optional, Protocol, runtime_checkable

from fastapi import Depends, FastAPI, Request
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, field_validator

# Reuse the Day44 output contract: a Worker Service validates raw Provider JSON
# through StructuredAIResult BEFORE any illustrative completion side effect.
from day44_pydantic_contracts import StructuredAIResult

# ---------------------------------------------------------------------------
# Stable application-level Provider errors (Adapter masks vendor detail)
# ---------------------------------------------------------------------------
# The Adapter translates vendor exceptions into these stable types. Day56 owns
# retry/backoff/cost/backpressure POLICY; this lesson only classifies/masks.
class ProviderError(Exception):
    """Base class for adapter-normalized Provider failures."""


class ProviderTimeout(ProviderError):
    pass


class ProviderRateLimited(ProviderError):
    pass


class ProviderAuthentication(ProviderError):
    pass


class ProviderTransport(ProviderError):
    """Transport/protocol-level failure (connection, malformed HTTP, etc.)."""


class ProviderNotReady(RuntimeError):
    """Raised when a use-site resolves the Provider before the lifespan has
    published a fully-initialized Container (readiness gate)."""


# ---------------------------------------------------------------------------
# Validated, secret-aware Settings (the configuration/secret boundary)
# ---------------------------------------------------------------------------
class Settings(BaseModel):
    # Immutable for one process lifecycle; reject undeclared config keys.
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_api_key: SecretStr
    provider_base_url: AnyHttpUrl
    provider_model: str = Field(min_length=1)
    request_timeout_s: float = Field(gt=0, le=120)
    # Non-sensitive, allowlisted labels used for safe logging. provider_base_url
    # may embed userinfo, an internal host, a port, or a private endpoint path,
    # so it is NEVER logged; provider_name is a coarse, non-sensitive identifier.
    provider_name: str = Field(default="openai-compatible", min_length=1)
    settings_version: str = Field(default="unknown", min_length=1)

    @field_validator("provider_api_key")
    @classmethod
    def _api_key_non_empty(cls, v: SecretStr) -> SecretStr:
        if not v.get_secret_value().strip():
            raise ValueError("provider_api_key must be a non-empty secret")
        return v

    @classmethod
    def load(cls, env: Optional[Mapping[str, object]] = None) -> "Settings":
        """Fail-fast construction from a mapping (default os.environ). A missing
        or invalid value raises ValidationError at startup, so a Worker stays not
        ready and does not claim Jobs."""
        src = os.environ if env is None else env
        data = {
            "provider_api_key": src.get("PROVIDER_API_KEY"),
            "provider_base_url": src.get("PROVIDER_BASE_URL"),
            "provider_model": src.get("PROVIDER_MODEL"),
            "request_timeout_s": src.get("PROVIDER_TIMEOUT_S", 30),
        }
        # Optional allowlisted labels; safe defaults keep fail-fast focused on the
        # required secret/URL/model/timeout.
        if src.get("PROVIDER_NAME") is not None:
            data["provider_name"] = src.get("PROVIDER_NAME")
        if src.get("SETTINGS_VERSION") is not None:
            data["settings_version"] = src.get("SETTINGS_VERSION")
        return cls.model_validate(data)

    def safe_log_fields(self) -> dict:
        """Allowlisted, redacted view for logs. Emits ONLY non-sensitive fields:
        a coarse provider_name, the model, the timeout, and a settings_version.
        It NEVER emits the API key, the whole Settings, a raw model_dump(), or the
        provider_base_url (which can carry userinfo/internal host/port/private
        endpoint path)."""
        return {
            "provider_name": self.provider_name,
            "provider_model": self.provider_model,
            "request_timeout_s": self.request_timeout_s,
            "settings_version": self.settings_version,
            "provider_api_key": "***REDACTED***",
        }


# ---------------------------------------------------------------------------
# The small AIProvider seam (interface), NOT a vendor SDK
# ---------------------------------------------------------------------------
@runtime_checkable
class AIProvider(Protocol):
    async def generate(self, *, prompt: str, max_tokens: int) -> str:
        """Return RAW, UNTRUSTED provider JSON text. The caller validates it via
        the Day44 contract before any completion side effect."""
        ...


# A closeable async resource (an httpx.AsyncClient in production). Kept structural
# so a tracking fake can record close without a real network stack.
SupportsAclose = object


async def _aclose(resource: object) -> None:
    close = getattr(resource, "aclose", None)
    if close is not None:
        await close()


# ---------------------------------------------------------------------------
# Production-shaped adapter (illustrative; NO real network in Day45)
# ---------------------------------------------------------------------------
# A transport callable stands in for the real vendor SDK/HTTP call. Injecting it
# keeps Day45 free of a real network while still demonstrating the actual
# vendor-error -> stable-error translation. Day53 provides the real transport.
Transport = Callable[..., Awaitable[str]]


class OpenAICompatibleAdapter:
    """Hides SDK/HTTP construction, request shaping, vendor response extraction,
    and vendor-specific exceptions behind the small AIProvider seam. It owns NO
    Job lifecycle.

    Day45 demonstrates the seam and the error-translation boundary over an
    INJECTED ``transport`` callable with no real network; a real OpenAI-compatible
    call and full response parsing are Day53. If no transport is injected,
    ``generate`` raises ``NotImplementedError`` (Day45 has no real Provider), and
    tests use ``FakeAIProvider`` or inject a transport for the translation cases.
    """

    def __init__(
        self,
        settings: Settings,
        http_client: object,
        *,
        transport: Optional[Transport] = None,
    ) -> None:
        self._settings = settings
        self._http = http_client  # owned by the lifespan, not by the adapter
        self._transport = transport

    async def generate(self, *, prompt: str, max_tokens: int) -> str:
        if self._transport is None:
            raise NotImplementedError(
                "OpenAICompatibleAdapter has no real Provider transport wired in "
                "Day45; inject a transport (tests) or use the Day53 SDK. "
                "FakeAIProvider is the deterministic no-network test seam."
            )
        try:
            return await self._transport(prompt=prompt, max_tokens=max_tokens)
        except ProviderError:
            raise  # already a stable application error
        except BaseException as exc:  # noqa: BLE001 - deliberately classify all vendor faults
            raise self._translate(exc) from exc

    @staticmethod
    def _translate(exc: BaseException) -> ProviderError:
        """Map an opaque vendor/transport exception to a stable application error.
        The classification uses portable signals (builtin timeout, an HTTP-style
        ``status_code`` attribute, a connection error); real vendor SDK exception
        types are wrapped the same way in Day53."""
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            return ProviderTimeout("provider request timed out")
        status = getattr(exc, "status_code", None)
        if status == 429:
            return ProviderRateLimited("provider rate limited (HTTP 429)")
        if status in (401, 403):
            return ProviderAuthentication(f"provider authentication failed (HTTP {status})")
        if isinstance(exc, ConnectionError):
            return ProviderTransport("provider transport/connection error")
        return ProviderTransport(f"provider transport error: {type(exc).__name__}")


# ---------------------------------------------------------------------------
# Deterministic test double (no network, no cost)
# ---------------------------------------------------------------------------
@dataclass
class FakeAIProvider:
    """Returns deterministic raw JSON (valid or invalid) or raises a deterministic
    classified error. Records how many times it was called."""

    raw_json: Optional[str] = None
    raises: Optional[BaseException] = None
    calls: int = 0

    async def generate(self, *, prompt: str, max_tokens: int) -> str:
        self.calls += 1
        if self.raises is not None:
            raise self.raises
        assert self.raw_json is not None
        return self.raw_json


# ---------------------------------------------------------------------------
# Stateless per-request/per-Job service (depends on the interface only)
# ---------------------------------------------------------------------------
@dataclass
class JobService:
    provider: AIProvider

    async def run_job(self, *, prompt: str, max_tokens: int) -> StructuredAIResult:
        raw = await self.provider.generate(prompt=prompt, max_tokens=max_tokens)
        # Day44 boundary: validate untrusted Provider output BEFORE completion.
        return StructuredAIResult.model_validate_json(raw)


# ---------------------------------------------------------------------------
# Worker-style harness (NOT an HTTP route)
# ---------------------------------------------------------------------------
@dataclass
class WorkerJobRunner:
    """Represents what a WORKER process does with a Job — NOT an HTTP handler.
    It resolves the app-scoped Provider, runs the (possibly long) Job through a
    stateless per-Job ``JobService``, validates raw output via Day44, and records
    an illustrative in-memory completion. A real durable Worker (Celery claim/
    ACK/drain/recovery) is Day55; this is a test-only demonstration so the
    Provider call never happens inside a FastAPI request."""

    provider: AIProvider
    completed: List[StructuredAIResult] = field(default_factory=list)

    async def run(self, *, prompt: str, max_tokens: int) -> StructuredAIResult:
        service = JobService(provider=self.provider)  # stateless, per Job
        result = await service.run_job(prompt=prompt, max_tokens=max_tokens)
        # Illustrative in-memory completion (NOT a guarded PostgreSQL commit).
        self.completed.append(result)
        return result


# ---------------------------------------------------------------------------
# The application Container: app/process-scoped resources, published only after
# COMPLETE initialization succeeds.
# ---------------------------------------------------------------------------
@dataclass
class Container:
    settings: Settings
    http_client: object
    provider: AIProvider


# Explicit factory seams keep tests from constructing a real client/adapter.
HttpClientFactory = Callable[[Settings], object]
ProviderFactory = Callable[[Settings, object], AIProvider]


# ---------------------------------------------------------------------------
# Dependencies: Depends() supplies already-created, lifespan-owned instances.
# ---------------------------------------------------------------------------
def get_provider(request: Request) -> AIProvider:
    container: Optional[Container] = getattr(request.app.state, "container", None)
    if container is None:
        raise ProviderNotReady("Provider is not ready: Container not published.")
    return container.provider


def get_job_service(provider: AIProvider = Depends(get_provider)) -> JobService:
    # Stateless, lightweight, per request/Job. Carries no tenant/trace/job state.
    return JobService(provider=provider)


# ---------------------------------------------------------------------------
# Composition root: create_app receives Settings + explicit factories.
# ---------------------------------------------------------------------------
def create_app(
    settings: Settings,
    *,
    http_client_factory: HttpClientFactory,
    provider_factory: ProviderFactory,
) -> FastAPI:
    """Explicit, testable composition seam. The lifespan creates resources in a
    fixed order and publishes the Container only after complete initialization;
    on partial failure it closes what it created and publishes nothing."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Order: Settings (already validated) -> HTTP client -> ProviderAdapter
        #        -> publish Container -> yield ready -> clear container -> close.
        http_client = http_client_factory(settings)
        try:
            provider = provider_factory(settings, http_client)
        except Exception:
            # Partial init: close the already-created client, publish nothing,
            # and let startup fail so a Worker stays not ready and cannot claim.
            await _aclose(http_client)
            raise
        app.state.container = Container(
            settings=settings, http_client=http_client, provider=provider
        )
        try:
            yield
        finally:
            # Reverse creation order: stop using the Container, then close the
            # client. Never close the shared client per request.
            app.state.container = None
            await _aclose(http_client)

    app = FastAPI(lifespan=lifespan)
    app.state.container = None

    @app.get("/provider/status")
    async def provider_status(
        request: Request,
        provider: AIProvider = Depends(get_provider),
    ):
        # SHORT HTTP boundary: this proves the lifespan-owned Provider is
        # resolvable via Depends and returns only allowlisted, redacted metadata.
        # It deliberately does NOT run a (possibly long) Provider generation — a
        # Job's Provider call belongs to a Worker (see WorkerJobRunner and Day55).
        container: Container = request.app.state.container
        return {"provider_ready": provider is not None, **container.settings.safe_log_fields()}

    @app.get("/healthz")
    async def healthz(request: Request):
        ready = getattr(request.app.state, "container", None) is not None
        return {"ready": ready}

    return app
