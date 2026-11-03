from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day100_hybrid_retrieval_filtering import (
    build_day100_fixture,
    load_real_day99_handoff,
    retrieval_request,
)
from rag_retrieval_contracts import RetrievalOutcome


class Day100RetrievalEligibilityTests(unittest.TestCase):
    def test_real_day99_handoff_is_sealed_but_not_selected(self) -> None:
        handoff = load_real_day99_handoff()
        self.assertEqual(handoff["generation_state"], "SEALED")
        self.assertFalse(handoff["selected_bundle"])
        self.assertEqual(handoff["ann_recall"], "NOT_RUN")
        self.assertEqual(handoff["real_provider"], "NOT_RUN")

    def test_missing_selected_bundle_fails_before_all_calls(self) -> None:
        fixture = build_day100_fixture(select_bundle=False)
        result = fixture.retriever.retrieve(retrieval_request(fixture))
        self.assertEqual(result.outcome, RetrievalOutcome.REJECTED)
        self.assertEqual(result.safe_reason, "NO_CURRENT_SELECTED_RETRIEVAL_BUNDLE")
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(result.database_calls, 0)

    def test_client_generation_override_is_forbidden_before_calls(self) -> None:
        fixture = build_day100_fixture()
        result = fixture.retriever.retrieve(retrieval_request(
            fixture,
            client_generation_id="synthetic-vector-generation-g2",
        ))
        self.assertEqual(result.safe_reason, "CLIENT_GENERATION_OVERRIDE_FORBIDDEN")
        self.assertEqual((result.provider_calls, result.database_calls), (0, 0))
        event = fixture.audit.events()[-1]
        self.assertEqual(event.selected_generation_id, fixture.bundle.generation_id)
        self.assertEqual(event.client_generation_hint, "synthetic-vector-generation-g2")
        self.assertFalse(event.client_generation_authoritative)

    def test_query_encoder_contract_mismatch_fails_before_calls(self) -> None:
        fixture = build_day100_fixture()
        request = replace(
            retrieval_request(fixture),
            query_encoder_contract_fingerprint="sha256:wrong",
        )
        result = fixture.retriever.retrieve(request)
        self.assertEqual(result.safe_reason, "QUERY_ENCODER_CONTRACT_MISMATCH")
        self.assertEqual((result.provider_calls, result.database_calls), (0, 0))

    def test_synthetic_bundle_cannot_run_outside_classroom_mode(self) -> None:
        fixture = build_day100_fixture(classroom_mode=False)
        result = fixture.retriever.retrieve(retrieval_request(fixture))
        self.assertEqual(
            result.safe_reason,
            "SYNTHETIC_BUNDLE_FORBIDDEN_OUTSIDE_CLASSROOM",
        )
        self.assertEqual((result.provider_calls, result.database_calls), (0, 0))

    def test_top_k_policy_is_checked_before_provider_calls(self) -> None:
        fixture = build_day100_fixture()
        result = fixture.retriever.retrieve(retrieval_request(fixture, top_k=6))
        self.assertEqual(result.safe_reason, "REQUESTED_TOP_K_EXCEEDS_POLICY")
        self.assertEqual((result.provider_calls, result.database_calls), (0, 0))

    def test_lexical_and_dense_sources_must_share_current_chunk_set(self) -> None:
        fixture = build_day100_fixture()
        with self.assertRaises(ValueError):
            replace(
                fixture.bundle,
                chunk_set_id="different-chunk-set",
            )


if __name__ == "__main__":
    unittest.main()
