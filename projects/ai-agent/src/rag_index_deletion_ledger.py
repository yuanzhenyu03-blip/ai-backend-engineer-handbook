"""Durable-intent mechanics for Day104 logical and physical deletion.

The implementation is a process-local transactional model.  A Tombstone is
application truth; Outbox delivery and Provider deletion are projections.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import threading

from rag_chunking_contracts import stable_hash
from rag_index_lifecycle_contracts import (
    DeletionEvidence,
    DeletionEvidenceScope,
    DeletionIntent,
    DeletionSnapshot,
    DeletionState,
    EvidenceStatus,
    InboxRecord,
    MessageState,
    OutboxEvent,
    parse_aware_datetime,
)


DEFAULT_TRUSTED_DELETION_VALIDATORS = frozenset(
    {
        ("day104-deletion-validator", "v1"),
    }
)


class DeletionOutcome(str, Enum):
    ACCEPTED = "ACCEPTED"
    EXACT_REPLAY = "EXACT_REPLAY"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    NOT_FOUND = "NOT_FOUND"
    DISPATCHED = "DISPATCHED"
    VERIFIED = "VERIFIED"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"


class InboxOutcome(str, Enum):
    APPLIED = "APPLIED"
    EXACT_REPLAY = "EXACT_REPLAY"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


@dataclass(frozen=True)
class DeletionResult:
    outcome: DeletionOutcome
    safe_reason: str
    intent: DeletionIntent | None = None
    snapshot: DeletionSnapshot | None = None
    durable_transition: bool = False


@dataclass(frozen=True)
class InboxResult:
    outcome: InboxOutcome
    safe_reason: str
    record: InboxRecord
    durable_transition: bool = False


class InMemoryDeletionLedger:
    """One-process teaching ledger; not a real durable database."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._intents: dict[str, DeletionIntent] = {}
        self._operation_bindings: dict[str, str] = {}
        self._idempotency_bindings: dict[tuple[str, str], str] = {}
        self._scope_revisions: dict[str, int] = {}
        self._tombstones: dict[str, set[str]] = {}
        self._snapshots: dict[str, DeletionSnapshot] = {}
        self._outbox: dict[str, OutboxEvent] = {}
        self._inbox: dict[str, InboxRecord] = {}
        self._evidence: dict[str, DeletionEvidence] = {}

    def read_intent(self, deletion_id: str) -> DeletionIntent | None:
        with self._lock:
            return self._intents.get(deletion_id)

    def read_snapshot(self, snapshot_id: str) -> DeletionSnapshot | None:
        with self._lock:
            return self._snapshots.get(snapshot_id)

    def read_inbox(self, event_id: str) -> InboxRecord | None:
        with self._lock:
            return self._inbox.get(event_id)

    def outbox_events(self) -> tuple[OutboxEvent, ...]:
        with self._lock:
            return tuple(self._outbox.values())

    def evidence(self) -> tuple[DeletionEvidence, ...]:
        with self._lock:
            return tuple(self._evidence.values())

    def current_snapshot(
        self,
        *,
        scope_id: str,
        created_at: str,
    ) -> DeletionSnapshot:
        with self._lock:
            return self._snapshot_locked(scope_id, created_at)

    def _snapshot_locked(
        self,
        scope_id: str,
        created_at: str,
    ) -> DeletionSnapshot:
        revision = self._scope_revisions.get(scope_id, 0)
        occurrence_ids = tuple(sorted(self._tombstones.get(scope_id, set())))
        snapshot_id = stable_hash(
            (
                "DELETION_SNAPSHOT",
                scope_id,
                revision,
                occurrence_ids,
            )
        )
        snapshot = DeletionSnapshot(
            deletion_snapshot_id=snapshot_id,
            scope_id=scope_id,
            ledger_revision=revision,
            occurrence_ids=occurrence_ids,
            created_at=created_at,
        )
        return self._snapshots.setdefault(snapshot_id, snapshot)


class DeletionLedgerCommitter:
    def __init__(
        self,
        store: InMemoryDeletionLedger,
        *,
        trusted_validators: frozenset[tuple[str, str]] = (
            DEFAULT_TRUSTED_DELETION_VALIDATORS
        ),
    ) -> None:
        if not trusted_validators or any(
            not validator_id.strip() or not validator_version.strip()
            for validator_id, validator_version in trusted_validators
        ):
            raise ValueError(
                "at least one complete trusted deletion validator is required"
            )
        self._store = store
        self._trusted_validators = trusted_validators

    def accept(self, intent: DeletionIntent) -> DeletionResult:
        if intent.state is not DeletionState.ACCEPTED:
            return DeletionResult(
                DeletionOutcome.IDENTITY_CONFLICT,
                "NEW_DELETION_INTENT_MUST_START_ACCEPTED",
            )
        store = self._store
        with store._lock:
            existing = store._intents.get(intent.deletion_id)
            operation_binding = store._operation_bindings.get(intent.operation_id)
            idempotency_key = (intent.scope_id, intent.idempotency_key)
            idempotency_binding = store._idempotency_bindings.get(idempotency_key)
            if existing is not None:
                bindings_are_complete = (
                    operation_binding == existing.deletion_id
                    and idempotency_binding == existing.deletion_id
                )
                if bindings_are_complete and self._same_intent_identity(
                    existing, intent
                ):
                    snapshot = store._snapshot_locked(
                        intent.scope_id,
                        intent.accepted_at,
                    )
                    return DeletionResult(
                        DeletionOutcome.EXACT_REPLAY,
                        "EXACT_DELETE_REPLAY_CONVERGED",
                        existing,
                        snapshot,
                    )
                return DeletionResult(
                    DeletionOutcome.IDENTITY_CONFLICT,
                    "DELETION_ID_OR_REPLAY_BINDINGS_CONFLICT",
                    existing,
                )
            if operation_binding is not None or idempotency_binding is not None:
                bound_ids = {
                    binding
                    for binding in (operation_binding, idempotency_binding)
                    if binding is not None
                }
                bound = (
                    store._intents.get(next(iter(bound_ids)))
                    if len(bound_ids) == 1
                    else None
                )
                return DeletionResult(
                    DeletionOutcome.IDENTITY_CONFLICT,
                    "DELETE_OPERATION_OR_IDEMPOTENCY_BINDING_CONFLICT",
                    bound,
                )
            revision = store._scope_revisions.get(intent.scope_id, 0) + 1
            store._scope_revisions[intent.scope_id] = revision
            store._tombstones.setdefault(intent.scope_id, set()).add(
                intent.occurrence_id
            )
            store._intents[intent.deletion_id] = intent
            store._operation_bindings[intent.operation_id] = intent.deletion_id
            store._idempotency_bindings[idempotency_key] = intent.deletion_id
            snapshot = store._snapshot_locked(
                intent.scope_id,
                intent.accepted_at,
            )
            event_id = stable_hash(
                (
                    "INDEX_DELETE_ACCEPTED",
                    intent.deletion_id,
                    revision,
                    intent.identity_digest,
                )
            )
            store._outbox[event_id] = OutboxEvent(
                event_id=event_id,
                event_type="INDEX_DELETE_ACCEPTED",
                aggregate_id=intent.deletion_id,
                aggregate_revision=revision,
                payload_digest=intent.identity_digest,
            )
            return DeletionResult(
                DeletionOutcome.ACCEPTED,
                "TOMBSTONE_INTENT_AND_OUTBOX_COMMITTED_ATOMICALLY",
                intent,
                snapshot,
                durable_transition=True,
            )

    def mark_dispatched(self, deletion_id: str) -> DeletionResult:
        store = self._store
        with store._lock:
            intent = store._intents.get(deletion_id)
            if intent is None:
                return DeletionResult(
                    DeletionOutcome.NOT_FOUND,
                    "DELETION_INTENT_NOT_FOUND",
                )
            if intent.state in {
                DeletionState.DISPATCHED,
                DeletionState.VERIFIED,
            }:
                return DeletionResult(
                    DeletionOutcome.DISPATCHED,
                    "DELETION_ALREADY_DISPATCHED",
                    intent,
                )
            updated = replace(intent, state=DeletionState.DISPATCHED)
            store._intents[deletion_id] = updated
            for event_id, event in tuple(store._outbox.items()):
                if event.aggregate_id == deletion_id:
                    store._outbox[event_id] = replace(
                        event,
                        state=MessageState.DISPATCHED,
                    )
            return DeletionResult(
                DeletionOutcome.DISPATCHED,
                "DELETE_OUTBOX_DISPATCH_RECORDED",
                updated,
                durable_transition=True,
            )

    def consume(
        self,
        *,
        event_id: str,
        payload_digest: str,
        source_stream: str,
        result_id: str,
        result_digest: str,
    ) -> InboxResult:
        store = self._store
        with store._lock:
            existing = store._inbox.get(event_id)
            if existing is not None:
                if existing.payload_digest == payload_digest:
                    return InboxResult(
                        InboxOutcome.EXACT_REPLAY,
                        "EXACT_INBOX_REPLAY_CONVERGED",
                        existing,
                    )
                return InboxResult(
                    InboxOutcome.IDENTITY_CONFLICT,
                    "EVENT_ID_ALREADY_BOUND_TO_OTHER_PAYLOAD",
                    existing,
                )
            record = InboxRecord(
                event_id=event_id,
                payload_digest=payload_digest,
                source_stream=source_stream,
                state=MessageState.APPLIED,
                result_id=result_id,
                result_digest=result_digest,
            )
            store._inbox[event_id] = record
            return InboxResult(
                InboxOutcome.APPLIED,
                "INBOX_AND_INTERNAL_RESULT_COMMITTED_ATOMICALLY",
                record,
                durable_transition=True,
            )

    def record_evidence(self, evidence: DeletionEvidence) -> DeletionOutcome:
        store = self._store
        with store._lock:
            snapshot = store._snapshots.get(evidence.deletion_snapshot_id)
            if snapshot is None:
                return DeletionOutcome.NOT_FOUND
            if (
                evidence.validator_id,
                evidence.validator_version,
            ) not in self._trusted_validators:
                return DeletionOutcome.IDENTITY_CONFLICT
            if evidence.tombstoned_occurrence_ids != snapshot.occurrence_ids:
                return DeletionOutcome.IDENTITY_CONFLICT
            relevant_policies = {
                intent.verification_policy_id
                for intent in store._intents.values()
                if (
                    intent.scope_id == snapshot.scope_id
                    and intent.occurrence_id in snapshot.occurrence_ids
                )
            }
            if evidence.verification_policy_id not in relevant_policies:
                return DeletionOutcome.IDENTITY_CONFLICT
            existing = store._evidence.get(evidence.evidence_id)
            if existing is not None:
                return (
                    DeletionOutcome.EXACT_REPLAY
                    if existing == evidence
                    else DeletionOutcome.IDENTITY_CONFLICT
                )
            store._evidence[evidence.evidence_id] = evidence
            return DeletionOutcome.ACCEPTED

    def verify(
        self,
        *,
        deletion_id: str,
    ) -> DeletionResult:
        store = self._store
        with store._lock:
            intent = store._intents.get(deletion_id)
            if intent is None:
                return DeletionResult(
                    DeletionOutcome.NOT_FOUND,
                    "DELETION_INTENT_NOT_FOUND",
                )
            if intent.state is DeletionState.VERIFIED:
                adopted_snapshot = store._snapshots.get(
                    intent.verified_deletion_snapshot_id or ""
                )
                return DeletionResult(
                    DeletionOutcome.VERIFIED,
                    "DELETION_ALREADY_VERIFIED_WITH_ADOPTED_EVIDENCE",
                    intent,
                    adopted_snapshot,
                )
            if intent.state is not DeletionState.DISPATCHED:
                return DeletionResult(
                    DeletionOutcome.EVIDENCE_INCOMPLETE,
                    "DELETION_MUST_BE_DISPATCHED_BEFORE_VERIFICATION",
                    intent,
                )
            snapshots = tuple(
                item
                for item in store._snapshots.values()
                if (
                    item.scope_id == intent.scope_id
                    and intent.occurrence_id in item.occurrence_ids
                )
            )
            if not snapshots:
                return DeletionResult(
                    DeletionOutcome.EVIDENCE_INCOMPLETE,
                    "TOMBSTONE_SNAPSHOT_NOT_FOUND",
                    intent,
                )
            latest = max(snapshots, key=lambda item: item.ledger_revision)
            latest_evidence: dict[DeletionEvidenceScope, DeletionEvidence] = {}
            for item in store._evidence.values():
                if (
                    item.deletion_snapshot_id != latest.deletion_snapshot_id
                    or item.verification_policy_id != intent.verification_policy_id
                    or (
                        item.validator_id,
                        item.validator_version,
                    )
                    not in self._trusted_validators
                    or item.tombstoned_occurrence_ids != latest.occurrence_ids
                ):
                    continue
                previous = latest_evidence.get(item.scope)
                item_time = parse_aware_datetime(
                    item.observed_at,
                    label="deletion evidence observed-at",
                )
                if previous is None:
                    latest_evidence[item.scope] = item
                    continue
                previous_time = parse_aware_datetime(
                    previous.observed_at,
                    label="deletion evidence observed-at",
                )
                if item_time > previous_time or (
                    item_time == previous_time
                    and item.evidence_id > previous.evidence_id
                ):
                    latest_evidence[item.scope] = item
            passing_scopes = {
                scope
                for scope, item in latest_evidence.items()
                if item.status is EvidenceStatus.PASS
            }
            required_scopes = set(intent.required_evidence_scopes)
            if not required_scopes.issubset(passing_scopes):
                return DeletionResult(
                    DeletionOutcome.EVIDENCE_INCOMPLETE,
                    "REQUIRED_DELETION_EVIDENCE_SCOPES_NOT_PASSED",
                    intent,
                    latest,
                )
            adopted = tuple(
                latest_evidence[scope] for scope in intent.required_evidence_scopes
            )
            adopted_ids = tuple(sorted(item.evidence_id for item in adopted))
            adopted_digest = stable_hash(
                tuple(
                    (item.scope.value, item.evidence_id, item.digest)
                    for item in adopted
                )
            )
            verified = replace(
                intent,
                state=DeletionState.VERIFIED,
                verified_deletion_snapshot_id=latest.deletion_snapshot_id,
                verified_evidence_ids=adopted_ids,
                verified_evidence_digest=adopted_digest,
            )
            store._intents[deletion_id] = verified
            return DeletionResult(
                DeletionOutcome.VERIFIED,
                "REQUIRED_DELETION_EVIDENCE_SCOPES_PASSED",
                verified,
                latest,
                durable_transition=True,
            )

    @staticmethod
    def _same_intent_identity(
        left: DeletionIntent,
        right: DeletionIntent,
    ) -> bool:
        return (
            left.deletion_id == right.deletion_id
            and left.operation_id == right.operation_id
            and left.idempotency_key == right.idempotency_key
            and left.scope_id == right.scope_id
            and left.occurrence_id == right.occurrence_id
            and left.source_version == right.source_version
            and left.intent_digest == right.intent_digest
            and left.verification_policy_id == right.verification_policy_id
            and left.required_evidence_scopes == right.required_evidence_scopes
            and left.accepted_at == right.accepted_at
        )
