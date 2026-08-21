"""Day72 — concrete Provider Adapters over a controlled, in-process transport (standard library only).

Two fictional Providers (A and B) with DIFFERENT wire field names and DIFFERENT output-limit finish states,
each mapping to the SAME stable application surface. Each Adapter owns its OWN transport (injected at
construction) and exposes ``execute()`` — callers never pass a transport. The ``RecordingTransport`` records
calls so tests can prove that capability rejection / binding failure / a spent Attempt make ZERO new Provider
calls. There is NO network and NO real Provider.

All wire shapes here are classroom fixtures, not real API claims. Provider capabilities are current,
versioned facts bound to a CapabilityProfile — never permanent, Provider-wide truths.

``dispatch_attempt`` runs the pre-call gates in order — persisted-binding validation -> capability admission
-> guarded compare-and-set state transition — and then makes AT MOST ONE external call via the Adapter's own
transport. ``provider_calls`` counts THIS dispatch (0 or 1), never the transport's cumulative history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping

from provider_contract import (
    AdmissionResult,
    ApplicationRequest,
    AttemptExecutionContract,
    AttemptState,
    AttemptStateError,
    AttemptStateStore,
    CapabilityProfile,
    ProviderAdapter,
    ProviderOutcome,
    ProviderOutcomeKind,
    admit_capability,
    validate_attempt_binding,
)


# ---------------------------------------------------------------------------
# Controlled in-process transport (records calls; no network, no Provider).
# ---------------------------------------------------------------------------
@dataclass
class RecordingTransport:
    """Records every wire request it is asked to send and replays a scripted wire response. This stands in
    for a Provider SDK/HTTP client and stays ENTIRELY behind the Adapter boundary."""

    scripted_response: Mapping[str, object]
    calls: List[Dict[str, object]] = field(default_factory=list)

    def send(self, wire_request: Mapping[str, object]) -> Mapping[str, object]:
        self.calls.append(dict(wire_request))
        return dict(self.scripted_response)


# ---------------------------------------------------------------------------
# Provider A adapter — wire uses `max_tokens` and finish reason `length`.
# ---------------------------------------------------------------------------
class ProviderAAdapter:
    def __init__(self, transport: RecordingTransport, profile: CapabilityProfile) -> None:
        self._transport = transport   # Provider-specific client stays inside the Adapter (constructor-injected)
        self._profile = profile

    @property
    def capability_profile(self) -> CapabilityProfile:
        return self._profile

    def build_wire_request(self, request: ApplicationRequest) -> Dict[str, object]:
        # Provider A's SPECIFIC request syntax lives here, not in business code.
        return {
            "model": self._profile.model,
            "max_tokens": request.max_output_tokens,       # Provider A field name
            "input": request.prompt,
            "trace": request.correlation_id,
        }

    def execute(self, request: ApplicationRequest) -> ProviderOutcome:
        # Full cycle over the Adapter's OWN transport; exactly one external call.
        wire_response = self._transport.send(self.build_wire_request(request))
        return self.translate_outcome(wire_response)

    def translate_outcome(self, wire_response: Mapping[str, object]) -> ProviderOutcome:
        req_id = wire_response.get("id")                   # Provider A request-identity field
        if self._profile.requires_request_identity and not req_id:
            return ProviderOutcome(ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID,
                                   detail="missing_provider_request_id")
        finish = wire_response.get("finish_reason")
        if finish == "length":                             # Provider A output-limit state
            return ProviderOutcome(ProviderOutcomeKind.TRUNCATION, provider_request_id=str(req_id),
                                   detail="finish_reason=length")
        if finish == "stop":
            return ProviderOutcome(ProviderOutcomeKind.SUCCESS, provider_request_id=str(req_id),
                                   detail="finish_reason=stop")
        return ProviderOutcome(ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID, provider_request_id=str(req_id),
                               detail="unknown_finish_reason")


# ---------------------------------------------------------------------------
# Provider B adapter — wire uses `maxOutputTokens` and finish state `MAX_TOKENS`.
# ---------------------------------------------------------------------------
class ProviderBAdapter:
    def __init__(self, transport: RecordingTransport, profile: CapabilityProfile) -> None:
        self._transport = transport
        self._profile = profile

    @property
    def capability_profile(self) -> CapabilityProfile:
        return self._profile

    def build_wire_request(self, request: ApplicationRequest) -> Dict[str, object]:
        # Provider B's DIFFERENT request syntax — a different field name for the same MEANING.
        return {
            "modelId": self._profile.model,
            "maxOutputTokens": request.max_output_tokens,  # Provider B field name (different from A)
            "content": request.prompt,
            "correlationId": request.correlation_id,
        }

    def execute(self, request: ApplicationRequest) -> ProviderOutcome:
        wire_response = self._transport.send(self.build_wire_request(request))
        return self.translate_outcome(wire_response)

    def translate_outcome(self, wire_response: Mapping[str, object]) -> ProviderOutcome:
        req_id = wire_response.get("responseId")           # Provider B request-identity field (different key)
        if self._profile.requires_request_identity and not req_id:
            return ProviderOutcome(ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID,
                                   detail="missing_provider_request_id")
        state = wire_response.get("completionState")
        if state == "MAX_TOKENS":                          # Provider B output-limit state (different label)
            return ProviderOutcome(ProviderOutcomeKind.TRUNCATION, provider_request_id=str(req_id),
                                   detail="completionState=MAX_TOKENS")
        if state == "COMPLETE":
            return ProviderOutcome(ProviderOutcomeKind.SUCCESS, provider_request_id=str(req_id),
                                   detail="completionState=COMPLETE")
        return ProviderOutcome(ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID, provider_request_id=str(req_id),
                               detail="unknown_completion_state")


# ---------------------------------------------------------------------------
# Dispatch: binding -> admission -> guarded state transition -> AT MOST ONE call.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DispatchResult:
    outcome: ProviderOutcome
    provider_calls: int                 # THIS dispatch only: 0 or 1 (never the transport's cumulative total)
    attempt_state: AttemptState         # the Attempt state AFTER this dispatch


def dispatch_attempt(*, request: ApplicationRequest, contract: AttemptExecutionContract,
                     adapter: ProviderAdapter, state_store: AttemptStateStore) -> DispatchResult:
    """Dispatch one Attempt through the injected Adapter (which owns its transport). Order of pre-call gates:

    1. Only a ``PLANNED`` Attempt may dispatch; any other current state is rejected (``AttemptStateError``),
       zero new Provider calls.
    2. Persisted-binding validation: request.job_id / request.application_contract / the six profile version
       fields must match the Attempt contract and the Adapter's profile exactly; else ``AttemptBindingError``
       (an application invariant, NOT a Provider failure), zero calls, contract never rewritten/switched.
    3. Capability admission: a disabled/quarantined profile is a guarded PLANNED -> BLOCKED_PROFILE_DISABLED
       transition (zero calls, contract binding preserved); a contract the profile does not support returns a
       CAPABILITY_ERROR outcome (zero calls).
    4. A compare-and-set PLANNED -> DISPATCHED transition guards the single external call; a failed CAS means
       zero calls. Only then is the ONE Provider call made via the Adapter's own transport.
    """

    current = state_store.get(contract.attempt_id)
    if current is None:
        raise AttemptStateError(f"unknown attempt (not planned): {contract.attempt_id}")
    if current is not AttemptState.PLANNED:
        # A second dispatch, or a dispatch of an already-DISPATCHED/BLOCKED Attempt.
        raise AttemptStateError(
            f"attempt {contract.attempt_id} is {current.value}, only PLANNED may dispatch")

    # (2) Persisted-binding validation BEFORE any admission or call.
    validate_attempt_binding(request, contract, adapter.capability_profile)

    # (3) Capability admission.
    admission: AdmissionResult = admit_capability(adapter.capability_profile, request.application_contract)
    if not admission.admitted:
        assert admission.outcome is not None
        if admission.outcome.detail == "profile_not_selectable":
            # Real guarded state path: PLANNED -> BLOCKED_PROFILE_DISABLED (binding preserved, zero calls).
            if not state_store.compare_and_set(contract.attempt_id, AttemptState.PLANNED,
                                                AttemptState.BLOCKED_PROFILE_DISABLED):
                raise AttemptStateError(f"could not block attempt {contract.attempt_id}")
            return DispatchResult(admission.outcome, provider_calls=0,
                                  attempt_state=AttemptState.BLOCKED_PROFILE_DISABLED)
        # contract_not_supported: pre-admission rejection, Attempt stays PLANNED, zero calls.
        return DispatchResult(admission.outcome, provider_calls=0, attempt_state=AttemptState.PLANNED)

    # (4) Guarded single-call transition. CAS failure -> zero calls.
    if not state_store.compare_and_set(contract.attempt_id, AttemptState.PLANNED, AttemptState.DISPATCHED):
        raise AttemptStateError(f"attempt {contract.attempt_id} could not transition PLANNED -> DISPATCHED")

    outcome = adapter.execute(request)   # the ONE authorized external call for this Attempt
    return DispatchResult(outcome, provider_calls=1, attempt_state=AttemptState.DISPATCHED)
