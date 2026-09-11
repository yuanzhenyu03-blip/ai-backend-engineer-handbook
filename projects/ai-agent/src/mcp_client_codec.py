"""Day90 dependency-free codec for the current MCP wire contract.

The codec knows JSON-RPC and the 2026-07-28 per-request metadata shape.  It
does not know application operation IDs, authorization or durable state.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from mcp_protocol_model import MCPRequestDTO, MCPResponseDTO


JSONRPC_VERSION = "2.0"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META_KEY = (
    "io.modelcontextprotocol/clientCapabilities"
)


class MCPCodecError(ValueError):
    """The wire message cannot be represented by the application DTOs."""


def _is_request_id(value: object) -> bool:
    return isinstance(value, str) or type(value) is int


@dataclass(frozen=True)
class MCPWireCodec:
    """Serialize requests and deserialize responses without network I/O."""

    def encode_request(self, request: MCPRequestDTO) -> bytes:
        """Encode one application request as canonical UTF-8 JSON-RPC."""

        if not _is_request_id(request.protocol_request_id):
            raise MCPCodecError("invalid protocol request ID")
        if "_meta" in request.params:
            raise MCPCodecError("application params cannot override MCP metadata")

        client_capabilities = {
            capability: {}
            for capability in sorted(request.client_capabilities)
        }
        params: dict[str, Any] = dict(request.params)
        params["_meta"] = {
            PROTOCOL_VERSION_META_KEY: request.specification_version,
            CLIENT_CAPABILITIES_META_KEY: client_capabilities,
        }
        message = {
            "jsonrpc": JSONRPC_VERSION,
            "id": request.protocol_request_id,
            "method": request.method,
            "params": params,
        }
        try:
            encoded = json.dumps(
                message,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as error:
            raise MCPCodecError("request is not JSON serializable") from error
        return encoded.encode("utf-8")

    def decode_response(self, payload: bytes) -> MCPResponseDTO:
        """Decode one UTF-8 JSON-RPC result or error response."""

        try:
            message = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MCPCodecError("response is not valid UTF-8 JSON") from error
        if not isinstance(message, Mapping):
            raise MCPCodecError("response must be a JSON object")
        if message.get("jsonrpc") != JSONRPC_VERSION:
            raise MCPCodecError("unsupported JSON-RPC version")
        request_id = message.get("id")
        if not _is_request_id(request_id):
            raise MCPCodecError("invalid response ID")

        has_result = "result" in message
        has_error = "error" in message
        if has_result == has_error:
            raise MCPCodecError(
                "response must contain exactly one of result or error"
            )
        value = message["result"] if has_result else message["error"]
        if not isinstance(value, Mapping):
            raise MCPCodecError("response result or error must be an object")
        if has_error and (
            type(value.get("code")) is not int
            or not isinstance(value.get("message"), str)
        ):
            raise MCPCodecError("invalid JSON-RPC error object")

        return MCPResponseDTO(
            protocol_request_id=request_id,
            result=dict(value) if has_result else None,
            error=dict(value) if has_error else None,
        )
