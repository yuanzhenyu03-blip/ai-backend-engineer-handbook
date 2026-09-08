"""Day88 deterministic tests for the application-owned framework boundary."""
from dataclasses import replace
import unittest

from agent_framework_adapter import (
    AmbiguousToolResult,
    Committer,
    CurrentFacts,
    FrameworkToolCall,
    Outcome,
    ProposalEnvelope,
    ToolProposal,
    canonical_intent_hash,
)
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


class Day88AgentFrameworkAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = PydanticAIAdapter()
        self.output = FrameworkToolCall(
            "proposal_handler",
            {"tool_name": "refund", "amount_minor": 100, "currency": "USD"},
        )
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
        self.assertEqual(self.adapter.adapter_id, "pydantic-ai-slim@2.41.0")

    def test_valid_proposal_executes_once(self) -> None:
        audit, tool, _ = self.process()
        self.assertEqual(audit.outcome, Outcome.COMPLETED)
        self.assertEqual(tool.calls, [OPERATION_ID])

    def test_production_client_is_not_in_adapter_state(self) -> None:
        self.assertNotIn("tool", vars(self.adapter))

    def test_extra_control_field_is_invalid(self) -> None:
        arguments = dict(self.output.arguments)
        arguments["skip_authorization"] = True
        output = replace(self.output, arguments=arguments)
        audit, tool, _ = self.process(output=output)
        self.assertEqual(audit.outcome, Outcome.INVALID)
        self.assertEqual(audit.reasons, ("output_validation_failure",))
        self.assertEqual(tool.calls, [])

    def test_float_amount_is_invalid(self) -> None:
        output = replace(
            self.output,
            arguments={"tool_name": "refund", "amount_minor": 100.0, "currency": "USD"},
        )
        audit, tool, _ = self.process(output=output)
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
        output = replace(
            self.output,
            arguments={"tool_name": "refund", "amount_minor": 1_000, "currency": "USD"},
        )
        self.assert_denied("approval_argument_mismatch", output=output)

    def test_unregistered_tool_fails_closed(self) -> None:
        output = replace(
            self.output,
            arguments={"tool_name": "wire", "amount_minor": 100, "currency": "USD"},
        )
        self.assert_denied("unregistered_tool", output=output)

    def test_expired_deadline_fails_closed(self) -> None:
        self.assert_denied("deadline_expired", facts=replace(self.facts, now_ms=3_000))

    def test_cancelled_operation_fails_closed(self) -> None:
        self.assert_denied("cancelled", facts=replace(self.facts, cancelled=True))

    def test_all_validators_are_instrumented_for_compound_failure(self) -> None:
        output = replace(
            self.output,
            arguments={"tool_name": "refund", "amount_minor": 1_000, "currency": "USD"},
        )
        audit, tool, _ = self.process(
            output=output,
            envelope=replace(self.envelope, fence_token=7),
            facts=replace(self.facts, grant_active=False),
        )
        self.assertEqual(audit.outcome, Outcome.DENIED)
        self.assertTrue({"grant_revoked", "stale_fence", "approval_argument_mismatch"}.issubset(audit.reasons))
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
        changed = replace(
            self.output,
            arguments={"tool_name": "refund", "amount_minor": 1_000, "currency": "USD"},
        )
        conflict = committer.process(self.adapter, changed, self.envelope, self.facts)
        self.assertEqual(conflict.outcome, Outcome.CONFLICT)
        self.assertEqual(tool.calls, [OPERATION_ID])

    def test_ambiguous_tool_result_requires_reconciliation(self) -> None:
        tool = FakeTool(ambiguous=True)
        audit, _, committer = self.process(tool=tool)
        self.assertEqual(audit.outcome, Outcome.PENDING_RECONCILIATION)
        self.assertEqual(committer.durable_state[OPERATION_ID], Outcome.PENDING_RECONCILIATION)
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
        self.assertFalse(
            committer.reconcile_success(facts=self.facts, submitter_fence=7)
        )
        self.assertEqual(committer.durable_state[OPERATION_ID], Outcome.PENDING_RECONCILIATION)
        self.assertEqual(committer.evidence_inbox[0]["observer_fence"], 7)

    def test_current_worker_can_commit_reconciled_fact(self) -> None:
        committer = Committer(FakeTool())
        committer.durable_state[OPERATION_ID] = Outcome.PENDING_RECONCILIATION
        self.assertTrue(
            committer.reconcile_success(facts=self.facts, submitter_fence=8)
        )
        self.assertEqual(committer.durable_state[OPERATION_ID], Outcome.COMPLETED)

    def test_fake_adapter_proves_core_replaceability(self) -> None:
        tool = FakeTool()
        audit = Committer(tool).process(
            FakeAdapter(), self.output, self.envelope, self.facts
        )
        self.assertEqual(audit.outcome, Outcome.COMPLETED)
        self.assertEqual(tool.calls, [OPERATION_ID])


if __name__ == "__main__":
    unittest.main()
