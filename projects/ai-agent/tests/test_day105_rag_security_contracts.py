from __future__ import annotations

from dataclasses import replace
from typing import cast
import unittest

from day105_test_support import (
    build_happy_path,
    classroom_binding,
    classroom_occurrence,
    classroom_policy,
)
from rag_chunking_contracts import stable_hash
from rag_security_contracts import (
    ContentProvenanceSecurityRecord,
    ContextAssemblyManifest,
    DeniedOccurrence,
    EgressSink,
    IncidentState,
    IngestionSecurityDecision,
    ModelInvocationEnvelope,
    OutputReleaseDecision,
    ReleaseEvidence,
    RetrievalSecurityDecision,
    RetrievedContentTrust,
    SecurityDisposition,
    SecurityIncidentRecord,
    SecurityResult,
)


class Day105RagSecurityContractTests(unittest.TestCase):
    def test_every_policy_revision_changes_fingerprint(self) -> None:
        baseline = classroom_policy()
        changes = {
            "security_policy_version": "SP2",
            "parser_version": "parser-v2",
            "scanner_version": "scanner-v2",
            "detector_version": "detector-v2",
            "retrieval_config_version": "retrieval-v2",
            "context_assembler_version": "assembler-v2",
            "prompt_template_version": "prompt-v2",
            "model_policy_version": "model-policy-v2",
            "tool_policy_version": "tool-policy-v2",
            "output_policy_version": "output-policy-v2",
            "adversarial_set_digest": stable_hash("attacks-v2"),
        }
        for field_name, value in changes.items():
            with self.subTest(field_name=field_name):
                changed = replace(baseline, **{field_name: value})
                self.assertNotEqual(baseline.fingerprint, changed.fingerprint)

    def test_occurrence_security_identity_changes_with_content(self) -> None:
        occurrence = classroom_occurrence("A@v1")
        changed = replace(
            occurrence.identity,
            content_digest=stable_hash("A@v2-content"),
        )
        self.assertNotEqual(occurrence.identity.fingerprint, changed.fingerprint)

    def test_content_security_pass_requires_evidence(self) -> None:
        subject = classroom_occurrence("A@v1").identity
        with self.assertRaisesRegex(ValueError, "PASS requires evidence"):
            ContentProvenanceSecurityRecord(
                record_id="record-A",
                subject=subject,
                provenance_verified=True,
                result=SecurityResult.PASS,
                evidence_digests=(),
                reason_codes=(),
                observed_at="2026-11-15T00:00:00+08:00",
            )

    def test_content_security_pass_requires_verified_provenance(self) -> None:
        subject = classroom_occurrence("Y@v1").identity
        with self.assertRaisesRegex(ValueError, "verified provenance"):
            ContentProvenanceSecurityRecord(
                record_id="record-Y",
                subject=subject,
                provenance_verified=False,
                result=SecurityResult.PASS,
                evidence_digests=(stable_hash("scan"),),
                reason_codes=(),
                observed_at="2026-11-15T00:00:00+08:00",
            )

    def test_content_security_fail_requires_observed_evidence(self) -> None:
        subject = classroom_occurrence("X@v1").identity
        with self.assertRaisesRegex(ValueError, "FAIL requires evidence"):
            ContentProvenanceSecurityRecord(
                record_id="record-X",
                subject=subject,
                provenance_verified=True,
                result=SecurityResult.FAIL,
                evidence_digests=(),
                reason_codes=(),
                observed_at="2026-11-15T00:00:00+08:00",
            )

    def test_non_pass_ingestion_cannot_be_eligible(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be eligible"):
            IngestionSecurityDecision(
                decision_id="decision-Y",
                subject_fingerprint=stable_hash("Y"),
                policy_fingerprint=classroom_policy().fingerprint,
                result=SecurityResult.INCONCLUSIVE,
                disposition=SecurityDisposition.ELIGIBLE,
                evidence_digests=(),
                reason_codes=("DETECTOR_TIMEOUT",),
                observed_at="2026-11-15T00:00:00+08:00",
            )

    def test_read_view_revision_and_fence_must_be_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be positive"):
            replace(classroom_binding(), pointer_revision=0)
        with self.assertRaisesRegex(ValueError, "must be positive"):
            replace(classroom_binding(), read_view_fence=0)

    def test_read_view_must_be_open_and_request_owned(self) -> None:
        with self.assertRaisesRegex(ValueError, "validated OPEN ReadView"):
            replace(classroom_binding(), read_view_status="CLOSED")
        with self.assertRaisesRegex(ValueError, "unexpired ReadView"):
            replace(classroom_binding(), read_view_unexpired=False)
        with self.assertRaisesRegex(ValueError, "owned by this request"):
            replace(classroom_binding(), read_view_owner_id="other-request")

    def test_manifest_digest_must_match_exact_entries(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match entries"):
            replace(
                classroom_binding(),
                generation_manifest_digest=stable_hash("forged-manifest"),
            )

    def test_request_binding_requires_security_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires security evidence"):
            replace(classroom_binding(), security_evidence_digests=())

    def test_retrieved_content_cannot_claim_trusted_authority(self) -> None:
        occurrence = classroom_occurrence("X@v1")
        with self.assertRaisesRegex(ValueError, "untrusted data"):
            replace(
                occurrence,
                trust=cast(
                    RetrievedContentTrust,
                    "TRUSTED_INSTRUCTION",
                ),
            )

    def test_retrieval_allow_and_deny_sets_must_be_disjoint(self) -> None:
        with self.assertRaisesRegex(ValueError, "both allowed and denied"):
            RetrievalSecurityDecision(
                decision_id="retrieval",
                request_binding_fingerprint=classroom_binding().fingerprint,
                candidate_set_digest=stable_hash("candidates"),
                result=SecurityResult.PASS,
                allowed_occurrence_ids=("A@v1",),
                denied_occurrences=(DeniedOccurrence("A@v1", "DENY"),),
                evidence_digests=(stable_hash("evidence"),),
                observed_at="2026-11-15T00:00:00+08:00",
            )

    def test_non_pass_retrieval_cannot_release_occurrences(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot release"):
            RetrievalSecurityDecision(
                decision_id="retrieval",
                request_binding_fingerprint=classroom_binding().fingerprint,
                candidate_set_digest=stable_hash("candidates"),
                result=SecurityResult.INCONCLUSIVE,
                allowed_occurrence_ids=("A@v1",),
                denied_occurrences=(),
                evidence_digests=(),
                observed_at="2026-11-15T00:00:00+08:00",
            )

    def test_context_manifest_rejects_included_excluded_overlap(self) -> None:
        happy = build_happy_path()
        with self.assertRaisesRegex(ValueError, "must be disjoint"):
            replace(
                happy.context,
                excluded_occurrence_ids=("A@v1",),
            )

    def test_context_manifest_enforces_budget(self) -> None:
        happy = build_happy_path()
        with self.assertRaisesRegex(ValueError, "fit the positive budget"):
            replace(
                happy.context,
                context_budget=1,
                actual_context_units=2,
            )

    def test_disclosure_budget_cannot_exceed_allowed_fields(self) -> None:
        happy = build_happy_path()
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            replace(happy.disclosure, disclosure_budget=3)

    def test_model_envelope_rejects_secrets(self) -> None:
        happy = build_happy_path()
        with self.assertRaisesRegex(ValueError, "secrets cannot enter"):
            replace(happy.invocation, secret_count=1)

    def test_model_envelope_requires_untrusted_retrieved_data(self) -> None:
        happy = build_happy_path()
        with self.assertRaisesRegex(ValueError, "untrusted data"):
            replace(
                happy.invocation,
                retrieved_content_trust=cast(
                    RetrievedContentTrust,
                    "TRUSTED_INSTRUCTION",
                ),
            )
        self.assertIs(
            happy.invocation.retrieved_content_trust,
            RetrievedContentTrust.UNTRUSTED_DATA,
        )

    def test_pass_release_cannot_have_failure_reasons(self) -> None:
        happy = build_happy_path()
        with self.assertRaisesRegex(ValueError, "failure reasons"):
            OutputReleaseDecision(
                decision_id="release-Q3",
                request_binding_fingerprint=happy.binding.fingerprint,
                candidate_digest=happy.candidate.digest,
                disclosure_envelope_digest=happy.disclosure.digest,
                release_evidence_digest=stable_hash("release-evidence"),
                result=SecurityResult.PASS,
                disposition=SecurityDisposition.RELEASE,
                reason_codes=("SHOULD_NOT_EXIST",),
                released_citation_occurrence_ids=("A@v1", "C@v1"),
                observed_at="2026-11-15T00:00:00+08:00",
            )

    def test_non_pass_output_cannot_release(self) -> None:
        happy = build_happy_path()
        with self.assertRaisesRegex(ValueError, "cannot RELEASE"):
            OutputReleaseDecision(
                decision_id="release-Q3",
                request_binding_fingerprint=happy.binding.fingerprint,
                candidate_digest=happy.candidate.digest,
                disclosure_envelope_digest=happy.disclosure.digest,
                release_evidence_digest=stable_hash("release-evidence"),
                result=SecurityResult.FAIL,
                disposition=SecurityDisposition.RELEASE,
                reason_codes=("DLP_FAILED",),
                released_citation_occurrence_ids=(),
                observed_at="2026-11-15T00:00:00+08:00",
            )

    def test_observed_release_checks_require_evidence(self) -> None:
        happy = build_happy_path()
        with self.assertRaisesRegex(ValueError, "require evidence"):
            ReleaseEvidence(
                evidence_id="release-evidence-empty",
                candidate_digest=happy.candidate.digest,
                observed_claim_ids=("application_channel", "refund_window"),
                unclassified_claim_count=0,
                grounded_claim_ids=("application_channel", "refund_window"),
                supported_citation_keys=(
                    "application_channel:C@v1",
                    "refund_window:A@v1",
                ),
                current_authorization_revision=(happy.binding.authorization_revision),
                currently_authorized_occurrence_ids=("A@v1", "C@v1"),
                current_provenance_revision=(happy.binding.provenance_revision),
                current_tombstone_revision=happy.binding.tombstone_revision,
                current_content_security_snapshot_digest=(
                    happy.binding.content_security_snapshot_digest
                ),
                current_security_policy_fingerprint=(happy.binding.policy.fingerprint),
                dlp_result=SecurityResult.PASS,
                metadata_stripping_result=SecurityResult.PASS,
                destination_result=SecurityResult.PASS,
                evidence_digests=(),
            )

    def test_incident_record_rejects_raw_secret(self) -> None:
        with self.assertRaisesRegex(ValueError, "raw secrets"):
            SecurityIncidentRecord(
                incident_record_id="incident-record-1",
                incident_id="incident-1",
                previous_record_id=None,
                state=IncidentState.OPEN,
                affected_request_ids=("request-Q3",),
                affected_generation_ids=("G2",),
                affected_occurrence_ids=("X@v1",),
                affected_sinks=(EgressSink.EXTERNAL_DESTINATION,),
                containment_actions=("QUARANTINE_X",),
                evidence_digests=(stable_hash("incident-evidence"),),
                credential_rotation_status="PENDING",
                impact_analysis_digest=stable_hash("impact-pending"),
                actor_id="security-control-plane",
                observed_at="2026-11-15T00:00:00+08:00",
                raw_secret_logged=True,
            )

    def test_incident_cannot_supersede_itself(self) -> None:
        with self.assertRaisesRegex(ValueError, "supersede itself"):
            SecurityIncidentRecord(
                incident_record_id="incident-record-1",
                incident_id="incident-1",
                previous_record_id="incident-record-1",
                state=IncidentState.CONTAINED,
                affected_request_ids=("request-Q3",),
                affected_generation_ids=("G2",),
                affected_occurrence_ids=("X@v1",),
                affected_sinks=(EgressSink.RESPONSE,),
                containment_actions=("BLOCK_RESPONSE",),
                evidence_digests=(stable_hash("incident-evidence"),),
                credential_rotation_status="NOT_REQUIRED",
                impact_analysis_digest=stable_hash("impact"),
                actor_id="security-control-plane",
                observed_at="2026-11-15T00:00:00+08:00",
            )


if __name__ == "__main__":
    unittest.main()
