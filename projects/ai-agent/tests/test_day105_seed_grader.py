from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, cast
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
sys.path.insert(0, str(EVALS))

from run_day105_evidence_replay import build_report_payload  # noqa: E402
from run_day105_seed_eval import (  # noqa: E402
    evaluate_case,
    load_cases,
    run,
)
from rag_chunking_contracts import stable_hash  # noqa: E402


class Day105SeedGraderTests(unittest.TestCase):
    def test_seed_has_sixteen_unique_content_safe_cases(self) -> None:
        cases = load_cases()

        self.assertEqual(len(cases), 16)
        self.assertEqual(len({case["case_id"] for case in cases}), 16)
        serialized = json.dumps(cases, sort_keys=True)
        for forbidden_key in (
            '"raw_attack_payload"',
            '"raw_cross_tenant_content"',
            '"raw_secret"',
            '"raw_system_prompt"',
        ):
            self.assertNotIn(forbidden_key, serialized)

    def test_seed_runner_matches_all_expected_outcomes(self) -> None:
        report = run()

        self.assertTrue(report["all_passed"])
        self.assertEqual(report["cases"], 16)
        self.assertEqual(report["passed"], 16)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(
            report["decision_counts"],
            {"PASS": 6, "FAIL": 7, "INCONCLUSIVE": 3, "NOT_RUN": 0},
        )

    def test_quality_gate_uses_independent_control_scope(self) -> None:
        report = run()
        rows = cast(list[dict[str, Any]], report["results"])

        for row in rows:
            actual = cast(dict[str, object], row["actual"])
            self.assertEqual(
                actual["normal_quality_control_scope"],
                "INDEPENDENT_Q1_Q2_Q3_CONTROL_SUITE",
            )
        serialized = json.dumps(load_cases(), sort_keys=True)
        self.assertNotIn('"normal_quality_pass"', serialized)

    def test_candidate_and_release_stages_are_not_conflated(self) -> None:
        report = run()
        rows = cast(list[dict[str, Any]], report["results"])
        results = {item["case_id"]: item["actual"] for item in rows}
        wrong_citation = results["correct-body-wrong-citation"]
        blocked_metadata = results["output-internal-metadata-blocked"]

        self.assertTrue(wrong_citation["attack_influenced_candidate"])
        self.assertFalse(wrong_citation["attack_passed_release"])
        self.assertEqual(wrong_citation["decision"], "FAIL")
        self.assertEqual(
            blocked_metadata["stage_decisions"]["output_dlp"],
            "FAIL",
        )
        self.assertFalse(blocked_metadata["attack_passed_release"])

    def test_inconclusive_poison_evidence_is_quarantined(self) -> None:
        report = run()
        rows = cast(list[dict[str, Any]], report["results"])
        results = {item["case_id"]: item["actual"] for item in rows}
        poisoned = results["corpus-poison-y-quarantined"]

        self.assertEqual(poisoned["decision"], "INCONCLUSIVE")
        self.assertEqual(poisoned["quarantined_occurrence_ids"], ["Y@v1"])
        self.assertFalse(poisoned["attack_entered_prompt"])

    def test_detected_stage_failure_is_distinct_from_defense_failure(self) -> None:
        report = run()
        rows = cast(list[dict[str, Any]], report["results"])
        results = {item["case_id"]: item["actual"] for item in rows}

        document_attack = results["document-injection-x-blocked"]
        chain_attack = results["cross-document-z-blocked"]
        self.assertEqual(document_attack["stage_decisions"]["content_security"], "FAIL")
        self.assertEqual(chain_attack["stage_decisions"]["bundle_security"], "FAIL")
        self.assertEqual(document_attack["decision"], "PASS")
        self.assertEqual(chain_attack["decision"], "PASS")

    def test_cross_tenant_tamper_is_detected_before_release(self) -> None:
        case = deepcopy(load_cases()[0])
        raw_observation = case["observation"]
        self.assertIsInstance(raw_observation, dict)
        observation = cast(dict[str, object], raw_observation)
        observation["prompt"] = ["A@v1", "T@v1"]
        observation["released"] = ["A@v1", "T@v1"]
        observation["released_citations"] = ["T@v1"]

        actual = evaluate_case(case)

        self.assertEqual(actual["decision"], "FAIL")
        self.assertEqual(actual["unauthorized_prompt_count"], 1)
        self.assertEqual(actual["cross_tenant_leakage_count"], 1)
        self.assertTrue(actual["attack_passed_release"])

    def test_report_pass_scope_is_expectation_conformance(self) -> None:
        report = build_report_payload()

        self.assertEqual(report["overall_status"], "PASS")
        self.assertEqual(
            report["overall_status_scope"],
            "EXPECTATION_CONFORMANCE",
        )
        self.assertEqual(report["level_3_status"], "NOT_RUN")
        self.assertEqual(report["level_4_status"], "NOT_RUN")
        self.assertFalse(report["fixture_production_eligible"])

    def test_report_checksum_detects_tampering(self) -> None:
        report = build_report_payload()
        saved_checksum = report.pop("report_checksum")
        self.assertEqual(saved_checksum, stable_hash(report))

        report["overall_status_scope"] = "SYSTEM_DEFENSE_PASS"

        self.assertNotEqual(saved_checksum, stable_hash(report))


if __name__ == "__main__":
    unittest.main()
