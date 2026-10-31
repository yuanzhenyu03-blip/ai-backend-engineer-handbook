from __future__ import annotations

import unittest

from examples.day99_vector_database_index_design import (
    build_day99_fixture,
    vector_build_request,
)
from rag_vector_committer import ActivationOutcome, VectorCommitOutcome
from rag_vector_contracts import EvidenceGate, EvidenceState, ProductionReadiness


class Day99VectorBuildTests(unittest.TestCase):
    def test_generation_manifest_readback_and_outbox_seal_atomically(self) -> None:
        fixture = build_day99_fixture()
        result = fixture.orchestrator.run(vector_build_request(fixture))
        assert result.commit is not None and result.commit.generation is not None
        generation = result.commit.generation
        self.assertEqual(result.commit.outcome, VectorCommitOutcome.SEALED)
        self.assertEqual(
            generation.manifest.point_count,
            len(fixture.embedding_set.records),
        )
        self.assertEqual(len(fixture.store.outbox_intents()), 1)
        self.assertEqual(
            generation.evidence.state_for(EvidenceGate.CONTENT_READBACK),
            EvidenceState.PASS,
        )

    def test_point_identity_and_payload_are_tenant_generation_bound(self) -> None:
        fixture = build_day99_fixture()
        result = fixture.orchestrator.run(vector_build_request(fixture))
        assert result.generation_id is not None
        points = fixture.provider.readback(result.generation_id).points
        self.assertEqual(len({point.point_id for point in points}), len(points))
        self.assertTrue(all(
            point.generation_id == result.generation_id
            and dict(point.payload)["tenant_id"] == point.tenant_id
            and dict(point.payload)["embedding_set_id"]
            == fixture.embedding_set.embedding_set_id
            for point in points
        ))
        self.assertNotIn("vector=", repr(points))

    def test_local_flat_evidence_cannot_activate_production_bundle(self) -> None:
        fixture = build_day99_fixture()
        result = fixture.orchestrator.run(vector_build_request(fixture))
        assert result.commit is not None and result.commit.generation is not None
        generation = result.commit.generation
        self.assertEqual(
            generation.evidence.readiness,
            ProductionReadiness.MORE_EVIDENCE_NEEDED,
        )
        activation = fixture.committer.activate(
            generation_id=generation.generation_id,
            policy=fixture.policy,
            expected_generation_id=None,
            expected_revision=0,
            activation_fence=1,
        )
        self.assertEqual(activation.outcome, ActivationOutcome.NOT_READY)
        self.assertIsNone(fixture.store.read_selected_bundle("tenant-a"))

    def test_exact_replay_converges_without_second_outbox(self) -> None:
        fixture = build_day99_fixture()
        request = vector_build_request(fixture)
        first = fixture.orchestrator.run(request)
        second = fixture.orchestrator.run(request)
        assert second.commit is not None
        self.assertEqual(first.outcome.value, "SEALED")
        self.assertEqual(second.commit.outcome, VectorCommitOutcome.ALREADY_SEALED)
        self.assertEqual(len(fixture.store.outbox_intents()), 1)


if __name__ == "__main__":
    unittest.main()
