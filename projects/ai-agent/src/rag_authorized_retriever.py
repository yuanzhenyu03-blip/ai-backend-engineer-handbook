"""Current authorization scope and guarded Day100 content-release boundary."""

from __future__ import annotations

from dataclasses import dataclass, replace
import threading

from rag_acl_contracts import AuthorizationRevisionVector
from rag_retrieval_contracts import (
    AuthorizedRetrievalHit,
    FusedCandidate,
    RetrievalAuthorizationScope,
    RetrievalRecord,
)


class RetrievalAuthorizationUnavailable(RuntimeError):
    pass


class InMemoryRetrievalAuthorization:
    """Deterministic current-state authority, not production policy storage."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._scopes: dict[tuple[str, str, str, str], RetrievalAuthorizationScope] = {}
        self._available = True

    def put(self, scope: RetrievalAuthorizationScope) -> None:
        with self._lock:
            self._scopes[self._key(scope)] = scope

    def read(
        self,
        *,
        tenant_id: str,
        principal_subject: str,
        action: str,
        purpose: str,
    ) -> RetrievalAuthorizationScope | None:
        with self._lock:
            if not self._available:
                raise RetrievalAuthorizationUnavailable(
                    "RETRIEVAL_AUTHORIZATION_STATE_UNAVAILABLE"
                )
            return self._scopes.get((tenant_id, principal_subject, action, purpose))

    def set_available(self, available: bool) -> None:
        with self._lock:
            self._available = available

    def revoke_occurrence(
        self,
        *,
        tenant_id: str,
        principal_subject: str,
        action: str,
        purpose: str,
        occurrence_id: str,
    ) -> RetrievalAuthorizationScope:
        with self._lock:
            key = (tenant_id, principal_subject, action, purpose)
            current = self._scopes[key]
            revisions = replace(
                current.revisions,
                acl_revision=current.revisions.acl_revision + 1,
                authorization_epoch=current.revisions.authorization_epoch + 1,
            )
            updated = replace(
                current,
                revisions=revisions,
                allowed_occurrence_ids=tuple(
                    item for item in current.allowed_occurrence_ids
                    if item != occurrence_id
                ),
                decision_id=current.decision_id + ":revoked",
            )
            self._scopes[key] = updated
            return updated

    @staticmethod
    def _key(scope: RetrievalAuthorizationScope) -> tuple[str, str, str, str]:
        return (
            scope.tenant_id,
            scope.principal_subject,
            scope.action,
            scope.purpose,
        )


class InMemoryProtectedRetrievalStore:
    def __init__(self, records: tuple[RetrievalRecord, ...]) -> None:
        self._records = {
            record.identity.occurrence_id: record for record in records
        }
        self._current_provenance = {
            record.identity.occurrence_id: record.identity.provenance_fingerprint
            for record in records
        }

    def read(self, occurrence_id: str) -> RetrievalRecord | None:
        return self._records.get(occurrence_id)

    def change_provenance(self, occurrence_id: str, fingerprint: str) -> None:
        self._current_provenance[occurrence_id] = fingerprint

    def provenance_is_current(self, candidate: FusedCandidate) -> bool:
        return self._current_provenance.get(
            candidate.identity.occurrence_id
        ) == candidate.identity.provenance_fingerprint


@dataclass(frozen=True)
class ReleaseRejection:
    occurrence_id: str
    reason: str


@dataclass(frozen=True)
class GuardedReleaseReport:
    hits: tuple[AuthorizedRetrievalHit, ...]
    rejected: tuple[ReleaseRejection, ...]
    current_scope: RetrievalAuthorizationScope


class GuardedRetrievalReleaser:
    """The only Day100 boundary allowed to return protected Chunk text."""

    def __init__(
        self,
        *,
        authorization: InMemoryRetrievalAuthorization,
        content: InMemoryProtectedRetrievalStore,
    ) -> None:
        self._authorization = authorization
        self._content = content

    def release(
        self,
        *,
        candidates: tuple[FusedCandidate, ...],
        initial_scope: RetrievalAuthorizationScope,
        limit: int,
    ) -> GuardedReleaseReport:
        current = self._authorization.read(
            tenant_id=initial_scope.tenant_id,
            principal_subject=initial_scope.principal_subject,
            action=initial_scope.action,
            purpose=initial_scope.purpose,
        )
        if current is None:
            raise RetrievalAuthorizationUnavailable(
                "CURRENT_RETRIEVAL_AUTHORIZATION_NOT_FOUND"
            )
        allowed = frozenset(current.allowed_occurrence_ids)
        hits: list[AuthorizedRetrievalHit] = []
        rejected: list[ReleaseRejection] = []
        for candidate in candidates:
            occurrence_id = candidate.identity.occurrence_id
            if occurrence_id not in allowed:
                rejected.append(ReleaseRejection(
                    occurrence_id, "CURRENT_AUTHORIZATION_REVOKED"
                ))
                continue
            if not self._content.provenance_is_current(candidate):
                rejected.append(ReleaseRejection(
                    occurrence_id, "CURRENT_PROVENANCE_CHANGED"
                ))
                continue
            record = self._content.read(occurrence_id)
            if record is None or record.identity != candidate.identity:
                rejected.append(ReleaseRejection(
                    occurrence_id, "CURRENT_CHUNK_OCCURRENCE_NOT_FOUND"
                ))
                continue
            hits.append(AuthorizedRetrievalHit(
                identity=candidate.identity,
                rank=len(hits) + 1,
                rrf_score=candidate.rrf_score,
                text=record.text,
                source_reference=(
                    record.identity.document_id + ":" + record.identity.chunk_id
                ),
            ))
            if len(hits) >= limit:
                break
        return GuardedReleaseReport(tuple(hits), tuple(rejected), current)


def classroom_authorization_revisions(
    *,
    policy_revision: int = 1,
    acl_revision: int = 1,
    membership_revision: int = 1,
    authorization_epoch: int = 1,
) -> AuthorizationRevisionVector:
    return AuthorizationRevisionVector(
        policy_revision=policy_revision,
        acl_revision=acl_revision,
        membership_revision=membership_revision,
        role_version="retrieval-role-v1",
        action_catalog_version="retrieval-actions-v1",
        authorization_epoch=authorization_epoch,
    )
