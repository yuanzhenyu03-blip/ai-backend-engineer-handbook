"""Deterministic Day97 authorization/provenance example using synthetic data."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import itertools
import json

from examples.day96_active_fixture import active_day95_store
from mcp_auth import AuthenticatedPrincipal, AuthenticationSource
from rag_acl_contracts import (
    ACLEntry,
    AccessEffect,
    AuthorizationPolicySnapshot,
    InMemoryAuthorizationStateStore,
    PrincipalKind,
    ResourceRef,
    TenantMembership,
)
from rag_authorization import (
    AuthorizationRequest,
    BoundedAuthorizationDecisionCache,
    PermitIssuer,
    PolicyDecisionPoint,
    PolicyInformationPoint,
    RAGAuthorizationService,
)
from rag_authorized_chunk_reader import (
    ContentSafeAuditSink,
    GuardedChunkReader,
    PermitUseStore,
)
from rag_chunking_committer import ChunkSetCommitter, InMemoryChunkSetStore
from rag_chunking_contracts import (
    ChunkStrategy,
    ChunkingAttemptIdentity,
    ChunkingContract,
    ChunkingOperationIdentity,
    OversizedPolicy,
)
from rag_chunking_strategies import ChunkingStrategyAdapter
from rag_chunking_validator import ChunkSetCandidateValidator
from rag_metadata_committer import InMemoryMetadataStore, MetadataCommitter
from rag_metadata_contracts import (
    MetadataAssertion,
    MetadataContract,
    MetadataFieldDefinition,
    MetadataOrigin,
    MetadataProjectionAttempt,
    MetadataProjectionOperation,
    MetadataSensitivity,
    MetadataValueType,
)
from rag_metadata_orchestrator import (
    MetadataRunRequest,
    RAGMetadataOrchestrator,
)
from rag_metadata_projection import MetadataProjector
from rag_metadata_validator import MetadataCandidateValidator
from rag_ingestion_contracts import DocumentIdentity
from rag_provenance import CurrentRAGProvenanceValidator
from rag_tokenizer_adapter import ClassroomTokenizer


SYNTHETIC_TEXT = (
    "# Access policy\n\n"
    "Synthetic public guidance for authorized readers.\n\n"
    "Repeated sentence for provenance.\n\n"
    "Repeated sentence for provenance.\n"
)


@dataclass
class MutableClock:
    value: int = 1_000

    def __call__(self) -> int:
        return self.value


@dataclass(frozen=True)
class Day97Fixture:
    day95: object
    chunks: InMemoryChunkSetStore
    provenance: CurrentRAGProvenanceValidator
    authorization: InMemoryAuthorizationStateStore
    policy: AuthorizationPolicySnapshot
    principals: dict[str, AuthenticatedPrincipal]
    clock: MutableClock
    issuer: PermitIssuer
    service: RAGAuthorizationService
    cache: BoundedAuthorizationDecisionCache
    reader: GuardedChunkReader
    audit: ContentSafeAuditSink
    resource: ResourceRef
    chunk_ids: tuple[str, ...]
    metadata_contract: MetadataContract
    metadata_store: InMemoryMetadataStore


def _principal(subject: str, *, service: bool = False) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer="https://identity.synthetic.invalid",
        audiences=frozenset({"rag-api"}),
        scopes=frozenset(),
        source=AuthenticationSource.HTTP_BEARER,
        expires_at=10_000,
        client_id=(subject if service else None),
    )


def _metadata_contract(version: str = "metadata.v1") -> MetadataContract:
    return MetadataContract(version, (
        MetadataFieldDefinition(
            "system",
            "media_type",
            MetadataValueType.STRING,
            frozenset({MetadataOrigin.SYSTEM}),
            MetadataSensitivity.INTERNAL,
            filterable=True,
        ),
        MetadataFieldDefinition(
            "derived",
            "character_count",
            MetadataValueType.INTEGER,
            frozenset({MetadataOrigin.DERIVED}),
            MetadataSensitivity.INTERNAL,
            filterable=True,
        ),
        MetadataFieldDefinition(
            "source",
            "topic",
            MetadataValueType.STRING,
            frozenset({MetadataOrigin.SOURCE_DECLARED}),
            MetadataSensitivity.PROTECTED,
        ),
    ))


def build_fixture(
    text: str = SYNTHETIC_TEXT,
    *,
    soft_target_tokens: int = 8,
    hard_max_tokens: int = 12,
) -> Day97Fixture:
    day95, parsed = active_day95_store(text)
    document = day95.read_document(parsed.version.document)
    version = day95.read_version(parsed.version)
    ingestion = day95.read_operation(parsed.manifest.operation_id)
    source = day95.read_source_artifact(parsed.source_artifact_id)
    assert source is not None

    tokenizer = ClassroomTokenizer()
    contract = ChunkingContract(
        strategy=ChunkStrategy.FIXED_TOKEN,
        strategy_version="day97-fixture-v1",
        tokenizer=tokenizer.contract,
        normalization_version="identity-v1",
        soft_target_tokens=soft_target_tokens,
        hard_max_tokens=hard_max_tokens,
        min_useful_tokens=1,
        overlap_tokens=0,
        max_chunk_count=100,
        max_input_chars=10_000,
        max_output_chars=20_000,
        deadline_seconds=10.0,
        oversized_policy=OversizedPolicy.BOUNDED_FALLBACK,
    )
    operation = ChunkingOperationIdentity(
        parsed.version,
        parsed.source_artifact_id,
        parsed.parsed_artifact_id,
        "op-day97-selected",
        "idem-day97-selected",
        contract.fingerprint,
    )
    attempt = ChunkingAttemptIdentity(
        operation.operation_id,
        1,
        "request-day97-selected",
        1,
    )
    adapter = ChunkingStrategyAdapter(tokenizer)
    validator = ChunkSetCandidateValidator(tokenizer)
    candidate = adapter.generate(
        parsed=parsed,
        contract=contract,
        operation=operation,
        attempt=attempt,
        experiment_id="exp-day97-selected",
    )
    decision = validator.evaluate(
        document=document,
        version=version,
        ingestion=ingestion,
        parsed=parsed,
        source=source,
        contract=contract,
        candidate=candidate,
    )
    chunks = InMemoryChunkSetStore()
    committer = ChunkSetCommitter(
        day95_store=day95,
        chunk_store=chunks,
        validator=validator,
    )
    claim = committer.claim(operation, attempt)
    assert claim is not None
    committed = committer.persist(decision, contract=contract)
    assert committed.chunk_set is not None
    selected = committer.select(
        chunk_set_id=committed.chunk_set.chunk_set_id,
        expected_selected_id=None,
        expected_selection_revision=0,
        expected_document_state_version=document.state_version,
        expected_document_fence=document.fence_token,
        claim=claim,
    )
    assert selected.selection is not None

    provenance = CurrentRAGProvenanceValidator(
        day95_store=day95,
        chunk_store=chunks,
    )
    current = provenance.evaluate(document=parsed.version.document)
    assert current.valid and current.binding is not None
    resource = ResourceRef.chunk_set(
        parsed.version.tenant_id,
        parsed.version.document_id,
        parsed.version.document_version_id,
        current.binding.chunk_set_id,
    )
    chunk_ids = current.binding.chunk_ids
    principals = {
        "owner": _principal("tenant-a-owner"),
        "viewer": _principal("tenant-a-viewer"),
        "member": _principal("tenant-a-member-without-grant"),
        "tenant_b": _principal("tenant-b-owner"),
        "worker": _principal("embedding-worker-a", service=True),
        "disabled": _principal("disabled-service-principal", service=True),
    }
    authorization = InMemoryAuthorizationStateStore()
    for name, principal in principals.items():
        tenant_id = "tenant-b" if name == "tenant_b" else "tenant-a"
        authorization.put_membership(TenantMembership(
            tenant_id=tenant_id,
            principal_subject=principal.subject,
            principal_kind=(
                PrincipalKind.SERVICE
                if name in {"worker", "disabled"}
                else PrincipalKind.HUMAN
            ),
            active=name != "disabled",
            revision=1,
        ))
    document_resource = ResourceRef.document("tenant-a", "report-42")
    entries = (
        ACLEntry(
            "grant-owner-read",
            principals["owner"].subject,
            document_resource,
            "chunk.text.read",
            AccessEffect.ALLOW,
        ),
        ACLEntry(
            "grant-viewer-read",
            principals["viewer"].subject,
            document_resource,
            "chunk.text.read",
            AccessEffect.ALLOW,
        ),
        ACLEntry(
            "grant-worker-embedding",
            principals["worker"].subject,
            resource,
            "chunk:read_for_embedding",
            AccessEffect.ALLOW,
        ),
        ACLEntry(
            "grant-disabled-embedding",
            principals["disabled"].subject,
            resource,
            "chunk:read_for_embedding",
            AccessEffect.ALLOW,
        ),
    )
    policy = AuthorizationPolicySnapshot(
        tenant_id="tenant-a",
        document_id="report-42",
        policy_revision=1,
        acl_revision=1,
        role_version="roles.v1",
        action_catalog_version="actions.v1",
        authorization_epoch=1,
        supported_actions=frozenset({
            "chunk.text.read",
            "chunk.export",
            "chunk:read_for_embedding",
        }),
        entries=entries,
    )
    authorization.put_policy(policy)
    clock = MutableClock()
    synthetic_key = hashlib.sha256(
        b"deterministic Day97 classroom signing material"
    ).digest()
    nonce_counter = itertools.count(1)
    issuer = PermitIssuer(
        issuer="permit-issuer.synthetic.invalid",
        signing_key=synthetic_key,
        clock=clock,
        ttl_seconds=60,
        nonce_factory=lambda: f"deterministic-nonce-{next(nonce_counter)}",
    )
    pip = PolicyInformationPoint(
        state_store=authorization,
        provenance_validator=provenance,
    )
    cache = BoundedAuthorizationDecisionCache(clock=clock)
    service = RAGAuthorizationService(
        pip=pip,
        pdp=PolicyDecisionPoint(clock=clock),
        issuer=issuer,
        cache=cache,
    )
    audit = ContentSafeAuditSink()
    reader = GuardedChunkReader(
        issuer=issuer,
        state_store=authorization,
        provenance_validator=provenance,
        permit_uses=PermitUseStore(),
        audit_sink=audit,
        clock=clock,
    )
    return Day97Fixture(
        day95=day95,
        chunks=chunks,
        provenance=provenance,
        authorization=authorization,
        policy=policy,
        principals=principals,
        clock=clock,
        issuer=issuer,
        service=service,
        cache=cache,
        reader=reader,
        audit=audit,
        resource=resource,
        chunk_ids=chunk_ids,
        metadata_contract=_metadata_contract(),
        metadata_store=InMemoryMetadataStore(),
    )


def request_for(
    fixture: Day97Fixture,
    principal_name: str,
    *,
    action: str = "chunk.text.read",
    audience: str = "guarded-chunk-reader",
    purpose: str = "interactive-rag-read",
    chunk_ids: tuple[str, ...] | None = None,
) -> AuthorizationRequest:
    return AuthorizationRequest(
        principal=fixture.principals[principal_name],
        tenant_id=fixture.resource.tenant_id,
        resource=fixture.resource,
        action=action,
        audience=audience,
        purpose=purpose,
        chunk_ids=chunk_ids or fixture.chunk_ids,
    )


def run_example() -> dict[str, object]:
    fixture = build_fixture()
    # Metadata publication uses the same current selection/document guards.
    provenance = fixture.provenance.evaluate(
        document=DocumentIdentity("tenant-a", "report-42")
    )
    assert provenance.binding is not None
    operation = MetadataProjectionOperation(
        version=provenance.binding.version,
        chunk_set_id=provenance.binding.chunk_set_id,
        operation_id="op-day97-metadata-v1",
        idempotency_key="idem-day97-metadata-v1",
        contract_fingerprint=fixture.metadata_contract.fingerprint,
        expected_selection_revision=provenance.binding.selection_revision,
        expected_document_state_version=provenance.binding.document_state_version,
        expected_document_fence=provenance.binding.document_fence,
    )
    metadata_committer = MetadataCommitter(
        store=fixture.metadata_store,
        provenance_validator=fixture.provenance,
    )
    metadata_result = RAGMetadataOrchestrator(
        projector=MetadataProjector(),
        validator=MetadataCandidateValidator(),
        committer=metadata_committer,
    ).run(MetadataRunRequest(
        operation=operation,
        attempt=MetadataProjectionAttempt(
            operation.operation_id, 1, "request-day97-metadata-v1", 1
        ),
        contract=fixture.metadata_contract,
        assertions=(
            MetadataAssertion(
                "system.media_type",
                "text/markdown",
                MetadataOrigin.SYSTEM,
                "source-artifact:detected-media-type",
            ),
            MetadataAssertion(
                "derived.character_count",
                len(SYNTHETIC_TEXT),
                MetadataOrigin.DERIVED,
                "parsed-artifact:canonical-text-length",
            ),
            MetadataAssertion(
                "source.topic",
                "synthetic-policy",
                MetadataOrigin.SOURCE_DECLARED,
                "source-document:front-matter",
            ),
        ),
    ))
    authorization = fixture.service.authorize(request_for(
        fixture,
        "worker",
        action="chunk:read_for_embedding",
        purpose="day98-embedding",
    ))
    assert authorization.permit is not None
    read = fixture.reader.read(
        permit=authorization.permit,
        principal=fixture.principals["worker"],
        expected_action="chunk:read_for_embedding",
        expected_audience="guarded-chunk-reader",
        expected_purpose="day98-embedding",
    )
    handoff = fixture.reader.embedding_handoff(
        permit=authorization.permit,
        result=read,
    )
    return {
        "authorization_outcome": authorization.decision.outcome.value,
        "authorization_reason": authorization.decision.internal_reason_code,
        "guarded_read_outcome": read.outcome.value,
        "metadata_commit_outcome": metadata_result.outcome.value,
        "metadata_snapshot_id": (
            None if metadata_result.snapshot is None
            else metadata_result.snapshot.snapshot_id
        ),
        "selected_chunk_set_id": fixture.resource.chunk_set_id,
        "authorized_chunk_count": len(read.chunks),
        "day98_handoff": {
            "action": authorization.permit.claims.action,
            "chunk_count": len(handoff.chunks),
            "classification": handoff.protected_data_classification,
            "authorization_epoch": handoff.authorization_epoch,
        },
        "audit_event_count": len(fixture.audit.events()),
        "execution_evidence": "EXECUTED_LOCAL_RUNTIME",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2, sort_keys=True))
