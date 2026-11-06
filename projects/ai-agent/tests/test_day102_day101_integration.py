from __future__ import annotations

import unittest

from examples.day101_query_rewriting_reranking import (
    QUERY_DIGEST_SECRET,
    build_day101_fixture,
    day101_request,
)
from examples.day102_grounding_citations import classroom_grounding_contract
from rag_grounding_adapters import (
    ClaimTemplate,
    DeterministicAnswerProvider,
    DeterministicClaimExtractor,
    DeterministicEvidenceVerifier,
)
from rag_grounding_contracts import (
    Day102Outcome,
    GeneratorEgressPolicy,
    GroundingDegradationPolicy,
    GroundingRequest,
    RequestItem,
    SemanticRelation,
    VerifierEgressPolicy,
)
from rag_grounding_orchestrator import (
    AuthorizedGroundingOrchestrator,
    ContentSafeGroundingAuditSink,
)
from rag_grounding_planner import (
    DeterministicContextSelector,
    GroundingContextPlanner,
    GroundingCurrentnessOracle,
)
from rag_grounding_validator import GroundingValidator


class Day102Day101IntegrationTests(unittest.TestCase):
    def test_real_day101_response_exposes_eligible_handoff_identity(self) -> None:
        fixture = build_day101_fixture()
        response = fixture.pipeline.execute(day101_request(fixture))
        self.assertIsNotNone(response.original_query_digest)
        self.assertIsNotNone(response.authorization_scope_fingerprint)
        self.assertIsNotNone(response.handoff_digest)

    def test_day102_consumes_day101_orchestrator_output_not_adapter_output(self) -> None:
        day101 = build_day101_fixture()
        retrieval_request = day101_request(day101)
        response = day101.pipeline.execute(retrieval_request)
        top = response.hits[0]
        contract = classroom_grounding_contract()
        generator = DeterministicAnswerProvider(answer_text=top.text)
        extractor = DeterministicClaimExtractor(
            revision=contract.claim_extractor_revision,
            templates=(ClaimTemplate(
                "claim:top-hit",
                "request-item:top-hit",
                top.text,
                (top.identity.occurrence_id,),
            ),),
        )
        verifier = DeterministicEvidenceVerifier(
            revision=contract.verifier_revision,
            relations_by_claim_id={
                "claim:top-hit": SemanticRelation.SUPPORTED
            },
        )
        pipeline = AuthorizedGroundingOrchestrator(
            contract=contract,
            degradation=GroundingDegradationPolicy(
                "day102-integration-degradation-v1",
                True,
                False,
                False,
                False,
                False,
            ),
            generator_egress=GeneratorEgressPolicy(
                contract.egress_policy_version,
                frozenset({contract.generator_provider}),
                True,
                True,
            ),
            verifier_egress=VerifierEgressPolicy(
                "day102-integration-verifier-egress-v1",
                frozenset({contract.verifier_provider}),
                True,
                True,
            ),
            currentness=GroundingCurrentnessOracle(
                authorization=day101.day100.authorization,
                records=day101.day100.records,
            ),
            planner=GroundingContextPlanner(
                contract=contract,
                selector=DeterministicContextSelector((
                    top.identity.occurrence_id,
                )),
            ),
            generator=generator,
            fallback_generator=None,
            extractor=extractor,
            verifier=verifier,
            fallback_verifier=None,
            validator=GroundingValidator(),
            audit=ContentSafeGroundingAuditSink(),
            query_digest_secret=QUERY_DIGEST_SECRET,
        )
        request = GroundingRequest(
            operation_id="operation-day102-day101-integration",
            request_id="request-day102-day101-integration",
            tenant_id=retrieval_request.tenant_id,
            principal_subject=retrieval_request.principal_subject,
            action=retrieval_request.action,
            purpose=retrieval_request.purpose,
            original_query=retrieval_request.query_text,
            request_items=(RequestItem(
                "request-item:top-hit",
                "the top-hit statement",
                "Return the top-hit statement.",
            ),),
            day101_response=response,
            day101_handoff_digest=response.handoff_digest or "MISSING",
        )
        result = pipeline.execute(request)
        self.assertEqual(result.outcome, Day102Outcome.FULL)
        self.assertEqual(
            tuple(item.claim_id for item in result.released_claims),
            ("claim:top-hit",),
        )


if __name__ == "__main__":
    unittest.main()
