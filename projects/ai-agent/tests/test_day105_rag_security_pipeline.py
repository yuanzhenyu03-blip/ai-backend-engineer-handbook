from __future__ import annotations

from dataclasses import replace
from typing import Any
import unittest

from day105_test_support import (
    HappyPath,
    build_happy_path,
    classroom_binding,
    classroom_occurrence,
    classroom_policy,
)
from rag_chunking_contracts import stable_hash
from rag_security_contracts import (
    AnswerCandidate,
    ContentProvenanceSecurityRecord,
    EgressSink,
    IncidentState,
    ProposedCitation,
    ReleaseEvidence,
    SecurityCaseObservation,
    SecurityDisposition,
    SecurityIncidentRecord,
    SecurityResult,
)
from rag_security_pipeline import (
    InMemorySecurityIncidentLedger,
    RagSecurityPipeline,
    SecurityGateRejected,
    SecurityIdentityConflict,
)


def passing_release_evidence(
    happy: HappyPath,
    **changes: object,
) -> ReleaseEvidence:
    values: dict[str, Any] = {
        "evidence_id": "release-evidence-Q3",
        "candidate_digest": happy.candidate.digest,
        "observed_claim_ids": ("application_channel", "refund_window"),
        "unclassified_claim_count": 0,
        "grounded_claim_ids": ("application_channel", "refund_window"),
        "supported_citation_keys": (
            "application_channel:C@v1",
            "refund_window:A@v1",
        ),
        "current_authorization_revision": (happy.binding.authorization_revision),
        "currently_authorized_occurrence_ids": ("A@v1", "C@v1"),
        "current_provenance_revision": happy.binding.provenance_revision,
        "current_tombstone_revision": happy.binding.tombstone_revision,
        "current_content_security_snapshot_digest": (
            happy.binding.content_security_snapshot_digest
        ),
        "current_security_policy_fingerprint": (happy.binding.policy.fingerprint),
        "dlp_result": SecurityResult.PASS,
        "metadata_stripping_result": SecurityResult.PASS,
        "destination_result": SecurityResult.PASS,
        "evidence_digests": (stable_hash("release-checks-Q3"),),
    }
    values.update(changes)
    return ReleaseEvidence(**values)


def safe_case(case_id: str = "Q1-normal") -> SecurityCaseObservation:
    return SecurityCaseObservation(
        case_id=case_id,
        critical=True,
        evaluator_result=SecurityResult.PASS,
        attack_document_retrieved=False,
        unauthorized_entered_prompt=False,
        cross_tenant_disclosure=False,
        tombstone_resurrection=False,
        sensitive_output_violation=False,
        protected_metadata_disclosure=False,
        attack_succeeded=False,
        unsafe_rollback_activated=False,
        citations_exact=True,
        normal_quality_passed=True,
    )


class Day105IngestionAndRetrievalTests(unittest.TestCase):
    def _record(
        self,
        *,
        occurrence_id: str = "A@v1",
        result: SecurityResult = SecurityResult.PASS,
        provenance_verified: bool = True,
        reason_codes: tuple[str, ...] = (),
    ) -> ContentProvenanceSecurityRecord:
        subject = classroom_occurrence(occurrence_id).identity
        evidence = (
            ()
            if result is SecurityResult.NOT_RUN
            else (stable_hash((occurrence_id, result.value)),)
        )
        return ContentProvenanceSecurityRecord(
            record_id=f"record-{occurrence_id}-{result.value}",
            subject=subject,
            provenance_verified=provenance_verified,
            result=result,
            evidence_digests=evidence,
            reason_codes=tuple(sorted(reason_codes)),
            observed_at="2026-11-15T00:00:00+08:00",
        )

    def test_ingestion_pass_is_eligible(self) -> None:
        decision = RagSecurityPipeline.decide_ingestion(
            decision_id="ingestion-A",
            record=self._record(),
            policy=classroom_policy(),
            observed_at="2026-11-15T00:01:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.PASS)
        self.assertIs(decision.disposition, SecurityDisposition.ELIGIBLE)

    def test_detector_timeout_is_inconclusive_and_quarantined(self) -> None:
        decision = RagSecurityPipeline.decide_ingestion(
            decision_id="ingestion-Y",
            record=self._record(
                occurrence_id="Y@v1",
                result=SecurityResult.INCONCLUSIVE,
                reason_codes=("DETECTOR_TIMEOUT",),
            ),
            policy=classroom_policy(),
            observed_at="2026-11-15T00:01:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.INCONCLUSIVE)
        self.assertIs(decision.disposition, SecurityDisposition.QUARANTINE)

    def test_detector_version_drift_is_inconclusive_not_fail(self) -> None:
        decision = RagSecurityPipeline.decide_ingestion(
            decision_id="ingestion-Y",
            record=self._record(occurrence_id="Y@v1"),
            policy=classroom_policy(detector_version="detector-v2"),
            observed_at="2026-11-15T00:01:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.INCONCLUSIVE)
        self.assertIn(
            "STALE_OR_INCOMPATIBLE_SECURITY_EVIDENCE",
            decision.reason_codes,
        )

    def test_observed_attack_is_fail_and_quarantined(self) -> None:
        decision = RagSecurityPipeline.decide_ingestion(
            decision_id="ingestion-X",
            record=self._record(
                occurrence_id="X@v1",
                result=SecurityResult.FAIL,
                reason_codes=("DOCUMENT_PROMPT_INJECTION",),
            ),
            policy=classroom_policy(),
            observed_at="2026-11-15T00:01:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertIs(decision.disposition, SecurityDisposition.QUARANTINE)

    def test_retrieval_filters_tombstone_quarantine_and_other_tenant(self) -> None:
        binding = classroom_binding(
            generation_id="GX",
            manifest_occurrence_ids=(
                "A@v1",
                "B@v1",
                "C@v1",
                "T@v1",
                "X@v1",
            ),
            manifest_tenant_overrides=(("T@v1", "tenant-private"),),
        )
        candidates = (
            classroom_occurrence("A@v1", binding=binding),
            classroom_occurrence("B@v1", binding=binding, tombstoned=True),
            classroom_occurrence("C@v1", binding=binding),
            classroom_occurrence("X@v1", binding=binding, quarantined=True),
            classroom_occurrence("T@v1", binding=binding, tenant_id="tenant-private"),
        )
        decision = RagSecurityPipeline.decide_retrieval(
            decision_id="retrieval-Q3",
            binding=binding,
            candidates=candidates,
            least_context_occurrence_ids=("A@v1", "C@v1"),
            observed_at="2026-11-15T00:02:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.PASS)
        self.assertEqual(
            decision.allowed_occurrence_ids,
            ("A@v1", "C@v1"),
        )
        reasons = {
            item.occurrence_id: item.reason_code for item in decision.denied_occurrences
        }
        self.assertEqual(reasons["B@v1"], "TOMBSTONED")
        self.assertEqual(reasons["X@v1"], "CONTENT_QUARANTINED")
        self.assertEqual(reasons["T@v1"], "TENANT_UNAUTHORIZED")

    def test_g2_rejects_provider_candidates_outside_sealed_manifest(self) -> None:
        binding = classroom_binding()
        candidates = (
            classroom_occurrence("A@v1", binding=binding),
            classroom_occurrence("B@v1", binding=binding, tombstoned=True),
            classroom_occurrence("C@v1", binding=binding),
            classroom_occurrence("X@v1", binding=binding),
            classroom_occurrence(
                "T@v1",
                binding=binding,
                tenant_id="tenant-private",
            ),
        )
        decision = RagSecurityPipeline.decide_retrieval(
            decision_id="retrieval-corrupt-G2-readback",
            binding=binding,
            candidates=candidates,
            least_context_occurrence_ids=("A@v1", "C@v1"),
            observed_at="2026-11-15T00:02:00+08:00",
        )
        reasons = {
            item.occurrence_id: item.reason_code for item in decision.denied_occurrences
        }
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertEqual(decision.allowed_occurrence_ids, ())
        self.assertEqual(reasons["B@v1"], "NOT_IN_SEALED_MANIFEST")
        self.assertEqual(reasons["X@v1"], "NOT_IN_SEALED_MANIFEST")
        self.assertEqual(reasons["T@v1"], "NOT_IN_SEALED_MANIFEST")

    def test_manifest_content_substitution_is_fail(self) -> None:
        binding = classroom_binding()
        original = classroom_occurrence("A@v1", binding=binding)
        substituted = replace(
            original,
            identity=replace(
                original.identity,
                content_digest=stable_hash("substituted-A-content"),
            ),
        )
        decision = RagSecurityPipeline.decide_retrieval(
            decision_id="retrieval-substituted-A",
            binding=binding,
            candidates=(substituted,),
            least_context_occurrence_ids=("A@v1",),
            observed_at="2026-11-15T00:02:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertEqual(decision.allowed_occurrence_ids, ())
        self.assertEqual(
            decision.denied_occurrences[0].reason_code,
            "MANIFEST_ENTRY_MISMATCH",
        )

    def test_manifest_resource_substitution_is_fail(self) -> None:
        binding = classroom_binding()
        original = classroom_occurrence("A@v1", binding=binding)
        substituted = replace(
            original,
            identity=replace(
                original.identity,
                resource_id="different-resource-A",
            ),
        )
        decision = RagSecurityPipeline.decide_retrieval(
            decision_id="retrieval-resource-substitution-A",
            binding=binding,
            candidates=(substituted,),
            least_context_occurrence_ids=("A@v1",),
            observed_at="2026-11-15T00:02:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertEqual(
            decision.denied_occurrences[0].reason_code,
            "MANIFEST_ENTRY_MISMATCH",
        )

    def test_manifest_metadata_version_substitution_is_fail(self) -> None:
        binding = classroom_binding()
        original = classroom_occurrence("A@v1", binding=binding)
        substituted = replace(
            original,
            identity=replace(
                original.identity,
                metadata_version="metadata-v2",
            ),
        )
        decision = RagSecurityPipeline.decide_retrieval(
            decision_id="retrieval-metadata-version-substitution-A",
            binding=binding,
            candidates=(substituted,),
            least_context_occurrence_ids=("A@v1",),
            observed_at="2026-11-15T00:02:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertEqual(
            decision.denied_occurrences[0].reason_code,
            "MANIFEST_ENTRY_MISMATCH",
        )

    def test_required_unknown_security_evidence_is_inconclusive(self) -> None:
        binding = classroom_binding()
        candidate = classroom_occurrence(
            "A@v1",
            binding=binding,
            content_security_result=SecurityResult.INCONCLUSIVE,
        )
        decision = RagSecurityPipeline.decide_retrieval(
            decision_id="retrieval-Q1",
            binding=binding,
            candidates=(candidate,),
            least_context_occurrence_ids=("A@v1",),
            observed_at="2026-11-15T00:02:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.INCONCLUSIVE)
        self.assertEqual(decision.allowed_occurrence_ids, ())

    def test_required_stale_detector_identity_is_inconclusive(self) -> None:
        binding = classroom_binding(
            policy=classroom_policy(detector_version="detector-v2")
        )
        stale = classroom_occurrence(
            "A@v1",
            binding=classroom_binding(),
        )
        decision = RagSecurityPipeline.decide_retrieval(
            decision_id="retrieval-Q1",
            binding=binding,
            candidates=(stale,),
            least_context_occurrence_ids=("A@v1",),
            observed_at="2026-11-15T00:02:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.INCONCLUSIVE)
        self.assertEqual(decision.allowed_occurrence_ids, ())

    def test_q1_least_context_excludes_authorized_c(self) -> None:
        binding = classroom_binding()
        candidates = (
            classroom_occurrence("A@v1", binding=binding),
            classroom_occurrence("C@v1", binding=binding),
        )
        decision = RagSecurityPipeline.decide_retrieval(
            decision_id="retrieval-Q1",
            binding=binding,
            candidates=candidates,
            least_context_occurrence_ids=("A@v1",),
            observed_at="2026-11-15T00:02:00+08:00",
        )
        self.assertEqual(decision.allowed_occurrence_ids, ("A@v1",))
        self.assertEqual(
            decision.denied_occurrences[0].reason_code,
            "OUTSIDE_LEAST_CONTEXT",
        )

    def test_authorized_malicious_x_reaches_bundle_analysis_not_authority(self) -> None:
        binding = classroom_binding(
            generation_id="GX",
            manifest_occurrence_ids=("X@v1",),
        )
        x = classroom_occurrence(
            "X@v1",
            binding=binding,
            attack_tags=("DOCUMENT_INSTRUCTION_OVERRIDE",),
        )
        retrieval = RagSecurityPipeline.decide_retrieval(
            decision_id="retrieval-X",
            binding=binding,
            candidates=(x,),
            least_context_occurrence_ids=("X@v1",),
            observed_at="2026-11-15T00:02:00+08:00",
        )
        self.assertIs(retrieval.result, SecurityResult.PASS)
        bundle = RagSecurityPipeline.analyze_bundle(
            decision_id="bundle-X",
            binding=binding,
            retrieval_decision=retrieval,
            candidates=(x,),
        )
        self.assertIs(bundle.result, SecurityResult.FAIL)
        self.assertIn("DOCUMENT_PROMPT_INJECTION", bundle.reason_codes)

    def test_cross_document_chain_fails_bundle_analysis(self) -> None:
        binding = classroom_binding(
            generation_id="GZ",
            manifest_occurrence_ids=("Z1@v1", "Z2@v1"),
        )
        candidates = (
            classroom_occurrence(
                "Z1@v1",
                binding=binding,
                attack_tags=("CHAIN_READ_NEXT",),
            ),
            classroom_occurrence(
                "Z2@v1",
                binding=binding,
                attack_tags=("CHAIN_EXECUTE_HIDDEN",),
            ),
        )
        retrieval = RagSecurityPipeline.decide_retrieval(
            decision_id="retrieval-Z",
            binding=binding,
            candidates=candidates,
            least_context_occurrence_ids=("Z1@v1", "Z2@v1"),
            observed_at="2026-11-15T00:02:00+08:00",
        )
        bundle = RagSecurityPipeline.analyze_bundle(
            decision_id="bundle-Z",
            binding=binding,
            retrieval_decision=retrieval,
            candidates=candidates,
        )
        self.assertIs(bundle.result, SecurityResult.FAIL)
        self.assertIn("CROSS_DOCUMENT_ATTACK_CHAIN", bundle.reason_codes)


class Day105ContextAndReleaseTests(unittest.TestCase):
    def test_non_pass_bundle_cannot_cross_context_boundary(self) -> None:
        binding = classroom_binding(
            generation_id="GX",
            manifest_occurrence_ids=("X@v1",),
        )
        x = classroom_occurrence(
            "X@v1",
            binding=binding,
            attack_tags=("EXFILTRATE_CONTEXT",),
        )
        retrieval = RagSecurityPipeline.decide_retrieval(
            decision_id="retrieval-X",
            binding=binding,
            candidates=(x,),
            least_context_occurrence_ids=("X@v1",),
            observed_at="2026-11-15T00:02:00+08:00",
        )
        bundle_security = RagSecurityPipeline.analyze_bundle(
            decision_id="bundle-X",
            binding=binding,
            retrieval_decision=retrieval,
            candidates=(x,),
        )
        with self.assertRaisesRegex(SecurityGateRejected, "PASS decisions"):
            RagSecurityPipeline.build_retrieval_bundle(
                bundle_id="bundle-X",
                binding=binding,
                retrieval_decision=retrieval,
                bundle_decision=bundle_security,
                candidates=(x,),
                created_at="2026-11-15T00:03:00+08:00",
            )

    def test_bundle_analysis_rejects_post_decision_tag_substitution(self) -> None:
        happy = build_happy_path()
        substituted = (
            replace(
                happy.occurrences[0],
                attack_tags=("EXFILTRATE_CONTEXT",),
            ),
            happy.occurrences[1],
        )
        with self.assertRaisesRegex(
            SecurityIdentityConflict,
            "candidates changed",
        ):
            RagSecurityPipeline.analyze_bundle(
                decision_id="bundle-substituted-tags",
                binding=happy.binding,
                retrieval_decision=happy.retrieval,
                candidates=substituted,
            )

    def test_bundle_build_rejects_post_analysis_content_substitution(self) -> None:
        happy = build_happy_path()
        substituted_a = replace(
            happy.occurrences[0],
            identity=replace(
                happy.occurrences[0].identity,
                content_digest=stable_hash("post-analysis-substitution"),
            ),
        )
        with self.assertRaisesRegex(
            SecurityIdentityConflict,
            "candidates changed",
        ):
            RagSecurityPipeline.build_retrieval_bundle(
                bundle_id="bundle-substituted-content",
                binding=happy.binding,
                retrieval_decision=happy.retrieval,
                bundle_decision=happy.bundle_security,
                candidates=(substituted_a, happy.occurrences[1]),
                created_at="2026-11-15T00:03:00+08:00",
            )

    def test_bundle_cannot_be_reused_across_read_views(self) -> None:
        happy = build_happy_path()
        changed = classroom_binding(generation_id="G3", pointer_revision=9)
        with self.assertRaisesRegex(SecurityIdentityConflict, "binding changed"):
            RagSecurityPipeline.assemble_context(
                manifest_id="context-G3",
                binding=changed,
                bundle=happy.bundle,
                included_occurrence_ids=("A@v1", "C@v1"),
                context_budget=2,
                actual_context_units=2,
                envelope_schema_version="untrusted-evidence-v1",
                serialization_version="json-escaped-v1",
                projection_version="least-fields-v1",
                structured_untrusted_data_digest=stable_hash("structured-context-G3"),
            )

    def test_context_cannot_add_occurrence_outside_allowed_bundle(self) -> None:
        happy = build_happy_path()
        with self.assertRaisesRegex(SecurityGateRejected, "allowed bundle IDs"):
            RagSecurityPipeline.assemble_context(
                manifest_id="context-with-T",
                binding=happy.binding,
                bundle=happy.bundle,
                included_occurrence_ids=("A@v1", "C@v1", "T@v1"),
                context_budget=3,
                actual_context_units=3,
                envelope_schema_version="untrusted-evidence-v1",
                serialization_version="json-escaped-v1",
                projection_version="least-fields-v1",
                structured_untrusted_data_digest=stable_hash(
                    "structured-context-with-T"
                ),
            )

    def test_context_receipt_binds_actual_projected_data(self) -> None:
        happy = build_happy_path()
        changed = RagSecurityPipeline.assemble_context(
            manifest_id="context-Q3-different-projection",
            binding=happy.binding,
            bundle=happy.bundle,
            included_occurrence_ids=("A@v1", "C@v1"),
            context_budget=2,
            actual_context_units=2,
            envelope_schema_version="untrusted-evidence-v1",
            serialization_version="json-escaped-v1",
            projection_version="least-fields-v1",
            structured_untrusted_data_digest=stable_hash(
                "different-structured-projection"
            ),
        )
        self.assertNotEqual(
            happy.context.assembled_context_digest,
            changed.assembled_context_digest,
        )

    def test_context_receipt_rejects_unbound_projection_change(self) -> None:
        happy = build_happy_path()
        with self.assertRaisesRegex(
            ValueError,
            "does not match projection",
        ):
            replace(
                happy.context,
                structured_untrusted_data_digest=stable_hash(
                    "forged-structured-projection"
                ),
            )

    def test_model_envelope_rejects_forged_template_identity(self) -> None:
        happy = build_happy_path()
        forged = replace(happy.context, prompt_template_version="prompt-v2")
        with self.assertRaisesRegex(
            SecurityIdentityConflict,
            "context assembly identity changed",
        ):
            RagSecurityPipeline.build_model_envelope(
                envelope_id="invocation-forged",
                binding=happy.binding,
                context_manifest=forged,
                disclosure=happy.disclosure,
                system_policy_digest=stable_hash("system-policy"),
                model_id="controlled-model-v1",
                model_config_digest=stable_hash("model-config"),
            )

    def test_model_envelope_rejects_expanded_disclosure_purpose(self) -> None:
        happy = build_happy_path()
        forged = replace(happy.disclosure, purpose="export-all-context")
        with self.assertRaisesRegex(
            SecurityIdentityConflict,
            "disclosure purpose changed",
        ):
            RagSecurityPipeline.build_model_envelope(
                envelope_id="invocation-forged-purpose",
                binding=happy.binding,
                context_manifest=happy.context,
                disclosure=forged,
                system_policy_digest=stable_hash("system-policy"),
                model_id="controlled-model-v1",
                model_config_digest=stable_hash("model-config"),
            )

    def test_happy_q3_candidate_releases_exact_citations(self) -> None:
        happy = build_happy_path()
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-Q3",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=happy.candidate,
            evidence=passing_release_evidence(happy),
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.PASS)
        self.assertIs(decision.disposition, SecurityDisposition.RELEASE)
        self.assertEqual(
            decision.released_citation_occurrence_ids,
            ("A@v1", "C@v1"),
        )

    def test_cross_invocation_candidate_substitution_is_rejected(self) -> None:
        happy = build_happy_path()
        foreign = replace(
            happy.candidate,
            invocation_envelope_digest=stable_hash("foreign-invocation"),
        )
        evidence = passing_release_evidence(
            happy,
            candidate_digest=foreign.digest,
        )
        with self.assertRaisesRegex(
            SecurityIdentityConflict,
            "another invocation",
        ):
            RagSecurityPipeline.decide_output_release(
                decision_id="release-foreign",
                binding=happy.binding,
                context_manifest=happy.context,
                disclosure=happy.disclosure,
                model_envelope=happy.invocation,
                candidate=foreign,
                evidence=evidence,
                observed_at="2026-11-15T00:04:00+08:00",
            )

    def test_current_authorization_revocation_blocks_release(self) -> None:
        happy = build_happy_path()
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-revoked",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=happy.candidate,
            evidence=passing_release_evidence(
                happy,
                current_authorization_revision="AUTH-R2-REVOKED",
            ),
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertIs(decision.disposition, SecurityDisposition.BLOCKED)
        self.assertIn(
            "CURRENT_AUTHORIZATION_CHANGED",
            decision.reason_codes,
        )

    def test_current_citation_authorization_recheck_blocks_release(self) -> None:
        happy = build_happy_path()
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-citation-authorization-denied",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=happy.candidate,
            evidence=passing_release_evidence(
                happy,
                currently_authorized_occurrence_ids=("C@v1",),
            ),
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertIs(decision.disposition, SecurityDisposition.BLOCKED)
        self.assertIn(
            "CURRENT_CITATION_AUTHORIZATION_DENIED",
            decision.reason_codes,
        )

    def test_current_quarantine_snapshot_change_blocks_release(self) -> None:
        happy = build_happy_path()
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-quarantine-changed",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=happy.candidate,
            evidence=passing_release_evidence(
                happy,
                current_content_security_snapshot_digest=stable_hash(
                    "snapshot-after-quarantine"
                ),
            ),
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertIn(
            "CURRENT_CONTENT_SECURITY_SNAPSHOT_CHANGED",
            decision.reason_codes,
        )

    def test_current_security_policy_change_blocks_release(self) -> None:
        happy = build_happy_path()
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-policy-changed",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=happy.candidate,
            evidence=passing_release_evidence(
                happy,
                current_security_policy_fingerprint=classroom_policy(
                    security_policy_version="SP2"
                ).fingerprint,
            ),
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertIn(
            "CURRENT_SECURITY_POLICY_CHANGED",
            decision.reason_codes,
        )

    def test_hidden_extra_claim_cannot_bypass_disclosure_policy(self) -> None:
        happy = build_happy_path()
        candidate = replace(
            happy.candidate,
            answer_digest=stable_hash("candidate-with-hidden-extra-claim"),
        )
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-hidden-extra-claim",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=candidate,
            evidence=passing_release_evidence(
                happy,
                candidate_digest=candidate.digest,
                observed_claim_ids=(
                    "application_channel",
                    "internal_risk_score",
                    "refund_window",
                ),
                grounded_claim_ids=(
                    "application_channel",
                    "internal_risk_score",
                    "refund_window",
                ),
            ),
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertIn(
            "OUTPUT_CLAIM_MANIFEST_MISMATCH",
            decision.reason_codes,
        )
        self.assertIn(
            "DISCLOSURE_FIELD_NOT_ALLOWED",
            decision.reason_codes,
        )

    def test_dlp_timeout_is_inconclusive_and_blocked(self) -> None:
        happy = build_happy_path()
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-dlp-timeout",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=happy.candidate,
            evidence=passing_release_evidence(
                happy,
                dlp_result=SecurityResult.INCONCLUSIVE,
            ),
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.INCONCLUSIVE)
        self.assertIs(decision.disposition, SecurityDisposition.BLOCKED)

    def test_observed_metadata_leak_overrides_dlp_unknown(self) -> None:
        happy = build_happy_path()
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-metadata-leak",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=happy.candidate,
            evidence=passing_release_evidence(
                happy,
                dlp_result=SecurityResult.INCONCLUSIVE,
                metadata_stripping_result=SecurityResult.FAIL,
            ),
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertIn("DLP_EVIDENCE_UNAVAILABLE", decision.reason_codes)
        self.assertIn("METADATA_STRIPPING_FAILED", decision.reason_codes)

    def test_correct_body_without_citation_fails_release(self) -> None:
        happy = build_happy_path()
        candidate = replace(happy.candidate, proposed_citations=())
        evidence = passing_release_evidence(
            happy,
            candidate_digest=candidate.digest,
        )
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-no-citations",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=candidate,
            evidence=evidence,
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertIn("CLAIM_MISSING_CITATION", decision.reason_codes)

    def test_wrong_but_authorized_citation_fails_exact_support(self) -> None:
        happy = build_happy_path()
        candidate = replace(
            happy.candidate,
            proposed_citations=(
                ProposedCitation("application_channel", "A@v1"),
                ProposedCitation("refund_window", "A@v1"),
            ),
        )
        evidence = passing_release_evidence(
            happy,
            candidate_digest=candidate.digest,
        )
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-wrong-citation",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=candidate,
            evidence=evidence,
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertIn(
            "CITATION_NOT_EXACTLY_SUPPORTED",
            decision.reason_codes,
        )

    def test_sensitive_marker_blocks_release_even_after_model_refusal_seam(
        self,
    ) -> None:
        happy = build_happy_path()
        candidate = replace(
            happy.candidate,
            sensitive_markers=("SYSTEM_PROMPT_MARKER",),
        )
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-sensitive",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=candidate,
            evidence=passing_release_evidence(
                happy,
                candidate_digest=candidate.digest,
            ),
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertIn("SENSITIVE_OUTPUT_DETECTED", decision.reason_codes)

    def test_retrieved_tool_instruction_cannot_execute(self) -> None:
        happy = build_happy_path()
        candidate = replace(
            happy.candidate,
            proposed_tool_calls=("refund:external:10000",),
        )
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-tool-call",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=candidate,
            evidence=passing_release_evidence(
                happy,
                candidate_digest=candidate.digest,
            ),
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.FAIL)
        self.assertIn("TOOL_CALL_NOT_ADMITTED", decision.reason_codes)

    def test_empty_grounded_candidate_safely_abstains(self) -> None:
        happy = build_happy_path()
        candidate = AnswerCandidate(
            candidate_id="candidate-abstain",
            invocation_envelope_digest=happy.invocation.digest,
            answer_digest=stable_hash("safe-abstention"),
            claim_ids=(),
            proposed_citations=(),
            proposed_tool_calls=(),
            sensitive_markers=(),
            generated_at="2026-11-15T00:04:00+08:00",
        )
        evidence = ReleaseEvidence(
            evidence_id="release-evidence-abstain",
            candidate_digest=candidate.digest,
            observed_claim_ids=(),
            unclassified_claim_count=0,
            grounded_claim_ids=(),
            supported_citation_keys=(),
            current_authorization_revision=(happy.binding.authorization_revision),
            currently_authorized_occurrence_ids=(),
            current_provenance_revision=happy.binding.provenance_revision,
            current_tombstone_revision=happy.binding.tombstone_revision,
            current_content_security_snapshot_digest=(
                happy.binding.content_security_snapshot_digest
            ),
            current_security_policy_fingerprint=(happy.binding.policy.fingerprint),
            dlp_result=SecurityResult.PASS,
            metadata_stripping_result=SecurityResult.PASS,
            destination_result=SecurityResult.PASS,
            evidence_digests=(stable_hash("abstention-evidence"),),
        )
        decision = RagSecurityPipeline.decide_output_release(
            decision_id="release-abstain",
            binding=happy.binding,
            context_manifest=happy.context,
            disclosure=happy.disclosure,
            model_envelope=happy.invocation,
            candidate=candidate,
            evidence=evidence,
            observed_at="2026-11-15T00:04:00+08:00",
        )
        self.assertIs(decision.result, SecurityResult.PASS)
        self.assertIs(decision.disposition, SecurityDisposition.ABSTAIN)

    def test_cache_identity_changes_on_authorization_revision(self) -> None:
        happy = build_happy_path()
        baseline = RagSecurityPipeline.cache_identity(
            binding=happy.binding,
            disclosure=happy.disclosure,
            occurrence_ids=happy.bundle.occurrence_ids,
            content_digests=happy.bundle.content_digests,
        )
        changed_binding = classroom_binding(authorization_revision="AUTH-R2-REVOKED")
        changed_disclosure = replace(
            happy.disclosure,
            request_binding_fingerprint=changed_binding.fingerprint,
            authorization_revision=changed_binding.authorization_revision,
        )
        changed = RagSecurityPipeline.cache_identity(
            binding=changed_binding,
            disclosure=changed_disclosure,
            occurrence_ids=happy.bundle.occurrence_ids,
            content_digests=happy.bundle.content_digests,
        )
        self.assertNotEqual(baseline, changed)

    def test_cache_identity_changes_on_generation_and_policy(self) -> None:
        happy = build_happy_path()
        baseline = RagSecurityPipeline.cache_identity(
            binding=happy.binding,
            disclosure=happy.disclosure,
            occurrence_ids=happy.bundle.occurrence_ids,
            content_digests=happy.bundle.content_digests,
        )
        changed_binding = classroom_binding(
            policy=classroom_policy(security_policy_version="SP2"),
            generation_id="G3",
            pointer_revision=9,
        )
        changed_disclosure = replace(
            happy.disclosure,
            request_binding_fingerprint=changed_binding.fingerprint,
        )
        changed = RagSecurityPipeline.cache_identity(
            binding=changed_binding,
            disclosure=changed_disclosure,
            occurrence_ids=happy.bundle.occurrence_ids,
            content_digests=happy.bundle.content_digests,
        )
        self.assertNotEqual(baseline, changed)


class Day105EvaluationAndIncidentTests(unittest.TestCase):
    def test_all_security_and_quality_hard_gates_pass(self) -> None:
        report = RagSecurityPipeline.evaluate_security_cases(
            report_id="day105-eval-pass",
            policy=classroom_policy(),
            cases=(safe_case("Q1"), safe_case("Q2"), safe_case("Q3")),
            evidence_level=("EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"),
            not_run_boundaries=("PRODUCTION",),
        )
        self.assertIs(report.result, SecurityResult.PASS)
        self.assertTrue(report.checksum.startswith("sha256:"))

    def test_reject_all_is_fail_not_security_pass(self) -> None:
        overblocked = replace(
            safe_case("Q1-overblocked"),
            normal_quality_passed=False,
            evaluator_result=SecurityResult.FAIL,
        )
        report = RagSecurityPipeline.evaluate_security_cases(
            report_id="day105-eval-overblocked",
            policy=classroom_policy(),
            cases=(overblocked,),
            evidence_level=("EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"),
            not_run_boundaries=("PRODUCTION",),
        )
        gates = dict(report.hard_gate_results)
        self.assertIs(report.result, SecurityResult.FAIL)
        self.assertIs(
            gates["normal_quality_preserved"],
            SecurityResult.FAIL,
        )
        self.assertIs(
            gates["cross_tenant_leakage_zero"],
            SecurityResult.PASS,
        )

    def test_evaluator_timeout_is_inconclusive(self) -> None:
        timeout = replace(
            safe_case("detector-timeout"),
            evaluator_result=SecurityResult.INCONCLUSIVE,
        )
        report = RagSecurityPipeline.evaluate_security_cases(
            report_id="day105-eval-timeout",
            policy=classroom_policy(),
            cases=(timeout,),
            evidence_level=("EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"),
            not_run_boundaries=("PRODUCTION",),
        )
        self.assertIs(report.result, SecurityResult.INCONCLUSIVE)

    def test_observed_violation_overrides_inconclusive_case(self) -> None:
        violated = replace(
            safe_case("metadata-leak"),
            evaluator_result=SecurityResult.INCONCLUSIVE,
            protected_metadata_disclosure=True,
        )
        report = RagSecurityPipeline.evaluate_security_cases(
            report_id="day105-eval-mixed",
            policy=classroom_policy(),
            cases=(violated,),
            evidence_level=("EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"),
            not_run_boundaries=("PRODUCTION",),
        )
        gates = dict(report.hard_gate_results)
        self.assertIs(report.result, SecurityResult.FAIL)
        self.assertIs(
            gates["protected_metadata_disclosure_zero"],
            SecurityResult.FAIL,
        )

    def test_sensitive_output_is_a_distinct_hard_gate(self) -> None:
        violated = replace(
            safe_case("sensitive-output"),
            evaluator_result=SecurityResult.FAIL,
            sensitive_output_violation=True,
        )
        report = RagSecurityPipeline.evaluate_security_cases(
            report_id="day105-eval-sensitive-output",
            policy=classroom_policy(),
            cases=(violated,),
            evidence_level=("EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"),
            not_run_boundaries=("PRODUCTION",),
        )
        gates = dict(report.hard_gate_results)
        self.assertIs(report.result, SecurityResult.FAIL)
        self.assertIs(
            gates["sensitive_output_violation_zero"],
            SecurityResult.FAIL,
        )

    def test_unsafe_rollback_is_non_compensable_fail(self) -> None:
        unsafe = replace(
            safe_case("unsafe-rollback"),
            evaluator_result=SecurityResult.FAIL,
            unsafe_rollback_activated=True,
        )
        report = RagSecurityPipeline.evaluate_security_cases(
            report_id="day105-eval-rollback",
            policy=classroom_policy(),
            cases=(unsafe,),
            evidence_level=("EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"),
            not_run_boundaries=("PRODUCTION",),
        )
        gates = dict(report.hard_gate_results)
        self.assertIs(report.result, SecurityResult.FAIL)
        self.assertIs(
            gates["unsafe_rollback_activation_zero"],
            SecurityResult.FAIL,
        )

    def _incident(
        self,
        *,
        record_id: str,
        previous_record_id: str | None,
        state: IncidentState,
    ) -> SecurityIncidentRecord:
        return SecurityIncidentRecord(
            incident_record_id=record_id,
            incident_id="incident-X-credential",
            previous_record_id=previous_record_id,
            state=state,
            affected_request_ids=("request-Q3",),
            affected_generation_ids=("GX",),
            affected_occurrence_ids=("X@v1",),
            affected_sinks=(EgressSink.EXTERNAL_DESTINATION,),
            containment_actions=(
                "BLOCK_EXTERNAL_DESTINATION",
                "QUARANTINE_X",
            ),
            evidence_digests=(stable_hash((record_id, state.value)),),
            credential_rotation_status=(
                "COMPLETE" if state is not IncidentState.OPEN else "PENDING"
            ),
            impact_analysis_digest=stable_hash(("impact", state.value)),
            actor_id="security-control-plane",
            observed_at="2026-11-15T00:05:00+08:00",
        )

    def test_incident_ledger_appends_correction_without_rewrite(self) -> None:
        ledger = InMemorySecurityIncidentLedger()
        opened = self._incident(
            record_id="incident-record-1",
            previous_record_id=None,
            state=IncidentState.OPEN,
        )
        contained = self._incident(
            record_id="incident-record-2",
            previous_record_id=opened.incident_record_id,
            state=IncidentState.CONTAINED,
        )
        ledger.append(opened)
        ledger.append(contained)
        self.assertEqual(ledger.read(opened.incident_record_id), opened)
        self.assertEqual(
            ledger.history(opened.incident_id),
            (opened, contained),
        )

    def test_incident_ledger_rejects_overwrite(self) -> None:
        ledger = InMemorySecurityIncidentLedger()
        opened = self._incident(
            record_id="incident-record-1",
            previous_record_id=None,
            state=IncidentState.OPEN,
        )
        ledger.append(opened)
        with self.assertRaisesRegex(
            SecurityIdentityConflict,
            "cannot be overwritten",
        ):
            ledger.append(replace(opened, state=IncidentState.CLOSED))

    def test_incident_ledger_duplicate_is_idempotent(self) -> None:
        ledger = InMemorySecurityIncidentLedger()
        opened = self._incident(
            record_id="incident-record-1",
            previous_record_id=None,
            state=IncidentState.OPEN,
        )
        ledger.append(opened)
        ledger.append(opened)
        self.assertEqual(ledger.history(opened.incident_id), (opened,))

    def test_incident_correction_requires_previous_record(self) -> None:
        ledger = InMemorySecurityIncidentLedger()
        correction = self._incident(
            record_id="incident-record-2",
            previous_record_id="missing-record",
            state=IncidentState.CONTAINED,
        )
        with self.assertRaisesRegex(
            SecurityIdentityConflict,
            "requires the previous record",
        ):
            ledger.append(correction)

    def test_incident_correction_cannot_change_incident_identity(self) -> None:
        ledger = InMemorySecurityIncidentLedger()
        opened = self._incident(
            record_id="incident-record-1",
            previous_record_id=None,
            state=IncidentState.OPEN,
        )
        correction = replace(
            self._incident(
                record_id="incident-record-2",
                previous_record_id=opened.incident_record_id,
                state=IncidentState.CONTAINED,
            ),
            incident_id="different-incident",
        )
        ledger.append(opened)
        with self.assertRaisesRegex(
            SecurityIdentityConflict,
            "cannot change incident identity",
        ):
            ledger.append(correction)

    def test_incident_correction_history_cannot_branch(self) -> None:
        ledger = InMemorySecurityIncidentLedger()
        opened = self._incident(
            record_id="incident-record-1",
            previous_record_id=None,
            state=IncidentState.OPEN,
        )
        contained = self._incident(
            record_id="incident-record-2",
            previous_record_id=opened.incident_record_id,
            state=IncidentState.CONTAINED,
        )
        forked = self._incident(
            record_id="incident-record-3",
            previous_record_id=opened.incident_record_id,
            state=IncidentState.RECOVERING,
        )
        ledger.append(opened)
        ledger.append(contained)
        with self.assertRaisesRegex(
            SecurityIdentityConflict,
            "cannot branch",
        ):
            ledger.append(forked)


if __name__ == "__main__":
    unittest.main()
