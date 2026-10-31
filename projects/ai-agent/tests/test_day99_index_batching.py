from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day99_vector_database_index_design import (
    build_day99_fixture,
    vector_build_request,
)
from rag_vector_adapter import FakeVectorMode
from rag_vector_index_planner import (
    VectorBatchPlan,
    VectorBatchPlanError,
    plan_vector_batches,
    validate_batch_plan,
)
from rag_vector_orchestrator import VectorBuildOutcome


class Day99IndexBatchingTests(unittest.TestCase):
    def _prepared_plan(self):
        fixture = build_day99_fixture()
        prepared = fixture.orchestrator._prepare(  # noqa: SLF001
            vector_build_request(fixture)
        )
        self.assertIsInstance(prepared, tuple)
        operation, _, _, points, plan = prepared
        return fixture, operation, points, plan

    def test_plan_is_deterministic_and_preserves_each_vector(self) -> None:
        fixture, operation, points, first = self._prepared_plan()
        second = plan_vector_batches(
            tuple(reversed(points)),
            contract=fixture.contract,
            operation_id=operation.operation_id,
        )
        self.assertEqual(first, second)
        flattened = tuple(
            point for batch in first.batches for point in batch.points
        )
        self.assertEqual(
            flattened,
            tuple(sorted(points, key=lambda point: point.point_id)),
        )
        self.assertGreater(len(first.batches), 1)

    def test_cross_tenant_input_and_duplicate_batch_are_rejected(self) -> None:
        fixture, operation, points, plan = self._prepared_plan()
        with self.assertRaises(VectorBatchPlanError):
            plan_vector_batches(
                (replace(points[0], tenant_id="tenant-b"),) + points[1:],
                contract=fixture.contract,
                operation_id=operation.operation_id,
            )
        duplicate = VectorBatchPlan(
            plan.operation_id,
            plan.batches + (plan.batches[0],),
            plan.point_count,
            plan.checksum,
        )
        with self.assertRaises(VectorBatchPlanError):
            validate_batch_plan(duplicate, expected_points=points)

    def test_out_of_order_ack_is_accepted_by_exact_identity(self) -> None:
        fixture = build_day99_fixture(mode=FakeVectorMode.REVERSED_ACKS)
        result = fixture.orchestrator.run(vector_build_request(fixture))
        self.assertEqual(result.outcome, VectorBuildOutcome.SEALED)

    def test_invalid_database_acknowledgements_are_rejected(self) -> None:
        modes = (
            FakeVectorMode.MISSING_ACK,
            FakeVectorMode.DUPLICATE_ACK,
            FakeVectorMode.UNKNOWN_ACK,
            FakeVectorMode.PARTIAL_WRITE,
            FakeVectorMode.WRONG_GENERATION_ACK,
            FakeVectorMode.WRONG_NAMESPACE_ACK,
            FakeVectorMode.WRONG_TENANT_ACK,
            FakeVectorMode.STALE_REQUEST_ACK,
        )
        for mode in modes:
            with self.subTest(mode=mode):
                fixture = build_day99_fixture(mode=mode)
                result = fixture.orchestrator.run(vector_build_request(fixture))
                self.assertEqual(result.outcome, VectorBuildOutcome.REJECTED)
                self.assertEqual(fixture.store.generations(), ())

    def test_cross_tenant_readback_is_rejected(self) -> None:
        fixture = build_day99_fixture(mode=FakeVectorMode.CROSS_TENANT_POINT)
        result = fixture.orchestrator.run(vector_build_request(fixture))
        self.assertEqual(result.outcome, VectorBuildOutcome.REJECTED)
        self.assertEqual(fixture.store.generations(), ())


if __name__ == "__main__":
    unittest.main()
