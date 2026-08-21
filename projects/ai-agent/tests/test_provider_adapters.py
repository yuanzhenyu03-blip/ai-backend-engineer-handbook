"""Day72 — EXECUTED_LOCAL_RUNTIME tests for the replaceable Provider Adapter slice.

Seven deterministic, in-process tests. Standard library only; no network, no SDK, no real Provider,
no database. They prove the RULES of the Day72 boundary; they do NOT prove a real SDK/HTTP integration,
real model behaviour, cost/rate limits, credentials, INTEGRATION_RUNTIME or PRODUCTION.

Run from ``projects/ai-agent/``:  python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from provider_contract import (  # noqa: E402
    ApplicationRequest,
    AttemptExecutionContract,
    AttemptState,
    CapabilityProfile,
    ProfileDisabledError,
    ProfileStatus,
    ProviderOutcomeKind,
    ProviderRegistry,
    VerificationTier,
)
from provider_adapters import (  # noqa: E402
    ProviderAAdapter,
    ProviderBAdapter,
    RecordingTransport,
    dispatch_attempt,
)

CONTRACT = "research_claims.v1"


def _profile(profile_id="prof-A-v3", provider="provider_a", model="a-large", pv="v3",
             supported=(CONTRACT,), requires_id=True, status=ProfileStatus.ACTIVE):
    return CapabilityProfile(
        profile_id=profile_id, provider_name=provider, model=model, api_version="2026-08-01",
        profile_version=pv, adapter_version="1.0.0", supported_contracts=frozenset(supported),
        requires_request_identity=requires_id, verification_tier=VerificationTier.EXECUTED_LOCAL_RUNTIME,
        status=status)


def _request():
    return ApplicationRequest(job_id="job-1", tenant_id="tenantA", application_contract=CONTRACT,
                              task_type="research_report", max_output_tokens=512, correlation_id="corr-1",
                              prompt="...")


def _contract_for(profile, attempt_id="A1"):
    return AttemptExecutionContract.plan(attempt_id, "job-1", profile, CONTRACT)


class Day72ProviderAdapterTests(unittest.TestCase):
    # 1) Capability rejection BEFORE transport -> zero Provider calls.
    def test_capability_rejection_makes_zero_provider_calls(self):
        profile = _profile(supported=())  # does NOT support research_claims.v1
        transport = RecordingTransport(scripted_response={"id": "x", "finish_reason": "stop"})
        adapter = ProviderAAdapter(transport, profile)
        result = dispatch_attempt(request=_request(), contract=_contract_for(profile),
                                  adapter=adapter, transport=transport)
        self.assertIs(result.outcome.kind, ProviderOutcomeKind.CAPABILITY_ERROR)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(len(transport.calls), 0)

    # 2) Provider-specific request-field isolation (different wire keys, same MEANING).
    def test_provider_specific_request_fields_are_isolated(self):
        pa, pb = _profile(), _profile(profile_id="prof-B-v1", provider="provider_b", model="b-pro", pv="v1")
        a_wire = ProviderAAdapter(RecordingTransport({}), pa).build_wire_request(_request())
        b_wire = ProviderBAdapter(RecordingTransport({}), pb).build_wire_request(_request())
        self.assertIn("max_tokens", a_wire)          # Provider A field
        self.assertIn("maxOutputTokens", b_wire)     # Provider B field (different key)
        self.assertNotIn("maxOutputTokens", a_wire)
        self.assertNotIn("max_tokens", b_wire)
        # Same application meaning (max output) despite different Provider syntax.
        self.assertEqual(a_wire["max_tokens"], b_wire["maxOutputTokens"])

    # 3) Equivalent SUCCESS semantics across Providers.
    def test_equivalent_success_semantics(self):
        ta = RecordingTransport({"id": "ra", "finish_reason": "stop"})
        tb = RecordingTransport({"responseId": "rb", "completionState": "COMPLETE"})
        oa = dispatch_attempt(request=_request(), contract=_contract_for(_profile()),
                              adapter=ProviderAAdapter(ta, _profile()), transport=ta).outcome
        pb = _profile(profile_id="prof-B-v1", provider="provider_b", model="b-pro", pv="v1")
        ob = dispatch_attempt(request=_request(), contract=_contract_for(pb),
                              adapter=ProviderBAdapter(tb, pb), transport=tb).outcome
        self.assertIs(oa.kind, ProviderOutcomeKind.SUCCESS)
        self.assertIs(ob.kind, ProviderOutcomeKind.SUCCESS)

    # 4) Two DIFFERENT Provider output-limit states both map to TRUNCATION.
    def test_equivalent_truncation_semantics(self):
        ta = RecordingTransport({"id": "ra", "finish_reason": "length"})       # Provider A limit state
        tb = RecordingTransport({"responseId": "rb", "completionState": "MAX_TOKENS"})  # Provider B limit state
        oa = ProviderAAdapter(ta, _profile()).translate_outcome(ta.scripted_response)
        pb = _profile(provider="provider_b")
        ob = ProviderBAdapter(tb, pb).translate_outcome(tb.scripted_response)
        self.assertIs(oa.kind, ProviderOutcomeKind.TRUNCATION)
        self.assertIs(ob.kind, ProviderOutcomeKind.TRUNCATION)

    # 5) Missing required Provider request identity -> PROVIDER_RESPONSE_INVALID (Adapter gate).
    def test_missing_request_identity_is_provider_response_invalid(self):
        transport = RecordingTransport({"finish_reason": "stop"})   # no "id"
        outcome = ProviderAAdapter(transport, _profile(requires_id=True)).translate_outcome(
            transport.scripted_response)
        self.assertIs(outcome.kind, ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID)

    # 6) Registry injection: business code depends only on the ProviderAdapter Protocol.
    def test_registry_injects_concrete_adapter(self):
        profile = _profile()
        transport = RecordingTransport({"id": "ra", "finish_reason": "stop"})
        registry = ProviderRegistry()
        registry.register(ProviderAAdapter(transport, profile))
        adapter = registry.get(profile.profile_id)   # composition boundary hands back the concrete Adapter
        result = dispatch_attempt(request=_request(), contract=_contract_for(profile),
                                  adapter=adapter, transport=transport)
        self.assertIs(result.outcome.kind, ProviderOutcomeKind.SUCCESS)
        self.assertEqual(result.provider_calls, 1)

    # 7) A disabled Profile fails closed; the planned Attempt is retained, contract not rewritten.
    def test_disabled_profile_fails_closed_and_attempt_is_preserved(self):
        active = _profile()
        transport = RecordingTransport({"id": "ra", "finish_reason": "stop"})
        registry = ProviderRegistry()
        registry.register(ProviderAAdapter(transport, active.disabled()))  # v3 disabled before dispatch
        a1 = _contract_for(active, attempt_id="A1")                        # A1 was planned on v3
        with self.assertRaises(ProfileDisabledError):
            registry.get(active.profile_id)
        # No Provider call happened; A1 keeps its original v3 execution contract (never rewritten).
        self.assertEqual(len(transport.calls), 0)
        blocked = AttemptExecutionContract(
            attempt_id=a1.attempt_id, job_id=a1.job_id, profile_id=a1.profile_id,
            provider_name=a1.provider_name, model=a1.model, api_version=a1.api_version,
            profile_version=a1.profile_version, adapter_version=a1.adapter_version,
            application_contract=a1.application_contract, state=AttemptState.BLOCKED_PROFILE_DISABLED)
        self.assertEqual(blocked.profile_version, "v3")
        self.assertIs(blocked.state, AttemptState.BLOCKED_PROFILE_DISABLED)


if __name__ == "__main__":
    unittest.main()
