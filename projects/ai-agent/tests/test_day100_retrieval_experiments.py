from __future__ import annotations

import unittest
import sys
from pathlib import Path

from rag_retrieval_experiments import run_controlled_experiment

EVALS = Path(__file__).resolve().parents[1] / "evals"
sys.path.insert(0, str(EVALS))
from run_day100_evidence_replay import run as replay_evidence


class Day100RetrievalExperimentTests(unittest.TestCase):
    def test_controlled_report_is_deterministic(self) -> None:
        self.assertEqual(run_controlled_experiment(), run_controlled_experiment())

    def test_report_preserves_real_not_run_facts(self) -> None:
        report = run_controlled_experiment()
        self.assertEqual(report["real_provider"], "NOT_RUN")
        self.assertEqual(report["real_ann_recall"], "NOT_RUN")
        self.assertEqual(report["production_readiness"], "MORE_EVIDENCE_NEEDED")
        self.assertFalse(report["fixture_production_eligible"])

    def test_report_is_content_safe(self) -> None:
        report = run_controlled_experiment()
        self.assertFalse(report["raw_queries_in_report"])
        self.assertFalse(report["protected_text_in_report"])
        self.assertFalse(report["vectors_in_report"])
        self.assertTrue(all(
            not case["raw_query_logged"]
            and not case["protected_text_logged"]
            for case in report["cases"]
        ))

    def test_report_keeps_real_handoff_unselected(self) -> None:
        report = run_controlled_experiment()
        self.assertFalse(report["real_day99_handoff"]["selected_bundle"])
        self.assertEqual(
            report["real_day99_handoff"]["generation_state"], "SEALED"
        )

    def test_saved_evidence_replays_exactly(self) -> None:
        self.assertEqual(replay_evidence()["replay"], "PASS")


if __name__ == "__main__":
    unittest.main()
