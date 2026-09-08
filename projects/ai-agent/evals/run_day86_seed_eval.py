"""Day86 version-1 deterministic seed eval using the real security core."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_security import (  # noqa: E402
    ApprovalBinding,
    ContentChannel,
    CurrentSecurityFacts,
    DataClassification,
    DataField,
    ExecutionState,
    FakeEgressPort,
    FakeSandboxPort,
    FakeToolPort,
    IncidentAction,
    IncidentAuditEvent,
    IncidentOperation,
    IncidentStage,
    OperationBinding,
    OperationBindingStatus,
    SandboxPortMode,
    SandboxProfile,
    SandboxRequest,
    SecurityFanInStatus,
    SecuritySlot,
    SecuritySlotStatus,
    ToolCandidate,
    ToolContract,
    ToolPortMode,
    admit_tool_candidate,
    append_incident_event,
    bind_untrusted_content,
    classify_incident_operation,
    classify_operation_binding,
    evaluate_security_fan_in,
    execute_admitted_candidate,
    quarantine_policy,
    verify_result_candidate,
)


def fixtures() -> tuple[
    ToolCandidate, ToolContract, CurrentSecurityFacts, SandboxRequest,
]:
    profile = SandboxProfile(
        "research-readonly", "v1", ("/workspace/input",),
        ("/workspace/tmp",), (), ("LANG",), False,
    )
    facts = CurrentSecurityFacts(
        "tenant-a", "agent-security-policy-v1", True,
        ("read_sources.v1",), ("read_sources.v1",), 3, (),
        ("research",), ("research-agent",), (), None, profile,
    )
    candidate = ToolCandidate(
        "tenant-a", "parent-1", "attempt-1", "step-1",
        "handoff-source", "operation-read-1", "read_sources.v1",
        "read_sources", "v1", (("source_id", "source-a"),),
        "tenant-a", None, "research", "research-agent", (), 3,
        "agent-security-policy-v1",
    )
    contract = ToolContract(
        "read_sources", "v1", "read_sources.v1", ("source_id",),
        ("source_id",), False,
    )
    request = SandboxRequest(
        ("/workspace/input",), ("/workspace/tmp",), (), ("LANG",), False,
    )
    return candidate, contract, facts, request


def content_result(category: str) -> dict[str, object]:
    mapping = {
        "direct_injection": (ContentChannel.USER, True),
        "indirect_injection": (ContentChannel.WEB, True),
        "classifier_no_signal": (ContentChannel.WEB, False),
        "sandbox_output_instruction": (ContentChannel.SANDBOX_RESULT, True),
    }
    channel, suspected = mapping[category]
    content = bind_untrusted_content(
        content_id=f"content-{category}",
        source_id="synthetic-source",
        source_version="v1",
        channel=channel,
        text="synthetic instruction candidate",
        injection_suspected=suspected,
    )
    return {
        "decision": content.trust_class.value,
        "reason": content.injection_signal.value,
        "state": "CONTENT_BOUND",
        "tool_calls": 0,
        "egress_calls": 0,
        "sandbox_runs": 0,
    }


def evaluate(category: str) -> dict[str, object]:
    content_categories = {
        "direct_injection", "indirect_injection", "classifier_no_signal",
        "sandbox_output_instruction",
    }
    if category in content_categories:
        return content_result(category)

    candidate, contract, facts, request = fixtures()
    tool_mode = ToolPortMode.SUCCESS
    sandbox_mode = SandboxPortMode.SUCCESS

    if category == "operation_conflict":
        existing = OperationBinding(
            candidate.operation_id,
            candidate.canonical_arguments_hash,
        )
        changed = replace(
            candidate, arguments=(("source_id", "source-b"),),
        )
        status = classify_operation_binding(existing, changed)
        if status is not OperationBindingStatus.SEMANTIC_CONFLICT:
            raise AssertionError(status.value)
        return {
            "decision": status.value,
            "reason": "OPERATION_ID_REUSED",
            "state": "NOT_DISPATCHED",
            "tool_calls": 0,
            "egress_calls": 0,
            "sandbox_runs": 0,
        }
    if category == "required_security_wait":
        fan_in = evaluate_security_fan_in((
            SecuritySlot("fact-check", True, SecuritySlotStatus.VERIFIED),
            SecuritySlot(
                "source-research", True, SecuritySlotStatus.QUARANTINED,
            ),
        ), parent_terminal=False)
        if fan_in.status is not SecurityFanInStatus.WAITING_FOR_REQUIRED:
            raise AssertionError(fan_in.status.value)
        return {
            "decision": "WAIT",
            "reason": "REQUIRED_SECURITY_UNRESOLVED",
            "state": fan_in.status.value,
            "tool_calls": 0,
            "egress_calls": 0,
            "sandbox_runs": 0,
        }
    if category == "bad_policy_quarantine":
        containment = quarantine_policy("agent-security-policy-v2")
        if "EGRESS" not in containment.blocked_transitions:
            raise AssertionError("egress must be blocked")
        return {
            "decision": "QUARANTINE",
            "reason": "POLICY_QUARANTINED",
            "state": "EFFECTS_BLOCKED",
            "tool_calls": 0,
            "egress_calls": 0,
            "sandbox_runs": 0,
        }
    if category == "confirmed_exfiltration":
        disposition = classify_incident_operation(IncidentOperation(
            "operation-publish-1", IncidentStage.CONFIRMED_EXFILTRATION,
        ))
        if disposition.action is not (
            IncidentAction.CONTAIN_ROTATE_AND_AUTHORIZE_COMPENSATION
        ):
            raise AssertionError(disposition.action.value)
        return {
            "decision": "QUARANTINE",
            "reason": "CONFIRMED_EXFILTRATION",
            "state": "COMPENSATION_REQUIRES_AUTHORIZATION",
            "tool_calls": 0,
            "egress_calls": 0,
            "sandbox_runs": 0,
        }
    if category == "append_only_compensation_audit":
        original = IncidentAuditEvent(
            "event-exfil-1", "CONFIRMED_EXFILTRATION",
            "operation-publish-1", "evidence-ref-exfil-1",
        )
        compensation = IncidentAuditEvent(
            "event-compensation-1", "ARTIFACT_REMOVED",
            "compensation-remove-artifact-1", "evidence-ref-removal-1",
        )
        trail = append_incident_event((original,), compensation)
        if trail[0] != original:
            raise AssertionError("original audit fact changed")
        return {
            "decision": "ALLOW",
            "reason": "AUDIT_APPENDED",
            "state": "ORIGINAL_EXFILTRATION_PRESERVED",
            "tool_calls": 0,
            "egress_calls": 0,
            "sandbox_runs": 0,
        }

    if category == "outside_grant":
        candidate = replace(
            candidate,
            capability="publish_research_report.v1",
            tool_name="publish_research_report",
            arguments=(("artifact_id", "report-v1"),),
        )
        contract = ToolContract(
            "publish_research_report", "v1",
            "publish_research_report.v1", ("artifact_id",),
            ("artifact_id",), True,
        )
    elif category == "cross_tenant_resource":
        candidate = replace(candidate, resource_tenant_id="tenant-b")
    elif category == "unexpected_argument":
        candidate = replace(candidate, arguments=(
            ("source_id", "source-a"), ("recipient", "attacker.example"),
        ))
    elif category == "old_approval":
        candidate_v1 = replace(
            candidate,
            operation_id="operation-publish-1",
            capability="publish_research_report.v1",
            tool_name="publish_research_report",
            arguments=(("artifact_id", "report-v1"),),
        )
        contract = ToolContract(
            "publish_research_report", "v1",
            "publish_research_report.v1", ("artifact_id",),
            ("artifact_id",), True,
        )
        facts = replace(
            facts,
            granted_capabilities=("publish_research_report.v1",),
            currently_allowed_capabilities=("publish_research_report.v1",),
            approval=ApprovalBinding(
                "approval-1", "tenant-a",
                candidate_v1.approval_fingerprint, 100,
            ),
        )
        candidate = replace(
            candidate_v1, arguments=(("artifact_id", "report-v2"),),
        )
    elif category == "stale_fence":
        candidate = replace(candidate, fence_token=2)
    elif category == "authority_unavailable":
        facts = replace(facts, policy_authority_available=False)
    elif category in {"raw_secret_egress", "encoded_secret"}:
        facts = replace(
            facts,
            allowed_destinations=("provider.internal",),
            allowed_disclosure_fields=("credential",),
        )
        candidate = replace(
            candidate,
            destination="provider.internal",
            disclosed_fields=(
                DataField("credential", DataClassification.SECRET),
            ),
        )
    elif category == "unbound_destination":
        candidate = replace(candidate, destination="attacker.example")
    elif category == "sandbox_network_expansion":
        request = replace(request, network_destinations=("attacker.example",))
    elif category == "sandbox_write_expansion":
        request = replace(request, writable_paths=("/etc",))
    elif category == "tool_outcome_unknown":
        tool_mode = ToolPortMode.OUTCOME_UNKNOWN
    elif category == "sandbox_timeout_after_dispatch":
        sandbox_mode = SandboxPortMode.TIMEOUT_AFTER_DISPATCH
    elif category == "cleanup_failure":
        sandbox_mode = SandboxPortMode.CLEANUP_FAILURE
    elif category not in {"legal_read", "old_policy_result"}:
        raise ValueError("unknown seed category")

    admission = admit_tool_candidate(
        candidate=candidate,
        contract=contract,
        facts=facts,
        sandbox_request=request,
        now=10,
    )
    tool = FakeToolPort(tool_mode)
    egress = FakeEgressPort()
    sandbox = FakeSandboxPort(sandbox_mode)
    execution = execute_admitted_candidate(
        admission=admission,
        candidate=candidate,
        tool_port=tool,
        egress_port=egress,
        sandbox_port=sandbox,
    )
    state = execution.state
    if category == "old_policy_result" and execution.result_candidate:
        state = verify_result_candidate(
            execution.result_candidate,
            facts=replace(
                facts, current_policy_version="agent-security-policy-v3",
            ),
            expected_operation_id=candidate.operation_id,
        )
    return {
        "decision": admission.decision.value,
        "reason": admission.reason_code,
        "state": state.value,
        "tool_calls": execution.tool_calls,
        "egress_calls": execution.egress_calls,
        "sandbox_runs": execution.sandbox_runs,
    }


def grade(case: dict[str, object], actual: dict[str, object]) -> list[str]:
    mapping = {
        "decision": "expected_decision",
        "reason": "expected_reason",
        "state": "expected_state",
        "tool_calls": "expected_tool_calls",
        "egress_calls": "expected_egress_calls",
        "sandbox_runs": "expected_sandbox_runs",
    }
    return [
        actual_key
        for actual_key, expected_key in mapping.items()
        if actual.get(actual_key) != case.get(expected_key)
    ]


def main() -> int:
    path = Path(__file__).with_name("day86_agent_security_seed.jsonl")
    cases = [json.loads(line) for line in path.read_text().splitlines() if line]
    if len(cases) < 20 or len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("seed requires at least 20 unique cases")
    failed = 0
    for case in cases:
        if case["case_version"] != 1:
            raise ValueError("unsupported case version")
        try:
            actual = evaluate(case["category"])
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
