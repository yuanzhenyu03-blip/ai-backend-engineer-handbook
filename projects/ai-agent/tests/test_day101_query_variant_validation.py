from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day101_query_rewriting_reranking import (
    QUERY_DIGEST_SECRET,
    build_day101_fixture,
    classroom_rewrite_contract,
    day101_request,
)
from rag_query_rewrite_contracts import QueryVariantSource, RewriteCandidate


class Day101QueryVariantValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = build_day101_fixture()
        self.original = self.fixture.pipeline._original_query(
            day101_request(self.fixture)
        )
        self.validator = self.fixture.pipeline.rewriter.validator

    def test_normalized_duplicate_of_original_is_rejected(self) -> None:
        report = self.validator.validate(
            original=self.original,
            contract=classroom_rewrite_contract(),
            candidates=(RewriteCandidate(
                QueryVariantSource.NORMALIZED, "en", 1, "  REFUND   POLICY "
            ),),
            digest_secret=QUERY_DIGEST_SECRET,
        )
        self.assertEqual(report.rejected[0][1], "REWRITE_NORMALIZED_DUPLICATE")

    def test_wrong_locale_is_rejected(self) -> None:
        report = self.validator.validate(
            original=self.original,
            contract=classroom_rewrite_contract(),
            candidates=(RewriteCandidate(
                QueryVariantSource.PARAPHRASE, "zh", 1, "退款规则"
            ),),
            digest_secret=QUERY_DIGEST_SECRET,
        )
        self.assertEqual(report.rejected[0][1], "REWRITE_LOCALE_MISMATCH")

    def test_variant_length_is_bounded(self) -> None:
        contract = replace(classroom_rewrite_contract(), max_variant_chars=8)
        report = self.validator.validate(
            original=self.original,
            contract=contract,
            candidates=(RewriteCandidate(
                QueryVariantSource.PARAPHRASE, "en", 1, "long refund rules"
            ),),
            digest_secret=QUERY_DIGEST_SECRET,
        )
        self.assertEqual(report.rejected[0][1], "REWRITE_VARIANT_TOO_LONG")

    def test_generated_variant_count_is_bounded(self) -> None:
        contract = replace(classroom_rewrite_contract(), max_generated_variants=1)
        report = self.validator.validate(
            original=self.original,
            contract=contract,
            candidates=(
                RewriteCandidate(QueryVariantSource.PARAPHRASE, "en", 1, "rules one"),
                RewriteCandidate(QueryVariantSource.PARAPHRASE, "en", 2, "rules two"),
            ),
            digest_secret=QUERY_DIGEST_SECRET,
        )
        self.assertEqual(len(report.accepted), 1)
        self.assertEqual(report.rejected[0][1], "REWRITE_BUDGET_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()
