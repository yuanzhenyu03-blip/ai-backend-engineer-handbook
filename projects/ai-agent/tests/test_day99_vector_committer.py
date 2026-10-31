from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day99_vector_database_index_design import (
    build_day99_fixture,
    classroom_vector_contract,
    rebind_vector_contract,
    vector_build_request,
)
from rag_vector_committer import (
    ActivationOutcome,
    VectorCommitOutcome,
    VectorOutboxHintOutcome,
)
from rag_vector_contracts import (
    EvidenceGate,
    EvidenceState,
    GateEvidence,
    GenerationEvidence,
    GenerationState,
    IndexAlgorithm,
    IndexBuildParameters,
    VectorBuildAttempt,
)


class Day99VectorCommitterTests(unittest.TestCase):
    @staticmethod
    def _mark_ready(fixture, generation):
        evidence = GenerationEvidence(tuple(
            GateEvidence(
                gate,
                EvidenceState.PASS,
                "SYNTHETIC_STATE_MACHINE_TEST_ONLY",
                "CONTROL_FLOW_ONLY",
            ) for gate in EvidenceGate
        ))
        ready = replace(
            generation,
            evidence=evidence,
            state=GenerationState.PRODUCTION_READY,
        )
        with fixture.store._lock:
            fixture.store._generations[generation.generation_id] = ready
        return ready

    def test_changed_embedding_selection_blocks_before_provider_dispatch(self) -> None:
        fixture = build_day99_fixture()
        operation = fixture.embedding_set.operation
        key = (
            operation.tenant_id,
            operation.document_id,
            operation.chunk_set_id,
        )
        with fixture.day98.store._lock:
            current = fixture.day98.store._selections[key]
            fixture.day98.store._selections[key] = replace(
                current,
                revision=current.revision + 1,
            )
        result = fixture.orchestrator.run(vector_build_request(fixture))
        self.assertEqual(result.outcome.value, "REJECTED")
        self.assertIsNone(result.commit)
        self.assertEqual(fixture.provider.write_calls, [])
        self.assertEqual(fixture.store.generations(), ())

    def test_embedding_selection_race_is_rechecked_before_commit(self) -> None:
        fixture = build_day99_fixture()
        operation = fixture.embedding_set.operation
        key = (
            operation.tenant_id,
            operation.document_id,
            operation.chunk_set_id,
        )
        original_readback = fixture.provider.readback

        def drifting_readback(generation_id: str):
            readback = original_readback(generation_id)
            with fixture.day98.store._lock:
                current = fixture.day98.store._selections[key]
                fixture.day98.store._selections[key] = replace(
                    current,
                    revision=current.revision + 1,
                )
            return readback

        fixture.provider.readback = drifting_readback  # type: ignore[method-assign]
        result = fixture.orchestrator.run(vector_build_request(fixture))
        assert result.commit is not None
        self.assertEqual(
            result.commit.outcome,
            VectorCommitOutcome.STALE_EMBEDDING_SELECTION,
        )
        self.assertEqual(fixture.store.generations(), ())

    def test_build_contract_upgrade_creates_new_generation_and_retains_old(self) -> None:
        fixture = build_day99_fixture()
        first = fixture.orchestrator.run(vector_build_request(fixture))
        assert first.generation_id is not None
        upgraded_contract = classroom_vector_contract(
            fixture.embedding_set,
            contract_version="vector-index-contract.hnsw-v1",
            build=IndexBuildParameters(
                IndexAlgorithm.HNSW,
                m=16,
                ef_construction=128,
            ),
        )
        upgraded = rebind_vector_contract(fixture, upgraded_contract)
        second = upgraded.orchestrator.run(vector_build_request(
            upgraded,
            operation_id="op-day99-vector-generation-hnsw-v1",
            idempotency_key="idem-day99-vector-generation-hnsw-v1",
            request_id="request-day99-vector-generation-hnsw-v1",
        ))
        assert second.generation_id is not None
        self.assertNotEqual(first.generation_id, second.generation_id)
        self.assertEqual(len(fixture.store.generations()), 2)
        self.assertIsNotNone(fixture.store.read_generation(first.generation_id))

    def test_activation_is_atomic_only_after_every_hard_gate(self) -> None:
        fixture = build_day99_fixture()
        built = fixture.orchestrator.run(vector_build_request(fixture))
        assert built.commit is not None and built.commit.generation is not None
        generation = built.commit.generation
        self._mark_ready(fixture, generation)
        activated = fixture.committer.activate(
            generation_id=generation.generation_id,
            policy=fixture.policy,
            expected_generation_id=None,
            expected_revision=0,
            activation_fence=1,
        )
        self.assertEqual(activated.outcome, ActivationOutcome.ACTIVATED)
        self.assertIsNotNone(fixture.store.read_selected_bundle("tenant-a"))
        self.assertEqual(len(fixture.store.outbox_intents()), 2)
        replay = fixture.committer.activate(
            generation_id=generation.generation_id,
            policy=fixture.policy,
            expected_generation_id=None,
            expected_revision=0,
            activation_fence=1,
        )
        self.assertEqual(
            replay.outcome, ActivationOutcome.ALREADY_ACTIVATED
        )
        stale = fixture.committer.activate(
            generation_id=generation.generation_id,
            policy=fixture.policy,
            expected_generation_id=generation.generation_id,
            expected_revision=1,
            activation_fence=0,
        )
        self.assertEqual(stale.outcome, ActivationOutcome.STALE_FENCE)

    def test_competing_operations_converge_to_one_stable_generation(self) -> None:
        fixture = build_day99_fixture()
        first = fixture.orchestrator.run(vector_build_request(fixture))
        second = fixture.orchestrator.run(vector_build_request(
            fixture,
            operation_id="op-day99-competing-builder",
            idempotency_key="idem-day99-competing-builder",
            request_id="request-day99-competing-builder",
        ))
        assert first.commit is not None and second.commit is not None
        self.assertEqual(first.commit.outcome, VectorCommitOutcome.SEALED)
        self.assertEqual(
            second.commit.outcome, VectorCommitOutcome.ALREADY_SEALED
        )
        assert first.claim is not None and second.claim is not None
        self.assertGreater(second.claim.fence, first.claim.fence)
        self.assertEqual(len(fixture.store.generations()), 1)
        self.assertEqual(len(fixture.store.outbox_intents()), 1)

    def test_same_stable_identity_with_changed_manifest_conflicts(self) -> None:
        fixture = build_day99_fixture()
        first = fixture.orchestrator.run(vector_build_request(fixture))
        assert first.operation is not None
        assert first.commit is not None and first.commit.generation is not None
        competing_operation = replace(
            first.operation,
            operation_id="op-day99-conflicting-builder",
            idempotency_key="idem-day99-conflicting-builder",
        )
        claim = fixture.committer.claim(
            competing_operation,
            VectorBuildAttempt(
                competing_operation.operation_id,
                1,
                "request-day99-conflicting-builder",
            ),
        )
        assert claim is not None
        conflicting = replace(
            first.commit.generation,
            operation=competing_operation,
            manifest=replace(
                first.commit.generation.manifest,
                vector_digest="sha256:conflicting-vector-manifest",
            ),
        )
        result = fixture.committer.persist(
            claim=claim,
            contract=fixture.contract,
            generation=conflicting,
            authorization=fixture.authorization,
        )
        self.assertEqual(result.outcome, VectorCommitOutcome.IDENTITY_CONFLICT)

    def test_duplicate_and_delayed_selection_outbox_are_classified(self) -> None:
        fixture = build_day99_fixture()
        first = fixture.orchestrator.run(vector_build_request(fixture))
        assert first.commit is not None and first.commit.generation is not None
        self._mark_ready(fixture, first.commit.generation)
        activated_first = fixture.committer.activate(
            generation_id=first.commit.generation.generation_id,
            policy=fixture.policy,
            expected_generation_id=None,
            expected_revision=0,
            activation_fence=1,
        )
        self.assertEqual(activated_first.outcome, ActivationOutcome.ACTIVATED)
        upgraded_contract = classroom_vector_contract(
            fixture.embedding_set,
            contract_version="vector-index-contract.hnsw-outbox-v1",
            build=IndexBuildParameters(
                IndexAlgorithm.HNSW,
                m=16,
                ef_construction=128,
            ),
        )
        upgraded = rebind_vector_contract(fixture, upgraded_contract)
        second = upgraded.orchestrator.run(vector_build_request(
            upgraded,
            operation_id="op-day99-outbox-upgrade",
            idempotency_key="idem-day99-outbox-upgrade",
            request_id="request-day99-outbox-upgrade",
        ))
        assert second.commit is not None and second.commit.generation is not None
        self._mark_ready(fixture, second.commit.generation)
        activated_second = upgraded.committer.activate(
            generation_id=second.commit.generation.generation_id,
            policy=upgraded.policy,
            expected_generation_id=first.commit.generation.generation_id,
            expected_revision=1,
            activation_fence=2,
        )
        self.assertEqual(activated_second.outcome, ActivationOutcome.ACTIVATED)
        selection_events = tuple(
            intent for intent in fixture.store.outbox_intents()
            if intent.event_type == "VECTOR_BUNDLE_SELECTED"
        )
        self.assertEqual(len(selection_events), 2)
        old_event, current_event = selection_events
        self.assertEqual(
            fixture.store.classify_outbox_hint(old_event.event_id),
            VectorOutboxHintOutcome.STALE,
        )
        self.assertEqual(
            fixture.store.classify_outbox_hint(current_event.event_id),
            VectorOutboxHintOutcome.CURRENT,
        )
        self.assertTrue(
            fixture.store.mark_outbox_dispatched(current_event.event_id)
        )
        self.assertTrue(
            fixture.store.mark_outbox_dispatched(current_event.event_id)
        )
        self.assertEqual(
            fixture.store.classify_outbox_hint("missing-event"),
            VectorOutboxHintOutcome.NOT_FOUND,
        )


if __name__ == "__main__":
    unittest.main()
