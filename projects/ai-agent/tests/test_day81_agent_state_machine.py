import unittest

from agent_loop import AgentStepInput, ControlDecision, decide_control
from agent_state_machine import (
    AgentState,
    AgentTransitionInput,
    AuthoritativeAgentRecord,
    BudgetSnapshot,
    ContextBudget,
    InMemoryAgentStateStore,
    ProgressSnapshot,
    RecoveryAction,
    TerminationReason,
    TransitionAction,
    TransitionApplyStatus,
    decide_transition,
    no_progress_threshold_reached,
)
from tool_governance import InvocationGovernanceStatus


def budgets(
    *, steps_used=1, held_tokens=0, settled_tokens=0,
    held_cost=0, settled_cost=0
):
    return BudgetSnapshot(
        step_limit=4,
        steps_used=steps_used,
        token_limit=10_000,
        settled_tokens=settled_tokens,
        held_token_reservations=held_tokens,
        cost_limit=100,
        settled_cost=settled_cost,
        held_cost_reservations=held_cost,
    )


def context(*, input_tokens=2_000, output=1_000, margin=100, permitted=8_000):
    return ContextBudget(
        input_tokens=input_tokens,
        reserved_output_tokens=output,
        safety_margin=margin,
        permitted_context_budget=permitted,
        provider_context_limit=128_000,
    )


def day79_result(
    *, observations=("O1", "O2"), required=3,
    pending=None, waiting=None
):
    return decide_control(
        AgentStepInput(
            tenant_id="tenant-a",
            job_id="J1",
            current_step_id="S1",
            runtime_attempt_id="A1",
            goal_required_observations=required,
            verified_observation_ids=observations,
            pending_reconciliation_identity=pending,
            waiting_for=waiting,
            model_proposal="model advice only",
        )
    )


def transition_input(**changes):
    values = dict(
        tenant_id="tenant-a",
        job_id="J1",
        step_id="S1",
        attempt_id="A1",
        state=AgentState.RUNNING,
        fence_token=8,
        day79_result=day79_result(),
        goal_verified=False,
        pending_reconciliation_identity=None,
        current_authorization=True,
        day80_governance=(
            InvocationGovernanceStatus.ALLOWED_TO_DAY74_ADMISSION
        ),
        hard_loop_detected=False,
        budget=budgets(),
        context_budget=context(),
        requested_token_reservation=2_000,
        requested_cost_reservation=20,
    )
    values.update(changes)
    return AgentTransitionInput(**values)


class DecisionPriorityTests(unittest.TestCase):
    def test_model_complete_advice_cannot_override_missing_evidence(self):
        item = transition_input()
        decision = decide_transition(item)
        self.assertIs(item.day79_result.decision, ControlDecision.CONTINUE)
        self.assertIs(decision.action, TransitionAction.CONTINUE)

    def test_goal_verified_completes_even_when_step_budget_is_zero(self):
        decision = decide_transition(
            transition_input(goal_verified=True, budget=budgets(steps_used=4))
        )
        self.assertIs(decision.action, TransitionAction.COMPLETE)
        self.assertIs(
            decision.termination_reason, TerminationReason.GOAL_SATISFIED
        )

    def test_goal_incomplete_with_zero_steps_terminates(self):
        decision = decide_transition(
            transition_input(budget=budgets(steps_used=4))
        )
        self.assertIs(
            decision.termination_reason,
            TerminationReason.STEP_BUDGET_EXHAUSTED,
        )
        self.assertIsNone(decision.next_step)

    def test_unknown_execution_reconciles_before_exhausted_budgets(self):
        result = day79_result(pending="provider-request-A1")
        decision = decide_transition(
            transition_input(
                day79_result=result,
                pending_reconciliation_identity="provider-request-A1",
                budget=budgets(steps_used=4, held_cost=100),
            )
        )
        self.assertIs(decision.action, TransitionAction.RECONCILE)
        self.assertIs(
            decision.recovery_action,
            RecoveryAction.RECONCILE_ORIGINAL_IDENTITY,
        )
        self.assertIn("reservation_must_remain_held", decision.evidence)

    def test_known_wait_is_not_reconciliation(self):
        decision = decide_transition(
            transition_input(day79_result=day79_result(waiting="approval"))
        )
        self.assertIs(decision.action, TransitionAction.WAIT)
        self.assertIs(
            decision.recovery_action, RecoveryAction.WAIT_FOR_PREREQUISITE
        )

    def test_hard_loop_blocks_despite_remaining_budgets(self):
        decision = decide_transition(
            transition_input(hard_loop_detected=True)
        )
        self.assertIs(
            decision.termination_reason,
            TerminationReason.NO_PROGRESS_LOOP_DETECTED,
        )

    def test_terminal_state_is_noop_and_preserves_history(self):
        decision = decide_transition(
            transition_input(state=AgentState.COMPLETED)
        )
        self.assertIs(decision.action, TransitionAction.NOOP)
        self.assertIs(decision.proposed_next_state, AgentState.COMPLETED)


class GovernanceAndBudgetTests(unittest.TestCase):
    def test_current_permission_revocation_terminates(self):
        decision = decide_transition(
            transition_input(
                day80_governance=(
                    InvocationGovernanceStatus.CURRENT_PERMISSION_REVOKED
                )
            )
        )
        self.assertIs(
            decision.termination_reason,
            TerminationReason.AUTHORIZATION_REVOKED,
        )

    def test_disabled_old_binding_waits_for_replan_not_substitution(self):
        decision = decide_transition(
            transition_input(
                day80_governance=(
                    InvocationGovernanceStatus.CURRENT_REGISTRY_BLOCKED
                )
            )
        )
        self.assertIs(decision.action, TransitionAction.WAIT)
        self.assertIs(
            decision.recovery_action,
            RecoveryAction.REPLAN_WITH_CURRENT_CAPABILITIES,
        )
        self.assertIn("old_binding_not_rewritten", decision.evidence)

    def test_context_budget_can_be_stricter_than_provider_limit(self):
        decision = decide_transition(
            transition_input(
                context_budget=context(
                    input_tokens=25_000,
                    output=6_000,
                    margin=2_000,
                    permitted=32_000,
                )
            )
        )
        self.assertIs(decision.action, TransitionAction.WAIT)
        self.assertEqual(decision.status, "CONTEXT_BUDGET_EXCEEDED")

    def test_token_budget_is_not_context_capacity(self):
        decision = decide_transition(
            transition_input(
                budget=budgets(settled_tokens=5_000),
                requested_token_reservation=8_000,
            )
        )
        self.assertIs(
            decision.termination_reason,
            TerminationReason.TOKEN_BUDGET_EXHAUSTED,
        )

    def test_unknown_held_cost_is_not_released_or_called_exhausted(self):
        result = day79_result(pending="provider-request-A1")
        decision = decide_transition(
            transition_input(
                day79_result=result,
                pending_reconciliation_identity="provider-request-A1",
                budget=budgets(held_cost=100),
            )
        )
        self.assertIs(decision.action, TransitionAction.RECONCILE)
        self.assertIsNone(decision.termination_reason)

    def test_cost_budget_exhaustion_blocks_new_attempt(self):
        decision = decide_transition(
            transition_input(
                budget=budgets(settled_cost=90),
                requested_cost_reservation=20,
            )
        )
        self.assertIs(
            decision.termination_reason,
            TerminationReason.COST_BUDGET_EXHAUSTED,
        )


class LoopDetectionTests(unittest.TestCase):
    @staticmethod
    def progress(observations, action):
        return ProgressSnapshot(
            state=AgentState.RUNNING,
            remaining_goal_conditions=("need-third-observation",),
            verified_observation_ids=observations,
            action_fingerprint=action,
        )

    def test_different_actions_can_be_no_progress_loop(self):
        history = (
            self.progress(("O1", "O2"), "tool-x"),
            self.progress(("O1", "O2"), "tool-y"),
            self.progress(("O1", "O2"), "tool-z"),
        )
        self.assertTrue(no_progress_threshold_reached(history, 3))

    def test_same_action_with_new_evidence_is_progress(self):
        history = (
            self.progress(("O1",), "tool-x"),
            self.progress(("O1", "O2"), "tool-x"),
            self.progress(("O1", "O2", "O3"), "tool-x"),
        )
        self.assertFalse(no_progress_threshold_reached(history, 3))


class ConditionalApplyTests(unittest.TestCase):
    @staticmethod
    def store(*, state=AgentState.RUNNING, fence=8, budget=None):
        return InMemoryAgentStateStore(
            AuthoritativeAgentRecord(
                tenant_id="tenant-a",
                job_id="J1",
                current_step_id="S1",
                state=state,
                fence_token=fence,
                budget=budget or budgets(),
            )
        )

    def test_applied_continue_consumes_step_and_holds_reservations(self):
        decision = decide_transition(transition_input())
        store = self.store()
        self.assertIs(store.apply(decision), TransitionApplyStatus.APPLIED)
        self.assertEqual(store.record.budget.steps_used, 2)
        self.assertEqual(store.record.budget.held_token_reservations, 2_000)
        self.assertEqual(store.record.budget.held_cost_reservations, 20)
        self.assertEqual(store.record.fence_token, 9)
        self.assertEqual(store.record.current_step_id, decision.next_step.step_id)

    def test_duplicate_transition_does_not_consume_twice(self):
        decision = decide_transition(transition_input())
        store = self.store()
        self.assertIs(store.apply(decision), TransitionApplyStatus.APPLIED)
        self.assertIs(
            store.apply(decision), TransitionApplyStatus.DUPLICATE_REPLAY
        )
        self.assertEqual(store.record.budget.steps_used, 2)

    def test_stale_fence_rejects_candidate(self):
        decision = decide_transition(transition_input())
        store = self.store(fence=9)
        self.assertIs(store.apply(decision), TransitionApplyStatus.NOOP_STALE)

    def test_terminal_job_rejects_old_continue(self):
        decision = decide_transition(transition_input())
        store = self.store(state=AgentState.COMPLETED, fence=9)
        self.assertIs(
            store.apply(decision), TransitionApplyStatus.NOOP_TERMINAL
        )

    def test_apply_rechecks_budget_and_rejects_reservation_race(self):
        decision = decide_transition(transition_input())
        changed = budgets(settled_tokens=9_000, settled_cost=90)
        store = self.store(budget=changed)
        self.assertIs(
            store.apply(decision), TransitionApplyStatus.RESERVATION_CONFLICT
        )
        self.assertEqual(store.record.budget.steps_used, 1)


if __name__ == "__main__":
    unittest.main()
