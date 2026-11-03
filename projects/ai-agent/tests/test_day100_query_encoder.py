from __future__ import annotations

import math
import unittest

from examples.day100_hybrid_retrieval_filtering import (
    build_day100_fixture,
)
from rag_query_encoder import (
    FakeQueryEncoderMode,
    QueryEncodingError,
    QuerySensitivity,
    classify_query_sensitivity,
)


class Day100QueryEncoderTests(unittest.TestCase):
    def test_document_and_query_roles_and_prefixes_are_distinct(self) -> None:
        contract = build_day100_fixture().bundle.query_encoder
        self.assertNotEqual(contract.document_input_role, contract.query_input_role)
        self.assertNotEqual(contract.document_prefix, contract.query_prefix)

    def test_normal_query_is_unit_normalized_and_dimensioned(self) -> None:
        fixture = build_day100_fixture()
        encoded = fixture.encoder.encode(
            query_text="refund policy",
            expected_contract_fingerprint=fixture.bundle.query_encoder.fingerprint,
        )
        self.assertEqual(len(encoded.vector), 4)
        self.assertTrue(math.isclose(
            math.sqrt(sum(value * value for value in encoded.vector)),
            1.0,
            rel_tol=1e-6,
        ))
        self.assertEqual(fixture.encoder.calls, 1)

    def test_pii_egress_denial_happens_before_provider_call(self) -> None:
        fixture = build_day100_fixture()
        with self.assertRaises(QueryEncodingError) as caught:
            fixture.encoder.encode(
                query_text="find alice@example.com refund",
                expected_contract_fingerprint=fixture.bundle.query_encoder.fingerprint,
            )
        self.assertEqual(caught.exception.reason, "QUERY_EGRESS_SENSITIVITY_DENIED")
        self.assertFalse(caught.exception.provider_called)
        self.assertEqual(fixture.encoder.calls, 0)

    def test_secret_classifier_precedes_pii(self) -> None:
        self.assertEqual(
            classify_query_sensitivity("alice@example.com sk-demo12345"),
            QuerySensitivity.SUSPECTED_SECRET,
        )

    def test_wrong_dimensions_are_a_contract_violation(self) -> None:
        fixture = build_day100_fixture(
            encoder_mode=FakeQueryEncoderMode.WRONG_DIMENSIONS
        )
        with self.assertRaises(QueryEncodingError) as caught:
            fixture.encoder.encode(
                query_text="refund policy",
                expected_contract_fingerprint=fixture.bundle.query_encoder.fingerprint,
            )
        self.assertEqual(caught.exception.reason, "QUERY_ENCODER_DIMENSIONS_MISMATCH")
        self.assertTrue(caught.exception.provider_called)

    def test_timeout_is_classified_after_provider_call(self) -> None:
        fixture = build_day100_fixture(encoder_mode=FakeQueryEncoderMode.TIMEOUT)
        with self.assertRaises(QueryEncodingError) as caught:
            fixture.encoder.encode(
                query_text="refund policy",
                expected_contract_fingerprint=fixture.bundle.query_encoder.fingerprint,
            )
        self.assertEqual(caught.exception.reason, "QUERY_ENCODER_TIMEOUT")
        self.assertTrue(caught.exception.provider_called)

    def test_non_finite_vector_is_rejected(self) -> None:
        fixture = build_day100_fixture(encoder_mode=FakeQueryEncoderMode.NON_FINITE)
        with self.assertRaises(QueryEncodingError) as caught:
            fixture.encoder.encode(
                query_text="refund policy",
                expected_contract_fingerprint=fixture.bundle.query_encoder.fingerprint,
            )
        self.assertEqual(caught.exception.reason, "QUERY_ENCODER_NON_FINITE_VECTOR")

    def test_contract_mismatch_does_not_call_provider(self) -> None:
        fixture = build_day100_fixture()
        with self.assertRaises(QueryEncodingError) as caught:
            fixture.encoder.encode(
                query_text="refund policy",
                expected_contract_fingerprint="sha256:wrong",
            )
        self.assertFalse(caught.exception.provider_called)
        self.assertEqual(fixture.encoder.calls, 0)


if __name__ == "__main__":
    unittest.main()
