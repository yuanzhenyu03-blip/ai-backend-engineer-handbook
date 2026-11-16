"""Unit checks for the Day105 PostgreSQL security repository boundary.

These tests use recording connections only.  The opt-in integration suite is
responsible for proving PostgreSQL constraints, locks and transaction behavior
against the pinned Docker fixture.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import cast
import unittest

from rag_chunking_contracts import stable_hash
from rag_security_contracts import (
    EgressSink,
    IncidentState,
    OutputReleaseDecision,
    SecurityDisposition,
    SecurityIncidentRecord,
    SecurityResult,
)
from rag_security_postgres import (
    PostgresRagSecurityRepository,
    SecurityArtifact,
    SecurityArtifactType,
    SecurityRepositoryOutcome,
    SecuritySnapshot,
)


class FakeCursor:
    def __init__(self) -> None:
        self.executions: list[tuple[str, object]] = []
        self.fetchone_values: list[object] = []
        self.fetchall_values: list[list[object]] = []
        self.rowcount = 1
        self.closed = False
        self.failure: Exception | None = None

    def execute(self, query: str, params: object = None) -> object:
        self.executions.append((query, params))
        if self.failure is not None:
            raise self.failure
        return None

    def fetchone(self) -> object:
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def fetchall(self) -> list[object]:
        return self.fetchall_values.pop(0) if self.fetchall_values else []

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, cursor: FakeCursor | None = None) -> None:
        self.fake_cursor = cursor or FakeCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def snapshot(
    *,
    snapshot_id: str = "SEC-P1",
    revision: int = 1,
    authorization_id: str = "P1",
    occurrences: tuple[str, ...] = ("A@v1", "C@v1"),
) -> SecuritySnapshot:
    return SecuritySnapshot(
        snapshot_id=snapshot_id,
        tenant_id="tenant-refund",
        revision=revision,
        authorization_snapshot_id=authorization_id,
        authorization_snapshot_digest=stable_hash(authorization_id),
        provenance_revision="PR7",
        provenance_digest=stable_hash("PR7"),
        tombstone_revision="D1",
        tombstone_digest=stable_hash(("D1", "B@v1")),
        content_security_policy_version="CSP1",
        content_security_digest=stable_hash(("CSP1", occurrences)),
        security_policy_version="SP2",
        security_policy_digest=stable_hash("SP2"),
        occurrence_ids=occurrences,
        evidence_digests=(stable_hash(("security-evidence", revision)),),
        created_at=f"2026-11-16T0{revision}:00:00+00:00",
    )


def artifact(
    *,
    artifact_id: str = "request-binding-1",
    artifact_type: SecurityArtifactType = SecurityArtifactType.REQUEST_BINDING,
    subject_digest: str | None = None,
    parent_digests: tuple[str, ...] = (),
    request_id: str | None = "request-1",
) -> SecurityArtifact:
    return SecurityArtifact(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        request_id=request_id,
        subject_digest=subject_digest or stable_hash(("subject", artifact_id)),
        parent_digests=parent_digests,
        result=SecurityResult.PASS,
        disposition=SecurityDisposition.ELIGIBLE,
        payload=(("request_binding_fingerprint", stable_hash("binding-1")),),
        created_at="2026-11-16T01:00:00+00:00",
    )


def release_decision(
    *,
    result: SecurityResult = SecurityResult.PASS,
    disposition: SecurityDisposition = SecurityDisposition.RELEASE,
) -> OutputReleaseDecision:
    return OutputReleaseDecision(
        decision_id="release-decision-1",
        request_binding_fingerprint=stable_hash("binding-1"),
        candidate_digest=stable_hash("candidate-1"),
        disclosure_envelope_digest=stable_hash("disclosure-1"),
        release_evidence_digest=stable_hash("release-evidence-1"),
        result=result,
        disposition=disposition,
        reason_codes=() if result is SecurityResult.PASS else ("DLP_FAILED",),
        released_citation_occurrence_ids=("A@v1",)
        if disposition is SecurityDisposition.RELEASE
        else (),
        observed_at="2026-11-16T01:10:00+00:00",
    )


def incident(
    record_id: str,
    *,
    previous_record_id: str | None = None,
) -> SecurityIncidentRecord:
    return SecurityIncidentRecord(
        incident_record_id=record_id,
        incident_id="incident-1",
        previous_record_id=previous_record_id,
        state=IncidentState.CONTAINED,
        affected_request_ids=("request-1",),
        affected_generation_ids=("G2",),
        affected_occurrence_ids=("A@v1",),
        affected_sinks=(EgressSink.RESPONSE,),
        containment_actions=("BLOCK_RELEASE",),
        evidence_digests=(stable_hash(("incident-evidence", record_id)),),
        credential_rotation_status="ROTATED",
        impact_analysis_digest=stable_hash(("impact", record_id)),
        actor_id="incident-control-plane",
        observed_at="2026-11-16T01:20:00+00:00",
    )


def repository(
    connection: FakeConnection,
    *,
    enabled: bool = True,
    schema_path: Path | None = None,
) -> PostgresRagSecurityRepository:
    return PostgresRagSecurityRepository(
        lambda: connection,  # type: ignore[arg-type,return-value]
        integration_enabled=enabled,
        schema_path=schema_path,
    )


class Day105SecurityValueTests(unittest.TestCase):
    def test_snapshot_digest_binds_every_currentness_identity(self) -> None:
        first = snapshot()
        changed = snapshot(authorization_id="P2")

        self.assertNotEqual(first.identity_digest, changed.identity_digest)
        self.assertEqual(first.occurrence_ids, ("A@v1", "C@v1"))

    def test_snapshot_requires_canonical_occurrences_and_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "sorted and unique"):
            snapshot(occurrences=("C@v1", "A@v1"))
        with self.assertRaisesRegex(ValueError, "revision"):
            snapshot(revision=0)

    def test_artifact_rejects_raw_prompt_and_database_url(self) -> None:
        for unsafe_key in ("raw_prompt", "database_url"):
            with self.subTest(unsafe_key=unsafe_key):
                with self.assertRaisesRegex(ValueError, "forbids"):
                    SecurityArtifact(
                        artifact_id="unsafe",
                        artifact_type=SecurityArtifactType.ANSWER_CANDIDATE,
                        request_id="request-1",
                        subject_digest=stable_hash("candidate"),
                        parent_digests=(),
                        result=SecurityResult.FAIL,
                        disposition=SecurityDisposition.BLOCKED,
                        payload=((unsafe_key, "must-not-persist"),),
                        created_at="2026-11-16T01:00:00+00:00",
                    )

    def test_artifact_wrapper_binds_contract_subject_digest(self) -> None:
        left = artifact(subject_digest=stable_hash("candidate-left"))
        right = artifact(subject_digest=stable_hash("candidate-right"))

        self.assertNotEqual(left.identity_digest, right.identity_digest)
        self.assertIn(("subject_digest", left.subject_digest), left.storage_payload)


class Day105RepositoryBoundaryTests(unittest.TestCase):
    def test_integration_flag_fails_closed_before_opening_connection(self) -> None:
        calls = 0

        def connect() -> FakeConnection:
            nonlocal calls
            calls += 1
            return FakeConnection()

        with tempfile.TemporaryDirectory() as directory:
            schema = Path(directory) / "schema.sql"
            schema.write_text("SELECT 1;", encoding="utf-8")
            repo = PostgresRagSecurityRepository(
                connect,  # type: ignore[arg-type]
                schema_path=schema,
                integration_enabled=False,
            )
            with self.assertRaisesRegex(RuntimeError, "DAY105_L3_INTEGRATION"):
                repo.install_schema()

        self.assertEqual(calls, 0)

    def test_install_schema_commits_and_closes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schema = Path(directory) / "schema.sql"
            schema.write_text("SELECT 1;", encoding="utf-8")
            connection = FakeConnection()

            repository(connection, schema_path=schema).install_schema()

        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertTrue(connection.closed)
        self.assertTrue(connection.fake_cursor.closed)

    def test_reset_requires_exact_confirmation_and_lab_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schema = Path(directory) / "schema.sql"
            schema.write_text("SELECT 1;", encoding="utf-8")
            connection = FakeConnection()
            with self.assertRaisesRegex(ValueError, "confirmation"):
                repository(connection, schema_path=schema).reset_lab_schemas(
                    confirmation="yes"
                )
            self.assertEqual(connection.fake_cursor.executions, [])

            cursor = FakeCursor()
            cursor.fetchone_values.append(("production",))
            connection = FakeConnection(cursor)
            with self.assertRaisesRegex(ValueError, "day105_l3 database"):
                repository(connection, schema_path=schema).reset_lab_schemas(
                    confirmation="RESET_DAY105_L3_SCHEMAS"
                )
            self.assertEqual(connection.rollbacks, 1)
            self.assertNotIn(
                "reset_day105_l3_schemas",
                "\n".join(query for query, _ in cursor.executions),
            )

    def test_reset_invokes_database_guard_before_reinstall(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schema = Path(directory) / "schema.sql"
            schema.write_text("SELECT 1;", encoding="utf-8")
            cursor = FakeCursor()
            cursor.fetchone_values.append(("day105_l3",))
            connection = FakeConnection(cursor)

            repository(connection, schema_path=schema).reset_lab_schemas(
                confirmation="RESET_DAY105_L3_SCHEMAS"
            )

        sql = "\n".join(query for query, _ in cursor.executions)
        self.assertIn("public.reset_day105_l3_schemas", sql)
        self.assertEqual(cursor.executions[1][1], ("1", "RESET_DAY105_L3_SCHEMAS"))

    def test_append_snapshot_applies_and_exact_replay_converges(self) -> None:
        value = snapshot()
        apply_cursor = FakeCursor()
        apply_cursor.fetchall_values.append([])
        applied = repository(FakeConnection(apply_cursor)).append_security_snapshot(
            value
        )
        self.assertEqual(applied.outcome, SecurityRepositoryOutcome.APPLIED)
        self.assertIn(
            "authorization_snapshot_digest",
            "\n".join(query for query, _ in apply_cursor.executions),
        )
        insert_query, insert_params = next(
            (query, params)
            for query, params in apply_cursor.executions
            if "INSERT INTO day105_l3.security_snapshots" in query
        )
        self.assertIsInstance(insert_params, tuple)
        self.assertEqual(
            insert_query.count("%s"),
            len(cast(tuple[object, ...], insert_params)),
        )

        replay_cursor = FakeCursor()
        replay_cursor.fetchall_values.append(
            [(value.snapshot_id, value.identity_digest)]
        )
        replayed = repository(FakeConnection(replay_cursor)).append_security_snapshot(
            value
        )
        self.assertEqual(replayed.outcome, SecurityRepositoryOutcome.EXACT_REPLAY)

    def test_append_snapshot_rejects_id_or_revision_conflict(self) -> None:
        value = snapshot()
        cursor = FakeCursor()
        cursor.fetchall_values.append([(value.snapshot_id, stable_hash("different"))])

        result = repository(FakeConnection(cursor)).append_security_snapshot(value)

        self.assertEqual(result.outcome, SecurityRepositoryOutcome.IDENTITY_CONFLICT)
        self.assertNotIn(
            "INSERT INTO day105_l3.security_snapshots",
            "\n".join(query for query, _ in cursor.executions),
        )

    def test_snapshot_pointer_cas_commits_snapshot_transition_and_pointer(self) -> None:
        value = snapshot()
        cursor = FakeCursor()
        cursor.fetchone_values.extend([None, None])
        cursor.fetchall_values.append([])
        connection = FakeConnection(cursor)

        result = repository(connection).advance_current_security_snapshot(
            value,
            expected_revision=0,
        )

        self.assertEqual(result.outcome, SecurityRepositoryOutcome.APPLIED)
        self.assertEqual(connection.commits, 1)
        sql = "\n".join(query for query, _ in cursor.executions)
        self.assertIn("INSERT INTO day105_l3.security_snapshots", sql)
        self.assertIn("SECURITY_SNAPSHOT_TRANSITION", str(cursor.executions))
        self.assertIn("INSERT INTO day105_l3.current_security_snapshots", sql)

    def test_snapshot_pointer_cas_rejects_stale_revision_without_writes(self) -> None:
        cursor = FakeCursor()
        cursor.fetchone_values.append(("SEC-P4", 4, stable_hash("SEC-P4")))

        result = repository(FakeConnection(cursor)).advance_current_security_snapshot(
            snapshot(),
            expected_revision=0,
        )

        self.assertEqual(result.outcome, SecurityRepositoryOutcome.STALE_REVISION)
        self.assertNotIn("INSERT INTO", "\n".join(q for q, _ in cursor.executions))

    def test_artifact_exact_replay_and_identity_conflict_are_distinct(self) -> None:
        value = artifact()
        for stored, expected in (
            (value.identity_digest, SecurityRepositoryOutcome.EXACT_REPLAY),
            (stable_hash("other"), SecurityRepositoryOutcome.IDENTITY_CONFLICT),
        ):
            with self.subTest(expected=expected):
                cursor = FakeCursor()
                cursor.fetchone_values.append((value.artifact_id, stored))
                result = repository(FakeConnection(cursor)).append_artifact(value)
                self.assertEqual(result.outcome, expected)

    def test_child_artifact_accepts_subject_digest_parent_binding(self) -> None:
        parent_subject = stable_hash("candidate-contract")
        child = artifact(
            artifact_id="release-evidence-1",
            artifact_type=SecurityArtifactType.RELEASE_EVIDENCE,
            parent_digests=(parent_subject,),
        )
        cursor = FakeCursor()
        cursor.fetchone_values.append(None)
        cursor.fetchall_values.append([(stable_hash("parent-wrapper"), parent_subject)])

        result = repository(FakeConnection(cursor)).append_artifact(child)

        self.assertEqual(result.outcome, SecurityRepositoryOutcome.APPLIED)
        self.assertIn("subject_digest", "\n".join(q for q, _ in cursor.executions))

    def test_child_artifact_fails_closed_when_parent_is_missing(self) -> None:
        child = artifact(parent_digests=(stable_hash("missing-parent"),))
        cursor = FakeCursor()
        cursor.fetchone_values.append(None)
        cursor.fetchall_values.append([])

        result = repository(FakeConnection(cursor)).append_artifact(child)

        self.assertEqual(result.outcome, SecurityRepositoryOutcome.NOT_FOUND)
        self.assertNotIn(
            "INSERT INTO day105_l3.security_artifacts",
            "\n".join(query for query, _ in cursor.executions),
        )

    def test_output_decision_and_release_intent_commit_atomically(self) -> None:
        decision = release_decision()
        cursor = FakeCursor()
        cursor.fetchone_values.append(None)
        cursor.fetchall_values.extend(
            [
                [],
                [
                    (stable_hash("wrapper-1"), decision.candidate_digest),
                    (
                        stable_hash("wrapper-2"),
                        decision.disclosure_envelope_digest,
                    ),
                    (stable_hash("wrapper-3"), decision.release_evidence_digest),
                ],
            ]
        )
        connection = FakeConnection(cursor)

        result = repository(connection).append_output_decision_and_intent(
            decision,
            request_id="request-1",
            intent_id="response-intent-1",
            destination_digest=stable_hash("response-channel"),
        )

        self.assertEqual(result.outcome, SecurityRepositoryOutcome.APPLIED)
        sql = "\n".join(query for query, _ in cursor.executions)
        self.assertIn("INSERT INTO day105_l3.security_artifacts", sql)
        self.assertIn("INSERT INTO day105_l3.response_intents", sql)
        self.assertIn("RELEASE", str(cursor.executions))
        self.assertEqual(connection.commits, 1)

    def test_output_fault_rolls_back_decision_and_intent_together(self) -> None:
        decision = release_decision()
        cursor = FakeCursor()
        cursor.fetchone_values.append(None)
        cursor.fetchall_values.extend(
            [
                [],
                [
                    (stable_hash("wrapper-1"), decision.candidate_digest),
                    (
                        stable_hash("wrapper-2"),
                        decision.disclosure_envelope_digest,
                    ),
                    (stable_hash("wrapper-3"), decision.release_evidence_digest),
                ],
            ]
        )
        connection = FakeConnection(cursor)

        with self.assertRaisesRegex(RuntimeError, "INJECTED"):
            repository(connection).append_output_decision_and_intent(
                decision,
                request_id="request-1",
                intent_id="response-intent-1",
                destination_digest=stable_hash("response-channel"),
                inject_failure_after_decision=True,
            )

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertNotIn(
            "INSERT INTO day105_l3.response_intents",
            "\n".join(query for query, _ in cursor.executions),
        )

    def test_blocked_decision_can_only_create_blocked_intent(self) -> None:
        decision = release_decision(
            result=SecurityResult.FAIL,
            disposition=SecurityDisposition.BLOCKED,
        )
        cursor = FakeCursor()
        cursor.fetchone_values.append(None)
        cursor.fetchall_values.extend(
            [
                [],
                [
                    (stable_hash("wrapper-1"), decision.candidate_digest),
                    (
                        stable_hash("wrapper-2"),
                        decision.disclosure_envelope_digest,
                    ),
                    (stable_hash("wrapper-3"), decision.release_evidence_digest),
                ],
            ]
        )

        result = repository(FakeConnection(cursor)).append_output_decision_and_intent(
            decision,
            request_id="request-1",
            intent_id="response-intent-blocked",
            destination_digest=stable_hash("response-channel"),
        )

        self.assertEqual(result.outcome, SecurityRepositoryOutcome.APPLIED)
        intent_parameters = next(
            params
            for query, params in cursor.executions
            if "INSERT INTO day105_l3.response_intents" in query
        )
        assert isinstance(intent_parameters, tuple)
        self.assertEqual(intent_parameters[6], "BLOCKED")

    def test_incident_chain_rejects_branch_and_supports_exact_replay(self) -> None:
        root = incident("incident-record-1")
        replay_cursor = FakeCursor()
        replay_cursor.fetchone_values.append((root.incident_record_id, root.digest))
        replay = repository(FakeConnection(replay_cursor)).append_incident_record(root)
        self.assertEqual(replay.outcome, SecurityRepositoryOutcome.EXACT_REPLAY)

        branch = incident(
            "incident-record-branch",
            previous_record_id="incident-record-1",
        )
        branch_cursor = FakeCursor()
        branch_cursor.fetchone_values.append(None)
        branch_cursor.fetchall_values.append(
            [
                ("incident-record-1", None),
                ("incident-record-2", "incident-record-1"),
            ]
        )
        rejected = repository(FakeConnection(branch_cursor)).append_incident_record(
            branch
        )
        self.assertEqual(
            rejected.outcome,
            SecurityRepositoryOutcome.IDENTITY_CONFLICT,
        )

    def test_request_and_incident_readback_return_content_safe_identities(self) -> None:
        now = datetime(2026, 11, 16, 1, 30, tzinfo=timezone.utc)
        request_cursor = FakeCursor()
        request_cursor.fetchall_values.append(
            [
                (
                    "candidate-1",
                    "ANSWER_CANDIDATE",
                    "request-1",
                    stable_hash("wrapper"),
                    stable_hash("subject"),
                    [stable_hash("parent")],
                    "PASS",
                    "ELIGIBLE",
                    now,
                )
            ]
        )
        request_rows = repository(FakeConnection(request_cursor)).read_request_chain(
            "request-1"
        )
        self.assertEqual(request_rows[0].subject_digest, stable_hash("subject"))

        incident_cursor = FakeCursor()
        incident_cursor.fetchall_values.append(
            [
                (
                    "incident-record-1",
                    "incident-1",
                    None,
                    stable_hash("incident"),
                    "CONTAINED",
                    stable_hash("scope"),
                    now,
                )
            ]
        )
        incident_rows = repository(
            FakeConnection(incident_cursor)
        ).read_incident_history("incident-1")
        self.assertEqual(incident_rows[0].previous_record_id, None)
        self.assertEqual(incident_rows[0].created_at, "2026-11-16T01:30:00Z")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
