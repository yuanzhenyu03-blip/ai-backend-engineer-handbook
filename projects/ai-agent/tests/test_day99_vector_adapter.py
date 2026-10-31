from __future__ import annotations

import unittest

from examples.day99_vector_database_index_design import (
    build_day99_fixture,
    vector_build_request,
)
from rag_vector_adapter import (
    ApplicationVectorAdapter,
    ProviderRawHit,
)


class DistanceStubProvider:
    def query_raw(self, **_: object) -> tuple[ProviderRawHit, ...]:
        return (ProviderRawHit("point-1", "chunk-1", 0.18, "g1"),)


class InvalidDistanceStubProvider:
    def query_raw(self, **_: object) -> tuple[ProviderRawHit, ...]:
        return (ProviderRawHit("point-1", "chunk-1", float("nan"), "g1"),)


class Day99VectorAdapterTests(unittest.TestCase):
    def test_adapter_returns_application_similarity_not_provider_distance(self) -> None:
        adapter = ApplicationVectorAdapter(DistanceStubProvider())  # type: ignore[arg-type]
        hit = adapter.search(
            generation_id="g1",
            query_vector=(1.0, 0.0),
            tenant_id="tenant-a",
            top_k=1,
        )[0]
        self.assertAlmostEqual(hit.similarity, 0.82)

    def test_adapter_rejects_invalid_provider_distance(self) -> None:
        adapter = ApplicationVectorAdapter(
            InvalidDistanceStubProvider()  # type: ignore[arg-type]
        )
        with self.assertRaises(ValueError):
            adapter.search(
                generation_id="g1",
                query_vector=(1.0, 0.0),
                tenant_id="tenant-a",
                top_k=1,
            )

    def test_exact_self_query_is_sorted_and_tenant_scoped(self) -> None:
        fixture = build_day99_fixture()
        result = fixture.orchestrator.run(vector_build_request(fixture))
        assert result.commit is not None and result.commit.generation is not None
        generation = result.commit.generation
        point = fixture.provider.readback(generation.generation_id).points[0]
        adapter = ApplicationVectorAdapter(fixture.provider)
        allowed = adapter.search(
            generation_id=generation.generation_id,
            query_vector=point.vector,
            tenant_id=point.tenant_id,
            top_k=1,
        )
        denied = adapter.search(
            generation_id=generation.generation_id,
            query_vector=point.vector,
            tenant_id="tenant-b",
            top_k=3,
        )
        self.assertEqual(allowed[0].point_id, point.point_id)
        self.assertAlmostEqual(allowed[0].similarity, 1.0)
        self.assertEqual(denied, ())


if __name__ == "__main__":
    unittest.main()
