"""Thin Day94 router across application-owned Agent and MCP boundaries.

The Orchestrator sequences typed decisions.  It does not implement policy,
authorize a Tool, infer remote execution, or write durable business state.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from agent_mcp_capstone import (
    AgentMCPProposalBoundary,
    AgentMCPToolProposal,
    CapstoneAccessGate,
    CapstoneAccessOutcome,
    CapstoneCandidateOutcome,
    CapstoneCandidatePipeline,
    CapstoneCommitOutcome,
    CapstoneCommitResult,
    CapstoneDispatchClaimer,
    CapstoneOperationIdentity,
    CapstoneOperationIdentityBoundary,
    CapstonePreflight,
    CapstonePreflightOutcome,
    CapstoneToolResultCandidate,
    DurableDispatchGuard,
    OperationPreparationOutcome,
    ProposalBoundaryOutcome,
)
from human_control import ApprovalDecision, ApprovalRequest, ApprovalStatus
from mcp_authorization import AuthorizationDecision
from mcp_protocol_model import ProtocolObservation
from mcp_remote_lifecycle import DeadlineBudget
from mcp_remote_lifecycle import ExecutionCertainty, FailureEvidence
from mcp_remote_protection import TenantCapacityDecision
from mcp_remote_session import RemoteRequestBinding, RemoteResponseCorrelation
from mcp_retry_policy import (
    RetryDispatchClaimOutcome,
    RetryDispatchRecordState,
)
from mcp_versioning import VersionNegotiationResult, VersionedPermitDecision
from tool_governance import ToolCapabilitySnapshot


@dataclass(frozen=True)
class CapstoneTransportExchange:
    """Application-owned transport result, still only candidate evidence."""

    correlation: RemoteResponseCorrelation
    observation: ProtocolObservation
    candidate: CapstoneToolResultCandidate
    transport_calls: int = 1
    handler_calls: int = 1
    controlled_tool_calls: int = 1


class CapstoneTransportPort(Protocol):
    def execute(
        self,
        *,
        identity: CapstoneOperationIdentity,
        tool_name: str,
        attempt: RemoteRequestBinding,
    ) -> CapstoneTransportExchange: ...


class CapstoneUnknownTransportOutcome(RuntimeError):
    """Trusted adapter evidence for a request with no credible result."""

    def __init__(
        self,
        evidence: FailureEvidence,
        *,
        transport_calls: int = 1,
        handler_calls: int = 0,
        controlled_tool_calls: int = 0,
    ) -> None:
        super().__init__(evidence.kind.value)
        if evidence.execution_certainty is not ExecutionCertainty.POSSIBLY_EXECUTED:
            raise ValueError("unknown transport outcome must be possibly executed")
        self.evidence = evidence
        self.transport_calls = transport_calls
        self.handler_calls = handler_calls
        self.controlled_tool_calls = controlled_tool_calls


class CapstoneCommitterPort(Protocol):
    def commit(
        self,
        decision,
        *,
        expected_state: RetryDispatchRecordState,
        expected_version: int,
        expected_fence: int,
    ) -> CapstoneCommitResult: ...


class OrchestrationOutcome(str, Enum):
    PROPOSAL_BLOCKED = "PROPOSAL_BLOCKED"
    IDENTITY_BLOCKED = "IDENTITY_BLOCKED"
    ACCESS_BLOCKED = "ACCESS_BLOCKED"
    PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"
    CLAIM_BLOCKED = "CLAIM_BLOCKED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    CANDIDATE_BLOCKED = "CANDIDATE_BLOCKED"
    COMMIT_BLOCKED = "COMMIT_BLOCKED"
    SUCCEEDED = "SUCCEEDED"


class VerifiedAgentOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"


@dataclass(frozen=True)
class VerifiedAgentObservation:
    """Durable application truth that is safe to return to the Agent."""

    operation_id: str
    resource_id: str
    external_object_id: str
    durable_version: int
    outcome: VerifiedAgentOutcome = VerifiedAgentOutcome.SUCCEEDED
    source: str = "SOLE_COMMITTER"

    def __post_init__(self) -> None:
        if not all(
            (self.operation_id, self.resource_id, self.external_object_id)
        ):
            raise ValueError("verified Agent observation binding is required")
        if self.durable_version < 1:
            raise ValueError("verified observation requires a durable version")


@dataclass(frozen=True)
class CapstoneOrchestrationInput:
    proposal: AgentMCPToolProposal
    capability_snapshot: ToolCapabilitySnapshot
    identity: CapstoneOperationIdentity
    approval_status: ApprovalStatus
    approval_request: ApprovalRequest
    approval_decision: ApprovalDecision | None
    authorization_decision: AuthorizationDecision | None
    guard: DurableDispatchGuard
    attempt: RemoteRequestBinding
    deadline: DeadlineBudget
    now: float
    negotiation: VersionNegotiationResult
    versioned_permit: VersionedPermitDecision
    capacity: TenantCapacityDecision
    circuit_allows_request: bool


@dataclass(frozen=True)
class CapstoneOrchestrationResult:
    outcome: OrchestrationOutcome
    safe_reason: str
    transport_calls: int = 0
    handler_calls: int = 0
    controlled_tool_calls: int = 0
    committer_calls: int = 0
    durable_transition: bool = False
    candidate_validation_calls: int = 0
    failure_evidence: FailureEvidence | None = None
    verified_agent_observation: VerifiedAgentObservation | None = None

    def __post_init__(self) -> None:
        succeeded = self.outcome is OrchestrationOutcome.SUCCEEDED
        if succeeded != (self.verified_agent_observation is not None):
            raise ValueError(
                "only durable success can expose a verified Agent observation"
            )


class AgentMCPOrchestrator:
    """Route typed decisions without absorbing their authority."""

    def __init__(
        self,
        *,
        dispatch_store,
        transport: CapstoneTransportPort,
        committer: CapstoneCommitterPort,
    ) -> None:
        self._dispatch_store = dispatch_store
        self._transport = transport
        self._committer = committer

    def run(
        self,
        request: CapstoneOrchestrationInput,
    ) -> CapstoneOrchestrationResult:
        proposal = AgentMCPProposalBoundary().bind(
            proposal=request.proposal,
            capability_snapshot=request.capability_snapshot,
        )
        if proposal.outcome is not ProposalBoundaryOutcome.ACCEPTED_FOR_GOVERNANCE:
            return CapstoneOrchestrationResult(
                OrchestrationOutcome.PROPOSAL_BLOCKED,
                proposal.safe_reason,
            )
        assert proposal.candidate is not None

        prepared = CapstoneOperationIdentityBoundary().prepare_authorization(
            identity=request.identity,
            candidate=proposal.candidate,
        )
        if prepared.outcome is not OperationPreparationOutcome.READY_FOR_CURRENT_AUTHORIZATION:
            return CapstoneOrchestrationResult(
                OrchestrationOutcome.IDENTITY_BLOCKED,
                prepared.safe_reason,
            )

        access = CapstoneAccessGate().compose(
            identity=request.identity,
            candidate=proposal.candidate,
            approval_status=request.approval_status,
            approval_request=request.approval_request,
            approval_decision=request.approval_decision,
            authorization_decision=request.authorization_decision,
            now=int(request.now),
        )
        if access.outcome is not CapstoneAccessOutcome.READY_FOR_PREFLIGHT:
            return CapstoneOrchestrationResult(
                OrchestrationOutcome.ACCESS_BLOCKED,
                access.safe_reason,
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
        if preflight.outcome is not CapstonePreflightOutcome.READY_FOR_DISPATCH_CLAIM:
            return CapstoneOrchestrationResult(
                OrchestrationOutcome.PREFLIGHT_BLOCKED,
                preflight.safe_reason,
            )

        claim = CapstoneDispatchClaimer().claim(
            store=self._dispatch_store,
            identity=request.identity,
            candidate=proposal.candidate,
            guard=request.guard,
            preflight=preflight,
        )
        if (
            claim.outcome is not RetryDispatchClaimOutcome.CLAIMED
            or claim.record is None
        ):
            return CapstoneOrchestrationResult(
                OrchestrationOutcome.CLAIM_BLOCKED,
                claim.outcome.value,
            )

        try:
            exchange = self._transport.execute(
                identity=request.identity,
                tool_name=proposal.candidate.binding.tool_name,
                attempt=request.attempt,
            )
        except CapstoneUnknownTransportOutcome as unknown:
            evidence = unknown.evidence
            if (
                evidence.operation_id != request.identity.operation_id
                or evidence.idempotency_key != request.identity.idempotency_key
                or evidence.protocol_request_id
                != request.attempt.key.protocol_request_id
                or evidence.attempt_number != request.attempt.attempt_number
            ):
                raise ValueError("transport failure evidence binding mismatch")
            return CapstoneOrchestrationResult(
                outcome=OrchestrationOutcome.PENDING_RECONCILIATION,
                safe_reason=(
                    f"{evidence.kind.value}:"
                    f"{evidence.dispatch_certainty.value}:"
                    f"{evidence.execution_certainty.value}"
                ),
                transport_calls=unknown.transport_calls,
                handler_calls=unknown.handler_calls,
                controlled_tool_calls=unknown.controlled_tool_calls,
                failure_evidence=evidence,
            )
        candidate = CapstoneCandidatePipeline().evaluate(
            identity=request.identity,
            expected_tool_name=proposal.candidate.binding.tool_name,
            expected_attempt=request.attempt,
            correlation=exchange.correlation,
            observation=exchange.observation,
            candidate=exchange.candidate,
        )
        if candidate.outcome is not CapstoneCandidateOutcome.TRANSITION_PROPOSAL_READY:
            return CapstoneOrchestrationResult(
                OrchestrationOutcome.CANDIDATE_BLOCKED,
                candidate.safe_reason,
                exchange.transport_calls,
                exchange.handler_calls,
                exchange.controlled_tool_calls,
            )

        committed = self._committer.commit(
            candidate,
            expected_state=RetryDispatchRecordState.DISPATCH_STARTED,
            expected_version=claim.record.version,
            expected_fence=claim.record.fence_token,
        )
        succeeded = committed.outcome in {
            CapstoneCommitOutcome.COMMITTED,
            CapstoneCommitOutcome.ALREADY_COMMITTED,
        }
        verified_observation = None
        if succeeded:
            if committed.record is None or committed.record.external_object_id is None:
                raise ValueError("committed success record is incomplete")
            verified_observation = VerifiedAgentObservation(
                operation_id=committed.record.operation_id,
                resource_id=committed.record.resource_id or "",
                external_object_id=committed.record.external_object_id,
                durable_version=committed.record.version,
            )
        return CapstoneOrchestrationResult(
            (
                OrchestrationOutcome.SUCCEEDED
                if succeeded
                else OrchestrationOutcome.COMMIT_BLOCKED
            ),
            committed.outcome.value,
            exchange.transport_calls,
            exchange.handler_calls,
            exchange.controlled_tool_calls,
            committed.committer_calls,
            committed.durable_transition,
            candidate_validation_calls=1,
            verified_agent_observation=verified_observation,
        )
