"""Day72 — concrete Provider Adapters over a controlled, in-process transport (standard library only).

Two fictional Providers (A and B) with DIFFERENT wire field names, DIFFERENT finish states, and DIFFERENT
Provider-specific SDK failure TYPES, each mapping equivalent facts to the SAME stable application surface.
Each Adapter owns its OWN transport (injected at construction) and exposes ``execute()`` — callers never pass
a transport and never see an SDK exception. Failure classification uses explicit structured exception TYPES,
never message-string matching, and each Adapter has a LAST-LINE-OF-DEFENSE catch of its Provider SDK base
exception so an unknown (not-yet-enumerated) SDK error is mapped conservatively by its structured execution
certainty (``DEFINITELY_NOT_SENT`` -> ``TRANSPORT_ERROR``; anything else / missing -> ``TIMEOUT_UNKNOWN``).
Non-SDK programming errors are NOT swallowed — they propagate so real defects surface.

Provider-controlled evidence (``retry_after``, request ids) is passed through a strict application-level
allowlist normalizer before it may enter ``safe_evidence``; an invalid value is dropped, never placed in
``detail``.

There is NO network and NO real Provider. All wire shapes and SDK error types here are classroom fixtures,
not real API claims.

``dispatch_attempt`` takes the AUTHORITATIVE ``ProviderRegistry`` (not a caller-supplied Adapter or
lifecycle): it reads the authoritative ``AttemptExecutionContract`` from the state store, rejects a
caller-supplied contract that differs from it (``AttemptBindingError``), resolves the bound Adapter through
that Registry, admits against the Registry's OWN lifecycle catalog, then makes AT MOST ONE external call
guarded by a thread-safe compare-and-set. The trusted composition root injects a Registry backed by the
shared lifecycle authority; the dispatch caller cannot pass a standalone Adapter or lifecycle override.
``provider_calls`` counts THIS dispatch (0 before a send attempt, 1 once a send attempt begins).
"""

from __future__ import annotations

import string
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional, Protocol

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
    ProfileStatus,
    ProviderOutcome,
    ProviderOutcomeKind,
    ProviderRegistry,
    UnknownProfileError,
    admit_capability,
    validate_attempt_binding,
)


# ---------------------------------------------------------------------------
# Structured execution certainty for UNKNOWN SDK failures (never message strings).
# ---------------------------------------------------------------------------
class ExecutionCertainty(Enum):
    DEFINITELY_NOT_SENT = "DEFINITELY_NOT_SENT"   # the request provably never left -> TRANSPORT_ERROR
    EXECUTION_UNKNOWN = "EXECUTION_UNKNOWN"       # no reliable non-execution evidence -> TIMEOUT_UNKNOWN


# ---------------------------------------------------------------------------
# Application-level safe normalizers for Provider-controlled evidence (strict allowlist parsing).
# ---------------------------------------------------------------------------
_RETRY_AFTER_MAX_SECONDS = 86400
_RETRY_AFTER_MAX_LEN = 8


def normalize_retry_after(value: object) -> Optional[str]:
    """Return a canonical non-negative integer-seconds string in [0, 86400], or ``None`` if the
    Provider-controlled value is not a plain decimal integer within bounds. STRICT allowlist: ASCII decimal
    digits only (no whitespace, sign, dot, newline, control chars, or arbitrary text); leading zeros are
    normalized away. There is NO trimming — a value with surrounding whitespace is rejected."""

    if not isinstance(value, str):
        return None
    if not (1 <= len(value) <= _RETRY_AFTER_MAX_LEN):
        return None
    if not value.isascii() or not value.isdigit():   # isdigit() rejects sign, space, '.', control, empty
        return None
    n = int(value)
    if n > _RETRY_AFTER_MAX_SECONDS:                 # n >= 0 guaranteed by isdigit()
        return None
    return str(n)                                    # canonical decimal (drops leading zeros)


_REQUEST_ID_MAX_LEN = 128
_REQUEST_ID_ALLOWED = frozenset(string.ascii_letters + string.digits + "-_.")


def normalize_request_id(value: object) -> Optional[str]:
    """Return the Provider-minted request id only if it is a short, ASCII, allowlisted-character string
    (letters/digits/``-`` ``_`` ``.``, length 1..128); otherwise ``None``. This bounds a Provider-controlled
    identifier before it may become application evidence."""

    if not isinstance(value, str):
        return None
    if not (1 <= len(value) <= _REQUEST_ID_MAX_LEN):
        return None
    if not value.isascii():
        return None
    if any(c not in _REQUEST_ID_ALLOWED for c in value):
        return None
    return value


# ---------------------------------------------------------------------------
# Fictional Provider-specific SDK failure TYPES (stay inside each Adapter boundary).
# Structured types — classification never inspects a message string. The base classes carry a class-default
# ``execution_certainty`` so an UNKNOWN subclass is still mapped conservatively.
# ---------------------------------------------------------------------------
class ProviderASDKError(Exception):
    """Base of Provider A's fictional SDK exceptions. Default certainty is conservative (EXECUTION_UNKNOWN)."""

    execution_certainty: Optional[ExecutionCertainty] = ExecutionCertainty.EXECUTION_UNKNOWN


class ProviderARefused(ProviderASDKError):
    pass


class ProviderARateLimited(ProviderASDKError):
    def __init__(self, retry_after: Optional[str] = None) -> None:
        super().__init__("rate_limited")
        self.retry_after = retry_after


class ProviderAAuthFailed(ProviderASDKError):
    pass


class ProviderATimedOut(ProviderASDKError):
    execution_certainty = ExecutionCertainty.EXECUTION_UNKNOWN

    def __init__(self, request_id: Optional[str] = None) -> None:
        super().__init__("timed_out")
        self.request_id = request_id


class ProviderAConnectionError(ProviderASDKError):
    execution_certainty = ExecutionCertainty.DEFINITELY_NOT_SENT


class ProviderBSDKError(Exception):
    """Base of Provider B's fictional SDK exceptions (a DIFFERENT type hierarchy)."""

    execution_certainty: Optional[ExecutionCertainty] = ExecutionCertainty.EXECUTION_UNKNOWN


class ProviderBDeclined(ProviderBSDKError):
    pass


class ProviderBThrottled(ProviderBSDKError):
    def __init__(self, retry_after: Optional[str] = None) -> None:
        super().__init__("throttled")
        self.retry_after = retry_after


class ProviderBUnauthorized(ProviderBSDKError):
    pass


class ProviderBDeadlineExceeded(ProviderBSDKError):
    execution_certainty = ExecutionCertainty.EXECUTION_UNKNOWN

    def __init__(self, request_id: Optional[str] = None) -> None:
        super().__init__("deadline_exceeded")
        self.request_id = request_id


class ProviderBNetworkError(ProviderBSDKError):
    execution_certainty = ExecutionCertainty.DEFINITELY_NOT_SENT


def _map_unknown_sdk_error(err: object, label: str) -> ProviderOutcome:
    """Conservative mapping for an UNKNOWN (not individually enumerated) Provider SDK error, using its
    structured ``execution_certainty`` — NEVER its message. Missing certainty is treated as EXECUTION_UNKNOWN
    and mapped to TIMEOUT_UNKNOWN (never optimistically to a retryable TRANSPORT_ERROR). No SDK object or
    message enters the outcome."""

    certainty = getattr(err, "execution_certainty", ExecutionCertainty.EXECUTION_UNKNOWN)
    if certainty is ExecutionCertainty.DEFINITELY_NOT_SENT:
        return ProviderOutcome(ProviderOutcomeKind.TRANSPORT_ERROR, detail=f"{label}_unknown_sdk_not_sent")
    return ProviderOutcome(ProviderOutcomeKind.TIMEOUT_UNKNOWN, detail=f"{label}_unknown_sdk_execution_unknown")


# ---------------------------------------------------------------------------
# Controlled in-process transport (records calls; returns a wire response OR raises a scripted SDK error).
# ---------------------------------------------------------------------------
class ProviderTransport(Protocol):
    """Minimal injected transport seam implemented by recording and Fake transports."""

    def send(self, wire_request: Mapping[str, object]) -> Mapping[str, object]:
        """Send one Provider-specific request or raise a Provider SDK error."""


@dataclass
class RecordingTransport:
    """Records every wire request it is asked to send, then either returns a scripted wire response or raises
    a scripted Provider-specific SDK exception. Stands in for a Provider SDK/HTTP client and stays ENTIRELY
    behind the Adapter boundary. The call is recorded BEFORE raising, so a send attempt counts as one call."""

    scripted_response: Optional[Mapping[str, object]] = None
    scripted_error: Optional[BaseException] = None
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
    def __init__(self, transport: ProviderTransport, profile: CapabilityProfile) -> None:
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
        Never raises an SDK exception; never retries; never creates another Attempt or switches Provider. A
        non-SDK programming error is NOT swallowed."""
        try:
            wire_response = self._transport.send(self.build_wire_request(request))
        except ProviderARateLimited as e:
            ra = normalize_retry_after(e.retry_after)
            ev = {"retry_after": ra} if ra is not None else {}
            return ProviderOutcome(ProviderOutcomeKind.RATE_LIMITED, detail="provider_a_rate_limited",
                                   safe_evidence=ev)
        except ProviderAAuthFailed:
            return ProviderOutcome(ProviderOutcomeKind.AUTHENTICATION_ERROR, detail="provider_a_auth_failed")
        except ProviderATimedOut as e:
            # UNKNOWN execution/cost -> reconcile; NOT a retryable transport error.
            return ProviderOutcome(ProviderOutcomeKind.TIMEOUT_UNKNOWN,
                                   provider_request_id=normalize_request_id(e.request_id),
                                   detail="provider_a_timeout")
        except ProviderAConnectionError:
            return ProviderOutcome(ProviderOutcomeKind.TRANSPORT_ERROR, detail="provider_a_connection_error")
        except ProviderARefused:
            return ProviderOutcome(ProviderOutcomeKind.REFUSAL, detail="provider_a_refused")
        except ProviderASDKError as e:
            # LAST LINE OF DEFENSE: an unknown/new Provider A SDK error must not escape the Adapter.
            return _map_unknown_sdk_error(e, "provider_a")
        return self.translate_outcome(wire_response)

    def translate_outcome(self, wire_response: Mapping[str, object]) -> ProviderOutcome:
        req_id = normalize_request_id(wire_response.get("id"))     # Provider A request-identity field
        if self._profile.requires_request_identity and not req_id:
            return ProviderOutcome(ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID,
                                   detail="missing_provider_request_id")
        finish = wire_response.get("finish_reason")
        if finish == "length":                             # Provider A output-limit state
            return ProviderOutcome(ProviderOutcomeKind.TRUNCATION, provider_request_id=req_id,
                                   detail="finish_reason=length")
        if finish == "stop":
            return ProviderOutcome(ProviderOutcomeKind.SUCCESS, provider_request_id=req_id,
                                   detail="finish_reason=stop")
        return ProviderOutcome(ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID, provider_request_id=req_id,
                               detail="unknown_finish_reason")


# ---------------------------------------------------------------------------
# Provider B adapter — wire uses `maxOutputTokens` / finish state `MAX_TOKENS`; B-specific SDK errors.
# ---------------------------------------------------------------------------
class ProviderBAdapter:
    def __init__(self, transport: ProviderTransport, profile: CapabilityProfile) -> None:
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
            ra = normalize_retry_after(e.retry_after)
            ev = {"retry_after": ra} if ra is not None else {}
            return ProviderOutcome(ProviderOutcomeKind.RATE_LIMITED, detail="provider_b_throttled",
                                   safe_evidence=ev)
        except ProviderBUnauthorized:
            return ProviderOutcome(ProviderOutcomeKind.AUTHENTICATION_ERROR, detail="provider_b_unauthorized")
        except ProviderBDeadlineExceeded as e:
            return ProviderOutcome(ProviderOutcomeKind.TIMEOUT_UNKNOWN,
                                   provider_request_id=normalize_request_id(e.request_id),
                                   detail="provider_b_deadline_exceeded")
        except ProviderBNetworkError:
            return ProviderOutcome(ProviderOutcomeKind.TRANSPORT_ERROR, detail="provider_b_network_error")
        except ProviderBDeclined:
            return ProviderOutcome(ProviderOutcomeKind.REFUSAL, detail="provider_b_declined")
        except ProviderBSDKError as e:
            return _map_unknown_sdk_error(e, "provider_b")
        return self.translate_outcome(wire_response)

    def translate_outcome(self, wire_response: Mapping[str, object]) -> ProviderOutcome:
        req_id = normalize_request_id(wire_response.get("responseId"))  # Provider B request-identity field
        if self._profile.requires_request_identity and not req_id:
            return ProviderOutcome(ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID,
                                   detail="missing_provider_request_id")
        state = wire_response.get("completionState")
        if state == "MAX_TOKENS":                          # Provider B output-limit state (different label)
            return ProviderOutcome(ProviderOutcomeKind.TRUNCATION, provider_request_id=req_id,
                                   detail="completionState=MAX_TOKENS")
        if state == "COMPLETE":
            return ProviderOutcome(ProviderOutcomeKind.SUCCESS, provider_request_id=req_id,
                                   detail="completionState=COMPLETE")
        return ProviderOutcome(ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID, provider_request_id=req_id,
                               detail="unknown_completion_state")


# ---------------------------------------------------------------------------
# Dispatch: authoritative binding + Registry-owned Adapter/lifecycle -> guarded ONE call.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DispatchResult:
    outcome: ProviderOutcome
    provider_calls: int                 # THIS dispatch only: 0 or 1 (never the transport's cumulative total)
    attempt_state: AttemptState         # the Attempt state AFTER this dispatch


def dispatch_attempt(*, request: ApplicationRequest, contract: AttemptExecutionContract,
                     state_store: AttemptStateStore, registry: ProviderRegistry) -> DispatchResult:
    """Dispatch one Attempt using the AUTHORITATIVE ``registry`` (which owns both the concrete Adapters and
    the lifecycle catalog). The trusted composition root supplies the Registry; a dispatch caller can NOT
    pass a standalone Adapter or lifecycle override. Gates, in
    order — each failing with ZERO Provider calls:

    1. Read the AUTHORITATIVE record from the store; reject if unknown, if the caller's ``contract`` differs
       from the stored authoritative contract (``AttemptBindingError``), or if the state is not PLANNED.
    2. Resolve the bound Adapter through the Registry by the Attempt's exact profile/versions
       (``resolve_bound_attempt``), then ``validate_attempt_binding`` for request.job_id /
       request.application_contract / the six version fields (``AttemptBindingError``).
    3. Read the CURRENT status from the Registry's OWN lifecycle catalog. An UNKNOWN profile fails closed
       (``UnknownProfileError``). A disabled/quarantined profile is a guarded PLANNED ->
       BLOCKED_PROFILE_DISABLED transition (binding preserved); an unsupported contract returns a
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

    # (2) Resolve the bound Adapter through the AUTHORITATIVE Registry (exact-version), then validate.
    adapter = registry.resolve_bound_attempt(authoritative)
    validate_attempt_binding(request, authoritative, adapter.capability_profile)

    # (3) Admission against the Registry's OWN lifecycle catalog (not any caller-supplied lifecycle).
    current_status: ProfileStatus = registry.lifecycle.status(authoritative.profile_id)
    if current_status is ProfileStatus.UNKNOWN:
        # A bound profile must be known to the authority; fail closed rather than assume ACTIVE.
        raise UnknownProfileError(authoritative.profile_id)
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
