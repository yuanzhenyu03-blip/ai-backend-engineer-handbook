"""Day99 Provider port, exact reference and typed score Adapter."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Protocol

from rag_chunking_contracts import stable_hash
from rag_vector_contracts import (
    ApplicationVectorHit,
    VectorIndexContract,
    VectorPoint,
)
from rag_vector_index_planner import VectorBatchPlan


class FakeVectorMode(str, Enum):
    NORMAL = "NORMAL"
    ACK_ONLY = "ACK_ONLY"
    PARTIAL_WRITE = "PARTIAL_WRITE"
    MISSING_ACK = "MISSING_ACK"
    DUPLICATE_ACK = "DUPLICATE_ACK"
    UNKNOWN_ACK = "UNKNOWN_ACK"
    WRONG_GENERATION_ACK = "WRONG_GENERATION_ACK"
    WRONG_NAMESPACE_ACK = "WRONG_NAMESPACE_ACK"
    WRONG_TENANT_ACK = "WRONG_TENANT_ACK"
    STALE_REQUEST_ACK = "STALE_REQUEST_ACK"
    REVERSED_ACKS = "REVERSED_ACKS"
    WRONG_VECTOR = "WRONG_VECTOR"
    WRONG_PAYLOAD = "WRONG_PAYLOAD"
    CROSS_TENANT_POINT = "CROSS_TENANT_POINT"
    WRONG_QUERY_ORDER = "WRONG_QUERY_ORDER"
    TIMEOUT_UNKNOWN = "TIMEOUT_UNKNOWN"


class VectorProviderError(RuntimeError):
    def __init__(self, reason: str, *, execution_state: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.execution_state = execution_state


@dataclass(frozen=True)
class ProviderWriteAck:
    generation_id: str
    namespace: str
    tenant_id: str
    request_id: str
    batch_id: str
    accepted_point_ids: tuple[str, ...]
    operation_id: str
    checkpoint: str


@dataclass(frozen=True)
class ProviderReadback:
    generation_id: str
    points: tuple[VectorPoint, ...]
    checkpoint: str


@dataclass(frozen=True)
class ProviderRawHit:
    point_id: str
    chunk_id: str
    cosine_distance: float
    generation_id: str


class VectorProviderPort(Protocol):
    def replace_generation(
        self,
        *,
        generation_id: str,
        contract: VectorIndexContract,
        plan: VectorBatchPlan,
        operation_id: str,
        request_id: str,
        fence: int,
    ) -> tuple[ProviderWriteAck, ...]: ...

    def readback(self, generation_id: str) -> ProviderReadback: ...

    def query_raw(
        self,
        *,
        generation_id: str,
        query_vector: tuple[float, ...],
        tenant_id: str,
        top_k: int,
    ) -> tuple[ProviderRawHit, ...]: ...


def cosine_similarity(
    left: tuple[float, ...], right: tuple[float, ...]
) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("vectors must have the same positive dimension")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise ValueError("cosine similarity is undefined for zero vectors")
    similarity = sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )
    return max(-1.0, min(1.0, similarity))


class ApplicationVectorAdapter:
    """Translates Provider-private distance into application similarity."""

    def __init__(self, provider: VectorProviderPort) -> None:
        self._provider = provider

    def search(
        self,
        *,
        generation_id: str,
        query_vector: tuple[float, ...],
        tenant_id: str,
        top_k: int,
    ) -> tuple[ApplicationVectorHit, ...]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        raw = self._provider.query_raw(
            generation_id=generation_id,
            query_vector=query_vector,
            tenant_id=tenant_id,
            top_k=top_k,
        )
        if len({item.point_id for item in raw}) != len(raw):
            raise ValueError("Provider returned duplicate point identities")
        hits: list[ApplicationVectorHit] = []
        for item in raw:
            if item.generation_id != generation_id:
                raise ValueError("Provider generation correlation mismatch")
            if (
                not math.isfinite(item.cosine_distance)
                or item.cosine_distance < -1e-12
                or item.cosine_distance > 2.0 + 1e-12
            ):
                raise ValueError("Provider cosine distance is invalid")
            similarity = max(-1.0, min(1.0, 1.0 - item.cosine_distance))
            hits.append(ApplicationVectorHit(
                point_id=item.point_id,
                chunk_id=item.chunk_id,
                similarity=similarity,
                generation_id=item.generation_id,
            ))
        return tuple(hits)


class ExactFlatReference:
    @staticmethod
    def search(
        *,
        points: tuple[VectorPoint, ...],
        query_vector: tuple[float, ...],
        tenant_id: str,
        top_k: int,
    ) -> tuple[ApplicationVectorHit, ...]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        hits = [ApplicationVectorHit(
            point.point_id,
            point.chunk_id,
            cosine_similarity(query_vector, point.vector),
            point.generation_id,
        ) for point in points if point.tenant_id == tenant_id]
        hits.sort(key=lambda item: (-item.similarity, item.point_id))
        return tuple(hits[:top_k])


class DeterministicFakeVectorProvider:
    """Process-local fake; never evidence of a real DB or ANN implementation."""

    def __init__(self, mode: FakeVectorMode = FakeVectorMode.NORMAL) -> None:
        self.mode = mode
        self._generations: dict[str, tuple[VectorPoint, ...]] = {}
        self._fences: dict[str, int] = {}
        self.write_calls: list[tuple[str, str, int]] = []
        self.query_calls: list[tuple[str, str, int]] = []

    def replace_generation(
        self,
        *,
        generation_id: str,
        contract: VectorIndexContract,
        plan: VectorBatchPlan,
        operation_id: str,
        request_id: str,
        fence: int,
    ) -> tuple[ProviderWriteAck, ...]:
        current_fence = self._fences.get(generation_id, 0)
        if fence < current_fence:
            raise VectorProviderError(
                "STALE_PROVIDER_FENCE", execution_state="PROVEN_NOT_EXECUTED"
            )
        self._fences[generation_id] = fence
        self.write_calls.append((generation_id, operation_id, fence))
        points = tuple(
            point for batch in plan.batches for point in batch.points
        )
        stored = points
        if self.mode is FakeVectorMode.ACK_ONLY:
            stored = ()
        elif self.mode is FakeVectorMode.PARTIAL_WRITE:
            stored = points[:-1]
        elif self.mode is FakeVectorMode.WRONG_VECTOR and points:
            first = points[0]
            stored = (replace(
                first,
                vector=tuple(-value for value in first.vector),
            ),) + points[1:]
        elif self.mode is FakeVectorMode.WRONG_PAYLOAD and points:
            first = points[0]
            payload = dict(first.payload)
            payload["tenant_id"] = "tenant-corrupted"
            stored = (replace(first, payload=tuple(sorted(payload.items()))),) + points[1:]
        elif self.mode is FakeVectorMode.CROSS_TENANT_POINT and points:
            first = points[0]
            payload = dict(first.payload)
            payload["tenant_id"] = "tenant-forbidden"
            stored = (replace(
                first,
                tenant_id="tenant-forbidden",
                payload=tuple(sorted(payload.items())),
            ),) + points[1:]
        self._generations[generation_id] = stored
        checkpoint = self._checkpoint(generation_id, fence, stored)
        if self.mode is FakeVectorMode.TIMEOUT_UNKNOWN:
            raise VectorProviderError(
                "TIMEOUT_AFTER_PROVIDER_WRITE", execution_state="UNKNOWN"
            )
        acknowledgements = [ProviderWriteAck(
            generation_id=generation_id,
            namespace=batch.namespace,
            tenant_id=contract.tenant_id,
            request_id=request_id,
            batch_id=batch.batch_id,
            accepted_point_ids=tuple(
                point.point_id for point in batch.points
            ),
            operation_id=operation_id,
            checkpoint=checkpoint,
        ) for batch in plan.batches]
        if self.mode is FakeVectorMode.PARTIAL_WRITE and acknowledgements:
            last = acknowledgements[-1]
            acknowledgements[-1] = replace(
                last,
                accepted_point_ids=last.accepted_point_ids[:-1],
            )
        elif self.mode is FakeVectorMode.MISSING_ACK:
            acknowledgements = acknowledgements[:-1]
        elif self.mode is FakeVectorMode.DUPLICATE_ACK and acknowledgements:
            acknowledgements.append(acknowledgements[0])
        elif self.mode is FakeVectorMode.UNKNOWN_ACK and acknowledgements:
            acknowledgements.append(replace(
                acknowledgements[0],
                batch_id="vector-batch:unknown",
            ))
        elif self.mode is FakeVectorMode.WRONG_GENERATION_ACK and acknowledgements:
            acknowledgements[0] = replace(
                acknowledgements[0], generation_id="generation-wrong"
            )
        elif self.mode is FakeVectorMode.WRONG_NAMESPACE_ACK and acknowledgements:
            acknowledgements[0] = replace(
                acknowledgements[0], namespace="namespace-wrong"
            )
        elif self.mode is FakeVectorMode.WRONG_TENANT_ACK and acknowledgements:
            acknowledgements[0] = replace(
                acknowledgements[0], tenant_id="tenant-wrong"
            )
        elif self.mode is FakeVectorMode.STALE_REQUEST_ACK and acknowledgements:
            acknowledgements[0] = replace(
                acknowledgements[0], request_id="request-stale"
            )
        elif self.mode is FakeVectorMode.REVERSED_ACKS:
            acknowledgements.reverse()
        return tuple(acknowledgements)

    def readback(self, generation_id: str) -> ProviderReadback:
        points = self._generations.get(generation_id, ())
        fence = self._fences.get(generation_id, 0)
        return ProviderReadback(
            generation_id,
            points,
            self._checkpoint(generation_id, fence, points),
        )

    def query_raw(
        self,
        *,
        generation_id: str,
        query_vector: tuple[float, ...],
        tenant_id: str,
        top_k: int,
    ) -> tuple[ProviderRawHit, ...]:
        self.query_calls.append((generation_id, tenant_id, top_k))
        points = self._generations.get(generation_id, ())
        hits = [ProviderRawHit(
            point.point_id,
            point.chunk_id,
            1.0 - cosine_similarity(query_vector, point.vector),
            generation_id,
        ) for point in points if point.tenant_id == tenant_id]
        hits.sort(key=lambda item: (item.cosine_distance, item.point_id))
        if self.mode is FakeVectorMode.WRONG_QUERY_ORDER:
            hits.reverse()
        return tuple(hits[:top_k])

    @staticmethod
    def _checkpoint(
        generation_id: str,
        fence: int,
        points: tuple[VectorPoint, ...],
    ) -> str:
        canonical = tuple((
            point.point_id,
            point.generation_id,
            point.tenant_id,
            point.embedding_id,
            point.chunk_id,
            point.vector,
            point.payload,
        ) for point in sorted(points, key=lambda item: item.point_id))
        return stable_hash((generation_id, fence, canonical))
