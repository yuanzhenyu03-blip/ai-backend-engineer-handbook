"""Deterministic Day104 READY, activation and rollback mechanics."""

from __future__ import annotations

from dataclasses import replace
import unittest

from day104_test_support import (
    build_day104_fixture,
    candidate_evidence,
    classroom_build_snapshot,
    make_ready,
    register_candidate,
)
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
    EvaluationRuler,
    GenerationState,
    MessageState,
)


class Day104ReadyGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = build_day104_fixture()

    def test_matching_evidence_makes_candidate_ready(self) -> None:
        candidate = candidate_evidence(self.fixture, "G2")
        register_candidate(self.fixture, candidate)

        result = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=candidate.evaluation.evidence_id,
        )

        self.assertIs(result.outcome, ReadyOutcome.READY)
        self.assertTrue(result.durable_transition)
        self.assertEqual(result.lifecycle.state, GenerationState.READY)
        self.assertEqual(
            result.artifact.manifest_digest,
            candidate.manifest.digest,
        )
        replay = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=candidate.evaluation.evidence_id,
        )
        self.assertIs(replay.outcome, ReadyOutcome.ALREADY_READY)
        self.assertFalse(replay.durable_transition)

    def test_inconclusive_stays_validating_then_pass_can_make_ready(self) -> None:
        candidate = candidate_evidence(
            self.fixture,
            "G2",
            evaluation_decision=EvaluationDecision.INCONCLUSIVE,
        )
        register_candidate(self.fixture, candidate)

        inconclusive = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=candidate.evaluation.evidence_id,
        )

        self.assertIs(
            inconclusive.outcome,
            ReadyOutcome.EVIDENCE_INCONCLUSIVE,
        )
        self.assertEqual(
            self.fixture.store.read_lifecycle("G2").state,
            GenerationState.VALIDATING,
        )
        passing = replace(
            candidate.evaluation,
            evidence_id="evaluation:G2:retry-pass",
            evaluation_report_checksum="sha256:report-G2-retry-pass",
            decision=EvaluationDecision.PASS,
            observed_at="2026-11-11T00:02:00Z",
        )
        self.fixture.committer.record_evaluation(passing)
        ready = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=passing.evidence_id,
        )
        self.assertIs(ready.outcome, ReadyOutcome.READY)
        self.assertEqual(ready.lifecycle.state, GenerationState.READY)

    def test_observed_evaluation_failure_is_terminal(self) -> None:
        candidate = candidate_evidence(
            self.fixture,
            "G2",
            evaluation_decision=EvaluationDecision.FAIL,
        )
        register_candidate(self.fixture, candidate)

        failed = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=candidate.evaluation.evidence_id,
        )

        self.assertIs(failed.outcome, ReadyOutcome.EVALUATION_FAILED)
        self.assertTrue(failed.durable_transition)
        self.assertEqual(failed.lifecycle.state, GenerationState.FAILED)

    def test_current_snapshot_drift_blocks_ready_without_partial_state(self) -> None:
        candidate = candidate_evidence(self.fixture, "G2")
        register_candidate(self.fixture, candidate)
        self.fixture.store.set_current_build_snapshot(
            classroom_build_snapshot(
                snapshot_id="BS2",
                authorization="P2",
            )
        )

        stale = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=candidate.evaluation.evidence_id,
        )

        self.assertIs(stale.outcome, ReadyOutcome.STALE_BUILD_SNAPSHOT)
        self.assertFalse(stale.durable_transition)
        self.assertEqual(
            self.fixture.store.read_lifecycle("G2").state,
            GenerationState.VALIDATING,
        )
        self.assertIsNone(self.fixture.store.read_artifact("G2"))

    def test_provider_checkpoint_mismatch_blocks_ready(self) -> None:
        candidate = candidate_evidence(
            self.fixture,
            "G2",
            provider_checkpoint="checkpoint:G2:sealed",
            validation_checkpoint="checkpoint:G2:old-readback",
        )
        register_candidate(self.fixture, candidate)

        stale = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=candidate.evaluation.evidence_id,
        )

        self.assertIs(stale.outcome, ReadyOutcome.STALE_READBACK)
        self.assertFalse(stale.durable_transition)
        self.assertEqual(
            self.fixture.store.read_lifecycle("G2").state,
            GenerationState.VALIDATING,
        )

    def test_wrong_day103_ruler_is_rejected_at_record_and_ready(self) -> None:
        wrong_ruler = EvaluationRuler(
            dataset_fingerprint="sha256:dataset-L2",
            evaluator_fingerprint=(self.fixture.evaluation_ruler.evaluator_fingerprint),
            policy_fingerprint=(self.fixture.evaluation_ruler.policy_fingerprint),
        )
        candidate = candidate_evidence(
            self.fixture,
            "G2",
            observed_evaluation_ruler=wrong_ruler,
        )
        changed_build = replace(
            candidate.build,
            evaluation_ruler=wrong_ruler,
        )
        self.assertNotEqual(
            candidate.build.fingerprint,
            changed_build.fingerprint,
        )
        registered = self.fixture.committer.register_validating_candidate(
            build=candidate.build,
            manifest=candidate.manifest,
            seal=candidate.seal,
            validation=candidate.validation,
        )
        self.assertIs(registered.outcome, RegistrationOutcome.REGISTERED)
        changed_build_registration = (
            self.fixture.committer.register_validating_candidate(
                build=changed_build,
                manifest=candidate.manifest,
                seal=candidate.seal,
                validation=candidate.validation,
            )
        )
        self.assertIs(
            changed_build_registration.outcome,
            RegistrationOutcome.IDENTITY_CONFLICT,
        )
        self.assertIs(
            self.fixture.committer.record_evaluation(candidate.evaluation),
            RegistrationOutcome.IDENTITY_CONFLICT,
        )

        # Simulate corrupted persistence to prove READY independently checks
        # the frozen ruler rather than trusting record-time validation alone.
        with self.fixture.store._lock:
            self.fixture.store._evaluations[
                candidate.evaluation.evidence_id
            ] = candidate.evaluation
        ready = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=candidate.evaluation.evidence_id,
        )
        self.assertIs(
            ready.outcome,
            ReadyOutcome.EVIDENCE_BINDING_CONFLICT,
        )
        self.assertEqual(
            self.fixture.store.read_lifecycle("G2").state,
            GenerationState.VALIDATING,
        )

    def test_validation_id_is_globally_set_once(self) -> None:
        first = candidate_evidence(self.fixture, "G1")
        register_candidate(self.fixture, first)
        second = candidate_evidence(self.fixture, "G2")
        second_validation = replace(
            second.validation,
            validation_id=first.validation.validation_id,
        )

        conflict = self.fixture.committer.register_validating_candidate(
            build=second.build,
            manifest=second.manifest,
            seal=second.seal,
            validation=second_validation,
        )

        self.assertIs(
            conflict.outcome,
            RegistrationOutcome.IDENTITY_CONFLICT,
        )
        self.assertEqual(
            conflict.safe_reason,
            "VALIDATION_ID_ALREADY_BOUND_TO_OTHER_EVIDENCE",
        )
        self.assertIsNone(self.fixture.store.read_build("G2"))
        self.assertIsNone(self.fixture.store.read_lifecycle("G2"))

    def test_already_ready_rechecks_snapshot_seal_and_artifact_binding(self) -> None:
        candidate = make_ready(self.fixture, "G2")
        self.fixture.store.set_current_build_snapshot(
            classroom_build_snapshot(
                snapshot_id="BS2",
                authorization="P2",
            )
        )
        stale_snapshot = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=candidate.evaluation.evidence_id,
        )
        self.assertIs(
            stale_snapshot.outcome,
            ReadyOutcome.STALE_BUILD_SNAPSHOT,
        )

        self.fixture.store.set_current_build_snapshot(self.fixture.snapshot)
        with self.fixture.store._lock:
            self.fixture.store._builds["G2"] = replace(
                candidate.build,
                expected_manifest_fingerprint="sha256:changed-expected",
            )
        changed_expected = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=candidate.evaluation.evidence_id,
        )
        self.assertIs(
            changed_expected.outcome,
            ReadyOutcome.EVIDENCE_BINDING_CONFLICT,
        )

        with self.fixture.store._lock:
            self.fixture.store._builds["G2"] = candidate.build
            self.fixture.store._seals["G2"] = replace(
                candidate.seal,
                generation_id="G-other",
            )
        changed_seal_identity = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=candidate.evaluation.evidence_id,
        )
        self.assertIs(
            changed_seal_identity.outcome,
            ReadyOutcome.EVIDENCE_BINDING_CONFLICT,
        )

        with self.fixture.store._lock:
            self.fixture.store._seals["G2"] = replace(
                candidate.seal,
                provider_checkpoint="checkpoint:G2:changed",
            )
        stale_seal = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=candidate.evaluation.evidence_id,
        )
        self.assertIs(stale_seal.outcome, ReadyOutcome.STALE_READBACK)

        with self.fixture.store._lock:
            self.fixture.store._seals["G2"] = candidate.seal
        alternate = replace(
            candidate.evaluation,
            evidence_id="evaluation:G2:alternate",
            observed_at="2026-11-11T00:02:00Z",
        )
        self.assertIs(
            self.fixture.committer.record_evaluation(alternate),
            RegistrationOutcome.REGISTERED,
        )
        changed_artifact_binding = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=alternate.evidence_id,
        )
        self.assertIs(
            changed_artifact_binding.outcome,
            ReadyOutcome.EVIDENCE_BINDING_CONFLICT,
        )
        alternate_validation = replace(
            candidate.validation,
            validation_id="validation:G2:alternate",
            observed_at="2026-11-11T00:02:00Z",
        )
        validation_replay = self.fixture.committer.register_validating_candidate(
            build=candidate.build,
            manifest=candidate.manifest,
            seal=candidate.seal,
            validation=alternate_validation,
        )
        self.assertIs(
            validation_replay.outcome,
            RegistrationOutcome.ALREADY_REGISTERED,
        )
        changed_validation_binding = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=alternate_validation.validation_id,
            evaluation_evidence_id=candidate.evaluation.evidence_id,
        )
        self.assertIs(
            changed_validation_binding.outcome,
            ReadyOutcome.EVIDENCE_BINDING_CONFLICT,
        )
        wrong_ruler = replace(
            candidate.evaluation,
            evidence_id="evaluation:G2:wrong-ruler",
            dataset_fingerprint="sha256:dataset-L2",
        )
        with self.fixture.store._lock:
            self.fixture.store._evaluations[wrong_ruler.evidence_id] = wrong_ruler
        changed_ruler_binding = self.fixture.committer.mark_ready(
            generation_id="G2",
            expected_state_version=1,
            validation_record_id=candidate.validation.validation_id,
            evaluation_evidence_id=wrong_ruler.evidence_id,
        )
        self.assertIs(
            changed_ruler_binding.outcome,
            ReadyOutcome.EVIDENCE_BINDING_CONFLICT,
        )
        self.assertEqual(
            self.fixture.store.read_lifecycle("G2").state,
            GenerationState.READY,
        )


class Day104ActivationTests(unittest.TestCase):
    pointer_name = "refund-rag-active"

    def setUp(self) -> None:
        self.fixture = build_day104_fixture()
        make_ready(self.fixture, "G1")
        self.fixture.store.seed_active_pointer(
            pointer=ActivePointer(self.pointer_name, "G1", 7),
            provider_alias_generation_id="G1",
        )
        self.lease = self.fixture.store.issue_activation_lease(
            pointer_name=self.pointer_name,
            committer_id="committer-a",
            issued_at="2026-11-11T00:02:00Z",
        )
        make_ready(self.fixture, "G2")

    def _activate(
        self,
        *,
        activation_id: str = "ACT-8",
        target: str = "G2",
        expected: str = "G1",
        revision: int = 7,
        fence: int = 1,
        committer_id: str = "committer-a",
        committed_at: str = "2026-11-11T00:03:00Z",
    ):
        return self.fixture.committer.activate(
            activation_id=activation_id,
            pointer_name=self.pointer_name,
            target_generation_id=target,
            expected_generation_id=expected,
            expected_revision=revision,
            committer_id=committer_id,
            committer_fence=fence,
            committed_at=committed_at,
        )

    def test_activation_atomically_updates_pointer_states_record_and_outbox(
        self,
    ) -> None:
        result = self._activate()

        self.assertIs(result.outcome, ActivationOutcome.ACTIVATED)
        self.assertTrue(result.durable_transition)
        self.assertEqual(
            result.pointer,
            ActivePointer(
                self.pointer_name,
                "G2",
                8,
            ),
        )
        self.assertEqual(
            self.fixture.store.read_lifecycle("G1").state,
            GenerationState.DRAINING,
        )
        self.assertEqual(
            self.fixture.store.read_lifecycle("G2").state,
            GenerationState.ACTIVE,
        )
        self.assertEqual(len(self.fixture.store.activation_records()), 1)
        self.assertEqual(len(self.fixture.store.outbox_events()), 1)
        self.assertEqual(
            self.fixture.store.read_provider_alias(self.pointer_name),
            "G1",
        )

    def test_stale_pointer_and_fence_publish_no_partial_state(self) -> None:
        before_pointer = self.fixture.store.read_pointer(self.pointer_name)
        before_g1 = self.fixture.store.read_lifecycle("G1")
        before_g2 = self.fixture.store.read_lifecycle("G2")

        stale_fence = self._activate(fence=0)
        self.assertIs(stale_fence.outcome, ActivationOutcome.STALE_FENCE)
        stale_pointer = self._activate(revision=6, fence=1)
        self.assertIs(stale_pointer.outcome, ActivationOutcome.STALE_POINTER)
        self.assertEqual(
            self.fixture.store.read_pointer(self.pointer_name),
            before_pointer,
        )
        self.assertEqual(self.fixture.store.read_lifecycle("G1"), before_g1)
        self.assertEqual(self.fixture.store.read_lifecycle("G2"), before_g2)
        self.assertEqual(self.fixture.store.activation_records(), ())
        self.assertEqual(self.fixture.store.outbox_events(), ())

    def test_activation_without_authority_issued_lease_is_rejected(self) -> None:
        before_pointer = self.fixture.store.read_pointer(self.pointer_name)
        with self.fixture.store._lock:
            self.fixture.store._activation_leases.pop(self.pointer_name)

        rejected = self._activate()

        self.assertIs(rejected.outcome, ActivationOutcome.STALE_FENCE)
        self.assertFalse(rejected.durable_transition)
        self.assertEqual(
            self.fixture.store.read_pointer(self.pointer_name),
            before_pointer,
        )
        self.assertEqual(self.fixture.store.activation_records(), ())
        self.assertEqual(self.fixture.store.outbox_events(), ())

    def test_exact_activation_replay_converges_without_second_event(self) -> None:
        first = self._activate()
        second = self._activate()

        self.assertIs(first.outcome, ActivationOutcome.ACTIVATED)
        self.assertIs(second.outcome, ActivationOutcome.ALREADY_ACTIVATED)
        self.assertFalse(second.durable_transition)
        self.assertEqual(len(self.fixture.store.activation_records()), 1)
        self.assertEqual(len(self.fixture.store.outbox_events()), 1)
        changed_input = self._activate(
            committed_at="2026-11-11T00:03:01Z",
        )
        self.assertIs(
            changed_input.outcome,
            ActivationOutcome.IDENTITY_CONFLICT,
        )
        self.assertEqual(len(self.fixture.store.activation_records()), 1)
        self.assertEqual(len(self.fixture.store.outbox_events()), 1)

    def test_committed_exact_replay_converges_after_lease_rotation(self) -> None:
        first = self._activate()
        self.fixture.store.rotate_activation_lease(
            pointer_name=self.pointer_name,
            expected_fencing_token=1,
            committer_id="committer-b",
            issued_at="2026-11-11T00:04:00Z",
        )

        replay = self._activate()

        self.assertIs(first.outcome, ActivationOutcome.ACTIVATED)
        self.assertIs(replay.outcome, ActivationOutcome.ALREADY_ACTIVATED)
        self.assertFalse(replay.durable_transition)
        self.assertEqual(len(self.fixture.store.activation_records()), 1)
        self.assertEqual(len(self.fixture.store.outbox_events()), 1)

    def test_only_one_successor_may_claim_pointer_revision(self) -> None:
        applied = self._activate()
        self.assertIs(applied.outcome, ActivationOutcome.ACTIVATED)
        make_ready(self.fixture, "G4")
        self.fixture.store.rotate_activation_lease(
            pointer_name=self.pointer_name,
            expected_fencing_token=1,
            committer_id="committer-a",
            issued_at="2026-11-11T00:04:00Z",
        )
        with self.fixture.store._lock:
            self.fixture.store._pointers[self.pointer_name] = ActivePointer(
                self.pointer_name,
                "G1",
                7,
            )

        conflict = self._activate(
            activation_id="ACT-8-competing",
            target="G4",
            fence=2,
        )

        self.assertIs(
            conflict.outcome,
            ActivationOutcome.UNIQUE_SUCCESSOR_CONFLICT,
        )
        self.assertFalse(conflict.durable_transition)
        self.assertEqual(len(self.fixture.store.activation_records()), 1)
        self.assertEqual(len(self.fixture.store.outbox_events()), 1)

    def test_alias_projection_recovers_commit_before_project_and_lost_ack(self) -> None:
        activated = self._activate()
        event = self.fixture.store.outbox_events()[0]
        self.assertEqual(
            self.fixture.store.read_provider_alias(self.pointer_name),
            "G1",
        )

        lost_ack = self.fixture.committer.project_provider_alias(
            event.event_id,
            acknowledge=False,
        )
        self.assertIs(lost_ack.outcome, AliasProjectionOutcome.APPLIED)
        self.assertEqual(
            self.fixture.store.read_provider_alias(self.pointer_name),
            "G2",
        )
        self.assertEqual(
            self.fixture.store.read_outbox(event.event_id).state,
            MessageState.PENDING,
        )
        retry = self.fixture.committer.project_provider_alias(event.event_id)
        self.assertIs(retry.outcome, AliasProjectionOutcome.ALREADY_APPLIED)
        self.assertEqual(
            self.fixture.store.read_outbox(event.event_id).state,
            MessageState.DISPATCHED,
        )
        self.assertEqual(
            self.fixture.store.read_pointer(self.pointer_name),
            activated.pointer,
        )

    def test_compatible_draining_generation_can_rollback_and_aba_is_blocked(
        self,
    ) -> None:
        self._activate()
        self.fixture.store.rotate_activation_lease(
            pointer_name=self.pointer_name,
            expected_fencing_token=1,
            committer_id="committer-a",
            issued_at="2026-11-11T00:04:00Z",
        )
        rolled_back = self._activate(
            activation_id="ROLLBACK-9",
            target="G1",
            expected="G2",
            revision=8,
            fence=2,
        )

        self.assertIs(rolled_back.outcome, ActivationOutcome.ACTIVATED)
        self.assertEqual(
            rolled_back.pointer,
            ActivePointer(self.pointer_name, "G1", 9),
        )
        self.assertEqual(
            self.fixture.store.read_lifecycle("G1").state,
            GenerationState.ACTIVE,
        )
        self.assertEqual(
            self.fixture.store.read_lifecycle("G2").state,
            GenerationState.DRAINING,
        )
        make_ready(self.fixture, "G3")
        self.fixture.store.rotate_activation_lease(
            pointer_name=self.pointer_name,
            expected_fencing_token=2,
            committer_id="committer-a",
            issued_at="2026-11-11T00:05:00Z",
        )
        stale_aba = self._activate(
            activation_id="ACT-stale-ABA",
            target="G3",
            expected="G1",
            revision=7,
            fence=3,
        )
        self.assertIs(stale_aba.outcome, ActivationOutcome.STALE_POINTER)

    def test_stale_snapshot_blocks_rollback(self) -> None:
        self._activate()
        self.fixture.store.rotate_activation_lease(
            pointer_name=self.pointer_name,
            expected_fencing_token=1,
            committer_id="committer-a",
            issued_at="2026-11-11T00:04:00Z",
        )
        next_snapshot = classroom_build_snapshot(
            snapshot_id="BS2",
            authorization="P2",
        )
        self.fixture.store.set_current_build_snapshot(next_snapshot)

        stale = self._activate(
            activation_id="ROLLBACK-stale",
            target="G1",
            expected="G2",
            revision=8,
            fence=2,
        )

        self.assertIs(
            stale.outcome,
            ActivationOutcome.STALE_BUILD_SNAPSHOT,
        )
        self.assertFalse(stale.durable_transition)
        self.assertEqual(
            self.fixture.store.read_pointer(self.pointer_name),
            ActivePointer(self.pointer_name, "G2", 8),
        )

    def test_new_lease_token_fences_old_worker_before_commit(self) -> None:
        old_pointer = self.fixture.store.read_pointer(self.pointer_name)
        old_g1 = self.fixture.store.read_lifecycle("G1")
        old_g2 = self.fixture.store.read_lifecycle("G2")
        current = self.fixture.store.rotate_activation_lease(
            pointer_name=self.pointer_name,
            expected_fencing_token=self.lease.fencing_token,
            committer_id="committer-b",
            issued_at="2026-11-11T00:04:00Z",
        )

        late_old_worker = self._activate()

        self.assertIs(
            late_old_worker.outcome,
            ActivationOutcome.STALE_FENCE,
        )
        self.assertEqual(
            self.fixture.store.read_pointer(self.pointer_name),
            old_pointer,
        )
        self.assertEqual(self.fixture.store.read_lifecycle("G1"), old_g1)
        self.assertEqual(self.fixture.store.read_lifecycle("G2"), old_g2)
        self.assertEqual(self.fixture.store.activation_records(), ())
        self.assertEqual(self.fixture.store.outbox_events(), ())

        current_worker = self._activate(
            fence=current.fencing_token,
            committer_id=current.committer_id,
        )
        self.assertIs(current_worker.outcome, ActivationOutcome.ACTIVATED)

    def test_activation_lease_issue_and_rotation_are_cas_guarded(self) -> None:
        with self.assertRaisesRegex(ValueError, "rotate it explicitly"):
            self.fixture.store.issue_activation_lease(
                pointer_name=self.pointer_name,
                committer_id="committer-b",
                issued_at="2026-11-11T00:04:00Z",
            )
        with self.assertRaisesRegex(ValueError, "token changed"):
            self.fixture.store.rotate_activation_lease(
                pointer_name=self.pointer_name,
                expected_fencing_token=99,
                committer_id="committer-b",
                issued_at="2026-11-11T00:04:00Z",
            )
        self.assertEqual(
            self.fixture.store.read_activation_lease(self.pointer_name),
            self.lease,
        )


if __name__ == "__main__":
    unittest.main()
