"""Day93 credential-safe logs, bounded metrics and diagnostic traces."""
import unittest

from mcp_client_transport import DispatchCertainty
from mcp_observability import (
    BoundedMetricRecorder,
    OperationRefEncoder,
    SafeTraceCorrelation,
    lifecycle_failure_log,
)
from mcp_remote_lifecycle import (
    ExecutionCertainty,
    FailureEvidence,
    FailureKind,
    FailurePhase,
)


RAW_OPERATION_ID = "op-report-42"
CONTROLLED_RAW_CREDENTIAL = "controlled-sensitive-credential-value"


def evidence() -> FailureEvidence:
    return FailureEvidence(
        operation_id=RAW_OPERATION_ID,
        idempotency_key="idem-report-42",
        protocol_request_id="mcp-request-93-1",
        attempt_number=1,
        phase=FailurePhase.READ,
        kind=FailureKind.READ_TIMEOUT,
        dispatch_certainty=DispatchCertainty.POSSIBLY_SENT,
        execution_certainty=ExecutionCertainty.POSSIBLY_EXECUTED,
        evidence_source="mcp-sdk-2.2.0-dispatcher",
    )


class Day93MCPObservabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.encoder = OperationRefEncoder(b"day93-test-key-material")

    def test_structured_log_uses_hmac_ref_and_has_no_credential_slot(self) -> None:
        encoded = lifecycle_failure_log(
            evidence(),
            encoder=self.encoder,
            transport_generation=2,
        ).to_json()

        self.assertNotIn(RAW_OPERATION_ID, encoded)
        self.assertNotIn("idempotency", encoded.lower())
        self.assertNotIn("authorization", encoded.lower())
        self.assertNotIn(CONTROLLED_RAW_CREDENTIAL, encoded)
        self.assertIn("opref-", encoded)

    def test_operation_ref_is_stable_and_keyed(self) -> None:
        first = self.encoder.encode(RAW_OPERATION_ID)
        repeated = self.encoder.encode(RAW_OPERATION_ID)
        other_key = OperationRefEncoder(
            b"different-test-key-material"
        ).encode(RAW_OPERATION_ID)

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, other_key)

    def test_metric_rejects_operation_ref_even_when_pseudonymous(self) -> None:
        metrics = BoundedMetricRecorder()

        with self.assertRaisesRegex(ValueError, "high-cardinality"):
            metrics.increment(
                "mcp_remote_failures_total",
                {"operation_ref": self.encoder.encode(RAW_OPERATION_ID)},
            )

    def test_metric_accepts_only_bounded_failure_dimensions(self) -> None:
        metrics = BoundedMetricRecorder()
        labels = {
            "phase": "READ",
            "failure_kind": "READ_TIMEOUT",
            "execution_certainty": "POSSIBLY_EXECUTED",
            "transport": "streamable_http",
        }

        metrics.increment("mcp_remote_failures_total", labels)

        self.assertEqual(
            metrics.value("mcp_remote_failures_total", labels),
            1,
        )

    def test_trace_correlates_but_cannot_be_authority(self) -> None:
        trace = SafeTraceCorrelation(
            trace_id="trace-93-1",
            operation_ref=self.encoder.encode(RAW_OPERATION_ID),
            transport_generation=2,
        )

        self.assertFalse(trace.authority_evidence)
        with self.assertRaisesRegex(ValueError, "authority"):
            SafeTraceCorrelation(
                trace_id="trace-93-2",
                operation_ref=trace.operation_ref,
                transport_generation=2,
                authority_evidence=True,
            )


if __name__ == "__main__":
    unittest.main()
