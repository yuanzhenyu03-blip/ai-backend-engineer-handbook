from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day102_grounding_citations import build_day102_fixture
from rag_grounding_cache import GroundingResponseCache
from rag_grounding_contracts import SemanticRelation
from day102_test_support import cache_key, revoke


class Day102CacheAuthorizationTests(unittest.TestCase):
    def test_exact_identity_cache_hit(self) -> None:
        fixture = build_day102_fixture()
        response = fixture.pipeline.execute(fixture.request)
        key = cache_key(fixture, response.bundle_digest or "MISSING")
        cache = GroundingResponseCache()
        cache.put(key, response)
        self.assertIs(
            cache.get(
                key,
                current_authorization_scope_fingerprint=fixture.scope.fingerprint,
            ),
            response,
        )

    def test_authorization_scope_change_forces_cache_miss(self) -> None:
        fixture = build_day102_fixture()
        response = fixture.pipeline.execute(fixture.request)
        key = cache_key(fixture, response.bundle_digest or "MISSING")
        cache = GroundingResponseCache()
        cache.put(key, response)
        revoke(fixture, "occurrence:A")
        current = fixture.authorization.read(
            tenant_id=fixture.request.tenant_id,
            principal_subject=fixture.request.principal_subject,
            action=fixture.request.action,
            purpose=fixture.request.purpose,
        )
        assert current is not None
        self.assertIsNone(cache.get(
            key,
            current_authorization_scope_fingerprint=current.fingerprint,
        ))

    def test_principal_identity_changes_cache_key(self) -> None:
        fixture = build_day102_fixture()
        response = fixture.pipeline.execute(fixture.request)
        key = cache_key(fixture, response.bundle_digest or "MISSING")
        other = replace(key, principal_fingerprint="sha256:other-principal")
        self.assertNotEqual(key.fingerprint, other.fingerprint)

    def test_source_version_or_bundle_change_changes_cache_key(self) -> None:
        fixture = build_day102_fixture()
        response = fixture.pipeline.execute(fixture.request)
        key = cache_key(fixture, response.bundle_digest or "MISSING")
        changed = replace(
            key,
            grounding_bundle_digest="sha256:changed-window-bundle",
        )
        self.assertNotEqual(key.fingerprint, changed.fingerprint)

    def test_abstained_response_is_not_cacheable_as_answer(self) -> None:
        fixture = build_day102_fixture(relations_by_claim_id={})
        # Explicitly override both known Claims to unsupported.
        fixture.verifier.relations_by_claim_id = {
            "claim:refund-window": SemanticRelation.UNSUPPORTED,
            "claim:submission-channel": SemanticRelation.UNSUPPORTED,
        }
        response = fixture.pipeline.execute(fixture.request)
        key = cache_key(fixture, response.bundle_digest or "MISSING")
        with self.assertRaises(ValueError):
            GroundingResponseCache().put(key, response)


if __name__ == "__main__":
    unittest.main()
