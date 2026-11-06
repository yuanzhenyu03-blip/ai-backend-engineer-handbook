from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import unittest

from examples.day102_grounding_citations import (
    QUERY,
    build_day102_fixture,
    classroom_grounding_contract,
)
from rag_chunking_contracts import stable_hash
from rag_grounding_contracts import (
    GroundingRequest,
    RequestItem,
    SourceWindow,
)


class Day102GroundingContractTests(unittest.TestCase):
    def test_contract_requires_immutable_generator_revision(self) -> None:
        contract = classroom_grounding_contract()
        with self.assertRaises(ValueError):
            replace(contract, immutable_generator_revision="latest")

    def test_contract_rejects_non_positive_budget(self) -> None:
        contract = classroom_grounding_contract()
        with self.assertRaises(ValueError):
            replace(contract, max_claims=0)

    def test_contract_rejects_impossible_total_window_budget(self) -> None:
        contract = classroom_grounding_contract()
        with self.assertRaises(ValueError):
            replace(
                contract,
                max_chars_per_window=256,
                max_total_source_chars=128,
            )

    def test_request_requires_request_items_for_coverage(self) -> None:
        fixture = build_day102_fixture()
        request = fixture.request
        with self.assertRaises(ValueError):
            GroundingRequest(
                request.operation_id,
                request.request_id,
                request.tenant_id,
                request.principal_subject,
                request.action,
                request.purpose,
                QUERY,
                (),
                request.day101_response,
                request.day101_handoff_digest,
            )

    def test_request_item_ids_must_be_unique(self) -> None:
        fixture = build_day102_fixture()
        request = fixture.request
        duplicate = RequestItem("same", "one", "first")
        with self.assertRaises(ValueError):
            replace(request, request_items=(duplicate, duplicate))

    def test_source_window_binds_text_digest(self) -> None:
        fixture = build_day102_fixture()
        identity = fixture.records[0].identity
        with self.assertRaises(ValueError):
            SourceWindow(
                "window:A",
                identity,
                "policy-a:A-12",
                "policy-a:A-12",
                1,
                "complete-window-v1",
                stable_hash("different text"),
                "actual text",
            )

    def test_day101_handoff_digest_is_present_and_stable(self) -> None:
        fixture = build_day102_fixture()
        digest = fixture.day101_response.handoff_digest
        self.assertIsNotNone(digest)
        self.assertEqual(digest, fixture.day101_response.handoff_digest)

    def test_contracts_are_immutable(self) -> None:
        fixture = build_day102_fixture()
        with self.assertRaises(FrozenInstanceError):
            fixture.request.request_id = "mutated"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
