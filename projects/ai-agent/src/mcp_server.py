"""Application-owned Day91 MCP Server admission and backpressure boundary.

This module deliberately contains no MCP SDK types.  The future SDK-private
Server Adapter may translate wire requests into ``ServerToolRequest`` values,
but application admission, capacity and effect authority remain here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol


class ServerToolOutcome(str, Enum):
    """Auditable result of one Server-side Tool request."""

    BACKPRESSURE_REJECTED = "BACKPRESSURE_REJECTED"
    APPLICATION_REJECTED = "APPLICATION_REJECTED"
    DUPLICATE_REJECTED = "DUPLICATE_REJECTED"
    IDENTITY_CONFLICT_REJECTED = "IDENTITY_CONFLICT_REJECTED"
    OUTPUT_REJECTED = "OUTPUT_REJECTED"
    CANDIDATE_RESULT = "CANDIDATE_RESULT"


class ServerResourceOutcome(str, Enum):
    """Auditable result of one Server-side Resource request."""

    BACKPRESSURE_REJECTED = "BACKPRESSURE_REJECTED"
    APPLICATION_REJECTED = "APPLICATION_REJECTED"
    INDIRECT_PROMPT_INJECTION_REJECTED = (
        "INDIRECT_PROMPT_INJECTION_REJECTED"
    )
    CONTENT_CANDIDATE = "CONTENT_CANDIDATE"


class ServerPromptOutcome(str, Enum):
    """Auditable result of one Server-side Prompt request."""

    BACKPRESSURE_REJECTED = "BACKPRESSURE_REJECTED"
    PROMPT_INJECTION_REJECTED = "PROMPT_INJECTION_REJECTED"
    RENDERED_CANDIDATE = "RENDERED_CANDIDATE"


@dataclass(frozen=True)
class ServerToolRequest:
    """SDK-independent candidate built from one protocol request."""

    protocol_request_id: str | int
    tool_name: str
    arguments: Mapping[str, object]


@dataclass(frozen=True)
class ServerToolDecision:
    """Server result candidate; never durable business authority."""

    outcome: ServerToolOutcome
    request: ServerToolRequest
    reason: str
    is_error: bool
    structured_content: Mapping[str, object] | None = None
    handler_calls: int = 0
    controlled_service_calls: int = 0
    durable_transitions: int = 0


@dataclass(frozen=True)
class ServerResourceRequest:
    """SDK-independent Resource request built by the Server Adapter."""

    protocol_request_id: str | int
    uri: str
    tenant_id: str
    resource_id: str


@dataclass(frozen=True)
class ServerResourceDecision:
    """Application-owned Resource admission/read result."""

    outcome: ServerResourceOutcome
    request: ServerResourceRequest
    reason: str
    content: str | None = None
    resource_reads: int = 0


@dataclass(frozen=True)
class ServerPromptRequest:
    """SDK-independent Prompt request built by the Server Adapter."""

    protocol_request_id: str | int
    prompt_name: str
    arguments: Mapping[str, str]


@dataclass(frozen=True)
class ServerPromptDecision:
    """Application-owned Prompt validation/render result."""

    outcome: ServerPromptOutcome
    request: ServerPromptRequest
    reason: str
    rendered_text: str | None = None
    prompt_renders: int = 0
    tool_calls: int = 0
    resource_reads: int = 0


class CapacityLease(Protocol):
    """One bounded unit of Server execution capacity."""

    def release(self) -> None: ...


class CapacityGate(Protocol):
    """Fail-fast capacity port evaluated before any Tool handler."""

    def try_acquire(self) -> CapacityLease | None: ...


class ToolRequestHandler(Protocol):
    """Application handler port; its result is still only a candidate."""

    def handle(self, request: ServerToolRequest) -> ServerToolDecision: ...


class ResourceRequestHandler(Protocol):
    """Application Resource handler port behind the Server Adapter."""

    def handle(
        self,
        request: ServerResourceRequest,
    ) -> ServerResourceDecision: ...


class PromptRequestHandler(Protocol):
    """Application Prompt handler port behind the Server Adapter."""

    def handle(self, request: ServerPromptRequest) -> ServerPromptDecision: ...


@dataclass(frozen=True)
class MCPServerRequestCoordinator:
    """Apply backpressure before dispatching to an application handler."""

    capacity_gate: CapacityGate
    tool_handler: ToolRequestHandler

    def handle_tool(self, request: ServerToolRequest) -> ServerToolDecision:
        lease = self.capacity_gate.try_acquire()
        if lease is None:
            return ServerToolDecision(
                outcome=ServerToolOutcome.BACKPRESSURE_REJECTED,
                request=request,
                reason="server capacity is exhausted",
                is_error=True,
            )
        try:
            return self.tool_handler.handle(request)
        finally:
            lease.release()


@dataclass(frozen=True)
class MCPServerResourceCoordinator:
    """Apply backpressure before dispatching to a Resource handler."""

    capacity_gate: CapacityGate
    resource_handler: ResourceRequestHandler

    def handle_resource(
        self,
        request: ServerResourceRequest,
    ) -> ServerResourceDecision:
        lease = self.capacity_gate.try_acquire()
        if lease is None:
            return ServerResourceDecision(
                outcome=ServerResourceOutcome.BACKPRESSURE_REJECTED,
                request=request,
                reason="server capacity is exhausted",
                resource_reads=0,
            )
        try:
            return self.resource_handler.handle(request)
        finally:
            lease.release()


@dataclass(frozen=True)
class MCPServerPromptCoordinator:
    """Apply backpressure before validating or rendering a Prompt."""

    capacity_gate: CapacityGate
    prompt_handler: PromptRequestHandler

    def handle_prompt(
        self,
        request: ServerPromptRequest,
    ) -> ServerPromptDecision:
        lease = self.capacity_gate.try_acquire()
        if lease is None:
            return ServerPromptDecision(
                outcome=ServerPromptOutcome.BACKPRESSURE_REJECTED,
                request=request,
                reason="server capacity is exhausted",
                prompt_renders=0,
            )
        try:
            return self.prompt_handler.handle(request)
        finally:
            lease.release()
