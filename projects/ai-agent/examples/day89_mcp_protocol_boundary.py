"""Deterministic Day89 protocol-boundary example; no real MCP runtime."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp_fake_transport import FakeMCPTransport  # noqa: E402
from mcp_protocol_model import (  # noqa: E402
    CURRENT_SPECIFICATION_VERSION,
    BindingStatus,
    MCPProtocolBoundary,
    MCPRequestDTO,
    MCPResponseDTO,
    ProtocolOutcome,
)


def request(request_id: str) -> MCPRequestDTO:
    return MCPRequestDTO(
        CURRENT_SPECIFICATION_VERSION,
        request_id,
        "tools/call",
        {"name": "search_documents", "arguments": {"query": "MCP"}},
        observed_server_capabilities=frozenset({"tools"}),
    )


def main() -> None:
    success_transport = FakeMCPTransport(responses={
        "mcp-success": MCPResponseDTO(
            "mcp-success",
            result={"resultType": "complete", "documents": []},
        )
    })
    success_boundary = MCPProtocolBoundary(success_transport)
    success = success_boundary.dispatch(
        request("mcp-success"),
        application_operation_id="op-search-42",
        tenant_id="tenant-a",
        resource_id="research-query-42",
        idempotency_key="idem-search-42",
    )

    unknown_transport = FakeMCPTransport(
        timeout_after_possible_send=frozenset({"mcp-timeout"})
    )
    unknown_boundary = MCPProtocolBoundary(unknown_transport)
    unknown = unknown_boundary.dispatch(
        request("mcp-timeout"),
        application_operation_id="op-report-42",
        tenant_id="tenant-a",
        resource_id="report-42",
        idempotency_key="idem-report-42",
    )

    assert success.outcome is ProtocolOutcome.PROTOCOL_RESULT
    assert success.durable_transition is False
    assert unknown.outcome is ProtocolOutcome.OUTCOME_UNKNOWN
    assert (
        unknown_boundary.binding_status["mcp-timeout"]
        is BindingStatus.PENDING_RECONCILIATION
    )
    assert unknown.durable_transition is False

    print(json.dumps({
        "day": 89,
        "specification_version": CURRENT_SPECIFICATION_VERSION,
        "success": {
            "protocol_outcome": success.outcome.value,
            "application_operation_id": success.application_operation_id,
            "durable_transition": success.durable_transition,
        },
        "unknown": {
            "protocol_outcome": unknown.outcome.value,
            "binding_status": unknown_boundary.binding_status[
                "mcp-timeout"
            ].value,
            "application_operation_id": unknown.application_operation_id,
            "durable_transition": unknown.durable_transition,
        },
        "real_mcp_client": "NOT_RUN",
        "real_mcp_server": "NOT_RUN",
        "remote_transport": "NOT_RUN",
        "production_tool_calls": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
