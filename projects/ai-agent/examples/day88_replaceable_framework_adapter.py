"""Day88 two-adapter contract example; no Provider, network or production Tool."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_framework_adapter import (  # noqa: E402
    Committer,
    CurrentFacts,
    FrameworkAdapter,
    FrameworkToolCall,
    ProposalEnvelope,
    ToolProposal,
    canonical_intent_hash,
)
from langgraph_framework_adapter import LangGraphAdapter  # noqa: E402
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
    cases: tuple[tuple[FrameworkAdapter, FrameworkToolCall], ...] = (
        (
            PydanticAIAdapter(),
            FrameworkToolCall(
                "proposal_handler",
                {"tool_name": "refund", "amount_minor": 100, "currency": "USD"},
            ),
        ),
        (
            LangGraphAdapter(),
            FrameworkToolCall(
                "tools",
                {
                    "name": "proposal_handler",
                    "args": {
                        "tool_name": "refund",
                        "amount_minor": 100,
                        "currency": "USD",
                    },
                    "id": "langgraph-call-1",
                    "type": "tool_call",
                },
            ),
        ),
    )

    results = []
    for adapter, output in cases:
        fake_tool = FakeTool()
        audit = Committer(fake_tool).process(adapter, output, envelope, facts)
        assert "tool" not in vars(adapter)
        results.append({
            "adapter_id": adapter.adapter_id,
            "outcome": audit.outcome.value,
            "operation_id": audit.operation_id,
            "fake_tool_calls": len(fake_tool.calls),
        })

    assert results[0]["outcome"] == results[1]["outcome"] == "COMPLETED"
    print(json.dumps({
        "day": 88,
        "default_course_adapter": "pydantic-ai-slim@2.41.0",
        "contract_level_adapters": results,
        "production_provider_calls": 0,
        "production_tool_calls": 0,
        "langgraph_runtime_executed": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "day89_handoff": "MCP Foundations and Protocol Model",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
