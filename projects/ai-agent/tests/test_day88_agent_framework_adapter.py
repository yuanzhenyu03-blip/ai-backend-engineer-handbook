"""Day88 deterministic tests for both application-owned framework adapters."""
from dataclasses import replace
from typing import TYPE_CHECKING
import unittest

from agent_framework_adapter import (
    AmbiguousToolResult,
    Committer,
    CurrentFacts,
    FrameworkAdapter,
    FrameworkToolCall,
    Outcome,
    ProposalEnvelope,
    ToolProposal,
    canonical_intent_hash,
)
from langgraph_framework_adapter import LangGraphAdapter
from pydantic_ai_framework_adapter import PydanticAIAdapter


OPERATION_ID = "op-88-1"
VALID_PROPOSAL = ToolProposal("refund", 100, "USD")


class FakeTool:
    def __init__(self, ambiguous: bool = False) -> None:
        self.ambiguous = ambiguous
        self.calls: list[str] = []
        self.effects: dict[str, dict[str, object]] = {}

    def invoke(
        self,
        *,
        operation_id: str,
        proposal: ToolProposal,
    ) -> dict[str, object]:
        self.calls.append(operation_id)
        result = {"refund_id": "refund-88", "amount_minor": proposal.amount_minor}
        self.effects.setdefault(operation_id, result)
        if self.ambiguous:
            raise AmbiguousToolResult("response lost after effect")
        return result


class FakeAdapter:
    adapter_id = "fake"

    def to_proposal(self, output: FrameworkToolCall) -> ToolProposal:
        del output
        return VALID_PROPOSAL


if TYPE_CHECKING:
    class _TestCaseTypeBase(unittest.TestCase):
        pass
else:
    class _TestCaseTypeBase:
        pass


class AdapterContractMixin(_TestCaseTypeBase):
    adapter_class: type[FrameworkAdapter] = PydanticAIAdapter
    expected_adapter_id = ""

    def make_output(
        self,
        *,
        tool_name: object = "refund",
        amount_minor: object = 100,
        currency: object = "USD",
        extra_field: bool = False,
    ) -> FrameworkToolCall:
        raise NotImplementedError

    def setUp(self) -> None:
        self.adapter: FrameworkAdapter = self.adapter_class()
        self.output = self.make_output()
        self.envelope = ProposalEnvelope(
            OPERATION_ID, "attempt-1", "approval-88", 8, 3, 2_000,
        )
        self.facts = CurrentFacts(
            OPERATION_ID,
            True,
            "approval-88",
            canonical_intent_hash(VALID_PROPOSAL),
            8,
            3,
            1_000,
        )

    def process(self, *, output=None, envelope=None, facts=None, tool=None):
        selected_tool = tool or FakeTool()
        committer = Committer(selected_tool)
        audit = committer.process(
            self.adapter,
            output or self.output,
            envelope or self.envelope,
            facts or self.facts,
        )
        return audit, selected_tool, committer

    def assert_denied(self, expected: str, **kwargs) -> None:
        audit, tool, _ = self.process(**kwargs)
        self.assertEqual(audit.outcome, Outcome.DENIED)
        self.assertIn(expected, audit.reasons)
        self.assertEqual(audit.validators_executed, Committer.VALIDATORS)
        self.assertEqual(tool.calls, [])
        self.assertFalse(audit.durable_transition)

    def test_selected_adapter_version_is_explicit(self) -> None:
        self.assertEqual(self.adapter.adapter_id, self.expected_adapter_id)

    def test_valid_proposal_executes_once(self) -> None:
        audit, tool, _ = self.process()
        self.assertEqual(audit.outcome, Outcome.COMPLETED)
        self.assertEqual(tool.calls, [OPERATION_ID])

    def test_production_client_is_not_in_adapter_state(self) -> None:
        self.assertNotIn("tool", vars(self.adapter))

    def test_extra_control_field_is_invalid(self) -> None:
        audit, tool, _ = self.process(output=self.make_output(extra_field=True))
        self.assertEqual(audit.outcome, Outcome.INVALID)
        self.assertEqual(audit.reasons, ("output_validation_failure",))
        self.assertEqual(tool.calls, [])

    def test_float_amount_is_invalid(self) -> None:
        audit, tool, _ = self.process(output=self.make_output(amount_minor=100.0))
        self.assertEqual(audit.outcome, Outcome.INVALID)
        self.assertEqual(tool.calls, [])

    def test_operation_id_mismatch_fails_closed(self) -> None:
        self.assert_denied(
            "operation_id_mismatch",
            envelope=replace(self.envelope, operation_id="model-created"),
        )

    def test_revoked_grant_fails_closed(self) -> None:
        self.assert_denied("grant_revoked", facts=replace(self.facts, grant_active=False))

    def test_stale_fence_fails_closed(self) -> None:
        self.assert_denied("stale_fence", envelope=replace(self.envelope, fence_token=7))

    def test_stale_policy_fails_closed(self) -> None:
        self.assert_denied(
            "stale_policy", envelope=replace(self.envelope, policy_version=2)
        )

    def test_approval_identity_mismatch_fails_closed(self) -> None:
        self.assert_denied(
            "approval_id_mismatch",
            envelope=replace(self.envelope, approval_id="approval-other"),
        )

    def test_approval_argument_binding_mismatch_fails_closed(self) -> None:
        self.assert_denied(
            "approval_argument_mismatch",
            output=self.make_output(amount_minor=1_000),
        )

    def test_unregistered_tool_fails_closed(self) -> None:
        self.assert_denied("unregistered_tool", output=self.make_output(tool_name="wire"))

    def test_expired_deadline_fails_closed(self) -> None:
        self.assert_denied("deadline_expired", facts=replace(self.facts, now_ms=3_000))

    def test_cancelled_operation_fails_closed(self) -> None:
        self.assert_denied("cancelled", facts=replace(self.facts, cancelled=True))

    def test_all_validators_are_instrumented_for_compound_failure(self) -> None:
        audit, tool, _ = self.process(
            output=self.make_output(amount_minor=1_000),
            envelope=replace(self.envelope, fence_token=7),
            facts=replace(self.facts, grant_active=False),
        )
        self.assertEqual(audit.outcome, Outcome.DENIED)
        self.assertTrue(
            {"grant_revoked", "stale_fence", "approval_argument_mismatch"}.issubset(
                audit.reasons
            )
        )
        self.assertEqual(audit.validators_executed, Committer.VALIDATORS)
        self.assertEqual(tool.calls, [])

    def test_duplicate_replays_saved_result_without_second_call(self) -> None:
        tool = FakeTool()
        committer = Committer(tool)
        first = committer.process(self.adapter, self.output, self.envelope, self.facts)
        replay = committer.process(self.adapter, self.output, self.envelope, self.facts)
        self.assertEqual(first.outcome, Outcome.COMPLETED)
        self.assertEqual(replay.outcome, Outcome.REPLAY)
        self.assertEqual(tool.calls, [OPERATION_ID])
        self.assertIsNotNone(replay.replayed_result)

    def test_duplicate_with_different_intent_is_conflict(self) -> None:
        tool = FakeTool()
        committer = Committer(tool)
        committer.process(self.adapter, self.output, self.envelope, self.facts)
        conflict = committer.process(
            self.adapter,
            self.make_output(amount_minor=1_000),
            self.envelope,
            self.facts,
        )
        self.assertEqual(conflict.outcome, Outcome.CONFLICT)
        self.assertEqual(tool.calls, [OPERATION_ID])

    def test_ambiguous_tool_result_requires_reconciliation(self) -> None:
        tool = FakeTool(ambiguous=True)
        audit, _, committer = self.process(tool=tool)
        self.assertEqual(audit.outcome, Outcome.PENDING_RECONCILIATION)
        self.assertEqual(
            committer.durable_state[OPERATION_ID], Outcome.PENDING_RECONCILIATION
        )
        self.assertEqual(len(tool.effects), 1)

    def test_stale_worker_observation_cannot_commit(self) -> None:
        committer = Committer(FakeTool())
        committer.durable_state[OPERATION_ID] = Outcome.PENDING_RECONCILIATION
        committer.submit_observation(
            operation_id=OPERATION_ID,
            observer_fence=7,
            result="EXECUTED",
            source="authoritative-tool-query",
        )
        self.assertFalse(committer.reconcile_success(facts=self.facts, submitter_fence=7))
        self.assertEqual(
            committer.durable_state[OPERATION_ID], Outcome.PENDING_RECONCILIATION
        )
        self.assertEqual(committer.evidence_inbox[0]["observer_fence"], 7)

    def test_current_worker_can_commit_reconciled_fact(self) -> None:
        committer = Committer(FakeTool())
        committer.durable_state[OPERATION_ID] = Outcome.PENDING_RECONCILIATION
        self.assertTrue(committer.reconcile_success(facts=self.facts, submitter_fence=8))
        self.assertEqual(committer.durable_state[OPERATION_ID], Outcome.COMPLETED)


class PydanticAIAdapterContractTests(AdapterContractMixin, unittest.TestCase):
    adapter_class = PydanticAIAdapter
    expected_adapter_id = "pydantic-ai-slim@2.41.0"

    def make_output(
        self,
        *,
        tool_name: object = "refund",
        amount_minor: object = 100,
        currency: object = "USD",
        extra_field: bool = False,
    ) -> FrameworkToolCall:
        arguments = {
            "tool_name": tool_name,
            "amount_minor": amount_minor,
            "currency": currency,
        }
        if extra_field:
            arguments["skip_authorization"] = True
        return FrameworkToolCall("proposal_handler", arguments)


class LangGraphAdapterContractTests(AdapterContractMixin, unittest.TestCase):
    adapter_class = LangGraphAdapter
    expected_adapter_id = "langgraph@1.2.11"

    def make_output(
        self,
        *,
        tool_name: object = "refund",
        amount_minor: object = 100,
        currency: object = "USD",
        extra_field: bool = False,
    ) -> FrameworkToolCall:
        arguments = {
            "tool_name": tool_name,
            "amount_minor": amount_minor,
            "currency": currency,
        }
        if extra_field:
            arguments["skip_authorization"] = True
        return FrameworkToolCall(
            "tools",
            {
                "name": "proposal_handler",
                "args": arguments,
                "id": "langgraph-call-1",
                "type": "tool_call",
            },
        )

    def test_langgraph_tool_call_envelope_is_strict(self) -> None:
        valid = dict(self.output.arguments)
        invalid_envelopes = (
            {**valid, "skip_authorization": True},
            {**valid, "id": 7},
            {**valid, "type": "function"},
            {**valid, "args": [("tool_name", "refund")]},
        )
        for arguments in invalid_envelopes:
            with self.subTest(arguments=arguments):
                audit, tool, _ = self.process(
                    output=FrameworkToolCall("tools", arguments)
                )
                self.assertEqual(audit.outcome, Outcome.INVALID)
                self.assertEqual(audit.reasons, ("output_validation_failure",))
                self.assertEqual(tool.calls, [])


class CrossAdapterReplaceabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.envelope = ProposalEnvelope(
            OPERATION_ID, "attempt-1", "approval-88", 8, 3, 2_000,
        )
        self.facts = CurrentFacts(
            OPERATION_ID,
            True,
            "approval-88",
            canonical_intent_hash(VALID_PROPOSAL),
            8,
            3,
            1_000,
        )

    def test_fake_adapter_proves_core_replaceability(self) -> None:
        tool = FakeTool()
        audit = Committer(tool).process(
            FakeAdapter(), FrameworkToolCall("unused", {}), self.envelope, self.facts
        )
        self.assertEqual(audit.outcome, Outcome.COMPLETED)
        self.assertEqual(tool.calls, [OPERATION_ID])

    def test_real_adapters_have_equivalent_application_outcome(self) -> None:
        cases: tuple[tuple[FrameworkAdapter, FrameworkToolCall], ...] = (
            (
                PydanticAIAdapter(),
                FrameworkToolCall(
                    "proposal_handler",
                    {"tool_name": "refund", "amount_minor": 100, "currency": "USD"},
                ),
            ),
            (
                LangGraphAdapter(),
                FrameworkToolCall(
                    "tools",
                    {
                        "name": "proposal_handler",
                        "args": {
                            "tool_name": "refund",
                            "amount_minor": 100,
                            "currency": "USD",
                        },
                        "id": "langgraph-call-1",
                        "type": "tool_call",
                    },
                ),
            ),
        )
        observed = []
        for adapter, output in cases:
            tool = FakeTool()
            committer = Committer(tool)
            audit = committer.process(adapter, output, self.envelope, self.facts)
            observed.append((audit.outcome, tool.calls, committer.durable_state))
        self.assertEqual(observed[0], observed[1])
        self.assertEqual(observed[0][0], Outcome.COMPLETED)


if __name__ == "__main__":
    unittest.main()
