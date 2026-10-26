from __future__ import annotations

import unittest

from examples.day98_embedding_selection_versioning import (
    build_day98_fixture,
    run_request,
)
from rag_embedding_adapter import FakeResponseMode
from rag_embedding_orchestrator import EmbeddingRunOutcome


class Day98EmbeddingValidationTests(unittest.TestCase):
    def test_out_of_order_is_safe_only_with_explicit_item_identity(self) -> None:
        fixture = build_day98_fixture(mode=FakeResponseMode.REVERSED)
        result = run_request(fixture)
        self.assertEqual(result.outcome, EmbeddingRunOutcome.COMMITTED)
        assert result.commit is not None and result.commit.embedding_set is not None
        self.assertEqual(
            tuple(record.chunk_id for record in result.commit.embedding_set.records),
            fixture.handoff.authorized_chunk_ids,
        )

    def test_every_structural_or_numeric_fault_rejects_whole_operation(self) -> None:
        modes = (
            FakeResponseMode.MISSING,
            FakeResponseMode.DUPLICATE,
            FakeResponseMode.UNKNOWN,
            FakeResponseMode.WRONG_MODEL,
            FakeResponseMode.WRONG_DIMENSION,
            FakeResponseMode.NAN,
            FakeResponseMode.INFINITY,
            FakeResponseMode.ZERO,
            FakeResponseMode.WRONG_TYPE,
            FakeResponseMode.WRONG_SCHEMA,
            FakeResponseMode.WRONG_USAGE,
            FakeResponseMode.PARTIAL,
        )
        for mode in modes:
            with self.subTest(mode=mode):
                fixture = build_day98_fixture(mode=mode)
                result = run_request(fixture)
                self.assertEqual(result.outcome, EmbeddingRunOutcome.REJECTED)
                self.assertEqual(fixture.store.outbox_intents(), ())
                self.assertIsNone(fixture.store.read_selection(
                    fixture.handoff.tenant_id,
                    fixture.handoff.document_id,
                    fixture.handoff.chunk_set_id,
                ))


if __name__ == "__main__":
    unittest.main()
