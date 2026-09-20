"""SDK-private Day94 conversion from PydanticAI output to an application DTO.

PydanticAI-native values are unpacked at the caller-facing edge.  The core
receives only ``FrameworkToolCall`` and returns ``AgentMCPToolProposal``.
This adapter has no Tool transport, authorization service, or Committer.
"""
from __future__ import annotations

from collections.abc import Mapping

from agent_framework_adapter import FrameworkToolCall, ProposalValidationError
from agent_mcp_capstone import AgentMCPToolProposal


class PydanticAICapstoneAdapter:
    """Strict conversion for the deterministic Research Agent proposal."""

    adapter_id = "pydantic-ai-capstone"

    def to_proposal(self, output: FrameworkToolCall) -> AgentMCPToolProposal:
        if output.tool_name != "proposal_handler":
            raise ProposalValidationError("unexpected framework handler")

        payload = dict(output.arguments)
        if set(payload) != {"tool_name", "tool_version", "arguments"}:
            raise ProposalValidationError(
                "capstone proposal fields must match the strict schema"
            )
        tool_name = payload["tool_name"]
        tool_version = payload["tool_version"]
        arguments = payload["arguments"]
        if not isinstance(tool_name, str) or not tool_name:
            raise ProposalValidationError("tool_name must be a non-empty string")
        if not isinstance(tool_version, str) or not tool_version:
            raise ProposalValidationError("tool_version must be a non-empty string")
        if not isinstance(arguments, Mapping):
            raise ProposalValidationError("arguments must be an object mapping")
        try:
            return AgentMCPToolProposal.from_mapping(
                tool_name=tool_name,
                tool_version=tool_version,
                arguments=arguments,
            )
        except (TypeError, ValueError) as exc:
            raise ProposalValidationError("arguments must be JSON-compatible") from exc
