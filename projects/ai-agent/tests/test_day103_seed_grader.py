from __future__ import annotations

import json
from pathlib import Path
import unittest

from evals.run_day103_seed_eval import SEED_PATH, run


class Day103SeedGraderTests(unittest.TestCase):
    def test_seed_has_ten_unique_cases(self) -> None:
        cases = [
            json.loads(line)
            for line in Path(SEED_PATH).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(cases), 10)
        self.assertEqual(len({case["case_id"] for case in cases}), 10)

    def test_seed_expectations_are_structured(self) -> None:
        cases = [
            json.loads(line)
            for line in Path(SEED_PATH).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(all(
            isinstance(case.get("expected"), dict)
            and "decision" in case["expected"]
            for case in cases
        ))

    def test_seed_runner_passes(self) -> None:
        report = run()
        self.assertTrue(report["all_passed"])
        self.assertEqual(report["passed"], report["cases"])


if __name__ == "__main__":
    unittest.main()
