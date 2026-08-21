"""Day72 — EXECUTED_LOCAL_RUNTIME tests for the replaceable Provider Adapter slice (post-review).

Deterministic, in-process tests. Standard library only; no network, no SDK, no real Provider, no database.
They prove the RULES of the Day72 boundary and the Day72 review regressions:

  Finding 1 — persisted Attempt execution-contract binding is validated before any call (AttemptBindingError).
  Finding 2 — one Attempt makes at most one external call (guarded compare-and-set PLANNED -> DISPATCHED).
  Finding 3 — the transport/SDK client stays inside the Adapter (execute()); dispatch takes no transport.
  Finding 4 — ProviderSelectionPolicy uses the application contract (incompatible -> ProviderIncompatibleError).
  Finding 5 — ProviderRegistry rejects a conflicting duplicate profile_id.
  Finding 6 — a disabled profile reaches BLOCKED_PROFILE_DISABLED through the real guarded dispatch path.
  Finding 7 — preserved outcome/failure semantics (CAPABILITY_ERROR pre-call, TRUNCATION, PROVIDER_RESPONSE_INVALID).

They do NOT prove a real SDK/API, real HTTP, Provider behaviour, cost, rate limits, credentials,
INTEGRATION_RUNTIME or PRODUCTION.

Run from ``projects/ai-agent/``:  python3 -m unittest discover -s tests -v
"""

import inspect
import os
import sys
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
    ProfileStatus,
    ProviderIncompatibleError,
    ProviderOutcomeKind,
    ProviderRegistry,
    ProviderSelectionPolicy,
    VerificationTier,
)
from provider_adapters import (  # noqa: E402
    ProviderAAdapter,
    ProviderBAdapter,
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
                              prompt="...")


def _planned(profile, attempt_id="A1", job_id="job-1"):
    contract = AttemptExecutionContract.plan(attempt_id, job_id, profile, CONTRACT)
    store = InMemoryAttemptStateStore()
    store.plan(attempt_id)
    return contract, store


def _a_success_transport():
    return RecordingTransport({"id": "ra", "finish_reason": "stop"})


class Finding1AttemptBinding(unittest.TestCase):
    # A1 bound to Provider A/v3 cannot be dispatched by a Provider B Adapter.
    def test_wrong_provider_adapter_is_binding_error_zero_calls(self):
        a_profile = _profile()                       # the Attempt was planned on Provider A/v3
        contract, store = _planned(a_profile)
        b_profile = _profile(profile_id="prof-B-v1", provider="provider_b", model="b-pro", pv="v1")
        b_transport = RecordingTransport({"responseId": "rb", "completionState": "COMPLETE"})
        with self.assertRaises(AttemptBindingError):
            dispatch_attempt(request=_request(), contract=contract,
                             adapter=ProviderBAdapter(b_transport, b_profile), state_store=store)
        self.assertEqual(len(b_transport.calls), 0)
        self.assertIs(store.get("A1"), AttemptState.PLANNED)   # contract/state not rewritten

    def test_application_contract_mismatch_zero_calls(self):
        profile = _profile()
        contract, store = _planned(profile)
        transport = _a_success_transport()
        with self.assertRaises(AttemptBindingError):
            dispatch_attempt(request=_request(contract="other.v1"), contract=contract,
                             adapter=ProviderAAdapter(transport, profile), state_store=store)
        self.assertEqual(len(transport.calls), 0)

    def test_job_id_mismatch_zero_calls(self):
        profile = _profile()
        contract, store = _planned(profile)
        transport = _a_success_transport()
        with self.assertRaises(AttemptBindingError):
            dispatch_attempt(request=_request(job_id="job-OTHER"), contract=contract,
                             adapter=ProviderAAdapter(transport, profile), state_store=store)
        self.assertEqual(len(transport.calls), 0)

    def test_profile_version_mismatch_zero_calls(self):
        contract, store = _planned(_profile(pv="v3"))         # contract bound to v3
        drifted = _profile(pv="v4")                            # adapter carries a v4 profile (same profile_id)
        transport = _a_success_transport()
        with self.assertRaises(AttemptBindingError):
            dispatch_attempt(request=_request(), contract=contract,
                             adapter=ProviderAAdapter(transport, drifted), state_store=store)
        self.assertEqual(len(transport.calls), 0)

    def test_adapter_version_mismatch_zero_calls(self):
        contract, store = _planned(_profile(av="1.0.0"))
        transport = _a_success_transport()
        with self.assertRaises(AttemptBindingError):
            dispatch_attempt(request=_request(), contract=contract,
                             adapter=ProviderAAdapter(transport, _profile(av="2.0.0")), state_store=store)
        self.assertEqual(len(transport.calls), 0)


class Finding2OneCallPerAttempt(unittest.TestCase):
    def test_first_dispatch_one_call_and_dispatched(self):
        profile = _profile()
        contract, store = _planned(profile)
        transport = _a_success_transport()
        result = dispatch_attempt(request=_request(), contract=contract,
                                  adapter=ProviderAAdapter(transport, profile), state_store=store)
        self.assertIs(result.outcome.kind, ProviderOutcomeKind.SUCCESS)
        self.assertEqual(result.provider_calls, 1)
        self.assertIs(result.attempt_state, AttemptState.DISPATCHED)
        self.assertIs(store.get("A1"), AttemptState.DISPATCHED)

    def test_second_dispatch_same_attempt_rejected_zero_new_calls(self):
        profile = _profile()
        contract, store = _planned(profile)
        transport = _a_success_transport()
        adapter = ProviderAAdapter(transport, profile)
        dispatch_attempt(request=_request(), contract=contract, adapter=adapter, state_store=store)
        self.assertEqual(len(transport.calls), 1)
        with self.assertRaises(AttemptStateError):
            dispatch_attempt(request=_request(), contract=contract, adapter=adapter, state_store=store)
        self.assertEqual(len(transport.calls), 1)   # no NEW call

    def test_already_dispatched_attempt_is_not_called_again(self):
        profile = _profile()
        contract, store = _planned(profile)
        # Simulate the Attempt already DISPATCHED by a prior call.
        store.compare_and_set("A1", AttemptState.PLANNED, AttemptState.DISPATCHED)
        transport = _a_success_transport()
        with self.assertRaises(AttemptStateError):
            dispatch_attempt(request=_request(), contract=contract,
                             adapter=ProviderAAdapter(transport, profile), state_store=store)
        self.assertEqual(len(transport.calls), 0)

    def test_unknown_attempt_transition_failure_zero_calls(self):
        profile = _profile()
        contract = AttemptExecutionContract.plan("A1", "job-1", profile, CONTRACT)
        store = InMemoryAttemptStateStore()   # NOT planned -> get() returns None
        transport = _a_success_transport()
        with self.assertRaises(AttemptStateError):
            dispatch_attempt(request=_request(), contract=contract,
                             adapter=ProviderAAdapter(transport, profile), state_store=store)
        self.assertEqual(len(transport.calls), 0)


class Finding3TransportInsideAdapter(unittest.TestCase):
    def test_dispatch_has_no_transport_parameter(self):
        params = set(inspect.signature(dispatch_attempt).parameters)
        self.assertNotIn("transport", params)
        self.assertEqual(params, {"request", "contract", "adapter", "state_store"})

    def test_registry_adapter_dispatches_without_business_passing_transport(self):
        profile = _profile()
        registry = ProviderRegistry()
        registry.register(ProviderAAdapter(_a_success_transport(), profile))
        adapter = registry.get(profile.profile_id)     # business code only holds the ProviderAdapter
        contract, store = _planned(profile)
        result = dispatch_attempt(request=_request(), contract=contract, adapter=adapter, state_store=store)
        self.assertIs(result.outcome.kind, ProviderOutcomeKind.SUCCESS)
        self.assertEqual(result.provider_calls, 1)

    def test_provider_a_and_b_distinct_wire_but_same_success_semantics(self):
        pa = _profile()
        pb = _profile(profile_id="prof-B-v1", provider="provider_b", model="b-pro", pv="v1")
        a_wire = ProviderAAdapter(RecordingTransport({}), pa).build_wire_request(_request())
        b_wire = ProviderBAdapter(RecordingTransport({}), pb).build_wire_request(_request())
        self.assertIn("max_tokens", a_wire)
        self.assertIn("maxOutputTokens", b_wire)
        self.assertNotIn("maxOutputTokens", a_wire)
        self.assertNotIn("max_tokens", b_wire)
        # equivalent application semantics via execute()
        oa = ProviderAAdapter(RecordingTransport({"id": "ra", "finish_reason": "stop"}), pa).execute(_request())
        ob = ProviderBAdapter(RecordingTransport({"responseId": "rb", "completionState": "COMPLETE"}), pb).execute(_request())
        self.assertIs(oa.kind, ProviderOutcomeKind.SUCCESS)
        self.assertIs(ob.kind, ProviderOutcomeKind.SUCCESS)


class Finding4SelectionUsesContract(unittest.TestCase):
    def test_compatible_profile_selected(self):
        profile = _profile()
        policy = ProviderSelectionPolicy({"standard": profile})
        self.assertIs(policy.select(ProductOption("standard"), CONTRACT), profile)

    def test_incompatible_contract_rejected_no_fallback(self):
        incompatible = _profile(profile_id="prof-B-v1", provider="provider_b", supported=())
        fallback = _profile()   # present in allowlist but must NOT be auto-selected
        policy = ProviderSelectionPolicy({"standard": incompatible, "premium": fallback})
        with self.assertRaises(ProviderIncompatibleError):
            policy.select(ProductOption("standard"), CONTRACT)

    def test_disabled_profile_in_allowlist_rejected(self):
        policy = ProviderSelectionPolicy({"standard": _profile(status=ProfileStatus.DISABLED)})
        with self.assertRaises(ProfileDisabledError):
            policy.select(ProductOption("standard"), CONTRACT)


class Finding5RegistryDuplicate(unittest.TestCase):
    def test_conflicting_duplicate_profile_id_rejected(self):
        profile = _profile()
        registry = ProviderRegistry()
        registry.register(ProviderAAdapter(_a_success_transport(), profile))
        with self.assertRaises(DuplicateProfileRegistrationError):
            registry.register(ProviderAAdapter(_a_success_transport(), profile))   # different instance

    def test_idempotent_same_instance_registration_is_noop(self):
        profile = _profile()
        adapter = ProviderAAdapter(_a_success_transport(), profile)
        registry = ProviderRegistry()
        registry.register(adapter)
        registry.register(adapter)   # same object -> idempotent
        self.assertIs(registry.get(profile.profile_id), adapter)


class Finding6DisableRealPath(unittest.TestCase):
    def test_profile_disabled_before_dispatch_blocks_via_state_path(self):
        v3 = _profile(pv="v3")
        contract, store = _planned(v3, attempt_id="A1")     # A1 bound to v3
        disabled_adapter = ProviderAAdapter(_a_success_transport(), v3.disabled())  # v3 disabled before dispatch
        result = dispatch_attempt(request=_request(), contract=contract,
                                  adapter=disabled_adapter, state_store=store)
        self.assertEqual(result.provider_calls, 0)
        # A1 reached BLOCKED_PROFILE_DISABLED through the real guarded dispatch path (not hand-built).
        self.assertIs(result.attempt_state, AttemptState.BLOCKED_PROFILE_DISABLED)
        self.assertIs(store.get("A1"), AttemptState.BLOCKED_PROFILE_DISABLED)
        # A1's persisted binding is unchanged (still v3); it is NOT rebound to v4.
        self.assertEqual(contract.profile_version, "v3")
        # Choosing another Profile requires an explicit NEW Attempt (A2) with its own contract + state.
        v4 = _profile(profile_id="prof-A-v4", pv="v4")
        contract2, store2 = _planned(v4, attempt_id="A2")
        r2 = dispatch_attempt(request=_request(), contract=contract2,
                              adapter=ProviderAAdapter(_a_success_transport(), v4), state_store=store2)
        self.assertIs(r2.attempt_state, AttemptState.DISPATCHED)
        self.assertEqual(r2.provider_calls, 1)


class Finding7PreservedSemantics(unittest.TestCase):
    def test_capability_not_supported_is_precall_capability_error_zero_calls(self):
        profile = _profile(supported=())              # does not support research_claims.v1
        contract, store = _planned(profile)
        transport = _a_success_transport()
        result = dispatch_attempt(request=_request(), contract=contract,
                                  adapter=ProviderAAdapter(transport, profile), state_store=store)
        self.assertIs(result.outcome.kind, ProviderOutcomeKind.CAPABILITY_ERROR)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(len(transport.calls), 0)
        self.assertIs(store.get("A1"), AttemptState.PLANNED)

    def test_two_output_limit_states_both_map_to_truncation(self):
        pa = _profile()
        pb = _profile(provider="provider_b")
        oa = ProviderAAdapter(RecordingTransport({"id": "ra", "finish_reason": "length"}), pa).execute(_request())
        ob = ProviderBAdapter(RecordingTransport({"responseId": "rb", "completionState": "MAX_TOKENS"}), pb).execute(_request())
        self.assertIs(oa.kind, ProviderOutcomeKind.TRUNCATION)
        self.assertIs(ob.kind, ProviderOutcomeKind.TRUNCATION)

    def test_missing_required_request_identity_is_provider_response_invalid(self):
        transport = RecordingTransport({"finish_reason": "stop"})   # no "id"
        outcome = ProviderAAdapter(transport, _profile(requires_id=True)).execute(_request())
        self.assertIs(outcome.kind, ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID)


if __name__ == "__main__":
    unittest.main()
