from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day98_embedding_selection_versioning import (
    build_day98_fixture,
    classroom_contract,
    run_request,
)
from rag_embedding_committer import EmbeddingCommitOutcome
from rag_ingestion_contracts import DocumentIdentity


class Day98EmbeddingAuthorizationTests(unittest.TestCase):
    def test_expired_permit_blocks_commit_even_after_provider_success(self) -> None:
        fixture = build_day98_fixture()
        fixture.day97.clock.value = fixture.handoff.permit_expires_at
        result = run_request(fixture)
        assert result.commit is not None
        self.assertEqual(result.commit.outcome, EmbeddingCommitOutcome.STALE_AUTHORIZATION)
        self.assertEqual(fixture.store.outbox_intents(), ())

    def test_acl_revision_change_blocks_commit_without_reembedding_rule(self) -> None:
        for mutation in ("revision", "exact-grant"):
            with self.subTest(mutation=mutation):
                fixture = build_day98_fixture()
                policy = fixture.day97.authorization.read_policy(
                    "tenant-a", "report-42"
                )
                assert policy is not None
                if mutation == "revision":
                    updated = replace(
                        policy,
                        acl_revision=policy.acl_revision + 1,
                        authorization_epoch=policy.authorization_epoch + 1,
                    )
                else:
                    updated = replace(
                        policy,
                        entries=tuple(
                            entry for entry in policy.entries
                            if entry.entry_id != "grant-worker-embedding"
                        ),
                    )
                fixture.day97.authorization.put_policy(updated)
                result = run_request(fixture)
                assert result.commit is not None
                self.assertEqual(
                    result.commit.outcome,
                    EmbeddingCommitOutcome.STALE_AUTHORIZATION,
                )

    def test_selection_document_or_contract_change_blocks_commit(self) -> None:
        for mutation in ("selection", "document", "contract"):
            with self.subTest(mutation=mutation):
                fixture = build_day98_fixture()
                if mutation == "selection":
                    key = ("tenant-a", "report-42")
                    with fixture.day97.chunks._lock:
                        current = fixture.day97.chunks._selections[key]
                        fixture.day97.chunks._selections[key] = replace(
                            current, revision=current.revision + 1
                        )
                elif mutation == "document":
                    identity = DocumentIdentity("tenant-a", "report-42")
                    with fixture.day97.day95._lock:
                        current = fixture.day97.day95.read_document(identity)
                        fixture.day97.day95._documents[("tenant-a", "report-42")] = replace(
                            current,
                            state_version=current.state_version + 1,
                            fence_token=current.fence_token + 1,
                        )
                else:
                    replacement = classroom_contract(
                        contract_version="embedding-contract.changed"
                    )
                    fixture.store.select_contract(
                        fixture.handoff.tenant_id,
                        replacement.fingerprint,
                    )
                result = run_request(fixture)
                assert result.commit is not None
                self.assertEqual(
                    result.commit.outcome,
                    EmbeddingCommitOutcome.STALE_CONTRACT
                    if mutation == "contract"
                    else EmbeddingCommitOutcome.STALE_PROVENANCE,
                )


if __name__ == "__main__":
    unittest.main()
