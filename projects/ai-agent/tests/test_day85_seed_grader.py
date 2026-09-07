"""Day85 seed grader behavior tests."""
import importlib.util
import json
from pathlib import Path
import unittest

EVALS = Path(__file__).resolve().parents[1] / "evals"
SPEC = importlib.util.spec_from_file_location(
    "day85_grader", EVALS / "run_day85_seed_eval.py",
)
GRADER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRADER)


class Day85SeedGraderTests(unittest.TestCase):
    def test_wrong_decision_fails_without_rewriting_expected(self) -> None:
        case = json.loads(
            (EVALS / "day85_multi_agent_seed.jsonl").read_text().splitlines()[0]
        )
        actual = GRADER.evaluate(case["category"])
        actual["decision"] = "WRONG"
        self.assertEqual(GRADER.grade(case, actual), ["decision"])
        self.assertEqual(case["expected_decision"], "ACCEPTED")

    def test_provider_calls_are_checked_independently(self) -> None:
        case = {"expected_decision": "BLOCKED", "expected_provider_calls": 0}
        actual = {"decision": "BLOCKED", "provider_calls": 1}
        self.assertEqual(GRADER.grade(case, actual), ["provider_calls"])

    def test_unknown_category_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            GRADER.evaluate("future_unknown_category")


if __name__ == "__main__":
    unittest.main()
