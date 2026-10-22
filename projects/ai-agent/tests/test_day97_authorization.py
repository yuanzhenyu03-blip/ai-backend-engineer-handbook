from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day97_authorized_chunk_access import build_fixture, request_for
from rag_acl_contracts import ACLEntry, AccessEffect, ResourceRef
from rag_authorization import (
    AuthorizationOutcome,
    AuthorizationRequest,
)


class Day97AuthorizationTests(unittest.TestCase):
    def test_owner_and_viewer_exact_read_are_allowed(self) -> None:
        for principal_name in ("owner", "viewer"):
            with self.subTest(principal=principal_name):
                fixture = build_fixture()
                result = fixture.service.authorize(
                    request_for(fixture, principal_name)
                )
                self.assertEqual(
                    result.decision.outcome,
                    AuthorizationOutcome.ALLOW,
                )
                self.assertIsNotNone(result.permit)

    def test_same_tenant_member_without_grant_is_default_denied(self) -> None:
        fixture = build_fixture()
        result = fixture.service.authorize(request_for(fixture, "member"))
        self.assertEqual(result.decision.outcome, AuthorizationOutcome.DENY)
        self.assertEqual(
            result.decision.internal_reason_code,
            "DEFAULT_DENY_NO_APPLICABLE_GRANT",
        )
        self.assertIsNone(result.permit)

    def test_unsupported_or_ungranted_action_is_denied(self) -> None:
        fixture = build_fixture()
        result = fixture.service.authorize(request_for(
            fixture,
            "viewer",
            action="chunk.export",
        ))
        self.assertEqual(result.decision.outcome, AuthorizationOutcome.DENY)

    def test_cross_tenant_and_missing_use_same_external_response(self) -> None:
        fixture = build_fixture()
        member_denial = fixture.service.authorize(
            request_for(fixture, "member")
        ).decision
        guessed_resource = ResourceRef.chunk_set(
            "tenant-b",
            "guessed-document",
            "guessed-version",
            fixture.resource.chunk_set_id or "chunk-set:guessed",
        )
        cross_request = AuthorizationRequest(
            principal=fixture.principals["tenant_b"],
            tenant_id="tenant-b",
            resource=guessed_resource,
            action="chunk.text.read",
            audience="guarded-chunk-reader",
            purpose="interactive-rag-read",
            chunk_ids=fixture.chunk_ids,
        )
        cross_denial = fixture.service.authorize(cross_request).decision
        self.assertEqual(cross_denial.outcome, AuthorizationOutcome.DENY)
        self.assertEqual(cross_denial.external_status, member_denial.external_status)
        self.assertEqual(
            cross_denial.safe_external_message,
            member_denial.safe_external_message,
        )

    def test_explicit_chunk_deny_overrides_document_allow(self) -> None:
        fixture = build_fixture()
        denied_chunk = fixture.resource.chunk(fixture.chunk_ids[0])
        policy = replace(
            fixture.policy,
            entries=fixture.policy.entries + (ACLEntry(
                "deny-viewer-first-chunk",
                fixture.principals["viewer"].subject,
                denied_chunk,
                "chunk.text.read",
                AccessEffect.DENY,
            ),),
        )
        fixture.authorization.put_policy(policy)
        result = fixture.service.authorize(request_for(fixture, "viewer"))
        self.assertEqual(result.decision.outcome, AuthorizationOutcome.DENY)
        self.assertEqual(
            result.decision.internal_reason_code,
            "APPLICABLE_EXPLICIT_DENY",
        )

    def test_chunk_allow_cannot_expand_parent_permission_by_default(self) -> None:
        fixture = build_fixture()
        policy = replace(
            fixture.policy,
            entries=fixture.policy.entries + (ACLEntry(
                "grant-member-one-child",
                fixture.principals["member"].subject,
                fixture.resource.chunk(fixture.chunk_ids[0]),
                "chunk.text.read",
                AccessEffect.ALLOW,
            ),),
        )
        fixture.authorization.put_policy(policy)
        result = fixture.service.authorize(request_for(
            fixture,
            "member",
            chunk_ids=(fixture.chunk_ids[0],),
        ))
        self.assertEqual(result.decision.outcome, AuthorizationOutcome.DENY)
        self.assertEqual(
            result.decision.internal_reason_code,
            "CHILD_ALLOW_CANNOT_EXPAND_PARENT_PERMISSION",
        )

    def test_service_principal_requires_exact_embedding_action(self) -> None:
        fixture = build_fixture()
        allowed = fixture.service.authorize(request_for(
            fixture,
            "worker",
            action="chunk:read_for_embedding",
            purpose="day98-embedding",
        ))
        unrelated = fixture.service.authorize(request_for(
            fixture,
            "worker",
            action="chunk.text.read",
        ))
        self.assertEqual(allowed.decision.outcome, AuthorizationOutcome.ALLOW)
        self.assertEqual(unrelated.decision.outcome, AuthorizationOutcome.DENY)

    def test_human_cannot_use_service_only_embedding_action(self) -> None:
        fixture = build_fixture()
        policy = replace(
            fixture.policy,
            entries=fixture.policy.entries + (ACLEntry(
                "grant-owner-embedding",
                fixture.principals["owner"].subject,
                fixture.resource,
                "chunk:read_for_embedding",
                AccessEffect.ALLOW,
            ),),
        )
        fixture.authorization.put_policy(policy)
        result = fixture.service.authorize(request_for(
            fixture,
            "owner",
            action="chunk:read_for_embedding",
            purpose="day98-embedding",
        ))
        self.assertEqual(result.decision.outcome, AuthorizationOutcome.DENY)

    def test_disabled_service_principal_is_denied(self) -> None:
        fixture = build_fixture()
        result = fixture.service.authorize(request_for(
            fixture,
            "disabled",
            action="chunk:read_for_embedding",
            purpose="day98-embedding",
        ))
        self.assertEqual(result.decision.outcome, AuthorizationOutcome.DENY)

    def test_authorization_outage_is_indeterminate_and_503(self) -> None:
        fixture = build_fixture()
        fixture.authorization.set_available(False)
        decision = fixture.service.authorize(
            request_for(fixture, "viewer")
        ).decision
        self.assertEqual(decision.outcome, AuthorizationOutcome.INDETERMINATE)
        self.assertEqual(decision.external_status, 503)
        self.assertEqual(
            decision.internal_reason_code,
            "AUTHORIZATION_STATE_UNAVAILABLE",
        )

    def test_cache_is_revision_bound_and_never_reuses_stale_allow(self) -> None:
        fixture = build_fixture()
        request = request_for(fixture, "viewer")
        first = fixture.service.authorize(request)
        second = fixture.service.authorize(request)
        self.assertEqual(first.decision.outcome, AuthorizationOutcome.ALLOW)
        self.assertEqual(second.decision.outcome, AuthorizationOutcome.ALLOW)
        self.assertEqual(fixture.cache.hits, 1)
        fixture.authorization.revoke_grant(
            tenant_id="tenant-a",
            document_id="report-42",
            entry_id="grant-viewer-read",
        )
        after_revocation = fixture.service.authorize(request)
        self.assertEqual(
            after_revocation.decision.outcome,
            AuthorizationOutcome.DENY,
        )
        self.assertEqual(fixture.cache.hits, 1)

    def test_unknown_chunk_is_denied_before_permit_issuance(self) -> None:
        fixture = build_fixture()
        decision = fixture.service.authorize(request_for(
            fixture,
            "owner",
            chunk_ids=("chunk:guessed",),
        )).decision
        self.assertEqual(decision.outcome, AuthorizationOutcome.DENY)


if __name__ == "__main__":
    unittest.main()
