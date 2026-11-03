from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day100_hybrid_retrieval_filtering import build_day100_fixture
from rag_lexical_retrieval import BM25ReferenceIndex
from rag_retrieval_filters import FilterExpression


class Day100LexicalBM25Tests(unittest.TestCase):
    def test_bm25_returns_deterministic_ranked_occurrences(self) -> None:
        fixture = build_day100_fixture()
        left = fixture.lexical.search(
            query_text="refund policy",
            bundle=fixture.bundle,
            scope=fixture.scope,
            business_filter=None,
            system_excluded_occurrence_ids=(),
            offset=0,
            limit=5,
        )
        right = fixture.lexical.search(
            query_text="refund policy",
            bundle=fixture.bundle,
            scope=fixture.scope,
            business_filter=None,
            system_excluded_occurrence_ids=(),
            offset=0,
            limit=5,
        )
        self.assertEqual(left, right)
        self.assertEqual(tuple(item.branch_rank for item in left), tuple(range(1, len(left) + 1)))

    def test_unauthorized_occurrence_never_enters_normal_branch(self) -> None:
        fixture = build_day100_fixture()
        results = fixture.lexical.search(
            query_text="refund",
            bundle=fixture.bundle,
            scope=fixture.scope,
            business_filter=None,
            system_excluded_occurrence_ids=(),
            offset=0,
            limit=10,
        )
        self.assertNotIn("occurrence:X", {
            item.identity.occurrence_id for item in results
        })

    def test_business_filter_intersects_authorization_scope(self) -> None:
        fixture = build_day100_fixture()
        results = fixture.lexical.search(
            query_text="refund",
            bundle=fixture.bundle,
            scope=fixture.scope,
            business_filter=FilterExpression.eq("category", "finance"),
            system_excluded_occurrence_ids=(),
            offset=0,
            limit=10,
        )
        self.assertEqual(
            {item.identity.occurrence_id for item in results},
            {"occurrence:A", "occurrence:A2"},
        )

    def test_same_text_different_occurrences_are_preserved(self) -> None:
        fixture = build_day100_fixture()
        results = fixture.lexical.search(
            query_text="refund policy",
            bundle=fixture.bundle,
            scope=fixture.scope,
            business_filter=None,
            system_excluded_occurrence_ids=(),
            offset=0,
            limit=10,
        )
        ids = {item.identity.occurrence_id for item in results}
        self.assertIn("occurrence:A", ids)
        self.assertIn("occurrence:A2", ids)
        a, a2 = fixture.records[0], fixture.records[4]
        self.assertEqual(a.identity.content_hash, a2.identity.content_hash)
        self.assertNotEqual(a.identity.occurrence_id, a2.identity.occurrence_id)

    def test_unknown_terms_return_no_candidates(self) -> None:
        fixture = build_day100_fixture()
        results = fixture.lexical.search(
            query_text="unicorn-never-present",
            bundle=fixture.bundle,
            scope=fixture.scope,
            business_filter=None,
            system_excluded_occurrence_ids=(),
            offset=0,
            limit=10,
        )
        self.assertEqual(results, ())

    def test_bm25_contract_rejects_invalid_k1_and_b(self) -> None:
        fixture = build_day100_fixture()
        with self.assertRaises(ValueError):
            replace(fixture.bundle.lexical, k1=0)
        with self.assertRaises(ValueError):
            replace(fixture.bundle.lexical, b=1.1)

    def test_analyzer_version_changes_contract_fingerprint(self) -> None:
        fixture = build_day100_fixture()
        changed = replace(
            fixture.bundle.lexical,
            analyzer_version="lowercase-word-analyzer-v2",
        )
        self.assertNotEqual(
            fixture.bundle.lexical.fingerprint,
            changed.fingerprint,
        )
        self.assertIsInstance(
            BM25ReferenceIndex(contract=changed, records=fixture.records),
            BM25ReferenceIndex,
        )


if __name__ == "__main__":
    unittest.main()
