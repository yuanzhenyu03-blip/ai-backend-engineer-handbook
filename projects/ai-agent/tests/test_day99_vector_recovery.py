from __future__ import annotations

import unittest

from examples.day99_vector_database_index_design import (
    build_day99_fixture,
    vector_build_request,
)
from rag_vector_adapter import FakeVectorMode, VectorProviderError
from rag_vector_orchestrator import VectorBuildOutcome
from rag_vector_index_planner import plan_vector_batches


class Day99VectorRecoveryTests(unittest.TestCase):
    def test_timeout_unknown_requires_reconciliation_and_blocks_new_attempt(self) -> None:
        fixture = build_day99_fixture(mode=FakeVectorMode.TIMEOUT_UNKNOWN)
        request = vector_build_request(fixture)
        first = fixture.orchestrator.run(request)
        self.assertEqual(
            first.outcome, VectorBuildOutcome.RECONCILIATION_REQUIRED
        )
        retry = fixture.orchestrator.run(vector_build_request(
            fixture,
            attempt_number=2,
            request_id="request-day99-blind-retry-2",
        ))
        self.assertEqual(retry.outcome, VectorBuildOutcome.CLAIM_CONFLICT)
        reconciled = fixture.orchestrator.reconcile(request)
        self.assertEqual(reconciled.outcome, VectorBuildOutcome.SEALED)

    def test_provider_rejects_late_stale_fence(self) -> None:
        fixture = build_day99_fixture()
        first = fixture.orchestrator.run(vector_build_request(fixture))
        second = fixture.orchestrator.run(vector_build_request(
            fixture,
            attempt_number=2,
            request_id="request-day99-fence-2",
        ))
        assert first.claim is not None and second.claim is not None
        assert first.generation_id is not None
        points = fixture.provider.readback(first.generation_id).points
        plan = plan_vector_batches(
            points,
            contract=fixture.contract,
            operation_id=first.operation.operation_id,  # type: ignore[union-attr]
        )
        with self.assertRaises(VectorProviderError):
            fixture.provider.replace_generation(
                generation_id=first.generation_id,
                contract=fixture.contract,
                plan=plan,
                operation_id=first.operation.operation_id,  # type: ignore[union-attr]
                request_id="request-day99-late-stale-fence",
                fence=first.claim.fence,
            )


if __name__ == "__main__":
    unittest.main()
