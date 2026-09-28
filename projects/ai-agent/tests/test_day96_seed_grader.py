from __future__ import annotations

import unittest

from evals.run_day96_seed_eval import run


class Day96SeedGraderTests(unittest.TestCase):
    def test_all_distinct_seed_cases_match_expected_boundary(self) -> None:
        result = run()
        self.assertEqual(result["total"], 16)
        self.assertEqual(result["passed"], 16, result["cases"])


if __name__ == "__main__":
    unittest.main()
