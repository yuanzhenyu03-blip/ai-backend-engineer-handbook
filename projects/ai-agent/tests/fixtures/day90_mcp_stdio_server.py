"""Controlled separate-process MCP Server for Day90 integration evidence."""
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError


server = MCPServer("day90-controlled-stdio-server")


@server.tool(name="research.lookup", structured_output=True)
async def research_lookup(query: str, context: Context) -> dict[str, str]:
    """Echo bounded evidence, including the request ID observed by the server."""

    return {
        "query": query,
        "observed_protocol_request_id": context.request_id,
    }


@server.tool(name="research.reject")
async def research_reject(reason: str) -> str:
    """Produce a legitimate Tool-level error, not a protocol error."""

    raise ToolError(reason)


@server.resource(
    "research://tenant-a/report-42",
    name="research-report-42",
    mime_type="text/plain",
)
def research_report() -> str:
    """Return controlled Resource content."""

    return "MCP Client integration evidence for tenant-a/report-42"


@server.prompt(name="summarize-research")
def summarize_research(style: str) -> str:
    """Return a controlled user-role Prompt template."""

    return f"Summarize the admitted research in a {style} style."


if __name__ == "__main__":
    server.run(transport="stdio")
