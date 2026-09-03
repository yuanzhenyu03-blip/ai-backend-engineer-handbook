"""Repeatable local Day83 scenario. All external integrations are NOT RUN."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

from durable_agent_jobs import ExternalCertainty
from human_control import Operation
from human_control_scenarios import build_scenario
from run_day83_seed_eval import evaluate_facts


def emit(label: str, **facts: object) -> None:
    print(json.dumps({"stage": label, **facts}, sort_keys=True))


def main() -> None:
    s = build_scenario()
    c, _ = s.apply(s.command())
    assert c.status == "APPROVAL_PENDING" and s.effect_calls == 0
    emit("approval_required", decision=c.status, provider_calls=0, local_tool_calls=0)
    s.approve()
    version = s.store.snapshot.job.state_version
    c, status = s.apply(s.approval_command("duplicate-callback"))
    assert status == "AUDIT_ONLY" and s.store.snapshot.job.state_version == version
    emit("duplicate_decision", decision=c.status, business_version_unchanged=True)
    event_id = s.publish_intent()
    action = s.store.snapshot.action
    assert s.store.snapshot.job.outbox_intents[-1].published_at_epoch_ms is None
    first = s.store.dispatch_once(event_id, s.worker,
                                  s.store.snapshot.job.fence_token,
                                  s.facts, 30, s.local_effect)
    duplicate = s.store.dispatch_once(event_id, s.worker,
                                      s.store.snapshot.job.fence_token,
                                      s.facts, 30, s.local_effect)
    assert first and not duplicate and s.effect_calls == 1
    assert s.verified_result[0].status.value == "VERIFIED"
    emit("approved_local_execution", tenant=action.tenant_id,
         job=action.job_id, step=action.step_id, attempt=action.attempt_id,
         operation=action.operation_id, request=s.store.snapshot.request.request_id,
         tool=action.tool_name + "." + action.tool_version,
         action_fingerprint=action.digest, event_id=event_id,
         local_tool_calls=1, duplicate_delivery_suppressed=True,
         outcome=s.verified_result[0].status.value,
         provider_calls=0, external_tool_calls=0)

    pre = build_scenario()
    pre.approve()
    event = pre.publish_intent()
    c, _ = pre.apply(pre.command(Operation.INTERRUPT, "interrupt-before"))
    called = pre.store.dispatch_once(event, pre.worker,
                                    pre.store.snapshot.job.fence_token,
                                    pre.facts, 30, pre.local_effect)
    assert not called and pre.effect_calls == 0
    emit("pre_dispatch_interrupt", decision=c.status,
         reservation=asdict(pre.store.snapshot.job.reservations[0]),
         local_tool_calls=0, outbox_history_retained=True)

    post = build_scenario()
    post.approve()
    event = post.publish_intent()
    old_fence = post.store.snapshot.job.fence_token

    def timeout_port(_action: object) -> None:
        post.effect_calls += 1
        raise TimeoutError("synthetic_post_claim_timeout")

    try:
        post.store.dispatch_once(event, post.worker, old_fence,
                                 post.facts, 30, timeout_port)
    except TimeoutError:
        pass
    else:
        raise AssertionError("injected timeout not reached")
    post.facts = replace(post.facts, certainty=ExternalCertainty.OUTCOME_UNKNOWN)
    c, _ = post.apply(post.command(Operation.INTERRUPT, "interrupt-after"))
    post.apply(post.command(Operation.OBSERVE_CANCEL, "worker-observed"))
    identity = post.store.snapshot.action
    late, status = post.apply(post.command(
        Operation.LATE_RESULT, "late-result", source_fence=old_fence,
        source_attempt_id=identity.attempt_id,
        source_operation_id=identity.operation_id, evidence_id="late-result-ref"))
    assert status == "AUDIT_ONLY" and late.status == "STALE_RESULT_EVIDENCE"
    for index in range(4):
        recovery, _ = post.apply(post.command(Operation.RECOVER, f"query-{index}"))
    assert recovery.status == "ESCALATE_BOUNDED_RECOVERY_EXHAUSTED"
    assert post.store.snapshot.action == identity
    emit("post_dispatch_unknown_then_escalation", interrupt=c.status,
         state=post.store.snapshot.job.state.value,
         reservation=asdict(post.store.snapshot.job.reservations[0]),
         fence_before=old_fence, fence_after=post.store.snapshot.job.fence_token,
         late_result=late.status, cancellation_observed=True,
         recovery_count=post.store.snapshot.job.recovery_operations[-1].attempts_used,
         escalation=asdict(post.store.snapshot.escalations[0]),
         query_intents=sum(e.event_type == "RECONCILIATION_QUERY"
                           for e in post.store.snapshot.job.outbox_intents),
         actual_external_queries=0)

    failure = build_scenario()
    failure.approve()
    before = failure.store.snapshot
    candidate = failure.store.plan(failure.command(), failure.facts, 30)
    try:
        failure.store.apply(candidate, failure.facts, 30, fail_before_commit=True)
    except RuntimeError:
        pass
    assert failure.store.snapshot == before
    emit("injected_precommit_failure", failure_point="BEFORE_LOCAL_SNAPSHOT_COMMIT",
         snapshot_unchanged=True, new_outbox_intents=0)
    for name, facts in (
        ("expired", {"approved": True, "now": 800}),
        ("stale_artifact", {"approved": True, "artifact_version": "8"}),
        ("rejected", {"approval_status": "REJECTED"}),
        ("conflict", {"approved": True, "callback": "conflict"}),
        ("completed_accounting", {"job_state": "COMPLETED", "operation": "RECOVER",
                                  "external_certainty": "OUTCOME_UNKNOWN"}),
    ):
        actual = evaluate_facts(facts)
        assert not actual["execution_allowed"] and actual["local_effect_calls"] == 0
        emit(name, **actual)
    emit("evidence_boundary", evidence_level="EXECUTED_LOCAL_RUNTIME",
         provider_gate="NOT RUN",
         not_run=["PostgreSQL", "durable transactions", "Relay/Broker",
                  "cross-process Worker interrupt/fence", "real Provider/Tool",
                  "real auth/approval callback", "alert delivery", "production"],
         synthetic_input_only=True)


if __name__ == "__main__":
    main()
