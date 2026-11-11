"""Replay Day104 L3 evidence from a fresh application repository instance.

This runner is deliberately narrower than the destructive integration setup.
It never installs or resets the schema.  It reads the already-completed L3
scenario, creates one uniquely named ReadView for retrieval verification, and
closes that view before returning content-safe evidence.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, cast
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from rag_chunking_contracts import stable_hash  # noqa: E402
from rag_index_lifecycle_orchestrator import (  # noqa: E402
    IndexedOccurrence,
    manifest_facts,
)
from rag_index_lifecycle_postgres import (  # noqa: E402
    ConnectionFactory,
    PostgresIndexLifecycleRepository,
    QueryMode,
    RepositoryOutcome,
    psycopg2_connection_factory,
)


SCHEMA_VERSION = "day104-l3-restart-replay.v1"
SCENARIO_ID = "day104-refund-index-generation-lifecycle-l3-restart-v1"
SCOPE = "refund-rag"
TENANT = "tenant-refund"
POINTER = "refund-serving"
AUTHORIZATION_SNAPSHOT = "P1"
EXPECTED_IDS = ("A@v1", "C@v1")
TOMBSTONED_IDS = ("B@v1",)


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


def _read_rows(
    factory: ConnectionFactory,
    query: str,
    params: Sequence[object] | None = None,
) -> list[Sequence[Any]]:
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute(query, params)
        rows = cursor.fetchall()
        connection.commit()
        return rows
    except BaseException:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def _durable_state(factory: ConnectionFactory) -> dict[str, object]:
    pointer_rows = _read_rows(
        factory,
        """
        SELECT generation_id, revision
        FROM day104_l3.active_pointers
        WHERE pointer_name = %s
        """,
        (POINTER,),
    )
    if pointer_rows != [("G2", 8)]:
        raise AssertionError("RESTART_POINTER_NOT_G2_R8")

    generation_rows = _read_rows(
        factory,
        """
        SELECT generation_id, state, active_readers
        FROM day104_l3.generations
        WHERE generation_id IN ('G1', 'G2')
        ORDER BY generation_id
        """,
    )
    expected_generations = [("G1", "RETIRED", 0), ("G2", "ACTIVE", 0)]
    if generation_rows != expected_generations:
        raise AssertionError("RESTART_GENERATION_STATE_MISMATCH")

    tombstone_rows = _read_rows(
        factory,
        """
        SELECT occurrence_id, deletion_id, ledger_revision
        FROM day104_l3.tombstones
        WHERE scope_id = %s
        ORDER BY occurrence_id
        """,
        (SCOPE,),
    )
    if len(tombstone_rows) != 1 or tombstone_rows[0][0] != "B@v1":
        raise AssertionError("RESTART_TOMBSTONE_BINDING_MISMATCH")

    delivery_rows = _read_rows(
        factory,
        """
        SELECT outbox.event_id, outbox.payload_digest, outbox.state,
               inbox.payload_digest, inbox.state
        FROM day104_l3.outbox_events AS outbox
        LEFT JOIN day104_l3.inbox_records AS inbox
          ON inbox.event_id = outbox.event_id
        ORDER BY outbox.event_id
        """,
    )
    if len(delivery_rows) != 2 or any(
        row[2] != "DISPATCHED" or row[4] != "APPLIED" or row[1] != row[3]
        for row in delivery_rows
    ):
        raise AssertionError("RESTART_OUTBOX_INBOX_BINDING_MISMATCH")

    return {
        "pointer": {"generation_id": "G2", "revision": 8},
        "generations": {
            "G1": {"state": "RETIRED", "active_readers": 0},
            "G2": {"state": "ACTIVE", "active_readers": 0},
        },
        "tombstones": {
            "occurrence_ids": list(TOMBSTONED_IDS),
            "count": len(tombstone_rows),
            "binding_digest": stable_hash(tuple(tuple(row) for row in tombstone_rows)),
        },
        "delivery": {
            "outbox_dispatched": len(delivery_rows),
            "inbox_applied": len(delivery_rows),
            "binding_digest": stable_hash(tuple(tuple(row) for row in delivery_rows)),
        },
    }


def _query_matrix(
    repository: PostgresIndexLifecycleRepository,
    *,
    view_id: str,
    observed_at: str,
) -> dict[str, dict[str, list[str]]]:
    root_half = 1.0 / math.sqrt(2.0)
    queries = {
        "Q1": ((1.0, 0.0, 0.0), 1),
        "Q2": ((0.0, 1.0, 0.0), 1),
        "Q3": ((root_half, root_half, 0.0), 2),
    }
    matrix: dict[str, dict[str, list[str]]] = {}
    for mode in (QueryMode.EXACT, QueryMode.HNSW):
        mode_results: dict[str, list[str]] = {}
        for query_id, (query_vector, top_k) in queries.items():
            hits = repository.query_read_view(
                view_id=view_id,
                expected_fencing_token=1,
                expected_generation_id="G2",
                expected_authorization_snapshot_id=AUTHORIZATION_SNAPSHOT,
                tenant_id=TENANT,
                query_vector=cast(tuple[float, ...], query_vector),
                top_k=cast(int, top_k),
                mode=mode,
                observed_at=observed_at,
            )
            if any(hit.generation_id != "G2" for hit in hits):
                raise AssertionError("RESTART_QUERY_MIXED_GENERATIONS")
            mode_results[query_id] = [hit.occurrence_id for hit in hits]
        matrix[mode.value] = mode_results

    expected = {
        "Q1": ["A@v1"],
        "Q2": ["C@v1"],
        "Q3": ["A@v1", "C@v1"],
    }
    if matrix.get("EXACT") != expected or matrix.get("HNSW") != expected:
        raise AssertionError("RESTART_Q1_Q2_Q3_MISMATCH")
    return matrix


def _closed_view_evidence(
    factory: ConnectionFactory,
    *,
    view_id: str,
) -> dict[str, object]:
    rows = _read_rows(
        factory,
        """
        SELECT view.status, view.fencing_token, view.generation_id,
               generation.active_readers
        FROM day104_l3.read_views AS view
        JOIN day104_l3.generations AS generation
          ON generation.generation_id = view.generation_id
        WHERE view.view_id = %s
        """,
        (view_id,),
    )
    if rows != [("CLOSED", 2, "G2", 0)]:
        raise AssertionError("RESTART_READ_VIEW_NOT_CLOSED_CLEANLY")
    return {
        "view_id_digest": stable_hash(view_id),
        "generation_id": "G2",
        "final_status": "CLOSED",
        "final_fencing_token": 2,
        "active_readers_after_close": 0,
    }


def run_restart_replay(database_url: str) -> dict[str, object]:
    if not database_url.strip():
        raise ValueError("DAY104_L3_DATABASE_URL_REQUIRED")

    factory = psycopg2_connection_factory(
        database_url,
        application_name="day104-l3-restart-replay",
    )
    repository = PostgresIndexLifecycleRepository(factory)

    durable_state = _durable_state(factory)
    manifest = repository.readback_manifest("G2")
    expected_manifest = _expected_manifest()
    if manifest != expected_manifest or manifest.occurrence_ids != EXPECTED_IDS:
        raise AssertionError("RESTART_G2_MANIFEST_MISMATCH")

    now = datetime.now(timezone.utc)
    acquired_at = now.isoformat()
    lease_expires_at = (now + timedelta(minutes=10)).isoformat()
    view_id = f"restart-read-view-{uuid4().hex}"
    acquired = False
    query_matrix: dict[str, dict[str, list[str]]] | None = None
    try:
        result = repository.acquire_read_view(
            view_id=view_id,
            pointer_name=POINTER,
            expected_generation_id="G2",
            expected_pointer_revision=8,
            owner_id="day104-l3-restart-replay",
            authorization_snapshot_id=AUTHORIZATION_SNAPSHOT,
            acquired_at=acquired_at,
            lease_expires_at=lease_expires_at,
        )
        if result.outcome is not RepositoryOutcome.APPLIED:
            raise AssertionError("RESTART_READ_VIEW_ACQUIRE_FAILED")
        acquired = True
        query_matrix = _query_matrix(
            repository,
            view_id=view_id,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )
    finally:
        if acquired:
            released = repository.release_read_view(
                view_id=view_id,
                expected_fencing_token=1,
                released_at=datetime.now(timezone.utc).isoformat(),
            )
            if released.outcome is not RepositoryOutcome.APPLIED:
                raise AssertionError("RESTART_READ_VIEW_RELEASE_FAILED")

    if query_matrix is None:
        raise AssertionError("RESTART_QUERY_MATRIX_NOT_PRODUCED")
    closed_view = _closed_view_evidence(factory, view_id=view_id)

    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "status": "PASS",
        "evidence_level": ("EXECUTED_LOCAL_DOCKER_INTEGRATION_POSTGRESQL_PGVECTOR"),
        "application_restart": {
            "new_repository_instance": True,
            "database_container_restart_proven": False,
        },
        "durable_state": durable_state,
        "manifest": {
            "generation_id": "G2",
            "occurrence_count": manifest.occurrence_count,
            "occurrence_ids": list(manifest.occurrence_ids),
            "manifest_fingerprint": manifest.fingerprint,
        },
        "read_view": closed_view,
        "queries": query_matrix,
        "checks": {
            "pointer_g2_revision_8": True,
            "generation_states": True,
            "g2_manifest_exact_readback": True,
            "b_tombstone_durable": True,
            "two_outbox_and_inbox_bindings": True,
            "read_view_closed_after_exact_and_hnsw": True,
            "q1_q2_q3_same_ruler": True,
        },
        "claim_boundary": (
            "Fresh application connections replayed durable PostgreSQL and pgvector "
            "facts. This does not prove a database-container restart, replication, "
            "backup restore, physical erasure, load behavior or production readiness."
        ),
        "fixture_production_eligible": False,
        "raw_content_logged": False,
        "raw_vectors_logged": False,
        "database_url_logged": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }
    report["report_checksum"] = stable_hash(report)
    return report


def _fail_closed_payload(
    reason: str, error_type: str | None = None
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "status": "FAIL_CLOSED",
        "evidence_level": "NOT_RUN",
        "safe_reason": reason,
        "fixture_production_eligible": False,
        "raw_content_logged": False,
        "raw_vectors_logged": False,
        "database_url_logged": False,
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
        report = run_restart_replay(database_url)
    except BaseException as exc:
        print(
            json.dumps(
                _fail_closed_payload(
                    "DAY104_L3_RESTART_REPLAY_FAILED",
                    type(exc).__name__,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
