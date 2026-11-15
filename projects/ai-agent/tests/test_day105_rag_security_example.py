from __future__ import annotations

import json
import unittest

from examples.day105_rag_security import run_example
from rag_chunking_contracts import stable_hash


class Day105RagSecurityExampleTests(unittest.TestCase):
    def test_example_is_deterministic_and_checksum_bound(self) -> None:
        first = run_example()
        second = run_example()
        self.assertEqual(first, second)
        unsigned = {
            key: value for key, value in first.items() if key != "report_checksum"
        }
        self.assertEqual(first["report_checksum"], stable_hash(unsigned))

    def test_q1_q2_q3_preserve_normal_quality(self) -> None:
        report = run_example()
        queries = report["normal_queries"]
        self.assertEqual(queries["Q1"]["prompt_occurrence_ids"], ["A@v1"])
        self.assertEqual(queries["Q2"]["prompt_occurrence_ids"], ["C@v1"])
        self.assertEqual(
            queries["Q3"]["prompt_occurrence_ids"],
            ["A@v1", "C@v1"],
        )
        for query in queries.values():
            self.assertEqual(query["release_result"], "PASS")
            self.assertEqual(query["release_disposition"], "RELEASE")
        self.assertEqual(
            report["evaluation"]["hard_gates"]["normal_quality_preserved"],
            "PASS",
        )

    def test_adversarial_occurrences_never_enter_prompt(self) -> None:
        gates = run_example()["adversarial_gates"]
        self.assertEqual(gates["G2_exact_manifest"]["result"], "FAIL")
        self.assertEqual(gates["G2_exact_manifest"]["allowed"], [])
        self.assertEqual(
            gates["X_document_injection"]["bundle_result"],
            "FAIL",
        )
        self.assertEqual(gates["Y_detector_timeout"]["result"], "INCONCLUSIVE")
        self.assertEqual(
            gates["Z_cross_document_chain"]["bundle_result"],
            "FAIL",
        )
        self.assertEqual(gates["T_cross_tenant"]["result"], "FAIL")
        for name in (
            "X_document_injection",
            "Y_detector_timeout",
            "Z_cross_document_chain",
            "T_cross_tenant",
        ):
            self.assertFalse(gates[name]["entered_prompt"])
            self.assertFalse(gates[name]["selected_for_serving"])

    def test_failure_injections_fail_closed_without_reject_all(self) -> None:
        report = run_example()
        failures = report["failure_injections"]
        self.assertEqual(failures["authorization_revocation"]["result"], "FAIL")
        self.assertEqual(
            failures["authorization_revocation"]["disposition"],
            "BLOCKED",
        )
        self.assertEqual(
            failures["content_quarantine_changed"]["result"],
            "FAIL",
        )
        self.assertEqual(failures["detector_timeout"]["result"], "INCONCLUSIVE")
        self.assertEqual(failures["dlp_timeout"]["result"], "INCONCLUSIVE")
        self.assertEqual(
            failures["reject_all_quality_gate"]["normal_quality_gate"],
            "FAIL",
        )
        self.assertEqual(report["evaluation"]["result"], "PASS")

    def test_cache_pinning_and_incident_history_are_explicit(self) -> None:
        report = run_example()
        cache = report["cache"]
        self.assertEqual(cache["old_request_generation"], "G2")
        self.assertEqual(cache["new_request_generation"], "G3")
        self.assertTrue(cache["old_request_remains_pinned"])
        self.assertTrue(cache["cache_identity_changed"])
        incident = report["incident"]
        self.assertTrue(incident["append_only"])
        self.assertEqual(incident["states"], ["OPEN", "CONTAINED"])
        self.assertFalse(incident["raw_secret_logged"])

    def test_report_is_content_safe_and_not_production_evidence(self) -> None:
        report = run_example()
        serialized = json.dumps(report, sort_keys=True).lower()
        for forbidden in (
            "instruction override payload",
            "raw-secret-value",
            "protected chunk body",
            "system prompt body",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(report["fixture_production_eligible"])
        self.assertEqual(
            report["production_readiness"],
            "MORE_EVIDENCE_NEEDED",
        )
        self.assertFalse(report["raw_attack_payloads_logged"])
        self.assertFalse(report["raw_protected_content_logged"])
        self.assertFalse(report["raw_secrets_logged"])


if __name__ == "__main__":
    unittest.main()
