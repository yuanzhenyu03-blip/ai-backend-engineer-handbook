from __future__ import annotations

import unittest

from evals.run_day97_seed_eval import run


class Day97SeedGraderTests(unittest.TestCase):
    def test_all_day97_seed_cases_match_expected_boundary(self) -> None:
        result = run()
        self.assertEqual(result["total"], 24)
        self.assertEqual(result["passed"], 24, result["cases"])


if __name__ == "__main__":
    unittest.main()
