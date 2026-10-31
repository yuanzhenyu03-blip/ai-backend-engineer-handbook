from __future__ import annotations

import unittest

from evals.run_day99_seed_eval import run


class Day99SeedGraderTests(unittest.TestCase):
    def test_seed_matrix_passes(self) -> None:
        result = run()
        self.assertEqual(result["passed"], result["total"])
        self.assertEqual(result["total"], 8)
        self.assertEqual(result["real_provider_execution"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
