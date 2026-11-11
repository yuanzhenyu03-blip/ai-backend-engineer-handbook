"""Run the opt-in Day104 PostgreSQL + pgvector integration scenario.

The runner is fail-closed.  It never opens a database connection unless both
``DAY104_L3_INTEGRATION=1`` and ``DAY104_L3_DATABASE_URL`` are present.  Output
contains identities, digests, versions and decisions only; it never includes a
DSN, password, source text or raw vector.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import threading
from typing import Any, TypedDict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from rag_chunking_contracts import stable_hash  # noqa: E402
from rag_index_lifecycle_contracts import (  # noqa: E402
    BuildSnapshot,
    DeletionEvidence,
    DeletionEvidenceScope,
    EvidenceStatus,
    EvaluationRuler,
    ImmutableBinding,
)
from rag_index_lifecycle_orchestrator import (  # noqa: E402
    IndexedOccurrence,
    manifest_facts,
)
from rag_index_lifecycle_postgres import (  # noqa: E402
    DeletionReceipt,
    PgVectorPoint,
    PostgresIndexLifecycleRepository,
    QueryMode,
    RepositoryOutcome,
    SourceDeletionCommand,
    SourceOccurrenceRecord,
    psycopg2_connection_factory,
)


L2_REPORT_CHECKSUM = (
    "sha256:2faf8b4f538de1c5340596eb9b74ec5331fb23ba70a04bbd0fb97569359e7140"
)
SCOPE = "refund-rag"
TENANT = "tenant-refund"
POINTER = "refund-serving"
EXPECTED_IDS = ("A@v1", "C@v1")
TOMBSTONED_IDS = ("B@v1",)
RESET_CONFIRMATION = "RESET_DAY104_L3_SCHEMA"


class EnvironmentEvidence(TypedDict):
    postgresql_server_version: str
    postgresql_server_version_num: int
    pgvector_extension_version: str


class PointerEvidence(TypedDict):
    generation_id: str
    revision: int


class GenerationStateEvidence(TypedDict):
    state: str
    state_version: int
    active_readers: int


class DatabaseStateEvidence(TypedDict):
    pointer: PointerEvidence
    G1: GenerationStateEvidence
    G2: GenerationStateEvidence


class ActivationFootprintEvidence(DatabaseStateEvidence):
    activation_record_count: int
    activation_outbox_count: int


class _FaultInjectingCursor:
    def __init__(self, inner: Any, *, query_fragment: str) -> None:
        self._inner = inner
        self._query_fragment = query_fragment

    @property
    def rowcount(self) -> int:
        return int(self._inner.rowcount)

    def execute(self, query: str, params: object = None) -> object:
        normalized = " ".join(str(query).split())
        if self._query_fragment in normalized:
            raise RuntimeError("DAY104_ACTIVATION_RECORD_FAULT_INJECTED")
        return self._inner.execute(query, params)

    def fetchone(self):
        return self._inner.fetchone()

    def fetchall(self):
        return self._inner.fetchall()

    def close(self) -> None:
        self._inner.close()


class _FaultInjectingConnection:
    def __init__(self, inner: Any, *, query_fragment: str) -> None:
        self._inner = inner
        self._query_fragment = query_fragment

    def cursor(self) -> _FaultInjectingCursor:
        return _FaultInjectingCursor(
            self._inner.cursor(),
            query_fragment=self._query_fragment,
        )

    def commit(self) -> None:
        self._inner.commit()

    def rollback(self) -> None:
        self._inner.rollback()

    def close(self) -> None:
        self._inner.close()


def _occurrence(occurrence_id: str, logical_id: str) -> SourceOccurrenceRecord:
    return SourceOccurrenceRecord(
        occurrence_id=occurrence_id,
        logical_id=logical_id,
        source_version="S1",
        content_digest=stable_hash(("content", occurrence_id)),
        metadata_digest=stable_hash(("metadata", occurrence_id)),
        provenance_digest=stable_hash(("provenance", occurrence_id)),
        tenant_id=TENANT,
    )


def _source_command() -> SourceDeletionCommand:
    deletion = DeletionReceipt(
        deletion_id="delete-B-v1",
        operation_id="delete-operation-B-v1",
        idempotency_key="delete-idempotency-B-v1",
        occurrence_id="B@v1",
        source_version="S1",
        intent_digest=stable_hash(("delete", SCOPE, "B@v1")),
        verification_policy_id="day104-l3-serving-absence-v1",
        required_evidence_scopes=(
            "LOGICAL_RELEASE",
            "SERVING_INDEX_ABSENCE",
        ),
        accepted_at="2026-11-11T09:00:00+08:00",
    )
    return SourceDeletionCommand(
        operation_id="receive-S1-D1",
        idempotency_key="receive-refund-S1-D1",
        scope_id=SCOPE,
        source_snapshot_id="S1",
        source_version="S1",
        source_digest=stable_hash(("source-snapshot", "S1")),
        occurrences=(
            _occurrence("A@v1", "A"),
            _occurrence("B@v1", "B"),
            _occurrence("C@v1", "C"),
        ),
        deletion_snapshot_id="D1",
        deletion_digest=stable_hash(("deletion-snapshot", "D1", "B@v1")),
        deletion_ledger_revision=1,
        deletions=(deletion,),
        received_at="2026-11-11T09:00:00+08:00",
    )


def _build_snapshot(command: SourceDeletionCommand) -> BuildSnapshot:
    return BuildSnapshot(
        build_snapshot_id="BS1",
        scope_id=SCOPE,
        source_snapshot=ImmutableBinding("S1", command.source_digest),
        authorization_snapshot=ImmutableBinding(
            "P1",
            stable_hash(("authorization", "P1", "metadata-r1")),
        ),
        embedding_contract=ImmutableBinding(
            "E1",
            stable_hash(("embedding", "E1", 3, "cosine")),
        ),
        index_schema=ImmutableBinding(
            "IS1",
            stable_hash(("index-schema", "IS1", "pgvector-hnsw")),
        ),
        source_watermark="W1",
        deletion_snapshot=ImmutableBinding("D1", command.deletion_digest),
    )


def _ruler() -> EvaluationRuler:
    return EvaluationRuler(
        dataset_fingerprint=stable_hash(("day103", "Q1", "Q2", "Q3")),
        evaluator_fingerprint=stable_hash(("day103-evaluator", "v1")),
        policy_fingerprint=stable_hash(("day103-hard-gates", "v1")),
    )


def _expected_manifest():
    return manifest_facts(
        tuple(
            IndexedOccurrence(
                occurrence_id,
                stable_hash(("content", occurrence_id)),
                stable_hash(("metadata", occurrence_id)),
                stable_hash(("provenance", occurrence_id)),
            )
            for occurrence_id in EXPECTED_IDS
        )
    )


def _points(generation_id: str) -> tuple[PgVectorPoint, ...]:
    vectors = {
        "A@v1": (1.0, 0.0, 0.0),
        "C@v1": (0.0, 1.0, 0.0),
    }
    return tuple(
        PgVectorPoint(
            point_id=f"{generation_id}:{occurrence_id}",
            generation_id=generation_id,
            occurrence_id=occurrence_id,
            tenant_id=TENANT,
            content_digest=stable_hash(("content", occurrence_id)),
            metadata_digest=stable_hash(("metadata", occurrence_id)),
            provenance_digest=stable_hash(("provenance", occurrence_id)),
            embedding=vectors[occurrence_id],
            metadata=(
                ("authorization_revision", "P1"),
                ("source_snapshot", "S1"),
            ),
        )
        for occurrence_id in EXPECTED_IDS
    )


def _query_one(factory, query: str, params: tuple[object, ...] = ()):
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
        row = cursor.fetchone()
        connection.commit()
        return row
    except BaseException:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def _environment(factory) -> EnvironmentEvidence:
    row = _query_one(
        factory,
        """
        SELECT current_setting('server_version'),
               current_setting('server_version_num')::integer,
               extversion
        FROM pg_extension
        WHERE extname = 'vector'
        """,
    )
    if row is None:
        raise AssertionError("PGVECTOR_EXTENSION_NOT_INSTALLED")
    return {
        "postgresql_server_version": str(row[0]),
        "postgresql_server_version_num": int(row[1]),
        "pgvector_extension_version": str(row[2]),
    }


def _database_state(factory) -> DatabaseStateEvidence:
    pointer = _query_one(
        factory,
        """
        SELECT generation_id, revision
        FROM day104_l3.active_pointers
        WHERE pointer_name = %s
        """,
        (POINTER,),
    )
    g1 = _query_one(
        factory,
        """
        SELECT state, state_version, active_readers
        FROM day104_l3.generations
        WHERE generation_id = 'G1'
        """,
    )
    g2 = _query_one(
        factory,
        """
        SELECT state, state_version, active_readers
        FROM day104_l3.generations
        WHERE generation_id = 'G2'
        """,
    )
    if pointer is None or g1 is None or g2 is None:
        raise AssertionError("DURABLE_STATE_INCOMPLETE")
    return {
        "pointer": {"generation_id": str(pointer[0]), "revision": int(pointer[1])},
        "G1": {
            "state": str(g1[0]),
            "state_version": int(g1[1]),
            "active_readers": int(g1[2]),
        },
        "G2": {
            "state": str(g2[0]),
            "state_version": int(g2[1]),
            "active_readers": int(g2[2]),
        },
    }


def _activation_footprint(factory) -> ActivationFootprintEvidence:
    state = _database_state(factory)
    activation_count = _query_one(
        factory,
        "SELECT count(*) FROM day104_l3.activation_records",
    )
    activation_outbox_count = _query_one(
        factory,
        """
        SELECT count(*)
        FROM day104_l3.outbox_events
        WHERE event_type = 'INDEX_POINTER_CHANGED'
        """,
    )
    if activation_count is None or activation_outbox_count is None:
        raise AssertionError("ACTIVATION_FOOTPRINT_READBACK_FAILED")
    return {
        "pointer": state["pointer"],
        "G1": state["G1"],
        "G2": state["G2"],
        "activation_record_count": int(activation_count[0]),
        "activation_outbox_count": int(activation_outbox_count[0]),
    }


def _direct_sealed_write_is_rejected(factory) -> bool:
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO day104_l3.index_points
                (generation_id, point_id, occurrence_id, tenant_id,
                 content_digest, metadata_digest, provenance_digest,
                 vector_digest, embedding, metadata, created_at)
            VALUES ('G2', 'G2:late-B', 'B@v1', %s, %s, %s, %s, %s,
                    '[0,0,1]'::vector, '{}'::jsonb, clock_timestamp())
            """,
            (
                TENANT,
                stable_hash(("content", "B@v1")),
                stable_hash(("metadata", "B@v1")),
                stable_hash(("provenance", "B@v1")),
                stable_hash(("vector", "late-B")),
            ),
        )
    except Exception:
        connection.rollback()
        return True
    else:
        connection.rollback()
        return False
    finally:
        cursor.close()
        connection.close()


def _hnsw_plan_evidence(factory) -> dict[str, object]:
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute("SET LOCAL enable_seqscan = off")
        cursor.execute("SET LOCAL enable_sort = off")
        cursor.execute("SELECT set_config('hnsw.ef_search', '40', true)")
        cursor.execute(
            """
            EXPLAIN (FORMAT JSON)
            SELECT point.point_id
            FROM day104_l3.index_points AS point
            WHERE point.generation_id = %s AND point.tenant_id = %s
            ORDER BY point.embedding <=> '[0.70710677,0.70710677,0]'::vector
            LIMIT 2
            """,
            ("G2", TENANT),
        )
        row = cursor.fetchone()
        if row is None:
            raise AssertionError("HNSW_EXPLAIN_RETURNED_NO_PLAN")
        plan = row[0]
        if isinstance(plan, str):
            plan = json.loads(plan)
        canonical_plan = json.loads(json.dumps(plan, sort_keys=True))
        serialized = json.dumps(canonical_plan, sort_keys=True)
        uses_hnsw_index = "index_points_embedding_hnsw_cosine_idx" in serialized
        connection.rollback()
        return {
            "uses_hnsw_index": uses_hnsw_index,
            "plan_digest": stable_hash(canonical_plan),
        }
    except BaseException:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def _query_matrix(
    repository: PostgresIndexLifecycleRepository,
    generation_id: str,
    *,
    view_id: str | None = None,
    observed_at: str = "2026-11-11T10:07:00+08:00",
) -> dict[str, dict[str, list[str]]]:
    root_half = 1.0 / math.sqrt(2.0)
    queries = {
        "Q1": ((1.0, 0.0, 0.0), 1),
        "Q2": ((0.0, 1.0, 0.0), 1),
        "Q3": ((root_half, root_half, 0.0), 2),
    }
    matrix: dict[str, dict[str, list[str]]] = {}
    for mode in (QueryMode.EXACT, QueryMode.HNSW):
        results: dict[str, list[str]] = {}
        for query_id, (vector, top_k) in queries.items():
            if view_id is None:
                hits = repository.query_generation(
                    generation_id=generation_id,
                    tenant_id=TENANT,
                    query_vector=vector,
                    top_k=top_k,
                    mode=mode,
                )
            else:
                hits = repository.query_read_view(
                    view_id=view_id,
                    expected_fencing_token=1,
                    expected_generation_id=generation_id,
                    expected_authorization_snapshot_id="P1",
                    tenant_id=TENANT,
                    query_vector=vector,
                    top_k=top_k,
                    mode=mode,
                    observed_at=observed_at,
                )
            if any(hit.generation_id != generation_id for hit in hits):
                raise AssertionError("QUERY_MIXED_GENERATIONS")
            results[query_id] = [hit.occurrence_id for hit in hits]
        matrix[mode.value] = results
    return matrix


def _assert_query_matrix(matrix: dict[str, dict[str, list[str]]]) -> None:
    expected = {
        "Q1": ["A@v1"],
        "Q2": ["C@v1"],
        "Q3": ["A@v1", "C@v1"],
    }
    if matrix.get("EXACT") != expected or matrix.get("HNSW") != expected:
        raise AssertionError("DAY103_QUERY_RULER_MISMATCH")


def _gate(evidence_id: str, digest_value: object) -> dict[str, object]:
    return {
        "status": "PASS",
        "evidence_id": evidence_id,
        "evidence_digest": stable_hash(digest_value),
    }


def run_integration(database_url: str) -> dict[str, object]:
    """Execute the real database scenario and return content-safe evidence."""

    if not database_url.strip():
        raise ValueError("DAY104_L3_DATABASE_URL_REQUIRED")
    started_at = datetime.now(timezone.utc).isoformat()
    factory = psycopg2_connection_factory(database_url)
    repository = PostgresIndexLifecycleRepository(factory)
    repository.reset_schema(confirmation=RESET_CONFIRMATION)

    environment = _environment(factory)
    if environment["postgresql_server_version_num"] < 130000:
        raise AssertionError("POSTGRESQL_VERSION_BELOW_DAY99_BOUNDARY")
    if environment["pgvector_extension_version"] != "0.8.7":
        raise AssertionError("PGVECTOR_VERSION_DIFFERS_FROM_DAY99_CANDIDATE")
    schema_table_count = _query_one(
        factory,
        """
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'day104_l3'
        """,
    )
    if schema_table_count is None or int(schema_table_count[0]) < 10:
        raise AssertionError("DAY104_L3_SCHEMA_INSTALL_INCOMPLETE")

    command = _source_command()
    ingest = repository.receive_source_and_deletion(command)
    if ingest.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("SOURCE_DELETE_INGEST_NOT_APPLIED")
    replay = repository.receive_source_and_deletion(command)
    if replay.outcome is not RepositoryOutcome.EXACT_REPLAY:
        raise AssertionError("SOURCE_DELETE_EXACT_REPLAY_DID_NOT_CONVERGE")
    changed_command = SourceDeletionCommand(
        **{
            **command.__dict__,
            "source_digest": stable_hash(("source-snapshot", "changed")),
        }
    )
    conflict = repository.receive_source_and_deletion(changed_command)
    if conflict.outcome is not RepositoryOutcome.IDENTITY_CONFLICT:
        raise AssertionError("SOURCE_DELETE_DIGEST_CONFLICT_NOT_REJECTED")

    snapshot = _build_snapshot(command)
    snapshot_result = repository.put_current_build_snapshot(
        snapshot=snapshot,
        expected_current_revision=0,
        created_at="2026-11-11T09:05:00+08:00",
    )
    if snapshot_result.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("BUILD_SNAPSHOT_NOT_SELECTED")
    stored_snapshot = _query_one(
        factory,
        """
        SELECT snapshot_fingerprint
        FROM day104_l3.build_snapshots
        WHERE build_snapshot_id = 'BS1'
        """,
    )
    if stored_snapshot != (snapshot.fingerprint,):
        raise AssertionError("BUILD_SNAPSHOT_READBACK_MISMATCH")
    changed_snapshot = BuildSnapshot(
        **{
            **snapshot.__dict__,
            "build_snapshot_id": "BS-drift",
            "authorization_snapshot": ImmutableBinding(
                "P2",
                stable_hash(("authorization", "P2", "metadata-r2")),
            ),
        }
    )
    if changed_snapshot.fingerprint == snapshot.fingerprint:
        raise AssertionError("BUILD_SNAPSHOT_DID_NOT_BIND_AUTHORIZATION")

    ruler = _ruler()
    expected_manifest = _expected_manifest()
    generation_evidence: dict[str, dict[str, object]] = {}
    for offset, generation_id in enumerate(("G1", "G2"), start=1):
        registered = repository.register_generation(
            generation_id=generation_id,
            snapshot=snapshot,
            ruler=ruler,
            expected_manifest=expected_manifest,
            physical_namespace=f"refund-generation-{generation_id.lower()}",
            provider_write_fence=offset,
            created_at=f"2026-11-11T09:{10 + offset:02d}:00+08:00",
        )
        if registered.outcome is not RepositoryOutcome.APPLIED:
            raise AssertionError("GENERATION_REGISTRATION_FAILED")
        write = repository.write_generation_points(
            generation_id=generation_id,
            provider_write_fence=offset,
            points=_points(generation_id),
            created_at=f"2026-11-11T09:{20 + offset:02d}:00+08:00",
        )
        if write.outcome is not RepositoryOutcome.APPLIED:
            raise AssertionError("PGVECTOR_WRITE_FAILED")
        readback = repository.readback_manifest(generation_id)
        if readback != expected_manifest or "B@v1" in readback.occurrence_ids:
            raise AssertionError("PGVECTOR_READBACK_MISMATCH")
        sealed = repository.seal_generation(
            generation_id=generation_id,
            expected_manifest=expected_manifest,
            expected_absent_occurrence_ids=TOMBSTONED_IDS,
            provider_write_fence=offset,
            observed_at=f"2026-11-11T09:{30 + offset:02d}:00+08:00",
        )
        if (
            sealed.outcome is not RepositoryOutcome.APPLIED
            or sealed.manifest is None
            or not sealed.manifest.integrity_matches
            or sealed.state_version is None
        ):
            raise AssertionError("GENERATION_SEAL_OR_MANIFEST_FAILED")
        if generation_id == "G2":
            wrong_ruler = EvaluationRuler(
                ruler.dataset_fingerprint,
                ruler.evaluator_fingerprint,
                stable_hash(("wrong-policy", "v2")),
            )
            wrong_ready = repository.mark_ready(
                generation_id=generation_id,
                expected_state_version=sealed.state_version,
                expected_manifest=expected_manifest,
                expected_absent_occurrence_ids=TOMBSTONED_IDS,
                ruler=wrong_ruler,
                validation_record_digest=stable_hash(("validation", generation_id)),
                evaluation_evidence_digest=stable_hash(("evidence", generation_id)),
                evaluation_report_digest=stable_hash(("report", generation_id)),
                evaluation_decision="PASS",
                observed_at="2026-11-11T09:39:00+08:00",
            )
            if wrong_ready.outcome is not RepositoryOutcome.IDENTITY_CONFLICT:
                raise AssertionError("WRONG_DAY103_RULER_WAS_NOT_REJECTED")
        ready = repository.mark_ready(
            generation_id=generation_id,
            expected_state_version=sealed.state_version,
            expected_manifest=expected_manifest,
            expected_absent_occurrence_ids=TOMBSTONED_IDS,
            ruler=ruler,
            validation_record_digest=stable_hash(
                ("validation", generation_id, sealed.checkpoint)
            ),
            evaluation_evidence_digest=stable_hash(
                ("evaluation-evidence", generation_id, ruler.fingerprint)
            ),
            evaluation_report_digest=stable_hash(
                ("evaluation-report", generation_id, ruler.fingerprint)
            ),
            evaluation_decision="PASS",
            observed_at=f"2026-11-11T09:{40 + offset:02d}:00+08:00",
        )
        if ready.outcome is not RepositoryOutcome.READY:
            raise AssertionError("GENERATION_READY_GATE_FAILED")
        generation_evidence[generation_id] = {
            "manifest_digest": sealed.manifest.digest,
            "checkpoint": sealed.checkpoint,
            "ready_state_version": ready.state_version,
            "occurrence_ids": list(readback.occurrence_ids),
        }

    changed_g2 = list(_points("G2"))
    changed_g2[1] = PgVectorPoint(
        **{
            **changed_g2[1].__dict__,
            "embedding": (0.0, 0.0, 1.0),
        }
    )
    late_write = repository.write_generation_points(
        generation_id="G2",
        provider_write_fence=2,
        points=tuple(changed_g2),
        created_at="2026-11-11T09:50:00+08:00",
    )
    if late_write.outcome is not RepositoryOutcome.IDENTITY_CONFLICT:
        raise AssertionError("SEALED_REPOSITORY_WRITE_NOT_REJECTED")
    if not _direct_sealed_write_is_rejected(factory):
        raise AssertionError("SEALED_DATABASE_WRITE_NOT_REJECTED")

    seeded = repository.seed_pointer(
        pointer_name=POINTER,
        scope_id=SCOPE,
        generation_id="G1",
        revision=7,
        seeded_at="2026-11-11T10:00:00+08:00",
    )
    if seeded.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("G1_POINTER_SEED_FAILED")
    old_view = repository.acquire_read_view(
        view_id="read-view-old-G1",
        pointer_name=POINTER,
        expected_generation_id="G1",
        expected_pointer_revision=7,
        owner_id="request-old",
        authorization_snapshot_id="P1",
        acquired_at="2026-11-11T10:01:00+08:00",
        lease_expires_at="2026-11-11T13:00:00+08:00",
    )
    if old_view.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("OLD_G1_READ_VIEW_NOT_ACQUIRED")

    lease_1 = repository.issue_activation_lease(
        pointer_name=POINTER,
        committer_id="committer-1",
        issued_at="2026-11-11T10:02:00+08:00",
        lease_expires_at="2026-11-11T12:30:00+08:00",
    )
    lease_2 = repository.rotate_activation_lease(
        pointer_name=POINTER,
        expected_committer_id=lease_1.committer_id,
        expected_fencing_token=lease_1.fencing_token,
        new_committer_id="committer-2",
        issued_at="2026-11-11T10:03:00+08:00",
        lease_expires_at="2026-11-11T12:30:00+08:00",
    )
    if lease_2 is None or lease_2.fencing_token != lease_1.fencing_token + 1:
        raise AssertionError("ACTIVATION_LEASE_ROTATION_FAILED")
    stale_activation = repository.activate(
        activation_id="activate-G2-stale-token",
        pointer_name=POINTER,
        target_generation_id="G2",
        expected_generation_id="G1",
        expected_revision=7,
        committer_id=lease_1.committer_id,
        committer_fence=lease_1.fencing_token,
        committed_at="2026-11-11T10:04:00+08:00",
        previous_retire_after="2026-11-11T12:00:00+08:00",
    )
    if stale_activation.outcome is not RepositoryOutcome.STALE_FENCE:
        raise AssertionError("STALE_ACTIVATION_TOKEN_WAS_NOT_FENCED")

    repeatable_connection = factory()
    repeatable_cursor = repeatable_connection.cursor()
    try:
        repeatable_cursor.execute("BEGIN ISOLATION LEVEL REPEATABLE READ")
        repeatable_cursor.execute(
            """
            SELECT build_snapshot_id, revision
            FROM day104_l3.current_build_snapshots
            WHERE scope_id = %s
            """,
            (SCOPE,),
        )
        repeatable_first = repeatable_cursor.fetchone()
        drift_result = repository.put_current_build_snapshot(
            snapshot=changed_snapshot,
            expected_current_revision=1,
            created_at="2026-11-11T10:03:30+08:00",
        )
        if (
            repeatable_first != ("BS1", 1)
            or drift_result.outcome is not RepositoryOutcome.APPLIED
            or drift_result.revision != 2
        ):
            raise AssertionError("REPEATABLE_READ_DRIFT_SETUP_FAILED")
        repeatable_cursor.execute(
            """
            SELECT build_snapshot_id, revision
            FROM day104_l3.current_build_snapshots
            WHERE scope_id = %s
            """,
            (SCOPE,),
        )
        repeatable_second = repeatable_cursor.fetchone()
        if repeatable_second != ("BS1", 1):
            raise AssertionError("REPEATABLE_READ_SNAPSHOT_CHANGED")
    finally:
        repeatable_connection.rollback()
        repeatable_cursor.close()
        repeatable_connection.close()
    current_after_drift = _query_one(
        factory,
        """
        SELECT build_snapshot_id, revision
        FROM day104_l3.current_build_snapshots
        WHERE scope_id = %s
        """,
        (SCOPE,),
    )
    if current_after_drift != ("BS-drift", 2):
        raise AssertionError("SECOND_CONNECTION_DID_NOT_COMMIT_SNAPSHOT_DRIFT")

    stale_snapshot_activation = repository.activate(
        activation_id="activate-G2-stale-build-snapshot",
        pointer_name=POINTER,
        target_generation_id="G2",
        expected_generation_id="G1",
        expected_revision=7,
        committer_id=lease_2.committer_id,
        committer_fence=lease_2.fencing_token,
        committed_at="2026-11-11T10:03:40+08:00",
        previous_retire_after="2026-11-11T12:00:00+08:00",
    )
    if stale_snapshot_activation.outcome is not RepositoryOutcome.STALE_POINTER:
        raise AssertionError("STALE_BUILD_SNAPSHOT_ACTIVATION_NOT_REJECTED")
    restored_snapshot = repository.put_current_build_snapshot(
        snapshot=snapshot,
        expected_current_revision=2,
        created_at="2026-11-11T10:04:20+08:00",
    )
    if (
        restored_snapshot.outcome is not RepositoryOutcome.APPLIED
        or restored_snapshot.revision != 3
    ):
        raise AssertionError("BUILD_SNAPSHOT_CAS_RESTORE_FAILED")

    atomicity_before = _activation_footprint(factory)

    def faulting_factory():
        return _FaultInjectingConnection(
            factory(),
            query_fragment="INSERT INTO day104_l3.activation_records",
        )

    faulting_repository = PostgresIndexLifecycleRepository(faulting_factory)
    fault_was_injected = False
    try:
        faulting_repository.activate(
            activation_id="activate-G2-fault-injected",
            pointer_name=POINTER,
            target_generation_id="G2",
            expected_generation_id="G1",
            expected_revision=7,
            committer_id=lease_2.committer_id,
            committer_fence=lease_2.fencing_token,
            committed_at="2026-11-11T10:04:30+08:00",
            previous_retire_after="2026-11-11T12:00:00+08:00",
        )
    except RuntimeError as exc:
        if str(exc) != "DAY104_ACTIVATION_RECORD_FAULT_INJECTED":
            raise
        fault_was_injected = True
    if not fault_was_injected:
        raise AssertionError("ACTIVATION_FAULT_INJECTION_DID_NOT_FIRE")
    atomicity_after = _activation_footprint(factory)
    if atomicity_after != atomicity_before:
        raise AssertionError("ACTIVATION_TRANSACTION_LEFT_PARTIAL_STATE")
    if (
        atomicity_after["pointer"] != {"generation_id": "G1", "revision": 7}
        or atomicity_after["G1"]["state"] != "ACTIVE"
        or atomicity_after["G2"]["state"] != "READY"
        or atomicity_after["activation_record_count"] != 0
        or atomicity_after["activation_outbox_count"] != 0
    ):
        raise AssertionError("ACTIVATION_TRANSACTION_ROLLBACK_INCOMPLETE")

    barrier = threading.Barrier(2)

    def activate_competitor(activation_id: str):
        competitor = PostgresIndexLifecycleRepository(factory)
        barrier.wait(timeout=10)
        return competitor.activate(
            activation_id=activation_id,
            pointer_name=POINTER,
            target_generation_id="G2",
            expected_generation_id="G1",
            expected_revision=7,
            committer_id=lease_2.committer_id,
            committer_fence=lease_2.fencing_token,
            committed_at="2026-11-11T10:05:00+08:00",
            previous_retire_after="2026-11-11T12:00:00+08:00",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                activate_competitor,
                ("activate-G2-race-a", "activate-G2-race-b"),
            )
        )
    race_outcomes = sorted(result.outcome.value for result in results)
    if race_outcomes != ["ACTIVATED", "STALE_POINTER"]:
        raise AssertionError("POINTER_RACE_DID_NOT_HAVE_EXACTLY_ONE_WINNER")

    new_view = repository.acquire_read_view(
        view_id="read-view-new-G2",
        pointer_name=POINTER,
        expected_generation_id="G2",
        expected_pointer_revision=8,
        owner_id="request-new",
        authorization_snapshot_id="P1",
        acquired_at="2026-11-11T10:06:00+08:00",
        lease_expires_at="2026-11-11T13:00:00+08:00",
    )
    if new_view.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("NEW_G2_READ_VIEW_NOT_ACQUIRED")
    abandoned_view = repository.acquire_read_view(
        view_id="read-view-abandoned-G2",
        pointer_name=POINTER,
        expected_generation_id="G2",
        expected_pointer_revision=8,
        owner_id="request-abandoned",
        authorization_snapshot_id="P1",
        acquired_at="2026-11-11T10:06:30+08:00",
        lease_expires_at="2026-11-11T10:08:00+08:00",
    )
    if abandoned_view.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("ABANDONED_G2_READ_VIEW_NOT_ACQUIRED")

    old_query = repository.query_read_view(
        view_id="read-view-old-G1",
        expected_fencing_token=1,
        expected_generation_id="G1",
        expected_authorization_snapshot_id="P1",
        tenant_id=TENANT,
        query_vector=(1.0, 0.0, 0.0),
        top_k=1,
        mode=QueryMode.EXACT,
        observed_at="2026-11-11T10:07:00+08:00",
    )
    if [hit.generation_id for hit in old_query] != ["G1"]:
        raise AssertionError("OLD_READ_VIEW_QUERY_MIXED_GENERATIONS")
    query_matrix = _query_matrix(
        repository,
        "G2",
        view_id="read-view-new-G2",
    )
    _assert_query_matrix(query_matrix)
    hnsw_plan = _hnsw_plan_evidence(factory)
    if hnsw_plan["uses_hnsw_index"] is not True:
        raise AssertionError("HNSW_QUERY_PLAN_DID_NOT_USE_FROZEN_INDEX")
    reaped_views = repository.reap_expired_read_views(
        observed_at="2026-11-11T10:09:00+08:00",
    )
    if reaped_views != ("read-view-abandoned-G2",):
        raise AssertionError("EXPIRED_READ_VIEW_NOT_REAPED_EXACTLY_ONCE")

    old_release = repository.release_read_view(
        view_id="read-view-old-G1",
        expected_fencing_token=1,
        released_at="2026-11-11T10:10:00+08:00",
    )
    if (
        old_release.outcome is not RepositoryOutcome.APPLIED
        or old_release.state_version is None
    ):
        raise AssertionError("OLD_READ_VIEW_RELEASE_FAILED")
    retired = repository.retire_generation(
        generation_id="G1",
        expected_state_version=old_release.state_version,
        retired_at="2026-11-11T12:01:00+08:00",
    )
    if retired.outcome is not RepositoryOutcome.RETIRED:
        raise AssertionError("G1_RETIREMENT_FAILED")
    new_release = repository.release_read_view(
        view_id="read-view-new-G2",
        expected_fencing_token=1,
        released_at="2026-11-11T12:02:00+08:00",
    )
    if new_release.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("NEW_READ_VIEW_RELEASE_FAILED")

    logical_release_evidence = DeletionEvidence(
        evidence_id="deletion-evidence-logical-release",
        deletion_snapshot_id="D1",
        verification_policy_id="day104-l3-serving-absence-v1",
        validator_id="day104-deletion-validator",
        validator_version="v1",
        scope=DeletionEvidenceScope.LOGICAL_RELEASE,
        status=EvidenceStatus.PASS,
        pointer_name=POINTER,
        pointer_revision=8,
        generation_ids=("G2",),
        tombstoned_occurrence_ids=TOMBSTONED_IDS,
        readback_digest=stable_hash(
            (
                "LOGICAL_RELEASE",
                command.deletion_snapshot_id,
                command.deletion_digest,
                POINTER,
                8,
                ("G2",),
                TOMBSTONED_IDS,
            )
        ),
        observed_at="2026-11-11T12:02:10+08:00",
    )
    serving_absence_evidence = DeletionEvidence(
        evidence_id="deletion-evidence-serving-index-absence",
        deletion_snapshot_id="D1",
        verification_policy_id="day104-l3-serving-absence-v1",
        validator_id="day104-deletion-validator",
        validator_version="v1",
        scope=DeletionEvidenceScope.SERVING_INDEX_ABSENCE,
        status=EvidenceStatus.PASS,
        pointer_name=POINTER,
        pointer_revision=8,
        generation_ids=("G2",),
        tombstoned_occurrence_ids=TOMBSTONED_IDS,
        readback_digest=stable_hash(
            (
                "SERVING_INDEX_ABSENCE",
                generation_evidence["G2"],
                query_matrix,
            )
        ),
        observed_at="2026-11-11T12:02:11+08:00",
    )
    physical_purge_evidence = DeletionEvidence(
        evidence_id="deletion-evidence-physical-purge-not-run",
        deletion_snapshot_id="D1",
        verification_policy_id="day104-l3-serving-absence-v1",
        validator_id="day104-deletion-validator",
        validator_version="v1",
        scope=DeletionEvidenceScope.PHYSICAL_PURGE,
        status=EvidenceStatus.NOT_RUN,
        pointer_name=POINTER,
        pointer_revision=8,
        generation_ids=(),
        tombstoned_occurrence_ids=TOMBSTONED_IDS,
        readback_digest=stable_hash(("PHYSICAL_PURGE", "NOT_RUN")),
        observed_at="2026-11-11T12:02:12+08:00",
    )
    dispatched_deletion = repository.mark_deletion_dispatched(deletion_id="delete-B-v1")
    if dispatched_deletion.outcome is not RepositoryOutcome.DISPATCHED:
        raise AssertionError("DELETION_INTENT_NOT_DISPATCHED")
    deletion_evidence_results = tuple(
        repository.record_deletion_evidence(evidence)
        for evidence in (
            logical_release_evidence,
            serving_absence_evidence,
            physical_purge_evidence,
        )
    )
    if any(
        result.outcome is not RepositoryOutcome.APPLIED
        for result in deletion_evidence_results
    ):
        raise AssertionError("DELETION_EVIDENCE_RECORDING_FAILED")
    verified_deletion = repository.verify_deletion(deletion_id="delete-B-v1")
    replayed_deletion = repository.verify_deletion(deletion_id="delete-B-v1")
    if (
        verified_deletion.outcome is not RepositoryOutcome.VERIFIED
        or replayed_deletion.outcome is not RepositoryOutcome.EXACT_REPLAY
    ):
        raise AssertionError("DELETION_VERIFICATION_DID_NOT_CONVERGE")
    persisted_deletion = _query_one(
        factory,
        """
        SELECT state, verified_deletion_snapshot_id,
               verified_evidence_ids, verified_evidence_digest
        FROM day104_l3.deletion_intents
        WHERE deletion_id = 'delete-B-v1'
        """,
    )
    if (
        persisted_deletion is None
        or persisted_deletion[0] != "VERIFIED"
        or persisted_deletion[1] != "D1"
        or tuple(persisted_deletion[2])
        != (
            "deletion-evidence-logical-release",
            "deletion-evidence-serving-index-absence",
        )
        or persisted_deletion[3] != verified_deletion.identity_digest
    ):
        raise AssertionError("PERSISTED_DELETION_VERIFICATION_BINDING_MISMATCH")

    first_claim = repository.claim_outbox(
        worker_id="outbox-worker-1",
        claimed_at="2026-11-11T12:02:30+08:00",
    )
    if first_claim is None:
        raise AssertionError("OUTBOX_EVENT_NOT_CLAIMED")
    reclaimed_claim = repository.reclaim_stale_outbox(
        worker_id="outbox-worker-recovery",
        reclaimed_at="2026-11-11T12:04:00+08:00",
        processing_timeout_seconds=60.0,
    )
    if (
        reclaimed_claim is None
        or reclaimed_claim.event_id != first_claim.event_id
        or reclaimed_claim.claim_fence != first_claim.claim_fence + 1
    ):
        raise AssertionError("STALE_OUTBOX_CLAIM_NOT_RECLAIMED")
    stale_claim_apply = repository.apply_outbox(
        claim=first_claim,
        payload_digest=first_claim.payload_digest,
        source_stream="day104-l3-outbox",
        result_id="result-source-deletion",
        result_digest=stable_hash(("result", first_claim.event_id)),
        applied_at="2026-11-11T12:04:10+08:00",
    )
    if stale_claim_apply.outcome is not RepositoryOutcome.STALE_FENCE:
        raise AssertionError("RECLAIMED_OUTBOX_DID_NOT_FENCE_OLD_WORKER")
    first_apply = repository.apply_outbox(
        claim=reclaimed_claim,
        payload_digest=reclaimed_claim.payload_digest,
        source_stream="day104-l3-outbox",
        result_id="result-source-deletion",
        result_digest=stable_hash(("result", reclaimed_claim.event_id)),
        applied_at="2026-11-11T12:04:20+08:00",
    )
    exact_apply = repository.apply_outbox(
        claim=reclaimed_claim,
        payload_digest=reclaimed_claim.payload_digest,
        source_stream="day104-l3-outbox",
        result_id="result-source-deletion",
        result_digest=stable_hash(("result", reclaimed_claim.event_id)),
        applied_at="2026-11-11T12:04:30+08:00",
    )
    conflicting_apply = repository.apply_outbox(
        claim=reclaimed_claim,
        payload_digest=stable_hash(("conflicting-payload", reclaimed_claim.event_id)),
        source_stream="day104-l3-outbox",
        result_id="result-source-deletion",
        result_digest=stable_hash(("result", reclaimed_claim.event_id)),
        applied_at="2026-11-11T12:04:40+08:00",
    )
    if (
        first_apply.outcome is not RepositoryOutcome.APPLIED
        or exact_apply.outcome is not RepositoryOutcome.EXACT_REPLAY
        or conflicting_apply.outcome is not RepositoryOutcome.IDENTITY_CONFLICT
    ):
        raise AssertionError("OUTBOX_REPLAY_OR_CONFLICT_RULE_FAILED")

    second_claim = repository.claim_outbox(
        worker_id="outbox-worker-2",
        claimed_at="2026-11-11T12:05:30+08:00",
    )
    if second_claim is None:
        raise AssertionError("ACTIVATION_OUTBOX_EVENT_NOT_CLAIMED")
    second_apply = repository.apply_outbox(
        claim=second_claim,
        payload_digest=second_claim.payload_digest,
        source_stream="day104-l3-outbox",
        result_id="result-activation",
        result_digest=stable_hash(("result", second_claim.event_id)),
        applied_at="2026-11-11T12:06:00+08:00",
    )
    if second_apply.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("ACTIVATION_OUTBOX_EVENT_NOT_APPLIED")
    inbox_count = _query_one(
        factory,
        "SELECT count(*) FROM day104_l3.inbox_records",
    )
    if inbox_count != (2,):
        raise AssertionError("INBOX_DURABLE_RESULT_COUNT_MISMATCH")

    restarted_repository = PostgresIndexLifecycleRepository(factory)
    restarted_manifest = restarted_repository.readback_manifest("G2")
    restarted_queries = _query_matrix(restarted_repository, "G2")
    durable_state = _database_state(factory)
    if (
        restarted_manifest != expected_manifest
        or restarted_queries != query_matrix
        or durable_state["pointer"] != {"generation_id": "G2", "revision": 8}
        or durable_state["G1"]["state"] != "RETIRED"
        or durable_state["G2"]["state"] != "ACTIVE"
    ):
        raise AssertionError("REPOSITORY_RESTART_READBACK_MISMATCH")

    hard_gates = {
        "day99_candidate_identity_match": _gate(
            "component-version-readback",
            environment,
        ),
        "schema_migration_integrity": _gate(
            "installed-day104-l3-schema",
            (environment, schema_table_count),
        ),
        "build_snapshot_repeatable_read": _gate(
            "two-connection-repeatable-read-and-cas-restore",
            (
                repeatable_first,
                repeatable_second,
                current_after_drift,
                restored_snapshot.revision,
                snapshot.fingerprint,
                changed_snapshot.fingerprint,
            ),
        ),
        "physical_generation_immutability": _gate(
            "sealed-write-rejected",
            (late_write.outcome.value, True),
        ),
        "manifest_exact_readback": _gate(
            "generation-manifest-readback",
            generation_evidence,
        ),
        "day103_evaluation_hard_gates": _gate(
            "Q1-Q2-Q3-query-matrix",
            (query_matrix, hnsw_plan),
        ),
        "ready_freshness_guard": _gate(
            "wrong-ruler-and-stale-build-snapshot-rejected",
            (
                ruler.fingerprint,
                stale_snapshot_activation.outcome.value,
                current_after_drift,
                restored_snapshot.revision,
            ),
        ),
        "activation_transaction_atomicity": _gate(
            "activation-record-fault-rolls-back-transaction",
            (atomicity_before, atomicity_after),
        ),
        "lease_fencing": _gate(
            "activation-lease-rotation",
            (
                lease_1.fencing_token,
                lease_2.fencing_token,
                stale_activation.outcome.value,
            ),
        ),
        "concurrent_pointer_cas": _gate(
            "two-connection-activation-race",
            race_outcomes,
        ),
        "read_view_single_generation": _gate(
            "old-G1-new-G2-read-views",
            (old_view.generation_id, new_view.generation_id, query_matrix),
        ),
        "expired_read_view_reaper": _gate(
            "abandoned-G2-read-view-reaped",
            reaped_views,
        ),
        "drain_and_retirement": _gate(
            "G1-reader-drain-retire",
            (old_release.state_version, retired.state_version),
        ),
        "pointer_projection_authority": _gate(
            "database-pointer-remains-authoritative",
            (durable_state["pointer"], second_apply.outcome.value),
        ),
        "outbox_inbox_reconciliation": _gate(
            "outbox-reclaim-inbox-replay-and-conflict",
            (
                reclaimed_claim.event_id,
                stale_claim_apply.outcome.value,
                exact_apply.outcome.value,
                conflicting_apply.outcome.value,
                inbox_count,
            ),
        ),
        "deletion_no_resurrection": _gate(
            "D1-excludes-B-from-both-generations-and-retrieval",
            (
                command.identity_digest,
                replay.outcome.value,
                conflict.outcome.value,
                generation_evidence,
                query_matrix,
                tuple(result.outcome.value for result in deletion_evidence_results),
                verified_deletion.outcome.value,
                replayed_deletion.outcome.value,
                persisted_deletion,
            ),
        ),
        "restart_durability_and_idempotency": _gate(
            "new-repository-instance",
            (restarted_manifest.fingerprint, restarted_queries, durable_state),
        ),
    }
    completed_at = datetime.now(timezone.utc).isoformat()
    payload: dict[str, object] = {
        "schema_version": "day104-l3-runner.v1",
        "scenario_id": "day104-refund-index-generation-lifecycle-l3-v1",
        "status": "PASS",
        "evidence_level": ("EXECUTED_LOCAL_DOCKER_INTEGRATION_POSTGRESQL_PGVECTOR"),
        "started_at": started_at,
        "completed_at": completed_at,
        "baseline": {
            "day99_candidate_id": "postgresql-pgvector-0.8.7",
            "day99_outcome": "PROVISIONAL_SELECTED",
            "day104_l2_report_checksum": L2_REPORT_CHECKSUM,
        },
        "environment": environment,
        "scenario": {
            "source_occurrence_count": 3,
            "eligible_occurrence_ids": list(EXPECTED_IDS),
            "tombstoned_occurrence_ids": list(TOMBSTONED_IDS),
            "query_expected_ids": {
                "Q1": ["A@v1"],
                "Q2": ["C@v1"],
                "Q3": ["A@v1", "C@v1"],
            },
        },
        "identities": {
            "source_snapshot_digest": command.source_digest,
            "deletion_snapshot_digest": command.deletion_digest,
            "build_snapshot_fingerprint": snapshot.fingerprint,
            "evaluation_ruler_fingerprint": ruler.fingerprint,
        },
        "generations": generation_evidence,
        "repeatable_read": {
            "connection_1_first": list(repeatable_first or ()),
            "connection_2_committed": list(current_after_drift or ()),
            "connection_1_second": list(repeatable_second or ()),
            "restored_current": ["BS1", restored_snapshot.revision],
            "stale_activation_outcome": stale_snapshot_activation.outcome.value,
        },
        "activation": {
            "stale_token_outcome": stale_activation.outcome.value,
            "fault_injection_raised": fault_was_injected,
            "atomicity_before": atomicity_before,
            "atomicity_after": atomicity_after,
            "race_outcomes": race_outcomes,
            "active_pointer": durable_state["pointer"],
        },
        "read_views": {
            "old_generation": old_view.generation_id,
            "new_generation": new_view.generation_id,
            "old_generation_final_state": durable_state["G1"]["state"],
            "reaped_views": list(reaped_views),
        },
        "retrieval": query_matrix,
        "hnsw_plan": hnsw_plan,
        "outbox": {
            "first_apply": first_apply.outcome.value,
            "stale_claim_apply": stale_claim_apply.outcome.value,
            "reclaimed_fence": reclaimed_claim.claim_fence,
            "exact_replay": exact_apply.outcome.value,
            "different_digest": conflicting_apply.outcome.value,
            "activation_event_apply": second_apply.outcome.value,
            "inbox_record_count": int(inbox_count[0]),
        },
        "deletion_evidence": {
            "intent_id": "delete-B-v1",
            "intent_state": str(persisted_deletion[0]),
            "deletion_snapshot_id": str(persisted_deletion[1]),
            "logical_release": {
                "status": logical_release_evidence.status.value,
                "evidence_id": logical_release_evidence.evidence_id,
                "evidence_digest": logical_release_evidence.digest,
            },
            "serving_index_absence": {
                "status": serving_absence_evidence.status.value,
                "evidence_id": serving_absence_evidence.evidence_id,
                "evidence_digest": serving_absence_evidence.digest,
            },
            "physical_purge": {
                "status": physical_purge_evidence.status.value,
                "evidence_id": physical_purge_evidence.evidence_id,
                "evidence_digest": physical_purge_evidence.digest,
            },
            "adopted_evidence_ids": list(persisted_deletion[2]),
            "adopted_evidence_digest": str(persisted_deletion[3]),
            "verify_outcome": verified_deletion.outcome.value,
            "verify_replay_outcome": replayed_deletion.outcome.value,
        },
        "application_restart": {
            "new_repository_instance": True,
            "manifest_fingerprint": restarted_manifest.fingerprint,
            "pointer": durable_state["pointer"],
        },
        "hard_gates": hard_gates,
        "fixture_production_eligible": False,
        "raw_content_logged": False,
        "raw_vectors_logged": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "not_run": [
            "database container restart",
            "PostgreSQL HA, replica failover and backup restore",
            "physical purge across WAL, backups and caches",
            "production-scale recall, latency, capacity, cost and soak",
            "production traffic and incident observation window",
        ],
        "claim_boundary": (
            "Local disposable PostgreSQL/pgvector integration fixture only; "
            "no physical-purge, HA, zero-downtime or production claim."
        ),
    }
    payload["report_checksum"] = stable_hash(payload)
    return payload


def _fail_closed_payload(reason: str, error_type: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "day104-l3-runner.v1",
        "scenario_id": "day104-refund-index-generation-lifecycle-l3-v1",
        "status": "FAIL_CLOSED",
        "evidence_level": "NOT_RUN",
        "safe_reason": reason,
        "fixture_production_eligible": False,
        "raw_content_logged": False,
        "raw_vectors_logged": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }
    if error_type is not None:
        payload["error_type"] = error_type
    payload["report_checksum"] = stable_hash(payload)
    return payload


def main() -> int:
    if os.environ.get("DAY104_L3_INTEGRATION") != "1":
        print(
            json.dumps(
                _fail_closed_payload("DAY104_L3_INTEGRATION_FLAG_REQUIRED"),
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    database_url = os.environ.get("DAY104_L3_DATABASE_URL", "")
    if not database_url.strip():
        print(
            json.dumps(
                _fail_closed_payload("DAY104_L3_DATABASE_URL_REQUIRED"),
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    try:
        report = run_integration(database_url)
    except BaseException as exc:
        report = _fail_closed_payload(
            "DAY104_L3_INTEGRATION_FAILED",
            type(exc).__name__,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
