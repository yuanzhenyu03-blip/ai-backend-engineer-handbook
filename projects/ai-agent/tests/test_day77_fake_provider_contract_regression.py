"""Day77 deterministic Fake Provider, Contract, and LLM regression tests.

The suite exercises the real Day72–Day76 seams with standard-library doubles.
It is EXECUTED_LOCAL_RUNTIME evidence only: no real SDK, network, Provider,
database, broker, Worker, Redis, external tool, billing system, or production
traffic participates.
"""

import json
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fake_provider_testing import (  # noqa: E402
    BehaviorGolden,
    BehaviorObservation,
    ControlledFakeTransport,
    FakeClock,
    IndependentProviderCallLog,
    ScriptedExchange,
    golden_mismatches,
)
from output_tool_contracts import (  # noqa: E402
    AdmissionStatus,
    AuthContext,
    CompletionStatus,
    InMemoryDurableStore,
    InMemoryToolExecutor,
    JobRecord,
    JobStatus,
    OutcomeDecision,
    OutcomeStatus,
    admit_tool_call,
    default_registry,
    default_report_store,
)
from prompt_contracts import (  # noqa: E402
    CITATIONS_REQUIRED,
    MessageRole,
    MessageTemplate,
    PromptContractRevision,
    VariableSpec,
    backward_incompatibilities,
)
from provider_adapters import (  # noqa: E402
    ExecutionCertainty as AdapterExecutionCertainty,
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
)
from provider_contract import (  # noqa: E402
    ApplicationRequest,
    AttemptExecutionContract,
    CapabilityProfile,
    ProfileStatus,
    ProviderOutcomeKind,
    VerificationTier,
)
from recovery_cost import (  # noqa: E402
    AttemptCost,
    CostStatus,
    ExecutionCertainty as RecoveryExecutionCertainty,
    FailureClass,
    FallbackPolicy,
    IncidentRecoveryEvidence,
    RecoveryAction as Day76RecoveryAction,
    mark_unknown,
    may_close_incident,
    plan_recovery,
    settle,
)
from routing_policy import (  # noqa: E402
    Candidate,
    LatencyEvidence,
    PricingEvidence,
    RoutingPolicy,
    route,
)
from streaming_cache_batching import (  # noqa: E402
    BatchEnvelopeStatus,
    BatchItem,
    BatchItemOutcome,
    BatchCompatibilityKey,
    CacheKey,
    CacheLookupStatus,
    CacheableCandidate,
    CompleteCandidate,
    InMemoryResponseCache,
    ProviderBatchItemResult,
    RecoveryAction as BatchRecoveryAction,
    StreamAssembler,
    StreamAssemblyStatus,
    StreamEvent,
    StreamEventType,
    map_batch_results,
)


CONTRACT = "research.v1"


def profile(
    profile_id: str,
    provider_name: str,
    model: str,
) -> CapabilityProfile:
    return CapabilityProfile(
        profile_id=profile_id,
        provider_name=provider_name,
        model=model,
        api_version="api.v1",
        profile_version="profile.v1",
        adapter_version="adapter.v1",
        supported_contracts=frozenset({CONTRACT}),
        requires_request_identity=True,
        verification_tier=VerificationTier.EXECUTED_LOCAL_RUNTIME,
    )


PROFILE_A = profile("profile-a", "provider_a", "model-a")
PROFILE_B = profile("profile-b", "provider_b", "model-b")


def request() -> ApplicationRequest:
    return ApplicationRequest(
        job_id="job-1",
        tenant_id="tenant-a",
        application_contract=CONTRACT,
        task_type="research",
        max_output_tokens=256,
        correlation_id="corr-1",
        prompt="SECRET-PROMPT-MUST-NOT-ENTER-DAY77-CALL-LOG",
    )


def run_a(exchange: ScriptedExchange):
    transport = ControlledFakeTransport(
        provider_label="provider_a",
        exchanges=(exchange,),
    )
    return ProviderAAdapter(transport, PROFILE_A).execute(request()), transport


def run_b(exchange: ScriptedExchange):
    transport = ControlledFakeTransport(
        provider_label="provider_b",
        exchanges=(exchange,),
    )
    return ProviderBAdapter(transport, PROFILE_B).execute(request()), transport


class UnknownANotSent(ProviderASDKError):
    execution_certainty = AdapterExecutionCertainty.DEFINITELY_NOT_SENT


class UnknownAExecutionUnknown(ProviderASDKError):
    execution_certainty = AdapterExecutionCertainty.EXECUTION_UNKNOWN


class UnknownBExecutionUnknown(ProviderBSDKError):
    execution_certainty = AdapterExecutionCertainty.EXECUTION_UNKNOWN


class Day77SharedAdapterContractTests(unittest.TestCase):
    def assert_parity(self, a_exchange, b_exchange, expected):
        a, a_transport = run_a(a_exchange)
        b, b_transport = run_b(b_exchange)
        self.assertIs(a.kind, expected)
        self.assertIs(b.kind, expected)
        self.assertEqual(a_transport.call_count, 1)
        self.assertEqual(b_transport.call_count, 1)

    def test_success_semantics_are_stable_across_adapters(self):
        self.assert_parity(
            ScriptedExchange(response={"id": "req-a", "finish_reason": "stop"}),
            ScriptedExchange(
                response={"responseId": "req-b", "completionState": "COMPLETE"}
            ),
            ProviderOutcomeKind.SUCCESS,
        )

    def test_truncation_semantics_are_stable_across_adapters(self):
        self.assert_parity(
            ScriptedExchange(response={"id": "req-a", "finish_reason": "length"}),
            ScriptedExchange(
                response={"responseId": "req-b", "completionState": "MAX_TOKENS"}
            ),
            ProviderOutcomeKind.TRUNCATION,
        )

    def test_refusal_semantics_are_stable_across_adapters(self):
        self.assert_parity(
            ScriptedExchange(error=ProviderARefused()),
            ScriptedExchange(error=ProviderBDeclined()),
            ProviderOutcomeKind.REFUSAL,
        )

    def test_rate_limit_semantics_are_stable_across_adapters(self):
        self.assert_parity(
            ScriptedExchange(error=ProviderARateLimited("2")),
            ScriptedExchange(error=ProviderBThrottled("2")),
            ProviderOutcomeKind.RATE_LIMITED,
        )

    def test_auth_semantics_are_stable_across_adapters(self):
        self.assert_parity(
            ScriptedExchange(error=ProviderAAuthFailed()),
            ScriptedExchange(error=ProviderBUnauthorized()),
            ProviderOutcomeKind.AUTHENTICATION_ERROR,
        )

    def test_timeout_unknown_semantics_are_stable_across_adapters(self):
        self.assert_parity(
            ScriptedExchange(error=ProviderATimedOut("req-a")),
            ScriptedExchange(error=ProviderBDeadlineExceeded("req-b")),
            ProviderOutcomeKind.TIMEOUT_UNKNOWN,
        )

    def test_definitely_not_sent_semantics_are_stable_across_adapters(self):
        self.assert_parity(
            ScriptedExchange(error=ProviderAConnectionError()),
            ScriptedExchange(error=ProviderBNetworkError()),
            ProviderOutcomeKind.TRANSPORT_ERROR,
        )

    def test_invalid_response_semantics_are_stable_across_adapters(self):
        self.assert_parity(
            ScriptedExchange(response={"id": "req-a", "finish_reason": "new"}),
            ScriptedExchange(
                response={"responseId": "req-b", "completionState": "NEW"}
            ),
            ProviderOutcomeKind.PROVIDER_RESPONSE_INVALID,
        )

    def test_unknown_sdk_execution_is_conservative(self):
        self.assertIs(
            run_a(ScriptedExchange(error=UnknownAExecutionUnknown("secret")))[0].kind,
            ProviderOutcomeKind.TIMEOUT_UNKNOWN,
        )
        self.assertIs(
            run_b(ScriptedExchange(error=UnknownBExecutionUnknown("secret")))[0].kind,
            ProviderOutcomeKind.TIMEOUT_UNKNOWN,
        )
        self.assertIs(
            run_a(ScriptedExchange(error=UnknownANotSent("secret")))[0].kind,
            ProviderOutcomeKind.TRANSPORT_ERROR,
        )

    def test_call_evidence_is_minimized_and_prompt_free(self):
        _, transport = run_a(
            ScriptedExchange(response={"id": "req-a", "finish_reason": "stop"})
        )
        evidence = transport.call_log.records()[0]
        self.assertEqual(evidence.correlation_id, "corr-1")
        self.assertEqual(evidence.model, "model-a")
        self.assertNotIn("SECRET-PROMPT", repr(evidence))


class Day77DeterministicFailureControlTests(unittest.TestCase):
    def test_fake_clock_advances_without_wall_clock_wait(self):
        clock = FakeClock(1_000)
        self.assertEqual(clock.advance_ms(31_000), 32_000)
        with self.assertRaises(ValueError):
            clock.advance_ms(-1)

    def test_controlled_gate_opens_timeout_window_and_call_stays_one(self):
        log = IndependentProviderCallLog()
        transport = ControlledFakeTransport(
            provider_label="provider_a",
            exchanges=(
                ScriptedExchange(
                    response={"id": "req-a", "finish_reason": "stop"}
                ),
            ),
            call_log=log,
            auto_release=False,
        )
        adapter = ProviderAAdapter(transport, PROFILE_A)
        result = {}

        def worker():
            result["outcome"] = adapter.execute(request())

        thread = threading.Thread(target=worker)
        thread.start()
        try:
            self.assertTrue(transport.request_received.wait(timeout=2))
            self.assertEqual(log.count, 1)
            self.assertTrue(thread.is_alive())
            clock = FakeClock()
            clock.advance_ms(31_000)
            unknown_cost = mark_unknown(AttemptCost("A1", "pricing.v1", 4, 5))
            self.assertIs(unknown_cost.status, CostStatus.PENDING_RECONCILIATION)
            self.assertEqual(log.count, 1)
        finally:
            transport.release_response.set()
            thread.join(timeout=2)
        self.assertIs(result["outcome"].kind, ProviderOutcomeKind.SUCCESS)
        self.assertEqual(log.count, 1)

    def test_independent_log_survives_simulated_worker_object_loss(self):
        log = IndependentProviderCallLog()
        transport = ControlledFakeTransport(
            provider_label="provider_a",
            exchanges=(
                ScriptedExchange(
                    response={"id": "req-a", "finish_reason": "stop"}
                ),
            ),
            call_log=log,
        )
        ProviderAAdapter(transport, PROFILE_A).execute(request())
        del transport
        self.assertEqual(log.count, 1)
        self.assertEqual(log.records()[0].provider_label, "provider_a")

    def test_unscripted_second_call_fails_loudly(self):
        transport = ControlledFakeTransport(
            provider_label="provider_a",
            exchanges=(
                ScriptedExchange(
                    response={"id": "req-a", "finish_reason": "stop"}
                ),
            ),
        )
        adapter = ProviderAAdapter(transport, PROFILE_A)
        adapter.execute(request())
        with self.assertRaises(AssertionError):
            adapter.execute(request())


def tool_candidate(*, tenant_id: str = "tenant-a") -> str:
    return json.dumps(
        {
            "kind": "tool_call",
            "tool_call_id": "call-1",
            "tool_name": "publish_report",
            "tool_version": "v1",
            "arguments": {"tenant_id": tenant_id, "report_id": "report-7"},
        }
    )


def batch_item(number: int) -> BatchItem:
    return BatchItem(
        item_id=f"item-{number}",
        tenant_id="tenant-a",
        job_id=f"job-{number}",
        attempt_id=f"A{number}",
        tool_call_id=f"call-{number}",
        idempotency_key=f"key-{number}",
        compatibility=BatchCompatibilityKey(
            "profile.v1", "model-a", "params.v1", "output.v1"
        ),
        enqueued_at=0,
        deadline=100,
    )


class Day77RuntimeRegressionTests(unittest.TestCase):
    def test_prompt_semantic_guarantee_weakening_is_breaking(self):
        old = PromptContractRevision(
            "research",
            "v1",
            (MessageTemplate(MessageRole.USER, "Research {topic}"),),
            (VariableSpec("topic"),),
            frozenset({CONTRACT}),
            frozenset({CITATIONS_REQUIRED}),
            "renderer.v1",
        )
        new = PromptContractRevision(
            "research",
            "v2",
            old.messages,
            old.variables,
            old.compatible_application_contracts,
            frozenset(),
            "renderer.v1",
        )
        reasons = backward_incompatibilities(old, new)
        self.assertTrue(any(CITATIONS_REQUIRED in reason for reason in reasons))

    def test_unauthorized_tool_candidate_has_zero_effect(self):
        registry = default_registry()
        reports = default_report_store()
        allowed = admit_tool_call(
            tool_candidate(),
            attempt_id="A1",
            job_id="job-1",
            registry=registry,
            auth=AuthContext("tenant-a", "user-1", "publisher"),
            reports=reports,
        )
        self.assertIs(allowed.status, AdmissionStatus.ALLOWED)
        executor = InMemoryToolExecutor()
        denied = admit_tool_call(
            tool_candidate(),
            attempt_id="A2",
            job_id="job-1",
            registry=registry,
            auth=AuthContext("tenant-a", "user-2", "viewer"),
            reports=reports,
        )
        self.assertIs(denied.status, AdmissionStatus.UNAUTHORIZED)
        self.assertIsNone(denied.admitted_call)
        self.assertEqual(executor.effect_count(allowed.admitted_call), 0)

    def test_partial_stream_never_emits_candidate(self):
        assembler = StreamAssembler(
            tenant_id="tenant-a",
            job_id="job-1",
            attempt_id="A1",
            stream_id="stream-1",
        )
        decision = assembler.accept(
            StreamEvent(
                "tenant-a",
                "job-1",
                "A1",
                "stream-1",
                1,
                StreamEventType.CONTENT_DELTA,
                tool_candidate()[:-1],
            )
        )
        self.assertIs(decision.status, StreamAssemblyStatus.BUFFERING)
        self.assertIsNone(decision.candidate)

    def test_stream_sequence_gap_fails_even_if_bytes_look_valid(self):
        assembler = StreamAssembler(
            tenant_id="tenant-a",
            job_id="job-1",
            attempt_id="A1",
            stream_id="stream-1",
        )
        assembler.accept(
            StreamEvent(
                "tenant-a",
                "job-1",
                "A1",
                "stream-1",
                1,
                StreamEventType.CONTENT_DELTA,
                tool_candidate(),
            )
        )
        decision = assembler.accept(
            StreamEvent(
                "tenant-a",
                "job-1",
                "A1",
                "stream-1",
                3,
                StreamEventType.COMPLETED,
            )
        )
        self.assertIs(decision.status, StreamAssemblyStatus.MALFORMED_STREAM)
        self.assertIsNone(decision.candidate)

    def test_cache_candidate_cannot_reuse_revoked_authorization(self):
        key = CacheKey(
            "tenant-a",
            "publish",
            "auth.v1",
            CONTRACT,
            "input:1",
            "prompt",
            "v1",
            "output.v1",
            "tool.v1",
            "profile.v1",
            "model-a",
            "cache.v1",
        )
        cache = InMemoryResponseCache()
        cache.put(
            key,
            CacheableCandidate(
                CompleteCandidate(
                    "tenant-a", "job-old", "A-old", "stream-old", tool_candidate()
                ),
                resource_version=7,
                created_at=0,
                expires_at=10,
            ),
        )
        result = cache.get(
            key,
            now=5,
            trusted_tenant_id="tenant-a",
            currently_authorized=False,
            current_resource_version=7,
        )
        self.assertIs(result.status, CacheLookupStatus.UNAUTHORIZED)
        self.assertIsNone(result.candidate)

    def test_missing_batch_result_makes_entire_envelope_unreliable(self):
        decision = map_batch_results(
            (batch_item(1), batch_item(2)),
            (
                ProviderBatchItemResult(
                    "item-1", BatchItemOutcome.GUARDED_SUCCEEDED
                ),
            ),
        )
        self.assertIs(decision.status, BatchEnvelopeStatus.ENVELOPE_FAILURE)
        self.assertTrue(
            all(
                result.recovery is BatchRecoveryAction.RECONCILE
                for result in decision.item_results
            )
        )

    def test_duplicate_batch_result_identity_reconciles_every_item(self):
        decision = map_batch_results(
            (batch_item(1), batch_item(2)),
            (
                ProviderBatchItemResult(
                    "item-1", BatchItemOutcome.GUARDED_SUCCEEDED
                ),
                ProviderBatchItemResult(
                    "item-1", BatchItemOutcome.GUARDED_SUCCEEDED
                ),
            ),
        )
        self.assertIs(decision.status, BatchEnvelopeStatus.ENVELOPE_FAILURE)
        self.assertEqual(
            {item.recovery for item in decision.item_results},
            {BatchRecoveryAction.RECONCILE},
        )

    def test_fallback_preserves_a1_and_creates_a2(self):
        source = AttemptExecutionContract.plan("A1", "job-1", PROFILE_A, CONTRACT)
        policy = FallbackPolicy(
            "fallback.v1", 3, 20, (FailureClass.RATE_LIMITED,)
        )
        decision, new_binding = plan_recovery(
            source=source,
            failure=FailureClass.RATE_LIMITED,
            certainty=RecoveryExecutionCertainty.DEFINITELY_NOT_ACCEPTED,
            policy=policy,
            attempt_count=1,
            remaining_deadline_ms=5_000,
            job_cost_and_reservations=4,
            target_estimated_cost=5,
            target=PROFILE_B,
            target_current_status=ProfileStatus.ACTIVE,
            new_attempt_id="A2",
        )
        self.assertIs(decision.action, Day76RecoveryAction.FALLBACK_NEW_ATTEMPT)
        self.assertEqual(source.profile_id, "profile-a")
        self.assertEqual(new_binding.attempt_id, "A2")
        self.assertEqual(new_binding.profile_id, "profile-b")

    def test_timeout_unknown_creates_no_a2_and_keeps_reservation(self):
        source = AttemptExecutionContract.plan("A1", "job-1", PROFILE_A, CONTRACT)
        policy = FallbackPolicy(
            "fallback.v1", 3, 20, (FailureClass.RATE_LIMITED,)
        )
        decision, new_binding = plan_recovery(
            source=source,
            failure=FailureClass.RATE_LIMITED,
            certainty=RecoveryExecutionCertainty.TIMEOUT_UNKNOWN,
            policy=policy,
            attempt_count=1,
            remaining_deadline_ms=5_000,
            job_cost_and_reservations=4,
            target_estimated_cost=5,
            target=PROFILE_B,
            target_current_status=ProfileStatus.ACTIVE,
            new_attempt_id="A2",
        )
        cost = mark_unknown(AttemptCost("A1", "pricing.v1", 4, 5))
        self.assertIs(decision.action, Day76RecoveryAction.RECONCILE)
        self.assertIsNone(new_binding)
        self.assertIs(cost.status, CostStatus.PENDING_RECONCILIATION)
        self.assertEqual(cost.released, 0)

    def test_retry_and_fallback_costs_aggregate_per_attempt(self):
        a1 = settle(
            AttemptCost("A1", "pricing.v1", 3, 5),
            pricing_revision="pricing.v1",
            actual=2,
        )
        a2 = settle(
            AttemptCost("A2", "pricing.v1", 5, 6),
            pricing_revision="pricing.v1",
            actual=4,
        )
        self.assertEqual(a1.actual + a2.actual, 6)

    def test_late_superseded_attempt_has_zero_completion_effect(self):
        registry = default_registry()
        admission = admit_tool_call(
            tool_candidate(),
            attempt_id="A1",
            job_id="job-1",
            registry=registry,
            auth=AuthContext("tenant-a", "user-1", "publisher"),
            reports=default_report_store(),
        )
        store = InMemoryDurableStore(
            (JobRecord("job-1", JobStatus.RUNNING, "A2", "call-2"),)
        )
        decision = store.guarded_complete(
            call=admission.admitted_call,
            outcome=OutcomeDecision(OutcomeStatus.VERIFIED, "verified"),
            operation_id="op-1",
        )
        self.assertIs(decision.status, CompletionStatus.NOOP_STALE)
        self.assertIs(store.get("job-1").status, JobStatus.RUNNING)

    def test_eligibility_still_precedes_preference(self):
        policy = RoutingPolicy("route", "v1", ("profile-a", "profile-b"), 8_000, 6)
        incompatible = CapabilityProfile(
            "profile-a",
            "provider_a",
            "model-a",
            "api.v1",
            "profile.v1",
            "adapter.v1",
            frozenset(),
            True,
            VerificationTier.EXECUTED_LOCAL_RUNTIME,
        )
        candidates = (
            Candidate(
                incompatible,
                ProfileStatus.ACTIVE,
                LatencyEvidence("profile-a", "PROVIDER_COMPLETE", 1, 900, 200),
                PricingEvidence("profile-a", "price.v1", 1, 900, 200),
            ),
            Candidate(
                PROFILE_B,
                ProfileStatus.ACTIVE,
                LatencyEvidence("profile-b", "PROVIDER_COMPLETE", 7_000, 900, 200),
                PricingEvidence("profile-b", "price.v1", 5, 900, 200),
            ),
        )
        decision, binding = route(
            job_id="job-1",
            attempt_id="A1",
            application_contract=CONTRACT,
            policy=policy,
            candidates=candidates,
            now_ms=1_000,
        )
        self.assertEqual(decision.selected_profile_id, "profile-b")
        self.assertEqual(binding.profile_id, "profile-b")


class Day77GoldenAndIncidentTests(unittest.TestCase):
    def test_independent_golden_matches_observed_semantics(self):
        golden = BehaviorGolden(
            "timeout-after-receipt",
            "contract.v1",
            "policy.v1",
            "TIMEOUT_UNKNOWN",
            "RECONCILE",
            "PENDING_RECONCILIATION",
            1,
            0,
            False,
            "PENDING_RECONCILIATION",
        )
        actual = BehaviorObservation(
            "TIMEOUT_UNKNOWN",
            "RECONCILE",
            "PENDING_RECONCILIATION",
            1,
            0,
            False,
            "PENDING_RECONCILIATION",
        )
        self.assertEqual(golden_mismatches(golden, actual), ())

    def test_golden_reports_side_effect_regression(self):
        golden = BehaviorGolden(
            "unauthorized-tool",
            "contract.v1",
            "policy.v1",
            "SUCCESS",
            "REJECT",
            "RUNNING",
            1,
            0,
            False,
            "SETTLED",
        )
        actual = BehaviorObservation(
            "SUCCESS", "REJECT", "RUNNING", 1, 1, False, "SETTLED"
        )
        self.assertEqual(golden_mismatches(golden, actual), ("tool_effect_count",))

    def test_bad_v6_unknown_sdk_error_cannot_authorize_fallback(self):
        outcome, _ = run_a(
            ScriptedExchange(error=UnknownAExecutionUnknown("v6-new-error"))
        )
        self.assertIs(outcome.kind, ProviderOutcomeKind.TIMEOUT_UNKNOWN)
        source = AttemptExecutionContract.plan("A1", "job-1", PROFILE_A, CONTRACT)
        decision, new_binding = plan_recovery(
            source=source,
            failure=FailureClass.TRANSPORT_BEFORE_DISPATCH,
            certainty=RecoveryExecutionCertainty.TIMEOUT_UNKNOWN,
            policy=FallbackPolicy(
                "fallback.v6", 3, 20, (FailureClass.TRANSPORT_BEFORE_DISPATCH,)
            ),
            attempt_count=1,
            remaining_deadline_ms=5_000,
            job_cost_and_reservations=5,
            target_estimated_cost=5,
            target=PROFILE_B,
            target_current_status=ProfileStatus.ACTIVE,
            new_attempt_id="A2",
        )
        self.assertIs(decision.action, Day76RecoveryAction.RECONCILE)
        self.assertIsNone(new_binding)

    def test_rollback_and_green_tests_are_not_incident_closure(self):
        incomplete = IncidentRecoveryEvidence(
            stable_policy_active=True,
            bad_policy_stopped=True,
            bad_profile_quarantined=True,
            attempts_classified=False,
            unknowns_reconciling_or_resolved=False,
            costs_settled_or_reconciling=False,
            repairs_verified=False,
            compensations_verified=False,
            regression_tests_passed=True,
        )
        self.assertFalse(may_close_incident(incomplete))

    def test_incident_may_close_only_with_all_evidence(self):
        complete = IncidentRecoveryEvidence(
            stable_policy_active=True,
            bad_policy_stopped=True,
            bad_profile_quarantined=True,
            attempts_classified=True,
            unknowns_reconciling_or_resolved=True,
            costs_settled_or_reconciling=True,
            repairs_verified=True,
            compensations_verified=True,
            regression_tests_passed=True,
        )
        self.assertTrue(may_close_incident(complete))


if __name__ == "__main__":
    unittest.main()
