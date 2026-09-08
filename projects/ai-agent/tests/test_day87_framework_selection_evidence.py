"""Day87 deterministic evidence-boundary tests."""
from dataclasses import replace
import unittest

from framework_selection_evidence import (
    Confidence,
    ContractAssessment,
    ContractFit,
    EvidenceKind,
    EvidenceRecord,
    EvidenceStatus,
    Freshness,
    JobPosting,
    PostingStatus,
    Readiness,
    RequirementSignal,
    SourceType,
    assessment_is_proven,
    build_day88_handoff,
    company_concentration,
    dedupe_active_postings,
    eligible_evidence,
    sensitivity_is_unstable,
    supersede_record,
    transferable_signal,
    validate_evidence,
)


class Day87FrameworkSelectionEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.docs = EvidenceRecord(
            "ev-docs", "candidate-b", "supports tool hooks",
            "official documentation claim only",
            "https://example.com/docs", "Candidate B",
            SourceType.OFFICIAL_DOCS, EvidenceKind.DOCUMENTATION, "1.2.3",
            "2026-09-01T00:00:00+00:00", "2026-09-08T16:08:29+08:00",
            Freshness.CURRENT, "", Confidence.HIGH,
        )
        self.spike = replace(
            self.docs,
            evidence_id="ev-spike",
            claim="adapter blocks direct dispatch",
            supported_scope="local deterministic spike; Fake Tool",
            evidence_kind=EvidenceKind.EXECUTED_SPIKE,
            confidence=Confidence.MEDIUM,
        )
        self.hard = ContractAssessment(
            "candidate-b", "application-adapter-current-auth", True,
            ContractFit.ADAPTER, ("ev-spike",), True,
        )
        self.job = JobPosting(
            "Example Co", "Agent Platform Engineer", "Singapore", "42",
            "https://example.com/jobs/42", PostingStatus.ACTIVE,
            SourceType.OFFICIAL_ATS, "2026-09-08T16:08:29+08:00",
            RequirementSignal.REQUIRED, ("LangGraph or equivalent",),
        )

    def test_complete_official_evidence_is_valid(self) -> None:
        validate_evidence(self.docs)

    def test_missing_supported_scope_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "supported_scope"):
            validate_evidence(replace(self.docs, supported_scope=""))

    def test_missing_observed_version_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "observed_version"):
            validate_evidence(replace(self.docs, observed_version=""))

    def test_non_https_source_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "https"):
            validate_evidence(replace(self.docs, source_url="http://example.com"))

    def test_timestamp_requires_timezone(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone"):
            validate_evidence(replace(self.docs, retrieved_at="2026-09-08T10:00:00"))

    def test_unpublished_source_date_is_explicit_unknown(self) -> None:
        validate_evidence(replace(self.docs, published_or_updated_at="UNKNOWN"))

    def test_conflict_cannot_claim_high_confidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "conflicting evidence"):
            validate_evidence(replace(self.docs, conflicting_evidence="registry differs"))

    def test_unknown_is_not_rewritten_as_gap(self) -> None:
        assessment = replace(self.hard, fit=ContractFit.UNKNOWN, evidence_ids=())
        self.assertFalse(assessment_is_proven(assessment, {}))
        self.assertEqual(assessment.fit, ContractFit.UNKNOWN)

    def test_documentation_does_not_replace_required_spike(self) -> None:
        assessment = replace(self.hard, evidence_ids=("ev-docs",))
        self.assertFalse(assessment_is_proven(assessment, {"ev-docs": self.docs}))

    def test_current_primary_executed_spike_proves_adapter_fit(self) -> None:
        self.assertTrue(assessment_is_proven(self.hard, {"ev-spike": self.spike}))

    def test_stale_spike_does_not_prove_current_version(self) -> None:
        stale = replace(self.spike, freshness=Freshness.STALE)
        self.assertFalse(assessment_is_proven(self.hard, {"ev-spike": stale}))

    def test_superseded_spike_is_preserved_but_ineligible(self) -> None:
        old = supersede_record(self.spike)
        self.assertEqual(old.status, EvidenceStatus.SUPERSEDED)
        self.assertEqual(eligible_evidence((old,)), ())

    def test_unknown_hard_constraint_requires_more_evidence(self) -> None:
        unknown = replace(self.hard, fit=ContractFit.UNKNOWN, evidence_ids=())
        handoff = build_day88_handoff(
            candidate="candidate-b", assessments=(unknown,), evidence=(self.docs,),
            score_scenarios=({"candidate-a": 7, "candidate-b": 8},),
        )
        self.assertEqual(handoff.readiness, Readiness.MORE_EVIDENCE_NEEDED)
        self.assertFalse(handoff.framework_selection_final)

    def test_hard_gap_blocks_candidate_even_with_high_score(self) -> None:
        gap = replace(self.hard, fit=ContractFit.GAP, evidence_ids=())
        handoff = build_day88_handoff(
            candidate="candidate-b", assessments=(gap,), evidence=(),
            score_scenarios=({"candidate-a": 1, "candidate-b": 99},),
        )
        self.assertEqual(handoff.readiness, Readiness.HARD_CONSTRAINT_FAILED)
        self.assertIsNone(handoff.candidate)

    def test_sensitivity_flip_recommends_discriminating_spike(self) -> None:
        handoff = build_day88_handoff(
            candidate="candidate-b", assessments=(self.hard,), evidence=(self.spike,),
            score_scenarios=(
                {"candidate-a": 7.9, "candidate-b": 8.0},
                {"candidate-a": 8.1, "candidate-b": 8.0},
            ),
        )
        self.assertEqual(handoff.readiness, Readiness.MORE_EVIDENCE_NEEDED)
        self.assertIn("fails closed", handoff.discriminating_spike)

    def test_stable_scores_are_not_sensitive(self) -> None:
        self.assertFalse(sensitivity_is_unstable((
            {"candidate-a": 7, "candidate-b": 9},
            {"candidate-a": 7.5, "candidate-b": 8.5},
        )))

    def test_tied_score_is_sensitive(self) -> None:
        self.assertTrue(sensitivity_is_unstable((
            {"candidate-a": 8, "candidate-b": 8},
        )))

    def test_mirror_url_does_not_increase_job_count(self) -> None:
        mirror = replace(self.job, canonical_url="https://mirror.example/jobs/42")
        self.assertEqual(len(dedupe_active_postings((self.job, mirror))), 1)

    def test_closed_and_unknown_jobs_are_not_active(self) -> None:
        closed = replace(self.job, posting_id="43", status=PostingStatus.CLOSED)
        unknown = replace(self.job, posting_id="44", status=PostingStatus.UNKNOWN)
        self.assertEqual(dedupe_active_postings((closed, unknown)), ())

    def test_aggregator_is_not_primary_active_evidence(self) -> None:
        aggregator = replace(self.job, source_type=SourceType.AGGREGATOR)
        self.assertEqual(dedupe_active_postings((aggregator,)), ())

    def test_distinct_roles_at_same_company_count_separately(self) -> None:
        security = replace(
            self.job, normalized_role="AI Platform Security Engineer",
            posting_id="security-1", canonical_url="https://example.com/jobs/security-1",
        )
        self.assertEqual(len(dedupe_active_postings((self.job, security))), 2)
        self.assertEqual(company_concentration((self.job, security))["Example Co"], 2)

    def test_or_equivalent_is_transferable_not_framework_authority(self) -> None:
        self.assertTrue(transferable_signal(self.job))
        self.assertEqual(self.job.framework_signal, RequirementSignal.REQUIRED)
        self.assertIn("or equivalent", self.job.named_frameworks[0])


if __name__ == "__main__":
    unittest.main()
