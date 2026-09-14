"""Day91 seed grader integrity tests."""
import importlib.util
import json
from pathlib import Path
import unittest


EVALS = Path(__file__).resolve().parents[1] / "evals"
SPEC = importlib.util.spec_from_file_location(
    "day91_grader", EVALS / "run_day91_seed_eval.py"
)
GRADER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRADER)


class Day91SeedGraderTests(unittest.TestCase):
    def test_wrong_outcome_fails_without_rewriting_expected(self) -> None:
        case = json.loads(
            (EVALS / "day91_mcp_server_seed.jsonl").read_text().splitlines()[0]
        )
        actual = GRADER.evaluate(case["category"])
        actual["outcome"] = "WRONG"

        self.assertEqual(GRADER.grade(case, actual), ["outcome"])
        self.assertEqual(case["expected_outcome"], "BACKPRESSURE_REJECTED")

    def test_effect_counters_are_compared_independently(self) -> None:
        case = {
            "expected_outcome": "INDIRECT_PROMPT_INJECTION_REJECTED",
            "expected_service_calls": 0,
            "expected_resource_reads": 1,
            "expected_prompt_renders": 0,
            "expected_durable_transitions": 0,
        }
        actual = dict(
            outcome="INDIRECT_PROMPT_INJECTION_REJECTED",
            service_calls=0,
            resource_reads=0,
            prompt_renders=0,
            durable_transitions=0,
        )

        self.assertEqual(GRADER.grade(case, actual), ["resource_reads"])

    def test_unknown_category_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            GRADER.evaluate("future_unknown_category")


if __name__ == "__main__":
    unittest.main()
