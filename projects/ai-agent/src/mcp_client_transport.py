"""Day90 transport port and dispatch-certainty failure contract."""
from __future__ import annotations

from enum import Enum
from typing import Protocol


class DispatchCertainty(str, Enum):
    """What the transport can prove about an unsuccessful dispatch."""

    PROVEN_NOT_SENT = "PROVEN_NOT_SENT"
    POSSIBLY_SENT = "POSSIBLY_SENT"


class MCPTransportFailure(RuntimeError):
    """Transport failure carrying explicit, auditable send certainty."""

    def __init__(
        self,
        reason: str,
        *,
        dispatch_certainty: DispatchCertainty,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.dispatch_certainty = dispatch_certainty


class MCPByteTransport(Protocol):
    """Exchange one encoded request for one encoded final response."""

    def exchange(self, message: bytes) -> bytes: ...
