from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, cast
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
sys.path.insert(0, str(EVALS))

from run_day106_seed_eval import load_cases, run  # noqa: E402


class Day106SeedGraderTests(unittest.TestCase):
    def test_seed_has_thirteen_unique_content_safe_cases(self) -> None:
        cases = load_cases()

        self.assertEqual(len(cases), 13)
        self.assertEqual(len({case["case_id"] for case in cases}), 13)
        serialized = json.dumps(cases, sort_keys=True).lower()
        for forbidden in (
            "raw_prompt",
            "protected_chunk",
            "answer_candidate_text",
            "raw_vector",
            "secret_value",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_seed_runner_matches_all_expected_outcomes(self) -> None:
        result = run()

        self.assertTrue(result["all_passed"])
        self.assertEqual(result["cases"], 13)
        self.assertEqual(result["passed"], 13)
        self.assertEqual(result["failed"], 0)

    def test_seed_covers_quality_revocation_security_recovery_and_scope(self) -> None:
        cases = cast(tuple[dict[str, Any], ...], load_cases())
        case_ids = {str(item["case_id"]) for item in cases}

        required = {
            "normal-q1-release",
            "normal-q2-release",
            "normal-q3-release",
            "old-g2-candidate-blocked",
            "old-g2-retrieval-rechecks",
            "new-g3-q2-release",
            "new-g3-q1-no-revoked-a",
            "new-g3-q3-no-revoked-a",
            "security-negatives-prompt-zero",
            "unauthorized-prompt-zero",
            "unknown-recovery-delivered",
            "external-real-not-run",
            "l2-overall-pass",
        }
        self.assertEqual(case_ids, required)


if __name__ == "__main__":
    unittest.main()
