"""Opt-in real PostgreSQL + pgvector checks for the Day104 lifecycle.

The suite is skipped unless the caller explicitly supplies both the integration
flag and a disposable database URL.  The scenario resets only the ``day104_l3``
schema in that database.
"""

from __future__ import annotations

import json
import os
from typing import Any, cast
import unittest

from evals.run_day104_l3_integration import run_integration


DATABASE_URL = os.environ.get("DAY104_L3_DATABASE_URL", "")
INTEGRATION_ENABLED = os.environ.get("DAY104_L3_INTEGRATION") == "1" and bool(
    DATABASE_URL.strip()
)


@unittest.skipUnless(
    INTEGRATION_ENABLED,
    "set DAY104_L3_INTEGRATION=1 and DAY104_L3_DATABASE_URL to run",
)
class Day104RealPostgresPgvectorIntegrationTests(unittest.TestCase):
    report: dict[str, object]

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_integration(DATABASE_URL)

    def test_all_executed_scenario_gates_pass(self) -> None:
        self.assertEqual(self.report["status"], "PASS")
        hard_gates = cast(dict[str, dict[str, object]], self.report["hard_gates"])
        self.assertTrue(hard_gates)
        self.assertEqual(
            {gate["status"] for gate in hard_gates.values()},
            {"PASS"},
        )
        self.assertTrue(
            {
                "build_snapshot_repeatable_read",
                "activation_transaction_atomicity",
                "concurrent_pointer_cas",
                "outbox_inbox_reconciliation",
                "restart_durability_and_idempotency",
            }.issubset(hard_gates)
        )

    def test_repeatable_read_freshness_and_activation_atomicity(self) -> None:
        repeatable = cast(dict[str, Any], self.report["repeatable_read"])
        activation = cast(dict[str, Any], self.report["activation"])

        self.assertEqual(repeatable["connection_1_first"], ["BS1", 1])
        self.assertEqual(
            repeatable["connection_2_committed"],
            ["BS-drift", 2],
        )
        self.assertEqual(repeatable["connection_1_second"], ["BS1", 1])
        self.assertEqual(repeatable["restored_current"], ["BS1", 3])
        self.assertEqual(
            repeatable["stale_activation_outcome"],
            "STALE_POINTER",
        )
        self.assertTrue(activation["fault_injection_raised"])
        self.assertEqual(
            activation["atomicity_before"],
            activation["atomicity_after"],
        )
        footprint = activation["atomicity_after"]
        self.assertEqual(
            footprint["pointer"],
            {"generation_id": "G1", "revision": 7},
        )
        self.assertEqual(footprint["G1"]["state"], "ACTIVE")
        self.assertEqual(footprint["G2"]["state"], "READY")
        self.assertEqual(footprint["activation_record_count"], 0)
        self.assertEqual(footprint["activation_outbox_count"], 0)

    def test_same_ruler_exact_and_hnsw_return_only_a_and_c(self) -> None:
        expected = {
            "Q1": ["A@v1"],
            "Q2": ["C@v1"],
            "Q3": ["A@v1", "C@v1"],
        }
        retrieval = cast(
            dict[str, dict[str, list[str]]],
            self.report["retrieval"],
        )
        hnsw_plan = cast(dict[str, object], self.report["hnsw_plan"])

        self.assertEqual(retrieval["EXACT"], expected)
        self.assertEqual(retrieval["HNSW"], expected)
        self.assertIs(hnsw_plan["uses_hnsw_index"], True)
        self.assertRegex(str(hnsw_plan["plan_digest"]), r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn("B@v1", json.dumps(retrieval, sort_keys=True))

    def test_fencing_and_two_connection_pointer_race(self) -> None:
        activation = cast(dict[str, Any], self.report["activation"])

        self.assertEqual(activation["stale_token_outcome"], "STALE_FENCE")
        self.assertEqual(
            activation["race_outcomes"],
            ["ACTIVATED", "STALE_POINTER"],
        )
        self.assertEqual(
            activation["active_pointer"],
            {"generation_id": "G2", "revision": 8},
        )

    def test_read_views_outbox_retirement_and_restart_are_durable(self) -> None:
        read_views = cast(dict[str, Any], self.report["read_views"])
        outbox = cast(dict[str, Any], self.report["outbox"])
        restarted = cast(dict[str, Any], self.report["application_restart"])

        self.assertEqual(read_views["old_generation"], "G1")
        self.assertEqual(read_views["new_generation"], "G2")
        self.assertEqual(read_views["old_generation_final_state"], "RETIRED")
        self.assertEqual(
            read_views["reaped_views"],
            ["read-view-abandoned-G2"],
        )
        self.assertEqual(outbox["first_apply"], "APPLIED")
        self.assertEqual(outbox["stale_claim_apply"], "STALE_FENCE")
        self.assertEqual(outbox["reclaimed_fence"], 2)
        self.assertEqual(outbox["exact_replay"], "EXACT_REPLAY")
        self.assertEqual(outbox["different_digest"], "IDENTITY_CONFLICT")
        self.assertEqual(outbox["inbox_record_count"], 2)
        self.assertTrue(restarted["new_repository_instance"])
        self.assertEqual(
            restarted["pointer"],
            {"generation_id": "G2", "revision": 8},
        )

    def test_deletion_evidence_verifies_without_claiming_physical_purge(
        self,
    ) -> None:
        deletion = cast(dict[str, Any], self.report["deletion_evidence"])

        self.assertEqual(deletion["intent_id"], "delete-B-v1")
        self.assertEqual(deletion["intent_state"], "VERIFIED")
        self.assertEqual(deletion["deletion_snapshot_id"], "D1")
        self.assertEqual(deletion["logical_release"]["status"], "PASS")
        self.assertEqual(
            deletion["serving_index_absence"]["status"],
            "PASS",
        )
        self.assertEqual(deletion["physical_purge"]["status"], "NOT_RUN")
        self.assertEqual(
            deletion["adopted_evidence_ids"],
            [
                "deletion-evidence-logical-release",
                "deletion-evidence-serving-index-absence",
            ],
        )
        self.assertEqual(deletion["verify_outcome"], "VERIFIED")
        self.assertEqual(deletion["verify_replay_outcome"], "EXACT_REPLAY")

    def test_report_is_content_safe_and_preserves_l4_boundary(self) -> None:
        serialized = json.dumps(self.report, sort_keys=True)
        forbidden_keys = {
            "database_url",
            "dsn",
            "password",
            "raw_content",
            "raw_vector",
        }

        def object_keys(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value).union(*(object_keys(item) for item in value.values()))
            if isinstance(value, list):
                return set().union(*(object_keys(item) for item in value))
            return set()

        self.assertTrue(forbidden_keys.isdisjoint(object_keys(self.report)))
        self.assertNotIn(DATABASE_URL, serialized)
        self.assertFalse(self.report["fixture_production_eligible"])
        self.assertFalse(self.report["raw_content_logged"])
        self.assertFalse(self.report["raw_vectors_logged"])
        self.assertEqual(
            self.report["production_readiness"],
            "MORE_EVIDENCE_NEEDED",
        )
        not_run = cast(list[str], self.report["not_run"])
        self.assertIn("database container restart", not_run)
        self.assertIn(
            "physical purge across WAL, backups and caches",
            not_run,
        )


if __name__ == "__main__":
    unittest.main()
