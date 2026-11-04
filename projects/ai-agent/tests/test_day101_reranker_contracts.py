from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day101_query_rewriting_reranking import (
    build_day101_fixture,
    classroom_reranker_contract,
)
from rag_reranker_contracts import RerankerInputItem
from day101_test_support import build_intermediate


class Day101RerankerContractTests(unittest.TestCase):
    def test_model_revision_must_be_immutable(self) -> None:
        with self.assertRaises(ValueError):
            replace(classroom_reranker_contract(), immutable_model_revision="main")

    def test_top_n_cannot_exceed_candidate_budget(self) -> None:
        with self.assertRaises(ValueError):
            replace(classroom_reranker_contract(), top_n=6, max_candidates=5)

    def test_input_items_have_explicit_candidate_correlation(self) -> None:
        fixture = build_day101_fixture()
        *_, request = build_intermediate(fixture)
        self.assertTrue(all(
            item.candidate_id == item.identity.occurrence_id
            for item in request.items
        ))
        self.assertEqual(
            tuple(item.input_index for item in request.items),
            tuple(range(len(request.items))),
        )

    def test_scores_are_explicitly_not_calibrated_probabilities(self) -> None:
        contract = classroom_reranker_contract()
        self.assertEqual(contract.score_calibration, "NOT_CALIBRATED_NOT_A_PROBABILITY")

    def test_input_item_rejects_candidate_identity_mismatch(self) -> None:
        fixture = build_day101_fixture()
        *_, request = build_intermediate(fixture)
        item = request.items[0]
        with self.assertRaises(ValueError):
            RerankerInputItem(
                item.input_index,
                "unknown",
                item.identity,
                item.prior_fusion_rank,
                item.input_window_digest,
                item.input_window_policy_version,
                item.protected_input_window,
            )


if __name__ == "__main__":
    unittest.main()
