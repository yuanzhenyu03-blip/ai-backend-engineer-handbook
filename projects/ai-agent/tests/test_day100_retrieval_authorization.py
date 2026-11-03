from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day100_hybrid_retrieval_filtering import build_day100_fixture
from rag_authorized_retriever import (
    GuardedRetrievalReleaser,
    InMemoryProtectedRetrievalStore,
    RetrievalAuthorizationUnavailable,
)
from rag_dense_retrieval import DenseMode
from rag_hybrid_fusion import reciprocal_rank_fusion
from rag_retrieval_contracts import RetrievalOutcome
from rag_retrieval_validator import RetrievalCandidateValidator


class Day100RetrievalAuthorizationTests(unittest.TestCase):
    def _dense_candidates(self, fixture):
        encoded = fixture.encoder.encode(
            query_text="refund policy",
            expected_contract_fingerprint=fixture.bundle.query_encoder.fingerprint,
        )
        return fixture.dense.search(
            encoded_query=encoded,
            bundle=fixture.bundle,
            scope=fixture.scope,
            business_filter=None,
            system_excluded_occurrence_ids=(),
            offset=0,
            limit=10,
        )

    def test_leaked_unauthorized_candidate_is_rejected_before_fusion(self) -> None:
        fixture = build_day100_fixture(dense_mode=DenseMode.LEAK_UNAUTHORIZED)
        candidates = self._dense_candidates(fixture)
        self.assertIn("occurrence:X", {
            item.identity.occurrence_id for item in candidates
        })
        report = RetrievalCandidateValidator().validate(
            candidates=candidates,
            bundle=fixture.bundle,
            scope=fixture.scope,
        )
        self.assertNotIn("occurrence:X", {
            item.identity.occurrence_id for item in report.accepted
        })
        self.assertIn(
            "CANDIDATE_OUTSIDE_AUTHORIZATION_SCOPE",
            {item.reason for item in report.rejected},
        )

    def test_revocation_after_fusion_blocks_guarded_release(self) -> None:
        fixture = build_day100_fixture()
        candidates = self._dense_candidates(fixture)
        fused = reciprocal_rank_fusion(
            candidates, policy=fixture.bundle.fusion_policy
        )
        fixture.authorization.revoke_occurrence(
            tenant_id=fixture.scope.tenant_id,
            principal_subject=fixture.scope.principal_subject,
            action=fixture.scope.action,
            purpose=fixture.scope.purpose,
            occurrence_id="occurrence:B",
        )
        releaser = GuardedRetrievalReleaser(
            authorization=fixture.authorization,
            content=InMemoryProtectedRetrievalStore(fixture.records),
        )
        report = releaser.release(
            candidates=fused,
            initial_scope=fixture.scope,
            limit=5,
        )
        self.assertNotIn("occurrence:B", {
            item.identity.occurrence_id for item in report.hits
        })
        self.assertIn("CURRENT_AUTHORIZATION_REVOKED", {
            item.reason for item in report.rejected
        })

    def test_stale_provenance_blocks_content_release(self) -> None:
        fixture = build_day100_fixture()
        candidates = self._dense_candidates(fixture)
        fused = reciprocal_rank_fusion(candidates, policy=fixture.bundle.fusion_policy)
        content = InMemoryProtectedRetrievalStore(fixture.records)
        occurrence = fused[0].identity.occurrence_id
        content.change_provenance(occurrence, "sha256:new-provenance")
        report = GuardedRetrievalReleaser(
            authorization=fixture.authorization,
            content=content,
        ).release(candidates=fused, initial_scope=fixture.scope, limit=5)
        self.assertIn("CURRENT_PROVENANCE_CHANGED", {
            item.reason for item in report.rejected
        })

    def test_unavailable_current_authorization_never_releases(self) -> None:
        fixture = build_day100_fixture()
        candidates = self._dense_candidates(fixture)
        fused = reciprocal_rank_fusion(candidates, policy=fixture.bundle.fusion_policy)
        fixture.authorization.set_available(False)
        with self.assertRaises(RetrievalAuthorizationUnavailable):
            GuardedRetrievalReleaser(
                authorization=fixture.authorization,
                content=InMemoryProtectedRetrievalStore(fixture.records),
            ).release(candidates=fused, initial_scope=fixture.scope, limit=5)

    def test_cross_tenant_candidate_is_rejected(self) -> None:
        fixture = build_day100_fixture()
        candidate = self._dense_candidates(fixture)[0]
        cross_tenant = replace(
            candidate,
            identity=replace(candidate.identity, tenant_id="tenant-other"),
        )
        report = RetrievalCandidateValidator().validate(
            candidates=(cross_tenant,),
            bundle=fixture.bundle,
            scope=fixture.scope,
        )
        self.assertEqual(report.rejected[0].reason, "CROSS_TENANT_CANDIDATE")

    def test_no_current_grant_is_authorization_denied_before_search(self) -> None:
        fixture = build_day100_fixture()
        fixture.authorization.put(replace(
            fixture.scope,
            allowed_occurrence_ids=(),
            decision_id="decision-empty",
        ))
        from examples.day100_hybrid_retrieval_filtering import retrieval_request
        result = fixture.retriever.retrieve(retrieval_request(fixture))
        self.assertEqual(result.outcome, RetrievalOutcome.AUTHORIZATION_DENIED)
        self.assertEqual((result.provider_calls, result.database_calls), (0, 0))


if __name__ == "__main__":
    unittest.main()
