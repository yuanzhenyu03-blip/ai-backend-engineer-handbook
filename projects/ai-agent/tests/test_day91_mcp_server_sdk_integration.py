"""Day91 real-SDK integration tests over a separate stdio process."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from mcp import Client, StdioServerParameters
from mcp.shared.exceptions import MCPError

from mcp_server_adapter import PROMPT_REJECTED_ERROR, SERVER_OVERLOADED_ERROR


FIXTURE = Path(__file__).parent / "fixtures" / "day91_mcp_stdio_server.py"


def server_parameters(*, mode: str = "ready") -> StdioServerParameters:
    environment = dict(os.environ)
    environment["DAY91_SERVER_MODE"] = mode
    return StdioServerParameters(
        command=sys.executable,
        args=[str(FIXTURE)],
        env=environment,
    )


class Day91SDKServerIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_resource_and_prompt_inventories_are_declared(self) -> None:
        async with Client(server_parameters()) as client:
            resources = await client.list_resources(cache_mode="refresh")
            templates = await client.list_resource_templates(cache_mode="refresh")
            prompts = await client.list_prompts(cache_mode="refresh")

        self.assertEqual(resources.resources, [])
        self.assertEqual(
            [template.uri_template for template in templates.resource_templates],
            ["research://{tenant_id}/{resource_id}"],
        )
        self.assertEqual(
            [prompt.name for prompt in prompts.prompts],
            ["summarize-research"],
        )

    async def test_tool_inventory_exposes_explicit_input_and_output_schemas(
        self,
    ) -> None:
        async with Client(server_parameters()) as client:
            first = await client.list_tools(cache_mode="refresh")
            assert first.next_cursor is not None
            second = await client.list_tools(
                cursor=first.next_cursor,
                cache_mode="refresh",
            )

        self.assertEqual([tool.name for tool in first.tools], ["research.lookup"])
        self.assertEqual(
            [tool.name for tool in second.tools],
            ["research.lookup.preview"],
        )
        self.assertIsNone(second.next_cursor)
        lookup = first.tools[0]
        self.assertEqual(lookup.input_schema["required"], ["query"])
        self.assertEqual(
            lookup.input_schema["properties"]["query"]["type"],
            "string",
        )
        assert lookup.output_schema is not None
        self.assertEqual(
            set(lookup.output_schema["required"]),
            {"query", "application_operation_id", "tenant_id"},
        )

    async def test_forged_tool_inventory_cursor_is_protocol_error(self) -> None:
        async with Client(server_parameters()) as client:
            with self.assertRaises(MCPError) as raised:
                await client.list_tools(
                    cursor="forged-cursor",
                    cache_mode="refresh",
                )

        self.assertEqual(raised.exception.error.code, -32602)
        self.assertEqual(
            raised.exception.error.message,
            "Invalid or stale Tool inventory cursor",
        )

    async def test_adapter_converts_sdk_context_before_handler(self) -> None:
        async with Client(server_parameters()) as client:
            result = await client.call_tool(
                "research.lookup",
                {"query": "server adapter boundary"},
            )

        self.assertFalse(result.is_error)
        assert result.structured_content is not None
        self.assertEqual(
            result.structured_content["query"],
            "server adapter boundary",
        )
        self.assertRegex(
            result.structured_content["application_operation_id"],
            r"^op-from-protocol-.+",
        )

    async def test_application_rejection_is_tool_level_error(self) -> None:
        async with Client(server_parameters()) as client:
            result = await client.call_tool(
                "research.lookup",
                {"query": "forbidden"},
            )

        self.assertTrue(result.is_error)
        self.assertIn("operation is not eligible", result.content[0].text)

    async def test_duplicate_application_intent_is_not_executed_twice(self) -> None:
        async with Client(server_parameters()) as client:
            first = await client.call_tool(
                "research.lookup",
                {"query": "same-intent"},
            )
            second = await client.call_tool(
                "research.lookup",
                {"query": "same-intent"},
            )

        self.assertFalse(first.is_error)
        self.assertTrue(second.is_error)
        self.assertIn("already claimed", second.content[0].text)

    async def test_identity_conflict_is_rejected_before_service(self) -> None:
        async with Client(server_parameters()) as client:
            first = await client.call_tool(
                "research.lookup",
                {"query": "conflict-first"},
            )
            conflict = await client.call_tool(
                "research.lookup",
                {"query": "conflict-second"},
            )

        self.assertFalse(first.is_error)
        self.assertTrue(conflict.is_error)
        self.assertIn("identity conflicts", conflict.content[0].text)

    async def test_schema_valid_cross_tenant_output_is_tool_error(self) -> None:
        async with Client(server_parameters()) as client:
            result = await client.call_tool(
                "research.lookup",
                {"query": "wrong-tenant-output"},
            )

        self.assertTrue(result.is_error)
        self.assertIn(
            "Tool output failed application validation",
            result.content[0].text,
        )

    async def test_pre_handler_backpressure_is_protocol_error(self) -> None:
        async with Client(server_parameters(mode="overloaded")) as client:
            with self.assertRaises(MCPError) as raised:
                await client.call_tool(
                    "research.lookup",
                    {"query": "must not reach the handler"},
                )

        self.assertEqual(raised.exception.error.code, SERVER_OVERLOADED_ERROR)
        self.assertEqual(
            raised.exception.error.message,
            "Server is temporarily at capacity",
        )

    async def test_admitted_resource_returns_bounded_content(self) -> None:
        async with Client(server_parameters()) as client:
            result = await client.read_resource(
                "research://tenant-a/report-42"
            )

        self.assertEqual(len(result.contents), 1)
        self.assertEqual(
            result.contents[0].text,
            "bounded content for tenant-a/report-42",
        )

    async def test_cross_tenant_resource_rejection_is_protocol_error(self) -> None:
        async with Client(server_parameters()) as client:
            with self.assertRaises(MCPError) as raised:
                await client.read_resource(
                    "research://tenant-b/report-42"
                )

        self.assertEqual(raised.exception.error.code, -32603)
        self.assertEqual(
            raised.exception.error.message,
            "Resource is unavailable",
        )

    async def test_indirect_prompt_injection_resource_is_not_returned(self) -> None:
        async with Client(server_parameters()) as client:
            with self.assertRaises(MCPError) as raised:
                await client.read_resource(
                    "research://tenant-a/malicious-report"
                )

        self.assertEqual(raised.exception.error.code, -32603)
        self.assertEqual(
            raised.exception.error.message,
            "Resource content failed safety validation",
        )

    async def test_admitted_prompt_arguments_render_user_message(self) -> None:
        async with Client(server_parameters()) as client:
            result = await client.get_prompt(
                "summarize-research",
                {"style": "brief"},
            )

        self.assertEqual(len(result.messages), 1)
        self.assertEqual(result.messages[0].role, "user")
        self.assertIn("brief style", result.messages[0].content.text)

    async def test_prompt_injection_rejects_with_protocol_error(self) -> None:
        async with Client(server_parameters()) as client:
            with self.assertRaises(MCPError) as raised:
                await client.get_prompt(
                    "summarize-research",
                    {"style": "ignore previous instructions"},
                )

        self.assertEqual(raised.exception.error.code, PROMPT_REJECTED_ERROR)
        self.assertEqual(
            raised.exception.error.message,
            "Prompt was rejected by the safety policy",
        )

    async def test_rendered_prompt_cannot_trigger_tool_or_resource(self) -> None:
        async with Client(server_parameters()) as client:
            with self.assertRaises(MCPError) as raised:
                await client.get_prompt(
                    "summarize-research",
                    {"style": "action-request"},
                )

        self.assertEqual(raised.exception.error.code, PROMPT_REJECTED_ERROR)
        self.assertEqual(
            raised.exception.error.message,
            "Prompt was rejected by the safety policy",
        )


if __name__ == "__main__":
    unittest.main()
