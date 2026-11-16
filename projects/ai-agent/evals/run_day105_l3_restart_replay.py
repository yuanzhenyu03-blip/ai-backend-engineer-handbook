"""Replay Day105 L3 after a real PostgreSQL container restart.

This runner never installs or resets schemas. It uses fresh connections,
compares the durable pre-restart postmaster identity with the current server,
replays the active G3 query, and drains the historical G2 ReadView.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import sys
from typing import cast
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from evals.run_day105_l3_integration import (  # noqa: E402
    POINTER,
    SCENARIO_ID,
    TENANT,
    _durable_restart_state_identity,
    _query_one,
    _query_read_view_ids,
)
from rag_chunking_contracts import stable_hash  # noqa: E402
from rag_index_lifecycle_postgres import (  # noqa: E402
    ConnectionFactory,
    PostgresIndexLifecycleRepository,
    QueryMode,
    ReadViewQueryRejected,
    RepositoryOutcome,
    psycopg2_connection_factory,
)
from rag_security_contracts import (  # noqa: E402
    SecurityDisposition,
    SecurityResult,
)
from rag_security_postgres import (  # noqa: E402
    PostgresRagSecurityRepository,
    SecurityArtifact,
    SecurityArtifactType,
    SecurityRepositoryOutcome,
)


SCHEMA_VERSION = "day105-l3-restart-replay.v1"
REPORT_PATH = ROOT / "evidence" / "day105-l3-restart-replay.json"


def _postmaster_times(
    factory: ConnectionFactory,
) -> tuple[datetime, datetime, str]:
    stored = _query_one(
        factory,
        """
        SELECT payload ->> 'postmaster_start_at',
               payload ->> 'pre_restart_state_identity_digest'
        FROM day105_l3.security_artifacts
        WHERE artifact_id = 'environment-evidence:pre-container-restart'
        """,
    )
    current = _query_one(factory, "SELECT pg_postmaster_start_time()")
    if stored is None or current is None:
        raise AssertionError("POSTMASTER_RESTART_BINDING_MISSING")
    before = datetime.fromisoformat(str(stored[0]).replace("Z", "+00:00"))
    after = cast(datetime, current[0]).astimezone(timezone.utc)
    pre_restart_identity = cast(str | None, stored[1])
    if (
        before.tzinfo is None
        or after <= before
        or pre_restart_identity is None
        or not pre_restart_identity.startswith("sha256:")
    ):
        raise AssertionError("DATABASE_CONTAINER_RESTART_NOT_PROVEN")
    return before, after, pre_restart_identity


def _artifact_replay(
    repository: PostgresRagSecurityRepository,
    factory: ConnectionFactory,
) -> tuple[str, str]:
    row = _query_one(
        factory,
        """
        SELECT request_id, identity_digest, payload ->> 'subject_digest',
               parent_digests, result, disposition,
               payload ->> 'evidence_digest', created_at
        FROM day105_l3.security_artifacts
        WHERE artifact_id = 'security-artifact-replay-probe'
        """,
    )
    if row is None:
        raise AssertionError("REPLAY_PROBE_NOT_DURABLE")
    artifact = SecurityArtifact(
        artifact_id="security-artifact-replay-probe",
        artifact_type=SecurityArtifactType.CONTENT_SECURITY_RECORD,
        request_id=cast(str | None, row[0]),
        subject_digest=cast(str, row[2]),
        parent_digests=tuple(row[3]),
        result=SecurityResult(cast(str, row[4])),
        disposition=SecurityDisposition(cast(str, row[5])),
        payload=(("evidence_digest", cast(str, row[6])),),
        created_at=cast(datetime, row[7]).astimezone(timezone.utc).isoformat(),
    )
    replay = repository.append_artifact(artifact)
    conflict = repository.append_artifact(
        SecurityArtifact(
            **{
                **artifact.__dict__,
                "subject_digest": stable_hash("restart-changed-subject"),
            }
        )
    )
    if (
        replay.outcome is not SecurityRepositoryOutcome.EXACT_REPLAY
        or conflict.outcome is not SecurityRepositoryOutcome.IDENTITY_CONFLICT
    ):
        raise AssertionError("RESTART_REPLAY_OR_CONFLICT_RULE_FAILED")
    return replay.outcome.value, conflict.outcome.value


def _response_state(factory: ConnectionFactory) -> tuple[str, str]:
    old = _query_one(
        factory,
        """
        SELECT action FROM day105_l3.response_intents
        WHERE release_decision_id = 'release-Q3-pending-after-P2'
        """,
    )
    orphan_candidate = _query_one(
        factory,
        """
        SELECT payload ->> 'subject_digest'
        FROM day105_l3.security_artifacts
        WHERE artifact_id = 'candidate-Q2-G3-orphan'
          AND artifact_type = 'ANSWER_CANDIDATE'
        """,
    )
    if old != ("BLOCKED",) or orphan_candidate is None:
        raise AssertionError("RESTART_RESPONSE_STATE_UNSAFE")
    candidate_digest = cast(str, orphan_candidate[0])
    orphan_release = _query_one(
        factory,
        """
        SELECT
          (SELECT count(*) FROM day105_l3.security_artifacts
           WHERE artifact_type = 'OUTPUT_RELEASE_DECISION'
             AND payload ->> 'candidate_digest' = %s),
          (SELECT count(*) FROM day105_l3.response_intents
           WHERE candidate_digest = %s)
        """,
        (candidate_digest, candidate_digest),
    )
    if orphan_release != (0, 0):
        raise AssertionError("RESTART_ORPHAN_CANDIDATE_WAS_RELEASED")
    return cast(str, old[0]), "BLOCKED"


def _fresh_g3_query(
    lifecycle: PostgresIndexLifecycleRepository,
    factory: ConnectionFactory,
) -> tuple[list[str], bool]:
    now = datetime.now(timezone.utc)
    request_id = f"restart-G3-{uuid4().hex}"
    view_id = f"read-view:{request_id}"
    acquired = lifecycle.acquire_read_view(
        view_id=view_id,
        pointer_name=POINTER,
        expected_generation_id="G3",
        expected_pointer_revision=9,
        owner_id=request_id,
        authorization_snapshot_id="P2",
        acquired_at=now.isoformat(),
        lease_expires_at=(now + timedelta(minutes=10)).isoformat(),
    )
    if acquired.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("RESTART_G3_READ_VIEW_ACQUIRE_FAILED")
    try:
        exact = _query_read_view_ids(
            lifecycle,
            view_id=view_id,
            generation_id="G3",
            authorization_id="P2",
            query_vector=(0.0, 1.0, 0.0),
            top_k=1,
            mode=QueryMode.EXACT,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )
        hnsw = _query_read_view_ids(
            lifecycle,
            view_id=view_id,
            generation_id="G3",
            authorization_id="P2",
            query_vector=(0.0, 1.0, 0.0),
            top_k=1,
            mode=QueryMode.HNSW,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )
        if exact != ("C@v1",) or hnsw != ("C@v1",):
            raise AssertionError("RESTART_G3_QUERY_MISMATCH")
    finally:
        released_at = max(datetime.now(timezone.utc), now)
        released = lifecycle.release_read_view(
            view_id=view_id,
            expected_fencing_token=1,
            released_at=released_at.isoformat(),
        )
        if released.outcome is not RepositoryOutcome.APPLIED:
            raise AssertionError("RESTART_G3_READ_VIEW_RELEASE_FAILED")
    closed = _query_one(
        factory,
        "SELECT status FROM day104_l3.read_views WHERE view_id = %s",
        (view_id,),
    )
    return list(exact), closed == ("CLOSED",)


def _old_g2_query_and_drain(
    lifecycle: PostgresIndexLifecycleRepository,
    factory: ConnectionFactory,
) -> str:
    state = _query_one(
        factory,
        """
        SELECT generation.state, generation.state_version,
               generation.retire_after, view.status,
               view.acquired_at, view.lease_expires_at,
               view.authorization_snapshot_id,
               current.snapshot_id
        FROM day104_l3.generations AS generation
        JOIN day104_l3.read_views AS view
          ON view.generation_id = generation.generation_id
        JOIN day105_l3.current_security_snapshots AS current
          ON current.tenant_id = %s
        WHERE generation.generation_id = 'G2'
          AND view.view_id = 'read-view:request-Q3-pending-G2'
        """,
        (TENANT,),
    )
    if state is None:
        raise AssertionError("RESTART_OLD_G2_STATE_MISSING")
    if state[6] != "P1" or state[7] != "P2":
        raise AssertionError("RESTART_OLD_G2_AUTHORIZATION_BINDING_UNEXPECTED")
    if state[0] == "DRAINING" and state[3] == "OPEN":
        try:
            _query_read_view_ids(
                lifecycle,
                view_id="read-view:request-Q3-pending-G2",
                generation_id="G2",
                authorization_id="P1",
                query_vector=(
                    1.0 / math.sqrt(2.0),
                    1.0 / math.sqrt(2.0),
                    0.0,
                ),
                top_k=2,
                mode=QueryMode.EXACT,
                observed_at=datetime.now(timezone.utc).isoformat(),
            )
        except ReadViewQueryRejected as exc:
            if str(exc) != "CURRENT_AUTHORIZATION_CHANGED":
                raise
        else:
            raise AssertionError("RESTART_OLD_G2_QUERY_NOT_REJECTED")
        acquired_at = cast(datetime, state[4]).astimezone(timezone.utc)
        lease_expires_at = cast(datetime, state[5]).astimezone(timezone.utc)
        if lease_expires_at <= acquired_at:
            raise AssertionError("RESTART_OLD_G2_LEASE_WINDOW_INVALID")
        released_at = max(datetime.now(timezone.utc), acquired_at)
        released = lifecycle.release_read_view(
            view_id="read-view:request-Q3-pending-G2",
            expected_fencing_token=1,
            released_at=released_at.isoformat(),
        )
        if (
            released.outcome is not RepositoryOutcome.APPLIED
            or released.state_version is None
        ):
            raise AssertionError("RESTART_OLD_G2_RELEASE_FAILED")
        retire_after = cast(datetime, state[2])
        retired_at = max(
            datetime.now(timezone.utc),
            retire_after.astimezone(timezone.utc) + timedelta(seconds=1),
            released_at,
        )
        retired = lifecycle.retire_generation(
            generation_id="G2",
            expected_state_version=released.state_version,
            retired_at=retired_at.isoformat(),
        )
        if retired.outcome is not RepositoryOutcome.RETIRED:
            raise AssertionError("RESTART_G2_RETIREMENT_FAILED")
    elif state[0] != "RETIRED" or state[3] != "CLOSED":
        raise AssertionError("RESTART_G2_DRAIN_STATE_UNEXPECTED")
    return "REJECTED_CURRENT_AUTHORIZATION"


def run_restart_replay(database_url: str) -> dict[str, object]:
    if os.environ.get("DAY105_L3_INTEGRATION") != "1":
        raise RuntimeError("DAY105_L3_INTEGRATION_FLAG_REQUIRED")
    if not database_url.strip():
        raise ValueError("DAY105_L3_DATABASE_URL_REQUIRED")
    started = datetime.now(timezone.utc)
    factory = psycopg2_connection_factory(
        database_url,
        application_name="day105-l3-container-restart-replay",
    )
    lifecycle = PostgresIndexLifecycleRepository(factory)
    security = PostgresRagSecurityRepository(factory, integration_enabled=True)

    before_postmaster, after_postmaster, pre_restart_identity = _postmaster_times(
        factory
    )
    post_restart_identity = _durable_restart_state_identity(factory)
    if post_restart_identity != pre_restart_identity:
        raise AssertionError("PRE_AND_POST_RESTART_DURABLE_IDENTITY_MISMATCH")
    old_release, orphan_release = _response_state(factory)
    replay_result, conflict_result = _artifact_replay(security, factory)
    old_query = _old_g2_query_and_drain(lifecycle, factory)
    query_ids, fresh_closed = _fresh_g3_query(lifecycle, factory)
    identity_after = _durable_restart_state_identity(factory)
    if post_restart_identity != identity_after:
        raise AssertionError("RESTART_DURABLE_IDENTITY_CHANGED")
    completed = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "run_id": f"day105-l3-restart-{uuid4().hex}",
        "status": "PASS",
        "started_at": started.isoformat(),
        "completed_at": completed.isoformat(),
        "before_postmaster_started_at": before_postmaster.isoformat(),
        "after_postmaster_started_at": after_postmaster.isoformat(),
        "state_identity_digest_before": pre_restart_identity,
        "state_identity_digest_after": identity_after,
        "current_authorization_revision": "P2",
        "current_generation_id": "G3",
        "pointer_revision": 9,
        "new_query_occurrence_ids": query_ids,
        "old_g2_query_result": old_query,
        "old_candidate_release": old_release,
        "orphan_candidate_release": orphan_release,
        "exact_replay_result": replay_result,
        "changed_digest_result": conflict_result,
        "fresh_read_view_closed": fresh_closed,
        "raw_content_logged": False,
        "raw_vectors_logged": False,
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
        "raw_content_logged": False,
        "raw_vectors_logged": False,
        "database_url_logged": False,
    }
    if error_type is not None:
        payload["error_type"] = error_type
    payload["report_checksum"] = stable_hash(payload)
    return payload


def main() -> int:
    if os.environ.get("DAY105_L3_INTEGRATION") != "1":
        print(
            json.dumps(
                _fail_closed("DAY105_L3_INTEGRATION_FLAG_REQUIRED"),
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    database_url = os.environ.get("DAY105_L3_DATABASE_URL", "")
    if not database_url.strip():
        print(
            json.dumps(
                _fail_closed("DAY105_L3_DATABASE_URL_REQUIRED"),
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
                _fail_closed("DAY105_L3_RESTART_REPLAY_FAILED", type(exc).__name__),
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
