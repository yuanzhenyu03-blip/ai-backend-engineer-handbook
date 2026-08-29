"""Day78 application-owned LLM Runtime orchestration checkpoint.

This module composes existing Day72-Day76 public boundaries.  Its stores and
locks are deterministic in-process models, not database, queue, Provider,
external-tool, billing, integration-runtime, or production evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
from types import MappingProxyType
import threading
from typing import Iterable, Mapping, Optional, Tuple

from output_tool_contracts import (
    AdmittedToolCall,
    AdmissionDecision,
    AdmissionStatus,
    AuthContext,
    ExecutionResult,
    ExecutionStatus,
    InMemoryReportStore,
    InMemoryToolExecutor,
    OutcomeDecision,
    OutcomeStatus,
    ToolRegistry,
    admit_tool_call,
    verify_publish_outcome,
)
from prompt_contracts import (
    AttemptPromptBinding,
    PromptContractRegistry,
    RenderedMessage,
    compute_rendered_hash,
    plan_attempt_binding,
)
from provider_contract import (
    ApplicationRequest,
    AttemptExecutionContract,
    ProviderOutcome,
    ProviderOutcomeKind,
)
from routing_policy import Candidate, RoutingDecision, RoutingPolicy, route


class RuntimeStage(str, Enum):
    PREPARATION = "PREPARATION"
    PROVIDER_DISPATCH = "PROVIDER_DISPATCH"
    CANDIDATE_VALIDATION = "CANDIDATE_VALIDATION"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    OUTCOME_VERIFICATION = "OUTCOME_VERIFICATION"
    COMPLETION = "COMPLETION"
    COST_SETTLEMENT = "COST_SETTLEMENT"


class RuntimeStatus(str, Enum):
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    BLOCKED_PRE_DISPATCH = "BLOCKED_PRE_DISPATCH"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"


class RecoveryAction(str, Enum):
    NONE = "NONE"
    REJECT = "REJECT"
    RECONCILE_ORIGINAL_IDENTITY = "RECONCILE_ORIGINAL_IDENTITY"


class EvidenceLevel(str, Enum):
    CONCEPTUAL = "CONCEPTUAL"
    STATIC = "STATIC"
    EXECUTED_LOCAL_RUNTIME = "EXECUTED_LOCAL_RUNTIME"
    INTEGRATION_RUNTIME = "INTEGRATION_RUNTIME"
    PRODUCTION = "PRODUCTION"


@dataclass(frozen=True)
class RuntimeResult:
    job_id: str
    attempt_id: str
    stage: RuntimeStage
    status: RuntimeStatus
    recovery_action: RecoveryAction
    evidence_level: EvidenceLevel
    reason: str
    safe_evidence: Mapping[str, str] = field(default_factory=dict)
    operation_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.job_id or not self.attempt_id or not self.reason:
            raise ValueError("job_id, attempt_id, and reason are required")
        if (
            self.status is RuntimeStatus.PENDING_RECONCILIATION
            and self.recovery_action
            is not RecoveryAction.RECONCILE_ORIGINAL_IDENTITY
        ):
            raise ValueError("pending reconciliation must preserve identity")
        if (
            self.status is RuntimeStatus.COMPLETED
            and self.recovery_action is not RecoveryAction.NONE
        ):
            raise ValueError("completed results cannot request recovery")
        object.__setattr__(
            self,
            "safe_evidence",
            MappingProxyType(dict(self.safe_evidence)),
        )


@dataclass(frozen=True)
class ResolvedExecutionRequirements:
    application_contract: str
    prompt_contract_id: str
    output_contract_revision: str
    tool_contract_revision: str
    parameter_policy_id: str
    parameter_policy_revision: str


@dataclass(frozen=True)
class PreparedAttempt:
    requirements: ResolvedExecutionRequirements
    routing_decision: RoutingDecision
    provider_binding: AttemptExecutionContract
    prompt_binding: AttemptPromptBinding
    rendered_messages: Tuple[RenderedMessage, ...]


class NoEligibleRouteError(Exception):
    def __init__(self, decision: RoutingDecision) -> None:
        super().__init__("no eligible Provider route")
        self.decision = decision


def prepare_runtime_attempt(
    *,
    job_id: str,
    attempt_id: str,
    requirements: ResolvedExecutionRequirements,
    variables: Mapping[str, object],
    prompt_registry: PromptContractRegistry,
    routing_policy: RoutingPolicy,
    candidates: Iterable[Candidate],
    now_ms: int,
) -> PreparedAttempt:
    """Resolve the Prompt before eligibility, preference, and immutable binding."""

    revision = prompt_registry.select_default_for_new_attempt(
        requirements.prompt_contract_id,
        requirements.application_contract,
    )
    decision, provider_binding = route(
        job_id=job_id,
        attempt_id=attempt_id,
        application_contract=requirements.application_contract,
        policy=routing_policy,
        candidates=candidates,
        now_ms=now_ms,
    )
    if provider_binding is None:
        raise NoEligibleRouteError(decision)
    prompt_binding, messages = plan_attempt_binding(
        attempt_id=attempt_id,
        job_id=job_id,
        revision=revision,
        parameter_policy_id=requirements.parameter_policy_id,
        parameter_policy_revision=requirements.parameter_policy_revision,
        application_contract=requirements.application_contract,
        variables=variables,
    )
    return PreparedAttempt(
        requirements=requirements,
        routing_decision=decision,
        provider_binding=provider_binding,
        prompt_binding=prompt_binding,
        rendered_messages=tuple(messages),
    )


class RuntimeAttemptStatus(str, Enum):
    PREPARED = "PREPARED"
    DISPATCH_CLAIMED = "DISPATCH_CLAIMED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    TOOL_ADMITTED = "TOOL_ADMITTED"
    TOOL_EXECUTED = "TOOL_EXECUTED"
    TOOL_EXECUTION_BLOCKED = "TOOL_EXECUTION_BLOCKED"
    OUTCOME_REJECTED = "OUTCOME_REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class RuntimeAttemptRecord:
    prepared: PreparedAttempt
    status: RuntimeAttemptStatus
    claimed_by: Optional[str] = None
    fence_token: Optional[int] = None
    reason: str = ""
    tool_call_id: Optional[str] = None
    tool_idempotency_key: Optional[str] = None
    operation_id: Optional[str] = None


class CompensationStatus(str, Enum):
    PLANNED = "PLANNED"
    DISPATCH_CLAIMED = "DISPATCH_CLAIMED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"


@dataclass(frozen=True)
class CompensationRecord:
    compensation_id: str
    source_attempt_id: str
    source_tool_call_id: str
    source_operation_id: str
    idempotency_key: str
    status: CompensationStatus
    claimed_by: Optional[str] = None


class InMemoryRuntimeAttemptStore:
    """One authoritative in-process lifecycle; models conditional UPDATE."""

    def __init__(self) -> None:
        self._records: dict[str, RuntimeAttemptRecord] = {}
        self._compensations: dict[str, CompensationRecord] = {}
        self._next_fence_token = 0
        self._lock = threading.RLock()

    def persist_prepared(self, prepared: PreparedAttempt) -> None:
        attempt_id = prepared.provider_binding.attempt_id
        with self._lock:
            if attempt_id in self._records:
                raise ValueError("Attempt already exists")
            self._records[attempt_id] = RuntimeAttemptRecord(
                prepared, RuntimeAttemptStatus.PREPARED
            )

    def get(self, attempt_id: str) -> Optional[RuntimeAttemptRecord]:
        with self._lock:
            return self._records.get(attempt_id)

    def claim_dispatch(
        self, *, attempt_id: str, expected_prompt_hash: str, worker_id: str
    ) -> Optional[RuntimeAttemptRecord]:
        with self._lock:
            current = self._records.get(attempt_id)
            if (
                current is None
                or current.status is not RuntimeAttemptStatus.PREPARED
                or current.prepared.prompt_binding.rendered_message_hash
                != expected_prompt_hash
            ):
                return None
            self._next_fence_token += 1
            claimed = replace(
                current,
                status=RuntimeAttemptStatus.DISPATCH_CLAIMED,
                claimed_by=worker_id,
                fence_token=self._next_fence_token,
                reason="dispatch_claimed",
            )
            self._records[attempt_id] = claimed
            return claimed

    def mark_provider_execution_unknown(
        self, *, attempt_id: str, worker_id: str
    ) -> RuntimeAttemptRecord:
        with self._lock:
            current = self._owned(attempt_id, worker_id)
            if current.status is not RuntimeAttemptStatus.DISPATCH_CLAIMED:
                raise ValueError("unknown transition requires dispatch claim")
            updated = replace(
                current,
                status=RuntimeAttemptStatus.PENDING_RECONCILIATION,
                reason="provider_execution_unknown",
            )
            self._records[attempt_id] = updated
            return updated

    def record_tool_admission(
        self, *, worker_id: str, call: AdmittedToolCall
    ) -> RuntimeAttemptRecord:
        with self._lock:
            current = self._owned(call.attempt_id, worker_id)
            if (
                current.status is not RuntimeAttemptStatus.DISPATCH_CLAIMED
                or call.job_id != current.prepared.provider_binding.job_id
            ):
                raise ValueError("Admission does not match current Attempt")
            updated = replace(
                current,
                status=RuntimeAttemptStatus.TOOL_ADMITTED,
                reason="tool_admitted",
                tool_call_id=call.tool_call_id,
                tool_idempotency_key=call.idempotency_key,
            )
            self._records[call.attempt_id] = updated
            return updated

    def record_tool_execution(
        self, *, attempt_id: str, worker_id: str, result: ExecutionResult
    ) -> RuntimeAttemptRecord:
        with self._lock:
            current = self._owned(attempt_id, worker_id)
            if current.status is not RuntimeAttemptStatus.TOOL_ADMITTED:
                raise ValueError("execution requires current Admission")
            executed = result.status in {
                ExecutionStatus.EXECUTED,
                ExecutionStatus.DUPLICATE_SUPPRESSED,
            }
            updated = replace(
                current,
                status=(
                    RuntimeAttemptStatus.TOOL_EXECUTED
                    if executed
                    else RuntimeAttemptStatus.TOOL_EXECUTION_BLOCKED
                ),
                reason="tool_executed" if executed else "tool_execution_blocked",
                operation_id=result.operation_id,
            )
            self._records[attempt_id] = updated
            return updated

    def execute_admitted_with_fence(
        self,
        *,
        call: AdmittedToolCall,
        worker_id: str,
        expected_fence_token: int,
        registry: ToolRegistry,
        executor: InMemoryToolExecutor,
    ) -> ExecutionResult:
        """Recheck lifecycle and fencing at the modeled effect boundary."""

        with self._lock:
            current = self._owned(call.attempt_id, worker_id)
            if (
                current.status is not RuntimeAttemptStatus.TOOL_ADMITTED
                or current.fence_token != expected_fence_token
                or current.tool_call_id != call.tool_call_id
                or current.tool_idempotency_key != call.idempotency_key
            ):
                raise ValueError("stale Tool execution authority")
            result = executor.execute(call, registry=registry)
            self.record_tool_execution(
                attempt_id=call.attempt_id,
                worker_id=worker_id,
                result=result,
            )
            return result

    def record_outcome(
        self,
        *,
        worker_id: str,
        call: AdmittedToolCall,
        operation_id: str,
        outcome: OutcomeDecision,
    ) -> RuntimeAttemptRecord:
        with self._lock:
            current = self._owned(call.attempt_id, worker_id)
            if (
                current.status is not RuntimeAttemptStatus.TOOL_EXECUTED
                or current.tool_call_id != call.tool_call_id
                or current.operation_id != operation_id
                or call.job_id != current.prepared.provider_binding.job_id
            ):
                raise ValueError("outcome does not match current Runtime identity")
            if outcome.status is OutcomeStatus.VERIFIED:
                status = RuntimeAttemptStatus.COMPLETED
            elif outcome.status is OutcomeStatus.IDENTITY_MISMATCH:
                status = RuntimeAttemptStatus.PENDING_RECONCILIATION
            else:
                status = RuntimeAttemptStatus.OUTCOME_REJECTED
            updated = replace(
                current,
                status=status,
                reason=outcome.safe_reason_code,
            )
            self._records[call.attempt_id] = updated
            return updated

    def cancel_after_external_effect(self, attempt_id: str) -> RuntimeAttemptRecord:
        with self._lock:
            current = self._records[attempt_id]
            if current.status is not RuntimeAttemptStatus.TOOL_EXECUTED:
                raise ValueError("cancellation path requires executed effect")
            updated = replace(current, status=RuntimeAttemptStatus.CANCELLED)
            self._records[attempt_id] = updated
            return updated

    def create_compensation(
        self, *, compensation_id: str, source_attempt_id: str, idempotency_key: str
    ) -> CompensationRecord:
        with self._lock:
            source = self._records[source_attempt_id]
            if (
                source.status is not RuntimeAttemptStatus.CANCELLED
                or source.tool_call_id is None
                or source.operation_id is None
            ):
                raise ValueError("compensation requires cancelled executed source")
            if idempotency_key == source.tool_idempotency_key:
                raise ValueError("compensation requires a new idempotency key")
            if compensation_id in self._compensations:
                raise ValueError("compensation already exists")
            record = CompensationRecord(
                compensation_id,
                source_attempt_id,
                source.tool_call_id,
                source.operation_id,
                idempotency_key,
                CompensationStatus.PLANNED,
            )
            self._compensations[compensation_id] = record
            return record

    def claim_compensation(
        self, compensation_id: str, worker_id: str
    ) -> Optional[CompensationRecord]:
        with self._lock:
            current = self._compensations.get(compensation_id)
            if current is None or current.status is not CompensationStatus.PLANNED:
                return None
            claimed = replace(
                current,
                status=CompensationStatus.DISPATCH_CLAIMED,
                claimed_by=worker_id,
            )
            self._compensations[compensation_id] = claimed
            return claimed

    def mark_compensation_unknown(
        self, compensation_id: str, worker_id: str
    ) -> CompensationRecord:
        with self._lock:
            current = self._compensations[compensation_id]
            if (
                current.status is not CompensationStatus.DISPATCH_CLAIMED
                or current.claimed_by != worker_id
            ):
                raise ValueError("only current compensation owner may update")
            pending = replace(
                current, status=CompensationStatus.PENDING_RECONCILIATION
            )
            self._compensations[compensation_id] = pending
            return pending

    def _owned(self, attempt_id: str, worker_id: str) -> RuntimeAttemptRecord:
        current = self._records.get(attempt_id)
        if current is None or current.claimed_by != worker_id:
            raise ValueError("worker does not own current Attempt")
        return current


class ProviderPayloadBindingError(Exception):
    pass


class ProviderCandidateBindingError(Exception):
    pass


class ProtectedCandidateNotLoadedError(Exception):
    pass


def candidate_sha256(raw_candidate: str) -> str:
    return "sha256:" + hashlib.sha256(raw_candidate.encode()).hexdigest()


def build_bound_application_request(
    *, prepared: PreparedAttempt, tenant_id: str, max_output_tokens: int,
    correlation_id: str
) -> ApplicationRequest:
    messages = list(prepared.rendered_messages)
    if compute_rendered_hash(messages) != prepared.prompt_binding.rendered_message_hash:
        raise ProviderPayloadBindingError("rendered messages differ from Prompt binding")
    prompt = json.dumps(
        [[message.role.value, message.content] for message in messages],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return ApplicationRequest(
        job_id=prepared.provider_binding.job_id,
        tenant_id=tenant_id,
        application_contract=prepared.requirements.application_contract,
        task_type="research",
        max_output_tokens=max_output_tokens,
        correlation_id=correlation_id,
        prompt=prompt,
    )


@dataclass(frozen=True)
class ProviderExecutionEnvelope:
    job_id: str
    attempt_id: str
    correlation_id: str
    outcome: ProviderOutcome
    candidate_hash: Optional[str] = None
    raw_candidate: Optional[str] = field(default=None, repr=False)
    protected_candidate_ref: Optional[str] = None

    def __post_init__(self) -> None:
        sources = sum(
            item is not None
            for item in (self.raw_candidate, self.protected_candidate_ref)
        )
        if self.outcome.kind is ProviderOutcomeKind.SUCCESS:
            if sources != 1 or self.candidate_hash is None:
                raise ValueError("SUCCESS requires one candidate source and hash")
        elif sources or self.candidate_hash is not None:
            raise ValueError("non-success cannot carry candidate")


def admit_provider_candidate(
    *, envelope: ProviderExecutionEnvelope, prepared: PreparedAttempt,
    expected_correlation_id: str, registry: ToolRegistry, auth: AuthContext,
    reports: InMemoryReportStore
) -> AdmissionDecision:
    if (
        envelope.job_id != prepared.provider_binding.job_id
        or envelope.attempt_id != prepared.provider_binding.attempt_id
        or envelope.correlation_id != expected_correlation_id
    ):
        raise ProviderCandidateBindingError("candidate identity mismatch")
    if envelope.outcome.kind is not ProviderOutcomeKind.SUCCESS:
        raise ProviderCandidateBindingError("non-success has no candidate")
    if envelope.raw_candidate is None:
        raise ProtectedCandidateNotLoadedError("authorized loader not integrated")
    if candidate_sha256(envelope.raw_candidate) != envelope.candidate_hash:
        raise ProviderCandidateBindingError("candidate hash mismatch")
    return admit_tool_call(
        envelope.raw_candidate,
        attempt_id=envelope.attempt_id,
        job_id=envelope.job_id,
        registry=registry,
        auth=auth,
        reports=reports,
    )


def execute_admitted_tool(
    *, decision: AdmissionDecision, store: InMemoryRuntimeAttemptStore,
    worker_id: str, expected_fence_token: int, registry: ToolRegistry,
    executor: InMemoryToolExecutor
) -> ExecutionResult:
    if decision.status is not AdmissionStatus.ALLOWED or decision.admitted_call is None:
        raise ValueError("only allowed Admission may execute")
    call = decision.admitted_call
    store.record_tool_admission(worker_id=worker_id, call=call)
    return store.execute_admitted_with_fence(
        call=call,
        worker_id=worker_id,
        expected_fence_token=expected_fence_token,
        registry=registry,
        executor=executor,
    )


def verify_outcome_and_complete(
    *, raw_tool_outcome: str, call: AdmittedToolCall,
    execution: ExecutionResult, store: InMemoryRuntimeAttemptStore,
    worker_id: str
) -> tuple[OutcomeDecision, RuntimeResult]:
    if execution.operation_id is None or execution.status not in {
        ExecutionStatus.EXECUTED,
        ExecutionStatus.DUPLICATE_SUPPRESSED,
    }:
        raise ValueError("only executed operations produce outcomes")
    outcome = verify_publish_outcome(
        raw_tool_outcome,
        call=call,
        expected_operation_id=execution.operation_id,
    )
    store.record_outcome(
        worker_id=worker_id,
        call=call,
        operation_id=execution.operation_id,
        outcome=outcome,
    )
    mismatch = outcome.status is OutcomeStatus.IDENTITY_MISMATCH
    verified = outcome.status is OutcomeStatus.VERIFIED
    return outcome, RuntimeResult(
        job_id=call.job_id,
        attempt_id=call.attempt_id,
        stage=RuntimeStage.COMPLETION if verified else RuntimeStage.OUTCOME_VERIFICATION,
        status=(
            RuntimeStatus.COMPLETED
            if verified
            else RuntimeStatus.PENDING_RECONCILIATION
            if mismatch
            else RuntimeStatus.REJECTED
        ),
        recovery_action=(
            RecoveryAction.NONE
            if verified
            else RecoveryAction.RECONCILE_ORIGINAL_IDENTITY
            if mismatch
            else RecoveryAction.REJECT
        ),
        evidence_level=EvidenceLevel.EXECUTED_LOCAL_RUNTIME,
        reason=outcome.safe_reason_code,
        safe_evidence={"outcome_status": outcome.status.value},
        operation_id=execution.operation_id,
    )


class CostSettlementStatus(str, Enum):
    REQUESTED = "REQUESTED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    SETTLED = "SETTLED"


@dataclass(frozen=True)
class CostSettlementRecord:
    settlement_id: str
    job_id: str
    attempt_id: str
    reservation_id: str
    reserved_units: int
    status: CostSettlementStatus
    actual_usage_units: Optional[int] = None
    released_units: Optional[int] = None


class InMemoryCostSettlementStore:
    def __init__(self) -> None:
        self._records: dict[str, CostSettlementRecord] = {}
        self._lock = threading.RLock()

    def request(
        self, *, settlement_id: str, job_id: str, attempt_id: str,
        reservation_id: str, reserved_units: int
    ) -> CostSettlementRecord:
        if reserved_units < 0:
            raise ValueError("negative reservation")
        proposed = CostSettlementRecord(
            settlement_id, job_id, attempt_id, reservation_id, reserved_units,
            CostSettlementStatus.REQUESTED,
        )
        with self._lock:
            existing = self._records.get(settlement_id)
            if existing is not None:
                if (
                    existing.job_id,
                    existing.attempt_id,
                    existing.reservation_id,
                    existing.reserved_units,
                ) != (job_id, attempt_id, reservation_id, reserved_units):
                    raise ValueError("settlement identity rebound")
                return existing
            self._records[settlement_id] = proposed
            return proposed

    def mark_unknown(self, settlement_id: str) -> CostSettlementRecord:
        with self._lock:
            current = self._records[settlement_id]
            if current.status is CostSettlementStatus.SETTLED:
                return current
            updated = replace(
                current, status=CostSettlementStatus.PENDING_RECONCILIATION
            )
            self._records[settlement_id] = updated
            return updated

    def settle(
        self, settlement_id: str, actual_usage_units: int
    ) -> CostSettlementRecord:
        with self._lock:
            current = self._records[settlement_id]
            if current.status is CostSettlementStatus.SETTLED:
                if current.actual_usage_units != actual_usage_units:
                    raise ValueError("settled usage is immutable")
                return current
            if not 0 <= actual_usage_units <= current.reserved_units:
                raise ValueError("usage outside reservation")
            updated = replace(
                current,
                status=CostSettlementStatus.SETTLED,
                actual_usage_units=actual_usage_units,
                released_units=current.reserved_units - actual_usage_units,
            )
            self._records[settlement_id] = updated
            return updated
