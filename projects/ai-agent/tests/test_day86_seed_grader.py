"""Day86 seed grader behavior tests."""
import importlib.util
import json
from pathlib import Path
import unittest


EVALS = Path(__file__).resolve().parents[1] / "evals"
SPEC = importlib.util.spec_from_file_location(
    "day86_grader", EVALS / "run_day86_seed_eval.py",
)
GRADER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRADER)


class Day86SeedGraderTests(unittest.TestCase):
    def test_wrong_decision_fails_without_rewriting_expected(self) -> None:
        case = json.loads(
            (EVALS / "day86_agent_security_seed.jsonl")
            .read_text()
            .splitlines()[0]
        )
        actual = GRADER.evaluate(case["category"])
        actual["decision"] = "WRONG"
        self.assertEqual(GRADER.grade(case, actual), ["decision"])
        self.assertEqual(case["expected_decision"], "ALLOW")

    def test_forbidden_effects_are_compared_independently(self) -> None:
        case = {
            "expected_decision": "DENY",
            "expected_reason": "TEST",
            "expected_state": "NOT_DISPATCHED",
            "expected_tool_calls": 0,
            "expected_egress_calls": 0,
            "expected_sandbox_runs": 0,
        }
        actual = {
            "decision": "DENY",
            "reason": "TEST",
            "state": "NOT_DISPATCHED",
            "tool_calls": 1,
            "egress_calls": 0,
            "sandbox_runs": 0,
        }
        self.assertEqual(GRADER.grade(case, actual), ["tool_calls"])

    def test_unknown_category_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            GRADER.evaluate("future_unknown_category")


if __name__ == "__main__":
    unittest.main()
