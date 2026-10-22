from __future__ import annotations

from dataclasses import replace
import threading
import unittest

from examples.day97_authorized_chunk_access import build_fixture
from rag_ingestion_contracts import DocumentIdentity
from rag_metadata_committer import (
    MetadataCommitOutcome,
    MetadataCommitter,
    MetadataRefreshOutcome,
)
from rag_metadata_contracts import (
    MetadataAssertion,
    MetadataContract,
    MetadataFieldDefinition,
    MetadataOrigin,
    MetadataProjectionAttempt,
    MetadataProjectionOperation,
    MetadataSensitivity,
    MetadataValueType,
)
from rag_metadata_projection import MetadataProjector
from rag_metadata_validator import (
    MetadataCandidateValidator,
    MetadataValidationOutcome,
)


class Day97MetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = build_fixture()
        current = self.fixture.provenance.evaluate(
            document=DocumentIdentity("tenant-a", "report-42")
        )
        assert current.binding is not None
        self.binding = current.binding
        self.committer = MetadataCommitter(
            store=self.fixture.metadata_store,
            provenance_validator=self.fixture.provenance,
        )
        self.projector = MetadataProjector()
        self.validator = MetadataCandidateValidator()

    def operation(
        self,
        *,
        operation_id: str = "op-metadata-v1",
        idempotency_key: str = "idem-metadata-v1",
        contract: MetadataContract | None = None,
        expected_snapshot_id: str | None = None,
        expected_snapshot_revision: int = 0,
    ) -> MetadataProjectionOperation:
        active_contract = contract or self.fixture.metadata_contract
        return MetadataProjectionOperation(
            self.binding.version,
            self.binding.chunk_set_id,
            operation_id,
            idempotency_key,
            active_contract.fingerprint,
            self.binding.selection_revision,
            self.binding.document_state_version,
            self.binding.document_fence,
            expected_snapshot_id,
            expected_snapshot_revision,
        )

    @staticmethod
    def assertions() -> tuple[MetadataAssertion, ...]:
        return (
            MetadataAssertion(
                "system.media_type",
                "text/markdown",
                MetadataOrigin.SYSTEM,
                "source:media-type",
            ),
            MetadataAssertion(
                "derived.character_count",
                137,
                MetadataOrigin.DERIVED,
                "parsed:length",
            ),
        )

    def decision(
        self,
        operation: MetadataProjectionOperation,
        attempt: MetadataProjectionAttempt,
        *,
        contract: MetadataContract | None = None,
        assertions: tuple[MetadataAssertion, ...] | None = None,
    ):
        active_contract = contract or self.fixture.metadata_contract
        candidate = self.projector.project(
            operation=operation,
            attempt=attempt,
            assertions=assertions or self.assertions(),
        )
        return self.validator.evaluate(
            contract=active_contract,
            candidate=candidate,
        )

    def test_source_declared_acl_is_rejected(self) -> None:
        operation = self.operation()
        attempt = MetadataProjectionAttempt(operation.operation_id, 1, "r1", 1)
        candidate = self.projector.project(
            operation=operation,
            attempt=attempt,
            assertions=(MetadataAssertion(
                "source.acl",
                "allow attacker",
                MetadataOrigin.SOURCE_DECLARED,
                "source:front-matter",
            ),),
        )
        decision = self.validator.evaluate(
            contract=self.fixture.metadata_contract,
            candidate=candidate,
        )
        self.assertEqual(
            decision.outcome,
            MetadataValidationOutcome.AUTHORITY_FIELD_REJECTED,
        )

    def test_unknown_namespace_and_wrong_type_are_rejected(self) -> None:
        operation = self.operation()
        attempt = MetadataProjectionAttempt(operation.operation_id, 1, "r1", 1)
        for assertion, expected in (
            (
                MetadataAssertion(
                    "unknown.field", "x", MetadataOrigin.SYSTEM, "system:x"
                ),
                MetadataValidationOutcome.UNKNOWN_FIELD,
            ),
            (
                MetadataAssertion(
                    "derived.character_count",
                    "137",
                    MetadataOrigin.DERIVED,
                    "parsed:length",
                ),
                MetadataValidationOutcome.TYPE_REJECTED,
            ),
        ):
            with self.subTest(expected=expected):
                candidate = self.projector.project(
                    operation=operation,
                    attempt=attempt,
                    assertions=(assertion,),
                )
                self.assertEqual(
                    self.validator.evaluate(
                        contract=self.fixture.metadata_contract,
                        candidate=candidate,
                    ).outcome,
                    expected,
                )

    def test_exact_duplicate_converges_without_second_snapshot(self) -> None:
        operation = self.operation()
        attempt = MetadataProjectionAttempt(operation.operation_id, 1, "r1", 1)
        self.assertIsNotNone(self.committer.claim(operation, attempt))
        decision = self.decision(operation, attempt)
        first = self.committer.persist(
            decision, contract=self.fixture.metadata_contract
        )
        repeated = self.committer.persist(
            decision, contract=self.fixture.metadata_contract
        )
        self.assertEqual(first.outcome, MetadataCommitOutcome.COMMITTED)
        self.assertEqual(
            repeated.outcome,
            MetadataCommitOutcome.ALREADY_COMMITTED,
        )
        self.assertEqual(first.snapshot, repeated.snapshot)
        self.assertEqual(len(self.fixture.metadata_store.outbox_intents()), 1)

    def test_same_operation_with_changed_contract_is_conflict(self) -> None:
        operation = self.operation()
        attempt = MetadataProjectionAttempt(operation.operation_id, 1, "r1", 1)
        self.assertIsNotNone(self.committer.claim(operation, attempt))
        changed = MetadataContract(
            "metadata.v2",
            self.fixture.metadata_contract.fields,
        )
        changed_operation = replace(
            operation,
            contract_fingerprint=changed.fingerprint,
        )
        self.assertIsNone(self.committer.claim(changed_operation, attempt))

    def test_contract_change_creates_new_snapshot_without_rechunking(self) -> None:
        first_operation = self.operation()
        first_attempt = MetadataProjectionAttempt(
            first_operation.operation_id, 1, "r1", 1
        )
        self.assertIsNotNone(self.committer.claim(first_operation, first_attempt))
        first = self.committer.persist(
            self.decision(first_operation, first_attempt),
            contract=self.fixture.metadata_contract,
        )
        assert first.snapshot is not None and first.pointer is not None
        before_set = self.fixture.chunks.read_chunk_set(self.binding.chunk_set_id)

        v2 = MetadataContract(
            "metadata.v2",
            self.fixture.metadata_contract.fields + (
                MetadataFieldDefinition(
                    "derived",
                    "reviewed",
                    MetadataValueType.BOOLEAN,
                    frozenset({MetadataOrigin.DERIVED}),
                    MetadataSensitivity.INTERNAL,
                ),
            ),
        )
        second_operation = self.operation(
            operation_id="op-metadata-v2",
            idempotency_key="idem-metadata-v2",
            contract=v2,
            expected_snapshot_id=first.snapshot.snapshot_id,
            expected_snapshot_revision=first.pointer.revision,
        )
        second_attempt = MetadataProjectionAttempt(
            second_operation.operation_id, 1, "r2", 1
        )
        self.assertIsNotNone(
            self.committer.claim(second_operation, second_attempt)
        )
        second_assertions = self.assertions() + (MetadataAssertion(
            "derived.reviewed",
            True,
            MetadataOrigin.DERIVED,
            "review:synthetic",
        ),)
        second = self.committer.persist(
            self.decision(
                second_operation,
                second_attempt,
                contract=v2,
                assertions=second_assertions,
            ),
            contract=v2,
        )
        self.assertEqual(second.outcome, MetadataCommitOutcome.COMMITTED)
        assert second.snapshot is not None
        self.assertNotEqual(first.snapshot.snapshot_id, second.snapshot.snapshot_id)
        self.assertIsNotNone(
            self.fixture.metadata_store.read_snapshot(first.snapshot.snapshot_id)
        )
        self.assertEqual(
            before_set,
            self.fixture.chunks.read_chunk_set(self.binding.chunk_set_id),
        )

    def test_concurrent_writers_converge_to_one_snapshot(self) -> None:
        operation = self.operation()
        attempt = MetadataProjectionAttempt(operation.operation_id, 1, "r1", 1)
        self.assertIsNotNone(self.committer.claim(operation, attempt))
        decision = self.decision(operation, attempt)
        outcomes = []
        output_lock = threading.Lock()

        def worker() -> None:
            result = self.committer.persist(
                decision,
                contract=self.fixture.metadata_contract,
            )
            with output_lock:
                outcomes.append(result.outcome)

        workers = [threading.Thread(target=worker) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertCountEqual(outcomes, (
            MetadataCommitOutcome.COMMITTED,
            MetadataCommitOutcome.ALREADY_COMMITTED,
        ))

    def test_duplicate_and_delayed_refresh_are_absorbed(self) -> None:
        first_operation = self.operation()
        first_attempt = MetadataProjectionAttempt(
            first_operation.operation_id, 1, "r1", 1
        )
        self.assertIsNotNone(self.committer.claim(first_operation, first_attempt))
        first = self.committer.persist(
            self.decision(first_operation, first_attempt),
            contract=self.fixture.metadata_contract,
        )
        assert first.snapshot is not None and first.pointer is not None
        first_event = self.fixture.metadata_store.outbox_intents()[0]

        v2 = MetadataContract(
            "metadata.v2", self.fixture.metadata_contract.fields
        )
        second_operation = self.operation(
            operation_id="op-metadata-v2",
            idempotency_key="idem-metadata-v2",
            contract=v2,
            expected_snapshot_id=first.snapshot.snapshot_id,
            expected_snapshot_revision=first.pointer.revision,
        )
        second_attempt = MetadataProjectionAttempt(
            second_operation.operation_id, 1, "r2", 1
        )
        self.assertIsNotNone(
            self.committer.claim(second_operation, second_attempt)
        )
        second = self.committer.persist(
            self.decision(second_operation, second_attempt, contract=v2),
            contract=v2,
        )
        self.assertEqual(second.outcome, MetadataCommitOutcome.COMMITTED)
        second_event = self.fixture.metadata_store.outbox_intents()[1]
        self.assertEqual(
            self.fixture.metadata_store.apply_refresh(first_event.event_id),
            MetadataRefreshOutcome.STALE,
        )
        self.assertEqual(
            self.fixture.metadata_store.apply_refresh(second_event.event_id),
            MetadataRefreshOutcome.APPLIED,
        )
        self.assertEqual(
            self.fixture.metadata_store.apply_refresh(second_event.event_id),
            MetadataRefreshOutcome.DUPLICATE,
        )


if __name__ == "__main__":
    unittest.main()
