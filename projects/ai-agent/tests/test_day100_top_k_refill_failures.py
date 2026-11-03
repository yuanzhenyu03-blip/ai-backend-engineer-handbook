from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day100_hybrid_retrieval_filtering import (
    build_day100_fixture,
    retrieval_request,
)
from rag_dense_retrieval import DenseMode
from rag_lexical_retrieval import LexicalMode
from rag_retrieval_contracts import (
    DegradationReason,
    RetrievalBranch,
    RetrievalOutcome,
)
from rag_retrieval_filters import FilterExpression


class Day100TopKRefillFailureTests(unittest.TestCase):
    def test_egress_denial_can_be_explicit_lexical_only_partial(self) -> None:
        fixture = build_day100_fixture()
        result = fixture.retriever.retrieve(retrieval_request(
            fixture,
            query_text="alice@example.com refund policy",
            top_k=2,
        ))
        self.assertEqual(result.outcome, RetrievalOutcome.PARTIAL)
        self.assertEqual(result.degradation_reason, DegradationReason.DENSE_EGRESS_DENIED)
        self.assertIn(RetrievalBranch.DENSE, result.missing_branches)
        self.assertEqual(result.provider_calls, 0)
        self.assertGreater(result.database_calls, 0)

    def test_dense_timeout_is_not_labeled_full_hybrid(self) -> None:
        fixture = build_day100_fixture(dense_mode=DenseMode.TIMEOUT)
        result = fixture.retriever.retrieve(retrieval_request(fixture, top_k=2))
        self.assertEqual(result.outcome, RetrievalOutcome.PARTIAL)
        self.assertEqual(result.degradation_reason, DegradationReason.DENSE_BRANCH_FAILED)
        self.assertIn(RetrievalBranch.DENSE, result.missing_branches)

    def test_lexical_timeout_can_be_dense_only_partial(self) -> None:
        fixture = build_day100_fixture(lexical_mode=LexicalMode.TIMEOUT)
        result = fixture.retriever.retrieve(retrieval_request(fixture, top_k=2))
        self.assertEqual(result.outcome, RetrievalOutcome.PARTIAL)
        self.assertEqual(result.degradation_reason, DegradationReason.LEXICAL_BRANCH_FAILED)
        self.assertIn(RetrievalBranch.LEXICAL, result.missing_branches)

    def test_both_branch_failures_are_unavailable_not_partial(self) -> None:
        fixture = build_day100_fixture(
            lexical_mode=LexicalMode.TIMEOUT,
            dense_mode=DenseMode.TIMEOUT,
        )
        result = fixture.retriever.retrieve(retrieval_request(fixture, top_k=2))
        self.assertEqual(result.outcome, RetrievalOutcome.UNAVAILABLE)
        self.assertEqual(result.safe_reason, "NO_RETRIEVAL_BRANCH_COMPLETED")
        self.assertEqual(result.hits, ())

    def test_refill_budget_exhaustion_is_explicit(self) -> None:
        fixture = build_day100_fixture()
        limited = replace(
            fixture.bundle,
            bundle_id="synthetic-selected-retrieval-bundle-v2",
            revision=2,
            retrieval_policy=replace(
                fixture.bundle.retrieval_policy,
                max_refill_rounds=1,
                max_candidate_budget=2,
                max_candidate_depth=2,
            ),
            fusion_policy=replace(
                fixture.bundle.fusion_policy,
                candidate_depth=1,
            ),
        )
        fixture.bundles.select(limited)
        result = fixture.retriever.retrieve(retrieval_request(fixture, top_k=3))
        self.assertEqual(result.outcome, RetrievalOutcome.PARTIAL)
        self.assertEqual(
            result.degradation_reason,
            DegradationReason.REFILL_BUDGET_EXHAUSTED,
        )
        self.assertLess(len(result.hits), 3)
        self.assertLessEqual(result.candidates_examined, 2)

    def test_refill_deadline_is_bounded(self) -> None:
        fixture = build_day100_fixture()
        limited = replace(
            fixture.bundle,
            bundle_id="synthetic-selected-retrieval-bundle-deadline",
            revision=2,
            fusion_policy=replace(
                fixture.bundle.fusion_policy,
                candidate_depth=1,
            ),
        )
        fixture.bundles.select(limited)
        original = fixture.lexical.search

        def advance_clock(**kwargs):
            result = original(**kwargs)
            fixture.clock.value += 1
            return result

        fixture.lexical.search = advance_clock  # type: ignore[method-assign]
        result = fixture.retriever.retrieve(retrieval_request(fixture, top_k=5))
        self.assertEqual(result.outcome, RetrievalOutcome.PARTIAL)
        self.assertEqual(
            result.degradation_reason,
            DegradationReason.DEADLINE_EXHAUSTED,
        )

    def test_exhausted_authorized_corpus_can_return_full_fewer_than_k(self) -> None:
        fixture = build_day100_fixture()
        result = fixture.retriever.retrieve(retrieval_request(
            fixture,
            top_k=5,
            client_filter=FilterExpression.eq("category", "never-matches"),
        ))
        self.assertEqual(result.outcome, RetrievalOutcome.EMPTY)
        self.assertEqual(result.degradation_reason, DegradationReason.NONE)
        self.assertEqual(result.hits, ())

    def test_refill_never_adds_unauthorized_occurrence(self) -> None:
        fixture = build_day100_fixture(dense_mode=DenseMode.LEAK_UNAUTHORIZED)
        result = fixture.retriever.retrieve(retrieval_request(fixture, top_k=5))
        self.assertNotIn("occurrence:X", {
            hit.identity.occurrence_id for hit in result.hits
        })


if __name__ == "__main__":
    unittest.main()
