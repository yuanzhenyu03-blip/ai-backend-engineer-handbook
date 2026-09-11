"""Day90 deterministic seed evaluation for the MCP Client boundary."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp_client import DependencyFreeMCPClientAdapter  # noqa: E402
from mcp_client_codec import MCPCodecError, MCPWireCodec  # noqa: E402
from mcp_client_transport import (  # noqa: E402
    DispatchCertainty,
    MCPTransportFailure,
)
from mcp_protocol_model import (  # noqa: E402
    BindingStatus,
    CURRENT_SPECIFICATION_VERSION,
    ExternalContentCandidate,
    ExternalContentKind,
    MCPProtocolBoundary,
    MCPRequestBinding,
    MCPRequestDTO,
    MCPResponseDTO,
    validate_external_content_candidate,
    validate_read_resource_content,
)


def request(request_id: str = "request-1") -> MCPRequestDTO:
    return MCPRequestDTO(
        CURRENT_SPECIFICATION_VERSION,
        request_id,
        "tools/call",
        {"name": "research.lookup", "arguments": {"query": "MCP"}},
        client_capabilities=frozenset({"tools"}),
        observed_server_capabilities=frozenset({"tools"}),
    )


def binding(request_id: str = "request-1") -> MCPRequestBinding:
    return MCPRequestBinding(
        request_id,
        "op-report-42",
        "tools/call",
        "fingerprint-1",
        tenant_id="tenant-a",
        resource_id="report-42",
        idempotency_key="idem-report-42",
    )


class ByteTransport:
    def __init__(
        self,
        response: bytes,
        certainty: DispatchCertainty | None = None,
    ) -> None:
        self.response = response
        self.certainty = certainty
        self.messages: list[bytes] = []

    def exchange(self, message: bytes) -> bytes:
        self.messages.append(message)
        if self.certainty is not None:
            raise MCPTransportFailure(
                "controlled transport failure",
                dispatch_certainty=self.certainty,
            )
        return self.response


def result(
    outcome: str,
    *,
    sends: int = 0,
    resource_reads: int = 0,
) -> dict[str, object]:
    return {
        "outcome": outcome,
        "sends": sends,
        "resource_reads": resource_reads,
        "durable_transition": False,
    }


def evaluate(category: str) -> dict[str, object]:
    codec = MCPWireCodec()
    if category in {"wire_metadata", "application_id_isolated"}:
        message = json.loads(codec.encode_request(request()))
        if category == "wire_metadata":
            meta = message["params"]["_meta"]
            assert meta["io.modelcontextprotocol/protocolVersion"] == CURRENT_SPECIFICATION_VERSION
            return result("ENCODED_CURRENT_METADATA")
        assert "application_operation_id" not in json.dumps(message)
        return result("APPLICATION_ID_NOT_ON_WIRE")
    if category in {
        "adapter_success",
        "possible_send_timeout",
        "proven_not_sent",
        "malformed_response",
        "binding_mismatch",
    }:
        response = (
            b'{"jsonrpc":"2.0","id":"request-1","result":{"content":[]}}'
            if category != "malformed_response"
            else b'{"jsonrpc":"2.0","id":"request-1"}'
        )
        certainty = (
            DispatchCertainty.POSSIBLY_SENT
            if category == "possible_send_timeout"
            else DispatchCertainty.PROVEN_NOT_SENT
            if category == "proven_not_sent"
            else None
        )
        transport = ByteTransport(response, certainty)
        local_binding = binding(
            "different-request" if category == "binding_mismatch" else "request-1"
        )
        try:
            exchange = DependencyFreeMCPClientAdapter(transport).exchange(
                request(), local_binding
            )
        except MCPCodecError:
            return result("INVALID_MESSAGE", sends=len(transport.messages))
        except ValueError:
            return result("REJECTED_PRE_DISPATCH", sends=len(transport.messages))
        if exchange.observation is not None:
            return result(
                exchange.observation.outcome.value,
                sends=len(transport.messages),
            )
        return result("RESPONSE_DTO", sends=len(transport.messages))

    boundary = MCPProtocolBoundary(transport=object())  # type: ignore[arg-type]
    local_binding = binding()
    boundary.bindings["request-1"] = local_binding
    boundary.binding_status["request-1"] = BindingStatus.PENDING
    if category == "pre_dispatch_abort":
        observation = boundary.abort_before_dispatch(
            "request-1", reason="inventory changed"
        )
        return result(observation.outcome.value)
    if category == "post_dispatch_cancellation":
        observation = boundary.mark_outcome_unknown(
            "request-1", reason="caller cancelled after dispatch"
        )
        return result(observation.outcome.value)
    if category in {"resource_scope_rejected", "resource_injection_after_read"}:
        candidate = ExternalContentCandidate(
            ExternalContentKind.RESOURCE,
            "research://tenant-b/report-42"
            if category == "resource_scope_rejected"
            else "research://tenant-a/report-42",
            tenant_id="tenant-b" if category == "resource_scope_rejected" else "tenant-a",
            resource_id="report-42",
            injection_suspected=category == "resource_injection_after_read",
        )
        decision = (
            validate_external_content_candidate(local_binding, candidate)
            if category == "resource_scope_rejected"
            else validate_read_resource_content(local_binding, candidate)
        )
        return result(
            decision.outcome.value,
            resource_reads=decision.resource_reads,
        )
    first = MCPResponseDTO("request-1", result={"content": []})
    boundary.correlate(first)
    if category == "duplicate_response":
        return result(boundary.correlate(first).outcome.value)
    if category == "conflicting_response":
        second = MCPResponseDTO("request-1", result={"content": [{"different": True}]})
        return result(boundary.correlate(second).outcome.value)
    raise ValueError("unknown seed category")


def grade(case: dict[str, object], actual: dict[str, object]) -> list[str]:
    mapping = {
        "outcome": "expected_outcome",
        "sends": "expected_sends",
        "resource_reads": "expected_resource_reads",
        "durable_transition": "expected_durable_transition",
    }
    return [
        actual_key
        for actual_key, expected_key in mapping.items()
        if actual.get(actual_key) != case.get(expected_key)
    ]


def main() -> int:
    path = Path(__file__).with_name("day90_mcp_client_seed.jsonl")
    cases = [json.loads(line) for line in path.read_text().splitlines() if line]
    if not 12 <= len(cases) <= 16:
        raise ValueError("Day90 seed requires 12 to 16 cases")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Day90 seed case IDs must be unique")
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
