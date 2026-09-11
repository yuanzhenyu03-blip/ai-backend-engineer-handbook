"""First Day90 tests for codec, identity isolation and send certainty."""
import json
import unittest

from mcp_client import DependencyFreeMCPClientAdapter
from mcp_client_codec import MCPCodecError, MCPWireCodec
from mcp_client_transport import (
    DispatchCertainty,
    MCPTransportFailure,
)
from mcp_protocol_model import (
    BindingStatus,
    CURRENT_SPECIFICATION_VERSION,
    ExternalContentCandidate,
    ExternalContentKind,
    MCPProtocolBoundary,
    MCPRequestBinding,
    MCPRequestDTO,
    OutputValidationOutcome,
    ProtocolOutcome,
    validate_read_resource_content,
)


def request() -> MCPRequestDTO:
    return MCPRequestDTO(
        specification_version=CURRENT_SPECIFICATION_VERSION,
        protocol_request_id="mcp-request-8",
        method="tools/call",
        params={
            "name": "research.lookup",
            "arguments": {"query": "MCP client boundary"},
        },
        client_capabilities=frozenset({"tools"}),
        observed_server_capabilities=frozenset({"tools"}),
    )


def binding() -> MCPRequestBinding:
    return MCPRequestBinding(
        protocol_request_id="mcp-request-8",
        application_operation_id="op-report-42",
        expected_method="tools/call",
        request_fingerprint="request-fingerprint-8",
        tenant_id="tenant-a",
        resource_id="report-42",
        idempotency_key="idem-report-42",
    )


class RecordingTransport:
    def __init__(self, response: bytes) -> None:
        self.response = response
        self.messages: list[bytes] = []

    def exchange(self, message: bytes) -> bytes:
        self.messages.append(message)
        return self.response


class FailingTransport:
    def __init__(self, certainty: DispatchCertainty) -> None:
        self.certainty = certainty
        self.messages: list[bytes] = []

    def exchange(self, message: bytes) -> bytes:
        self.messages.append(message)
        raise MCPTransportFailure(
            "transport timeout",
            dispatch_certainty=self.certainty,
        )


class Day90MCPClientTests(unittest.TestCase):
    def test_codec_serializes_current_per_request_metadata(self) -> None:
        encoded = MCPWireCodec().encode_request(request())
        message = json.loads(encoded)

        self.assertEqual(message["jsonrpc"], "2.0")
        self.assertEqual(message["id"], "mcp-request-8")
        self.assertEqual(
            message["params"]["_meta"][
                "io.modelcontextprotocol/protocolVersion"
            ],
            CURRENT_SPECIFICATION_VERSION,
        )
        self.assertEqual(
            message["params"]["_meta"][
                "io.modelcontextprotocol/clientCapabilities"
            ],
            {"tools": {}},
        )
        self.assertNotIn("application_operation_id", encoded.decode())

    def test_adapter_returns_dto_before_application_correlation(self) -> None:
        transport = RecordingTransport(
            b'{"jsonrpc":"2.0","id":"mcp-request-8",'
            b'"result":{"documents":[]}}'
        )

        exchange = DependencyFreeMCPClientAdapter(transport).exchange(
            request(), binding()
        )

        self.assertIsNotNone(exchange.response)
        self.assertIsNone(exchange.observation)
        assert exchange.response is not None
        self.assertEqual(
            exchange.response.protocol_request_id,
            "mcp-request-8",
        )

    def test_possible_send_timeout_preserves_unknown_outcome(self) -> None:
        transport = FailingTransport(DispatchCertainty.POSSIBLY_SENT)

        exchange = DependencyFreeMCPClientAdapter(transport).exchange(
            request(), binding()
        )

        assert exchange.observation is not None
        self.assertEqual(
            exchange.observation.outcome,
            ProtocolOutcome.OUTCOME_UNKNOWN,
        )
        self.assertEqual(
            exchange.observation.application_operation_id,
            "op-report-42",
        )
        self.assertFalse(exchange.observation.durable_transition)

    def test_only_explicit_not_sent_evidence_is_pre_send_failure(self) -> None:
        transport = FailingTransport(DispatchCertainty.PROVEN_NOT_SENT)

        exchange = DependencyFreeMCPClientAdapter(transport).exchange(
            request(), binding()
        )

        assert exchange.observation is not None
        self.assertEqual(
            exchange.observation.outcome,
            ProtocolOutcome.PRE_DISPATCH_ABORTED,
        )

    def test_binding_mismatch_stops_before_transport(self) -> None:
        transport = RecordingTransport(b"not used")
        wrong_binding = MCPRequestBinding(
            protocol_request_id="mcp-request-other",
            application_operation_id="op-report-42",
            expected_method="tools/call",
            request_fingerprint="other",
        )

        with self.assertRaisesRegex(ValueError, "local binding"):
            DependencyFreeMCPClientAdapter(transport).exchange(
                request(), wrong_binding
            )

        self.assertEqual(transport.messages, [])

    def test_codec_rejects_response_without_exact_result_or_error(self) -> None:
        payload = b'{"jsonrpc":"2.0","id":"mcp-request-8"}'

        with self.assertRaisesRegex(MCPCodecError, "exactly one"):
            MCPWireCodec().decode_response(payload)

    def test_post_dispatch_cancellation_requires_reconciliation(self) -> None:
        local_binding = binding()
        boundary = MCPProtocolBoundary(transport=object())  # type: ignore[arg-type]
        boundary.bindings[local_binding.protocol_request_id] = local_binding
        boundary.binding_status[local_binding.protocol_request_id] = (
            BindingStatus.PENDING
        )

        observation = boundary.mark_outcome_unknown(
            local_binding.protocol_request_id,
            reason="caller cancelled after dispatch began",
        )

        self.assertEqual(observation.outcome, ProtocolOutcome.OUTCOME_UNKNOWN)
        self.assertEqual(
            boundary.binding_status[local_binding.protocol_request_id],
            BindingStatus.PENDING_RECONCILIATION,
        )
        self.assertFalse(observation.durable_transition)

        impossible_abort = boundary.abort_before_dispatch(
            local_binding.protocol_request_id,
            reason="cannot rewrite post-dispatch uncertainty",
        )
        self.assertEqual(impossible_abort.outcome, ProtocolOutcome.CONFLICT)

    def test_rejected_post_read_content_still_counts_the_read(self) -> None:
        local_binding = binding()
        candidate = ExternalContentCandidate(
            ExternalContentKind.RESOURCE,
            "research://tenant-a/report-42",
            tenant_id="tenant-a",
            resource_id="report-42",
            injection_suspected=True,
        )

        decision = validate_read_resource_content(
            local_binding,
            candidate,
        )

        self.assertEqual(
            decision.outcome,
            OutputValidationOutcome.INDIRECT_PROMPT_INJECTION,
        )
        self.assertEqual(decision.resource_reads, 1)
        self.assertEqual(decision.policy_mutations, 0)
        self.assertFalse(decision.durable_transition)


if __name__ == "__main__":
    unittest.main()
