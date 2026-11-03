from __future__ import annotations

import sys
from pathlib import Path
import unittest

EVALS = Path(__file__).resolve().parents[1] / "evals"
sys.path.insert(0, str(EVALS))

from run_day100_seed_eval import run


class Day100SeedGraderTests(unittest.TestCase):
    def test_all_seed_cases_pass_and_keep_production_honest(self) -> None:
        result = run()
        self.assertEqual(result["passed"], result["total"])
        self.assertEqual(result["total"], 8)
        self.assertFalse(result["synthetic_fixture_production_eligible"])
        self.assertEqual(result["real_provider"], "NOT_RUN")
        self.assertEqual(result["production_readiness"], "MORE_EVIDENCE_NEEDED")


if __name__ == "__main__":
    unittest.main()
