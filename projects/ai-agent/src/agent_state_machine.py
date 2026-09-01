"""Day81 Agent state, termination, loop and budget control boundary.

The module consumes Day79 control results and Day80 governance results, then
returns one deterministic candidate transition. Only the process-local store's
conditional apply may create a next Step. This classroom model is not durable
database, queue, Worker, tokenizer, billing, integration, or production proof.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import threading
from typing import Optional

from agent_loop import AgentStepResult, ControlDecision, NextStepRequest
from tool_governance import InvocationGovernanceStatus


class AgentState(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = frozenset(
    {
        AgentState.COMPLETED,
        AgentState.TERMINATED,
        AgentState.FAILED,
        AgentState.CANCELLED,
    }
)


class TransitionAction(str, Enum):
    CONTINUE = "CONTINUE"
    WAIT = "WAIT"
    RECONCILE = "RECONCILE"
    COMPLETE = "COMPLETE"
    TERMINATE = "TERMINATE"
    FAIL = "FAIL"
    NOOP = "NOOP"


class TerminationReason(str, Enum):
    GOAL_SATISFIED = "GOAL_SATISFIED"
    NO_PROGRESS_LOOP_DETECTED = "NO_PROGRESS_LOOP_DETECTED"
    STEP_BUDGET_EXHAUSTED = "STEP_BUDGET_EXHAUSTED"
    TOKEN_BUDGET_EXHAUSTED = "TOKEN_BUDGET_EXHAUSTED"
    COST_BUDGET_EXHAUSTED = "COST_BUDGET_EXHAUSTED"
    AUTHORIZATION_REVOKED = "AUTHORIZATION_REVOKED"
    NON_RECOVERABLE_FAILURE = "NON_RECOVERABLE_FAILURE"


class RecoveryAction(str, Enum):
    NONE = "NONE"
    RECONCILE_ORIGINAL_IDENTITY = "RECONCILE_ORIGINAL_IDENTITY"
    WAIT_FOR_PREREQUISITE = "WAIT_FOR_PREREQUISITE"
    WAIT_FOR_REPLAN = "WAIT_FOR_REPLAN"
    REPLAN_WITH_CURRENT_CAPABILITIES = "REPLAN_WITH_CURRENT_CAPABILITIES"


class TransitionApplyStatus(str, Enum):
    APPLIED = "APPLIED"
    DUPLICATE_REPLAY = "DUPLICATE_REPLAY"
    NOOP_TERMINAL = "NOOP_TERMINAL"
    NOOP_STALE = "NOOP_STALE"
    RESERVATION_CONFLICT = "RESERVATION_CONFLICT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class BudgetSnapshot:
    step_limit: int
    steps_used: int
    token_limit: int
    settled_tokens: int
    held_token_reservations: int
    cost_limit: int
    settled_cost: int
    held_cost_reservations: int

    def __post_init__(self) -> None:
        values = (
            self.step_limit,
            self.steps_used,
            self.token_limit,
            self.settled_tokens,
            self.held_token_reservations,
            self.cost_limit,
            self.settled_cost,
            self.held_cost_reservations,
        )
        if any(value < 0 for value in values):
            raise ValueError("budget values must be non-negative")

    @property
    def remaining_steps(self) -> int:
        return self.step_limit - self.steps_used

    @property
    def available_tokens(self) -> int:
        return (
            self.token_limit
            - self.settled_tokens
            - self.held_token_reservations
        )

    @property
    def available_cost(self) -> int:
        return (
            self.cost_limit
            - self.settled_cost
            - self.held_cost_reservations
        )


@dataclass(frozen=True)
class ContextBudget:
    input_tokens: int
    reserved_output_tokens: int
    safety_margin: int
    permitted_context_budget: int
    provider_context_limit: int

    def __post_init__(self) -> None:
        values = (
            self.input_tokens,
            self.reserved_output_tokens,
            self.safety_margin,
            self.permitted_context_budget,
            self.provider_context_limit,
        )
        if any(value < 0 for value in values):
            raise ValueError("context budget values must be non-negative")

    @property
    def required_capacity(self) -> int:
        return (
            self.input_tokens
            + self.reserved_output_tokens
            + self.safety_margin
        )

    @property
    def admitted(self) -> bool:
        return (
            self.required_capacity <= self.permitted_context_budget
            <= self.provider_context_limit
        )


@dataclass(frozen=True)
class ProgressSnapshot:
    state: AgentState
    remaining_goal_conditions: tuple[str, ...]
    verified_observation_ids: tuple[str, ...]
    action_fingerprint: str

    def __post_init__(self) -> None:
        if len(set(self.verified_observation_ids)) != len(
            self.verified_observation_ids
        ):
            raise ValueError("verified observation identities must be unique")
        if not self.action_fingerprint:
            raise ValueError("action fingerprint is required")

    @property
    def progress_fingerprint(self) -> str:
        material = "\x1f".join(
            (
                self.state.value,
                ",".join(sorted(self.remaining_goal_conditions)),
                ",".join(sorted(self.verified_observation_ids)),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


def no_progress_threshold_reached(
    history: tuple[ProgressSnapshot, ...], threshold: int
) -> bool:
    """Return true when a bounded trailing window has no verified progress."""

    if threshold < 2:
        raise ValueError("no-progress threshold must be at least two")
    if len(history) < threshold:
        return False
    window = history[-threshold:]
    return len({item.progress_fingerprint for item in window}) == 1


@dataclass(frozen=True)
class AgentTransitionInput:
    tenant_id: str
    job_id: str
    step_id: str
    attempt_id: str
    state: AgentState
    fence_token: int
    day79_result: AgentStepResult
    goal_verified: bool
    pending_reconciliation_identity: Optional[str]
    current_authorization: bool
    day80_governance: Optional[InvocationGovernanceStatus]
    hard_loop_detected: bool
    budget: BudgetSnapshot
    context_budget: ContextBudget
    requested_token_reservation: int
    requested_cost_reservation: int

    def __post_init__(self) -> None:
        if not all((self.tenant_id, self.job_id, self.step_id, self.attempt_id)):
            raise ValueError("tenant, Job, Step, and Attempt identities required")
        if self.fence_token < 0:
            raise ValueError("fence token must be non-negative")
        if self.requested_token_reservation < 0:
            raise ValueError("negative token reservation")
        if self.requested_cost_reservation < 0:
            raise ValueError("negative cost reservation")
        result_identity = (
            self.day79_result.tenant_id,
            self.day79_result.job_id,
            self.day79_result.step_id,
            self.day79_result.source_attempt_id,
        )
        if result_identity != (
            self.tenant_id,
            self.job_id,
            self.step_id,
            self.attempt_id,
        ):
            raise ValueError("Day79 result identity mismatch")


@dataclass(frozen=True)
class TransitionDecision:
    phase: str
    status: str
    transition_id: str
    tenant_id: str
    job_id: str
    step_id: str
    attempt_id: str
    expected_state: AgentState
    expected_fence_token: int
    action: TransitionAction
    proposed_next_state: AgentState
    termination_reason: Optional[TerminationReason]
    recovery_action: RecoveryAction
    next_step: Optional[NextStepRequest]
    requested_token_reservation: int
    requested_cost_reservation: int
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        if (self.action is TransitionAction.CONTINUE) != (
            self.next_step is not None
        ):
            raise ValueError("only CONTINUE carries a Day79 next Step")


def _transition_id(
    item: AgentTransitionInput,
    action: TransitionAction,
    status: str,
) -> str:
    material = "\x1f".join(
        (
            item.tenant_id,
            item.job_id,
            item.step_id,
            item.attempt_id,
            str(item.fence_token),
            item.day79_result.control_decision_id,
            action.value,
            status,
        )
    )
    return "transition-" + hashlib.sha256(
        material.encode("utf-8")
    ).hexdigest()[:20]


def _decision(
    item: AgentTransitionInput,
    *,
    action: TransitionAction,
    next_state: AgentState,
    status: str,
    termination_reason: Optional[TerminationReason] = None,
    recovery_action: RecoveryAction = RecoveryAction.NONE,
    next_step: Optional[NextStepRequest] = None,
    reserve: bool = False,
    evidence: tuple[str, ...] = (),
) -> TransitionDecision:
    return TransitionDecision(
        phase="PRE_NEXT_STEP_GUARD",
        status=status,
        transition_id=_transition_id(item, action, status),
        tenant_id=item.tenant_id,
        job_id=item.job_id,
        step_id=item.step_id,
        attempt_id=item.attempt_id,
        expected_state=item.state,
        expected_fence_token=item.fence_token,
        action=action,
        proposed_next_state=next_state,
        termination_reason=termination_reason,
        recovery_action=recovery_action,
        next_step=next_step,
        requested_token_reservation=(
            item.requested_token_reservation if reserve else 0
        ),
        requested_cost_reservation=(
            item.requested_cost_reservation if reserve else 0
        ),
        evidence=evidence,
    )


def decide_transition(item: AgentTransitionInput) -> TransitionDecision:
    """Return one deterministic candidate transition with zero side effects."""

    if item.state in TERMINAL_STATES:
        return _decision(
            item,
            action=TransitionAction.NOOP,
            next_state=item.state,
            status="ALREADY_TERMINAL",
            evidence=("terminal_history_preserved",),
        )

    if (
        item.pending_reconciliation_identity is not None
        or item.day79_result.decision is ControlDecision.RECONCILE
    ):
        return _decision(
            item,
            action=TransitionAction.RECONCILE,
            next_state=AgentState.PENDING_RECONCILIATION,
            status="EXTERNAL_OUTCOME_UNKNOWN",
            recovery_action=RecoveryAction.RECONCILE_ORIGINAL_IDENTITY,
            evidence=(
                item.pending_reconciliation_identity
                or item.day79_result.source_attempt_id,
                "reservation_must_remain_held",
            ),
        )

    if item.goal_verified:
        return _decision(
            item,
            action=TransitionAction.COMPLETE,
            next_state=AgentState.COMPLETED,
            status="GOAL_VERIFIED",
            termination_reason=TerminationReason.GOAL_SATISFIED,
            evidence=("verified_goal_evidence",),
        )

    if item.day79_result.decision is ControlDecision.WAIT:
        return _decision(
            item,
            action=TransitionAction.WAIT,
            next_state=AgentState.WAITING,
            status="KNOWN_PREREQUISITE_PENDING",
            recovery_action=RecoveryAction.WAIT_FOR_PREREQUISITE,
        )

    if item.day79_result.decision is ControlDecision.FAIL:
        return _decision(
            item,
            action=TransitionAction.FAIL,
            next_state=AgentState.FAILED,
            status="NON_RECOVERABLE_CONTROL_FAILURE",
            termination_reason=TerminationReason.NON_RECOVERABLE_FAILURE,
        )

    if item.hard_loop_detected:
        return _decision(
            item,
            action=TransitionAction.TERMINATE,
            next_state=AgentState.TERMINATED,
            status="HARD_LOOP_DETECTED",
            termination_reason=TerminationReason.NO_PROGRESS_LOOP_DETECTED,
            evidence=("no_progress_threshold_reached",),
        )

    if not item.current_authorization:
        return _decision(
            item,
            action=TransitionAction.TERMINATE,
            next_state=AgentState.TERMINATED,
            status="CURRENT_AUTHORIZATION_REVOKED",
            termination_reason=TerminationReason.AUTHORIZATION_REVOKED,
            evidence=("current_authorization_recheck_failed",),
        )

    governance = item.day80_governance
    if governance is not None and governance is not (
        InvocationGovernanceStatus.ALLOWED_TO_DAY74_ADMISSION
    ):
        if governance is InvocationGovernanceStatus.CURRENT_PERMISSION_REVOKED:
            return _decision(
                item,
                action=TransitionAction.TERMINATE,
                next_state=AgentState.TERMINATED,
                status="DAY80_CURRENT_PERMISSION_REVOKED",
                termination_reason=TerminationReason.AUTHORIZATION_REVOKED,
                evidence=(governance.value,),
            )
        return _decision(
            item,
            action=TransitionAction.WAIT,
            next_state=AgentState.WAITING,
            status="DAY80_GOVERNANCE_REPLAN_REQUIRED",
            recovery_action=RecoveryAction.REPLAN_WITH_CURRENT_CAPABILITIES,
            evidence=(governance.value, "old_binding_not_rewritten"),
        )

    if item.day79_result.decision is not ControlDecision.CONTINUE:
        return _decision(
            item,
            action=TransitionAction.FAIL,
            next_state=AgentState.FAILED,
            status="UNSUPPORTED_DAY79_DECISION",
            termination_reason=TerminationReason.NON_RECOVERABLE_FAILURE,
        )

    if item.budget.remaining_steps <= 0:
        return _decision(
            item,
            action=TransitionAction.TERMINATE,
            next_state=AgentState.TERMINATED,
            status="STEP_BUDGET_EXHAUSTED",
            termination_reason=TerminationReason.STEP_BUDGET_EXHAUSTED,
        )

    if not item.context_budget.admitted:
        return _decision(
            item,
            action=TransitionAction.WAIT,
            next_state=AgentState.WAITING,
            status="CONTEXT_BUDGET_EXCEEDED",
            recovery_action=RecoveryAction.WAIT_FOR_REPLAN,
            evidence=(
                f"required_capacity={item.context_budget.required_capacity}",
                "identity_authorization_and_evidence_must_be_preserved",
            ),
        )

    if item.requested_token_reservation > item.budget.available_tokens:
        return _decision(
            item,
            action=TransitionAction.TERMINATE,
            next_state=AgentState.TERMINATED,
            status="TOKEN_BUDGET_EXHAUSTED",
            termination_reason=TerminationReason.TOKEN_BUDGET_EXHAUSTED,
        )

    if item.requested_cost_reservation > item.budget.available_cost:
        return _decision(
            item,
            action=TransitionAction.TERMINATE,
            next_state=AgentState.TERMINATED,
            status="COST_BUDGET_EXHAUSTED",
            termination_reason=TerminationReason.COST_BUDGET_EXHAUSTED,
        )

    assert item.day79_result.next_step is not None
    return _decision(
        item,
        action=TransitionAction.CONTINUE,
        next_state=AgentState.RUNNING,
        status="NEXT_STEP_CANDIDATE",
        next_step=item.day79_result.next_step,
        reserve=True,
        evidence=("snapshot_guards_passed_candidate_only",),
    )


@dataclass
class AuthoritativeAgentRecord:
    tenant_id: str
    job_id: str
    current_step_id: str
    state: AgentState
    fence_token: int
    budget: BudgetSnapshot


class InMemoryAgentStateStore:
    """Process-local conditional apply; not durable Day82 evidence."""

    def __init__(self, record: AuthoritativeAgentRecord) -> None:
        self.record = record
        self._applied: dict[str, TransitionDecision] = {}
        self._lock = threading.RLock()

    def apply(self, decision: TransitionDecision) -> TransitionApplyStatus:
        with self._lock:
            current = self.record
            if decision.transition_id in self._applied:
                return TransitionApplyStatus.DUPLICATE_REPLAY
            if (
                current.tenant_id != decision.tenant_id
                or current.job_id != decision.job_id
            ):
                return TransitionApplyStatus.NOOP_STALE
            if current.state in TERMINAL_STATES:
                return TransitionApplyStatus.NOOP_TERMINAL
            if (
                current.state is not decision.expected_state
                or current.current_step_id != decision.step_id
                or current.fence_token != decision.expected_fence_token
            ):
                return TransitionApplyStatus.NOOP_STALE

            if decision.action is TransitionAction.CONTINUE:
                budget = current.budget
                if (
                    budget.remaining_steps <= 0
                    or decision.requested_token_reservation
                    > budget.available_tokens
                    or decision.requested_cost_reservation
                    > budget.available_cost
                ):
                    return TransitionApplyStatus.RESERVATION_CONFLICT
                assert decision.next_step is not None
                budget = replace(
                    budget,
                    steps_used=budget.steps_used + 1,
                    held_token_reservations=(
                        budget.held_token_reservations
                        + decision.requested_token_reservation
                    ),
                    held_cost_reservations=(
                        budget.held_cost_reservations
                        + decision.requested_cost_reservation
                    ),
                )
                self.record = replace(
                    current,
                    current_step_id=decision.next_step.step_id,
                    state=decision.proposed_next_state,
                    fence_token=current.fence_token + 1,
                    budget=budget,
                )
                self._applied[decision.transition_id] = decision
                return TransitionApplyStatus.APPLIED

            if decision.action in {
                TransitionAction.WAIT,
                TransitionAction.RECONCILE,
                TransitionAction.COMPLETE,
                TransitionAction.TERMINATE,
                TransitionAction.FAIL,
            }:
                self.record = replace(
                    current,
                    state=decision.proposed_next_state,
                    fence_token=current.fence_token + 1,
                )
                self._applied[decision.transition_id] = decision
                return TransitionApplyStatus.APPLIED

            return TransitionApplyStatus.NOT_APPLICABLE
