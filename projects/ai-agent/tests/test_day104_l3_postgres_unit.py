"""Unit checks for the Day104 PostgreSQL/pgvector integration boundary.

These tests deliberately do not connect to Docker.  They lock down canonical
identity construction, validation and emitted SQL while the separate L3 suite
proves behavior against a real PostgreSQL + pgvector container.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone

from rag_chunking_contracts import stable_hash
from rag_index_lifecycle_contracts import (
    BuildSnapshot,
    DeletionEvidence,
    DeletionEvidenceScope,
    EvaluationRuler,
    EvidenceStatus,
    GenerationManifest,
    ImmutableBinding,
    ManifestFacts,
)
from rag_index_lifecycle_orchestrator import IndexedOccurrence, manifest_facts
from rag_index_lifecycle_postgres import (
    DeletionReceipt,
    OutboxClaim,
    PgVectorPoint,
    PostgresIndexLifecycleRepository,
    QueryMode,
    ReadViewQueryRejected,
    RepositoryOutcome,
    SourceDeletionCommand,
    SourceOccurrenceRecord,
    canonical_float32_values,
    canonical_vector_literal,
    manifest_from_point_rows,
    points_identity_digest,
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


def occurrence(occurrence_id: str, logical_id: str) -> SourceOccurrenceRecord:
    return SourceOccurrenceRecord(
        occurrence_id=occurrence_id,
        logical_id=logical_id,
        source_version="S1",
        content_digest=stable_hash(("content", occurrence_id)),
        metadata_digest=stable_hash(("metadata", occurrence_id)),
        provenance_digest=stable_hash(("provenance", occurrence_id)),
        tenant_id="tenant-refund",
    )


def deletion() -> DeletionReceipt:
    return DeletionReceipt(
        deletion_id="delete-B-v1",
        operation_id="delete-operation-B-v1",
        idempotency_key="delete-idempotency-B-v1",
        occurrence_id="B@v1",
        source_version="S1",
        intent_digest=stable_hash(("delete", "B@v1")),
        verification_policy_id="delete-policy-v1",
        required_evidence_scopes=(
            "LOGICAL_RELEASE",
            "SERVING_INDEX_ABSENCE",
        ),
        accepted_at="2026-11-11T09:00:00+08:00",
    )


def source_delete_command(
    *,
    operation_id: str = "receive-S1-D1",
    source_digest: str | None = None,
) -> SourceDeletionCommand:
    return SourceDeletionCommand(
        operation_id=operation_id,
        idempotency_key="receive-refund-S1-D1",
        scope_id="refund-rag",
        source_snapshot_id="S1",
        source_version="S1",
        source_digest=source_digest or stable_hash("S1"),
        occurrences=(
            occurrence("A@v1", "A"),
            occurrence("B@v1", "B"),
            occurrence("C@v1", "C"),
        ),
        deletion_snapshot_id="D1",
        deletion_digest=stable_hash(("D1", "B@v1")),
        deletion_ledger_revision=1,
        deletions=(deletion(),),
        received_at="2026-11-11T09:00:00+08:00",
    )


def point(
    point_id: str,
    occurrence_id: str,
    embedding: tuple[float, ...],
    *,
    generation_id: str = "G1",
) -> PgVectorPoint:
    return PgVectorPoint(
        point_id=point_id,
        generation_id=generation_id,
        occurrence_id=occurrence_id,
        tenant_id="tenant-refund",
        content_digest=stable_hash(("content", occurrence_id)),
        metadata_digest=stable_hash(("metadata", occurrence_id)),
        provenance_digest=stable_hash(("provenance", occurrence_id)),
        embedding=embedding,
        metadata=(("authorization_revision", "P1"),),
    )


def build_snapshot() -> BuildSnapshot:
    return BuildSnapshot(
        build_snapshot_id="BS1",
        scope_id="refund-rag",
        source_snapshot=ImmutableBinding("S1", stable_hash("S1")),
        authorization_snapshot=ImmutableBinding("P1", stable_hash("P1")),
        embedding_contract=ImmutableBinding("E1", stable_hash("E1")),
        index_schema=ImmutableBinding("IS1", stable_hash("IS1")),
        source_watermark="W1",
        deletion_snapshot=ImmutableBinding(
            "D1",
            stable_hash(("D1", "B@v1")),
        ),
    )


def evaluation_ruler() -> EvaluationRuler:
    return EvaluationRuler(
        stable_hash("dataset-L1"),
        stable_hash("evaluator-v1"),
        stable_hash("policy-v1"),
    )


def expected_manifest() -> ManifestFacts:
    def indexed(occurrence_id: str) -> IndexedOccurrence:
        return IndexedOccurrence(
            occurrence_id,
            stable_hash(("content", occurrence_id)),
            stable_hash(("metadata", occurrence_id)),
            stable_hash(("provenance", occurrence_id)),
        )

    return manifest_facts((indexed("A@v1"), indexed("C@v1")))


def deletion_evidence(
    evidence_id: str,
    scope: DeletionEvidenceScope,
    status: EvidenceStatus,
) -> DeletionEvidence:
    return DeletionEvidence(
        evidence_id=evidence_id,
        deletion_snapshot_id="D1",
        verification_policy_id="delete-policy-v1",
        validator_id="day104-deletion-validator",
        validator_version="v1",
        scope=scope,
        status=status,
        pointer_name="refund-active",
        pointer_revision=8,
        generation_ids=() if scope is DeletionEvidenceScope.PHYSICAL_PURGE else ("G2",),
        tombstoned_occurrence_ids=("B@v1",),
        readback_digest=stable_hash((scope.value, status.value)),
        observed_at="2026-11-11T09:30:00+08:00",
    )


def evidence_row(evidence: DeletionEvidence) -> tuple[object, ...]:
    return (
        evidence.evidence_id,
        evidence.deletion_snapshot_id,
        evidence.verification_policy_id,
        evidence.validator_id,
        evidence.validator_version,
        evidence.scope.value,
        evidence.status.value,
        evidence.pointer_name,
        evidence.pointer_revision,
        list(evidence.generation_ids),
        list(evidence.tombstoned_occurrence_ids),
        evidence.readback_digest,
        datetime(2026, 11, 11, 1, 30, tzinfo=timezone.utc),
    )


class CanonicalPgVectorTests(unittest.TestCase):
    def test_vector_literal_uses_frozen_float32_values(self) -> None:
        values = (0.1, 0.2, 0.3)
        literal = canonical_vector_literal(values)

        self.assertEqual(literal, canonical_vector_literal(values))
        self.assertEqual(len(canonical_float32_values(values)), 3)
        self.assertTrue(literal.startswith("["))
        self.assertTrue(literal.endswith("]"))

    def test_vector_validation_rejects_dimension_and_nonfinite_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "dimensions"):
            canonical_vector_literal((0.1, 0.2))
        with self.assertRaisesRegex(ValueError, "finite"):
            canonical_vector_literal((0.1, float("nan"), 0.3))

    def test_point_digest_is_order_independent_but_content_sensitive(self) -> None:
        first = point("point-A", "A@v1", (1.0, 0.0, 0.0))
        second = point("point-C", "C@v1", (0.0, 1.0, 0.0))

        left = points_identity_digest((first, second))
        right = points_identity_digest((second, first))
        changed = points_identity_digest(
            (first, point("point-C", "C@v1", (0.0, 0.0, 1.0)))
        )

        self.assertEqual(left, right)
        self.assertNotEqual(left, changed)

    def test_point_digest_rejects_duplicate_or_mixed_generation_identity(self) -> None:
        first = point("point-A", "A@v1", (1.0, 0.0, 0.0))
        duplicate = point("point-A", "C@v1", (0.0, 1.0, 0.0))
        other_generation = point(
            "point-C",
            "C@v1",
            (0.0, 1.0, 0.0),
            generation_id="G2",
        )

        with self.assertRaisesRegex(ValueError, "point IDs"):
            points_identity_digest((first, duplicate))
        with self.assertRaisesRegex(ValueError, "mix generations"):
            points_identity_digest((first, other_generation))

    def test_manifest_readback_sorts_exact_occurrences(self) -> None:
        rows = (
            (
                "C@v1",
                stable_hash("content-C"),
                stable_hash("metadata-C"),
                stable_hash("provenance-C"),
            ),
            (
                "A@v1",
                stable_hash("content-A"),
                stable_hash("metadata-A"),
                stable_hash("provenance-A"),
            ),
        )

        observed = manifest_from_point_rows(rows)
        replayed = manifest_from_point_rows(tuple(reversed(rows)))

        self.assertEqual(observed.occurrence_ids, ("A@v1", "C@v1"))
        self.assertEqual(observed.occurrence_count, 2)
        self.assertEqual(observed, replayed)


class SourceDeletionIdentityTests(unittest.TestCase):
    def test_identity_and_result_digests_are_stable(self) -> None:
        first = source_delete_command()
        replay = source_delete_command()
        changed = source_delete_command(source_digest=stable_hash("S2"))

        self.assertEqual(first.identity_digest, replay.identity_digest)
        self.assertEqual(first.result_digest, replay.result_digest)
        self.assertNotEqual(first.identity_digest, changed.identity_digest)
        self.assertNotEqual(first.result_digest, changed.result_digest)
        self.assertEqual(first.deletion_occurrence_ids, ("B@v1",))

    def test_command_rejects_unsorted_occurrences(self) -> None:
        original = source_delete_command()
        with self.assertRaisesRegex(ValueError, "canonically sorted"):
            SourceDeletionCommand(
                **{
                    **original.__dict__,
                    "occurrences": tuple(reversed(original.occurrences)),
                }
            )

    def test_command_rejects_tombstone_for_other_source_version(self) -> None:
        original = source_delete_command()
        wrong = DeletionReceipt(
            **{
                **deletion().__dict__,
                "source_version": "S2",
            }
        )
        with self.assertRaisesRegex(ValueError, "received version"):
            SourceDeletionCommand(
                **{
                    **original.__dict__,
                    "deletions": (wrong,),
                }
            )


class DeletionPersistenceTests(unittest.TestCase):
    def test_physical_purge_pass_is_rejected_without_false_claim(self) -> None:
        connection = FakeConnection()
        result = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).record_deletion_evidence(
            deletion_evidence(
                "physical-pass",
                DeletionEvidenceScope.PHYSICAL_PURGE,
                EvidenceStatus.PASS,
            )
        )

        self.assertEqual(result.outcome, RepositoryOutcome.INTEGRITY_FAILED)
        self.assertEqual(connection.fake_cursor.executions, [])

    def test_serving_absence_evidence_checks_authoritative_sets(self) -> None:
        evidence = deletion_evidence(
            "serving-absence",
            DeletionEvidenceScope.SERVING_INDEX_ABSENCE,
            EvidenceStatus.PASS,
        )
        cursor = FakeCursor()
        cursor.fetchone_values.extend(
            [
                ("refund-rag", ["B@v1"]),
                (8, "refund-rag"),
                None,
            ]
        )
        cursor.fetchall_values.extend(
            [
                [],
                [("B@v1",)],
                [("G2",)],
            ]
        )
        connection = FakeConnection(cursor)

        result = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).record_deletion_evidence(evidence)

        self.assertEqual(result.outcome, RepositoryOutcome.APPLIED)
        sql = "\n".join(query for query, _ in cursor.executions)
        self.assertIn("generation_id = ANY", sql)
        self.assertIn("INSERT INTO day104_l3.deletion_evidence", sql)

    def test_physical_purge_not_run_is_recorded_but_not_adopted(self) -> None:
        evidence = deletion_evidence(
            "physical-not-run",
            DeletionEvidenceScope.PHYSICAL_PURGE,
            EvidenceStatus.NOT_RUN,
        )
        cursor = FakeCursor()
        cursor.fetchone_values.extend(
            [
                ("refund-rag", ["B@v1"]),
                (8, "refund-rag"),
            ]
        )
        cursor.fetchall_values.extend(
            [
                [],
                [("B@v1",)],
                [("G2",)],
            ]
        )
        connection = FakeConnection(cursor)

        result = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).record_deletion_evidence(evidence)

        self.assertEqual(result.outcome, RepositoryOutcome.APPLIED)
        insert_params = cursor.executions[-1][1]
        assert isinstance(insert_params, tuple)
        self.assertEqual(insert_params[6], "NOT_RUN")
        self.assertEqual(insert_params[9], [])

    def test_dispatch_then_verify_uses_only_persisted_required_scopes(self) -> None:
        dispatch_cursor = FakeCursor()
        dispatch_cursor.fetchone_values.append(("ACCEPTED",))
        dispatch_connection = FakeConnection(dispatch_cursor)
        dispatched = PostgresIndexLifecycleRepository(
            lambda: dispatch_connection  # type: ignore[arg-type,return-value]
        ).mark_deletion_dispatched(deletion_id="delete-B")
        self.assertEqual(dispatched.outcome, RepositoryOutcome.DISPATCHED)

        logical = deletion_evidence(
            "logical-pass",
            DeletionEvidenceScope.LOGICAL_RELEASE,
            EvidenceStatus.PASS,
        )
        serving = deletion_evidence(
            "serving-pass",
            DeletionEvidenceScope.SERVING_INDEX_ABSENCE,
            EvidenceStatus.PASS,
        )
        verify_cursor = FakeCursor()
        verify_cursor.fetchone_values.extend(
            [
                (
                    "refund-rag",
                    "B@v1",
                    "delete-policy-v1",
                    ["LOGICAL_RELEASE", "SERVING_INDEX_ABSENCE"],
                    "DISPATCHED",
                    None,
                    [],
                    None,
                ),
                ("D1", 1),
            ]
        )
        verify_cursor.fetchall_values.append(
            [
                evidence_row(logical),
                evidence_row(serving),
            ]
        )
        verify_connection = FakeConnection(verify_cursor)

        verified = PostgresIndexLifecycleRepository(
            lambda: verify_connection  # type: ignore[arg-type,return-value]
        ).verify_deletion(deletion_id="delete-B")

        self.assertEqual(verified.outcome, RepositoryOutcome.VERIFIED)
        update_query, update_params = verify_cursor.executions[-1]
        self.assertIn("SET state = 'VERIFIED'", update_query)
        assert isinstance(update_params, tuple)
        self.assertEqual(
            update_params[1],
            ["logical-pass", "serving-pass"],
        )

        replay_cursor = FakeCursor()
        replay_cursor.fetchone_values.append(
            (
                "refund-rag",
                "B@v1",
                "delete-policy-v1",
                ["LOGICAL_RELEASE", "SERVING_INDEX_ABSENCE"],
                "VERIFIED",
                "D1",
                ["logical-pass", "serving-pass"],
                verified.identity_digest,
            )
        )
        replay_cursor.fetchall_values.append(
            [evidence_row(logical), evidence_row(serving)]
        )
        replay_connection = FakeConnection(replay_cursor)
        replayed = PostgresIndexLifecycleRepository(
            lambda: replay_connection  # type: ignore[arg-type,return-value]
        ).verify_deletion(deletion_id="delete-B")

        self.assertEqual(replayed.outcome, RepositoryOutcome.EXACT_REPLAY)

    def test_missing_required_scope_keeps_deletion_unverified(self) -> None:
        logical = deletion_evidence(
            "logical-pass",
            DeletionEvidenceScope.LOGICAL_RELEASE,
            EvidenceStatus.PASS,
        )
        cursor = FakeCursor()
        cursor.fetchone_values.extend(
            [
                (
                    "refund-rag",
                    "B@v1",
                    "delete-policy-v1",
                    ["LOGICAL_RELEASE", "SERVING_INDEX_ABSENCE"],
                    "DISPATCHED",
                    None,
                    [],
                    None,
                ),
                ("D1", 1),
            ]
        )
        cursor.fetchall_values.append([evidence_row(logical)])
        connection = FakeConnection(cursor)

        result = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).verify_deletion(deletion_id="delete-B")

        self.assertEqual(result.outcome, RepositoryOutcome.EVIDENCE_INCOMPLETE)
        self.assertNotIn(
            "SET state = 'VERIFIED'",
            "\n".join(query for query, _ in cursor.executions),
        )


class RepositoryBoundaryTests(unittest.TestCase):
    def repository(
        self,
        connection: FakeConnection,
        schema_path: Path,
    ) -> PostgresIndexLifecycleRepository:
        return PostgresIndexLifecycleRepository(
            lambda: connection,  # type: ignore[arg-type,return-value]
            schema_path=schema_path,
        )

    def test_schema_install_commits_and_closes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schema = Path(directory) / "schema.sql"
            schema.write_text("SELECT 1;", encoding="utf-8")
            connection = FakeConnection()

            self.repository(connection, schema).install_schema()

        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertTrue(connection.closed)
        self.assertTrue(connection.fake_cursor.closed)
        self.assertIn("SELECT 1", connection.fake_cursor.executions[0][0])

    def test_schema_install_rolls_back_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schema = Path(directory) / "schema.sql"
            schema.write_text("BROKEN DDL;", encoding="utf-8")
            cursor = FakeCursor()
            cursor.failure = RuntimeError("database rejected DDL")
            connection = FakeConnection(cursor)

            with self.assertRaisesRegex(RuntimeError, "rejected"):
                self.repository(connection, schema).install_schema()

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)

    def test_schema_reset_requires_explicit_narrow_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schema = Path(directory) / "schema.sql"
            schema.write_text("SELECT 1;", encoding="utf-8")
            connection = FakeConnection()
            repository = self.repository(connection, schema)

            with self.assertRaisesRegex(ValueError, "confirmation"):
                repository.reset_schema(confirmation="yes")

        self.assertEqual(connection.fake_cursor.executions, [])

    def test_schema_reset_rejects_any_other_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schema = Path(directory) / "schema.sql"
            schema.write_text("SELECT 1;", encoding="utf-8")
            cursor = FakeCursor()
            cursor.fetchone_values.append(("production",))
            connection = FakeConnection(cursor)

            with self.assertRaisesRegex(ValueError, "day104_l3 database"):
                self.repository(connection, schema).reset_schema(
                    confirmation="RESET_DAY104_L3_SCHEMA"
                )

        self.assertEqual(connection.rollbacks, 1)
        self.assertNotIn(
            "DROP SCHEMA",
            "\n".join(query for query, _ in cursor.executions),
        )

    def test_snapshot_replay_checks_the_persisted_fingerprint(self) -> None:
        snapshot = build_snapshot()
        cursor = FakeCursor()
        cursor.fetchone_values.extend(
            [
                (snapshot.build_snapshot_id, 1),
                (stable_hash("different-snapshot"),),
            ]
        )
        connection = FakeConnection(cursor)

        result = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).put_current_build_snapshot(
            snapshot=snapshot,
            expected_current_revision=1,
            created_at="2026-11-11T09:01:00+08:00",
        )

        self.assertEqual(result.outcome, RepositoryOutcome.IDENTITY_CONFLICT)

    def test_namespace_reuse_by_another_generation_is_not_exact_replay(self) -> None:
        snapshot = build_snapshot()
        manifest = expected_manifest()
        ruler = evaluation_ruler()
        cursor = FakeCursor()
        cursor.fetchall_values.append(
            [
                (
                    "G-old",
                    snapshot.scope_id,
                    snapshot.build_snapshot_id,
                    snapshot.fingerprint,
                    ruler.fingerprint,
                    manifest.fingerprint,
                    "refund_g1",
                    1,
                )
            ]
        )
        connection = FakeConnection(cursor)

        result = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).register_generation(
            generation_id="G1",
            snapshot=snapshot,
            ruler=ruler,
            expected_manifest=manifest,
            physical_namespace="refund_g1",
            provider_write_fence=1,
            created_at="2026-11-11T09:02:00+08:00",
        )

        self.assertEqual(result.outcome, RepositoryOutcome.IDENTITY_CONFLICT)

    def test_ready_replay_checks_every_release_evidence_digest(self) -> None:
        snapshot = build_snapshot()
        manifest = expected_manifest()
        ruler = evaluation_ruler()
        full_manifest = GenerationManifest(
            manifest,
            manifest,
            ("B@v1",),
        )
        cursor = FakeCursor()
        cursor.fetchone_values.append(
            (
                snapshot.scope_id,
                snapshot.build_snapshot_id,
                snapshot.fingerprint,
                ruler.fingerprint,
                manifest.fingerprint,
                manifest.fingerprint,
                full_manifest.digest,
                stable_hash("validation-G1"),
                stable_hash("evaluation-G1"),
                stable_hash("stored-report-G1"),
                "READY",
                3,
                2,
                stable_hash("checkpoint-G1"),
                datetime(2026, 11, 11, 1, 4, tzinfo=timezone.utc),
                snapshot.fingerprint,
            )
        )
        connection = FakeConnection(cursor)

        result = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).mark_ready(
            generation_id="G1",
            expected_state_version=2,
            expected_manifest=manifest,
            expected_absent_occurrence_ids=("B@v1",),
            ruler=ruler,
            validation_record_digest=stable_hash("validation-G1"),
            evaluation_evidence_digest=stable_hash("evaluation-G1"),
            evaluation_report_digest=stable_hash("changed-report-G1"),
            evaluation_decision="PASS",
            observed_at="2026-11-11T09:05:00+08:00",
        )

        self.assertEqual(result.outcome, RepositoryOutcome.IDENTITY_CONFLICT)

    def test_lease_issue_refuses_to_implicitly_rotate_existing_authority(self) -> None:
        cursor = FakeCursor()
        cursor.fetchone_values.append(("committer-old", 7))
        connection = FakeConnection(cursor)
        repository = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        )

        with self.assertRaisesRegex(ValueError, "CAS rotation"):
            repository.issue_activation_lease(
                pointer_name="refund-active",
                committer_id="committer-new",
                issued_at="2026-11-11T09:06:00+08:00",
                lease_expires_at="2026-11-11T09:16:00+08:00",
            )

    def test_activation_rechecks_target_against_current_snapshot(self) -> None:
        cursor = FakeCursor()
        cursor.fetchone_values.extend(
            [
                None,
                ("G1", 7, "refund-rag"),
                (
                    "committer-1",
                    5,
                    datetime(2026, 11, 11, 2, 0, tzinfo=timezone.utc),
                ),
                (stable_hash("BS-current"),),
            ]
        )
        cursor.fetchall_values.append(
            [
                ("G1", "ACTIVE", 4, stable_hash("BS-old"), "refund-rag"),
                ("G2", "READY", 3, stable_hash("BS-target"), "refund-rag"),
            ]
        )
        connection = FakeConnection(cursor)

        result = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).activate(
            activation_id="activate-G2",
            pointer_name="refund-active",
            target_generation_id="G2",
            expected_generation_id="G1",
            expected_revision=7,
            committer_id="committer-1",
            committer_fence=5,
            committed_at="2026-11-11T09:10:00+08:00",
            previous_retire_after="2026-11-11T09:20:00+08:00",
        )

        self.assertEqual(result.outcome, RepositoryOutcome.STALE_POINTER)
        self.assertNotIn(
            "SET state = 'ACTIVE'",
            "\n".join(query for query, _ in cursor.executions),
        )

    def test_empty_generation_write_is_a_valid_bound_result(self) -> None:
        cursor = FakeCursor()
        cursor.fetchone_values.append(("BUILDING", 1, None))
        cursor.fetchall_values.append([])
        connection = FakeConnection(cursor)

        result = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).write_generation_points(
            generation_id="G-empty",
            provider_write_fence=1,
            points=(),
            created_at="2026-11-11T09:03:00+08:00",
        )

        self.assertEqual(result.outcome, RepositoryOutcome.APPLIED)
        self.assertNotIn(
            "INSERT INTO day104_l3.index_points",
            "\n".join(query for query, _ in cursor.executions),
        )

    def test_exact_source_delete_replay_converges_without_new_writes(self) -> None:
        command = source_delete_command()
        cursor = FakeCursor()
        cursor.fetchall_values.append(
            [
                (
                    command.operation_id,
                    command.identity_digest,
                    command.result_digest,
                )
            ]
        )
        connection = FakeConnection(cursor)

        result = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).receive_source_and_deletion(command)

        self.assertEqual(result.outcome, RepositoryOutcome.EXACT_REPLAY)
        self.assertEqual(connection.commits, 1)
        sql = "\n".join(query for query, _ in cursor.executions)
        self.assertNotIn("INSERT INTO day104_l3.source_snapshots", sql)

    def test_changed_source_delete_replay_is_a_conflict(self) -> None:
        command = source_delete_command()
        cursor = FakeCursor()
        cursor.fetchall_values.append(
            [(command.operation_id, stable_hash("other"), stable_hash("other"))]
        )
        connection = FakeConnection(cursor)

        result = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).receive_source_and_deletion(command)

        self.assertEqual(result.outcome, RepositoryOutcome.IDENTITY_CONFLICT)

    def test_exact_query_emits_generation_and_tenant_bound_sql(self) -> None:
        cursor = FakeCursor()
        cursor.fetchall_values.append([("point-A", "A@v1", "G2", 0.125)])
        connection = FakeConnection(cursor)
        repository = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        )

        hits = repository.query_generation(
            generation_id="G2",
            tenant_id="tenant-refund",
            query_vector=(1.0, 0.0, 0.0),
            top_k=3,
            mode=QueryMode.EXACT,
        )

        self.assertEqual(tuple(hit.occurrence_id for hit in hits), ("A@v1",))
        self.assertAlmostEqual(hits[0].similarity, 0.875)
        sql = "\n".join(query for query, _ in cursor.executions)
        self.assertIn("enable_indexscan = off", sql)
        self.assertIn("point.generation_id = %s", sql)
        self.assertIn("point.tenant_id = %s", sql)

    def test_hnsw_query_binds_ef_search_and_disables_seqscan(self) -> None:
        cursor = FakeCursor()
        cursor.fetchall_values.append([])
        connection = FakeConnection(cursor)
        repository = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        )

        self.assertEqual(
            repository.query_generation(
                generation_id="G2",
                tenant_id="tenant-refund",
                query_vector=(1.0, 0.0, 0.0),
                top_k=3,
                mode=QueryMode.HNSW,
                ef_search=64,
            ),
            (),
        )

        self.assertEqual(cursor.executions[0][1], ("64",))
        self.assertIn("enable_seqscan = off", cursor.executions[1][0])

    def test_read_view_query_requires_current_authorization_and_open_fence(
        self,
    ) -> None:
        snapshot = build_snapshot()
        cursor = FakeCursor()
        cursor.fetchone_values.append(
            (
                "G2",
                "OPEN",
                9,
                datetime(2026, 11, 11, 2, 0, tzinfo=timezone.utc),
                "P1",
                snapshot.fingerprint,
                "ACTIVE",
                snapshot.fingerprint,
                "P1",
            )
        )
        cursor.fetchall_values.append([("point-A", "A@v1", "G2", 0.0)])
        connection = FakeConnection(cursor)

        hits = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).query_read_view(
            view_id="view-1",
            expected_fencing_token=9,
            expected_generation_id="G2",
            expected_authorization_snapshot_id="P1",
            tenant_id="tenant-refund",
            query_vector=(1.0, 0.0, 0.0),
            top_k=3,
            mode=QueryMode.EXACT,
            observed_at="2026-11-11T09:30:00+08:00",
        )

        self.assertEqual(tuple(hit.generation_id for hit in hits), ("G2",))
        sql = "\n".join(query for query, _ in cursor.executions)
        self.assertIn("FOR UPDATE OF read_view, generation, selected", sql)

    def test_read_view_query_rejects_changed_current_authorization(self) -> None:
        snapshot = build_snapshot()
        cursor = FakeCursor()
        cursor.fetchone_values.append(
            (
                "G2",
                "OPEN",
                9,
                datetime(2026, 11, 11, 2, 0, tzinfo=timezone.utc),
                "P1",
                snapshot.fingerprint,
                "DRAINING",
                snapshot.fingerprint,
                "P2",
            )
        )
        connection = FakeConnection(cursor)

        with self.assertRaisesRegex(
            ReadViewQueryRejected,
            "CURRENT_AUTHORIZATION_CHANGED",
        ):
            PostgresIndexLifecycleRepository(
                lambda: connection  # type: ignore[arg-type,return-value]
            ).query_read_view(
                view_id="view-1",
                expected_fencing_token=9,
                expected_generation_id="G2",
                expected_authorization_snapshot_id="P1",
                tenant_id="tenant-refund",
                query_vector=(1.0, 0.0, 0.0),
                top_k=3,
                mode=QueryMode.EXACT,
                observed_at="2026-11-11T09:30:00+08:00",
            )

    def test_outbox_claim_records_time_and_apply_writes_inbox(self) -> None:
        claim_cursor = FakeCursor()
        claim_cursor.fetchone_values.append(
            ("event-1", "INDEX_POINTER_CHANGED", "refund-active", 8, "digest", None)
        )
        claim_connection = FakeConnection(claim_cursor)
        claim = PostgresIndexLifecycleRepository(
            lambda: claim_connection  # type: ignore[arg-type,return-value]
        ).claim_outbox(
            worker_id="relay-1",
            claimed_at="2026-11-11T09:10:00+08:00",
        )
        assert claim is not None
        self.assertEqual(claim.claimed_at, "2026-11-11T09:10:00+08:00")
        self.assertIn(
            "claimed_at = %s",
            "\n".join(query for query, _ in claim_cursor.executions),
        )

        apply_cursor = FakeCursor()
        apply_cursor.fetchone_values.extend(
            [
                ("digest", "PROCESSING", "relay-1", 1),
                None,
            ]
        )
        apply_connection = FakeConnection(apply_cursor)
        result = PostgresIndexLifecycleRepository(
            lambda: apply_connection  # type: ignore[arg-type,return-value]
        ).apply_outbox(
            claim=claim,
            payload_digest="digest",
            source_stream="day104-outbox",
            result_id="projection-1",
            result_digest=stable_hash("projection-1"),
            applied_at="2026-11-11T09:11:00+08:00",
        )

        self.assertEqual(result.outcome, RepositoryOutcome.APPLIED)
        self.assertIn(
            "INSERT INTO day104_l3.inbox_records",
            "\n".join(query for query, _ in apply_cursor.executions),
        )

    def test_stale_outbox_claim_is_reclaimed_with_next_fence(self) -> None:
        cursor = FakeCursor()
        cursor.fetchone_values.append(
            ("event-1", "INDEX_POINTER_CHANGED", "refund-active", 8, "digest", 3)
        )
        connection = FakeConnection(cursor)

        claim = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).reclaim_stale_outbox(
            worker_id="relay-2",
            reclaimed_at="2026-11-11T09:20:00+08:00",
            processing_timeout_seconds=60,
        )

        assert claim is not None
        self.assertEqual(claim.claim_fence, 4)
        self.assertEqual(claim.claim_owner, "relay-2")

    def test_expired_read_view_reaper_decrements_reader_once(self) -> None:
        cursor = FakeCursor()
        cursor.fetchall_values.append([("view-expired", "G1", 5)])
        cursor.fetchone_values.append((11, 1))
        connection = FakeConnection(cursor)

        reaped = PostgresIndexLifecycleRepository(
            lambda: connection  # type: ignore[arg-type,return-value]
        ).reap_expired_read_views(
            observed_at="2026-11-11T09:30:00+08:00",
        )

        self.assertEqual(reaped, ("view-expired",))
        sql = "\n".join(query for query, _ in cursor.executions)
        self.assertIn("status = 'EXPIRED'", sql)
        self.assertIn("active_readers = active_readers - 1", sql)


if __name__ == "__main__":
    unittest.main()
