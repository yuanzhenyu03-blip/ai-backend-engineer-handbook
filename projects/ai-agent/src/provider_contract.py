"""Day72 — Provider Capabilities and the Replaceable Provider Adapter (Phase 7A).

Provider-independent contract surface for the LLM Application Runtime. Standard library only.

Core boundaries (decided in the Day72 class, built on Day53's ProviderRequest -> ProviderOutcome seam
and Day61's real-HTTP Adapter foundation):

* The application owns a STABLE product contract (e.g. ``research_claims.v1``). Providers only offer
  VERSIONED capabilities.
* A ``CapabilityProfile`` is an immutable, versioned audit fact bound to Provider + model + API version +
  profile version + Adapter version + verification tier. Published revisions are never edited in place;
  drift disables/quarantines the old revision for NEW selections and a NEW revision is published.
* Capability admission happens BEFORE a paid Provider call. Known incompatibility -> ``CAPABILITY_ERROR``
  with zero Provider calls; the contract is never weakened to a lowest-common-denominator.
* The ``ProviderAdapter`` translates Provider-specific requests, responses and failures into the stable
  surface, keeping SDK/wire types behind the boundary. The Adapter does NOT hide retries, switch Providers,
  or decide Job terminal state.
* A Provider ``SUCCESS`` is still an UNTRUSTED candidate: it must pass schema, evidence and policy gates plus
  guarded completion (owned by the Runtime, not this module).
* ``TIMEOUT_UNKNOWN`` is reconciled, never blindly retried.

This module is CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME (deterministic in-process). It performs NO real
SDK, HTTP, Provider, database, credential, cost or Production work.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, FrozenSet, Mapping, Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# 1. Stable, application-owned outcome surface (Provider-independent).
# ---------------------------------------------------------------------------
class ProviderOutcomeKind(str, Enum):
    """The ONLY outcome vocabulary the application reasons about. Each concrete Adapter maps its
    Provider-specific evidence into exactly one of these; recovery differs per kind, so the
    distinctions are preserved and never collapsed."""

    SUCCESS = "SUCCESS"                              # untrusted candidate; still needs Runtime validation
    PROVIDER_RESPONSE_INVALID = "PROVIDER_RESPONSE_INVALID"  # wire/envelope violates its bound contract
    REFUSAL = "REFUSAL"
    TRUNCATION = "TRUNCATION"                        # output ended before the required result was complete
    RATE_LIMITED = "RATE_LIMITED"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    CAPABILITY_ERROR = "CAPABILITY_ERROR"            # incompatible capability; raised pre-call, zero calls
    TIMEOUT_UNKNOWN = "TIMEOUT_UNKNOWN"              # execution/cost unknown -> reconcile, never blind retry
    TRANSPORT_ERROR = "TRANSPORT_ERROR"


@dataclass(frozen=True)
class ProviderOutcome:
    """A stable, safe outcome. Carries ONLY minimized application-safe evidence — never SDK objects,
    raw prompts, secrets, or full Provider payloads. ``safe_evidence`` is a small, explicit map."""

    kind: ProviderOutcomeKind
    provider_request_id: Optional[str] = None    # Provider-minted identity (distinct from correlation_id)
    detail: str = ""                             # short, safe reason (e.g. finish reason label)
    safe_evidence: Mapping[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 2. Provider-independent request (application-owned meaning only).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ApplicationRequest:
    """What the application MEANS, independent of any Provider's request syntax. The concrete Adapter maps
    this to Provider-specific wire fields; business code never writes Provider request syntax."""

    job_id: str
    tenant_id: str
    application_contract: str        # e.g. "research_claims.v1"
    task_type: str
    max_output_tokens: int
    correlation_id: str              # application-minted pre-call identity (NOT the Provider request id)
    prompt: str = field(repr=False, default="")   # transport-only; never persisted/logged


# ---------------------------------------------------------------------------
# 3. Versioned Capability Profile (immutable, disable/quarantine-able audit fact).
# ---------------------------------------------------------------------------
class ProfileStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    QUARANTINED = "QUARANTINED"


class VerificationTier(str, Enum):
    """Honest evidence level for a capability CLAIM. Provider docs/marketing are only DECLARED."""

    DECLARED = "DECLARED"                       # documentation/marketing input fact; not compatibility proof
    STATIC = "STATIC"                           # Adapter translation review
    EXECUTED_LOCAL_RUNTIME = "EXECUTED_LOCAL_RUNTIME"   # deterministic in-process translation execution
    INTEGRATION_RUNTIME = "INTEGRATION_RUNTIME"         # real SDK/HTTP boundary, only when actually run
    PRODUCTION = "PRODUCTION"                           # real production evidence, only when established


@dataclass(frozen=True)
class CapabilityProfile:
    """A current, versioned capability FACT. Immutable: a published revision is never mutated; drift
    disables/quarantines it and a NEW revision (new profile_version) is published."""

    profile_id: str
    provider_name: str
    model: str
    api_version: str
    profile_version: str
    adapter_version: str
    supported_contracts: FrozenSet[str]          # application contracts this profile is VERIFIED to satisfy
    requires_request_identity: bool              # whether a Provider request id is mandatory in responses
    verification_tier: VerificationTier
    status: ProfileStatus = ProfileStatus.ACTIVE

    def supports(self, application_contract: str) -> bool:
        return application_contract in self.supported_contracts

    def is_selectable(self) -> bool:
        """Only ACTIVE profiles may be selected for NEW dispatches (fail closed)."""
        return self.status is ProfileStatus.ACTIVE

    # Lifecycle transitions return NEW frozen instances; the audit fact is never edited in place.
    def disabled(self) -> "CapabilityProfile":
        return replace(self, status=ProfileStatus.DISABLED)

    def quarantined(self) -> "CapabilityProfile":
        return replace(self, status=ProfileStatus.QUARANTINED)


# ---------------------------------------------------------------------------
# 4. Immutable per-Attempt execution contract (persisted binding).
# ---------------------------------------------------------------------------
class AttemptState(str, Enum):
    PLANNED = "PLANNED"
    DISPATCHED = "DISPATCHED"
    BLOCKED_PROFILE_DISABLED = "BLOCKED_PROFILE_DISABLED"


@dataclass(frozen=True)
class AttemptExecutionContract:
    """Snapshot of the profile/versions bound to ONE Attempt when it was planned/dispatched. The current
    configuration governs NEW calls; this persisted contract governs interpretation of an already-issued
    call. It is never rewritten to a different profile — a re-plan is an explicit NEW Attempt."""

    attempt_id: str
    job_id: str
    profile_id: str
    provider_name: str
    model: str
    api_version: str
    profile_version: str
    adapter_version: str
    application_contract: str
    state: AttemptState = AttemptState.PLANNED

    @classmethod
    def plan(cls, attempt_id: str, job_id: str, profile: CapabilityProfile,
             application_contract: str) -> "AttemptExecutionContract":
        return cls(
            attempt_id=attempt_id, job_id=job_id, profile_id=profile.profile_id,
            provider_name=profile.provider_name, model=profile.model, api_version=profile.api_version,
            profile_version=profile.profile_version, adapter_version=profile.adapter_version,
            application_contract=application_contract,
        )


# ---------------------------------------------------------------------------
# 5. Capability admission (BEFORE any paid call).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AdmissionResult:
    admitted: bool
    outcome: Optional[ProviderOutcome] = None    # a CAPABILITY_ERROR outcome when not admitted


def admit_capability(profile: CapabilityProfile, application_contract: str) -> AdmissionResult:
    """Pre-call admission. A selectable profile that VERIFIABLY supports the exact application contract is
    admitted; otherwise a ``CAPABILITY_ERROR`` is returned and NO Provider call may be made. This never
    weakens the contract to a lowest-common-denominator. A passing pre-call check does not guarantee runtime
    success — the actual response is still new evidence the Runtime must classify."""

    if not profile.is_selectable():
        return AdmissionResult(False, ProviderOutcome(
            ProviderOutcomeKind.CAPABILITY_ERROR, detail="profile_not_selectable",
            safe_evidence={"profile_id": profile.profile_id, "status": profile.status.value}))
    if not profile.supports(application_contract):
        return AdmissionResult(False, ProviderOutcome(
            ProviderOutcomeKind.CAPABILITY_ERROR, detail="contract_not_supported",
            safe_evidence={"profile_id": profile.profile_id, "contract": application_contract}))
    return AdmissionResult(True)


# ---------------------------------------------------------------------------
# 6. The stable ProviderAdapter Protocol + a Registry / selection boundary.
# ---------------------------------------------------------------------------
@runtime_checkable
class ProviderAdapter(Protocol):
    """The ONLY seam business code depends on. Concrete Adapters own Provider-specific wire fields and
    reason codes. The Adapter observes and translates FACTS; it must not hide retries, switch Providers, or
    decide Job terminal state."""

    @property
    def capability_profile(self) -> CapabilityProfile: ...

    def build_wire_request(self, request: ApplicationRequest) -> Dict[str, object]:
        """Translate the provider-independent request into Provider-specific wire fields."""
        ...

    def translate_outcome(self, wire_response: Mapping[str, object]) -> ProviderOutcome:
        """Translate a Provider-specific response/finish/error into the stable ProviderOutcome surface."""
        ...


class ProfileDisabledError(Exception):
    """Raised when a disabled/quarantined profile is selected — the Registry fails closed."""


class ProviderRegistry:
    """Injects the concrete Adapter for a selected profile through a composition boundary. Business code
    never constructs concrete Adapters or branches on Provider identity."""

    def __init__(self) -> None:
        self._by_profile: Dict[str, ProviderAdapter] = {}

    def register(self, adapter: ProviderAdapter) -> None:
        self._by_profile[adapter.capability_profile.profile_id] = adapter

    def get(self, profile_id: str) -> ProviderAdapter:
        if profile_id not in self._by_profile:
            raise KeyError(profile_id)
        adapter = self._by_profile[profile_id]
        if not adapter.capability_profile.is_selectable():
            raise ProfileDisabledError(profile_id)   # fail closed on DISABLED/QUARANTINED
        return adapter


@dataclass(frozen=True)
class ProductOption:
    """A CONSTRAINED client selector — never a Provider/model/profile authority."""

    tier: str                     # e.g. "standard" | "high_fidelity"; server maps it to an allowlisted profile


class ProviderSelectionPolicy:
    """Server-owned allowlist. Maps a constrained client ProductOption to an approved, selectable
    CapabilityProfile. Clients cannot authorize arbitrary Provider/model/profile identifiers."""

    def __init__(self, allowlist: Mapping[str, CapabilityProfile]) -> None:
        self._allowlist = dict(allowlist)

    def select(self, option: ProductOption, application_contract: str) -> CapabilityProfile:
        if option.tier not in self._allowlist:
            raise KeyError(option.tier)
        profile = self._allowlist[option.tier]
        if not profile.is_selectable():
            raise ProfileDisabledError(profile.profile_id)
        return profile
