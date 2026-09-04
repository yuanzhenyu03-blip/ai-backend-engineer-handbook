"""Day84 seed grader contract tests."""
import importlib.util
import json
from pathlib import Path
import unittest

EVALS = Path(__file__).resolve().parents[1] / "evals"
SPEC = importlib.util.spec_from_file_location(
    "day84_grader", EVALS / "run_day84_seed_eval.py")
GRADER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRADER)


class Day84SeedGraderTests(unittest.TestCase):
    def test_wrong_decision_fails_without_changing_expected(self) -> None:
        case = json.loads((EVALS / "day84_context_memory_seed.jsonl").read_text().splitlines()[0])
        actual = GRADER.evaluate(case["category"])
        actual["decision"] = "APPROVED"
        self.assertEqual(GRADER.grade(case, actual), ["decision"])
        self.assertEqual(case["expected_decision"], "SELECTED")

    def test_business_effects_checked_independently(self) -> None:
        case = {"expected_decision": "BLOCKED", "expected_business_effects": []}
        actual = {"decision": "BLOCKED", "business_effects": ["publish_call"]}
        self.assertEqual(GRADER.grade(case, actual), ["business_effects"])

    def test_unknown_category_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            GRADER.evaluate("future_unknown_category")


if __name__ == "__main__":
    unittest.main()
