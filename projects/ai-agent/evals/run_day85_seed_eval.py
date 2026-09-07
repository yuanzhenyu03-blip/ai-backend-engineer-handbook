"""Day85 version-1 deterministic seed eval using the coordination core."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multi_agent_coordination import (  # noqa: E402
    ChildResultCandidate,
    CurrentCoordinationFacts,
    HandoffCandidate,
    InMemoryCoordinationStore,
)


def facts() -> CurrentCoordinationFacts:
    return CurrentCoordinationFacts(
        "tenant-a", ("read_sources.v1", "check_claims.v1"),
        ("read_sources.v1", "check_claims.v1"),
        ("evidence_candidate.v1",), ("context-1",),
        "handoff-policy-v1", max_delegation_depth=2,
        max_fan_out=10, concurrency_limit=10,
    )


def candidate(handoff_id: str = "handoff-1", **changes: object) -> HandoffCandidate:
    values: dict[str, object] = {
        "tenant_id": "tenant-a", "parent_job_id": "parent-1",
        "parent_attempt_id": "parent-attempt-1",
        "parent_step_id": "parent-step-1", "handoff_id": handoff_id,
        "idempotency_key": f"idem-{handoff_id}",
        "policy_version": "handoff-policy-v1",
        "objective": "collect scoped evidence",
        "input_contract": "research_input.v1",
        "output_contract": "evidence_candidate.v1",
        "context_manifest_id": "context-1",
        "context_source_versions": (("source-a", 3),),
        "requested_capabilities": ("read_sources.v1",),
        "requested_tokens": 4_000, "receiver_role": "source_research",
        "aggregation_slot": "source-evidence", "required": True,
        "deadline": 100, "delegation_depth": 1,
    }
    values.update(changes)
    return HandoffCandidate(**values)


def new_store() -> InMemoryCoordinationStore:
    return InMemoryCoordinationStore(
        parent_job_id="parent-1", parent_token_reservation=9_000,
    )


def accept(store: InMemoryCoordinationStore, item: HandoffCandidate | None = None):
    return store.accept(item or candidate(), facts=facts(), now=10)


def dispatch(store: InMemoryCoordinationStore, handoff_id: str = "handoff-1",
             worker: str = "worker-a"):
    claim = store.claim(handoff_id, worker_id=worker, now=20, lease_duration=20)
    decision = store.record_provider_dispatch(
        handoff_id, worker_id=worker, fence_token=claim.fence_token,
        required_capability="read_sources.v1",
        current_allowed_capabilities=("read_sources.v1",),
        operation_id=f"operation-{handoff_id}", now=21,
    )
    if decision.status.value != "ALLOWED":
        raise AssertionError(decision.status.value)
    return claim


def result(store: InMemoryCoordinationStore, handoff_id: str, worker: str,
           fence: int) -> ChildResultCandidate:
    record = store.get(handoff_id)
    return ChildResultCandidate(
        f"result-{handoff_id}", handoff_id, record.child_attempt_id,
        worker, fence, record.candidate.output_contract,
        record.candidate.context_source_versions,
        f"evidence-{handoff_id}", "COMPLETE", "claim-a", "confirmed",
    )


def evaluate(category: str) -> dict[str, object]:
    store = new_store()
    provider_calls = 0
    if category == "legal_acceptance":
        decision = accept(store).status.value
    elif category == "cross_tenant":
        decision = accept(store, candidate(tenant_id="tenant-b")).status.value
    elif category in {"summary_cannot_grant_publish", "capability_subset"}:
        decision = accept(store, candidate(
            requested_capabilities=("publish_research_report.v1",),
        )).status.value
    elif category == "duplicate_handoff":
        accept(store)
        decision = accept(store).status.value
    elif category == "conflicting_handoff":
        accept(store)
        decision = accept(store, candidate(objective="different")).status.value
    elif category == "output_contract":
        decision = accept(store, candidate(output_contract="unknown.v9")).status.value
    elif category == "budget_allocation":
        accept(store, candidate("handoff-a"))
        accept(store, candidate("handoff-b"))
        decision = accept(store, candidate("handoff-c")).status.value
    elif category == "accepted_not_dispatch":
        accept(store)
        decision = store.authorize_provider_dispatch(
            "handoff-1", worker_id="worker-a", fence_token=0,
            required_capability="read_sources.v1",
            current_allowed_capabilities=("read_sources.v1",), now=20,
        ).status.value
    elif category == "crash_before_claim":
        accept(store)
        decision = store.claim(
            "handoff-1", worker_id="worker-b", now=20,
            lease_duration=10,
        ).status.value
    elif category == "stale_fence":
        accept(store)
        old = store.claim(
            "handoff-1", worker_id="worker-a", now=20, lease_duration=10,
        )
        store.take_over_expired_lease(
            "handoff-1", worker_id="worker-b", now=30, lease_duration=10,
        )
        decision = store.authorize_provider_dispatch(
            "handoff-1", worker_id="worker-a", fence_token=old.fence_token,
            required_capability="read_sources.v1",
            current_allowed_capabilities=("read_sources.v1",), now=31,
        ).status.value
    elif category == "outcome_unknown":
        accept(store)
        dispatch(store)
        provider_calls = 1
        store.mark_outcome_unknown(
            "handoff-1", operation_id="operation-handoff-1",
        )
        record = store.get("handoff-1")
        decision = f"{record.state.value}_{record.allocation.status}"
    elif category == "cancel_before_dispatch":
        accept(store)
        cancelled = store.cancel("handoff-1")
        decision = f"{cancelled.status.value}_{cancelled.allocation_status}"
    elif category == "cancel_after_dispatch":
        accept(store)
        dispatch(store)
        provider_calls = 1
        cancelled = store.cancel("handoff-1")
        decision = f"{cancelled.status.value}_{cancelled.allocation_status}"
    elif category == "required_wait":
        accept(store)
        decision = store.aggregate().status.value
    elif category == "optional_partial":
        accept(store, candidate("required"))
        accept(store, candidate(
            "optional", required=False, requested_tokens=1_000,
            aggregation_slot="optional-check",
        ))
        claim = dispatch(store, "required")
        provider_calls = 1
        store.verify_result(
            result(store, "required", "worker-a", claim.fence_token),
            current_source_versions=(("source-a", 3),),
        )
        decision = store.aggregate().status.value
    elif category in {"stale_context_source", "parent_terminal_late_result"}:
        accept(store)
        claim = dispatch(store)
        provider_calls = 1
        if category == "parent_terminal_late_result":
            store.parent_terminal = True
        versions = (("source-a", 4),) if category == "stale_context_source" else (("source-a", 3),)
        decision = store.verify_result(
            result(store, "handoff-1", "worker-a", claim.fence_token),
            current_source_versions=versions,
        ).status.value
    else:
        raise ValueError("unknown seed category")
    return {"decision": decision, "provider_calls": provider_calls}


def grade(case: dict[str, object], actual: dict[str, object]) -> list[str]:
    differences: list[str] = []
    if actual["decision"] != case["expected_decision"]:
        differences.append("decision")
    if actual["provider_calls"] != case["expected_provider_calls"]:
        differences.append("provider_calls")
    return differences


def main() -> int:
    path = Path(__file__).with_name("day85_multi_agent_seed.jsonl")
    cases = [json.loads(line) for line in path.read_text().splitlines() if line]
    if len(cases) < 18 or len({item["case_id"] for item in cases}) != len(cases):
        raise ValueError("seed requires at least 18 unique cases")
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
            "case_id": case["case_id"], "result": status,
            "differences": differences, "actual": actual,
        }, sort_keys=True))
    print(json.dumps({
        "cases": len(cases), "passed": len(cases) - failed,
        "failed": failed, "case_version": 1,
        "evidence_level": "EXECUTED_LOCAL_RUNTIME",
    }))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
