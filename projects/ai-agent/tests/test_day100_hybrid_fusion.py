from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day100_hybrid_retrieval_filtering import build_day100_fixture
from rag_hybrid_fusion import FusionError, reciprocal_rank_fusion
from rag_retrieval_contracts import (
    BranchCandidate,
    RetrievalBranch,
    ScoreDirection,
)


class Day100HybridFusionTests(unittest.TestCase):
    def _candidate(
        self,
        fixture,
        occurrence: str,
        branch: RetrievalBranch,
        rank: int,
        score: float,
    ) -> BranchCandidate:
        record = next(
            item for item in fixture.records
            if item.identity.occurrence_id == occurrence
        )
        return BranchCandidate(
            record.identity,
            branch,
            rank,
            score,
            ScoreDirection.HIGHER_IS_BETTER,
            fixture.bundle.generation_id,
            fixture.bundle.lexical_corpus_generation_id,
            fixture.bundle.fingerprint,
            record.metadata,
        )

    def test_rrf_expected_order_uses_ranks(self) -> None:
        fixture = build_day100_fixture()
        candidates = (
            self._candidate(fixture, "occurrence:A", RetrievalBranch.LEXICAL, 1, 12.4),
            self._candidate(fixture, "occurrence:C", RetrievalBranch.LEXICAL, 2, 7.8),
            self._candidate(fixture, "occurrence:B", RetrievalBranch.LEXICAL, 3, 1.2),
            self._candidate(fixture, "occurrence:B", RetrievalBranch.DENSE, 1, 0.91),
            self._candidate(fixture, "occurrence:A", RetrievalBranch.DENSE, 2, 0.83),
        )
        fused = reciprocal_rank_fusion(candidates, policy=fixture.bundle.fusion_policy)
        self.assertEqual(
            tuple(item.identity.occurrence_id for item in fused),
            ("occurrence:A", "occurrence:B", "occurrence:C"),
        )

    def test_raw_score_magnitudes_do_not_change_rrf_order(self) -> None:
        fixture = build_day100_fixture()
        baseline = (
            self._candidate(fixture, "occurrence:A", RetrievalBranch.LEXICAL, 1, 1.0),
            self._candidate(fixture, "occurrence:B", RetrievalBranch.DENSE, 1, 0.1),
        )
        changed = (
            replace(baseline[0], raw_score=1_000_000.0),
            replace(baseline[1], raw_score=-0.9),
        )
        left = reciprocal_rank_fusion(
            baseline, policy=fixture.bundle.fusion_policy
        )
        right = reciprocal_rank_fusion(
            changed, policy=fixture.bundle.fusion_policy
        )
        self.assertEqual(
            tuple((item.identity.key, item.rrf_score) for item in left),
            tuple((item.identity.key, item.rrf_score) for item in right),
        )

    def test_same_occurrence_from_two_branches_is_merged(self) -> None:
        fixture = build_day100_fixture()
        fused = reciprocal_rank_fusion((
            self._candidate(fixture, "occurrence:A", RetrievalBranch.LEXICAL, 1, 1.0),
            self._candidate(fixture, "occurrence:A", RetrievalBranch.DENSE, 2, 0.8),
        ), policy=fixture.bundle.fusion_policy)
        self.assertEqual(len(fused), 1)
        self.assertEqual(len(fused[0].branch_candidates), 2)

    def test_same_content_different_occurrences_are_not_deduplicated(self) -> None:
        fixture = build_day100_fixture()
        self.assertEqual(
            fixture.records[0].identity.content_hash,
            fixture.records[4].identity.content_hash,
        )
        fused = reciprocal_rank_fusion((
            self._candidate(fixture, "occurrence:A", RetrievalBranch.LEXICAL, 1, 1.0),
            self._candidate(fixture, "occurrence:A2", RetrievalBranch.LEXICAL, 2, 0.9),
        ), policy=fixture.bundle.fusion_policy)
        self.assertEqual(len(fused), 2)

    def test_duplicate_branch_candidate_keeps_best_rank(self) -> None:
        fixture = build_day100_fixture()
        fused = reciprocal_rank_fusion((
            self._candidate(fixture, "occurrence:A", RetrievalBranch.LEXICAL, 5, 10.0),
            self._candidate(fixture, "occurrence:A", RetrievalBranch.LEXICAL, 1, 1.0),
        ), policy=fixture.bundle.fusion_policy)
        self.assertEqual(fused[0].best_branch_rank, 1)

    def test_exact_tie_uses_occurrence_identity(self) -> None:
        fixture = build_day100_fixture()
        fused = reciprocal_rank_fusion((
            self._candidate(fixture, "occurrence:B", RetrievalBranch.LEXICAL, 1, 1.0),
            self._candidate(fixture, "occurrence:A", RetrievalBranch.LEXICAL, 1, 1.0),
        ), policy=fixture.bundle.fusion_policy)
        self.assertEqual(
            tuple(item.identity.occurrence_id for item in fused),
            ("occurrence:A", "occurrence:B"),
        )

    def test_occurrence_identity_conflict_fails_closed(self) -> None:
        fixture = build_day100_fixture()
        candidate = self._candidate(
            fixture, "occurrence:A", RetrievalBranch.LEXICAL, 1, 1.0
        )
        conflicting_identity = replace(
            candidate.identity,
            document_id="different-document",
        )
        with self.assertRaises(FusionError):
            reciprocal_rank_fusion((
                candidate,
                replace(
                    candidate,
                    identity=conflicting_identity,
                    branch=RetrievalBranch.DENSE,
                ),
            ), policy=fixture.bundle.fusion_policy)


if __name__ == "__main__":
    unittest.main()
