from __future__ import annotations

import unittest

from rag_reranking_experiments import run_controlled_experiment


class Day101RerankingExperimentTests(unittest.TestCase):
    def test_report_preserves_real_negative_and_synthetic_boundary(self) -> None:
        report = run_controlled_experiment()
        self.assertEqual(
            report["real_production_negative"]["reason"],
            "NO_CURRENT_DAY100_BUNDLE",
        )
        self.assertEqual(
            report["real_production_negative"]["rewrite_provider_calls"], 0
        )
        self.assertFalse(report["fixture_production_eligible"])

    def test_report_is_content_safe(self) -> None:
        report = run_controlled_experiment()
        self.assertFalse(report["raw_queries_in_report"])
        self.assertFalse(report["protected_text_in_report"])
        self.assertFalse(report["vectors_in_report"])
        self.assertTrue(all(not case["raw_query_logged"] for case in report["cases"]))

    def test_report_keeps_real_model_evidence_not_run(self) -> None:
        report = run_controlled_experiment()
        self.assertEqual(report["real_local_cross_encoder"], "NOT_RUN")
        self.assertEqual(report["real_cohere_rerank"], "NOT_RUN")
        self.assertEqual(report["real_reranker_quality"], "NOT_RUN")
        self.assertEqual(report["production_readiness"], "MORE_EVIDENCE_NEEDED")

    def test_report_checksum_is_deterministic(self) -> None:
        self.assertEqual(
            run_controlled_experiment()["report_checksum"],
            run_controlled_experiment()["report_checksum"],
        )


if __name__ == "__main__":
    unittest.main()
