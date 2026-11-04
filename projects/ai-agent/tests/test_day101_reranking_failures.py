from __future__ import annotations

import unittest

from examples.day101_query_rewriting_reranking import (
    build_day101_fixture,
    day101_request,
)
from rag_query_rewrite_contracts import RewriteMode
from rag_query_rewriter import RewriteProviderMode
from rag_reranker_adapter import RerankerProviderMode
from rag_reranker_contracts import (
    Day101Outcome,
    RawRerankerItem,
    RawRerankerResponse,
    RerankingMode,
)
from day101_test_support import build_intermediate


class Day101RerankingFailureTests(unittest.TestCase):
    def test_rewrite_timeout_is_explicit_original_only_fallback(self) -> None:
        fixture = build_day101_fixture(
            rewrite_provider_mode=RewriteProviderMode.TIMEOUT
        )
        result = fixture.pipeline.execute(day101_request(fixture))
        self.assertEqual(result.rewrite_mode, RewriteMode.ORIGINAL_ONLY_FALLBACK.value)
        self.assertEqual(result.outcome, Day101Outcome.DEGRADED)

    def test_reranker_failure_is_explicit_unreranked_fallback(self) -> None:
        fixture = build_day101_fixture(
            reranker_provider_mode=RerankerProviderMode.FAILED
        )
        result = fixture.pipeline.execute(day101_request(fixture))
        self.assertEqual(result.reranking_mode, RerankingMode.UNRERANKED_FALLBACK)
        self.assertEqual(result.safe_reason, "RERANKER_FAILED")
        self.assertEqual(result.outcome, Day101Outcome.DEGRADED)

    def test_reranker_egress_denied_makes_zero_reranker_calls(self) -> None:
        fixture = build_day101_fixture(allow_reranker_egress=False)
        result = fixture.pipeline.execute(day101_request(fixture))
        self.assertEqual(result.reranking_mode, RerankingMode.UNRERANKED_FALLBACK)
        self.assertEqual(result.reranker_provider_calls, 0)
        self.assertEqual(result.safe_reason, "RERANK_EGRESS_DENIED")

    def test_invalid_output_discards_entire_result_and_falls_back(self) -> None:
        fixture = build_day101_fixture()
        *_, request = build_intermediate(fixture)
        count = len(request.items)
        results = [RawRerankerItem(index, 1.0) for index in range(count)]
        results[-1] = RawRerankerItem(0, 0.5)
        fixture.reranker._response_override = RawRerankerResponse(
            request.attempt_id,
            request.candidate_pool_digest,
            request.reranker_contract_fingerprint,
            tuple(results),
        )
        result = fixture.pipeline.execute(day101_request(fixture))
        self.assertEqual(result.reranking_mode, RerankingMode.UNRERANKED_FALLBACK)
        self.assertEqual(result.safe_reason, "RERANKER_OUTPUT_INVALID")
        self.assertIsNone(result.validated_rerank_digest)


if __name__ == "__main__":
    unittest.main()
