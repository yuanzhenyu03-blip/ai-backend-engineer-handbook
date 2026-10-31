from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day99_vector_database_index_design import (
    build_day99_fixture,
    vector_build_request,
)
from rag_vector_committer import VectorCommitOutcome
from rag_vector_orchestrator import VectorBuildOutcome


class Day99IndexAuthorizationTests(unittest.TestCase):
    def test_embedding_action_cannot_substitute_for_index_action(self) -> None:
        fixture = build_day99_fixture()
        with self.assertRaises(ValueError):
            replace(
                fixture.authorization,
                action="chunk:read_for_embedding",
            )

    def test_expired_index_build_permit_fails_before_dispatch(self) -> None:
        fixture = build_day99_fixture()
        fixture.day98.day97.clock.value = (
            fixture.authorization.permit_expires_at
        )
        result = fixture.orchestrator.run(vector_build_request(fixture))
        self.assertEqual(result.outcome, VectorBuildOutcome.REJECTED)
        self.assertEqual(result.safe_reason, "INDEX_BUILD_PERMIT_EXPIRED")
        self.assertEqual(fixture.provider.write_calls, [])

    def test_authorization_change_during_build_blocks_commit(self) -> None:
        fixture = build_day99_fixture()
        original_readback = fixture.provider.readback

        def revoke_then_read(generation_id: str):
            readback = original_readback(generation_id)
            fixture.day98.day97.authorization.revoke_grant(
                tenant_id=fixture.authorization.tenant_id,
                document_id=fixture.authorization.document_id,
                entry_id="grant-index-builder-read-embedding-set",
            )
            return readback

        fixture.provider.readback = revoke_then_read  # type: ignore[method-assign]
        result = fixture.orchestrator.run(vector_build_request(fixture))
        assert result.commit is not None
        self.assertEqual(
            result.commit.outcome,
            VectorCommitOutcome.STALE_AUTHORIZATION,
        )
        self.assertEqual(fixture.store.generations(), ())

    def test_contract_selection_change_during_build_blocks_commit(self) -> None:
        fixture = build_day99_fixture()
        original_readback = fixture.provider.readback

        def change_contract_then_read(generation_id: str):
            readback = original_readback(generation_id)
            fixture.store.select_contract(
                fixture.authorization.tenant_id,
                "sha256:new-selected-vector-contract",
            )
            return readback

        fixture.provider.readback = (  # type: ignore[method-assign]
            change_contract_then_read
        )
        result = fixture.orchestrator.run(vector_build_request(fixture))
        assert result.commit is not None
        self.assertEqual(
            result.commit.outcome,
            VectorCommitOutcome.STALE_CONTRACT,
        )
        self.assertEqual(fixture.store.generations(), ())


if __name__ == "__main__":
    unittest.main()
