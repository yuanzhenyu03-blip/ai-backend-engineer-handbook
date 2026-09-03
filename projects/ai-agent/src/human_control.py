"""Day83 human control: pure candidates + one process-local apply boundary.

CurrentFacts and Principal are trusted application inputs, NOT callback claims.
No authentication service, database, broker, worker process or Provider is used.
The immutable Snapshot is swapped once under an RLock. This is local atomicity,
not durable PostgreSQL proof. Day82 records/recovery/accounting are composed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
import hashlib
import json
import threading
from typing import Callable

from agent_state_machine import AgentState, TERMINAL_STATES
from durable_agent_jobs import (
    DurableAgentJobRecord, DurableCheckpoint, DurableRecoveryCandidate,
    DurableRecoveryDecision, ExternalCertainty, InMemoryDurableAgentJobStore,
    OutboxIntent, RecoveryApplyStatus, RecoveryOperation, RecoveryRequest,
    ReservationAction, ReservationStatus, decide_durable_recovery,
)
from tool_governance import InvocationGovernanceStatus


class ApprovalStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"
    CONFLICT = "CONFLICT"


class Risk(str, Enum):
    LOW = "LOW"
    HIGH = "HIGH"


class Operation(str, Enum):
    DECISION = "DECISION"
    GATE = "GATE"
    INTERRUPT = "INTERRUPT"
    OBSERVE_CANCEL = "OBSERVE_CANCEL"
    RECOVER = "RECOVER"
    LATE_RESULT = "LATE_RESULT"
    INVALIDATE = "INVALIDATE"


def fingerprint(value: object) -> str:
    """Canonical JSON hash; rejects NaN; never emits the input payload."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    actor_id: str
    role: str
    authenticated: bool
    permissions: tuple[str, ...]


@dataclass(frozen=True)
class ActionBinding:
    tenant_id: str
    job_id: str
    step_id: str
    attempt_id: str
    operation_id: str
    action_type: str
    tool_name: str
    tool_version: str
    arguments_fingerprint: str
    artifact_id: str
    artifact_version: str
    requester_id: str
    policy_id: str
    policy_version: str
    risk: Risk
    execution_binding_fingerprint: str

    @property
    def digest(self) -> str:
        return fingerprint(asdict(self))


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    binding: ActionBinding
    requested_at: int
    respond_by: int
    expires_at: int
    eligible_roles: tuple[str, ...]
    separation_required: bool
    issued_state_version: int
    issued_fence: int
    supersedes: str | None = None


@dataclass(frozen=True)
class ApprovalDecision:
    decision_id: str
    request_id: str
    binding_fingerprint: str
    actor_id: str
    tenant_id: str
    choice: ApprovalStatus
    decided_at: int
    reason_code: str

    @property
    def digest(self) -> str:
        return fingerprint(asdict(self))


@dataclass(frozen=True)
class CurrentFacts:
    """Injected trusted facts; caller must enforce real authz outside this model."""
    executor: Principal
    approver: Principal
    policy_available: bool
    policy_id: str
    policy_version: str
    policy_quarantined: bool
    approval_required: bool
    governance: InvocationGovernanceStatus
    admission_allowed: bool
    business_valid: bool
    budget_allowed: bool
    certainty: ExternalCertainty
    recovery: RecoveryOperation
    policy_wait_deadline: int
    owner: Principal
    fallback_owner: Principal
    owner_available: bool
    escalation_deadline: int
    verified_usage: int | None = None
    outcome_evidence_id: str | None = None


@dataclass(frozen=True)
class Command:
    command_id: str
    operation: Operation
    actor: Principal
    expected_state: AgentState
    expected_state_version: int
    expected_fence: int
    decision: ApprovalDecision | None = None
    invalidate_to: ApprovalStatus | None = None
    evidence_id: str | None = None
    source_attempt_id: str | None = None
    source_operation_id: str | None = None
    source_fence: int | None = None


@dataclass(frozen=True)
class Escalation:
    escalation_id: str
    tenant_id: str
    attempt_id: str
    operation_id: str
    owner_id: str | None
    reason: str
    priority: str
    deadline: int
    alert_status: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class Snapshot:
    job: DurableAgentJobRecord
    action: ActionBinding
    request: ApprovalRequest
    approval: ApprovalStatus = ApprovalStatus.PENDING
    decisions: tuple[ApprovalDecision, ...] = ()
    decision_evidence: tuple[ApprovalDecision, ...] = ()
    interrupt_id: str | None = None
    cancellation_observed_by: tuple[str, ...] = ()
    dispatch_started: bool = False
    claimed_events: tuple[str, ...] = ()
    escalations: tuple[Escalation, ...] = ()
    checkpoint_history: tuple[DurableCheckpoint, ...] = ()

    @property
    def digest(self) -> str:
        return fingerprint(asdict(self))


@dataclass(frozen=True)
class HumanControlCandidate:
    phase: str
    snapshot_fingerprint: str
    command: Command
    status: str
    next_state: AgentState
    approval_status: ApprovalStatus
    execution_allowed: bool
    reservation_action: ReservationAction
    outbox_action: str
    follow_up: str
    authorization_result: bool
    separation_result: bool
    evidence: tuple[str, ...]
    escalation: Escalation | None = None
    recovery_candidate: DurableRecoveryCandidate | None = None


def _permitted(principal: Principal, tenant: str, permission: str) -> bool:
    return (principal.authenticated is True and principal.tenant_id == tenant
            and permission in principal.permissions)


def decide_human_control(
    snapshot: Snapshot, command: Command, facts: CurrentFacts, now: int,
) -> HumanControlCandidate:
    """Zero side effects. APPROVED is only one guard, not a dispatch permit."""
    job, action, request = snapshot.job, snapshot.action, snapshot.request
    authz = (_permitted(facts.executor, action.tenant_id, action.action_type)
             and facts.executor.actor_id == action.requester_id)
    sod = (not request.separation_required
           or facts.approver.actor_id != action.requester_id)

    def result(
        status: str, *, state: AgentState | None = None,
        approval: ApprovalStatus | None = None, allowed: bool = False,
        reservation: ReservationAction = ReservationAction.NO_CHANGE,
        outbox: str = "NONE", follow_up: str = "NONE",
        evidence: tuple[str, ...] = (), escalation: Escalation | None = None,
        recovery: DurableRecoveryCandidate | None = None,
    ) -> HumanControlCandidate:
        return HumanControlCandidate(
            "HUMAN_CONTROL", snapshot.digest, command, status,
            state or job.state, approval or snapshot.approval, allowed,
            reservation, outbox, follow_up, authz, sod, evidence,
            escalation, recovery,
        )

    def escalate(reason: str, *, state: AgentState | None = None,
                 approval: ApprovalStatus | None = None,
                 recovery: DurableRecoveryCandidate | None = None,
                 reservation: ReservationAction | None = None,
                 evidence: tuple[str, ...] = ()) -> HumanControlCandidate:
        owner = facts.owner if facts.owner_available else facts.fallback_owner
        owner_ok = _permitted(owner, action.tenant_id, "operate")
        if facts.escalation_deadline <= now:
            return result("INVALID_ESCALATION_DEADLINE")
        extra = () if facts.owner_available else ("OWNER_UNAVAILABLE",)
        record = Escalation(
            "escalation:" + command.command_id, action.tenant_id,
            action.attempt_id, action.operation_id,
            owner.actor_id if owner_ok else None, reason, "HIGH",
            facts.escalation_deadline,
            "PENDING" if owner_ok else "UNROUTABLE", evidence + extra,
        )
        unknown = facts.certainty is ExternalCertainty.OUTCOME_UNKNOWN
        reserve = reservation or (ReservationAction.KEEP_HELD if unknown
                                  else ReservationAction.NO_CHANGE)
        return result(
            "ESCALATE_" + reason, state=state, approval=approval,
            reservation=reserve, outbox="ESCALATION_ALERT",
            follow_up="OPERATOR_REVIEW", evidence=evidence + extra,
            escalation=record, recovery=recovery,
        )

    # Unknown enum values and non-boolean guard inputs must never fall through.
    enum_values = ((command.operation, Operation), (job.state, AgentState),
                   (snapshot.approval, ApprovalStatus), (action.risk, Risk),
                   (facts.certainty, ExternalCertainty),
                   (facts.governance, InvocationGovernanceStatus))
    bool_values = (facts.policy_available, facts.policy_quarantined,
                   facts.approval_required, facts.admission_allowed,
                   facts.business_valid, facts.budget_allowed,
                   facts.owner_available, request.separation_required)
    if (any(not isinstance(value, kind) for value, kind in enum_values)
            or any(type(value) is not bool for value in bool_values)):
        return result("INVALID_FACTS", evidence=("fail_closed",))
    if (not command.command_id or type(now) is not int or now < 0
            or not request.request_id
            or not 0 <= request.requested_at <= request.respond_by
            <= request.expires_at
            or not all(isinstance(v, str) and v for v in asdict(action).values())):
        return result("INVALID_FACTS", evidence=("fail_closed",))
    if not _permitted(command.actor, action.tenant_id, "control"):
        return result("CONTROL_NOT_AUTHORIZED")
    if ((job.tenant_id, job.job_id, job.current_step_id, job.current_attempt_id)
            != (action.tenant_id, action.job_id, action.step_id, action.attempt_id)
            or action.execution_binding_fingerprint
            != fingerprint(asdict(job.current_checkpoint.bindings))):
        return result("EXECUTION_BINDING_MISMATCH")

    # Evidence collection is separate from old Worker write authority.
    if command.operation is Operation.LATE_RESULT:
        if (not command.evidence_id
                or command.source_attempt_id != action.attempt_id
                or command.source_operation_id != action.operation_id):
            return result("RESULT_IDENTITY_MISMATCH")
        stale = (command.source_fence != job.fence_token
                 or command.actor.actor_id != job.lease_owner
                 or job.state in TERMINAL_STATES)
        return result("STALE_RESULT_EVIDENCE" if stale else "RESULT_EVIDENCE",
                      evidence=("original_identity_evidence", command.evidence_id),
                      follow_up="VERIFY_ORIGINAL_RESULT")

    # Callback identity is immutable, independently of current lifecycle version.
    if command.operation is Operation.DECISION:
        decision = command.decision
        if (decision is None or not decision.decision_id
                or decision.choice not in {ApprovalStatus.APPROVED,
                                           ApprovalStatus.REJECTED}
                or not isinstance(decision.choice, ApprovalStatus)):
            return result("INVALID_DECISION")
        if (not _permitted(command.actor, action.tenant_id, "approve")
                or command.actor.actor_id != decision.actor_id
                or command.actor.tenant_id != decision.tenant_id
                or command.actor != facts.approver):
            return result("APPROVER_NOT_AUTHORIZED")
        previous = next((d for d in snapshot.decisions
                         if d.decision_id == decision.decision_id), None)
        if previous is not None:
            if previous == decision:
                return result("DUPLICATE_DECISION",
                              evidence=("duplicate_no_business_effect",))
            return escalate("DECISION_IDENTITY_CONFLICT",
                            approval=ApprovalStatus.CONFLICT,
                            evidence=(previous.digest, decision.digest))

    if ((command.expected_state, command.expected_state_version,
         command.expected_fence)
            != (job.state, job.state_version, job.fence_token)):
        return result("STALE_CANDIDATE", evidence=("reload_current_facts",))

    if command.operation is Operation.RECOVER:
        prior_recoveries = tuple(r for r in job.recovery_operations
                                 if r.source_attempt_id == action.attempt_id)
        recovery = prior_recoveries[-1] if prior_recoveries else facts.recovery
        if (not _permitted(command.actor, action.tenant_id, "operate")
                or recovery.source_attempt_id != action.attempt_id
                or recovery.attempts_used < 0 or recovery.attempt_limit < 1):
            return result("RECOVERY_NOT_AUTHORIZED")
        if (facts.verified_usage is not None
                and (facts.certainty is not ExternalCertainty.VERIFIED_TERMINAL
                     or not facts.outcome_evidence_id)):
            return result("USAGE_EVIDENCE_REQUIRED")
        if facts.verified_usage is not None:
            reservations = tuple(r for r in job.reservations
                                 if r.attempt_id == action.attempt_id)
            if (len(reservations) != 1 or type(facts.verified_usage) is not int
                    or not 0 <= facts.verified_usage <= reservations[0].reserved_units):
                return result("INVALID_VERIFIED_USAGE")
            reservation = reservations[0]
            if reservation.status is ReservationStatus.SETTLED:
                if reservation.settled_units == facts.verified_usage:
                    return result("SETTLEMENT_ALREADY_RECORDED")
                return escalate("SETTLEMENT_CONFLICT",
                                evidence=("settled_usage_not_rewritten",))
            if reservation.status is not ReservationStatus.HELD:
                return escalate("SETTLEMENT_RESERVATION_CONFLICT")
            # A verified accounting operation is not another automatic query.
            # Give this distinct operation its own one-step authorization
            # window; preserve the exhausted QUERY counter in apply/history.
            recovery = RecoveryOperation(
                "settlement:" + command.command_id, action.attempt_id,
                recovery.recovery_generation, 0, 1, now + 1,
                facts.outcome_evidence_id,
            )
        if facts.certainty is ExternalCertainty.DEFINITELY_NOT_DISPATCHED:
            return result("NO_EXTERNAL_OPERATION_TO_RECONCILE")
        recovery_request = RecoveryRequest(
            command.command_id, action.tenant_id, action.job_id, action.step_id,
            action.attempt_id, job.current_checkpoint.checkpoint_id,
            job.state, job.state_version, job.fence_token, now, facts.certainty,
            authz, not facts.policy_quarantined,
            verified_usage_units=facts.verified_usage,
        )
        candidate = decide_durable_recovery(job, recovery, recovery_request)
        if candidate.decision is DurableRecoveryDecision.ESCALATE:
            return escalate("BOUNDED_RECOVERY_EXHAUSTED",
                            state=candidate.next_state, recovery=candidate,
                            evidence=("original_identity_preserved",))
        if candidate.decision is DurableRecoveryDecision.RECONCILE:
            return result("RECONCILE", state=candidate.next_state,
                          reservation=ReservationAction.KEEP_HELD,
                          outbox="RECONCILIATION_QUERY",
                          follow_up="RECONCILE_ORIGINAL_OPERATION",
                          evidence=("original_identity_preserved",),
                          recovery=candidate)
        if candidate.decision is DurableRecoveryDecision.SETTLE:
            return result("SETTLE", reservation=ReservationAction.SETTLE_VERIFIED,
                          evidence=("verified_usage",), recovery=candidate)
        return result("RECOVERY_NO_NEW_BUSINESS_EXECUTION")

    if command.operation is Operation.OBSERVE_CANCEL:
        if not snapshot.interrupt_id:
            return result("NO_CANCELLATION_REQUEST")
        return result("CANCELLATION_OBSERVED",
                      evidence=("worker_observed_not_external_absence",))

    if command.operation is Operation.INTERRUPT:
        if not _permitted(command.actor, action.tenant_id, "interrupt"):
            return result("INTERRUPT_NOT_AUTHORIZED")
        if snapshot.interrupt_id:
            return result("DUPLICATE_INTERRUPT")
        definitely_unused = (not snapshot.dispatch_started and facts.certainty
                             is ExternalCertainty.DEFINITELY_NOT_DISPATCHED)
        state = job.state if job.state in TERMINAL_STATES else (
            AgentState.CANCELLED if definitely_unused
            else AgentState.PENDING_RECONCILIATION)
        return result(
            "INTERRUPTED_PRE_DISPATCH" if definitely_unused
            else "INTERRUPTED_POST_DISPATCH", state=state,
            reservation=(ReservationAction.RELEASE if definitely_unused
                         else ReservationAction.KEEP_HELD),
            follow_up=("NONE" if definitely_unused
                       else "CANCELLATION_REQUEST_AND_RECONCILIATION"),
            evidence=("interrupt_is_not_external_absence",),
        )

    if command.operation is Operation.INVALIDATE:
        if (not _permitted(command.actor, action.tenant_id, "operate")
                or not isinstance(command.invalidate_to, ApprovalStatus)
                or command.invalidate_to not in {
                    ApprovalStatus.REVOKED, ApprovalStatus.SUPERSEDED,
                    ApprovalStatus.CANCELLED}):
            return result("INVALID_LIFECYCLE_CHANGE")
        return result("APPROVAL_" + command.invalidate_to.value,
                      approval=command.invalidate_to,
                      evidence=("approval_history_preserved",))

    if job.state in TERMINAL_STATES:
        return result("TERMINAL_NOOP", evidence=("terminal_not_reopened",))
    if snapshot.interrupt_id:
        return result("INTERRUPT_BLOCKED")
    if snapshot.approval in {
        ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED, ApprovalStatus.REVOKED,
        ApprovalStatus.SUPERSEDED, ApprovalStatus.CANCELLED,
        ApprovalStatus.CONFLICT,
    }:
        return result("APPROVAL_" + snapshot.approval.value)
    if request.binding != action:
        return result("APPROVAL_BINDING_MISMATCH",
                      evidence=("new_request_required",))
    if now >= request.expires_at and facts.approval_required:
        return result("APPROVAL_EXPIRED", approval=ApprovalStatus.EXPIRED,
                      evidence=("no_silent_renewal",))
    if facts.policy_quarantined:
        return result("POLICY_QUARANTINED", evidence=("old_binding_preserved",))
    if not facts.policy_available:
        if now >= facts.policy_wait_deadline:
            return escalate("APPROVAL_POLICY_UNAVAILABLE",
                            state=AgentState.WAITING,
                            evidence=("POLICY_WAIT_DEADLINE_EXCEEDED",))
        return result("POLICY_UNAVAILABLE", state=AgentState.WAITING)
    if (facts.policy_id, facts.policy_version) != (
            action.policy_id, action.policy_version):
        return result("POLICY_BINDING_MISMATCH")
    if action.risk is Risk.HIGH and not facts.approval_required:
        return result("RISK_POLICY_CONFLICT")

    if command.operation is Operation.DECISION:
        decision = command.decision
        assert decision is not None
        if (decision.request_id != request.request_id
                or decision.binding_fingerprint != action.digest):
            return result("DECISION_BINDING_MISMATCH")
        if (not request.requested_at <= decision.decided_at <= now
                or decision.decided_at >= request.expires_at):
            return result("DECISION_TIME_INVALID")
        if command.actor.role not in request.eligible_roles or not sod:
            return result("APPROVER_POLICY_REJECTED")
        if snapshot.decisions:
            return escalate("CONFLICTING_HUMAN_DECISION",
                            approval=ApprovalStatus.CONFLICT,
                            evidence=("original_decision_preserved",))
        return result("DECISION_RECORDED", approval=decision.choice,
                      evidence=("human_decision_not_dispatch",))

    # Execution and human approval authorization remain separate.
    if not authz:
        unused = (not snapshot.dispatch_started and facts.certainty
                  is ExternalCertainty.DEFINITELY_NOT_DISPATCHED)
        return result("AUTHORIZATION_REVOKED",
                      reservation=(ReservationAction.RELEASE if unused
                                   else ReservationAction.KEEP_HELD))
    if facts.governance is not (
            InvocationGovernanceStatus.ALLOWED_TO_DAY74_ADMISSION):
        return result("TOOL_GOVERNANCE_BLOCKED")
    if not facts.business_valid:
        return result("BUSINESS_VALIDATION_FAILED")
    if not facts.admission_allowed:
        return result("TOOL_ADMISSION_BLOCKED")
    if not facts.budget_allowed:
        return result("BUDGET_BLOCKED")
    if snapshot.dispatch_started:
        return result("ALREADY_DISPATCH_CLAIMED")
    if facts.certainty is not ExternalCertainty.DEFINITELY_NOT_DISPATCHED:
        return result("EXTERNAL_OPERATION_ALREADY_POSSIBLE")
    if not any(r.attempt_id == action.attempt_id
               and r.status is ReservationStatus.HELD
               for r in job.reservations):
        return result("RESERVATION_NOT_HELD")
    if facts.approval_required:
        if snapshot.approval is not ApprovalStatus.APPROVED:
            if now >= request.respond_by:
                return escalate("APPROVAL_OVERDUE", state=AgentState.WAITING)
            return result("APPROVAL_PENDING", state=AgentState.WAITING,
                          outbox="APPROVAL_REQUEST")
        if not snapshot.decisions:
            return result("APPROVAL_EVIDENCE_MISSING")
        approved = snapshot.decisions[0]
        if (approved.choice is not ApprovalStatus.APPROVED
                or approved.binding_fingerprint != action.digest
                or approved.request_id != request.request_id
                or approved.actor_id != facts.approver.actor_id
                or not _permitted(facts.approver, action.tenant_id, "approve")
                or facts.approver.role not in request.eligible_roles or not sod):
            return result("CURRENT_APPROVER_INVALID")
    return result("EXECUTION_CANDIDATE", state=AgentState.RUNNING,
                  approval=(snapshot.approval if facts.approval_required
                            else ApprovalStatus.NOT_REQUIRED),
                  allowed=True, outbox="PUBLISH",
                  evidence=("current_guards_passed_candidate_only",))


class InMemoryHumanControlStore:
    """Only local control authority. External calls are NEVER made by apply."""

    def __init__(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot
        self._lock = threading.RLock()
        self._commands: dict[str, Command] = {}

    def plan(self, command: Command, facts: CurrentFacts,
             now: int) -> HumanControlCandidate:
        with self._lock:
            return decide_human_control(self.snapshot, command, facts, now)

    def apply(self, candidate: HumanControlCandidate, facts: CurrentFacts,
              now: int, *, fail_before_commit: bool = False) -> str:
        with self._lock:
            previous = self._commands.get(candidate.command.command_id)
            if previous is not None:
                return "DUPLICATE_COMMAND" if previous == candidate.command else (
                    "COMMAND_IDENTITY_CONFLICT")
            current = self.snapshot
            if candidate.snapshot_fingerprint != current.digest:
                return "STALE_CANDIDATE"
            fresh = decide_human_control(current, candidate.command, facts, now)
            if fresh != candidate:
                return "CURRENT_FACTS_CHANGED"
            job = current.job
            # Rejected/duplicate/stale messages may add evidence but cannot
            # advance business versions, checkpoint, reservations or outbox.
            transitions = {
                "DECISION_RECORDED", "EXECUTION_CANDIDATE", "APPROVAL_PENDING",
                "APPROVAL_EXPIRED", "APPROVAL_REVOKED", "APPROVAL_CANCELLED",
                "APPROVAL_SUPERSEDED", "POLICY_UNAVAILABLE", "RECONCILE",
                "SETTLE", "CANCELLATION_OBSERVED", "AUTHORIZATION_REVOKED",
            }
            if (candidate.command.operation is not Operation.INVALIDATE
                    and candidate.status in {"APPROVAL_REVOKED",
                                             "APPROVAL_CANCELLED",
                                             "APPROVAL_SUPERSEDED"}):
                transitions.discard(candidate.status)
            if (candidate.status not in transitions
                    and not candidate.status.startswith("ESCALATE_")
                    and not candidate.status.startswith("INTERRUPTED_")):
                if fail_before_commit:
                    raise RuntimeError("INJECTED_BEFORE_COMMIT")
                evidence = current.decision_evidence
                if candidate.command.decision is not None:
                    evidence += (candidate.command.decision,)
                self.snapshot = replace(
                    current, decision_evidence=evidence,
                    job=replace(job, audit_events=job.audit_events
                                + (candidate.status,) + candidate.evidence),
                )
                self._commands[candidate.command.command_id] = candidate.command
                return "AUDIT_ONLY"
            next_job = job
            if candidate.recovery_candidate is not None:
                # Stage Day82 apply on an isolated local value, then commit the
                # whole human-control aggregate with a single snapshot swap.
                staged = InMemoryDurableAgentJobStore(job)
                if staged.apply(candidate.recovery_candidate) is not (
                        RecoveryApplyStatus.APPLIED):
                    return "RECOVERY_APPLY_REJECTED"
                next_job = staged.record
                previous_recoveries = tuple(
                    r for r in job.recovery_operations
                    if r.source_attempt_id == current.action.attempt_id)
                control = (previous_recoveries[-1] if previous_recoveries
                           else facts.recovery)
                recorded_recovery = replace(
                    control, recovery_id=candidate.command.command_id,
                    attempts_used=control.attempts_used
                    + (1 if candidate.status == "RECONCILE" else 0),
                    last_evidence_fingerprint=fingerprint(candidate.evidence),
                )
                next_job = replace(next_job, recovery_operations=
                                   job.recovery_operations + (recorded_recovery,))
                # Day83 owns routing to query vs human alert for this operation.
                next_job = replace(next_job, outbox_intents=job.outbox_intents)
            reservations = next_job.reservations
            if candidate.reservation_action is ReservationAction.RELEASE:
                if current.dispatch_started or facts.certainty is not (
                        ExternalCertainty.DEFINITELY_NOT_DISPATCHED):
                    return "UNSAFE_RELEASE_REJECTED"
                reservations = tuple(
                    replace(r, status=ReservationStatus.RELEASED,
                            released_units=r.reserved_units)
                    if r.attempt_id == current.action.attempt_id
                    and r.status is ReservationStatus.HELD else r
                    for r in reservations)
            events = next_job.outbox_intents
            if candidate.outbox_action != "NONE":
                event_id = fingerprint([
                    current.action.digest, current.request.request_id,
                    candidate.outbox_action,
                    candidate.command.command_id if candidate.escalation
                    or candidate.outbox_action == "RECONCILIATION_QUERY" else "",
                ])
                if not any(e.event_id == event_id for e in events):
                    events += (OutboxIntent(
                        event_id, job.job_id, job.current_step_id,
                        job.current_attempt_id, candidate.outbox_action),)
            interrupting = candidate.status.startswith("INTERRUPTED_")
            version = job.state_version + 1
            fence = job.fence_token + (1 if interrupting else 0)
            if candidate.recovery_candidate:
                fence = next_job.fence_token
            checkpoint = replace(
                next_job.current_checkpoint,
                checkpoint_id="human:" + candidate.command.command_id,
                checkpoint_version=job.current_checkpoint.checkpoint_version + 1,
                authoritative_state=candidate.next_state,
                state_version=version, fence_token=fence,
                previous_checkpoint_id=job.current_checkpoint.checkpoint_id,
            )
            next_job = replace(
                next_job, state=candidate.next_state, state_version=version,
                fence_token=fence, current_checkpoint=checkpoint,
                lease_owner=None if interrupting else next_job.lease_owner,
                lease_expiry_epoch_ms=(None if interrupting
                                       else next_job.lease_expiry_epoch_ms),
                reservations=reservations, outbox_intents=events,
                audit_events=next_job.audit_events + (candidate.status,)
                + candidate.evidence,
            )
            decisions = current.decisions
            evidence = current.decision_evidence
            if candidate.command.decision is not None:
                evidence += (candidate.command.decision,)
                if candidate.status == "DECISION_RECORDED":
                    decisions += (candidate.command.decision,)
            escalations = current.escalations
            if candidate.escalation:
                escalations += (candidate.escalation,)
            observed = current.cancellation_observed_by
            if candidate.status == "CANCELLATION_OBSERVED":
                observed += (candidate.command.actor.actor_id,)
            if fail_before_commit:
                raise RuntimeError("INJECTED_BEFORE_COMMIT")
            self.snapshot = replace(
                current, job=next_job, approval=candidate.approval_status,
                decisions=decisions, decision_evidence=evidence,
                interrupt_id=(candidate.command.command_id if interrupting
                              else current.interrupt_id),
                cancellation_observed_by=observed, escalations=escalations,
                checkpoint_history=current.checkpoint_history
                + (job.current_checkpoint,),
            )
            self._commands[candidate.command.command_id] = candidate.command
            return "APPLIED"

    def dispatch_once(
        self, event_id: str, worker: Principal, expected_fence: int,
        facts: CurrentFacts, now: int, effect: Callable[[ActionBinding], object],
    ) -> bool:
        """Local claim + current recheck. effect is a trusted injected local port.

        The claim marks possible dispatch BEFORE the port call. An interrupt
        after claim is conservative post-dispatch/unknown. There is no claim of
        a distributed check-and-send transaction or guaranteed remote cancel.
        """
        with self._lock:
            s = self.snapshot
            event = next((e for e in s.job.outbox_intents
                          if e.event_id == event_id and e.event_type == "PUBLISH"),
                         None)
            if (event is None or event_id in s.claimed_events
                    or expected_fence != s.job.fence_token
                    or worker.actor_id != s.job.lease_owner
                    or s.job.lease_expiry_epoch_ms is None
                    or now >= s.job.lease_expiry_epoch_ms):
                return False
            command = Command("dispatch:" + event_id, Operation.GATE, worker,
                              s.job.state, s.job.state_version, expected_fence)
            check = decide_human_control(s, command, facts, now)
            if not check.execution_allowed:
                return False
            cp = replace(s.job.current_checkpoint,
                         checkpoint_id="dispatch:" + event_id,
                         checkpoint_version=s.job.current_checkpoint.checkpoint_version + 1,
                         state_version=s.job.state_version + 1,
                         previous_checkpoint_id=s.job.current_checkpoint.checkpoint_id)
            self.snapshot = replace(
                s, dispatch_started=True, claimed_events=s.claimed_events + (event_id,),
                checkpoint_history=s.checkpoint_history + (s.job.current_checkpoint,),
                job=replace(s.job, state_version=s.job.state_version + 1,
                            current_checkpoint=cp,
                            audit_events=s.job.audit_events + ("DISPATCH_CLAIMED",)),
            )
        effect(s.action)
        return True
