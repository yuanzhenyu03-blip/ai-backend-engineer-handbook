"""Day72 — concrete Provider Adapters over a controlled, in-process transport (standard library only).

Two fictional Providers (A and B) with DIFFERENT wire field names and DIFFERENT output-limit finish states,
each mapping to the SAME stable application surface. The ``RecordingTransport`` records calls so tests can
prove that capability rejection makes ZERO Provider calls. There is NO network and NO real Provider.

All wire shapes here are classroom fixtures, not real API claims. Provider capabilities are current,
versioned facts bound to a CapabilityProfile — never permanent, Provider-wide truths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

from provider_contract import (
    AdmissionResult,
    ApplicationRequest,
    AttemptExecutionContract,
    CapabilityProfile,
    ProfileStatus,
    ProviderAdapter,
    ProviderOutcome,
    ProviderOutcomeKind,
    ProviderRegistry,
    VerificationTier,
    admit_capability,
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
        self._transport = transport   # Provider-specific client stays inside the Adapter
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
# Dispatch: admission BEFORE any call, then adapter translation.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DispatchResult:
    outcome: ProviderOutcome
    provider_calls: int
    execution_contract: AttemptExecutionContract


def dispatch_attempt(*, request: ApplicationRequest, contract: AttemptExecutionContract,
                     adapter: ProviderAdapter, transport: RecordingTransport) -> DispatchResult:
    """Admit capability (no call on failure), then build the Provider-specific wire request, send it through
    the transport, and translate the response into the stable surface. The number of Provider calls is
    reported honestly. This helper does NOT retry, switch Providers, or complete the Job — that is Runtime
    policy owned elsewhere (Day71)."""

    admission: AdmissionResult = admit_capability(adapter.capability_profile, request.application_contract)
    if not admission.admitted:
        # Incompatible capability -> zero Provider calls; the contract is not weakened.
        assert admission.outcome is not None
        return DispatchResult(admission.outcome, provider_calls=0, execution_contract=contract)

    wire_request = adapter.build_wire_request(request)
    wire_response = transport.send(wire_request)           # the ONE authorized call for this Attempt
    outcome = adapter.translate_outcome(wire_response)
    return DispatchResult(outcome, provider_calls=len(transport.calls), execution_contract=contract)
