from __future__ import annotations

import unittest

from examples.day101_query_rewriting_reranking import (
    build_day101_fixture,
    day101_request,
)
from rag_reranker_contracts import Day101Outcome


def revoke(fixture, occurrence_id: str) -> None:
    request = day101_request(fixture)
    fixture.day100.authorization.revoke_occurrence(
        tenant_id=request.tenant_id,
        principal_subject=request.principal_subject,
        action=request.action,
        purpose=request.purpose,
        occurrence_id=occurrence_id,
    )


class Day101RerankingAuthorizationTests(unittest.TestCase):
    def test_post_rerank_revocation_removes_top_candidate(self) -> None:
        fixture = build_day101_fixture()
        original_rank = fixture.reranker.rank

        def rank_then_revoke(request):
            response = original_rank(request)
            revoke(fixture, "occurrence:B")
            return response

        fixture.reranker.rank = rank_then_revoke
        result = fixture.pipeline.execute(day101_request(fixture))
        ids = tuple(hit.identity.occurrence_id for hit in result.hits)
        self.assertNotIn("occurrence:B", ids)
        self.assertIn(("occurrence:B", "STALE_AUTHORIZATION"), result.release_rejections)
        self.assertEqual(result.outcome, Day101Outcome.DEGRADED)

    def test_post_rerank_provenance_change_removes_candidate(self) -> None:
        fixture = build_day101_fixture()
        original_rank = fixture.reranker.rank

        def rank_then_change(request):
            response = original_rank(request)
            fixture.currentness.change_provenance(
                "occurrence:B", "sha256:new-provenance"
            )
            return response

        fixture.reranker.rank = rank_then_change
        result = fixture.pipeline.execute(day101_request(fixture))
        ids = tuple(hit.identity.occurrence_id for hit in result.hits)
        self.assertNotIn("occurrence:B", ids)
        self.assertIn(("occurrence:B", "STALE_PROVENANCE"), result.release_rejections)

    def test_final_output_is_subset_of_day100_candidate_pool(self) -> None:
        fixture = build_day101_fixture()
        result = fixture.pipeline.execute(day101_request(fixture))
        self.assertEqual(len(result.hits), len({hit.identity.occurrence_id for hit in result.hits}))
        self.assertNotIn("occurrence:X", {
            hit.identity.occurrence_id for hit in result.hits
        })

    def test_high_reranker_score_does_not_override_revocation(self) -> None:
        fixture = build_day101_fixture()
        revoke(fixture, "occurrence:B")
        result = fixture.pipeline.execute(day101_request(fixture))
        self.assertNotIn("occurrence:B", {
            hit.identity.occurrence_id for hit in result.hits
        })


if __name__ == "__main__":
    unittest.main()
