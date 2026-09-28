"""Sole Day96 writer with an in-memory transactional classroom store.

The shared in-process locks model conditional writes and recovery decisions. They
do not establish distributed transactions, multi-process fencing, or production
durability. The Day95 lifecycle itself is never mutated by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import threading

from rag_chunking_contracts import (
    Chunk,
    ChunkSet,
    ChunkSetCandidate,
    ChunkingAttemptIdentity,
    ChunkingContract,
    ChunkingOperationIdentity,
    stable_hash,
)
from rag_chunking_validator import ChunkSetCandidateValidator, ChunkValidationDecision
from rag_document_lifecycle import evaluate_day96_chunking_eligibility
from rag_ingestion_committer import InMemoryIngestionLifecycleStore
from rag_ingestion_contracts import DocumentIdentity, sha256_text


class ChunkCommitOutcome(str, Enum):
    COMMITTED = "COMMITTED"
    ALREADY_COMMITTED = "ALREADY_COMMITTED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    NOT_READY = "NOT_READY"
    STALE_ATTEMPT = "STALE_ATTEMPT"
    STALE_DAY95_INPUT = "STALE_DAY95_INPUT"
    NOT_FOUND = "NOT_FOUND"


class SelectionOutcome(str, Enum):
    SELECTED = "SELECTED"
    ALREADY_SELECTED = "ALREADY_SELECTED"
    STALE_SELECTION = "STALE_SELECTION"
    STALE_DAY95_INPUT = "STALE_DAY95_INPUT"
    STALE_ATTEMPT = "STALE_ATTEMPT"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class ChunkingClaim:
    operation: ChunkingOperationIdentity
    attempt: ChunkingAttemptIdentity
    revision: int
    fence: int


@dataclass(frozen=True)
class ChunkSelection:
    tenant_id: str
    document_id: str
    document_version_id: str
    chunk_set_id: str
    revision: int
    fence: int


@dataclass(frozen=True)
class ChunkSelectionOutboxIntent:
    event_id: str
    tenant_id: str
    document_id: str
    document_version_id: str
    chunk_set_id: str
    selection_revision: int
    state: str = "PENDING"


@dataclass(frozen=True)
class ChunkCommitResult:
    outcome: ChunkCommitOutcome
    safe_reason: str
    chunk_set: ChunkSet | None = None
    durable_transition: bool = False


@dataclass(frozen=True)
class ChunkSelectionResult:
    outcome: SelectionOutcome
    safe_reason: str
    selection: ChunkSelection | None = None
    durable_transition: bool = False


class InMemoryChunkSetStore:
    """One in-process lock protects Day96 identities, facts, and outbox intent."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._operations: dict[str, ChunkingOperationIdentity] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._claims: dict[str, ChunkingClaim] = {}
        self._sets: dict[str, ChunkSet] = {}
        self._result_keys: dict[str, str] = {}
        self._selections: dict[tuple[str, str], ChunkSelection] = {}
        self._outbox: dict[str, ChunkSelectionOutboxIntent] = {}

    def read_chunk_set(self, chunk_set_id: str) -> ChunkSet | None:
        with self._lock:
            return self._sets.get(chunk_set_id)

    def read_selection(self, identity: DocumentIdentity) -> ChunkSelection | None:
        with self._lock:
            return self._selections.get((identity.tenant_id, identity.document_id))

    def read_claim(self, operation_id: str) -> ChunkingClaim | None:
        with self._lock:
            return self._claims.get(operation_id)

    def outbox_intents(self) -> tuple[ChunkSelectionOutboxIntent, ...]:
        with self._lock:
            return tuple(self._outbox.values())

    def pending_outbox_intents(self) -> tuple[ChunkSelectionOutboxIntent, ...]:
        with self._lock:
            return tuple(
                intent
                for intent in self._outbox.values()
                if intent.state == "PENDING"
            )

    def mark_outbox_dispatched(self, event_id: str) -> bool:
        """Acknowledge delivery only after an external dispatcher returns."""

        with self._lock:
            current = self._outbox.get(event_id)
            if current is None:
                return False
            if current.state == "DISPATCHED":
                return True
            self._outbox[event_id] = replace(current, state="DISPATCHED")
            return True


class ChunkSetCommitter:
    """Only component permitted to establish ChunkSet and selection facts."""

    def __init__(
        self,
        *,
        day95_store: InMemoryIngestionLifecycleStore,
        chunk_store: InMemoryChunkSetStore,
        validator: ChunkSetCandidateValidator,
    ) -> None:
        self._day95 = day95_store
        self._store = chunk_store
        self._validator = validator

    def claim(
        self,
        operation: ChunkingOperationIdentity,
        attempt: ChunkingAttemptIdentity,
    ) -> ChunkingClaim | None:
        """Conditionally claim a fresh attempt; None means conflict or stale."""

        store = self._store
        if attempt.operation_id != operation.operation_id:
            return None
        with self._day95._lock, store._lock:
            try:
                document = self._day95.read_document(operation.version.document)
                version = self._day95.read_version(operation.version)
                ingestion = self._day95.read_operation(
                    version.definition.created_by_operation_id
                )
            except KeyError:
                return None
            eligibility = evaluate_day96_chunking_eligibility(
                document=document, version=version, operation=ingestion
            )
            parsed = self._day95.read_parsed_artifact(
                operation.parsed_artifact_id
            )
            source = self._day95.read_source_artifact(
                operation.source_artifact_id
            )
            if (
                not eligibility.eligible
                or eligibility.parsed_artifact_id != operation.parsed_artifact_id
                or parsed is None
                or source is None
                or parsed.version != operation.version
                or source.version != operation.version
                or parsed.source_artifact_id != source.source_artifact_id
                or parsed.manifest.source_checksum_sha256
                != source.checksum_sha256
                or parsed.source_artifact_id
                != version.definition.source_artifact_id
                or parsed.manifest.tenant_id != operation.version.tenant_id
                or parsed.manifest.document_id != operation.version.document_id
                or parsed.manifest.document_version_id
                != operation.version.document_version_id
                or parsed.manifest.source_artifact_id
                != operation.source_artifact_id
                or parsed.manifest.operation_id
                != ingestion.identity.operation_id
                or parsed.manifest.idempotency_key
                != ingestion.identity.idempotency_key
                or parsed.manifest.parse_contract_version
                != version.definition.parse_contract_version
                or ingestion.identity.version != operation.version
                or ingestion.identity.source_artifact_id
                != operation.source_artifact_id
                or ingestion.attempt is None
                or parsed.manifest.attempt_number
                != ingestion.attempt.attempt_number
                or parsed.manifest.parser_request_id
                != ingestion.attempt.parser_request_id
                or parsed.manifest.parser_generation
                != ingestion.attempt.parser_generation
                or parsed.output_checksum_sha256
                != sha256_text(parsed.canonical_text)
                or parsed.manifest.output_checksum_sha256
                != parsed.output_checksum_sha256
            ):
                return None
            existing = store._operations.get(operation.operation_id)
            idempotency_key = (
                operation.version.tenant_id, operation.idempotency_key
            )
            prior_operation_id = store._idempotency.get(idempotency_key)
            if existing is not None and existing != operation:
                return None
            if prior_operation_id not in (None, operation.operation_id):
                return None
            previous = store._claims.get(operation.operation_id)
            if previous is not None:
                if attempt == previous.attempt:
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
            claim = ChunkingClaim(
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
        decision: ChunkValidationDecision,
        *,
        contract: ChunkingContract,
    ) -> ChunkCommitResult:
        """Recheck Day95 and all candidate evidence before atomic insertion."""

        if not decision.ready or decision.candidate is None:
            return ChunkCommitResult(
                ChunkCommitOutcome.NOT_READY, "CANDIDATE_NOT_READY"
            )
        candidate = decision.candidate
        operation = candidate.operation
        store = self._store
        # Both are in-memory teaching stores. Shared locking is not a production
        # substitute for one transactional durable authority.
        with self._day95._lock, store._lock:
            current_claim = store._claims.get(operation.operation_id)
            if current_claim is None or current_claim.attempt != candidate.attempt:
                return ChunkCommitResult(
                    ChunkCommitOutcome.STALE_ATTEMPT,
                    "CHUNKING_ATTEMPT_GENERATION_STALE",
                )
            try:
                document = self._day95.read_document(operation.version.document)
                version = self._day95.read_version(operation.version)
                ingestion = self._day95.read_operation(
                    version.definition.created_by_operation_id
                )
            except KeyError:
                return ChunkCommitResult(
                    ChunkCommitOutcome.STALE_DAY95_INPUT,
                    "DAY95_LIFECYCLE_FACT_MISSING",
                )
            parsed = self._day95.read_parsed_artifact(operation.parsed_artifact_id)
            source = self._day95.read_source_artifact(
                operation.source_artifact_id
            )
            if parsed is None or source is None:
                return ChunkCommitResult(
                    ChunkCommitOutcome.STALE_DAY95_INPUT,
                    "DAY95_SOURCE_OR_PARSED_ARTIFACT_MISSING",
                )
            refreshed = self._validator.evaluate(
                document=document,
                version=version,
                ingestion=ingestion,
                parsed=parsed,
                source=source,
                contract=contract,
                candidate=candidate,
            )
            if not refreshed.ready:
                return ChunkCommitResult(
                    ChunkCommitOutcome.STALE_DAY95_INPUT,
                    refreshed.safe_reason,
                )
            existing_id = store._result_keys.get(operation.stable_result_key)
            if existing_id is not None:
                existing_set = store._sets[existing_id]
                if (
                    existing_set.manifest != candidate.manifest
                    or existing_set.operation.contract_fingerprint
                    != operation.contract_fingerprint
                ):
                    return ChunkCommitResult(
                        ChunkCommitOutcome.IDENTITY_CONFLICT,
                        "SAME_RESULT_IDENTITY_HAS_DIFFERENT_MANIFEST",
                    )
                return ChunkCommitResult(
                    ChunkCommitOutcome.ALREADY_COMMITTED,
                    "EXACT_CHUNK_SET_ALREADY_COMMITTED",
                    existing_set,
                )
            chunk_set_id = "chunk-set:" + operation.stable_result_key.removeprefix(
                "sha256:"
            )
            chunks = tuple(
                Chunk(
                    chunk_id="chunk:" + stable_hash((
                        chunk_set_id,
                        item.ordinal,
                        tuple((s.start, s.end, s.role) for s in item.source_segments),
                    )).removeprefix("sha256:"),
                    chunk_set_id=chunk_set_id,
                    candidate=item,
                )
                for item in candidate.chunks
            )
            chunk_set = ChunkSet(
                chunk_set_id,
                operation,
                candidate.experiment_id,
                candidate.manifest,
                chunks,
            )
            store._sets[chunk_set_id] = chunk_set
            store._result_keys[operation.stable_result_key] = chunk_set_id
            return ChunkCommitResult(
                ChunkCommitOutcome.COMMITTED,
                "IMMUTABLE_CHUNK_SET_COMMITTED",
                chunk_set,
                durable_transition=True,
            )

    def select(
        self,
        *,
        chunk_set_id: str,
        expected_selected_id: str | None,
        expected_selection_revision: int,
        expected_document_state_version: int,
        expected_document_fence: int,
        claim: ChunkingClaim,
    ) -> ChunkSelectionResult:
        """Conditional selection and outbox insertion in one modeled transaction."""

        store = self._store
        with self._day95._lock, store._lock:
            chunk_set = store._sets.get(chunk_set_id)
            if chunk_set is None:
                return ChunkSelectionResult(
                    SelectionOutcome.NOT_FOUND, "CHUNK_SET_NOT_FOUND"
                )
            operation = chunk_set.operation
            if (
                claim.operation.stable_result_key != operation.stable_result_key
                or store._claims.get(claim.operation.operation_id) != claim
            ):
                return ChunkSelectionResult(
                    SelectionOutcome.STALE_ATTEMPT, "CHUNKING_CLAIM_FENCE_STALE"
                )
            try:
                document = self._day95.read_document(operation.version.document)
                version = self._day95.read_version(operation.version)
                ingestion = self._day95.read_operation(
                    version.definition.created_by_operation_id
                )
            except KeyError:
                return ChunkSelectionResult(
                    SelectionOutcome.STALE_DAY95_INPUT, "DAY95_LIFECYCLE_FACT_MISSING"
                )
            eligibility = evaluate_day96_chunking_eligibility(
                document=document, version=version, operation=ingestion
            )
            parsed = self._day95.read_parsed_artifact(
                operation.parsed_artifact_id
            )
            source = self._day95.read_source_artifact(
                operation.source_artifact_id
            )
            if (
                not eligibility.eligible
                or eligibility.parsed_artifact_id != operation.parsed_artifact_id
                or parsed is None
                or source is None
                or parsed.output_checksum_sha256
                != sha256_text(parsed.canonical_text)
                or parsed.manifest.source_checksum_sha256
                != source.checksum_sha256
                or document.state_version != expected_document_state_version
                or document.fence_token != expected_document_fence
            ):
                return ChunkSelectionResult(
                    SelectionOutcome.STALE_DAY95_INPUT,
                    "DAY95_ACTIVE_VERSION_OR_FENCE_CHANGED",
                )
            key = (operation.version.tenant_id, operation.version.document_id)
            previous = store._selections.get(key)
            if previous is not None and previous.chunk_set_id == chunk_set_id:
                return ChunkSelectionResult(
                    SelectionOutcome.ALREADY_SELECTED,
                    "CHUNK_SET_ALREADY_SELECTED",
                    previous,
                )
            actual_id = None if previous is None else previous.chunk_set_id
            actual_revision = 0 if previous is None else previous.revision
            if (
                actual_id != expected_selected_id
                or actual_revision != expected_selection_revision
            ):
                return ChunkSelectionResult(
                    SelectionOutcome.STALE_SELECTION,
                    "SELECTED_CHUNK_SET_BASELINE_CHANGED",
                    previous,
                )
            selection = ChunkSelection(
                operation.version.tenant_id,
                operation.version.document_id,
                operation.version.document_version_id,
                chunk_set_id,
                revision=actual_revision + 1,
                fence=claim.fence,
            )
            event_id = stable_hash((key, selection.revision, chunk_set_id))
            outbox = ChunkSelectionOutboxIntent(
                event_id,
                selection.tenant_id,
                selection.document_id,
                selection.document_version_id,
                chunk_set_id,
                selection.revision,
            )
            store._selections[key] = selection
            store._outbox[event_id] = outbox
            return ChunkSelectionResult(
                SelectionOutcome.SELECTED,
                "CHUNK_SET_SELECTED_WITH_OUTBOX_INTENT",
                selection,
                durable_transition=True,
            )
