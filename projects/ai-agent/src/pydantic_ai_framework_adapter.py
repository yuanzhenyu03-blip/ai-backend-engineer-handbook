"""Private PydanticAI translation for the Day88 application contract.

PydanticAI-native objects may be unpacked before this boundary, but they never
enter application core interfaces or durable business state.
"""
from agent_framework_adapter import (
    FrameworkToolCall,
    ProposalValidationError,
    ToolProposal,
)


class PydanticAIAdapter:
    """Selected course Adapter for pydantic-ai-slim 2.41.0."""

    adapter_id = "pydantic-ai-slim@2.41.0"

    def to_proposal(self, output: FrameworkToolCall) -> ToolProposal:
        if output.tool_name != "proposal_handler":
            raise ProposalValidationError("unexpected framework handler")
        arguments = dict(output.arguments)
        expected = {"tool_name", "amount_minor", "currency"}
        if set(arguments) != expected:
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
