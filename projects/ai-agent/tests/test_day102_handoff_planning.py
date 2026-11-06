from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day102_grounding_citations import (
    QUERY,
    QUERY_DIGEST_SECRET,
    build_day102_fixture,
)
from rag_grounding_contracts import (
    Day102Outcome,
    GeneratorMode,
    RequestItemStatus,
    VerificationMode,
)
from rag_query_rewrite_contracts import protected_query_digest
from rag_reranker_contracts import Day101Outcome


class Day102HandoffPlanningTests(unittest.TestCase):
    def test_happy_path_releases_two_claims_with_exact_citations(self) -> None:
        fixture = build_day102_fixture()
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.FULL)
        self.assertEqual(len(result.released_claims), 2)
        self.assertEqual({
            citation.exact_span
            for claim in result.released_claims
            for citation in claim.citations
        }, {"policy-a:A-12", "manual-c:C-21"})
        self.assertTrue(all(
            item.status is RequestItemStatus.ANSWERED
            for item in result.request_coverage
        ))

    def test_tampered_handoff_rejects_before_provider_calls(self) -> None:
        fixture = build_day102_fixture()
        fixture.request = replace(
            fixture.request,
            day101_handoff_digest="sha256:tampered",
        )
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.REJECTED)
        self.assertEqual(result.safe_reason, "INVALID_DAY101_HANDOFF")
        self.assertEqual(result.generator_calls, 0)
        self.assertEqual(result.verifier_calls, 0)

    def test_query_mismatch_rejects_handoff(self) -> None:
        fixture = build_day102_fixture()
        fixture.request = replace(fixture.request, original_query=QUERY + " changed")
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.REJECTED)
        self.assertEqual(result.generator_calls, 0)

    def test_degraded_handoff_is_preserved_when_policy_allows_it(self) -> None:
        fixture = build_day102_fixture(day101_outcome=Day101Outcome.DEGRADED)
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.DEGRADED)
        self.assertEqual(result.upstream_outcome, "DEGRADED")
        self.assertEqual(result.upstream_reranking_mode, "UNRERANKED_FALLBACK")
        self.assertEqual(result.generator_mode, GeneratorMode.PRIMARY)
        self.assertEqual(result.verification_mode, VerificationMode.PRIMARY)

    def test_degraded_handoff_rejects_when_policy_disallows_it(self) -> None:
        fixture = build_day102_fixture(
            day101_outcome=Day101Outcome.DEGRADED,
            allow_degraded_handoff=False,
        )
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.REJECTED)
        self.assertEqual(result.safe_reason, "UPSTREAM_OUTCOME_NOT_ALLOWED")
        self.assertEqual(result.generator_calls, 0)

    def test_selector_cannot_add_candidate_outside_day101_handoff(self) -> None:
        fixture = build_day102_fixture(
            selected_occurrence_ids=("occurrence:A", "occurrence:D")
        )
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.REJECTED)
        self.assertEqual(result.safe_reason, "GROUNDING_PLAN_INVALID")
        self.assertEqual(result.generator_calls, 0)

    def test_day101_handoff_binds_original_query_digest(self) -> None:
        fixture = build_day102_fixture()
        expected = protected_query_digest(
            QUERY_DIGEST_SECRET,
            fixture.request.tenant_id,
            fixture.request.original_query,
        )
        self.assertEqual(
            fixture.day101_response.original_query_digest,
            expected,
        )


if __name__ == "__main__":
    unittest.main()
