"""Deterministic rank-only Day100 hybrid fusion."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from rag_retrieval_contracts import (
    BranchCandidate,
    CandidateIdentity,
    FusedCandidate,
    FusionPolicy,
    RetrievalBranch,
)


class FusionError(ValueError):
    pass


def reciprocal_rank_fusion(
    candidates: Iterable[BranchCandidate],
    *,
    policy: FusionPolicy,
) -> tuple[FusedCandidate, ...]:
    """Fuse ranks without pretending incomparable raw scores share a scale."""

    per_identity: dict[str, dict[RetrievalBranch, BranchCandidate]] = defaultdict(dict)
    identities: dict[str, CandidateIdentity] = {}
    for candidate in candidates:
        key = candidate.identity.key
        existing_identity = identities.get(key)
        if existing_identity is not None and existing_identity != candidate.identity:
            raise FusionError("OCCURRENCE_IDENTITY_CONFLICT")
        identities[key] = candidate.identity
        existing = per_identity[key].get(candidate.branch)
        if existing is None or candidate.branch_rank < existing.branch_rank:
            per_identity[key][candidate.branch] = candidate

    fused: list[FusedCandidate] = []
    for key, branches in per_identity.items():
        ordered = tuple(sorted(
            branches.values(),
            key=lambda item: (item.branch.value, item.branch_rank),
        ))
        score = 0.0
        for item in ordered:
            weight = (
                policy.lexical_weight
                if item.branch is RetrievalBranch.LEXICAL
                else policy.dense_weight
            )
            score += weight / (policy.rrf_k + item.branch_rank)
        fused.append(FusedCandidate(
            identities[key],
            score,
            min(item.branch_rank for item in ordered),
            ordered,
        ))
    fused.sort(key=lambda item: (
        -item.rrf_score,
        item.best_branch_rank,
        item.identity.occurrence_id,
    ))
    return tuple(fused)
