from __future__ import annotations

import unittest

from examples.day101_query_rewriting_reranking import (
    build_day101_fixture,
    day101_request,
)
from rag_reranker_contracts import Day101Outcome


class Day101HandoffEligibilityTests(unittest.TestCase):
    def test_missing_real_bundle_stops_before_side_effects(self) -> None:
        fixture = build_day101_fixture(
            select_bundle=False, classroom_mode=False, production_mode=True
        )
        result = fixture.pipeline.execute(day101_request(fixture))
        self.assertEqual(result.outcome, Day101Outcome.REJECTED)
        self.assertEqual(result.safe_reason, "NO_CURRENT_DAY100_BUNDLE")
        self.assertEqual(result.rewrite_provider_calls, 0)
        self.assertEqual(result.reranker_provider_calls, 0)
        self.assertEqual(fixture.day100.lexical.database_calls, 0)
        self.assertEqual(fixture.day100.dense.database_calls, 0)

    def test_non_production_fixture_is_rejected_in_production_mode(self) -> None:
        fixture = build_day101_fixture(production_mode=True)
        result = fixture.pipeline.execute(day101_request(fixture))
        self.assertEqual(result.safe_reason, "DAY100_HANDOFF_REJECTED")
        self.assertEqual(result.rewrite_provider_calls, 0)
        self.assertEqual(result.reranker_provider_calls, 0)

    def test_classroom_fixture_can_prove_only_control_flow(self) -> None:
        fixture = build_day101_fixture()
        result = fixture.pipeline.execute(day101_request(fixture))
        self.assertEqual(result.outcome, Day101Outcome.FULL)
        self.assertEqual(
            tuple(
                (hit.identity.occurrence_id, hit.rank, hit.prior_fusion_rank)
                for hit in result.hits
            ),
            (
                ("occurrence:B", 1, 2),
                ("occurrence:A", 2, 1),
                ("occurrence:C", 3, 4),
                ("occurrence:A2", 4, 3),
            ),
        )
        self.assertFalse(fixture.day100.bundle.production_eligible)
        self.assertEqual(fixture.day100.bundle.fixture_scope, "DAY100_CLASSROOM_ONLY")

    def test_non_classroom_mode_rejects_classroom_bundle(self) -> None:
        fixture = build_day101_fixture(classroom_mode=False)
        result = fixture.pipeline.execute(day101_request(fixture))
        self.assertEqual(result.safe_reason, "DAY100_HANDOFF_REJECTED")


if __name__ == "__main__":
    unittest.main()
