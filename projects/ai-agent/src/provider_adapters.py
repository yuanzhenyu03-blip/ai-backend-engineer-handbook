"""Day72 — concrete Provider Adapters over a controlled, in-process transport (standard library only).

Two fictional Providers (A and B) with DIFFERENT wire field names, DIFFERENT finish states, and DIFFERENT
Provider-specific SDK failure TYPES, each mapping equivalent facts to the SAME stable application surface.
Each Adapter owns its OWN transport (injected at construction) and exposes ``execute()`` — callers never pass
a transport and never see an SDK exception. Failure classification uses explicit structured exception TYPES,
never message-string matching.

There is NO network and NO real Provider. All wire shapes and SDK error types here are classroom fixtures,
not real API claims. Provider capabilities are current, versioned facts bound to a CapabilityProfile.

``dispatch_attempt`` reads the AUTHORITATIVE ``AttemptExecutionContract`` from the state store, rejects a
caller-supplied contract that differs from it (``AttemptBindingError``), validates the request/profile
binding, admits against the CURRENT lifecycle status, then makes AT MOST ONE external call guarded by a
thread-safe compare-and-set. ``provider_calls`` counts THIS dispatch (0 before a send attempt, 1 once a send
attempt begins), never the transport's cumulative history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

from provider_contract import (
    AdmissionResult,
    ApplicationRequest,
    AttemptExecutionContract,
    AttemptBindingError,
    AttemptRecord,
    AttemptState,
    AttemptStateError,
    AttemptStateStore,
    CapabilityProfile,
    ProfileLifecycle,
    ProfileStatus,
    ProviderAdapter,
    ProviderOutcome,
    ProviderOutcomeKind,
    admit_capability,
    validate_attempt_binding,
)


# ---------------------------------------------------------------------------
# Fictional Provider-specific SDK failure TYPES (stay inside each Adapter boundary).
# Structured types — classification never inspects a message string.
# ---------------------------------------------------------------------------
class ProviderASDKError(Exception):
    """Base of Provider A's fictional SDK exceptions."""


class ProviderARefused(ProviderASDKError):
    pass


class ProviderARateLimited(ProviderASDKError):
    def __init__(self, retry_after: Optional[str] = None) -> None:
        super().__init__("rate_limited")
        self.retry_after = retry_after


class ProviderAAuthFailed(ProviderASDKError):
    pass


class ProviderATimedOut(ProviderASDKError):
    def __init__(self, request_id: Optional[str] = None) -> None:
        super().__init__("timed_out")
        self.request_id = request_id


class ProviderAConnectionError(ProviderASDKError):
    pass


class ProviderBSDKError(Exception):
    """Base of Provider B's fictional SDK exceptions (a DIFFERENT type hierarchy)."""


class ProviderBDeclined(ProviderBSDKError):
    pass


class ProviderBThrottled(ProviderBSDKError):
    def __init__(self, retry_after: Optional[str] = None) -> None:
        super().__init__("throttled")
        self.retry_after = retry_after


class ProviderBUnauthorized(ProviderBSDKError):
    pass


class ProviderBDeadlineExceeded(ProviderBSDKError):
    def __init__(self, request_id: Optional[str] = None) -> None:
        super().__init__("deadline_exceeded")
        self.request_id = request_id


class ProviderBNetworkError(ProviderBSDKError):
    pass


# ---------------------------------------------------------------------------
# Controlled in-process transport (records calls; returns a wire response OR raises a scripted SDK error).
# ---------------------------------------------------------------------------
@dataclass
class RecordingTransport:
    """Records every wire request it is asked to send, then either returns a scripted wire response or raises
    a scripted Provider-specific SDK exception. Stands in for a Provider SDK/HTTP client and stays ENTIRELY
    behind the Adapter boundary. The call is recorded BEFORE raising, so a send attempt counts as one call."""

    scripted_response: Optional[Mapping[str, object]] = None
    scripted_error: Optional[Exception] = None
    calls: List[Dict[str, object]] = field(default_factory=list)

    def send(self, wire_request: Mapping[str, object]) -> Mapping[str, object]:
        self.calls.append(dict(wire_request))          # a send attempt began -> recorded as one call
        if self.scripted_error is not None:
            raise self.scripted_error
        return dict(self.scripted_response or {})


# ---------------------------------------------------------------------------
# Provider A adapter — wire uses `max_tokens` / finish reason `length`; A-specific SDK errors.
# ---------------------------------------------------------------------------
class ProviderAAdapter:
    def __init__(self, transport: RecordingTransport, profile: CapabilityProfile) -> None:
        self._transport = transport   # Provider-specific client stays inside the Adapter (constructor-injected)
        self._profile = profile

    @property
    def capability_profile(self) -> CapabilityProfile:
        return self._profile

    def build_wire_request(self, request: ApplicationRequest) -> Dict[str, object]:
        return {
            "model": self._profile.model,
            "max_tokens": request.max_output_tokens,       # Provider A field name
            "input": request.prompt,
            "trace": request.correlation_id,
        }

    def execute(self, request: ApplicationRequest) -> ProviderOutcome:
        """One external send attempt; translate Provider A SDK failures + responses into the stable surface.
        Never raises an SDK exception; never retries; never creates another Attempt or switches Provider."""
        try:
            wire_response = self._transport.send(self.build_wire_request(request))
        except ProviderARateLimited as e:
            ev = {"retry_after": e.retry_after} if e.retry_after else {}
            return ProviderOutcome(ProviderOutcomeKind.RATE_LIMITED, detail="provider_a_rate_limited",
                                   safe_evidence=ev)
        except ProviderAAuthFailed:
            return ProviderOutcome(ProviderOutcomeKind.AUTHENTICATION_ERROR, detail="provider_a_auth_failed")
        except ProviderATimedOut as e:
            # UNKNOWN execution/cost -> reconcile; NOT a retryable transport error.
            return ProviderOutcome(ProviderOutcomeKind.TIMEOUT_UNKNOWN, provider_request_id=e.request_id,
                                   detail="provider_a_timeout")
        except ProviderAConnectionError:
            return ProviderOutcome(ProviderOutcomeKind.TRANSPORT_ERROR, detail="provider_a_connection_error")
        except ProviderARefused:
            return ProviderOutcome(ProviderOutcomeKind.REFUSAL, detail="provider_a_refused")
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
# Provider B adapter — wire uses `maxOutputTokens` / finish state `MAX_TOKENS`; B-specific SDK errors.
# ---------------------------------------------------------------------------
class ProviderBAdapter:
    def __init__(self, transport: RecordingTransport, profile: CapabilityProfile) -> None:
        self._transport = transport
        self._profile = profile

    @property
    def capability_profile(self) -> CapabilityProfile:
        return self._profile

    def build_wire_request(self, request: ApplicationRequest) -> Dict[str, object]:
        return {
            "modelId": self._profile.model,
            "maxOutputTokens": request.max_output_tokens,  # Provider B field name (different from A)
            "content": request.prompt,
            "correlationId": request.correlation_id,
        }

    def execute(self, request: ApplicationRequest) -> ProviderOutcome:
        try:
            wire_response = self._transport.send(self.build_wire_request(request))
        except ProviderBThrottled as e:
            ev = {"retry_after": e.retry_after} if e.retry_after else {}
            return ProviderOutcome(ProviderOutcomeKind.RATE_LIMITED, detail="provider_b_throttled",
                                   safe_evidence=ev)
        except ProviderBUnauthorized:
            return ProviderOutcome(ProviderOutcomeKind.AUTHENTICATION_ERROR, detail="provider_b_unauthorized")
        except ProviderBDeadlineExceeded as e:
            return ProviderOutcome(ProviderOutcomeKind.TIMEOUT_UNKNOWN, provider_request_id=e.request_id,
                                   detail="provider_b_deadline_exceeded")
        except ProviderBNetworkError:
            return ProviderOutcome(ProviderOutcomeKind.TRANSPORT_ERROR, detail="provider_b_network_error")
        except ProviderBDeclined:
            return ProviderOutcome(ProviderOutcomeKind.REFUSAL, detail="provider_b_declined")
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
# Dispatch: authoritative binding -> request/profile binding -> lifecycle admission -> guarded ONE call.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DispatchResult:
    outcome: ProviderOutcome
    provider_calls: int                 # THIS dispatch only: 0 or 1 (never the transport's cumulative total)
    attempt_state: AttemptState         # the Attempt state AFTER this dispatch


def dispatch_attempt(*, request: ApplicationRequest, contract: AttemptExecutionContract,
                     adapter: ProviderAdapter, state_store: AttemptStateStore,
                     lifecycle: ProfileLifecycle) -> DispatchResult:
    """Dispatch one Attempt through the injected Adapter (which owns its transport). Gates, in order — each
    failing with ZERO Provider calls:

    1. Read the AUTHORITATIVE record from the store; reject if unknown, if the caller's ``contract`` differs
       from the stored authoritative contract (``AttemptBindingError``), or if the state is not PLANNED.
    2. ``validate_attempt_binding`` — request.job_id / request.application_contract / the six profile version
       fields must match the authoritative contract and the Adapter's profile exactly (``AttemptBindingError``).
    3. Capability admission against the CURRENT lifecycle status: a disabled/quarantined profile is a guarded
       PLANNED -> BLOCKED_PROFILE_DISABLED transition (binding preserved); an unsupported contract returns a
       CAPABILITY_ERROR outcome.
    4. A thread-safe compare-and-set PLANNED -> DISPATCHED (bound to identity + full binding + expected state)
       guards the SINGLE external call; a lost race means zero calls (``AttemptStateError``).
    """

    record: Optional[AttemptRecord] = state_store.get_record(contract.attempt_id)
    if record is None:
        raise AttemptStateError(f"unknown attempt (not planned): {contract.attempt_id}")
    authoritative = record.contract
    # (1) Reject a forged/mismatched caller contract; use the STORE's authoritative binding thereafter.
    if contract != authoritative:
        raise AttemptBindingError(
            f"caller contract does not match the persisted Attempt binding for {contract.attempt_id}")
    if record.state is not AttemptState.PLANNED:
        raise AttemptStateError(
            f"attempt {contract.attempt_id} is {record.state.value}, only PLANNED may dispatch")

    # (2) request/profile binding validation against the authoritative contract.
    validate_attempt_binding(request, authoritative, adapter.capability_profile)

    # (3) Admission against the CURRENT lifecycle status of the bound profile.
    current_status: ProfileStatus = lifecycle.status(authoritative.profile_id)
    admission: AdmissionResult = admit_capability(
        adapter.capability_profile, authoritative.application_contract, current_status)
    if not admission.admitted:
        assert admission.outcome is not None
        if admission.outcome.detail == "profile_not_selectable":
            if not state_store.compare_and_set(authoritative, AttemptState.PLANNED,
                                                AttemptState.BLOCKED_PROFILE_DISABLED):
                raise AttemptStateError(f"could not block attempt {contract.attempt_id}")
            return DispatchResult(admission.outcome, provider_calls=0,
                                  attempt_state=AttemptState.BLOCKED_PROFILE_DISABLED)
        return DispatchResult(admission.outcome, provider_calls=0, attempt_state=AttemptState.PLANNED)

    # (4) Guarded single-call transition (atomic compare-and-set). A lost race -> zero calls.
    if not state_store.compare_and_set(authoritative, AttemptState.PLANNED, AttemptState.DISPATCHED):
        raise AttemptStateError(
            f"attempt {contract.attempt_id} could not transition PLANNED -> DISPATCHED")

    outcome = adapter.execute(request)   # the ONE authorized external send attempt for this Attempt
    return DispatchResult(outcome, provider_calls=1, attempt_state=AttemptState.DISPATCHED)
