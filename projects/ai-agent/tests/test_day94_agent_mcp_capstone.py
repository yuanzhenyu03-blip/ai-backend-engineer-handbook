from __future__ import annotations

import inspect
import json
import unittest
from dataclasses import replace

from agent_framework_adapter import FrameworkToolCall, ProposalValidationError
from agent_mcp_capstone import (
    AgentMCPProposalBoundary,
    AgentMCPToolProposal,
    CapstoneAccessGate,
    CapstoneAccessOutcome,
    CapstoneCandidateOutcome,
    CapstoneCandidatePipeline,
    CapstoneCommitOutcome,
    CapstoneCommitter,
    CapstoneDispatchClaimer,
    CapstoneGracefulShutdown,
    CapstoneOperationIdentity,
    CapstoneOperationIdentityBoundary,
    CapstoneOperatorEvidenceBuilder,
    CapstonePreflight,
    CapstonePreflightOutcome,
    CapstoneReconciliationCycle,
    CapstoneRecoveryCoordinator,
    CapstoneRetryAttemptFactory,
    CapstoneToolResultCandidate,
    DurableDispatchGuard,
    OperationPreparationOutcome,
    ProposalBoundaryOutcome,
    RecoveryCoordinationOutcome,
    GracefulShutdownOutcome,
    OperatorTelemetryClaim,
)
from agent_mcp_orchestrator import (
    AgentMCPOrchestrator,
    CapstoneOrchestrationInput,
    CapstoneTransportExchange,
    CapstoneUnknownTransportOutcome,
    OrchestrationOutcome,
    VerifiedAgentOutcome,
)
from mcp_client_transport import DispatchCertainty
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
    InMemoryOperationAuthorizationBindings,
    OperationAuthorizationBinding,
    OperationBindingOutcome,
    ToolAuthorizationPermit,
)
from mcp_observability import OperationRefEncoder, SafeTraceCorrelation
from mcp_remote_lifecycle import DeadlineBudget
from mcp_remote_lifecycle import (
    ExecutionCertainty,
    FailureEvidence,
    FailureKind,
    FailurePhase,
)
from mcp_protocol_model import ProtocolObservation, ProtocolOutcome
from mcp_remote_protection import (
    TenantCapacityAdmission,
    TenantCapacityClass,
)
from mcp_reconciliation import (
    AuthoritativeOperationStatus,
    AuthoritativeResultEvidence,
    BoundedReconciliationPolicy,
    ComplianceOutcome,
    InMemoryReconciliationStore,
    ReconciledBusinessOutcome,
    ReconciliationCommitOutcome,
    ReconciliationCommitter,
    ReconciliationDecision,
    ReconciliationDecisionKind,
    ReconciliationScheduleOutcome,
    ReconciliationScheduleState,
    authoritative_not_executed_evidence,
)
from mcp_remote_session import (
    RemoteRequestBinding,
    RemoteRequestKey,
    RemoteResponseCorrelation,
    RemoteResponseCorrelationOutcome,
)
from mcp_retry_policy import (
    BoundedRetryPolicy,
    InMemoryRetryDispatchStore,
    RetryContext,
    RetryDispatchClaimOutcome,
    RetryDispatchRecordState,
)
from mcp_versioning import (
    VersionedApplicationPermit,
    negotiate_generation,
    validate_versioned_permit,
)
from pydantic_ai_capstone_adapter import PydanticAICapstoneAdapter
from tool_governance import ToolCapabilitySnapshot, VisibleToolDefinition


def research_snapshot() -> ToolCapabilitySnapshot:
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
        snapshot_id="snapshot-day94",
        tenant_id="tenant-a",
        user_id="researcher-1",
        role="researcher",
        job_id="job-report-42",
        step_id="step-lookup",
        visible_tools=(
            VisibleToolDefinition(
                name="research.lookup",
                version="1",
                description="Controlled research lookup",
                base_schema_sha256="base-schema-94",
                arguments_schema_json=json.dumps(schema, sort_keys=True),
                arguments_schema_sha256="projected-schema-94",
            ),
        ),
        decisions=(),
    )


class Day94AgentMCPProposalBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = PydanticAICapstoneAdapter()
        self.boundary = AgentMCPProposalBoundary()
        self.snapshot = research_snapshot()

    def bound_candidate(
        self,
        *,
        resource_id: str = "report-42",
        extra_arguments: dict[str, object] | None = None,
    ):
        arguments: dict[str, object] = {
            "resource_id": resource_id,
            "query": "bounded evidence",
        }
        arguments.update(extra_arguments or {})
        decision = self.boundary.bind(
            proposal=AgentMCPToolProposal.from_mapping(
                tool_name="research.lookup",
                tool_version="1",
                arguments=arguments,
            ),
            capability_snapshot=self.snapshot,
        )
        assert decision.candidate is not None
        return decision.candidate

    def operation_identity(self) -> CapstoneOperationIdentity:
        return CapstoneOperationIdentity(
            operation_id="op-report-42",
            idempotency_key="idem-report-42",
            tenant_id="tenant-a",
            resource_id="report-42",
        )

    def approval_evidence(self, candidate):
        identity = self.operation_identity()
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
            execution_binding_fingerprint="execution-binding-94",
        )
        request = ApprovalRequest(
            request_id="approval-request-94",
            binding=action,
            requested_at=10,
            respond_by=80,
            expires_at=100,
            eligible_roles=("ResearchManager",),
            separation_required=True,
            issued_state_version=1,
            issued_fence=7,
        )
        decision = ApprovalDecision(
            decision_id="approval-decision-94",
            request_id=request.request_id,
            binding_fingerprint=action.digest,
            actor_id="manager-1",
            tenant_id=identity.tenant_id,
            choice=ApprovalStatus.APPROVED,
            decided_at=20,
            reason_code="RESEARCH_LOOKUP_REVIEWED",
        )
        return request, decision

    def authorized_decision(self) -> AuthorizationDecision:
        identity = self.operation_identity()
        return AuthorizationDecision(
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

    def ready_access(self):
        candidate = self.bound_candidate()
        request, approval = self.approval_evidence(candidate)
        access = CapstoneAccessGate().compose(
            identity=self.operation_identity(),
            candidate=candidate,
            approval_status=ApprovalStatus.APPROVED,
            approval_request=request,
            approval_decision=approval,
            authorization_decision=self.authorized_decision(),
            now=30,
        )
        self.assertEqual(access.outcome, CapstoneAccessOutcome.READY_FOR_PREFLIGHT)
        assert access.permit is not None
        return access

    def preflight_inputs(self):
        identity = self.operation_identity()
        access = self.ready_access()
        guard = DurableDispatchGuard(
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
        capacity = TenantCapacityAdmission(
            tenant_classes={
                "tenant-a": TenantCapacityClass.STANDARD,
            },
            available_classes=frozenset({TenantCapacityClass.STANDARD}),
        ).admit(
            access.permit,
            protocol_request_id=attempt.key.protocol_request_id,
            attempt_number=attempt.attempt_number,
        )
        return {
            "identity": identity,
            "access": access,
            "guard": guard,
            "attempt": attempt,
            "deadline": DeadlineBudget(deadline=100.0),
            "now": 30.0,
            "negotiation": negotiation,
            "versioned_permit": versioned_permit,
            "capacity": capacity,
            "circuit_allows_request": True,
        }

    def test_framework_output_becomes_application_owned_proposal(self) -> None:
        proposal = self.adapter.to_proposal(
            FrameworkToolCall(
                "proposal_handler",
                {
                    "tool_name": "research.lookup",
                    "tool_version": "1",
                    "arguments": {
                        "query": "bounded evidence",
                        "resource_id": "report-42",
                    },
                },
            )
        )

        self.assertIsInstance(proposal, AgentMCPToolProposal)
        self.assertEqual(
            proposal.arguments_json,
            '{"query":"bounded evidence","resource_id":"report-42"}',
        )

    def test_visible_proposal_is_bound_but_not_authorized_or_dispatched(self) -> None:
        proposal = AgentMCPToolProposal.from_mapping(
            tool_name="research.lookup",
            tool_version="1",
            arguments={
                "resource_id": "report-42",
                "query": "bounded evidence",
            },
        )

        decision = self.boundary.bind(
            proposal=proposal,
            capability_snapshot=self.snapshot,
        )

        self.assertEqual(
            decision.outcome,
            ProposalBoundaryOutcome.ACCEPTED_FOR_GOVERNANCE,
        )
        self.assertIsNotNone(decision.candidate)
        assert decision.candidate is not None
        self.assertEqual(decision.candidate.binding.tenant_id, "tenant-a")
        self.assertEqual(decision.candidate.binding.snapshot_id, "snapshot-day94")
        self.assertEqual(decision.candidate.binding.tool_id, "research.lookup@1")
        self.assertFalse(hasattr(self.boundary, "transport"))
        self.assertFalse(hasattr(self.boundary, "committer"))

    def test_invisible_tool_cannot_become_governed_candidate(self) -> None:
        proposal = AgentMCPToolProposal.from_mapping(
            tool_name="research.admin_lookup",
            tool_version="1",
            arguments={"resource_id": "report-42", "query": "secret"},
        )

        decision = self.boundary.bind(
            proposal=proposal,
            capability_snapshot=self.snapshot,
        )

        self.assertEqual(
            decision.outcome,
            ProposalBoundaryOutcome.TOOL_NOT_VISIBLE,
        )
        self.assertIsNone(decision.candidate)

    def test_adapter_rejects_extra_authority_fields(self) -> None:
        with self.assertRaises(ProposalValidationError):
            self.adapter.to_proposal(
                FrameworkToolCall(
                    "proposal_handler",
                    {
                        "tool_name": "research.lookup",
                        "tool_version": "1",
                        "arguments": {"resource_id": "report-42", "query": "x"},
                        "authorized": True,
                    },
                )
            )

    def test_application_boundary_signature_has_no_framework_or_sdk_types(self) -> None:
        signature = inspect.signature(AgentMCPProposalBoundary.bind)
        annotations = " ".join(str(value.annotation) for value in signature.parameters.values())
        annotations += " " + str(signature.return_annotation)

        self.assertNotIn("Pydantic", annotations)
        self.assertNotIn("LangGraph", annotations)
        self.assertNotIn("ClientSession", annotations)

    def test_application_identity_overrides_untrusted_model_operation_id(self) -> None:
        candidate = self.bound_candidate(
            extra_arguments={"operation_id": "model-controlled-operation"},
        )
        identity = CapstoneOperationIdentity(
            operation_id="op-report-42",
            idempotency_key="idem-report-42",
            tenant_id="tenant-a",
            resource_id="report-42",
        )

        prepared = CapstoneOperationIdentityBoundary().prepare_authorization(
            identity=identity,
            candidate=candidate,
        )

        self.assertEqual(
            prepared.outcome,
            OperationPreparationOutcome.READY_FOR_CURRENT_AUTHORIZATION,
        )
        assert prepared.authorization_request is not None
        self.assertEqual(
            prepared.authorization_request.application_operation_id,
            "op-report-42",
        )
        self.assertEqual(
            prepared.authorization_request.resource_id,
            "report-42",
        )

    def test_exact_duplicate_converges_to_existing_operation_binding(self) -> None:
        store = InMemoryOperationAuthorizationBindings()
        binding = OperationAuthorizationBinding(
            principal_issuer="https://auth.example.com",
            principal_subject="researcher-1",
            application_operation_id="op-report-42",
            idempotency_key="idem-report-42",
            tenant_id="tenant-a",
            tool_name="research.lookup",
            resource_id="report-42",
        )

        first = store.bind(binding)
        duplicate = store.bind(binding)

        self.assertEqual(first, OperationBindingOutcome.BOUND)
        self.assertEqual(duplicate, OperationBindingOutcome.DUPLICATE)

    def test_same_operation_with_different_resource_is_identity_conflict(self) -> None:
        store = InMemoryOperationAuthorizationBindings()
        original = OperationAuthorizationBinding(
            principal_issuer="https://auth.example.com",
            principal_subject="researcher-1",
            application_operation_id="op-report-42",
            idempotency_key="idem-report-42",
            tenant_id="tenant-a",
            tool_name="research.lookup",
            resource_id="report-42",
        )
        conflicting = OperationAuthorizationBinding(
            principal_issuer=original.principal_issuer,
            principal_subject=original.principal_subject,
            application_operation_id=original.application_operation_id,
            idempotency_key=original.idempotency_key,
            tenant_id=original.tenant_id,
            tool_name=original.tool_name,
            resource_id="report-99",
        )

        first = store.bind(original)
        conflict = store.bind(conflicting)

        self.assertEqual(first, OperationBindingOutcome.BOUND)
        self.assertEqual(conflict, OperationBindingOutcome.IDENTITY_CONFLICT)

    def test_human_and_authorization_decisions_remain_separate(self) -> None:
        candidate = self.bound_candidate()
        request, approval = self.approval_evidence(candidate)
        authorization = self.authorized_decision()

        access = CapstoneAccessGate().compose(
            identity=self.operation_identity(),
            candidate=candidate,
            approval_status=ApprovalStatus.APPROVED,
            approval_request=request,
            approval_decision=approval,
            authorization_decision=authorization,
            now=30,
        )

        self.assertEqual(access.outcome, CapstoneAccessOutcome.READY_FOR_PREFLIGHT)
        self.assertIs(access.approval_decision, approval)
        self.assertIs(access.authorization_decision, authorization)
        self.assertIs(access.permit, authorization.permit)

    def test_expired_approval_blocks_even_with_current_authorization(self) -> None:
        candidate = self.bound_candidate()
        request, approval = self.approval_evidence(candidate)

        access = CapstoneAccessGate().compose(
            identity=self.operation_identity(),
            candidate=candidate,
            approval_status=ApprovalStatus.APPROVED,
            approval_request=request,
            approval_decision=approval,
            authorization_decision=self.authorized_decision(),
            now=request.expires_at,
        )

        self.assertEqual(
            access.outcome,
            CapstoneAccessOutcome.HUMAN_CHECKPOINT_BLOCKED,
        )
        self.assertIsNone(access.permit)

    def test_revoked_authorization_blocks_even_with_valid_approval(self) -> None:
        candidate = self.bound_candidate()
        request, approval = self.approval_evidence(candidate)
        revoked = AuthorizationDecision(
            AuthorizationOutcome.PRINCIPAL_REVOKED,
            "Request is not authorized",
        )

        access = CapstoneAccessGate().compose(
            identity=self.operation_identity(),
            candidate=candidate,
            approval_status=ApprovalStatus.APPROVED,
            approval_request=request,
            approval_decision=approval,
            authorization_decision=revoked,
            now=30,
        )

        self.assertEqual(
            access.outcome,
            CapstoneAccessOutcome.CURRENT_AUTHORIZATION_BLOCKED,
        )
        self.assertIs(access.approval_decision, approval)
        self.assertIs(access.authorization_decision, revoked)

    def test_mismatched_exact_permit_cannot_be_repaired_by_approval(self) -> None:
        candidate = self.bound_candidate()
        request, approval = self.approval_evidence(candidate)
        authorization = self.authorized_decision()
        assert authorization.permit is not None
        mismatched = AuthorizationDecision(
            AuthorizationOutcome.AUTHORIZED,
            "Authorized",
            replace(authorization.permit, resource_id="report-99"),
        )

        access = CapstoneAccessGate().compose(
            identity=self.operation_identity(),
            candidate=candidate,
            approval_status=ApprovalStatus.APPROVED,
            approval_request=request,
            approval_decision=approval,
            authorization_decision=mismatched,
            now=30,
        )

        self.assertEqual(
            access.outcome,
            CapstoneAccessOutcome.PERMIT_BINDING_CONFLICT,
        )
        self.assertIsNone(access.permit)

    def test_preflight_passes_without_calling_transport_handler_or_committer(self) -> None:
        decision = CapstonePreflight().evaluate(**self.preflight_inputs())

        self.assertEqual(
            decision.outcome,
            CapstonePreflightOutcome.READY_FOR_DISPATCH_CLAIM,
        )
        self.assertEqual(decision.transport_calls, 0)
        self.assertEqual(decision.handler_calls, 0)
        self.assertEqual(decision.committer_calls, 0)

    def test_stale_fence_blocks_before_dispatch_claim(self) -> None:
        inputs = self.preflight_inputs()
        inputs["guard"] = replace(inputs["guard"], current_fence=8)

        decision = CapstonePreflight().evaluate(**inputs)

        self.assertEqual(
            decision.outcome,
            CapstonePreflightOutcome.DURABLE_OWNERSHIP_STALE,
        )
        self.assertEqual(decision.transport_calls, 0)

    def test_cancellation_or_exhausted_deadline_blocks_new_dispatch(self) -> None:
        cancelled_inputs = self.preflight_inputs()
        cancelled_inputs["guard"] = replace(
            cancelled_inputs["guard"],
            cancelled=True,
        )
        cancelled = CapstonePreflight().evaluate(**cancelled_inputs)

        deadline_inputs = self.preflight_inputs()
        deadline_inputs["now"] = 100.0
        exhausted = CapstonePreflight().evaluate(**deadline_inputs)

        self.assertEqual(
            cancelled.outcome,
            CapstonePreflightOutcome.CALLER_INTENT_INACTIVE,
        )
        self.assertEqual(
            exhausted.outcome,
            CapstonePreflightOutcome.DEADLINE_EXHAUSTED,
        )

    def test_attempt_cannot_cross_transport_generation(self) -> None:
        inputs = self.preflight_inputs()
        inputs["attempt"] = replace(
            inputs["attempt"],
            key=RemoteRequestKey(2, "mcp-request-94-1"),
        )

        decision = CapstonePreflight().evaluate(**inputs)

        self.assertEqual(
            decision.outcome,
            CapstonePreflightOutcome.ATTEMPT_GENERATION_MISMATCH,
        )
        self.assertEqual(decision.transport_calls, 0)

    def test_capability_downgrade_rejects_versioned_permit(self) -> None:
        inputs = self.preflight_inputs()
        identity = self.operation_identity()
        downgraded = negotiate_generation(
            generation=1,
            client_versions=("2026-07-28",),
            server_versions=frozenset({"2026-07-28"}),
            server_capabilities=frozenset(),
        )
        inputs["negotiation"] = downgraded
        inputs["versioned_permit"] = validate_versioned_permit(
            downgraded,
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

        decision = CapstonePreflight().evaluate(**inputs)

        self.assertEqual(
            decision.outcome,
            CapstonePreflightOutcome.VERSIONED_PERMIT_REJECTED,
        )
        self.assertEqual(decision.handler_calls, 0)

    def test_current_tenant_capacity_rejection_stops_before_claim(self) -> None:
        inputs = self.preflight_inputs()
        access = inputs["access"]
        attempt = inputs["attempt"]
        assert access.permit is not None
        inputs["capacity"] = TenantCapacityAdmission(
            tenant_classes={"tenant-a": TenantCapacityClass.STANDARD},
            available_classes=frozenset(),
        ).admit(
            access.permit,
            protocol_request_id=attempt.key.protocol_request_id,
            attempt_number=attempt.attempt_number,
        )

        decision = CapstonePreflight().evaluate(**inputs)

        self.assertEqual(
            decision.outcome,
            CapstonePreflightOutcome.CAPACITY_REJECTED,
        )
        self.assertEqual(decision.transport_calls, 0)

    def test_open_circuit_stops_before_dispatch_claim(self) -> None:
        inputs = self.preflight_inputs()
        inputs["circuit_allows_request"] = False

        decision = CapstonePreflight().evaluate(**inputs)

        self.assertEqual(
            decision.outcome,
            CapstonePreflightOutcome.CIRCUIT_OPEN,
        )
        self.assertEqual(decision.transport_calls, 0)

    def test_atomic_claim_persists_complete_attempt_before_transport(self) -> None:
        inputs = self.preflight_inputs()
        preflight = CapstonePreflight().evaluate(**inputs)
        identity = inputs["identity"]
        candidate = self.bound_candidate()
        store = InMemoryRetryDispatchStore()
        store.add_ready_operation(
            operation_id=identity.operation_id,
            idempotency_key=identity.idempotency_key,
            tenant_id=identity.tenant_id,
            resource_id=identity.resource_id,
            tool_name=candidate.binding.tool_name,
            version=inputs["guard"].current_version,
            fence_token=inputs["guard"].current_fence,
        )

        claim = CapstoneDispatchClaimer().claim(
            store=store,
            identity=identity,
            candidate=candidate,
            guard=inputs["guard"],
            preflight=preflight,
        )

        self.assertEqual(claim.outcome, RetryDispatchClaimOutcome.CLAIMED)
        assert claim.record is not None
        self.assertEqual(
            claim.record.state,
            RetryDispatchRecordState.DISPATCH_STARTED,
        )
        self.assertEqual(claim.record.tenant_id, "tenant-a")
        self.assertEqual(claim.record.resource_id, "report-42")
        self.assertEqual(claim.record.tool_name, "research.lookup")
        self.assertEqual(claim.record.attempt_number, 1)
        self.assertEqual(claim.record.protocol_request_id, "mcp-request-94-1")
        self.assertEqual(claim.record.transport_generation, 1)
        self.assertEqual(claim.record.version, 5)
        self.assertEqual(claim.record.fence_token, 8)
        self.assertEqual(claim.transport_calls, 0)

    def test_two_workers_compete_but_only_one_claims_dispatch(self) -> None:
        inputs = self.preflight_inputs()
        preflight = CapstonePreflight().evaluate(**inputs)
        identity = inputs["identity"]
        candidate = self.bound_candidate()
        store = InMemoryRetryDispatchStore()
        store.add_ready_operation(
            operation_id=identity.operation_id,
            idempotency_key=identity.idempotency_key,
            tenant_id=identity.tenant_id,
            resource_id=identity.resource_id,
            tool_name=candidate.binding.tool_name,
            version=inputs["guard"].current_version,
            fence_token=inputs["guard"].current_fence,
        )
        claimer = CapstoneDispatchClaimer()

        winner = claimer.claim(
            store=store,
            identity=identity,
            candidate=candidate,
            guard=inputs["guard"],
            preflight=preflight,
        )
        loser = claimer.claim(
            store=store,
            identity=identity,
            candidate=candidate,
            guard=inputs["guard"],
            preflight=preflight,
        )

        self.assertEqual(winner.outcome, RetryDispatchClaimOutcome.CLAIMED)
        self.assertEqual(loser.outcome, RetryDispatchClaimOutcome.STATE_CONFLICT)
        self.assertEqual(loser.transport_calls, 0)

    def test_restart_after_claim_preserves_unknown_outcome_for_reconciliation(
        self,
    ) -> None:
        inputs = self.preflight_inputs()
        preflight = CapstonePreflight().evaluate(**inputs)
        identity = inputs["identity"]
        candidate = self.bound_candidate()
        store = InMemoryRetryDispatchStore()
        store.add_ready_operation(
            operation_id=identity.operation_id,
            idempotency_key=identity.idempotency_key,
            tenant_id=identity.tenant_id,
            resource_id=identity.resource_id,
            tool_name=candidate.binding.tool_name,
            version=inputs["guard"].current_version,
            fence_token=inputs["guard"].current_fence,
        )
        claim = CapstoneDispatchClaimer().claim(
            store=store,
            identity=identity,
            candidate=candidate,
            guard=inputs["guard"],
            preflight=preflight,
        )
        assert claim.record is not None

        recovered = CapstoneRecoveryCoordinator().plan(claim.record)

        self.assertEqual(
            recovered.outcome,
            RecoveryCoordinationOutcome.RECONCILIATION_REQUIRED,
        )
        self.assertEqual(
            recovered.failure.execution_certainty,
            ExecutionCertainty.POSSIBLY_EXECUTED,
        )
        self.assertEqual(recovered.binding.operation_id, "op-report-42")
        self.assertEqual(recovered.binding.resource_id, "report-42")
        self.assertEqual(recovered.attempt_number, 1)
        self.assertEqual(recovered.protocol_request_id, "mcp-request-94-1")
        self.assertEqual(recovered.transport_generation, 1)
        self.assertEqual(recovered.original_tool_calls, 0)
        self.assertEqual(recovered.committer_calls, 0)

    def test_graceful_shutdown_preserves_dispatch_marker_for_recovery(
        self,
    ) -> None:
        store, claimed = self.claimed_operation_store()

        shutdown = CapstoneGracefulShutdown().preserve_unknown(
            claimed,
            transport_handoff_completed=True,
            trustworthy_response_received=False,
        )
        persisted = store.read(claimed.operation_id)
        assert persisted is not None
        recovered = CapstoneRecoveryCoordinator().plan(persisted)

        self.assertEqual(
            shutdown.outcome,
            GracefulShutdownOutcome.UNKNOWN_OUTCOME_PRESERVED,
        )
        self.assertEqual(
            shutdown.execution_certainty,
            ExecutionCertainty.POSSIBLY_EXECUTED,
        )
        self.assertFalse(shutdown.new_dispatch_allowed)
        self.assertEqual(shutdown.committer_calls, 0)
        self.assertFalse(shutdown.durable_transition)
        self.assertEqual(persisted, claimed)
        self.assertEqual(
            persisted.state,
            RetryDispatchRecordState.DISPATCH_STARTED,
        )
        self.assertEqual(persisted.operation_id, "op-report-42")
        self.assertEqual(persisted.idempotency_key, "idem-report-42")
        self.assertEqual(persisted.tenant_id, "tenant-a")
        self.assertEqual(persisted.resource_id, "report-42")
        self.assertEqual(persisted.tool_name, "research.lookup")
        self.assertEqual(persisted.attempt_number, 1)
        self.assertEqual(persisted.protocol_request_id, "mcp-request-94-1")
        self.assertEqual(persisted.transport_generation, 1)
        self.assertEqual(
            recovered.outcome,
            RecoveryCoordinationOutcome.RECONCILIATION_REQUIRED,
        )
        self.assertEqual(recovered.original_tool_calls, 0)
        self.assertEqual(recovered.committer_calls, 0)

    def test_operator_report_separates_trace_authority_and_durable_fact(
        self,
    ) -> None:
        _, claimed = self.claimed_operation_store()
        encoder = OperationRefEncoder(b"day94-test-key-material")
        trace = SafeTraceCorrelation(
            trace_id="trace-day94-old-process",
            operation_ref=encoder.encode(claimed.operation_id),
            transport_generation=claimed.transport_generation or 0,
        )

        report = CapstoneOperatorEvidenceBuilder(
            encoder
        ).build_not_found_report(
            record=claimed,
            trace=trace,
            telemetry_claim=OperatorTelemetryClaim.REMOTE_TOOL_SUCCESS,
            authoritative_status=AuthoritativeOperationStatus.NOT_FOUND,
        )
        encoded = report.to_json()

        self.assertFalse(report.telemetry_is_authority)
        self.assertFalse(report.authority_resolved_outcome)
        self.assertTrue(report.durable_fact_is_authority)
        self.assertEqual(
            report.durable_state,
            RetryDispatchRecordState.DISPATCH_STARTED,
        )
        self.assertEqual(
            report.execution_certainty,
            ExecutionCertainty.POSSIBLY_EXECUTED,
        )
        self.assertFalse(report.committer_allowed)
        self.assertEqual(
            report.next_action,
            "CONTINUE_BOUNDED_RECONCILIATION",
        )
        self.assertNotIn("op-report-42", encoded)
        self.assertNotIn("idem-report-42", encoded)
        self.assertNotIn("tenant-a", encoded)
        self.assertNotIn("report-42", encoded)

    def test_not_found_remains_pending_and_only_schedules_another_query(
        self,
    ) -> None:
        store, claimed = self.claimed_operation_store()
        recovery = CapstoneRecoveryCoordinator().plan(claimed)

        class NotFoundAuthority:
            def __init__(self) -> None:
                self.calls = 0

            def query(self, *, binding):
                self.calls += 1
                return AuthoritativeResultEvidence(
                    binding=binding,
                    status=AuthoritativeOperationStatus.NOT_FOUND,
                    evidence_source="controlled-authoritative-ledger",
                )

        class NoopAlerts:
            def __init__(self) -> None:
                self.items = []

            def emit(self, alert) -> None:
                self.items.append(alert)

        authority = NotFoundAuthority()
        alerts = NoopAlerts()
        cycle = CapstoneReconciliationCycle().run_once(
            recovery,
            authority=authority,
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
            operation_ref="safe-opref-42",
            alerts=alerts,
        )

        self.assertEqual(authority.calls, 1)
        self.assertEqual(
            cycle.observation.kind,
            ReconciliationDecisionKind.STILL_PENDING,
        )
        self.assertEqual(
            cycle.schedule.outcome,
            ReconciliationScheduleOutcome.NEXT_QUERY_SCHEDULED,
        )
        self.assertTrue(cycle.schedule.state.pending_reconciliation)
        self.assertEqual(cycle.schedule.state.next_query_at, 101.0)
        self.assertEqual(cycle.original_tool_calls, 0)
        self.assertEqual(cycle.committer_calls, 0)
        self.assertEqual(alerts.items, [])

    def test_reconciled_success_preserves_authorization_violation(self) -> None:
        store, claimed = self.claimed_operation_store()
        recovery = CapstoneRecoveryCoordinator().plan(claimed)

        class SucceededAuthority:
            def query(self, *, binding):
                return AuthoritativeResultEvidence(
                    binding=binding,
                    status=AuthoritativeOperationStatus.SUCCEEDED,
                    evidence_source="controlled-authoritative-ledger",
                    external_object_id="external-report-42",
                )

        class NoopAlerts:
            def emit(self, alert) -> None:
                raise AssertionError("resolved evidence must not alert")

        cycle = CapstoneReconciliationCycle().run_once(
            recovery,
            authority=SucceededAuthority(),
            policy=BoundedReconciliationPolicy(jitter_ratio=0.0),
            state=ReconciliationScheduleState(
                recovery.binding,
                queries_used=0,
                maximum_queries=3,
                deadline=200.0,
            ),
            now=100.0,
            operation_ref="safe-opref-42",
            alerts=NoopAlerts(),
        )
        reconciliation_store = InMemoryReconciliationStore()
        reconciliation_store.add_pending(recovery.binding)

        committed = ReconciliationCommitter(reconciliation_store).commit(
            cycle.observation,
            expected_version=1,
            authorization_valid_at_effect=False,
        )

        self.assertEqual(
            cycle.observation.kind,
            ReconciliationDecisionKind.RESOLVED_SUCCEEDED,
        )
        self.assertEqual(
            cycle.schedule.outcome,
            ReconciliationScheduleOutcome.RESOLUTION_READY,
        )
        self.assertEqual(committed.outcome, ReconciliationCommitOutcome.COMMITTED)
        self.assertTrue(committed.durable_transition)
        assert committed.record is not None
        self.assertEqual(
            committed.record.business_outcome,
            ReconciledBusinessOutcome.SUCCEEDED,
        )
        self.assertEqual(
            committed.record.compliance_outcome,
            ComplianceOutcome.AUTHORIZATION_VIOLATION,
        )
        self.assertEqual(committed.record.external_object_id, "external-report-42")

    def test_reconciled_failure_cannot_become_not_executed_retry_proof(
        self,
    ) -> None:
        store, claimed = self.claimed_operation_store()
        recovery = CapstoneRecoveryCoordinator().plan(claimed)

        class FailedAuthority:
            def query(self, *, binding):
                return AuthoritativeResultEvidence(
                    binding=binding,
                    status=AuthoritativeOperationStatus.FAILED,
                    evidence_source="controlled-authoritative-ledger",
                )

        class NoopAlerts:
            def emit(self, alert) -> None:
                raise AssertionError("resolved evidence must not alert")

        cycle = CapstoneReconciliationCycle().run_once(
            recovery,
            authority=FailedAuthority(),
            policy=BoundedReconciliationPolicy(jitter_ratio=0.0),
            state=ReconciliationScheduleState(
                recovery.binding,
                queries_used=0,
                maximum_queries=3,
                deadline=200.0,
            ),
            now=100.0,
            operation_ref="safe-opref-42",
            alerts=NoopAlerts(),
        )
        reconciliation_store = InMemoryReconciliationStore()
        reconciliation_store.add_pending(recovery.binding)
        committed = ReconciliationCommitter(reconciliation_store).commit(
            cycle.observation,
            expected_version=1,
            authorization_valid_at_effect=True,
        )

        self.assertEqual(
            cycle.observation.kind,
            ReconciliationDecisionKind.RESOLVED_FAILED,
        )
        self.assertEqual(committed.outcome, ReconciliationCommitOutcome.COMMITTED)
        assert committed.record is not None
        self.assertEqual(
            committed.record.business_outcome,
            ReconciledBusinessOutcome.FAILED,
        )
        with self.assertRaisesRegex(
            ValueError,
            "committed NOT_EXECUTED fact is required",
        ):
            authoritative_not_executed_evidence(
                committed,
                original_failure=recovery.failure,
            )

    def test_committed_not_executed_creates_fresh_attempt_and_dispatch_marker(
        self,
    ) -> None:
        _, claimed = self.claimed_operation_store()
        recovery = CapstoneRecoveryCoordinator().plan(claimed)
        reconciliation_store = InMemoryReconciliationStore()
        reconciliation_store.add_pending(recovery.binding)
        committed = ReconciliationCommitter(reconciliation_store).commit(
            ReconciliationDecision(
                ReconciliationDecisionKind.RESOLVED_NOT_EXECUTED,
                recovery.binding,
                evidence_source="controlled-authoritative-ledger",
            ),
            expected_version=1,
            authorization_valid_at_effect=False,
        )
        evidence = authoritative_not_executed_evidence(
            committed,
            original_failure=recovery.failure,
        )
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
        identity = self.operation_identity()
        prepared = CapstoneRetryAttemptFactory().prepare(
            identity=identity,
            tool_name="research.lookup",
            evidence=evidence,
            decision=retry,
            new_protocol_request_id="mcp-request-94-2",
            current_transport_generation=2,
        )

        self.assertIs(prepared.identity, identity)
        self.assertEqual(prepared.binding.operation_id, identity.operation_id)
        self.assertEqual(
            prepared.binding.idempotency_key,
            identity.idempotency_key,
        )
        self.assertEqual(prepared.binding.attempt_number, 2)
        self.assertEqual(
            prepared.binding.key.protocol_request_id,
            "mcp-request-94-2",
        )
        self.assertEqual(prepared.binding.key.transport_generation, 2)

        dispatch_store = InMemoryRetryDispatchStore()
        dispatch_store.add_retryable(
            evidence,
            tenant_id=identity.tenant_id,
            resource_id=identity.resource_id,
            tool_name=prepared.tool_name,
            version=10,
            fence_token=20,
        )
        inputs = self.preflight_inputs()
        inputs["attempt"] = prepared.binding
        inputs["guard"] = DurableDispatchGuard(
            operation_id=identity.operation_id,
            idempotency_key=identity.idempotency_key,
            expected_state="READY_FOR_RETRY",
            current_state="READY_FOR_RETRY",
            expected_version=10,
            current_version=10,
            expected_fence=20,
            current_fence=20,
            caller_intent_active=True,
            cancelled=False,
        )
        inputs["negotiation"] = negotiate_generation(
            generation=2,
            client_versions=("2026-07-28",),
            server_versions=frozenset({"2026-07-28"}),
            server_capabilities=frozenset({"tools"}),
        )
        inputs["versioned_permit"] = validate_versioned_permit(
            inputs["negotiation"],
            VersionedApplicationPermit(
                generation=2,
                negotiated_version="2026-07-28",
                capabilities=frozenset({"tools"}),
                authorization_revision=2,
                method="tools/call",
                tenant_id=identity.tenant_id,
                resource_id=identity.resource_id,
            ),
            requested_method="tools/call",
        )
        preflight = CapstonePreflight().evaluate(**inputs)
        marker = CapstoneDispatchClaimer().claim(
            store=dispatch_store,
            identity=identity,
            candidate=self.bound_candidate(),
            guard=inputs["guard"],
            preflight=preflight,
        )

        self.assertEqual(marker.outcome, RetryDispatchClaimOutcome.CLAIMED)
        assert marker.record is not None
        self.assertEqual(marker.record.state, RetryDispatchRecordState.DISPATCH_STARTED)
        self.assertEqual(marker.record.version, 11)
        self.assertEqual(marker.record.fence_token, 21)
        self.assertEqual(marker.record.attempt_number, 2)
        self.assertEqual(marker.record.protocol_request_id, "mcp-request-94-2")
        self.assertEqual(marker.record.transport_generation, 2)
        self.assertEqual(marker.transport_calls, 0)

    def test_stale_response_stops_before_output_validation(self) -> None:
        attempt = self.preflight_inputs()["attempt"]
        decision = CapstoneCandidatePipeline().evaluate(
            identity=self.operation_identity(),
            expected_tool_name="research.lookup",
            expected_attempt=attempt,
            correlation=RemoteResponseCorrelation(
                RemoteResponseCorrelationOutcome.STALE_GENERATION,
                attempt,
            ),
            observation=ProtocolObservation(
                ProtocolOutcome.PROTOCOL_RESULT,
                attempt.key.protocol_request_id,
                attempt.operation_id,
                payload={"resource_id": "report-42"},
            ),
            candidate=CapstoneToolResultCandidate(
                operation_id="op-report-42",
                tenant_id="tenant-a",
                resource_id="report-42",
                tool_name="research.lookup",
                external_object_id="result-42",
            ),
        )

        self.assertEqual(
            decision.outcome,
            CapstoneCandidateOutcome.CORRELATION_REJECTED,
        )
        self.assertEqual(decision.output_validation_calls, 0)
        self.assertEqual(decision.committer_calls, 0)

    def test_late_previous_attempt_stops_at_correlation(self) -> None:
        current_attempt = self.preflight_inputs()["attempt"]
        current_attempt = replace(
            current_attempt,
            key=RemoteRequestKey(2, "mcp-request-94-2"),
            attempt_number=2,
        )
        late_attempt = replace(
            current_attempt,
            key=RemoteRequestKey(1, "mcp-request-94-1"),
            attempt_number=1,
        )

        decision = CapstoneCandidatePipeline().evaluate(
            identity=self.operation_identity(),
            expected_tool_name="research.lookup",
            expected_attempt=current_attempt,
            correlation=RemoteResponseCorrelation(
                RemoteResponseCorrelationOutcome.MATCHED,
                late_attempt,
            ),
            observation=ProtocolObservation(
                ProtocolOutcome.PROTOCOL_RESULT,
                late_attempt.key.protocol_request_id,
                late_attempt.operation_id,
                payload={"resource_id": "report-42"},
            ),
            candidate=CapstoneToolResultCandidate(
                operation_id="op-report-42",
                tenant_id="tenant-a",
                resource_id="report-42",
                tool_name="research.lookup",
                external_object_id="late-result-42",
            ),
        )

        self.assertEqual(
            decision.outcome,
            CapstoneCandidateOutcome.CORRELATION_REJECTED,
        )
        self.assertEqual(decision.correlation_checks, 1)
        self.assertEqual(decision.protocol_validation_calls, 0)
        self.assertEqual(decision.output_validation_calls, 0)
        self.assertEqual(decision.committer_calls, 0)
        self.assertEqual(decision.durable_transitions, 0)

    def test_correlated_candidate_with_wrong_resource_fails_output_validation(
        self,
    ) -> None:
        attempt = self.preflight_inputs()["attempt"]
        decision = CapstoneCandidatePipeline().evaluate(
            identity=self.operation_identity(),
            expected_tool_name="research.lookup",
            expected_attempt=attempt,
            correlation=RemoteResponseCorrelation(
                RemoteResponseCorrelationOutcome.MATCHED,
                attempt,
            ),
            observation=ProtocolObservation(
                ProtocolOutcome.PROTOCOL_RESULT,
                attempt.key.protocol_request_id,
                attempt.operation_id,
                payload={"resource_id": "report-99"},
            ),
            candidate=CapstoneToolResultCandidate(
                operation_id="op-report-42",
                tenant_id="tenant-a",
                resource_id="report-99",
                tool_name="research.lookup",
                external_object_id="result-99",
            ),
        )

        self.assertEqual(
            decision.outcome,
            CapstoneCandidateOutcome.OUTPUT_REJECTED,
        )
        self.assertEqual(decision.correlation_checks, 1)
        self.assertEqual(decision.protocol_validation_calls, 1)
        self.assertEqual(decision.output_validation_calls, 1)
        self.assertIsNone(decision.proposal)
        self.assertEqual(decision.committer_calls, 0)
        self.assertEqual(decision.durable_transitions, 0)

    def test_valid_candidate_only_proposes_a_success_transition(self) -> None:
        attempt = self.preflight_inputs()["attempt"]
        decision = CapstoneCandidatePipeline().evaluate(
            identity=self.operation_identity(),
            expected_tool_name="research.lookup",
            expected_attempt=attempt,
            correlation=RemoteResponseCorrelation(
                RemoteResponseCorrelationOutcome.MATCHED,
                attempt,
            ),
            observation=ProtocolObservation(
                ProtocolOutcome.PROTOCOL_RESULT,
                attempt.key.protocol_request_id,
                attempt.operation_id,
                payload={"resource_id": "report-42"},
            ),
            candidate=CapstoneToolResultCandidate(
                operation_id="op-report-42",
                tenant_id="tenant-a",
                resource_id="report-42",
                tool_name="research.lookup",
                external_object_id="result-42",
            ),
        )

        self.assertEqual(
            decision.outcome,
            CapstoneCandidateOutcome.TRANSITION_PROPOSAL_READY,
        )
        assert decision.proposal is not None
        self.assertEqual(decision.proposal.resource_id, "report-42")
        self.assertFalse(decision.proposal.durable_transition)
        self.assertEqual(decision.committer_calls, 0)
        self.assertEqual(decision.durable_transitions, 0)

    def valid_candidate_decision(self):
        attempt = self.preflight_inputs()["attempt"]
        return CapstoneCandidatePipeline().evaluate(
            identity=self.operation_identity(),
            expected_tool_name="research.lookup",
            expected_attempt=attempt,
            correlation=RemoteResponseCorrelation(
                RemoteResponseCorrelationOutcome.MATCHED,
                attempt,
            ),
            observation=ProtocolObservation(
                ProtocolOutcome.PROTOCOL_RESULT,
                attempt.key.protocol_request_id,
                attempt.operation_id,
                payload={"resource_id": "report-42"},
            ),
            candidate=CapstoneToolResultCandidate(
                operation_id="op-report-42",
                tenant_id="tenant-a",
                resource_id="report-42",
                tool_name="research.lookup",
                external_object_id="result-42",
            ),
        )

    def claimed_operation_store(self):
        inputs = self.preflight_inputs()
        store = InMemoryRetryDispatchStore()
        identity = inputs["identity"]
        candidate = self.bound_candidate()
        store.add_ready_operation(
            operation_id=identity.operation_id,
            idempotency_key=identity.idempotency_key,
            tenant_id=identity.tenant_id,
            resource_id=identity.resource_id,
            tool_name=candidate.binding.tool_name,
            version=inputs["guard"].current_version,
            fence_token=inputs["guard"].current_fence,
        )
        claim = CapstoneDispatchClaimer().claim(
            store=store,
            identity=identity,
            candidate=candidate,
            guard=inputs["guard"],
            preflight=CapstonePreflight().evaluate(**inputs),
        )
        assert claim.record is not None
        return store, claim.record

    def orchestration_input(self) -> CapstoneOrchestrationInput:
        inputs = self.preflight_inputs()
        candidate = self.bound_candidate()
        approval_request, approval_decision = self.approval_evidence(candidate)
        return CapstoneOrchestrationInput(
            proposal=AgentMCPToolProposal.from_mapping(
                tool_name="research.lookup",
                tool_version="1",
                arguments={
                    "resource_id": "report-42",
                    "query": "bounded evidence",
                },
            ),
            capability_snapshot=self.snapshot,
            identity=inputs["identity"],
            approval_status=ApprovalStatus.APPROVED,
            approval_request=approval_request,
            approval_decision=approval_decision,
            authorization_decision=self.authorized_decision(),
            guard=inputs["guard"],
            attempt=inputs["attempt"],
            deadline=inputs["deadline"],
            now=inputs["now"],
            negotiation=inputs["negotiation"],
            versioned_permit=inputs["versioned_permit"],
            capacity=inputs["capacity"],
            circuit_allows_request=inputs["circuit_allows_request"],
        )

    def ready_orchestration_store(self, request: CapstoneOrchestrationInput):
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

    def controlled_success_transport(self, store):
        class ControlledSuccessTransport:
            def __init__(self) -> None:
                self.calls = 0

            def execute(self, *, identity, tool_name, attempt):
                persisted = store.read(identity.operation_id)
                assert persisted is not None
                if persisted.state is not RetryDispatchRecordState.DISPATCH_STARTED:
                    raise AssertionError("transport called before durable claim")
                self.calls += 1
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

        return ControlledSuccessTransport()

    def test_thin_orchestrator_runs_happy_path_through_sole_committer(
        self,
    ) -> None:
        request = self.orchestration_input()
        store = self.ready_orchestration_store(request)
        transport = self.controlled_success_transport(store)

        result = AgentMCPOrchestrator(
            dispatch_store=store,
            transport=transport,
            committer=CapstoneCommitter(store),
        ).run(request)

        self.assertEqual(result.outcome, OrchestrationOutcome.SUCCEEDED)
        self.assertEqual(result.transport_calls, 1)
        self.assertEqual(result.handler_calls, 1)
        self.assertEqual(result.controlled_tool_calls, 1)
        self.assertEqual(result.committer_calls, 1)
        self.assertTrue(result.durable_transition)
        assert result.verified_agent_observation is not None
        self.assertEqual(
            result.verified_agent_observation.outcome,
            VerifiedAgentOutcome.SUCCEEDED,
        )
        self.assertEqual(
            result.verified_agent_observation.source,
            "SOLE_COMMITTER",
        )
        self.assertEqual(
            result.verified_agent_observation.external_object_id,
            "external-report-42",
        )
        persisted = store.read(request.identity.operation_id)
        assert persisted is not None
        self.assertEqual(persisted.state, RetryDispatchRecordState.COMPLETED)
        self.assertEqual(persisted.external_object_id, "external-report-42")

    def test_orchestrator_never_calls_transport_when_dispatch_claim_loses(
        self,
    ) -> None:
        request = self.orchestration_input()
        store = self.ready_orchestration_store(request)
        candidate = self.bound_candidate()
        access = self.ready_access()
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
        winner = CapstoneDispatchClaimer().claim(
            store=store,
            identity=request.identity,
            candidate=candidate,
            guard=request.guard,
            preflight=preflight,
        )
        self.assertEqual(winner.outcome, RetryDispatchClaimOutcome.CLAIMED)
        transport = self.controlled_success_transport(store)

        result = AgentMCPOrchestrator(
            dispatch_store=store,
            transport=transport,
            committer=CapstoneCommitter(store),
        ).run(request)

        self.assertEqual(result.outcome, OrchestrationOutcome.CLAIM_BLOCKED)
        self.assertEqual(transport.calls, 0)
        self.assertEqual(result.transport_calls, 0)
        self.assertEqual(result.committer_calls, 0)
        self.assertFalse(result.durable_transition)
        self.assertIsNone(result.verified_agent_observation)

    def test_orchestrator_read_timeout_preserves_unknown_outcome(self) -> None:
        request = self.orchestration_input()
        store = self.ready_orchestration_store(request)

        class ControlledReadTimeoutTransport:
            def execute(self, *, identity, tool_name, attempt):
                persisted = store.read(identity.operation_id)
                assert persisted is not None
                if persisted.state is not RetryDispatchRecordState.DISPATCH_STARTED:
                    raise AssertionError("timeout occurred before durable claim")
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
                    transport_calls=1,
                    handler_calls=1,
                    controlled_tool_calls=1,
                )

        result = AgentMCPOrchestrator(
            dispatch_store=store,
            transport=ControlledReadTimeoutTransport(),
            committer=CapstoneCommitter(store),
        ).run(request)

        self.assertEqual(
            result.outcome,
            OrchestrationOutcome.PENDING_RECONCILIATION,
        )
        assert result.failure_evidence is not None
        self.assertEqual(
            result.failure_evidence.dispatch_certainty,
            DispatchCertainty.POSSIBLY_SENT,
        )
        self.assertEqual(
            result.failure_evidence.execution_certainty,
            ExecutionCertainty.POSSIBLY_EXECUTED,
        )
        self.assertEqual(result.transport_calls, 1)
        self.assertEqual(result.handler_calls, 1)
        self.assertEqual(result.controlled_tool_calls, 1)
        self.assertEqual(result.candidate_validation_calls, 0)
        self.assertEqual(result.committer_calls, 0)
        self.assertFalse(result.durable_transition)
        self.assertIsNone(result.verified_agent_observation)
        persisted = store.read(request.identity.operation_id)
        assert persisted is not None
        self.assertEqual(
            persisted.state,
            RetryDispatchRecordState.DISPATCH_STARTED,
        )

    def test_two_valid_proposals_produce_exactly_one_durable_transition(
        self,
    ) -> None:
        store, claimed = self.claimed_operation_store()
        decision = self.valid_candidate_decision()
        committer = CapstoneCommitter(store)

        winner = committer.commit(
            decision,
            expected_state=RetryDispatchRecordState.DISPATCH_STARTED,
            expected_version=claimed.version,
            expected_fence=claimed.fence_token,
        )
        duplicate = committer.commit(
            decision,
            expected_state=RetryDispatchRecordState.DISPATCH_STARTED,
            expected_version=claimed.version,
            expected_fence=claimed.fence_token,
        )

        self.assertEqual(winner.outcome, CapstoneCommitOutcome.COMMITTED)
        self.assertTrue(winner.durable_transition)
        self.assertEqual(
            duplicate.outcome,
            CapstoneCommitOutcome.ALREADY_COMMITTED,
        )
        self.assertFalse(duplicate.durable_transition)
        self.assertEqual(winner.committer_calls, 1)
        self.assertEqual(duplicate.committer_calls, 1)
        assert duplicate.record is not None
        self.assertEqual(
            duplicate.record.state,
            RetryDispatchRecordState.COMPLETED,
        )

    def test_committer_rejects_stale_fence_without_transition(self) -> None:
        store, claimed = self.claimed_operation_store()

        result = CapstoneCommitter(store).commit(
            self.valid_candidate_decision(),
            expected_state=RetryDispatchRecordState.DISPATCH_STARTED,
            expected_version=claimed.version,
            expected_fence=claimed.fence_token - 1,
        )

        self.assertEqual(result.outcome, CapstoneCommitOutcome.FENCE_CONFLICT)
        self.assertFalse(result.durable_transition)
        current = store.read(claimed.operation_id)
        assert current is not None
        self.assertEqual(current.state, RetryDispatchRecordState.DISPATCH_STARTED)

    def test_committer_rejects_cross_resource_binding_without_transition(
        self,
    ) -> None:
        store, claimed = self.claimed_operation_store()
        decision = self.valid_candidate_decision()
        assert decision.proposal is not None
        conflicting = replace(
            decision,
            proposal=replace(decision.proposal, resource_id="report-99"),
        )

        result = CapstoneCommitter(store).commit(
            conflicting,
            expected_state=RetryDispatchRecordState.DISPATCH_STARTED,
            expected_version=claimed.version,
            expected_fence=claimed.fence_token,
        )

        self.assertEqual(result.outcome, CapstoneCommitOutcome.BINDING_CONFLICT)
        self.assertFalse(result.durable_transition)


if __name__ == "__main__":
    unittest.main()
