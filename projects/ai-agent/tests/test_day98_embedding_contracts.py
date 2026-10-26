from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day98_embedding_selection_versioning import (
    build_day98_fixture,
    classroom_contract,
    run_request,
)
from rag_embedding_contracts import DeploymentKind, InputRole, ModelIdentity


class Day98EmbeddingContractTests(unittest.TestCase):
    def test_contract_fingerprint_covers_preprocessing_and_model_revision(self) -> None:
        baseline = classroom_contract()
        changed_preprocessing = classroom_contract(
            preprocessing_version="prefix-only-v2"
        )
        changed_model = replace(
            baseline,
            model=ModelIdentity(
                baseline.model.provider,
                baseline.model.model_id,
                "sha256:another-immutable-revision",
                baseline.model.deployment,
            ),
        )
        self.assertNotEqual(baseline.fingerprint, changed_preprocessing.fingerprint)
        self.assertNotEqual(baseline.fingerprint, changed_model.fingerprint)
        self.assertEqual(baseline.dimensions, changed_model.dimensions)

    def test_alias_revision_and_query_role_are_rejected(self) -> None:
        baseline = classroom_contract()
        with self.assertRaises(ValueError):
            replace(
                baseline,
                model=replace(baseline.model, immutable_revision="latest"),
            )
        with self.assertRaises(ValueError):
            replace(baseline, input_role=InputRole.QUERY)
        with self.assertRaises(ValueError):
            replace(
                baseline,
                model=replace(
                    baseline.model,
                    deployment=DeploymentKind.HOSTED,
                ),
            )

    def test_default_repr_hides_protected_text_principal_and_vectors(self) -> None:
        fixture = build_day98_fixture()
        result = run_request(fixture)
        assert result.commit is not None and result.commit.embedding_set is not None
        representation = repr((fixture.handoff, result.commit.embedding_set))
        self.assertNotIn(fixture.handoff.principal_subject, representation)
        self.assertNotIn(fixture.handoff.chunks[0].text, representation)
        self.assertNotIn("vector=", representation)


if __name__ == "__main__":
    unittest.main()
