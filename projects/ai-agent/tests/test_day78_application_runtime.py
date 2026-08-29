import json
import threading
import unittest
from dataclasses import FrozenInstanceError, replace

from application_runtime import (
    CompensationStatus,
    CostSettlementStatus,
    EvidenceLevel,
    InMemoryCostSettlementStore,
    InMemoryRuntimeAttemptStore,
    NoEligibleRouteError,
    PreparedAttempt,
    ProviderCandidateBindingError,
    ProviderExecutionEnvelope,
    ProviderPayloadBindingError,
    RecoveryAction,
    ResolvedExecutionRequirements,
    RuntimeAttemptStatus,
    RuntimeResult,
    RuntimeStage,
    RuntimeStatus,
    admit_provider_candidate,
    build_bound_application_request,
    candidate_sha256,
    execute_admitted_tool,
    prepare_runtime_attempt,
    verify_outcome_and_complete,
)
from output_tool_contracts import (
    AdmissionStatus,
    AuthContext,
    ExecutionStatus,
    InMemoryToolExecutor,
    OutcomeStatus,
    default_registry,
    default_report_store,
)
from prompt_contracts import (
    CITATIONS_REQUIRED,
    MessageRole,
    MessageTemplate,
    PromptContractRegistry,
    PromptContractRevision,
    VariableSpec,
)
from provider_contract import (
    CapabilityProfile,
    ProfileStatus,
    ProviderOutcome,
    ProviderOutcomeKind,
    VerificationTier,
)
from routing_policy import (
    Candidate,
    LatencyEvidence,
    PricingEvidence,
    RoutingPolicy,
)


class Day78Fixture(unittest.TestCase):
    def candidate(
        self,
        profile_id: str = "P2",
        contracts: frozenset[str] = frozenset({"research.strict-tools.v1"}),
        units: int = 8,
    ) -> Candidate:
        profile = CapabilityProfile(
            profile_id=profile_id,
            provider_name="fixture-provider",
            model=f"model-{profile_id}",
            api_version="api-1",
            profile_version="profile-1",
            adapter_version="adapter-1",
            supported_contracts=contracts,
            requires_request_identity=True,
            verification_tier=VerificationTier.EXECUTED_LOCAL_RUNTIME,
        )
        return Candidate(
            profile,
            ProfileStatus.ACTIVE,
            LatencyEvidence(profile_id, "PROVIDER_COMPLETE", 100, 90, 100),
            PricingEvidence(profile_id, "price-1", units, 90, 100),
        )

    def prepared(self, candidates: tuple[Candidate, ...] | None = None) -> PreparedAttempt:
        prompts = PromptContractRegistry()
        prompts.publish(
            PromptContractRevision(
                prompt_contract_id="research.prompt",
                revision="v3",
                messages=(MessageTemplate(MessageRole.USER, "Research {topic}"),),
                variables=(VariableSpec("topic"),),
                compatible_application_contracts=frozenset(
                    {"research.strict-tools.v1"}
                ),
                semantic_guarantees=frozenset({CITATIONS_REQUIRED}),
                renderer_version="renderer-1",
            ),
            make_default=True,
        )
        return prepare_runtime_attempt(
            job_id="J1",
            attempt_id="A1",
            requirements=ResolvedExecutionRequirements(
                "research.strict-tools.v1",
                "research.prompt",
                "output-v2",
                "tool-v2",
                "params",
                "p1",
            ),
            variables={"topic": "runtime safety"},
            prompt_registry=prompts,
            routing_policy=RoutingPolicy("route", "r7", ("P2",), 1_000, 10),
            candidates=candidates or (self.candidate(),),
            now_ms=100,
        )

    @staticmethod
    def candidate_json() -> str:
        return json.dumps(
            {
                "kind": "tool_call",
                "tool_call_id": "tc-1",
                "tool_name": "publish_report",
                "tool_version": "v1",
                "arguments": {
                    "tenant_id": "tenant-a",
                    "report_id": "report-7",
                },
            }
        )

    def admitted_fixture(self):
        prepared = self.prepared()
        store = InMemoryRuntimeAttemptStore()
        store.persist_prepared(prepared)
        store.claim_dispatch(
            attempt_id="A1",
            expected_prompt_hash=prepared.prompt_binding.rendered_message_hash,
            worker_id="W1",
        )
        raw = self.candidate_json()
        envelope = ProviderExecutionEnvelope(
            "J1",
            "A1",
            "C1",
            ProviderOutcome(ProviderOutcomeKind.SUCCESS),
            candidate_sha256(raw),
            raw,
        )
        registry = default_registry()
        decision = admit_provider_candidate(
            envelope=envelope,
            prepared=prepared,
            expected_correlation_id="C1",
            registry=registry,
            auth=AuthContext("tenant-a", "user-1", "publisher"),
            reports=default_report_store(),
        )
        return prepared, store, registry, decision


class RuntimeResultTests(Day78Fixture):
    def test_01_pending_reconciliation_preserves_identity(self) -> None:
        result = RuntimeResult(
            "J1",
            "A3",
            RuntimeStage.PROVIDER_DISPATCH,
            RuntimeStatus.PENDING_RECONCILIATION,
            RecoveryAction.RECONCILE_ORIGINAL_IDENTITY,
            EvidenceLevel.EXECUTED_LOCAL_RUNTIME,
            "provider_execution_unknown",
            {"reservation": "HELD"},
        )
        self.assertEqual(result.attempt_id, "A3")

    def test_02_pending_cannot_request_reject(self) -> None:
        with self.assertRaises(ValueError):
            RuntimeResult(
                "J1", "A1", RuntimeStage.PROVIDER_DISPATCH,
                RuntimeStatus.PENDING_RECONCILIATION, RecoveryAction.REJECT,
                EvidenceLevel.EXECUTED_LOCAL_RUNTIME, "unknown",
            )

    def test_03_result_is_immutable_and_evidence_read_only(self) -> None:
        result = RuntimeResult(
            "J1", "A1", RuntimeStage.COMPLETION, RuntimeStatus.COMPLETED,
            RecoveryAction.NONE, EvidenceLevel.EXECUTED_LOCAL_RUNTIME,
            "complete", {"revision": "v3"},
        )
        with self.assertRaises(FrozenInstanceError):
            result.reason = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            result.safe_evidence["revision"] = "v4"  # type: ignore[index]

    def test_04_success_envelope_requires_candidate(self) -> None:
        with self.assertRaises(ValueError):
            ProviderExecutionEnvelope(
                "J1", "A1", "C1", ProviderOutcome(ProviderOutcomeKind.SUCCESS)
            )

    def test_05_non_success_envelope_rejects_candidate(self) -> None:
        with self.assertRaises(ValueError):
            ProviderExecutionEnvelope(
                "J1", "A1", "C1",
                ProviderOutcome(ProviderOutcomeKind.TIMEOUT_UNKNOWN),
                "hash", "candidate",
            )

    def test_06_raw_candidate_is_not_in_repr(self) -> None:
        raw = "sensitive-candidate"
        envelope = ProviderExecutionEnvelope(
            "J1", "A1", "C1", ProviderOutcome(ProviderOutcomeKind.SUCCESS),
            candidate_sha256(raw), raw,
        )
        self.assertNotIn(raw, repr(envelope))


class RuntimePreparationTests(Day78Fixture):
    def test_07_incompatible_candidate_excluded_before_preference(self) -> None:
        cheap = self.candidate("CHEAP", frozenset({"other"}), 1)
        prepared = self.prepared((cheap, self.candidate()))
        self.assertEqual(prepared.routing_decision.selected_profile_id, "P2")

    def test_08_no_eligible_route_fails_before_binding(self) -> None:
        with self.assertRaises(NoEligibleRouteError):
            self.prepared((self.candidate("P2", frozenset({"other"})),))

    def test_09_bridge_preserves_role_order_and_hash(self) -> None:
        prepared = self.prepared()
        request = build_bound_application_request(
            prepared=prepared,
            tenant_id="tenant-a",
            max_output_tokens=200,
            correlation_id="C1",
        )
        self.assertEqual(json.loads(request.prompt)[0][0], "user")
        self.assertEqual(request.correlation_id, "C1")

    def test_10_bridge_rejects_hash_mismatch(self) -> None:
        prepared = self.prepared()
        broken = replace(
            prepared,
            prompt_binding=replace(
                prepared.prompt_binding, rendered_message_hash="sha256:wrong"
            ),
        )
        with self.assertRaises(ProviderPayloadBindingError):
            build_bound_application_request(
                prepared=broken,
                tenant_id="tenant-a",
                max_output_tokens=200,
                correlation_id="C1",
            )

    def test_11_one_dispatch_winner(self) -> None:
        prepared = self.prepared()
        store = InMemoryRuntimeAttemptStore()
        store.persist_prepared(prepared)
        winners = []
        lock = threading.Lock()

        def claim(worker: str) -> None:
            result = store.claim_dispatch(
                attempt_id="A1",
                expected_prompt_hash=prepared.prompt_binding.rendered_message_hash,
                worker_id=worker,
            )
            with lock:
                winners.append(result is not None)

        threads = [threading.Thread(target=claim, args=(f"W{i}",)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(winners.count(True), 1)

    def test_12_unknown_dispatch_never_reopens(self) -> None:
        prepared = self.prepared()
        store = InMemoryRuntimeAttemptStore()
        store.persist_prepared(prepared)
        store.claim_dispatch(
            attempt_id="A1",
            expected_prompt_hash=prepared.prompt_binding.rendered_message_hash,
            worker_id="W1",
        )
        store.mark_provider_execution_unknown(attempt_id="A1", worker_id="W1")
        self.assertIsNone(
            store.claim_dispatch(
                attempt_id="A1",
                expected_prompt_hash=prepared.prompt_binding.rendered_message_hash,
                worker_id="W2",
            )
        )

    def test_13_candidate_identity_mismatch_fails_before_admission(self) -> None:
        prepared = self.prepared()
        raw = self.candidate_json()
        envelope = ProviderExecutionEnvelope(
            "J1", "OTHER", "C1", ProviderOutcome(ProviderOutcomeKind.SUCCESS),
            candidate_sha256(raw), raw,
        )
        with self.assertRaises(ProviderCandidateBindingError):
            admit_provider_candidate(
                envelope=envelope,
                prepared=prepared,
                expected_correlation_id="C1",
                registry=default_registry(),
                auth=AuthContext("tenant-a", "u", "publisher"),
                reports=default_report_store(),
            )

    def test_14_candidate_calls_real_day74_admission(self) -> None:
        _, _, _, decision = self.admitted_fixture()
        self.assertIs(decision.status, AdmissionStatus.ALLOWED)


class ToolOutcomeTests(Day78Fixture):
    def test_15_disabled_after_admission_has_zero_effect(self) -> None:
        _, store, registry, decision = self.admitted_fixture()
        assert decision.admitted_call is not None
        executor = InMemoryToolExecutor()
        with self.assertRaises(ValueError):
            execute_admitted_tool(
                decision=decision, store=store, worker_id="W1",
                expected_fence_token=0, registry=registry, executor=executor,
            )
        self.assertEqual(executor.effect_count(decision.admitted_call), 0)

        # Recreate the fixture because stale authority was rejected after Admission.
        _, store, registry, decision = self.admitted_fixture()
        assert decision.admitted_call is not None
        registry.disable("publish_report", "v1")
        current = store.get("A1")
        assert current is not None and current.fence_token is not None
        result = execute_admitted_tool(
            decision=decision, store=store, worker_id="W1",
            expected_fence_token=current.fence_token,
            registry=registry, executor=executor,
        )
        self.assertIs(result.status, ExecutionStatus.REJECTED_DISABLED)
        self.assertEqual(executor.effect_count(decision.admitted_call), 0)

    def execution_fixture(self):
        prepared, store, registry, decision = self.admitted_fixture()
        assert decision.admitted_call is not None
        current = store.get("A1")
        assert current is not None and current.fence_token is not None
        execution = execute_admitted_tool(
            decision=decision, store=store, worker_id="W1",
            expected_fence_token=current.fence_token,
            registry=registry, executor=InMemoryToolExecutor(),
        )
        return prepared, store, decision.admitted_call, execution

    def test_16_active_tool_executes(self) -> None:
        _, store, _, execution = self.execution_fixture()
        self.assertIs(execution.status, ExecutionStatus.EXECUTED)
        assert store.get("A1") is not None
        self.assertIs(store.get("A1").status, RuntimeAttemptStatus.TOOL_EXECUTED)  # type: ignore[union-attr]

    def test_17_verified_outcome_completes(self) -> None:
        _, store, call, execution = self.execution_fixture()
        raw = json.dumps(
            {"operation_id": execution.operation_id, "published": True,
             "report": {"report_id": "report-7", "version": 7}, "warnings": []}
        )
        outcome, result = verify_outcome_and_complete(
            raw_tool_outcome=raw, call=call, execution=execution,
            store=store, worker_id="W1",
        )
        self.assertIs(outcome.status, OutcomeStatus.VERIFIED)
        self.assertIs(result.status, RuntimeStatus.COMPLETED)

    def test_18_identity_mismatch_reconciles(self) -> None:
        _, store, call, execution = self.execution_fixture()
        raw = json.dumps(
            {"operation_id": execution.operation_id, "published": True,
             "report": {"report_id": "report-7", "version": 6}, "warnings": []}
        )
        outcome, result = verify_outcome_and_complete(
            raw_tool_outcome=raw, call=call, execution=execution,
            store=store, worker_id="W1",
        )
        self.assertIs(outcome.status, OutcomeStatus.IDENTITY_MISMATCH)
        self.assertIs(result.status, RuntimeStatus.PENDING_RECONCILIATION)

    def test_19_schema_invalid_outcome_rejects(self) -> None:
        _, store, call, execution = self.execution_fixture()
        outcome, result = verify_outcome_and_complete(
            raw_tool_outcome='{"published":true}', call=call,
            execution=execution, store=store, worker_id="W1",
        )
        self.assertIs(outcome.status, OutcomeStatus.SCHEMA_INVALID)
        self.assertIs(result.status, RuntimeStatus.REJECTED)

    def test_20_compensation_preserves_source_and_new_identity(self) -> None:
        _, store, call, execution = self.execution_fixture()
        store.cancel_after_external_effect("A1")
        compensation = store.create_compensation(
            compensation_id="COMP-1",
            source_attempt_id="A1",
            idempotency_key="compensation:COMP-1",
        )
        self.assertEqual(compensation.source_operation_id, execution.operation_id)
        self.assertNotEqual(compensation.idempotency_key, call.idempotency_key)

    def test_21_unknown_compensation_keeps_identity(self) -> None:
        _, store, _, _ = self.execution_fixture()
        store.cancel_after_external_effect("A1")
        store.create_compensation(
            compensation_id="COMP-1", source_attempt_id="A1",
            idempotency_key="compensation:COMP-1",
        )
        store.claim_compensation("COMP-1", "CW1")
        pending = store.mark_compensation_unknown("COMP-1", "CW1")
        self.assertIs(pending.status, CompensationStatus.PENDING_RECONCILIATION)
        self.assertIsNone(store.claim_compensation("COMP-1", "CW2"))

    def test_22_cost_settlement_is_idempotent_and_releases_unused(self) -> None:
        ledger = InMemoryCostSettlementStore()
        ledger.request(
            settlement_id="S1", job_id="J1", attempt_id="A1",
            reservation_id="R1", reserved_units=10,
        )
        pending = ledger.mark_unknown("S1")
        first = ledger.settle("S1", 6)
        replay = ledger.settle("S1", 6)
        self.assertIs(pending.status, CostSettlementStatus.PENDING_RECONCILIATION)
        self.assertEqual(first.released_units, 4)
        self.assertEqual(first, replay)


if __name__ == "__main__":
    unittest.main()
