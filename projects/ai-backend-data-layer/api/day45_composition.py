"""Day45 — Dependency Injection, Lifespan, Configuration and AI Provider Adapters.

A MINIMAL, runnable composition root that wires the Day44 typed contracts into a
testable FastAPI runtime WITHOUT letting Routers or business services own
infrastructure. The composition boundary owns expensive, closeable, app/process-
scoped resources (validated Settings, an async HTTP client, and a concrete
Provider adapter); ``Depends`` supplies already-created interfaces; a stateless
``JobService`` is created per request/Job.

Scope and honesty (see the Day45 lesson and design doc):
    * This example is executed locally with FastAPI's ``TestClient`` and a FAKE,
      no-network Provider. A real Provider SDK/network call, PostgreSQL,
      SQLAlchemy/Alembic, Celery/Redis/Object Storage, Secret rotation/drain, and
      production are NOT implemented and NOT run. Those are later lessons
      (Day46/47/50/53/54/55/56).
    * The completion target is an in-memory list on ``app.state``, NOT a
      PostgreSQL guarded completion.
    * ``SecretStr`` reduces accidental printing/repr/serialization exposure; it is
      NOT encryption in process memory and does not replace permissions, rotation,
      or secure logging.
    * Local Settings validation proves local configuration is well-formed; it does
      NOT prove the external Provider is currently reachable or authenticated.
"""

from __future__ import annotations

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
        return cls.model_validate(data)

    def safe_log_fields(self) -> dict:
        """Allowlisted, redacted view for logs. NEVER logs the API key, whole
        Settings, or raw model_dump(). Use allowlisted metadata only."""
        return {
            "provider_base_url": str(self.provider_base_url),
            "provider_model": self.provider_model,
            "request_timeout_s": self.request_timeout_s,
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
# Production-shaped adapter (illustrative; NOT executed against a real network)
# ---------------------------------------------------------------------------
class OpenAICompatibleAdapter:
    """Hides SDK/HTTP construction, request shaping, vendor response extraction,
    and vendor-specific exceptions behind the small AIProvider seam. It owns NO
    Job lifecycle. Day45 does NOT run this against a real Provider (that is
    Day53); it exists to show the seam and error-translation boundary."""

    def __init__(self, settings: Settings, http_client: object) -> None:
        self._settings = settings
        self._http = http_client  # owned by the lifespan, not by the adapter

    async def generate(self, *, prompt: str, max_tokens: int) -> str:  # pragma: no cover
        # Illustrative only. A real OpenAI-compatible call + robust vendor-error
        # translation (timeout/rate-limit/auth/transport) is implemented in Day53.
        raise NotImplementedError(
            "OpenAICompatibleAdapter.generate is not wired to a real Provider in "
            "Day45; inject a FakeAIProvider for deterministic no-network tests."
        )


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
# Request/response models for the illustrative use-site
# ---------------------------------------------------------------------------
class RunJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    max_tokens: int = Field(ge=1, le=8_000)


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
    app.state.completed = []  # illustrative in-memory completion (NOT PostgreSQL)

    @app.post("/jobs/run")
    async def run_job(
        body: RunJobRequest,
        request: Request,
        service: JobService = Depends(get_job_service),
    ):
        # Validation-before-side-effect: if the raw Provider JSON is invalid,
        # run_job raises before we append to the completion list.
        result = await service.run_job(prompt=body.prompt, max_tokens=body.max_tokens)
        request.app.state.completed.append(result)
        return {"summary": result.summary, "confidence": result.confidence}

    @app.get("/healthz")
    async def healthz(request: Request):
        ready = getattr(request.app.state, "container", None) is not None
        return {"ready": ready}

    return app
