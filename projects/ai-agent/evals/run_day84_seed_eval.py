"""Day84 version-1 deterministic seed eval; expected facts are never written."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_state_machine import AgentState
from context_memory import (
    AssemblyStatus, CompactionCandidate, Completeness, ContextPart, ContextScope,
    FakeTokenEstimator, InMemoryMemoryStore, InMemorySummaryStore, MemoryKind,
    MemoryRecord, MemoryWriteCandidate, OmissionReason, ReferenceReadStatus,
    ResultReference, SourceSpan, SourceVersion, SummaryRevision,
    ValidatedToolResult, assemble_context, authorize_result_reference_read,
    bound_validated_tool_result, rehydrate_with_current_human_control,
    select_memories, source_fingerprint,
)
from durable_agent_jobs import ExternalCertainty, ReservationStatus
from human_control import Operation
from human_control_scenarios import build_scenario


def summary(revision: int = 7, end: int = 2,
            content: str = "synthetic summary") -> SummaryRevision:
    events = tuple(str(i) for i in range(1, end + 1))
    return SummaryRevision(
        "summary-1", revision,
        SourceSpan("tenant-a", "user-a", "session-a", 1, end,
                   source_fingerprint(events)),
        "context-policy-v1", "FAKE_DETERMINISTIC_SUMMARIZER", content,
    )


def evaluate(category: str) -> dict[str, object]:
    scope = ContextScope("tenant-a", "user-a", "session-a", "job-a")
    source = SourceVersion("source-1", 1, ("user-a",))
    memory = MemoryRecord(
        "memory-1", MemoryKind.EXPLICIT_PREFERENCE, 1, scope,
        "默认中文", (("source-1", 1),), expires_at=100,
    )
    effects: list[str] = []
    decision = "UNHANDLED"
    if category in {"allowed_preference", "cross_tenant", "expired_memory"}:
        record = memory
        now = 20
        if category == "cross_tenant":
            record = replace(memory, scope=replace(scope, tenant_id="tenant-b"))
        if category == "expired_memory":
            now = 100
        result = select_memories(
            (record,), scope=scope, now=now, current_sources=(source,),
        )
        decision = "SELECTED" if result.selected else result.omissions[0].reason.value
    elif category in {"summary_claimed_approval", "old_summary_new_artifact"}:
        scenario = build_scenario()
        if category == "old_summary_new_artifact":
            state = scenario.store.snapshot
            scenario.store.snapshot = replace(
                state, action=replace(state.action, artifact_version="8"),
            )
        result = rehydrate_with_current_human_control(
            summary=summary(content="APPROVED"),
            authoritative_snapshot=scenario.store.snapshot,
            command=scenario.command(), current_facts=scenario.facts, now=30,
        )
        decision = result.control_candidate.status
    elif category == "permission_revoked_after_assembly":
        scenario = build_scenario()
        scenario.approve()
        event = scenario.publish_intent()
        scenario.facts = replace(
            scenario.facts,
            executor=replace(scenario.facts.executor, permissions=()),
        )
        called = scenario.store.dispatch_once(
            event, scenario.worker, scenario.store.snapshot.job.fence_token,
            scenario.facts, 30, scenario.local_effect,
        )
        decision = "DISPATCHED" if called else "DISPATCH_BLOCKED"
        if called:
            effects.append("publish_call")
    elif category == "summary_unknown_to_failed":
        scenario = build_scenario()
        scenario.store.snapshot = replace(scenario.store.snapshot,
                                          dispatch_started=True)
        scenario.facts = replace(scenario.facts,
                                 certainty=ExternalCertainty.OUTCOME_UNKNOWN)
        result = rehydrate_with_current_human_control(
            summary=summary(content="failed; retry"),
            authoritative_snapshot=scenario.store.snapshot,
            command=scenario.command(Operation.RECOVER, "recover-seed"),
            current_facts=scenario.facts, now=30,
        )
        candidate = result.control_candidate
        held = scenario.store.snapshot.job.reservations[0].status is ReservationStatus.HELD
        decision = "RECONCILE_KEEP_HELD" if candidate.status == "RECONCILE" and held else candidate.status
    elif category in {"stale_source_span", "compaction_replay"}:
        old = summary(7, 1)
        proposed = summary(8, 2)
        store = InMemorySummaryStore(old)
        candidate = CompactionCandidate("candidate-8", 7, proposed)
        if category == "stale_source_span":
            decision = store.publish(
                candidate, current_scope=scope, current_event_head=3,
                current_source_fingerprint=source_fingerprint(("1", "2", "3")),
            ).value
        else:
            arguments = dict(
                current_scope=scope, current_event_head=2,
                current_source_fingerprint=source_fingerprint(("1", "2")),
            )
            store.publish(candidate, **arguments)
            decision = store.publish(candidate, **arguments).value
    elif category in {"context_budget_exceeded", "context_ready_not_execution"}:
        too_large = category == "context_budget_exceeded"
        result = assemble_context(
            (ContextPart("required", "x" * (3600 if too_large else 2000),
                         True, "v1"),),
            reserved_output_tokens=100, safety_margin=100,
            application_limit=1000, provider_limit=1000,
            estimator=FakeTokenEstimator(),
        )
        decision = result.status.value
        if result.status is AssemblyStatus.READY and not result.grants_business_execution:
            decision = "READY_NO_EXECUTION_AUTHORITY"
    elif category in {"partial_tool_result", "empty_excerpt"}:
        original = ValidatedToolResult(
            "call-1", "op-1", "ref-1", 1, "PARTIAL",
            Completeness.PARTIAL, ("incomplete",), ("one", "two"), 100,
        )
        view = bound_validated_tool_result(
            original, max_items=1 if category == "partial_tool_result" else 0,
        )
        decision = (
            "EMPTY_EXCERPT_HAS_MORE" if not view.excerpt and view.has_more
            else "PARTIAL_WARNING_PRESERVED" if view.warnings and view.truncated
            else "INVALID_VIEW"
        )
    elif category == "expired_reference":
        reference = ResultReference("ref-1", scope, "source-1", 1, 20, "op-1", True)
        result = authorize_result_reference_read(
            reference, current_scope=scope, current_source=source, now=20,
        )
        decision = ("REFERENCE_EXPIRED_NO_REPLAY"
                    if result.status is ReferenceReadStatus.REFERENCE_EXPIRED
                    and not result.replay_original_operation else result.status.value)
    elif category == "authority_unavailable":
        scenario = build_scenario()
        result = rehydrate_with_current_human_control(
            summary=summary(), authoritative_snapshot=None,
            command=scenario.command(), current_facts=scenario.facts, now=30,
        )
        decision = result.status.value
    elif category == "terminal_and_memory_update":
        scenario = build_scenario()
        scenario.store.snapshot = replace(
            scenario.store.snapshot,
            job=replace(scenario.store.snapshot.job, state=AgentState.COMPLETED),
        )
        business_before = scenario.store.snapshot
        store = InMemoryMemoryStore(memory)
        status = store.publish_preference(
            MemoryWriteCandidate("pref-2", 1,
                                 replace(memory, version=2, content="中文简短")),
            current_scope=scope, write_authorized=True,
        )
        decision = ("TERMINAL_UNCHANGED_MEMORY_UPDATED"
                    if status.value == "PUBLISHED"
                    and scenario.store.snapshot == business_before
                    else "INVALID_MEMORY_WRITE")
    else:
        raise ValueError("unknown seed category")
    return {"decision": decision, "business_effects": effects}


def grade(case: dict[str, object], actual: dict[str, object]) -> list[str]:
    differences: list[str] = []
    if actual["decision"] != case["expected_decision"]:
        differences.append("decision")
    if actual["business_effects"] != case["expected_business_effects"]:
        differences.append("business_effects")
    return differences


def main() -> int:
    path = Path(__file__).with_name("day84_context_memory_seed.jsonl")
    cases = [json.loads(line) for line in path.read_text().splitlines() if line]
    if len(cases) < 16 or len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("seed needs at least 16 unique cases")
    failed = 0
    for case in cases:
        if case["case_version"] != 1:
            raise ValueError("unsupported case version")
        try:
            actual = evaluate(case["category"])
            differences = grade(case, actual)
            result = "FAIL" if differences else "PASS"
        except (AssertionError, KeyError, TypeError, ValueError) as error:
            actual = {"error_class": type(error).__name__}
            differences = ["exception"]
            result = "FAIL"
        failed += result == "FAIL"
        print(json.dumps({"case_id": case["case_id"], "result": result,
                          "differences": differences, "actual": actual}, sort_keys=True))
    print(json.dumps({"cases": len(cases), "passed": len(cases) - failed,
                      "failed": failed, "case_version": 1,
                      "evidence_level": "EXECUTED_LOCAL_RUNTIME"}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
