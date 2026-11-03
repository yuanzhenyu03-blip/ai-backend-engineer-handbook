"""Day100 exact dense reference and application-owned score semantics."""

from __future__ import annotations

from enum import Enum
import math

from rag_query_encoder import EncodedQuery
from rag_retrieval_contracts import (
    BranchCandidate,
    RetrievalAuthorizationScope,
    RetrievalBranch,
    RetrievalRecord,
    ScoreDirection,
    SelectedRetrievalBundle,
)
from rag_retrieval_filters import (
    FilterExpression,
    authorized_and_business_match,
)


class DenseMode(str, Enum):
    NORMAL = "NORMAL"
    TIMEOUT = "TIMEOUT"
    LEAK_UNAUTHORIZED = "LEAK_UNAUTHORIZED"


class DenseRetrievalError(RuntimeError):
    pass


def cosine_similarity(
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> float:
    if len(left) != len(right) or not left:
        raise DenseRetrievalError("DENSE_VECTOR_DIMENSIONS_MISMATCH")
    if any(not math.isfinite(value) for value in left + right):
        raise DenseRetrievalError("DENSE_VECTOR_NON_FINITE")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise DenseRetrievalError("DENSE_ZERO_VECTOR")
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


class ExactDenseRetrievalAdapter:
    """Exhaustive classroom reference; this is not ANN evidence."""

    def __init__(
        self,
        records: tuple[RetrievalRecord, ...],
        *,
        mode: DenseMode = DenseMode.NORMAL,
    ) -> None:
        if not records:
            raise ValueError("exact dense reference requires records")
        self.records = records
        self.mode = mode
        self.database_calls = 0

    def search(
        self,
        *,
        encoded_query: EncodedQuery,
        bundle: SelectedRetrievalBundle,
        scope: RetrievalAuthorizationScope,
        business_filter: FilterExpression | None,
        system_excluded_occurrence_ids: tuple[str, ...],
        offset: int,
        limit: int,
    ) -> tuple[BranchCandidate, ...]:
        if (
            encoded_query.contract_fingerprint
            != bundle.query_encoder.fingerprint
        ):
            raise DenseRetrievalError("DENSE_QUERY_ENCODER_CONTRACT_MISMATCH")
        if len(encoded_query.vector) != bundle.query_encoder.dimensions:
            raise DenseRetrievalError("DENSE_QUERY_DIMENSIONS_MISMATCH")
        if scope.tenant_id != bundle.tenant_id:
            raise DenseRetrievalError("DENSE_SCOPE_TENANT_MISMATCH")
        if offset < 0 or limit <= 0:
            raise DenseRetrievalError("DENSE_PAGE_BOUNDS_INVALID")
        self.database_calls += 1
        if self.mode is DenseMode.TIMEOUT:
            raise DenseRetrievalError("DENSE_READ_TIMEOUT")
        scored: list[tuple[float, RetrievalRecord]] = []
        unauthorized: list[tuple[float, RetrievalRecord]] = []
        for record in self.records:
            score = cosine_similarity(encoded_query.vector, record.embedding)
            allowed = authorized_and_business_match(
                scope=scope,
                occurrence_id=record.identity.occurrence_id,
                metadata=record.metadata_dict,
                business_filter=business_filter,
                system_excluded_occurrence_ids=system_excluded_occurrence_ids,
            )
            if allowed:
                scored.append((score, record))
            elif self.mode is DenseMode.LEAK_UNAUTHORIZED:
                unauthorized.append((score, record))
        if self.mode is DenseMode.LEAK_UNAUTHORIZED and unauthorized:
            scored.append(max(unauthorized, key=lambda item: item[0]))
        scored.sort(key=lambda item: (-item[0], item[1].identity.occurrence_id))
        page = scored[offset: offset + limit]
        return tuple(
            BranchCandidate(
                identity=record.identity,
                branch=RetrievalBranch.DENSE,
                branch_rank=offset + index + 1,
                raw_score=score,
                score_direction=ScoreDirection.HIGHER_IS_BETTER,
                generation_id=bundle.generation_id,
                corpus_generation_id=bundle.lexical_corpus_generation_id,
                bundle_fingerprint=bundle.fingerprint,
                metadata=record.metadata,
            )
            for index, (score, record) in enumerate(page)
        )
