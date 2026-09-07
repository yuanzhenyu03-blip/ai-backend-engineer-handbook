"""Day85 application-owned handoff and coordination boundary.

This first increment is deliberately in-process.  It models candidate validation,
minimal delegated authority, bounded child allocation, idempotent acceptance and
receiver claim/lease/fence behavior.  It performs no Provider, Tool or network I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
import threading
from typing import Protocol


class HandoffState(str, Enum):
    ACCEPTED = "ACCEPTED"
    CLAIMED = "CLAIMED"
    DISPATCHED = "DISPATCHED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    VERIFIED_COMPLETED = "VERIFIED_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AcceptanceStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    SEMANTIC_CONFLICT = "SEMANTIC_CONFLICT"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    CAPABILITY_NOT_DELEGATABLE = "CAPABILITY_NOT_DELEGATABLE"
    CAPABILITY_NOT_CURRENTLY_ALLOWED = "CAPABILITY_NOT_CURRENTLY_ALLOWED"
    OUTPUT_CONTRACT_REJECTED = "OUTPUT_CONTRACT_REJECTED"
    CONTEXT_REJECTED = "CONTEXT_REJECTED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    DEADLINE_EXPIRED = "DEADLINE_EXPIRED"
    DELEGATION_DEPTH_EXCEEDED = "DELEGATION_DEPTH_EXCEEDED"
    FAN_OUT_EXCEEDED = "FAN_OUT_EXCEEDED"
    CONCURRENCY_LIMIT_REACHED = "CONCURRENCY_LIMIT_REACHED"


class ClaimStatus(str, Enum):
    CLAIMED = "CLAIMED"
    DUPLICATE = "DUPLICATE"
    ALREADY_CLAIMED = "ALREADY_CLAIMED"
    HANDOFF_NOT_FOUND = "HANDOFF_NOT_FOUND"
    HANDOFF_NOT_CLAIMABLE = "HANDOFF_NOT_CLAIMABLE"


class DispatchStatus(str, Enum):
    ALLOWED = "ALLOWED"
    HANDOFF_NOT_FOUND = "HANDOFF_NOT_FOUND"
    NOT_CURRENT_OWNER = "NOT_CURRENT_OWNER"
    STALE_FENCE = "STALE_FENCE"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    CURRENT_AUTHORIZATION_DENIED = "CURRENT_AUTHORIZATION_DENIED"
    HANDOFF_NOT_CLAIMED = "HANDOFF_NOT_CLAIMED"


class ResultVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    HANDOFF_NOT_FOUND = "HANDOFF_NOT_FOUND"
    CHILD_ATTEMPT_MISMATCH = "CHILD_ATTEMPT_MISMATCH"
    OUTPUT_CONTRACT_MISMATCH = "OUTPUT_CONTRACT_MISMATCH"
    SOURCE_VERSION_STALE = "SOURCE_VERSION_STALE"
    STALE_FENCE = "STALE_FENCE"
    NOT_CURRENT_OWNER = "NOT_CURRENT_OWNER"
    PARENT_TERMINAL = "PARENT_TERMINAL"
    HANDOFF_NOT_READY = "HANDOFF_NOT_READY"


class CancellationStatus(str, Enum):
    CANCELLED_BEFORE_DISPATCH = "CANCELLED_BEFORE_DISPATCH"
    COOPERATIVE_CANCELLATION_PENDING = "COOPERATIVE_CANCELLATION_PENDING"
    HANDOFF_NOT_FOUND = "HANDOFF_NOT_FOUND"
    TERMINAL_NOOP = "TERMINAL_NOOP"


class AggregationStatus(str, Enum):
    WAITING_FOR_REQUIRED = "WAITING_FOR_REQUIRED"
    READY = "READY"
    PARTIAL = "PARTIAL"
    CONFLICT = "CONFLICT"
    PARENT_TERMINAL = "PARENT_TERMINAL"


class FakeWorkerMode(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    CRASH_BEFORE_CLAIM = "CRASH_BEFORE_CLAIM"
    DELAYED = "DELAYED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class HandoffCandidate:
    tenant_id: str
    parent_job_id: str
    parent_attempt_id: str
    parent_step_id: str
    handoff_id: str
    idempotency_key: str
    policy_version: str
    objective: str
    input_contract: str
    output_contract: str
    context_manifest_id: str
    context_source_versions: tuple[tuple[str, int], ...]
    requested_capabilities: tuple[str, ...]
    requested_tokens: int
    receiver_role: str
    aggregation_slot: str
    required: bool
    deadline: int
    delegation_depth: int = 1

    def __post_init__(self) -> None:
        values = (
            self.tenant_id, self.parent_job_id, self.parent_attempt_id,
            self.parent_step_id, self.handoff_id, self.idempotency_key,
            self.policy_version, self.objective, self.input_contract,
            self.output_contract, self.context_manifest_id,
            self.receiver_role, self.aggregation_slot,
        )
        if any(not value for value in values):
            raise ValueError("handoff identity and contracts must be non-empty")
        if self.requested_tokens <= 0:
            raise ValueError("requested_tokens must be positive")
        if self.delegation_depth <= 0:
            raise ValueError("delegation_depth must be positive")
        if len(set(self.requested_capabilities)) != len(
                self.requested_capabilities):
            raise ValueError("requested capabilities must be unique")

    @property
    def fingerprint(self) -> str:
        semantic = {
            "tenant_id": self.tenant_id,
            "parent_job_id": self.parent_job_id,
            "parent_attempt_id": self.parent_attempt_id,
            "parent_step_id": self.parent_step_id,
            "objective": self.objective,
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "context_manifest_id": self.context_manifest_id,
            "context_source_versions": self.context_source_versions,
            "requested_capabilities": sorted(self.requested_capabilities),
            "requested_tokens": self.requested_tokens,
            "receiver_role": self.receiver_role,
            "aggregation_slot": self.aggregation_slot,
            "required": self.required,
            "deadline": self.deadline,
            "delegation_depth": self.delegation_depth,
            "policy_version": self.policy_version,
        }
        payload = json.dumps(
            semantic, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class CurrentCoordinationFacts:
    tenant_id: str
    delegatable_capabilities: tuple[str, ...]
    currently_allowed_capabilities: tuple[str, ...]
    accepted_output_contracts: tuple[str, ...]
    readable_context_manifests: tuple[str, ...]
    current_policy_version: str
    max_delegation_depth: int = 2
    max_fan_out: int = 3
    concurrency_limit: int = 2


@dataclass(frozen=True)
class DelegationGrant:
    tenant_id: str
    handoff_id: str
    child_job_id: str
    child_attempt_id: str
    capabilities: tuple[str, ...]
    policy_version: str
    expires_at: int


@dataclass(frozen=True)
class ChildAllocation:
    parent_job_id: str
    handoff_id: str
    reserved_tokens: int
    status: str = "HELD"


@dataclass(frozen=True)
class CoordinationOutboxIntent:
    intent_id: str
    handoff_id: str
    child_job_id: str
    fingerprint: str
    published_at: int | None = None


@dataclass(frozen=True)
class HandoffRecord:
    candidate: HandoffCandidate
    fingerprint: str
    child_job_id: str
    child_attempt_id: str
    grant: DelegationGrant
    allocation: ChildAllocation
    outbox_intent: CoordinationOutboxIntent
    state: HandoffState = HandoffState.ACCEPTED
    state_version: int = 1
    claim_owner: str | None = None
    lease_expires_at: int | None = None
    fence_token: int = 0
    operation_id: str | None = None
    cancellation_requested: bool = False


@dataclass(frozen=True)
class AcceptanceDecision:
    status: AcceptanceStatus
    handoff_id: str
    fingerprint: str
    record: HandoffRecord | None = None


@dataclass(frozen=True)
class ClaimDecision:
    status: ClaimStatus
    handoff_id: str
    owner: str | None
    fence_token: int | None


@dataclass(frozen=True)
class DispatchDecision:
    status: DispatchStatus
    handoff_id: str
    provider_calls: int = 0


@dataclass(frozen=True)
class ChildResultCandidate:
    result_id: str
    handoff_id: str
    child_attempt_id: str
    worker_id: str
    fence_token: int
    output_contract: str
    source_versions: tuple[tuple[str, int], ...]
    evidence_reference: str
    completeness: str
    fact_key: str
    fact_value: str


@dataclass(frozen=True)
class ResultEvidence:
    candidate: ChildResultCandidate
    status: ResultVerificationStatus
    applied_to_current_state: bool


@dataclass(frozen=True)
class ResultVerificationDecision:
    status: ResultVerificationStatus
    handoff_id: str
    applied_to_current_state: bool


@dataclass(frozen=True)
class CancellationDecision:
    status: CancellationStatus
    handoff_id: str
    allocation_status: str


@dataclass(frozen=True)
class AggregationDecision:
    status: AggregationStatus
    required_total: int
    required_verified: int
    optional_total: int
    optional_verified: int
    failed: int
    pending_reconciliation: int
    parent_completed: bool


@dataclass(frozen=True)
class WorkerRequest:
    handoff_id: str
    child_attempt_id: str
    objective: str
    fence_token: int


@dataclass(frozen=True)
class WorkerOutcome:
    mode: FakeWorkerMode
    status: str
    fact_value: str | None
    fake_provider_calls: int


class WorkerPort(Protocol):
    def execute(self, request: WorkerRequest) -> WorkerOutcome:
        """Return a candidate outcome without owning coordination state."""


class FakeWorker:
    """Deterministic failure-injection fixture, not a distributed Worker."""

    def __init__(self, mode: FakeWorkerMode) -> None:
        self.mode = mode
        self.requests: list[WorkerRequest] = []

    def execute(self, request: WorkerRequest) -> WorkerOutcome:
        self.requests.append(request)
        outcomes = {
            FakeWorkerMode.SUCCESS: WorkerOutcome(
                self.mode, "RESULT_CANDIDATE", "confirmed", 1,
            ),
            FakeWorkerMode.FAILURE: WorkerOutcome(
                self.mode, "FAILED", None, 1,
            ),
            FakeWorkerMode.CRASH_BEFORE_CLAIM: WorkerOutcome(
                self.mode, "CRASHED_BEFORE_CLAIM", None, 0,
            ),
            FakeWorkerMode.DELAYED: WorkerOutcome(
                self.mode, "DELAYED", None, 0,
            ),
            FakeWorkerMode.OUTCOME_UNKNOWN: WorkerOutcome(
                self.mode, "PENDING_RECONCILIATION", None, 1,
            ),
            FakeWorkerMode.CONFLICT: WorkerOutcome(
                self.mode, "RESULT_CANDIDATE", "contradicted", 1,
            ),
        }
        return outcomes[self.mode]


class InMemoryCoordinationStore:
    """Deterministic store model; not evidence of database durability."""

    def __init__(self, *, parent_job_id: str, parent_token_reservation: int) -> None:
        if parent_token_reservation <= 0:
            raise ValueError("parent_token_reservation must be positive")
        self.parent_job_id = parent_job_id
        self.parent_token_reservation = parent_token_reservation
        self._records: dict[str, HandoffRecord] = {}
        self.result_evidence: list[ResultEvidence] = []
        self.parent_terminal = False
        self._lock = threading.RLock()

    @property
    def allocated_tokens(self) -> int:
        return sum(
            record.allocation.reserved_tokens
            for record in self._records.values()
            if record.allocation.status == "HELD"
        )

    @property
    def unpublished_outbox_intents(self) -> tuple[CoordinationOutboxIntent, ...]:
        return tuple(
            record.outbox_intent
            for record in self._records.values()
            if record.outbox_intent.published_at is None
        )

    def get(self, handoff_id: str) -> HandoffRecord | None:
        return self._records.get(handoff_id)

    def accept(
        self, candidate: HandoffCandidate, *, facts: CurrentCoordinationFacts,
        now: int,
    ) -> AcceptanceDecision:
        """Validate and atomically model acceptance plus child/grant/allocation."""
        with self._lock:
            fingerprint = candidate.fingerprint
            existing = self._records.get(candidate.handoff_id)
            if existing is not None:
                status = (
                    AcceptanceStatus.DUPLICATE
                    if existing.fingerprint == fingerprint
                    else AcceptanceStatus.SEMANTIC_CONFLICT
                )
                return AcceptanceDecision(
                    status, candidate.handoff_id, fingerprint, existing,
                )
            if candidate.tenant_id != facts.tenant_id:
                return AcceptanceDecision(
                    AcceptanceStatus.SCOPE_MISMATCH,
                    candidate.handoff_id, fingerprint,
                )
            if candidate.policy_version != facts.current_policy_version:
                return AcceptanceDecision(
                    AcceptanceStatus.CONTEXT_REJECTED,
                    candidate.handoff_id, fingerprint,
                )
            if now >= candidate.deadline:
                return AcceptanceDecision(
                    AcceptanceStatus.DEADLINE_EXPIRED,
                    candidate.handoff_id, fingerprint,
                )
            if candidate.delegation_depth > facts.max_delegation_depth:
                return AcceptanceDecision(
                    AcceptanceStatus.DELEGATION_DEPTH_EXCEEDED,
                    candidate.handoff_id, fingerprint,
                )
            if len(self._records) >= facts.max_fan_out:
                return AcceptanceDecision(
                    AcceptanceStatus.FAN_OUT_EXCEEDED,
                    candidate.handoff_id, fingerprint,
                )
            active = sum(
                record.state not in {
                    HandoffState.CANCELLED,
                    HandoffState.VERIFIED_COMPLETED,
                    HandoffState.FAILED,
                }
                for record in self._records.values()
            )
            if active >= facts.concurrency_limit:
                return AcceptanceDecision(
                    AcceptanceStatus.CONCURRENCY_LIMIT_REACHED,
                    candidate.handoff_id, fingerprint,
                )
            if candidate.output_contract not in facts.accepted_output_contracts:
                return AcceptanceDecision(
                    AcceptanceStatus.OUTPUT_CONTRACT_REJECTED,
                    candidate.handoff_id, fingerprint,
                )
            if candidate.context_manifest_id not in facts.readable_context_manifests:
                return AcceptanceDecision(
                    AcceptanceStatus.CONTEXT_REJECTED,
                    candidate.handoff_id, fingerprint,
                )
            requested = set(candidate.requested_capabilities)
            if not requested <= set(facts.delegatable_capabilities):
                return AcceptanceDecision(
                    AcceptanceStatus.CAPABILITY_NOT_DELEGATABLE,
                    candidate.handoff_id, fingerprint,
                )
            if not requested <= set(facts.currently_allowed_capabilities):
                return AcceptanceDecision(
                    AcceptanceStatus.CAPABILITY_NOT_CURRENTLY_ALLOWED,
                    candidate.handoff_id, fingerprint,
                )
            if self.allocated_tokens + candidate.requested_tokens > (
                    self.parent_token_reservation):
                return AcceptanceDecision(
                    AcceptanceStatus.BUDGET_EXCEEDED,
                    candidate.handoff_id, fingerprint,
                )

            child_job_id = f"{candidate.parent_job_id}:child:{candidate.handoff_id}"
            child_attempt_id = f"{child_job_id}:attempt:1"
            grant = DelegationGrant(
                candidate.tenant_id, candidate.handoff_id, child_job_id,
                child_attempt_id, tuple(sorted(requested)),
                candidate.policy_version, candidate.deadline,
            )
            allocation = ChildAllocation(
                candidate.parent_job_id, candidate.handoff_id,
                candidate.requested_tokens,
            )
            outbox_intent = CoordinationOutboxIntent(
                f"handoff-dispatch:{candidate.handoff_id}",
                candidate.handoff_id, child_job_id, fingerprint,
            )
            record = HandoffRecord(
                candidate, fingerprint, child_job_id, child_attempt_id,
                grant, allocation, outbox_intent,
            )
            self._records[candidate.handoff_id] = record
            return AcceptanceDecision(
                AcceptanceStatus.ACCEPTED, candidate.handoff_id,
                fingerprint, record,
            )

    def mark_outbox_published(
        self, handoff_id: str, *, published_at: int,
    ) -> bool:
        """Record publish evidence without treating delivery as a claim."""
        with self._lock:
            record = self._records.get(handoff_id)
            if record is None:
                return False
            if record.outbox_intent.published_at is not None:
                return True
            intent = replace(record.outbox_intent, published_at=published_at)
            self._records[handoff_id] = replace(
                record, outbox_intent=intent,
            )
            return True

    def claim(
        self, handoff_id: str, *, worker_id: str, now: int,
        lease_duration: int,
    ) -> ClaimDecision:
        """Atomically claim accepted work; delivery alone grants nothing."""
        if lease_duration <= 0:
            raise ValueError("lease_duration must be positive")
        with self._lock:
            record = self._records.get(handoff_id)
            if record is None:
                return ClaimDecision(
                    ClaimStatus.HANDOFF_NOT_FOUND, handoff_id, None, None,
                )
            if record.state is HandoffState.CANCELLED:
                return ClaimDecision(
                    ClaimStatus.HANDOFF_NOT_CLAIMABLE, handoff_id,
                    record.claim_owner, record.fence_token,
                )
            if record.claim_owner is not None:
                status = (
                    ClaimStatus.DUPLICATE
                    if record.claim_owner == worker_id
                    else ClaimStatus.ALREADY_CLAIMED
                )
                return ClaimDecision(
                    status, handoff_id, record.claim_owner,
                    record.fence_token,
                )
            updated = replace(
                record, state=HandoffState.CLAIMED,
                state_version=record.state_version + 1,
                claim_owner=worker_id,
                lease_expires_at=now + lease_duration,
                fence_token=record.fence_token + 1,
            )
            self._records[handoff_id] = updated
            return ClaimDecision(
                ClaimStatus.CLAIMED, handoff_id, worker_id,
                updated.fence_token,
            )

    def take_over_expired_lease(
        self, handoff_id: str, *, worker_id: str, now: int,
        lease_duration: int,
    ) -> ClaimDecision:
        """Move ownership and fence only after the current lease expires."""
        if lease_duration <= 0:
            raise ValueError("lease_duration must be positive")
        with self._lock:
            record = self._records.get(handoff_id)
            if record is None:
                return ClaimDecision(
                    ClaimStatus.HANDOFF_NOT_FOUND, handoff_id, None, None,
                )
            if (record.claim_owner is None or record.lease_expires_at is None
                    or now < record.lease_expires_at):
                return ClaimDecision(
                    ClaimStatus.HANDOFF_NOT_CLAIMABLE, handoff_id,
                    record.claim_owner, record.fence_token,
                )
            updated = replace(
                record, state_version=record.state_version + 1,
                claim_owner=worker_id,
                lease_expires_at=now + lease_duration,
                fence_token=record.fence_token + 1,
            )
            self._records[handoff_id] = updated
            return ClaimDecision(
                ClaimStatus.CLAIMED, handoff_id, worker_id,
                updated.fence_token,
            )

    def authorize_provider_dispatch(
        self, handoff_id: str, *, worker_id: str, fence_token: int,
        required_capability: str, current_allowed_capabilities: tuple[str, ...],
        now: int,
    ) -> DispatchDecision:
        """Perform the final current checks without actually calling a Provider."""
        with self._lock:
            record = self._records.get(handoff_id)
            if record is None:
                return DispatchDecision(
                    DispatchStatus.HANDOFF_NOT_FOUND, handoff_id,
                )
            if record.state is not HandoffState.CLAIMED:
                return DispatchDecision(
                    DispatchStatus.HANDOFF_NOT_CLAIMED, handoff_id,
                )
            if record.fence_token != fence_token:
                return DispatchDecision(
                    DispatchStatus.STALE_FENCE, handoff_id,
                )
            if record.claim_owner != worker_id:
                return DispatchDecision(
                    DispatchStatus.NOT_CURRENT_OWNER, handoff_id,
                )
            if record.lease_expires_at is None or now >= record.lease_expires_at:
                return DispatchDecision(
                    DispatchStatus.LEASE_EXPIRED, handoff_id,
                )
            if (required_capability not in record.grant.capabilities
                    or required_capability not in current_allowed_capabilities):
                return DispatchDecision(
                    DispatchStatus.CURRENT_AUTHORIZATION_DENIED, handoff_id,
                )
            return DispatchDecision(DispatchStatus.ALLOWED, handoff_id)

    def record_provider_dispatch(
        self, handoff_id: str, *, worker_id: str, fence_token: int,
        required_capability: str, current_allowed_capabilities: tuple[str, ...],
        operation_id: str, now: int,
    ) -> DispatchDecision:
        """Conditionally persist dispatch identity; no external call occurs here."""
        with self._lock:
            decision = self.authorize_provider_dispatch(
                handoff_id, worker_id=worker_id, fence_token=fence_token,
                required_capability=required_capability,
                current_allowed_capabilities=current_allowed_capabilities,
                now=now,
            )
            if decision.status is not DispatchStatus.ALLOWED:
                return decision
            record = self._records[handoff_id]
            self._records[handoff_id] = replace(
                record, state=HandoffState.DISPATCHED,
                state_version=record.state_version + 1,
                operation_id=operation_id,
            )
            return decision

    def mark_outcome_unknown(
        self, handoff_id: str, *, operation_id: str,
    ) -> bool:
        """Keep the original operation and child allocation held for lookup."""
        with self._lock:
            record = self._records.get(handoff_id)
            if (record is None or record.state is not HandoffState.DISPATCHED
                    or record.operation_id != operation_id):
                return False
            self._records[handoff_id] = replace(
                record, state=HandoffState.PENDING_RECONCILIATION,
                state_version=record.state_version + 1,
            )
            return True

    def cancel(self, handoff_id: str) -> CancellationDecision:
        """Block unstarted work; dispatched work remains uncertain until verified."""
        with self._lock:
            record = self._records.get(handoff_id)
            if record is None:
                return CancellationDecision(
                    CancellationStatus.HANDOFF_NOT_FOUND, handoff_id, "NONE",
                )
            if record.state in {
                    HandoffState.CANCELLED, HandoffState.VERIFIED_COMPLETED}:
                return CancellationDecision(
                    CancellationStatus.TERMINAL_NOOP, handoff_id,
                    record.allocation.status,
                )
            if record.state in {HandoffState.ACCEPTED, HandoffState.CLAIMED}:
                allocation = replace(record.allocation, status="RELEASED")
                self._records[handoff_id] = replace(
                    record, state=HandoffState.CANCELLED,
                    state_version=record.state_version + 1,
                    cancellation_requested=True, allocation=allocation,
                )
                return CancellationDecision(
                    CancellationStatus.CANCELLED_BEFORE_DISPATCH,
                    handoff_id, allocation.status,
                )
            self._records[handoff_id] = replace(
                record, state=HandoffState.PENDING_RECONCILIATION,
                state_version=record.state_version + 1,
                cancellation_requested=True,
            )
            return CancellationDecision(
                CancellationStatus.COOPERATIVE_CANCELLATION_PENDING,
                handoff_id, record.allocation.status,
            )

    def verify_result(
        self, candidate: ChildResultCandidate, *,
        current_source_versions: tuple[tuple[str, int], ...],
    ) -> ResultVerificationDecision:
        """Turn a bound candidate into a fact only under current durable guards."""
        with self._lock:
            record = self._records.get(candidate.handoff_id)
            if record is None:
                return ResultVerificationDecision(
                    ResultVerificationStatus.HANDOFF_NOT_FOUND,
                    candidate.handoff_id, False,
                )
            status = ResultVerificationStatus.VERIFIED
            if self.parent_terminal:
                status = ResultVerificationStatus.PARENT_TERMINAL
            elif candidate.child_attempt_id != record.child_attempt_id:
                status = ResultVerificationStatus.CHILD_ATTEMPT_MISMATCH
            elif candidate.output_contract != record.candidate.output_contract:
                status = ResultVerificationStatus.OUTPUT_CONTRACT_MISMATCH
            elif (candidate.source_versions
                  != record.candidate.context_source_versions
                  or current_source_versions != candidate.source_versions):
                status = ResultVerificationStatus.SOURCE_VERSION_STALE
            elif candidate.fence_token != record.fence_token:
                status = ResultVerificationStatus.STALE_FENCE
            elif candidate.worker_id != record.claim_owner:
                status = ResultVerificationStatus.NOT_CURRENT_OWNER
            elif record.state is not HandoffState.DISPATCHED:
                status = ResultVerificationStatus.HANDOFF_NOT_READY

            applied = status is ResultVerificationStatus.VERIFIED
            self.result_evidence.append(ResultEvidence(candidate, status, applied))
            if applied:
                self._records[candidate.handoff_id] = replace(
                    record, state=HandoffState.VERIFIED_COMPLETED,
                    state_version=record.state_version + 1,
                )
            return ResultVerificationDecision(
                status, candidate.handoff_id, applied,
            )

    def aggregate(self) -> AggregationDecision:
        """Aggregate verified facts only; never authorize external publication."""
        with self._lock:
            records = tuple(self._records.values())
            required = tuple(item for item in records if item.candidate.required)
            optional = tuple(item for item in records if not item.candidate.required)
            required_verified = sum(
                item.state is HandoffState.VERIFIED_COMPLETED
                for item in required
            )
            optional_verified = sum(
                item.state is HandoffState.VERIFIED_COMPLETED
                for item in optional
            )
            failed = sum(item.state is HandoffState.FAILED for item in records)
            pending = sum(
                item.state is HandoffState.PENDING_RECONCILIATION
                for item in records
            )
            if self.parent_terminal:
                status = AggregationStatus.PARENT_TERMINAL
            elif required_verified != len(required):
                status = AggregationStatus.WAITING_FOR_REQUIRED
            else:
                verified = [
                    item.candidate
                    for item in self.result_evidence
                    if item.applied_to_current_state
                ]
                values: dict[str, set[str]] = {}
                for item in verified:
                    values.setdefault(item.fact_key, set()).add(item.fact_value)
                if any(len(items) > 1 for items in values.values()):
                    status = AggregationStatus.CONFLICT
                elif optional_verified != len(optional):
                    status = AggregationStatus.PARTIAL
                else:
                    status = AggregationStatus.READY
            return AggregationDecision(
                status, len(required), required_verified, len(optional),
                optional_verified, failed, pending, False,
            )
