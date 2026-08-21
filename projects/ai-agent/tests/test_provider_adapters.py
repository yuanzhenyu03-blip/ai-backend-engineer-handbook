"""Day72 — EXECUTED_LOCAL_RUNTIME tests for the replaceable Provider Adapter slice (round-3 review).

Deterministic, in-process tests. Standard library only; no network, no SDK, no real Provider, no database.
Round-3 findings covered (on top of the preserved round-1/round-2 invariants):

  Finding 1 — the lifecycle authority is fail-closed and explicit at the trusted composition boundary.
              ``ProfileLifecycle.status``
              returns ``UNKNOWN`` (never ACTIVE) for a profile the authority never registered, and every
              caller fails closed on it. ``dispatch_attempt`` takes the AUTHORITATIVE ``ProviderRegistry`` —
              it has NO ``adapter`` and NO ``lifecycle`` parameter, so a dispatch caller cannot pass a
              standalone override; the Adapter is resolved and the status is read through the Registry's own
              catalog. Both ``ProviderRegistry`` and ``ProviderSelectionPolicy`` REQUIRE the shared lifecycle
              authority; neither can silently fabricate a fresh ACTIVE catalog and bypass a disable.
  Finding 2 — an UNKNOWN (not individually enumerated) Provider SDK error cannot leak. A last-line base-class
              catch maps it by STRUCTURED execution certainty — ``DEFINITELY_NOT_SENT`` -> TRANSPORT_ERROR,
              anything else / missing -> TIMEOUT_UNKNOWN (conservative) — never by a message string, and no
              SDK object or message enters the outcome. A non-SDK programming error is NOT swallowed.
  Finding 3 — Provider-controlled retry/identity evidence is sanitized by a strict application-level allowlist
              (``normalize_retry_after`` / ``normalize_request_id``) before it may enter ``safe_evidence``; an
              invalid value is dropped and never placed in ``detail``.

They do NOT prove a real SDK/API, real HTTP, Provider behaviour, cost, rate limits, credentials,
INTEGRATION_RUNTIME or PRODUCTION. The in-memory store models compare-and-set for IN-PROCESS threads only; a
production deployment needs a durable DB conditional UPDATE / transaction.

Run from ``projects/ai-agent/``:  python3 -m unittest discover -s tests -v
"""

import inspect
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from provider_contract import (  # noqa: E402
    ApplicationRequest,
    AttemptBindingError,
    AttemptExecutionContract,
    AttemptState,
    AttemptStateError,
    CapabilityProfile,
    DuplicateProfileRegistrationError,
    InMemoryAttemptStateStore,
    ProductOption,
    ProfileDisabledError,
    ProfileLifecycle,
    ProfileStatus,
    ProviderIncompatibleError,
    ProviderOutcomeKind,
    ProviderRegistry,
    ProviderSelectionPolicy,
    UnknownProfileError,
    VerificationTier,
)
from provider_adapters import (  # noqa: E402
    ExecutionCertainty,
    ProviderAAdapter,
    ProviderAAuthFailed,
    ProviderAConnectionError,
    ProviderARateLimited,
    ProviderARefused,
    ProviderASDKError,
    ProviderATimedOut,
    ProviderBAdapter,
    ProviderBDeadlineExceeded,
    ProviderBDeclined,
    ProviderBNetworkError,
    ProviderBSDKError,
    ProviderBThrottled,
    ProviderBUnauthorized,
    RecordingTransport,
    dispatch_attempt,
    normalize_request_id,
    normalize_retry_after,
)

CONTRACT = "research_claims.v1"


def _profile(profile_id="prof-A-v3", provider="provider_a", model="a-large", pv="v3", av="1.0.0",
             supported=(CONTRACT,), requires_id=True, status=ProfileStatus.ACTIVE):
    return CapabilityProfile(
        profile_id=profile_id, provider_name=provider, model=model, api_version="2026-08-01",
        profile_version=pv, adapter_version=av, supported_contracts=frozenset(supported),
        requires_request_identity=requires_id, verification_tier=VerificationTier.EXECUTED_LOCAL_RUNTIME,
        status=status)


def _request(job_id="job-1", contract=CONTRACT):
    return ApplicationRequest(job_id=job_id, tenant_id="tenantA", application_contract=contract,
                              task_type="research_report", max_output_tokens=512, correlation_id="corr-1",
                              prompt="SECRET-PROMPT-do-not-leak")


def _a_ok():
    return RecordingTransport(scripted_response={"id": "ra", "finish_reason": "stop"})


def _b_ok():
    return RecordingTransport(scripted_response={"responseId": "rb", "completionState": "COMPLETE"})


def _registered(profile, transport=None, attempt_id="A1", job_id="job-1"):
    """Register the Adapter into an AUTHORITATIVE Registry, plan the Attempt in a store, and return
    (contract, store, registry, transport, adapter). Dispatch takes ONLY (request, contract, state_store,
    registry) — the Adapter + lifecycle authority live inside the Registry, not in the caller's hands."""
    transport = transport if transport is not None else _a_ok()
    is_a = profile.provider_name == "provider_a"
    adapter = (ProviderAAdapter if is_a else ProviderBAdapter)(transport, profile)
    registry = ProviderRegistry(ProfileLifecycle())
    registry.register(adapter)
    contract = AttemptExecutionContract.plan(attempt_id, job_id, profile, CONTRACT)
    store = InMemoryAttemptStateStore()
    store.plan(contract)
    return contract, store, registry, transport, adapter


# ===========================================================================
# Finding 1 — fail-closed shared lifecycle + Registry-owned dispatch at the trusted composition boundary.
# ===========================================================================
class Finding1AuthorityNotReplaceable(unittest.TestCase):
    def test_dispatch_signature_has_no_adapter_or_lifecycle_param(self):
        params = set(inspect.signature(dispatch_attempt).parameters)
        self.assertEqual(params, {"request", "contract", "state_store", "registry"})
        for forbidden in ("adapter", "lifecycle", "transport"):
            self.assertNotIn(forbidden, params,
                             f"caller must NOT be able to substitute {forbidden}")

    def test_unknown_profile_lifecycle_lookup_is_unknown_not_active(self):
        lc = ProfileLifecycle()
        self.assertIs(lc.status("never-registered"), ProfileStatus.UNKNOWN)
        self.assertFalse(lc.is_active("never-registered"))

    def test_registry_requires_shared_lifecycle_authority(self):
        with self.assertRaises(TypeError):
            ProviderRegistry(lifecycle=None)

    def test_replacement_registry_shares_disable_and_cannot_reactivate_profile(self):
        profile = _profile(pv="v3")
        lifecycle = ProfileLifecycle()
        original = ProviderRegistry(lifecycle)
        original.register(ProviderAAdapter(_a_ok(), profile))
        original.disable(profile.profile_id)

        replacement_transport = _a_ok()
        replacement = ProviderRegistry(lifecycle)
        replacement.register(ProviderAAdapter(replacement_transport, profile))
        contract = AttemptExecutionContract.plan("A1", "job-1", profile, CONTRACT)
        store = InMemoryAttemptStateStore()
        store.plan(contract)

        result = dispatch_attempt(
            request=_request(), contract=contract, state_store=store, registry=replacement)
        self.assertIs(result.outcome.kind, ProviderOutcomeKind.CAPABILITY_ERROR)
        self.assertIs(result.attempt_state, AttemptState.BLOCKED_PROFILE_DISABLED)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(len(replacement_transport.calls), 0)
        self.assertIs(lifecycle.status(profile.profile_id), ProfileStatus.DISABLED)

    def test_unregistered_profile_cannot_be_selected(self):
        registry = ProviderRegistry(ProfileLifecycle())
        with self.assertRaises(UnknownProfileError):
            registry.get_selectable("ghost", CONTRACT)

    def test_selection_policy_requires_lifecycle(self):
        with self.assertRaises(TypeError):
            ProviderSelectionPolicy({"standard": _profile()}, lifecycle=None)

    def test_selection_policy_cannot_bypass_disable_by_omitting_lifecycle(self):
        good = _profile()
        lc = ProfileLifecycle(); lc.register(good); lc.disable(good.profile_id)
        # The only constructor form carries the authoritative lifecycle; a disable is honoured.
        with self.assertRaises(ProfileDisabledError):
            ProviderSelectionPolicy({"standard": good}, lc).select(ProductOption("standard"), CONTRACT)

    def test_selection_policy_unknown_profile_fails_closed(self):
        good = _profile()
        lc = ProfileLifecycle()   # good is NOT registered here -> UNKNOWN
        with self.assertRaises(UnknownProfileError):
            ProviderSelectionPolicy({"standard": good}, lc).select(ProductOption("standard"), CONTRACT)

    def test_selection_policy_quarantined_and_disabled_both_fail_closed(self):
        good = _profile()
        for mutate in (ProfileLifecycle.disable, ProfileLifecycle.quarantine):
            lc = ProfileLifecycle(); lc.register(good); mutate(lc, good.profile_id)
            with self.assertRaises(ProfileDisabledError):
                ProviderSelectionPolicy({"standard": good}, lc).select(ProductOption("standard"), CONTRACT)

    def test_selection_policy_active_compatible_selects(self):
        good = _profile()
        lc = ProfileLifecycle(); lc.register(good)
        self.assertIs(ProviderSelectionPolicy({"standard": good}, lc).select(
            ProductOption("standard"), CONTRACT), good)

    def test_active_compatible_profile_still_calls_once(self):
        contract, store, registry, transport, _ = _registered(_profile())
        r = dispatch_attempt(request=_request(), contract=contract, state_store=store, registry=registry)
        self.assertEqual(r.provider_calls, 1)
        self.assertEqual(len(transport.calls), 1)
        self.assertIs(r.attempt_state, AttemptState.DISPATCHED)
        self.assertIs(r.outcome.kind, ProviderOutcomeKind.SUCCESS)

    def test_register_disable_dispatch_blocks_with_zero_calls(self):
        v3 = _profile(pv="v3")
        contract, store, registry, transport, _ = _registered(v3)
        registry.disable(v3.profile_id)                          # disable via the Registry's own lifecycle
        # New-task selection now fails closed.
        with self.assertRaises(ProfileDisabledError):
            registry.get_selectable(v3.profile_id, CONTRACT)
        # Bound-attempt resolution still returns the exact bound Adapter (for the zero-call block / audit).
        self.assertEqual(registry.resolve_bound_attempt(contract).capability_profile.profile_version, "v3")
        result = dispatch_attempt(request=_request(), contract=contract, state_store=store, registry=registry)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(len(transport.calls), 0)
        self.assertIs(result.attempt_state, AttemptState.BLOCKED_PROFILE_DISABLED)
        self.assertIs(store.get_record("A1").state, AttemptState.BLOCKED_PROFILE_DISABLED)
        self.assertEqual(store.get_record("A1").contract.profile_version, "v3")   # A1 still v3
        self.assertIsNone(store.get_record("A2"))                # no A2 auto-created

    def test_quarantined_profile_dispatch_blocks_with_zero_calls(self):
        contract, store, registry, transport, _ = _registered(_profile())
        registry.quarantine(_profile().profile_id)
        result = dispatch_attempt(request=_request(), contract=contract, state_store=store, registry=registry)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(len(transport.calls), 0)
        self.assertIs(result.attempt_state, AttemptState.BLOCKED_PROFILE_DISABLED)

    def test_dispatch_unknown_lifecycle_status_fails_closed_zero_calls(self):
        # If the Registry's lifecycle catalog no longer knows the bound profile, dispatch must fail closed
        # (UnknownProfileError) rather than assume ACTIVE — with zero external calls.
        contract, store, registry, transport, _ = _registered(_profile())
        registry.lifecycle.set_status(_profile().profile_id, ProfileStatus.UNKNOWN)
        with self.assertRaises(UnknownProfileError):
            dispatch_attempt(request=_request(), contract=contract, state_store=store, registry=registry)
        self.assertEqual(len(transport.calls), 0)
        self.assertIs(store.get_record("A1").state, AttemptState.PLANNED)

    def test_forged_caller_contract_rejected_zero_calls(self):
        # Store's authoritative binding is Provider A / v3. A caller forges a self-consistent Provider B
        # contract reusing attempt_id A1; because dispatch reads the AUTHORITATIVE contract from the store and
        # compares, the forged contract is rejected before any resolution or call.
        a_profile = _profile()
        contract, store, registry, _, _ = _registered(a_profile)
        b_profile = _profile(profile_id="prof-B-v1", provider="provider_b", model="b-pro", pv="v1")
        forged = AttemptExecutionContract.plan("A1", "job-1", b_profile, CONTRACT)
        with self.assertRaises(AttemptBindingError):
            dispatch_attempt(request=_request(), contract=forged, state_store=store, registry=registry)
        rec = store.get_record("A1")
        self.assertEqual(rec.contract, contract)                 # authoritative binding unchanged
        self.assertIs(rec.state, AttemptState.PLANNED)

    def test_forged_registry_cannot_replace_authoritative_binding_zero_calls(self):
        # Store holds the authoritative v3 contract, but a substituted Registry only knows a DRIFTED v4 Adapter
        # under the same profile_id. resolve_bound_attempt must reject the mismatch -> zero calls.
        v3 = _profile(pv="v3")
        contract = AttemptExecutionContract.plan("A1", "job-1", v3, CONTRACT)
        store = InMemoryAttemptStateStore(); store.plan(contract)
        v4 = _profile(pv="v4")
        drift_transport = _a_ok()
        drifted_registry = ProviderRegistry(ProfileLifecycle())
        drifted_registry.register(ProviderAAdapter(drift_transport, v4))
        with self.assertRaises(AttemptBindingError):
            dispatch_attempt(request=_request(), contract=contract, state_store=store,
                             registry=drifted_registry)
        self.assertEqual(len(drift_transport.calls), 0)
        self.assertIs(store.get_record("A1").state, AttemptState.PLANNED)

    def test_unknown_attempt_zero_calls(self):
        profile = _profile()
        contract = AttemptExecutionContract.plan("A1", "job-1", profile, CONTRACT)
        store = InMemoryAttemptStateStore()   # never planned
        transport = _a_ok()
        registry = ProviderRegistry(ProfileLifecycle()); registry.register(ProviderAAdapter(transport, profile))
        with self.assertRaises(AttemptStateError):
            dispatch_attempt(request=_request(), contract=contract, state_store=store, registry=registry)
        self.assertEqual(len(transport.calls), 0)

    def test_request_profile_binding_mismatch_zero_calls(self):
        # A request whose job_id disagrees with the authoritative contract is an invariant violation.
        contract, store, registry, transport, _ = _registered(_profile(pv="v3"))
        with self.assertRaises(AttemptBindingError):
            dispatch_attempt(request=_request(job_id="job-OTHER"), contract=contract, state_store=store,
                             registry=registry)
        self.assertEqual(len(transport.calls), 0)


# ===========================================================================
# Finding 1 (cont.) — thread-safe compare-and-set + real concurrency (one call).
# ===========================================================================
class Finding1ConcurrencyOneCall(unittest.TestCase):
    def test_two_concurrent_dispatches_make_exactly_one_call(self):
        for _ in range(40):   # repeat for stability; deterministic assertions, no sleeps
            contract, store, registry, transport, _ = _registered(_profile())
            barrier = threading.Barrier(2)
            results, errors = [], []

            def worker():
                barrier.wait()   # align both threads at the same start point
                try:
                    results.append(dispatch_attempt(request=_request(), contract=contract,
                                                    state_store=store, registry=registry))
                except AttemptStateError as e:
                    errors.append(e)

            t1, t2 = threading.Thread(target=worker), threading.Thread(target=worker)
            t1.start(); t2.start(); t1.join(); t2.join()

            self.assertEqual(len(results), 1, "exactly one dispatch must win execution")
            self.assertEqual(len(errors), 1, "the loser must get an explicit AttemptStateError")
            self.assertEqual(results[0].provider_calls, 1)
            self.assertEqual(len(transport.calls), 1, "the transport must be called exactly once")
            self.assertIs(store.get_record("A1").state, AttemptState.DISPATCHED)

    def test_first_dispatch_one_call_second_rejected_zero_new(self):
        contract, store, registry, transport, _ = _registered(_profile())
        r = dispatch_attempt(request=_request(), contract=contract, state_store=store, registry=registry)
        self.assertEqual(r.provider_calls, 1)
        self.assertIs(r.attempt_state, AttemptState.DISPATCHED)
        with self.assertRaises(AttemptStateError):
            dispatch_attempt(request=_request(), contract=contract, state_store=store, registry=registry)
        self.assertEqual(len(transport.calls), 1)


# ===========================================================================
# Finding 1 (cont.) — Registry composition surfaces (selection vs bound resolution).
# ===========================================================================
class Finding1RegistryComposition(unittest.TestCase):
    def test_get_selectable_active_supported_returns_adapter(self):
        v3 = _profile()
        registry = ProviderRegistry(ProfileLifecycle()); registry.register(ProviderAAdapter(_a_ok(), v3))
        self.assertIs(registry.get_selectable(v3.profile_id, CONTRACT).capability_profile, v3)

    def test_get_selectable_incompatible_contract_rejected(self):
        p = _profile(supported=())
        registry = ProviderRegistry(ProfileLifecycle()); registry.register(ProviderAAdapter(_a_ok(), p))
        with self.assertRaises(ProviderIncompatibleError):
            registry.get_selectable(p.profile_id, CONTRACT)

    def test_get_selectable_quarantined_rejected(self):
        p = _profile()
        registry = ProviderRegistry(ProfileLifecycle()); registry.register(ProviderAAdapter(_a_ok(), p))
        registry.quarantine(p.profile_id)
        with self.assertRaises(ProfileDisabledError):
            registry.get_selectable(p.profile_id, CONTRACT)

    def test_resolve_bound_attempt_binding_mismatch_rejected(self):
        registry = ProviderRegistry(ProfileLifecycle()); registry.register(ProviderAAdapter(_a_ok(), _profile(pv="v3")))
        drifted_contract = AttemptExecutionContract.plan("A1", "job-1", _profile(pv="v4"), CONTRACT)
        with self.assertRaises(AttemptBindingError):
            registry.resolve_bound_attempt(drifted_contract)

    def test_resolve_bound_attempt_unknown_profile_rejected(self):
        registry = ProviderRegistry(ProfileLifecycle())
        contract = AttemptExecutionContract.plan("A1", "job-1", _profile(), CONTRACT)
        with self.assertRaises(UnknownProfileError):
            registry.resolve_bound_attempt(contract)

    def test_duplicate_registration_rejected_idempotent_same_instance(self):
        p = _profile()
        registry = ProviderRegistry(ProfileLifecycle())
        registry.register(ProviderAAdapter(_a_ok(), p))
        with self.assertRaises(DuplicateProfileRegistrationError):
            registry.register(ProviderAAdapter(_a_ok(), p))     # different instance -> reject
        same = ProviderAAdapter(_a_ok(), _profile(profile_id="prof-X"))
        registry.register(same); registry.register(same)        # same instance -> idempotent


# ===========================================================================
# Finding 2 — unknown Provider SDK exceptions cannot leak (structured certainty, not message strings).
# ===========================================================================
class _ProviderAUnknownNotSent(ProviderASDKError):
    execution_certainty = ExecutionCertainty.DEFINITELY_NOT_SENT

    def __init__(self):
        super().__init__("brand-new-A-error SECRET-PROMPT-do-not-leak internal-stack-xyz")


class _ProviderAUnknownExecUnknown(ProviderASDKError):
    execution_certainty = ExecutionCertainty.EXECUTION_UNKNOWN

    def __init__(self):
        super().__init__("brand-new-A-error SECRET-PROMPT-do-not-leak internal-stack-xyz")


class _ProviderAUnknownNoCertainty(ProviderASDKError):
    # Force-remove the class default to simulate a missing execution_certainty attribute entirely.
    execution_certainty = None

    def __init__(self):
        super().__init__("mystery-A SECRET-PROMPT-do-not-leak")


class _ProviderBUnknownNotSent(ProviderBSDKError):
    execution_certainty = ExecutionCertainty.DEFINITELY_NOT_SENT

    def __init__(self):
        super().__init__("brand-new-B-error SECRET-PROMPT-do-not-leak")


class _ProviderBUnknownExecUnknown(ProviderBSDKError):
    execution_certainty = ExecutionCertainty.EXECUTION_UNKNOWN

    def __init__(self):
        super().__init__("brand-new-B-error SECRET-PROMPT-do-not-leak")


class Finding2UnknownSdkContainment(unittest.TestCase):
    def _a(self, error):
        return ProviderAAdapter(RecordingTransport(scripted_error=error), _profile())

    def _b(self, error):
        return ProviderBAdapter(RecordingTransport(scripted_error=error), _profile(provider="provider_b"))

    def test_unknown_not_sent_maps_to_transport_error(self):
        self.assertIs(self._a(_ProviderAUnknownNotSent()).execute(_request()).kind,
                      ProviderOutcomeKind.TRANSPORT_ERROR)
        self.assertIs(self._b(_ProviderBUnknownNotSent()).execute(_request()).kind,
                      ProviderOutcomeKind.TRANSPORT_ERROR)

    def test_unknown_execution_unknown_maps_to_timeout_unknown(self):
        self.assertIs(self._a(_ProviderAUnknownExecUnknown()).execute(_request()).kind,
                      ProviderOutcomeKind.TIMEOUT_UNKNOWN)
        self.assertIs(self._b(_ProviderBUnknownExecUnknown()).execute(_request()).kind,
                      ProviderOutcomeKind.TIMEOUT_UNKNOWN)

    def test_unknown_missing_certainty_is_conservative_timeout_unknown(self):
        self.assertIs(self._a(_ProviderAUnknownNoCertainty()).execute(_request()).kind,
                      ProviderOutcomeKind.TIMEOUT_UNKNOWN)

    def test_unknown_sdk_message_not_in_outcome(self):
        for adapter in (self._a(_ProviderAUnknownNotSent()), self._a(_ProviderAUnknownExecUnknown()),
                        self._b(_ProviderBUnknownExecUnknown())):
            outcome = adapter.execute(_request())
            blob = outcome.detail + "".join(
                f"{k}{v}" for k, v in dict(outcome.safe_evidence).items())
            self.assertNotIn("SECRET-PROMPT", blob)
            self.assertNotIn("internal-stack", blob)
            self.assertNotIn("brand-new", blob)

    def test_unknown_sdk_does_not_propagate_and_makes_one_attempt_only(self):
        adapter = self._a(_ProviderAUnknownExecUnknown())
        outcome = adapter.execute(_request())                   # must NOT raise
        self.assertIs(outcome.kind, ProviderOutcomeKind.TIMEOUT_UNKNOWN)
        self.assertEqual(len(adapter._transport.calls), 1)      # one send attempt; no second call

    def test_unknown_sdk_through_dispatch_stays_pending_no_second_call(self):
        contract, store, registry, transport, _ = _registered(
            _profile(), transport=RecordingTransport(scripted_error=_ProviderAUnknownExecUnknown()))
        r = dispatch_attempt(request=_request(), contract=contract, state_store=store, registry=registry)
        self.assertIs(r.outcome.kind, ProviderOutcomeKind.TIMEOUT_UNKNOWN)
        self.assertEqual(r.provider_calls, 1)
        self.assertIs(r.attempt_state, AttemptState.DISPATCHED)   # sent / pending reconcile, not retried
        with self.assertRaises(AttemptStateError):
            dispatch_attempt(request=_request(), contract=contract, state_store=store, registry=registry)
        self.assertEqual(len(transport.calls), 1)

    def test_non_sdk_programming_error_is_not_swallowed(self):
        # A defect (not a Provider SDK error) must propagate so it surfaces, not be mapped to an outcome.
        adapter = ProviderAAdapter(RecordingTransport(scripted_error=ValueError("bug")), _profile())
        with self.assertRaises(ValueError):
            adapter.execute(_request())


# ===========================================================================
# Finding 3 — sanitize Provider-controlled retry / identity evidence (strict allowlist).
# ===========================================================================
class Finding3RetryAfterNormalization(unittest.TestCase):
    def test_valid_plain_integers(self):
        self.assertEqual(normalize_retry_after("2"), "2")
        self.assertEqual(normalize_retry_after("0002"), "2")     # canonicalized, leading zeros dropped
        self.assertEqual(normalize_retry_after("0"), "0")
        self.assertEqual(normalize_retry_after("86400"), "86400")

    def test_invalid_values_dropped(self):
        for bad in ("-1", "2.5", " 2 ", "2 ", " 2", "86401", "999999999", "0x10", "2e3",
                    "٢", "２", "2\n", "\t2", "2\x00", "abc", "", "   ", "drop table", "12345678901234"):
            self.assertIsNone(normalize_retry_after(bad), f"{bad!r} must be rejected")

    def test_non_string_dropped(self):
        for bad in (2, 2.5, None, ["2"], {"retry_after": "2"}, True):
            self.assertIsNone(normalize_retry_after(bad))

    def test_adapter_valid_retry_after_enters_safe_evidence(self):
        outcome = ProviderAAdapter(RecordingTransport(scripted_error=ProviderARateLimited("2")),
                                   _profile()).execute(_request())
        self.assertIs(outcome.kind, ProviderOutcomeKind.RATE_LIMITED)
        self.assertEqual(dict(outcome.safe_evidence), {"retry_after": "2"})

    def test_adapter_canonicalizes_retry_after(self):
        outcome = ProviderBAdapter(RecordingTransport(scripted_error=ProviderBThrottled("0002")),
                                   _profile(provider="provider_b")).execute(_request())
        self.assertEqual(dict(outcome.safe_evidence), {"retry_after": "2"})

    def test_adapter_invalid_retry_after_dropped_not_in_detail_or_evidence(self):
        for adapter, raw in (
            (ProviderAAdapter(RecordingTransport(scripted_error=ProviderARateLimited("2.5 SECRET-PROMPT")),
                              _profile()), "2.5 SECRET-PROMPT"),
            (ProviderBAdapter(RecordingTransport(scripted_error=ProviderBThrottled("-1")),
                              _profile(provider="provider_b")), "-1"),
        ):
            outcome = adapter.execute(_request())
            self.assertIs(outcome.kind, ProviderOutcomeKind.RATE_LIMITED)
            self.assertNotIn("retry_after", dict(outcome.safe_evidence))   # invalid -> dropped entirely
            self.assertNotIn(raw, outcome.detail)                          # never the raw value in detail
            self.assertNotIn("SECRET-PROMPT", outcome.detail)

    def test_adapter_missing_retry_after_yields_empty_evidence(self):
        outcome = ProviderAAdapter(RecordingTransport(scripted_error=ProviderARateLimited(None)),
                                   _profile()).execute(_request())
        self.assertEqual(dict(outcome.safe_evidence), {})


class Finding3RequestIdNormalization(unittest.TestCase):
    def test_valid_request_ids(self):
        self.assertEqual(normalize_request_id("req-123_ABC.def"), "req-123_ABC.def")
        self.assertEqual(normalize_request_id("a"), "a")

    def test_invalid_request_ids_dropped(self):
        for bad in ("a b", "req/123", "req\n123", "req\x00", "req#1", "req 1",
                    "x" * 129, "", "reqé", "req\t1"):
            self.assertIsNone(normalize_request_id(bad), f"{bad!r} must be rejected")

    def test_non_string_request_id_dropped(self):
        for bad in (123, None, ["req"], object()):
            self.assertIsNone(normalize_request_id(bad))

    def test_valid_request_id_flows_through_translate(self):
        outcome = ProviderAAdapter(
            RecordingTransport(scripted_response={"id": "req-OK_1.2", "finish_reason": "stop"}),
            _profile()).execute(_request())
        self.assertIs(outcome.kind, ProviderOutcomeKind.SUCCESS)
        self.assertEqual(outcome.provider_request_id, "req-OK_1.2")

    def test_invalid_response_request_id_treated_as_missing(self):
        # requires_request_identity=True: an unsafe id normalizes to None -> PROVIDER_RESPONSE_INVALID.
        outcome = ProviderAAdapter(
            RecordingTransport(scripted_response={"id": "bad id\n", "finish_reason": "stop"}),
            _profile(requires_id=True)).execute(_request())
        self.assertIs(outcome.kind, ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID)
        self.assertEqual(outcome.detail, "missing_provider_request_id")

    def test_timeout_request_id_normalized(self):
        outcome = ProviderAAdapter(
            RecordingTransport(scripted_error=ProviderATimedOut("bad id\n")), _profile()).execute(_request())
        self.assertIs(outcome.kind, ProviderOutcomeKind.TIMEOUT_UNKNOWN)
        self.assertIsNone(outcome.provider_request_id)          # unsafe id dropped, not carried


# ===========================================================================
# Finding 4 (preserved) — Provider-specific failure translation (A/B parity).
# ===========================================================================
class Finding4FailureTranslation(unittest.TestCase):
    def _a(self, error=None, response=None):
        return ProviderAAdapter(RecordingTransport(scripted_response=response, scripted_error=error),
                                _profile())

    def _b(self, error=None, response=None):
        return ProviderBAdapter(RecordingTransport(scripted_response=response, scripted_error=error),
                                _profile(provider="provider_b"))

    def test_refusal(self):
        self.assertIs(self._a(error=ProviderARefused()).execute(_request()).kind, ProviderOutcomeKind.REFUSAL)
        self.assertIs(self._b(error=ProviderBDeclined()).execute(_request()).kind, ProviderOutcomeKind.REFUSAL)

    def test_rate_limited(self):
        self.assertIs(self._a(error=ProviderARateLimited("2")).execute(_request()).kind,
                      ProviderOutcomeKind.RATE_LIMITED)
        self.assertIs(self._b(error=ProviderBThrottled("2")).execute(_request()).kind,
                      ProviderOutcomeKind.RATE_LIMITED)

    def test_authentication_error(self):
        self.assertIs(self._a(error=ProviderAAuthFailed()).execute(_request()).kind,
                      ProviderOutcomeKind.AUTHENTICATION_ERROR)
        self.assertIs(self._b(error=ProviderBUnauthorized()).execute(_request()).kind,
                      ProviderOutcomeKind.AUTHENTICATION_ERROR)

    def test_timeout_unknown_and_no_second_call(self):
        for adapter in (self._a(error=ProviderATimedOut("ra")), self._b(error=ProviderBDeadlineExceeded("rb"))):
            outcome = adapter.execute(_request())
            self.assertIs(outcome.kind, ProviderOutcomeKind.TIMEOUT_UNKNOWN)
            self.assertEqual(len(adapter._transport.calls), 1)   # one send attempt; NOT a second call

    def test_transport_error(self):
        self.assertIs(self._a(error=ProviderAConnectionError()).execute(_request()).kind,
                      ProviderOutcomeKind.TRANSPORT_ERROR)
        self.assertIs(self._b(error=ProviderBNetworkError()).execute(_request()).kind,
                      ProviderOutcomeKind.TRANSPORT_ERROR)

    def test_provider_response_invalid(self):
        self.assertIs(self._a(response={"id": "ra", "finish_reason": "??"}).execute(_request()).kind,
                      ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID)
        self.assertIs(self._b(response={"responseId": "rb", "completionState": "??"}).execute(_request()).kind,
                      ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID)

    def test_truncation(self):
        self.assertIs(self._a(response={"id": "ra", "finish_reason": "length"}).execute(_request()).kind,
                      ProviderOutcomeKind.TRUNCATION)
        self.assertIs(self._b(response={"responseId": "rb", "completionState": "MAX_TOKENS"}).execute(_request()).kind,
                      ProviderOutcomeKind.TRUNCATION)

    def test_success(self):
        self.assertIs(self._a(response={"id": "ra", "finish_reason": "stop"}).execute(_request()).kind,
                      ProviderOutcomeKind.SUCCESS)
        self.assertIs(self._b(response={"responseId": "rb", "completionState": "COMPLETE"}).execute(_request()).kind,
                      ProviderOutcomeKind.SUCCESS)

    def test_outcome_leaks_no_prompt_or_secret(self):
        outcome = self._a(error=ProviderARateLimited("2")).execute(_request())
        blob = outcome.detail + "".join(f"{k}{v}" for k, v in dict(outcome.safe_evidence).items())
        self.assertNotIn("SECRET-PROMPT", blob)


# ===========================================================================
# Finding 5 (preserved) — earlier structural fixes.
# ===========================================================================
class Finding5Preserved(unittest.TestCase):
    def test_provider_specific_wire_fields_isolated(self):
        pa, pb = _profile(), _profile(profile_id="prof-B-v1", provider="provider_b", model="b-pro", pv="v1")
        a_wire = ProviderAAdapter(_a_ok(), pa).build_wire_request(_request())
        b_wire = ProviderBAdapter(_b_ok(), pb).build_wire_request(_request())
        self.assertIn("max_tokens", a_wire); self.assertNotIn("maxOutputTokens", a_wire)
        self.assertIn("maxOutputTokens", b_wire); self.assertNotIn("max_tokens", b_wire)
        self.assertEqual(a_wire["max_tokens"], b_wire["maxOutputTokens"])

    def test_missing_request_id_is_provider_response_invalid(self):
        outcome = ProviderAAdapter(RecordingTransport(scripted_response={"finish_reason": "stop"}),
                                   _profile(requires_id=True)).execute(_request())
        self.assertIs(outcome.kind, ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID)

    def test_cas_bound_to_identity_binding_and_state(self):
        contract, store, _, _, _ = _registered(_profile())
        other = AttemptExecutionContract.plan(
            "A1", "job-1", _profile(profile_id="prof-B-v1", provider="provider_b", pv="v1"), CONTRACT)
        self.assertFalse(store.compare_and_set(other, AttemptState.PLANNED, AttemptState.DISPATCHED))
        self.assertIs(store.get_record("A1").state, AttemptState.PLANNED)
        self.assertTrue(store.compare_and_set(contract, AttemptState.PLANNED, AttemptState.DISPATCHED))


if __name__ == "__main__":
    unittest.main()
