"""Controlled real MCP 2.2.0 Streamable HTTP server for Day93 tests."""
from __future__ import annotations

import argparse

import anyio
from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse


server = MCPServer("day93-controlled-http", log_level="ERROR")
counts = {
    "handler_calls": 0,
    "controlled_service_calls": 0,
    "completed_calls": 0,
    "cancelled_calls": 0,
}


@server.tool(name="research.lookup")
async def research_lookup(query: str, delay_ms: int = 0) -> dict[str, object]:
    counts["handler_calls"] += 1
    counts["controlled_service_calls"] += 1
    try:
        if delay_ms:
            await anyio.sleep(delay_ms / 1000)
        counts["completed_calls"] += 1
        return {"query": query, "source": "controlled-loopback"}
    except BaseException:
        counts["cancelled_calls"] += 1
        raise


@server.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ready"})


@server.custom_route("/stats", methods=["GET"])
async def stats(_: Request) -> JSONResponse:
    return JSONResponse(dict(counts))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    server.run(
        "streamable-http",
        host="127.0.0.1",
        port=args.port,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
