from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day101_query_rewriting_reranking import (
    build_day101_fixture,
    classroom_reranker_contract,
)
from rag_reranker_adapter import (
    DeterministicRerankerAdapter,
    RerankerInputBuilder,
    RerankerProviderError,
    RerankerProviderMode,
)
from day101_test_support import build_intermediate


class Day101RerankerAdapterTests(unittest.TestCase):
    def test_deterministic_adapter_uses_explicit_input_indexes(self) -> None:
        fixture = build_day101_fixture()
        *_, request = build_intermediate(fixture)
        response = fixture.reranker.rank(request)
        mapped = tuple(request.items[item.input_index].candidate_id for item in response.results)
        self.assertEqual(mapped[0], "occurrence:B")
        self.assertEqual(len(mapped), len(set(mapped)))

    def test_window_policy_change_changes_input_identity(self) -> None:
        fixture = build_day101_fixture()
        *_, pool, first = build_intermediate(fixture)
        changed_contract = replace(
            classroom_reranker_contract(),
            input_window_policy_version="day101-head-window-v2",
            input_window_strategy="HEAD",
        )
        second = RerankerInputBuilder(changed_contract).build(
            original_query_digest=first.original_query_digest,
            protected_query=first.protected_query,
            pool=pool,
        )
        self.assertNotEqual(first.input_windows_digest, second.input_windows_digest)
        self.assertNotEqual(first.attempt_id, second.attempt_id)

    def test_protected_windows_are_hidden_from_repr(self) -> None:
        fixture = build_day101_fixture()
        *_, request = build_intermediate(fixture)
        self.assertNotIn(request.items[0].protected_input_window, repr(request.items[0]))

    def test_provider_failure_is_not_silently_converted_by_adapter(self) -> None:
        fixture = build_day101_fixture()
        *_, request = build_intermediate(fixture)
        adapter = DeterministicRerankerAdapter(
            contract=classroom_reranker_contract(),
            scores_by_candidate_id={},
            mode=RerankerProviderMode.FAILED,
        )
        with self.assertRaises(RerankerProviderError):
            adapter.rank(request)
        self.assertEqual(adapter.calls, 1)


if __name__ == "__main__":
    unittest.main()
