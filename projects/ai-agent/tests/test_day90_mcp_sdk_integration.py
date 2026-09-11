"""Day90 real-SDK integration test over a separate stdio server process."""
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from mcp import StdioServerParameters

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
    validate_external_content_candidate,
)
from mcp_sdk_private_adapter import (
    CapabilityEvidenceError,
    SDKPrivateMCPClientAdapter,
    ToolInputValidationError,
)


FIXTURE = Path(__file__).parent / "fixtures" / "day90_mcp_stdio_server.py"


class Day90SDKStdioIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_persisted_request_id_reaches_separate_sdk_server(self) -> None:
        request_id = "day90-bound-request-001"
        request = MCPRequestDTO(
            specification_version=CURRENT_SPECIFICATION_VERSION,
            protocol_request_id=request_id,
            method="tools/call",
            params={
                "name": "research.lookup",
                "arguments": {"query": "durable binding before dispatch"},
            },
            client_capabilities=frozenset({"tools"}),
            observed_server_capabilities=frozenset({"tools"}),
        )
        binding = MCPRequestBinding(
            protocol_request_id=request_id,
            application_operation_id="application-operation-001",
            expected_method="tools/call",
            request_fingerprint="fixture-fingerprint-001",
            tenant_id="tenant-a",
            resource_id="report-001",
            idempotency_key="tool-idempotency-001",
        )
        server = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURE)],
        )

        async with SDKPrivateMCPClientAdapter(server) as adapter:
            preflight_permit = adapter.issue_preflight_permit(
                "tools/call",
                tool_name="research.lookup",
                arguments={"query": "durable binding before dispatch"},
            )
            exchange = await adapter.exchange(
                request,
                binding,
                preflight_permit,
            )

        self.assertIsNone(exchange.observation)
        self.assertIsNotNone(exchange.response)
        assert exchange.response is not None
        self.assertEqual(exchange.response.protocol_request_id, request_id)
        assert exchange.response.result is not None
        self.assertEqual(
            exchange.response.result["structuredContent"][
                "observed_protocol_request_id"
            ],
            request_id,
        )

    async def test_tool_level_error_is_still_a_protocol_result(self) -> None:
        request_id = "day90-tool-error-001"
        request = MCPRequestDTO(
            specification_version=CURRENT_SPECIFICATION_VERSION,
            protocol_request_id=request_id,
            method="tools/call",
            params={
                "name": "research.reject",
                "arguments": {"reason": "bounded input rejected"},
            },
            client_capabilities=frozenset({"tools"}),
            observed_server_capabilities=frozenset({"tools"}),
        )
        binding = MCPRequestBinding(
            protocol_request_id=request_id,
            application_operation_id="application-operation-error-001",
            expected_method="tools/call",
            request_fingerprint="fixture-fingerprint-error-001",
        )
        server = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURE)],
        )

        async with SDKPrivateMCPClientAdapter(server) as adapter:
            preflight_permit = adapter.issue_preflight_permit(
                "tools/call",
                tool_name="research.reject",
                arguments={"reason": "bounded input rejected"},
            )
            exchange = await adapter.exchange(
                request,
                binding,
                preflight_permit,
            )

        assert exchange.response is not None
        assert exchange.response.result is not None
        self.assertTrue(exchange.response.result["isError"])

        boundary = MCPProtocolBoundary(transport=object())  # type: ignore[arg-type]
        boundary.bindings[request_id] = binding
        boundary.binding_status[request_id] = BindingStatus.PENDING
        observation = boundary.correlate(exchange.response)

        self.assertEqual(observation.outcome, ProtocolOutcome.PROTOCOL_RESULT)
        self.assertTrue(observation.payload["isError"])
        self.assertFalse(observation.durable_transition)

    async def test_resource_read_follows_application_scope_admission(self) -> None:
        request_id = "day90-resource-request-001"
        binding = MCPRequestBinding(
            protocol_request_id=request_id,
            application_operation_id="application-resource-operation-001",
            expected_method="resources/read",
            request_fingerprint="resource-fingerprint-001",
            tenant_id="tenant-a",
            resource_id="report-42",
        )
        candidate = ExternalContentCandidate(
            ExternalContentKind.RESOURCE,
            "research://tenant-a/report-42",
            tenant_id="tenant-a",
            resource_id="report-42",
        )
        admission = validate_external_content_candidate(binding, candidate)
        self.assertEqual(
            admission.outcome,
            OutputValidationOutcome.REFERENCE_ADMITTED,
        )
        request = MCPRequestDTO(
            specification_version=CURRENT_SPECIFICATION_VERSION,
            protocol_request_id=request_id,
            method="resources/read",
            params={"uri": candidate.source_id},
            client_capabilities=frozenset({"resources"}),
            observed_server_capabilities=frozenset({"resources"}),
        )
        server = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURE)],
        )

        async with SDKPrivateMCPClientAdapter(server) as adapter:
            permit = adapter.issue_preflight_permit(
                "resources/read",
                resource_uri=candidate.source_id,
            )
            exchange = await adapter.exchange(request, binding, permit)

        self.assertIsNone(exchange.observation)
        assert exchange.response is not None
        assert exchange.response.result is not None
        self.assertIn("contents", exchange.response.result)

    async def test_prompt_get_returns_dto_without_role_escalation(self) -> None:
        request_id = "day90-prompt-request-001"
        request = MCPRequestDTO(
            specification_version=CURRENT_SPECIFICATION_VERSION,
            protocol_request_id=request_id,
            method="prompts/get",
            params={
                "name": "summarize-research",
                "arguments": {"style": "brief"},
            },
            client_capabilities=frozenset({"prompts"}),
            observed_server_capabilities=frozenset({"prompts"}),
        )
        binding = MCPRequestBinding(
            protocol_request_id=request_id,
            application_operation_id="application-prompt-operation-001",
            expected_method="prompts/get",
            request_fingerprint="prompt-fingerprint-001",
        )
        server = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURE)],
        )

        async with SDKPrivateMCPClientAdapter(server) as adapter:
            permit = adapter.issue_preflight_permit(
                "prompts/get",
                prompt_name="summarize-research",
                prompt_arguments={"style": "brief"},
            )
            exchange = await adapter.exchange(request, binding, permit)

        self.assertIsNone(exchange.observation)
        assert exchange.response is not None
        assert exchange.response.result is not None
        self.assertEqual(
            exchange.response.result["messages"][0]["role"],
            "user",
        )

    async def test_missing_discovery_evidence_rejects_pre_attempt(self) -> None:
        server = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURE)],
        )

        async with SDKPrivateMCPClientAdapter(server) as adapter:
            self.assertIn("tools", adapter.observed_server_capabilities)
            # Model an authenticated discovery snapshot in which the current
            # connection did not provide tools capability evidence.  This is
            # intentionally adapter-owned state, not a caller-controlled DTO.
            adapter._observed_server_capabilities = frozenset()
            with self.assertRaisesRegex(
                CapabilityEvidenceError,
                "not observed on this connection",
            ):
                adapter.issue_preflight_permit("tools/call")

    async def test_unlisted_tool_rejects_pre_attempt(self) -> None:
        server = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURE)],
        )

        async with SDKPrivateMCPClientAdapter(server) as adapter:
            self.assertIn("research.lookup", adapter.observed_tool_names)
            self.assertNotIn("research.missing", adapter.observed_tool_names)
            with self.assertRaisesRegex(
                CapabilityEvidenceError,
                "Tool not observed",
            ):
                adapter.issue_preflight_permit(
                    "tools/call", tool_name="research.missing"
                )

    async def test_invalid_tool_arguments_reject_pre_attempt(self) -> None:
        server = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURE)],
        )

        async with SDKPrivateMCPClientAdapter(server) as adapter:
            with self.assertRaisesRegex(
                ToolInputValidationError,
                "do not match input schema",
            ):
                adapter.issue_preflight_permit(
                    "tools/call",
                    tool_name="research.lookup",
                    arguments={"query": 42},
                )

    async def test_invalid_sdk_result_stops_before_application_dto(self) -> None:
        request_id = "request-invalid-sdk-result"
        request = MCPRequestDTO(
            specification_version=CURRENT_SPECIFICATION_VERSION,
            protocol_request_id=request_id,
            method="tools/call",
            params={
                "name": "research.lookup",
                "arguments": {"query": "malformed result"},
            },
            client_capabilities=frozenset({"tools"}),
            observed_server_capabilities=frozenset({"tools"}),
        )
        binding = MCPRequestBinding(
            protocol_request_id=request_id,
            application_operation_id="operation-invalid-sdk-result",
            expected_method="tools/call",
            request_fingerprint="fingerprint-invalid-sdk-result",
        )
        server = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURE)],
        )

        async with SDKPrivateMCPClientAdapter(server) as adapter:
            preflight_permit = adapter.issue_preflight_permit(
                "tools/call",
                tool_name="research.lookup",
                arguments={"query": "malformed result"},
            )
            malformed_result = AsyncMock(
                return_value={"content": "not-a-content-list"}
            )
            with patch.object(
                adapter._client.session._dispatcher,
                "send_raw_request",
                new=malformed_result,
            ):
                exchange = await adapter.exchange(
                    request,
                    binding,
                    preflight_permit,
                )

        self.assertIsNone(exchange.response)
        self.assertIsNotNone(exchange.observation)
        assert exchange.observation is not None
        self.assertEqual(
            exchange.observation.outcome,
            ProtocolOutcome.INVALID_MESSAGE,
        )
        self.assertEqual(
            exchange.observation.application_operation_id,
            "operation-invalid-sdk-result",
        )
        self.assertIsNone(exchange.observation.payload)
        self.assertFalse(exchange.observation.durable_transition)

    async def test_list_changed_invalidates_old_preflight_permit(self) -> None:
        request = MCPRequestDTO(
            specification_version=CURRENT_SPECIFICATION_VERSION,
            protocol_request_id="request-stale-inventory",
            method="tools/call",
            params={
                "name": "research.lookup",
                "arguments": {"query": "stale inventory"},
            },
            client_capabilities=frozenset({"tools"}),
            observed_server_capabilities=frozenset({"tools"}),
        )
        binding = MCPRequestBinding(
            protocol_request_id="request-stale-inventory",
            application_operation_id="operation-stale-inventory",
            expected_method="tools/call",
            request_fingerprint="fingerprint-stale-inventory",
        )
        server = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURE)],
        )

        async with SDKPrivateMCPClientAdapter(server) as adapter:
            preflight_permit = adapter.issue_preflight_permit(
                "tools/call",
                tool_name="research.lookup",
                arguments={"query": "stale inventory"},
            )
            adapter.note_tools_list_changed()

            with self.assertRaisesRegex(
                CapabilityEvidenceError,
                "Tool not observed|stale",
            ):
                await adapter.exchange(request, binding, preflight_permit)

            boundary = MCPProtocolBoundary(transport=object())  # type: ignore[arg-type]
            boundary.bindings[request.protocol_request_id] = binding
            boundary.binding_status[request.protocol_request_id] = (
                BindingStatus.PENDING
            )
            aborted = boundary.abort_before_dispatch(
                request.protocol_request_id,
                reason="Tool inventory changed before dispatch",
            )
            self.assertEqual(
                aborted.outcome,
                ProtocolOutcome.PRE_DISPATCH_ABORTED,
            )
            self.assertEqual(
                boundary.binding_status[request.protocol_request_id],
                BindingStatus.ABORTED_PRE_DISPATCH,
            )
            self.assertFalse(aborted.durable_transition)

            await adapter.refresh_tool_inventory()
            replacement = adapter.issue_preflight_permit(
                "tools/call",
                tool_name="research.lookup",
                arguments={"query": "stale inventory"},
            )
            self.assertNotEqual(preflight_permit, replacement)

    async def test_binding_mismatch_stops_before_client_lifecycle(self) -> None:
        request = MCPRequestDTO(
            specification_version=CURRENT_SPECIFICATION_VERSION,
            protocol_request_id="request-a",
            method="tools/call",
            params={"name": "research.lookup", "arguments": {}},
        )
        binding = MCPRequestBinding(
            protocol_request_id="request-b",
            application_operation_id="operation-a",
            expected_method="tools/call",
            request_fingerprint="fingerprint-a",
        )
        server = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURE)],
        )

        async with SDKPrivateMCPClientAdapter(server) as adapter:
            preflight_permit = adapter.issue_preflight_permit(
                "tools/call",
                tool_name="research.lookup",
                arguments={"query": "binding must still match"},
            )
            with self.assertRaisesRegex(ValueError, "local binding"):
                await adapter.exchange(request, binding, preflight_permit)


if __name__ == "__main__":
    unittest.main()
