from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day100_hybrid_retrieval_filtering import (
    build_day100_fixture,
    retrieval_request,
)
from rag_retrieval_contracts import RetrievalOutcome


class Day100PaginationCacheTests(unittest.TestCase):
    def test_full_result_cache_hit_still_uses_current_authorization(self) -> None:
        fixture = build_day100_fixture()
        request = retrieval_request(fixture, top_k=2)
        first = fixture.retriever.retrieve(request)
        self.assertEqual(first.outcome, RetrievalOutcome.FULL)
        second = fixture.retriever.retrieve(request)
        self.assertEqual(second.safe_reason, "CURRENT_AUTHORIZATION_RECHECKED_CACHE_HIT")
        self.assertEqual((second.provider_calls, second.database_calls), (0, 0))

    def test_authorization_change_prevents_stale_cache_hit(self) -> None:
        fixture = build_day100_fixture()
        request = retrieval_request(fixture, top_k=3)
        first = fixture.retriever.retrieve(request)
        self.assertTrue(first.hits)
        revoked = first.hits[0].identity.occurrence_id
        fixture.authorization.revoke_occurrence(
            tenant_id=fixture.scope.tenant_id,
            principal_subject=fixture.scope.principal_subject,
            action=fixture.scope.action,
            purpose=fixture.scope.purpose,
            occurrence_id=revoked,
        )
        second = fixture.retriever.retrieve(request)
        self.assertNotEqual(second.safe_reason, "CURRENT_AUTHORIZATION_RECHECKED_CACHE_HIT")
        self.assertNotIn(revoked, {
            hit.identity.occurrence_id for hit in second.hits
        })

    def test_authorization_change_invalidates_cursor(self) -> None:
        fixture = build_day100_fixture()
        request = retrieval_request(fixture, top_k=2)
        first = fixture.retriever.retrieve(request)
        assert first.cursor is not None
        fixture.authorization.revoke_occurrence(
            tenant_id=fixture.scope.tenant_id,
            principal_subject=fixture.scope.principal_subject,
            action=fixture.scope.action,
            purpose=fixture.scope.purpose,
            occurrence_id="occurrence:B",
        )
        second = fixture.retriever.retrieve(request, cursor_token=first.cursor)
        self.assertEqual(second.outcome, RetrievalOutcome.REJECTED)
        self.assertEqual(second.safe_reason, "CURSOR_AUTHORIZATION_CHANGED")

    def test_selected_bundle_change_invalidates_cursor(self) -> None:
        fixture = build_day100_fixture()
        request = retrieval_request(fixture, top_k=2)
        first = fixture.retriever.retrieve(request)
        assert first.cursor is not None
        changed = replace(
            fixture.bundle,
            bundle_id="synthetic-selected-retrieval-bundle-v2",
            revision=2,
            generation_id="synthetic-vector-generation-g2",
        )
        fixture.bundles.select(changed)
        second = fixture.retriever.retrieve(request, cursor_token=first.cursor)
        self.assertEqual(second.safe_reason, "CURSOR_SELECTED_BUNDLE_CHANGED")

    def test_tampered_cursor_is_rejected(self) -> None:
        fixture = build_day100_fixture()
        request = retrieval_request(fixture, top_k=2)
        first = fixture.retriever.retrieve(request)
        assert first.cursor is not None
        tampered = first.cursor[:-1] + ("A" if first.cursor[-1] != "A" else "B")
        second = fixture.retriever.retrieve(request, cursor_token=tampered)
        self.assertIn(second.safe_reason, {
            "CURSOR_SIGNATURE_INVALID",
            "CURSOR_ENCODING_NON_CANONICAL",
        })

    def test_expired_cursor_is_rejected(self) -> None:
        fixture = build_day100_fixture()
        request = retrieval_request(fixture, top_k=2)
        first = fixture.retriever.retrieve(request)
        assert first.cursor is not None
        fixture.clock.value += 301
        second = fixture.retriever.retrieve(request, cursor_token=first.cursor)
        self.assertEqual(second.safe_reason, "CURSOR_EXPIRED")

    def test_query_change_invalidates_cursor(self) -> None:
        fixture = build_day100_fixture()
        first_request = retrieval_request(fixture, top_k=2)
        first = fixture.retriever.retrieve(first_request)
        assert first.cursor is not None
        changed = retrieval_request(
            fixture,
            query_text="finance compliance",
            top_k=2,
        )
        second = fixture.retriever.retrieve(changed, cursor_token=first.cursor)
        self.assertEqual(second.safe_reason, "CURSOR_QUERY_CHANGED")


if __name__ == "__main__":
    unittest.main()
