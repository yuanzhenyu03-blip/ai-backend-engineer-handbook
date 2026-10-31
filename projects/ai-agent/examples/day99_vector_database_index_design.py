"""Dependency-free Day99 shadow vector generation over Day98 output."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json

from examples.day98_embedding_selection_versioning import (
    Day98Fixture,
    build_day98_fixture,
    run_request as run_embedding_request,
)
from rag_embedding_contracts import EmbeddingSet
from mcp_auth import AuthenticatedPrincipal, AuthenticationSource
from rag_acl_contracts import (
    ACLEntry,
    AccessEffect,
    PrincipalKind,
    TenantMembership,
)
from rag_authorization import AuthorizationRequest
from rag_vector_adapter import (
    DeterministicFakeVectorProvider,
    FakeVectorMode,
)
from rag_vector_committer import (
    InMemoryVectorControlPlane,
    VectorGenerationCommitter,
)
from rag_vector_contracts import (
    DistanceMetric,
    EvidenceGate,
    IndexAlgorithm,
    IndexBuildParameters,
    ProductionReadiness,
    RetrievalPolicyRevision,
    ThresholdOperator,
    VectorBuildAttempt,
    VectorIndexContract,
    VectorProviderIdentity,
)
from rag_vector_orchestrator import (
    VectorBuildRequest,
    VectorGenerationOrchestrator,
)
from rag_vector_validator import VectorGenerationValidator
from rag_vector_index_authorization import (
    INDEX_BUILD_ACTION,
    INDEX_BUILD_AUDIENCE,
    INDEX_BUILD_PURPOSE,
    AuthorizedIndexBuildInput,
    IndexBuildAuthorizationGuard,
    authorized_index_build_input,
)
from rag_vector_index_planner import plan_vector_batches


@dataclass(frozen=True)
class Day99Fixture:
    day98: Day98Fixture
    embedding_set: EmbeddingSet
    embedding_selection_revision: int
    authorization: AuthorizedIndexBuildInput
    contract: VectorIndexContract
    contract_selection_revision: int
    policy: RetrievalPolicyRevision
    provider: DeterministicFakeVectorProvider
    store: InMemoryVectorControlPlane
    committer: VectorGenerationCommitter
    orchestrator: VectorGenerationOrchestrator


def classroom_vector_contract(
    embedding_set: EmbeddingSet,
    *,
    contract_version: str = "vector-index-contract.v1",
    build: IndexBuildParameters | None = None,
) -> VectorIndexContract:
    return VectorIndexContract(
        contract_version=contract_version,
        provider=VectorProviderIdentity(
            "classroom-fake-vector-provider",
            "fake-vector-port.v1",
            "sha256:day99-fake-flat-revision-v1",
        ),
        tenant_id=embedding_set.operation.tenant_id,
        embedding_set_id=embedding_set.embedding_set_id,
        embedding_contract_fingerprint=embedding_set.contract.fingerprint,
        dimensions=embedding_set.contract.dimensions,
        numeric_type=embedding_set.contract.numeric_type,
        normalization=embedding_set.contract.normalization,
        metric=DistanceMetric.COSINE_DISTANCE,
        build=build or IndexBuildParameters(IndexAlgorithm.FLAT),
        namespace_schema_version="tenant-generation.v1",
        point_identity_version="tenant-generation-embedding.v1",
        payload_schema_version="rag-vector-payload.v1",
        quantization_policy="NONE_FLOAT32_EXACT",
        tenant_isolation_strategy="DEDICATED_TENANT_GENERATION_NAMESPACE",
        batch_max_items=2,
        batch_max_bytes=64_000,
        durability_expectation="READBACK_REQUIRED_BEFORE_SEAL",
        backup_policy_version="backup-not-run.v1",
        update_policy_version="COPY_ON_WRITE_GENERATION.v1",
        protected_data_policy="NO_RAW_VECTOR_IN_ORDINARY_EVIDENCE.v1",
    )


def classroom_retrieval_policy(
    contract: VectorIndexContract,
    *,
    policy_version: str = "retrieval-policy.v1",
    minimum_similarity: float = 0.8,
) -> RetrievalPolicyRevision:
    ef_search = 64 if (
        contract.build.algorithm is IndexAlgorithm.HNSW
    ) else None
    probes = 8 if (
        contract.build.algorithm is IndexAlgorithm.IVFFLAT
    ) else None
    return RetrievalPolicyRevision(
        policy_version=policy_version,
        generation_contract_fingerprint=contract.fingerprint,
        top_k=3,
        minimum_similarity=minimum_similarity,
        threshold_operator=ThresholdOperator.GREATER_THAN_OR_EQUAL,
        ef_search=ef_search,
        probes=probes,
    )


def build_day99_fixture(
    *,
    mode: FakeVectorMode = FakeVectorMode.NORMAL,
    contract_version: str = "vector-index-contract.v1",
    build: IndexBuildParameters | None = None,
) -> Day99Fixture:
    day98 = build_day98_fixture()
    embedded = run_embedding_request(day98)
    assert embedded.commit is not None
    assert embedded.commit.embedding_set is not None
    embedding_set = embedded.commit.embedding_set
    selection = day98.store.read_selection(
        embedding_set.operation.tenant_id,
        embedding_set.operation.document_id,
        embedding_set.operation.chunk_set_id,
    )
    assert selection is not None
    contract = classroom_vector_contract(
        embedding_set,
        contract_version=contract_version,
        build=build,
    )
    provider = DeterministicFakeVectorProvider(mode)
    store = InMemoryVectorControlPlane()
    contract_selection_revision = store.select_contract(
        embedding_set.operation.tenant_id,
        contract.fingerprint,
    )
    index_builder = AuthenticatedPrincipal(
        subject="index-builder-a",
        issuer="https://identity.synthetic.invalid",
        audiences=frozenset({"rag-api"}),
        scopes=frozenset(),
        source=AuthenticationSource.HTTP_BEARER,
        expires_at=10_000,
        client_id="index-builder-a",
    )
    day98.day97.principals["index_builder"] = index_builder
    day98.day97.authorization.put_membership(TenantMembership(
        tenant_id=embedding_set.operation.tenant_id,
        principal_subject=index_builder.subject,
        principal_kind=PrincipalKind.SERVICE,
        active=True,
        revision=1,
    ))
    current_policy = day98.day97.authorization.read_policy(
        embedding_set.operation.tenant_id,
        embedding_set.operation.document_id,
    )
    assert current_policy is not None
    index_grant = ACLEntry(
        "grant-index-builder-read-embedding-set",
        index_builder.subject,
        day98.day97.resource,
        INDEX_BUILD_ACTION,
        AccessEffect.ALLOW,
    )
    current_policy = replace(
        current_policy,
        policy_revision=current_policy.policy_revision + 1,
        acl_revision=current_policy.acl_revision + 1,
        authorization_epoch=current_policy.authorization_epoch + 1,
        supported_actions=(
            current_policy.supported_actions | frozenset({INDEX_BUILD_ACTION})
        ),
        entries=current_policy.entries + (index_grant,),
    )
    day98.day97.authorization.put_policy(current_policy)
    authorization_result = day98.day97.service.authorize(
        AuthorizationRequest(
            principal=index_builder,
            tenant_id=embedding_set.operation.tenant_id,
            resource=day98.day97.resource,
            action=INDEX_BUILD_ACTION,
            audience=INDEX_BUILD_AUDIENCE,
            purpose=INDEX_BUILD_PURPOSE,
            chunk_ids=tuple(
                record.chunk_id for record in embedding_set.records
            ),
        )
    )
    assert authorization_result.permit is not None
    authorization = authorized_index_build_input(
        permit=authorization_result.permit,
        issuer=day98.day97.issuer,
        embedding_set=embedding_set,
        embedding_selection_revision=selection.revision,
        contract=contract,
        contract_selection_revision=contract_selection_revision,
    )
    authorization_guard = IndexBuildAuthorizationGuard(
        issuer=day98.day97.issuer,
        authorization=day98.day97.authorization,
        provenance=day98.day97.provenance,
        embeddings=day98.store,
        contracts=store,
        clock=day98.day97.clock,
    )
    committer = VectorGenerationCommitter(
        store=store,
        embeddings=day98.store,
        authorization_guard=authorization_guard,
    )
    orchestrator = VectorGenerationOrchestrator(
        embeddings=day98.store,
        provider=provider,
        validator=VectorGenerationValidator(),
        committer=committer,
        authorization_guard=authorization_guard,
    )
    return Day99Fixture(
        day98,
        embedding_set,
        selection.revision,
        authorization,
        contract,
        contract_selection_revision,
        classroom_retrieval_policy(contract),
        provider,
        store,
        committer,
        orchestrator,
    )


def vector_build_request(
    fixture: Day99Fixture,
    *,
    operation_id: str = "op-day99-vector-generation-v1",
    idempotency_key: str = "idem-day99-vector-generation-v1",
    attempt_number: int = 1,
    request_id: str = "request-day99-vector-generation-v1",
) -> VectorBuildRequest:
    operation = fixture.embedding_set.operation
    return VectorBuildRequest(
        operation_id=operation_id,
        idempotency_key=idempotency_key,
        tenant_id=operation.tenant_id,
        document_id=operation.document_id,
        chunk_set_id=operation.chunk_set_id,
        embedding_set_id=fixture.embedding_set.embedding_set_id,
        expected_embedding_selection_revision=(
            fixture.embedding_selection_revision
        ),
        expected_contract_selection_revision=(
            fixture.contract_selection_revision
        ),
        contract=fixture.contract,
        authorization=fixture.authorization,
        attempt=VectorBuildAttempt(
            operation_id,
            attempt_number,
            request_id,
        ),
    )


def rebind_vector_contract(
    fixture: Day99Fixture,
    contract: VectorIndexContract,
) -> Day99Fixture:
    """Select and authorize a new physical contract without replacing vectors."""

    revision = fixture.store.select_contract(
        fixture.embedding_set.operation.tenant_id,
        contract.fingerprint,
    )
    authorization = authorized_index_build_input(
        permit=fixture.authorization.permit,
        issuer=fixture.day98.day97.issuer,
        embedding_set=fixture.embedding_set,
        embedding_selection_revision=fixture.embedding_selection_revision,
        contract=contract,
        contract_selection_revision=revision,
    )
    return replace(
        fixture,
        authorization=authorization,
        contract=contract,
        contract_selection_revision=revision,
        policy=classroom_retrieval_policy(contract),
    )


def run_example() -> dict[str, object]:
    fixture = build_day99_fixture()
    result = fixture.orchestrator.run(vector_build_request(fixture))
    assert result.commit is not None and result.commit.generation is not None
    generation = result.commit.generation
    points = fixture.provider.readback(generation.generation_id).points
    plan = plan_vector_batches(
        points,
        contract=fixture.contract,
        operation_id=generation.operation.operation_id,
    )
    activation = fixture.committer.activate(
        generation_id=generation.generation_id,
        policy=fixture.policy,
        expected_generation_id=None,
        expected_revision=0,
        activation_fence=1,
    )
    return {
        "build_outcome": result.outcome.value,
        "safe_reason": result.safe_reason,
        "generation_id": generation.generation_id,
        "generation_state": generation.state.value,
        "point_count": generation.manifest.point_count,
        "build_batch_count": len(plan.batches),
        "build_plan_checksum": plan.checksum,
        "index_build_action": fixture.authorization.action,
        "contract_selection_revision": fixture.contract_selection_revision,
        "manifest_contains_vectors": False,
        "provider_write_calls": len(fixture.provider.write_calls),
        "provider_query_calls": len(fixture.provider.query_calls),
        "content_readback": generation.evidence.state_for(
            EvidenceGate.CONTENT_READBACK
        ).value,
        "score_semantics": generation.evidence.state_for(
            EvidenceGate.SCORE_SEMANTICS
        ).value,
        "exact_parity": generation.evidence.state_for(
            EvidenceGate.EXACT_PARITY
        ).value,
        "fake_tenant_filter": generation.evidence.state_for(
            EvidenceGate.TENANT_FILTER
        ).value,
        "ann_recall": generation.evidence.state_for(
            EvidenceGate.ANN_RECALL
        ).value,
        "real_provider": generation.evidence.state_for(
            EvidenceGate.REAL_PROVIDER
        ).value,
        "production_readiness": generation.evidence.readiness.value,
        "activation_outcome": activation.outcome.value,
        "selected_bundle": fixture.store.read_selected_bundle(
            fixture.embedding_set.operation.tenant_id
        ) is not None,
        "outbox_intent_count": len(fixture.store.outbox_intents()),
        "execution_evidence": "EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE",
        "day100_handoff": "SEALED_NON_SERVING_GENERATION_METADATA_ONLY",
    }


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2, sort_keys=True))
