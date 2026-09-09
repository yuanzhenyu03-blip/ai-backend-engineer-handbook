"""Contract-level LangGraph translation for the Day88 application boundary.

This module deliberately does not import or execute LangGraph. It models the
documented ToolCall envelope that a private LangGraph runtime adapter would
translate. Framework output remains an untrusted proposal, and no production
Tool client is accepted or retained here.
"""
from collections.abc import Mapping

from agent_framework_adapter import (
    FrameworkToolCall,
    ProposalValidationError,
    ToolProposal,
)


class LangGraphAdapter:
    """Translate a strict LangGraph-style ToolCall into an application DTO."""

    adapter_id = "langgraph@1.2.11"

    def to_proposal(self, output: FrameworkToolCall) -> ToolProposal:
        if output.tool_name != "tools":
            raise ProposalValidationError("unexpected LangGraph node")
        if not isinstance(output.arguments, Mapping):
            raise ProposalValidationError("LangGraph ToolCall must be a mapping")

        tool_call = dict(output.arguments)
        if set(tool_call) != {"name", "args", "id", "type"}:
            raise ProposalValidationError(
                "LangGraph ToolCall fields must match strict schema"
            )
        if (
            type(tool_call["name"]) is not str
            or tool_call["name"] != "proposal_handler"
        ):
            raise ProposalValidationError("unexpected proposal handler")
        if (
            type(tool_call["id"]) is not str
            or not tool_call["id"]
            or type(tool_call["type"]) is not str
            or tool_call["type"] != "tool_call"
        ):
            raise ProposalValidationError("invalid LangGraph ToolCall identity")

        raw_arguments = tool_call["args"]
        if not isinstance(raw_arguments, Mapping):
            raise ProposalValidationError("ToolCall args must be a mapping")
        arguments = dict(raw_arguments)
        if set(arguments) != {"tool_name", "amount_minor", "currency"}:
            raise ProposalValidationError("proposal fields must match strict schema")

        tool_name = arguments["tool_name"]
        amount_minor = arguments["amount_minor"]
        currency = arguments["currency"]
        if not isinstance(tool_name, str) or not tool_name:
            raise ProposalValidationError("tool_name must be a non-empty string")
        if type(amount_minor) is not int or amount_minor <= 0:
            raise ProposalValidationError("amount_minor must be a positive integer")
        if not isinstance(currency, str) or len(currency) != 3:
            raise ProposalValidationError("currency must be a three-letter code")
        return ToolProposal(tool_name, amount_minor, currency.upper())
