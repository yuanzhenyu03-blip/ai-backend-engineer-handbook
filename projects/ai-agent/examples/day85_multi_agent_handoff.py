"""Deterministic Day85 handoff scenario; all external systems are NOT RUN."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from context_memory import ContextPart, FakeTokenEstimator, assemble_context
from multi_agent_coordination import (
    ChildResultCandidate,
    CurrentCoordinationFacts,
    FakeWorker,
    FakeWorkerMode,
    HandoffCandidate,
    InMemoryCoordinationStore,
    WorkerRequest,
)


def emit(stage: str, **facts: object) -> None:
    print(json.dumps({"stage": stage, **facts}, sort_keys=True))


def main() -> None:
    context = assemble_context(
        (
            ContextPart(
                "application-rule", "publishing requires current approval",
                True, "prompt-v3",
            ),
            ContextPart(
                "source-a", "synthetic permitted research source", True,
                "source-a:v3",
            ),
        ),
        reserved_output_tokens=200, safety_margin=100,
        application_limit=1_000, provider_limit=1_000,
        estimator=FakeTokenEstimator(),
    )
    assert context.status.value == "READY"
    assert not context.grants_business_execution
    emit(
        "day84_context_candidate", status=context.status.value,
        grants_business_execution=context.grants_business_execution,
        selected_ids=context.selected_ids,
    )

    facts = CurrentCoordinationFacts(
        "tenant-a", ("read_sources.v1",), ("read_sources.v1",),
        ("evidence_candidate.v1",), ("context-manifest-1",),
        "handoff-policy-v1", max_delegation_depth=2,
        max_fan_out=3, concurrency_limit=2,
    )
    candidate = HandoffCandidate(
        "tenant-a", "parent-1", "parent-attempt-1", "parent-step-1",
        "handoff-source", "idem-source", "handoff-policy-v1",
        "collect scoped evidence", "research_input.v1",
        "evidence_candidate.v1", "context-manifest-1",
        (("source-a", 3),), ("read_sources.v1",), 4_000,
        "source_research", "source-evidence", True, 100,
    )
    store = InMemoryCoordinationStore(
        parent_job_id="parent-1", parent_token_reservation=9_000,
    )
    accepted = store.accept(candidate, facts=facts, now=10)
    duplicate = store.accept(candidate, facts=facts, now=10)
    conflict = store.accept(
        replace(candidate, objective="publish without approval"),
        facts=facts, now=10,
    )
    assert accepted.status.value == "ACCEPTED"
    assert duplicate.status.value == "DUPLICATE"
    assert conflict.status.value == "SEMANTIC_CONFLICT"
    emit(
        "durable_acceptance", accepted=accepted.status.value,
        duplicate=duplicate.status.value, conflict=conflict.status.value,
        allocation=accepted.record.allocation.reserved_tokens,
        granted_capabilities=accepted.record.grant.capabilities,
        unpublished_outbox=len(store.unpublished_outbox_intents),
    )

    claim = store.claim(
        candidate.handoff_id, worker_id="worker-a", now=20,
        lease_duration=10,
    )
    dispatch = store.record_provider_dispatch(
        candidate.handoff_id, worker_id="worker-a",
        fence_token=claim.fence_token,
        required_capability="read_sources.v1",
        current_allowed_capabilities=("read_sources.v1",),
        operation_id="fake-operation-1", now=21,
    )
    assert dispatch.status.value == "ALLOWED"
    worker = FakeWorker(FakeWorkerMode.SUCCESS)
    outcome = worker.execute(WorkerRequest(
        candidate.handoff_id, accepted.record.child_attempt_id,
        candidate.objective, claim.fence_token,
    ))
    result = ChildResultCandidate(
        "result-1", candidate.handoff_id,
        accepted.record.child_attempt_id, "worker-a", claim.fence_token,
        candidate.output_contract, candidate.context_source_versions,
        "evidence-ref-1", "COMPLETE", "claim-a",
        outcome.fact_value or "unknown",
    )
    verified = store.verify_result(
        result, current_source_versions=(("source-a", 3),),
    )
    aggregation = store.aggregate()
    assert verified.status.value == "VERIFIED"
    assert aggregation.status.value == "READY"
    assert not aggregation.parent_completed
    emit(
        "verified_child_and_fan_in",
        worker_mode=outcome.mode.value,
        fake_provider_calls=outcome.fake_provider_calls,
        result_status=verified.status.value,
        aggregation=aggregation.status.value,
        parent_completed=aggregation.parent_completed,
        publish_authorized=False,
    )

    denied = store.accept(
        replace(
            candidate, handoff_id="handoff-publish",
            idempotency_key="idem-publish",
            requested_capabilities=("publish_research_report.v1",),
        ), facts=facts, now=10,
    )
    assert denied.status.value == "CAPABILITY_NOT_DELEGATABLE"
    emit(
        "delegated_authority_boundary", decision=denied.status.value,
        real_provider_calls=0, real_tool_calls=0,
    )

    emit(
        "evidence_boundary", evidence_level="EXECUTED_LOCAL_RUNTIME",
        store="IN_MEMORY", worker="FAKE_DETERMINISTIC",
        clock="SYNTHETIC_INTEGER", real_provider_calls=0,
        real_tool_calls=0,
        not_run=[
            "PostgreSQL", "Outbox Relay/Broker/Worker",
            "real Provider", "external Tool", "production",
        ],
    )


if __name__ == "__main__":
    main()
