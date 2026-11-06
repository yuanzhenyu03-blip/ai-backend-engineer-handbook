"""Executable Day102 grounding, citation and source-verification fixture."""

from __future__ import annotations

from dataclasses import dataclass
import json

from examples.day100_hybrid_retrieval_filtering import (
    classroom_authorization_revisions,
)
from rag_authorized_retriever import InMemoryRetrievalAuthorization
from rag_chunking_contracts import stable_hash
from rag_grounding_adapters import (
    AdapterMode,
    ClaimTemplate,
    DeterministicAnswerProvider,
    DeterministicClaimExtractor,
    DeterministicEvidenceVerifier,
)
from rag_grounding_contracts import (
    GeneratorEgressPolicy,
    GroundingContract,
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
from rag_query_rewrite_contracts import RewriteMode, protected_query_digest
from rag_reranker_contracts import (
    Day101Outcome,
    Day101Response,
    FinalRerankedHit,
    RerankingMode,
)
from rag_retrieval_contracts import (
    CandidateIdentity,
    RetrievalAuthorizationScope,
    RetrievalRecord,
)


QUERY = "What is the refund window and where must a request be submitted?"
QUERY_DIGEST_SECRET = b"day102-classroom-query-digest-secret"
TENANT_ID = "tenant-day102"
PRINCIPAL = "principal-day102"
ACTION = "rag:answer"
PURPOSE = "customer-support"

CLAIM_WINDOW = "Unopened items may be refunded within 14 days of purchase."
CLAIM_CHANNEL = (
    "Refund requests must be submitted through online customer service."
)
CLAIM_OLD_WINDOW = "Items may be refunded within 30 days of purchase."


def classroom_grounding_contract() -> GroundingContract:
    return GroundingContract(
        contract_version="day102-grounding-v1",
        generator_provider="classroom-deterministic-generator",
        immutable_generator_revision="fake-generator-sha256-001",
        generator_prompt_revision="source-as-data-prompt-v1",
        claim_extractor_revision="deterministic-claim-extractor-v1",
        verifier_provider="classroom-deterministic-verifier",
        verifier_revision="fake-verifier-sha256-001",
        verification_policy_version="claim-evidence-policy-v1",
        source_window_policy_version="complete-chunk-window-v1",
        max_source_windows=3,
        max_chars_per_window=256,
        max_total_source_chars=768,
        max_claims=6,
        protected_data_policy="CLASSROOM_SYNTHETIC_ONLY",
        egress_policy_version="day102-generator-egress-v1",
    )


def _identity(name: str, text: str, version: str) -> CandidateIdentity:
    return CandidateIdentity(
        tenant_id=TENANT_ID,
        document_id="document:" + name,
        document_version_id="document:" + name + ":" + version,
        chunk_set_id="chunk-set:day102:v1",
        chunk_id="chunk:" + name.lower(),
        occurrence_id="occurrence:" + name,
        provenance_fingerprint=stable_hash((name, version, "provenance")),
        content_hash=stable_hash(text),
    )


def classroom_records() -> tuple[RetrievalRecord, ...]:
    definitions = (
        ("A", CLAIM_WINDOW, "2026-v1", "policy-a:A-12"),
        ("C", CLAIM_CHANNEL, "manual-v3", "manual-c:C-21"),
        ("B", CLAIM_OLD_WINDOW, "2024-v1", "policy-b:B-07"),
    )
    return tuple(RetrievalRecord(
        identity=_identity(name, text, version),
        text=text,
        metadata=tuple(sorted({
            "tenant_id": TENANT_ID,
            "category": "refund-policy",
            "status": "active",
            "source_reference": source_reference,
        }.items())),
        embedding=(1.0, 0.0),
    ) for name, text, version, source_reference in definitions)


def classroom_scope(
    records: tuple[RetrievalRecord, ...]
) -> RetrievalAuthorizationScope:
    return RetrievalAuthorizationScope(
        tenant_id=TENANT_ID,
        principal_subject=PRINCIPAL,
        action=ACTION,
        purpose=PURPOSE,
        revisions=classroom_authorization_revisions(),
        allowed_occurrence_ids=tuple(
            record.identity.occurrence_id for record in records
        ),
        decision_id="decision-day102-v1",
    )


def classroom_day101_response(
    *,
    records: tuple[RetrievalRecord, ...],
    scope: RetrievalAuthorizationScope,
    outcome: Day101Outcome = Day101Outcome.FULL,
) -> Day101Response:
    source_by_id = {
        "occurrence:A": "policy-a:A-12",
        "occurrence:C": "manual-c:C-21",
        "occurrence:B": "policy-b:B-07",
    }
    hits = tuple(FinalRerankedHit(
        rank=index,
        identity=record.identity,
        source_reference=source_by_id[record.identity.occurrence_id],
        reranker_score=(0.95, 0.91, 0.64)[index - 1],
        prior_fusion_rank=index,
        text=record.text,
    ) for index, record in enumerate(records, start=1))
    degraded = outcome is Day101Outcome.DEGRADED
    return Day101Response(
        outcome=outcome,
        safe_reason=(
            "RERANKER_FAILED" if degraded
            else "FULL_REWRITTEN_RERANKED_SUCCESS"
        ),
        rewrite_mode=RewriteMode.FULL_REWRITE.value,
        reranking_mode=(
            RerankingMode.UNRERANKED_FALLBACK
            if degraded else RerankingMode.RERANKED_SUCCESS
        ),
        hits=hits,
        rewrite_set_fingerprint=stable_hash("day102-rewrite-set"),
        candidate_pool_digest=stable_hash(tuple(
            record.identity.occurrence_id for record in records
        )),
        validated_rerank_digest=(
            None if degraded else stable_hash("day102-validated-rerank")
        ),
        original_query_digest=protected_query_digest(
            QUERY_DIGEST_SECRET, TENANT_ID, QUERY
        ),
        authorization_scope_fingerprint=scope.fingerprint,
    )


def default_claim_templates() -> tuple[ClaimTemplate, ...]:
    return (
        ClaimTemplate(
            "claim:refund-window",
            "request-item:refund-window",
            CLAIM_WINDOW,
            ("occurrence:A",),
        ),
        ClaimTemplate(
            "claim:submission-channel",
            "request-item:submission-channel",
            CLAIM_CHANNEL,
            ("occurrence:C",),
        ),
    )


@dataclass
class Day102Fixture:
    records: tuple[RetrievalRecord, ...]
    scope: RetrievalAuthorizationScope
    authorization: InMemoryRetrievalAuthorization
    day101_response: Day101Response
    currentness: GroundingCurrentnessOracle
    generator: DeterministicAnswerProvider
    fallback_generator: DeterministicAnswerProvider | None
    extractor: DeterministicClaimExtractor
    verifier: DeterministicEvidenceVerifier
    fallback_verifier: DeterministicEvidenceVerifier | None
    audit: ContentSafeGroundingAuditSink
    pipeline: AuthorizedGroundingOrchestrator
    request: GroundingRequest


def build_day102_fixture(
    *,
    day101_outcome: Day101Outcome = Day101Outcome.FULL,
    allow_degraded_handoff: bool = True,
    selected_occurrence_ids: tuple[str, ...] = (
        "occurrence:A", "occurrence:C"
    ),
    answer_text: str = CLAIM_WINDOW + " " + CLAIM_CHANNEL,
    claim_templates: tuple[ClaimTemplate, ...] | None = None,
    relations_by_claim_id: dict[str, SemanticRelation] | None = None,
    generator_mode: AdapterMode = AdapterMode.NORMAL,
    verifier_mode: AdapterMode = AdapterMode.NORMAL,
    use_generator_fallback: bool = False,
    use_verifier_fallback: bool = False,
    allow_generator_egress: bool = True,
    allow_verifier_egress: bool = True,
) -> Day102Fixture:
    records = classroom_records()
    scope = classroom_scope(records)
    authorization = InMemoryRetrievalAuthorization()
    authorization.put(scope)
    day101_response = classroom_day101_response(
        records=records,
        scope=scope,
        outcome=day101_outcome,
    )
    contract = classroom_grounding_contract()
    currentness = GroundingCurrentnessOracle(
        authorization=authorization,
        records=records,
    )
    generator = DeterministicAnswerProvider(
        answer_text=answer_text,
        mode=generator_mode,
    )
    fallback_generator = (
        DeterministicAnswerProvider(answer_text=answer_text)
        if use_generator_fallback else None
    )
    extractor = DeterministicClaimExtractor(
        revision=contract.claim_extractor_revision,
        templates=(
            claim_templates
            if claim_templates is not None else default_claim_templates()
        ),
    )
    relations = relations_by_claim_id or {
        "claim:refund-window": SemanticRelation.SUPPORTED,
        "claim:submission-channel": SemanticRelation.SUPPORTED,
    }
    verifier = DeterministicEvidenceVerifier(
        revision=contract.verifier_revision,
        relations_by_claim_id=relations,
        mode=verifier_mode,
    )
    fallback_verifier = (
        DeterministicEvidenceVerifier(
            revision="fake-fallback-verifier-sha256-001",
            relations_by_claim_id=relations,
        )
        if use_verifier_fallback else None
    )
    audit = ContentSafeGroundingAuditSink()
    pipeline = AuthorizedGroundingOrchestrator(
        contract=contract,
        degradation=GroundingDegradationPolicy(
            policy_version="day102-degradation-v1",
            allow_degraded_day101_handoff=allow_degraded_handoff,
            allow_generator_fallback_on_failure=True,
            allow_generator_fallback_on_timeout=True,
            allow_verifier_fallback_on_failure=True,
            allow_verifier_fallback_on_timeout=True,
        ),
        generator_egress=GeneratorEgressPolicy(
            policy_version=contract.egress_policy_version,
            allowed_providers=frozenset({contract.generator_provider}),
            allow_protected_query_egress=allow_generator_egress,
            allow_protected_source_egress=allow_generator_egress,
        ),
        verifier_egress=VerifierEgressPolicy(
            policy_version="day102-verifier-egress-v1",
            allowed_providers=frozenset({contract.verifier_provider}),
            allow_protected_claim_egress=allow_verifier_egress,
            allow_protected_source_egress=allow_verifier_egress,
        ),
        currentness=currentness,
        planner=GroundingContextPlanner(
            contract=contract,
            selector=DeterministicContextSelector(selected_occurrence_ids),
        ),
        generator=generator,
        fallback_generator=fallback_generator,
        extractor=extractor,
        verifier=verifier,
        fallback_verifier=fallback_verifier,
        validator=GroundingValidator(),
        audit=audit,
        query_digest_secret=QUERY_DIGEST_SECRET,
    )
    request = GroundingRequest(
        operation_id="operation-day102-v1",
        request_id="request-day102-v1",
        tenant_id=TENANT_ID,
        principal_subject=PRINCIPAL,
        action=ACTION,
        purpose=PURPOSE,
        original_query=QUERY,
        request_items=(
            RequestItem(
                "request-item:refund-window",
                "the refund window",
                "What is the refund window?",
            ),
            RequestItem(
                "request-item:submission-channel",
                "the submission channel",
                "Where must a refund request be submitted?",
            ),
        ),
        day101_response=day101_response,
        day101_handoff_digest=day101_response.handoff_digest or "NO_HANDOFF",
    )
    return Day102Fixture(
        records,
        scope,
        authorization,
        day101_response,
        currentness,
        generator,
        fallback_generator,
        extractor,
        verifier,
        fallback_verifier,
        audit,
        pipeline,
        request,
    )


def run_example() -> dict[str, object]:
    invalid = build_day102_fixture()
    invalid.request = GroundingRequest(
        operation_id=invalid.request.operation_id,
        request_id=invalid.request.request_id,
        tenant_id=invalid.request.tenant_id,
        principal_subject=invalid.request.principal_subject,
        action=invalid.request.action,
        purpose=invalid.request.purpose,
        original_query=invalid.request.original_query,
        request_items=invalid.request.request_items,
        day101_response=invalid.request.day101_response,
        day101_handoff_digest="sha256:tampered-handoff",
    )
    invalid_result = invalid.pipeline.execute(invalid.request)

    fixture = build_day102_fixture()
    result = fixture.pipeline.execute(fixture.request)
    return {
        "experiment_kind": "PIPELINE_CORRECTNESS_EXPERIMENT",
        "invalid_handoff_outcome": invalid_result.outcome.value,
        "invalid_handoff_reason": invalid_result.safe_reason,
        "invalid_handoff_generator_calls": invalid_result.generator_calls,
        "synthetic_outcome": result.outcome.value,
        "synthetic_released_claim_ids": tuple(
            item.claim_id for item in result.released_claims
        ),
        "synthetic_citation_targets": tuple(
            citation.exact_span
            for item in result.released_claims
            for citation in item.citations
        ),
        "synthetic_bundle_digest": result.bundle_digest,
        "synthetic_raw_query_logged": fixture.audit.events()[-1].raw_query_logged,
        "synthetic_protected_source_logged": (
            fixture.audit.events()[-1].protected_source_text_logged
        ),
        "real_generator": "NOT_RUN",
        "real_claim_extractor": "NOT_RUN",
        "real_nli_verifier": "NOT_RUN",
        "real_protected_data_egress": "NOT_RUN",
        "real_latency_capacity_quality": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2, sort_keys=True))
