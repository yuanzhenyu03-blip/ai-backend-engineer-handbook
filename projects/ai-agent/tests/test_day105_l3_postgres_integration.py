"""Opt-in real PostgreSQL/pgvector checks for Day105 L3 security."""

from __future__ import annotations

import json
import os
from typing import Any, cast
import unittest

from evals.run_day105_l3_integration import run_integration


DATABASE_URL = os.environ.get("DAY105_L3_DATABASE_URL", "")
INTEGRATION_ENABLED = os.environ.get("DAY105_L3_INTEGRATION") == "1" and bool(
    DATABASE_URL.strip()
)


@unittest.skipUnless(
    INTEGRATION_ENABLED,
    "set DAY105_L3_INTEGRATION=1 and DAY105_L3_DATABASE_URL to run",
)
class Day105RealPostgresPgvectorSecurityTests(unittest.TestCase):
    report: dict[str, object]

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_integration(DATABASE_URL)

    def test_schema_postgresql_pgvector_and_runner_pass(self) -> None:
        self.assertEqual(self.report["status"], "PASS")
        evidence_level = cast(str, self.report["evidence_level"])
        self.assertIn("POSTGRESQL_PGVECTOR", evidence_level)
        environment = cast(dict[str, Any], self.report["environment"])
        self.assertEqual(environment["pgvector_extension_version"], "0.8.7")
        server_version_num = cast(str, environment["postgresql_server_version_num"])
        self.assertTrue(server_version_num.isdigit())
        self.assertEqual(
            environment["transaction_isolation"],
            ["READ COMMITTED", "REPEATABLE READ"],
        )
        pre_restart_identity = cast(
            str,
            environment["pre_restart_state_identity_digest"],
        )
        self.assertTrue(pre_restart_identity.startswith("sha256:"))
        gates = cast(dict[str, dict[str, object]], self.report["hard_gates"])
        self.assertEqual(gates["schema_migration_integrity"]["status"], "PASS")
        self.assertEqual(
            gates["postgresql_pgvector_identity_match"]["status"],
            "PASS",
        )

    def test_poisoned_generation_manifest_never_serves(self) -> None:
        lifecycle = cast(dict[str, Any], self.report["lifecycle"])
        poisoned = lifecycle["poisoned_generation"]
        self.assertEqual(poisoned["generation_id"], "G_BAD")
        self.assertEqual(poisoned["seal_outcome"], "INTEGRITY_FAILED")
        self.assertEqual(poisoned["final_state"], "FAILED")
        self.assertFalse(poisoned["selected_for_serving"])
        self.assertEqual(lifecycle["pointer"], {"generation_id": "G3", "revision": 9})

    def test_g2_exact_and_hnsw_preserve_q1_q2_q3_and_b_absence(self) -> None:
        matrix = cast(dict[str, dict[str, list[str]]], self.report["normal_retrieval"])
        expected = {
            "Q1": ["A@v1"],
            "Q2": ["C@v1"],
            "Q3": ["A@v1", "C@v1"],
        }
        self.assertEqual(matrix["EXACT"], expected)
        self.assertEqual(matrix["HNSW"], expected)
        self.assertNotIn("B@v1", json.dumps(matrix, sort_keys=True))

    def test_x_y_z_t_and_versioned_y_rescan_fail_closed(self) -> None:
        controls = cast(
            dict[str, dict[str, object]], self.report["adversarial_controls"]
        )
        self.assertEqual(controls["X"]["bundle_result"], "FAIL")
        self.assertEqual(controls["Y"]["detector_result"], "INCONCLUSIVE")
        self.assertEqual(controls["Y"]["serving_action"], "QUARANTINE")
        self.assertEqual(controls["Z"]["bundle_result"], "FAIL")
        self.assertEqual(controls["T"]["retrieval_result"], "FAIL")
        self.assertEqual(controls["T"]["sql_tenant_filter_count"], 0)
        records = cast(dict[str, str], self.report["versioned_detector_records"])
        self.assertNotEqual(records["y_v1_digest"], records["y_v2_digest"])
        self.assertNotEqual(records["y_v1_artifact_id"], records["y_v2_artifact_id"])

    def test_context_exact_manifest_and_tamper_controls(self) -> None:
        failures = cast(list[dict[str, object]], self.report["failure_injections"])
        by_id = {item["checkpoint_id"]: item for item in failures}
        self.assertEqual(
            by_id["context-projection-digest-tamper"]["status"],
            "PASS",
        )
        self.assertEqual(
            by_id["manifest-content-or-metadata-substitution"]["status"],
            "PASS",
        )
        gates = cast(dict[str, dict[str, object]], self.report["hard_gates"])
        self.assertEqual(gates["context_assembly_exact_manifest"]["status"], "PASS")

    def test_p1_g2_r8_to_p2_g3_r9_keeps_old_request_bound_and_blocked(self) -> None:
        transition = cast(dict[str, object], self.report["authorization_transition"])
        self.assertEqual(transition["old_generation_id"], "G2")
        self.assertEqual(transition["old_pointer_revision"], 8)
        self.assertTrue(transition["old_request_remained_pinned"])
        self.assertEqual(
            transition["old_query_after_P2"],
            "CURRENT_AUTHORIZATION_CHANGED",
        )
        self.assertEqual(transition["old_release_result"], "FAIL")
        self.assertEqual(transition["old_release_disposition"], "BLOCKED")
        self.assertGreaterEqual(
            cast(int, transition["old_read_view_lease_duration_seconds"]),
            3600,
        )
        self.assertTrue(cast(bool, transition["restart_window_open_at_completion"]))
        self.assertEqual(transition["new_generation_id"], "G3")
        self.assertEqual(transition["new_pointer_revision"], 9)
        self.assertEqual(transition["new_query_ids"], ["C@v1"])
        self.assertTrue(transition["cross_generation_bundle_rejected"])

    def test_release_dlp_citation_and_database_intent_guards_fail_closed(self) -> None:
        cases = cast(list[dict[str, object]], self.report["security_cases"])
        by_id = {item["case_id"]: item for item in cases}
        for case_id, stage in (
            ("wrong-citation-blocked", "FAIL"),
            ("dlp-timeout-blocked", "INCONCLUSIVE"),
            ("dlp-sensitive-blocked", "FAIL"),
        ):
            self.assertEqual(by_id[case_id]["observed_stage_result"], stage)
            self.assertEqual(by_id[case_id]["serving_action"], "BLOCKED")
            self.assertEqual(by_id[case_id]["released_citation_occurrence_ids"], [])
        persistence = cast(dict[str, Any], self.report["security_persistence"])
        guards = persistence["database_guards"]
        self.assertTrue(guards["mismatched_action_rejected"])
        self.assertTrue(guards["mismatched_candidate_rejected"])
        self.assertTrue(guards["sensitive_value_rejected"])

    def test_append_only_cas_atomicity_orphan_and_incident_history(self) -> None:
        persistence = cast(dict[str, Any], self.report["security_persistence"])
        self.assertEqual(persistence["current_snapshot_id"], "P2")
        self.assertEqual(persistence["current_revision"], 2)
        self.assertEqual(
            persistence["snapshot_cas_race"],
            ["APPLIED", "STALE_REVISION"],
        )
        self.assertTrue(persistence["transition_fault"]["fault_raised"])
        self.assertEqual(persistence["transition_fault"]["current_pointer_count"], 0)
        self.assertTrue(persistence["append_only_mutation_rejected"])
        self.assertEqual(persistence["artifact_replay"]["replay"], "EXACT_REPLAY")
        self.assertEqual(
            persistence["artifact_replay"]["conflict"],
            "IDENTITY_CONFLICT",
        )
        orphan = persistence["orphan_release_fault"]
        self.assertEqual(orphan["candidate_count"], 1)
        self.assertEqual(orphan["release_decision_count"], 0)
        self.assertEqual(orphan["response_intent_count"], 0)
        self.assertEqual(orphan["default_serving_action"], "BLOCKED")
        self.assertEqual(persistence["incident"]["states"], ["OPEN", "CONTAINED"])
        self.assertEqual(persistence["incident"]["branch"], "IDENTITY_CONFLICT")

    def test_report_is_content_safe_and_preserves_production_boundary(self) -> None:
        serialized = json.dumps(self.report, sort_keys=True).lower()
        for forbidden in (
            "postgresql://",
            "day105_l3_database_url",
            "raw-secret-value",
            "protected chunk body",
            "system prompt body",
            "instruction override payload",
        ):
            self.assertNotIn(forbidden, serialized)
        for key in (
            "raw_attack_payloads_logged",
            "raw_protected_content_logged",
            "raw_system_prompts_logged",
            "raw_secrets_logged",
            "raw_cross_tenant_content_logged",
            "raw_vectors_logged",
            "database_url_logged",
            "fixture_production_eligible",
        ):
            self.assertFalse(self.report[key])
        self.assertEqual(self.report["production_readiness"], "MORE_EVIDENCE_NEEDED")
        cases = cast(list[dict[str, object]], self.report["security_cases"])
        self.assertEqual(len(cases), 14)
        self.assertTrue(all(item["defense_outcome"] == "PASS" for item in cases))


if __name__ == "__main__":
    unittest.main()
