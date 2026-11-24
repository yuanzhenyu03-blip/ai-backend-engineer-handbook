"""Canonical Day106 Day100 -> Day101 -> Day102 deterministic support.

This module intentionally lives under ``examples``.  It composes the public
Day100, Day101, and Day102 seams with one identity vocabulary so the Day106
example does not confuse independently passing classroom fixtures with an
end-to-end execution.  Production modules must not import this file.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from examples.day100_hybrid_retrieval_filtering import (
    ClassroomClock,
    Day100Fixture,
    classroom_filter_schema,
    classroom_query_contract,
)
from examples.day101_query_rewriting_reranking import (
    QUERY_DIGEST_SECRET,
    Day101Fixture,
    classroom_reranker_contract,
    classroom_rewrite_contract,
    default_rewrite_outputs,
)
from examples.day102_grounding_citations import classroom_grounding_contract
from rag_authorized_retriever import (
    GuardedRetrievalReleaser,
    InMemoryProtectedRetrievalStore,
    InMemoryRetrievalAuthorization,
    classroom_authorization_revisions,
)
from rag_capstone_contracts import Day101ExecutionReceipt
from rag_capstone_orchestrator import Day101ExecutionReceiptAuthority
from rag_chunking_contracts import stable_hash
from rag_dense_retrieval import DenseMode, ExactDenseRetrievalAdapter
from rag_grounding_adapters import (
    AnswerProvider,
    ClaimTemplate,
    DeterministicAnswerProvider,
    DeterministicClaimExtractor,
    DeterministicEvidenceVerifier,
    EvidenceVerifier,
)
from rag_grounding_contracts import (
    Day102Response,
    GeneratorEgressPolicy,
    GroundingDegradationPolicy,
    GroundingContract,
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
from rag_lexical_retrieval import (
    BM25ReferenceIndex,
    LexicalRetrievalAdapter,
)
from rag_multi_query_fusion import MultiQueryFusionPolicy
from rag_multi_query_retrieval import (
    Day100VariantRetrievalExecutor,
    MultiQueryExecutionPolicy,
)
from rag_query_encoder import (
    DeterministicFakeQueryEncoder,
    QueryEgressPolicy,
    QueryEncoderAdapter,
    QuerySensitivity,
)
from rag_query_rewrite_contracts import (
    protected_query_digest,
    QueryRewriteDegradationPolicy,
    RewriteEgressPolicy,
)
from rag_query_rewriter import (
    BoundedQueryRewriter,
    ContentSafeRewriteAuditSink,
    DeterministicRewriteProvider,
    QueryVariantValidator,
)
from rag_reranker_adapter import (
    DeterministicRerankerAdapter,
    RerankerInputBuilder,
)
from rag_reranker_contracts import (
    Day101Response,
    RerankerEgressPolicy,
    RerankingDegradationPolicy,
)
from rag_reranking_orchestrator import (
    AuthorizedRerankingOrchestrator,
    ContentSafeRerankingAuditSink,
    Day100CurrentnessOracle,
    Day101Eligibility,
)
from rag_reranking_validator import RerankingValidator
from rag_retrieval_cache import InMemoryRetrievalCache, RetrievalCursorCodec
from rag_retrieval_contracts import (
    CandidateIdentity,
    FusionPolicy,
    HybridRetrievalPolicy,
    LexicalRetrievalContract,
    RetrievalAuthorizationScope,
    RetrievalRecord,
    RetrievalRequest,
    SelectedRetrievalBundle,
    RETRIEVAL_ACTION,
    RETRIEVAL_PURPOSE,
)
from rag_retrieval_filters import (
    FilterOperator,
    FilterPlanner,
    ProviderFilterCapabilities,
)
from rag_retrieval_orchestrator import (
    AuthorizedHybridRetriever,
    ContentSafeRetrievalAuditSink,
)
from rag_retrieval_validator import (
    InMemoryRetrievalBundleAuthority,
    RetrievalCandidateValidator,
)
from rag_vector_contracts import GenerationState, ProductionReadiness


TENANT_ID = "tenant-refund"
PRINCIPAL_ID = "principal-refund-reader"

DAY101_EXECUTION_RECEIPT_AUTHORITY = Day101ExecutionReceiptAuthority(
    "day106-day101-execution-receipt-authority-v1",
    b"day106-deterministic-local-receipt-authority-secret-v1",
)

REFUND_WINDOW = "The refund window is 14 days for unopened goods."
APPLICATION_CHANNEL = (
    "The refund application channel is online customer service."
)


@dataclass(frozen=True)
class CanonicalClaim:
    """One protected answer claim and its exact occurrence support."""

    claim_id: str
    request_item_id: str
    safe_label: str
    question: str
    answer_text: str
    occurrence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all((
            self.claim_id,
            self.request_item_id,
            self.safe_label,
            self.question,
            self.answer_text,
        )):
            raise ValueError("complete canonical claim bindings are required")
        if not self.occurrence_ids or len(set(self.occurrence_ids)) != len(
            self.occurrence_ids
        ):
            raise ValueError("canonical claim occurrences must be non-empty and unique")


@dataclass(frozen=True)
class CanonicalRetrievalRun:
    """Day101 result before any context assembly or model invocation."""

    retrieval_request: RetrievalRequest
    day101_response: Day101Response
    execution_receipt: Day101ExecutionReceipt | None


@dataclass(frozen=True)
class CanonicalGroundingRun:
    """Day101 and Day102 results from the same request identity."""

    retrieval_request: RetrievalRequest
    day101_response: Day101Response
    day102_response: Day102Response
    grounding_audit_checksum: str


def _unit(values: tuple[float, ...]) -> tuple[float, ...]:
    norm = math.sqrt(sum(value * value for value in values))
    return tuple(value / norm for value in values)


def _lexical_contract(generation_id: str) -> LexicalRetrievalContract:
    return LexicalRetrievalContract(
        contract_version="day106-lexical-v1",
        corpus_generation_id=f"refund-lexical-{generation_id}",
        # The Generation changes; the exact committed ChunkSet lineage does not.
        chunk_set_id="refund-chunk-set-v1",
        analyzer_version="lowercase-word-analyzer-v1",
        tokenizer_version="regex-word-tokenizer-v1",
        language="en",
        k1=1.2,
        b=0.75,
        stop_words=("the", "a", "and"),
    )


def _selected_bundle(
    *,
    generation_id: str,
    pointer_revision: int,
    generation_artifact_fingerprint: str,
) -> SelectedRetrievalBundle:
    schema = classroom_filter_schema()
    query = classroom_query_contract()
    lexical = _lexical_contract(generation_id)
    return SelectedRetrievalBundle(
        bundle_id=f"refund-serving@{generation_id}/r{pointer_revision}",
        revision=pointer_revision,
        tenant_id=TENANT_ID,
        generation_id=generation_id,
        generation_state=GenerationState.ACTIVATED,
        generation_contract_fingerprint=generation_artifact_fingerprint,
        embedding_set_id="refund-embedding-set-v1",
        embedding_contract_fingerprint=query.document_contract_fingerprint,
        chunk_set_id=lexical.chunk_set_id,
        lexical_corpus_generation_id=lexical.corpus_generation_id,
        query_encoder=query,
        lexical=lexical,
        filter_schema_fingerprint=schema.fingerprint,
        retrieval_policy=HybridRetrievalPolicy(
            policy_version="day106-retrieval-policy-v1",
            max_top_k=3,
            max_candidate_depth=3,
            max_refill_rounds=2,
            max_candidate_budget=12,
            deadline_ms=500,
            allow_lexical_only=True,
            allow_dense_only=True,
            allow_split_or=False,
            allow_business_post_filter=False,
        ),
        fusion_policy=FusionPolicy(
            policy_version="day106-rrf-v1",
            rrf_k=60,
            candidate_depth=2,
        ),
        selected=True,
        evidence_level="EXECUTED_LOCAL_RUNTIME",
        # Day100 currently recognizes this explicit value as the only
        # non-production fixture scope.  The surrounding bundle identity and
        # evidence level still distinguish the Day106 execution.
        fixture_scope="DAY100_CLASSROOM_ONLY",
        production_eligible=False,
        production_readiness=ProductionReadiness.MORE_EVIDENCE_NEEDED,
    )


def _records(
    bundle: SelectedRetrievalBundle,
    occurrence_ids: tuple[str, ...],
) -> tuple[RetrievalRecord, ...]:
    definitions = {
        "A@v1": ("A", REFUND_WINDOW, "refund-policy"),
        "C@v1": ("C", APPLICATION_CHANNEL, "refund-instructions"),
    }
    if occurrence_ids != tuple(sorted(occurrence_ids)):
        raise ValueError("Generation occurrences must be sorted")
    if not set(occurrence_ids).issubset(definitions):
        raise ValueError("unsupported canonical occurrence")

    provider = DeterministicFakeQueryEncoder()
    records: list[RetrievalRecord] = []
    for occurrence_id in occurrence_ids:
        source_id, text, category = definitions[occurrence_id]
        embedding = provider.encode(
            contract=bundle.query_encoder,
            protected_query=bundle.query_encoder.document_prefix + text,
        )
        identity = CandidateIdentity(
            tenant_id=TENANT_ID,
            document_id=f"refund-source-{source_id}",
            document_version_id=occurrence_id,
            chunk_set_id=bundle.chunk_set_id,
            chunk_id=occurrence_id,
            occurrence_id=occurrence_id,
            provenance_fingerprint=stable_hash(
                (occurrence_id, "PROV-R1")
            ),
            content_hash=stable_hash(text),
        )
        records.append(RetrievalRecord(
            identity=identity,
            text=text,
            metadata=tuple(sorted({
                "tenant_id": TENANT_ID,
                "category": category,
                "owner_id": PRINCIPAL_ID,
                "status": "active",
            }.items())),
            embedding=_unit(embedding),
        ))
    return tuple(records)


def _build_day100_fixture(
    *,
    generation_id: str,
    pointer_revision: int,
    generation_artifact_fingerprint: str,
    manifest_occurrence_ids: tuple[str, ...],
    authorization_revision: int,
    authorization: InMemoryRetrievalAuthorization | None = None,
    authorization_scope: RetrievalAuthorizationScope | None = None,
) -> Day100Fixture:
    bundle = _selected_bundle(
        generation_id=generation_id,
        pointer_revision=pointer_revision,
        generation_artifact_fingerprint=generation_artifact_fingerprint,
    )
    records = _records(bundle, manifest_occurrence_ids)
    scope = authorization_scope or RetrievalAuthorizationScope(
        tenant_id=TENANT_ID,
        principal_subject=PRINCIPAL_ID,
        action=RETRIEVAL_ACTION,
        purpose=RETRIEVAL_PURPOSE,
        revisions=classroom_authorization_revisions(
            policy_revision=authorization_revision,
            acl_revision=authorization_revision,
            authorization_epoch=authorization_revision,
        ),
        allowed_occurrence_ids=manifest_occurrence_ids,
        decision_id=f"refund-retrieval-{generation_id}-P{authorization_revision}",
    )
    if (
        scope.tenant_id != TENANT_ID
        or scope.principal_subject != PRINCIPAL_ID
        or scope.action != RETRIEVAL_ACTION
        or scope.purpose != RETRIEVAL_PURPOSE
        or scope.allowed_occurrence_ids != manifest_occurrence_ids
    ):
        raise ValueError("authorization scope must match the selected Generation")
    bundles = InMemoryRetrievalBundleAuthority()
    bundles.select(bundle)
    authorization = authorization or InMemoryRetrievalAuthorization()
    authorization.put(scope)
    encoder_provider = DeterministicFakeQueryEncoder()
    encoder = QueryEncoderAdapter(
        contract=bundle.query_encoder,
        provider=encoder_provider,
        egress_policy=QueryEgressPolicy(
            bundle.query_encoder.egress_policy_version,
            frozenset({bundle.query_encoder.provider}),
            frozenset({QuerySensitivity.NORMAL}),
            allow_external=False,
        ),
    )
    lexical = LexicalRetrievalAdapter(
        BM25ReferenceIndex(contract=bundle.lexical, records=records)
    )
    dense = ExactDenseRetrievalAdapter(records, mode=DenseMode.NORMAL)
    audit = ContentSafeRetrievalAuditSink()
    clock = ClassroomClock()
    retriever = AuthorizedHybridRetriever(
        bundles=bundles,
        authorization=authorization,
        filter_planner=FilterPlanner(
            schema=classroom_filter_schema(),
            capabilities=ProviderFilterCapabilities(
                "day106-filter-capabilities-v1",
                frozenset({FilterOperator.EQ, FilterOperator.IN, FilterOperator.AND}),
            ),
            allow_split_or=False,
            allow_business_post_filter=False,
        ),
        query_encoder=encoder,
        lexical=lexical,
        dense=dense,
        validator=RetrievalCandidateValidator(),
        releaser=GuardedRetrievalReleaser(
            authorization=authorization,
            content=InMemoryProtectedRetrievalStore(records),
        ),
        cache=InMemoryRetrievalCache(),
        cursors=RetrievalCursorCodec(b"day106-capstone-cursor-secret"),
        audit=audit,
        clock=clock,
        classroom_mode=True,
    )
    return Day100Fixture(
        bundle,
        records,
        scope,
        bundles,
        authorization,
        encoder_provider,
        encoder,
        lexical,
        dense,
        audit,
        clock,
        retriever,
    )


def build_canonical_day101_fixture(
    *,
    generation_id: str,
    pointer_revision: int,
    generation_artifact_fingerprint: str,
    manifest_occurrence_ids: tuple[str, ...],
    authorization_revision: int,
    authorization: InMemoryRetrievalAuthorization | None = None,
    authorization_scope: RetrievalAuthorizationScope | None = None,
) -> Day101Fixture:
    """Build one selected Generation and the Day100/101 serving pipeline."""

    day100 = _build_day100_fixture(
        generation_id=generation_id,
        pointer_revision=pointer_revision,
        generation_artifact_fingerprint=generation_artifact_fingerprint,
        manifest_occurrence_ids=manifest_occurrence_ids,
        authorization_revision=authorization_revision,
        authorization=authorization,
        authorization_scope=authorization_scope,
    )
    rewrite_contract = classroom_rewrite_contract()
    rewrite_provider = DeterministicRewriteProvider(default_rewrite_outputs())
    rewrite_audit = ContentSafeRewriteAuditSink()
    rewriter = BoundedQueryRewriter(
        contract=rewrite_contract,
        degradation=QueryRewriteDegradationPolicy(
            "day106-rewrite-degradation-v1",
            allow_original_only_on_egress_denied=True,
            allow_original_only_on_provider_failure=True,
            allow_original_only_on_timeout=True,
            allow_partial_valid_variants=True,
        ),
        egress=RewriteEgressPolicy(
            "day101-rewrite-egress-v1",
            frozenset({rewrite_contract.provider}),
            True,
        ),
        provider=rewrite_provider,
        validator=QueryVariantValidator(
            lambda original, candidate: (
                "bypass" not in candidate.protected_text.casefold()
                and original.tenant_id == TENANT_ID
            )
        ),
        audit=rewrite_audit,
        digest_secret=QUERY_DIGEST_SECRET,
    )
    currentness = Day100CurrentnessOracle(
        authorization=day100.authorization,
        records=day100.records,
    )
    reranker_contract = classroom_reranker_contract()
    reranker = DeterministicRerankerAdapter(
        contract=reranker_contract,
        scores_by_candidate_id={"A@v1": 0.91, "C@v1": 0.89},
    )
    reranking_audit = ContentSafeRerankingAuditSink()
    pipeline = AuthorizedRerankingOrchestrator(
        selected_bundle=day100.bundle,
        eligibility=Day101Eligibility(True, False),
        rewriter=rewriter,
        multi_query=Day100VariantRetrievalExecutor(
            day100.retriever,
            MultiQueryExecutionPolicy(
                "day106-multi-query-v1",
                max_variants=3,
                max_total_candidate_observations=9,
                allow_partial_variant_failures=False,
            ),
        ),
        fusion_policy=MultiQueryFusionPolicy(
            "day106-multi-query-rrf-v1", 60, 3
        ),
        currentness=currentness,
        reranker_contract=reranker_contract,
        reranker_egress=RerankerEgressPolicy(
            "day101-reranker-egress-v1",
            frozenset({reranker_contract.provider}),
            allow_protected_query_egress=True,
            allow_protected_candidate_egress=True,
        ),
        reranking_degradation=RerankingDegradationPolicy(
            "day106-reranking-degradation-v1",
            allow_unreranked_on_egress_denied=True,
            allow_unreranked_on_provider_failure=True,
            allow_unreranked_on_timeout=True,
            allow_unreranked_on_invalid_output=True,
        ),
        input_builder=RerankerInputBuilder(reranker_contract),
        reranker=reranker,
        validator=RerankingValidator(),
        audit=reranking_audit,
        query_digest_secret=QUERY_DIGEST_SECRET,
    )
    return Day101Fixture(
        day100,
        rewrite_provider,
        rewrite_audit,
        currentness,
        reranker,
        reranking_audit,
        pipeline,
    )


def build_day101_request(
    fixture: Day101Fixture,
    *,
    query_id: str,
    query_text: str,
    request_attempt_id: str,
) -> RetrievalRequest:
    """Bind a query to the selected Generation; the client cannot choose it."""

    return RetrievalRequest(
        operation_id=f"operation-{request_attempt_id}",
        request_id=request_attempt_id,
        tenant_id=fixture.day100.bundle.tenant_id,
        principal_subject=fixture.day100.scope.principal_subject,
        action=RETRIEVAL_ACTION,
        purpose=RETRIEVAL_PURPOSE,
        query_text=query_text,
        top_k=len(fixture.day100.records),
        client_generation_id=None,
        query_encoder_contract_fingerprint=(
            fixture.day100.bundle.query_encoder.fingerprint
        ),
    )


def execute_grounded_query(
    fixture: Day101Fixture,
    *,
    query_id: str,
    query_text: str,
    claims: tuple[CanonicalClaim, ...],
    request_attempt_id: str | None = None,
) -> CanonicalGroundingRun:
    """Compatibility wrapper for isolated Day101 -> Day102 seam tests."""

    retrieval = execute_day101_query(
        fixture,
        query_id=query_id,
        query_text=query_text,
        request_attempt_id=(
            request_attempt_id or f"request-day106-{query_id}"
        ),
    )
    return execute_grounding_from_day101(
        fixture,
        retrieval=retrieval,
        claims=claims,
    )


def execute_day101_query(
    fixture: Day101Fixture,
    *,
    query_id: str,
    query_text: str,
    request_attempt_id: str,
) -> CanonicalRetrievalRun:
    """Run Day100/101 only, leaving the Prompt-before-security gate closed."""

    request = build_day101_request(
        fixture,
        query_id=query_id,
        query_text=query_text,
        request_attempt_id=request_attempt_id,
    )
    response = fixture.pipeline.execute(request)
    expected_original_query_digest = protected_query_digest(
        QUERY_DIGEST_SECRET,
        request.tenant_id,
        request.query_text,
    )
    if response.original_query_digest not in {
        None,
        expected_original_query_digest,
    }:
        raise RuntimeError("DAY101_ORIGINAL_QUERY_DIGEST_CONFLICT")
    handoff_digest = response.handoff_digest
    candidate_pool_digest = response.candidate_pool_digest
    authorization_scope_fingerprint = (
        response.authorization_scope_fingerprint
    )
    execution_receipt = None
    if (
        handoff_digest is not None
        and candidate_pool_digest is not None
        and authorization_scope_fingerprint is not None
    ):
        bundle = fixture.day100.bundle
        execution_receipt = DAY101_EXECUTION_RECEIPT_AUTHORITY.issue(
            receipt_id=f"day101-execution-{request.operation_id}",
            request_id=request.request_id,
            operation_id=request.operation_id,
            query_hash=request.query_hash,
            selected_bundle_id=bundle.bundle_id,
            selected_bundle_fingerprint=bundle.fingerprint,
            selected_generation_id=bundle.generation_id,
            selected_pointer_revision=bundle.revision,
            generation_artifact_digest=(
                bundle.generation_contract_fingerprint
            ),
            authorization_scope_fingerprint=(
                authorization_scope_fingerprint
            ),
            original_query_digest=expected_original_query_digest,
            day101_handoff_digest=handoff_digest,
            candidate_pool_digest=candidate_pool_digest,
            exact_occurrence_ids=tuple(
                item.identity.occurrence_id for item in response.hits
            ),
            exact_content_digests=tuple(
                item.identity.content_hash for item in response.hits
            ),
        )
    return CanonicalRetrievalRun(request, response, execution_receipt)


def execute_grounding_from_day101(
    fixture: Day101Fixture,
    *,
    retrieval: CanonicalRetrievalRun,
    claims: tuple[CanonicalClaim, ...],
    grounding_contract: GroundingContract | None = None,
    answer_provider: AnswerProvider | None = None,
    evidence_verifier: EvidenceVerifier | None = None,
) -> CanonicalGroundingRun:
    """Invoke Day102 only after the caller's Prompt-before-security gate passes."""

    if not claims:
        raise ValueError("a grounded query requires at least one claim")
    request = retrieval.retrieval_request
    day101_response = retrieval.day101_response
    contract = grounding_contract or classroom_grounding_contract()
    audit = ContentSafeGroundingAuditSink()
    answer_text = " ".join(claim.answer_text for claim in claims)
    verifier = evidence_verifier or DeterministicEvidenceVerifier(
        revision=contract.verifier_revision,
        relations_by_claim_id={
            claim.claim_id: SemanticRelation.SUPPORTED for claim in claims
        },
    )
    grounding = AuthorizedGroundingOrchestrator(
        contract=contract,
        degradation=GroundingDegradationPolicy(
            "day106-grounding-degradation-v1",
            allow_degraded_day101_handoff=False,
            allow_generator_fallback_on_failure=False,
            allow_generator_fallback_on_timeout=False,
            allow_verifier_fallback_on_failure=False,
            allow_verifier_fallback_on_timeout=False,
        ),
        generator_egress=GeneratorEgressPolicy(
            contract.egress_policy_version,
            frozenset({contract.generator_provider}),
            True,
            True,
        ),
        verifier_egress=VerifierEgressPolicy(
            "day106-verifier-egress-v1",
            frozenset({contract.verifier_provider}),
            True,
            True,
        ),
        currentness=GroundingCurrentnessOracle(
            authorization=fixture.day100.authorization,
            records=fixture.day100.records,
        ),
        planner=GroundingContextPlanner(
            contract=contract,
            selector=DeterministicContextSelector(tuple(
                occurrence_id
                for claim in claims
                for occurrence_id in claim.occurrence_ids
            )),
        ),
        generator=(
            answer_provider
            or DeterministicAnswerProvider(answer_text=answer_text)
        ),
        fallback_generator=None,
        extractor=DeterministicClaimExtractor(
            revision=contract.claim_extractor_revision,
            templates=tuple(ClaimTemplate(
                claim.claim_id,
                claim.request_item_id,
                claim.answer_text,
                claim.occurrence_ids,
            ) for claim in claims),
        ),
        verifier=verifier,
        fallback_verifier=None,
        validator=GroundingValidator(),
        audit=audit,
        query_digest_secret=QUERY_DIGEST_SECRET,
    )
    grounding_request = GroundingRequest(
        operation_id=f"grounding-{request.operation_id}",
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        principal_subject=request.principal_subject,
        action=request.action,
        purpose=request.purpose,
        original_query=request.query_text,
        request_items=tuple(RequestItem(
            claim.request_item_id,
            claim.safe_label,
            claim.question,
        ) for claim in claims),
        day101_response=day101_response,
        day101_handoff_digest=day101_response.handoff_digest or "MISSING",
    )
    day102_response = grounding.execute(grounding_request)
    events = audit.events()
    audit_checksum = stable_hash(tuple(
        (
            event.operation_id,
            event.bundle_digest,
            event.outcome,
            event.released_claim_count,
            event.rejected_claim_count,
        )
        for event in events
    ))
    return CanonicalGroundingRun(
        request,
        day101_response,
        day102_response,
        audit_checksum,
    )


def refund_window_claim() -> CanonicalClaim:
    return CanonicalClaim(
        claim_id="claim:refund-window",
        request_item_id="request-item:refund-window",
        safe_label="refund window",
        question="What is the refund window?",
        answer_text=REFUND_WINDOW,
        occurrence_ids=("A@v1",),
    )


def application_channel_claim() -> CanonicalClaim:
    return CanonicalClaim(
        claim_id="claim:application-channel",
        request_item_id="request-item:application-channel",
        safe_label="application channel",
        question="Where must a refund request be submitted?",
        answer_text=APPLICATION_CHANNEL,
        occurrence_ids=("C@v1",),
    )
