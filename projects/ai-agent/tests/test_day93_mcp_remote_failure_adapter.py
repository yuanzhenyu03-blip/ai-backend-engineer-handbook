"""Day93 tests for trusted conversion of remote rejection claims."""
import unittest

from mcp_client_transport import DispatchCertainty
from mcp_remote_failure_adapter import (
    ApplicationRemoteFailureAdapter,
    AuthenticatedRemoteContext,
    ControlledRemoteFailureContract,
    RemoteFailureClaim,
    RemoteFailureMappingOutcome,
)
from mcp_remote_lifecycle import ExecutionCertainty
from mcp_remote_protection import reject_local_circuit_open
from mcp_remote_session import (
    RemoteRequestBinding,
    RemoteRequestKey,
    RemoteResponseCorrelation,
    RemoteResponseCorrelationOutcome,
)
from mcp_retry_policy import BoundedRetryPolicy, RetryContext


def matched_correlation() -> RemoteResponseCorrelation:
    return RemoteResponseCorrelation(
        RemoteResponseCorrelationOutcome.MATCHED,
        RemoteRequestBinding(
            RemoteRequestKey(2, "mcp-request-93-2"),
            "op-report-42",
            "idem-report-42",
            2,
        ),
    )


def retry_context() -> RetryContext:
    return RetryContext(
        now=100.0,
        deadline=110.0,
        retries_used=0,
        max_retries=2,
        caller_intent_active=True,
        authorization_current=True,
        capacity_admitted=True,
        circuit_allows_request=True,
    )


class Day93MCPRemoteFailureAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = ApplicationRemoteFailureAdapter(
            ControlledRemoteFailureContract("research-mcp.internal")
        )
        self.claim = RemoteFailureClaim(503, "CAPACITY_REJECTED")

    def test_verified_contract_maps_to_proven_not_executed(self) -> None:
        mapped = self.adapter.translate(
            self.claim,
            context=AuthenticatedRemoteContext(
                "research-mcp.internal",
                identity_verified=True,
            ),
            correlation=matched_correlation(),
        )

        self.assertEqual(
            mapped.outcome,
            RemoteFailureMappingOutcome.VERIFIED_PRE_HANDLER_REJECTION,
        )
        self.assertEqual(
            mapped.evidence.execution_certainty,
            ExecutionCertainty.PROVEN_NOT_EXECUTED,
        )
        self.assertTrue(
            BoundedRetryPolicy().decide(
                mapped.evidence,
                retry_context(),
            ).eligible
        )

    def test_unverified_server_cannot_self_assert_no_execution(self) -> None:
        mapped = self.adapter.translate(
            self.claim,
            context=AuthenticatedRemoteContext(
                "attacker.example",
                identity_verified=False,
            ),
            correlation=matched_correlation(),
        )

        self.assertEqual(
            mapped.outcome,
            RemoteFailureMappingOutcome.UNVERIFIED_REMOTE_CLAIM,
        )
        self.assertEqual(
            mapped.evidence.execution_certainty,
            ExecutionCertainty.POSSIBLY_EXECUTED,
        )
        self.assertFalse(
            BoundedRetryPolicy().decide(
                mapped.evidence,
                retry_context(),
            ).eligible
        )

    def test_stale_response_cannot_create_failure_evidence_for_new_attempt(self) -> None:
        stale = RemoteResponseCorrelation(
            RemoteResponseCorrelationOutcome.STALE_GENERATION,
            matched_correlation().binding,
        )

        mapped = self.adapter.translate(
            self.claim,
            context=AuthenticatedRemoteContext(
                "research-mcp.internal",
                identity_verified=True,
            ),
            correlation=stale,
        )

        self.assertEqual(
            mapped.outcome,
            RemoteFailureMappingOutcome.CORRELATION_REJECTED,
        )
        self.assertIsNone(mapped.evidence)
        self.assertEqual(mapped.controlled_service_calls, 0)
        self.assertEqual(mapped.committer_calls, 0)

    def test_local_circuit_open_is_proven_not_sent_and_not_executed(self) -> None:
        rejected = reject_local_circuit_open(
            operation_id="op-report-42",
            idempotency_key="idem-report-42",
            protocol_request_id="mcp-request-93-2",
            attempt_number=2,
        )

        self.assertEqual(
            rejected.evidence.dispatch_certainty,
            DispatchCertainty.PROVEN_NOT_SENT,
        )
        self.assertEqual(
            rejected.evidence.execution_certainty,
            ExecutionCertainty.PROVEN_NOT_EXECUTED,
        )
        self.assertEqual(rejected.transport_calls, 0)
        self.assertEqual(rejected.handler_calls, 0)
        self.assertEqual(rejected.controlled_service_calls, 0)

    def test_trusted_server_circuit_open_is_sent_but_not_executed(self) -> None:
        mapped = self.adapter.translate(
            RemoteFailureClaim(503, "CIRCUIT_OPEN"),
            context=AuthenticatedRemoteContext(
                "research-mcp.internal",
                identity_verified=True,
            ),
            correlation=matched_correlation(),
        )

        self.assertEqual(
            mapped.evidence.dispatch_certainty,
            DispatchCertainty.PROVEN_SENT,
        )
        self.assertEqual(
            mapped.evidence.execution_certainty,
            ExecutionCertainty.PROVEN_NOT_EXECUTED,
        )
        self.assertEqual(mapped.controlled_service_calls, 0)


if __name__ == "__main__":
    unittest.main()
