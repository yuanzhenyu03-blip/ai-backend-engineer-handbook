"""Day93 late-response correlation, validation and commit tests."""
import unittest

from mcp_late_response import (
    LateResponseOutcome,
    LateSuccessCandidate,
    validate_late_success,
)
from mcp_reconciliation import (
    ApplicationOperationBinding,
    InMemoryReconciliationStore,
    ReconciliationCommitOutcome,
    ReconciliationCommitter,
)
from mcp_remote_session import (
    RemoteRequestBinding,
    RemoteRequestKey,
    RemoteResponseCorrelation,
    RemoteResponseCorrelationOutcome,
)


def binding(tenant_id: str = "tenant-a") -> ApplicationOperationBinding:
    return ApplicationOperationBinding(
        "op-report-42",
        "idem-report-42",
        tenant_id,
        "research-report-42",
    )


def correlation(
    outcome: RemoteResponseCorrelationOutcome = (
        RemoteResponseCorrelationOutcome.MATCHED
    ),
) -> RemoteResponseCorrelation:
    return RemoteResponseCorrelation(
        outcome,
        RemoteRequestBinding(
            RemoteRequestKey(2, "mcp-request-93-1"),
            "op-report-42",
            "idem-report-42",
            1,
        ),
    )


def candidate(
    *,
    observed_binding: ApplicationOperationBinding | None = None,
    protocol_schema_valid: bool = True,
    application_output_valid: bool = True,
) -> LateSuccessCandidate:
    return LateSuccessCandidate(
        observed_binding or binding(),
        "external-report-77",
        protocol_schema_valid,
        application_output_valid,
        "late-correlated-mcp-response",
    )


class Day93MCPLateResponseTests(unittest.TestCase):
    def test_valid_late_response_is_proposal_then_committer_cas(self) -> None:
        authoritative = binding()
        validated = validate_late_success(
            correlation(),
            authoritative_binding=authoritative,
            candidate=candidate(),
        )

        self.assertEqual(validated.outcome, LateResponseOutcome.PROPOSAL_READY)
        self.assertEqual(validated.committer_calls, 0)
        self.assertFalse(validated.durable_transition)

        store = InMemoryReconciliationStore()
        store.add_pending(authoritative)
        committed = ReconciliationCommitter(store).commit(
            validated.proposal,
            expected_version=1,
            authorization_valid_at_effect=True,
        )

        self.assertEqual(committed.outcome, ReconciliationCommitOutcome.COMMITTED)
        self.assertTrue(committed.durable_transition)

    def test_cross_tenant_late_response_cannot_create_proposal(self) -> None:
        decision = validate_late_success(
            correlation(),
            authoritative_binding=binding(),
            candidate=candidate(observed_binding=binding("tenant-b")),
        )

        self.assertEqual(decision.outcome, LateResponseOutcome.BINDING_CONFLICT)
        self.assertIsNone(decision.proposal)
        self.assertEqual(decision.committer_calls, 0)

    def test_stale_generation_response_cannot_create_proposal(self) -> None:
        decision = validate_late_success(
            correlation(RemoteResponseCorrelationOutcome.STALE_GENERATION),
            authoritative_binding=binding(),
            candidate=candidate(),
        )

        self.assertEqual(
            decision.outcome,
            LateResponseOutcome.CORRELATION_REJECTED,
        )
        self.assertIsNone(decision.proposal)

    def test_invalid_application_output_cannot_create_proposal(self) -> None:
        decision = validate_late_success(
            correlation(),
            authoritative_binding=binding(),
            candidate=candidate(application_output_valid=False),
        )

        self.assertEqual(decision.outcome, LateResponseOutcome.OUTPUT_REJECTED)
        self.assertIsNone(decision.proposal)


if __name__ == "__main__":
    unittest.main()
