"""Day83 deterministic local tests; not infrastructure/integration proof."""
from dataclasses import replace
import concurrent.futures
import unittest

from agent_state_machine import AgentState
from durable_agent_jobs import ExternalCertainty, ReservationAction, ReservationStatus
from human_control import ApprovalStatus, Operation, Risk
from human_control_scenarios import build_scenario
from tool_governance import InvocationGovernanceStatus


class HumanControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.s = build_scenario()

    def candidate(self, now: int = 30):
        return self.s.store.plan(self.s.command(), self.s.facts, now)

    def dispatch(self, event: str, now: int = 30) -> bool:
        s = self.s
        return s.store.dispatch_once(event, s.worker,
                                    s.store.snapshot.job.fence_token,
                                    s.facts, now, s.local_effect)

    def unknown(self) -> None:
        self.s.facts = replace(self.s.facts, certainty=ExternalCertainty.OUTCOME_UNKNOWN)
        self.s.store.snapshot = replace(self.s.store.snapshot, dispatch_started=True)

    def test_model_claim_is_not_approval(self) -> None:
        c = self.candidate()
        self.assertEqual(c.status, "APPROVAL_PENDING")
        self.assertFalse(c.execution_allowed)
        self.assertEqual(self.s.effect_calls, 0)

    def test_valid_decision_is_not_itself_dispatch(self) -> None:
        self.s.approve()
        self.assertEqual(self.s.store.snapshot.approval, ApprovalStatus.APPROVED)
        self.assertEqual(self.s.store.snapshot.job.outbox_intents, ())
        self.assertEqual(self.s.effect_calls, 0)

    def test_pending_then_approval_then_new_gate_command(self) -> None:
        self.s.apply(self.s.command())
        self.s.approve()
        event = self.s.publish_intent()
        self.assertTrue(self.dispatch(event))
        self.assertEqual(self.s.effect_calls, 1)

    def test_valid_approval_composes_existing_runtime_once(self) -> None:
        self.s.approve()
        event = self.s.publish_intent()
        self.assertTrue(self.dispatch(event))
        self.assertFalse(self.dispatch(event))
        self.assertEqual(self.s.effect_calls, 1)
        self.assertEqual(self.s.verified_result[0].status.value, "VERIFIED")

    def test_low_risk_current_policy_not_required(self) -> None:
        s = self.s.store.snapshot
        action = replace(s.action, risk=Risk.LOW, action_type="read",
                         tool_name="read_public_document")
        self.s.store.snapshot = replace(s, action=action,
                                       request=replace(s.request, binding=action))
        self.s.facts = replace(self.s.facts, approval_required=False,
                              executor=replace(self.s.facts.executor,
                                               permissions=("read",)))
        self.assertEqual(self.candidate().approval_status, ApprovalStatus.NOT_REQUIRED)
        self.assertTrue(self.candidate().execution_allowed)

    def test_high_risk_cannot_silently_be_not_required(self) -> None:
        self.s.facts = replace(self.s.facts, approval_required=False)
        self.assertEqual(self.candidate().status, "RISK_POLICY_CONFLICT")

    def test_rejected_decision_is_not_retried(self) -> None:
        self.s.apply(self.s.approval_command(choice=ApprovalStatus.REJECTED))
        self.assertEqual(self.candidate().status, "APPROVAL_REJECTED")
        self.assertFalse(self.candidate().execution_allowed)

    def test_expiry_at_boundary(self) -> None:
        self.s.approve()
        self.assertEqual(self.candidate(800).status, "APPROVAL_EXPIRED")

    def test_artifact_change_requires_new_request(self) -> None:
        self.s.approve()
        state = self.s.store.snapshot
        self.s.store.snapshot = replace(state, action=replace(state.action,
                                                              artifact_version="8"))
        self.assertEqual(self.candidate().status, "APPROVAL_BINDING_MISMATCH")
        self.assertEqual(self.s.store.snapshot.request.binding.artifact_version, "7")

    def test_argument_change_requires_new_request(self) -> None:
        self.s.approve()
        state = self.s.store.snapshot
        self.s.store.snapshot = replace(state, action=replace(state.action,
                                                arguments_fingerprint="changed"))
        self.assertEqual(self.candidate().status, "APPROVAL_BINDING_MISMATCH")

    def test_wrong_tenant_callback_cannot_approve(self) -> None:
        self.s.facts = replace(self.s.facts,
                              approver=replace(self.s.facts.approver, tenant_id="tenant-b"))
        c, status = self.s.apply(self.s.approval_command())
        self.assertEqual(c.status, "CONTROL_NOT_AUTHORIZED")
        self.assertEqual(status, "AUDIT_ONLY")
        self.assertEqual(self.s.store.snapshot.approval, ApprovalStatus.PENDING)

    def test_requester_cannot_approve_when_separation_required(self) -> None:
        self.s.facts = replace(self.s.facts,
                              approver=replace(self.s.facts.approver, actor_id="requester"))
        c, _ = self.s.apply(self.s.approval_command())
        self.assertEqual(c.status, "APPROVER_POLICY_REJECTED")

    def test_admin_role_alone_does_not_grant_approval(self) -> None:
        self.s.facts = replace(self.s.facts, approver=replace(
            self.s.facts.approver, role="Admin", permissions=("control",)))
        c, _ = self.s.apply(self.s.approval_command())
        self.assertEqual(c.status, "APPROVER_NOT_AUTHORIZED")

    def test_unauthenticated_callback_is_not_identity(self) -> None:
        self.s.facts = replace(self.s.facts, approver=replace(
            self.s.facts.approver, authenticated=False))
        self.assertEqual(self.s.apply(self.s.approval_command())[0].status,
                         "CONTROL_NOT_AUTHORIZED")

    def test_duplicate_callback_does_not_advance_business_state(self) -> None:
        self.s.approve()
        before = self.s.store.snapshot.job
        c, status = self.s.apply(self.s.approval_command("redelivery"))
        after = self.s.store.snapshot.job
        self.assertEqual(c.status, "DUPLICATE_DECISION")
        self.assertEqual(status, "AUDIT_ONLY")
        self.assertEqual(after.state_version, before.state_version)
        self.assertEqual(after.outbox_intents, before.outbox_intents)
        self.assertEqual(after.reservations, before.reservations)

    def test_conflicting_identity_preserves_both_decisions(self) -> None:
        self.s.approve()
        c, _ = self.s.apply(self.s.approval_command(
            "conflict", choice=ApprovalStatus.REJECTED,
            binding_fingerprint="F2"))
        self.assertEqual(c.status, "ESCALATE_DECISION_IDENTITY_CONFLICT")
        snapshot = self.s.store.snapshot
        self.assertEqual(len(snapshot.decisions), 1)
        self.assertEqual(len(snapshot.decision_evidence), 2)
        self.assertEqual(snapshot.approval, ApprovalStatus.CONFLICT)
        self.assertEqual(snapshot.escalations[0].owner_id, "operations")

    def test_different_decision_identity_cannot_overwrite_first(self) -> None:
        self.s.approve()
        c, _ = self.s.apply(self.s.approval_command(
            "new-callback", decision_id="decision-2", choice=ApprovalStatus.REJECTED))
        self.assertEqual(c.status, "ESCALATE_CONFLICTING_HUMAN_DECISION")

    def test_revoked_executor_authorization_blocks_and_releases_unused(self) -> None:
        self.s.approve()
        self.s.facts = replace(self.s.facts, executor=replace(
            self.s.facts.executor, permissions=()))
        c, _ = self.s.apply(self.s.command())
        self.assertEqual(c.status, "AUTHORIZATION_REVOKED")
        self.assertEqual(self.s.store.snapshot.job.reservations[0].status,
                         ReservationStatus.RELEASED)

    def test_tool_disabled_after_approval_blocks(self) -> None:
        self.s.approve()
        self.s.facts = replace(self.s.facts,
            governance=InvocationGovernanceStatus.CURRENT_REGISTRY_BLOCKED)
        self.assertEqual(self.candidate().status, "TOOL_GOVERNANCE_BLOCKED")

    def test_approval_does_not_replace_business_validation(self) -> None:
        self.s.approve()
        self.s.facts = replace(self.s.facts, business_valid=False)
        self.assertEqual(self.candidate().status, "BUSINESS_VALIDATION_FAILED")

    def test_approval_does_not_replace_tool_admission(self) -> None:
        self.s.approve()
        self.s.facts = replace(self.s.facts, admission_allowed=False)
        self.assertEqual(self.candidate().status, "TOOL_ADMISSION_BLOCKED")

    def test_approval_does_not_replace_budget_guard(self) -> None:
        self.s.approve()
        self.s.facts = replace(self.s.facts, budget_allowed=False)
        self.assertEqual(self.candidate().status, "BUDGET_BLOCKED")

    def test_unknown_status_and_non_boolean_guard_fail_closed(self) -> None:
        self.s.store.snapshot = replace(self.s.store.snapshot, approval="SURPRISE")
        self.assertEqual(self.candidate().status, "INVALID_FACTS")
        self.s = build_scenario()
        self.s.facts = replace(self.s.facts, approval_required="false")
        self.assertEqual(self.candidate().status, "INVALID_FACTS")

    def test_forged_candidate_cannot_be_applied(self) -> None:
        candidate = replace(self.candidate(), execution_allowed=True,
                            status="EXECUTION_CANDIDATE", outbox_action="PUBLISH")
        self.assertEqual(self.s.store.apply(candidate, self.s.facts, 30),
                         "CURRENT_FACTS_CHANGED")
        self.assertEqual(self.s.store.snapshot.job.outbox_intents, ())

    def test_authorization_changed_between_plan_and_apply(self) -> None:
        self.s.approve()
        c = self.candidate()
        facts = replace(self.s.facts, executor=replace(self.s.facts.executor, permissions=()))
        self.assertEqual(self.s.store.apply(c, facts, 30), "CURRENT_FACTS_CHANGED")

    def test_expiry_changed_between_plan_and_apply(self) -> None:
        self.s.approve()
        self.assertEqual(self.s.store.apply(self.candidate(), self.s.facts, 800),
                         "CURRENT_FACTS_CHANGED")

    def test_two_candidates_only_one_conditional_commit(self) -> None:
        self.s.approve()
        a = self.candidate()
        b = self.s.store.plan(self.s.command(command_id="gate-2"), self.s.facts, 30)
        self.assertEqual(self.s.store.apply(a, self.s.facts, 30), "APPLIED")
        self.assertEqual(self.s.store.apply(b, self.s.facts, 30), "STALE_CANDIDATE")
        self.assertEqual(len(self.s.store.snapshot.job.outbox_intents), 1)

    def test_precommit_failure_writes_nothing(self) -> None:
        self.s.approve()
        before = self.s.store.snapshot
        with self.assertRaisesRegex(RuntimeError, "INJECTED_BEFORE_COMMIT"):
            self.s.store.apply(self.candidate(), self.s.facts, 30,
                               fail_before_commit=True)
        self.assertEqual(self.s.store.snapshot, before)

    def test_committed_unpublished_intent_retains_identity(self) -> None:
        self.s.approve()
        event = self.s.publish_intent()
        self.assertIsNone(self.s.store.snapshot.job.outbox_intents[0].published_at_epoch_ms)
        self.assertTrue(self.dispatch(event))
        self.assertFalse(self.dispatch(event))
        self.assertEqual(self.s.effect_calls, 1)

    def test_atomic_thread_claim_allows_one_local_call(self) -> None:
        self.s.approve()
        event = self.s.publish_intent()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = tuple(pool.map(lambda _: self.dispatch(event), range(2)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.s.effect_calls, 1)

    def test_dispatch_rechecks_expiry_after_outbox_commit(self) -> None:
        self.s.approve()
        event = self.s.publish_intent()
        self.assertFalse(self.dispatch(event, 800))
        self.assertEqual(self.s.effect_calls, 0)

    def test_dispatch_rechecks_authorization_after_outbox_commit(self) -> None:
        self.s.approve()
        event = self.s.publish_intent()
        self.s.facts = replace(self.s.facts, executor=replace(
            self.s.facts.executor, permissions=()))
        self.assertFalse(self.dispatch(event))

    def test_pre_dispatch_interrupt_releases_unused_and_fences(self) -> None:
        self.s.approve()
        event = self.s.publish_intent()
        fence = self.s.store.snapshot.job.fence_token
        c, _ = self.s.apply(self.s.command(Operation.INTERRUPT, "interrupt-1"))
        self.assertEqual(c.status, "INTERRUPTED_PRE_DISPATCH")
        self.assertEqual(self.s.store.snapshot.job.fence_token, fence + 1)
        self.assertEqual(self.s.store.snapshot.job.reservations[0].released_units, 6000)
        self.assertFalse(self.dispatch(event))
        self.assertEqual(self.s.effect_calls, 0)

    def test_post_dispatch_interrupt_keeps_original_identity_held(self) -> None:
        self.unknown()
        before = self.s.store.snapshot.action
        c, _ = self.s.apply(self.s.command(Operation.INTERRUPT, "interrupt-1"))
        self.assertEqual(c.status, "INTERRUPTED_POST_DISPATCH")
        self.assertEqual(c.reservation_action, ReservationAction.KEEP_HELD)
        self.assertEqual(self.s.store.snapshot.action, before)
        self.assertEqual(self.s.store.snapshot.job.state, AgentState.PENDING_RECONCILIATION)

    def test_observed_cancellation_is_not_external_absence(self) -> None:
        self.unknown()
        self.s.apply(self.s.command(Operation.INTERRUPT, "interrupt-1"))
        c, _ = self.s.apply(self.s.command(Operation.OBSERVE_CANCEL, "observed-1"))
        self.assertEqual(c.status, "CANCELLATION_OBSERVED")
        self.assertEqual(self.s.store.snapshot.cancellation_observed_by, ("W1",))
        self.assertEqual(self.s.store.snapshot.job.reservations[0].status,
                         ReservationStatus.HELD)

    def test_stale_late_result_preserved_without_business_transition(self) -> None:
        self.unknown()
        self.s.apply(self.s.command(Operation.INTERRUPT, "interrupt-1"))
        job = self.s.store.snapshot.job
        c, status = self.s.apply(self.s.command(
            Operation.LATE_RESULT, "late-1", source_fence=8,
            source_attempt_id=self.s.store.snapshot.action.attempt_id,
            source_operation_id=self.s.store.snapshot.action.operation_id,
            evidence_id="safe-result-reference"))
        self.assertEqual(c.status, "STALE_RESULT_EVIDENCE")
        self.assertEqual(status, "AUDIT_ONLY")
        self.assertEqual(self.s.store.snapshot.job.state_version, job.state_version)
        self.assertIn("safe-result-reference", self.s.store.snapshot.job.audit_events)

    def test_recovery_limit_escalates_with_owner_deadline_alert(self) -> None:
        self.unknown()
        self.s.facts = replace(self.s.facts,
                              recovery=replace(self.s.facts.recovery, attempts_used=3))
        c, _ = self.s.apply(self.s.command(Operation.RECOVER, "recover-1"))
        self.assertEqual(c.status, "ESCALATE_BOUNDED_RECOVERY_EXHAUSTED")
        record = self.s.store.snapshot.escalations[0]
        self.assertEqual((record.owner_id, record.deadline, record.alert_status),
                         ("operations", 2000, "PENDING"))
        self.assertEqual(self.s.store.snapshot.job.reservations[0].status,
                         ReservationStatus.HELD)

    def test_recovery_count_cannot_reset_between_commands(self) -> None:
        self.unknown()
        for index in range(3):
            c, _ = self.s.apply(self.s.command(Operation.RECOVER, f"recover-{index}"))
            self.assertEqual(c.status, "RECONCILE")
        # The original injected facts still say zero. The committed history wins.
        self.assertEqual(self.s.facts.recovery.attempts_used, 0)
        c, _ = self.s.apply(self.s.command(Operation.RECOVER, "recover-exhausted"))
        self.assertEqual(c.status, "ESCALATE_BOUNDED_RECOVERY_EXHAUSTED")
        self.assertEqual(self.s.store.snapshot.job.recovery_operations[-1].attempts_used, 3)

    def test_late_callback_after_cancel_has_zero_business_version_change(self) -> None:
        self.s.apply(self.s.command(Operation.INVALIDATE, "cancel-request",
                                   invalidate_to=ApprovalStatus.CANCELLED))
        version = self.s.store.snapshot.job.state_version
        _, status = self.s.apply(self.s.approval_command())
        self.assertEqual(status, "AUDIT_ONLY")
        self.assertEqual(self.s.store.snapshot.job.state_version, version)

    def test_owner_unavailable_uses_permitted_fallback(self) -> None:
        self.unknown()
        self.s.facts = replace(self.s.facts, owner_available=False,
                              recovery=replace(self.s.facts.recovery, attempts_used=3))
        c, _ = self.s.apply(self.s.command(Operation.RECOVER, "recover-1"))
        self.assertEqual(c.escalation.owner_id, "backup-operations")
        self.assertIn("OWNER_UNAVAILABLE", c.evidence)

    def test_policy_unknown_is_not_external_unknown(self) -> None:
        self.s.facts = replace(self.s.facts, policy_available=False)
        self.assertEqual(self.candidate().status, "POLICY_UNAVAILABLE")
        self.assertEqual(self.candidate().next_state, AgentState.WAITING)
        self.assertEqual(self.candidate(400).status,
                         "ESCALATE_APPROVAL_POLICY_UNAVAILABLE")

    def test_approval_overdue_not_rejected(self) -> None:
        c = self.candidate(500)
        self.assertEqual(c.status, "ESCALATE_APPROVAL_OVERDUE")
        self.assertEqual(c.approval_status, ApprovalStatus.PENDING)

    def test_cancelled_request_rejects_late_decision(self) -> None:
        self.s.apply(self.s.command(Operation.INVALIDATE, "cancel-request",
                                   invalidate_to=ApprovalStatus.CANCELLED))
        c, _ = self.s.apply(self.s.approval_command())
        self.assertEqual(c.status, "APPROVAL_CANCELLED")
        self.assertEqual(self.s.store.snapshot.decisions, ())

    def test_revoked_and_superseded_do_not_dispatch(self) -> None:
        for status in (ApprovalStatus.REVOKED, ApprovalStatus.SUPERSEDED):
            with self.subTest(status=status):
                self.s = build_scenario()
                self.s.approve()
                self.s.apply(self.s.command(Operation.INVALIDATE, "invalidate",
                                           invalidate_to=status))
                self.assertFalse(self.candidate().execution_allowed)

    def test_terminal_job_does_not_reopen_for_approval(self) -> None:
        self.s.approve()
        s = self.s.store.snapshot
        self.s.store.snapshot = replace(s, job=replace(s.job, state=AgentState.COMPLETED))
        self.assertEqual(self.candidate().status, "TERMINAL_NOOP")

    def test_completed_job_can_reconcile_accounting_without_reopening(self) -> None:
        self.unknown()
        s = self.s.store.snapshot
        self.s.store.snapshot = replace(s, job=replace(s.job, state=AgentState.COMPLETED))
        c, _ = self.s.apply(self.s.command(Operation.RECOVER, "recover-accounting"))
        self.assertEqual(c.status, "RECONCILE")
        self.assertEqual(self.s.store.snapshot.job.state, AgentState.COMPLETED)

    def test_verified_accounting_settles_1800_releases_4200(self) -> None:
        self.s.facts = replace(self.s.facts,
                              certainty=ExternalCertainty.VERIFIED_TERMINAL,
                              verified_usage=1800, outcome_evidence_id="usage-evidence")
        c, _ = self.s.apply(self.s.command(Operation.RECOVER, "settle-1"))
        self.assertEqual(c.status, "SETTLE")
        record = self.s.store.snapshot.job.reservations[0]
        self.assertEqual((record.settled_units, record.released_units), (1800, 4200))

    def test_exhausted_queries_do_not_prevent_verified_settlement(self) -> None:
        self.unknown()
        for index in range(4):
            self.s.apply(self.s.command(Operation.RECOVER, f"query-{index}"))
        self.s.facts = replace(self.s.facts,
                              certainty=ExternalCertainty.VERIFIED_TERMINAL,
                              verified_usage=1800, outcome_evidence_id="usage-evidence")
        c, _ = self.s.apply(self.s.command(Operation.RECOVER, "settle-after-escalation"))
        self.assertEqual(c.status, "SETTLE")
        self.assertEqual(self.s.store.snapshot.job.recovery_operations[-1].attempts_used, 3)
        self.assertEqual(self.s.store.snapshot.job.reservations[0].settled_units, 1800)

    def test_settlement_duplicate_and_conflicting_usage_cannot_rewrite(self) -> None:
        self.s.facts = replace(self.s.facts,
                              certainty=ExternalCertainty.VERIFIED_TERMINAL,
                              verified_usage=1800, outcome_evidence_id="usage-evidence")
        self.s.apply(self.s.command(Operation.RECOVER, "settle-1"))
        c, _ = self.s.apply(self.s.command(Operation.RECOVER, "settle-repeat"))
        self.assertEqual(c.status, "SETTLEMENT_ALREADY_RECORDED")
        self.s.facts = replace(self.s.facts, verified_usage=1900)
        c, _ = self.s.apply(self.s.command(Operation.RECOVER, "settle-conflict"))
        self.assertEqual(c.status, "ESCALATE_SETTLEMENT_CONFLICT")
        self.assertEqual(self.s.store.snapshot.job.reservations[0].settled_units, 1800)

    def test_compensation_cannot_reuse_publish_approval(self) -> None:
        self.s.approve()
        state = self.s.store.snapshot
        self.s.store.snapshot = replace(state, action=replace(
            state.action, action_type="compensate", operation_id="compensation-1",
            tool_name="retract_research_report"))
        self.assertEqual(self.candidate().status, "APPROVAL_BINDING_MISMATCH")


if __name__ == "__main__":
    unittest.main()
