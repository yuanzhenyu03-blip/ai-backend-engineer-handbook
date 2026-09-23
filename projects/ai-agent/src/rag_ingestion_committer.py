"""Day95 sole Ingestion Committer and deterministic teaching store.

The in-memory store models one guarded database transaction.  It proves application
control flow only; it is not evidence of PostgreSQL transaction isolation, object
storage atomicity, distributed fencing, or production durability.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import threading

from rag_ingestion_contracts import (
    CandidateValidationDecision,
    CandidateValidationOutcome,
    DocumentHeadSnapshot,
    DocumentHeadState,
    DocumentIdentity,
    DocumentVersionDefinition,
    DocumentVersionIdentity,
    IngestionOperationIdentity,
    ParsedArtifactDefinition,
    ParserAttemptIdentity,
    SourceArtifactReference,
)


class DocumentVersionLifecycle(str, Enum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    QUARANTINED = "QUARANTINED"
    TOMBSTONED = "TOMBSTONED"
    STALE_RESULT = "STALE_RESULT"


class IngestionOperationState(str, Enum):
    READY_FOR_DISPATCH = "READY_FOR_DISPATCH"
    PARSE_DISPATCH_STARTED = "PARSE_DISPATCH_STARTED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"
    PROVEN_NOT_EXECUTED = "PROVEN_NOT_EXECUTED"


class IngestionCommitOutcome(str, Enum):
    COMMITTED = "COMMITTED"
    ALREADY_COMMITTED = "ALREADY_COMMITTED"
    NOT_READY = "NOT_READY"
    BINDING_CONFLICT = "BINDING_CONFLICT"
    DOCUMENT_STALE = "DOCUMENT_STALE"
    VERSION_STALE = "VERSION_STALE"
    OPERATION_STALE = "OPERATION_STALE"
    ARTIFACT_CONFLICT = "ARTIFACT_CONFLICT"


class IngestionDispatchClaimOutcome(str, Enum):
    CLAIMED = "CLAIMED"
    ALREADY_CLAIMED = "ALREADY_CLAIMED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    STATE_CONFLICT = "STATE_CONFLICT"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    FENCE_CONFLICT = "FENCE_CONFLICT"
    ATTEMPT_SEQUENCE_CONFLICT = "ATTEMPT_SEQUENCE_CONFLICT"


class IngestionOperationTransitionOutcome(str, Enum):
    COMMITTED = "COMMITTED"
    ALREADY_COMMITTED = "ALREADY_COMMITTED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    STALE = "STALE"


class IngestionIntakeOutcome(str, Enum):
    CREATED = "CREATED"
    NEW_IMMUTABLE_VERSION = "NEW_IMMUTABLE_VERSION"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    DOCUMENT_TOMBSTONED = "DOCUMENT_TOMBSTONED"


@dataclass(frozen=True)
class DocumentVersionLifecycleRecord:
    definition: DocumentVersionDefinition
    state: DocumentVersionLifecycle
    parsed_artifact_id: str | None
    activation_commit_id: str | None
    state_version: int
    fence_token: int

    def __post_init__(self) -> None:
        if self.state_version < 0 or self.fence_token < 0:
            raise ValueError("version state version and fence must be non-negative")
        publication_facts_complete = bool(
            self.parsed_artifact_id and self.activation_commit_id
        )
        publication_facts_partial = bool(self.parsed_artifact_id) != bool(
            self.activation_commit_id
        )
        if publication_facts_partial:
            raise ValueError("publication facts must be complete or absent")
        requires_publication = self.state in {
            DocumentVersionLifecycle.ACTIVE,
            DocumentVersionLifecycle.SUPERSEDED,
        }
        forbids_publication = self.state in {
            DocumentVersionLifecycle.REGISTERED,
            DocumentVersionLifecycle.QUARANTINED,
            DocumentVersionLifecycle.STALE_RESULT,
        }
        if requires_publication and not publication_facts_complete:
            raise ValueError(
                "activated or superseded version requires publication facts"
            )
        if forbids_publication and publication_facts_complete:
            raise ValueError(
                "unpublished lifecycle state cannot carry publication facts"
            )


@dataclass(frozen=True)
class IngestionOperationRecord:
    identity: IngestionOperationIdentity
    state: IngestionOperationState
    state_version: int
    fence_token: int
    attempt: ParserAttemptIdentity | None
    attempt_history: tuple[ParserAttemptIdentity, ...] = ()

    def __post_init__(self) -> None:
        if self.state_version < 0 or self.fence_token < 0:
            raise ValueError("operation state version and fence must be non-negative")
        requires_attempt = self.state in {
            IngestionOperationState.PARSE_DISPATCH_STARTED,
            IngestionOperationState.PENDING_RECONCILIATION,
            IngestionOperationState.COMPLETED,
        }
        if requires_attempt and self.attempt is None:
            raise ValueError("dispatched ingestion state requires an attempt")
        attempt_numbers = tuple(
            item.attempt_number for item in self.attempt_history
        )
        parser_request_ids = tuple(
            item.parser_request_id for item in self.attempt_history
        )
        if len(set(attempt_numbers)) != len(attempt_numbers):
            raise ValueError("attempt history numbers must be unique")
        if len(set(parser_request_ids)) != len(parser_request_ids):
            raise ValueError("attempt history parser request ids must be unique")
        if any(
            item.operation_id != self.identity.operation_id
            or item.idempotency_key != self.identity.idempotency_key
            for item in self.attempt_history
        ):
            raise ValueError("attempt history must retain operation identity")


@dataclass(frozen=True)
class IngestionDispatchClaim:
    outcome: IngestionDispatchClaimOutcome
    record: IngestionOperationRecord | None = None
    durable_transition: bool = False

    @property
    def claimed(self) -> bool:
        return self.outcome is IngestionDispatchClaimOutcome.CLAIMED


@dataclass(frozen=True)
class IngestionOperationTransitionResult:
    outcome: IngestionOperationTransitionOutcome
    record: IngestionOperationRecord | None = None
    committer_calls: int = 1
    durable_transition: bool = False


@dataclass(frozen=True)
class IngestionIntakeResult:
    outcome: IngestionIntakeOutcome
    safe_reason: str
    document: DocumentHeadSnapshot | None = None
    version: DocumentVersionLifecycleRecord | None = None
    operation: IngestionOperationRecord | None = None
    source: SourceArtifactReference | None = None
    committer_calls: int = 1
    durable_transition: bool = False


@dataclass(frozen=True)
class IngestionActivationGuard:
    expected_document_state: DocumentHeadState
    expected_active_version_id: str | None
    expected_document_state_version: int
    expected_document_fence: int
    expected_version_state: DocumentVersionLifecycle
    expected_version_state_version: int
    expected_version_fence: int
    expected_operation_state: IngestionOperationState
    expected_operation_state_version: int
    expected_operation_fence: int

    def __post_init__(self) -> None:
        numeric_guards = (
            self.expected_document_state_version,
            self.expected_document_fence,
            self.expected_version_state_version,
            self.expected_version_fence,
            self.expected_operation_state_version,
            self.expected_operation_fence,
        )
        if any(value < 0 for value in numeric_guards):
            raise ValueError("activation guards must be non-negative")


@dataclass(frozen=True)
class IngestionLifecycleOutboxIntent:
    event_id: str
    event_type: str
    tenant_id: str
    document_id: str
    document_version_id: str
    operation_id: str
    published_at_epoch_ms: int | None = None


@dataclass(frozen=True)
class IngestionCommitResult:
    outcome: IngestionCommitOutcome
    safe_reason: str
    document: DocumentHeadSnapshot | None = None
    version: DocumentVersionLifecycleRecord | None = None
    operation: IngestionOperationRecord | None = None
    parsed_artifact: ParsedArtifactDefinition | None = None
    committer_calls: int = 1
    durable_transition: bool = False


class InMemoryIngestionLifecycleStore:
    """Process-local model of guarded lifecycle writes for deterministic tests."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._documents: dict[tuple[str, str], DocumentHeadSnapshot] = {}
        self._versions: dict[
            tuple[str, str, str], DocumentVersionLifecycleRecord
        ] = {}
        self._operations: dict[str, IngestionOperationRecord] = {}
        self._parsed_artifacts: dict[str, ParsedArtifactDefinition] = {}
        self._source_artifacts: dict[str, SourceArtifactReference] = {}
        self._operation_source_fingerprints: dict[str, tuple[str, int, str, str]] = {}
        self._idempotency_operations: dict[tuple[str, str], str] = {}
        self._document_fingerprints: dict[
            tuple[str, str, tuple[str, int, str, str]], str
        ] = {}
        self._outbox: dict[str, IngestionLifecycleOutboxIntent] = {}

    @staticmethod
    def _document_key(identity: DocumentIdentity) -> tuple[str, str]:
        return identity.tenant_id, identity.document_id

    @staticmethod
    def _version_key(
        identity: DocumentVersionIdentity,
    ) -> tuple[str, str, str]:
        return (
            identity.tenant_id,
            identity.document_id,
            identity.document_version_id,
        )

    def register(
        self,
        *,
        document: DocumentHeadSnapshot,
        version: DocumentVersionLifecycleRecord,
        operation: IngestionOperationRecord,
    ) -> None:
        """Seed already-established facts; never overwrite a conflicting identity."""

        if version.definition.identity.document != document.identity:
            raise ValueError("version does not belong to document head")
        if operation.identity.version != version.definition.identity:
            raise ValueError("operation does not belong to document version")
        if (
            operation.identity.source_artifact_id
            != version.definition.source_artifact_id
        ):
            raise ValueError("operation source does not bind document version")

        document_key = self._document_key(document.identity)
        version_key = self._version_key(version.definition.identity)
        with self._lock:
            current_document = self._documents.get(document_key)
            if current_document is not None and current_document != document:
                raise ValueError("conflicting document head registration")
            if version_key in self._versions:
                raise ValueError("document version is already registered")
            if operation.identity.operation_id in self._operations:
                raise ValueError("ingestion operation is already registered")
            self._documents.setdefault(document_key, document)
            self._versions[version_key] = version
            self._operations[operation.identity.operation_id] = operation

    def read_document(self, identity: DocumentIdentity) -> DocumentHeadSnapshot:
        with self._lock:
            return self._documents[self._document_key(identity)]

    def read_version(
        self, identity: DocumentVersionIdentity
    ) -> DocumentVersionLifecycleRecord:
        with self._lock:
            return self._versions[self._version_key(identity)]

    def read_operation(self, operation_id: str) -> IngestionOperationRecord:
        with self._lock:
            return self._operations[operation_id]

    def read_parsed_artifact(
        self, parsed_artifact_id: str
    ) -> ParsedArtifactDefinition | None:
        with self._lock:
            return self._parsed_artifacts.get(parsed_artifact_id)

    def claim_parse_dispatch(
        self,
        *,
        identity: IngestionOperationIdentity,
        attempt: ParserAttemptIdentity,
        expected_state: IngestionOperationState,
        expected_state_version: int,
        expected_fence: int,
    ) -> IngestionDispatchClaim:
        """Atomically persist the complete attempt before parser handoff."""

        with self._lock:
            current = self._operations.get(identity.operation_id)
            if current is None or current.identity != identity:
                return IngestionDispatchClaim(
                    IngestionDispatchClaimOutcome.IDENTITY_CONFLICT
                )
            if (
                attempt.operation_id != identity.operation_id
                or attempt.idempotency_key != identity.idempotency_key
            ):
                return IngestionDispatchClaim(
                    IngestionDispatchClaimOutcome.IDENTITY_CONFLICT,
                    current,
                )
            if (
                current.state is IngestionOperationState.PARSE_DISPATCH_STARTED
                and current.attempt == attempt
            ):
                return IngestionDispatchClaim(
                    IngestionDispatchClaimOutcome.ALREADY_CLAIMED,
                    current,
                )
            if current.state is not expected_state:
                return IngestionDispatchClaim(
                    IngestionDispatchClaimOutcome.STATE_CONFLICT,
                    current,
                )
            if current.state_version != expected_state_version:
                return IngestionDispatchClaim(
                    IngestionDispatchClaimOutcome.VERSION_CONFLICT,
                    current,
                )
            if current.fence_token != expected_fence:
                return IngestionDispatchClaim(
                    IngestionDispatchClaimOutcome.FENCE_CONFLICT,
                    current,
                )
            if current.attempt is not None and (
                attempt.attempt_number != current.attempt.attempt_number + 1
                or attempt.parser_request_id
                == current.attempt.parser_request_id
            ):
                return IngestionDispatchClaim(
                    IngestionDispatchClaimOutcome.ATTEMPT_SEQUENCE_CONFLICT,
                    current,
                )
            history = current.attempt_history
            if current.attempt is not None and current.attempt not in history:
                history += (current.attempt,)
            if attempt not in history:
                history += (attempt,)
            claimed = replace(
                current,
                state=IngestionOperationState.PARSE_DISPATCH_STARTED,
                state_version=current.state_version + 1,
                fence_token=current.fence_token + 1,
                attempt=attempt,
                attempt_history=history,
            )
            self._operations[identity.operation_id] = claimed
            return IngestionDispatchClaim(
                IngestionDispatchClaimOutcome.CLAIMED,
                claimed,
                durable_transition=True,
            )

    def outbox_intents(self) -> tuple[IngestionLifecycleOutboxIntent, ...]:
        with self._lock:
            return tuple(self._outbox.values())


class IngestionCommitter:
    """The sole writer for a validated document activation proposal."""

    def __init__(self, store: InMemoryIngestionLifecycleStore) -> None:
        self._store = store

    def register_intake(
        self,
        *,
        operation: IngestionOperationIdentity,
        version: DocumentVersionDefinition,
        source: SourceArtifactReference,
    ) -> IngestionIntakeResult:
        """Create initial lifecycle facts or converge an exact duplicate.

        Filename and object key never participate in logical identity.  The
        fingerprint proves equality of admitted source evidence under one parse
        contract; tenant and document bindings are checked independently.
        """

        if (
            operation.version != version.identity
            or source.version != version.identity
            or operation.source_artifact_id != source.source_artifact_id
            or version.source_artifact_id != source.source_artifact_id
            or version.created_by_operation_id != operation.operation_id
        ):
            return IngestionIntakeResult(
                IngestionIntakeOutcome.IDENTITY_CONFLICT,
                "INTAKE_DOCUMENT_VERSION_SOURCE_BINDING_CONFLICT",
            )

        store = self._store
        fingerprint = (
            source.checksum_sha256,
            source.size_bytes,
            source.detected_media_type,
            version.parse_contract_version,
        )
        document_key = store._document_key(version.identity.document)
        version_key = store._version_key(version.identity)
        idempotency_key = (operation.tenant_id, operation.idempotency_key)
        fingerprint_key = (
            operation.tenant_id,
            operation.document_id,
            fingerprint,
        )

        with store._lock:
            existing_operation = store._operations.get(operation.operation_id)
            if existing_operation is not None:
                existing_fingerprint = store._operation_source_fingerprints.get(
                    operation.operation_id
                )
                existing_version = store._versions.get(
                    store._version_key(existing_operation.identity.version)
                )
                existing_source = store._source_artifacts.get(
                    existing_operation.identity.source_artifact_id
                )
                if (
                    existing_operation.identity == operation
                    and existing_fingerprint == fingerprint
                    and existing_version is not None
                    and existing_version.definition == version
                    and existing_source == source
                ):
                    return IngestionIntakeResult(
                        IngestionIntakeOutcome.EXACT_DUPLICATE,
                        "EXACT_OPERATION_AND_SOURCE_FINGERPRINT_REUSED",
                        store._documents.get(document_key),
                        existing_version,
                        existing_operation,
                        existing_source,
                        durable_transition=False,
                    )
                return IngestionIntakeResult(
                    IngestionIntakeOutcome.IDENTITY_CONFLICT,
                    "OPERATION_ID_ALREADY_BINDS_DIFFERENT_INGESTION_INPUT",
                    operation=existing_operation,
                )

            existing_idempotent_operation_id = store._idempotency_operations.get(
                idempotency_key
            )
            if existing_idempotent_operation_id is not None:
                return IngestionIntakeResult(
                    IngestionIntakeOutcome.IDENTITY_CONFLICT,
                    "IDEMPOTENCY_KEY_ALREADY_BINDS_ANOTHER_OPERATION",
                    operation=store._operations[existing_idempotent_operation_id],
                )

            duplicate_operation_id = store._document_fingerprints.get(
                fingerprint_key
            )
            if duplicate_operation_id is not None:
                duplicate_operation = store._operations[duplicate_operation_id]
                duplicate_version = store._versions[
                    store._version_key(duplicate_operation.identity.version)
                ]
                duplicate_source = store._source_artifacts[
                    duplicate_operation.identity.source_artifact_id
                ]
                return IngestionIntakeResult(
                    IngestionIntakeOutcome.EXACT_DUPLICATE,
                    "DOCUMENT_SOURCE_AND_PARSE_CONTRACT_ALREADY_REGISTERED",
                    store._documents.get(document_key),
                    duplicate_version,
                    duplicate_operation,
                    duplicate_source,
                    durable_transition=False,
                )

            current_document = store._documents.get(document_key)
            if (
                current_document is not None
                and current_document.state is DocumentHeadState.TOMBSTONED
            ):
                return IngestionIntakeResult(
                    IngestionIntakeOutcome.DOCUMENT_TOMBSTONED,
                    "TOMBSTONED_DOCUMENT_REQUIRES_EXPLICIT_RESTORE_POLICY",
                    document=current_document,
                )
            if version_key in store._versions:
                return IngestionIntakeResult(
                    IngestionIntakeOutcome.IDENTITY_CONFLICT,
                    "DOCUMENT_VERSION_ID_IS_IMMUTABLE_AND_ALREADY_EXISTS",
                    document=current_document,
                    version=store._versions[version_key],
                )
            if source.source_artifact_id in store._source_artifacts:
                return IngestionIntakeResult(
                    IngestionIntakeOutcome.IDENTITY_CONFLICT,
                    "SOURCE_ARTIFACT_ID_IS_IMMUTABLE_AND_ALREADY_EXISTS",
                    document=current_document,
                )

            created_document = current_document or DocumentHeadSnapshot(
                identity=version.identity.document,
                state=DocumentHeadState.REGISTERED,
                active_version_id=None,
                state_version=0,
                fence_token=0,
            )
            created_version = DocumentVersionLifecycleRecord(
                definition=version,
                state=DocumentVersionLifecycle.REGISTERED,
                parsed_artifact_id=None,
                activation_commit_id=None,
                state_version=0,
                fence_token=0,
            )
            created_operation = IngestionOperationRecord(
                identity=operation,
                state=IngestionOperationState.READY_FOR_DISPATCH,
                state_version=0,
                fence_token=0,
                attempt=None,
            )
            store._documents[document_key] = created_document
            store._versions[version_key] = created_version
            store._operations[operation.operation_id] = created_operation
            store._source_artifacts[source.source_artifact_id] = source
            store._operation_source_fingerprints[operation.operation_id] = fingerprint
            store._idempotency_operations[idempotency_key] = operation.operation_id
            store._document_fingerprints[fingerprint_key] = operation.operation_id
            event = IngestionLifecycleOutboxIntent(
                event_id=f"ingestion-registered:{operation.operation_id}",
                event_type="INGESTION_REGISTERED",
                tenant_id=operation.tenant_id,
                document_id=operation.document_id,
                document_version_id=operation.document_version_id,
                operation_id=operation.operation_id,
            )
            store._outbox.setdefault(event.event_id, event)
            return IngestionIntakeResult(
                (
                    IngestionIntakeOutcome.CREATED
                    if current_document is None
                    else IngestionIntakeOutcome.NEW_IMMUTABLE_VERSION
                ),
                (
                    "DOCUMENT_AND_FIRST_IMMUTABLE_VERSION_REGISTERED"
                    if current_document is None
                    else "NEW_IMMUTABLE_DOCUMENT_VERSION_REGISTERED"
                ),
                created_document,
                created_version,
                created_operation,
                source,
                durable_transition=True,
            )

    def prepare_proven_not_executed_retry(
        self,
        *,
        identity: IngestionOperationIdentity,
        expected_state_version: int,
        expected_fence: int,
    ) -> IngestionOperationTransitionResult:
        """Durably admit a policy-approved retry without creating its attempt.

        The caller still has to run parser preflight.  Only after preflight may
        the orchestrator claim the fresh attempt and persist its dispatch marker.
        """

        store = self._store
        with store._lock:
            current = store._operations.get(identity.operation_id)
            if current is None or current.identity != identity:
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.IDENTITY_CONFLICT
                )
            if current.state is IngestionOperationState.READY_FOR_DISPATCH:
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.ALREADY_COMMITTED,
                    current,
                )
            if (
                current.state
                is not IngestionOperationState.PROVEN_NOT_EXECUTED
                or current.state_version != expected_state_version
                or current.fence_token != expected_fence
                or current.attempt is None
            ):
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.STALE,
                    current,
                )
            history = current.attempt_history
            if current.attempt not in history:
                history += (current.attempt,)
            ready = replace(
                current,
                state=IngestionOperationState.READY_FOR_DISPATCH,
                state_version=current.state_version + 1,
                fence_token=current.fence_token + 1,
                attempt_history=history,
            )
            event = IngestionLifecycleOutboxIntent(
                event_id=f"ingestion-retry-ready:{identity.operation_id}:"
                f"{ready.state_version}",
                event_type="INGESTION_RETRY_READY",
                tenant_id=identity.tenant_id,
                document_id=identity.document_id,
                document_version_id=identity.document_version_id,
                operation_id=identity.operation_id,
            )
            store._operations[identity.operation_id] = ready
            store._outbox.setdefault(event.event_id, event)
            return IngestionOperationTransitionResult(
                IngestionOperationTransitionOutcome.COMMITTED,
                ready,
                durable_transition=True,
            )

    def mark_pending_reconciliation(
        self,
        *,
        identity: IngestionOperationIdentity,
        expected_state_version: int,
        expected_fence: int,
    ) -> IngestionOperationTransitionResult:
        """Persist response-loss uncertainty without replaying the parser."""

        store = self._store
        with store._lock:
            current = store._operations.get(identity.operation_id)
            if current is None or current.identity != identity:
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.IDENTITY_CONFLICT
                )
            if current.state is IngestionOperationState.PENDING_RECONCILIATION:
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.ALREADY_COMMITTED,
                    current,
                )
            if (
                current.state is not IngestionOperationState.PARSE_DISPATCH_STARTED
                or current.state_version != expected_state_version
                or current.fence_token != expected_fence
            ):
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.STALE,
                    current,
                )
            pending = replace(
                current,
                state=IngestionOperationState.PENDING_RECONCILIATION,
                state_version=current.state_version + 1,
                fence_token=current.fence_token + 1,
            )
            event = IngestionLifecycleOutboxIntent(
                event_id=f"ingestion-reconcile:{identity.operation_id}",
                event_type="INGESTION_RECONCILIATION_REQUIRED",
                tenant_id=identity.tenant_id,
                document_id=identity.document_id,
                document_version_id=identity.document_version_id,
                operation_id=identity.operation_id,
            )
            store._operations[identity.operation_id] = pending
            store._outbox.setdefault(event.event_id, event)
            return IngestionOperationTransitionResult(
                IngestionOperationTransitionOutcome.COMMITTED,
                pending,
                durable_transition=True,
            )

    def mark_quarantined(
        self,
        *,
        identity: IngestionOperationIdentity,
        expected_state_version: int,
        expected_fence: int,
    ) -> IngestionOperationTransitionResult:
        """Fail closed after a definitive parser or candidate rejection."""

        store = self._store
        with store._lock:
            current = store._operations.get(identity.operation_id)
            if current is None or current.identity != identity:
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.IDENTITY_CONFLICT
                )
            if current.state is IngestionOperationState.QUARANTINED:
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.ALREADY_COMMITTED,
                    current,
                )
            if (
                current.state is not IngestionOperationState.PARSE_DISPATCH_STARTED
                or current.state_version != expected_state_version
                or current.fence_token != expected_fence
            ):
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.STALE,
                    current,
                )
            quarantined = replace(
                current,
                state=IngestionOperationState.QUARANTINED,
                state_version=current.state_version + 1,
                fence_token=current.fence_token + 1,
            )
            version_key = store._version_key(identity.version)
            current_version = store._versions.get(version_key)
            if (
                current_version is None
                or current_version.state is not DocumentVersionLifecycle.REGISTERED
            ):
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.STALE,
                    current,
                )
            quarantined_version = replace(
                current_version,
                state=DocumentVersionLifecycle.QUARANTINED,
                state_version=current_version.state_version + 1,
                fence_token=current_version.fence_token + 1,
            )
            event = IngestionLifecycleOutboxIntent(
                event_id=f"ingestion-quarantined:{identity.operation_id}",
                event_type="INGESTION_QUARANTINED",
                tenant_id=identity.tenant_id,
                document_id=identity.document_id,
                document_version_id=identity.document_version_id,
                operation_id=identity.operation_id,
            )
            store._operations[identity.operation_id] = quarantined
            store._versions[version_key] = quarantined_version
            store._outbox.setdefault(event.event_id, event)
            return IngestionOperationTransitionResult(
                IngestionOperationTransitionOutcome.COMMITTED,
                quarantined,
                durable_transition=True,
            )

    def tombstone_document(
        self,
        *,
        identity: DocumentIdentity,
        expected_document_state: DocumentHeadState,
        expected_document_state_version: int,
        expected_document_fence: int,
    ) -> IngestionCommitResult:
        """Publish unavailability while retaining source and parsed evidence.

        This is a lifecycle fact, not physical deletion.  Retention expiry and
        absence of published references are separate prerequisites for a future
        purge workflow outside Day95.
        """

        store = self._store
        with store._lock:
            document = store._documents.get(store._document_key(identity))
            if document is None:
                return IngestionCommitResult(
                    IngestionCommitOutcome.BINDING_CONFLICT,
                    "DOCUMENT_NOT_FOUND",
                )
            if document.state is DocumentHeadState.TOMBSTONED:
                return IngestionCommitResult(
                    IngestionCommitOutcome.ALREADY_COMMITTED,
                    "DOCUMENT_ALREADY_TOMBSTONED",
                    document=document,
                )
            if (
                document.state is not expected_document_state
                or document.state_version != expected_document_state_version
                or document.fence_token != expected_document_fence
            ):
                return IngestionCommitResult(
                    IngestionCommitOutcome.DOCUMENT_STALE,
                    "DOCUMENT_STATE_VERSION_OR_FENCE_CHANGED",
                    document=document,
                )

            active_version = None
            if document.active_version_id is not None:
                active_key = (
                    identity.tenant_id,
                    identity.document_id,
                    document.active_version_id,
                )
                active_version = store._versions.get(active_key)
                if (
                    active_version is None
                    or active_version.state is not DocumentVersionLifecycle.ACTIVE
                ):
                    return IngestionCommitResult(
                        IngestionCommitOutcome.VERSION_STALE,
                        "ACTIVE_POINTER_DOES_NOT_BIND_ACTIVE_VERSION",
                        document=document,
                        version=active_version,
                    )
                active_version = replace(
                    active_version,
                    state=DocumentVersionLifecycle.TOMBSTONED,
                    state_version=active_version.state_version + 1,
                    fence_token=active_version.fence_token + 1,
                )
                store._versions[active_key] = active_version

            tombstoned = replace(
                document,
                state=DocumentHeadState.TOMBSTONED,
                active_version_id=None,
                state_version=document.state_version + 1,
                fence_token=document.fence_token + 1,
            )
            event = IngestionLifecycleOutboxIntent(
                event_id=f"document-tombstoned:{identity.tenant_id}:"
                f"{identity.document_id}:{tombstoned.state_version}",
                event_type="DOCUMENT_TOMBSTONED",
                tenant_id=identity.tenant_id,
                document_id=identity.document_id,
                document_version_id=(
                    active_version.definition.identity.document_version_id
                    if active_version is not None
                    else "none"
                ),
                operation_id="lifecycle-tombstone",
            )
            store._documents[store._document_key(identity)] = tombstoned
            store._outbox.setdefault(event.event_id, event)
            return IngestionCommitResult(
                IngestionCommitOutcome.COMMITTED,
                "DOCUMENT_TOMBSTONE_PUBLISHED_EVIDENCE_RETAINED",
                document=tombstoned,
                version=active_version,
                durable_transition=True,
            )

    def commit_authoritative_reconciliation(
        self,
        *,
        identity: IngestionOperationIdentity,
        target_state: IngestionOperationState,
        expected_state_version: int,
        expected_fence: int,
    ) -> IngestionOperationTransitionResult:
        """Persist a terminal authoritative reconciliation fact.

        This method never schedules or performs a retry.  ``PROVEN_NOT_EXECUTED``
        becomes evidence that a separate retry policy may later evaluate.
        """

        if target_state not in {
            IngestionOperationState.FAILED,
            IngestionOperationState.PROVEN_NOT_EXECUTED,
        }:
            raise ValueError("unsupported authoritative reconciliation target")
        store = self._store
        with store._lock:
            current = store._operations.get(identity.operation_id)
            if current is None or current.identity != identity:
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.IDENTITY_CONFLICT
                )
            if current.state is target_state:
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.ALREADY_COMMITTED,
                    current,
                )
            if (
                current.state is not IngestionOperationState.PENDING_RECONCILIATION
                or current.state_version != expected_state_version
                or current.fence_token != expected_fence
            ):
                return IngestionOperationTransitionResult(
                    IngestionOperationTransitionOutcome.STALE,
                    current,
                )
            reconciled = replace(
                current,
                state=target_state,
                state_version=current.state_version + 1,
                fence_token=current.fence_token + 1,
            )
            event_type = (
                "INGESTION_PROVEN_NOT_EXECUTED"
                if target_state is IngestionOperationState.PROVEN_NOT_EXECUTED
                else "INGESTION_AUTHORITATIVE_FAILURE"
            )
            event = IngestionLifecycleOutboxIntent(
                event_id=f"{event_type.lower()}:{identity.operation_id}",
                event_type=event_type,
                tenant_id=identity.tenant_id,
                document_id=identity.document_id,
                document_version_id=identity.document_version_id,
                operation_id=identity.operation_id,
            )
            store._operations[identity.operation_id] = reconciled
            store._outbox.setdefault(event.event_id, event)
            return IngestionOperationTransitionResult(
                IngestionOperationTransitionOutcome.COMMITTED,
                reconciled,
                durable_transition=True,
            )

    def commit(
        self,
        decision: CandidateValidationDecision,
        *,
        guard: IngestionActivationGuard,
    ) -> IngestionCommitResult:
        if (
            decision.outcome is not CandidateValidationOutcome.READY_FOR_COMMIT
            or decision.proposal is None
        ):
            return IngestionCommitResult(
                IngestionCommitOutcome.NOT_READY,
                "VALIDATED_ACTIVATION_PROPOSAL_REQUIRED",
            )

        proposal = decision.proposal
        operation_identity = proposal.operation
        version_identity = operation_identity.version
        document_identity = version_identity.document
        artifact = proposal.parsed_artifact
        store = self._store

        with store._lock:
            document = store._documents.get(store._document_key(document_identity))
            version = store._versions.get(store._version_key(version_identity))
            operation = store._operations.get(operation_identity.operation_id)
            if document is None or version is None or operation is None:
                return IngestionCommitResult(
                    IngestionCommitOutcome.BINDING_CONFLICT,
                    "CURRENT_LIFECYCLE_FACTS_NOT_FOUND",
                )

            if not self._bindings_match(
                document=document,
                version=version,
                operation=operation,
                proposal_operation=operation_identity,
                proposal_attempt=proposal.attempt,
                artifact=artifact,
            ):
                return IngestionCommitResult(
                    IngestionCommitOutcome.BINDING_CONFLICT,
                    "ACTIVATION_PROPOSAL_BINDING_CONFLICT",
                    document,
                    version,
                    operation,
                )

            if self._already_committed(
                document=document,
                version=version,
                operation=operation,
                artifact=artifact,
            ):
                return IngestionCommitResult(
                    IngestionCommitOutcome.ALREADY_COMMITTED,
                    "ACTIVATION_ALREADY_COMMITTED",
                    document,
                    version,
                    operation,
                    artifact,
                )

            if not self._document_guard_matches(document, guard):
                return IngestionCommitResult(
                    IngestionCommitOutcome.DOCUMENT_STALE,
                    "DOCUMENT_STATE_VERSION_OR_FENCE_CHANGED",
                    document,
                    version,
                    operation,
                )
            if not self._version_guard_matches(version, guard):
                return IngestionCommitResult(
                    IngestionCommitOutcome.VERSION_STALE,
                    "DOCUMENT_VERSION_STATE_VERSION_OR_FENCE_CHANGED",
                    document,
                    version,
                    operation,
                )
            if not self._operation_guard_matches(operation, guard):
                return IngestionCommitResult(
                    IngestionCommitOutcome.OPERATION_STALE,
                    "INGESTION_OPERATION_STATE_VERSION_OR_FENCE_CHANGED",
                    document,
                    version,
                    operation,
                )

            existing_artifact = store._parsed_artifacts.get(
                artifact.parsed_artifact_id
            )
            if existing_artifact is not None and existing_artifact != artifact:
                return IngestionCommitResult(
                    IngestionCommitOutcome.ARTIFACT_CONFLICT,
                    "PARSED_ARTIFACT_IDENTITY_CONFLICT",
                    document,
                    version,
                    operation,
                )

            commit_id = (
                f"activate:{operation_identity.operation_id}:"
                f"{document.state_version + 1}"
            )
            previous_active_id = document.active_version_id
            if previous_active_id and previous_active_id != (
                version_identity.document_version_id
            ):
                previous_key = (
                    document_identity.tenant_id,
                    document_identity.document_id,
                    previous_active_id,
                )
                previous = store._versions.get(previous_key)
                if (
                    previous is None
                    or previous.state is not DocumentVersionLifecycle.ACTIVE
                ):
                    return IngestionCommitResult(
                        IngestionCommitOutcome.BINDING_CONFLICT,
                        "ACTIVE_POINTER_DOES_NOT_BIND_AN_ACTIVE_VERSION",
                        document,
                        version,
                        operation,
                    )
                store._versions[previous_key] = replace(
                    previous,
                    state=DocumentVersionLifecycle.SUPERSEDED,
                    state_version=previous.state_version + 1,
                    fence_token=previous.fence_token + 1,
                )

            committed_version = replace(
                version,
                state=DocumentVersionLifecycle.ACTIVE,
                parsed_artifact_id=artifact.parsed_artifact_id,
                activation_commit_id=commit_id,
                state_version=version.state_version + 1,
                fence_token=version.fence_token + 1,
            )
            committed_document = replace(
                document,
                state=DocumentHeadState.ACTIVE,
                active_version_id=version_identity.document_version_id,
                state_version=document.state_version + 1,
                fence_token=document.fence_token + 1,
            )
            committed_operation = replace(
                operation,
                state=IngestionOperationState.COMPLETED,
                state_version=operation.state_version + 1,
                fence_token=operation.fence_token + 1,
            )
            event = IngestionLifecycleOutboxIntent(
                event_id=f"document-version-active:{operation_identity.operation_id}",
                event_type="DOCUMENT_VERSION_ACTIVATED",
                tenant_id=operation_identity.tenant_id,
                document_id=operation_identity.document_id,
                document_version_id=operation_identity.document_version_id,
                operation_id=operation_identity.operation_id,
            )

            # One modeled transaction: all assignments occur while holding the same
            # store lock and after every guard has passed.
            store._parsed_artifacts.setdefault(artifact.parsed_artifact_id, artifact)
            store._versions[store._version_key(version_identity)] = committed_version
            store._documents[store._document_key(document_identity)] = (
                committed_document
            )
            store._operations[operation_identity.operation_id] = committed_operation
            store._outbox.setdefault(event.event_id, event)

            return IngestionCommitResult(
                IngestionCommitOutcome.COMMITTED,
                "DOCUMENT_VERSION_ACTIVATED",
                committed_document,
                committed_version,
                committed_operation,
                artifact,
                durable_transition=True,
            )

    @staticmethod
    def _bindings_match(
        *,
        document: DocumentHeadSnapshot,
        version: DocumentVersionLifecycleRecord,
        operation: IngestionOperationRecord,
        proposal_operation: IngestionOperationIdentity,
        proposal_attempt: ParserAttemptIdentity,
        artifact: ParsedArtifactDefinition,
    ) -> bool:
        return (
            document.identity == proposal_operation.version.document
            and version.definition.identity == proposal_operation.version
            and version.definition.source_artifact_id
            == proposal_operation.source_artifact_id
            and operation.identity == proposal_operation
            and operation.attempt == proposal_attempt
            and artifact.version == proposal_operation.version
            and artifact.source_artifact_id
            == proposal_operation.source_artifact_id
            and artifact.manifest.operation_id == proposal_operation.operation_id
            and artifact.manifest.idempotency_key
            == proposal_operation.idempotency_key
        )

    @staticmethod
    def _already_committed(
        *,
        document: DocumentHeadSnapshot,
        version: DocumentVersionLifecycleRecord,
        operation: IngestionOperationRecord,
        artifact: ParsedArtifactDefinition,
    ) -> bool:
        return (
            document.state is DocumentHeadState.ACTIVE
            and document.active_version_id
            == version.definition.identity.document_version_id
            and version.state is DocumentVersionLifecycle.ACTIVE
            and version.parsed_artifact_id == artifact.parsed_artifact_id
            and operation.state is IngestionOperationState.COMPLETED
        )

    @staticmethod
    def _document_guard_matches(
        document: DocumentHeadSnapshot,
        guard: IngestionActivationGuard,
    ) -> bool:
        return (
            document.state is guard.expected_document_state
            and document.active_version_id == guard.expected_active_version_id
            and document.state_version
            == guard.expected_document_state_version
            and document.fence_token == guard.expected_document_fence
        )

    @staticmethod
    def _version_guard_matches(
        version: DocumentVersionLifecycleRecord,
        guard: IngestionActivationGuard,
    ) -> bool:
        return (
            version.state is guard.expected_version_state
            and version.state_version == guard.expected_version_state_version
            and version.fence_token == guard.expected_version_fence
        )

    @staticmethod
    def _operation_guard_matches(
        operation: IngestionOperationRecord,
        guard: IngestionActivationGuard,
    ) -> bool:
        return (
            operation.state is guard.expected_operation_state
            and operation.state_version
            == guard.expected_operation_state_version
            and operation.fence_token == guard.expected_operation_fence
        )
