"""Narrow Day99 authorization boundary for reading one EmbeddingSet."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from rag_acl_contracts import (
    AccessEffect,
    AuthorizationRevisionVector,
    AuthorizationStateUnavailable,
    InMemoryAuthorizationStateStore,
    PrincipalKind,
    ResourceRef,
)
from rag_authorization import PermitIssuer, SignedPermit
from rag_embedding_committer import InMemoryEmbeddingStore
from rag_embedding_contracts import EmbeddingSet
from rag_ingestion_contracts import DocumentIdentity
from rag_provenance import CurrentRAGProvenanceValidator
from rag_vector_contracts import VectorIndexContract


INDEX_BUILD_ACTION = "embedding_set:read_for_indexing"
INDEX_BUILD_AUDIENCE = "vector-index-builder"
INDEX_BUILD_PURPOSE = "day99-vector-index-build"


class ContractSelectionReader(Protocol):
    def read_contract_selection(
        self, tenant_id: str
    ) -> tuple[str, int] | None: ...


@dataclass(frozen=True)
class AuthorizedIndexBuildInput:
    """Signed, current-state-bound authorization for exactly one build input."""

    permit: SignedPermit = field(repr=False)
    tenant_id: str
    principal_subject: str = field(repr=False)
    action: str
    audience: str
    purpose: str
    permit_expires_at: int
    authorization_decision_id: str
    authorization_revisions: AuthorizationRevisionVector
    document_id: str
    document_version_id: str
    chunk_set_id: str
    chunk_ids: tuple[str, ...]
    chunk_selection_revision: int
    document_state_version: int
    document_fence: int
    embedding_set_id: str
    embedding_set_checksum: str
    embedding_record_ids: tuple[str, ...]
    embedding_contract_fingerprint: str
    embedding_selection_revision: int
    vector_contract_fingerprint: str
    vector_contract_selection_revision: int
    protected_data_classification: str

    def __post_init__(self) -> None:
        if self.action != INDEX_BUILD_ACTION:
            raise ValueError("exact index-build action is required")
        if (
            self.audience != INDEX_BUILD_AUDIENCE
            or self.purpose != INDEX_BUILD_PURPOSE
        ):
            raise ValueError("index-build permit context is not exact")
        if self.permit_expires_at <= 0:
            raise ValueError("index-build permit expiry is required")
        if not self.chunk_ids or len(set(self.chunk_ids)) != len(self.chunk_ids):
            raise ValueError("exact unique Chunk identities are required")
        if (
            not self.embedding_record_ids
            or len(set(self.embedding_record_ids))
            != len(self.embedding_record_ids)
        ):
            raise ValueError("exact unique EmbeddingRecord identities are required")
        if self.embedding_selection_revision <= 0:
            raise ValueError("current EmbeddingSet selection revision is required")
        if self.chunk_selection_revision <= 0:
            raise ValueError("current ChunkSet selection revision is required")
        if self.vector_contract_selection_revision <= 0:
            raise ValueError("current VectorIndexContract revision is required")
        if not self.protected_data_classification:
            raise ValueError("protected vector classification is required")


def authorized_index_build_input(
    *,
    permit: SignedPermit,
    issuer: PermitIssuer,
    embedding_set: EmbeddingSet,
    embedding_selection_revision: int,
    contract: VectorIndexContract,
    contract_selection_revision: int,
    protected_data_classification: str = "PROTECTED_VECTOR",
) -> AuthorizedIndexBuildInput:
    """Bind a verified Day97 permit to Day98 and Day99 immutable identities."""

    if not issuer.verify_signature(permit):
        raise ValueError("index-build permit signature is invalid")
    claims = permit.claims
    record_ids = tuple(record.embedding_id for record in embedding_set.records)
    chunk_ids = tuple(record.chunk_id for record in embedding_set.records)
    if (
        claims.action != INDEX_BUILD_ACTION
        or claims.audience != INDEX_BUILD_AUDIENCE
        or claims.purpose != INDEX_BUILD_PURPOSE
        or claims.tenant_id != embedding_set.operation.tenant_id
        or claims.document_id != embedding_set.operation.document_id
        or claims.document_version_id
        != embedding_set.operation.document_version_id
        or claims.chunk_set_id != embedding_set.operation.chunk_set_id
        or claims.chunk_ids != chunk_ids
        or contract.embedding_set_id != embedding_set.embedding_set_id
        or not contract.accepts(embedding_set)
    ):
        raise ValueError("permit, EmbeddingSet and index contract do not bind")
    return AuthorizedIndexBuildInput(
        permit=permit,
        tenant_id=claims.tenant_id,
        principal_subject=claims.subject,
        action=claims.action,
        audience=claims.audience,
        purpose=claims.purpose,
        permit_expires_at=claims.expires_at,
        authorization_decision_id=claims.decision_id,
        authorization_revisions=claims.revisions,
        document_id=claims.document_id,
        document_version_id=claims.document_version_id,
        chunk_set_id=claims.chunk_set_id,
        chunk_ids=chunk_ids,
        chunk_selection_revision=claims.selection_revision,
        document_state_version=claims.document_state_version,
        document_fence=claims.document_fence,
        embedding_set_id=embedding_set.embedding_set_id,
        embedding_set_checksum=embedding_set.manifest_checksum,
        embedding_record_ids=record_ids,
        embedding_contract_fingerprint=embedding_set.contract.fingerprint,
        embedding_selection_revision=embedding_selection_revision,
        vector_contract_fingerprint=contract.fingerprint,
        vector_contract_selection_revision=contract_selection_revision,
        protected_data_classification=protected_data_classification,
    )


class IndexBuildAuthorizationGuard:
    """Fail-closed PEP used both before dispatch and immediately before commit."""

    def __init__(
        self,
        *,
        issuer: PermitIssuer,
        authorization: InMemoryAuthorizationStateStore,
        provenance: CurrentRAGProvenanceValidator,
        embeddings: InMemoryEmbeddingStore,
        contracts: ContractSelectionReader,
        clock: Callable[[], int],
    ) -> None:
        self._issuer = issuer
        self._authorization = authorization
        self._provenance = provenance
        self._embeddings = embeddings
        self._contracts = contracts
        self._clock = clock

    def check(
        self,
        handoff: AuthorizedIndexBuildInput,
        contract: VectorIndexContract,
    ) -> str | None:
        claims = handoff.permit.claims
        if not self._issuer.verify_signature(handoff.permit):
            return "INDEX_BUILD_PERMIT_SIGNATURE_INVALID"
        if (
            claims.subject != handoff.principal_subject
            or claims.decision_id != handoff.authorization_decision_id
            or claims.action != INDEX_BUILD_ACTION
            or claims.audience != INDEX_BUILD_AUDIENCE
            or claims.purpose != INDEX_BUILD_PURPOSE
            or claims.tenant_id != handoff.tenant_id
            or claims.document_id != handoff.document_id
            or claims.document_version_id != handoff.document_version_id
            or claims.chunk_set_id != handoff.chunk_set_id
            or claims.chunk_ids != handoff.chunk_ids
            or claims.expires_at != handoff.permit_expires_at
            or claims.revisions != handoff.authorization_revisions
            or claims.selection_revision != handoff.chunk_selection_revision
            or claims.document_state_version != handoff.document_state_version
            or claims.document_fence != handoff.document_fence
        ):
            return "INDEX_BUILD_PERMIT_CONTEXT_CHANGED"
        if claims.expires_at <= self._clock():
            return "INDEX_BUILD_PERMIT_EXPIRED"
        try:
            membership = self._authorization.read_membership(
                handoff.tenant_id, handoff.principal_subject
            )
            policy = self._authorization.read_policy(
                handoff.tenant_id, handoff.document_id
            )
        except AuthorizationStateUnavailable:
            return "INDEX_BUILD_AUTHORIZATION_UNAVAILABLE"
        if (
            membership is None
            or policy is None
            or not membership.active
            or membership.principal_kind is not PrincipalKind.SERVICE
        ):
            return "INDEX_BUILD_PRINCIPAL_NOT_ACTIVE"
        current_revisions = AuthorizationRevisionVector(
            policy.policy_revision,
            policy.acl_revision,
            membership.revision,
            policy.role_version,
            policy.action_catalog_version,
            policy.authorization_epoch,
        )
        if current_revisions != handoff.authorization_revisions:
            return "INDEX_BUILD_AUTHORIZATION_REVISIONS_CHANGED"
        resource = ResourceRef.chunk_set(
            handoff.tenant_id,
            handoff.document_id,
            handoff.document_version_id,
            handoff.chunk_set_id,
        )
        entries = tuple(
            entry
            for entry in policy.entries
            if entry.principal_subject == handoff.principal_subject
            and entry.action == INDEX_BUILD_ACTION
            and entry.resource.is_ancestor_of(resource)
        )
        if (
            INDEX_BUILD_ACTION not in policy.supported_actions
            or any(entry.effect is AccessEffect.DENY for entry in entries)
            or not any(entry.effect is AccessEffect.ALLOW for entry in entries)
        ):
            return "CURRENT_EXACT_INDEX_BUILD_GRANT_NOT_ALLOWED"
        current = self._provenance.evaluate(
            document=DocumentIdentity(handoff.tenant_id, handoff.document_id),
            expected_chunk_set_id=handoff.chunk_set_id,
        )
        if not current.valid or current.binding is None:
            return "CURRENT_INDEX_BUILD_PROVENANCE_INVALID"
        binding = current.binding
        if (
            binding.version.document_version_id != handoff.document_version_id
            or binding.chunk_set_id != handoff.chunk_set_id
            or binding.chunk_ids != handoff.chunk_ids
            or binding.selection_revision != handoff.chunk_selection_revision
            or binding.document_state_version != handoff.document_state_version
            or binding.document_fence != handoff.document_fence
        ):
            return "CURRENT_INDEX_BUILD_PROVENANCE_CHANGED"
        selection = self._embeddings.read_selection(
            handoff.tenant_id,
            handoff.document_id,
            handoff.chunk_set_id,
        )
        embedding_set = self._embeddings.read_set(handoff.embedding_set_id)
        if (
            selection is None
            or selection.embedding_set_id != handoff.embedding_set_id
            or selection.revision != handoff.embedding_selection_revision
            or embedding_set is None
            or embedding_set.manifest_checksum != handoff.embedding_set_checksum
            or tuple(record.embedding_id for record in embedding_set.records)
            != handoff.embedding_record_ids
            or embedding_set.contract.fingerprint
            != handoff.embedding_contract_fingerprint
            or not contract.accepts(embedding_set)
        ):
            return "CURRENT_INDEX_BUILD_EMBEDDING_SET_CHANGED"
        selected_contract = self._contracts.read_contract_selection(
            handoff.tenant_id
        )
        if selected_contract != (
            handoff.vector_contract_fingerprint,
            handoff.vector_contract_selection_revision,
        ) or contract.fingerprint != handoff.vector_contract_fingerprint:
            return "CURRENT_VECTOR_INDEX_CONTRACT_CHANGED"
        return None
