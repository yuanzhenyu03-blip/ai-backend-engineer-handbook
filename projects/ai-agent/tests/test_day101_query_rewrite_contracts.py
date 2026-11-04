from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day101_query_rewriting_reranking import (
    QUERY_DIGEST_SECRET,
    build_day101_fixture,
    classroom_rewrite_contract,
    day101_request,
)
from rag_query_rewrite_contracts import (
    QueryVariant,
    QueryVariantSource,
    QueryVariantValidation,
    protected_query_digest,
)


class Day101QueryRewriteContractTests(unittest.TestCase):
    def test_query_digest_is_tenant_bound_and_keyed(self) -> None:
        left = protected_query_digest(QUERY_DIGEST_SECRET, "tenant-a", "secret")
        right = protected_query_digest(QUERY_DIGEST_SECRET, "tenant-b", "secret")
        self.assertNotEqual(left, right)
        self.assertTrue(left.startswith("hmac-sha256:"))

    def test_original_query_repr_hides_protected_text(self) -> None:
        fixture = build_day101_fixture()
        original = fixture.pipeline._original_query(day101_request(fixture))
        self.assertNotIn("refund policy", repr(original))

    def test_rewrite_contract_rejects_mutable_revision(self) -> None:
        with self.assertRaises(ValueError):
            replace(classroom_rewrite_contract(), immutable_provider_revision="latest")

    def test_variant_zero_must_be_original(self) -> None:
        with self.assertRaises(ValueError):
            QueryVariant(
                "operation",
                "set",
                "variant",
                0,
                QueryVariantSource.PARAPHRASE,
                "hmac-sha256:digest",
                "contract",
                "en",
                QueryVariantValidation.APPROVED,
                "query",
            )

    def test_rewrite_contract_fingerprint_changes_with_budget(self) -> None:
        contract = classroom_rewrite_contract()
        changed = replace(contract, max_generated_variants=1)
        self.assertNotEqual(contract.fingerprint, changed.fingerprint)


if __name__ == "__main__":
    unittest.main()
