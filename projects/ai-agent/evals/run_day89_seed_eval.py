"""Day89 version-1 deterministic seed eval using the real protocol model."""
from __future__ import annotations

from dataclasses import replace
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
from mcp_fake_transport import FakeMCPTransport  # noqa: E402
from mcp_protocol_model import (  # noqa: E402
    CURRENT_SPECIFICATION_VERSION,
    ExternalContentCandidate,
    ExternalContentKind,
    MCPProtocolBoundary,
    MCPRequestDTO,
    MCPResponseDTO,
    TimeoutAfterPossibleSend,
    validate_external_content_candidate,
)
from pydantic_ai_framework_adapter import PydanticAIAdapter  # noqa: E402


def tool_request(
    request_id: str = "mcp-request-7",
    *,
    version: str = CURRENT_SPECIFICATION_VERSION,
    capabilities: frozenset[str] = frozenset({"tools"}),
) -> MCPRequestDTO:
    return MCPRequestDTO(
        version,
        request_id,
        "tools/call",
        {"name": "search_documents", "arguments": {"query": "MCP"}},
        observed_server_capabilities=capabilities,
    )


def result(
    outcome: str,
    boundary: MCPProtocolBoundary,
    transport: object,
    *,
    durable_transition: bool = False,
) -> dict[str, object]:
    sent = getattr(transport, "sent")
    return {
        "outcome": outcome,
        "mcp_sends": len(sent),
        "bindings": len(boundary.bindings),
        "durable_transition": durable_transition,
    }


def denied_by_committer(*, stale_policy: bool) -> dict[str, object]:
    transport = FakeMCPTransport()
    boundary = MCPProtocolBoundary(transport)

    class ProtocolTool:
        def invoke(self, *, operation_id: str, proposal: ToolProposal) -> dict[str, object]:
            observation = boundary.dispatch(
                tool_request(), application_operation_id=operation_id
            )
            return {"protocol_outcome": observation.outcome.value}

    proposal = ToolProposal("refund", 100, "USD")
    envelope = ProposalEnvelope("op-42", "attempt-1", "approval-1", 5, 9, 2_000)
    facts = CurrentFacts(
        "op-42",
        True if stale_policy else False,
        "approval-1",
        canonical_intent_hash(proposal),
        5,
        10 if stale_policy else 9,
        1_000,
    )
    audit = Committer(ProtocolTool()).process(
        PydanticAIAdapter(),
        FrameworkToolCall(
            "proposal_handler",
            {"tool_name": "refund", "amount_minor": 100, "currency": "USD"},
        ),
        envelope,
        facts,
    )
    return result(
        f"{audit.outcome.value}:{audit.reasons[0]}",
        boundary,
        transport,
        durable_transition=audit.durable_transition,
    )


class AlternateFakeTransport:
    def __init__(self) -> None:
        self.sent: list[MCPRequestDTO] = []

    def send(self, request: MCPRequestDTO) -> MCPResponseDTO:
        self.sent.append(request)
        return MCPResponseDTO(
            request.protocol_request_id,
            result={"resultType": "complete", "documents": []},
        )


def evaluate(category: str) -> dict[str, object]:
    if category == "authorization_revoked":
        return denied_by_committer(stale_policy=False)
    if category == "committer_final_gate":
        return denied_by_committer(stale_policy=True)
    if category == "unknown_response":
        transport = FakeMCPTransport()
        boundary = MCPProtocolBoundary(transport)
        observation = boundary.correlate(
            MCPResponseDTO("unknown-request", result={"ok": True})
        )
        return result(observation.outcome.value, boundary, transport)
    if category == "replaceable_transport":
        transport = AlternateFakeTransport()
        boundary = MCPProtocolBoundary(transport)
        observation = boundary.dispatch(
            tool_request(), application_operation_id="op-report-42"
        )
        return result(
            observation.outcome.value,
            boundary,
            transport,
            durable_transition=observation.durable_transition,
        )

    response = MCPResponseDTO(
        "mcp-request-7",
        result={"resultType": "complete", "documents": []},
    )
    transport = FakeMCPTransport(responses={"mcp-request-7": response})
    boundary = MCPProtocolBoundary(transport)
    request = tool_request()

    if category == "unsupported_version":
        request = tool_request(version="2025-11-25")
    elif category == "unknown_method":
        request = replace(request, method="initialize", params={})
    elif category == "invalid_params":
        request = replace(
            request,
            params={"name": "search_documents", "arguments": {}, "approve": True},
        )
    elif category == "capability_mismatch":
        request = tool_request(capabilities=frozenset())
    elif category == "timeout_after_possible_send":
        transport = FakeMCPTransport(
            timeout_after_possible_send=frozenset({"mcp-request-7"})
        )
        boundary = MCPProtocolBoundary(transport)
    elif category in {"cross_tenant_resource", "untrusted_prompt"}:
        transport = FakeMCPTransport(responses={"mcp-request-7": None})
        boundary = MCPProtocolBoundary(transport)
        boundary.dispatch(
            request,
            application_operation_id="op-report-42",
            tenant_id="tenant-a",
            resource_id="report-42",
        )
        candidate = (
            ExternalContentCandidate(
                ExternalContentKind.RESOURCE,
                "research://tenant-b/report-42",
                tenant_id="tenant-b",
                resource_id="report-42",
            )
            if category == "cross_tenant_resource"
            else ExternalContentCandidate(
                ExternalContentKind.PROMPT,
                "prompt://server/ignore-authorization",
                injection_suspected=True,
            )
        )
        decision = validate_external_content_candidate(
            boundary.bindings["mcp-request-7"], candidate
        )
        return result(
            decision.outcome.value,
            boundary,
            transport,
            durable_transition=decision.durable_transition,
        )
    elif category not in {
        "valid_current_message",
        "identity_separation",
        "duplicate_response",
        "conflicting_response",
        "protocol_result_observation_only",
    }:
        raise ValueError("unknown seed category")

    observation = boundary.dispatch(request, application_operation_id="op-report-42")
    outcome = observation.outcome.value
    durable_transition = observation.durable_transition
    if category == "identity_separation":
        binding = boundary.bindings["mcp-request-7"]
        if binding.application_operation_id == binding.protocol_request_id:
            raise AssertionError("protocol and operation IDs were conflated")
        outcome = "IDS_SEPARATED"
    elif category == "duplicate_response":
        outcome = boundary.correlate(response).outcome.value
    elif category == "conflicting_response":
        outcome = boundary.correlate(
            MCPResponseDTO(
                "mcp-request-7",
                result={"resultType": "complete", "documents": ["different"]},
            )
        ).outcome.value
    return result(
        outcome,
        boundary,
        transport,
        durable_transition=durable_transition,
    )


def grade(case: dict[str, object], actual: dict[str, object]) -> list[str]:
    mapping = {
        "outcome": "expected_outcome",
        "mcp_sends": "expected_mcp_sends",
        "bindings": "expected_bindings",
        "durable_transition": "expected_durable_transition",
    }
    return [
        actual_key
        for actual_key, expected_key in mapping.items()
        if actual.get(actual_key) != case.get(expected_key)
    ]


def main() -> int:
    path = Path(__file__).with_name("day89_mcp_protocol_seed.jsonl")
    cases = [json.loads(line) for line in path.read_text().splitlines() if line]
    if not 12 <= len(cases) <= 16:
        raise ValueError("Day89 seed requires 12 to 16 cases")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Day89 seed case IDs must be unique")
    failed = 0
    for case in cases:
        if case["case_version"] != 1:
            raise ValueError("unsupported case version")
        try:
            actual = evaluate(str(case["category"]))
            differences = grade(case, actual)
            status = "FAIL" if differences else "PASS"
        except (AssertionError, KeyError, TypeError, ValueError) as error:
            actual = {"error_class": type(error).__name__}
            differences = ["exception"]
            status = "FAIL"
        failed += status == "FAIL"
        print(json.dumps({
            "case_id": case["case_id"],
            "result": status,
            "differences": differences,
            "actual": actual,
        }, sort_keys=True))
    print(json.dumps({
        "cases": len(cases),
        "passed": len(cases) - failed,
        "failed": failed,
        "case_version": 1,
        "evidence_level": "EXECUTED_LOCAL_RUNTIME",
    }, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
