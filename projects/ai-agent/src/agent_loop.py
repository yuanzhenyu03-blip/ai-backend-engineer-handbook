"""Day79 framework-agnostic Agent Loop control boundary.

This module owns deterministic control decisions and step identity while
delegating one constrained LLM application execution to the existing Day78
Runtime boundary. Its store is an in-process classroom model, not durable
database, queue, Worker, integration-runtime, or production evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import Iterable, Optional, Protocol

from application_runtime import (
    PreparedAttempt,
    ResolvedExecutionRequirements,
    RuntimeResult,
    RuntimeStatus,
    build_bound_application_request,
    prepare_runtime_attempt,
)
from prompt_contracts import PromptContractRegistry
from provider_contract import ApplicationRequest
from routing_policy import Candidate, RoutingPolicy


class ControlDecision(str, Enum):
    CONTINUE = "CONTINUE"
    COMPLETE = "COMPLETE"
    WAIT = "WAIT"
    FAIL = "FAIL"
    RECONCILE = "RECONCILE"


class ControlApplyStatus(str, Enum):
    CREATED = "CREATED"
    DUPLICATE_REPLAY = "DUPLICATE_REPLAY"
    NOOP_STALE = "NOOP_STALE"
    NOOP_TERMINAL = "NOOP_TERMINAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class AgentStepInput:
    tenant_id: str
    job_id: str
    current_step_id: str
    runtime_attempt_id: str
    goal_required_observations: int
    verified_observation_ids: tuple[str, ...]
    job_is_terminal: bool = False
    runtime_result: Optional[RuntimeResult] = None
    pending_reconciliation_identity: Optional[str] = None
    waiting_for: Optional[str] = None
    model_proposal: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.job_id or not self.current_step_id:
            raise ValueError(
                "tenant_id, job_id, and current_step_id are required"
            )
        if not self.runtime_attempt_id:
            raise ValueError("runtime_attempt_id is required")
        if self.goal_required_observations < 1:
            raise ValueError("goal_required_observations must be positive")
        if len(set(self.verified_observation_ids)) != len(
            self.verified_observation_ids
        ):
            raise ValueError("verified observation identities must be unique")
        if self.runtime_result is not None and (
            self.runtime_result.job_id != self.job_id
            or self.runtime_result.attempt_id != self.runtime_attempt_id
        ):
            raise ValueError("RuntimeResult identity does not match Agent step")


@dataclass(frozen=True)
class NextStepRequest:
    tenant_id: str
    job_id: str
    step_id: str
    parent_step_id: str
    runtime_attempt_id: str
    control_decision_id: str
    verified_observation_ids: tuple[str, ...]


@dataclass(frozen=True)
class AgentStepResult:
    tenant_id: str
    job_id: str
    step_id: str
    source_attempt_id: str
    control_decision_id: str
    decision: ControlDecision
    reason: str
    next_step: Optional[NextStepRequest] = None

    def __post_init__(self) -> None:
        if not self.reason or not self.control_decision_id:
            raise ValueError("reason and control_decision_id are required")
        if (self.decision is ControlDecision.CONTINUE) != (
            self.next_step is not None
        ):
            raise ValueError("only CONTINUE must carry exactly one next step")


def _stable_id(prefix: str, *parts: str) -> str:
    material = "\x1f".join(parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def _result(
    step: AgentStepInput,
    decision: ControlDecision,
    reason: str,
) -> AgentStepResult:
    observation_material = ",".join(step.verified_observation_ids)
    decision_id = _stable_id(
        "decision",
        step.tenant_id,
        step.job_id,
        step.current_step_id,
        step.runtime_attempt_id,
        decision.value,
        reason,
        observation_material,
    )
    next_step = None
    if decision is ControlDecision.CONTINUE:
        next_step_id = _stable_id(
            "step", step.job_id, step.current_step_id, decision_id
        )
        next_attempt_id = _stable_id("attempt", step.job_id, next_step_id)
        next_step = NextStepRequest(
            tenant_id=step.tenant_id,
            job_id=step.job_id,
            step_id=next_step_id,
            parent_step_id=step.current_step_id,
            runtime_attempt_id=next_attempt_id,
            control_decision_id=decision_id,
            verified_observation_ids=step.verified_observation_ids,
        )
    return AgentStepResult(
        tenant_id=step.tenant_id,
        job_id=step.job_id,
        step_id=step.current_step_id,
        source_attempt_id=step.runtime_attempt_id,
        control_decision_id=decision_id,
        decision=decision,
        reason=reason,
        next_step=next_step,
    )


def decide_control(step: AgentStepInput) -> AgentStepResult:
    """Return one deterministic control decision with zero side effects."""

    if step.job_is_terminal:
        return _result(step, ControlDecision.COMPLETE, "job_already_terminal")

    if step.pending_reconciliation_identity is not None:
        return _result(
            step,
            ControlDecision.RECONCILE,
            "external_outcome_unknown",
        )

    runtime_result = step.runtime_result
    if runtime_result is not None:
        if runtime_result.status is RuntimeStatus.PENDING_RECONCILIATION:
            return _result(
                step,
                ControlDecision.RECONCILE,
                "runtime_pending_reconciliation",
            )
        if runtime_result.status in {
            RuntimeStatus.REJECTED,
            RuntimeStatus.BLOCKED_PRE_DISPATCH,
        }:
            return _result(
                step,
                ControlDecision.FAIL,
                "runtime_explicit_non_success",
            )

    if len(step.verified_observation_ids) >= step.goal_required_observations:
        return _result(
            step,
            ControlDecision.COMPLETE,
            "goal_satisfied_by_verified_observations",
        )

    if step.waiting_for is not None:
        return _result(step, ControlDecision.WAIT, "known_prerequisite_pending")

    return _result(step, ControlDecision.CONTINUE, "goal_not_yet_satisfied")


@dataclass
class AgentJobState:
    tenant_id: str
    job_id: str
    current_step_id: str
    is_terminal: bool = False

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.job_id or not self.current_step_id:
            raise ValueError(
                "tenant_id, job_id, and current_step_id are required"
            )


class InMemoryControlStore:
    """Process-local control transition model, not durable Day82 evidence."""

    def __init__(self, state: AgentJobState) -> None:
        self.state = state
        self._next_steps_by_decision: dict[str, NextStepRequest] = {}

    def apply_continue(self, result: AgentStepResult) -> ControlApplyStatus:
        if (
            result.tenant_id != self.state.tenant_id
            or result.job_id != self.state.job_id
        ):
            raise ValueError("control result does not match store identity")
        if result.decision is not ControlDecision.CONTINUE:
            return ControlApplyStatus.NOT_APPLICABLE
        if self.state.is_terminal:
            return ControlApplyStatus.NOOP_TERMINAL
        if result.control_decision_id in self._next_steps_by_decision:
            return ControlApplyStatus.DUPLICATE_REPLAY
        if self.state.current_step_id != result.step_id:
            return ControlApplyStatus.NOOP_STALE
        assert result.next_step is not None
        self._next_steps_by_decision[result.control_decision_id] = (
            result.next_step
        )
        self.state.current_step_id = result.next_step.step_id
        return ControlApplyStatus.CREATED

    def next_step_for(
        self, control_decision_id: str
    ) -> Optional[NextStepRequest]:
        return self._next_steps_by_decision.get(control_decision_id)


class AgentRuntimePort(Protocol):
    def execute_step(self, request: NextStepRequest) -> RuntimeResult:
        """Execute one next step through the Day78 Runtime boundary."""

        ...


def orchestrate_next_step(
    *,
    result: AgentStepResult,
    store: InMemoryControlStore,
    runtime: AgentRuntimePort,
) -> tuple[ControlApplyStatus, Optional[RuntimeResult]]:
    """Apply a result; only a newly-created CONTINUE may execute."""

    status = store.apply_continue(result)
    if status is not ControlApplyStatus.CREATED:
        return status, None
    assert result.next_step is not None
    return status, runtime.execute_step(result.next_step)


@dataclass(frozen=True)
class Day78PreparedStep:
    prepared: PreparedAttempt
    request: ApplicationRequest


def prepare_next_step_with_day78(
    *,
    next_step: NextStepRequest,
    requirements: ResolvedExecutionRequirements,
    variables: dict[str, object],
    prompt_registry: PromptContractRegistry,
    routing_policy: RoutingPolicy,
    candidates: Iterable[Candidate],
    now_ms: int,
    max_output_tokens: int,
    correlation_id: str,
) -> Day78PreparedStep:
    """Compose real Day78 preparation/request functions without Provider I/O."""

    prepared = prepare_runtime_attempt(
        job_id=next_step.job_id,
        attempt_id=next_step.runtime_attempt_id,
        requirements=requirements,
        variables=variables,
        prompt_registry=prompt_registry,
        routing_policy=routing_policy,
        candidates=candidates,
        now_ms=now_ms,
    )
    request = build_bound_application_request(
        prepared=prepared,
        tenant_id=next_step.tenant_id,
        max_output_tokens=max_output_tokens,
        correlation_id=correlation_id,
    )
    return Day78PreparedStep(prepared=prepared, request=request)
