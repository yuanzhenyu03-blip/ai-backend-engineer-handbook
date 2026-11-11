"""Day104 provider, read-back and delayed-projection failure tests."""

from __future__ import annotations

import unittest

from day104_test_support import build_day104_fixture, make_ready
from rag_index_lifecycle_committer import (
    ActivationOutcome,
    AliasProjectionOutcome,
    ReadyOutcome,
    RegistrationOutcome,
)
from rag_index_lifecycle_contracts import (
    ActivePointer,
    EvaluationDecision,
    EvaluationEvidence,
    GenerationState,
    MessageState,
)
from rag_index_lifecycle_orchestrator import (
    BuildValidationOutcome,
    DeterministicSealedIndexProvider,
    IndexLifecycleOrchestrator,
    IndexedOccurrence,
    ProviderWriteOutcome,
)


def _record(occurrence_id: str, suffix: str) -> IndexedOccurrence:
    return IndexedOccurrence(
        occurrence_id,
        f"sha256:content-{suffix}",
        f"sha256:metadata-{suffix}",
        f"sha256:provenance-{suffix}",
    )


class Day104ProviderFailureTests(unittest.TestCase):
    def test_physical_namespace_is_set_once_for_one_generation(self) -> None:
        provider = DeterministicSealedIndexProvider()
        records = (_record("A@v1", "A"),)
        first = provider.replace_generation(
            generation_id="G2",
            namespace="refund/shared",
            occurrences=records,
            fence=7,
        )

        conflicting = provider.replace_generation(
            generation_id="G3",
            namespace="refund/shared",
            occurrences=records,
            fence=8,
        )

        self.assertIs(first.outcome, ProviderWriteOutcome.WRITTEN)
        self.assertIs(
            conflicting.outcome,
            ProviderWriteOutcome.IDENTITY_CONFLICT,
        )
        self.assertEqual(
            conflicting.safe_reason,
            "PHYSICAL_NAMESPACE_ALREADY_BOUND_TO_OTHER_GENERATION",
        )

    def test_seal_rejects_late_or_rewritten_provider_generation(self) -> None:
        provider = DeterministicSealedIndexProvider()
        records = (_record("A@v1", "A"), _record("C@v1", "C"))
        written = provider.replace_generation(
            generation_id="G2",
            namespace="refund/G2",
            occurrences=records,
            fence=7,
        )
        assert written.checkpoint is not None
        seal = provider.seal(
            generation_id="G2",
            expected_checkpoint=written.checkpoint,
            expected_fence=7,
        )
        self.assertIsNotNone(seal)

        late = provider.replace_generation(
            generation_id="G2",
            namespace="refund/G2",
            occurrences=records,
            fence=6,
        )
        rewritten = provider.replace_generation(
            generation_id="G2",
            namespace="refund/G2",
            occurrences=(_record("A@v2", "A2"),),
            fence=8,
        )
        self.assertIs(late.outcome, ProviderWriteOutcome.SEALED)
        self.assertIs(rewritten.outcome, ProviderWriteOutcome.SEALED)
        self.assertEqual(provider.readback("G2")[0], records)

    def test_empty_corpus_can_be_sealed_validated_and_made_ready(self) -> None:
        fixture = build_day104_fixture()
        orchestrator = IndexLifecycleOrchestrator(
            provider=DeterministicSealedIndexProvider(),
            committer=fixture.committer,
        )
        built = orchestrator.build_and_validate(
            generation_id="G-empty",
            build_snapshot=fixture.snapshot,
            evaluation_ruler=fixture.evaluation_ruler,
            expected_occurrences=(),
            expected_absent_occurrence_ids=("B@v1",),
            physical_namespace="refund/G-empty",
            provider_write_fence=7,
            validation_id="validation:G-empty",
            validator_version="validator-v1",
            observed_at="2026-11-11T00:00:00Z",
        )

        self.assertIs(built.outcome, BuildValidationOutcome.VALIDATING)
        assert built.manifest is not None
        self.assertEqual(built.manifest.expected.occurrence_ids, ())
        self.assertEqual(built.manifest.actual.occurrence_ids, ())
        self.assertTrue(built.manifest.integrity_matches)
        evidence = EvaluationEvidence(
            evidence_id="evaluation:G-empty",
            generation_id="G-empty",
            build_snapshot_fingerprint=fixture.snapshot.fingerprint,
            manifest_digest=built.manifest.digest,
            dataset_fingerprint=fixture.evaluation_ruler.dataset_fingerprint,
            evaluator_fingerprint=(fixture.evaluation_ruler.evaluator_fingerprint),
            policy_fingerprint=fixture.evaluation_ruler.policy_fingerprint,
            evaluation_report_checksum="sha256:report-empty",
            evidence_level="DETERMINISTIC_FAKE",
            decision=EvaluationDecision.PASS,
            observed_at="2026-11-11T00:01:00Z",
        )
        self.assertIs(
            fixture.committer.record_evaluation(evidence),
            RegistrationOutcome.REGISTERED,
        )

        ready = fixture.committer.mark_ready(
            generation_id="G-empty",
            expected_state_version=1,
            validation_record_id="validation:G-empty",
            evaluation_evidence_id="evaluation:G-empty",
        )

        self.assertIs(ready.outcome, ReadyOutcome.READY)
        self.assertEqual(ready.lifecycle.state, GenerationState.READY)

    def test_equal_count_substitution_and_tombstone_fail_integrity(self) -> None:
        fixture = build_day104_fixture()
        provider = DeterministicSealedIndexProvider()
        orchestrator = IndexLifecycleOrchestrator(
            provider=provider,
            committer=fixture.committer,
        )
        expected = (_record("A@v1", "A"), _record("C@v1", "C"))
        actual = (_record("A@v1", "A"), _record("B@v1", "B"))
        built = orchestrator.build_and_validate(
            generation_id="G2",
            build_snapshot=fixture.snapshot,
            evaluation_ruler=fixture.evaluation_ruler,
            expected_occurrences=expected,
            provider_occurrences=actual,
            expected_absent_occurrence_ids=("B@v1",),
            physical_namespace="refund/G2",
            provider_write_fence=7,
            validation_id="validation:G2",
            validator_version="validator-v1",
            observed_at="2026-11-11T00:00:00Z",
        )
        self.assertIs(built.outcome, BuildValidationOutcome.VALIDATING)
        assert built.manifest is not None
        self.assertFalse(built.manifest.integrity_matches)
        evidence = EvaluationEvidence(
            evidence_id="evaluation:G2",
            generation_id="G2",
            build_snapshot_fingerprint=fixture.snapshot.fingerprint,
            manifest_digest=built.manifest.digest,
            dataset_fingerprint=fixture.evaluation_ruler.dataset_fingerprint,
            evaluator_fingerprint=(fixture.evaluation_ruler.evaluator_fingerprint),
            policy_fingerprint=fixture.evaluation_ruler.policy_fingerprint,
            evaluation_report_checksum="sha256:report",
            evidence_level="DETERMINISTIC_FAKE",
            decision=EvaluationDecision.PASS,
            observed_at="2026-11-11T00:01:00Z",
        )
        self.assertIs(
            fixture.committer.record_evaluation(evidence),
            RegistrationOutcome.REGISTERED,
        )
        ready = fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id="validation:G2",
            evaluation_evidence_id="evaluation:G2",
        )
        self.assertIs(ready.outcome, ReadyOutcome.INTEGRITY_FAILED)
        self.assertEqual(ready.lifecycle.state, GenerationState.FAILED)

    def test_sealed_exact_replay_records_new_validation_evidence(self) -> None:
        fixture = build_day104_fixture()
        provider = DeterministicSealedIndexProvider()
        orchestrator = IndexLifecycleOrchestrator(
            provider=provider,
            committer=fixture.committer,
        )
        records = (_record("A@v1", "A"), _record("C@v1", "C"))
        first = orchestrator.build_and_validate(
            generation_id="G2",
            build_snapshot=fixture.snapshot,
            evaluation_ruler=fixture.evaluation_ruler,
            expected_occurrences=records,
            expected_absent_occurrence_ids=("B@v1",),
            physical_namespace="refund/G2",
            provider_write_fence=7,
            validation_id="validation:G2:first",
            validator_version="validator-v1",
            observed_at="2026-11-11T00:00:00Z",
        )
        replay = orchestrator.build_and_validate(
            generation_id="G2",
            build_snapshot=fixture.snapshot,
            evaluation_ruler=fixture.evaluation_ruler,
            expected_occurrences=records,
            expected_absent_occurrence_ids=("B@v1",),
            physical_namespace="refund/G2",
            provider_write_fence=7,
            validation_id="validation:G2:replay",
            validator_version="validator-v1",
            observed_at="2026-11-11T00:01:00Z",
        )
        self.assertIs(first.outcome, BuildValidationOutcome.VALIDATING)
        self.assertIs(replay.outcome, BuildValidationOutcome.VALIDATING)
        assert replay.manifest is not None
        evidence = EvaluationEvidence(
            evidence_id="evaluation:G2",
            generation_id="G2",
            build_snapshot_fingerprint=fixture.snapshot.fingerprint,
            manifest_digest=replay.manifest.digest,
            dataset_fingerprint=fixture.evaluation_ruler.dataset_fingerprint,
            evaluator_fingerprint=(fixture.evaluation_ruler.evaluator_fingerprint),
            policy_fingerprint=fixture.evaluation_ruler.policy_fingerprint,
            evaluation_report_checksum="sha256:report",
            evidence_level="DETERMINISTIC_FAKE",
            decision=EvaluationDecision.PASS,
            observed_at="2026-11-11T00:02:00Z",
        )
        fixture.committer.record_evaluation(evidence)
        ready = fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id="validation:G2:replay",
            evaluation_evidence_id="evaluation:G2",
        )
        self.assertIs(ready.outcome, ReadyOutcome.READY)


class Day104DelayedAliasTests(unittest.TestCase):
    def test_delayed_old_alias_event_cannot_reverse_database_pointer(self) -> None:
        fixture = build_day104_fixture()
        make_ready(fixture, "G1")
        fixture.store.seed_active_pointer(
            pointer=ActivePointer("refund-active", "G1", 7),
            provider_alias_generation_id="G1",
        )
        first_lease = fixture.store.issue_activation_lease(
            pointer_name="refund-active",
            committer_id="committer",
            issued_at="2026-11-11T00:02:00Z",
        )
        make_ready(fixture, "G2")
        first = fixture.committer.activate(
            activation_id="ACT-8",
            pointer_name="refund-active",
            target_generation_id="G2",
            expected_generation_id="G1",
            expected_revision=7,
            committer_id="committer",
            committer_fence=first_lease.fencing_token,
            committed_at="2026-11-11T00:03:00Z",
        )
        second_lease = fixture.store.rotate_activation_lease(
            pointer_name="refund-active",
            expected_fencing_token=first_lease.fencing_token,
            committer_id="committer",
            issued_at="2026-11-11T00:03:30Z",
        )
        make_ready(fixture, "G3")
        second = fixture.committer.activate(
            activation_id="ACT-9",
            pointer_name="refund-active",
            target_generation_id="G3",
            expected_generation_id="G2",
            expected_revision=8,
            committer_id="committer",
            committer_fence=second_lease.fencing_token,
            committed_at="2026-11-11T00:04:00Z",
        )
        self.assertIs(first.outcome, ActivationOutcome.ACTIVATED)
        self.assertIs(second.outcome, ActivationOutcome.ACTIVATED)
        old_event, current_event = fixture.store.outbox_events()

        delayed = fixture.committer.project_provider_alias(old_event.event_id)
        self.assertIs(delayed.outcome, AliasProjectionOutcome.APPLIED)
        self.assertEqual(
            delayed.safe_reason,
            "STALE_EVENT_RECONCILED_TO_CURRENT_DATABASE_POINTER",
        )
        self.assertEqual(
            fixture.store.read_provider_alias("refund-active"),
            "G3",
        )
        acknowledged = fixture.store.read_outbox(old_event.event_id)
        self.assertIsNotNone(acknowledged)
        assert acknowledged is not None
        self.assertIs(acknowledged.state, MessageState.DISPATCHED)
        projected = fixture.committer.project_provider_alias(current_event.event_id)
        self.assertIs(
            projected.outcome,
            AliasProjectionOutcome.ALREADY_APPLIED,
        )
        self.assertEqual(
            fixture.store.read_provider_alias("refund-active"),
            "G3",
        )
        self.assertEqual(
            fixture.store.read_pointer("refund-active"),
            ActivePointer("refund-active", "G3", 9),
        )


if __name__ == "__main__":
    unittest.main()
