"""Day100 selected-bundle and branch-candidate validation boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from rag_retrieval_contracts import (
    BranchCandidate,
    RetrievalAuthorizationScope,
    SelectedRetrievalBundle,
)


class InMemoryRetrievalBundleAuthority:
    """Application authority; Provider aliases and client hints are not truth."""

    def __init__(self) -> None:
        self._selected: dict[str, SelectedRetrievalBundle] = {}

    def select(self, bundle: SelectedRetrievalBundle) -> None:
        current = self._selected.get(bundle.tenant_id)
        if current is not None and bundle.revision <= current.revision:
            raise ValueError("selected retrieval bundle revision must advance")
        self._selected[bundle.tenant_id] = bundle

    def read_selected(self, tenant_id: str) -> SelectedRetrievalBundle | None:
        return self._selected.get(tenant_id)


@dataclass(frozen=True)
class RejectedCandidate:
    occurrence_id: str
    reason: str


@dataclass(frozen=True)
class CandidateValidationReport:
    accepted: tuple[BranchCandidate, ...]
    rejected: tuple[RejectedCandidate, ...]

    @property
    def contract_violation(self) -> bool:
        return bool(self.rejected)


class RetrievalCandidateValidator:
    def validate(
        self,
        *,
        candidates: Iterable[BranchCandidate],
        bundle: SelectedRetrievalBundle,
        scope: RetrievalAuthorizationScope,
    ) -> CandidateValidationReport:
        accepted: list[BranchCandidate] = []
        rejected: list[RejectedCandidate] = []
        allowed = frozenset(scope.allowed_occurrence_ids)
        for candidate in candidates:
            identity = candidate.identity
            reason: str | None = None
            if candidate.bundle_fingerprint != bundle.fingerprint:
                reason = "CANDIDATE_BUNDLE_MISMATCH"
            elif candidate.generation_id != bundle.generation_id:
                reason = "CANDIDATE_VECTOR_GENERATION_MISMATCH"
            elif (
                candidate.corpus_generation_id
                != bundle.lexical_corpus_generation_id
            ):
                reason = "CANDIDATE_LEXICAL_GENERATION_MISMATCH"
            elif identity.tenant_id != bundle.tenant_id:
                reason = "CROSS_TENANT_CANDIDATE"
            elif identity.chunk_set_id != bundle.chunk_set_id:
                reason = "CANDIDATE_CHUNK_SET_MISMATCH"
            elif identity.occurrence_id not in allowed:
                reason = "CANDIDATE_OUTSIDE_AUTHORIZATION_SCOPE"
            elif candidate.metadata_dict.get("tenant_id") != scope.tenant_id:
                reason = "CANDIDATE_METADATA_TENANT_MISMATCH"
            if reason is None:
                accepted.append(candidate)
            else:
                rejected.append(RejectedCandidate(identity.occurrence_id, reason))
        return CandidateValidationReport(tuple(accepted), tuple(rejected))
