"""Deterministic Day89 transport double; this is not real MCP integration."""
from __future__ import annotations

from dataclasses import dataclass, field

from mcp_protocol_model import (
    MCPRequestDTO,
    MCPResponseDTO,
    TimeoutAfterPossibleSend,
    TimeoutBeforeSend,
)


@dataclass
class FakeMCPTransport:
    """Return configured responses and preserve an exact send record."""

    responses: dict[str | int, MCPResponseDTO | None] = field(default_factory=dict)
    timeout_before_send: frozenset[str | int] = frozenset()
    timeout_after_possible_send: frozenset[str | int] = frozenset()
    sent: list[MCPRequestDTO] = field(default_factory=list)

    def send(self, request: MCPRequestDTO) -> MCPResponseDTO | None:
        request_id = request.protocol_request_id
        if request_id in self.timeout_before_send:
            raise TimeoutBeforeSend(request_id)
        self.sent.append(request)
        if request_id in self.timeout_after_possible_send:
            raise TimeoutAfterPossibleSend(request_id)
        return self.responses.get(request_id)
