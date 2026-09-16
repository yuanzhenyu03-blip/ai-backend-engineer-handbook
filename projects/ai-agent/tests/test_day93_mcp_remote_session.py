"""Day93 reconnect and response-correlation tests."""
import unittest

from mcp_remote_session import (
    RemoteCorrelationRegistry,
    RemoteRequestBinding,
    RemoteRequestKey,
    RemoteResponseCorrelationOutcome,
)


def binding(
    generation: int,
    *,
    operation_id: str,
    attempt_number: int,
) -> RemoteRequestBinding:
    return RemoteRequestBinding(
        RemoteRequestKey(generation, "mcp-request-shared"),
        operation_id,
        f"idem-{operation_id}",
        attempt_number,
    )


class Day93MCPRemoteSessionTests(unittest.TestCase):
    def test_late_old_response_cannot_complete_new_generation_request(self) -> None:
        registry = RemoteCorrelationRegistry()
        old_generation = registry.begin_generation()
        old_binding = binding(
            old_generation,
            operation_id="op-old-42",
            attempt_number=1,
        )
        registry.bind(old_binding)
        new_generation = registry.begin_generation()
        new_binding = binding(
            new_generation,
            operation_id="op-new-77",
            attempt_number=1,
        )
        registry.bind(new_binding)

        stale = registry.correlate_response(old_binding.key)
        current = registry.correlate_response(new_binding.key)

        self.assertEqual(
            stale.outcome,
            RemoteResponseCorrelationOutcome.STALE_GENERATION,
        )
        self.assertEqual(stale.binding.operation_id, "op-old-42")
        self.assertEqual(stale.committer_calls, 0)
        self.assertEqual(stale.controlled_service_calls, 0)
        self.assertEqual(
            current.outcome,
            RemoteResponseCorrelationOutcome.MATCHED,
        )
        self.assertEqual(current.binding.operation_id, "op-new-77")

    def test_protocol_request_id_alone_is_not_a_unique_key(self) -> None:
        old = RemoteRequestKey(1, "mcp-request-shared")
        new = RemoteRequestKey(2, "mcp-request-shared")

        self.assertNotEqual(old, new)

    def test_duplicate_response_is_observed_without_second_commit(self) -> None:
        registry = RemoteCorrelationRegistry()
        generation = registry.begin_generation()
        request = binding(
            generation,
            operation_id="op-report-42",
            attempt_number=1,
        )
        registry.bind(request)

        first = registry.correlate_response(request.key)
        duplicate = registry.correlate_response(request.key)

        self.assertEqual(
            first.outcome,
            RemoteResponseCorrelationOutcome.MATCHED,
        )
        self.assertEqual(
            duplicate.outcome,
            RemoteResponseCorrelationOutcome.ALREADY_COMPLETED,
        )
        self.assertEqual(duplicate.committer_calls, 0)


if __name__ == "__main__":
    unittest.main()
