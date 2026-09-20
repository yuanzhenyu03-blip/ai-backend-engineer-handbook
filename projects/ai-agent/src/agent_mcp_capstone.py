"""Day94 application-owned Agent-to-MCP proposal boundary.

Framework-native output must be converted before it enters this module.  This
boundary binds an untrusted proposal to the immutable Day80 capability
snapshot; it does not authorize, dispatch, call MCP, or commit durable state.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol

from human_control import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    fingerprint,
)
from mcp_authorization import (
    AuthorizationDecision,
    AuthorizationOutcome,
    ToolAuthorizationPermit,
    ToolAuthorizationRequest,
)
from mcp_observability import OperationRefEncoder, SafeTraceCorrelation
from mcp_protocol_model import ProtocolObservation, ProtocolOutcome
from mcp_remote_lifecycle import DeadlineBudget
from mcp_remote_lifecycle import ExecutionCertainty, FailureEvidence
from mcp_remote_protection import (
    TenantCapacityDecision,
    TenantCapacityOutcome,
)
from mcp_remote_session import (
    RemoteRequestBinding,
    RemoteRequestKey,
    RemoteResponseCorrelation,
    RemoteResponseCorrelationOutcome,
)
from mcp_retry_policy import (
    RetryDecision,
    RetryAttemptPlan,
    RetryDispatchClaim,
    RetryDispatchClaimOutcome,
    RetryDispatchDecision,
    RetryDispatchDecisionKind,
    RetryDispatchRecordState,
    RetryDispatchRecord,
    plan_retry_attempt,
    recover_abandoned_dispatch,
)
from mcp_reconciliation import (
    ApplicationOperationBinding,
    AuthoritativeOperationStatus,
    AuthoritativeStatusQueryPort,
    BoundedReconciliationPolicy,
    OperationalAlertPort,
    ReconciliationDecision,
    ReconciliationScheduleDecision,
    ReconciliationScheduleState,
    ReconciliationScheduler,
)
from mcp_versioning import (
    VersionNegotiationOutcome,
    VersionNegotiationResult,
    VersionedPermitDecision,
    VersionedPermitOutcome,
)
from tool_governance import (
    BoundToolInvocation,
    GovernedToolCandidate,
    ToolCapabilitySnapshot,
)


@dataclass(frozen=True)
class AgentMCPToolProposal:
    """Application DTO produced from untrusted model/framework output."""

    tool_name: str
    tool_version: str
    arguments_json: str

    def __post_init__(self) -> None:
        if not self.tool_name or not self.tool_version:
            raise ValueError("proposal Tool identity is required")
        try:
            arguments = json.loads(self.arguments_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("proposal arguments must be valid JSON") from exc
        if not isinstance(arguments, dict):
            raise ValueError("proposal arguments must be a JSON object")
        canonical = json.dumps(
            arguments,
            sort_keys=True,
            separators=(",", ":"),
        )
        object.__setattr__(self, "arguments_json", canonical)

    @classmethod
    def from_mapping(
        cls,
        *,
        tool_name: str,
        tool_version: str,
        arguments: Mapping[str, object],
    ) -> "AgentMCPToolProposal":
        return cls(
            tool_name=tool_name,
            tool_version=tool_version,
            arguments_json=json.dumps(
                dict(arguments),
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    def arguments(self) -> Mapping[str, object]:
        decoded = json.loads(self.arguments_json)
        if not isinstance(decoded, dict):  # Defensive; __post_init__ guarantees it.
            raise ValueError("proposal arguments must remain a JSON object")
        return decoded


class ProposalBoundaryOutcome(str, Enum):
    ACCEPTED_FOR_GOVERNANCE = "ACCEPTED_FOR_GOVERNANCE"
    TOOL_NOT_VISIBLE = "TOOL_NOT_VISIBLE"


@dataclass(frozen=True)
class ProposalBoundaryDecision:
    """A binding decision, never authorization or permission to dispatch."""

    outcome: ProposalBoundaryOutcome
    safe_reason: str
    candidate: GovernedToolCandidate | None = None

    def __post_init__(self) -> None:
        accepted = self.outcome is ProposalBoundaryOutcome.ACCEPTED_FOR_GOVERNANCE
        if accepted != (self.candidate is not None):
            raise ValueError("only an accepted proposal carries a candidate")


class AgentMCPProposalBoundary:
    """Bind a proposal to Day80 facts without gaining execution authority."""

    def bind(
        self,
        *,
        proposal: AgentMCPToolProposal,
        capability_snapshot: ToolCapabilitySnapshot,
    ) -> ProposalBoundaryDecision:
        visible = next(
            (
                tool
                for tool in capability_snapshot.visible_tools
                if tool.name == proposal.tool_name
                and tool.version == proposal.tool_version
            ),
            None,
        )
        if visible is None:
            return ProposalBoundaryDecision(
                ProposalBoundaryOutcome.TOOL_NOT_VISIBLE,
                "PROPOSED_TOOL_NOT_IN_IMMUTABLE_SNAPSHOT",
            )

        binding = BoundToolInvocation(
            snapshot_id=capability_snapshot.snapshot_id,
            tenant_id=capability_snapshot.tenant_id,
            user_id=capability_snapshot.user_id,
            role=capability_snapshot.role,
            job_id=capability_snapshot.job_id,
            step_id=capability_snapshot.step_id,
            tool_name=visible.name,
            tool_version=visible.version,
            arguments_schema_sha256=visible.arguments_schema_sha256,
        )
        return ProposalBoundaryDecision(
            ProposalBoundaryOutcome.ACCEPTED_FOR_GOVERNANCE,
            "BOUND_TO_APPLICATION_CAPABILITY_SNAPSHOT",
            GovernedToolCandidate(
                binding=binding,
                arguments=proposal.arguments(),
            ),
        )


@dataclass(frozen=True)
class CapstoneOperationIdentity:
    """Trusted stable identity established by the application controller."""

    operation_id: str
    idempotency_key: str
    tenant_id: str
    resource_id: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.operation_id,
                self.idempotency_key,
                self.tenant_id,
                self.resource_id,
            )
        ):
            raise ValueError("stable operation identity fields are required")


class OperationPreparationOutcome(str, Enum):
    READY_FOR_CURRENT_AUTHORIZATION = "READY_FOR_CURRENT_AUTHORIZATION"
    TENANT_BINDING_CONFLICT = "TENANT_BINDING_CONFLICT"
    RESOURCE_BINDING_CONFLICT = "RESOURCE_BINDING_CONFLICT"


@dataclass(frozen=True)
class OperationPreparationDecision:
    """Identity binding result; an authorization request is not a permit."""

    outcome: OperationPreparationOutcome
    safe_reason: str
    authorization_request: ToolAuthorizationRequest | None = None

    def __post_init__(self) -> None:
        ready = (
            self.outcome
            is OperationPreparationOutcome.READY_FOR_CURRENT_AUTHORIZATION
        )
        if ready != (self.authorization_request is not None):
            raise ValueError("only a ready decision carries an auth request")


class CapstoneOperationIdentityBoundary:
    """Combine trusted identity with a bound proposal before authorization."""

    def prepare_authorization(
        self,
        *,
        identity: CapstoneOperationIdentity,
        candidate: GovernedToolCandidate,
    ) -> OperationPreparationDecision:
        if candidate.binding.tenant_id != identity.tenant_id:
            return OperationPreparationDecision(
                OperationPreparationOutcome.TENANT_BINDING_CONFLICT,
                "CAPABILITY_SNAPSHOT_TENANT_MISMATCH",
            )
        proposed_resource = candidate.arguments.get("resource_id")
        if proposed_resource != identity.resource_id:
            return OperationPreparationDecision(
                OperationPreparationOutcome.RESOURCE_BINDING_CONFLICT,
                "PROPOSAL_RESOURCE_DOES_NOT_MATCH_TRUSTED_OPERATION",
            )
        return OperationPreparationDecision(
            OperationPreparationOutcome.READY_FOR_CURRENT_AUTHORIZATION,
            "TRUSTED_OPERATION_BOUND_TO_PROPOSAL",
            ToolAuthorizationRequest(
                application_operation_id=identity.operation_id,
                idempotency_key=identity.idempotency_key,
                requested_tenant_id=identity.tenant_id,
                tool_name=candidate.binding.tool_name,
                resource_id=identity.resource_id,
            ),
        )


class CapstoneAccessOutcome(str, Enum):
    READY_FOR_PREFLIGHT = "READY_FOR_PREFLIGHT"
    HUMAN_CHECKPOINT_BLOCKED = "HUMAN_CHECKPOINT_BLOCKED"
    APPROVAL_BINDING_CONFLICT = "APPROVAL_BINDING_CONFLICT"
    CURRENT_AUTHORIZATION_BLOCKED = "CURRENT_AUTHORIZATION_BLOCKED"
    PERMIT_BINDING_CONFLICT = "PERMIT_BINDING_CONFLICT"


@dataclass(frozen=True)
class CapstoneAccessDecision:
    """Preserve separate human and authorization evidence for audit."""

    outcome: CapstoneAccessOutcome
    safe_reason: str
    approval_decision: ApprovalDecision | None
    authorization_decision: AuthorizationDecision | None
    permit: ToolAuthorizationPermit | None = None

    def __post_init__(self) -> None:
        ready = self.outcome is CapstoneAccessOutcome.READY_FOR_PREFLIGHT
        if ready != (self.permit is not None):
            raise ValueError("only a preflight-ready decision carries a permit")


class CapstoneAccessGate:
    """Compose Day83 approval with Day92 current exact authorization."""

    def compose(
        self,
        *,
        identity: CapstoneOperationIdentity,
        candidate: GovernedToolCandidate,
        approval_status: ApprovalStatus,
        approval_request: ApprovalRequest,
        approval_decision: ApprovalDecision | None,
        authorization_decision: AuthorizationDecision | None,
        now: int,
    ) -> CapstoneAccessDecision:
        if (
            approval_status is not ApprovalStatus.APPROVED
            or approval_decision is None
            or approval_decision.choice is not ApprovalStatus.APPROVED
            or now >= approval_request.expires_at
        ):
            return CapstoneAccessDecision(
                CapstoneAccessOutcome.HUMAN_CHECKPOINT_BLOCKED,
                "CURRENT_HUMAN_APPROVAL_REQUIRED",
                approval_decision,
                authorization_decision,
            )

        action = approval_request.binding
        expected_approval_binding = (
            action.operation_id == identity.operation_id
            and action.tenant_id == identity.tenant_id
            and action.artifact_id == identity.resource_id
            and action.tool_name == candidate.binding.tool_name
            and action.tool_version == candidate.binding.tool_version
            and action.arguments_fingerprint
            == fingerprint(dict(candidate.arguments))
            and approval_decision.request_id == approval_request.request_id
            and approval_decision.binding_fingerprint == action.digest
            and approval_decision.tenant_id == identity.tenant_id
        )
        if not expected_approval_binding:
            return CapstoneAccessDecision(
                CapstoneAccessOutcome.APPROVAL_BINDING_CONFLICT,
                "APPROVAL_DOES_NOT_BIND_CURRENT_OPERATION",
                approval_decision,
                authorization_decision,
            )

        if (
            authorization_decision is None
            or authorization_decision.outcome
            is not AuthorizationOutcome.AUTHORIZED
            or authorization_decision.permit is None
        ):
            return CapstoneAccessDecision(
                CapstoneAccessOutcome.CURRENT_AUTHORIZATION_BLOCKED,
                "CURRENT_EXACT_TOOL_AUTHORIZATION_REQUIRED",
                approval_decision,
                authorization_decision,
            )

        permit = authorization_decision.permit
        if (
            permit.application_operation_id != identity.operation_id
            or permit.idempotency_key != identity.idempotency_key
            or permit.tenant_id != identity.tenant_id
            or permit.resource_id != identity.resource_id
            or permit.tool_name != candidate.binding.tool_name
        ):
            return CapstoneAccessDecision(
                CapstoneAccessOutcome.PERMIT_BINDING_CONFLICT,
                "AUTHORIZATION_PERMIT_DOES_NOT_BIND_CURRENT_OPERATION",
                approval_decision,
                authorization_decision,
            )

        return CapstoneAccessDecision(
            CapstoneAccessOutcome.READY_FOR_PREFLIGHT,
            "HUMAN_AND_CURRENT_AUTHORIZATION_COMPOSED",
            approval_decision,
            authorization_decision,
            permit,
        )


@dataclass(frozen=True)
class DurableDispatchGuard:
    """Current durable ownership facts, not a dispatch command."""

    operation_id: str
    idempotency_key: str
    expected_state: str
    current_state: str
    expected_version: int
    current_version: int
    expected_fence: int
    current_fence: int
    caller_intent_active: bool
    cancelled: bool

    def __post_init__(self) -> None:
        if not all(
            (
                self.operation_id,
                self.idempotency_key,
                self.expected_state,
                self.current_state,
            )
        ):
            raise ValueError("durable dispatch identity and state are required")
        if any(
            value < 0
            for value in (
                self.expected_version,
                self.current_version,
                self.expected_fence,
                self.current_fence,
            )
        ):
            raise ValueError("durable versions and fences must be non-negative")


class CapstonePreflightOutcome(str, Enum):
    READY_FOR_DISPATCH_CLAIM = "READY_FOR_DISPATCH_CLAIM"
    ACCESS_NOT_CURRENT = "ACCESS_NOT_CURRENT"
    ATTEMPT_IDENTITY_CONFLICT = "ATTEMPT_IDENTITY_CONFLICT"
    DURABLE_OWNERSHIP_STALE = "DURABLE_OWNERSHIP_STALE"
    CALLER_INTENT_INACTIVE = "CALLER_INTENT_INACTIVE"
    DEADLINE_EXHAUSTED = "DEADLINE_EXHAUSTED"
    PROTOCOL_NEGOTIATION_INCOMPATIBLE = "PROTOCOL_NEGOTIATION_INCOMPATIBLE"
    ATTEMPT_GENERATION_MISMATCH = "ATTEMPT_GENERATION_MISMATCH"
    VERSIONED_PERMIT_REJECTED = "VERSIONED_PERMIT_REJECTED"
    CAPACITY_REJECTED = "CAPACITY_REJECTED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"


@dataclass(frozen=True)
class CapstonePreflightDecision:
    """Pure pre-dispatch result; it never persists a claim or sends MCP."""

    outcome: CapstonePreflightOutcome
    safe_reason: str
    attempt: RemoteRequestBinding | None = None
    transport_calls: int = 0
    handler_calls: int = 0
    committer_calls: int = 0

    def __post_init__(self) -> None:
        ready = (
            self.outcome
            is CapstonePreflightOutcome.READY_FOR_DISPATCH_CLAIM
        )
        if ready != (self.attempt is not None):
            raise ValueError("only a ready preflight carries an attempt")
        if any(
            value != 0
            for value in (
                self.transport_calls,
                self.handler_calls,
                self.committer_calls,
            )
        ):
            raise ValueError("preflight cannot call transport, handler or Committer")


class CapstonePreflight:
    """Compose ownership, attempt, protocol and admission evidence."""

    def evaluate(
        self,
        *,
        identity: CapstoneOperationIdentity,
        access: CapstoneAccessDecision,
        guard: DurableDispatchGuard,
        attempt: RemoteRequestBinding,
        deadline: DeadlineBudget,
        now: float,
        negotiation: VersionNegotiationResult,
        versioned_permit: VersionedPermitDecision,
        capacity: TenantCapacityDecision,
        circuit_allows_request: bool,
    ) -> CapstonePreflightDecision:
        if access.outcome is not CapstoneAccessOutcome.READY_FOR_PREFLIGHT:
            return self._blocked(
                CapstonePreflightOutcome.ACCESS_NOT_CURRENT,
                "FRESH_HUMAN_AND_AUTHORIZATION_DECISIONS_REQUIRED",
            )
        if (
            guard.operation_id != identity.operation_id
            or guard.idempotency_key != identity.idempotency_key
            or attempt.operation_id != identity.operation_id
            or attempt.idempotency_key != identity.idempotency_key
        ):
            return self._blocked(
                CapstonePreflightOutcome.ATTEMPT_IDENTITY_CONFLICT,
                "ATTEMPT_DOES_NOT_BIND_STABLE_OPERATION",
            )
        if (
            guard.expected_state != guard.current_state
            or guard.expected_version != guard.current_version
            or guard.expected_fence != guard.current_fence
        ):
            return self._blocked(
                CapstonePreflightOutcome.DURABLE_OWNERSHIP_STALE,
                "STATE_VERSION_OR_FENCE_CHANGED",
            )
        if not guard.caller_intent_active or guard.cancelled:
            return self._blocked(
                CapstonePreflightOutcome.CALLER_INTENT_INACTIVE,
                "CALLER_INTENT_OR_CANCELLATION_BLOCKS_NEW_DISPATCH",
            )
        if deadline.remaining(now=now) <= 0:
            return self._blocked(
                CapstonePreflightOutcome.DEADLINE_EXHAUSTED,
                "PARENT_DEADLINE_EXHAUSTED",
            )
        if negotiation.outcome is not VersionNegotiationOutcome.NEGOTIATED:
            return self._blocked(
                CapstonePreflightOutcome.PROTOCOL_NEGOTIATION_INCOMPATIBLE,
                "NO_COMPATIBLE_PROTOCOL_VERSION",
            )
        if attempt.key.transport_generation != negotiation.generation:
            return self._blocked(
                CapstonePreflightOutcome.ATTEMPT_GENERATION_MISMATCH,
                "ATTEMPT_NOT_BOUND_TO_CURRENT_TRANSPORT_GENERATION",
            )
        if versioned_permit.outcome is not VersionedPermitOutcome.ADMITTED:
            return self._blocked(
                CapstonePreflightOutcome.VERSIONED_PERMIT_REJECTED,
                versioned_permit.outcome.value,
            )
        if capacity.outcome is not TenantCapacityOutcome.ADMITTED:
            return self._blocked(
                CapstonePreflightOutcome.CAPACITY_REJECTED,
                "CURRENT_TENANT_CAPACITY_NOT_ADMITTED",
            )
        if not circuit_allows_request:
            return self._blocked(
                CapstonePreflightOutcome.CIRCUIT_OPEN,
                "LOCAL_CIRCUIT_OPEN",
            )
        return CapstonePreflightDecision(
            CapstonePreflightOutcome.READY_FOR_DISPATCH_CLAIM,
            "ALL_PREFLIGHT_GATES_PASSED",
            attempt,
        )

    @staticmethod
    def _blocked(
        outcome: CapstonePreflightOutcome,
        reason: str,
    ) -> CapstonePreflightDecision:
        return CapstonePreflightDecision(outcome, reason)


class DispatchClaimStorePort(Protocol):
    def claim_dispatch(
        self,
        dispatch: RetryDispatchDecision,
        *,
        expected_version: int,
        expected_state: RetryDispatchRecordState,
        expected_fence: int | None,
        new_fence: int | None,
        tenant_id: str | None,
        resource_id: str | None,
        tool_name: str | None,
    ) -> RetryDispatchClaim: ...


class CapstoneDispatchClaimer:
    """Persist one conditional claim; transport handoff remains outside."""

    def claim(
        self,
        *,
        store: DispatchClaimStorePort,
        identity: CapstoneOperationIdentity,
        candidate: GovernedToolCandidate,
        guard: DurableDispatchGuard,
        preflight: CapstonePreflightDecision,
    ) -> RetryDispatchClaim:
        if (
            preflight.outcome
            is not CapstonePreflightOutcome.READY_FOR_DISPATCH_CLAIM
            or preflight.attempt is None
        ):
            return RetryDispatchClaim(
                # The existing contract represents failed admission without
                # fabricating transport activity.
                outcome=RetryDispatchClaimOutcome.NOT_ADMITTED,
            )

        binding = preflight.attempt
        attempt = RetryAttemptPlan(
            operation_id=binding.operation_id,
            idempotency_key=binding.idempotency_key,
            protocol_request_id=binding.key.protocol_request_id,
            attempt_number=binding.attempt_number,
            delay_seconds=0.0,
            transport_generation=binding.key.transport_generation,
        )
        dispatch = RetryDispatchDecision(
            RetryDispatchDecisionKind.ADMITTED,
            attempt,
        )
        return store.claim_dispatch(
            dispatch,
            expected_version=guard.current_version,
            expected_state=RetryDispatchRecordState(guard.current_state),
            expected_fence=guard.current_fence,
            new_fence=guard.current_fence + 1,
            tenant_id=identity.tenant_id,
            resource_id=identity.resource_id,
            tool_name=candidate.binding.tool_name,
        )


class RecoveryCoordinationOutcome(str, Enum):
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


@dataclass(frozen=True)
class RecoveryCoordinationDecision:
    """A restart plan that can only schedule read-only reconciliation."""

    outcome: RecoveryCoordinationOutcome
    binding: ApplicationOperationBinding
    failure: FailureEvidence
    attempt_number: int
    protocol_request_id: str | int
    transport_generation: int
    original_tool_calls: int = 0
    committer_calls: int = 0

    def __post_init__(self) -> None:
        if self.failure.execution_certainty is not ExecutionCertainty.POSSIBLY_EXECUTED:
            raise ValueError("recovery coordination requires an unknown outcome")
        if self.original_tool_calls != 0 or self.committer_calls != 0:
            raise ValueError("Recovery Coordinator cannot replay or commit")


class CapstoneRecoveryCoordinator:
    """Recover a durable claim without guessing whether transport ran."""

    def plan(self, record: RetryDispatchRecord) -> RecoveryCoordinationDecision:
        if record.state is not RetryDispatchRecordState.DISPATCH_STARTED:
            raise ValueError("only DISPATCH_STARTED requires crash recovery")
        if (
            record.tenant_id is None
            or record.resource_id is None
            or record.protocol_request_id is None
            or record.transport_generation is None
        ):
            raise ValueError("recovery requires complete durable attempt identity")

        failure = recover_abandoned_dispatch(record)
        binding = ApplicationOperationBinding(
            operation_id=record.operation_id,
            idempotency_key=record.idempotency_key,
            tenant_id=record.tenant_id,
            resource_id=record.resource_id,
        )
        return RecoveryCoordinationDecision(
            RecoveryCoordinationOutcome.RECONCILIATION_REQUIRED,
            binding,
            failure,
            record.attempt_number,
            record.protocol_request_id,
            record.transport_generation,
        )


class GracefulShutdownOutcome(str, Enum):
    UNKNOWN_OUTCOME_PRESERVED = "UNKNOWN_OUTCOME_PRESERVED"


@dataclass(frozen=True)
class GracefulShutdownDecision:
    """Shutdown evidence only; the durable dispatch marker is unchanged."""

    outcome: GracefulShutdownOutcome
    record: RetryDispatchRecord
    execution_certainty: ExecutionCertainty
    new_dispatch_allowed: bool = False
    committer_calls: int = 0
    durable_transition: bool = False

    def __post_init__(self) -> None:
        if self.execution_certainty is not ExecutionCertainty.POSSIBLY_EXECUTED:
            raise ValueError("shutdown must preserve possible execution")
        if self.new_dispatch_allowed:
            raise ValueError("unknown shutdown outcome cannot dispatch")
        if self.committer_calls != 0 or self.durable_transition:
            raise ValueError("shutdown handler cannot commit business state")


class CapstoneGracefulShutdown:
    """Stop local work without inventing a remote execution conclusion."""

    def preserve_unknown(
        self,
        record: RetryDispatchRecord,
        *,
        transport_handoff_completed: bool,
        trustworthy_response_received: bool,
    ) -> GracefulShutdownDecision:
        if record.state is not RetryDispatchRecordState.DISPATCH_STARTED:
            raise ValueError("shutdown recovery requires DISPATCH_STARTED")
        if not transport_handoff_completed or trustworthy_response_received:
            raise ValueError("this path requires handoff without a response")
        return GracefulShutdownDecision(
            GracefulShutdownOutcome.UNKNOWN_OUTCOME_PRESERVED,
            record,
            ExecutionCertainty.POSSIBLY_EXECUTED,
        )


class OperatorTelemetryClaim(str, Enum):
    REMOTE_TOOL_SUCCESS = "REMOTE_TOOL_SUCCESS"


@dataclass(frozen=True)
class CapstoneOperatorEvidenceReport:
    """Credential-safe report that labels observation versus authority."""

    operation_ref: str
    telemetry_claim: OperatorTelemetryClaim
    telemetry_is_authority: bool
    authoritative_status: AuthoritativeOperationStatus
    authority_resolved_outcome: bool
    durable_state: RetryDispatchRecordState
    durable_fact_is_authority: bool
    execution_certainty: ExecutionCertainty
    next_action: str
    committer_allowed: bool

    def to_json(self) -> str:
        return json.dumps(
            {
                "operation_ref": self.operation_ref,
                "telemetry": {
                    "claim": self.telemetry_claim.value,
                    "is_authority": self.telemetry_is_authority,
                },
                "authoritative_query": {
                    "status": self.authoritative_status.value,
                    "resolved_outcome": self.authority_resolved_outcome,
                },
                "durable_application_fact": {
                    "state": self.durable_state.value,
                    "is_authority": self.durable_fact_is_authority,
                },
                "execution_certainty": self.execution_certainty.value,
                "next_action": self.next_action,
                "committer_allowed": self.committer_allowed,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


class CapstoneOperatorEvidenceBuilder:
    """Build the pending-reconciliation report without granting authority."""

    def __init__(self, encoder: OperationRefEncoder) -> None:
        self._encoder = encoder

    def build_not_found_report(
        self,
        *,
        record: RetryDispatchRecord,
        trace: SafeTraceCorrelation,
        telemetry_claim: OperatorTelemetryClaim,
        authoritative_status: AuthoritativeOperationStatus,
    ) -> CapstoneOperatorEvidenceReport:
        operation_ref = self._encoder.encode(record.operation_id)
        if trace.operation_ref != operation_ref:
            raise ValueError("trace does not correlate to the durable operation")
        if trace.transport_generation != record.transport_generation:
            raise ValueError("trace transport generation does not match")
        if record.state is not RetryDispatchRecordState.DISPATCH_STARTED:
            raise ValueError("pending operator report requires DISPATCH_STARTED")
        if authoritative_status is not AuthoritativeOperationStatus.NOT_FOUND:
            raise ValueError("this report is only for unresolved NOT_FOUND")
        return CapstoneOperatorEvidenceReport(
            operation_ref=operation_ref,
            telemetry_claim=telemetry_claim,
            telemetry_is_authority=False,
            authoritative_status=authoritative_status,
            authority_resolved_outcome=False,
            durable_state=record.state,
            durable_fact_is_authority=True,
            execution_certainty=ExecutionCertainty.POSSIBLY_EXECUTED,
            next_action="CONTINUE_BOUNDED_RECONCILIATION",
            committer_allowed=False,
        )


@dataclass(frozen=True)
class CapstoneReconciliationCycleResult:
    """One read-only observation plus its bounded follow-up schedule."""

    observation: ReconciliationDecision
    schedule: ReconciliationScheduleDecision
    original_tool_calls: int = 0
    committer_calls: int = 0

    def __post_init__(self) -> None:
        if self.original_tool_calls != 0 or self.committer_calls != 0:
            raise ValueError("reconciliation observation cannot replay or commit")


class CapstoneReconciliationCycle:
    """Compose Day94 recovery with the existing Day93 reconciliation policy."""

    def run_once(
        self,
        recovery: RecoveryCoordinationDecision,
        *,
        authority: AuthoritativeStatusQueryPort,
        policy: BoundedReconciliationPolicy,
        state: ReconciliationScheduleState,
        now: float,
        operation_ref: str,
        alerts: OperationalAlertPort,
    ) -> CapstoneReconciliationCycleResult:
        if recovery.outcome is not RecoveryCoordinationOutcome.RECONCILIATION_REQUIRED:
            raise ValueError("recovery must require reconciliation")
        if state.binding != recovery.binding:
            raise ValueError("reconciliation schedule binding mismatch")

        observation = ReconciliationScheduler(authority).reconcile_once(
            recovery.failure,
            binding=recovery.binding,
        )
        schedule = policy.advance(
            observation,
            state,
            now=now,
            operation_ref=operation_ref,
            alerts=alerts,
        )
        return CapstoneReconciliationCycleResult(observation, schedule)


@dataclass(frozen=True)
class CapstoneRetryAttempt:
    """Stable application identity plus one fresh protocol attempt."""

    identity: CapstoneOperationIdentity
    tool_name: str
    binding: RemoteRequestBinding


class CapstoneRetryAttemptFactory:
    """Create attempt identity only after committed retry-safe evidence."""

    def prepare(
        self,
        *,
        identity: CapstoneOperationIdentity,
        tool_name: str,
        evidence: FailureEvidence,
        decision: RetryDecision,
        new_protocol_request_id: str | int,
        current_transport_generation: int,
    ) -> CapstoneRetryAttempt:
        if (
            evidence.execution_certainty
            is not ExecutionCertainty.PROVEN_NOT_EXECUTED
        ):
            raise ValueError("retry attempt requires PROVEN_NOT_EXECUTED")
        if (
            evidence.operation_id != identity.operation_id
            or evidence.idempotency_key != identity.idempotency_key
        ):
            raise ValueError("retry evidence changed stable operation identity")
        if not tool_name or current_transport_generation < 1:
            raise ValueError("current Tool and transport generation are required")

        planned = plan_retry_attempt(
            evidence,
            decision,
            new_protocol_request_id=new_protocol_request_id,
            transport_generation=current_transport_generation,
        )
        return CapstoneRetryAttempt(
            identity,
            tool_name,
            RemoteRequestBinding(
                key=RemoteRequestKey(
                    current_transport_generation,
                    planned.protocol_request_id,
                ),
                operation_id=planned.operation_id,
                idempotency_key=planned.idempotency_key,
                attempt_number=planned.attempt_number,
            ),
        )


@dataclass(frozen=True)
class CapstoneToolResultCandidate:
    """Untrusted application content decoded from a correlated MCP result."""

    operation_id: str
    tenant_id: str
    resource_id: str
    tool_name: str
    external_object_id: str


@dataclass(frozen=True)
class CapstoneSuccessTransitionProposal:
    """Validated success proposal; only a Committer may persist it."""

    operation_id: str
    idempotency_key: str
    tenant_id: str
    resource_id: str
    tool_name: str
    attempt_number: int
    protocol_request_id: str | int
    transport_generation: int
    external_object_id: str
    desired_state: str = "SUCCEEDED"
    durable_transition: bool = False


class CapstoneCandidateOutcome(str, Enum):
    CORRELATION_REJECTED = "CORRELATION_REJECTED"
    PROTOCOL_REJECTED = "PROTOCOL_REJECTED"
    OUTPUT_REJECTED = "OUTPUT_REJECTED"
    TRANSITION_PROPOSAL_READY = "TRANSITION_PROPOSAL_READY"


@dataclass(frozen=True)
class CapstoneCandidateDecision:
    """Explicit stage result with negative-path call counts."""

    outcome: CapstoneCandidateOutcome
    safe_reason: str
    proposal: CapstoneSuccessTransitionProposal | None = None
    correlation_checks: int = 1
    protocol_validation_calls: int = 0
    output_validation_calls: int = 0
    committer_calls: int = 0
    durable_transitions: int = 0

    def __post_init__(self) -> None:
        ready = (
            self.outcome
            is CapstoneCandidateOutcome.TRANSITION_PROPOSAL_READY
        )
        if ready != (self.proposal is not None):
            raise ValueError("only a ready decision carries a proposal")
        if self.correlation_checks != 1:
            raise ValueError("candidate evaluation performs one correlation check")
        if self.committer_calls != 0 or self.durable_transitions != 0:
            raise ValueError("candidate evaluation cannot commit durable state")


class CapstoneCandidatePipeline:
    """Separate response identity, protocol shape and application output."""

    def evaluate(
        self,
        *,
        identity: CapstoneOperationIdentity,
        expected_tool_name: str,
        expected_attempt: RemoteRequestBinding,
        correlation: RemoteResponseCorrelation,
        observation: ProtocolObservation,
        candidate: CapstoneToolResultCandidate,
    ) -> CapstoneCandidateDecision:
        remote_binding = correlation.binding
        if (
            correlation.outcome
            is not RemoteResponseCorrelationOutcome.MATCHED
            or remote_binding is None
            or remote_binding != expected_attempt
            or expected_attempt.operation_id != identity.operation_id
            or expected_attempt.idempotency_key != identity.idempotency_key
        ):
            return CapstoneCandidateDecision(
                CapstoneCandidateOutcome.CORRELATION_REJECTED,
                "RESPONSE_NOT_BOUND_TO_CURRENT_ATTEMPT_AND_GENERATION",
            )

        if (
            observation.outcome is not ProtocolOutcome.PROTOCOL_RESULT
            or observation.protocol_request_id
            != expected_attempt.key.protocol_request_id
            or observation.application_operation_id != identity.operation_id
        ):
            return CapstoneCandidateDecision(
                CapstoneCandidateOutcome.PROTOCOL_REJECTED,
                "PROTOCOL_OBSERVATION_NOT_A_MATCHED_RESULT",
                protocol_validation_calls=1,
            )

        if (
            candidate.operation_id != identity.operation_id
            or candidate.tenant_id != identity.tenant_id
            or candidate.resource_id != identity.resource_id
            or candidate.tool_name != expected_tool_name
            or not candidate.external_object_id
        ):
            return CapstoneCandidateDecision(
                CapstoneCandidateOutcome.OUTPUT_REJECTED,
                "CANDIDATE_OUTPUT_DOES_NOT_MATCH_APPLICATION_BINDING",
                protocol_validation_calls=1,
                output_validation_calls=1,
            )

        return CapstoneCandidateDecision(
            CapstoneCandidateOutcome.TRANSITION_PROPOSAL_READY,
            "CORRELATED_AND_VALIDATED_CANDIDATE_REQUIRES_COMMITTER",
            CapstoneSuccessTransitionProposal(
                operation_id=identity.operation_id,
                idempotency_key=identity.idempotency_key,
                tenant_id=identity.tenant_id,
                resource_id=identity.resource_id,
                tool_name=expected_tool_name,
                attempt_number=expected_attempt.attempt_number,
                protocol_request_id=expected_attempt.key.protocol_request_id,
                transport_generation=(
                    expected_attempt.key.transport_generation
                ),
                external_object_id=candidate.external_object_id,
            ),
            protocol_validation_calls=1,
            output_validation_calls=1,
        )


class CapstoneCommitStorePort(Protocol):
    def read(self, operation_id: str) -> RetryDispatchRecord | None: ...

    def compare_and_set_completed(
        self,
        *,
        operation_id: str,
        idempotency_key: str,
        tenant_id: str,
        resource_id: str,
        tool_name: str,
        attempt_number: int,
        protocol_request_id: str | int,
        transport_generation: int,
        expected_state: RetryDispatchRecordState,
        expected_version: int,
        expected_fence: int,
        external_object_id: str,
    ) -> RetryDispatchRecord | None: ...


class CapstoneCommitOutcome(str, Enum):
    COMMITTED = "COMMITTED"
    ALREADY_COMMITTED = "ALREADY_COMMITTED"
    PROPOSAL_NOT_READY = "PROPOSAL_NOT_READY"
    BINDING_CONFLICT = "BINDING_CONFLICT"
    ATTEMPT_CONFLICT = "ATTEMPT_CONFLICT"
    STATE_CONFLICT = "STATE_CONFLICT"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    FENCE_CONFLICT = "FENCE_CONFLICT"
    CAS_CONFLICT = "CAS_CONFLICT"


@dataclass(frozen=True)
class CapstoneCommitResult:
    outcome: CapstoneCommitOutcome
    record: RetryDispatchRecord | None = None
    committer_calls: int = 1
    durable_transition: bool = False


class CapstoneCommitter:
    """The sole writer for a validated candidate's durable success fact."""

    def __init__(self, store: CapstoneCommitStorePort) -> None:
        self._store = store

    def commit(
        self,
        decision: CapstoneCandidateDecision,
        *,
        expected_state: RetryDispatchRecordState,
        expected_version: int,
        expected_fence: int,
    ) -> CapstoneCommitResult:
        proposal = decision.proposal
        if (
            decision.outcome
            is not CapstoneCandidateOutcome.TRANSITION_PROPOSAL_READY
            or proposal is None
        ):
            return CapstoneCommitResult(
                CapstoneCommitOutcome.PROPOSAL_NOT_READY
            )

        current = self._store.read(proposal.operation_id)
        if (
            current is None
            or current.idempotency_key != proposal.idempotency_key
            or current.tenant_id != proposal.tenant_id
            or current.resource_id != proposal.resource_id
            or current.tool_name != proposal.tool_name
        ):
            return CapstoneCommitResult(CapstoneCommitOutcome.BINDING_CONFLICT)

        attempt_matches = (
            current.attempt_number == proposal.attempt_number
            and current.protocol_request_id == proposal.protocol_request_id
            and current.transport_generation == proposal.transport_generation
        )
        if not attempt_matches:
            return CapstoneCommitResult(CapstoneCommitOutcome.ATTEMPT_CONFLICT)

        if current.state is RetryDispatchRecordState.COMPLETED:
            if current.external_object_id == proposal.external_object_id:
                return CapstoneCommitResult(
                    CapstoneCommitOutcome.ALREADY_COMMITTED,
                    current,
                )
            return CapstoneCommitResult(CapstoneCommitOutcome.STATE_CONFLICT)
        if current.state is not expected_state:
            return CapstoneCommitResult(CapstoneCommitOutcome.STATE_CONFLICT)
        if current.version != expected_version:
            return CapstoneCommitResult(CapstoneCommitOutcome.VERSION_CONFLICT)
        if current.fence_token != expected_fence:
            return CapstoneCommitResult(CapstoneCommitOutcome.FENCE_CONFLICT)

        updated = self._store.compare_and_set_completed(
            operation_id=proposal.operation_id,
            idempotency_key=proposal.idempotency_key,
            tenant_id=proposal.tenant_id,
            resource_id=proposal.resource_id,
            tool_name=proposal.tool_name,
            attempt_number=proposal.attempt_number,
            protocol_request_id=proposal.protocol_request_id,
            transport_generation=proposal.transport_generation,
            expected_state=expected_state,
            expected_version=expected_version,
            expected_fence=expected_fence,
            external_object_id=proposal.external_object_id,
        )
        if updated is None:
            return CapstoneCommitResult(CapstoneCommitOutcome.CAS_CONFLICT)
        return CapstoneCommitResult(
            CapstoneCommitOutcome.COMMITTED,
            updated,
            durable_transition=True,
        )
