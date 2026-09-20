"""Day94 seed must remain executable and internally consistent."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


EVALS = Path(__file__).resolve().parents[1] / "evals"
RUNNER = EVALS / "run_day94_seed_eval.py"
SEED = EVALS / "day94_agent_mcp_capstone_seed.jsonl"


class Day94SeedGraderTests(unittest.TestCase):
    def test_all_seed_cases_match_executable_invariants(self) -> None:
        spec = importlib.util.spec_from_file_location("day94_seed_runner", RUNNER)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cases = [
            json.loads(line)
            for line in SEED.read_text(encoding="utf-8").splitlines()
            if line
        ]

        self.assertEqual(len(cases), 16)
        self.assertEqual(len({case["case_id"] for case in cases}), 16)
        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                actual = module.evaluate(case["category"])
                self.assertEqual(module.grade(case, actual), [])


if __name__ == "__main__":
    unittest.main()
