from __future__ import annotations

from dataclasses import replace
import hashlib
import unittest

from examples.day97_authorized_chunk_access import build_fixture, request_for
from rag_authorization import PermitIssuer, SignedPermit
from rag_authorized_chunk_reader import GuardedReadOutcome
from rag_ingestion_contracts import DocumentIdentity


class Day97GuardedChunkReaderTests(unittest.TestCase):
    def authorize(self, fixture, *, action="chunk.text.read", purpose=None):
        principal_name = "worker" if action == "chunk:read_for_embedding" else "owner"
        actual_purpose = purpose or (
            "day98-embedding"
            if action == "chunk:read_for_embedding"
            else "interactive-rag-read"
        )
        result = fixture.service.authorize(request_for(
            fixture,
            principal_name,
            action=action,
            purpose=actual_purpose,
        ))
        assert result.permit is not None
        return principal_name, actual_purpose, result.permit

    def read(self, fixture, principal_name, purpose, permit, *, action=None):
        return fixture.reader.read(
            permit=permit,
            principal=fixture.principals[principal_name],
            expected_action=action or permit.claims.action,
            expected_audience="guarded-chunk-reader",
            expected_purpose=purpose,
        )

    def test_valid_permit_releases_only_bound_chunks_once(self) -> None:
        fixture = build_fixture()
        name, purpose, permit = self.authorize(fixture)
        first = self.read(fixture, name, purpose, permit)
        replay = self.read(fixture, name, purpose, permit)
        self.assertEqual(first.outcome, GuardedReadOutcome.RELEASED)
        self.assertEqual(
            tuple(chunk.chunk_id for chunk in first.chunks),
            permit.claims.chunk_ids,
        )
        self.assertEqual(replay.outcome, GuardedReadOutcome.DENIED)
        self.assertEqual(replay.internal_reason_code, "PERMIT_ALREADY_CONSUMED")

    def test_tampered_signature_is_rejected(self) -> None:
        fixture = build_fixture()
        name, purpose, permit = self.authorize(fixture)
        tampered = SignedPermit(permit.claims, "0" * len(permit.signature))
        result = self.read(fixture, name, purpose, tampered)
        self.assertEqual(result.outcome, GuardedReadOutcome.DENIED)
        self.assertEqual(result.internal_reason_code, "PERMIT_SIGNATURE_INVALID")

    def test_untrusted_issuer_is_rejected_even_with_same_hmac_key(self) -> None:
        fixture = build_fixture()
        authorization = fixture.service.authorize(request_for(fixture, "owner"))
        malicious_issuer = PermitIssuer(
            issuer="untrusted-issuer.synthetic.invalid",
            signing_key=hashlib.sha256(
                b"deterministic Day97 classroom signing material"
            ).digest(),
            clock=fixture.clock,
            nonce_factory=lambda: "untrusted-issuer-nonce",
        )
        permit = malicious_issuer.issue(authorization.decision)
        result = self.read(
            fixture,
            "owner",
            "interactive-rag-read",
            permit,
        )
        self.assertEqual(result.outcome, GuardedReadOutcome.DENIED)
        self.assertEqual(result.internal_reason_code, "PERMIT_SIGNATURE_INVALID")

    def test_subject_action_audience_and_purpose_are_bound(self) -> None:
        scenarios = (
            ("viewer", "interactive-rag-read", "chunk.text.read", "guarded-chunk-reader"),
            ("owner", "interactive-rag-read", "chunk.export", "guarded-chunk-reader"),
            ("owner", "different-purpose", "chunk.text.read", "guarded-chunk-reader"),
            ("owner", "interactive-rag-read", "chunk.text.read", "other-reader"),
        )
        for principal_name, purpose, action, audience in scenarios:
            with self.subTest(
                principal=principal_name,
                purpose=purpose,
                action=action,
                audience=audience,
            ):
                fixture = build_fixture()
                _, _, permit = self.authorize(fixture)
                result = fixture.reader.read(
                    permit=permit,
                    principal=fixture.principals[principal_name],
                    expected_action=action,
                    expected_audience=audience,
                    expected_purpose=purpose,
                )
                self.assertEqual(result.outcome, GuardedReadOutcome.DENIED)

    def test_expired_permit_is_rejected(self) -> None:
        fixture = build_fixture()
        name, purpose, permit = self.authorize(fixture)
        fixture.clock.value = permit.claims.expires_at
        result = self.read(fixture, name, purpose, permit)
        self.assertEqual(result.outcome, GuardedReadOutcome.DENIED)
        self.assertEqual(
            result.internal_reason_code,
            "PERMIT_EXPIRED_OR_NOT_YET_VALID",
        )

    def test_revoked_grant_advances_acl_and_epoch_and_rejects_old_permit(self) -> None:
        fixture = build_fixture()
        name, purpose, permit = self.authorize(
            fixture,
            action="chunk:read_for_embedding",
        )
        previous_set = fixture.chunks.read_chunk_set(fixture.resource.chunk_set_id)
        updated = fixture.authorization.revoke_grant(
            tenant_id="tenant-a",
            document_id="report-42",
            entry_id="grant-worker-embedding",
        )
        self.assertEqual(updated.acl_revision, permit.claims.revisions.acl_revision + 1)
        self.assertEqual(
            updated.authorization_epoch,
            permit.claims.revisions.authorization_epoch + 1,
        )
        result = self.read(fixture, name, purpose, permit)
        self.assertEqual(result.outcome, GuardedReadOutcome.DENIED)
        self.assertEqual(
            previous_set,
            fixture.chunks.read_chunk_set(fixture.resource.chunk_set_id),
        )

    def test_epoch_policy_acl_and_membership_revision_mismatch_reject(self) -> None:
        mutations = (
            "epoch",
            "policy_revision",
            "acl_revision",
            "membership_revision",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                fixture = build_fixture()
                name, purpose, permit = self.authorize(fixture)
                if mutation == "epoch":
                    fixture.authorization.advance_authorization_epoch(
                        tenant_id="tenant-a", document_id="report-42"
                    )
                elif mutation in {"policy_revision", "acl_revision"}:
                    policy = fixture.authorization.read_policy(
                        "tenant-a", "report-42"
                    )
                    assert policy is not None
                    fixture.authorization.put_policy(replace(
                        policy,
                        **{mutation: getattr(policy, mutation) + 1},
                    ))
                else:
                    membership = fixture.authorization.read_membership(
                        "tenant-a", fixture.principals["owner"].subject
                    )
                    assert membership is not None
                    fixture.authorization.put_membership(replace(
                        membership,
                        revision=membership.revision + 1,
                    ))
                result = self.read(fixture, name, purpose, permit)
                self.assertEqual(result.outcome, GuardedReadOutcome.DENIED)
                self.assertEqual(
                    result.internal_reason_code,
                    "PERMIT_AUTHORIZATION_REVISION_MISMATCH",
                )

    def test_selected_pointer_and_document_fence_mismatch_reject(self) -> None:
        for mutation in ("selection", "document"):
            with self.subTest(mutation=mutation):
                fixture = build_fixture()
                name, purpose, permit = self.authorize(fixture)
                if mutation == "selection":
                    key = ("tenant-a", "report-42")
                    with fixture.chunks._lock:
                        current = fixture.chunks._selections[key]
                        fixture.chunks._selections[key] = replace(
                            current,
                            revision=current.revision + 1,
                        )
                else:
                    identity = DocumentIdentity("tenant-a", "report-42")
                    with fixture.day95._lock:
                        current = fixture.day95.read_document(identity)
                        fixture.day95._documents[("tenant-a", "report-42")] = replace(
                            current,
                            state_version=current.state_version + 1,
                            fence_token=current.fence_token + 1,
                        )
                result = self.read(fixture, name, purpose, permit)
                self.assertEqual(result.outcome, GuardedReadOutcome.DENIED)

    def test_policy_outage_at_pep_is_indeterminate_and_releases_nothing(self) -> None:
        fixture = build_fixture()
        name, purpose, permit = self.authorize(fixture)
        fixture.authorization.set_available(False)
        result = self.read(fixture, name, purpose, permit)
        self.assertEqual(result.outcome, GuardedReadOutcome.INDETERMINATE)
        self.assertEqual(result.external_status, 503)
        self.assertEqual(result.chunks, ())

    def test_embedding_handoff_requires_embedding_action(self) -> None:
        fixture = build_fixture()
        name, purpose, permit = self.authorize(
            fixture,
            action="chunk:read_for_embedding",
        )
        result = self.read(fixture, name, purpose, permit)
        handoff = fixture.reader.embedding_handoff(
            permit=permit,
            result=result,
        )
        self.assertEqual(handoff.chunk_set_id, fixture.resource.chunk_set_id)
        self.assertEqual(handoff.authorization_epoch, 1)
        self.assertEqual(handoff.protected_data_classification, "PROTECTED")

    def test_audit_is_content_safe_and_excludes_raw_principal(self) -> None:
        fixture = build_fixture()
        name, purpose, permit = self.authorize(fixture)
        result = self.read(fixture, name, purpose, permit)
        self.assertTrue(result.released)
        evidence = str(fixture.audit.events())
        self.assertNotIn("tenant-a-owner", evidence)
        self.assertNotIn("Synthetic public guidance", evidence)
        self.assertIn("sha256:", evidence)


if __name__ == "__main__":
    unittest.main()
