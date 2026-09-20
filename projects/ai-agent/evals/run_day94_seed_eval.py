"""Deterministic Day94 Agent + MCP capstone invariant evaluation."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent_mcp_capstone import (  # noqa: E402
    AgentMCPProposalBoundary,
    AgentMCPToolProposal,
    CapstoneAccessGate,
    CapstoneCandidatePipeline,
    CapstoneCommitter,
    CapstoneDispatchClaimer,
    CapstoneGracefulShutdown,
    CapstoneOperatorEvidenceBuilder,
    CapstonePreflight,
    CapstoneRecoveryCoordinator,
    CapstoneRetryAttemptFactory,
    CapstoneToolResultCandidate,
    OperatorTelemetryClaim,
)
from agent_mcp_orchestrator import AgentMCPOrchestrator  # noqa: E402
from examples.day94_agent_mcp_capstone import (  # noqa: E402
    ControlledReadTimeoutTransport,
    ControlledSuccessTransport,
    orchestration_input,
    ready_store,
)
from mcp_authorization import AuthorizationDecision, AuthorizationOutcome  # noqa: E402
from mcp_observability import OperationRefEncoder, SafeTraceCorrelation  # noqa: E402
from mcp_protocol_model import ProtocolObservation, ProtocolOutcome  # noqa: E402
from mcp_reconciliation import (  # noqa: E402
    AuthoritativeOperationStatus,
    BoundedReconciliationPolicy,
    InMemoryReconciliationStore,
    ReconciliationCommitter,
    ReconciliationDecision,
    ReconciliationDecisionKind,
    ReconciliationScheduleState,
    authoritative_not_executed_evidence,
)
from mcp_remote_session import (  # noqa: E402
    RemoteRequestKey,
    RemoteResponseCorrelation,
    RemoteResponseCorrelationOutcome,
)
from mcp_retry_policy import (  # noqa: E402
    BoundedRetryPolicy,
    RetryContext,
    RetryDispatchRecordState,
)


def result(
    outcome: str,
    *,
    transport_calls: int = 0,
    tool_calls: int = 0,
    committer_calls: int = 0,
    durable_transitions: int = 0,
) -> dict[str, object]:
    return {
        "outcome": outcome,
        "transport_calls": transport_calls,
        "tool_calls": tool_calls,
        "committer_calls": committer_calls,
        "durable_transitions": durable_transitions,
    }


def bound_candidate(request):
    decision = AgentMCPProposalBoundary().bind(
        proposal=request.proposal,
        capability_snapshot=request.capability_snapshot,
    )
    assert decision.candidate is not None
    return decision.candidate


def claim_once(request, store):
    candidate = bound_candidate(request)
    access = CapstoneAccessGate().compose(
        identity=request.identity,
        candidate=candidate,
        approval_status=request.approval_status,
        approval_request=request.approval_request,
        approval_decision=request.approval_decision,
        authorization_decision=request.authorization_decision,
        now=int(request.now),
    )
    preflight = CapstonePreflight().evaluate(
        identity=request.identity,
        access=access,
        guard=request.guard,
        attempt=request.attempt,
        deadline=request.deadline,
        now=request.now,
        negotiation=request.negotiation,
        versioned_permit=request.versioned_permit,
        capacity=request.capacity,
        circuit_allows_request=request.circuit_allows_request,
    )
    return CapstoneDispatchClaimer().claim(
        store=store,
        identity=request.identity,
        candidate=candidate,
        guard=request.guard,
        preflight=preflight,
    )


def candidate_decision(request, *, resource_id: str, stale: bool = False):
    expected_attempt = request.attempt
    response_attempt = (
        replace(
            expected_attempt,
            key=RemoteRequestKey(1, "stale-request"),
            attempt_number=1,
        )
        if stale
        else expected_attempt
    )
    if stale:
        expected_attempt = replace(
            expected_attempt,
            key=RemoteRequestKey(2, "current-request"),
            attempt_number=2,
        )
    return CapstoneCandidatePipeline().evaluate(
        identity=request.identity,
        expected_tool_name="research.lookup",
        expected_attempt=expected_attempt,
        correlation=RemoteResponseCorrelation(
            RemoteResponseCorrelationOutcome.MATCHED,
            response_attempt,
        ),
        observation=ProtocolObservation(
            ProtocolOutcome.PROTOCOL_RESULT,
            response_attempt.key.protocol_request_id,
            response_attempt.operation_id,
            payload={"resource_id": resource_id},
        ),
        candidate=CapstoneToolResultCandidate(
            operation_id=request.identity.operation_id,
            tenant_id=request.identity.tenant_id,
            resource_id=resource_id,
            tool_name="research.lookup",
            external_object_id="controlled-result-42",
        ),
    )


def claimed_record(request):
    store = ready_store(request)
    claim = claim_once(request, store)
    assert claim.record is not None
    return store, claim.record


def committed_not_executed(request):
    _, marker = claimed_record(request)
    recovery = CapstoneRecoveryCoordinator().plan(marker)
    reconciliation_store = InMemoryReconciliationStore()
    reconciliation_store.add_pending(recovery.binding)
    committed = ReconciliationCommitter(reconciliation_store).commit(
        ReconciliationDecision(
            ReconciliationDecisionKind.RESOLVED_NOT_EXECUTED,
            recovery.binding,
            evidence_source="day94-seed-authority",
        ),
        expected_version=1,
        authorization_valid_at_effect=False,
    )
    evidence = authoritative_not_executed_evidence(
        committed,
        original_failure=recovery.failure,
    )
    return committed, evidence


def evaluate(category: str) -> dict[str, object]:
    request = orchestration_input()
    if category in {"happy_path", "read_timeout_unknown"}:
        store = ready_store(request)
        transport = (
            ControlledSuccessTransport(store)
            if category == "happy_path"
            else ControlledReadTimeoutTransport(store)
        )
        evaluated = AgentMCPOrchestrator(
            dispatch_store=store,
            transport=transport,
            committer=CapstoneCommitter(store),
        ).run(request)
        return result(
            evaluated.outcome.value,
            transport_calls=evaluated.transport_calls,
            tool_calls=evaluated.controlled_tool_calls,
            committer_calls=evaluated.committer_calls,
            durable_transitions=int(evaluated.durable_transition),
        )
    if category == "invisible_tool":
        request = replace(
            request,
            proposal=AgentMCPToolProposal.from_mapping(
                tool_name="research.invisible",
                tool_version="1",
                arguments={"resource_id": "report-42", "query": "x"},
            ),
        )
    elif category == "approval_expired":
        request = replace(request, now=100.0)
    elif category == "authorization_revoked":
        request = replace(
            request,
            authorization_decision=AuthorizationDecision(
                AuthorizationOutcome.PRINCIPAL_REVOKED,
                "revoked",
            ),
        )
    elif category == "resource_binding_conflict":
        request = replace(
            request,
            proposal=AgentMCPToolProposal.from_mapping(
                tool_name="research.lookup",
                tool_version="1",
                arguments={"resource_id": "report-99", "query": "x"},
            ),
        )
    if category in {
        "invisible_tool",
        "approval_expired",
        "authorization_revoked",
        "resource_binding_conflict",
    }:
        store = ready_store(request)
        evaluated = AgentMCPOrchestrator(
            dispatch_store=store,
            transport=ControlledSuccessTransport(store),
            committer=CapstoneCommitter(store),
        ).run(request)
        return result(evaluated.outcome.value)
    if category == "dispatch_claim_loser":
        store = ready_store(request)
        claim_once(request, store)
        evaluated = AgentMCPOrchestrator(
            dispatch_store=store,
            transport=ControlledSuccessTransport(store),
            committer=CapstoneCommitter(store),
        ).run(request)
        return result(evaluated.outcome.value)
    if category == "candidate_output_mismatch":
        decision = candidate_decision(request, resource_id="report-99")
        return result(decision.outcome.value)
    if category == "stale_attempt":
        decision = candidate_decision(
            request,
            resource_id="report-42",
            stale=True,
        )
        return result(decision.outcome.value)
    if category == "duplicate_commit":
        store, marker = claimed_record(request)
        decision = candidate_decision(request, resource_id="report-42")
        committer = CapstoneCommitter(store)
        first = committer.commit(
            decision,
            expected_state=RetryDispatchRecordState.DISPATCH_STARTED,
            expected_version=marker.version,
            expected_fence=marker.fence_token,
        )
        second = committer.commit(
            decision,
            expected_state=RetryDispatchRecordState.DISPATCH_STARTED,
            expected_version=marker.version,
            expected_fence=marker.fence_token,
        )
        assert first.durable_transition and not second.durable_transition
        return result(
            "EXACTLY_ONE_DURABLE_COMMIT",
            committer_calls=2,
            durable_transitions=1,
        )
    if category in {"graceful_shutdown", "restart_recovery", "authority_not_found"}:
        _, marker = claimed_record(request)
        if category == "graceful_shutdown":
            decision = CapstoneGracefulShutdown().preserve_unknown(
                marker,
                transport_handoff_completed=True,
                trustworthy_response_received=False,
            )
            return result(decision.outcome.value)
        recovery = CapstoneRecoveryCoordinator().plan(marker)
        if category == "restart_recovery":
            return result(recovery.outcome.value)

        class NotFoundAuthority:
            def query(self, *, binding):
                from mcp_reconciliation import AuthoritativeResultEvidence

                return AuthoritativeResultEvidence(
                    binding,
                    AuthoritativeOperationStatus.NOT_FOUND,
                    "day94-seed-authority",
                )

        class Alerts:
            def emit(self, alert):
                raise AssertionError("query budget should remain")

        from agent_mcp_capstone import CapstoneReconciliationCycle

        cycle = CapstoneReconciliationCycle().run_once(
            recovery,
            authority=NotFoundAuthority(),
            policy=BoundedReconciliationPolicy(jitter_ratio=0.0),
            state=ReconciliationScheduleState(
                recovery.binding,
                queries_used=0,
                maximum_queries=3,
                deadline=200.0,
            ),
            now=100.0,
            operation_ref="safe-seed-ref",
            alerts=Alerts(),
        )
        return result(cycle.observation.kind.value)
    if category in {"authoritative_not_executed", "retry_identity"}:
        committed, evidence = committed_not_executed(request)
        retry = BoundedRetryPolicy(jitter_ratio=0.0).decide(
            evidence,
            RetryContext(
                now=100.0,
                deadline=110.0,
                retries_used=0,
                max_retries=1,
                caller_intent_active=True,
                authorization_current=True,
                capacity_admitted=True,
                circuit_allows_request=True,
            ),
        )
        if category == "authoritative_not_executed":
            return result(
                retry.kind.value,
                committer_calls=1,
                durable_transitions=int(committed.durable_transition),
            )
        attempt = CapstoneRetryAttemptFactory().prepare(
            identity=request.identity,
            tool_name="research.lookup",
            evidence=evidence,
            decision=retry,
            new_protocol_request_id="mcp-request-94-2",
            current_transport_generation=2,
        )
        invariant = (
            attempt.binding.operation_id == request.identity.operation_id
            and attempt.binding.idempotency_key == request.identity.idempotency_key
            and attempt.binding.attempt_number == 2
            and attempt.binding.key.protocol_request_id == "mcp-request-94-2"
        )
        return result("SAME_OPERATION_FRESH_ATTEMPT" if invariant else "BROKEN")
    if category == "trace_not_authority":
        _, marker = claimed_record(request)
        encoder = OperationRefEncoder(b"day94-seed-key-material")
        report = CapstoneOperatorEvidenceBuilder(encoder).build_not_found_report(
            record=marker,
            trace=SafeTraceCorrelation(
                "trace-day94-seed",
                encoder.encode(marker.operation_id),
                marker.transport_generation or 0,
            ),
            telemetry_claim=OperatorTelemetryClaim.REMOTE_TOOL_SUCCESS,
            authoritative_status=AuthoritativeOperationStatus.NOT_FOUND,
        )
        assert not report.telemetry_is_authority and not report.committer_allowed
        return result(report.next_action)
    raise ValueError(f"unknown category: {category}")


def grade(case: dict[str, object], actual: dict[str, object]) -> list[str]:
    return [
        name
        for name in (
            "outcome",
            "transport_calls",
            "tool_calls",
            "committer_calls",
            "durable_transitions",
        )
        if actual[name] != case[f"expected_{name}"]
    ]


def main() -> int:
    path = Path(__file__).with_name("day94_agent_mcp_capstone_seed.jsonl")
    cases = [json.loads(line) for line in path.read_text().splitlines() if line]
    if len(cases) != 16:
        raise ValueError("Day94 seed requires 16 independent cases")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Day94 seed case IDs must be unique")
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
