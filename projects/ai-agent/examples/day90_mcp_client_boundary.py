"""Deterministic Day90 Client-boundary example; no network or credentials."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp_client import DependencyFreeMCPClientAdapter  # noqa: E402
from mcp_client_transport import (  # noqa: E402
    DispatchCertainty,
    MCPTransportFailure,
)
from mcp_protocol_model import (  # noqa: E402
    CURRENT_SPECIFICATION_VERSION,
    MCPRequestBinding,
    MCPRequestDTO,
)


class ControlledByteTransport:
    def __init__(self, *, fail_after_possible_send: bool = False) -> None:
        self.fail_after_possible_send = fail_after_possible_send
        self.messages: list[bytes] = []

    def exchange(self, message: bytes) -> bytes:
        self.messages.append(message)
        if self.fail_after_possible_send:
            raise MCPTransportFailure(
                "controlled timeout after possible send",
                dispatch_certainty=DispatchCertainty.POSSIBLY_SENT,
            )
        request = json.loads(message)
        return json.dumps({
            "jsonrpc": "2.0",
            "id": request["id"],
            "result": {"content": [], "isError": False},
        }).encode()


def request(request_id: str) -> MCPRequestDTO:
    return MCPRequestDTO(
        CURRENT_SPECIFICATION_VERSION,
        request_id,
        "tools/call",
        {"name": "research.lookup", "arguments": {"query": "MCP Client"}},
        client_capabilities=frozenset({"tools"}),
        observed_server_capabilities=frozenset({"tools"}),
    )


def binding(request_id: str) -> MCPRequestBinding:
    return MCPRequestBinding(
        request_id,
        "op-report-42",
        "tools/call",
        f"fingerprint-{request_id}",
        tenant_id="tenant-a",
        resource_id="report-42",
        idempotency_key="idem-report-42",
    )


def main() -> None:
    success_transport = ControlledByteTransport()
    success = DependencyFreeMCPClientAdapter(success_transport).exchange(
        request("day90-success-1"), binding("day90-success-1")
    )

    uncertain_transport = ControlledByteTransport(fail_after_possible_send=True)
    uncertain = DependencyFreeMCPClientAdapter(uncertain_transport).exchange(
        request("day90-unknown-1"), binding("day90-unknown-1")
    )

    assert success.response is not None
    assert uncertain.observation is not None
    print(json.dumps({
        "day": 90,
        "success_response_id": success.response.protocol_request_id,
        "unknown_outcome": uncertain.observation.outcome.value,
        "application_operation_id": (
            uncertain.observation.application_operation_id
        ),
        "success_wire_sends": len(success_transport.messages),
        "unknown_wire_sends": len(uncertain_transport.messages),
        "durable_transitions": 0,
        "real_sdk_integration": "TESTED_SEPARATELY",
        "production": "NOT_RUN",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
