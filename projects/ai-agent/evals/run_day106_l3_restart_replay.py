"""Read back the Day106 L3 durable chain after a real container restart.

This entrypoint never installs or resets schemas and never calls a model
Provider.  A final evidence replay compares its postmaster timestamp and state
digest with the initial integration report.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence, cast


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from rag_capstone_contracts import ResponseIntentState  # noqa: E402
from rag_capstone_postgres import PostgresRagCapstoneRepository  # noqa: E402
from rag_chunking_contracts import stable_hash  # noqa: E402
from rag_index_lifecycle_postgres import (  # noqa: E402
    ConnectionFactory,
    psycopg2_connection_factory,
)


SCHEMA_VERSION = "day106-l3-restart-replay.v2"
SCENARIO_ID = "day106-production-rag-postgresql-pgvector-l3a-v1"
INTENT_ID = "response-intent-Day106-Q2-G3"


def _query_one(
    factory: ConnectionFactory,
    query: str,
    params: tuple[object, ...] = (),
) -> Sequence[Any] | None:
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def run_restart_replay(database_url: str) -> dict[str, object]:
    if os.environ.get("DAY106_L3_INTEGRATION") != "1":
        raise RuntimeError("DAY106_L3_INTEGRATION_FLAG_REQUIRED")
    if not database_url.strip():
        raise ValueError("DAY106_L3_DATABASE_URL_REQUIRED")

    started = datetime.now(timezone.utc)
    factory = psycopg2_connection_factory(
        database_url,
        application_name="day106-l3-container-restart-replay",
    )
    capstone = PostgresRagCapstoneRepository(factory, integration_enabled=True)
    environment = _query_one(
        factory,
        """
        SELECT current_database(), current_setting('server_version'),
               (SELECT extversion FROM pg_extension WHERE extname = 'vector'),
               pg_postmaster_start_time()
        """,
    )
    pointer = _query_one(
        factory,
        """
        SELECT generation_id, revision
        FROM day104_l3.active_pointers
        WHERE pointer_name = 'refund-serving'
        """,
    )
    security = _query_one(
        factory,
        """
        SELECT snapshot_id, revision
        FROM day105_l3.current_security_snapshots
        WHERE tenant_id = 'tenant-refund'
        """,
    )
    provider_count = _query_one(
        factory,
        "SELECT count(*) FROM day106_l3.provider_call_receipts",
    )
    intent = capstone.read_response_intent(INTENT_ID)
    history = capstone.read_recovery_history(INTENT_ID)
    state_identity = capstone.durable_state_identity(INTENT_ID)
    if (
        environment is None
        or environment[0] != "day106_l3"
        or environment[2] is None
        or pointer != ("G3", 9)
        or security != ("P2", 2)
        or provider_count is None
        or int(provider_count[0]) != 0
        or intent is None
        or intent.state != ResponseIntentState.DELIVERED.value
        or len(history) != 7
        or state_identity is None
    ):
        raise AssertionError("DAY106_RESTART_DURABLE_STATE_MISMATCH")

    completed = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "run_id": f"day106-l3-restart-{stable_hash((started.isoformat(), state_identity))[7:23]}",
        "status": "PASS",
        "started_at": started.isoformat(),
        "completed_at": completed.isoformat(),
        "postmaster_started_at": cast(datetime, environment[3]).isoformat(),
        "database_identity_digest": stable_hash(
            ("day106_l3", str(environment[1]), str(environment[2]))
        ),
        "generation_id": "G3",
        "pointer_revision": 9,
        "authorization_snapshot_id": "P2",
        "authorization_revision": 2,
        "intent_id": INTENT_ID,
        "intent_identity_digest": intent.identity_digest,
        "final_dispatch_state": intent.state,
        "recovery_record_count": len(history),
        "recovery_record_digests": [item.identity_digest for item in history],
        "durable_state_identity_digest": state_identity,
        "provider_call_count": 0,
        "schemas_reinstalled": False,
        "schemas_reset": False,
        "external_provider_called": False,
        "raw_content_logged": False,
        "provider_response_logged": False,
        "secret_logged": False,
        "raw_vector_logged": False,
        "database_url_logged": False,
    }
    payload["report_checksum"] = stable_hash(payload)
    return payload


def _fail_closed(reason: str, error_type: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "status": "FAIL_CLOSED",
        "safe_reason": reason,
        "provider_call_count": 0,
        "schemas_reinstalled": False,
        "schemas_reset": False,
        "external_provider_called": False,
        "raw_content_logged": False,
        "provider_response_logged": False,
        "secret_logged": False,
        "raw_vector_logged": False,
        "database_url_logged": False,
    }
    if error_type is not None:
        payload["error_type"] = error_type
    payload["report_checksum"] = stable_hash(payload)
    return payload


def _write_exclusive(path: Path, report: dict[str, object]) -> None:
    """Write sanitized restart evidence once without rewriting history."""

    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-path",
        type=Path,
        help="optional new path for sanitized restart evidence; refuses overwrite",
    )
    arguments = parser.parse_args()
    if os.environ.get("DAY106_L3_INTEGRATION") != "1":
        print(
            json.dumps(
                _fail_closed("DAY106_L3_INTEGRATION_FLAG_REQUIRED"),
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    database_url = os.environ.get("DAY106_L3_DATABASE_URL", "")
    if not database_url.strip():
        print(
            json.dumps(
                _fail_closed("DAY106_L3_DATABASE_URL_REQUIRED"),
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
                _fail_closed("DAY106_L3_RESTART_REPLAY_FAILED", type(exc).__name__),
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    if arguments.report_path is not None:
        try:
            _write_exclusive(arguments.report_path, report)
        except BaseException as exc:
            print(
                json.dumps(
                    _fail_closed(
                        "DAY106_L3_RESTART_REPORT_WRITE_FAILED",
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
