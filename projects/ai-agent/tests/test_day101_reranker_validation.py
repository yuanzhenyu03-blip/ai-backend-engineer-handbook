from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day101_query_rewriting_reranking import build_day101_fixture
from rag_reranker_contracts import RawRerankerItem, RawRerankerResponse
from rag_reranking_validator import RerankingValidationError, RerankingValidator
from day101_test_support import build_intermediate


class Day101RerankerValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = build_day101_fixture()
        *_, self.request = build_intermediate(self.fixture)
        self.validator = RerankingValidator()
        self.contract = self.fixture.pipeline.reranker_contract

    def _response(self, results):
        return RawRerankerResponse(
            self.request.attempt_id,
            self.request.candidate_pool_digest,
            self.request.reranker_contract_fingerprint,
            tuple(results),
        )

    def test_valid_response_maps_indexes_then_sorts_by_score(self) -> None:
        results = tuple(
            RawRerankerItem(index, float(index))
            for index in range(len(self.request.items))
        )
        report = self.validator.validate(
            request=self.request,
            response=self._response(tuple(reversed(results))),
            contract=self.contract,
        )
        expected = self.request.items[-1].candidate_id
        self.assertEqual(report.result.items[0].candidate_id, expected)

    def test_duplicate_index_rejects_entire_response(self) -> None:
        count = len(self.request.items)
        results = [RawRerankerItem(index, 1.0) for index in range(count)]
        results[-1] = RawRerankerItem(0, 0.5)
        with self.assertRaisesRegex(
            RerankingValidationError, "RERANKER_DUPLICATE_CANDIDATE"
        ):
            self.validator.validate(
                request=self.request,
                response=self._response(results),
                contract=self.contract,
            )

    def test_unknown_index_rejects_entire_response(self) -> None:
        count = len(self.request.items)
        results = [RawRerankerItem(index, 1.0) for index in range(count)]
        results[-1] = RawRerankerItem(count, 0.5)
        with self.assertRaisesRegex(
            RerankingValidationError, "RERANKER_UNKNOWN_CANDIDATE"
        ):
            self.validator.validate(
                request=self.request,
                response=self._response(results),
                contract=self.contract,
            )

    def test_missing_full_permutation_is_rejected(self) -> None:
        results = tuple(
            RawRerankerItem(index, 1.0)
            for index in range(len(self.request.items) - 1)
        )
        with self.assertRaisesRegex(
            RerankingValidationError, "RERANKER_OUTPUT_INCOMPLETE"
        ):
            self.validator.validate(
                request=self.request,
                response=self._response(results),
                contract=self.contract,
            )

    def test_attempt_mismatch_is_rejected(self) -> None:
        response = self.fixture.reranker.rank(self.request)
        with self.assertRaisesRegex(
            RerankingValidationError, "RERANK_ATTEMPT_MISMATCH"
        ):
            self.validator.validate(
                request=self.request,
                response=replace(response, attempt_id="wrong"),
                contract=self.contract,
            )


if __name__ == "__main__":
    unittest.main()
