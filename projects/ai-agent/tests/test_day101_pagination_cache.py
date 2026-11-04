from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day101_query_rewriting_reranking import build_day101_fixture
from rag_reranking_cache import (
    InMemoryRerankingCache,
    RerankingCacheEntry,
    RerankingCacheKey,
    RerankingCursor,
    RerankingCursorCodec,
    RerankingCursorError,
)
from day101_test_support import build_intermediate


class Day101PaginationCacheTests(unittest.TestCase):
    def _key_and_result(self):
        fixture = build_day101_fixture()
        request, original, rewrite_set, _, pool, rerank_request = build_intermediate(fixture)
        result = fixture.pipeline.validator.validate(
            request=rerank_request,
            response=fixture.reranker.rank(rerank_request),
            contract=fixture.pipeline.reranker_contract,
        ).result
        key = RerankingCacheKey(
            request.tenant_id,
            original.principal_hash,
            fixture.day100.scope.fingerprint,
            fixture.day100.bundle.fingerprint,
            original.fingerprint,
            rewrite_set.fingerprint,
            fixture.pipeline.multi_query.policy.fingerprint,
            pool.digest,
            fixture.pipeline.reranker_contract.fingerprint,
            rerank_request.input_windows_digest,
        )
        return key, result

    def test_cache_key_binds_rewrite_set_identity(self) -> None:
        key, _ = self._key_and_result()
        changed = replace(key, rewrite_set_fingerprint="changed")
        self.assertNotEqual(key.fingerprint, changed.fingerprint)

    def test_cache_miss_after_identity_change(self) -> None:
        key, result = self._key_and_result()
        cache = InMemoryRerankingCache()
        cache.put(RerankingCacheEntry(key, result, expires_at=200))
        self.assertIsNotNone(cache.get(key, now=100))
        self.assertIsNone(cache.get(
            replace(key, candidate_pool_digest="changed"), now=100
        ))

    def test_signed_cursor_detects_tampering(self) -> None:
        key, result = self._key_and_result()
        cursor = RerankingCursor(
            "day101-cursor-v1",
            key.tenant_id,
            key.principal_hash,
            key.authorization_scope_fingerprint,
            key.selected_bundle_fingerprint,
            key.original_query_fingerprint,
            key.rewrite_set_fingerprint,
            key.candidate_pool_digest,
            key.reranker_contract_fingerprint,
            result.digest,
            2,
            200,
        )
        codec = RerankingCursorCodec(b"cursor-secret")
        token = codec.encode(cursor)
        with self.assertRaises(RerankingCursorError):
            codec.decode(token[:-1] + ("A" if token[-1] != "A" else "B"))

    def test_cursor_rejects_bundle_change(self) -> None:
        key, result = self._key_and_result()
        cursor = RerankingCursor(
            "day101-cursor-v1",
            key.tenant_id,
            key.principal_hash,
            key.authorization_scope_fingerprint,
            key.selected_bundle_fingerprint,
            key.original_query_fingerprint,
            key.rewrite_set_fingerprint,
            key.candidate_pool_digest,
            key.reranker_contract_fingerprint,
            result.digest,
            2,
            200,
        )
        codec = RerankingCursorCodec(b"cursor-secret")
        changed = replace(cursor, selected_bundle_fingerprint="new-bundle")
        with self.assertRaisesRegex(
            RerankingCursorError, "selected_bundle_fingerprint"
        ):
            codec.validate_current(cursor, expected=changed, now=100)


if __name__ == "__main__":
    unittest.main()
