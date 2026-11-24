from __future__ import annotations

from dataclasses import asdict, fields, replace
import json
from typing import Any, cast
import unittest
from unittest.mock import patch

from examples.day106_capstone_support import (
    build_canonical_day101_fixture,
    execute_day101_query,
    execute_grounding_from_day101,
    refund_window_claim,
)
from examples.day101_query_rewriting_reranking import QUERY_DIGEST_SECRET
from examples.day106_production_rag_capstone import (
    POINTER_NAME,
    _bind_attempt,
    _build_generation,
    _decide_query,
    _lineages,
    _load_prerequisite_evidence,
    _policy,
    _prepare_query,
    _ruler,
    _release_currentness_snapshot,
    _snapshot,
    run_example,
)
from rag_authorized_retriever import classroom_authorization_revisions
from rag_capstone_contracts import CapstoneRequestBinding
from rag_capstone_orchestrator import (
    CapstoneIdentityConflict,
    InMemoryReleaseCurrentnessAuthority,
)
from rag_chunking_contracts import stable_hash
from rag_grounding_adapters import DeterministicAnswerProvider
from rag_grounding_contracts import Day102Outcome
from rag_grounding_planner import GroundingCurrentnessOracle
from rag_index_lifecycle_committer import (
    IndexLifecycleCommitter,
    InMemoryIndexLifecycleStore,
)
from rag_index_lifecycle_contracts import ActivePointer
from rag_index_lifecycle_orchestrator import (
    DeterministicSealedIndexProvider,
    IndexLifecycleOrchestrator,
)
from rag_index_read_views import IndexReadViewManager
from rag_security_contracts import context_assembly_digest
from rag_security_pipeline import RagSecurityPipeline, SecurityGateRejected
from rag_query_rewrite_contracts import protected_query_digest


def build_binding_fixture():
    prerequisite = _load_prerequisite_evidence()
    lineage_by_id = _lineages(prerequisite)
    lineages = tuple(lineage_by_id[key] for key in sorted(lineage_by_id))
    source_snapshot_digest = stable_hash(tuple(item.digest for item in lineages))
    revisions = classroom_authorization_revisions(
        policy_revision=1,
        acl_revision=1,
        authorization_epoch=1,
    )
    authorization_digest = stable_hash(asdict(revisions))
    snapshot = _snapshot(
        snapshot_id="BS1-test",
        authorization_revision_digest=authorization_digest,
        included=lineages,
        source_snapshot_digest=source_snapshot_digest,
    )
    store = InMemoryIndexLifecycleStore()
    committer = IndexLifecycleCommitter(store)
    lifecycle = IndexLifecycleOrchestrator(
        provider=DeterministicSealedIndexProvider(),
        committer=committer,
    )
    generation = _build_generation(
        generation_id="G2-test",
        snapshot=snapshot,
        included=lineages,
        provider_fence=8,
        ruler=_ruler(prerequisite),
        prerequisite=prerequisite,
        store=store,
        committer=committer,
        orchestrator=lifecycle,
    )
    pointer = ActivePointer(POINTER_NAME + "-test", "G2-test", 8)
    store.seed_active_pointer(
        pointer=pointer,
        provider_alias_generation_id="G2-test",
    )
    serving = build_canonical_day101_fixture(
        generation_id="G2-test",
        pointer_revision=8,
        generation_artifact_fingerprint=generation.artifact.fingerprint,
        manifest_occurrence_ids=("A@v1", "C@v1"),
        authorization_revision=1,
    )
    return (
        generation,
        pointer,
        lineages,
        serving,
        IndexReadViewManager(store),
        authorization_digest,
    )


class Day106CapstonePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_example()

    def test_report_is_deterministic_and_checksum_bound(self) -> None:
        replayed = run_example()

        self.assertEqual(self.report, replayed)
        unsigned = {
            key: value
            for key, value in self.report.items()
            if key != "report_checksum"
        }
        self.assertEqual(self.report["report_checksum"], stable_hash(unsigned))

    def test_normal_q1_q2_q3_release_with_exact_context(self) -> None:
        queries = cast(dict[str, dict[str, Any]], self.report["normal_queries"])

        self.assertEqual(queries["Q1"]["prompt_occurrence_ids"], ["A@v1"])
        self.assertEqual(queries["Q2"]["prompt_occurrence_ids"], ["C@v1"])
        self.assertEqual(
            queries["Q3"]["prompt_occurrence_ids"],
            ["A@v1", "C@v1"],
        )
        for query in queries.values():
            self.assertEqual(query["release_result"], "PASS")
            self.assertEqual(query["release_disposition"], "RELEASE")
            self.assertTrue(query["response_intent_expected"])
            self.assertEqual(query["final_response_state"], "DELIVERED")
            self.assertEqual(
                query["request_attempt_id"],
                query["retrieval_request_id"],
            )

    def test_request_binding_spine_binds_artifact_bundle_and_auth_revision(
        self,
    ) -> None:
        generation, pointer, lineages, serving, views, auth_digest = (
            build_binding_fixture()
        )

        bound = _bind_attempt(
            attempt_id="R-binding-spine",
            pointer=pointer,
            generation=generation,
            serving_fixture=serving,
            lineages=lineages,
            policy=_policy(),
            views=views,
            observed_at="2026-11-23T09:01:00+08:00",
        )
        spine = bound.capstone

        self.assertEqual(spine.request_attempt_id, bound.security.request_id)
        self.assertEqual(spine.generation_id, pointer.generation_id)
        self.assertEqual(spine.pointer_revision, pointer.revision)
        self.assertEqual(
            spine.generation_artifact_digest,
            generation.artifact.fingerprint,
        )
        self.assertEqual(
            spine.selected_retrieval_bundle_fingerprint,
            serving.day100.bundle.fingerprint,
        )
        self.assertEqual(
            serving.day100.bundle.generation_contract_fingerprint,
            generation.artifact.fingerprint,
        )
        self.assertEqual(spine.retrieval_authorization_revision_digest, auth_digest)
        self.assertNotIn(
            "occurrence_ids",
            {item.name for item in fields(CapstoneRequestBinding)},
        )

    def test_request_binding_rejects_bundle_artifact_and_auth_digest_drift(
        self,
    ) -> None:
        generation, pointer, lineages, serving, views, _ = build_binding_fixture()
        original_bundle = serving.day100.bundle
        serving.day100.bundle = replace(
            original_bundle,
            generation_contract_fingerprint=stable_hash("wrong-artifact"),
        )
        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RETRIEVAL_GENERATION_ARTIFACT_CONFLICT",
        ):
            _bind_attempt(
                attempt_id="R-bad-bundle",
                pointer=pointer,
                generation=generation,
                serving_fixture=serving,
                lineages=lineages,
                policy=_policy(),
                views=views,
                observed_at="2026-11-23T09:01:00+08:00",
            )

    def test_request_binding_rejects_foreign_retrieval_contracts(self) -> None:
        cases = (
            (
                "RETRIEVAL_CHUNK_SET_CONFLICT",
                lambda bundle: replace(
                    bundle,
                    chunk_set_id="foreign-chunk-set",
                    lexical=replace(
                        bundle.lexical,
                        chunk_set_id="foreign-chunk-set",
                    ),
                ),
            ),
            (
                "RETRIEVAL_EMBEDDING_SET_CONFLICT",
                lambda bundle: replace(
                    bundle,
                    embedding_set_id="foreign-embedding-set",
                ),
            ),
            (
                "RETRIEVAL_EMBEDDING_CONTRACT_CONFLICT",
                lambda bundle: replace(
                    bundle,
                    embedding_contract_fingerprint="foreign-contract",
                    query_encoder=replace(
                        bundle.query_encoder,
                        document_contract_fingerprint="foreign-contract",
                    ),
                ),
            ),
        )
        for reason, mutate in cases:
            with self.subTest(reason=reason):
                generation, pointer, lineages, serving, views, _ = (
                    build_binding_fixture()
                )
                serving.day100.bundle = mutate(serving.day100.bundle)
                with self.assertRaisesRegex(CapstoneIdentityConflict, reason):
                    _bind_attempt(
                        attempt_id=f"R-{reason}",
                        pointer=pointer,
                        generation=generation,
                        serving_fixture=serving,
                        lineages=lineages,
                        policy=_policy(),
                        views=views,
                        observed_at="2026-11-23T09:01:00+08:00",
                    )

        generation, pointer, lineages, serving, views, _ = build_binding_fixture()
        serving.day100.scope = replace(
            serving.day100.scope,
            revisions=classroom_authorization_revisions(
                policy_revision=2,
                acl_revision=2,
                authorization_epoch=2,
            ),
        )
        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "AUTHORIZATION_REVISION_DIGEST_CONFLICT",
        ):
            _bind_attempt(
                attempt_id="R-bad-auth-revision",
                pointer=pointer,
                generation=generation,
                serving_fixture=serving,
                lineages=lineages,
                policy=_policy(),
                views=views,
                observed_at="2026-11-23T09:01:00+08:00",
            )

    def test_request_binding_rejects_lineage_digest_drift(self) -> None:
        generation, pointer, lineages, serving, views, _ = build_binding_fixture()
        tampered = (
            replace(lineages[0], content_digest=stable_hash("changed-content")),
            lineages[1],
        )

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "MANIFEST_LINEAGE_CONTENT_CONFLICT",
        ):
            _bind_attempt(
                attempt_id="R-bad-lineage",
                pointer=pointer,
                generation=generation,
                serving_fixture=serving,
                lineages=tampered,
                policy=_policy(),
                views=views,
                observed_at="2026-11-23T09:01:00+08:00",
            )

    def test_foreign_generation_day101_handoff_is_rejected(self) -> None:
        generation, pointer, lineages, serving, views, _ = build_binding_fixture()
        bound = _bind_attempt(
            attempt_id="R-current-generation",
            pointer=pointer,
            generation=generation,
            serving_fixture=serving,
            lineages=lineages,
            policy=_policy(),
            views=views,
            observed_at="2026-11-23T09:01:00+08:00",
        )
        foreign = build_canonical_day101_fixture(
            generation_id="GX-foreign",
            pointer_revision=99,
            generation_artifact_fingerprint=stable_hash("foreign-artifact"),
            manifest_occurrence_ids=("A@v1", "C@v1"),
            authorization_revision=1,
        )
        foreign_run = execute_day101_query(
            foreign,
            query_id="foreign-Q1",
            query_text="What is the refund window?",
            request_attempt_id="R-current-generation",
        )
        release_currentness = InMemoryReleaseCurrentnessAuthority()
        release_snapshot = _release_currentness_snapshot(
            snapshot_id="release-currentness-test-G2",
            revision=1,
            generation=generation,
            eligible_occurrence_ids=("A@v1", "C@v1"),
            policy=_policy(),
        )
        release_currentness.put(release_snapshot)

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "DAY101_EXECUTION_RECEIPT_CONFLICT",
        ):
            _prepare_query(
                query_id="mixed-generation-Q1",
                bound=bound,
                serving_fixture=serving,
                release_currentness_authority=release_currentness,
                retrieval_run=foreign_run,
                claims=(refund_window_claim(),),
                lineages={item.occurrence_id: item for item in lineages},
                policy=_policy(),
                observed_at="2026-11-23T09:02:00+08:00",
            )

    def test_day101_query_identity_mismatch_is_rejected_before_model(self) -> None:
        generation, pointer, lineages, serving, views, _ = build_binding_fixture()
        bound = _bind_attempt(
            attempt_id="R-query-binding",
            pointer=pointer,
            generation=generation,
            serving_fixture=serving,
            lineages=lineages,
            policy=_policy(),
            views=views,
            observed_at="2026-11-23T09:01:00+08:00",
        )
        retrieval = execute_day101_query(
            serving,
            query_id="query-binding-Q1",
            query_text="What is the refund window?",
            request_attempt_id="R-query-binding",
        )
        mismatched = replace(
            retrieval,
            retrieval_request=replace(
                retrieval.retrieval_request,
                query_text="A different exact request",
            ),
        )
        currentness = InMemoryReleaseCurrentnessAuthority()
        currentness.put(
            _release_currentness_snapshot(
                snapshot_id="release-currentness-query-binding",
                revision=1,
                generation=generation,
                eligible_occurrence_ids=("A@v1", "C@v1"),
                policy=_policy(),
            )
        )

        with patch(
            "examples.day106_production_rag_capstone."
            "execute_grounding_from_day101"
        ) as generator:
            with self.assertRaisesRegex(
                CapstoneIdentityConflict,
                "DAY101_EXECUTION_RECEIPT_CONFLICT",
            ):
                _prepare_query(
                    query_id="query-binding-Q1",
                    bound=bound,
                    serving_fixture=serving,
                    release_currentness_authority=currentness,
                    retrieval_run=mismatched,
                    claims=(refund_window_claim(),),
                    lineages={item.occurrence_id: item for item in lineages},
                    policy=_policy(),
                    observed_at="2026-11-23T09:02:00+08:00",
                )
            generator.assert_not_called()

    def test_co_mutated_day101_handoff_requires_application_authority(self) -> None:
        generation, pointer, lineages, serving, views, _ = build_binding_fixture()
        bound = _bind_attempt(
            attempt_id="R-forged-query-binding",
            pointer=pointer,
            generation=generation,
            serving_fixture=serving,
            lineages=lineages,
            policy=_policy(),
            views=views,
            observed_at="2026-11-23T09:01:00+08:00",
        )
        retrieval = execute_day101_query(
            serving,
            query_id="forged-query-binding-Q1",
            query_text="What is the refund window?",
            request_attempt_id="R-forged-query-binding",
        )
        self.assertIsNotNone(retrieval.execution_receipt)
        forged_query = "A different exact request"
        forged_request = replace(
            retrieval.retrieval_request,
            query_text=forged_query,
        )
        forged_original_digest = protected_query_digest(
            QUERY_DIGEST_SECRET,
            forged_request.tenant_id,
            forged_query,
        )
        forged_response = replace(
            retrieval.day101_response,
            original_query_digest=forged_original_digest,
        )
        forged_receipt = replace(
            retrieval.execution_receipt,
            query_hash=forged_request.query_hash,
            original_query_digest=forged_original_digest,
            day101_handoff_digest=forged_response.handoff_digest,
        )
        forged_run = replace(
            retrieval,
            retrieval_request=forged_request,
            day101_response=forged_response,
            execution_receipt=forged_receipt,
        )
        currentness = InMemoryReleaseCurrentnessAuthority()
        currentness.put(
            _release_currentness_snapshot(
                snapshot_id="release-currentness-forged-query-binding",
                revision=1,
                generation=generation,
                eligible_occurrence_ids=("A@v1", "C@v1"),
                policy=_policy(),
            )
        )

        with patch(
            "examples.day106_production_rag_capstone."
            "execute_grounding_from_day101"
        ) as generator:
            with self.assertRaisesRegex(
                RuntimeError,
                "DAY101_EXECUTION_RECEIPT_AUTHORITY_CONFLICT",
            ):
                _prepare_query(
                    query_id="forged-query-binding-Q1",
                    bound=bound,
                    serving_fixture=serving,
                    release_currentness_authority=currentness,
                    retrieval_run=forged_run,
                    claims=(refund_window_claim(),),
                    lineages={item.occurrence_id: item for item in lineages},
                    policy=_policy(),
                    observed_at="2026-11-23T09:02:00+08:00",
                )
            generator.assert_not_called()

    def test_authorization_change_after_precheck_cannot_reach_generator(
        self,
    ) -> None:
        generation, _, _, serving, _, _ = build_binding_fixture()
        retrieval = execute_day101_query(
            serving,
            query_id="guarded-generation-Q1",
            query_text="What is the refund window?",
            request_attempt_id="R-guarded-generation",
        )
        original_recheck = GroundingCurrentnessOracle.recheck_identities
        revoked = False

        def recheck_then_revoke(oracle, *, identities, request):
            nonlocal revoked
            result = original_recheck(
                oracle,
                identities=identities,
                request=request,
            )
            if not revoked:
                revoked = True
                serving.day100.authorization.revoke_occurrence(
                    tenant_id=request.tenant_id,
                    principal_subject=request.principal_subject,
                    action=request.action,
                    purpose=request.purpose,
                    occurrence_id="A@v1",
                )
            return result

        with patch.object(
            GroundingCurrentnessOracle,
            "recheck_identities",
            autospec=True,
            side_effect=recheck_then_revoke,
        ), patch.object(
            DeterministicAnswerProvider,
            "generate",
            autospec=True,
            side_effect=AssertionError("revoked content reached generator"),
        ) as generator:
            grounding = execute_grounding_from_day101(
                serving,
                retrieval=retrieval,
                claims=(refund_window_claim(),),
            )

        self.assertTrue(revoked)
        self.assertEqual(grounding.day102_response.outcome, Day102Outcome.ABSTAINED)
        generator.assert_not_called()

    def test_context_content_digest_mismatch_is_rejected_before_model(self) -> None:
        generation, pointer, lineages, serving, views, _ = build_binding_fixture()
        bound = _bind_attempt(
            attempt_id="R-context-digest",
            pointer=pointer,
            generation=generation,
            serving_fixture=serving,
            lineages=lineages,
            policy=_policy(),
            views=views,
            observed_at="2026-11-23T09:01:00+08:00",
        )
        retrieval = execute_day101_query(
            serving,
            query_id="context-digest-Q1",
            query_text="What is the refund window?",
            request_attempt_id="R-context-digest",
        )
        currentness = InMemoryReleaseCurrentnessAuthority()
        currentness.put(
            _release_currentness_snapshot(
                snapshot_id="release-currentness-context-digest",
                revision=1,
                generation=generation,
                eligible_occurrence_ids=("A@v1", "C@v1"),
                policy=_policy(),
            )
        )
        original_assemble = RagSecurityPipeline.assemble_context

        def assemble_with_wrong_digest(**kwargs):
            context = original_assemble(**kwargs)
            wrong_digests = (stable_hash("wrong-content"),)
            return replace(
                context,
                included_content_digests=wrong_digests,
                assembled_context_digest=context_assembly_digest(
                    envelope_schema_version=context.envelope_schema_version,
                    serialization_version=context.serialization_version,
                    projection_version=context.projection_version,
                    included_occurrence_ids=context.included_occurrence_ids,
                    included_content_digests=wrong_digests,
                    structured_untrusted_data_digest=(
                        context.structured_untrusted_data_digest
                    ),
                ),
            )

        with patch.object(
            RagSecurityPipeline,
            "assemble_context",
            side_effect=assemble_with_wrong_digest,
        ), patch(
            "examples.day106_production_rag_capstone."
            "execute_grounding_from_day101"
        ) as generator:
            with self.assertRaisesRegex(
                CapstoneIdentityConflict,
                "CONTEXT_CONTENT_DIGEST_CONFLICT",
            ):
                _prepare_query(
                    query_id="context-digest-Q1",
                    bound=bound,
                    serving_fixture=serving,
                    release_currentness_authority=currentness,
                    retrieval_run=retrieval,
                    claims=(refund_window_claim(),),
                    lineages={item.occurrence_id: item for item in lineages},
                    policy=_policy(),
                    observed_at="2026-11-23T09:02:00+08:00",
                )
            generator.assert_not_called()

    def test_revocation_after_day101_blocks_before_prompt_and_model(self) -> None:
        generation, pointer, lineages, serving, views, _ = build_binding_fixture()
        bound = _bind_attempt(
            attempt_id="R-revoked-before-prompt",
            pointer=pointer,
            generation=generation,
            serving_fixture=serving,
            lineages=lineages,
            policy=_policy(),
            views=views,
            observed_at="2026-11-23T09:01:00+08:00",
        )
        retrieval = execute_day101_query(
            serving,
            query_id="revoked-before-prompt-Q1",
            query_text="What is the refund window?",
            request_attempt_id="R-revoked-before-prompt",
        )
        serving.day100.authorization.revoke_occurrence(
            tenant_id=bound.capstone.tenant_id,
            principal_subject=bound.capstone.principal_id,
            action=bound.capstone.action,
            purpose=bound.capstone.purpose,
            occurrence_id="A@v1",
        )
        currentness = InMemoryReleaseCurrentnessAuthority()
        currentness.put(
            _release_currentness_snapshot(
                snapshot_id="release-currentness-before-prompt",
                revision=1,
                generation=generation,
                eligible_occurrence_ids=("A@v1", "C@v1"),
                policy=_policy(),
            )
        )

        with patch(
            "examples.day106_production_rag_capstone."
            "execute_grounding_from_day101"
        ) as generator:
            with self.assertRaisesRegex(
                SecurityGateRejected,
                "retrieval decision is not PASS",
            ):
                _prepare_query(
                    query_id="revoked-before-prompt-Q1",
                    bound=bound,
                    serving_fixture=serving,
                    release_currentness_authority=currentness,
                    retrieval_run=retrieval,
                    claims=(refund_window_claim(),),
                    lineages={item.occurrence_id: item for item in lineages},
                    policy=_policy(),
                    observed_at="2026-11-23T09:02:00+08:00",
                )
            generator.assert_not_called()

    def test_release_rechecks_owned_current_authorization_after_revocation(
        self,
    ) -> None:
        generation, pointer, lineages, serving, views, _ = build_binding_fixture()
        bound = _bind_attempt(
            attempt_id="R-current-auth",
            pointer=pointer,
            generation=generation,
            serving_fixture=serving,
            lineages=lineages,
            policy=_policy(),
            views=views,
            observed_at="2026-11-23T09:01:00+08:00",
        )
        retrieval = execute_day101_query(
            serving,
            query_id="current-auth-Q1",
            query_text="What is the refund window?",
            request_attempt_id="R-current-auth",
        )
        release_currentness = InMemoryReleaseCurrentnessAuthority()
        release_snapshot = _release_currentness_snapshot(
            snapshot_id="release-currentness-test-G2",
            revision=1,
            generation=generation,
            eligible_occurrence_ids=("A@v1", "C@v1"),
            policy=_policy(),
        )
        release_currentness.put(release_snapshot)
        prepared = _prepare_query(
            query_id="current-auth-Q1",
            bound=bound,
            serving_fixture=serving,
            release_currentness_authority=release_currentness,
            retrieval_run=retrieval,
            claims=(refund_window_claim(),),
            lineages={item.occurrence_id: item for item in lineages},
            policy=_policy(),
            observed_at="2026-11-23T09:02:00+08:00",
        )
        serving.day100.authorization.revoke_occurrence(
            tenant_id=bound.capstone.tenant_id,
            principal_subject=bound.capstone.principal_id,
            action=bound.capstone.action,
            purpose=bound.capstone.purpose,
            occurrence_id="A@v1",
        )
        release_currentness.put(
            replace(
                release_snapshot,
                snapshot_id="release-currentness-test-G2-updated",
                revision=2,
                provenance_revision="PROV-R2",
                dlp_result="FAIL",
                evidence_digests=(stable_hash("updated-release-facts"),),
            )
        )

        decided = _decide_query(
            query_id="current-auth-Q1-after-revocation",
            prepared=prepared,
            observed_at="2026-11-23T09:03:00+08:00",
        )

        self.assertEqual(decided.record.disposition, "BLOCKED")
        self.assertIn(
            "CURRENT_AUTHORIZATION_CHANGED",
            decided.record.safe_reason_codes,
        )
        self.assertIn(
            "CURRENT_PROVENANCE_CHANGED",
            decided.record.safe_reason_codes,
        )
        self.assertIn("DLP_FAILED", decided.record.safe_reason_codes)
        self.assertIsNone(decided.record.response_intent_id)

    def test_release_currentness_authority_is_forward_only(self) -> None:
        generation, _, _, _, _, _ = build_binding_fixture()
        authority = InMemoryReleaseCurrentnessAuthority()
        first = _release_currentness_snapshot(
            snapshot_id="release-currentness-r1",
            revision=1,
            generation=generation,
            eligible_occurrence_ids=("A@v1", "C@v1"),
            policy=_policy(),
        )
        authority.put(first)

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RELEASE_CURRENTNESS_REVISION_CONFLICT",
        ):
            authority.put(
                replace(
                    first,
                    snapshot_id="release-currentness-r3",
                    revision=3,
                )
            )

        second = replace(
            first,
            snapshot_id="release-currentness-r2",
            revision=2,
        )
        authority.put(second)
        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "STALE_RELEASE_CURRENTNESS_REPLAY",
        ):
            authority.put(first)

    def test_p2_preserves_old_identity_but_blocks_old_release(self) -> None:
        lifecycle = cast(dict[str, Any], self.report["lifecycle"])
        revocation = cast(dict[str, Any], self.report["revocation_behavior"])
        candidate = cast(dict[str, Any], revocation["old_G2_candidate"])
        retrieval = cast(dict[str, Any], revocation["old_G2_retrieval_after_P2"])

        self.assertTrue(lifecycle["old_readview_identity_preserved"])
        self.assertEqual(candidate["generation_id"], "G2")
        self.assertEqual(candidate["pointer_revision"], 8)
        self.assertEqual(candidate["release_result"], "FAIL")
        self.assertEqual(candidate["release_disposition"], "BLOCKED")
        self.assertFalse(candidate["response_intent_expected"])
        self.assertEqual(candidate["final_response_state"], "NOT_ATTEMPTED")
        self.assertIn("CURRENT_AUTHORIZATION_CHANGED", candidate["safe_reason_codes"])
        self.assertNotIn("A@v1", retrieval["day101_occurrence_ids"])
        self.assertEqual(retrieval["generator_calls"], 0)

    def test_g3_cas_serves_q2_and_blocks_q1_q3_without_a(self) -> None:
        lifecycle = cast(dict[str, Any], self.report["lifecycle"])
        current = cast(dict[str, Any], lifecycle["current"])
        revocation = cast(dict[str, Any], self.report["revocation_behavior"])
        q2 = cast(dict[str, Any], revocation["new_G3_Q2"])
        blocked = cast(dict[str, dict[str, Any]], revocation["new_G3_blocks"])

        self.assertEqual(current["generation"], "G3")
        self.assertEqual(current["pointer_revision"], 9)
        self.assertEqual(current["manifest_occurrence_ids"], ["C@v1"])
        self.assertEqual(q2["prompt_occurrence_ids"], ["C@v1"])
        self.assertEqual(q2["release_disposition"], "RELEASE")
        self.assertEqual(q2["final_response_state"], "DELIVERED")
        for query_id in ("Q1", "Q3"):
            query = blocked[query_id]
            self.assertFalse(query["revoked_A_used"])
            self.assertNotIn("A@v1", query["retrieved_occurrence_ids"])
            self.assertEqual(query["generator_calls"], 0)
            self.assertEqual(query["response_dispatch"], "NOT_ATTEMPTED")

    def test_x_y_z_t_b_controls_never_enter_prompt(self) -> None:
        controls = cast(
            dict[str, dict[str, Any]],
            self.report["security_negative_controls"],
        )

        self.assertEqual(set(controls), {
            "X_document_injection",
            "Y_detector_inconclusive",
            "Z_composed_attack",
            "T_cross_tenant",
            "B_tombstoned",
            "ACL_current_authorization_denied",
            "PROVENANCE_stale",
        })
        self.assertEqual(controls["X_document_injection"]["bundle"], "FAIL")
        self.assertEqual(controls["Y_detector_inconclusive"]["retrieval"], "INCONCLUSIVE")
        self.assertEqual(controls["Z_composed_attack"]["bundle"], "FAIL")
        self.assertEqual(controls["T_cross_tenant"]["retrieval"], "FAIL")
        self.assertEqual(controls["B_tombstoned"]["retrieval"], "FAIL")
        self.assertEqual(
            controls["T_cross_tenant"]["safe_reason_code"],
            "TENANT_UNAUTHORIZED",
        )
        self.assertEqual(
            controls["B_tombstoned"]["safe_reason_code"],
            "TOMBSTONED",
        )
        self.assertEqual(
            controls["ACL_current_authorization_denied"]["safe_reason_code"],
            "CURRENT_AUTHORIZATION_DENIED",
        )
        self.assertEqual(
            controls["PROVENANCE_stale"]["safe_reason_code"],
            "STALE_PROVENANCE",
        )
        for control in controls.values():
            self.assertFalse(control["entered_prompt"])

    def test_unknown_reconciles_before_retry_and_delivery(self) -> None:
        recovery = cast(dict[str, Any], self.report["recovery"])
        history = cast(list[dict[str, Any]], recovery["history"])

        self.assertEqual(recovery["final_state"], "DELIVERED")
        self.assertTrue(recovery["append_only"])
        self.assertFalse(recovery["candidate_rewritten"])
        self.assertFalse(recovery["decision_rewritten"])
        self.assertEqual(
            [item["observation"] for item in history],
            [
                "SEND_STARTED",
                "UNKNOWN",
                "NOT_FOUND",
                "SEND_STARTED",
                "ACCEPTED",
                "DELIVERED",
                "DUPLICATE_RECEIPT",
            ],
        )
        for index, item in enumerate(history):
            expected_previous = None if index == 0 else history[index - 1]["record_id"]
            self.assertEqual(item["previous_record_id"], expected_previous)

    def test_report_is_content_safe_and_l2_scoped(self) -> None:
        serialized = json.dumps(self.report, sort_keys=True).lower()

        for forbidden in (
            "raw-secret-value",
            "database://",
            "system prompt body",
            "protected chunk body",
            "instruction override payload",
        ):
            self.assertNotIn(forbidden, serialized)
        for flag in (
            "raw_prompt_logged",
            "protected_chunk_logged",
            "answer_candidate_text_logged",
            "secret_logged",
            "raw_vector_logged",
        ):
            self.assertFalse(self.report[flag])
        self.assertEqual(self.report["overall_status"], "PASS")
        self.assertEqual(
            self.report["day106_overall_status"],
            "NOT_CLAIMED_BY_RUNTIME_REPORT",
        )
        self.assertIn("EXCLUDES_OFFLINE_REPLAY", self.report["overall_status_scope"])
        self.assertEqual(self.report["evidence_level"], "EXECUTED_LOCAL_RUNTIME")
        self.assertEqual(
            self.report["evaluation"]["external_real_boundary"],
            "NOT_RUN",
        )
        self.assertEqual(
            self.report["production_readiness"],
            "MORE_EVIDENCE_NEEDED",
        )

    def test_execution_seal_cross_links_lineage_and_evaluation(self) -> None:
        manifest = cast(dict[str, Any], self.report["execution_manifest"])
        evaluation = cast(dict[str, Any], self.report["evaluation"])
        lineage = cast(dict[str, dict[str, Any]], self.report["lineage"])
        currentness = cast(
            list[dict[str, Any]],
            self.report["release_currentness_history"],
        )

        self.assertEqual(
            manifest["lineage_digests"],
            tuple(sorted(item["digest"] for item in lineage.values())),
        )
        self.assertEqual(
            manifest["evaluation_decision_digest"],
            evaluation["decision_digest"],
        )
        self.assertEqual(len(manifest["request_binding_digests"]), 7)
        self.assertEqual(len(set(manifest["request_binding_digests"])), 7)
        self.assertEqual(len(manifest["retrieval_context_receipt_digests"]), 5)
        self.assertEqual(
            manifest["release_currentness_snapshot_digests"],
            tuple(sorted(item["digest"] for item in currentness)),
        )
        self.assertEqual(
            evaluation["hard_gates"]["tenant_acl_provenance_exact_reason_codes"],
            "PASS",
        )


if __name__ == "__main__":
    unittest.main()
