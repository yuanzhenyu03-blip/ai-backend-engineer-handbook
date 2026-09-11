"""SDK-private Day90 MCP Client Adapter pinned to ``mcp==2.2.0``.

The public high-level SDK API mints its own JSON-RPC request IDs.  Day89's
application contract requires a binding to be durable before dispatch, so this
adapter deliberately owns the small private seam that supplies the already
bound ID to the SDK dispatcher.  SDK objects never cross this module boundary.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any, Mapping

from jsonschema import exceptions as jsonschema_exceptions
from jsonschema.protocols import Validator
from jsonschema.validators import validator_for
from mcp import Client, StdioServerParameters, types
from mcp.shared.dispatcher import CallOptions
from mcp.shared.exceptions import MCPError
from mcp_types import CONNECTION_CLOSED, REQUEST_TIMEOUT
from pydantic import ValidationError

from mcp_client import MCPClientExchange
from mcp_protocol_model import (
    CURRENT_SPECIFICATION_VERSION,
    MCPRequestBinding,
    MCPRequestDTO,
    MCPResponseDTO,
    ProtocolObservation,
    ProtocolOutcome,
)


SUPPORTED_MCP_SDK_VERSION = "2.2.0"

_RESULT_TYPES = {
    "server/discover": types.DiscoverResult,
    "tools/call": types.CallToolResult,
    "resources/read": types.ReadResourceResult,
    "prompts/get": types.GetPromptResult,
}

_METHOD_CAPABILITIES = {
    "server/discover": None,
    "tools/call": "tools",
    "resources/read": "resources",
    "prompts/get": "prompts",
}


class SDKContractError(RuntimeError):
    """The installed SDK or requested operation does not fit this adapter."""


class CapabilityEvidenceError(SDKContractError):
    """The current connection did not supply the required capability evidence."""


class ToolInputValidationError(SDKContractError):
    """Arguments do not satisfy the current connection's Tool schema."""


@dataclass(frozen=True)
class MCPAttemptPreflightPermit:
    """Adapter-issued preflight proof, not tenant or business authorization."""

    inventory_generation: int
    request_fingerprint: str


def _attempt_fingerprint(
    method: str,
    params: Mapping[str, Any],
) -> str:
    try:
        value = json.dumps(
            {
                "method": method,
                "params": dict(params),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ToolInputValidationError(
            "Tool arguments are not JSON serializable"
        ) from error
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SDKPrivateMCPClientAdapter:
    """Own one real SDK Client lifecycle without leaking SDK response types."""

    def __init__(
        self,
        server: StdioServerParameters | str,
        *,
        read_timeout_seconds: float | None = None,
    ) -> None:
        installed = version("mcp")
        if installed != SUPPORTED_MCP_SDK_VERSION:
            raise SDKContractError(
                "SDK-private adapter requires "
                f"mcp=={SUPPORTED_MCP_SDK_VERSION}; found {installed}"
            )
        self._client = Client(
            server,
            mode="auto",
            read_timeout_seconds=read_timeout_seconds,
        )
        self._entered = False
        self._observed_server_capabilities: frozenset[str] = frozenset()
        self._observed_tool_names: frozenset[str] = frozenset()
        self._tool_input_validators: dict[str, Validator] = {}
        self._inventory_generation = 0

    async def __aenter__(self) -> "SDKPrivateMCPClientAdapter":
        await self._client.__aenter__()
        try:
            if self._client.protocol_version != CURRENT_SPECIFICATION_VERSION:
                raise SDKContractError(
                    "server did not negotiate the required MCP specification version"
                )
            capability_data = self._client.server_capabilities.model_dump(
                by_alias=True,
                mode="json",
                exclude_none=True,
            )
            self._observed_server_capabilities = frozenset(capability_data)
            if "tools" in self._observed_server_capabilities:
                await self._refresh_tool_inventory_unchecked()
        except BaseException as error:
            await self._client.__aexit__(
                type(error),
                error,
                error.__traceback__,
            )
            raise
        self._entered = True
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            await self._client.__aexit__(exc_type, exc, tb)
        finally:
            self._entered = False
            self._observed_server_capabilities = frozenset()
            self._observed_tool_names = frozenset()
            self._tool_input_validators = {}

    @property
    def observed_server_capabilities(self) -> frozenset[str]:
        """Connection-owned capability evidence produced by SDK discovery."""

        if not self._entered:
            raise SDKContractError("client lifecycle has not been entered")
        return self._observed_server_capabilities

    @property
    def observed_tool_names(self) -> frozenset[str]:
        """SDK-validated Tool inventory for the current connection."""

        if not self._entered:
            raise SDKContractError("client lifecycle has not been entered")
        return self._observed_tool_names

    def issue_preflight_permit(
        self,
        method: str,
        *,
        tool_name: str | None = None,
        arguments: Mapping[str, Any] | None = None,
        resource_uri: str | None = None,
        prompt_name: str | None = None,
        prompt_arguments: Mapping[str, str] | None = None,
    ) -> MCPAttemptPreflightPermit:
        """Fail before the caller creates a business protocol attempt.

        Lifecycle discovery is read-only and SDK-owned.  Callers invoke this
        preflight before minting a business request ID, persisting a binding or
        dispatch marker, and sending a request.  ``exchange`` repeats the check
        as defense in depth.
        """

        if not self._entered:
            raise SDKContractError("client lifecycle has not been entered")
        if method not in _METHOD_CAPABILITIES:
            raise SDKContractError(f"unsupported MCP method: {method}")
        required = _METHOD_CAPABILITIES[method]
        if (
            required is not None
            and required not in self._observed_server_capabilities
        ):
            raise CapabilityEvidenceError(
                f"server capability not observed on this connection: {required}"
            )
        if method == "tools/call":
            if not tool_name:
                raise SDKContractError(
                    "tools/call preflight requires a concrete Tool name"
                )
            if tool_name not in self._observed_tool_names:
                raise CapabilityEvidenceError(
                    f"Tool not observed on this connection: {tool_name}"
                )
            validator = self._tool_input_validators[tool_name]
            errors = validator.iter_errors(
                dict(arguments) if arguments is not None else {}
            )
            error = jsonschema_exceptions.best_match(errors)
            if error is not None:
                raise ToolInputValidationError(
                    f"arguments do not match input schema for Tool {tool_name}: "
                    f"{error.message}"
                ) from error
            attempt_params: Mapping[str, Any] = {
                "name": tool_name,
                "arguments": dict(arguments) if arguments is not None else {},
            }
        elif method == "resources/read":
            if not resource_uri:
                raise SDKContractError(
                    "resources/read preflight requires a concrete Resource URI"
                )
            attempt_params = {"uri": resource_uri}
        elif method == "prompts/get":
            if not prompt_name:
                raise SDKContractError(
                    "prompts/get preflight requires a concrete Prompt name"
                )
            attempt_params = {
                "name": prompt_name,
                "arguments": (
                    dict(prompt_arguments)
                    if prompt_arguments is not None
                    else {}
                ),
            }
        else:
            attempt_params = {}
        return MCPAttemptPreflightPermit(
            inventory_generation=self._inventory_generation,
            request_fingerprint=_attempt_fingerprint(
                method,
                attempt_params,
            ),
        )

    def note_tools_list_changed(self) -> None:
        """Invalidate all Tool preflights before asynchronously refreshing."""

        if not self._entered:
            raise SDKContractError("client lifecycle has not been entered")
        self._inventory_generation += 1
        self._observed_tool_names = frozenset()
        self._tool_input_validators = {}

    async def refresh_tool_inventory(self) -> None:
        """Fetch a complete new inventory after invalidation.

        Nothing is published until all pages and schemas validate, so a failed
        refresh leaves Tool dispatch closed.
        """

        if not self._entered:
            raise SDKContractError("client lifecycle has not been entered")
        if "tools" not in self._observed_server_capabilities:
            raise CapabilityEvidenceError(
                "server capability not observed on this connection: tools"
            )
        await self._refresh_tool_inventory_unchecked()

    async def _refresh_tool_inventory_unchecked(self) -> None:
        names: set[str] = set()
        validators: dict[str, Validator] = {}
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while True:
            page = await self._client.list_tools(
                cursor=cursor,
                cache_mode="reload",
            )
            for tool in page.tools:
                if tool.name in names:
                    raise SDKContractError(
                        f"tools/list returned duplicate Tool: {tool.name}"
                    )
                schema = dict(tool.input_schema)
                validator_class = validator_for(schema)
                try:
                    validator_class.check_schema(schema)
                except jsonschema_exceptions.SchemaError as error:
                    raise SDKContractError(
                        f"invalid input schema for Tool {tool.name}"
                    ) from error
                names.add(tool.name)
                validators[tool.name] = validator_class(schema)
            cursor = page.next_cursor
            if cursor is None:
                break
            if cursor in seen_cursors:
                raise SDKContractError(
                    "tools/list returned a repeated pagination cursor"
                )
            seen_cursors.add(cursor)
        self._observed_tool_names = frozenset(names)
        self._tool_input_validators = validators

    async def exchange(
        self,
        request: MCPRequestDTO,
        binding: MCPRequestBinding,
        preflight_permit: MCPAttemptPreflightPermit,
    ) -> MCPClientExchange:
        """Send one already-bound request through the real SDK transport.

        A dispatcher timeout or connection loss cannot prove the request was
        not sent, so it becomes OUTCOME_UNKNOWN.  A peer JSON-RPC error remains
        a response DTO for the application correlation stage.
        """

        if not self._entered:
            raise SDKContractError("client lifecycle has not been entered")
        if request.protocol_request_id != binding.protocol_request_id:
            raise ValueError("request does not match the local binding")
        if request.method != binding.expected_method:
            raise ValueError("request method does not match the local binding")
        if request.specification_version != CURRENT_SPECIFICATION_VERSION:
            raise SDKContractError("unsupported MCP specification version")
        if request.method not in _RESULT_TYPES:
            raise SDKContractError(f"unsupported MCP method: {request.method}")
        tool_name = (
            request.params.get("name")
            if request.method == "tools/call"
            else None
        )
        current_preflight_permit = self.issue_preflight_permit(
            request.method,
            tool_name=tool_name if isinstance(tool_name, str) else None,
            arguments=(
                request.params.get("arguments")
                if isinstance(request.params.get("arguments"), Mapping)
                else None
            ),
            resource_uri=(
                request.params.get("uri")
                if request.method == "resources/read"
                and isinstance(request.params.get("uri"), str)
                else None
            ),
            prompt_name=(
                request.params.get("name")
                if request.method == "prompts/get"
                and isinstance(request.params.get("name"), str)
                else None
            ),
            prompt_arguments=(
                request.params.get("arguments")
                if request.method == "prompts/get"
                and isinstance(request.params.get("arguments"), Mapping)
                else None
            ),
        )
        if preflight_permit != current_preflight_permit:
            raise CapabilityEvidenceError(
                "preflight permit is stale or belongs to another request"
            )
        required = _METHOD_CAPABILITIES[request.method]
        if (
            required is not None
            and required not in request.observed_server_capabilities
        ):
            raise CapabilityEvidenceError(
                f"request lacks application capability evidence: {required}"
            )
        if "_meta" in request.params:
            raise SDKContractError("application params cannot override MCP metadata")

        data: dict[str, Any] = {
            "method": request.method,
            "params": dict(request.params),
        }
        opts: CallOptions = {"request_id": request.protocol_request_id}

        # Version-pinned private seam: reuse the SDK's current per-request
        # metadata/header stamping, then supply the locally persisted ID before
        # the SDK dispatcher constructs and writes the JSON-RPC request.
        self._client.session._stamp(data, opts)  # type: ignore[attr-defined]
        try:
            raw = await self._client.session._dispatcher.send_raw_request(  # type: ignore[attr-defined]
                request.method,
                data.get("params"),
                opts,
            )
        except MCPError as error:
            if error.code in {REQUEST_TIMEOUT, CONNECTION_CLOSED}:
                return MCPClientExchange(
                    observation=ProtocolObservation(
                        outcome=ProtocolOutcome.OUTCOME_UNKNOWN,
                        protocol_request_id=request.protocol_request_id,
                        application_operation_id=(
                            binding.application_operation_id
                        ),
                        reason=error.message,
                    )
                )
            error_value: dict[str, Any] = {
                "code": error.code,
                "message": error.message,
            }
            if error.data is not None:
                error_value["data"] = error.data
            return MCPClientExchange(
                response=MCPResponseDTO(
                    protocol_request_id=request.protocol_request_id,
                    error=error_value,
                )
            )

        result_type = _RESULT_TYPES[request.method]
        try:
            validated = result_type.model_validate(raw, by_name=False)
        except ValidationError:
            return MCPClientExchange(
                observation=ProtocolObservation(
                    outcome=ProtocolOutcome.INVALID_MESSAGE,
                    protocol_request_id=request.protocol_request_id,
                    application_operation_id=(
                        binding.application_operation_id
                    ),
                    reason="SDK result validation failed",
                )
            )
        result: Mapping[str, Any] = validated.model_dump(
            by_alias=True,
            mode="json",
            exclude_none=True,
        )
        return MCPClientExchange(
            response=MCPResponseDTO(
                protocol_request_id=request.protocol_request_id,
                result=dict(result),
            )
        )
