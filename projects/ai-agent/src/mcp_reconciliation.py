"""Read-only Day93 reconciliation for possibly dispatched MCP operations.

The scheduler is intentionally incapable of invoking the original Tool.  It
can only query an application-owned authority and return a proposal for a
separate Committer to validate and persist.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, replace
from enum import Enum
from threading import Lock
from typing import Protocol

from mcp_remote_lifecycle import (
    ExecutionCertainty,
    FailureEvidence,
    FailureKind,
    FailurePhase,
)


class AuthoritativeOperationStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_EXECUTED = "NOT_EXECUTED"
    NOT_FOUND = "NOT_FOUND"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ApplicationOperationBinding:
    """Application-owned identity used by both observation and commit."""

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
            raise ValueError("application operation binding must be complete")


@dataclass(frozen=True)
class AuthoritativeResultEvidence:
    """Result of a read-only lookup; not yet a durable application fact."""

    binding: ApplicationOperationBinding
    status: AuthoritativeOperationStatus
    evidence_source: str
    external_object_id: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_source:
            raise ValueError("evidence_source must not be empty")
        if (
            self.status is AuthoritativeOperationStatus.SUCCEEDED
            and not self.external_object_id
        ):
            raise ValueError("successful evidence requires external_object_id")


class AuthoritativeStatusQueryPort(Protocol):
    """A read-only authority; this port cannot execute the original Tool."""

    def query(
        self,
        *,
        binding: ApplicationOperationBinding,
    ) -> AuthoritativeResultEvidence: ...


class ReconciliationDecisionKind(str, Enum):
    RESOLVED_SUCCEEDED = "RESOLVED_SUCCEEDED"
    RESOLVED_FAILED = "RESOLVED_FAILED"
    RESOLVED_NOT_EXECUTED = "RESOLVED_NOT_EXECUTED"
    STILL_PENDING = "STILL_PENDING"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True)
class ReconciliationDecision:
    """A proposal only; durable_transition remains owned by a Committer."""

    kind: ReconciliationDecisionKind
    binding: ApplicationOperationBinding
    evidence_source: str | None = None
    external_object_id: str | None = None
    durable_transition: bool = False
    original_tool_calls: int = 0


class ReconciliationScheduler:
    """Run one read-only reconciliation observation for an unknown outcome."""

    def __init__(self, authority: AuthoritativeStatusQueryPort) -> None:
        self._authority = authority

    def reconcile_once(
        self,
        failure: FailureEvidence,
        *,
        binding: ApplicationOperationBinding,
    ) -> ReconciliationDecision:
        if (
            failure.operation_id != binding.operation_id
            or failure.idempotency_key != binding.idempotency_key
        ):
            return ReconciliationDecision(
                ReconciliationDecisionKind.EVIDENCE_CONFLICT,
                binding,
                evidence_source=failure.evidence_source,
            )
        if (
            failure.execution_certainty
            is ExecutionCertainty.PROVEN_NOT_EXECUTED
        ):
            return ReconciliationDecision(
                ReconciliationDecisionKind.NOT_REQUIRED,
                binding,
            )

        observed = self._authority.query(binding=binding)
        if observed.binding != binding:
            return ReconciliationDecision(
                ReconciliationDecisionKind.EVIDENCE_CONFLICT,
                binding,
                evidence_source=observed.evidence_source,
            )

        if observed.status is AuthoritativeOperationStatus.SUCCEEDED:
            kind = ReconciliationDecisionKind.RESOLVED_SUCCEEDED
        elif observed.status is AuthoritativeOperationStatus.FAILED:
            kind = ReconciliationDecisionKind.RESOLVED_FAILED
        elif observed.status is AuthoritativeOperationStatus.NOT_EXECUTED:
            kind = ReconciliationDecisionKind.RESOLVED_NOT_EXECUTED
        else:
            # NOT_FOUND is not proof of non-execution: the authority may be
            # eventually consistent or the external result may arrive late.
            kind = ReconciliationDecisionKind.STILL_PENDING

        return ReconciliationDecision(
            kind,
            binding,
            evidence_source=observed.evidence_source,
            external_object_id=observed.external_object_id,
        )


class ReconciledBusinessOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_EXECUTED = "NOT_EXECUTED"


class ComplianceOutcome(str, Enum):
    COMPLIANT = "COMPLIANT"
    AUTHORIZATION_VIOLATION = "AUTHORIZATION_VIOLATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReconciliationRecordState(str, Enum):
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class ReconciliationRecord:
    binding: ApplicationOperationBinding
    state: ReconciliationRecordState
    version: int
    business_outcome: ReconciledBusinessOutcome | None = None
    compliance_outcome: ComplianceOutcome | None = None
    external_object_id: str | None = None
    evidence_source: str | None = None


class InMemoryReconciliationStore:
    """Teaching CAS store; production uses one durable atomic update."""

    def __init__(self) -> None:
        self._records: dict[str, ReconciliationRecord] = {}
        self._lock = Lock()

    def add_pending(self, binding: ApplicationOperationBinding) -> None:
        with self._lock:
            if binding.operation_id in self._records:
                raise ValueError("operation is already registered")
            self._records[binding.operation_id] = ReconciliationRecord(
                binding,
                ReconciliationRecordState.PENDING_RECONCILIATION,
                version=1,
            )

    def read(self, operation_id: str) -> ReconciliationRecord | None:
        with self._lock:
            return self._records.get(operation_id)

    def compare_and_set_completed(
        self,
        *,
        binding: ApplicationOperationBinding,
        expected_version: int,
        business_outcome: ReconciledBusinessOutcome,
        compliance_outcome: ComplianceOutcome,
        external_object_id: str | None,
        evidence_source: str,
    ) -> ReconciliationRecord | None:
        with self._lock:
            current = self._records.get(binding.operation_id)
            if (
                current is None
                or current.binding != binding
                or current.state
                is not ReconciliationRecordState.PENDING_RECONCILIATION
                or current.version != expected_version
            ):
                return None
            updated = replace(
                current,
                state=ReconciliationRecordState.COMPLETED,
                version=current.version + 1,
                business_outcome=business_outcome,
                compliance_outcome=compliance_outcome,
                external_object_id=external_object_id,
                evidence_source=evidence_source,
            )
            self._records[binding.operation_id] = updated
            return updated


class ReconciliationCommitOutcome(str, Enum):
    COMMITTED = "COMMITTED"
    PROPOSAL_NOT_RESOLVED = "PROPOSAL_NOT_RESOLVED"
    BINDING_CONFLICT = "BINDING_CONFLICT"
    STATE_CONFLICT = "STATE_CONFLICT"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    CAS_CONFLICT = "CAS_CONFLICT"


@dataclass(frozen=True)
class ReconciliationCommitResult:
    outcome: ReconciliationCommitOutcome
    record: ReconciliationRecord | None = None
    durable_transition: bool = False


class ReconciliationCommitter:
    """Validate a proposal against current state, then atomically repair facts."""

    def __init__(self, store: InMemoryReconciliationStore) -> None:
        self._store = store

    def commit(
        self,
        proposal: ReconciliationDecision,
        *,
        expected_version: int,
        authorization_valid_at_effect: bool,
    ) -> ReconciliationCommitResult:
        if proposal.kind not in {
            ReconciliationDecisionKind.RESOLVED_SUCCEEDED,
            ReconciliationDecisionKind.RESOLVED_FAILED,
            ReconciliationDecisionKind.RESOLVED_NOT_EXECUTED,
        } or proposal.evidence_source is None:
            return ReconciliationCommitResult(
                ReconciliationCommitOutcome.PROPOSAL_NOT_RESOLVED
            )

        current = self._store.read(proposal.binding.operation_id)
        if current is None or current.binding != proposal.binding:
            return ReconciliationCommitResult(
                ReconciliationCommitOutcome.BINDING_CONFLICT
            )
        if current.state is not ReconciliationRecordState.PENDING_RECONCILIATION:
            return ReconciliationCommitResult(
                ReconciliationCommitOutcome.STATE_CONFLICT
            )
        if current.version != expected_version:
            return ReconciliationCommitResult(
                ReconciliationCommitOutcome.VERSION_CONFLICT
            )

        if proposal.kind is ReconciliationDecisionKind.RESOLVED_SUCCEEDED:
            business_outcome = ReconciledBusinessOutcome.SUCCEEDED
        elif proposal.kind is ReconciliationDecisionKind.RESOLVED_FAILED:
            business_outcome = ReconciledBusinessOutcome.FAILED
        else:
            business_outcome = ReconciledBusinessOutcome.NOT_EXECUTED
        compliance_outcome = (
            ComplianceOutcome.NOT_APPLICABLE
            if business_outcome is ReconciledBusinessOutcome.NOT_EXECUTED
            else ComplianceOutcome.COMPLIANT
            if authorization_valid_at_effect
            else ComplianceOutcome.AUTHORIZATION_VIOLATION
        )
        updated = self._store.compare_and_set_completed(
            binding=proposal.binding,
            expected_version=expected_version,
            business_outcome=business_outcome,
            compliance_outcome=compliance_outcome,
            external_object_id=proposal.external_object_id,
            evidence_source=proposal.evidence_source,
        )
        if updated is None:
            return ReconciliationCommitResult(
                ReconciliationCommitOutcome.CAS_CONFLICT
            )
        return ReconciliationCommitResult(
            ReconciliationCommitOutcome.COMMITTED,
            updated,
            durable_transition=True,
        )


def authoritative_not_executed_evidence(
    committed: ReconciliationCommitResult,
    *,
    original_failure: FailureEvidence,
) -> FailureEvidence:
    """Convert a committed fact into retry input, never into a retry command."""

    record = committed.record
    if (
        committed.outcome is not ReconciliationCommitOutcome.COMMITTED
        or record is None
        or record.business_outcome
        is not ReconciledBusinessOutcome.NOT_EXECUTED
        or record.evidence_source is None
    ):
        raise ValueError("committed NOT_EXECUTED fact is required")
    if (
        original_failure.operation_id != record.binding.operation_id
        or original_failure.idempotency_key != record.binding.idempotency_key
    ):
        raise ValueError("original failure does not match reconciled binding")
    return FailureEvidence(
        operation_id=record.binding.operation_id,
        idempotency_key=record.binding.idempotency_key,
        protocol_request_id=original_failure.protocol_request_id,
        attempt_number=original_failure.attempt_number,
        phase=FailurePhase.RECONCILIATION,
        kind=FailureKind.AUTHORITATIVE_NOT_EXECUTED,
        dispatch_certainty=original_failure.dispatch_certainty,
        execution_certainty=ExecutionCertainty.PROVEN_NOT_EXECUTED,
        evidence_source=record.evidence_source,
    )


class ReconciliationScheduleOutcome(str, Enum):
    NEXT_QUERY_SCHEDULED = "NEXT_QUERY_SCHEDULED"
    RESOLUTION_READY = "RESOLUTION_READY"
    OPERATIONAL_ALERT_REQUIRED = "OPERATIONAL_ALERT_REQUIRED"
    ALREADY_ALERTED = "ALREADY_ALERTED"


@dataclass(frozen=True)
class ReconciliationScheduleState:
    binding: ApplicationOperationBinding
    queries_used: int
    maximum_queries: int
    deadline: float
    next_query_at: float | None = None
    alert_emitted: bool = False
    pending_reconciliation: bool = True

    def __post_init__(self) -> None:
        if self.queries_used < 0 or self.maximum_queries < 1:
            raise ValueError("reconciliation query budget must be positive")
        if self.queries_used > self.maximum_queries:
            raise ValueError("queries_used exceeds reconciliation budget")
        if not math.isfinite(self.deadline):
            raise ValueError("reconciliation deadline must be finite")


@dataclass(frozen=True)
class ReconciliationOperationalAlert:
    """Operator signal uses a safe reference, not a metric label."""

    operation_ref: str
    reason: str
    queries_used: int


class OperationalAlertPort(Protocol):
    def emit(self, alert: ReconciliationOperationalAlert) -> None: ...


@dataclass(frozen=True)
class ReconciliationScheduleDecision:
    outcome: ReconciliationScheduleOutcome
    state: ReconciliationScheduleState
    original_tool_calls: int = 0
    durable_transition: bool = False


@dataclass(frozen=True)
class BoundedReconciliationPolicy:
    base_delay_seconds: float = 1.0
    maximum_delay_seconds: float = 30.0
    jitter_ratio: float = 0.2
    minimum_query_window_seconds: float = 0.05

    def advance(
        self,
        decision: ReconciliationDecision,
        state: ReconciliationScheduleState,
        *,
        now: float,
        operation_ref: str,
        alerts: OperationalAlertPort,
    ) -> ReconciliationScheduleDecision:
        if not math.isfinite(now):
            raise ValueError("reconciliation clock must be finite")
        if decision.binding != state.binding:
            raise ValueError("reconciliation schedule binding mismatch")
        if decision.kind in {
            ReconciliationDecisionKind.RESOLVED_SUCCEEDED,
            ReconciliationDecisionKind.RESOLVED_FAILED,
            ReconciliationDecisionKind.RESOLVED_NOT_EXECUTED,
        }:
            return ReconciliationScheduleDecision(
                ReconciliationScheduleOutcome.RESOLUTION_READY,
                replace(state, next_query_at=None),
            )
        if state.alert_emitted:
            return ReconciliationScheduleDecision(
                ReconciliationScheduleOutcome.ALREADY_ALERTED,
                state,
            )

        queries_used = state.queries_used + 1
        delay = self._delay_seconds(state.binding.operation_id, queries_used)
        budget_exhausted = queries_used >= state.maximum_queries
        deadline_exhausted = (
            now + delay + self.minimum_query_window_seconds > state.deadline
        )
        evidence_conflict = (
            decision.kind is ReconciliationDecisionKind.EVIDENCE_CONFLICT
        )
        if budget_exhausted or deadline_exhausted or evidence_conflict:
            reason = (
                "EVIDENCE_CONFLICT"
                if evidence_conflict
                else "QUERY_BUDGET_EXHAUSTED"
                if budget_exhausted
                else "RECONCILIATION_DEADLINE_EXHAUSTED"
            )
            alerts.emit(
                ReconciliationOperationalAlert(
                    operation_ref,
                    reason,
                    queries_used,
                )
            )
            return ReconciliationScheduleDecision(
                ReconciliationScheduleOutcome.OPERATIONAL_ALERT_REQUIRED,
                replace(
                    state,
                    queries_used=queries_used,
                    next_query_at=None,
                    alert_emitted=True,
                ),
            )
        return ReconciliationScheduleDecision(
            ReconciliationScheduleOutcome.NEXT_QUERY_SCHEDULED,
            replace(
                state,
                queries_used=queries_used,
                next_query_at=now + delay,
            ),
        )

    def _delay_seconds(self, operation_id: str, queries_used: int) -> float:
        base = min(
            self.maximum_delay_seconds,
            self.base_delay_seconds * (2 ** (queries_used - 1)),
        )
        digest = hashlib.sha256(
            f"reconcile:{operation_id}:{queries_used}".encode("utf-8")
        ).digest()
        unit = int.from_bytes(digest[:8], "big") / (2**64 - 1)
        factor = 1.0 + self.jitter_ratio * ((2.0 * unit) - 1.0)
        return min(self.maximum_delay_seconds, base * factor)
