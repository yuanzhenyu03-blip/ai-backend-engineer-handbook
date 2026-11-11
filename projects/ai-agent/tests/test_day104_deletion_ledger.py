from __future__ import annotations

from dataclasses import replace
import unittest

from rag_index_deletion_ledger import (
    DEFAULT_TRUSTED_DELETION_VALIDATORS,
    DeletionLedgerCommitter,
    DeletionOutcome,
    DeletionResult,
    InboxOutcome,
    InMemoryDeletionLedger,
)
from rag_index_lifecycle_contracts import (
    BuildSnapshot,
    DeletionEvidence,
    DeletionEvidenceScope,
    DeletionIntent,
    DeletionSnapshot,
    DeletionState,
    EvidenceStatus,
    ImmutableBinding,
    MessageState,
)


POLICY_ID = "deletion-verification-policy-v1"
VALIDATOR_ID = "day104-deletion-validator"
VALIDATOR_VERSION = "v1"
ALL_EVIDENCE_SCOPES = tuple(
    sorted(
        DeletionEvidenceScope,
        key=lambda scope: scope.value,
    )
)


class Day104DeletionLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryDeletionLedger()
        self.committer = DeletionLedgerCommitter(self.store)
        self.intent = self._intent()

    @staticmethod
    def _intent(
        *,
        deletion_id: str = "delete-refund-B-v1",
        operation_id: str = "op-delete-refund-B-v1",
        idempotency_key: str = "idem-delete-refund-B-v1",
        occurrence_id: str = "B@v1",
        source_version: str = "B@v1",
        intent_digest: str = "sha256:delete-refund-B-v1",
        verification_policy_id: str = POLICY_ID,
        required_evidence_scopes: tuple[DeletionEvidenceScope, ...] = (
            ALL_EVIDENCE_SCOPES
        ),
        accepted_at: str = "2026-11-11T00:00:00Z",
    ) -> DeletionIntent:
        return DeletionIntent(
            deletion_id=deletion_id,
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            scope_id="refund-rag",
            occurrence_id=occurrence_id,
            source_version=source_version,
            intent_digest=intent_digest,
            verification_policy_id=verification_policy_id,
            required_evidence_scopes=required_evidence_scopes,
            state=DeletionState.ACCEPTED,
            accepted_at=accepted_at,
        )

    def _accept(self) -> DeletionResult:
        result = self.committer.accept(self.intent)
        self.assertEqual(result.outcome, DeletionOutcome.ACCEPTED)
        self.assertTrue(result.durable_transition)
        self.assertIsNotNone(result.snapshot)
        return result

    @staticmethod
    def _binding(identity: str) -> ImmutableBinding:
        return ImmutableBinding(identity, f"sha256:{identity}")

    @staticmethod
    def _evidence(
        *,
        evidence_id: str,
        snapshot: DeletionSnapshot,
        scope: DeletionEvidenceScope,
        status: EvidenceStatus = EvidenceStatus.PASS,
        policy_id: str = POLICY_ID,
        validator_id: str = VALIDATOR_ID,
        validator_version: str = VALIDATOR_VERSION,
        observed_at: str = "2026-11-11T00:05:00Z",
    ) -> DeletionEvidence:
        generation_ids = (
            () if scope is DeletionEvidenceScope.PHYSICAL_PURGE else ("G2",)
        )
        return DeletionEvidence(
            evidence_id=evidence_id,
            deletion_snapshot_id=snapshot.deletion_snapshot_id,
            verification_policy_id=policy_id,
            validator_id=validator_id,
            validator_version=validator_version,
            scope=scope,
            status=status,
            pointer_name="refund-rag-active",
            pointer_revision=8,
            generation_ids=generation_ids,
            tombstoned_occurrence_ids=snapshot.occurrence_ids,
            readback_digest=f"sha256:{evidence_id}",
            observed_at=observed_at,
        )

    def test_accept_atomically_publishes_tombstone_intent_and_outbox(self) -> None:
        result = self._accept()
        assert result.snapshot is not None

        self.assertEqual(
            self.store.read_intent(self.intent.deletion_id),
            self.intent,
        )
        self.assertEqual(result.snapshot.ledger_revision, 1)
        self.assertEqual(result.snapshot.occurrence_ids, ("B@v1",))
        events = self.store.outbox_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].aggregate_id, self.intent.deletion_id)
        self.assertEqual(events[0].aggregate_revision, 1)
        self.assertEqual(events[0].payload_digest, self.intent.identity_digest)
        self.assertNotEqual(events[0].payload_digest, self.intent.intent_digest)
        self.assertEqual(events[0].state, MessageState.PENDING)

    def test_intent_requires_nonempty_canonical_durable_policy_scopes(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self._intent(required_evidence_scopes=())
        with self.assertRaisesRegex(ValueError, "sorted and unique"):
            self._intent(
                required_evidence_scopes=(
                    DeletionEvidenceScope.SERVING_INDEX_ABSENCE,
                    DeletionEvidenceScope.LOGICAL_RELEASE,
                )
            )
        with self.assertRaisesRegex(ValueError, "non-empty identity"):
            self._intent(verification_policy_id="")

    def test_exact_delete_replay_converges_without_second_event(self) -> None:
        first = self._accept()
        second = self.committer.accept(self.intent)

        self.assertEqual(second.outcome, DeletionOutcome.EXACT_REPLAY)
        self.assertFalse(second.durable_transition)
        self.assertEqual(second.intent, first.intent)
        self.assertEqual(second.snapshot, first.snapshot)
        self.assertEqual(len(self.store.outbox_events()), 1)

    def test_retry_after_dispatch_preserves_original_intent_binding(self) -> None:
        self._accept()
        dispatched = self.committer.mark_dispatched(self.intent.deletion_id)
        replay = self.committer.accept(self.intent)

        self.assertEqual(dispatched.outcome, DeletionOutcome.DISPATCHED)
        self.assertEqual(replay.outcome, DeletionOutcome.EXACT_REPLAY)
        assert replay.intent is not None
        self.assertEqual(replay.intent.state, DeletionState.DISPATCHED)
        self.assertEqual(len(self.store.outbox_events()), 1)

    def test_same_operation_and_idempotency_with_other_digest_conflicts(self) -> None:
        self._accept()
        conflicting = replace(
            self.intent,
            deletion_id="delete-refund-B-conflict",
            intent_digest="sha256:different-delete-payload",
        )

        result = self.committer.accept(conflicting)

        self.assertEqual(result.outcome, DeletionOutcome.IDENTITY_CONFLICT)
        self.assertFalse(result.durable_transition)
        self.assertEqual(result.intent, self.intent)
        self.assertIsNone(self.store.read_intent(conflicting.deletion_id))
        self.assertEqual(len(self.store.outbox_events()), 1)

    def test_policy_and_required_scopes_are_part_of_replay_identity(self) -> None:
        self._accept()
        changed_policy = replace(
            self.intent,
            verification_policy_id="deletion-verification-policy-v2",
        )
        changed_scopes = replace(
            self.intent,
            required_evidence_scopes=(DeletionEvidenceScope.LOGICAL_RELEASE,),
        )

        self.assertEqual(
            self.committer.accept(changed_policy).outcome,
            DeletionOutcome.IDENTITY_CONFLICT,
        )
        self.assertEqual(
            self.committer.accept(changed_scopes).outcome,
            DeletionOutcome.IDENTITY_CONFLICT,
        )

    def test_operation_and_idempotency_bindings_must_both_match(self) -> None:
        self._accept()
        operation_only = replace(
            self.intent,
            deletion_id="delete-operation-only",
            idempotency_key="different-idempotency-key",
        )
        idempotency_only = replace(
            self.intent,
            deletion_id="delete-idempotency-only",
            operation_id="different-operation-id",
        )

        operation_result = self.committer.accept(operation_only)
        idempotency_result = self.committer.accept(idempotency_only)

        self.assertEqual(
            operation_result.outcome,
            DeletionOutcome.IDENTITY_CONFLICT,
        )
        self.assertEqual(
            idempotency_result.outcome,
            DeletionOutcome.IDENTITY_CONFLICT,
        )
        self.assertIsNone(self.store.read_intent(operation_only.deletion_id))
        self.assertIsNone(self.store.read_intent(idempotency_only.deletion_id))

    def test_inbox_exact_replay_and_digest_conflict_preserve_first_result(self) -> None:
        first = self.committer.consume(
            event_id="event-delete-B",
            payload_digest="sha256:event-delete-B",
            source_stream="index-delete-outbox",
            result_id="rebuild-job-D1",
            result_digest="sha256:rebuild-job-D1",
        )
        replay = self.committer.consume(
            event_id="event-delete-B",
            payload_digest="sha256:event-delete-B",
            source_stream="index-delete-outbox",
            result_id="ignored-retry-result",
            result_digest="sha256:ignored-retry-result",
        )
        conflict = self.committer.consume(
            event_id="event-delete-B",
            payload_digest="sha256:changed-payload",
            source_stream="index-delete-outbox",
            result_id="conflicting-job",
            result_digest="sha256:conflicting-job",
        )

        self.assertEqual(first.outcome, InboxOutcome.APPLIED)
        self.assertTrue(first.durable_transition)
        self.assertEqual(replay.outcome, InboxOutcome.EXACT_REPLAY)
        self.assertFalse(replay.durable_transition)
        self.assertEqual(conflict.outcome, InboxOutcome.IDENTITY_CONFLICT)
        self.assertFalse(conflict.durable_transition)
        self.assertEqual(replay.record, first.record)
        self.assertEqual(conflict.record, first.record)
        self.assertEqual(self.store.read_inbox("event-delete-B"), first.record)

    def test_snapshot_revision_and_exact_tombstones_advance_monotonically(self) -> None:
        first = self._accept()
        second_intent = self._intent(
            deletion_id="delete-refund-C-v1",
            operation_id="op-delete-refund-C-v1",
            idempotency_key="idem-delete-refund-C-v1",
            occurrence_id="C@v1",
            source_version="C@v1",
            intent_digest="sha256:delete-refund-C-v1",
            accepted_at="2026-11-11T00:01:00Z",
        )
        second = self.committer.accept(second_intent)

        assert first.snapshot is not None and second.snapshot is not None
        self.assertEqual(first.snapshot.ledger_revision, 1)
        self.assertEqual(first.snapshot.occurrence_ids, ("B@v1",))
        self.assertEqual(second.outcome, DeletionOutcome.ACCEPTED)
        self.assertEqual(second.snapshot.ledger_revision, 2)
        self.assertEqual(second.snapshot.occurrence_ids, ("B@v1", "C@v1"))
        self.assertNotEqual(first.snapshot.fingerprint, second.snapshot.fingerprint)

    def test_build_snapshot_fingerprint_binds_deletion_snapshot_against_revival(
        self,
    ) -> None:
        first = self._accept()
        assert first.snapshot is not None
        before = BuildSnapshot(
            build_snapshot_id="BS-before-delete",
            scope_id="refund-rag",
            source_snapshot=self._binding("S1"),
            authorization_snapshot=self._binding("P1"),
            embedding_contract=self._binding("E1"),
            index_schema=self._binding("IS1"),
            source_watermark="W1",
            deletion_snapshot=self._binding("D0"),
        )
        after = replace(
            before,
            build_snapshot_id="BS-after-delete",
            deletion_snapshot=ImmutableBinding(
                first.snapshot.deletion_snapshot_id,
                first.snapshot.fingerprint,
            ),
        )

        self.assertNotEqual(before.fingerprint, after.fingerprint)
        self.assertEqual(
            after.deletion_snapshot.identity,
            first.snapshot.deletion_snapshot_id,
        )

    def test_evidence_contract_requires_pointer_servable_set_and_exact_tombstones(
        self,
    ) -> None:
        accepted = self._accept()
        assert accepted.snapshot is not None
        evidence = self._evidence(
            evidence_id="evidence-logical",
            snapshot=accepted.snapshot,
            scope=DeletionEvidenceScope.LOGICAL_RELEASE,
        )

        with self.assertRaisesRegex(ValueError, "pointer revision"):
            replace(evidence, pointer_revision=0)
        with self.assertRaisesRegex(ValueError, "non-empty identity"):
            replace(evidence, pointer_name="")
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            replace(evidence, generation_ids=())
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            replace(evidence, tombstoned_occurrence_ids=())
        with self.assertRaisesRegex(ValueError, "explicit UTC offset"):
            replace(evidence, observed_at="2026-11-11T00:05:00")

    def test_record_evidence_rejects_untrusted_validator_policy_and_tombstones(
        self,
    ) -> None:
        accepted = self._accept()
        assert accepted.snapshot is not None
        base = self._evidence(
            evidence_id="evidence-logical",
            snapshot=accepted.snapshot,
            scope=DeletionEvidenceScope.LOGICAL_RELEASE,
        )

        untrusted = replace(
            base,
            evidence_id="untrusted",
            validator_id="unknown-validator",
        )
        wrong_policy = replace(
            base,
            evidence_id="wrong-policy",
            verification_policy_id="unknown-policy",
        )
        wrong_tombstones = replace(
            base,
            evidence_id="wrong-tombstones",
            tombstoned_occurrence_ids=("C@v1",),
        )

        for item in (untrusted, wrong_policy, wrong_tombstones):
            self.assertEqual(
                self.committer.record_evidence(item),
                DeletionOutcome.IDENTITY_CONFLICT,
            )
        self.assertEqual(self.store.evidence(), ())

    def test_record_evidence_exact_replay_and_digest_conflict(self) -> None:
        accepted = self._accept()
        assert accepted.snapshot is not None
        evidence = self._evidence(
            evidence_id="evidence-logical",
            snapshot=accepted.snapshot,
            scope=DeletionEvidenceScope.LOGICAL_RELEASE,
        )

        first = self.committer.record_evidence(evidence)
        replay = self.committer.record_evidence(evidence)
        conflict = self.committer.record_evidence(
            replace(
                evidence,
                readback_digest="sha256:conflicting-readback",
            )
        )

        self.assertEqual(first, DeletionOutcome.ACCEPTED)
        self.assertEqual(replay, DeletionOutcome.EXACT_REPLAY)
        self.assertEqual(conflict, DeletionOutcome.IDENTITY_CONFLICT)
        self.assertEqual(self.store.evidence(), (evidence,))

    def test_committer_requires_a_nonempty_trusted_validator_set(self) -> None:
        self.assertEqual(
            DEFAULT_TRUSTED_DELETION_VALIDATORS,
            frozenset({(VALIDATOR_ID, VALIDATOR_VERSION)}),
        )
        with self.assertRaisesRegex(ValueError, "trusted deletion validator"):
            DeletionLedgerCommitter(
                InMemoryDeletionLedger(),
                trusted_validators=frozenset(),
            )

    def test_deletion_evidence_scopes_remain_independent(self) -> None:
        accepted = self._accept()
        assert accepted.snapshot is not None
        logical = self._evidence(
            evidence_id="evidence-logical",
            snapshot=accepted.snapshot,
            scope=DeletionEvidenceScope.LOGICAL_RELEASE,
        )
        serving = self._evidence(
            evidence_id="evidence-serving",
            snapshot=accepted.snapshot,
            scope=DeletionEvidenceScope.SERVING_INDEX_ABSENCE,
            status=EvidenceStatus.NOT_RUN,
        )
        physical = self._evidence(
            evidence_id="evidence-physical",
            snapshot=accepted.snapshot,
            scope=DeletionEvidenceScope.PHYSICAL_PURGE,
            status=EvidenceStatus.FAIL,
        )

        for item in (logical, serving, physical):
            self.assertEqual(
                self.committer.record_evidence(item),
                DeletionOutcome.ACCEPTED,
            )

        recorded = {item.scope: item.status for item in self.store.evidence()}
        self.assertEqual(
            recorded[DeletionEvidenceScope.LOGICAL_RELEASE],
            EvidenceStatus.PASS,
        )
        self.assertEqual(
            recorded[DeletionEvidenceScope.SERVING_INDEX_ABSENCE],
            EvidenceStatus.NOT_RUN,
        )
        self.assertEqual(
            recorded[DeletionEvidenceScope.PHYSICAL_PURGE],
            EvidenceStatus.FAIL,
        )

    def test_verification_uses_durable_scopes_and_persists_adopted_evidence(
        self,
    ) -> None:
        accepted = self._accept()
        assert accepted.snapshot is not None

        for evidence_id, scope in (
            ("logical-pass", DeletionEvidenceScope.LOGICAL_RELEASE),
            ("serving-pass", DeletionEvidenceScope.SERVING_INDEX_ABSENCE),
        ):
            self.assertEqual(
                self.committer.record_evidence(
                    self._evidence(
                        evidence_id=evidence_id,
                        snapshot=accepted.snapshot,
                        scope=scope,
                    )
                ),
                DeletionOutcome.ACCEPTED,
            )

        dispatched = self.committer.mark_dispatched(self.intent.deletion_id)
        self.assertEqual(dispatched.outcome, DeletionOutcome.DISPATCHED)
        incomplete = self.committer.verify(deletion_id=self.intent.deletion_id)
        self.assertEqual(incomplete.outcome, DeletionOutcome.EVIDENCE_INCOMPLETE)
        self.assertFalse(incomplete.durable_transition)
        assert incomplete.intent is not None
        self.assertEqual(incomplete.intent.state, DeletionState.DISPATCHED)

        physical = self._evidence(
            evidence_id="physical-pass",
            snapshot=accepted.snapshot,
            scope=DeletionEvidenceScope.PHYSICAL_PURGE,
        )
        self.assertEqual(
            self.committer.record_evidence(physical),
            DeletionOutcome.ACCEPTED,
        )
        verified = self.committer.verify(deletion_id=self.intent.deletion_id)

        self.assertEqual(verified.outcome, DeletionOutcome.VERIFIED)
        self.assertTrue(verified.durable_transition)
        assert verified.intent is not None
        self.assertEqual(verified.intent.state, DeletionState.VERIFIED)
        self.assertEqual(
            verified.intent.verified_deletion_snapshot_id,
            accepted.snapshot.deletion_snapshot_id,
        )
        self.assertEqual(
            verified.intent.verified_evidence_ids,
            ("logical-pass", "physical-pass", "serving-pass"),
        )
        self.assertIsNotNone(verified.intent.verified_evidence_digest)

        later_fail = replace(
            physical,
            evidence_id="physical-later-fail",
            status=EvidenceStatus.FAIL,
            observed_at="2026-11-11T00:06:00Z",
        )
        self.assertEqual(
            self.committer.record_evidence(later_fail),
            DeletionOutcome.ACCEPTED,
        )
        replay = self.committer.verify(deletion_id=self.intent.deletion_id)
        self.assertEqual(replay.outcome, DeletionOutcome.VERIFIED)
        self.assertFalse(replay.durable_transition)
        self.assertEqual(replay.intent, verified.intent)

    def test_complete_evidence_cannot_verify_before_dispatch(self) -> None:
        accepted = self._accept()
        assert accepted.snapshot is not None
        for scope in ALL_EVIDENCE_SCOPES:
            evidence = self._evidence(
                evidence_id=f"complete-{scope.value}",
                snapshot=accepted.snapshot,
                scope=scope,
            )
            self.assertEqual(
                self.committer.record_evidence(evidence),
                DeletionOutcome.ACCEPTED,
            )

        result = self.committer.verify(deletion_id=self.intent.deletion_id)

        self.assertEqual(result.outcome, DeletionOutcome.EVIDENCE_INCOMPLETE)
        self.assertEqual(
            result.safe_reason,
            "DELETION_MUST_BE_DISPATCHED_BEFORE_VERIFICATION",
        )
        self.assertFalse(result.durable_transition)
        assert result.intent is not None
        self.assertEqual(result.intent.state, DeletionState.ACCEPTED)
        self.assertIsNone(result.intent.verified_evidence_digest)

    def test_latest_evidence_uses_aware_time_not_lexical_time(self) -> None:
        self.intent = self._intent(
            required_evidence_scopes=(DeletionEvidenceScope.LOGICAL_RELEASE,)
        )
        accepted = self._accept()
        assert accepted.snapshot is not None
        older_pass = self._evidence(
            evidence_id="logical-old-pass",
            snapshot=accepted.snapshot,
            scope=DeletionEvidenceScope.LOGICAL_RELEASE,
            observed_at="2026-11-11T10:00:00+08:00",
        )
        newer_fail = self._evidence(
            evidence_id="logical-new-fail",
            snapshot=accepted.snapshot,
            scope=DeletionEvidenceScope.LOGICAL_RELEASE,
            status=EvidenceStatus.FAIL,
            observed_at="2026-11-11T03:00:00+00:00",
        )
        self.assertGreater(older_pass.observed_at, newer_fail.observed_at)
        self.committer.record_evidence(older_pass)
        self.committer.record_evidence(newer_fail)
        self.committer.mark_dispatched(self.intent.deletion_id)

        result = self.committer.verify(deletion_id=self.intent.deletion_id)

        self.assertEqual(result.outcome, DeletionOutcome.EVIDENCE_INCOMPLETE)
        assert result.intent is not None
        self.assertEqual(result.intent.state, DeletionState.DISPATCHED)


if __name__ == "__main__":
    unittest.main()
