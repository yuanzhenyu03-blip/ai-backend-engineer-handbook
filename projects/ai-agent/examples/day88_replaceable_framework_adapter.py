"""Day88 deterministic example; no Provider, network or production Tool calls."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_framework_adapter import (  # noqa: E402
    Committer,
    CurrentFacts,
    FrameworkToolCall,
    ProposalEnvelope,
    ToolProposal,
    canonical_intent_hash,
)
from pydantic_ai_framework_adapter import PydanticAIAdapter  # noqa: E402


class FakeTool:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def invoke(
        self,
        *,
        operation_id: str,
        proposal: ToolProposal,
    ) -> dict[str, object]:
        self.calls.append(operation_id)
        return {"refund_id": "refund-88", "amount_minor": proposal.amount_minor}


def main() -> None:
    proposal = ToolProposal("refund", 100, "USD")
    facts = CurrentFacts(
        "op-88-1",
        True,
        "approval-88",
        canonical_intent_hash(proposal),
        8,
        3,
        1_000,
    )
    envelope = ProposalEnvelope(
        "op-88-1", "attempt-1", "approval-88", 8, 3, 2_000,
    )
    output = FrameworkToolCall(
        "proposal_handler",
        {"tool_name": "refund", "amount_minor": 100, "currency": "USD"},
    )
    tool = FakeTool()
    adapter = PydanticAIAdapter()
    audit = Committer(tool).process(adapter, output, envelope, facts)
    assert "tool" not in vars(adapter)
    print(json.dumps({
        "day": 88,
        "selected_candidate": "Candidate C",
        "adapter_id": adapter.adapter_id,
        "outcome": audit.outcome.value,
        "operation_id": audit.operation_id,
        "tool_calls": len(tool.calls),
        "production_provider_calls": 0,
        "production_tool_calls": 0,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "day89_handoff": "MCP Foundations and Protocol Model",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
