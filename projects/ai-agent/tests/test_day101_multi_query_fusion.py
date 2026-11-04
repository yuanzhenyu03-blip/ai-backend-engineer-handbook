from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day101_query_rewriting_reranking import build_day101_fixture
from rag_multi_query_fusion import (
    MultiQueryFusionError,
    fuse_multi_query_results,
)
from rag_multi_query_retrieval import MultiQueryRetrievalReport, VariantRetrievalResult
from day101_test_support import build_intermediate


class Day101MultiQueryFusionTests(unittest.TestCase):
    def test_occurrence_ids_are_unique_but_keep_all_variant_evidence(self) -> None:
        fixture = build_day101_fixture()
        _, _, _, retrieval, pool, _ = build_intermediate(fixture)
        ids = tuple(item.identity.occurrence_id for item in pool.candidates)
        self.assertEqual(len(ids), len(set(ids)))
        repeated = next(
            item for item in pool.candidates
            if item.identity.occurrence_id == "occurrence:B"
        )
        self.assertGreater(len(repeated.evidence), 1)

    def test_multi_query_fusion_is_deterministic(self) -> None:
        fixture = build_day101_fixture()
        _, _, _, retrieval, pool, _ = build_intermediate(fixture)
        again = fuse_multi_query_results(retrieval, fixture.pipeline.fusion_policy)
        self.assertEqual(pool.digest, again.digest)
        self.assertEqual(
            tuple(item.identity.occurrence_id for item in pool.candidates),
            tuple(item.identity.occurrence_id for item in again.candidates),
        )

    def test_same_text_different_occurrences_are_not_merged(self) -> None:
        fixture = build_day101_fixture()
        _, _, _, _, pool, _ = build_intermediate(fixture)
        ids = {item.identity.occurrence_id for item in pool.candidates}
        self.assertIn("occurrence:A", ids)
        self.assertIn("occurrence:A2", ids)

    def test_conflicting_occurrence_identity_fails_closed(self) -> None:
        fixture = build_day101_fixture()
        _, _, _, retrieval, _, _ = build_intermediate(fixture)
        first = retrieval.results[0]
        hit = first.response.hits[0]
        conflicting = replace(
            hit, identity=replace(hit.identity, document_id="other-document")
        )
        conflicting_response = replace(first.response, hits=(conflicting,))
        report = MultiQueryRetrievalReport(
            retrieval.rewrite_set_fingerprint,
            retrieval.results + (
                VariantRetrievalResult(first.variant, conflicting_response),
            ),
            (),
            retrieval.candidate_observations + 1,
        )
        with self.assertRaisesRegex(
            MultiQueryFusionError, "MULTI_QUERY_OCCURRENCE_IDENTITY_CONFLICT"
        ):
            fuse_multi_query_results(report, fixture.pipeline.fusion_policy)


if __name__ == "__main__":
    unittest.main()
