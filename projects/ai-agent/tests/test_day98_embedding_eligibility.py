from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day98_embedding_selection_versioning import build_day98_fixture
from rag_embedding_requirements import (
    EmbeddingEligibilityError,
    ReturnToDay96Required,
    prepare_authorized_items,
)
from rag_tokenizer_adapter import ClassroomTokenizer


class Day98EmbeddingEligibilityTests(unittest.TestCase):
    def test_only_exact_authorized_order_enters_preprocessing(self) -> None:
        fixture = build_day98_fixture()
        items = prepare_authorized_items(
            fixture.handoff,
            contract=fixture.contract,
            tokenizer=ClassroomTokenizer(),
        )
        self.assertEqual(
            tuple(item.chunk_id for item in items),
            fixture.handoff.authorized_chunk_ids,
        )
        self.assertTrue(all(item.text.startswith("document: ") for item in items))

    def test_oversized_chunk_returns_to_day96_instead_of_truncating(self) -> None:
        fixture = build_day98_fixture()
        contract = replace(fixture.contract, hard_max_tokens=1)
        with self.assertRaises(ReturnToDay96Required):
            prepare_authorized_items(
                fixture.handoff,
                contract=contract,
                tokenizer=ClassroomTokenizer(),
            )

    def test_tokenizer_contract_mismatch_fails_closed(self) -> None:
        fixture = build_day98_fixture()
        contract = replace(
            fixture.contract,
            tokenizer=replace(fixture.contract.tokenizer, version="2.0.0"),
        )
        with self.assertRaises(EmbeddingEligibilityError):
            prepare_authorized_items(
                fixture.handoff,
                contract=contract,
                tokenizer=ClassroomTokenizer(),
            )


if __name__ == "__main__":
    unittest.main()
