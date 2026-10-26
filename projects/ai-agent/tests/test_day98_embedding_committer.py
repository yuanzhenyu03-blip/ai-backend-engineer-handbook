from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor

from examples.day98_embedding_selection_versioning import (
    build_day98_fixture,
    classroom_contract,
    run_request,
)
from rag_embedding_adapter import FakeResponseMode
from rag_embedding_committer import EmbeddingCommitOutcome, OutboxHintOutcome


class Day98EmbeddingCommitterTests(unittest.TestCase):
    def test_set_records_pointer_and_outbox_commit_atomically(self) -> None:
        fixture = build_day98_fixture()
        result = run_request(fixture)
        assert result.commit is not None and result.commit.embedding_set is not None
        self.assertEqual(result.commit.outcome, EmbeddingCommitOutcome.COMMITTED)
        embedding_set = result.commit.embedding_set
        self.assertEqual(
            len(embedding_set.records), len(fixture.handoff.chunks)
        )
        self.assertEqual(len(fixture.store.outbox_intents()), 1)
        self.assertEqual(
            fixture.store.read_selection(
                fixture.handoff.tenant_id,
                fixture.handoff.document_id,
                fixture.handoff.chunk_set_id,
            ).embedding_set_id,
            embedding_set.embedding_set_id,
        )

    def test_exact_replay_converges_without_second_outbox(self) -> None:
        fixture = build_day98_fixture()
        first = run_request(fixture)
        second = run_request(fixture)
        assert first.commit is not None and second.commit is not None
        self.assertEqual(second.commit.outcome, EmbeddingCommitOutcome.ALREADY_COMMITTED)
        self.assertEqual(len(fixture.store.outbox_intents()), 1)
        fixture.adapter.mode = FakeResponseMode.PERTURBED_VALID
        conflict = run_request(fixture)
        assert conflict.commit is not None
        self.assertEqual(
            conflict.commit.outcome, EmbeddingCommitOutcome.IDENTITY_CONFLICT
        )
        self.assertEqual(len(fixture.store.outbox_intents()), 1)

    def test_contract_upgrade_creates_new_set_and_retains_old_set(self) -> None:
        fixture = build_day98_fixture()
        first = run_request(fixture)
        assert first.commit is not None and first.commit.embedding_set is not None
        old = first.commit.embedding_set
        upgraded_contract = classroom_contract(
            contract_version="embedding-contract.v2",
            dimensions=12,
        )
        upgraded = build_day98_fixture(contract=upgraded_contract)
        # Reuse the durable Day98 store and current Day97 authorities.
        upgraded.committer._store = fixture.store
        upgraded.orchestrator._committer = upgraded.committer
        contract_revision = fixture.store.select_contract(
            upgraded.handoff.tenant_id, upgraded_contract.fingerprint
        )
        result = run_request(
            upgraded,
            operation_id="op-day98-classroom-v2",
            idempotency_key="idem-day98-classroom-v2",
            request_id="request-day98-classroom-v2",
            expected_selected_id=old.embedding_set_id,
            expected_selection_revision=1,
            expected_contract_selection_revision=contract_revision,
        )
        assert result.commit is not None and result.commit.embedding_set is not None
        self.assertNotEqual(result.commit.embedding_set.embedding_set_id, old.embedding_set_id)
        self.assertIsNotNone(fixture.store.read_set(old.embedding_set_id))
        self.assertEqual(len(fixture.store.outbox_intents()), 2)
        old_intent, current_intent = fixture.store.outbox_intents()
        self.assertEqual(
            fixture.store.classify_outbox_hint(old_intent.event_id),
            OutboxHintOutcome.STALE,
        )
        self.assertEqual(
            fixture.store.classify_outbox_hint(current_intent.event_id),
            OutboxHintOutcome.CURRENT,
        )
        self.assertTrue(fixture.store.mark_outbox_dispatched(current_intent.event_id))
        self.assertTrue(fixture.store.mark_outbox_dispatched(current_intent.event_id))

    def test_two_writers_converge_to_one_set_and_one_outbox(self) -> None:
        fixture = build_day98_fixture()

        def execute(number: int):
            return run_request(
                fixture,
                operation_id=f"op-day98-race-{number}",
                idempotency_key=f"idem-day98-race-{number}",
                request_id=f"request-day98-race-{number}",
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = tuple(pool.map(execute, (1, 2)))
        outcomes = {result.commit.outcome for result in results if result.commit}
        self.assertEqual(outcomes, {
            EmbeddingCommitOutcome.COMMITTED,
            EmbeddingCommitOutcome.ALREADY_COMMITTED,
        })
        self.assertEqual(len(fixture.store.outbox_intents()), 1)


if __name__ == "__main__":
    unittest.main()
