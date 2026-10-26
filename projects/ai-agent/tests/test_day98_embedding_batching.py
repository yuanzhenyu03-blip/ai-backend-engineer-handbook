from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day98_embedding_selection_versioning import build_day98_fixture
from rag_embedding_batching import BatchPlanError, plan_batches
from rag_embedding_requirements import prepare_authorized_items
from rag_tokenizer_adapter import ClassroomTokenizer


class Day98EmbeddingBatchingTests(unittest.TestCase):
    def test_batch_plan_is_deterministic_and_preserves_order(self) -> None:
        fixture = build_day98_fixture()
        items = prepare_authorized_items(
            fixture.handoff,
            contract=fixture.contract,
            tokenizer=ClassroomTokenizer(),
        )
        first = plan_batches(
            items,
            limits=fixture.contract.batch_limits,
            operation_id="op",
        )
        second = plan_batches(
            items,
            limits=fixture.contract.batch_limits,
            operation_id="op",
        )
        self.assertEqual(first, second)
        self.assertEqual(
            tuple(item.chunk_id for batch in first for item in batch.items),
            fixture.handoff.authorized_chunk_ids,
        )
        self.assertTrue(all(len(batch.items) <= 2 for batch in first))

    def test_single_chunk_over_batch_limit_is_not_split(self) -> None:
        fixture = build_day98_fixture()
        items = prepare_authorized_items(
            fixture.handoff,
            contract=fixture.contract,
            tokenizer=ClassroomTokenizer(),
        )
        limits = replace(
            fixture.contract.batch_limits,
            max_utf8_bytes=1,
        )
        with self.assertRaises(BatchPlanError):
            plan_batches(items, limits=limits, operation_id="op")


if __name__ == "__main__":
    unittest.main()
