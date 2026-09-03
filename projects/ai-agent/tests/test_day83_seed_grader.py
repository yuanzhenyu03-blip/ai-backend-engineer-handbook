"""Test the grader separately from the frozen seed case results."""
import importlib.util
import json
from pathlib import Path
import unittest

EVALS = Path(__file__).resolve().parents[1] / "evals"
SPEC = importlib.util.spec_from_file_location("day83_grader", EVALS / "run_day83_seed_eval.py")
GRADER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRADER)


class SeedGraderTests(unittest.TestCase):
    def test_wrong_release_fails_without_changing_expected(self) -> None:
        cases = [json.loads(line) for line in
                 (EVALS / "day83_human_control_seed.jsonl").read_text().splitlines()]
        case = next(case for case in cases if case["case_id"] == "HC14")
        actual = GRADER.evaluate_facts(case["input_facts"])
        actual["reservation_action"] = "RELEASE"
        self.assertIn("reservation_action", GRADER.grade(case, actual))
        self.assertEqual(case["expected_reservation_action"], "KEEP_HELD")

    def test_forbidden_effect_is_checked_independently(self) -> None:
        case = dict(expected_decision="BLOCKED", expected_next_state="RUNNING",
                    expected_execution_allowed=False, expected_reservation_action="NO_CHANGE",
                    expected_outbox_action="NONE", expected_evidence=[],
                    forbidden_effects=["publish_call"])
        actual = dict(decision="BLOCKED", next_state="RUNNING", execution_allowed=False,
                      reservation_action="NO_CHANGE", outbox_action="NONE", evidence=[],
                      effects=["publish_call"])
        self.assertEqual(GRADER.grade(case, actual), ["forbidden_effects"])

    def test_unknown_fixture_fields_cannot_silently_pass(self) -> None:
        with self.assertRaises(ValueError):
            GRADER.evaluate_facts({"unexpected": True})


if __name__ == "__main__":
    unittest.main()
