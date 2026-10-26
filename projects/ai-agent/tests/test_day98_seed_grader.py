from __future__ import annotations

import unittest

from evals.run_day98_seed_eval import run


class Day98SeedGraderTests(unittest.TestCase):
    def test_all_seed_cases_match_expected_boundary(self) -> None:
        result = run()
        self.assertEqual(result["total"], 17)
        self.assertEqual(result["passed"], 17, result["cases"])
        self.assertFalse(result["vectors_in_report"])


if __name__ == "__main__":
    unittest.main()
