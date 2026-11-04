"""Rank-based Day101 fusion across already-authorized Day100 results."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from rag_chunking_contracts import stable_hash
from rag_multi_query_retrieval import MultiQueryRetrievalReport
from rag_retrieval_contracts import AuthorizedRetrievalHit, CandidateIdentity


class MultiQueryFusionError(RuntimeError):
    pass


@dataclass(frozen=True)
class MultiQueryFusionPolicy:
    policy_version: str
    rrf_k: int
    max_unique_candidates: int

    def __post_init__(self) -> None:
        if not self.policy_version or min(self.rrf_k, self.max_unique_candidates) <= 0:
            raise ValueError("multi-query fusion policy budgets are required")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class VariantRankEvidence:
    variant_id: str
    variant_ordinal: int
    rank: int
    day100_rrf_score: float


@dataclass(frozen=True)
class MultiQueryCandidate:
    identity: CandidateIdentity
    source_hit: AuthorizedRetrievalHit
    fused_score: float
    best_variant_rank: int
    evidence: tuple[VariantRankEvidence, ...]

    def __post_init__(self) -> None:
        if (
            self.source_hit.identity != self.identity
            or self.fused_score <= 0
            or self.best_variant_rank <= 0
            or not self.evidence
        ):
            raise ValueError("multi-query candidate requires consistent rank evidence")


@dataclass(frozen=True)
class MultiQueryCandidatePool:
    rewrite_set_fingerprint: str
    fusion_policy_fingerprint: str
    candidates: tuple[MultiQueryCandidate, ...]
    truncated: bool

    @property
    def digest(self) -> str:
        return stable_hash((
            self.rewrite_set_fingerprint,
            self.fusion_policy_fingerprint,
            tuple((
                item.identity.occurrence_id,
                item.identity.provenance_fingerprint,
                item.identity.content_hash,
                item.fused_score,
                item.best_variant_rank,
                tuple(asdict(evidence) for evidence in item.evidence),
            ) for item in self.candidates),
            self.truncated,
        ))


def fuse_multi_query_results(
    report: MultiQueryRetrievalReport,
    policy: MultiQueryFusionPolicy,
) -> MultiQueryCandidatePool:
    grouped: dict[str, tuple[CandidateIdentity, AuthorizedRetrievalHit, list[VariantRankEvidence]]] = {}
    for result in report.results:
        for hit in result.response.hits:
            key = hit.identity.occurrence_id
            evidence = VariantRankEvidence(
                result.variant.variant_id,
                result.variant.ordinal,
                hit.rank,
                hit.rrf_score,
            )
            existing = grouped.get(key)
            if existing is None:
                grouped[key] = (hit.identity, hit, [evidence])
            else:
                identity, source_hit, values = existing
                if identity != hit.identity:
                    raise MultiQueryFusionError(
                        "MULTI_QUERY_OCCURRENCE_IDENTITY_CONFLICT"
                    )
                values.append(evidence)
                grouped[key] = (identity, source_hit, values)

    values: list[MultiQueryCandidate] = []
    for identity, source_hit, evidence in grouped.values():
        ordered_evidence = tuple(sorted(
            evidence, key=lambda item: (item.variant_ordinal, item.rank)
        ))
        score = sum(1.0 / (policy.rrf_k + item.rank) for item in ordered_evidence)
        values.append(MultiQueryCandidate(
            identity,
            source_hit,
            score,
            min(item.rank for item in ordered_evidence),
            ordered_evidence,
        ))
    values.sort(key=lambda item: (
        -item.fused_score,
        item.best_variant_rank,
        item.identity.occurrence_id,
    ))
    truncated = len(values) > policy.max_unique_candidates
    return MultiQueryCandidatePool(
        report.rewrite_set_fingerprint,
        policy.fingerprint,
        tuple(values[:policy.max_unique_candidates]),
        truncated,
    )
