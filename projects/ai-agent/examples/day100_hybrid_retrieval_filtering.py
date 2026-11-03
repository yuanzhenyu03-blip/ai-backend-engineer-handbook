"""Executable Day100 negative handoff and isolated synthetic positive fixture."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

from rag_authorized_retriever import (
    GuardedRetrievalReleaser,
    InMemoryProtectedRetrievalStore,
    InMemoryRetrievalAuthorization,
    classroom_authorization_revisions,
)
from rag_chunking_contracts import stable_hash
from rag_dense_retrieval import DenseMode, ExactDenseRetrievalAdapter
from rag_lexical_retrieval import (
    BM25ReferenceIndex,
    LexicalMode,
    LexicalRetrievalAdapter,
)
from rag_query_encoder import (
    DeterministicFakeQueryEncoder,
    FakeQueryEncoderMode,
    QueryEgressPolicy,
    QueryEncoderAdapter,
    QuerySensitivity,
)
from rag_retrieval_cache import InMemoryRetrievalCache, RetrievalCursorCodec
from rag_retrieval_contracts import (
    CandidateIdentity,
    FusionPolicy,
    HybridRetrievalPolicy,
    LexicalRetrievalContract,
    QueryEncoderContract,
    RetrievalAuthorizationScope,
    RetrievalRecord,
    RetrievalRequest,
    SelectedRetrievalBundle,
    RETRIEVAL_ACTION,
    RETRIEVAL_PURPOSE,
)
from rag_retrieval_filters import (
    FilterExpression,
    FilterField,
    FilterOperator,
    FilterPlanner,
    FilterSchema,
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


class ClassroomClock:
    def __init__(self, value: int = 1_800_000_000) -> None:
        self.value = value

    def __call__(self) -> int:
        return self.value


@dataclass
class Day100Fixture:
    bundle: SelectedRetrievalBundle
    records: tuple[RetrievalRecord, ...]
    scope: RetrievalAuthorizationScope
    bundles: InMemoryRetrievalBundleAuthority
    authorization: InMemoryRetrievalAuthorization
    encoder_provider: DeterministicFakeQueryEncoder
    encoder: QueryEncoderAdapter
    lexical: LexicalRetrievalAdapter
    dense: ExactDenseRetrievalAdapter
    audit: ContentSafeRetrievalAuditSink
    clock: ClassroomClock
    retriever: AuthorizedHybridRetriever


def classroom_query_contract() -> QueryEncoderContract:
    return QueryEncoderContract(
        contract_version="day100-query-encoder-v1",
        provider="classroom-deterministic-query-encoder",
        immutable_model_revision="fake-query-model-sha256-001",
        document_contract_fingerprint="sha256:day98-document-contract",
        dimensions=4,
        query_input_role="QUERY",
        query_prefix="query: ",
        document_input_role="DOCUMENT",
        document_prefix="passage: ",
        tokenizer_revision="classroom-tokenizer-v1",
        normalization="UNIT_L2",
        protected_data_policy="PROTECTED_QUERY_NO_LOG",
        egress_policy_version="day100-egress-v1",
    )


def classroom_lexical_contract() -> LexicalRetrievalContract:
    return LexicalRetrievalContract(
        contract_version="day100-lexical-v1",
        corpus_generation_id="synthetic-lexical-generation-g1",
        chunk_set_id="synthetic-chunk-set-day100",
        analyzer_version="lowercase-word-analyzer-v1",
        tokenizer_version="regex-word-tokenizer-v1",
        language="en",
        k1=1.2,
        b=0.75,
        stop_words=("the", "a", "and"),
    )


def classroom_filter_schema() -> FilterSchema:
    return FilterSchema(
        "day100-filter-schema-v1",
        (
            FilterField("tenant_id", str, client_filterable=False),
            FilterField("category", str),
            FilterField("owner_id", str),
            FilterField("status", str),
        ),
        max_depth=4,
        max_nodes=12,
    )


def classroom_bundle(schema: FilterSchema) -> SelectedRetrievalBundle:
    query = classroom_query_contract()
    lexical = classroom_lexical_contract()
    return SelectedRetrievalBundle(
        bundle_id="synthetic-selected-retrieval-bundle-v1",
        revision=1,
        tenant_id="tenant-day100",
        generation_id="synthetic-vector-generation-g1",
        generation_state=GenerationState.ACTIVATED,
        generation_contract_fingerprint="sha256:synthetic-vector-contract",
        embedding_set_id="synthetic-embedding-set-day100",
        embedding_contract_fingerprint=query.document_contract_fingerprint,
        chunk_set_id=lexical.chunk_set_id,
        lexical_corpus_generation_id=lexical.corpus_generation_id,
        query_encoder=query,
        lexical=lexical,
        filter_schema_fingerprint=schema.fingerprint,
        retrieval_policy=HybridRetrievalPolicy(
            policy_version="day100-retrieval-policy-v1",
            max_top_k=5,
            max_candidate_depth=4,
            max_refill_rounds=3,
            max_candidate_budget=24,
            deadline_ms=500,
            allow_lexical_only=True,
            allow_dense_only=True,
            allow_split_or=True,
            allow_business_post_filter=True,
        ),
        fusion_policy=FusionPolicy(
            policy_version="day100-rrf-v1",
            rrf_k=60,
            candidate_depth=2,
        ),
        selected=True,
        evidence_level="DETERMINISTIC_FAKE+EXECUTED_LOCAL_RUNTIME",
        fixture_scope="DAY100_CLASSROOM_ONLY",
        production_eligible=False,
        production_readiness=ProductionReadiness.MORE_EVIDENCE_NEEDED,
    )


def _unit(values: tuple[float, ...]) -> tuple[float, ...]:
    norm = math.sqrt(sum(value * value for value in values))
    return tuple(value / norm for value in values)


def _query_vector(contract: QueryEncoderContract, text: str) -> tuple[float, ...]:
    provider = DeterministicFakeQueryEncoder()
    return provider.encode(
        contract=contract,
        protected_query=contract.query_prefix + text,
    )


def classroom_records(bundle: SelectedRetrievalBundle) -> tuple[RetrievalRecord, ...]:
    query = _query_vector(bundle.query_encoder, "refund policy")
    variants = (
        query,
        _unit((query[0] + 0.15, query[1] - 0.08, query[2], query[3])),
        _unit((query[1], query[0], query[2], query[3])),
        query,
        _unit((query[0] - 0.05, query[1] + 0.04, query[2], query[3])),
    )
    definitions = (
        ("A", "refund policy finance", "finance", "principal-day100", "doc-a"),
        ("B", "customer refund billing", "billing", "principal-day100", "doc-b"),
        ("C", "finance compliance handbook", "finance", "other-owner", "doc-c"),
        ("X", "refund secret restricted", "finance", "other-owner", "doc-x"),
        ("A2", "refund policy finance", "finance", "principal-day100", "doc-a2"),
    )
    records = []
    for values, embedding in zip(definitions, variants):
        occurrence_id, text, category, owner, document_id = values
        identity = CandidateIdentity(
            tenant_id=bundle.tenant_id,
            document_id=document_id,
            document_version_id=document_id + ":v1",
            chunk_set_id=bundle.chunk_set_id,
            chunk_id="chunk:" + occurrence_id.lower(),
            occurrence_id="occurrence:" + occurrence_id,
            provenance_fingerprint=stable_hash((document_id, "provenance-v1")),
            content_hash=stable_hash(text),
        )
        records.append(RetrievalRecord(
            identity,
            text,
            tuple(sorted({
                "tenant_id": bundle.tenant_id,
                "category": category,
                "owner_id": owner,
                "status": "active",
            }.items())),
            embedding,
        ))
    return tuple(records)


def build_day100_fixture(
    *,
    select_bundle: bool = True,
    encoder_mode: FakeQueryEncoderMode = FakeQueryEncoderMode.NORMAL,
    lexical_mode: LexicalMode = LexicalMode.NORMAL,
    dense_mode: DenseMode = DenseMode.NORMAL,
    allowed_sensitivities: frozenset[QuerySensitivity] = frozenset({
        QuerySensitivity.NORMAL,
    }),
    classroom_mode: bool = True,
) -> Day100Fixture:
    schema = classroom_filter_schema()
    bundle = classroom_bundle(schema)
    records = classroom_records(bundle)
    scope = RetrievalAuthorizationScope(
        tenant_id=bundle.tenant_id,
        principal_subject="principal-day100",
        action=RETRIEVAL_ACTION,
        purpose=RETRIEVAL_PURPOSE,
        revisions=classroom_authorization_revisions(),
        allowed_occurrence_ids=(
            "occurrence:A",
            "occurrence:B",
            "occurrence:C",
            "occurrence:A2",
        ),
        decision_id="decision-day100-retrieval-v1",
    )
    bundles = InMemoryRetrievalBundleAuthority()
    if select_bundle:
        bundles.select(bundle)
    authorization = InMemoryRetrievalAuthorization()
    authorization.put(scope)
    provider = DeterministicFakeQueryEncoder(encoder_mode)
    encoder = QueryEncoderAdapter(
        contract=bundle.query_encoder,
        provider=provider,
        egress_policy=QueryEgressPolicy(
            "day100-egress-v1",
            frozenset({bundle.query_encoder.provider}),
            allowed_sensitivities,
            allow_external=False,
        ),
    )
    lexical = LexicalRetrievalAdapter(
        BM25ReferenceIndex(contract=bundle.lexical, records=records),
        mode=lexical_mode,
    )
    dense = ExactDenseRetrievalAdapter(records, mode=dense_mode)
    content = InMemoryProtectedRetrievalStore(records)
    audit = ContentSafeRetrievalAuditSink()
    clock = ClassroomClock()
    retriever = AuthorizedHybridRetriever(
        bundles=bundles,
        authorization=authorization,
        filter_planner=FilterPlanner(
            schema=schema,
            capabilities=ProviderFilterCapabilities(
                "classroom-filter-capabilities-v1",
                frozenset({
                    FilterOperator.EQ,
                    FilterOperator.IN,
                    FilterOperator.AND,
                }),
            ),
            allow_split_or=bundle.retrieval_policy.allow_split_or,
            allow_business_post_filter=(
                bundle.retrieval_policy.allow_business_post_filter
            ),
        ),
        query_encoder=encoder,
        lexical=lexical,
        dense=dense,
        validator=RetrievalCandidateValidator(),
        releaser=GuardedRetrievalReleaser(
            authorization=authorization,
            content=content,
        ),
        cache=InMemoryRetrievalCache(),
        cursors=RetrievalCursorCodec(b"day100-classroom-cursor-secret"),
        audit=audit,
        clock=clock,
        classroom_mode=classroom_mode,
    )
    return Day100Fixture(
        bundle,
        records,
        scope,
        bundles,
        authorization,
        provider,
        encoder,
        lexical,
        dense,
        audit,
        clock,
        retriever,
    )


def retrieval_request(
    fixture: Day100Fixture,
    *,
    query_text: str = "refund policy",
    top_k: int = 3,
    client_filter: FilterExpression | None = None,
    client_generation_id: str | None = None,
    operation_id: str = "operation-day100-v1",
    request_id: str = "request-day100-v1",
) -> RetrievalRequest:
    return RetrievalRequest(
        operation_id=operation_id,
        request_id=request_id,
        tenant_id=fixture.bundle.tenant_id,
        principal_subject=fixture.scope.principal_subject,
        action=RETRIEVAL_ACTION,
        purpose=RETRIEVAL_PURPOSE,
        query_text=query_text,
        top_k=top_k,
        client_filter=client_filter,
        client_generation_id=client_generation_id,
        query_encoder_contract_fingerprint=(
            fixture.bundle.query_encoder.fingerprint
        ),
    )


def load_real_day99_handoff() -> dict[str, object]:
    path = Path(__file__).resolve().parents[1] / "evidence" / (
        "day99-index-build-report.json"
    )
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        "generation_id": report["generation_id"],
        "generation_state": report["generation_state"],
        "selected_bundle": report["selected_bundle"],
        "ann_recall": report["ann_recall"],
        "real_provider": report["real_provider"],
        "production_readiness": report["production_readiness"],
    }


def run_example() -> dict[str, object]:
    real_handoff = load_real_day99_handoff()
    negative = build_day100_fixture(select_bundle=False)
    negative_result = negative.retriever.retrieve(retrieval_request(negative))

    positive = build_day100_fixture()
    business_filter = FilterExpression.or_(
        FilterExpression.eq("category", "finance"),
        FilterExpression.eq("owner_id", "principal-day100"),
    )
    positive_result = positive.retriever.retrieve(retrieval_request(
        positive,
        client_filter=business_filter,
    ))
    return {
        "real_day99_handoff": real_handoff,
        "real_handoff_day100_outcome": negative_result.outcome.value,
        "real_handoff_reason": negative_result.safe_reason,
        "real_handoff_database_calls": negative_result.database_calls,
        "synthetic_fixture_scope": positive.bundle.fixture_scope,
        "synthetic_production_eligible": positive.bundle.production_eligible,
        "synthetic_outcome": positive_result.outcome.value,
        "synthetic_returned_occurrences": [
            hit.identity.occurrence_id for hit in positive_result.hits
        ],
        "synthetic_raw_query_logged": positive.audit.events()[-1].raw_query_logged,
        "real_provider": "NOT_RUN",
        "real_database": "NOT_RUN",
        "ann": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2, sort_keys=True))
