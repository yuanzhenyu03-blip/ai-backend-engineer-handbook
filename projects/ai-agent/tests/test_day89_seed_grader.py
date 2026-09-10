"""Day89 seed grader integrity tests."""
import importlib.util
import json
from pathlib import Path
import unittest


EVALS = Path(__file__).resolve().parents[1] / "evals"
SPEC = importlib.util.spec_from_file_location(
    "day89_grader", EVALS / "run_day89_seed_eval.py"
)
GRADER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRADER)


class Day89SeedGraderTests(unittest.TestCase):
    def test_wrong_outcome_fails_without_rewriting_expected(self) -> None:
        case = json.loads(
            (EVALS / "day89_mcp_protocol_seed.jsonl").read_text().splitlines()[0]
        )
        actual = GRADER.evaluate(case["category"])
        actual["outcome"] = "WRONG"
        self.assertEqual(GRADER.grade(case, actual), ["outcome"])
        self.assertEqual(case["expected_outcome"], "PROTOCOL_RESULT")

    def test_forbidden_send_is_compared_independently(self) -> None:
        case = {
            "expected_outcome": "UNSUPPORTED_VERSION",
            "expected_mcp_sends": 0,
            "expected_bindings": 0,
            "expected_durable_transition": False,
        }
        actual = {
            "outcome": "UNSUPPORTED_VERSION",
            "mcp_sends": 1,
            "bindings": 0,
            "durable_transition": False,
        }
        self.assertEqual(GRADER.grade(case, actual), ["mcp_sends"])

    def test_unknown_category_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            GRADER.evaluate("future_unknown_category")


if __name__ == "__main__":
    unittest.main()
