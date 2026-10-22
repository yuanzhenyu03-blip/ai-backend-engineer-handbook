"""Day97 PEP and guarded protected Chunk text release."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import threading
from typing import Callable

from mcp_auth import AuthenticatedPrincipal
from rag_acl_contracts import (
    AuthorizationRevisionVector,
    AuthorizationStateUnavailable,
    InMemoryAuthorizationStateStore,
)
from rag_authorization import PermitIssuer, SignedPermit
from rag_chunking_contracts import SourceSegment
from rag_ingestion_contracts import DocumentIdentity
from rag_provenance import CurrentRAGProvenanceValidator


class GuardedReadOutcome(str, Enum):
    RELEASED = "RELEASED"
    DENIED = "DENIED"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class AuthorizedChunkView:
    chunk_id: str
    text: str
    content_hash: str
    source_segments: tuple[SourceSegment, ...]


@dataclass(frozen=True)
class GuardedReadResult:
    outcome: GuardedReadOutcome
    internal_reason_code: str
    safe_external_message: str
    external_status: int
    decision_id: str
    chunks: tuple[AuthorizedChunkView, ...] = ()

    @property
    def released(self) -> bool:
        return self.outcome is GuardedReadOutcome.RELEASED

    def __post_init__(self) -> None:
        if self.released != bool(self.chunks):
            raise ValueError("only a released read carries protected Chunk views")


@dataclass(frozen=True)
class ContentSafeAuthorizationAudit:
    decision_id: str
    permit_id_hash: str
    principal_subject_hash: str
    outcome: str
    reason_code: str
    action: str
    chunk_count: int


class ContentSafeAuditSink:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[ContentSafeAuthorizationAudit] = []

    def record(self, event: ContentSafeAuthorizationAudit) -> None:
        with self._lock:
            self._events.append(event)

    def events(self) -> tuple[ContentSafeAuthorizationAudit, ...]:
        with self._lock:
            return tuple(self._events)


class PermitUseStore:
    """Atomic one-time permit consumption for the in-process classroom model."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._consumed: set[str] = set()

    def consume_once(self, permit_id: str) -> bool:
        with self._lock:
            if permit_id in self._consumed:
                return False
            self._consumed.add(permit_id)
            return True


@dataclass(frozen=True)
class AuthorizedEmbeddingInput:
    tenant_id: str
    document_id: str
    document_version_id: str
    chunk_set_id: str
    chunks: tuple[AuthorizedChunkView, ...]
    authorization_decision_id: str
    authorization_revisions: AuthorizationRevisionVector
    authorization_epoch: int
    protected_data_classification: str = "PROTECTED"


class GuardedChunkReader:
    """PEP: verify current state immediately before releasing minimal content."""

    def __init__(
        self,
        *,
        issuer: PermitIssuer,
        state_store: InMemoryAuthorizationStateStore,
        provenance_validator: CurrentRAGProvenanceValidator,
        permit_uses: PermitUseStore,
        audit_sink: ContentSafeAuditSink,
        clock: Callable[[], int],
    ) -> None:
        self._issuer = issuer
        self._state = state_store
        self._provenance = provenance_validator
        self._permit_uses = permit_uses
        self._audit = audit_sink
        self._clock = clock

    def read(
        self,
        *,
        permit: SignedPermit,
        principal: AuthenticatedPrincipal,
        expected_action: str,
        expected_audience: str,
        expected_purpose: str,
    ) -> GuardedReadResult:
        claims = permit.claims
        if not self._issuer.verify_signature(permit):
            return self._deny(permit, "PERMIT_SIGNATURE_INVALID")
        if (
            claims.subject != principal.subject
            or claims.action != expected_action
            or claims.audience != expected_audience
            or claims.purpose != expected_purpose
        ):
            return self._deny(permit, "PERMIT_CONTEXT_BINDING_MISMATCH")
        now = self._clock()
        if claims.issued_at > now or claims.expires_at <= now:
            return self._deny(permit, "PERMIT_EXPIRED_OR_NOT_YET_VALID")
        if principal.expires_at is not None and principal.expires_at <= now:
            return self._deny(permit, "AUTHENTICATED_PRINCIPAL_EXPIRED")

        provenance = self._provenance.evaluate(
            document=DocumentIdentity(claims.tenant_id, claims.document_id),
            expected_chunk_set_id=claims.chunk_set_id,
        )
        if not provenance.valid or provenance.binding is None:
            return self._deny(permit, "CURRENT_RESOURCE_BINDING_CHANGED")
        binding = provenance.binding
        if (
            binding.version.document_version_id != claims.document_version_id
            or binding.selection_revision != claims.selection_revision
            or binding.document_state_version != claims.document_state_version
            or binding.document_fence != claims.document_fence
            or not set(claims.chunk_ids).issubset(binding.chunk_ids)
        ):
            return self._deny(permit, "PERMIT_RESOURCE_REVISION_MISMATCH")

        try:
            membership = self._state.read_membership(
                claims.tenant_id,
                claims.subject,
            )
            policy = self._state.read_policy(
                claims.tenant_id,
                claims.document_id,
            )
        except AuthorizationStateUnavailable:
            return self._indeterminate(permit)
        if membership is None or policy is None or not membership.active:
            return self._deny(permit, "CURRENT_AUTHORIZATION_NOT_ACCESSIBLE")
        current = AuthorizationRevisionVector(
            policy_revision=policy.policy_revision,
            acl_revision=policy.acl_revision,
            membership_revision=membership.revision,
            role_version=policy.role_version,
            action_catalog_version=policy.action_catalog_version,
            authorization_epoch=policy.authorization_epoch,
        )
        if current != claims.revisions:
            return self._deny(permit, "PERMIT_AUTHORIZATION_REVISION_MISMATCH")
        if not self._permit_uses.consume_once(claims.permit_id):
            return self._deny(permit, "PERMIT_ALREADY_CONSUMED")

        assert provenance.chunk_set is not None
        by_id = {
            chunk.chunk_id: chunk for chunk in provenance.chunk_set.chunks
        }
        views = tuple(
            AuthorizedChunkView(
                chunk_id=chunk_id,
                text=by_id[chunk_id].candidate.text,
                content_hash=by_id[chunk_id].candidate.content_hash,
                source_segments=by_id[chunk_id].candidate.source_segments,
            )
            for chunk_id in claims.chunk_ids
        )
        result = GuardedReadResult(
            GuardedReadOutcome.RELEASED,
            "PERMIT_AND_CURRENT_STATE_VALID",
            "Authorized",
            200,
            claims.decision_id,
            views,
        )
        self._record(permit, result)
        return result

    def embedding_handoff(
        self,
        *,
        permit: SignedPermit,
        result: GuardedReadResult,
    ) -> AuthorizedEmbeddingInput:
        if (
            not result.released
            or permit.claims.action != "chunk:read_for_embedding"
        ):
            raise ValueError("Day98 requires an authorized embedding read")
        claims = permit.claims
        return AuthorizedEmbeddingInput(
            tenant_id=claims.tenant_id,
            document_id=claims.document_id,
            document_version_id=claims.document_version_id,
            chunk_set_id=claims.chunk_set_id,
            chunks=result.chunks,
            authorization_decision_id=claims.decision_id,
            authorization_revisions=claims.revisions,
            authorization_epoch=claims.revisions.authorization_epoch,
        )

    def _deny(self, permit: SignedPermit, reason: str) -> GuardedReadResult:
        result = GuardedReadResult(
            GuardedReadOutcome.DENIED,
            reason,
            "Resource not found or inaccessible",
            404,
            permit.claims.decision_id,
        )
        self._record(permit, result)
        return result

    def _indeterminate(self, permit: SignedPermit) -> GuardedReadResult:
        result = GuardedReadResult(
            GuardedReadOutcome.INDETERMINATE,
            "AUTHORIZATION_STATE_UNAVAILABLE",
            "Service unavailable",
            503,
            permit.claims.decision_id,
        )
        self._record(permit, result)
        return result

    def _record(
        self,
        permit: SignedPermit,
        result: GuardedReadResult,
    ) -> None:
        claims = permit.claims
        self._audit.record(ContentSafeAuthorizationAudit(
            decision_id=claims.decision_id,
            permit_id_hash=self._safe_hash(claims.permit_id),
            principal_subject_hash=self._safe_hash(claims.subject),
            outcome=result.outcome.value,
            reason_code=result.internal_reason_code,
            action=claims.action,
            chunk_count=len(result.chunks),
        ))

    @staticmethod
    def _safe_hash(value: str) -> str:
        return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
