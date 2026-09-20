"""Deterministic Day94 Agent + MCP capstone acceptance example.

Run from ``projects/ai-agent`` with::

    PYTHONPATH=src python examples/day94_agent_mcp_capstone.py

No Provider API, credential, network connection, or paid model is required.
"""
from __future__ import annotations

import json

from agent_mcp_capstone import (
    AgentMCPProposalBoundary,
    AgentMCPToolProposal,
    CapstoneCommitter,
    CapstoneGracefulShutdown,
    CapstoneOperationIdentity,
    CapstoneOperatorEvidenceBuilder,
    CapstoneReconciliationCycle,
    CapstoneRecoveryCoordinator,
    CapstoneToolResultCandidate,
    DurableDispatchGuard,
    OperatorTelemetryClaim,
)
from agent_mcp_orchestrator import (
    AgentMCPOrchestrator,
    CapstoneOrchestrationInput,
    CapstoneTransportExchange,
    CapstoneUnknownTransportOutcome,
    OrchestrationOutcome,
)
from human_control import (
    ActionBinding,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    Risk,
    fingerprint,
)
from mcp_authorization import (
    AuthorizationDecision,
    AuthorizationOutcome,
    ToolAuthorizationPermit,
)
from mcp_client_transport import DispatchCertainty
from mcp_observability import OperationRefEncoder, SafeTraceCorrelation
from mcp_protocol_model import ProtocolObservation, ProtocolOutcome
from mcp_reconciliation import (
    AuthoritativeOperationStatus,
    AuthoritativeResultEvidence,
    BoundedReconciliationPolicy,
    ReconciliationDecisionKind,
    ReconciliationScheduleOutcome,
    ReconciliationScheduleState,
)
from mcp_remote_lifecycle import (
    DeadlineBudget,
    ExecutionCertainty,
    FailureEvidence,
    FailureKind,
    FailurePhase,
)
from mcp_remote_protection import TenantCapacityAdmission, TenantCapacityClass
from mcp_remote_session import (
    RemoteRequestBinding,
    RemoteRequestKey,
    RemoteResponseCorrelation,
    RemoteResponseCorrelationOutcome,
)
from mcp_retry_policy import InMemoryRetryDispatchStore, RetryDispatchRecordState
from mcp_versioning import (
    VersionedApplicationPermit,
    negotiate_generation,
    validate_versioned_permit,
)
from tool_governance import ToolCapabilitySnapshot, VisibleToolDefinition


def capability_snapshot() -> ToolCapabilitySnapshot:
    schema = {
        "type": "object",
        "properties": {
            "resource_id": {"type": "string"},
            "query": {"type": "string"},
        },
        "required": ["resource_id", "query"],
        "additionalProperties": False,
    }
    return ToolCapabilitySnapshot(
        snapshot_id="snapshot-day94-example",
        tenant_id="tenant-a",
        user_id="researcher-1",
        role="researcher",
        job_id="job-report-42",
        step_id="step-lookup",
        visible_tools=(
            VisibleToolDefinition(
                name="research.lookup",
                version="1",
                description="Controlled lookup",
                base_schema_sha256="base-schema-day94",
                arguments_schema_json=json.dumps(schema, sort_keys=True),
                arguments_schema_sha256="projected-schema-day94",
            ),
        ),
        decisions=(),
    )


def orchestration_input() -> CapstoneOrchestrationInput:
    identity = CapstoneOperationIdentity(
        operation_id="op-report-42",
        idempotency_key="idem-report-42",
        tenant_id="tenant-a",
        resource_id="report-42",
    )
    proposal = AgentMCPToolProposal.from_mapping(
        tool_name="research.lookup",
        tool_version="1",
        arguments={
            "resource_id": identity.resource_id,
            "query": "bounded evidence",
        },
    )
    snapshot = capability_snapshot()
    bound = AgentMCPProposalBoundary().bind(
        proposal=proposal,
        capability_snapshot=snapshot,
    )
    assert bound.candidate is not None
    candidate = bound.candidate
    action = ActionBinding(
        tenant_id=identity.tenant_id,
        job_id="job-report-42",
        step_id="step-lookup",
        attempt_id="attempt-1",
        operation_id=identity.operation_id,
        action_type="research.lookup",
        tool_name=candidate.binding.tool_name,
        tool_version=candidate.binding.tool_version,
        arguments_fingerprint=fingerprint(dict(candidate.arguments)),
        artifact_id=identity.resource_id,
        artifact_version="1",
        requester_id="researcher-1",
        policy_id="research-approval",
        policy_version="1",
        risk=Risk.HIGH,
        execution_binding_fingerprint="execution-binding-day94",
    )
    approval_request = ApprovalRequest(
        request_id="approval-request-day94",
        binding=action,
        requested_at=10,
        respond_by=80,
        expires_at=100,
        eligible_roles=("ResearchManager",),
        separation_required=True,
        issued_state_version=1,
        issued_fence=7,
    )
    approval_decision = ApprovalDecision(
        decision_id="approval-decision-day94",
        request_id=approval_request.request_id,
        binding_fingerprint=action.digest,
        actor_id="manager-1",
        tenant_id=identity.tenant_id,
        choice=ApprovalStatus.APPROVED,
        decided_at=20,
        reason_code="RESEARCH_LOOKUP_REVIEWED",
    )
    authorization = AuthorizationDecision(
        AuthorizationOutcome.AUTHORIZED,
        "Authorized",
        ToolAuthorizationPermit(
            principal_issuer="https://auth.example.com",
            principal_subject="researcher-1",
            application_operation_id=identity.operation_id,
            idempotency_key=identity.idempotency_key,
            tenant_id=identity.tenant_id,
            tool_name="research.lookup",
            resource_id=identity.resource_id,
        ),
    )
    attempt = RemoteRequestBinding(
        key=RemoteRequestKey(1, "mcp-request-94-1"),
        operation_id=identity.operation_id,
        idempotency_key=identity.idempotency_key,
        attempt_number=1,
    )
    negotiation = negotiate_generation(
        generation=1,
        client_versions=("2026-07-28",),
        server_versions=frozenset({"2026-07-28"}),
        server_capabilities=frozenset({"tools"}),
    )
    versioned_permit = validate_versioned_permit(
        negotiation,
        VersionedApplicationPermit(
            generation=1,
            negotiated_version="2026-07-28",
            capabilities=frozenset({"tools"}),
            authorization_revision=1,
            method="tools/call",
            tenant_id=identity.tenant_id,
            resource_id=identity.resource_id,
        ),
        requested_method="tools/call",
    )
    assert authorization.permit is not None
    capacity = TenantCapacityAdmission(
        tenant_classes={"tenant-a": TenantCapacityClass.STANDARD},
        available_classes=frozenset({TenantCapacityClass.STANDARD}),
    ).admit(
        authorization.permit,
        protocol_request_id=attempt.key.protocol_request_id,
        attempt_number=attempt.attempt_number,
    )
    return CapstoneOrchestrationInput(
        proposal=proposal,
        capability_snapshot=snapshot,
        identity=identity,
        approval_status=ApprovalStatus.APPROVED,
        approval_request=approval_request,
        approval_decision=approval_decision,
        authorization_decision=authorization,
        guard=DurableDispatchGuard(
            operation_id=identity.operation_id,
            idempotency_key=identity.idempotency_key,
            expected_state="READY_FOR_DISPATCH",
            current_state="READY_FOR_DISPATCH",
            expected_version=4,
            current_version=4,
            expected_fence=7,
            current_fence=7,
            caller_intent_active=True,
            cancelled=False,
        ),
        attempt=attempt,
        deadline=DeadlineBudget(deadline=100.0),
        now=30.0,
        negotiation=negotiation,
        versioned_permit=versioned_permit,
        capacity=capacity,
        circuit_allows_request=True,
    )


def ready_store(request: CapstoneOrchestrationInput) -> InMemoryRetryDispatchStore:
    store = InMemoryRetryDispatchStore()
    store.add_ready_operation(
        operation_id=request.identity.operation_id,
        idempotency_key=request.identity.idempotency_key,
        tenant_id=request.identity.tenant_id,
        resource_id=request.identity.resource_id,
        tool_name="research.lookup",
        version=request.guard.current_version,
        fence_token=request.guard.current_fence,
    )
    return store


class ControlledSuccessTransport:
    def __init__(self, store: InMemoryRetryDispatchStore) -> None:
        self._store = store

    def execute(self, *, identity, tool_name, attempt):
        marker = self._store.read(identity.operation_id)
        assert marker is not None
        assert marker.state is RetryDispatchRecordState.DISPATCH_STARTED
        return CapstoneTransportExchange(
            correlation=RemoteResponseCorrelation(
                RemoteResponseCorrelationOutcome.MATCHED,
                attempt,
            ),
            observation=ProtocolObservation(
                ProtocolOutcome.PROTOCOL_RESULT,
                attempt.key.protocol_request_id,
                identity.operation_id,
                payload={"resource_id": identity.resource_id},
            ),
            candidate=CapstoneToolResultCandidate(
                operation_id=identity.operation_id,
                tenant_id=identity.tenant_id,
                resource_id=identity.resource_id,
                tool_name=tool_name,
                external_object_id="external-report-42",
            ),
        )


class ControlledReadTimeoutTransport:
    def __init__(self, store: InMemoryRetryDispatchStore) -> None:
        self._store = store

    def execute(self, *, identity, tool_name, attempt):
        marker = self._store.read(identity.operation_id)
        assert marker is not None
        assert marker.state is RetryDispatchRecordState.DISPATCH_STARTED
        raise CapstoneUnknownTransportOutcome(
            FailureEvidence(
                operation_id=identity.operation_id,
                idempotency_key=identity.idempotency_key,
                protocol_request_id=attempt.key.protocol_request_id,
                attempt_number=attempt.attempt_number,
                phase=FailurePhase.READ,
                kind=FailureKind.READ_TIMEOUT,
                dispatch_certainty=DispatchCertainty.POSSIBLY_SENT,
                execution_certainty=ExecutionCertainty.POSSIBLY_EXECUTED,
                evidence_source="controlled-timeout-transport",
            ),
            handler_calls=1,
            controlled_tool_calls=1,
        )


class NotFoundAuthority:
    def query(self, *, binding):
        return AuthoritativeResultEvidence(
            binding=binding,
            status=AuthoritativeOperationStatus.NOT_FOUND,
            evidence_source="controlled-authoritative-ledger",
        )


class RecordingAlerts:
    def __init__(self) -> None:
        self.items = []

    def emit(self, alert) -> None:
        self.items.append(alert)


def main() -> None:
    request = orchestration_input()

    happy_store = ready_store(request)
    happy = AgentMCPOrchestrator(
        dispatch_store=happy_store,
        transport=ControlledSuccessTransport(happy_store),
        committer=CapstoneCommitter(happy_store),
    ).run(request)
    assert happy.outcome is OrchestrationOutcome.SUCCEEDED
    assert happy.verified_agent_observation is not None

    timeout_store = ready_store(request)
    timeout = AgentMCPOrchestrator(
        dispatch_store=timeout_store,
        transport=ControlledReadTimeoutTransport(timeout_store),
        committer=CapstoneCommitter(timeout_store),
    ).run(request)
    assert timeout.outcome is OrchestrationOutcome.PENDING_RECONCILIATION
    marker = timeout_store.read(request.identity.operation_id)
    assert marker is not None
    shutdown = CapstoneGracefulShutdown().preserve_unknown(
        marker,
        transport_handoff_completed=True,
        trustworthy_response_received=False,
    )
    recovery = CapstoneRecoveryCoordinator().plan(shutdown.record)
    alerts = RecordingAlerts()
    cycle = CapstoneReconciliationCycle().run_once(
        recovery,
        authority=NotFoundAuthority(),
        policy=BoundedReconciliationPolicy(
            base_delay_seconds=1.0,
            jitter_ratio=0.0,
        ),
        state=ReconciliationScheduleState(
            recovery.binding,
            queries_used=0,
            maximum_queries=3,
            deadline=200.0,
        ),
        now=100.0,
        operation_ref="safe-example-ref",
        alerts=alerts,
    )
    assert cycle.observation.kind is ReconciliationDecisionKind.STILL_PENDING
    assert cycle.schedule.outcome is ReconciliationScheduleOutcome.NEXT_QUERY_SCHEDULED

    encoder = OperationRefEncoder(b"day94-example-key-material")
    report = CapstoneOperatorEvidenceBuilder(encoder).build_not_found_report(
        record=marker,
        trace=SafeTraceCorrelation(
            trace_id="trace-day94-example",
            operation_ref=encoder.encode(marker.operation_id),
            transport_generation=marker.transport_generation or 0,
        ),
        telemetry_claim=OperatorTelemetryClaim.REMOTE_TOOL_SUCCESS,
        authoritative_status=AuthoritativeOperationStatus.NOT_FOUND,
    )

    print(
        json.dumps(
            {
                "happy_path": {
                    "outcome": happy.outcome.value,
                    "durable_transition": happy.durable_transition,
                    "agent_observation_source": (
                        happy.verified_agent_observation.source
                    ),
                },
                "unknown_path": {
                    "outcome": timeout.outcome.value,
                    "dispatch_certainty": (
                        timeout.failure_evidence.dispatch_certainty.value
                        if timeout.failure_evidence
                        else None
                    ),
                    "execution_certainty": (
                        timeout.failure_evidence.execution_certainty.value
                        if timeout.failure_evidence
                        else None
                    ),
                    "committer_calls": timeout.committer_calls,
                },
                "restart_recovery": {
                    "outcome": recovery.outcome.value,
                    "authority_observation": cycle.observation.kind.value,
                    "schedule": cycle.schedule.outcome.value,
                    "next_query_at": cycle.schedule.state.next_query_at,
                },
                "operator_evidence": json.loads(report.to_json()),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
