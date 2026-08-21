"""Day72 — EXECUTED_LOCAL_RUNTIME tests for the replaceable Provider Adapter slice (round-2 review).

Deterministic, in-process tests. Standard library only; no network, no SDK, no real Provider, no database.
Round-2 findings covered:

  Finding 1 — the Attempt store holds the AUTHORITATIVE immutable contract; a self-consistent forged
              request+contract+Adapter trio is rejected because it does not match the stored binding.
  Finding 2 — the in-memory compare-and-set is thread-safe; two concurrent dispatches of one Attempt yield
              exactly one external call (proved with threading.Barrier; IN-PROCESS evidence only).
  Finding 3 — the real Registry composition path: get_selectable() (new task) vs resolve_bound_attempt()
              (already-persisted Attempt); a lifecycle disable reaches PLANNED -> BLOCKED_PROFILE_DISABLED
              WITHOUT constructing a disabled Adapter directly.
  Finding 4 — each Adapter translates Provider-specific SDK FAILURE facts into the same stable
              ProviderOutcomeKind (REFUSAL / RATE_LIMITED / AUTHENTICATION_ERROR / TIMEOUT_UNKNOWN /
              TRANSPORT_ERROR / PROVIDER_RESPONSE_INVALID / TRUNCATION / SUCCESS); timeout is never a second
              call and never a retryable transport error.
  Finding 5 — earlier fixes are preserved (binding validation, transport inside Adapter, no dispatch transport
              param, selection-by-contract, duplicate-registry rejection, one call per Attempt).

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
    VerificationTier,
)
from provider_adapters import (  # noqa: E402
    ProviderAAdapter,
    ProviderAAuthFailed,
    ProviderAConnectionError,
    ProviderARateLimited,
    ProviderARefused,
    ProviderATimedOut,
    ProviderBAdapter,
    ProviderBDeadlineExceeded,
    ProviderBDeclined,
    ProviderBNetworkError,
    ProviderBThrottled,
    ProviderBUnauthorized,
    RecordingTransport,
    dispatch_attempt,
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


def _planned(profile, attempt_id="A1", job_id="job-1"):
    contract = AttemptExecutionContract.plan(attempt_id, job_id, profile, CONTRACT)
    store = InMemoryAttemptStateStore()
    store.plan(contract)
    lifecycle = ProfileLifecycle()
    lifecycle.register(profile)
    return contract, store, lifecycle


# ===========================================================================
# Finding 1 — authoritative binding held by the store.
# ===========================================================================
class Finding1AuthoritativeBinding(unittest.TestCase):
    def test_forged_self_consistent_contract_is_rejected_zero_calls(self):
        a_profile = _profile()                              # store's authoritative binding: Provider A / v3
        contract, store, lifecycle = _planned(a_profile, attempt_id="A1")
        # Attacker forges a Provider B contract that REUSES attempt_id=A1; request + B contract + B Adapter
        # are all mutually consistent, so validate_attempt_binding() alone would pass.
        b_profile = _profile(profile_id="prof-B-v1", provider="provider_b", model="b-pro", pv="v1")
        forged = AttemptExecutionContract.plan("A1", "job-1", b_profile, CONTRACT)
        b_transport = _b_ok()
        lifecycle.register(b_profile)
        with self.assertRaises(AttemptBindingError):
            dispatch_attempt(request=_request(), contract=forged,
                             adapter=ProviderBAdapter(b_transport, b_profile),
                             state_store=store, lifecycle=lifecycle)
        self.assertEqual(len(b_transport.calls), 0)
        rec = store.get_record("A1")
        self.assertEqual(rec.contract, contract)            # authoritative binding unchanged (Provider A/v3)
        self.assertIs(rec.state, AttemptState.PLANNED)      # state unchanged

    def test_duplicate_plan_rejected(self):
        contract, store, _ = _planned(_profile())
        with self.assertRaises(AttemptStateError):
            store.plan(contract)                            # same attempt_id

    def test_plan_then_read_back_contract_is_identical(self):
        contract, store, _ = _planned(_profile())
        self.assertEqual(store.get_record("A1").contract, contract)

    def test_cas_bound_to_identity_binding_and_state(self):
        contract, store, _ = _planned(_profile())
        other = AttemptExecutionContract.plan(
            "A1", "job-1", _profile(profile_id="prof-B-v1", provider="provider_b", pv="v1"), CONTRACT)
        # A CAS with a NON-matching binding must fail even with the right expected state.
        self.assertFalse(store.compare_and_set(other, AttemptState.PLANNED, AttemptState.DISPATCHED))
        self.assertIs(store.get_record("A1").state, AttemptState.PLANNED)
        # The correct authoritative binding transitions.
        self.assertTrue(store.compare_and_set(contract, AttemptState.PLANNED, AttemptState.DISPATCHED))


# ===========================================================================
# Finding 2 — thread-safe compare-and-set + real concurrency (one call).
# ===========================================================================
class Finding2ConcurrencyOneCall(unittest.TestCase):
    def test_two_concurrent_dispatches_make_exactly_one_call(self):
        for _ in range(40):   # repeat for stability; deterministic assertions, no sleeps
            profile = _profile()
            contract, store, lifecycle = _planned(profile)
            transport = _a_ok()
            adapter = ProviderAAdapter(transport, profile)
            barrier = threading.Barrier(2)
            results, errors = [], []

            def worker():
                barrier.wait()   # align both threads at the same start point
                try:
                    results.append(dispatch_attempt(request=_request(), contract=contract, adapter=adapter,
                                                    state_store=store, lifecycle=lifecycle))
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
        profile = _profile()
        contract, store, lifecycle = _planned(profile)
        transport = _a_ok()
        adapter = ProviderAAdapter(transport, profile)
        r = dispatch_attempt(request=_request(), contract=contract, adapter=adapter, state_store=store,
                             lifecycle=lifecycle)
        self.assertEqual(r.provider_calls, 1)
        self.assertIs(r.attempt_state, AttemptState.DISPATCHED)
        with self.assertRaises(AttemptStateError):
            dispatch_attempt(request=_request(), contract=contract, adapter=adapter, state_store=store,
                             lifecycle=lifecycle)
        self.assertEqual(len(transport.calls), 1)

    def test_unknown_attempt_zero_calls(self):
        profile = _profile()
        contract = AttemptExecutionContract.plan("A1", "job-1", profile, CONTRACT)
        store = InMemoryAttemptStateStore()   # never planned
        lifecycle = ProfileLifecycle(); lifecycle.register(profile)
        transport = _a_ok()
        with self.assertRaises(AttemptStateError):
            dispatch_attempt(request=_request(), contract=contract, adapter=ProviderAAdapter(transport, profile),
                             state_store=store, lifecycle=lifecycle)
        self.assertEqual(len(transport.calls), 0)


# ===========================================================================
# Finding 3 — real Registry composition path for disable.
# ===========================================================================
class Finding3RegistryDisablePath(unittest.TestCase):
    def test_end_to_end_disable_via_lifecycle_reaches_blocked(self):
        v3 = _profile(pv="v3")
        registry = ProviderRegistry()
        transport = _a_ok()
        registry.register(ProviderAAdapter(transport, v3))            # register Provider A / v3
        # Persist A1 bound to v3 (PLANNED) using the same lifecycle overlay the Registry owns.
        contract = AttemptExecutionContract.plan("A1", "job-1", v3, CONTRACT)
        store = InMemoryAttemptStateStore(); store.plan(contract)
        # Disable v3 through the formal lifecycle API (NOT by constructing a disabled Adapter).
        registry.disable(v3.profile_id)
        # New-task selection now fails closed.
        with self.assertRaises(ProfileDisabledError):
            registry.get_selectable(v3.profile_id, CONTRACT)
        # Bound-attempt resolution still returns the exact bound Adapter (for zero-call block / audit).
        bound_adapter = registry.resolve_bound_attempt(contract)
        self.assertEqual(bound_adapter.capability_profile.profile_version, "v3")
        # Dispatch drives the real guarded state path.
        result = dispatch_attempt(request=_request(), contract=contract, adapter=bound_adapter,
                                  state_store=store, lifecycle=registry.lifecycle)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(len(transport.calls), 0)
        self.assertIs(result.attempt_state, AttemptState.BLOCKED_PROFILE_DISABLED)
        self.assertIs(store.get_record("A1").state, AttemptState.BLOCKED_PROFILE_DISABLED)
        self.assertEqual(store.get_record("A1").contract.profile_version, "v3")   # A1 still v3
        # No A2 was auto-created; only the single planned Attempt exists.
        self.assertIsNone(store.get_record("A2"))

    def test_get_selectable_active_supported_returns_adapter(self):
        v3 = _profile()
        registry = ProviderRegistry()
        registry.register(ProviderAAdapter(_a_ok(), v3))
        self.assertIs(registry.get_selectable(v3.profile_id, CONTRACT).capability_profile, v3)

    def test_get_selectable_incompatible_contract_rejected(self):
        p = _profile(supported=())
        registry = ProviderRegistry(); registry.register(ProviderAAdapter(_a_ok(), p))
        with self.assertRaises(ProviderIncompatibleError):
            registry.get_selectable(p.profile_id, CONTRACT)

    def test_get_selectable_quarantined_rejected(self):
        p = _profile()
        registry = ProviderRegistry(); registry.register(ProviderAAdapter(_a_ok(), p))
        registry.quarantine(p.profile_id)
        with self.assertRaises(ProfileDisabledError):
            registry.get_selectable(p.profile_id, CONTRACT)

    def test_resolve_bound_attempt_binding_mismatch_rejected(self):
        registry = ProviderRegistry()
        registry.register(ProviderAAdapter(_a_ok(), _profile(pv="v3")))
        drifted_contract = AttemptExecutionContract.plan("A1", "job-1", _profile(pv="v4"), CONTRACT)
        with self.assertRaises(AttemptBindingError):
            registry.resolve_bound_attempt(drifted_contract)

    def test_duplicate_registration_rejected_idempotent_same_instance(self):
        p = _profile()
        registry = ProviderRegistry()
        registry.register(ProviderAAdapter(_a_ok(), p))
        with self.assertRaises(DuplicateProfileRegistrationError):
            registry.register(ProviderAAdapter(_a_ok(), p))     # different instance -> reject
        same = ProviderAAdapter(_a_ok(), _profile(profile_id="prof-X"))
        registry.register(same); registry.register(same)        # same instance -> idempotent


# ===========================================================================
# Finding 4 — Provider-specific failure translation (A/B parity).
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
        for adapter, err in ((self._a(error=ProviderATimedOut("ra")), None),
                             (self._b(error=ProviderBDeadlineExceeded("rb")), None)):
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

    def test_timeout_through_dispatch_makes_no_second_call(self):
        profile = _profile()
        contract, store, lifecycle = _planned(profile)
        transport = RecordingTransport(scripted_error=ProviderATimedOut("ra"))
        adapter = ProviderAAdapter(transport, profile)
        r = dispatch_attempt(request=_request(), contract=contract, adapter=adapter, state_store=store,
                             lifecycle=lifecycle)
        self.assertIs(r.outcome.kind, ProviderOutcomeKind.TIMEOUT_UNKNOWN)
        self.assertEqual(r.provider_calls, 1)                        # one send attempt
        self.assertIs(r.attempt_state, AttemptState.DISPATCHED)      # Attempt is 'sent / pending reconcile'
        with self.assertRaises(AttemptStateError):                  # Adapter did NOT auto-create A2/retry
            dispatch_attempt(request=_request(), contract=contract, adapter=adapter, state_store=store,
                             lifecycle=lifecycle)
        self.assertEqual(len(transport.calls), 1)

    def test_pre_binding_failure_reports_zero_calls(self):
        # A binding failure before any send must report provider_calls semantics via zero transport calls.
        a_profile = _profile()
        contract, store, lifecycle = _planned(a_profile)
        wrong_profile = _profile(profile_id="prof-B-v1", provider="provider_b", pv="v1")
        wrong_contract = AttemptExecutionContract.plan("A1", "job-1", wrong_profile, CONTRACT)
        t = _b_ok()
        with self.assertRaises(AttemptBindingError):
            dispatch_attempt(request=_request(), contract=wrong_contract,
                             adapter=ProviderBAdapter(t, wrong_profile), state_store=store, lifecycle=lifecycle)
        self.assertEqual(len(t.calls), 0)


# ===========================================================================
# Finding 5 — preserved earlier fixes.
# ===========================================================================
class Finding5Preserved(unittest.TestCase):
    def test_dispatch_has_no_transport_parameter(self):
        params = set(inspect.signature(dispatch_attempt).parameters)
        self.assertNotIn("transport", params)
        self.assertEqual(params, {"request", "contract", "adapter", "state_store", "lifecycle"})

    def test_provider_specific_wire_fields_isolated(self):
        pa, pb = _profile(), _profile(profile_id="prof-B-v1", provider="provider_b", model="b-pro", pv="v1")
        a_wire = ProviderAAdapter(_a_ok(), pa).build_wire_request(_request())
        b_wire = ProviderBAdapter(_b_ok(), pb).build_wire_request(_request())
        self.assertIn("max_tokens", a_wire); self.assertNotIn("maxOutputTokens", a_wire)
        self.assertIn("maxOutputTokens", b_wire); self.assertNotIn("max_tokens", b_wire)
        self.assertEqual(a_wire["max_tokens"], b_wire["maxOutputTokens"])

    def test_selection_policy_uses_contract_and_status(self):
        good = _profile()
        policy = ProviderSelectionPolicy({"standard": good})
        self.assertIs(policy.select(ProductOption("standard"), CONTRACT), good)
        bad = ProviderSelectionPolicy({"standard": _profile(supported=())})
        with self.assertRaises(ProviderIncompatibleError):
            bad.select(ProductOption("standard"), CONTRACT)
        lc = ProfileLifecycle(); lc.register(good); lc.disable(good.profile_id)
        with self.assertRaises(ProfileDisabledError):
            ProviderSelectionPolicy({"standard": good}, lifecycle=lc).select(ProductOption("standard"), CONTRACT)

    def test_request_profile_binding_mismatch_zero_calls(self):
        contract, store, lifecycle = _planned(_profile(pv="v3"))
        transport = _a_ok()
        with self.assertRaises(AttemptBindingError):
            dispatch_attempt(request=_request(job_id="job-OTHER"), contract=contract,
                             adapter=ProviderAAdapter(transport, _profile(pv="v3")),
                             state_store=store, lifecycle=lifecycle)
        self.assertEqual(len(transport.calls), 0)


if __name__ == "__main__":
    unittest.main()
