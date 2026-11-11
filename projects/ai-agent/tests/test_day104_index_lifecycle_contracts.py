from __future__ import annotations

from dataclasses import replace
import unittest

from rag_index_lifecycle_contracts import (
    ActivationDecision,
    ActivationLease,
    ActivationRecord,
    BuildSnapshot,
    EvaluationRuler,
    GenerationArtifact,
    GenerationLifecycle,
    GenerationManifest,
    GenerationState,
    ImmutableBinding,
    InboxRecord,
    ManifestFacts,
    MessageState,
    ReadView,
    ReadViewStatus,
    ValidationDecision,
    ValidationRecord,
)


def _binding(name: str) -> ImmutableBinding:
    return ImmutableBinding(name, f"sha256:{name}")


def _build_snapshot() -> BuildSnapshot:
    return BuildSnapshot(
        build_snapshot_id="BS3",
        scope_id="refund-rag",
        source_snapshot=_binding("S2"),
        authorization_snapshot=_binding("P2"),
        embedding_contract=_binding("E1"),
        index_schema=_binding("IS1"),
        source_watermark="W2",
        deletion_snapshot=_binding("D1"),
    )


def _facts(
    occurrence_ids: tuple[str, ...] = ("A@v2", "C@v1"),
    *,
    content_digest: str = "sha256:content",
    metadata_digest: str = "sha256:metadata",
    provenance_digest: str = "sha256:provenance",
) -> ManifestFacts:
    return ManifestFacts(
        occurrence_ids=occurrence_ids,
        content_digest=content_digest,
        metadata_digest=metadata_digest,
        provenance_digest=provenance_digest,
    )


class Day104IndexLifecycleContractTests(unittest.TestCase):
    def test_evaluation_ruler_binds_all_day103_identities(self) -> None:
        baseline = EvaluationRuler(
            dataset_fingerprint="sha256:dataset",
            evaluator_fingerprint="sha256:evaluator",
            policy_fingerprint="sha256:policy",
        )
        changes = {
            "dataset_fingerprint": "sha256:dataset-v2",
            "evaluator_fingerprint": "sha256:evaluator-v2",
            "policy_fingerprint": "sha256:policy-v2",
        }
        for field_name, value in changes.items():
            with self.subTest(field_name=field_name):
                self.assertNotEqual(
                    baseline.fingerprint,
                    replace(baseline, **{field_name: value}).fingerprint,
                )

    def test_activation_lease_requires_positive_fencing_token(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be positive"):
            ActivationLease(
                pointer_name="refund-rag-active",
                committer_id="committer-1",
                fencing_token=0,
                issued_at="2026-11-11T00:00:00Z",
            )

    def test_every_build_binding_changes_snapshot_fingerprint(self) -> None:
        baseline = _build_snapshot()
        changes = {
            "source_snapshot": _binding("S3"),
            "authorization_snapshot": _binding("P3"),
            "embedding_contract": _binding("E2"),
            "index_schema": _binding("IS2"),
            "source_watermark": "W3",
            "deletion_snapshot": _binding("D2"),
        }
        for field_name, value in changes.items():
            with self.subTest(field_name=field_name):
                changed = replace(baseline, **{field_name: value})
                self.assertNotEqual(
                    baseline.fingerprint,
                    changed.fingerprint,
                )

    def test_snapshot_label_does_not_change_stable_input_fingerprint(self) -> None:
        baseline = _build_snapshot()
        replay = replace(baseline, build_snapshot_id="BS3-replay")
        self.assertEqual(baseline.fingerprint, replay.fingerprint)

    def test_matching_expected_and_actual_manifest_passes(self) -> None:
        facts = _facts()
        manifest = GenerationManifest(
            expected=facts,
            actual=facts,
            expected_absent_occurrence_ids=("B@v1",),
        )
        self.assertTrue(manifest.integrity_matches)
        self.assertEqual(facts.occurrence_count, 2)
        self.assertTrue(facts.occurrence_ids_digest.startswith("sha256:"))

    def test_equal_count_with_substituted_occurrence_fails(self) -> None:
        manifest = GenerationManifest(
            expected=_facts(),
            actual=_facts(("A@v2", "D@v1")),
        )
        self.assertEqual(
            manifest.expected.occurrence_count,
            manifest.actual.occurrence_count,
        )
        self.assertFalse(manifest.integrity_matches)

    def test_content_metadata_and_provenance_replacements_fail(self) -> None:
        expected = _facts()
        changes = {
            "content_digest": "sha256:changed-content",
            "metadata_digest": "sha256:changed-metadata",
            "provenance_digest": "sha256:changed-provenance",
        }
        for field_name, value in changes.items():
            with self.subTest(field_name=field_name):
                actual = replace(expected, **{field_name: value})
                manifest = GenerationManifest(expected, actual)
                self.assertFalse(manifest.integrity_matches)

    def test_tombstoned_occurrence_in_actual_manifest_fails(self) -> None:
        manifest = GenerationManifest(
            expected=_facts(),
            actual=_facts(("A@v2", "B@v1")),
            expected_absent_occurrence_ids=("B@v1",),
        )
        self.assertFalse(manifest.integrity_matches)

    def test_expected_manifest_cannot_include_tombstoned_occurrence(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected corpus"):
            GenerationManifest(
                expected=_facts(("A@v2", "B@v1")),
                actual=_facts(("A@v2", "B@v1")),
                expected_absent_occurrence_ids=("B@v1",),
            )

    def test_manifest_occurrence_ids_must_be_sorted_and_unique(self) -> None:
        with self.assertRaisesRegex(ValueError, "sorted and unique"):
            _facts(("C@v1", "A@v2"))
        with self.assertRaisesRegex(ValueError, "sorted and unique"):
            _facts(("A@v2", "A@v2"))

    def test_retired_generation_cannot_have_active_readers(self) -> None:
        with self.assertRaisesRegex(ValueError, "active readers"):
            GenerationLifecycle(
                generation_id="G2",
                state=GenerationState.RETIRED,
                state_version=8,
                transition_fence=4,
                active_readers=1,
            )

    def test_lifecycle_versions_and_counts_cannot_be_negative(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            GenerationLifecycle(
                generation_id="G2",
                state=GenerationState.DRAINING,
                state_version=8,
                transition_fence=4,
                active_readers=-1,
            )

    def test_activation_revision_must_advance_exactly_once(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one"):
            ActivationRecord(
                activation_id="ACT-3",
                pointer_name="refund-rag-active",
                expected_generation_id="G2",
                target_generation_id="G3",
                from_revision=8,
                to_revision=10,
                build_snapshot_fingerprint="sha256:bs",
                manifest_digest="sha256:manifest",
                evaluation_report_checksum="sha256:report",
                committer_id="committer-1",
                committer_fence=52,
                decision=ActivationDecision.APPLIED,
                committed_at="2026-11-11T00:00:00Z",
            )

    def test_activation_must_change_generation(self) -> None:
        with self.assertRaisesRegex(ValueError, "change the selected"):
            ActivationRecord(
                activation_id="ACT-3",
                pointer_name="refund-rag-active",
                expected_generation_id="G2",
                target_generation_id="G2",
                from_revision=8,
                to_revision=9,
                build_snapshot_fingerprint="sha256:bs",
                manifest_digest="sha256:manifest",
                evaluation_report_checksum="sha256:report",
                committer_id="committer-1",
                committer_fence=52,
                decision=ActivationDecision.APPLIED,
                committed_at="2026-11-11T00:00:00Z",
            )

    def test_read_view_requires_positive_pointer_revision_and_fence(self) -> None:
        with self.assertRaisesRegex(ValueError, "revision and fence"):
            ReadView(
                view_id="RV-1",
                pointer_name="refund-rag-active",
                generation_id="G2",
                pointer_revision=0,
                owner_id="request-1",
                build_snapshot_fingerprint="sha256:bs",
                authorization_snapshot_id="P2",
                status=ReadViewStatus.OPEN,
                fencing_token=1,
                lease_expires_at="2026-11-11T00:01:00Z",
                last_heartbeat_at="2026-11-11T00:00:00Z",
            )

    def test_applied_inbox_requires_complete_durable_result(self) -> None:
        with self.assertRaisesRegex(ValueError, "durable result"):
            InboxRecord(
                event_id="EV-B",
                payload_digest="sha256:payload",
                source_stream="deletion-events",
                state=MessageState.APPLIED,
            )
        with self.assertRaisesRegex(ValueError, "appear together"):
            InboxRecord(
                event_id="EV-B",
                payload_digest="sha256:payload",
                source_stream="deletion-events",
                state=MessageState.PROCESSING,
                result_id="job-1",
            )

    def test_validation_pass_requires_matching_manifest_digests(self) -> None:
        with self.assertRaisesRegex(ValueError, "matching expected"):
            ValidationRecord(
                validation_id="V3",
                generation_id="G3",
                build_snapshot_fingerprint="sha256:bs",
                expected_manifest_digest="sha256:expected",
                actual_manifest_digest="sha256:actual",
                physical_namespace="refund-g3",
                provider_checkpoint="cp17",
                provider_write_fence=42,
                validator_version="validator-v1",
                decision=ValidationDecision.PASS,
                observed_at="2026-11-11T00:00:00Z",
            )

    def test_fingerprints_and_digests_are_stable(self) -> None:
        left_snapshot = _build_snapshot()
        right_snapshot = _build_snapshot()
        left_manifest = GenerationManifest(_facts(), _facts())
        right_manifest = GenerationManifest(_facts(), _facts())
        self.assertEqual(left_snapshot.fingerprint, right_snapshot.fingerprint)
        self.assertEqual(left_manifest.digest, right_manifest.digest)

        left_artifact = GenerationArtifact(
            generation_id="G3",
            scope_id="refund-rag",
            build_snapshot_fingerprint=left_snapshot.fingerprint,
            manifest_digest=left_manifest.digest,
            evaluation_ruler_fingerprint="sha256:ruler",
            validation_record_digest="sha256:validation",
            evaluation_evidence_digest="sha256:evaluation",
            evaluation_report_digest="sha256:R3",
            physical_namespace="refund-g3",
        )
        right_artifact = replace(left_artifact)
        self.assertEqual(left_artifact.fingerprint, right_artifact.fingerprint)


if __name__ == "__main__":
    unittest.main()
