"""Focused tests for Day93 lifecycle evidence and bounded retry policy."""
import unittest

from mcp_client_transport import DispatchCertainty
from mcp_remote_lifecycle import (
    CancellationObservation,
    DeadlineBudget,
    ExecutionCertainty,
    FailureEvidence,
    FailureKind,
    FailurePhase,
    LifecycleOutcome,
    cancellation_failure_evidence,
    classify_lifecycle_outcome,
)
from mcp_retry_policy import (
    BoundedRetryPolicy,
    InMemoryRetryDispatchStore,
    RetryContext,
    RetryDecisionKind,
    RetryDispatchClaimOutcome,
    RetryDispatchContext,
    RetryDispatchDecisionKind,
    RetryDispatchRecordState,
    admit_retry_dispatch,
    plan_retry_attempt,
    recover_abandoned_dispatch,
)


def evidence(
    *,
    kind: FailureKind = FailureKind.CONNECT_TIMEOUT,
    phase: FailurePhase = FailurePhase.CONNECT,
    certainty: DispatchCertainty = DispatchCertainty.PROVEN_NOT_SENT,
    operation_id: str = "op-report-42",
    attempt_number: int = 1,
    execution_certainty: ExecutionCertainty | None = None,
) -> FailureEvidence:
    return FailureEvidence(
        operation_id=operation_id,
        idempotency_key="idem-report-42",
        protocol_request_id="mcp-request-93-1",
        attempt_number=attempt_number,
        phase=phase,
        kind=kind,
        dispatch_certainty=certainty,
        execution_certainty=(
            execution_certainty
            or (
                ExecutionCertainty.PROVEN_NOT_EXECUTED
                if certainty is DispatchCertainty.PROVEN_NOT_SENT
                else ExecutionCertainty.POSSIBLY_EXECUTED
            )
        ),
        evidence_source="controlled-transport-adapter",
    )


def retry_context(**overrides: object) -> RetryContext:
    values: dict[str, object] = {
        "now": 100.0,
        "deadline": 110.0,
        "retries_used": 0,
        "max_retries": 2,
        "caller_intent_active": True,
        "authorization_current": True,
        "capacity_admitted": True,
        "circuit_allows_request": True,
    }
    values.update(overrides)
    return RetryContext(**values)  # type: ignore[arg-type]


def retry_attempt():
    observed = evidence()
    decision = BoundedRetryPolicy().decide(observed, retry_context())
    return plan_retry_attempt(
        observed,
        decision,
        new_protocol_request_id="mcp-request-93-2",
    )


def dispatch_context(**overrides: object) -> RetryDispatchContext:
    values: dict[str, object] = {
        "now": 101.0,
        "deadline": 110.0,
        "caller_intent_active": True,
        "authorization_current": True,
        "capacity_admitted": True,
        "circuit_allows_request": True,
    }
    values.update(overrides)
    return RetryDispatchContext(**values)  # type: ignore[arg-type]


class Day93RemoteLifecycleTests(unittest.TestCase):
    def test_parent_deadline_caps_every_stage_timeout(self) -> None:
        budget = DeadlineBudget(deadline=108.0)

        self.assertEqual(
            budget.stage_timeout(now=100.0, configured_timeout=30.0),
            8.0,
        )
        self.assertEqual(
            budget.stage_timeout(now=103.0, configured_timeout=30.0),
            5.0,
        )

    def test_remote_task_cancelled_after_dispatch_remains_unknown(self) -> None:
        cancelled = cancellation_failure_evidence(
            CancellationObservation(
                operation_id="op-report-42",
                idempotency_key="idem-report-42",
                protocol_request_id="mcp-request-93-1",
                attempt_number=1,
                dispatch_certainty=DispatchCertainty.PROVEN_SENT,
                remote_task_cancelled=True,
                evidence_source="mcp-sdk-courtesy-cancellation",
            )
        )

        self.assertEqual(
            cancelled.execution_certainty,
            ExecutionCertainty.POSSIBLY_EXECUTED,
        )
        self.assertEqual(
            classify_lifecycle_outcome(cancelled),
            LifecycleOutcome.PENDING_RECONCILIATION,
        )

    def test_cancellation_before_dispatch_proves_not_executed(self) -> None:
        cancelled = cancellation_failure_evidence(
            CancellationObservation(
                operation_id="op-report-42",
                idempotency_key="idem-report-42",
                protocol_request_id="mcp-request-93-1",
                attempt_number=1,
                dispatch_certainty=DispatchCertainty.PROVEN_NOT_SENT,
                remote_task_cancelled=False,
                evidence_source="local-caller-cancellation",
            )
        )

        self.assertEqual(
            cancelled.execution_certainty,
            ExecutionCertainty.PROVEN_NOT_EXECUTED,
        )
        self.assertEqual(
            classify_lifecycle_outcome(cancelled),
            LifecycleOutcome.PRE_DISPATCH_ABORTED,
        )

    def test_cleanup_reserve_is_not_available_to_read_phase(self) -> None:
        budget = DeadlineBudget(
            deadline=108.0,
            cleanup_reserve_seconds=0.5,
        )

        self.assertEqual(
            budget.stage_timeout(now=103.0, configured_timeout=30.0),
            4.5,
        )

    def test_possible_dispatch_requires_reconciliation(self) -> None:
        observed = evidence(
            kind=FailureKind.READ_TIMEOUT,
            phase=FailurePhase.READ,
            certainty=DispatchCertainty.POSSIBLY_SENT,
        )

        self.assertEqual(
            classify_lifecycle_outcome(observed),
            LifecycleOutcome.PENDING_RECONCILIATION,
        )

    def test_proven_not_sent_is_pre_dispatch_abort(self) -> None:
        self.assertEqual(
            classify_lifecycle_outcome(evidence()),
            LifecycleOutcome.PRE_DISPATCH_ABORTED,
        )

    def test_possible_dispatch_never_becomes_retry_eligible(self) -> None:
        observed = evidence(
            kind=FailureKind.READ_TIMEOUT,
            phase=FailurePhase.READ,
            certainty=DispatchCertainty.POSSIBLY_SENT,
        )

        decision = BoundedRetryPolicy().decide(
            observed,
            retry_context(),
        )

        self.assertEqual(decision.kind, RetryDecisionKind.POSSIBLE_EXECUTION)
        self.assertFalse(decision.eligible)

    def test_retry_reuses_operation_identity(self) -> None:
        observed = evidence()
        decision = BoundedRetryPolicy().decide(
            observed,
            retry_context(),
        )
        attempt = plan_retry_attempt(
            observed,
            decision,
            new_protocol_request_id="mcp-request-93-2",
        )

        self.assertTrue(decision.eligible)
        self.assertEqual(attempt.operation_id, "op-report-42")
        self.assertEqual(attempt.idempotency_key, "idem-report-42")
        self.assertEqual(attempt.protocol_request_id, "mcp-request-93-2")
        self.assertEqual(attempt.attempt_number, 2)

    def test_retry_rejects_reused_protocol_request_id(self) -> None:
        observed = evidence()
        decision = BoundedRetryPolicy().decide(observed, retry_context())

        with self.assertRaisesRegex(ValueError, "fresh protocol_request_id"):
            plan_retry_attempt(
                observed,
                decision,
                new_protocol_request_id=observed.protocol_request_id,
            )

    def test_blocked_retry_cannot_create_an_attempt(self) -> None:
        observed = evidence(
            kind=FailureKind.READ_TIMEOUT,
            phase=FailurePhase.READ,
            certainty=DispatchCertainty.POSSIBLY_SENT,
        )
        decision = BoundedRetryPolicy().decide(observed, retry_context())

        with self.assertRaisesRegex(ValueError, "eligible retry"):
            plan_retry_attempt(
                observed,
                decision,
                new_protocol_request_id="mcp-request-93-2",
            )

    def test_authorization_is_rechecked_after_backoff(self) -> None:
        dispatch = admit_retry_dispatch(
            retry_attempt(),
            dispatch_context(authorization_current=False),
        )

        self.assertEqual(
            dispatch.kind,
            RetryDispatchDecisionKind.AUTHORIZATION_NOT_CURRENT,
        )
        self.assertFalse(dispatch.admitted)
        self.assertEqual(dispatch.transport_calls, 0)

    def test_parent_deadline_is_rechecked_after_backoff(self) -> None:
        dispatch = admit_retry_dispatch(
            retry_attempt(),
            dispatch_context(now=109.98, deadline=110.0),
        )

        self.assertEqual(
            dispatch.kind,
            RetryDispatchDecisionKind.DEADLINE_EXHAUSTED,
        )
        self.assertFalse(dispatch.admitted)

    def test_retry_dispatch_requires_all_fresh_gates(self) -> None:
        dispatch = admit_retry_dispatch(retry_attempt(), dispatch_context())

        self.assertEqual(dispatch.kind, RetryDispatchDecisionKind.ADMITTED)
        self.assertTrue(dispatch.admitted)
        self.assertEqual(dispatch.attempt.attempt_number, 2)

    def test_conditional_update_allows_only_one_worker_to_dispatch(self) -> None:
        observed = evidence()
        store = InMemoryRetryDispatchStore()
        store.add_retryable(observed)
        dispatch = admit_retry_dispatch(retry_attempt(), dispatch_context())

        worker_one = store.claim_dispatch(dispatch, expected_version=1)
        worker_two = store.claim_dispatch(dispatch, expected_version=1)

        self.assertEqual(worker_one.outcome, RetryDispatchClaimOutcome.CLAIMED)
        self.assertTrue(worker_one.durable_transition)
        self.assertEqual(
            worker_one.record.state,
            RetryDispatchRecordState.DISPATCH_STARTED,
        )
        self.assertEqual(
            worker_two.outcome,
            RetryDispatchClaimOutcome.STATE_CONFLICT,
        )
        self.assertFalse(worker_two.durable_transition)
        self.assertEqual(worker_two.transport_calls, 0)

    def test_dispatch_marker_is_durable_before_transport_handoff(self) -> None:
        store = InMemoryRetryDispatchStore()
        store.add_retryable(evidence())
        dispatch = admit_retry_dispatch(retry_attempt(), dispatch_context())

        claim = store.claim_dispatch(dispatch, expected_version=1)
        persisted = store.read("op-report-42")

        self.assertTrue(claim.claimed)
        self.assertEqual(
            persisted.state,
            RetryDispatchRecordState.DISPATCH_STARTED,
        )
        self.assertEqual(persisted.protocol_request_id, "mcp-request-93-2")
        self.assertEqual(claim.transport_calls, 0)

    def test_crash_after_dispatch_marker_becomes_possible_dispatch(self) -> None:
        store = InMemoryRetryDispatchStore()
        store.add_retryable(evidence())
        dispatch = admit_retry_dispatch(retry_attempt(), dispatch_context())
        store.claim_dispatch(dispatch, expected_version=1)

        recovered = recover_abandoned_dispatch(store.read("op-report-42"))
        retry = BoundedRetryPolicy().decide(recovered, retry_context())

        self.assertEqual(
            recovered.dispatch_certainty,
            DispatchCertainty.POSSIBLY_SENT,
        )
        self.assertEqual(recovered.kind, FailureKind.DISPATCH_OWNER_LOST)
        self.assertEqual(
            classify_lifecycle_outcome(recovered),
            LifecycleOutcome.PENDING_RECONCILIATION,
        )
        self.assertEqual(retry.kind, RetryDecisionKind.POSSIBLE_EXECUTION)
        self.assertFalse(retry.eligible)

    def test_sent_pre_handler_capacity_rejection_can_be_retry_eligible(self) -> None:
        rejected = evidence(
            kind=FailureKind.CAPACITY_REJECTED,
            phase=FailurePhase.CAPACITY,
            certainty=DispatchCertainty.PROVEN_SENT,
            execution_certainty=ExecutionCertainty.PROVEN_NOT_EXECUTED,
        )

        decision = BoundedRetryPolicy().decide(rejected, retry_context())

        self.assertEqual(
            classify_lifecycle_outcome(rejected),
            LifecycleOutcome.REJECTED_BEFORE_EXECUTION,
        )
        self.assertTrue(decision.eligible)

    def test_caller_cancellation_blocks_safe_pre_dispatch_retry(self) -> None:
        decision = BoundedRetryPolicy().decide(
            evidence(kind=FailureKind.CALLER_CANCELLED),
            retry_context(caller_intent_active=False),
        )

        self.assertEqual(
            decision.kind,
            RetryDecisionKind.CALLER_INTENT_INACTIVE,
        )

    def test_retry_budget_is_bounded(self) -> None:
        decision = BoundedRetryPolicy().decide(
            evidence(attempt_number=3),
            retry_context(retries_used=2, max_retries=2),
        )

        self.assertEqual(
            decision.kind,
            RetryDecisionKind.RETRY_BUDGET_EXHAUSTED,
        )

    def test_backoff_jitter_is_deterministic_and_operation_specific(self) -> None:
        policy = BoundedRetryPolicy()
        first = policy.decide(evidence(), retry_context())
        repeated = policy.decide(evidence(), retry_context())
        other = policy.decide(
            evidence(operation_id="op-report-43"),
            retry_context(),
        )

        self.assertEqual(first.delay_seconds, repeated.delay_seconds)
        self.assertNotEqual(first.delay_seconds, other.delay_seconds)

    def test_retry_wait_cannot_cross_parent_deadline(self) -> None:
        decision = BoundedRetryPolicy(
            base_delay_seconds=0.25,
            jitter_ratio=0.0,
            minimum_attempt_window_seconds=0.05,
        ).decide(
            evidence(),
            retry_context(deadline=100.2),
        )

        self.assertEqual(
            decision.kind,
            RetryDecisionKind.DEADLINE_EXHAUSTED,
        )


if __name__ == "__main__":
    unittest.main()
