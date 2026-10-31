from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day99_vector_database_index_design import (
    build_day99_fixture,
    classroom_retrieval_policy,
    classroom_vector_contract,
)
from rag_vector_adapter import cosine_similarity
from rag_vector_contracts import (
    IndexAlgorithm,
    IndexBuildParameters,
    ThresholdOperator,
)


class Day99VectorContractTests(unittest.TestCase):
    def test_build_parameter_change_changes_physical_contract(self) -> None:
        fixture = build_day99_fixture()
        hnsw = classroom_vector_contract(
            fixture.embedding_set,
            contract_version="vector-index-contract.hnsw-v1",
            build=IndexBuildParameters(
                IndexAlgorithm.HNSW,
                m=16,
                ef_construction=128,
            ),
        )
        changed = replace(
            hnsw,
            build=IndexBuildParameters(
                IndexAlgorithm.HNSW,
                m=32,
                ef_construction=128,
            ),
        )
        self.assertNotEqual(hnsw.fingerprint, changed.fingerprint)

    def test_query_policy_changes_without_changing_physical_contract(self) -> None:
        fixture = build_day99_fixture()
        baseline = classroom_retrieval_policy(fixture.contract)
        changed = replace(baseline, top_k=10, minimum_similarity=0.75)
        self.assertNotEqual(baseline.fingerprint, changed.fingerprint)
        self.assertEqual(
            baseline.generation_contract_fingerprint,
            fixture.contract.fingerprint,
        )
        self.assertEqual(
            changed.generation_contract_fingerprint,
            fixture.contract.fingerprint,
        )

    def test_full_precision_threshold_operator_is_explicit(self) -> None:
        fixture = build_day99_fixture()
        inclusive = classroom_retrieval_policy(fixture.contract)
        exclusive = replace(
            inclusive,
            threshold_operator=ThresholdOperator.GREATER_THAN,
        )
        self.assertTrue(inclusive.passes(0.8))
        self.assertFalse(exclusive.passes(0.8))
        self.assertFalse(inclusive.passes(0.79996))

    def test_unit_vectors_preserve_dot_cosine_relationship(self) -> None:
        left = (1.0, 0.0)
        right = (0.82, (1.0 - 0.82**2) ** 0.5)
        self.assertAlmostEqual(cosine_similarity(left, right), 0.82)
        squared_l2 = sum((a - b) ** 2 for a, b in zip(left, right))
        self.assertAlmostEqual(squared_l2, 2.0 - 2.0 * 0.82)


if __name__ == "__main__":
    unittest.main()
