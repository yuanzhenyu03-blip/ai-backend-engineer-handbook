from __future__ import annotations

import unittest

from rag_vector_store_selection import (
    FROZEN_WEIGHTS,
    HardGateStatus,
    VectorStoreCandidate,
    evaluate_candidates,
    run_store_selection_experiment,
)


def _scores(value: float) -> tuple[tuple[str, float], ...]:
    return tuple((name, value) for name in FROZEN_WEIGHTS)


class Day99StoreSelectionTests(unittest.TestCase):
    def test_saved_classroom_selection_is_evidence_bounded(self) -> None:
        result = run_store_selection_experiment()
        self.assertEqual(
            result["selected_candidate_id"],
            "postgresql-pgvector-0.8.7",
        )
        self.assertEqual(result["outcome"], "PROVISIONAL_SELECTED")
        self.assertEqual(result["real_database_execution"], "NOT_RUN")

    def test_unknown_or_failed_hard_gate_cannot_be_outscored(self) -> None:
        candidates = (
            VectorStoreCandidate(
                "pgvector-0.8.7",
                "0.8.7",
                "SELF_HOSTED_POSTGRES",
                (("protected_vector_egress", HardGateStatus.PASS),),
                _scores(60.0),
                ("real runtime NOT RUN",),
            ),
            VectorStoreCandidate(
                "pinecone-api-2025-10",
                "2025-10",
                "MANAGED",
                (("protected_vector_egress", HardGateStatus.UNKNOWN),),
                _scores(100.0),
                ("protected-vector egress approval UNKNOWN",),
            ),
            VectorStoreCandidate(
                "qdrant-1.20.0",
                "1.20.0",
                "SELF_HOSTED_OR_MANAGED",
                (("backup_restore", HardGateStatus.FAIL),),
                _scores(99.0),
                ("classroom restore gate failed",),
            ),
        )
        result = evaluate_candidates(candidates)
        self.assertEqual(result["selected_candidate_id"], "pgvector-0.8.7")
        rows = {row["candidate_id"]: row for row in result["candidates"]}
        self.assertIsNone(rows["pinecone-api-2025-10"]["weighted_score"])
        self.assertIsNone(rows["qdrant-1.20.0"]["weighted_score"])
        self.assertEqual(result["real_database_execution"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
