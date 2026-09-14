"""Day91 tests for shutdown admission, draining and reconciliation."""
import unittest

from mcp_server_lifecycle import (
    DrainOutcome,
    MCPServerLifecycle,
    RequestAdmissionOutcome,
    ServerLifecycleState,
)


class RecordingCancellation:
    def __init__(self) -> None:
        self.operation_ids: list[str] = []

    def cancel(self, operation_id: str) -> None:
        self.operation_ids.append(operation_id)


class RecordingReconciliation:
    def __init__(self) -> None:
        self.operation_ids: list[str] = []

    def mark_pending(self, operation_id: str) -> None:
        self.operation_ids.append(operation_id)


class Day91MCPServerLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cancellation = RecordingCancellation()
        self.reconciliation = RecordingReconciliation()
        self.lifecycle = MCPServerLifecycle(
            cancellation=self.cancellation,
            reconciliation=self.reconciliation,
        )

    def test_shutdown_closes_admission_before_drain(self) -> None:
        admitted = self.lifecycle.begin_request("operation-in-flight")

        self.lifecycle.start_shutdown()
        rejected = self.lifecycle.begin_request("operation-too-late")

        self.assertEqual(admitted.outcome, RequestAdmissionOutcome.ADMITTED)
        self.assertEqual(
            rejected.outcome,
            RequestAdmissionOutcome.SHUTDOWN_REJECTED,
        )
        self.assertEqual(
            self.lifecycle.in_flight_operation_ids,
            ("operation-in-flight",),
        )
        self.assertEqual(self.lifecycle.state, ServerLifecycleState.DRAINING)

    def test_completed_handlers_produce_clean_drain(self) -> None:
        self.lifecycle.begin_request("operation-completed")
        self.lifecycle.start_shutdown()
        self.assertTrue(self.lifecycle.complete_request("operation-completed"))

        report = self.lifecycle.finish_clean_drain()

        self.assertEqual(report.outcome, DrainOutcome.CLEAN)
        self.assertEqual(report.pending_operation_ids, ())
        self.assertEqual(self.cancellation.operation_ids, [])
        self.assertEqual(self.reconciliation.operation_ids, [])
        self.assertEqual(self.lifecycle.state, ServerLifecycleState.STOPPED)

    def test_timeout_cancels_and_preserves_operation_ids_for_reconciliation(self) -> None:
        self.lifecycle.begin_request("operation-2")
        self.lifecycle.begin_request("operation-1")
        self.lifecycle.start_shutdown()

        report = self.lifecycle.expire_drain_timeout()

        self.assertEqual(report.outcome, DrainOutcome.PENDING_RECONCILIATION)
        self.assertEqual(
            report.pending_operation_ids,
            ("operation-1", "operation-2"),
        )
        self.assertEqual(
            self.cancellation.operation_ids,
            ["operation-1", "operation-2"],
        )
        self.assertEqual(
            self.reconciliation.operation_ids,
            ["operation-1", "operation-2"],
        )
        self.assertEqual(self.lifecycle.state, ServerLifecycleState.STOPPED)

    def test_late_completion_cannot_erase_pending_reconciliation(self) -> None:
        self.lifecycle.begin_request("operation-unknown")
        self.lifecycle.start_shutdown()
        self.lifecycle.expire_drain_timeout()

        completed = self.lifecycle.complete_request("operation-unknown")

        self.assertFalse(completed)
        self.assertEqual(
            self.reconciliation.operation_ids,
            ["operation-unknown"],
        )


if __name__ == "__main__":
    unittest.main()
