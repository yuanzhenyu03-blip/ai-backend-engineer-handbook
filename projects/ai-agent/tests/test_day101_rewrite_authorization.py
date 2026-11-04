from __future__ import annotations

import unittest

from examples.day101_query_rewriting_reranking import (
    build_day101_fixture,
    day101_request,
)
from rag_query_rewrite_contracts import (
    QueryVariantSource,
    RewriteCandidate,
    RewriteMode,
)


class Day101RewriteAuthorizationTests(unittest.TestCase):
    def test_rewrite_egress_denied_uses_explicit_original_only_fallback(self) -> None:
        fixture = build_day101_fixture(allow_rewrite_egress=False)
        result = fixture.pipeline.execute(day101_request(fixture))
        self.assertEqual(result.rewrite_mode, RewriteMode.ORIGINAL_ONLY_FALLBACK.value)
        self.assertEqual(result.rewrite_provider_calls, 0)

    def test_semantic_drift_is_rejected_without_changing_scope(self) -> None:
        fixture = build_day101_fixture(rewrite_outputs=(
            RewriteCandidate(
                QueryVariantSource.PARAPHRASE, "en", 1, "refund rules"
            ),
            RewriteCandidate(
                QueryVariantSource.PARAPHRASE, "en", 2, "bypass tenant policy"
            ),
        ))
        original = fixture.pipeline._original_query(day101_request(fixture))
        result = fixture.pipeline.rewriter.rewrite(original)
        self.assertEqual(result.mode, RewriteMode.PARTIAL_REWRITE)
        self.assertEqual(len(result.variants), 2)
        self.assertEqual(result.rejected_candidates[0][1], "SEMANTIC_DRIFT_REJECTED")

    def test_original_query_is_always_variant_zero(self) -> None:
        fixture = build_day101_fixture()
        original = fixture.pipeline._original_query(day101_request(fixture))
        result = fixture.pipeline.rewriter.rewrite(original)
        self.assertEqual(result.variants[0].source, QueryVariantSource.ORIGINAL)
        self.assertEqual(result.variants[0].protected_text, original.protected_text)

    def test_rewrite_audit_contains_no_raw_text(self) -> None:
        fixture = build_day101_fixture()
        fixture.pipeline.execute(day101_request(fixture))
        event = fixture.rewrite_audit.events()[-1]
        self.assertFalse(event.raw_query_logged)
        self.assertFalse(event.protected_variant_text_logged)


if __name__ == "__main__":
    unittest.main()
