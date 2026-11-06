from __future__ import annotations

import unittest

from examples.day102_grounding_citations import build_day102_fixture
from rag_grounding_adapters import AdapterMode
from rag_grounding_contracts import (
    Day102Outcome,
    GeneratedAnswer,
    GeneratorMode,
    VerificationMode,
)


class Day102FailureFallbackTests(unittest.TestCase):
    def test_generator_egress_denied_makes_zero_provider_calls(self) -> None:
        fixture = build_day102_fixture(allow_generator_egress=False)
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.REJECTED)
        self.assertEqual(result.safe_reason, "GENERATOR_EGRESS_DENIED")
        self.assertEqual(result.generator_calls, 0)
        self.assertEqual(result.verifier_calls, 0)

    def test_verifier_egress_denied_stops_before_generator(self) -> None:
        fixture = build_day102_fixture(allow_verifier_egress=False)
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.REJECTED)
        self.assertEqual(result.safe_reason, "VERIFIER_EGRESS_DENIED")
        self.assertEqual(result.generator_calls, 0)
        self.assertEqual(result.verifier_calls, 0)

    def test_generator_timeout_without_fallback_is_unavailable(self) -> None:
        fixture = build_day102_fixture(generator_mode=AdapterMode.TIMEOUT)
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.UNAVAILABLE)
        self.assertEqual(result.safe_reason, "GENERATOR_TIMEOUT")
        self.assertEqual(result.generator_calls, 1)
        self.assertEqual(result.verifier_calls, 0)

    def test_generator_timeout_uses_explicit_fallback(self) -> None:
        fixture = build_day102_fixture(
            generator_mode=AdapterMode.TIMEOUT,
            use_generator_fallback=True,
        )
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.DEGRADED)
        self.assertIs(result.generator_mode, GeneratorMode.FALLBACK)
        self.assertEqual(result.generator_calls, 2)

    def test_verifier_timeout_without_fallback_is_unavailable(self) -> None:
        fixture = build_day102_fixture(verifier_mode=AdapterMode.TIMEOUT)
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.UNAVAILABLE)
        self.assertEqual(result.safe_reason, "VERIFIER_TIMEOUT")
        self.assertEqual(result.verifier_calls, 1)

    def test_verifier_timeout_uses_explicit_fallback(self) -> None:
        fixture = build_day102_fixture(
            verifier_mode=AdapterMode.TIMEOUT,
            use_verifier_fallback=True,
        )
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.DEGRADED)
        self.assertIs(result.verification_mode, VerificationMode.FALLBACK)
        self.assertEqual(result.verifier_calls, 2)

    def test_generator_identity_mismatch_rejects_output(self) -> None:
        fixture = build_day102_fixture()
        fixture.generator.response_override = GeneratedAnswer(
            attempt_id="wrong-attempt",
            bundle_digest="sha256:wrong-bundle",
            generator_contract_fingerprint=(
                fixture.pipeline.contract.fingerprint
            ),
            answer_text="wrong",
        )
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.REJECTED)
        self.assertEqual(result.safe_reason, "GENERATOR_OUTPUT_INVALID")

    def test_missing_verifier_result_rejects_entire_verifier_output(self) -> None:
        fixture = build_day102_fixture()
        fixture.verifier.response_override = ()
        result = fixture.pipeline.execute(fixture.request)
        self.assertEqual(result.outcome, Day102Outcome.REJECTED)
        self.assertEqual(result.safe_reason, "VERIFIER_OUTPUT_INVALID")

    def test_audit_never_logs_protected_content(self) -> None:
        fixture = build_day102_fixture()
        fixture.pipeline.execute(fixture.request)
        event = fixture.audit.events()[-1]
        self.assertFalse(event.raw_query_logged)
        self.assertFalse(event.protected_source_text_logged)
        self.assertFalse(event.protected_answer_logged)


if __name__ == "__main__":
    unittest.main()
