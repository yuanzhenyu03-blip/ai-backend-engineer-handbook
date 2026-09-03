"""Versioned deterministic seed evaluation. Never writes expected answers.

Inputs are synthetic fixture-v1 overrides, not an authenticated callback API.
Evidence is checked as a required subset; five decision fields are exact.
Actual apply/dispatch runs in the same in-memory Artifact. No LLM judge/I/O.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_state_machine import AgentState
from durable_agent_jobs import ExternalCertainty
from human_control import ApprovalStatus, Operation
from human_control_scenarios import build_scenario
from tool_governance import InvocationGovernanceStatus


def enum_or_unknown(enum: Any, value: str) -> Any:
    try:
        return enum(value)
    except ValueError:
        return value  # Deliberate invalid-input case; core must fail closed.


def evaluate_facts(inputs: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "approved", "approval_status", "callback", "now", "operation",
        "wrong_tenant", "self_approval", "artifact_version", "arguments_fingerprint",
        "authorization", "tool_enabled", "external_certainty", "dispatch_started",
        "recovery_used", "job_state", "compensation", "policy_available",
        "owner_available", "verified_usage", "policy_quarantined",
    }
    if set(inputs) - allowed:
        raise ValueError("unknown fixture input field")
    s = build_scenario()
    if inputs.get("approved"):
        s.approve()
    snapshot = s.store.snapshot
    action = snapshot.action
    for field in ("artifact_version", "arguments_fingerprint"):
        if field in inputs:
            action = replace(action, **{field: inputs[field]})
    if inputs.get("compensation"):
        action = replace(action, action_type="compensate",
                         tool_name="retract_research_report",
                         operation_id="new-compensation-operation")
    snapshot = replace(snapshot, action=action,
                       dispatch_started=inputs.get("dispatch_started", False))
    if "approval_status" in inputs:
        snapshot = replace(snapshot, approval=enum_or_unknown(
            ApprovalStatus, inputs["approval_status"]))
    if "job_state" in inputs:
        snapshot = replace(snapshot, job=replace(snapshot.job,
            state=enum_or_unknown(AgentState, inputs["job_state"])))
    s.store.snapshot = snapshot
    facts = s.facts
    for field in ("policy_available", "owner_available", "policy_quarantined"):
        if field in inputs:
            facts = replace(facts, **{field: inputs[field]})
    if inputs.get("wrong_tenant"):
        facts = replace(facts, approver=replace(facts.approver, tenant_id="tenant-b"))
    if inputs.get("self_approval"):
        facts = replace(facts, approver=replace(facts.approver, actor_id="requester"))
    if inputs.get("authorization") is False:
        facts = replace(facts, executor=replace(facts.executor, permissions=()))
    if inputs.get("tool_enabled") is False:
        s.registry.disable("publish_research_report", "v1")
        facts = replace(facts,
            governance=InvocationGovernanceStatus.CURRENT_REGISTRY_BLOCKED)
    if "external_certainty" in inputs:
        facts = replace(facts, certainty=enum_or_unknown(
            ExternalCertainty, inputs["external_certainty"]))
    if "recovery_used" in inputs:
        facts = replace(facts, recovery=replace(facts.recovery,
                                               attempts_used=inputs["recovery_used"]))
    if "verified_usage" in inputs:
        facts = replace(facts, verified_usage=inputs["verified_usage"],
                        outcome_evidence_id="synthetic-verified-usage")
    s.facts = facts
    now = inputs.get("now", 30)
    operation = enum_or_unknown(Operation, inputs.get("operation", "GATE"))
    command = s.command(operation, "eval-command")
    callback = inputs.get("callback")
    if callback in {"normal", "duplicate"}:
        command = s.approval_command("eval-command")
    elif callback == "conflict":
        command = s.approval_command("eval-command", choice=ApprovalStatus.REJECTED,
                                     binding_fingerprint="F2")
    elif callback is not None:
        raise ValueError("unknown callback fixture")
    if operation is Operation.LATE_RESULT:
        command = replace(command, evidence_id="late-evidence",
                          source_attempt_id=snapshot.action.attempt_id,
                          source_operation_id=snapshot.action.operation_id,
                          source_fence=snapshot.job.fence_token - 1)
    before = s.store.snapshot
    candidate = s.store.plan(command, facts, now)
    applied = s.store.apply(candidate, facts, now)
    if candidate.execution_allowed and applied == "APPLIED":
        event = next(e for e in s.store.snapshot.job.outbox_intents
                     if e.event_type == "PUBLISH")
        s.store.dispatch_once(event.event_id, s.worker,
                              s.store.snapshot.job.fence_token,
                              facts, now, s.local_effect)
    after = s.store.snapshot
    effects: list[str] = []
    if s.effect_calls:
        effects.append("publish_call")
    if any(a.released_units > b.released_units
           for a, b in zip(after.job.reservations, before.job.reservations)):
        effects.append("reservation_release")
    if after.action.attempt_id != before.action.attempt_id:
        effects.append("new_attempt")
    if len(after.job.reservations) > len(before.job.reservations):
        effects.append("new_reservation")
    if after.job.state_version != before.job.state_version:
        effects.append("business_version_change")
    if any(e.event_type == "PUBLISH" for e in after.job.outbox_intents
           if e not in before.job.outbox_intents):
        effects.append("publish_outbox")
    return {
        "decision": candidate.status, "next_state": candidate.next_state.value,
        "execution_allowed": candidate.execution_allowed,
        "reservation_action": candidate.reservation_action.value,
        "outbox_action": candidate.outbox_action,
        "evidence": list(candidate.evidence), "effects": effects,
        "apply_status": applied, "local_effect_calls": s.effect_calls,
        "external_provider_calls": 0, "external_tool_calls": 0,
        "audit_count": len(after.job.audit_events),
    }


def grade(case: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    differences = []
    for field in ("decision", "next_state", "execution_allowed",
                  "reservation_action", "outbox_action"):
        expected = case["expected_" + field]
        if type(actual[field]) is not type(expected) or actual[field] != expected:
            differences.append(field)
    if not set(case["expected_evidence"]) <= set(actual["evidence"]):
        differences.append("evidence")
    if set(case["forbidden_effects"]) & set(actual["effects"]):
        differences.append("forbidden_effects")
    return differences


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    if case["case_version"] != 1 or case["fixture_version"] != 1:
        raise ValueError("unsupported case or fixture version")
    if case["category"] == "mixed_rollback":
        actuals = [evaluate_facts(item) for item in case["input_facts"]["items"]]
        diff = []
        for index, actual in enumerate(actuals):
            expectation = {
                "expected_" + field: case["expected_" + field][index]
                for field in ("decision", "next_state", "execution_allowed",
                              "reservation_action", "outbox_action")
            }
            expectation.update(expected_evidence=case["expected_evidence"][index],
                               forbidden_effects=case["forbidden_effects"][index])
            diff.extend("item-" + str(index) + ":" + d
                        for d in grade(expectation, actual))
        actual = {"items": actuals}
    else:
        actual = evaluate_facts(case["input_facts"])
        diff = grade(case, actual)
    return {"case_id": case["case_id"], "result": "FAIL" if diff else "PASS",
            "different_fields": diff, "actual": actual}


def main() -> int:
    path = Path(__file__).with_name("day83_human_control_seed.jsonl")
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("duplicate seed case identity")
    failed = 0
    for case in cases:
        try:
            result = run_case(case)
        except (ValueError, KeyError, TypeError, AssertionError) as error:
            # Do not log raw input/payloads or exception messages.
            result = {"case_id": case["case_id"], "result": "FAIL",
                      "error_class": type(error).__name__}
        failed += result["result"] != "PASS"
        print(json.dumps(result, sort_keys=True))
    print(json.dumps({"cases": len(cases), "passed": len(cases) - failed,
                      "failed": failed, "case_version": 1,
                      "evidence_level": "EXECUTED_LOCAL_RUNTIME"}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
