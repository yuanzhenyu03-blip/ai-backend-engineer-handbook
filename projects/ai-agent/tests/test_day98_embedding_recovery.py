from __future__ import annotations

import unittest

from examples.day98_embedding_selection_versioning import (
    build_day98_fixture,
    run_request,
)
from rag_embedding_adapter import FakeResponseMode
from rag_embedding_orchestrator import (
    EmbeddingRunOutcome,
    deterministic_retry_delay_seconds,
)


class Day98EmbeddingRecoveryTests(unittest.TestCase):
    def test_timeout_after_dispatch_requires_reconciliation_not_blind_retry(self) -> None:
        fixture = build_day98_fixture(mode=FakeResponseMode.TIMEOUT_UNKNOWN)
        result = run_request(fixture)
        self.assertEqual(result.outcome, EmbeddingRunOutcome.RECONCILIATION_REQUIRED)
        self.assertEqual(fixture.store.outbox_intents(), ())

    def test_proven_non_execution_allows_fresh_attempt(self) -> None:
        fixture = build_day98_fixture(mode=FakeResponseMode.PROVEN_NOT_EXECUTED)
        first = run_request(fixture)
        self.assertEqual(first.outcome, EmbeddingRunOutcome.RETRY_ALLOWED)
        fixture.adapter.mode = FakeResponseMode.NORMAL
        second = run_request(
            fixture,
            attempt_number=2,
            generation=2,
            request_id="request-day98-classroom-retry-2",
        )
        self.assertEqual(second.outcome, EmbeddingRunOutcome.COMMITTED)
        stale = run_request(fixture)
        self.assertEqual(stale.outcome, EmbeddingRunOutcome.CLAIM_CONFLICT)

    def test_backoff_is_bounded_deterministic_and_honors_retry_after(self) -> None:
        self.assertEqual(
            deterministic_retry_delay_seconds(
                attempt_number=2, retry_after_seconds=9.0
            ),
            9.0,
        )
        self.assertLessEqual(
            deterministic_retry_delay_seconds(attempt_number=10), 31.0
        )


if __name__ == "__main__":
    unittest.main()
