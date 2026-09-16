"""Day93 tests: reconciliation observes authority and never replays a Tool."""
import unittest

from mcp_client_transport import DispatchCertainty
from mcp_reconciliation import (
    ApplicationOperationBinding,
    AuthoritativeOperationStatus,
    AuthoritativeResultEvidence,
    BoundedReconciliationPolicy,
    ComplianceOutcome,
    InMemoryReconciliationStore,
    ReconciledBusinessOutcome,
    ReconciliationCommitOutcome,
    ReconciliationCommitter,
    ReconciliationDecisionKind,
    ReconciliationScheduleOutcome,
    ReconciliationScheduleState,
    ReconciliationScheduler,
    authoritative_not_executed_evidence,
)
from mcp_remote_lifecycle import (
    ExecutionCertainty,
    FailureEvidence,
    FailureKind,
    FailurePhase,
)
from mcp_retry_policy import BoundedRetryPolicy, RetryContext, RetryDecisionKind


def failure(
    certainty: DispatchCertainty = DispatchCertainty.POSSIBLY_SENT,
) -> FailureEvidence:
    return FailureEvidence(
        operation_id="op-report-42",
        idempotency_key="idem-report-42",
        protocol_request_id="mcp-request-93-1",
        attempt_number=1,
        phase=FailurePhase.READ,
        kind=FailureKind.READ_TIMEOUT,
        dispatch_certainty=certainty,
        execution_certainty=(
            ExecutionCertainty.PROVEN_NOT_EXECUTED
            if certainty is DispatchCertainty.PROVEN_NOT_SENT
            else ExecutionCertainty.POSSIBLY_EXECUTED
        ),
        evidence_source="controlled-transport-adapter",
    )


class RecordingAuthority:
    def __init__(self, result: AuthoritativeResultEvidence) -> None:
        self.result = result
        self.queries: list[ApplicationOperationBinding] = []

    def query(
        self,
        *,
        binding: ApplicationOperationBinding,
    ) -> AuthoritativeResultEvidence:
        self.queries.append(binding)
        return self.result


class RecordingControlledService:
    """The original side-effecting Tool; never injected into the scheduler."""

    def __init__(self) -> None:
        self.calls = 0

    def execute(self) -> None:
        self.calls += 1


class RecordingAlerts:
    def __init__(self) -> None:
        self.items = []

    def emit(self, alert) -> None:
        self.items.append(alert)


def binding(
    *,
    operation_id: str = "op-report-42",
    idempotency_key: str = "idem-report-42",
    tenant_id: str = "tenant-a",
    resource_id: str = "research-report-42",
) -> ApplicationOperationBinding:
    return ApplicationOperationBinding(
        operation_id,
        idempotency_key,
        tenant_id,
        resource_id,
    )


def result(
    status: AuthoritativeOperationStatus,
    *,
    observed_binding: ApplicationOperationBinding | None = None,
    external_object_id: str | None = None,
) -> AuthoritativeResultEvidence:
    return AuthoritativeResultEvidence(
        binding=observed_binding or binding(),
        status=status,
        evidence_source="external-operation-ledger",
        external_object_id=external_object_id,
    )


class Day93MCPReconciliationTests(unittest.TestCase):
    def test_possible_dispatch_queries_authority_without_replaying_tool(self) -> None:
        authority = RecordingAuthority(
            result(
                AuthoritativeOperationStatus.SUCCEEDED,
                external_object_id="external-report-77",
            )
        )
        controlled_service = RecordingControlledService()

        expected_binding = binding()
        decision = ReconciliationScheduler(authority).reconcile_once(
            failure(),
            binding=expected_binding,
        )

        self.assertEqual(
            decision.kind,
            ReconciliationDecisionKind.RESOLVED_SUCCEEDED,
        )
        self.assertEqual(
            authority.queries,
            [expected_binding],
        )
        self.assertEqual(controlled_service.calls, 0)
        self.assertEqual(decision.original_tool_calls, 0)
        self.assertFalse(decision.durable_transition)

    def test_not_found_stays_pending_and_does_not_become_retry_proof(self) -> None:
        authority = RecordingAuthority(
            result(AuthoritativeOperationStatus.NOT_FOUND)
        )

        decision = ReconciliationScheduler(authority).reconcile_once(
            failure(),
            binding=binding(),
        )

        self.assertEqual(
            decision.kind,
            ReconciliationDecisionKind.STILL_PENDING,
        )
        self.assertFalse(decision.durable_transition)

    def test_authoritative_not_executed_converges_before_retry_policy(self) -> None:
        expected_binding = binding()
        observed_failure = failure()
        authority = RecordingAuthority(
            result(AuthoritativeOperationStatus.NOT_EXECUTED)
        )
        proposal = ReconciliationScheduler(authority).reconcile_once(
            observed_failure,
            binding=expected_binding,
        )
        store = InMemoryReconciliationStore()
        store.add_pending(expected_binding)

        self.assertEqual(
            proposal.kind,
            ReconciliationDecisionKind.RESOLVED_NOT_EXECUTED,
        )
        committed = ReconciliationCommitter(store).commit(
            proposal,
            expected_version=1,
            authorization_valid_at_effect=False,
        )
        retry_evidence = authoritative_not_executed_evidence(
            committed,
            original_failure=observed_failure,
        )
        retry = BoundedRetryPolicy().decide(
            retry_evidence,
            RetryContext(
                now=100.0,
                deadline=110.0,
                retries_used=0,
                max_retries=1,
                caller_intent_active=True,
                authorization_current=True,
                capacity_admitted=True,
                circuit_allows_request=True,
            ),
        )

        self.assertEqual(
            committed.record.business_outcome,
            ReconciledBusinessOutcome.NOT_EXECUTED,
        )
        self.assertEqual(
            committed.record.compliance_outcome,
            ComplianceOutcome.NOT_APPLICABLE,
        )
        self.assertEqual(
            retry_evidence.execution_certainty,
            ExecutionCertainty.PROVEN_NOT_EXECUTED,
        )
        self.assertTrue(retry.eligible)

    def test_not_executed_fact_does_not_override_inactive_caller_intent(self) -> None:
        expected_binding = binding()
        observed_failure = failure()
        proposal = ReconciliationScheduler(
            RecordingAuthority(result(AuthoritativeOperationStatus.NOT_EXECUTED))
        ).reconcile_once(observed_failure, binding=expected_binding)
        store = InMemoryReconciliationStore()
        store.add_pending(expected_binding)
        committed = ReconciliationCommitter(store).commit(
            proposal,
            expected_version=1,
            authorization_valid_at_effect=True,
        )

        retry = BoundedRetryPolicy().decide(
            authoritative_not_executed_evidence(
                committed,
                original_failure=observed_failure,
            ),
            RetryContext(
                now=100.0,
                deadline=110.0,
                retries_used=0,
                max_retries=1,
                caller_intent_active=False,
                authorization_current=True,
                capacity_admitted=True,
                circuit_allows_request=True,
            ),
        )

        self.assertEqual(
            retry.kind,
            RetryDecisionKind.CALLER_INTENT_INACTIVE,
        )
        self.assertFalse(retry.eligible)

    def test_mismatched_authoritative_identity_fails_closed(self) -> None:
        authority = RecordingAuthority(
            result(
                AuthoritativeOperationStatus.SUCCEEDED,
                observed_binding=binding(operation_id="op-other-99"),
                external_object_id="external-report-77",
            )
        )

        decision = ReconciliationScheduler(authority).reconcile_once(
            failure(),
            binding=binding(),
        )

        self.assertEqual(
            decision.kind,
            ReconciliationDecisionKind.EVIDENCE_CONFLICT,
        )
        self.assertFalse(decision.durable_transition)

    def test_proven_not_sent_does_not_enter_reconciliation(self) -> None:
        authority = RecordingAuthority(
            result(AuthoritativeOperationStatus.UNKNOWN)
        )

        decision = ReconciliationScheduler(authority).reconcile_once(
            failure(DispatchCertainty.PROVEN_NOT_SENT),
            binding=binding(),
        )

        self.assertEqual(
            decision.kind,
            ReconciliationDecisionKind.NOT_REQUIRED,
        )
        self.assertEqual(authority.queries, [])

    def test_committer_records_business_success_and_violation_separately(self) -> None:
        expected_binding = binding()
        authority = RecordingAuthority(
            result(
                AuthoritativeOperationStatus.SUCCEEDED,
                external_object_id="external-report-77",
            )
        )
        proposal = ReconciliationScheduler(authority).reconcile_once(
            failure(),
            binding=expected_binding,
        )
        store = InMemoryReconciliationStore()
        store.add_pending(expected_binding)

        committed = ReconciliationCommitter(store).commit(
            proposal,
            expected_version=1,
            authorization_valid_at_effect=False,
        )

        self.assertEqual(committed.outcome, ReconciliationCommitOutcome.COMMITTED)
        self.assertTrue(committed.durable_transition)
        self.assertEqual(
            committed.record.business_outcome,
            ReconciledBusinessOutcome.SUCCEEDED,
        )
        self.assertEqual(
            committed.record.compliance_outcome,
            ComplianceOutcome.AUTHORIZATION_VIOLATION,
        )
        self.assertEqual(committed.record.version, 2)

    def test_stale_version_cannot_commit_reconciliation(self) -> None:
        expected_binding = binding()
        authority = RecordingAuthority(
            result(
                AuthoritativeOperationStatus.SUCCEEDED,
                external_object_id="external-report-77",
            )
        )
        proposal = ReconciliationScheduler(authority).reconcile_once(
            failure(),
            binding=expected_binding,
        )
        store = InMemoryReconciliationStore()
        store.add_pending(expected_binding)

        rejected = ReconciliationCommitter(store).commit(
            proposal,
            expected_version=0,
            authorization_valid_at_effect=True,
        )

        self.assertEqual(
            rejected.outcome,
            ReconciliationCommitOutcome.VERSION_CONFLICT,
        )
        self.assertFalse(rejected.durable_transition)
        self.assertEqual(store.read(expected_binding.operation_id).version, 1)

    def test_cross_tenant_proposal_cannot_commit(self) -> None:
        stored_binding = binding()
        foreign_binding = binding(tenant_id="tenant-b")
        store = InMemoryReconciliationStore()
        store.add_pending(stored_binding)
        authority = RecordingAuthority(
            result(
                AuthoritativeOperationStatus.SUCCEEDED,
                observed_binding=foreign_binding,
                external_object_id="external-report-77",
            )
        )
        proposal = ReconciliationScheduler(authority).reconcile_once(
            failure(),
            binding=foreign_binding,
        )

        rejected = ReconciliationCommitter(store).commit(
            proposal,
            expected_version=1,
            authorization_valid_at_effect=True,
        )

        self.assertEqual(
            rejected.outcome,
            ReconciliationCommitOutcome.BINDING_CONFLICT,
        )
        self.assertFalse(rejected.durable_transition)

    def test_unknown_budget_exhaustion_preserves_pending_and_alerts_once(self) -> None:
        expected_binding = binding()
        authority = RecordingAuthority(
            result(AuthoritativeOperationStatus.UNKNOWN)
        )
        observation = ReconciliationScheduler(authority).reconcile_once(
            failure(),
            binding=expected_binding,
        )
        alerts = RecordingAlerts()
        state = ReconciliationScheduleState(
            expected_binding,
            queries_used=1,
            maximum_queries=2,
            deadline=200.0,
        )
        policy = BoundedReconciliationPolicy(jitter_ratio=0.0)

        exhausted = policy.advance(
            observation,
            state,
            now=100.0,
            operation_ref="opref-safe-42",
            alerts=alerts,
        )
        repeated = policy.advance(
            observation,
            exhausted.state,
            now=101.0,
            operation_ref="opref-safe-42",
            alerts=alerts,
        )

        self.assertEqual(
            exhausted.outcome,
            ReconciliationScheduleOutcome.OPERATIONAL_ALERT_REQUIRED,
        )
        self.assertTrue(exhausted.state.pending_reconciliation)
        self.assertTrue(exhausted.state.alert_emitted)
        self.assertEqual(exhausted.original_tool_calls, 0)
        self.assertFalse(exhausted.durable_transition)
        self.assertEqual(repeated.outcome, ReconciliationScheduleOutcome.ALREADY_ALERTED)
        self.assertEqual(len(alerts.items), 1)

    def test_unknown_with_budget_schedules_deterministic_next_query(self) -> None:
        expected_binding = binding()
        observation = ReconciliationScheduler(
            RecordingAuthority(result(AuthoritativeOperationStatus.NOT_FOUND))
        ).reconcile_once(failure(), binding=expected_binding)
        alerts = RecordingAlerts()
        state = ReconciliationScheduleState(
            expected_binding,
            queries_used=0,
            maximum_queries=3,
            deadline=200.0,
        )
        policy = BoundedReconciliationPolicy(
            base_delay_seconds=1.0,
            jitter_ratio=0.0,
        )

        scheduled = policy.advance(
            observation,
            state,
            now=100.0,
            operation_ref="opref-safe-42",
            alerts=alerts,
        )

        self.assertEqual(
            scheduled.outcome,
            ReconciliationScheduleOutcome.NEXT_QUERY_SCHEDULED,
        )
        self.assertEqual(scheduled.state.next_query_at, 101.0)
        self.assertTrue(scheduled.state.pending_reconciliation)
        self.assertEqual(alerts.items, [])


if __name__ == "__main__":
    unittest.main()
