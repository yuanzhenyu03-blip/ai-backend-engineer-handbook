from __future__ import annotations

import unittest

from examples.day99_vector_database_index_design import (
    build_day99_fixture,
    vector_build_request,
)
from rag_vector_adapter import FakeVectorMode
from rag_vector_orchestrator import VectorBuildOutcome


class Day99VectorValidationTests(unittest.TestCase):
    def test_invalid_provider_state_rejects_whole_generation(self) -> None:
        cases = (
            FakeVectorMode.ACK_ONLY,
            FakeVectorMode.PARTIAL_WRITE,
            FakeVectorMode.WRONG_VECTOR,
            FakeVectorMode.WRONG_PAYLOAD,
            FakeVectorMode.WRONG_QUERY_ORDER,
        )
        for mode in cases:
            with self.subTest(mode=mode):
                fixture = build_day99_fixture(mode=mode)
                result = fixture.orchestrator.run(
                    vector_build_request(fixture)
                )
                self.assertEqual(result.outcome, VectorBuildOutcome.REJECTED)
                self.assertEqual(fixture.store.generations(), ())
                self.assertEqual(fixture.store.outbox_intents(), ())

    def test_fake_validation_does_not_claim_ann_or_real_provider(self) -> None:
        fixture = build_day99_fixture()
        result = fixture.orchestrator.run(vector_build_request(fixture))
        assert result.commit is not None and result.commit.generation is not None
        evidence = result.commit.generation.evidence
        from rag_vector_contracts import EvidenceGate, EvidenceState
        self.assertEqual(
            evidence.state_for(EvidenceGate.ANN_RECALL), EvidenceState.NOT_RUN
        )
        self.assertEqual(
            evidence.state_for(EvidenceGate.REAL_PROVIDER), EvidenceState.NOT_RUN
        )


if __name__ == "__main__":
    unittest.main()
