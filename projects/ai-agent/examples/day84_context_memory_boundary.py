"""Deterministic Day84 scenario; all service/provider integrations are NOT RUN."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from context_memory import (
    CompactionCandidate, CompactionRequest, Completeness, ContextPart, ContextScope,
    FakeSummarizer, FakeTokenEstimator, InMemorySummaryStore, MemoryKind,
    MemoryRecord, ResultReference, SourceSpan, SourceVersion, SummaryRevision,
    ValidatedToolResult, assemble_context, authorize_result_reference_read,
    bound_validated_tool_result, rehydrate_with_current_human_control,
    select_memories, source_fingerprint, validate_summary_draft,
)
from human_control_scenarios import build_scenario


def emit(stage: str, **facts: object) -> None:
    print(json.dumps({"stage": stage, **facts}, sort_keys=True))


def main() -> None:
    scope = ContextScope("tenant-a", "user-a", "session-a", "J1")
    source = SourceVersion("preference-event", 1, ("user-a",))
    preference = MemoryRecord(
        "preference-1", MemoryKind.EXPLICIT_PREFERENCE, 1, scope,
        "default Chinese", ((source.source_id, source.version),), 100,
    )
    other_tenant = replace(
        preference, memory_id="other-tenant-note",
        scope=replace(scope, tenant_id="tenant-b"),
    )
    selection = select_memories(
        (preference, other_tenant), scope=scope, now=20,
        current_sources=(source,),
    )
    assert [item.memory_id for item in selection.selected] == ["preference-1"]
    emit("permission_scoped_memory",
         selected=[item.memory_id for item in selection.selected],
         omitted=[asdict(item) for item in selection.omissions])

    context = assemble_context(
        (ContextPart("application-rule", "approval required", True, "prompt-v3"),
         ContextPart("old-history", "x" * 3000, False, "history-v7")),
        reserved_output_tokens=200, safety_margin=100,
        application_limit=1000, provider_limit=1000,
        estimator=FakeTokenEstimator(),
    )
    assert not context.grants_business_execution
    emit("context_manifest", **asdict(context))

    original = ValidatedToolResult(
        "call-1", "read-op-1", "protected-result-1", 4, "PARTIAL",
        Completeness.PARTIAL, ("some sources failed",),
        tuple(f"item-{index}" for index in range(1000)), 50_000,
        "controlled-cursor-2",
    )
    view = bound_validated_tool_result(original, max_items=10)
    assert view.truncated and view.warnings and view.total_items == 1000
    emit("bounded_tool_result", **asdict(view))

    scenario = build_scenario()
    events = ("prepare report", "approval is pending")
    request = CompactionRequest(
        SourceSpan("tenant-a", "user-a", "session-a", 1, 2,
                   source_fingerprint(events)), events,
        ("approval-current", "job-current"),
    )
    draft = FakeSummarizer("misstate_approved").summarize(request)
    structural = validate_summary_draft(
        draft, required_fact_references=request.required_fact_references)
    summary = SummaryRevision(
        "summary-1", 7, request.source_span, "context-policy-v1",
        draft.generation_method, draft.content,
    )
    recovery = rehydrate_with_current_human_control(
        summary=summary, authoritative_snapshot=scenario.store.snapshot,
        command=scenario.command(), current_facts=scenario.facts, now=30,
    )
    assert structural.value == "STRUCTURALLY_VALID"
    assert recovery.control_candidate.status == "APPROVAL_PENDING"
    emit("misleading_summary_current_recheck",
         structural=structural.value,
         summary_claim=draft.content,
         current_decision=recovery.control_candidate.status,
         execution_allowed=recovery.control_candidate.execution_allowed)

    store = InMemorySummaryStore(summary)
    proposed = replace(summary, revision=8)
    before = store.current
    try:
        store.publish(
            CompactionCandidate("candidate-8", 7, proposed),
            current_scope=scope, current_event_head=2,
            current_source_fingerprint=source_fingerprint(events),
            fail_before_commit=True,
        )
    except RuntimeError:
        pass
    assert store.current == before
    emit("summary_publication_failure", active_revision=store.current.revision,
         candidate_revision=8, old_revision_preserved=True)

    reference = ResultReference(
        "protected-result-1", scope, source.source_id, source.version, 100,
        "publish-operation-1", True,
    )
    denied = authorize_result_reference_read(
        reference, current_scope=scope,
        current_source=replace(source, accessible_to=()), now=20,
    )
    assert not denied.replay_original_operation
    emit("reference_permission_revoked", **asdict(denied))
    emit("evidence_boundary", evidence_level="EXECUTED_LOCAL_RUNTIME",
         estimator="FAKE_UTF8_BYTES_DIVIDED_BY_4",
         summarizer="FAKE_DETERMINISTIC_SUMMARIZER",
         provider_calls=0, external_tool_calls=0,
         not_run=["real summarizer/provider", "PostgreSQL/Memory DB",
                  "Object Storage", "Relay/Queue/Worker", "production"])


if __name__ == "__main__":
    main()
