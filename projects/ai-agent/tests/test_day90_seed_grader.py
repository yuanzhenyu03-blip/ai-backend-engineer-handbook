"""Day90 seed grader integrity tests."""
import importlib.util
import json
from pathlib import Path
import unittest


EVALS = Path(__file__).resolve().parents[1] / "evals"
SPEC = importlib.util.spec_from_file_location(
    "day90_grader", EVALS / "run_day90_seed_eval.py"
)
GRADER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRADER)


class Day90SeedGraderTests(unittest.TestCase):
    def test_wrong_outcome_fails_without_rewriting_expected(self) -> None:
        case = json.loads(
            (EVALS / "day90_mcp_client_seed.jsonl").read_text().splitlines()[0]
        )
        actual = GRADER.evaluate(case["category"])
        actual["outcome"] = "WRONG"
        self.assertEqual(GRADER.grade(case, actual), ["outcome"])
        self.assertEqual(
            case["expected_outcome"], "ENCODED_CURRENT_METADATA"
        )

    def test_resource_read_count_is_compared_independently(self) -> None:
        case = {
            "expected_outcome": "INDIRECT_PROMPT_INJECTION",
            "expected_sends": 0,
            "expected_resource_reads": 1,
            "expected_durable_transition": False,
        }
        actual = dict(
            outcome="INDIRECT_PROMPT_INJECTION",
            sends=0,
            resource_reads=0,
            durable_transition=False,
        )
        self.assertEqual(GRADER.grade(case, actual), ["resource_reads"])

    def test_unknown_category_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            GRADER.evaluate("future_unknown_category")


if __name__ == "__main__":
    unittest.main()
