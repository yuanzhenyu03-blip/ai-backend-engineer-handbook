import json
import unittest

from agent_loop import (
    AgentJobState,
    AgentStepInput,
    ControlApplyStatus,
    ControlDecision,
    InMemoryControlStore,
    decide_control,
    orchestrate_next_step,
    prepare_next_step_with_day78,
)
from application_runtime import (
    EvidenceLevel,
    RecoveryAction,
    ResolvedExecutionRequirements,
    RuntimeResult,
    RuntimeStage,
    RuntimeStatus,
)
from prompt_contracts import (
    CITATIONS_REQUIRED,
    MessageRole,
    MessageTemplate,
    PromptContractRegistry,
    PromptContractRevision,
    VariableSpec,
)
from provider_contract import CapabilityProfile, ProfileStatus, VerificationTier
from routing_policy import (
    Candidate,
    LatencyEvidence,
    PricingEvidence,
    RoutingPolicy,
)


def runtime_result(status: RuntimeStatus) -> RuntimeResult:
    recovery_action = RecoveryAction.NONE
    if status is RuntimeStatus.PENDING_RECONCILIATION:
        recovery_action = RecoveryAction.RECONCILE_ORIGINAL_IDENTITY
    elif status in {
        RuntimeStatus.REJECTED,
        RuntimeStatus.BLOCKED_PRE_DISPATCH,
    }:
        recovery_action = RecoveryAction.REJECT

    return RuntimeResult(
        "J1",
        "A1",
        RuntimeStage.COMPLETION,
        status,
        recovery_action,
        EvidenceLevel.EXECUTED_LOCAL_RUNTIME,
        "classified runtime outcome",
    )


def step_input(**changes: object) -> AgentStepInput:
    values: dict[str, object] = {
        "tenant_id": "tenant-a",
        "job_id": "J1",
        "current_step_id": "S1",
        "runtime_attempt_id": "A1",
        "goal_required_observations": 3,
        "verified_observation_ids": ("O1", "O2"),
        "runtime_result": runtime_result(RuntimeStatus.COMPLETED),
        "model_proposal": "CONTINUE",
    }
    values.update(changes)
    return AgentStepInput(**values)


class RecordingRuntime:
    def __init__(self) -> None:
        self.requests = []

    def execute_step(self, request):
        self.requests.append(request)
        return RuntimeResult(
            request.job_id,
            request.runtime_attempt_id,
            RuntimeStage.COMPLETION,
            RuntimeStatus.COMPLETED,
            RecoveryAction.NONE,
            EvidenceLevel.EXECUTED_LOCAL_RUNTIME,
            "recording runtime completed",
        )


class ControllerDecisionTests(unittest.TestCase):
    def test_table_driven_control_decisions(self) -> None:
        cases = (
            ("terminal job", step_input(job_is_terminal=True), ControlDecision.COMPLETE),
            (
                "explicit reconciliation identity",
                step_input(pending_reconciliation_identity="A5"),
                ControlDecision.RECONCILE,
            ),
            (
                "unknown runtime outcome",
                step_input(
                    runtime_result=runtime_result(
                        RuntimeStatus.PENDING_RECONCILIATION
                    )
                ),
                ControlDecision.RECONCILE,
            ),
            (
                "runtime rejection",
                step_input(runtime_result=runtime_result(RuntimeStatus.REJECTED)),
                ControlDecision.FAIL,
            ),
            (
                "goal satisfied despite model proposal",
                step_input(goal_required_observations=2),
                ControlDecision.COMPLETE,
            ),
            (
                "known wait condition",
                step_input(waiting_for="human approval"),
                ControlDecision.WAIT,
            ),
            (
                "goal incomplete despite model proposal",
                step_input(model_proposal="COMPLETE"),
                ControlDecision.CONTINUE,
            ),
        )

        for label, current_input, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(decide_control(current_input).decision, expected)

    def test_runtime_result_identity_must_match_current_attempt(self) -> None:
        mismatched = RuntimeResult(
            "J1",
            "A9",
            RuntimeStage.COMPLETION,
            RuntimeStatus.COMPLETED,
            RecoveryAction.NONE,
            EvidenceLevel.EXECUTED_LOCAL_RUNTIME,
            "complete",
        )

        with self.assertRaisesRegex(ValueError, "RuntimeResult identity"):
            step_input(runtime_result=mismatched)

        foreign_result = decide_control(step_input(tenant_id="tenant-b"))
        store = InMemoryControlStore(AgentJobState("tenant-a", "J1", "S1"))
        with self.assertRaisesRegex(ValueError, "store identity"):
            store.apply_continue(foreign_result)

    def test_same_input_produces_same_control_and_next_step_identity(self) -> None:
        first = decide_control(step_input())
        second = decide_control(step_input())

        self.assertEqual(first, second)
        self.assertIsNotNone(first.next_step)
        self.assertEqual(first.next_step.step_id, second.next_step.step_id)
        self.assertEqual(
            first.next_step.runtime_attempt_id,
            second.next_step.runtime_attempt_id,
        )


class OrchestrationTests(unittest.TestCase):
    @staticmethod
    def store(*, current_step_id: str = "S1", terminal: bool = False):
        return InMemoryControlStore(
            AgentJobState("tenant-a", "J1", current_step_id, terminal)
        )

    def test_only_new_continue_invokes_runtime_once(self) -> None:
        store = self.store()
        runtime = RecordingRuntime()
        result = decide_control(step_input())

        first_status, first_runtime = orchestrate_next_step(
            result=result, store=store, runtime=runtime
        )
        replay_status, replay_runtime = orchestrate_next_step(
            result=result, store=store, runtime=runtime
        )

        self.assertEqual(first_status, ControlApplyStatus.CREATED)
        self.assertIsNotNone(first_runtime)
        self.assertEqual(replay_status, ControlApplyStatus.DUPLICATE_REPLAY)
        self.assertIsNone(replay_runtime)
        self.assertEqual(len(runtime.requests), 1)

    def test_terminal_continue_has_zero_runtime_calls(self) -> None:
        runtime = RecordingRuntime()
        status, result = orchestrate_next_step(
            result=decide_control(step_input()),
            store=self.store(terminal=True),
            runtime=runtime,
        )

        self.assertEqual(status, ControlApplyStatus.NOOP_TERMINAL)
        self.assertIsNone(result)
        self.assertEqual(runtime.requests, [])

    def test_stale_continue_has_zero_runtime_calls(self) -> None:
        runtime = RecordingRuntime()
        status, result = orchestrate_next_step(
            result=decide_control(step_input()),
            store=self.store(current_step_id="S2"),
            runtime=runtime,
        )

        self.assertEqual(status, ControlApplyStatus.NOOP_STALE)
        self.assertIsNone(result)
        self.assertEqual(runtime.requests, [])

    def test_non_continue_decision_has_zero_runtime_calls(self) -> None:
        runtime = RecordingRuntime()
        status, result = orchestrate_next_step(
            result=decide_control(step_input(goal_required_observations=2)),
            store=self.store(),
            runtime=runtime,
        )

        self.assertEqual(status, ControlApplyStatus.NOT_APPLICABLE)
        self.assertIsNone(result)
        self.assertEqual(runtime.requests, [])

    def test_next_step_composes_with_real_day78_prepare_boundary(self) -> None:
        next_step = decide_control(step_input()).next_step
        self.assertIsNotNone(next_step)
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
        profile = CapabilityProfile(
            profile_id="P2",
            provider_name="fixture-provider",
            model="model-P2",
            api_version="api-1",
            profile_version="profile-1",
            adapter_version="adapter-1",
            supported_contracts=frozenset({"research.strict-tools.v1"}),
            requires_request_identity=True,
            verification_tier=VerificationTier.EXECUTED_LOCAL_RUNTIME,
        )
        candidate = Candidate(
            profile,
            ProfileStatus.ACTIVE,
            LatencyEvidence("P2", "PROVIDER_COMPLETE", 100, 90, 100),
            PricingEvidence("P2", "price-1", 8, 90, 100),
        )

        prepared = prepare_next_step_with_day78(
            next_step=next_step,
            requirements=ResolvedExecutionRequirements(
                "research.strict-tools.v1",
                "research.prompt",
                "output-v2",
                "tool-v2",
                "params",
                "p1",
            ),
            variables={"topic": "agent loop control flow"},
            prompt_registry=prompts,
            routing_policy=RoutingPolicy("route", "r7", ("P2",), 1_000, 10),
            candidates=(candidate,),
            now_ms=100,
            max_output_tokens=256,
            correlation_id="C-next-step",
        )

        self.assertEqual(
            prepared.prepared.provider_binding.attempt_id,
            next_step.runtime_attempt_id,
        )
        self.assertEqual(prepared.request.job_id, "J1")
        self.assertEqual(prepared.request.tenant_id, "tenant-a")
        prompt = json.loads(prepared.request.prompt)
        self.assertEqual(prompt[0][0], "user")


if __name__ == "__main__":
    unittest.main()
