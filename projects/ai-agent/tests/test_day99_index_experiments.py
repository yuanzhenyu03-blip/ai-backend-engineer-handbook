from __future__ import annotations

import unittest

from rag_vector_index_experiments import (
    rank_overlap,
    recall_at_k,
    run_controlled_index_experiment,
)


class Day99IndexExperimentTests(unittest.TestCase):
    def test_recall_and_rank_overlap_use_exact_identity_sets(self) -> None:
        gold = ("a", "b", "c", "d", "e")
        proposal = ("a", "b", "c", "d", "f")
        self.assertEqual(recall_at_k(gold, proposal), 0.8)
        self.assertEqual(rank_overlap(gold, proposal), 0.8)
        with self.assertRaises(ValueError):
            recall_at_k(gold, ("a", "a"))

    def test_controlled_experiment_is_replayable_and_not_real_ann(self) -> None:
        first = run_controlled_index_experiment()
        second = run_controlled_index_experiment()
        self.assertEqual(first, second)
        self.assertEqual(first["corpus_size"], 256)
        self.assertEqual(first["mean_recall_at_k"], 0.9)
        self.assertEqual(first["real_ann_runtime"], "NOT_RUN")
        self.assertFalse(first["approximate_method_is_real_ann"])
        self.assertFalse(first["raw_vectors_in_report"])


if __name__ == "__main__":
    unittest.main()
