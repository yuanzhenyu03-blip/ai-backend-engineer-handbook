from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day101_query_rewriting_reranking import (
    build_day101_fixture,
    day101_request,
)
from rag_multi_query_retrieval import (
    Day100VariantRetrievalExecutor,
    MultiQueryExecutionPolicy,
    MultiQueryRetrievalError,
)


class Day101MultiQueryPlanningTests(unittest.TestCase):
    def test_every_variant_reuses_day100_retriever(self) -> None:
        fixture = build_day101_fixture()
        request = day101_request(fixture)
        original = fixture.pipeline._original_query(request)
        rewrite_set = fixture.pipeline.rewriter.rewrite(original)
        report = fixture.pipeline.multi_query.execute(
            base_request=request, rewrite_set=rewrite_set
        )
        self.assertEqual(len(report.results), len(rewrite_set.variants))
        self.assertEqual(
            len(fixture.day100.encoder_provider.calls), len(rewrite_set.variants)
        )
        self.assertEqual(len(fixture.day100.audit.events()), len(rewrite_set.variants))

    def test_variant_budget_is_enforced_before_retrieval(self) -> None:
        fixture = build_day101_fixture()
        request = day101_request(fixture)
        original = fixture.pipeline._original_query(request)
        rewrite_set = fixture.pipeline.rewriter.rewrite(original)
        executor = Day100VariantRetrievalExecutor(
            fixture.day100.retriever,
            MultiQueryExecutionPolicy("tiny", 2, 15, False),
        )
        with self.assertRaisesRegex(
            MultiQueryRetrievalError, "MULTI_QUERY_VARIANT_BUDGET_EXCEEDED"
        ):
            executor.execute(base_request=request, rewrite_set=rewrite_set)

    def test_candidate_observation_budget_is_enforced(self) -> None:
        fixture = build_day101_fixture()
        request = day101_request(fixture)
        original = fixture.pipeline._original_query(request)
        rewrite_set = fixture.pipeline.rewriter.rewrite(original)
        executor = Day100VariantRetrievalExecutor(
            fixture.day100.retriever,
            MultiQueryExecutionPolicy("tiny", 3, 1, False),
        )
        with self.assertRaisesRegex(
            MultiQueryRetrievalError,
            "MULTI_QUERY_CANDIDATE_OBSERVATION_BUDGET_EXCEEDED",
        ):
            executor.execute(base_request=request, rewrite_set=rewrite_set)

    def test_variant_changes_only_query_and_operation_identity(self) -> None:
        fixture = build_day101_fixture()
        request = day101_request(fixture)
        original = fixture.pipeline._original_query(request)
        rewrite_set = fixture.pipeline.rewriter.rewrite(original)
        report = fixture.pipeline.multi_query.execute(
            base_request=request, rewrite_set=rewrite_set
        )
        self.assertTrue(all(
            event.tenant_id == request.tenant_id
            for event in fixture.day100.audit.events()
        ))
        self.assertTrue(all(
            result.response.bundle_id == fixture.day100.bundle.bundle_id
            for result in report.results
        ))


if __name__ == "__main__":
    unittest.main()
