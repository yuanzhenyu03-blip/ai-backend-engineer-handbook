"""PostgreSQL control-plane repository for the bounded Day105 L3 lab.

The repository persists identity and digest receipts only.  Source text,
protected chunks, full prompts, model output, vectors, credentials and DSNs are
deliberately outside this boundary.  All immutable rows support exact replay;
the only mutable row is the tenant-scoped current-security pointer, advanced by
compare-and-swap in the same transaction as its append-only transition receipt.

The dependency on psycopg2 remains lazy.  The integration flag is checked
before a connection is opened so the normal deterministic course suite cannot
accidentally reach a local PostgreSQL instance.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
import re
from typing import Any, cast

from rag_chunking_contracts import stable_hash
from rag_index_lifecycle_contracts import parse_aware_datetime
from rag_index_lifecycle_postgres import (
    ConnectionFactory,
    CursorPort,
    psycopg2_connection_factory,
)
from rag_security_contracts import (
    OutputReleaseDecision,
    SecurityDisposition,
    SecurityIncidentRecord,
    SecurityResult,
)


SCHEMA = "day105_l3"
INTEGRATION_FLAG = "DAY105_L3_INTEGRATION"
RESET_CONFIRMATION = "RESET_DAY105_L3_SCHEMAS"
RESET_DATABASE_NAME = "day105_l3"


class SecurityRepositoryOutcome(str, Enum):
    APPLIED = "APPLIED"
    EXACT_REPLAY = "EXACT_REPLAY"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    STALE_REVISION = "STALE_REVISION"
    NOT_FOUND = "NOT_FOUND"
    INTEGRITY_FAILED = "INTEGRITY_FAILED"


class SecurityArtifactType(str, Enum):
    CONTENT_SECURITY_RECORD = "CONTENT_SECURITY_RECORD"
    INGESTION_DECISION = "INGESTION_DECISION"
    REQUEST_BINDING = "REQUEST_BINDING"
    RETRIEVAL_DECISION = "RETRIEVAL_DECISION"
    BUNDLE_DECISION = "BUNDLE_DECISION"
    RETRIEVAL_BUNDLE = "RETRIEVAL_BUNDLE"
    CONTEXT_MANIFEST = "CONTEXT_MANIFEST"
    DISCLOSURE_ENVELOPE = "DISCLOSURE_ENVELOPE"
    MODEL_INVOCATION = "MODEL_INVOCATION"
    ANSWER_CANDIDATE = "ANSWER_CANDIDATE"
    RELEASE_EVIDENCE = "RELEASE_EVIDENCE"
    OUTPUT_RELEASE_DECISION = "OUTPUT_RELEASE_DECISION"
    SECURITY_SNAPSHOT_TRANSITION = "SECURITY_SNAPSHOT_TRANSITION"
    ENVIRONMENT_EVIDENCE = "ENVIRONMENT_EVIDENCE"


@dataclass(frozen=True)
class SecurityRepositoryResult:
    outcome: SecurityRepositoryOutcome
    safe_reason: str
    durable_transition: bool = False
    identity_digest: str | None = None
    revision: int | None = None


def _require_text(*values: str) -> None:
    if not all(value.strip() for value in values):
        raise ValueError("complete non-empty identity bindings are required")


def _require_canonical(
    values: tuple[str, ...],
    *,
    label: str,
    allow_empty: bool = False,
) -> None:
    if not allow_empty and not values:
        raise ValueError(f"{label} must be non-empty")
    if any(not value.strip() for value in values):
        raise ValueError(f"{label} cannot contain empty values")
    if values != tuple(sorted(values)) or len(set(values)) != len(values):
        raise ValueError(f"{label} must be sorted and unique")


def _utc_datetime(value: str | datetime, *, label: str) -> datetime:
    parsed = (
        parse_aware_datetime(value, label=label) if isinstance(value, str) else value
    )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include an explicit UTC offset")
    return parsed.astimezone(timezone.utc)


def _utc_iso(value: str | datetime, *, label: str) -> str:
    return _utc_datetime(value, label=label).isoformat().replace("+00:00", "Z")


_SAFE_EXACT_KEYS = frozenset(
    {
        "action",
        "audience",
        "created_at",
        "disposition",
        "observed_at",
        "previous_revision",
        "purpose",
        "reason_codes",
        "result",
        "revision",
        "state",
        "status",
    }
)
_SAFE_KEY_SUFFIXES = (
    "_at",
    "_count",
    "_digest",
    "_digests",
    "_fence",
    "_fingerprint",
    "_id",
    "_ids",
    "_revision",
    "_status",
    "_version",
)
_FORBIDDEN_KEYS = frozenset(
    {
        "answer",
        "answer_text",
        "access_token",
        "api_key",
        "attack_payload",
        "candidate_text",
        "content",
        "credential",
        "cross_tenant_content",
        "database_url",
        "destination",
        "dsn",
        "embedding",
        "egress_url",
        "full_prompt",
        "model_output",
        "password",
        "prompt",
        "protected_chunk",
        "protected_content",
        "raw_content",
        "raw_prompt",
        "raw_secret",
        "raw_vector",
        "secret",
        "source_text",
        "system_prompt",
        "token",
        "vector",
    }
)
_SENSITIVE_VALUE = re.compile(
    r"(?:postgres(?:ql)?://|-----BEGIN [A-Z ]+PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{12,})",
    re.IGNORECASE,
)


def _validate_safe_value(value: object, *, path: str) -> None:
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        raise ValueError(f"content-safe payload cannot store floats at {path}")
    if isinstance(value, str):
        if len(value) > 1024 or "\x00" in value or _SENSITIVE_VALUE.search(value):
            raise ValueError(f"content-safe payload rejected sensitive value at {path}")
        return
    if isinstance(value, tuple):
        for index, item in enumerate(value):
            _validate_safe_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        _validate_content_safe_payload(value, path=path)
        return
    raise ValueError(f"unsupported content-safe payload value at {path}")


def _validate_content_safe_payload(
    payload: Mapping[str, object],
    *,
    path: str = "payload",
) -> None:
    for key, value in payload.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"content-safe payload requires named keys at {path}")
        normalized = key.strip().lower().replace("-", "_")
        if normalized in _FORBIDDEN_KEYS:
            raise ValueError(f"content-safe payload forbids {normalized}")
        if normalized not in _SAFE_EXACT_KEYS and not normalized.endswith(
            _SAFE_KEY_SUFFIXES
        ):
            raise ValueError(
                f"content-safe payload key is not allowlisted: {normalized}"
            )
        _validate_safe_value(value, path=f"{path}.{normalized}")


def _json_value(value: object) -> object:
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in sorted(value.items())}
    return value


def _payload_json(payload: tuple[tuple[str, object], ...]) -> str:
    return json.dumps(
        _json_value(dict(payload)),
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True)
class SecuritySnapshot:
    snapshot_id: str
    tenant_id: str
    revision: int
    authorization_snapshot_id: str
    authorization_snapshot_digest: str
    provenance_revision: str
    provenance_digest: str
    tombstone_revision: str
    tombstone_digest: str
    content_security_policy_version: str
    content_security_digest: str
    security_policy_version: str
    security_policy_digest: str
    occurrence_ids: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    created_at: str

    def __post_init__(self) -> None:
        _require_text(
            self.snapshot_id,
            self.tenant_id,
            self.authorization_snapshot_id,
            self.authorization_snapshot_digest,
            self.provenance_revision,
            self.provenance_digest,
            self.tombstone_revision,
            self.tombstone_digest,
            self.content_security_policy_version,
            self.content_security_digest,
            self.security_policy_version,
            self.security_policy_digest,
            self.created_at,
        )
        if self.revision <= 0:
            raise ValueError("security snapshot revision must be positive")
        _require_canonical(
            self.occurrence_ids,
            label="security snapshot occurrence IDs",
            allow_empty=True,
        )
        _require_canonical(
            self.evidence_digests,
            label="security snapshot evidence digests",
        )
        _utc_datetime(self.created_at, label="security snapshot created-at")
        _validate_content_safe_payload(dict(self.content_safe_payload))

    @property
    def identity_digest(self) -> str:
        return stable_hash(asdict(self))

    @property
    def content_safe_payload(self) -> tuple[tuple[str, object], ...]:
        return (
            ("authorization_snapshot_digest", self.authorization_snapshot_digest),
            ("authorization_snapshot_id", self.authorization_snapshot_id),
            (
                "content_security_digest",
                self.content_security_digest,
            ),
            ("content_security_policy_version", self.content_security_policy_version),
            ("evidence_digests", self.evidence_digests),
            ("occurrence_ids", self.occurrence_ids),
            ("provenance_digest", self.provenance_digest),
            ("provenance_revision", self.provenance_revision),
            ("security_policy_digest", self.security_policy_digest),
            ("security_policy_version", self.security_policy_version),
            ("tombstone_digest", self.tombstone_digest),
            ("tombstone_revision", self.tombstone_revision),
        )


@dataclass(frozen=True)
class SecurityArtifact:
    artifact_id: str
    artifact_type: SecurityArtifactType
    request_id: str | None
    subject_digest: str
    parent_digests: tuple[str, ...]
    result: SecurityResult
    disposition: SecurityDisposition
    payload: tuple[tuple[str, object], ...]
    created_at: str

    def __post_init__(self) -> None:
        _require_text(self.artifact_id, self.subject_digest, self.created_at)
        if self.request_id is not None:
            _require_text(self.request_id)
        _require_canonical(
            self.parent_digests,
            label="artifact parent digests",
            allow_empty=True,
        )
        payload_keys = tuple(key for key, _ in self.payload)
        if payload_keys != tuple(sorted(payload_keys)) or len(set(payload_keys)) != len(
            payload_keys
        ):
            raise ValueError("artifact payload keys must be sorted and unique")
        if "subject_digest" in payload_keys:
            raise ValueError("subject digest is stored by the artifact envelope")
        _validate_content_safe_payload(dict(self.payload))
        _utc_datetime(self.created_at, label="security artifact created-at")

    @property
    def storage_payload(self) -> tuple[tuple[str, object], ...]:
        return tuple(sorted((*self.payload, ("subject_digest", self.subject_digest))))

    @property
    def identity_digest(self) -> str:
        return stable_hash(
            {
                "artifact_id": self.artifact_id,
                "artifact_type": self.artifact_type.value,
                "request_id": self.request_id,
                "subject_digest": self.subject_digest,
                "parent_digests": self.parent_digests,
                "result": self.result.value,
                "disposition": self.disposition.value,
                "payload": self.payload,
                "created_at": _utc_iso(
                    self.created_at,
                    label="security artifact created-at",
                ),
            }
        )

    @property
    def artifact_digest(self) -> str:
        """Stable envelope digest persisted as ``identity_digest``."""

        return self.identity_digest

    @property
    def safe_payload(self) -> tuple[tuple[str, object], ...]:
        """Content-safe JSON projection including the contract subject digest."""

        return self.storage_payload


@dataclass(frozen=True)
class StoredSecurityArtifact:
    artifact_id: str
    artifact_type: str
    request_id: str | None
    identity_digest: str
    subject_digest: str
    parent_digests: tuple[str, ...]
    result: str
    disposition: str
    created_at: str


@dataclass(frozen=True)
class StoredIncidentRecord:
    record_id: str
    incident_id: str
    previous_record_id: str | None
    identity_digest: str
    state: str
    scope_digest: str
    created_at: str


@dataclass(frozen=True)
class CurrentSecuritySnapshot:
    tenant_id: str
    snapshot_id: str
    revision: int
    identity_digest: str


def psycopg2_day105_connection_factory(dsn: str) -> ConnectionFactory:
    """Return the Day105-specific lazy psycopg2 connection factory."""

    return psycopg2_connection_factory(
        dsn,
        application_name="day105-l3-rag-security",
    )


class PostgresRagSecurityRepository:
    """Application-owned security control-plane repository."""

    def __init__(
        self,
        connect: ConnectionFactory,
        *,
        schema_path: str | Path | None = None,
        integration_enabled: bool | None = None,
    ) -> None:
        self._connect = connect
        self._integration_enabled = (
            os.environ.get(INTEGRATION_FLAG) == "1"
            if integration_enabled is None
            else integration_enabled
        )
        default_schema = (
            Path(__file__).resolve().parent.parent
            / "integration"
            / "day105"
            / "schema.sql"
        )
        self._schema_path = Path(schema_path) if schema_path else default_schema

    def _require_enabled(self) -> None:
        if not self._integration_enabled:
            raise RuntimeError(
                "Day105 L3 PostgreSQL access requires DAY105_L3_INTEGRATION=1"
            )

    @contextmanager
    def _transaction(self) -> Iterator[CursorPort]:
        self._require_enabled()
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

    @staticmethod
    def _lock(cursor: CursorPort, *identities: str) -> None:
        for identity in sorted(set(identities)):
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (identity,),
            )

    def install_schema(self) -> None:
        ddl = self._schema_path.read_text(encoding="utf-8")
        if not ddl.strip():
            raise ValueError("Day105 L3 schema cannot be empty")
        with self._transaction() as cursor:
            cursor.execute(ddl)

    def reset_lab_schemas(self, *, confirmation: str) -> None:
        if confirmation != RESET_CONFIRMATION:
            raise ValueError(
                f"schema reset requires confirmation {RESET_CONFIRMATION!r}"
            )
        with self._transaction() as cursor:
            cursor.execute("SELECT current_database()")
            row = cursor.fetchone()
            if row is None or row[0] != RESET_DATABASE_NAME:
                raise ValueError("schema reset is restricted to the day105_l3 database")
            cursor.execute(
                "SELECT public.reset_day105_l3_schemas(%s, %s)",
                ("1", confirmation),
            )

    @staticmethod
    def _snapshot_result_from_existing(
        rows: list[Sequence[Any]],
        snapshot: SecuritySnapshot,
    ) -> SecurityRepositoryResult | None:
        if not rows:
            return None
        exact = (
            len(rows) == 1
            and rows[0][0] == snapshot.snapshot_id
            and rows[0][1] == snapshot.identity_digest
        )
        return SecurityRepositoryResult(
            SecurityRepositoryOutcome.EXACT_REPLAY
            if exact
            else SecurityRepositoryOutcome.IDENTITY_CONFLICT,
            "EXACT_SECURITY_SNAPSHOT_REPLAY"
            if exact
            else "SECURITY_SNAPSHOT_ID_OR_REVISION_CONFLICT",
            identity_digest=snapshot.identity_digest,
            revision=snapshot.revision,
        )

    @staticmethod
    def _find_snapshot(
        cursor: CursorPort,
        snapshot: SecuritySnapshot,
    ) -> list[Sequence[Any]]:
        cursor.execute(
            f"""
            SELECT snapshot_id, identity_digest
            FROM {SCHEMA}.security_snapshots
            WHERE snapshot_id = %s OR (tenant_id = %s AND revision = %s)
            FOR UPDATE
            """,
            (snapshot.snapshot_id, snapshot.tenant_id, snapshot.revision),
        )
        return cursor.fetchall()

    @staticmethod
    def _insert_snapshot(cursor: CursorPort, snapshot: SecuritySnapshot) -> None:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.security_snapshots
                (snapshot_id, tenant_id, revision,
                 authorization_snapshot_id, authorization_snapshot_digest,
                 provenance_revision, provenance_digest,
                 tombstone_revision, tombstone_digest,
                 content_security_policy_version, content_security_digest,
                 security_policy_version, security_policy_digest,
                 occurrence_ids, identity_digest, payload, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                snapshot.snapshot_id,
                snapshot.tenant_id,
                snapshot.revision,
                snapshot.authorization_snapshot_id,
                snapshot.authorization_snapshot_digest,
                snapshot.provenance_revision,
                snapshot.provenance_digest,
                snapshot.tombstone_revision,
                snapshot.tombstone_digest,
                snapshot.content_security_policy_version,
                snapshot.content_security_digest,
                snapshot.security_policy_version,
                snapshot.security_policy_digest,
                list(snapshot.occurrence_ids),
                snapshot.identity_digest,
                _payload_json(snapshot.content_safe_payload),
                _utc_datetime(snapshot.created_at, label="snapshot created-at"),
            ),
        )

    def append_security_snapshot(
        self,
        snapshot: SecuritySnapshot,
    ) -> SecurityRepositoryResult:
        with self._transaction() as cursor:
            self._lock(
                cursor,
                f"security-snapshot-id:{snapshot.snapshot_id}",
                f"security-snapshot-revision:{snapshot.tenant_id}:{snapshot.revision}",
            )
            existing = self._find_snapshot(cursor, snapshot)
            result = self._snapshot_result_from_existing(existing, snapshot)
            if result is not None:
                return result
            self._insert_snapshot(cursor, snapshot)
            return SecurityRepositoryResult(
                SecurityRepositoryOutcome.APPLIED,
                "SECURITY_SNAPSHOT_APPENDED",
                durable_transition=True,
                identity_digest=snapshot.identity_digest,
                revision=snapshot.revision,
            )

    @staticmethod
    def _transition_artifact(
        snapshot: SecuritySnapshot,
        expected_revision: int,
    ) -> SecurityArtifact:
        return SecurityArtifact(
            artifact_id=(
                f"security-snapshot-transition:{snapshot.tenant_id}:"
                f"{snapshot.revision}"
            ),
            artifact_type=SecurityArtifactType.SECURITY_SNAPSHOT_TRANSITION,
            request_id=None,
            subject_digest=snapshot.identity_digest,
            parent_digests=(snapshot.identity_digest,),
            result=SecurityResult.PASS,
            disposition=SecurityDisposition.ELIGIBLE,
            payload=(
                ("previous_revision", expected_revision),
                ("revision", snapshot.revision),
                ("snapshot_id", snapshot.snapshot_id),
                ("tenant_id", snapshot.tenant_id),
            ),
            created_at=snapshot.created_at,
        )

    @staticmethod
    def _find_artifact(
        cursor: CursorPort,
        artifact_id: str,
    ) -> Sequence[Any] | None:
        cursor.execute(
            f"""
            SELECT artifact_id, identity_digest
            FROM {SCHEMA}.security_artifacts
            WHERE artifact_id = %s
            FOR UPDATE
            """,
            (artifact_id,),
        )
        return cursor.fetchone()

    @staticmethod
    def _insert_artifact(cursor: CursorPort, artifact: SecurityArtifact) -> None:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.security_artifacts
                (artifact_id, artifact_type, request_id, identity_digest,
                 parent_digests, result, disposition, payload, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                artifact.artifact_id,
                artifact.artifact_type.value,
                artifact.request_id,
                artifact.identity_digest,
                list(artifact.parent_digests),
                artifact.result.value,
                artifact.disposition.value,
                _payload_json(artifact.storage_payload),
                _utc_datetime(artifact.created_at, label="artifact created-at"),
            ),
        )

    def advance_current_security_snapshot(
        self,
        snapshot: SecuritySnapshot,
        *,
        expected_revision: int,
    ) -> SecurityRepositoryResult:
        if expected_revision < 0 or snapshot.revision != expected_revision + 1:
            raise ValueError("security snapshot CAS requires revision + 1")
        transition = self._transition_artifact(snapshot, expected_revision)
        with self._transaction() as cursor:
            self._lock(cursor, f"current-security:{snapshot.tenant_id}")
            cursor.execute(
                f"""
                SELECT current.snapshot_id, current.revision,
                       snapshot.identity_digest
                FROM {SCHEMA}.current_security_snapshots AS current
                JOIN {SCHEMA}.security_snapshots AS snapshot
                  ON snapshot.snapshot_id = current.snapshot_id
                WHERE current.tenant_id = %s
                FOR UPDATE OF current
                """,
                (snapshot.tenant_id,),
            )
            current = cursor.fetchone()
            if current is not None and (
                current[0] == snapshot.snapshot_id
                and int(current[1]) == snapshot.revision
            ):
                stored_transition = self._find_artifact(cursor, transition.artifact_id)
                exact = (
                    current[2] == snapshot.identity_digest
                    and stored_transition is not None
                    and stored_transition[1] == transition.identity_digest
                )
                return SecurityRepositoryResult(
                    SecurityRepositoryOutcome.EXACT_REPLAY
                    if exact
                    else SecurityRepositoryOutcome.INTEGRITY_FAILED,
                    "EXACT_SECURITY_POINTER_REPLAY"
                    if exact
                    else "CURRENT_POINTER_OR_TRANSITION_BINDING_DAMAGED",
                    identity_digest=snapshot.identity_digest,
                    revision=snapshot.revision,
                )
            observed_revision = 0 if current is None else int(current[1])
            if observed_revision != expected_revision:
                return SecurityRepositoryResult(
                    SecurityRepositoryOutcome.STALE_REVISION,
                    "CURRENT_SECURITY_REVISION_NOT_EXPECTED",
                    revision=observed_revision,
                )
            existing = self._find_snapshot(cursor, snapshot)
            snapshot_result = self._snapshot_result_from_existing(existing, snapshot)
            if snapshot_result is not None and (
                snapshot_result.outcome is not SecurityRepositoryOutcome.EXACT_REPLAY
            ):
                return snapshot_result
            if snapshot_result is None:
                self._insert_snapshot(cursor, snapshot)
            stored_transition = self._find_artifact(cursor, transition.artifact_id)
            if stored_transition is not None:
                if stored_transition[1] != transition.identity_digest:
                    return SecurityRepositoryResult(
                        SecurityRepositoryOutcome.IDENTITY_CONFLICT,
                        "SECURITY_TRANSITION_ID_ALREADY_BOUND",
                        identity_digest=transition.identity_digest,
                    )
            else:
                self._insert_artifact(cursor, transition)
            if current is None:
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.current_security_snapshots
                        (tenant_id, snapshot_id, revision, updated_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        snapshot.tenant_id,
                        snapshot.snapshot_id,
                        snapshot.revision,
                        _utc_datetime(snapshot.created_at, label="snapshot created-at"),
                    ),
                )
            else:
                cursor.execute(
                    f"""
                    UPDATE {SCHEMA}.current_security_snapshots
                    SET snapshot_id = %s, revision = %s, updated_at = %s
                    WHERE tenant_id = %s AND revision = %s
                    """,
                    (
                        snapshot.snapshot_id,
                        snapshot.revision,
                        _utc_datetime(snapshot.created_at, label="snapshot created-at"),
                        snapshot.tenant_id,
                        expected_revision,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("CURRENT_SECURITY_POINTER_CAS_LOST")
            return SecurityRepositoryResult(
                SecurityRepositoryOutcome.APPLIED,
                "SECURITY_SNAPSHOT_AND_CURRENT_POINTER_COMMITTED_ATOMICALLY",
                durable_transition=True,
                identity_digest=snapshot.identity_digest,
                revision=snapshot.revision,
            )

    def current_security_snapshot(
        self,
        tenant_id: str,
    ) -> CurrentSecuritySnapshot | None:
        _require_text(tenant_id)
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT current.tenant_id, current.snapshot_id, current.revision,
                       snapshot.identity_digest
                FROM {SCHEMA}.current_security_snapshots AS current
                JOIN {SCHEMA}.security_snapshots AS snapshot
                  ON snapshot.snapshot_id = current.snapshot_id
                WHERE current.tenant_id = %s
                """,
                (tenant_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return CurrentSecuritySnapshot(
                tenant_id=cast(str, row[0]),
                snapshot_id=cast(str, row[1]),
                revision=int(row[2]),
                identity_digest=cast(str, row[3]),
            )

    @staticmethod
    def _parents_exist(
        cursor: CursorPort,
        parent_digests: tuple[str, ...],
    ) -> bool:
        if not parent_digests:
            return True
        cursor.execute(
            f"""
            SELECT identity_digest, payload ->> 'subject_digest'
            FROM {SCHEMA}.security_artifacts
            WHERE identity_digest = ANY(%s)
               OR payload ->> 'subject_digest' = ANY(%s)
            """,
            (list(parent_digests), list(parent_digests)),
        )
        observed: set[str] = set()
        for row in cursor.fetchall():
            if row[0] in parent_digests:
                observed.add(cast(str, row[0]))
            if len(row) > 1 and row[1] in parent_digests:
                observed.add(cast(str, row[1]))
        return observed == set(parent_digests)

    def append_artifact(
        self,
        artifact: SecurityArtifact,
        *,
        allow_external_parents: bool = False,
    ) -> SecurityRepositoryResult:
        with self._transaction() as cursor:
            self._lock(cursor, f"security-artifact:{artifact.artifact_id}")
            existing = self._find_artifact(cursor, artifact.artifact_id)
            if existing is not None:
                exact = existing[1] == artifact.identity_digest
                return SecurityRepositoryResult(
                    SecurityRepositoryOutcome.EXACT_REPLAY
                    if exact
                    else SecurityRepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_SECURITY_ARTIFACT_REPLAY"
                    if exact
                    else "SECURITY_ARTIFACT_ID_ALREADY_BOUND",
                    identity_digest=artifact.identity_digest,
                )
            if (
                artifact.parent_digests
                and not allow_external_parents
                and not self._parents_exist(cursor, artifact.parent_digests)
            ):
                return SecurityRepositoryResult(
                    SecurityRepositoryOutcome.NOT_FOUND,
                    "SECURITY_ARTIFACT_PARENT_NOT_FOUND",
                    identity_digest=artifact.identity_digest,
                )
            self._insert_artifact(cursor, artifact)
            return SecurityRepositoryResult(
                SecurityRepositoryOutcome.APPLIED,
                "SECURITY_ARTIFACT_APPENDED",
                durable_transition=True,
                identity_digest=artifact.identity_digest,
            )

    def append_output_decision_and_intent(
        self,
        decision: OutputReleaseDecision,
        *,
        request_id: str,
        intent_id: str,
        destination_digest: str,
        inject_failure_after_decision: bool = False,
    ) -> SecurityRepositoryResult:
        _require_text(request_id, intent_id, destination_digest)
        if (
            decision.disposition is SecurityDisposition.RELEASE
            and decision.result is not SecurityResult.PASS
        ):
            raise ValueError("non-PASS output cannot create a RELEASE intent")
        action = decision.disposition.value
        if action not in {"RELEASE", "BLOCKED", "ABSTAIN"}:
            raise ValueError("output disposition has no response intent action")
        artifact = SecurityArtifact(
            artifact_id=decision.decision_id,
            artifact_type=SecurityArtifactType.OUTPUT_RELEASE_DECISION,
            request_id=request_id,
            subject_digest=decision.digest,
            parent_digests=tuple(
                sorted(
                    (
                        decision.candidate_digest,
                        decision.disclosure_envelope_digest,
                        decision.release_evidence_digest,
                    )
                )
            ),
            result=decision.result,
            disposition=decision.disposition,
            payload=tuple(
                sorted(
                    (
                        ("candidate_digest", decision.candidate_digest),
                        (
                            "disclosure_envelope_digest",
                            decision.disclosure_envelope_digest,
                        ),
                        ("reason_codes", decision.reason_codes),
                        (
                            "released_citation_occurrence_ids",
                            decision.released_citation_occurrence_ids,
                        ),
                        (
                            "release_evidence_digest",
                            decision.release_evidence_digest,
                        ),
                        (
                            "request_binding_fingerprint",
                            decision.request_binding_fingerprint,
                        ),
                    )
                )
            ),
            created_at=decision.observed_at,
        )
        intent_digest = stable_hash(
            {
                "intent_id": intent_id,
                "request_id": request_id,
                "release_decision_id": decision.decision_id,
                "release_decision_digest": artifact.identity_digest,
                "candidate_digest": decision.candidate_digest,
                "destination_digest": destination_digest,
                "action": action,
            }
        )
        with self._transaction() as cursor:
            self._lock(
                cursor,
                f"security-artifact:{artifact.artifact_id}",
                f"response-intent:{intent_id}",
            )
            stored_artifact = self._find_artifact(cursor, artifact.artifact_id)
            cursor.execute(
                f"""
                SELECT intent_id, identity_digest
                FROM {SCHEMA}.response_intents
                WHERE intent_id = %s OR release_decision_id = %s
                FOR UPDATE
                """,
                (intent_id, decision.decision_id),
            )
            stored_intents = cursor.fetchall()
            if stored_artifact is not None or stored_intents:
                exact = (
                    stored_artifact is not None
                    and stored_artifact[1] == artifact.identity_digest
                    and len(stored_intents) == 1
                    and stored_intents[0][0] == intent_id
                    and stored_intents[0][1] == intent_digest
                )
                return SecurityRepositoryResult(
                    SecurityRepositoryOutcome.EXACT_REPLAY
                    if exact
                    else SecurityRepositoryOutcome.INTEGRITY_FAILED,
                    "EXACT_OUTPUT_DECISION_AND_INTENT_REPLAY"
                    if exact
                    else "OUTPUT_DECISION_AND_INTENT_PARTIAL_OR_CONFLICTING",
                    identity_digest=artifact.identity_digest,
                )
            if not self._parents_exist(cursor, artifact.parent_digests):
                return SecurityRepositoryResult(
                    SecurityRepositoryOutcome.NOT_FOUND,
                    "OUTPUT_DECISION_PARENT_ARTIFACT_NOT_FOUND",
                    identity_digest=artifact.identity_digest,
                )
            self._insert_artifact(cursor, artifact)
            if inject_failure_after_decision:
                raise RuntimeError("INJECTED_AFTER_OUTPUT_DECISION")
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.response_intents
                    (intent_id, request_id, release_decision_id,
                     release_decision_digest, candidate_digest,
                     destination_digest, action, identity_digest, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    intent_id,
                    request_id,
                    decision.decision_id,
                    artifact.identity_digest,
                    decision.candidate_digest,
                    destination_digest,
                    action,
                    intent_digest,
                    _utc_datetime(decision.observed_at, label="output observed-at"),
                ),
            )
            return SecurityRepositoryResult(
                SecurityRepositoryOutcome.APPLIED,
                "OUTPUT_DECISION_AND_RESPONSE_INTENT_COMMITTED_ATOMICALLY",
                durable_transition=True,
                identity_digest=artifact.identity_digest,
            )

    @staticmethod
    def _incident_payload(
        record: SecurityIncidentRecord,
    ) -> tuple[tuple[str, object], ...]:
        return (
            ("affected_generation_ids", record.affected_generation_ids),
            ("affected_occurrence_ids", record.affected_occurrence_ids),
            ("affected_request_ids", record.affected_request_ids),
            (
                "affected_sink_ids",
                tuple(item.value for item in record.affected_sinks),
            ),
            ("actor_id", record.actor_id),
            ("containment_action_ids", record.containment_actions),
            ("credential_rotation_status", record.credential_rotation_status),
            ("evidence_digests", record.evidence_digests),
            ("impact_analysis_digest", record.impact_analysis_digest),
        )

    def append_incident_record(
        self,
        record: SecurityIncidentRecord,
    ) -> SecurityRepositoryResult:
        payload = self._incident_payload(record)
        _validate_content_safe_payload(dict(payload))
        with self._transaction() as cursor:
            self._lock(cursor, f"security-incident:{record.incident_id}")
            cursor.execute(
                f"""
                SELECT record_id, identity_digest
                FROM {SCHEMA}.incident_records
                WHERE record_id = %s
                FOR UPDATE
                """,
                (record.incident_record_id,),
            )
            existing = cursor.fetchone()
            if existing is not None:
                exact = existing[1] == record.digest
                return SecurityRepositoryResult(
                    SecurityRepositoryOutcome.EXACT_REPLAY
                    if exact
                    else SecurityRepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_INCIDENT_RECORD_REPLAY"
                    if exact
                    else "INCIDENT_RECORD_ID_ALREADY_BOUND",
                    identity_digest=record.digest,
                )
            cursor.execute(
                f"""
                SELECT record_id, previous_record_id
                FROM {SCHEMA}.incident_records
                WHERE incident_id = %s
                ORDER BY created_at, record_id
                FOR UPDATE
                """,
                (record.incident_id,),
            )
            history = cursor.fetchall()
            by_id = {cast(str, row[0]): row[1] for row in history}
            if record.previous_record_id is None:
                if history:
                    return SecurityRepositoryResult(
                        SecurityRepositoryOutcome.IDENTITY_CONFLICT,
                        "INCIDENT_ALREADY_HAS_ROOT",
                        identity_digest=record.digest,
                    )
            else:
                if record.previous_record_id not in by_id:
                    return SecurityRepositoryResult(
                        SecurityRepositoryOutcome.NOT_FOUND,
                        "INCIDENT_PREVIOUS_RECORD_NOT_FOUND",
                        identity_digest=record.digest,
                    )
                if any(
                    previous == record.previous_record_id for previous in by_id.values()
                ):
                    return SecurityRepositoryResult(
                        SecurityRepositoryOutcome.IDENTITY_CONFLICT,
                        "INCIDENT_CORRECTION_BRANCH_REJECTED",
                        identity_digest=record.digest,
                    )
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.incident_records
                    (record_id, incident_id, previous_record_id,
                     identity_digest, state, scope_digest, payload, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    record.incident_record_id,
                    record.incident_id,
                    record.previous_record_id,
                    record.digest,
                    record.state.value,
                    record.impact_analysis_digest,
                    _payload_json(payload),
                    _utc_datetime(record.observed_at, label="incident observed-at"),
                ),
            )
            return SecurityRepositoryResult(
                SecurityRepositoryOutcome.APPLIED,
                "INCIDENT_RECORD_APPENDED",
                durable_transition=True,
                identity_digest=record.digest,
            )

    def read_request_chain(
        self,
        request_id: str,
    ) -> tuple[StoredSecurityArtifact, ...]:
        _require_text(request_id)
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT artifact_id, artifact_type, request_id,
                       identity_digest, payload ->> 'subject_digest',
                       parent_digests, result, disposition, created_at
                FROM {SCHEMA}.security_artifacts
                WHERE request_id = %s
                ORDER BY created_at, artifact_id
                """,
                (request_id,),
            )
            return tuple(
                StoredSecurityArtifact(
                    artifact_id=cast(str, row[0]),
                    artifact_type=cast(str, row[1]),
                    request_id=cast(str | None, row[2]),
                    identity_digest=cast(str, row[3]),
                    subject_digest=cast(str, row[4]),
                    parent_digests=tuple(row[5]),
                    result=cast(str, row[6]),
                    disposition=cast(str, row[7]),
                    created_at=_utc_iso(row[8], label="stored artifact created-at"),
                )
                for row in cursor.fetchall()
            )

    def read_incident_history(
        self,
        incident_id: str,
    ) -> tuple[StoredIncidentRecord, ...]:
        _require_text(incident_id)
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT record_id, incident_id, previous_record_id,
                       identity_digest, state, scope_digest, created_at
                FROM {SCHEMA}.incident_records
                WHERE incident_id = %s
                ORDER BY created_at, record_id
                """,
                (incident_id,),
            )
            return tuple(
                StoredIncidentRecord(
                    record_id=cast(str, row[0]),
                    incident_id=cast(str, row[1]),
                    previous_record_id=cast(str | None, row[2]),
                    identity_digest=cast(str, row[3]),
                    state=cast(str, row[4]),
                    scope_digest=cast(str, row[5]),
                    created_at=_utc_iso(row[6], label="stored incident created-at"),
                )
                for row in cursor.fetchall()
            )
