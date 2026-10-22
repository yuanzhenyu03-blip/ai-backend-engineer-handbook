"""Sole Day97 metadata snapshot writer and in-memory transactional model."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import threading

from rag_chunking_contracts import stable_hash
from rag_metadata_contracts import (
    MetadataContract,
    MetadataProjectionAttempt,
    MetadataProjectionOperation,
    MetadataSnapshot,
    MetadataSnapshotPointer,
)
from rag_metadata_validator import MetadataValidationDecision
from rag_provenance import CurrentRAGProvenanceValidator, ProvenanceDecision


class MetadataCommitOutcome(str, Enum):
    COMMITTED = "COMMITTED"
    ALREADY_COMMITTED = "ALREADY_COMMITTED"
    NOT_READY = "NOT_READY"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    STALE_ATTEMPT = "STALE_ATTEMPT"
    STALE_INPUT = "STALE_INPUT"
    STALE_POINTER = "STALE_POINTER"


class MetadataRefreshOutcome(str, Enum):
    APPLIED = "APPLIED"
    DUPLICATE = "DUPLICATE"
    STALE = "STALE"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class MetadataProjectionClaim:
    operation: MetadataProjectionOperation
    attempt: MetadataProjectionAttempt
    revision: int
    fence: int


@dataclass(frozen=True)
class MetadataRefreshOutboxIntent:
    event_id: str
    tenant_id: str
    document_id: str
    document_version_id: str
    chunk_set_id: str
    snapshot_id: str
    snapshot_revision: int
    state: str = "PENDING"


@dataclass(frozen=True)
class MetadataCommitResult:
    outcome: MetadataCommitOutcome
    safe_reason: str
    snapshot: MetadataSnapshot | None = None
    pointer: MetadataSnapshotPointer | None = None
    durable_transition: bool = False


class InMemoryMetadataStore:
    """One lock models CAS plus snapshot/pointer/Outbox atomicity."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._operations: dict[str, MetadataProjectionOperation] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._claims: dict[str, MetadataProjectionClaim] = {}
        self._snapshots: dict[str, MetadataSnapshot] = {}
        self._result_keys: dict[str, str] = {}
        self._pointers: dict[
            tuple[str, str, str, str], MetadataSnapshotPointer
        ] = {}
        self._outbox: dict[str, MetadataRefreshOutboxIntent] = {}
        self._applied_events: set[str] = set()

    @staticmethod
    def pointer_key(
        operation: MetadataProjectionOperation,
    ) -> tuple[str, str, str, str]:
        return (
            operation.version.tenant_id,
            operation.version.document_id,
            operation.version.document_version_id,
            operation.chunk_set_id,
        )

    def read_snapshot(self, snapshot_id: str) -> MetadataSnapshot | None:
        with self._lock:
            return self._snapshots.get(snapshot_id)

    def read_pointer(
        self,
        operation: MetadataProjectionOperation,
    ) -> MetadataSnapshotPointer | None:
        with self._lock:
            return self._pointers.get(self.pointer_key(operation))

    def outbox_intents(self) -> tuple[MetadataRefreshOutboxIntent, ...]:
        with self._lock:
            return tuple(self._outbox.values())

    def apply_refresh(self, event_id: str) -> MetadataRefreshOutcome:
        """Treat delivery as a hint; reread current pointer before any effect."""

        with self._lock:
            intent = self._outbox.get(event_id)
            if intent is None:
                return MetadataRefreshOutcome.NOT_FOUND
            if event_id in self._applied_events:
                return MetadataRefreshOutcome.DUPLICATE
            key = (
                intent.tenant_id,
                intent.document_id,
                intent.document_version_id,
                intent.chunk_set_id,
            )
            current = self._pointers.get(key)
            if (
                current is None
                or current.snapshot_id != intent.snapshot_id
                or current.revision != intent.snapshot_revision
            ):
                return MetadataRefreshOutcome.STALE
            self._applied_events.add(event_id)
            self._outbox[event_id] = replace(intent, state="DISPATCHED")
            return MetadataRefreshOutcome.APPLIED


class MetadataCommitter:
    """Only component allowed to publish immutable MetadataSnapshot facts."""

    def __init__(
        self,
        *,
        store: InMemoryMetadataStore,
        provenance_validator: CurrentRAGProvenanceValidator,
    ) -> None:
        self._store = store
        self._provenance = provenance_validator

    def claim(
        self,
        operation: MetadataProjectionOperation,
        attempt: MetadataProjectionAttempt,
    ) -> MetadataProjectionClaim | None:
        if attempt.operation_id != operation.operation_id:
            return None
        provenance = self._provenance.evaluate(
            document=operation.version.document,
            expected_chunk_set_id=operation.chunk_set_id,
        )
        if not self._operation_matches_current(operation, provenance):
            return None
        store = self._store
        with store._lock:
            existing = store._operations.get(operation.operation_id)
            idempotency_key = (
                operation.version.tenant_id,
                operation.idempotency_key,
            )
            prior_operation = store._idempotency.get(idempotency_key)
            if existing is not None and existing != operation:
                return None
            if prior_operation not in (None, operation.operation_id):
                return None
            previous = store._claims.get(operation.operation_id)
            if previous is not None:
                if previous.attempt == attempt:
                    return previous
                if (
                    attempt.attempt_number
                    != previous.attempt.attempt_number + 1
                    or attempt.generation != previous.attempt.generation + 1
                    or attempt.request_id == previous.attempt.request_id
                ):
                    return None
            elif attempt.attempt_number != 1 or attempt.generation != 1:
                return None
            claim = MetadataProjectionClaim(
                operation,
                attempt,
                revision=1 if previous is None else previous.revision + 1,
                fence=1 if previous is None else previous.fence + 1,
            )
            store._operations[operation.operation_id] = operation
            store._idempotency[idempotency_key] = operation.operation_id
            store._claims[operation.operation_id] = claim
            return claim

    def persist(
        self,
        decision: MetadataValidationDecision,
        *,
        contract: MetadataContract,
    ) -> MetadataCommitResult:
        if not decision.ready or decision.candidate is None:
            return MetadataCommitResult(
                MetadataCommitOutcome.NOT_READY,
                "METADATA_CANDIDATE_NOT_READY",
            )
        candidate = decision.candidate
        operation = candidate.operation
        store = self._store
        with store._lock:
            claim = store._claims.get(operation.operation_id)
            if claim is None or claim.attempt != candidate.attempt:
                return MetadataCommitResult(
                    MetadataCommitOutcome.STALE_ATTEMPT,
                    "METADATA_ATTEMPT_GENERATION_STALE",
                )
            if operation.contract_fingerprint != contract.fingerprint:
                return MetadataCommitResult(
                    MetadataCommitOutcome.IDENTITY_CONFLICT,
                    "METADATA_CONTRACT_IDENTITY_CONFLICT",
                )
            provenance = self._provenance.evaluate(
                document=operation.version.document,
                expected_chunk_set_id=operation.chunk_set_id,
            )
            if not self._operation_matches_current(operation, provenance):
                return MetadataCommitResult(
                    MetadataCommitOutcome.STALE_INPUT,
                    "DAY95_OR_DAY96_CURRENT_INPUT_CHANGED",
                )

            existing_id = store._result_keys.get(operation.stable_result_key)
            if existing_id is not None:
                existing = store._snapshots[existing_id]
                if (
                    existing.assertions != candidate.assertions
                    or existing.contract_fingerprint != contract.fingerprint
                ):
                    return MetadataCommitResult(
                        MetadataCommitOutcome.IDENTITY_CONFLICT,
                        "SAME_METADATA_OPERATION_HAS_DIFFERENT_RESULT",
                    )
                pointer = store._pointers[store.pointer_key(operation)]
                return MetadataCommitResult(
                    MetadataCommitOutcome.ALREADY_COMMITTED,
                    "EXACT_METADATA_SNAPSHOT_ALREADY_COMMITTED",
                    existing,
                    pointer,
                )

            key = store.pointer_key(operation)
            previous = store._pointers.get(key)
            actual_id = None if previous is None else previous.snapshot_id
            actual_revision = 0 if previous is None else previous.revision
            if (
                actual_id != operation.expected_snapshot_id
                or actual_revision != operation.expected_snapshot_revision
            ):
                return MetadataCommitResult(
                    MetadataCommitOutcome.STALE_POINTER,
                    "METADATA_SNAPSHOT_BASELINE_CHANGED",
                    pointer=previous,
                )
            assertion_material = tuple(
                (
                    item.qualified_name,
                    item.value,
                    item.origin.value,
                    item.origin_reference,
                )
                for item in candidate.assertions
            )
            snapshot_id = "metadata:" + stable_hash((
                operation.stable_result_key,
                assertion_material,
            )).removeprefix("sha256:")
            snapshot = MetadataSnapshot(
                snapshot_id=snapshot_id,
                version=operation.version,
                chunk_set_id=operation.chunk_set_id,
                contract_version=contract.version,
                contract_fingerprint=contract.fingerprint,
                assertions=candidate.assertions,
                created_by_operation_id=operation.operation_id,
                selection_revision=operation.expected_selection_revision,
                document_state_version=operation.expected_document_state_version,
                document_fence=operation.expected_document_fence,
            )
            pointer = MetadataSnapshotPointer(
                tenant_id=operation.version.tenant_id,
                document_id=operation.version.document_id,
                document_version_id=operation.version.document_version_id,
                chunk_set_id=operation.chunk_set_id,
                snapshot_id=snapshot_id,
                revision=actual_revision + 1,
            )
            event_id = stable_hash((
                key,
                pointer.revision,
                snapshot_id,
            ))
            intent = MetadataRefreshOutboxIntent(
                event_id=event_id,
                tenant_id=pointer.tenant_id,
                document_id=pointer.document_id,
                document_version_id=pointer.document_version_id,
                chunk_set_id=pointer.chunk_set_id,
                snapshot_id=pointer.snapshot_id,
                snapshot_revision=pointer.revision,
            )
            store._snapshots[snapshot_id] = snapshot
            store._result_keys[operation.stable_result_key] = snapshot_id
            store._pointers[key] = pointer
            store._outbox[event_id] = intent
            return MetadataCommitResult(
                MetadataCommitOutcome.COMMITTED,
                "IMMUTABLE_METADATA_SNAPSHOT_COMMITTED",
                snapshot,
                pointer,
                durable_transition=True,
            )

    @staticmethod
    def _operation_matches_current(
        operation: MetadataProjectionOperation,
        provenance: ProvenanceDecision,
    ) -> bool:
        binding = provenance.binding
        return bool(
            provenance.valid
            and binding is not None
            and binding.version == operation.version
            and binding.chunk_set_id == operation.chunk_set_id
            and binding.selection_revision
            == operation.expected_selection_revision
            and binding.document_state_version
            == operation.expected_document_state_version
            and binding.document_fence == operation.expected_document_fence
        )
