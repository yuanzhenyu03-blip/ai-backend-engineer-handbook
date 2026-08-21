"""Day72 — Provider Capabilities and the Replaceable Provider Adapter (Phase 7A).

Provider-independent contract surface for the LLM Application Runtime. Standard library only.

Core boundaries (Day72, hardened across two code-review rounds; built on Day53's ProviderRequest ->
ProviderOutcome seam and Day61's real-HTTP Adapter foundation):

* The application owns a STABLE product contract (e.g. ``research_claims.v1``). Providers only offer
  VERSIONED capabilities. A published ``CapabilityProfile`` revision is an IMMUTABLE audit fact; its current
  operational lifecycle status (ACTIVE / DISABLED / QUARANTINED) is tracked in a SEPARATE overlay so a
  lifecycle change never rewrites a historical revision or a bound Attempt's interpretation.
* The Attempt state store holds the AUTHORITATIVE, immutable ``AttemptExecutionContract`` per Attempt (not
  just an id -> state map). ``dispatch`` reads that authoritative contract and rejects any caller-supplied
  contract that does not match it EXACTLY (``AttemptBindingError``) — a self-consistent forged
  request+contract+Adapter trio cannot make a call.
* Before any paid call the Runtime enforces, in order: (1) the authoritative binding; (2) the request/profile
  binding; (3) capability admission against the CURRENT lifecycle status; (4) a thread-safe compare-and-set
  Attempt-state transition (bound to identity + full binding + expected state) so one Attempt makes at most
  one external call.
* The ``ProviderAdapter`` owns its transport and translates Provider-specific requests, responses AND
  failures into the stable surface via ``execute()``, keeping SDK/wire types behind the boundary. The Adapter
  does NOT hide retries, switch Providers, decide Job terminal state, create the next Attempt, or turn
  ``TIMEOUT_UNKNOWN`` into a retryable ``TRANSPORT_ERROR``.
* A Provider ``SUCCESS`` is still an UNTRUSTED candidate: schema/evidence/policy + guarded completion are the
  Runtime's, not this module's. ``TIMEOUT_UNKNOWN`` is reconciled, never blindly retried.

This module is CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME (deterministic in-process). It performs NO real
SDK, HTTP, Provider, database, credential, cost or Production work. ``InMemoryAttemptStateStore`` uses a
``threading.RLock`` to model an atomic compare-and-set for deterministic IN-PROCESS concurrency only; a
production deployment needs a durable database conditional UPDATE / transaction (or equivalent).
"""

from __future__ import annotations

import threading
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
# 3. Versioned Capability Profile (immutable published revision) + lifecycle overlay.
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
    """A current, versioned capability FACT (an immutable PUBLISHED revision). ``status`` is the status the
    revision was published with; the CURRENT operational lifecycle status lives in a separate
    ``ProfileLifecycle`` overlay so a live disable/quarantine never mutates this published fact and never
    changes how an already-bound Attempt is interpreted."""

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

    # Convenience revisions (used to publish a DIFFERENT starting status); the lifecycle overlay, not these,
    # is what a live disable/quarantine changes.
    def disabled(self) -> "CapabilityProfile":
        return replace(self, status=ProfileStatus.DISABLED)

    def quarantined(self) -> "CapabilityProfile":
        return replace(self, status=ProfileStatus.QUARANTINED)


class ProfileLifecycle:
    """Current operational status per profile_id (an overlay/catalog), SEPARATE from the immutable published
    revisions. A lifecycle update affects NEW selections and dispatch admission; it never edits a published
    revision's binding, and an already-bound Attempt is still interpreted by its original binding."""

    def __init__(self) -> None:
        self._status: Dict[str, ProfileStatus] = {}
        self._lock = threading.RLock()

    def register(self, profile: CapabilityProfile) -> None:
        with self._lock:
            self._status.setdefault(profile.profile_id, profile.status)

    def set_status(self, profile_id: str, status: ProfileStatus) -> None:
        with self._lock:
            self._status[profile_id] = status

    def disable(self, profile_id: str) -> None:
        self.set_status(profile_id, ProfileStatus.DISABLED)

    def quarantine(self, profile_id: str) -> None:
        self.set_status(profile_id, ProfileStatus.QUARANTINED)

    def status(self, profile_id: str) -> ProfileStatus:
        with self._lock:
            return self._status.get(profile_id, ProfileStatus.ACTIVE)

    def is_active(self, profile_id: str) -> bool:
        return self.status(profile_id) is ProfileStatus.ACTIVE


# ---------------------------------------------------------------------------
# 4. Immutable per-Attempt execution contract (persisted binding).
# ---------------------------------------------------------------------------
BINDING_FIELDS = (
    "profile_id", "provider_name", "model", "api_version", "profile_version", "adapter_version",
)


@dataclass(frozen=True)
class AttemptExecutionContract:
    """Snapshot of the profile/versions bound to ONE Attempt when it was planned. IMMUTABLE; never rewritten
    to a different profile — a re-plan is an explicit NEW Attempt. Equality (frozen dataclass) covers every
    binding field, so it can be compared as a whole for authoritative-binding checks."""

    attempt_id: str
    job_id: str
    profile_id: str
    provider_name: str
    model: str
    api_version: str
    profile_version: str
    adapter_version: str
    application_contract: str

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
# 5. Application-invariant errors (NOT Provider failures).
# ---------------------------------------------------------------------------
class AttemptBindingError(Exception):
    """The dispatch inputs do not match the Attempt's AUTHORITATIVE persisted execution contract
    (job/contract/profile/versions), or a caller-supplied contract differs from the stored one. This is an
    APPLICATION INVARIANT violation — never a Provider failure. Zero Provider calls; the original contract is
    never reinterpreted, overwritten, or auto-switched to another Provider/Profile."""


class AttemptStateError(Exception):
    """A guarded Attempt state transition was rejected (second dispatch, non-PLANNED dispatch, or a lost
    compare-and-set race). Zero NEW Provider calls."""


class DuplicateProfileRegistrationError(Exception):
    """A different Adapter was registered under an already-registered profile_id. Changing a Profile's
    Adapter behaviour requires publishing a NEW Profile revision, not overwriting an identity in place."""


class ProviderIncompatibleError(Exception):
    """A selected Profile does not support the required application contract. Selection fails closed BEFORE
    any Attempt is persisted or any paid call is made; no lowest-common-denominator downgrade, no automatic
    fallback."""


# ---------------------------------------------------------------------------
# 6. Guarded Attempt state store (holds the AUTHORITATIVE contract; thread-safe compare-and-set).
# ---------------------------------------------------------------------------
class AttemptState(str, Enum):
    PLANNED = "PLANNED"
    DISPATCHED = "DISPATCHED"
    BLOCKED_PROFILE_DISABLED = "BLOCKED_PROFILE_DISABLED"


@dataclass(frozen=True)
class AttemptRecord:
    """The authoritative, immutable per-Attempt record: the persisted execution contract plus the current
    guarded state."""

    contract: AttemptExecutionContract
    state: AttemptState


@runtime_checkable
class AttemptStateStore(Protocol):
    """Holds each Attempt's AUTHORITATIVE ``AttemptExecutionContract`` and guards the 'one Attempt -> at most
    one external call' invariant with a compare-and-set bound to (identity + full binding + expected state).
    A production slice is a durable, atomic store (a DB row with a conditional UPDATE)."""

    def plan(self, contract: AttemptExecutionContract) -> None:
        """Register a NEW Attempt (PLANNED) with its authoritative contract; reject a duplicate attempt_id."""
        ...

    def get_record(self, attempt_id: str) -> Optional[AttemptRecord]:
        ...

    def compare_and_set(self, contract: AttemptExecutionContract, expected: AttemptState,
                        new: AttemptState) -> bool:
        """Atomically set the state to ``new`` ONLY if the stored record for ``contract.attempt_id`` has
        BOTH an equal authoritative ``contract`` AND state == ``expected``. Returns True on success, else
        False (no change). Check and write occur in ONE critical section."""
        ...


class InMemoryAttemptStateStore:
    """A tiny, injectable in-memory ``AttemptStateStore`` for the deterministic local slice. Uses an
    ``RLock`` so ``plan``, ``get_record`` and ``compare_and_set`` share one synchronization boundary and the
    CAS check+write are atomic for IN-PROCESS threads. NOT a production-grade durable/atomic database — a
    production deployment needs a DB conditional UPDATE / transaction."""

    def __init__(self) -> None:
        self._records: Dict[str, AttemptRecord] = {}
        self._lock = threading.RLock()

    def plan(self, contract: AttemptExecutionContract) -> None:
        with self._lock:
            if contract.attempt_id in self._records:
                raise AttemptStateError(f"attempt already registered: {contract.attempt_id}")
            self._records[contract.attempt_id] = AttemptRecord(contract=contract, state=AttemptState.PLANNED)

    def get_record(self, attempt_id: str) -> Optional[AttemptRecord]:
        with self._lock:
            return self._records.get(attempt_id)

    def compare_and_set(self, contract: AttemptExecutionContract, expected: AttemptState,
                        new: AttemptState) -> bool:
        with self._lock:
            rec = self._records.get(contract.attempt_id)
            if rec is None or rec.contract != contract or rec.state != expected:
                return False
            self._records[contract.attempt_id] = AttemptRecord(contract=rec.contract, state=new)
            return True


# ---------------------------------------------------------------------------
# 7. Binding validation (BEFORE admission and before any call).
# ---------------------------------------------------------------------------
def validate_attempt_binding(request: ApplicationRequest, contract: AttemptExecutionContract,
                             profile: CapabilityProfile) -> None:
    """Raise ``AttemptBindingError`` unless the dispatch inputs EXACTLY match the AUTHORITATIVE Attempt
    contract: request.job_id, request.application_contract, and every profile binding field
    (profile_id/provider_name/model/api_version/profile_version/adapter_version). No reinterpretation,
    overwrite, or auto-switch is ever performed."""

    if request.job_id != contract.job_id:
        raise AttemptBindingError(f"job_id mismatch: request={request.job_id} contract={contract.job_id}")
    if request.application_contract != contract.application_contract:
        raise AttemptBindingError(
            f"application_contract mismatch: request={request.application_contract} "
            f"contract={contract.application_contract}")
    for f in BINDING_FIELDS:
        want = getattr(contract, f)
        got = getattr(profile, f)
        if want != got:
            raise AttemptBindingError(f"{f} mismatch: adapter_profile={got} contract={want}")


# ---------------------------------------------------------------------------
# 8. Capability admission (BEFORE any paid call) against the CURRENT lifecycle status.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AdmissionResult:
    admitted: bool
    outcome: Optional[ProviderOutcome] = None    # a CAPABILITY_ERROR outcome when not admitted


def admit_capability(profile: CapabilityProfile, application_contract: str,
                     current_status: ProfileStatus) -> AdmissionResult:
    """Pre-call admission. The profile must be ACTIVE by its CURRENT lifecycle status AND verifiably support
    the exact application contract; otherwise a ``CAPABILITY_ERROR`` is returned and NO Provider call may be
    made. Never a lowest-common-denominator weakening. A passing pre-call check does not guarantee runtime
    success — the actual response is still new evidence the Runtime must classify."""

    if current_status is not ProfileStatus.ACTIVE:
        return AdmissionResult(False, ProviderOutcome(
            ProviderOutcomeKind.CAPABILITY_ERROR, detail="profile_not_selectable",
            safe_evidence={"profile_id": profile.profile_id, "status": current_status.value}))
    if not profile.supports(application_contract):
        return AdmissionResult(False, ProviderOutcome(
            ProviderOutcomeKind.CAPABILITY_ERROR, detail="contract_not_supported",
            safe_evidence={"profile_id": profile.profile_id, "contract": application_contract}))
    return AdmissionResult(True)


# ---------------------------------------------------------------------------
# 9. The stable ProviderAdapter Protocol + a two-purpose Registry / selection boundary.
# ---------------------------------------------------------------------------
@runtime_checkable
class ProviderAdapter(Protocol):
    """The ONLY seam business code depends on. Concrete Adapters own Provider-specific wire fields, reason
    codes, and their OWN constructor-injected transport/client. ``execute`` performs the full
    build-request -> send -> translate cycle using that internal transport AND translates Provider-specific
    failures into the stable surface, so callers never pass a transport and never see an SDK exception. The
    Adapter observes and translates FACTS; it must not hide retries, switch Providers, decide Job terminal
    state, or create the next Attempt."""

    @property
    def capability_profile(self) -> CapabilityProfile: ...

    def execute(self, request: ApplicationRequest) -> ProviderOutcome:
        """Build the Provider-specific request, send it via the Adapter's OWN transport, and translate the
        response OR the Provider-specific failure into the stable ProviderOutcome. Exactly one external send
        attempt per invocation; never raises an SDK exception."""
        ...

    def build_wire_request(self, request: ApplicationRequest) -> Dict[str, object]:
        """Translate the provider-independent request into Provider-specific wire fields (Adapter-internal;
        exposed for static translation review/tests)."""
        ...

    def translate_outcome(self, wire_response: Mapping[str, object]) -> ProviderOutcome:
        """Translate a Provider-specific RESPONSE/finish into the stable ProviderOutcome surface."""
        ...


class ProfileDisabledError(Exception):
    """Raised when a disabled/quarantined profile is SELECTED for a new task — selection fails closed."""


class ProviderRegistry:
    """Injects the concrete Adapter for a profile through a composition boundary, and tracks each profile's
    current lifecycle status (an overlay, separate from the immutable revisions). Two distinct purposes:

    * ``get_selectable(profile_id, application_contract)`` — for NEW tasks: returns the Adapter ONLY if the
      profile is currently ACTIVE and supports the contract (fail closed otherwise). No fallback.
    * ``resolve_bound_attempt(contract)`` — for an ALREADY-persisted Attempt: returns the Adapter bound to
      that Attempt's exact profile/versions REGARDLESS of current status, so the Runtime can perform a
      zero-call block, response interpretation, or audit. Returning it does NOT authorize a new call —
      dispatch admission still sees the current lifecycle status and blocks a disabled profile.

    Business code never constructs concrete Adapters or branches on Provider identity."""

    def __init__(self, lifecycle: Optional[ProfileLifecycle] = None) -> None:
        self._by_profile: Dict[str, ProviderAdapter] = {}
        self._lifecycle = lifecycle if lifecycle is not None else ProfileLifecycle()

    @property
    def lifecycle(self) -> ProfileLifecycle:
        return self._lifecycle

    def register(self, adapter: ProviderAdapter) -> None:
        """Register an Adapter by its profile_id. A conflicting registration under an existing profile_id is
        REJECTED (fail closed); re-registering the EXACT same Adapter instance is an idempotent no-op."""
        pid = adapter.capability_profile.profile_id
        existing = self._by_profile.get(pid)
        if existing is not None and existing is not adapter:
            raise DuplicateProfileRegistrationError(pid)
        self._by_profile[pid] = adapter
        self._lifecycle.register(adapter.capability_profile)

    # Lifecycle updates (affect NEW selection + dispatch admission; never edit a revision or a bound Attempt).
    def disable(self, profile_id: str) -> None:
        self._lifecycle.disable(profile_id)

    def quarantine(self, profile_id: str) -> None:
        self._lifecycle.quarantine(profile_id)

    def get_selectable(self, profile_id: str, application_contract: str) -> ProviderAdapter:
        if profile_id not in self._by_profile:
            raise KeyError(profile_id)
        if not self._lifecycle.is_active(profile_id):
            raise ProfileDisabledError(profile_id)                 # fail closed for NEW selection
        adapter = self._by_profile[profile_id]
        if not adapter.capability_profile.supports(application_contract):
            raise ProviderIncompatibleError(f"{profile_id} does not support {application_contract}")
        return adapter

    def resolve_bound_attempt(self, contract: AttemptExecutionContract) -> ProviderAdapter:
        """Resolve the Adapter bound to an already-persisted Attempt by its EXACT profile/versions, even if
        the profile is now disabled/quarantined. Raises ``AttemptBindingError`` if the registered Adapter's
        immutable binding does not match the Attempt contract."""
        pid = contract.profile_id
        if pid not in self._by_profile:
            raise KeyError(pid)
        adapter = self._by_profile[pid]
        p = adapter.capability_profile
        for f in BINDING_FIELDS:
            if getattr(p, f) != getattr(contract, f):
                raise AttemptBindingError(
                    f"bound adapter {f} mismatch: adapter={getattr(p, f)} contract={getattr(contract, f)}")
        return adapter


@dataclass(frozen=True)
class ProductOption:
    """A CONSTRAINED client selector — never a Provider/model/profile authority."""

    tier: str                     # e.g. "standard" | "high_fidelity"; server maps it to an allowlisted profile


class ProviderSelectionPolicy:
    """Server-owned allowlist. Maps a constrained client ProductOption to an approved CapabilityProfile that
    is currently ACTIVE (per the shared lifecycle overlay when provided) AND supports the required
    application contract. Clients cannot authorize arbitrary Provider/model/profile identifiers."""

    def __init__(self, allowlist: Mapping[str, CapabilityProfile],
                 lifecycle: Optional[ProfileLifecycle] = None) -> None:
        self._allowlist = dict(allowlist)
        self._lifecycle = lifecycle

    def _current_status(self, profile: CapabilityProfile) -> ProfileStatus:
        if self._lifecycle is not None:
            return self._lifecycle.status(profile.profile_id)
        return profile.status

    def select(self, option: ProductOption, application_contract: str) -> CapabilityProfile:
        if option.tier not in self._allowlist:
            raise KeyError(option.tier)
        profile = self._allowlist[option.tier]
        if self._current_status(profile) is not ProfileStatus.ACTIVE:
            raise ProfileDisabledError(profile.profile_id)          # fail closed
        if not profile.supports(application_contract):
            raise ProviderIncompatibleError(
                f"profile {profile.profile_id} does not support {application_contract}")
        return profile
