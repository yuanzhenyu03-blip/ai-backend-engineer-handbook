"""SDK-private Day91 MCP Server Adapter.

Only this module knows MCP SDK request/context and exception types.  It
translates a validated SDK Tool call into the application's
``ServerToolRequest`` before dispatch and maps the application decision back
to the correct wire-level channel.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

from mcp import types as mcp_types
from mcp.server.context import CallNext, ServerRequestContext
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from mcp.shared.exceptions import MCPError
from pydantic import BaseModel, ConfigDict

from mcp_server import (
    MCPServerPromptCoordinator,
    MCPServerResourceCoordinator,
    MCPServerRequestCoordinator,
    ServerResourceOutcome,
    ServerResourceRequest,
    ServerPromptOutcome,
    ServerPromptRequest,
    ServerToolOutcome,
    ServerToolRequest,
)
from mcp_server_inventory import InvalidInventoryCursor, ToolInventoryPaginator


# JSON-RPC reserves -32000 through -32099 for implementation-defined Server
# errors.  Capacity rejection is a protocol failure because no Tool handler ran.
SERVER_OVERLOADED_ERROR = -32000
PROMPT_REJECTED_ERROR = -32001


class ResearchLookupWireOutput(BaseModel):
    """Explicit MCP output schema after application semantic validation."""

    model_config = ConfigDict(extra="forbid")

    query: str
    application_operation_id: str
    tenant_id: str


def build_mcp_server(
    coordinator: MCPServerRequestCoordinator,
    resource_coordinator: MCPServerResourceCoordinator | None = None,
    prompt_coordinator: MCPServerPromptCoordinator | None = None,
    inventory_cursor_secret: bytes | None = None,
) -> MCPServer:
    """Build an MCP Server around application-owned capacity and handlers."""

    server = MCPServer("day91-controlled-mcp-server")

    async def run_lookup(
        tool_name: str,
        query: str,
        context: Context,
    ) -> ResearchLookupWireOutput:
        # This is the one-way SDK -> application translation boundary.  SDK
        # Context never crosses into the coordinator or application handler.
        request = ServerToolRequest(
            protocol_request_id=context.request_id,
            tool_name=tool_name,
            arguments={"query": query},
        )
        decision = coordinator.handle_tool(request)

        if decision.outcome is ServerToolOutcome.BACKPRESSURE_REJECTED:
            raise MCPError(
                code=SERVER_OVERLOADED_ERROR,
                message="Server is temporarily at capacity",
            )
        if decision.outcome in {
            ServerToolOutcome.APPLICATION_REJECTED,
            ServerToolOutcome.DUPLICATE_REJECTED,
            ServerToolOutcome.IDENTITY_CONFLICT_REJECTED,
            ServerToolOutcome.OUTPUT_REJECTED,
        }:
            raise ToolError(decision.reason)
        if (
            decision.outcome is not ServerToolOutcome.CANDIDATE_RESULT
            or decision.structured_content is None
        ):
            raise RuntimeError("handler returned an invalid Server Tool decision")

        return ResearchLookupWireOutput.model_validate(
            dict(decision.structured_content)
        )

    @server.tool(name="research.lookup", structured_output=True)
    async def research_lookup(
        query: str,
        context: Context,
    ) -> ResearchLookupWireOutput:
        return await run_lookup("research.lookup", query, context)

    @server.tool(name="research.lookup.preview", structured_output=True)
    async def research_lookup_preview(
        query: str,
        context: Context,
    ) -> ResearchLookupWireOutput:
        return await run_lookup("research.lookup.preview", query, context)

    if resource_coordinator is not None:

        async def run_resource(
            tenant_id: str,
            resource_id: str,
            context: Context,
        ) -> str:
            request = ServerResourceRequest(
                protocol_request_id=context.request_id,
                uri=f"research://{tenant_id}/{resource_id}",
                tenant_id=tenant_id,
                resource_id=resource_id,
            )
            decision = resource_coordinator.handle_resource(request)

            if decision.outcome is ServerResourceOutcome.BACKPRESSURE_REJECTED:
                raise MCPError(
                    code=SERVER_OVERLOADED_ERROR,
                    message="Server is temporarily at capacity",
                )
            if decision.outcome is ServerResourceOutcome.APPLICATION_REJECTED:
                # Do not reveal whether an out-of-scope Resource exists.
                raise ResourceError("Resource is unavailable")
            if (
                decision.outcome
                is ServerResourceOutcome.INDIRECT_PROMPT_INJECTION_REJECTED
            ):
                raise ResourceError("Resource content failed safety validation")
            if (
                decision.outcome is not ServerResourceOutcome.CONTENT_CANDIDATE
                or decision.content is None
            ):
                raise RuntimeError(
                    "handler returned an invalid Server Resource decision"
                )
            return decision.content

        @server.resource(
            "research://{tenant_id}/{resource_id}",
            name="research-resource",
            mime_type="text/plain",
        )
        async def research_resource(
            tenant_id: str,
            resource_id: str,
            context: Context,
        ) -> str:
            return await run_resource(tenant_id, resource_id, context)

    if prompt_coordinator is not None:

        @server.prompt(name="summarize-research")
        async def summarize_research(
            style: str,
            context: Context,
        ) -> str:
            request = ServerPromptRequest(
                protocol_request_id=context.request_id,
                prompt_name="summarize-research",
                arguments={"style": style},
            )
            decision = prompt_coordinator.handle_prompt(request)

            if decision.outcome is ServerPromptOutcome.BACKPRESSURE_REJECTED:
                raise MCPError(
                    code=SERVER_OVERLOADED_ERROR,
                    message="Server is temporarily at capacity",
                )
            if (
                decision.outcome
                is ServerPromptOutcome.PROMPT_INJECTION_REJECTED
            ):
                raise MCPError(
                    code=PROMPT_REJECTED_ERROR,
                    message="Prompt was rejected by the safety policy",
                )
            if (
                decision.outcome is not ServerPromptOutcome.RENDERED_CANDIDATE
                or decision.rendered_text is None
            ):
                raise RuntimeError("handler returned an invalid Server Prompt decision")
            return decision.rendered_text

    paginator = ToolInventoryPaginator(
        secret=inventory_cursor_secret or secrets.token_bytes(32),
        page_size=1,
    )

    async def paginate_tool_inventory(
        ctx: ServerRequestContext[Any, Any],
        call_next: CallNext,
    ) -> dict[str, object] | None:
        result = await call_next(ctx)
        if ctx.method != "tools/list":
            return result
        if not isinstance(result, dict) or not isinstance(
            result.get("tools"),
            list,
        ):
            raise RuntimeError("tools/list handler returned an invalid result")

        serialized_tools = result["tools"]
        revision = hashlib.sha256(
            json.dumps(
                serialized_tools,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        raw_cursor = (ctx.params or {}).get("cursor")
        try:
            window = paginator.page(
                item_count=len(serialized_tools),
                revision=revision,
                cursor=raw_cursor if isinstance(raw_cursor, str) else None,
            )
        except InvalidInventoryCursor as exc:
            raise MCPError(
                code=mcp_types.INVALID_PARAMS,
                message="Invalid or stale Tool inventory cursor",
            ) from exc
        page = dict(result)
        page["tools"] = serialized_tools[window.start:window.end]
        if window.next_cursor is None:
            page.pop("nextCursor", None)
        else:
            page["nextCursor"] = window.next_cursor
        return page

    server.middleware.append(paginate_tool_inventory)

    return server
