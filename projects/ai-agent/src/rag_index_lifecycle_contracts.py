"""Application-owned Day104 index lifecycle value contracts.

The contracts in this module deliberately contain no database or vector-store
objects.  They separate immutable generation artifacts from mutable lifecycle
facts, bind every release decision to explicit evidence, and keep protected
content out of control-plane records.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum

from rag_chunking_contracts import stable_hash


def _require_non_empty(*values: str) -> None:
    if not all(value.strip() for value in values):
        raise ValueError("complete non-empty identity bindings are required")


def _require_canonical_ids(
    values: tuple[str, ...],
    *,
    label: str,
    allow_empty: bool = False,
) -> None:
    if not allow_empty and not values:
        raise ValueError(f"{label} cannot be empty")
    if any(not value.strip() for value in values):
        raise ValueError(f"{label} cannot contain empty identities")
    if values != tuple(sorted(values)) or len(set(values)) != len(values):
        raise ValueError(f"{label} must be sorted and unique")


def parse_aware_datetime(value: str, *, label: str) -> datetime:
    """Parse an ISO-8601 timestamp and reject timezone-ambiguous values."""

    _require_non_empty(value)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include an explicit UTC offset")
    return parsed


class GenerationState(str, Enum):
    BUILDING = "BUILDING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    RETIRED = "RETIRED"
    FAILED = "FAILED"


class ValidationDecision(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    STALE = "STALE"


class EvaluationDecision(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class ActivationDecision(str, Enum):
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"


class ReadViewStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"


class DeletionState(str, Enum):
    ACCEPTED = "ACCEPTED"
    DISPATCHED = "DISPATCHED"
    VERIFIED = "VERIFIED"


class DeletionEvidenceScope(str, Enum):
    LOGICAL_RELEASE = "LOGICAL_RELEASE"
    SERVING_INDEX_ABSENCE = "SERVING_INDEX_ABSENCE"
    PHYSICAL_PURGE = "PHYSICAL_PURGE"


class EvidenceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"


class MessageState(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    APPLIED = "APPLIED"
    DISPATCHED = "DISPATCHED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ImmutableBinding:
    """An immutable object identity plus its canonical digest."""

    identity: str
    digest: str

    def __post_init__(self) -> None:
        _require_non_empty(self.identity, self.digest)


@dataclass(frozen=True)
class EvaluationRuler:
    """Frozen Day103 dataset, evaluator and release-policy identity."""

    dataset_fingerprint: str
    evaluator_fingerprint: str
    policy_fingerprint: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.dataset_fingerprint,
            self.evaluator_fingerprint,
            self.policy_fingerprint,
        )

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class BuildSnapshot:
    """Point-in-time identity frozen before a generation build begins."""

    build_snapshot_id: str
    scope_id: str
    source_snapshot: ImmutableBinding
    authorization_snapshot: ImmutableBinding
    embedding_contract: ImmutableBinding
    index_schema: ImmutableBinding
    source_watermark: str
    deletion_snapshot: ImmutableBinding

    def __post_init__(self) -> None:
        _require_non_empty(
            self.build_snapshot_id,
            self.scope_id,
            self.source_watermark,
        )

    @property
    def fingerprint(self) -> str:
        return stable_hash(
            {
                "scope_id": self.scope_id,
                "source_snapshot": asdict(self.source_snapshot),
                "authorization_snapshot": asdict(self.authorization_snapshot),
                "embedding_contract": asdict(self.embedding_contract),
                "index_schema": asdict(self.index_schema),
                "source_watermark": self.source_watermark,
                "deletion_snapshot": asdict(self.deletion_snapshot),
            }
        )


@dataclass(frozen=True)
class ManifestFacts:
    """Exact, content-safe facts for one expected or observed corpus."""

    occurrence_ids: tuple[str, ...]
    content_digest: str
    metadata_digest: str
    provenance_digest: str

    def __post_init__(self) -> None:
        _require_canonical_ids(
            self.occurrence_ids,
            label="occurrence IDs",
            allow_empty=True,
        )
        _require_non_empty(
            self.content_digest,
            self.metadata_digest,
            self.provenance_digest,
        )

    @property
    def occurrence_count(self) -> int:
        return len(self.occurrence_ids)

    @property
    def occurrence_ids_digest(self) -> str:
        return stable_hash(self.occurrence_ids)

    @property
    def fingerprint(self) -> str:
        return stable_hash(
            {
                "occurrence_count": self.occurrence_count,
                "occurrence_ids": self.occurrence_ids,
                "occurrence_ids_digest": self.occurrence_ids_digest,
                "content_digest": self.content_digest,
                "metadata_digest": self.metadata_digest,
                "provenance_digest": self.provenance_digest,
            }
        )


@dataclass(frozen=True)
class GenerationManifest:
    """Independent Expected-versus-Actual generation integrity evidence."""

    expected: ManifestFacts
    actual: ManifestFacts
    expected_absent_occurrence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_canonical_ids(
            self.expected_absent_occurrence_ids,
            label="expected-absent occurrence IDs",
            allow_empty=True,
        )
        overlap = set(self.expected.occurrence_ids).intersection(
            self.expected_absent_occurrence_ids
        )
        if overlap:
            raise ValueError(
                "expected corpus cannot include expected-absent occurrences"
            )

    @property
    def integrity_matches(self) -> bool:
        return self.expected == self.actual and not set(
            self.actual.occurrence_ids
        ).intersection(self.expected_absent_occurrence_ids)

    @property
    def digest(self) -> str:
        return stable_hash(
            {
                "expected": asdict(self.expected),
                "expected_fingerprint": self.expected.fingerprint,
                "actual": asdict(self.actual),
                "actual_fingerprint": self.actual.fingerprint,
                "expected_absent_occurrence_ids": (self.expected_absent_occurrence_ids),
            }
        )


@dataclass(frozen=True)
class GenerationArtifact:
    """Immutable physical generation identity after provider seal."""

    generation_id: str
    scope_id: str
    build_snapshot_fingerprint: str
    manifest_digest: str
    evaluation_ruler_fingerprint: str
    validation_record_digest: str
    evaluation_evidence_digest: str
    evaluation_report_digest: str
    physical_namespace: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.generation_id,
            self.scope_id,
            self.build_snapshot_fingerprint,
            self.manifest_digest,
            self.evaluation_ruler_fingerprint,
            self.validation_record_digest,
            self.evaluation_evidence_digest,
            self.evaluation_report_digest,
            self.physical_namespace,
        )

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class GenerationLifecycle:
    """Mutable lifecycle facts represented as a versioned immutable value."""

    generation_id: str
    state: GenerationState
    state_version: int
    transition_fence: int
    active_readers: int = 0
    retire_after: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.generation_id)
        if (
            min(
                self.state_version,
                self.transition_fence,
                self.active_readers,
            )
            < 0
        ):
            raise ValueError(
                "lifecycle versions, fences and readers cannot be negative"
            )
        if self.state is GenerationState.RETIRED and self.active_readers != 0:
            raise ValueError("a retired generation cannot retain active readers")
        if self.retire_after is not None and not self.retire_after.strip():
            raise ValueError("retire-after must be absent or non-empty")


@dataclass(frozen=True)
class ValidationRecord:
    """Validator-owned provider read-back and seal evidence."""

    validation_id: str
    generation_id: str
    build_snapshot_fingerprint: str
    expected_manifest_digest: str
    actual_manifest_digest: str
    physical_namespace: str
    provider_checkpoint: str
    provider_write_fence: int
    validator_version: str
    decision: ValidationDecision
    observed_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.validation_id,
            self.generation_id,
            self.build_snapshot_fingerprint,
            self.expected_manifest_digest,
            self.actual_manifest_digest,
            self.physical_namespace,
            self.provider_checkpoint,
            self.validator_version,
            self.observed_at,
        )
        if self.provider_write_fence <= 0:
            raise ValueError("provider write fence must be positive")
        if (
            self.decision is ValidationDecision.PASS
            and self.expected_manifest_digest != self.actual_manifest_digest
        ):
            raise ValueError("PASS requires matching expected and actual manifests")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class EvaluationEvidence:
    """Day103-compatible quality evidence bound to one generation artifact."""

    evidence_id: str
    generation_id: str
    build_snapshot_fingerprint: str
    manifest_digest: str
    dataset_fingerprint: str
    evaluator_fingerprint: str
    policy_fingerprint: str
    evaluation_report_checksum: str
    evidence_level: str
    decision: EvaluationDecision
    observed_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.evidence_id,
            self.generation_id,
            self.build_snapshot_fingerprint,
            self.manifest_digest,
            self.dataset_fingerprint,
            self.evaluator_fingerprint,
            self.policy_fingerprint,
            self.evaluation_report_checksum,
            self.evidence_level,
            self.observed_at,
        )

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class ActivePointer:
    pointer_name: str
    generation_id: str
    revision: int

    def __post_init__(self) -> None:
        _require_non_empty(self.pointer_name, self.generation_id)
        if self.revision <= 0:
            raise ValueError("pointer revision must be positive")


@dataclass(frozen=True)
class ActivationLease:
    """Authority-issued current right to attempt pointer activation."""

    pointer_name: str
    committer_id: str
    fencing_token: int
    issued_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.pointer_name,
            self.committer_id,
            self.issued_at,
        )
        if self.fencing_token <= 0:
            raise ValueError("activation fencing token must be positive")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class ActivationRecord:
    """Append-only evidence for one attempted pointer transition."""

    activation_id: str
    pointer_name: str
    expected_generation_id: str
    target_generation_id: str
    from_revision: int
    to_revision: int
    build_snapshot_fingerprint: str
    manifest_digest: str
    evaluation_report_checksum: str
    committer_id: str
    committer_fence: int
    decision: ActivationDecision
    committed_at: str
    previous_retire_after: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(
            self.activation_id,
            self.pointer_name,
            self.expected_generation_id,
            self.target_generation_id,
            self.build_snapshot_fingerprint,
            self.manifest_digest,
            self.evaluation_report_checksum,
            self.committer_id,
            self.committed_at,
        )
        if min(self.from_revision, self.committer_fence) <= 0:
            raise ValueError("activation revision and fence must be positive")
        if self.to_revision != self.from_revision + 1:
            raise ValueError("activation revision must increase by exactly one")
        if self.expected_generation_id == self.target_generation_id:
            raise ValueError("activation must change the selected generation")
        if (
            self.previous_retire_after is not None
            and not self.previous_retire_after.strip()
        ):
            raise ValueError("previous retire-after must be absent or non-empty")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class ReadView:
    """A leased request pin to one pointer revision and generation."""

    view_id: str
    pointer_name: str
    generation_id: str
    pointer_revision: int
    owner_id: str
    build_snapshot_fingerprint: str
    authorization_snapshot_id: str
    status: ReadViewStatus
    fencing_token: int
    lease_expires_at: str
    last_heartbeat_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.view_id,
            self.pointer_name,
            self.generation_id,
            self.owner_id,
            self.build_snapshot_fingerprint,
            self.authorization_snapshot_id,
            self.lease_expires_at,
            self.last_heartbeat_at,
        )
        if min(self.pointer_revision, self.fencing_token) <= 0:
            raise ValueError("ReadView revision and fence must be positive")


@dataclass(frozen=True)
class DeletionIntent:
    """Immutable durable intent; physical erasure is separate evidence."""

    deletion_id: str
    operation_id: str
    idempotency_key: str
    scope_id: str
    occurrence_id: str
    source_version: str
    intent_digest: str
    verification_policy_id: str
    required_evidence_scopes: tuple[DeletionEvidenceScope, ...]
    state: DeletionState
    accepted_at: str
    verified_deletion_snapshot_id: str | None = None
    verified_evidence_ids: tuple[str, ...] = ()
    verified_evidence_digest: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(
            self.deletion_id,
            self.operation_id,
            self.idempotency_key,
            self.scope_id,
            self.occurrence_id,
            self.source_version,
            self.intent_digest,
            self.verification_policy_id,
            self.accepted_at,
        )
        if not self.required_evidence_scopes:
            raise ValueError("required deletion evidence scopes cannot be empty")
        if any(
            not isinstance(scope, DeletionEvidenceScope)
            for scope in self.required_evidence_scopes
        ):
            raise ValueError("required deletion evidence scopes are invalid")
        expected_scopes = tuple(
            sorted(
                self.required_evidence_scopes,
                key=lambda scope: scope.value,
            )
        )
        if self.required_evidence_scopes != expected_scopes or len(
            set(self.required_evidence_scopes)
        ) != len(self.required_evidence_scopes):
            raise ValueError(
                "required deletion evidence scopes must be sorted and unique"
            )
        parse_aware_datetime(self.accepted_at, label="deletion accepted-at")
        _require_canonical_ids(
            self.verified_evidence_ids,
            label="verified deletion evidence IDs",
            allow_empty=True,
        )
        if self.state is DeletionState.VERIFIED:
            if (
                self.verified_deletion_snapshot_id is None
                or not self.verified_evidence_ids
                or self.verified_evidence_digest is None
            ):
                raise ValueError(
                    "verified deletion requires adopted evidence IDs and digest"
                )
            _require_non_empty(self.verified_deletion_snapshot_id or "")
            if len(self.verified_evidence_ids) != len(self.required_evidence_scopes):
                raise ValueError(
                    "verified deletion requires one evidence ID per required scope"
                )
            _require_non_empty(self.verified_evidence_digest)
        elif (
            self.verified_deletion_snapshot_id is not None
            or self.verified_evidence_ids
            or self.verified_evidence_digest is not None
        ):
            raise ValueError("unverified deletion cannot adopt verification evidence")

    @property
    def identity_digest(self) -> str:
        """Digest of the immutable request and its durable verification policy."""

        return stable_hash(
            {
                "deletion_id": self.deletion_id,
                "operation_id": self.operation_id,
                "idempotency_key": self.idempotency_key,
                "scope_id": self.scope_id,
                "occurrence_id": self.occurrence_id,
                "source_version": self.source_version,
                "intent_digest": self.intent_digest,
                "verification_policy_id": self.verification_policy_id,
                "required_evidence_scopes": self.required_evidence_scopes,
                "accepted_at": self.accepted_at,
            }
        )


@dataclass(frozen=True)
class DeletionSnapshot:
    """Point-in-time exact Tombstone set consumed by future rebuilds."""

    deletion_snapshot_id: str
    scope_id: str
    ledger_revision: int
    occurrence_ids: tuple[str, ...]
    created_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.deletion_snapshot_id,
            self.scope_id,
            self.created_at,
        )
        if self.ledger_revision < 0:
            raise ValueError("deletion ledger revision cannot be negative")
        _require_canonical_ids(
            self.occurrence_ids,
            label="deleted occurrence IDs",
            allow_empty=True,
        )
        parse_aware_datetime(self.created_at, label="deletion snapshot created-at")

    @property
    def occurrence_ids_digest(self) -> str:
        return stable_hash(self.occurrence_ids)

    @property
    def fingerprint(self) -> str:
        return stable_hash(
            {
                "scope_id": self.scope_id,
                "ledger_revision": self.ledger_revision,
                "occurrence_ids": self.occurrence_ids,
                "occurrence_ids_digest": self.occurrence_ids_digest,
            }
        )


@dataclass(frozen=True)
class DeletionEvidence:
    evidence_id: str
    deletion_snapshot_id: str
    verification_policy_id: str
    validator_id: str
    validator_version: str
    scope: DeletionEvidenceScope
    status: EvidenceStatus
    pointer_name: str
    pointer_revision: int
    generation_ids: tuple[str, ...]
    tombstoned_occurrence_ids: tuple[str, ...]
    readback_digest: str
    observed_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.evidence_id,
            self.deletion_snapshot_id,
            self.verification_policy_id,
            self.validator_id,
            self.validator_version,
            self.pointer_name,
            self.readback_digest,
            self.observed_at,
        )
        if self.pointer_revision <= 0:
            raise ValueError("deletion-evidence pointer revision must be positive")
        _require_canonical_ids(
            self.generation_ids,
            label="deletion-evidence generation IDs",
            allow_empty=(self.scope is DeletionEvidenceScope.PHYSICAL_PURGE),
        )
        _require_canonical_ids(
            self.tombstoned_occurrence_ids,
            label="deletion-evidence tombstoned occurrence IDs",
        )
        parse_aware_datetime(self.observed_at, label="deletion evidence observed-at")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class OutboxEvent:
    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_revision: int
    payload_digest: str
    state: MessageState = MessageState.PENDING

    def __post_init__(self) -> None:
        _require_non_empty(
            self.event_id,
            self.event_type,
            self.aggregate_id,
            self.payload_digest,
        )
        if self.aggregate_revision <= 0:
            raise ValueError("Outbox aggregate revision must be positive")


@dataclass(frozen=True)
class InboxRecord:
    event_id: str
    payload_digest: str
    source_stream: str
    state: MessageState
    result_id: str | None = None
    result_digest: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(
            self.event_id,
            self.payload_digest,
            self.source_stream,
        )
        if (self.result_id is None) != (self.result_digest is None):
            raise ValueError("Inbox result identity and digest must appear together")
        if self.state is MessageState.APPLIED and self.result_id is None:
            raise ValueError("an applied Inbox record requires a durable result")
        if self.result_id is not None:
            _require_non_empty(self.result_id, self.result_digest or "")
