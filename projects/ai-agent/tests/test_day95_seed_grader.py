from __future__ import annotations

import unittest

from evals.run_day95_seed_eval import run


class Day95SeedGraderTests(unittest.TestCase):
    def test_all_day95_seed_cases_pass(self) -> None:
        report = run()

        self.assertEqual(report["total"], 16)
        self.assertEqual(report["passed"], 16)


if __name__ == "__main__":
    unittest.main()
