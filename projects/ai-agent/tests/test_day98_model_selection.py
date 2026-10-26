from __future__ import annotations

import unittest
import json
from pathlib import Path

from rag_embedding_experiments import run_selection_experiment


class Day98ModelSelectionTests(unittest.TestCase):
    def test_hard_gates_run_before_frozen_weighted_score(self) -> None:
        first = run_selection_experiment()
        second = run_selection_experiment()
        self.assertEqual(first, second)
        self.assertEqual(
            first["selected_candidate_id"],
            "BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181",
        )
        rejected = [
            candidate for candidate in first["candidates"]
            if not candidate["eligible"]
        ]
        self.assertEqual(len(rejected), 2)
        self.assertTrue(all(candidate["score"] is None for candidate in rejected))
        self.assertEqual(first["real_provider_execution"], "NOT_RUN")

    def test_saved_selection_matrix_replays_exactly(self) -> None:
        expected = json.loads(
            (Path(__file__).parents[1] / "evidence/day98-model-selection-matrix.json")
            .read_text(encoding="utf-8")
        )
        actual = json.loads(json.dumps(run_selection_experiment()))
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
