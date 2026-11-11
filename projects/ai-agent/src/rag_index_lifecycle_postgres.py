"""PostgreSQL + pgvector integration adapter for the Day104 lifecycle.

This module is intentionally synchronous.  It keeps the application database
as the control-plane authority and uses one PostgreSQL transaction for every
state transition.  The dependency on psycopg2 is lazy so importing the module
does not make the deterministic classroom suite depend on a local driver.

The SQL targets ``integration/day104/schema.sql``.  Provider writes are rows in
an immutable-per-generation pgvector table; a sealed generation is validated by
an independent read-back before it can become READY.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import math
from pathlib import Path
import struct
from typing import Any, Protocol, cast

from rag_chunking_contracts import stable_hash
from rag_index_lifecycle_contracts import (
    BuildSnapshot,
    DeletionEvidence,
    DeletionEvidenceScope,
    DeletionState,
    EvaluationRuler,
    EvidenceStatus,
    GenerationManifest,
    GenerationState,
    ManifestFacts,
    parse_aware_datetime,
)
from rag_index_deletion_ledger import DEFAULT_TRUSTED_DELETION_VALIDATORS
from rag_index_lifecycle_orchestrator import (
    IndexedOccurrence,
    manifest_facts,
)


SCHEMA = "day104_l3"
VECTOR_DIMENSIONS = 3
_RESET_CONFIRMATION = "RESET_DAY104_L3_SCHEMA"


class CursorPort(Protocol):
    rowcount: int

    def execute(
        self,
        query: str,
        params: Sequence[object] | Mapping[str, object] | None = None,
    ) -> object:
        ...

    def fetchone(self) -> Sequence[Any] | None:
        ...

    def fetchall(self) -> list[Sequence[Any]]:
        ...

    def close(self) -> None:
        ...


class ConnectionPort(Protocol):
    def cursor(self) -> CursorPort:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...

    def close(self) -> None:
        ...


ConnectionFactory = Callable[[], ConnectionPort]


def psycopg2_connection_factory(
    dsn: str,
    *,
    application_name: str = "day104-l3-index-lifecycle",
) -> ConnectionFactory:
    """Return a lazy psycopg2 connection factory.

    Importing this module remains safe when psycopg2 is absent.  Calling the
    returned factory without the dependency raises a focused RuntimeError.
    """

    if not dsn.strip() or not application_name.strip():
        raise ValueError("DSN and application name are required")

    def connect() -> ConnectionPort:
        try:
            import psycopg2  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - environment boundary
            raise RuntimeError(
                "psycopg2-binary is required for the Day104 L3 integration"
            ) from exc
        return cast(
            ConnectionPort,
            psycopg2.connect(dsn, application_name=application_name),
        )

    return connect


class RepositoryOutcome(str, Enum):
    APPLIED = "APPLIED"
    EXACT_REPLAY = "EXACT_REPLAY"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    NOT_FOUND = "NOT_FOUND"
    STALE_STATE = "STALE_STATE"
    STALE_FENCE = "STALE_FENCE"
    STALE_POINTER = "STALE_POINTER"
    INTEGRITY_FAILED = "INTEGRITY_FAILED"
    READY = "READY"
    ACTIVATED = "ACTIVATED"
    CLAIMED = "CLAIMED"
    READERS_PRESENT = "READERS_PRESENT"
    RETIRED = "RETIRED"
    DISPATCHED = "DISPATCHED"
    VERIFIED = "VERIFIED"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"


class QueryMode(str, Enum):
    EXACT = "EXACT"
    HNSW = "HNSW"


class ReadViewQueryRejected(RuntimeError):
    """The durable ReadView no longer authorizes this retrieval attempt."""


@dataclass(frozen=True)
class RepositoryResult:
    outcome: RepositoryOutcome
    safe_reason: str
    durable_transition: bool = False
    identity_digest: str | None = None
    generation_id: str | None = None
    revision: int | None = None
    state_version: int | None = None
    checkpoint: str | None = None
    manifest: GenerationManifest | None = None
    deletion_id: str | None = None
    evidence_id: str | None = None


@dataclass(frozen=True, order=True)
class SourceOccurrenceRecord:
    occurrence_id: str
    logical_id: str
    source_version: str
    content_digest: str
    metadata_digest: str
    provenance_digest: str
    tenant_id: str

    def __post_init__(self) -> None:
        _require_text(
            self.occurrence_id,
            self.logical_id,
            self.source_version,
            self.content_digest,
            self.metadata_digest,
            self.provenance_digest,
            self.tenant_id,
        )


@dataclass(frozen=True, order=True)
class DeletionReceipt:
    deletion_id: str
    operation_id: str
    idempotency_key: str
    occurrence_id: str
    source_version: str
    intent_digest: str
    verification_policy_id: str
    required_evidence_scopes: tuple[str, ...]
    accepted_at: str

    def __post_init__(self) -> None:
        _require_text(
            self.deletion_id,
            self.operation_id,
            self.idempotency_key,
            self.occurrence_id,
            self.source_version,
            self.intent_digest,
            self.verification_policy_id,
            self.accepted_at,
        )
        _require_canonical(self.required_evidence_scopes, "evidence scopes")
        parse_aware_datetime(self.accepted_at, label="deletion accepted-at")


@dataclass(frozen=True)
class SourceDeletionCommand:
    operation_id: str
    idempotency_key: str
    scope_id: str
    source_snapshot_id: str
    source_version: str
    source_digest: str
    occurrences: tuple[SourceOccurrenceRecord, ...]
    deletion_snapshot_id: str
    deletion_digest: str
    deletion_ledger_revision: int
    deletions: tuple[DeletionReceipt, ...]
    received_at: str

    def __post_init__(self) -> None:
        _require_text(
            self.operation_id,
            self.idempotency_key,
            self.scope_id,
            self.source_snapshot_id,
            self.source_version,
            self.source_digest,
            self.deletion_snapshot_id,
            self.deletion_digest,
            self.received_at,
        )
        if self.deletion_ledger_revision < 0:
            raise ValueError("deletion ledger revision cannot be negative")
        parse_aware_datetime(self.received_at, label="source receive time")
        occurrence_ids = tuple(item.occurrence_id for item in self.occurrences)
        if not occurrence_ids or len(set(occurrence_ids)) != len(occurrence_ids):
            raise ValueError(
                "source occurrence identities must be non-empty and unique"
            )
        if self.occurrences != tuple(sorted(self.occurrences)):
            raise ValueError("source occurrences must be canonically sorted")
        if any(
            occurrence.source_version != self.source_version
            for occurrence in self.occurrences
        ):
            raise ValueError("source occurrences must bind the received version")
        deletion_ids = tuple(item.deletion_id for item in self.deletions)
        if len(set(deletion_ids)) != len(deletion_ids):
            raise ValueError("deletion identities must be unique")
        if self.deletions != tuple(sorted(self.deletions)):
            raise ValueError("deletions must be canonically sorted")
        source_ids = set(occurrence_ids)
        if any(item.occurrence_id not in source_ids for item in self.deletions):
            raise ValueError("every Tombstone must reference the received source")
        if any(item.source_version != self.source_version for item in self.deletions):
            raise ValueError("every Tombstone must bind the received version")

    @property
    def deletion_occurrence_ids(self) -> tuple[str, ...]:
        return tuple(sorted(item.occurrence_id for item in self.deletions))

    @property
    def identity_digest(self) -> str:
        return stable_hash(
            {
                "operation_id": self.operation_id,
                "idempotency_key": self.idempotency_key,
                "scope_id": self.scope_id,
                "source_snapshot_id": self.source_snapshot_id,
                "source_version": self.source_version,
                "source_digest": self.source_digest,
                "occurrences": tuple(asdict(item) for item in self.occurrences),
                "deletion_snapshot_id": self.deletion_snapshot_id,
                "deletion_digest": self.deletion_digest,
                "deletion_ledger_revision": self.deletion_ledger_revision,
                "deletions": tuple(asdict(item) for item in self.deletions),
                "received_at": self.received_at,
            }
        )

    @property
    def result_digest(self) -> str:
        return stable_hash(
            (
                self.scope_id,
                self.source_snapshot_id,
                self.source_digest,
                self.deletion_snapshot_id,
                self.deletion_digest,
                self.deletion_ledger_revision,
                self.deletion_occurrence_ids,
            )
        )


@dataclass(frozen=True, order=True)
class PgVectorPoint:
    point_id: str
    generation_id: str
    occurrence_id: str
    tenant_id: str
    content_digest: str
    metadata_digest: str
    provenance_digest: str
    embedding: tuple[float, ...]
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _require_text(
            self.point_id,
            self.generation_id,
            self.occurrence_id,
            self.tenant_id,
            self.content_digest,
            self.metadata_digest,
            self.provenance_digest,
        )
        canonical_vector_literal(self.embedding, VECTOR_DIMENSIONS)
        if self.metadata != tuple(sorted(self.metadata)):
            raise ValueError("point metadata must be canonically sorted")
        if len({key for key, _ in self.metadata}) != len(self.metadata):
            raise ValueError("point metadata keys must be unique")

    @property
    def vector_digest(self) -> str:
        return stable_hash(canonical_float32_values(self.embedding))

    @property
    def identity_digest(self) -> str:
        return stable_hash(
            {
                "point_id": self.point_id,
                "generation_id": self.generation_id,
                "occurrence_id": self.occurrence_id,
                "tenant_id": self.tenant_id,
                "content_digest": self.content_digest,
                "metadata_digest": self.metadata_digest,
                "provenance_digest": self.provenance_digest,
                "vector_digest": self.vector_digest,
                "metadata": self.metadata,
            }
        )


@dataclass(frozen=True)
class PgVectorHit:
    point_id: str
    occurrence_id: str
    generation_id: str
    cosine_distance: float

    @property
    def similarity(self) -> float:
        return max(-1.0, min(1.0, 1.0 - self.cosine_distance))


@dataclass(frozen=True)
class ActivationLeaseRecord:
    pointer_name: str
    committer_id: str
    fencing_token: int
    issued_at: str
    lease_expires_at: str


@dataclass(frozen=True)
class OutboxClaim:
    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_revision: int
    payload_digest: str
    claim_owner: str
    claim_fence: int
    claimed_at: str


def _require_text(*values: str) -> None:
    if not all(value.strip() for value in values):
        raise ValueError("complete non-empty identity bindings are required")


def _require_canonical(values: tuple[str, ...], label: str) -> None:
    if not values or any(not value.strip() for value in values):
        raise ValueError(f"{label} must be non-empty")
    if values != tuple(sorted(values)) or len(set(values)) != len(values):
        raise ValueError(f"{label} must be sorted and unique")


def canonical_float32_values(values: tuple[float, ...]) -> tuple[float, ...]:
    if not values:
        raise ValueError("a vector cannot be empty")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("vectors require finite values")
    return tuple(struct.unpack("!f", struct.pack("!f", value))[0] for value in values)


def canonical_vector_literal(
    values: tuple[float, ...],
    expected_dimensions: int = VECTOR_DIMENSIONS,
) -> str:
    canonical = canonical_float32_values(values)
    if expected_dimensions <= 0 or len(canonical) != expected_dimensions:
        raise ValueError("vector dimensions do not match the frozen index schema")
    return "[" + ",".join(format(value, ".9g") for value in canonical) + "]"


def manifest_from_point_rows(
    rows: Iterable[Sequence[object]],
) -> ManifestFacts:
    occurrences: list[IndexedOccurrence] = []
    for row in rows:
        if len(row) != 4:
            raise ValueError("read-back rows require occurrence and three digests")
        occurrence_id, content, metadata, provenance = row
        if not all(isinstance(value, str) for value in row):
            raise ValueError("read-back manifest fields must be strings")
        occurrences.append(
            IndexedOccurrence(
                cast(str, occurrence_id),
                cast(str, content),
                cast(str, metadata),
                cast(str, provenance),
            )
        )
    return manifest_facts(tuple(occurrences))


def points_identity_digest(points: tuple[PgVectorPoint, ...]) -> str:
    canonical = tuple(sorted(points))
    if len({item.point_id for item in canonical}) != len(canonical):
        raise ValueError("point IDs must be unique")
    if len({item.occurrence_id for item in canonical}) != len(canonical):
        raise ValueError("occurrence IDs must be unique within a generation")
    if len({item.generation_id for item in canonical}) > 1:
        raise ValueError("one write cannot mix generations")
    return stable_hash(tuple(item.identity_digest for item in canonical))


def _utc_iso(value: str | datetime, *, label: str) -> str:
    parsed = (
        parse_aware_datetime(value, label=label) if isinstance(value, str) else value
    )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include an explicit UTC offset")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalized_deletion_evidence(evidence: DeletionEvidence) -> DeletionEvidence:
    return DeletionEvidence(
        evidence_id=evidence.evidence_id,
        deletion_snapshot_id=evidence.deletion_snapshot_id,
        verification_policy_id=evidence.verification_policy_id,
        validator_id=evidence.validator_id,
        validator_version=evidence.validator_version,
        scope=evidence.scope,
        status=evidence.status,
        pointer_name=evidence.pointer_name,
        pointer_revision=evidence.pointer_revision,
        generation_ids=evidence.generation_ids,
        tombstoned_occurrence_ids=evidence.tombstoned_occurrence_ids,
        readback_digest=evidence.readback_digest,
        observed_at=_utc_iso(
            evidence.observed_at,
            label="deletion evidence observed-at",
        ),
    )


def _deletion_evidence_from_row(row: Sequence[Any]) -> DeletionEvidence:
    if len(row) != 13:
        raise ValueError("persisted deletion evidence row is incomplete")
    return DeletionEvidence(
        evidence_id=cast(str, row[0]),
        deletion_snapshot_id=cast(str, row[1]),
        verification_policy_id=cast(str, row[2]),
        validator_id=cast(str, row[3]),
        validator_version=cast(str, row[4]),
        scope=DeletionEvidenceScope(cast(str, row[5])),
        status=EvidenceStatus(cast(str, row[6])),
        pointer_name=cast(str, row[7]),
        pointer_revision=int(row[8]),
        generation_ids=tuple(row[9]),
        tombstoned_occurrence_ids=tuple(row[10]),
        readback_digest=cast(str, row[11]),
        observed_at=_utc_iso(
            cast(datetime, row[12]),
            label="persisted deletion evidence observed-at",
        ),
    )


def _adopted_deletion_evidence_digest(
    evidence: tuple[DeletionEvidence, ...],
) -> str:
    return stable_hash(
        tuple((item.scope.value, item.evidence_id, item.digest) for item in evidence)
    )


class PostgresIndexLifecycleRepository:
    """Synchronous PostgreSQL repository and pgvector query adapter."""

    def __init__(
        self,
        connect: ConnectionFactory,
        *,
        schema_path: str | Path | None = None,
        trusted_deletion_validators: frozenset[tuple[str, str]] = (
            DEFAULT_TRUSTED_DELETION_VALIDATORS
        ),
    ) -> None:
        if not trusted_deletion_validators:
            raise ValueError("at least one trusted deletion validator is required")
        self._connect = connect
        self._trusted_deletion_validators = trusted_deletion_validators
        default_schema = (
            Path(__file__).resolve().parent.parent
            / "integration"
            / "day104"
            / "schema.sql"
        )
        self._schema_path = Path(schema_path) if schema_path else default_schema

    @contextmanager
    def _transaction(self) -> Iterator[CursorPort]:
        connection = self._connect()
        cursor = connection.cursor()
        try:
            yield cursor
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def install_schema(self) -> None:
        ddl = self._schema_path.read_text(encoding="utf-8")
        if not ddl.strip():
            raise ValueError("Day104 L3 schema cannot be empty")
        with self._transaction() as cursor:
            cursor.execute(ddl)

    def reset_schema(self, *, confirmation: str) -> None:
        if confirmation != _RESET_CONFIRMATION:
            raise ValueError(
                f"schema reset requires confirmation {_RESET_CONFIRMATION!r}"
            )
        ddl = self._schema_path.read_text(encoding="utf-8")
        if not ddl.strip():
            raise ValueError("Day104 L3 schema cannot be empty")
        with self._transaction() as cursor:
            cursor.execute("SELECT current_database()")
            database = cursor.fetchone()
            if database is None or database[0] != "day104_l3":
                raise ValueError("schema reset is restricted to the day104_l3 database")
            cursor.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
            cursor.execute(ddl)

    @staticmethod
    def _lock_identities(cursor: CursorPort, identities: Iterable[str]) -> None:
        for identity in sorted(set(identities)):
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (identity,),
            )

    def receive_source_and_deletion(
        self,
        command: SourceDeletionCommand,
    ) -> RepositoryResult:
        with self._transaction() as cursor:
            self._lock_identities(
                cursor,
                (
                    f"ingest-operation:{command.operation_id}",
                    f"ingest-idempotency:{command.scope_id}:{command.idempotency_key}",
                ),
            )
            cursor.execute(
                f"""
                SELECT operation_id, identity_digest, result_digest
                FROM {SCHEMA}.ingest_operations
                WHERE operation_id = %s
                   OR (scope_id = %s AND idempotency_key = %s)
                FOR UPDATE
                """,
                (
                    command.operation_id,
                    command.scope_id,
                    command.idempotency_key,
                ),
            )
            existing = cursor.fetchall()
            if existing:
                exact = (
                    len(existing) == 1
                    and existing[0][0] == command.operation_id
                    and existing[0][1] == command.identity_digest
                    and existing[0][2] == command.result_digest
                )
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY
                    if exact
                    else RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_SOURCE_DELETE_REPLAY_CONVERGED"
                    if exact
                    else "SOURCE_DELETE_OPERATION_OR_IDEMPOTENCY_CONFLICT",
                    identity_digest=command.identity_digest,
                )

            deletion_ids = tuple(item.deletion_id for item in command.deletions)
            deletion_operations = tuple(item.operation_id for item in command.deletions)
            if deletion_ids:
                cursor.execute(
                    f"""
                    SELECT deletion_id
                    FROM {SCHEMA}.deletion_intents
                    WHERE deletion_id = ANY(%s)
                       OR operation_id = ANY(%s)
                    FOR UPDATE
                    """,
                    (list(deletion_ids), list(deletion_operations)),
                )
                if cursor.fetchone() is not None:
                    return RepositoryResult(
                        RepositoryOutcome.IDENTITY_CONFLICT,
                        "DELETION_IDENTITY_ALREADY_BOUND",
                        identity_digest=command.identity_digest,
                    )

            received_at = parse_aware_datetime(
                command.received_at,
                label="source receive time",
            )
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.ingest_operations
                    (operation_id, scope_id, idempotency_key,
                     identity_digest, result_digest, created_at)
                VALUES (%s, %s, %s, %s, NULL, %s)
                """,
                (
                    command.operation_id,
                    command.scope_id,
                    command.idempotency_key,
                    command.identity_digest,
                    received_at,
                ),
            )
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.source_snapshots
                    (snapshot_id, scope_id, source_version,
                     source_digest, received_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    command.source_snapshot_id,
                    command.scope_id,
                    command.source_version,
                    command.source_digest,
                    received_at,
                ),
            )
            for occurrence in command.occurrences:
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.source_occurrences
                        (scope_id, snapshot_id, occurrence_id, logical_id,
                         source_version, content_digest, metadata_digest,
                         provenance_digest, tenant_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        command.scope_id,
                        command.source_snapshot_id,
                        occurrence.occurrence_id,
                        occurrence.logical_id,
                        occurrence.source_version,
                        occurrence.content_digest,
                        occurrence.metadata_digest,
                        occurrence.provenance_digest,
                        occurrence.tenant_id,
                        received_at,
                    ),
                )
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.deletion_snapshots
                    (snapshot_id, scope_id, deletion_digest,
                     occurrence_ids, ledger_revision, received_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    command.deletion_snapshot_id,
                    command.scope_id,
                    command.deletion_digest,
                    list(command.deletion_occurrence_ids),
                    command.deletion_ledger_revision,
                    received_at,
                ),
            )
            for deletion in command.deletions:
                accepted_at = parse_aware_datetime(
                    deletion.accepted_at,
                    label="deletion accepted-at",
                )
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.deletion_intents
                        (deletion_id, operation_id, scope_id, idempotency_key,
                         occurrence_id, source_version, intent_digest,
                         verification_policy_id, required_evidence_scopes,
                         state, accepted_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                            'ACCEPTED', %s)
                    """,
                    (
                        deletion.deletion_id,
                        deletion.operation_id,
                        command.scope_id,
                        deletion.idempotency_key,
                        deletion.occurrence_id,
                        deletion.source_version,
                        deletion.intent_digest,
                        deletion.verification_policy_id,
                        list(deletion.required_evidence_scopes),
                        accepted_at,
                    ),
                )
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.tombstones
                        (scope_id, occurrence_id, deletion_id,
                         ledger_revision, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        command.scope_id,
                        deletion.occurrence_id,
                        deletion.deletion_id,
                        command.deletion_ledger_revision,
                        accepted_at,
                    ),
                )
            event_id = stable_hash(
                ("SOURCE_DELETION_RECEIVED", command.identity_digest)
            )
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.outbox_events
                    (event_id, event_type, aggregate_id, aggregate_revision,
                     payload_digest, state, created_at)
                VALUES (%s, 'SOURCE_DELETION_RECEIVED', %s, %s, %s,
                        'PENDING', %s)
                """,
                (
                    event_id,
                    command.scope_id,
                    max(1, command.deletion_ledger_revision),
                    command.result_digest,
                    received_at,
                ),
            )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.ingest_operations
                SET result_digest = %s
                WHERE operation_id = %s
                """,
                (command.result_digest, command.operation_id),
            )
            return RepositoryResult(
                RepositoryOutcome.APPLIED,
                "SOURCE_DELETE_AND_OUTBOX_COMMITTED_ATOMICALLY",
                durable_transition=True,
                identity_digest=command.identity_digest,
            )

    def record_deletion_evidence(
        self,
        evidence: DeletionEvidence,
    ) -> RepositoryResult:
        normalized = _normalized_deletion_evidence(evidence)
        validator = (normalized.validator_id, normalized.validator_version)
        if validator not in self._trusted_deletion_validators:
            return RepositoryResult(
                RepositoryOutcome.IDENTITY_CONFLICT,
                "DELETION_EVIDENCE_VALIDATOR_NOT_TRUSTED",
                evidence_id=normalized.evidence_id,
            )
        if (
            normalized.scope is DeletionEvidenceScope.PHYSICAL_PURGE
            and normalized.status is EvidenceStatus.PASS
        ):
            return RepositoryResult(
                RepositoryOutcome.INTEGRITY_FAILED,
                "PHYSICAL_PURGE_NOT_PROVEN_BY_THIS_ADAPTER",
                evidence_id=normalized.evidence_id,
            )
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT evidence_id, deletion_snapshot_id,
                       verification_policy_id, validator_id,
                       validator_version, evidence_scope, status,
                       pointer_name, pointer_revision, generation_ids,
                       tombstoned_occurrence_ids, readback_digest, observed_at
                FROM {SCHEMA}.deletion_evidence
                WHERE evidence_id = %s
                   OR (
                       deletion_snapshot_id = %s
                       AND verification_policy_id = %s
                       AND validator_id = %s
                       AND validator_version = %s
                       AND evidence_scope = %s
                   )
                FOR UPDATE
                """,
                (
                    normalized.evidence_id,
                    normalized.deletion_snapshot_id,
                    normalized.verification_policy_id,
                    normalized.validator_id,
                    normalized.validator_version,
                    normalized.scope.value,
                ),
            )
            existing = cursor.fetchall()
            if existing:
                exact = (
                    len(existing) == 1
                    and _deletion_evidence_from_row(existing[0]) == normalized
                )
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY
                    if exact
                    else RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_DELETION_EVIDENCE_REPLAY"
                    if exact
                    else "DELETION_EVIDENCE_ID_ALREADY_BOUND",
                    evidence_id=normalized.evidence_id,
                    identity_digest=normalized.digest,
                )
            cursor.execute(
                f"""
                SELECT scope_id, occurrence_ids
                FROM {SCHEMA}.deletion_snapshots
                WHERE snapshot_id = %s
                FOR UPDATE
                """,
                (normalized.deletion_snapshot_id,),
            )
            snapshot = cursor.fetchone()
            if snapshot is None:
                return RepositoryResult(
                    RepositoryOutcome.NOT_FOUND,
                    "DELETION_SNAPSHOT_NOT_FOUND",
                    evidence_id=normalized.evidence_id,
                )
            scope_id = cast(str, snapshot[0])
            snapshot_tombstones = tuple(snapshot[1])
            if normalized.tombstoned_occurrence_ids != snapshot_tombstones:
                return RepositoryResult(
                    RepositoryOutcome.IDENTITY_CONFLICT,
                    "DELETION_EVIDENCE_TOMBSTONE_SET_MISMATCH",
                    evidence_id=normalized.evidence_id,
                )
            cursor.execute(
                f"""
                SELECT occurrence_id
                FROM {SCHEMA}.deletion_intents
                WHERE scope_id = %s AND verification_policy_id = %s
                  AND occurrence_id = ANY(%s)
                ORDER BY occurrence_id
                FOR UPDATE
                """,
                (
                    scope_id,
                    normalized.verification_policy_id,
                    list(snapshot_tombstones),
                ),
            )
            policy_occurrences = tuple(row[0] for row in cursor.fetchall())
            if policy_occurrences != snapshot_tombstones:
                return RepositoryResult(
                    RepositoryOutcome.IDENTITY_CONFLICT,
                    "DELETION_EVIDENCE_POLICY_DOES_NOT_BIND_TOMBSTONE_SET",
                    evidence_id=normalized.evidence_id,
                )
            cursor.execute(
                f"""
                SELECT revision, scope_id
                FROM {SCHEMA}.active_pointers
                WHERE pointer_name = %s
                FOR UPDATE
                """,
                (normalized.pointer_name,),
            )
            pointer = cursor.fetchone()
            if (
                pointer is None
                or int(pointer[0]) != normalized.pointer_revision
                or pointer[1] != scope_id
            ):
                return RepositoryResult(
                    RepositoryOutcome.STALE_POINTER,
                    "DELETION_EVIDENCE_POINTER_BINDING_CHANGED",
                    evidence_id=normalized.evidence_id,
                )
            cursor.execute(
                f"""
                SELECT generation_id
                FROM {SCHEMA}.generations
                WHERE scope_id = %s AND state IN ('ACTIVE', 'DRAINING')
                ORDER BY generation_id
                FOR UPDATE
                """,
                (scope_id,),
            )
            servable_generations = tuple(row[0] for row in cursor.fetchall())
            if normalized.scope is DeletionEvidenceScope.PHYSICAL_PURGE:
                if normalized.generation_ids:
                    return RepositoryResult(
                        RepositoryOutcome.IDENTITY_CONFLICT,
                        "UNEXECUTED_PHYSICAL_PURGE_MUST_NOT_CLAIM_GENERATIONS",
                        evidence_id=normalized.evidence_id,
                    )
            elif normalized.generation_ids != servable_generations:
                return RepositoryResult(
                    RepositoryOutcome.IDENTITY_CONFLICT,
                    "DELETION_EVIDENCE_SERVABLE_GENERATION_SET_MISMATCH",
                    evidence_id=normalized.evidence_id,
                )
            if (
                normalized.scope is DeletionEvidenceScope.SERVING_INDEX_ABSENCE
                and normalized.status is EvidenceStatus.PASS
                and servable_generations
            ):
                cursor.execute(
                    f"""
                    SELECT occurrence_id
                    FROM {SCHEMA}.index_points
                    WHERE generation_id = ANY(%s)
                      AND occurrence_id = ANY(%s)
                    LIMIT 1
                    """,
                    (
                        list(servable_generations),
                        list(snapshot_tombstones),
                    ),
                )
                if cursor.fetchone() is not None:
                    return RepositoryResult(
                        RepositoryOutcome.INTEGRITY_FAILED,
                        "TOMBSTONED_OCCURRENCE_STILL_EXISTS_IN_SERVING_INDEX",
                        evidence_id=normalized.evidence_id,
                    )
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.deletion_evidence
                    (evidence_id, deletion_snapshot_id,
                     verification_policy_id, validator_id, validator_version,
                     evidence_scope, status, pointer_name, pointer_revision,
                     generation_ids, tombstoned_occurrence_ids,
                     readback_digest, observed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s)
                """,
                (
                    normalized.evidence_id,
                    normalized.deletion_snapshot_id,
                    normalized.verification_policy_id,
                    normalized.validator_id,
                    normalized.validator_version,
                    normalized.scope.value,
                    normalized.status.value,
                    normalized.pointer_name,
                    normalized.pointer_revision,
                    list(normalized.generation_ids),
                    list(normalized.tombstoned_occurrence_ids),
                    normalized.readback_digest,
                    parse_aware_datetime(
                        normalized.observed_at,
                        label="deletion evidence observed-at",
                    ),
                ),
            )
            return RepositoryResult(
                RepositoryOutcome.APPLIED,
                "DELETION_EVIDENCE_RECORDED_APPEND_ONLY",
                durable_transition=True,
                evidence_id=normalized.evidence_id,
                identity_digest=normalized.digest,
            )

    def mark_deletion_dispatched(
        self,
        *,
        deletion_id: str,
    ) -> RepositoryResult:
        _require_text(deletion_id)
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT state
                FROM {SCHEMA}.deletion_intents
                WHERE deletion_id = %s
                FOR UPDATE
                """,
                (deletion_id,),
            )
            intent = cursor.fetchone()
            if intent is None:
                return RepositoryResult(
                    RepositoryOutcome.NOT_FOUND,
                    "DELETION_INTENT_NOT_FOUND",
                    deletion_id=deletion_id,
                )
            if intent[0] in {
                DeletionState.DISPATCHED.value,
                DeletionState.VERIFIED.value,
            }:
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY,
                    "DELETION_ALREADY_DISPATCHED",
                    deletion_id=deletion_id,
                )
            if intent[0] != DeletionState.ACCEPTED.value:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "DELETION_INTENT_NOT_ACCEPTED",
                    deletion_id=deletion_id,
                )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.deletion_intents
                SET state = 'DISPATCHED'
                WHERE deletion_id = %s AND state = 'ACCEPTED'
                """,
                (deletion_id,),
            )
            if cursor.rowcount != 1:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "DELETION_DISPATCH_CAS_FAILED",
                    deletion_id=deletion_id,
                )
            return RepositoryResult(
                RepositoryOutcome.DISPATCHED,
                "DELETION_DISPATCH_RECORDED",
                durable_transition=True,
                deletion_id=deletion_id,
            )

    def verify_deletion(self, *, deletion_id: str) -> RepositoryResult:
        _require_text(deletion_id)
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT scope_id, occurrence_id, verification_policy_id,
                       required_evidence_scopes, state,
                       verified_deletion_snapshot_id,
                       verified_evidence_ids, verified_evidence_digest
                FROM {SCHEMA}.deletion_intents
                WHERE deletion_id = %s
                FOR UPDATE
                """,
                (deletion_id,),
            )
            intent = cursor.fetchone()
            if intent is None:
                return RepositoryResult(
                    RepositoryOutcome.NOT_FOUND,
                    "DELETION_INTENT_NOT_FOUND",
                    deletion_id=deletion_id,
                )
            required_scopes = tuple(DeletionEvidenceScope(value) for value in intent[3])
            if intent[4] == DeletionState.VERIFIED.value:
                adopted_ids = tuple(intent[6])
                cursor.execute(
                    f"""
                    SELECT evidence_id, deletion_snapshot_id,
                           verification_policy_id, validator_id,
                           validator_version, evidence_scope, status,
                           pointer_name, pointer_revision, generation_ids,
                           tombstoned_occurrence_ids, readback_digest, observed_at
                    FROM {SCHEMA}.deletion_evidence
                    WHERE evidence_id = ANY(%s)
                    ORDER BY evidence_scope
                    """,
                    (list(adopted_ids),),
                )
                persisted = tuple(
                    _deletion_evidence_from_row(row) for row in cursor.fetchall()
                )
                by_scope = {item.scope: item for item in persisted}
                complete = all(scope in by_scope for scope in required_scopes)
                adopted = (
                    tuple(by_scope[scope] for scope in required_scopes)
                    if complete
                    else ()
                )
                exact = (
                    complete
                    and tuple(sorted(item.evidence_id for item in adopted))
                    == adopted_ids
                    and all(
                        item.deletion_snapshot_id == intent[5]
                        and item.verification_policy_id == intent[2]
                        and item.status is EvidenceStatus.PASS
                        for item in adopted
                    )
                    and _adopted_deletion_evidence_digest(adopted) == intent[7]
                )
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY
                    if exact
                    else RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_DELETION_VERIFICATION_REPLAY"
                    if exact
                    else "VERIFIED_DELETION_EVIDENCE_BINDING_CONFLICT",
                    deletion_id=deletion_id,
                    identity_digest=cast(str | None, intent[7]),
                )
            if intent[4] != DeletionState.DISPATCHED.value:
                return RepositoryResult(
                    RepositoryOutcome.EVIDENCE_INCOMPLETE,
                    "DELETION_MUST_BE_DISPATCHED_BEFORE_VERIFICATION",
                    deletion_id=deletion_id,
                )
            cursor.execute(
                f"""
                SELECT snapshot_id, ledger_revision
                FROM {SCHEMA}.deletion_snapshots
                WHERE scope_id = %s AND %s = ANY(occurrence_ids)
                ORDER BY ledger_revision DESC
                LIMIT 1
                FOR UPDATE
                """,
                (intent[0], intent[1]),
            )
            snapshot = cursor.fetchone()
            if snapshot is None:
                return RepositoryResult(
                    RepositoryOutcome.EVIDENCE_INCOMPLETE,
                    "TOMBSTONE_SNAPSHOT_NOT_FOUND",
                    deletion_id=deletion_id,
                )
            cursor.execute(
                f"""
                SELECT evidence_id, deletion_snapshot_id,
                       verification_policy_id, validator_id,
                       validator_version, evidence_scope, status,
                       pointer_name, pointer_revision, generation_ids,
                       tombstoned_occurrence_ids, readback_digest, observed_at
                FROM {SCHEMA}.deletion_evidence
                WHERE deletion_snapshot_id = %s
                  AND verification_policy_id = %s
                  AND evidence_scope = ANY(%s)
                ORDER BY evidence_scope, observed_at DESC, evidence_id DESC
                """,
                (
                    snapshot[0],
                    intent[2],
                    [scope.value for scope in required_scopes],
                ),
            )
            latest_by_scope: dict[DeletionEvidenceScope, DeletionEvidence] = {}
            for row in cursor.fetchall():
                evidence = _deletion_evidence_from_row(row)
                validator = (evidence.validator_id, evidence.validator_version)
                if validator not in self._trusted_deletion_validators:
                    continue
                latest_by_scope.setdefault(evidence.scope, evidence)
            selected_evidence: list[DeletionEvidence] = []
            for scope in required_scopes:
                scope_evidence = latest_by_scope.get(scope)
                if (
                    scope_evidence is None
                    or scope_evidence.status is not EvidenceStatus.PASS
                ):
                    return RepositoryResult(
                        RepositoryOutcome.EVIDENCE_INCOMPLETE,
                        "REQUIRED_DELETION_EVIDENCE_SCOPES_NOT_PASSED",
                        deletion_id=deletion_id,
                    )
                selected_evidence.append(scope_evidence)
            adopted_tuple = tuple(selected_evidence)
            adopted_ids = tuple(sorted(item.evidence_id for item in adopted_tuple))
            adopted_digest = _adopted_deletion_evidence_digest(adopted_tuple)
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.deletion_intents
                SET state = 'VERIFIED',
                    verified_deletion_snapshot_id = %s,
                    verified_evidence_ids = %s,
                    verified_evidence_digest = %s
                WHERE deletion_id = %s AND state = 'DISPATCHED'
                """,
                (
                    snapshot[0],
                    list(adopted_ids),
                    adopted_digest,
                    deletion_id,
                ),
            )
            if cursor.rowcount != 1:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "DELETION_VERIFICATION_CAS_FAILED",
                    deletion_id=deletion_id,
                )
            return RepositoryResult(
                RepositoryOutcome.VERIFIED,
                "REQUIRED_DELETION_EVIDENCE_SCOPES_PASSED",
                durable_transition=True,
                deletion_id=deletion_id,
                identity_digest=adopted_digest,
            )

    def put_current_build_snapshot(
        self,
        *,
        snapshot: BuildSnapshot,
        expected_current_revision: int,
        created_at: str,
    ) -> RepositoryResult:
        if expected_current_revision < 0:
            raise ValueError("expected snapshot revision cannot be negative")
        observed_at = parse_aware_datetime(created_at, label="snapshot time")
        with self._transaction() as cursor:
            self._lock_identities(
                cursor,
                (f"build-snapshot-scope:{snapshot.scope_id}",),
            )
            cursor.execute(
                f"""
                SELECT build_snapshot_id, revision
                FROM {SCHEMA}.current_build_snapshots
                WHERE scope_id = %s
                FOR UPDATE
                """,
                (snapshot.scope_id,),
            )
            current = cursor.fetchone()
            actual_revision = 0 if current is None else int(current[1])
            if actual_revision != expected_current_revision:
                return RepositoryResult(
                    RepositoryOutcome.STALE_POINTER,
                    "CURRENT_BUILD_SNAPSHOT_REVISION_CHANGED",
                    revision=actual_revision,
                )
            cursor.execute(
                f"""
                SELECT snapshot_fingerprint
                FROM {SCHEMA}.build_snapshots
                WHERE build_snapshot_id = %s
                FOR UPDATE
                """,
                (snapshot.build_snapshot_id,),
            )
            existing = cursor.fetchone()
            if existing is not None and existing[0] != snapshot.fingerprint:
                return RepositoryResult(
                    RepositoryOutcome.IDENTITY_CONFLICT,
                    "BUILD_SNAPSHOT_ID_ALREADY_BOUND",
                )
            if current is not None and current[0] == snapshot.build_snapshot_id:
                exact = existing is not None and existing[0] == snapshot.fingerprint
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY
                    if exact
                    else RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_CURRENT_BUILD_SNAPSHOT_REPLAY"
                    if exact
                    else "CURRENT_BUILD_SNAPSHOT_BINDING_CONFLICT",
                    revision=actual_revision,
                )
            if existing is None:
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.build_snapshots
                        (build_snapshot_id, scope_id, source_snapshot_id,
                         source_snapshot_digest,
                         authorization_snapshot_id, authorization_snapshot_digest,
                         embedding_contract_id, embedding_contract_digest,
                         index_schema_id, index_schema_digest, source_watermark,
                         deletion_snapshot_id, deletion_snapshot_digest,
                         snapshot_fingerprint, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        snapshot.build_snapshot_id,
                        snapshot.scope_id,
                        snapshot.source_snapshot.identity,
                        snapshot.source_snapshot.digest,
                        snapshot.authorization_snapshot.identity,
                        snapshot.authorization_snapshot.digest,
                        snapshot.embedding_contract.identity,
                        snapshot.embedding_contract.digest,
                        snapshot.index_schema.identity,
                        snapshot.index_schema.digest,
                        snapshot.source_watermark,
                        snapshot.deletion_snapshot.identity,
                        snapshot.deletion_snapshot.digest,
                        snapshot.fingerprint,
                        observed_at,
                    ),
                )
            next_revision = actual_revision + 1
            if current is None:
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.current_build_snapshots
                        (scope_id, build_snapshot_id, revision, updated_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        snapshot.scope_id,
                        snapshot.build_snapshot_id,
                        next_revision,
                        observed_at,
                    ),
                )
            else:
                cursor.execute(
                    f"""
                    UPDATE {SCHEMA}.current_build_snapshots
                    SET build_snapshot_id = %s, revision = %s, updated_at = %s
                    WHERE scope_id = %s AND revision = %s
                    """,
                    (
                        snapshot.build_snapshot_id,
                        next_revision,
                        observed_at,
                        snapshot.scope_id,
                        actual_revision,
                    ),
                )
                if cursor.rowcount != 1:
                    return RepositoryResult(
                        RepositoryOutcome.STALE_POINTER,
                        "CURRENT_BUILD_SNAPSHOT_CAS_FAILED",
                    )
            return RepositoryResult(
                RepositoryOutcome.APPLIED,
                "CURRENT_BUILD_SNAPSHOT_ADVANCED",
                durable_transition=True,
                revision=next_revision,
            )

    def register_generation(
        self,
        *,
        generation_id: str,
        snapshot: BuildSnapshot,
        ruler: EvaluationRuler,
        expected_manifest: ManifestFacts,
        physical_namespace: str,
        provider_write_fence: int,
        created_at: str,
    ) -> RepositoryResult:
        _require_text(generation_id, physical_namespace, created_at)
        if provider_write_fence <= 0:
            raise ValueError("Provider write fence must be positive")
        timestamp = parse_aware_datetime(created_at, label="generation created-at")
        identity = stable_hash(
            (
                generation_id,
                snapshot.build_snapshot_id,
                snapshot.fingerprint,
                ruler.fingerprint,
                expected_manifest.fingerprint,
                physical_namespace,
                provider_write_fence,
            )
        )
        with self._transaction() as cursor:
            self._lock_identities(
                cursor,
                (
                    f"generation:{generation_id}",
                    f"physical-namespace:{physical_namespace}",
                ),
            )
            cursor.execute(
                f"""
                SELECT generation_id, scope_id, build_snapshot_id,
                       build_snapshot_fingerprint,
                       evaluation_ruler_fingerprint, expected_manifest_digest,
                       physical_namespace, provider_write_fence
                FROM {SCHEMA}.generations
                WHERE generation_id = %s OR physical_namespace = %s
                FOR UPDATE
                """,
                (generation_id, physical_namespace),
            )
            existing = cursor.fetchall()
            if existing:
                row = existing[0]
                exact = len(existing) == 1 and row == (
                    generation_id,
                    snapshot.scope_id,
                    snapshot.build_snapshot_id,
                    snapshot.fingerprint,
                    ruler.fingerprint,
                    expected_manifest.fingerprint,
                    physical_namespace,
                    provider_write_fence,
                )
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY
                    if exact
                    else RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_GENERATION_REGISTRATION_REPLAY"
                    if exact
                    else "GENERATION_OR_NAMESPACE_IDENTITY_CONFLICT",
                    identity_digest=identity,
                    generation_id=generation_id,
                )
            cursor.execute(
                f"""
                SELECT current.snapshot_fingerprint
                FROM {SCHEMA}.current_build_snapshots AS selected
                JOIN {SCHEMA}.build_snapshots AS current
                  ON current.build_snapshot_id = selected.build_snapshot_id
                WHERE selected.scope_id = %s
                FOR UPDATE OF selected
                """,
                (snapshot.scope_id,),
            )
            current_snapshot = cursor.fetchone()
            if current_snapshot is None or current_snapshot[0] != snapshot.fingerprint:
                return RepositoryResult(
                    RepositoryOutcome.STALE_POINTER,
                    "BUILD_SNAPSHOT_IS_NOT_CURRENT",
                )
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.generations
                    (generation_id, scope_id, build_snapshot_id,
                     build_snapshot_fingerprint, evaluation_ruler_fingerprint,
                     expected_manifest_digest, physical_namespace,
                     provider_write_fence, state, state_version,
                     transition_fence, active_readers, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                        'BUILDING', 1, 0, 0, %s, %s)
                """,
                (
                    generation_id,
                    snapshot.scope_id,
                    snapshot.build_snapshot_id,
                    snapshot.fingerprint,
                    ruler.fingerprint,
                    expected_manifest.fingerprint,
                    physical_namespace,
                    provider_write_fence,
                    timestamp,
                    timestamp,
                ),
            )
            return RepositoryResult(
                RepositoryOutcome.APPLIED,
                "GENERATION_BUILD_REGISTERED",
                durable_transition=True,
                identity_digest=identity,
                generation_id=generation_id,
                state_version=1,
            )

    def write_generation_points(
        self,
        *,
        generation_id: str,
        provider_write_fence: int,
        points: tuple[PgVectorPoint, ...],
        created_at: str,
    ) -> RepositoryResult:
        _require_text(generation_id, created_at)
        if any(item.generation_id != generation_id for item in points):
            raise ValueError("one write cannot mix generation identities")
        write_digest = points_identity_digest(points)
        timestamp = parse_aware_datetime(created_at, label="point created-at")
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT state, provider_write_fence, sealed_at
                FROM {SCHEMA}.generations
                WHERE generation_id = %s
                FOR UPDATE
                """,
                (generation_id,),
            )
            generation = cursor.fetchone()
            if generation is None:
                return RepositoryResult(
                    RepositoryOutcome.NOT_FOUND,
                    "GENERATION_NOT_FOUND",
                )
            state, current_fence, sealed_at = generation
            if int(current_fence) != provider_write_fence:
                return RepositoryResult(
                    RepositoryOutcome.STALE_FENCE,
                    "PROVIDER_WRITE_FENCE_NOT_CURRENT",
                )
            cursor.execute(
                f"""
                SELECT point_id, occurrence_id, tenant_id, content_digest,
                       metadata_digest, provenance_digest, vector_digest,
                       metadata
                FROM {SCHEMA}.index_points
                WHERE generation_id = %s
                ORDER BY point_id
                """,
                (generation_id,),
            )
            existing_rows = cursor.fetchall()
            if existing_rows:
                observed = stable_hash(
                    tuple(
                        stable_hash(
                            {
                                "point_id": row[0],
                                "generation_id": generation_id,
                                "occurrence_id": row[1],
                                "tenant_id": row[2],
                                "content_digest": row[3],
                                "metadata_digest": row[4],
                                "provenance_digest": row[5],
                                "vector_digest": row[6],
                                "metadata": tuple(sorted((row[7] or {}).items())),
                            }
                        )
                        for row in existing_rows
                    )
                )
                exact = observed == write_digest
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY
                    if exact
                    else RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_PGVECTOR_WRITE_REPLAY"
                    if exact
                    else "GENERATION_POINTS_ALREADY_BOUND_TO_OTHER_CONTENT",
                    identity_digest=write_digest,
                    generation_id=generation_id,
                )
            if state != GenerationState.BUILDING.value or sealed_at is not None:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "ONLY_UNSEALED_BUILDING_GENERATIONS_ACCEPT_POINTS",
                )
            for point in sorted(points):
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.index_points
                        (generation_id, point_id, occurrence_id, tenant_id,
                         content_digest, metadata_digest, provenance_digest,
                         vector_digest, embedding, metadata, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                            %s::vector, %s::jsonb, %s)
                    """,
                    (
                        point.generation_id,
                        point.point_id,
                        point.occurrence_id,
                        point.tenant_id,
                        point.content_digest,
                        point.metadata_digest,
                        point.provenance_digest,
                        point.vector_digest,
                        canonical_vector_literal(point.embedding),
                        json.dumps(dict(point.metadata), sort_keys=True),
                        timestamp,
                    ),
                )
            return RepositoryResult(
                RepositoryOutcome.APPLIED,
                "PGVECTOR_GENERATION_WRITTEN_OFF_ACTIVE_PATH",
                durable_transition=True,
                identity_digest=write_digest,
                generation_id=generation_id,
            )

    @staticmethod
    def _readback_manifest(
        cursor: CursorPort,
        generation_id: str,
    ) -> ManifestFacts:
        cursor.execute(
            f"""
            SELECT occurrence_id, content_digest,
                   metadata_digest, provenance_digest
            FROM {SCHEMA}.index_points
            WHERE generation_id = %s
            ORDER BY occurrence_id
            """,
            (generation_id,),
        )
        return manifest_from_point_rows(cursor.fetchall())

    def readback_manifest(self, generation_id: str) -> ManifestFacts | None:
        _require_text(generation_id)
        with self._transaction() as cursor:
            cursor.execute(
                f"SELECT 1 FROM {SCHEMA}.generations WHERE generation_id = %s",
                (generation_id,),
            )
            if cursor.fetchone() is None:
                return None
            return self._readback_manifest(cursor, generation_id)

    def seal_generation(
        self,
        *,
        generation_id: str,
        expected_manifest: ManifestFacts,
        expected_absent_occurrence_ids: tuple[str, ...],
        provider_write_fence: int,
        observed_at: str,
    ) -> RepositoryResult:
        if expected_absent_occurrence_ids != tuple(
            sorted(expected_absent_occurrence_ids)
        ) or len(set(expected_absent_occurrence_ids)) != len(
            expected_absent_occurrence_ids
        ):
            raise ValueError("expected-absent IDs must be sorted and unique")
        timestamp = parse_aware_datetime(observed_at, label="seal observed-at")
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT state, state_version, transition_fence,
                       expected_manifest_digest, physical_namespace,
                       provider_write_fence, checkpoint, sealed_at
                FROM {SCHEMA}.generations
                WHERE generation_id = %s
                FOR UPDATE
                """,
                (generation_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return RepositoryResult(
                    RepositoryOutcome.NOT_FOUND,
                    "GENERATION_NOT_FOUND",
                )
            (
                state,
                state_version,
                transition_fence,
                stored_expected,
                namespace,
                stored_fence,
                stored_checkpoint,
                sealed_at,
            ) = row
            if int(stored_fence) != provider_write_fence:
                return RepositoryResult(
                    RepositoryOutcome.STALE_FENCE,
                    "PROVIDER_WRITE_FENCE_NOT_CURRENT",
                )
            if stored_expected != expected_manifest.fingerprint:
                return RepositoryResult(
                    RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXPECTED_MANIFEST_BINDING_CHANGED",
                )
            actual = self._readback_manifest(cursor, generation_id)
            manifest = GenerationManifest(
                expected=expected_manifest,
                actual=actual,
                expected_absent_occurrence_ids=expected_absent_occurrence_ids,
            )
            checkpoint = stable_hash(
                (
                    "PGVECTOR_READBACK",
                    generation_id,
                    namespace,
                    provider_write_fence,
                    actual.fingerprint,
                )
            )
            if state in {
                GenerationState.VALIDATING.value,
                GenerationState.READY.value,
                GenerationState.ACTIVE.value,
                GenerationState.DRAINING.value,
            }:
                exact = (
                    sealed_at is not None
                    and stored_checkpoint == checkpoint
                    and manifest.integrity_matches
                )
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY
                    if exact
                    else RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_GENERATION_SEAL_REPLAY"
                    if exact
                    else "SEALED_GENERATION_READBACK_CHANGED",
                    generation_id=generation_id,
                    state_version=int(state_version),
                    checkpoint=checkpoint,
                    manifest=manifest,
                )
            if state != GenerationState.BUILDING.value:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "GENERATION_NOT_BUILDING",
                )
            next_state = (
                GenerationState.VALIDATING.value
                if manifest.integrity_matches
                else GenerationState.FAILED.value
            )
            cursor.execute(
                "SELECT set_config('day104_l3.transition_reason', %s, true)",
                ("INDEPENDENT_PGVECTOR_READBACK",),
            )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.generations
                SET actual_manifest_digest = %s, manifest_digest = %s,
                    checkpoint = %s, sealed_at = %s, state = %s,
                    state_version = state_version + 1,
                    transition_fence = transition_fence + 1,
                    updated_at = %s
                WHERE generation_id = %s AND state_version = %s
                """,
                (
                    actual.fingerprint,
                    manifest.digest,
                    checkpoint,
                    timestamp,
                    next_state,
                    timestamp,
                    generation_id,
                    state_version,
                ),
            )
            if cursor.rowcount != 1:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "GENERATION_STATE_VERSION_CHANGED",
                )
            if not manifest.integrity_matches:
                return RepositoryResult(
                    RepositoryOutcome.INTEGRITY_FAILED,
                    "PGVECTOR_READBACK_MANIFEST_MISMATCH",
                    durable_transition=True,
                    generation_id=generation_id,
                    state_version=int(state_version) + 1,
                    checkpoint=checkpoint,
                    manifest=manifest,
                )
            return RepositoryResult(
                RepositoryOutcome.APPLIED,
                "PGVECTOR_GENERATION_SEALED_AND_READ_BACK",
                durable_transition=True,
                generation_id=generation_id,
                state_version=int(state_version) + 1,
                checkpoint=checkpoint,
                manifest=manifest,
            )

    def mark_ready(
        self,
        *,
        generation_id: str,
        expected_state_version: int,
        expected_manifest: ManifestFacts,
        expected_absent_occurrence_ids: tuple[str, ...],
        ruler: EvaluationRuler,
        validation_record_digest: str,
        evaluation_evidence_digest: str,
        evaluation_report_digest: str,
        evaluation_decision: str,
        observed_at: str,
    ) -> RepositoryResult:
        _require_text(
            generation_id,
            validation_record_digest,
            evaluation_evidence_digest,
            evaluation_report_digest,
            evaluation_decision,
        )
        timestamp = parse_aware_datetime(observed_at, label="READY observed-at")
        with self._transaction() as cursor:
            cursor.execute(
                "SELECT set_config('day104_l3.transition_reason', %s, true)",
                ("MANIFEST_AND_EVALUATION_GATES_PASSED",),
            )
            cursor.execute(
                f"""
                SELECT generation.scope_id, generation.build_snapshot_id,
                       generation.build_snapshot_fingerprint,
                       generation.evaluation_ruler_fingerprint,
                       generation.expected_manifest_digest,
                       generation.actual_manifest_digest,
                       generation.manifest_digest,
                       generation.validation_record_digest,
                       generation.evaluation_evidence_digest,
                       generation.evaluation_report_digest,
                       generation.state,
                       generation.state_version, generation.transition_fence,
                       generation.checkpoint, generation.sealed_at,
                       current.snapshot_fingerprint
                FROM {SCHEMA}.generations AS generation
                JOIN {SCHEMA}.current_build_snapshots AS selected
                  ON selected.scope_id = generation.scope_id
                JOIN {SCHEMA}.build_snapshots AS current
                  ON current.build_snapshot_id = selected.build_snapshot_id
                WHERE generation.generation_id = %s
                FOR UPDATE OF generation, selected
                """,
                (generation_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return RepositoryResult(
                    RepositoryOutcome.NOT_FOUND,
                    "GENERATION_NOT_FOUND",
                )
            (
                _scope_id,
                _snapshot_id,
                snapshot_fingerprint,
                ruler_fingerprint,
                stored_expected,
                stored_actual,
                stored_manifest,
                stored_validation,
                stored_evaluation,
                stored_report,
                state,
                state_version,
                _transition_fence,
                checkpoint,
                sealed_at,
                current_snapshot_fingerprint,
            ) = row
            manifest = GenerationManifest(
                expected=expected_manifest,
                actual=expected_manifest,
                expected_absent_occurrence_ids=expected_absent_occurrence_ids,
            )
            if state == GenerationState.READY.value:
                exact = all(
                    (
                        snapshot_fingerprint == current_snapshot_fingerprint,
                        ruler_fingerprint == ruler.fingerprint,
                        stored_expected == expected_manifest.fingerprint,
                        stored_actual == expected_manifest.fingerprint,
                        stored_manifest == manifest.digest,
                        stored_validation == validation_record_digest,
                        stored_evaluation == evaluation_evidence_digest,
                        stored_report == evaluation_report_digest,
                        evaluation_decision == "PASS",
                        checkpoint is not None,
                        sealed_at is not None,
                    )
                )
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY
                    if exact
                    else RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_READY_REPLAY" if exact else "READY_BINDING_CHANGED",
                    generation_id=generation_id,
                    state_version=int(state_version),
                    checkpoint=cast(str | None, checkpoint),
                )
            if (
                state != GenerationState.VALIDATING.value
                or int(state_version) != expected_state_version
            ):
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "GENERATION_NOT_AT_EXPECTED_VALIDATING_VERSION",
                    generation_id=generation_id,
                    state_version=int(state_version),
                )
            bindings_match = all(
                (
                    snapshot_fingerprint == current_snapshot_fingerprint,
                    ruler_fingerprint == ruler.fingerprint,
                    stored_expected == expected_manifest.fingerprint,
                    stored_actual == expected_manifest.fingerprint,
                    stored_manifest == manifest.digest,
                    checkpoint is not None,
                    sealed_at is not None,
                )
            )
            if not bindings_match:
                return RepositoryResult(
                    RepositoryOutcome.IDENTITY_CONFLICT,
                    "READY_EVIDENCE_OR_CURRENT_SNAPSHOT_MISMATCH",
                )
            if evaluation_decision != "PASS":
                return RepositoryResult(
                    RepositoryOutcome.INTEGRITY_FAILED,
                    "READY_REQUIRES_PASSING_EVALUATION",
                )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.generations
                SET validation_record_digest = %s,
                    evaluation_evidence_digest = %s,
                    evaluation_report_digest = %s,
                    state = 'READY', state_version = state_version + 1,
                    transition_fence = transition_fence + 1,
                    updated_at = %s
                WHERE generation_id = %s AND state = 'VALIDATING'
                  AND state_version = %s
                """,
                (
                    validation_record_digest,
                    evaluation_evidence_digest,
                    evaluation_report_digest,
                    timestamp,
                    generation_id,
                    expected_state_version,
                ),
            )
            if cursor.rowcount != 1:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "READY_CAS_FAILED",
                )
            return RepositoryResult(
                RepositoryOutcome.READY,
                "GENERATION_READY_WITH_BOUND_EVIDENCE",
                durable_transition=True,
                generation_id=generation_id,
                state_version=expected_state_version + 1,
                checkpoint=cast(str, checkpoint),
            )

    def seed_pointer(
        self,
        *,
        pointer_name: str,
        scope_id: str,
        generation_id: str,
        revision: int,
        seeded_at: str,
    ) -> RepositoryResult:
        _require_text(pointer_name, scope_id, generation_id)
        if revision <= 0:
            raise ValueError("pointer revision must be positive")
        timestamp = parse_aware_datetime(seeded_at, label="pointer seeded-at")
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT scope_id, generation_id, revision
                FROM {SCHEMA}.active_pointers
                WHERE pointer_name = %s
                FOR UPDATE
                """,
                (pointer_name,),
            )
            existing = cursor.fetchone()
            if existing is not None:
                exact = existing == (scope_id, generation_id, revision)
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY
                    if exact
                    else RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_POINTER_SEED_REPLAY" if exact else "POINTER_ALREADY_SEEDED",
                    generation_id=cast(str, existing[1]),
                    revision=int(existing[2]),
                )
            cursor.execute(
                f"""
                SELECT state, state_version
                FROM {SCHEMA}.generations
                WHERE generation_id = %s AND scope_id = %s
                FOR UPDATE
                """,
                (generation_id, scope_id),
            )
            generation = cursor.fetchone()
            if generation is None:
                return RepositoryResult(
                    RepositoryOutcome.NOT_FOUND,
                    "GENERATION_NOT_FOUND",
                )
            if generation[0] != GenerationState.READY.value:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "ONLY_READY_GENERATION_CAN_SEED_POINTER",
                )
            cursor.execute(
                "SELECT set_config('day104_l3.transition_reason', %s, true)",
                ("INITIAL_POINTER_SEED",),
            )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.generations
                SET state = 'ACTIVE', state_version = state_version + 1,
                    transition_fence = transition_fence + 1,
                    updated_at = %s
                WHERE generation_id = %s AND state = 'READY'
                  AND state_version = %s
                """,
                (timestamp, generation_id, generation[1]),
            )
            if cursor.rowcount != 1:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "POINTER_SEED_GENERATION_CAS_FAILED",
                )
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.active_pointers
                    (pointer_name, scope_id, generation_id, revision, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (pointer_name, scope_id, generation_id, revision, timestamp),
            )
            return RepositoryResult(
                RepositoryOutcome.APPLIED,
                "ACTIVE_POINTER_SEEDED",
                durable_transition=True,
                generation_id=generation_id,
                revision=revision,
            )

    def issue_activation_lease(
        self,
        *,
        pointer_name: str,
        committer_id: str,
        issued_at: str,
        lease_expires_at: str,
    ) -> ActivationLeaseRecord:
        _require_text(pointer_name, committer_id)
        issued = parse_aware_datetime(issued_at, label="lease issued-at")
        expires = parse_aware_datetime(lease_expires_at, label="lease expiry")
        if expires <= issued:
            raise ValueError("activation lease must expire after issuance")
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT committer_id, fencing_token
                FROM {SCHEMA}.activation_leases
                WHERE pointer_name = %s
                FOR UPDATE
                """,
                (pointer_name,),
            )
            current = cursor.fetchone()
            if current is not None:
                raise ValueError(
                    "activation lease already exists; use fenced CAS rotation"
                )
            token = 1
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.activation_leases
                    (pointer_name, committer_id, fencing_token,
                     issued_at, lease_expires_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (pointer_name, committer_id, token, issued, expires),
            )
        return ActivationLeaseRecord(
            pointer_name,
            committer_id,
            token,
            issued_at,
            lease_expires_at,
        )

    def rotate_activation_lease(
        self,
        *,
        pointer_name: str,
        expected_committer_id: str,
        expected_fencing_token: int,
        new_committer_id: str,
        issued_at: str,
        lease_expires_at: str,
    ) -> ActivationLeaseRecord | None:
        _require_text(pointer_name, expected_committer_id, new_committer_id)
        issued = parse_aware_datetime(issued_at, label="lease issued-at")
        expires = parse_aware_datetime(lease_expires_at, label="lease expiry")
        if expires <= issued:
            raise ValueError("activation lease must expire after issuance")
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT committer_id, fencing_token
                FROM {SCHEMA}.activation_leases
                WHERE pointer_name = %s
                FOR UPDATE
                """,
                (pointer_name,),
            )
            current = cursor.fetchone()
            if current != (expected_committer_id, expected_fencing_token):
                return None
            token = expected_fencing_token + 1
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.activation_leases
                SET committer_id = %s, fencing_token = %s,
                    issued_at = %s, lease_expires_at = %s
                WHERE pointer_name = %s AND committer_id = %s
                  AND fencing_token = %s
                """,
                (
                    new_committer_id,
                    token,
                    issued,
                    expires,
                    pointer_name,
                    expected_committer_id,
                    expected_fencing_token,
                ),
            )
            if cursor.rowcount != 1:
                return None
        return ActivationLeaseRecord(
            pointer_name,
            new_committer_id,
            token,
            issued_at,
            lease_expires_at,
        )

    def activate(
        self,
        *,
        activation_id: str,
        pointer_name: str,
        target_generation_id: str,
        expected_generation_id: str,
        expected_revision: int,
        committer_id: str,
        committer_fence: int,
        committed_at: str,
        previous_retire_after: str,
    ) -> RepositoryResult:
        _require_text(
            activation_id,
            pointer_name,
            target_generation_id,
            expected_generation_id,
            committer_id,
            committed_at,
            previous_retire_after,
        )
        if target_generation_id == expected_generation_id:
            raise ValueError("activation must change generations")
        committed = parse_aware_datetime(committed_at, label="activation time")
        retire_after = parse_aware_datetime(
            previous_retire_after,
            label="retire-after",
        )
        if retire_after <= committed:
            raise ValueError("retire-after must be later than activation")
        record_digest = stable_hash(
            {
                "activation_id": activation_id,
                "pointer_name": pointer_name,
                "from_generation_id": expected_generation_id,
                "to_generation_id": target_generation_id,
                "from_revision": expected_revision,
                "to_revision": expected_revision + 1,
                "committer_id": committer_id,
                "committer_fence": committer_fence,
                "committed_at": committed_at,
            }
        )
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT record_digest
                FROM {SCHEMA}.activation_records
                WHERE activation_id = %s
                FOR UPDATE
                """,
                (activation_id,),
            )
            existing = cursor.fetchone()
            if existing is not None:
                exact = existing[0] == record_digest
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY
                    if exact
                    else RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_ACTIVATION_REPLAY"
                    if exact
                    else "ACTIVATION_ID_ALREADY_BOUND",
                    identity_digest=record_digest,
                    generation_id=target_generation_id,
                    revision=expected_revision + 1,
                )
            cursor.execute(
                f"""
                SELECT generation_id, revision, scope_id
                FROM {SCHEMA}.active_pointers
                WHERE pointer_name = %s
                FOR UPDATE
                """,
                (pointer_name,),
            )
            pointer = cursor.fetchone()
            if pointer is None:
                return RepositoryResult(
                    RepositoryOutcome.NOT_FOUND,
                    "ACTIVE_POINTER_NOT_FOUND",
                )
            if (
                pointer[0] != expected_generation_id
                or int(pointer[1]) != expected_revision
            ):
                return RepositoryResult(
                    RepositoryOutcome.STALE_POINTER,
                    "ACTIVE_POINTER_CAS_MISMATCH",
                    generation_id=cast(str, pointer[0]),
                    revision=int(pointer[1]),
                )
            cursor.execute(
                f"""
                SELECT committer_id, fencing_token, lease_expires_at
                FROM {SCHEMA}.activation_leases
                WHERE pointer_name = %s
                FOR UPDATE
                """,
                (pointer_name,),
            )
            lease = cursor.fetchone()
            if (
                lease is None
                or lease[0] != committer_id
                or int(lease[1]) != committer_fence
                or cast(datetime, lease[2]) <= committed
            ):
                return RepositoryResult(
                    RepositoryOutcome.STALE_FENCE,
                    "ACTIVATION_LEASE_OR_FENCE_NOT_CURRENT",
                )
            cursor.execute(
                f"""
                SELECT generation_id, state, state_version,
                       build_snapshot_fingerprint, scope_id
                FROM {SCHEMA}.generations
                WHERE generation_id IN (%s, %s)
                ORDER BY generation_id
                FOR UPDATE
                """,
                (expected_generation_id, target_generation_id),
            )
            generations = {row[0]: row for row in cursor.fetchall()}
            if set(generations) != {
                expected_generation_id,
                target_generation_id,
            }:
                return RepositoryResult(
                    RepositoryOutcome.NOT_FOUND,
                    "ACTIVATION_GENERATION_NOT_FOUND",
                )
            previous = generations[expected_generation_id]
            target = generations[target_generation_id]
            if previous[1] != GenerationState.ACTIVE.value:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "EXPECTED_GENERATION_NOT_ACTIVE",
                )
            if target[1] != GenerationState.READY.value:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "TARGET_GENERATION_NOT_READY",
                )
            if previous[4] != pointer[2] or target[4] != pointer[2]:
                return RepositoryResult(
                    RepositoryOutcome.IDENTITY_CONFLICT,
                    "ACTIVATION_GENERATION_SCOPE_MISMATCH",
                )
            cursor.execute(
                f"""
                SELECT snapshot.snapshot_fingerprint
                FROM {SCHEMA}.current_build_snapshots AS selected
                JOIN {SCHEMA}.build_snapshots AS snapshot
                  ON snapshot.build_snapshot_id = selected.build_snapshot_id
                WHERE selected.scope_id = %s
                FOR UPDATE OF selected
                """,
                (pointer[2],),
            )
            current_snapshot = cursor.fetchone()
            if current_snapshot is None or current_snapshot[0] != target[3]:
                return RepositoryResult(
                    RepositoryOutcome.STALE_POINTER,
                    "TARGET_BUILD_SNAPSHOT_IS_NOT_CURRENT",
                )
            next_revision = expected_revision + 1
            cursor.execute(
                "SELECT set_config('day104_l3.transition_reason', %s, true)",
                ("POINTER_ACTIVATION",),
            )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.generations
                SET state = 'ACTIVE', state_version = state_version + 1,
                    transition_fence = transition_fence + 1,
                    updated_at = %s
                WHERE generation_id = %s AND state = 'READY'
                  AND state_version = %s
                """,
                (committed, target_generation_id, target[2]),
            )
            if cursor.rowcount != 1:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "TARGET_ACTIVATION_CAS_FAILED",
                )
            cursor.execute(
                "SELECT set_config('day104_l3.transition_reason', %s, true)",
                ("SUCCESSOR_ACTIVATED",),
            )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.generations
                SET state = 'DRAINING', state_version = state_version + 1,
                    transition_fence = transition_fence + 1,
                    retire_after = %s, updated_at = %s
                WHERE generation_id = %s AND state = 'ACTIVE'
                  AND state_version = %s
                """,
                (
                    retire_after,
                    committed,
                    expected_generation_id,
                    previous[2],
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("previous Generation drain CAS failed")
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.active_pointers
                SET generation_id = %s, revision = %s, updated_at = %s
                WHERE pointer_name = %s AND generation_id = %s
                  AND revision = %s
                """,
                (
                    target_generation_id,
                    next_revision,
                    committed,
                    pointer_name,
                    expected_generation_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("active pointer CAS failed after lifecycle updates")
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.activation_records
                    (activation_id, pointer_name, from_generation_id,
                     to_generation_id, from_revision, to_revision,
                     committer_id, committer_fence, record_digest, committed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    activation_id,
                    pointer_name,
                    expected_generation_id,
                    target_generation_id,
                    expected_revision,
                    next_revision,
                    committer_id,
                    committer_fence,
                    record_digest,
                    committed,
                ),
            )
            payload_digest = stable_hash(
                (
                    pointer_name,
                    target_generation_id,
                    next_revision,
                    record_digest,
                )
            )
            event_id = stable_hash(("INDEX_POINTER_CHANGED", payload_digest))
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.outbox_events
                    (event_id, event_type, aggregate_id, aggregate_revision,
                     payload_digest, state, created_at)
                VALUES (%s, 'INDEX_POINTER_CHANGED', %s, %s, %s,
                        'PENDING', %s)
                """,
                (
                    event_id,
                    pointer_name,
                    next_revision,
                    payload_digest,
                    committed,
                ),
            )
            return RepositoryResult(
                RepositoryOutcome.ACTIVATED,
                "POINTER_AND_LIFECYCLES_COMMITTED_WITH_OUTBOX",
                durable_transition=True,
                identity_digest=record_digest,
                generation_id=target_generation_id,
                revision=next_revision,
            )

    def acquire_read_view(
        self,
        *,
        view_id: str,
        pointer_name: str,
        expected_generation_id: str,
        expected_pointer_revision: int,
        owner_id: str,
        authorization_snapshot_id: str,
        acquired_at: str,
        lease_expires_at: str,
    ) -> RepositoryResult:
        _require_text(
            view_id,
            pointer_name,
            expected_generation_id,
            owner_id,
            authorization_snapshot_id,
        )
        acquired = parse_aware_datetime(acquired_at, label="ReadView acquired-at")
        expires = parse_aware_datetime(lease_expires_at, label="ReadView expiry")
        if expires <= acquired:
            raise ValueError("ReadView lease must expire after acquisition")
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT pointer_name, generation_id, pointer_revision,
                       owner_id, authorization_snapshot_id, status
                FROM {SCHEMA}.read_views
                WHERE view_id = %s
                FOR UPDATE
                """,
                (view_id,),
            )
            existing = cursor.fetchone()
            if existing is not None:
                exact = existing == (
                    pointer_name,
                    expected_generation_id,
                    expected_pointer_revision,
                    owner_id,
                    authorization_snapshot_id,
                    "OPEN",
                )
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY
                    if exact
                    else RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_READ_VIEW_ACQUIRE_REPLAY"
                    if exact
                    else "READ_VIEW_ID_ALREADY_BOUND",
                    generation_id=cast(str, existing[1]),
                    revision=int(existing[2]),
                )
            cursor.execute(
                f"""
                SELECT generation_id, revision
                FROM {SCHEMA}.active_pointers
                WHERE pointer_name = %s
                FOR UPDATE
                """,
                (pointer_name,),
            )
            pointer = cursor.fetchone()
            if pointer != (expected_generation_id, expected_pointer_revision):
                return RepositoryResult(
                    RepositoryOutcome.STALE_POINTER,
                    "READ_VIEW_POINTER_CHANGED",
                    generation_id=None if pointer is None else cast(str, pointer[0]),
                    revision=None if pointer is None else int(pointer[1]),
                )
            cursor.execute(
                f"""
                SELECT state, state_version, build_snapshot_fingerprint
                FROM {SCHEMA}.generations
                WHERE generation_id = %s
                FOR UPDATE
                """,
                (expected_generation_id,),
            )
            generation = cursor.fetchone()
            if generation is None or generation[0] != GenerationState.ACTIVE.value:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "READ_VIEW_REQUIRES_ACTIVE_GENERATION",
                )
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.read_views
                    (view_id, pointer_name, generation_id, pointer_revision,
                     owner_id, build_snapshot_fingerprint,
                     authorization_snapshot_id, status, fencing_token,
                     lease_expires_at, last_heartbeat_at, acquired_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'OPEN', 1,
                        %s, %s, %s)
                """,
                (
                    view_id,
                    pointer_name,
                    expected_generation_id,
                    expected_pointer_revision,
                    owner_id,
                    generation[2],
                    authorization_snapshot_id,
                    expires,
                    acquired,
                    acquired,
                ),
            )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.generations
                SET active_readers = active_readers + 1,
                    state_version = state_version + 1,
                    updated_at = %s
                WHERE generation_id = %s AND state = 'ACTIVE'
                  AND state_version = %s
                """,
                (acquired, expected_generation_id, generation[1]),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("ReadView reader increment CAS failed")
            return RepositoryResult(
                RepositoryOutcome.APPLIED,
                "READ_VIEW_PINNED_TO_ONE_GENERATION",
                durable_transition=True,
                generation_id=expected_generation_id,
                revision=expected_pointer_revision,
                state_version=int(generation[1]) + 1,
            )

    def release_read_view(
        self,
        *,
        view_id: str,
        expected_fencing_token: int,
        released_at: str,
    ) -> RepositoryResult:
        timestamp = parse_aware_datetime(released_at, label="ReadView released-at")
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT generation_id, status, fencing_token
                FROM {SCHEMA}.read_views
                WHERE view_id = %s
                FOR UPDATE
                """,
                (view_id,),
            )
            view = cursor.fetchone()
            if view is None:
                return RepositoryResult(
                    RepositoryOutcome.NOT_FOUND,
                    "READ_VIEW_NOT_FOUND",
                )
            if int(view[2]) != expected_fencing_token:
                return RepositoryResult(
                    RepositoryOutcome.STALE_FENCE,
                    "READ_VIEW_FENCE_NOT_CURRENT",
                )
            if view[1] != "OPEN":
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "READ_VIEW_ALREADY_CLOSED",
                )
            cursor.execute(
                f"""
                SELECT state_version, active_readers
                FROM {SCHEMA}.generations
                WHERE generation_id = %s
                FOR UPDATE
                """,
                (view[0],),
            )
            generation = cursor.fetchone()
            if generation is None or int(generation[1]) <= 0:
                raise RuntimeError("ReadView ledger and reader counter diverged")
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.read_views
                SET status = 'CLOSED', fencing_token = fencing_token + 1,
                    last_heartbeat_at = %s, closed_at = %s
                WHERE view_id = %s AND status = 'OPEN'
                  AND fencing_token = %s
                """,
                (timestamp, timestamp, view_id, expected_fencing_token),
            )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.generations
                SET active_readers = active_readers - 1,
                    state_version = state_version + 1,
                    updated_at = %s
                WHERE generation_id = %s AND state_version = %s
                  AND active_readers > 0
                """,
                (timestamp, view[0], generation[0]),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("ReadView reader decrement CAS failed")
            return RepositoryResult(
                RepositoryOutcome.APPLIED,
                "READ_VIEW_CLOSED_ONCE",
                durable_transition=True,
                generation_id=cast(str, view[0]),
                state_version=int(generation[0]) + 1,
            )

    def reap_expired_read_views(
        self,
        *,
        observed_at: str,
        limit: int = 100,
    ) -> tuple[str, ...]:
        if limit <= 0:
            raise ValueError("ReadView reaper limit must be positive")
        timestamp = parse_aware_datetime(
            observed_at,
            label="ReadView reaper time",
        )
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT view_id, generation_id, fencing_token
                FROM {SCHEMA}.read_views
                WHERE status = 'OPEN' AND lease_expires_at <= %s
                ORDER BY generation_id, view_id
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (timestamp, limit),
            )
            expired = cursor.fetchall()
            reaped: list[str] = []
            for view_id, generation_id, fencing_token in expired:
                cursor.execute(
                    f"""
                    SELECT state_version, active_readers
                    FROM {SCHEMA}.generations
                    WHERE generation_id = %s
                    FOR UPDATE
                    """,
                    (generation_id,),
                )
                generation = cursor.fetchone()
                if generation is None or int(generation[1]) <= 0:
                    raise RuntimeError(
                        "expired ReadView ledger and reader counter diverged"
                    )
                cursor.execute(
                    f"""
                    UPDATE {SCHEMA}.read_views
                    SET status = 'EXPIRED', fencing_token = fencing_token + 1,
                        closed_at = %s
                    WHERE view_id = %s AND status = 'OPEN'
                      AND fencing_token = %s AND lease_expires_at <= %s
                    """,
                    (timestamp, view_id, fencing_token, timestamp),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("expired ReadView CAS failed")
                cursor.execute(
                    f"""
                    UPDATE {SCHEMA}.generations
                    SET active_readers = active_readers - 1,
                        state_version = state_version + 1,
                        updated_at = %s
                    WHERE generation_id = %s AND state_version = %s
                      AND active_readers > 0
                    """,
                    (timestamp, generation_id, generation[0]),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("expired ReadView decrement CAS failed")
                reaped.append(cast(str, view_id))
            return tuple(reaped)

    def retire_generation(
        self,
        *,
        generation_id: str,
        expected_state_version: int,
        retired_at: str,
    ) -> RepositoryResult:
        timestamp = parse_aware_datetime(retired_at, label="retirement time")
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT state, state_version, active_readers, retire_after
                FROM {SCHEMA}.generations
                WHERE generation_id = %s
                FOR UPDATE
                """,
                (generation_id,),
            )
            generation = cursor.fetchone()
            if generation is None:
                return RepositoryResult(
                    RepositoryOutcome.NOT_FOUND,
                    "GENERATION_NOT_FOUND",
                )
            if (
                generation[0] != GenerationState.DRAINING.value
                or int(generation[1]) != expected_state_version
            ):
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "GENERATION_NOT_AT_EXPECTED_DRAINING_VERSION",
                    state_version=int(generation[1]),
                )
            cursor.execute(
                f"""
                SELECT count(*)
                FROM {SCHEMA}.read_views
                WHERE generation_id = %s AND status = 'OPEN'
                """,
                (generation_id,),
            )
            count_row = cursor.fetchone()
            if count_row is None:
                raise RuntimeError("ReadView count query returned no row")
            open_views = int(count_row[0])
            if open_views or int(generation[2]) != 0:
                return RepositoryResult(
                    RepositoryOutcome.READERS_PRESENT,
                    "OPEN_READ_VIEWS_MUST_DRAIN",
                )
            retire_after = generation[3]
            if retire_after is None or cast(datetime, retire_after) > timestamp:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "ROLLBACK_RETENTION_WINDOW_NOT_SATISFIED",
                )
            cursor.execute(
                "SELECT set_config('day104_l3.transition_reason', %s, true)",
                ("READERS_DRAINED_AND_RETENTION_MET",),
            )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.generations
                SET state = 'RETIRED', state_version = state_version + 1,
                    transition_fence = transition_fence + 1,
                    updated_at = %s
                WHERE generation_id = %s AND state = 'DRAINING'
                  AND state_version = %s AND active_readers = 0
                """,
                (timestamp, generation_id, expected_state_version),
            )
            if cursor.rowcount != 1:
                return RepositoryResult(
                    RepositoryOutcome.STALE_STATE,
                    "RETIREMENT_CAS_FAILED",
                )
            return RepositoryResult(
                RepositoryOutcome.RETIRED,
                "GENERATION_RETIRED_WITHOUT_PHYSICAL_PURGE_CLAIM",
                durable_transition=True,
                generation_id=generation_id,
                state_version=expected_state_version + 1,
            )

    def claim_outbox(
        self,
        *,
        worker_id: str,
        claimed_at: str,
    ) -> OutboxClaim | None:
        _require_text(worker_id)
        timestamp = parse_aware_datetime(claimed_at, label="outbox claimed-at")
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT event_id, event_type, aggregate_id,
                       aggregate_revision, payload_digest, claim_fence
                FROM {SCHEMA}.outbox_events
                WHERE state = 'PENDING'
                ORDER BY created_at, event_id
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """
            )
            event = cursor.fetchone()
            if event is None:
                return None
            next_fence = int(event[5] or 0) + 1
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.outbox_events
                SET state = 'PROCESSING', claim_owner = %s,
                    claim_fence = %s, claimed_at = %s
                WHERE event_id = %s AND state = 'PENDING'
                """,
                (worker_id, next_fence, timestamp, event[0]),
            )
            if cursor.rowcount != 1:
                return None
            return OutboxClaim(
                event_id=cast(str, event[0]),
                event_type=cast(str, event[1]),
                aggregate_id=cast(str, event[2]),
                aggregate_revision=int(event[3]),
                payload_digest=cast(str, event[4]),
                claim_owner=worker_id,
                claim_fence=next_fence,
                claimed_at=claimed_at,
            )

    def reclaim_stale_outbox(
        self,
        *,
        worker_id: str,
        reclaimed_at: str,
        processing_timeout_seconds: float,
    ) -> OutboxClaim | None:
        _require_text(worker_id)
        if processing_timeout_seconds <= 0:
            raise ValueError("processing timeout must be positive")
        timestamp = parse_aware_datetime(
            reclaimed_at,
            label="outbox reclaimed-at",
        )
        stale_before = timestamp - timedelta(seconds=processing_timeout_seconds)
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT event_id, event_type, aggregate_id,
                       aggregate_revision, payload_digest, claim_fence
                FROM {SCHEMA}.outbox_events
                WHERE state = 'PROCESSING' AND claimed_at <= %s
                ORDER BY claimed_at, event_id
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """,
                (stale_before,),
            )
            event = cursor.fetchone()
            if event is None:
                return None
            next_fence = int(event[5]) + 1
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.outbox_events
                SET claim_owner = %s, claim_fence = %s, claimed_at = %s
                WHERE event_id = %s AND state = 'PROCESSING'
                  AND claimed_at <= %s AND claim_fence = %s
                """,
                (
                    worker_id,
                    next_fence,
                    timestamp,
                    event[0],
                    stale_before,
                    event[5],
                ),
            )
            if cursor.rowcount != 1:
                return None
            return OutboxClaim(
                event_id=cast(str, event[0]),
                event_type=cast(str, event[1]),
                aggregate_id=cast(str, event[2]),
                aggregate_revision=int(event[3]),
                payload_digest=cast(str, event[4]),
                claim_owner=worker_id,
                claim_fence=next_fence,
                claimed_at=reclaimed_at,
            )

    def apply_outbox(
        self,
        *,
        claim: OutboxClaim,
        payload_digest: str,
        source_stream: str,
        result_id: str,
        result_digest: str,
        applied_at: str,
    ) -> RepositoryResult:
        _require_text(
            payload_digest,
            source_stream,
            result_id,
            result_digest,
        )
        timestamp = parse_aware_datetime(applied_at, label="outbox applied-at")
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT payload_digest, state, claim_owner, claim_fence
                FROM {SCHEMA}.outbox_events
                WHERE event_id = %s
                FOR UPDATE
                """,
                (claim.event_id,),
            )
            event = cursor.fetchone()
            if event is None:
                return RepositoryResult(
                    RepositoryOutcome.NOT_FOUND,
                    "OUTBOX_EVENT_NOT_FOUND",
                )
            cursor.execute(
                f"""
                SELECT payload_digest, source_stream, state,
                       result_id, result_digest
                FROM {SCHEMA}.inbox_records
                WHERE event_id = %s
                FOR UPDATE
                """,
                (claim.event_id,),
            )
            inbox = cursor.fetchone()
            expected_inbox = (
                payload_digest,
                source_stream,
                "APPLIED",
                result_id,
                result_digest,
            )
            if event[1] == "DISPATCHED":
                exact = (
                    event[0] == payload_digest == claim.payload_digest
                    and inbox == expected_inbox
                )
                return RepositoryResult(
                    RepositoryOutcome.EXACT_REPLAY
                    if exact
                    else RepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_OUTBOX_APPLY_REPLAY" if exact else "OUTBOX_PAYLOAD_CONFLICT",
                )
            if (
                event[0] != payload_digest
                or claim.payload_digest != payload_digest
                or event[1] != "PROCESSING"
                or event[2] != claim.claim_owner
                or int(event[3]) != claim.claim_fence
            ):
                return RepositoryResult(
                    RepositoryOutcome.STALE_FENCE,
                    "OUTBOX_CLAIM_OR_PAYLOAD_NOT_CURRENT",
                )
            if inbox is not None and inbox != expected_inbox:
                return RepositoryResult(
                    RepositoryOutcome.IDENTITY_CONFLICT,
                    "INBOX_EVENT_ID_ALREADY_BOUND_TO_OTHER_RESULT",
                )
            if inbox is None:
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.inbox_records
                        (event_id, payload_digest, source_stream, state,
                         result_id, result_digest, applied_at)
                    VALUES (%s, %s, %s, 'APPLIED', %s, %s, %s)
                    """,
                    (
                        claim.event_id,
                        payload_digest,
                        source_stream,
                        result_id,
                        result_digest,
                        timestamp,
                    ),
                )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.outbox_events
                SET state = 'DISPATCHED', published_at = %s
                WHERE event_id = %s AND state = 'PROCESSING'
                  AND claim_owner = %s AND claim_fence = %s
                """,
                (
                    timestamp,
                    claim.event_id,
                    claim.claim_owner,
                    claim.claim_fence,
                ),
            )
            return RepositoryResult(
                RepositoryOutcome.APPLIED,
                "OUTBOX_EVENT_DISPATCHED_ONCE",
                durable_transition=True,
            )

    def query_generation(
        self,
        *,
        generation_id: str,
        tenant_id: str,
        query_vector: tuple[float, ...],
        top_k: int,
        mode: QueryMode,
        ef_search: int = 40,
    ) -> tuple[PgVectorHit, ...]:
        """Query a sealed Generation for validation/diagnostics.

        Online serving must use :meth:`query_read_view`, which locks and checks
        the ReadView, its fence and the current authorization snapshot in the
        same transaction as the vector query.
        """

        _require_text(generation_id, tenant_id)
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if ef_search <= 0:
            raise ValueError("ef_search must be positive")
        vector = canonical_vector_literal(query_vector)
        with self._transaction() as cursor:
            if mode is QueryMode.EXACT:
                cursor.execute("SET LOCAL enable_indexscan = off")
                cursor.execute("SET LOCAL enable_bitmapscan = off")
            elif mode is QueryMode.HNSW:
                cursor.execute(
                    "SELECT set_config('hnsw.ef_search', %s, true)",
                    (str(ef_search),),
                )
                cursor.execute("SET LOCAL enable_seqscan = off")
            else:  # pragma: no cover - Enum protects public callers
                raise ValueError("unsupported query mode")
            cursor.execute(
                f"""
                SELECT point.point_id, point.occurrence_id,
                       point.generation_id,
                       point.embedding <=> %s::vector AS cosine_distance
                FROM {SCHEMA}.index_points AS point
                JOIN {SCHEMA}.generations AS generation
                  ON generation.generation_id = point.generation_id
                WHERE point.generation_id = %s
                  AND point.tenant_id = %s
                  AND generation.sealed_at IS NOT NULL
                  AND generation.state IN
                      ('READY', 'ACTIVE', 'DRAINING')
                ORDER BY point.embedding <=> %s::vector, point.point_id
                LIMIT %s
                """,
                (vector, generation_id, tenant_id, vector, top_k),
            )
            hits: list[PgVectorHit] = []
            for row in cursor.fetchall():
                distance = float(row[3])
                if not math.isfinite(distance) or not -1e-12 <= distance <= 2.0 + 1e-12:
                    raise ValueError("pgvector returned invalid cosine distance")
                hits.append(
                    PgVectorHit(
                        cast(str, row[0]),
                        cast(str, row[1]),
                        cast(str, row[2]),
                        max(0.0, min(2.0, distance)),
                    )
                )
            return tuple(hits)

    def query_read_view(
        self,
        *,
        view_id: str,
        expected_fencing_token: int,
        expected_generation_id: str,
        expected_authorization_snapshot_id: str,
        tenant_id: str,
        query_vector: tuple[float, ...],
        top_k: int,
        mode: QueryMode,
        observed_at: str,
        ef_search: int = 40,
    ) -> tuple[PgVectorHit, ...]:
        _require_text(
            view_id,
            expected_generation_id,
            expected_authorization_snapshot_id,
            tenant_id,
        )
        if expected_fencing_token <= 0 or top_k <= 0 or ef_search <= 0:
            raise ValueError("positive fence, top_k and ef_search are required")
        now = parse_aware_datetime(observed_at, label="ReadView query time")
        vector = canonical_vector_literal(query_vector)
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT read_view.generation_id, read_view.status,
                       read_view.fencing_token, read_view.lease_expires_at,
                       read_view.authorization_snapshot_id,
                       read_view.build_snapshot_fingerprint,
                       generation.state,
                       generation.build_snapshot_fingerprint,
                       current.authorization_snapshot_id
                FROM {SCHEMA}.read_views AS read_view
                JOIN {SCHEMA}.generations AS generation
                  ON generation.generation_id = read_view.generation_id
                JOIN {SCHEMA}.current_build_snapshots AS selected
                  ON selected.scope_id = generation.scope_id
                JOIN {SCHEMA}.build_snapshots AS current
                  ON current.build_snapshot_id = selected.build_snapshot_id
                WHERE read_view.view_id = %s
                FOR UPDATE OF read_view, generation, selected
                """,
                (view_id,),
            )
            binding = cursor.fetchone()
            if binding is None:
                raise ReadViewQueryRejected("READ_VIEW_NOT_FOUND")
            if binding[0] != expected_generation_id:
                raise ReadViewQueryRejected("READ_VIEW_GENERATION_CHANGED")
            if binding[1] != "OPEN":
                raise ReadViewQueryRejected("READ_VIEW_NOT_OPEN")
            if int(binding[2]) != expected_fencing_token:
                raise ReadViewQueryRejected("READ_VIEW_FENCE_NOT_CURRENT")
            if cast(datetime, binding[3]) <= now:
                raise ReadViewQueryRejected("READ_VIEW_LEASE_EXPIRED")
            if binding[4] != expected_authorization_snapshot_id:
                raise ReadViewQueryRejected("READ_VIEW_AUTHORIZATION_CHANGED")
            if binding[5] != binding[7]:
                raise ReadViewQueryRejected("READ_VIEW_GENERATION_BINDING_CHANGED")
            if binding[6] not in {
                GenerationState.ACTIVE.value,
                GenerationState.DRAINING.value,
            }:
                raise ReadViewQueryRejected("GENERATION_NOT_SERVABLE")
            if binding[8] != expected_authorization_snapshot_id:
                raise ReadViewQueryRejected("CURRENT_AUTHORIZATION_CHANGED")
            if mode is QueryMode.EXACT:
                cursor.execute("SET LOCAL enable_indexscan = off")
                cursor.execute("SET LOCAL enable_bitmapscan = off")
            elif mode is QueryMode.HNSW:
                cursor.execute(
                    "SELECT set_config('hnsw.ef_search', %s, true)",
                    (str(ef_search),),
                )
                cursor.execute("SET LOCAL enable_seqscan = off")
            else:  # pragma: no cover - Enum protects public callers
                raise ValueError("unsupported query mode")
            cursor.execute(
                f"""
                SELECT point.point_id, point.occurrence_id,
                       point.generation_id,
                       point.embedding <=> %s::vector AS cosine_distance
                FROM {SCHEMA}.index_points AS point
                WHERE point.generation_id = %s AND point.tenant_id = %s
                ORDER BY point.embedding <=> %s::vector, point.point_id
                LIMIT %s
                """,
                (
                    vector,
                    expected_generation_id,
                    tenant_id,
                    vector,
                    top_k,
                ),
            )
            hits: list[PgVectorHit] = []
            for row in cursor.fetchall():
                distance = float(row[3])
                if not math.isfinite(distance) or not -1e-12 <= distance <= 2.0 + 1e-12:
                    raise ValueError("pgvector returned invalid cosine distance")
                hits.append(
                    PgVectorHit(
                        cast(str, row[0]),
                        cast(str, row[1]),
                        cast(str, row[2]),
                        max(0.0, min(2.0, distance)),
                    )
                )
            return tuple(hits)
