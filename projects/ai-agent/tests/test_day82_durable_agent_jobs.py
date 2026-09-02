import unittest

from agent_state_machine import AgentState
from durable_agent_jobs import (
    DeliveryStatus,
    DurableAgentJobRecord,
    DurableCheckpoint,
    DurableRecoveryDecision,
    ExecutionBindings,
    ExternalCertainty,
    InMemoryDurableAgentJobStore,
    InMemoryOutboxConsumerGuard,
    OutboxIntent,
    RecoveryApplyStatus,
    RecoveryOperation,
    RecoveryRequest,
    ReservationAction,
    ReservationRecord,
    ReservationStatus,
    decide_durable_recovery,
)


def checkpoint(*, state=AgentState.RUNNING):
    return DurableCheckpoint(
        tenant_id="tenant-a",
        job_id="J1",
        step_id="S1",
        attempt_id="A1",
        checkpoint_id="CP1",
        checkpoint_version=3,
        authoritative_state=state,
        state_version=12,
        fence_token=8,
        lease_generation=2,
        bindings=ExecutionBindings(
            controller_release="stable-v6",
            prompt_binding="prompt-v4",
            provider_binding="provider-profile-v3",
            tool_binding="tool-v1",
            policy_binding="policy-v5",
        ),
        progress_fingerprint="progress-1",
        verified_observation_ids=("O1",),
        reservation_ids=("RES1",),
        pending_reconciliation_ids=(),
    )


def record(*, state=AgentState.RUNNING, lease_expiry=100):
    cp = checkpoint(state=state)
    return DurableAgentJobRecord(
        tenant_id="tenant-a",
        job_id="J1",
        current_step_id="S1",
        current_attempt_id="A1",
        state=state,
        state_version=12,
        fence_token=8,
        lease_owner="W1",
        lease_expiry_epoch_ms=lease_expiry,
        lease_generation=2,
        current_checkpoint=cp,
        reservations=(ReservationRecord("RES1", "A1", 6000),),
    )


def recovery(*, used=0, limit=3, deadline=1000):
    return RecoveryOperation("R1", "A1", 2, used, limit, deadline, None)


def request(**changes):
    values = dict(
        recovery_id="R1",
        tenant_id="tenant-a",
        job_id="J1",
        step_id="S1",
        attempt_id="A1",
        checkpoint_id="CP1",
        expected_state=AgentState.RUNNING,
        expected_state_version=12,
        expected_fence_token=8,
        now_epoch_ms=200,
        external_certainty=ExternalCertainty.VERIFIED_TERMINAL,
        current_authorization=True,
        original_binding_currently_allowed=True,
    )
    values.update(changes)
    return RecoveryRequest(**values)


class CheckpointAndDecisionTests(unittest.TestCase):
    def test_matching_checkpoint_can_resume_same_identity(self):
        item = decide_durable_recovery(record(), recovery(), request())
        self.assertIs(item.decision, DurableRecoveryDecision.RESUME)

    def test_checkpoint_attempt_mismatch_is_rejected(self):
        item = decide_durable_recovery(
            record(), recovery(), request(attempt_id="A0")
        )
        self.assertIs(item.decision, DurableRecoveryDecision.REJECT_STALE)

    def test_checkpoint_id_mismatch_is_rejected(self):
        item = decide_durable_recovery(
            record(), recovery(), request(checkpoint_id="CP0")
        )
        self.assertEqual(item.status, "CHECKPOINT_IDENTITY_MISMATCH")

    def test_old_state_version_is_rejected(self):
        item = decide_durable_recovery(
            record(), recovery(), request(expected_state_version=11)
        )
        self.assertIs(item.decision, DurableRecoveryDecision.REJECT_STALE)

    def test_old_fence_is_rejected(self):
        item = decide_durable_recovery(
            record(), recovery(), request(expected_fence_token=7)
        )
        self.assertIs(item.decision, DurableRecoveryDecision.REJECT_STALE)

    def test_terminal_job_is_noop(self):
        item = decide_durable_recovery(
            record(state=AgentState.COMPLETED),
            recovery(),
            request(expected_state=AgentState.COMPLETED),
        )
        self.assertIs(item.decision, DurableRecoveryDecision.TERMINAL_NOOP)

    def test_completed_job_can_reconcile_unknown_accounting(self):
        item = decide_durable_recovery(
            record(state=AgentState.COMPLETED),
            recovery(),
            request(
                expected_state=AgentState.COMPLETED,
                external_certainty=ExternalCertainty.OUTCOME_UNKNOWN,
            ),
        )
        self.assertIs(item.decision, DurableRecoveryDecision.RECONCILE)
        self.assertIs(item.next_state, AgentState.COMPLETED)
        self.assertIs(item.reservation_action, ReservationAction.KEEP_HELD)

    def test_completed_job_can_settle_verified_usage(self):
        item = decide_durable_recovery(
            record(state=AgentState.COMPLETED),
            recovery(),
            request(
                expected_state=AgentState.COMPLETED,
                verified_usage_units=1800,
            ),
        )
        self.assertIs(item.decision, DurableRecoveryDecision.SETTLE)
        self.assertIs(item.next_state, AgentState.COMPLETED)

    def test_unknown_outcome_reconciles_original_identity(self):
        item = decide_durable_recovery(
            record(),
            recovery(),
            request(external_certainty=ExternalCertainty.OUTCOME_UNKNOWN),
        )
        self.assertIs(item.decision, DurableRecoveryDecision.RECONCILE)
        self.assertIs(item.reservation_action, ReservationAction.KEEP_HELD)
        self.assertIn("original_attempt_identity_preserved", item.evidence)

    def test_recovery_attempt_limit_escalates_and_holds(self):
        item = decide_durable_recovery(
            record(),
            recovery(used=3),
            request(external_certainty=ExternalCertainty.OUTCOME_UNKNOWN),
        )
        self.assertIs(item.decision, DurableRecoveryDecision.ESCALATE)
        self.assertIs(item.reservation_action, ReservationAction.KEEP_HELD)

    def test_recovery_deadline_escalates_and_holds(self):
        item = decide_durable_recovery(
            record(),
            recovery(deadline=200),
            request(external_certainty=ExternalCertainty.OUTCOME_UNKNOWN),
        )
        self.assertIs(item.decision, DurableRecoveryDecision.ESCALATE)

    def test_disabled_old_binding_replans_without_rewrite(self):
        item = decide_durable_recovery(
            record(),
            recovery(),
            request(
                external_certainty=(
                    ExternalCertainty.DEFINITELY_NOT_DISPATCHED
                ),
                original_binding_currently_allowed=False,
            ),
        )
        self.assertIs(item.decision, DurableRecoveryDecision.REPLAN)
        self.assertIn("old_binding_not_rewritten", item.evidence)

    def test_definitely_not_dispatched_may_retry(self):
        item = decide_durable_recovery(
            record(),
            recovery(),
            request(
                external_certainty=(
                    ExternalCertainty.DEFINITELY_NOT_DISPATCHED
                )
            ),
        )
        self.assertIs(item.decision, DurableRecoveryDecision.RETRY)
        self.assertIs(item.reservation_action, ReservationAction.RELEASE)

    def test_retry_cannot_bypass_revoked_authorization(self):
        item = decide_durable_recovery(
            record(),
            recovery(),
            request(
                external_certainty=(
                    ExternalCertainty.DEFINITELY_NOT_DISPATCHED
                ),
                current_authorization=False,
            ),
        )
        self.assertIs(item.decision, DurableRecoveryDecision.BLOCKED)

    def test_internal_reference_issue_uses_repair(self):
        item = decide_durable_recovery(
            record(), recovery(), request(internal_repair_required=True)
        )
        self.assertIs(item.decision, DurableRecoveryDecision.REPAIR)

    def test_unwanted_verified_effect_uses_compensation(self):
        item = decide_durable_recovery(
            record(), recovery(), request(verified_effect_unwanted=True)
        )
        self.assertIs(item.decision, DurableRecoveryDecision.COMPENSATE)

    def test_compensation_requires_current_authorization(self):
        item = decide_durable_recovery(
            record(),
            recovery(),
            request(
                verified_effect_unwanted=True,
                current_authorization=False,
            ),
        )
        self.assertIs(item.decision, DurableRecoveryDecision.BLOCKED)

    def test_verified_usage_creates_settlement_candidate(self):
        item = decide_durable_recovery(
            record(), recovery(), request(verified_usage_units=1800)
        )
        self.assertIs(item.decision, DurableRecoveryDecision.SETTLE)
        self.assertIs(
            item.reservation_action, ReservationAction.SETTLE_VERIFIED
        )


class ConditionalApplyTests(unittest.TestCase):
    def test_apply_advances_state_checkpoint_and_fence_together(self):
        store = InMemoryDurableAgentJobStore(record())
        item = decide_durable_recovery(store.record, recovery(), request())
        self.assertIs(store.apply(item), RecoveryApplyStatus.APPLIED)
        self.assertEqual(store.record.state_version, 13)
        self.assertEqual(store.record.fence_token, 9)
        self.assertEqual(store.record.current_checkpoint.checkpoint_version, 4)
        self.assertEqual(
            store.record.current_checkpoint.previous_checkpoint_id, "CP1"
        )

    def test_duplicate_recovery_does_not_apply_twice(self):
        store = InMemoryDurableAgentJobStore(record())
        item = decide_durable_recovery(store.record, recovery(), request())
        self.assertIs(store.apply(item), RecoveryApplyStatus.APPLIED)
        self.assertIs(
            store.apply(item), RecoveryApplyStatus.DUPLICATE_REPLAY
        )
        self.assertEqual(len(store.record.recovery_operations), 1)

    def test_stale_candidate_creates_no_outbox_intent(self):
        store = InMemoryDurableAgentJobStore(record())
        item = decide_durable_recovery(
            store.record,
            recovery(),
            request(external_certainty=ExternalCertainty.OUTCOME_UNKNOWN),
        )
        store.record = record()
        store.record = DurableAgentJobRecord(
            **{
                **store.record.__dict__,
                "state_version": 13,
                "fence_token": 9,
            }
        )
        self.assertIs(store.apply(item), RecoveryApplyStatus.NOOP_STALE)
        self.assertEqual(store.record.outbox_intents, ())

    def test_reconciliation_keeps_held_reservation(self):
        store = InMemoryDurableAgentJobStore(record())
        item = decide_durable_recovery(
            store.record,
            recovery(),
            request(external_certainty=ExternalCertainty.OUTCOME_UNKNOWN),
        )
        self.assertIs(store.apply(item), RecoveryApplyStatus.APPLIED)
        self.assertIs(
            store.record.reservations[0].status, ReservationStatus.HELD
        )
        self.assertEqual(len(store.record.outbox_intents), 1)

    def test_verified_usage_settles_1800_and_releases_4200(self):
        store = InMemoryDurableAgentJobStore(record())
        item = decide_durable_recovery(
            store.record, recovery(), request(verified_usage_units=1800)
        )
        self.assertIs(store.apply(item), RecoveryApplyStatus.APPLIED)
        reservation = store.record.reservations[0]
        self.assertIs(reservation.status, ReservationStatus.SETTLED)
        self.assertEqual(reservation.settled_units, 1800)
        self.assertEqual(reservation.released_units, 4200)

    def test_retry_releases_original_reservation_once(self):
        store = InMemoryDurableAgentJobStore(record())
        item = decide_durable_recovery(
            store.record,
            recovery(),
            request(
                external_certainty=(
                    ExternalCertainty.DEFINITELY_NOT_DISPATCHED
                )
            ),
        )
        self.assertIs(store.apply(item), RecoveryApplyStatus.APPLIED)
        self.assertIs(
            store.record.reservations[0].status,
            ReservationStatus.RELEASED,
        )
        self.assertEqual(store.record.reservations[0].released_units, 6000)

    def test_revoked_retry_still_releases_proven_unused_reservation(self):
        store = InMemoryDurableAgentJobStore(record())
        item = decide_durable_recovery(
            store.record,
            recovery(),
            request(
                external_certainty=(
                    ExternalCertainty.DEFINITELY_NOT_DISPATCHED
                ),
                current_authorization=False,
            ),
        )
        self.assertIs(item.decision, DurableRecoveryDecision.BLOCKED)
        self.assertIs(store.apply(item), RecoveryApplyStatus.APPLIED)
        self.assertIs(
            store.record.reservations[0].status,
            ReservationStatus.RELEASED,
        )
        self.assertEqual(store.record.reservations[0].released_units, 6000)

    def test_completed_job_settles_accounting_without_reopening(self):
        store = InMemoryDurableAgentJobStore(
            record(state=AgentState.COMPLETED)
        )
        item = decide_durable_recovery(
            store.record,
            recovery(),
            request(
                expected_state=AgentState.COMPLETED,
                verified_usage_units=1800,
            ),
        )
        self.assertIs(store.apply(item), RecoveryApplyStatus.APPLIED)
        self.assertIs(store.record.state, AgentState.COMPLETED)
        self.assertEqual(store.record.reservations[0].settled_units, 1800)


class LeaseAndDeliveryTests(unittest.TestCase):
    def test_relay_rescans_only_null_published_at_intents(self):
        pending = OutboxIntent("E1", "J1", "S1", "A1", "RESUME")
        published = OutboxIntent(
            "E2",
            "J1",
            "S1",
            "A1",
            "RESUME",
            published_at_epoch_ms=250,
        )
        item = record()
        store = InMemoryDurableAgentJobStore(
            DurableAgentJobRecord(
                **{
                    **item.__dict__,
                    "outbox_intents": (pending, published),
                }
            )
        )
        self.assertEqual(store.unpublished_outbox_intents(), (pending,))

    def test_lease_takeover_advances_fence(self):
        store = InMemoryDurableAgentJobStore(record())
        self.assertTrue(
            store.take_over_expired_lease(worker_id="W2", now_epoch_ms=100)
        )
        self.assertEqual(store.record.lease_owner, "W2")
        self.assertEqual(store.record.lease_generation, 3)
        self.assertEqual(store.record.fence_token, 9)

    def test_unexpired_lease_cannot_be_taken_over(self):
        store = InMemoryDurableAgentJobStore(record(lease_expiry=300))
        self.assertFalse(
            store.take_over_expired_lease(worker_id="W2", now_epoch_ms=100)
        )

    def test_old_worker_result_is_evidence_but_cannot_apply(self):
        store = InMemoryDurableAgentJobStore(record())
        store.take_over_expired_lease(worker_id="W2", now_epoch_ms=100)
        self.assertFalse(
            store.accept_result(
                worker_id="W1",
                result_fence_token=8,
                evidence_id="provider-result-A1",
            )
        )
        self.assertIn(
            "late_or_current_result:provider-result-A1",
            store.record.audit_events,
        )

    def test_duplicate_delivery_keeps_same_business_identity(self):
        guard = InMemoryOutboxConsumerGuard()
        event = OutboxIntent("E1", "J1", "S1", "A1", "RESUME")
        self.assertIs(guard.accept(event), DeliveryStatus.NEW)
        self.assertIs(guard.accept(event), DeliveryStatus.DUPLICATE)

    def test_reused_event_id_with_new_attempt_is_conflict(self):
        guard = InMemoryOutboxConsumerGuard()
        guard.accept(OutboxIntent("E1", "J1", "S1", "A1", "RESUME"))
        changed = OutboxIntent("E1", "J1", "S1", "A2", "RESUME")
        self.assertIs(guard.accept(changed), DeliveryStatus.IDENTITY_CONFLICT)


if __name__ == "__main__":
    unittest.main()
