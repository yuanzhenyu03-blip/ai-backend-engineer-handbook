"""Deterministic, tenant-scoped Day99 vector write planning."""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_chunking_contracts import stable_hash
from rag_vector_contracts import VectorIndexContract, VectorPoint


class VectorBatchPlanError(ValueError):
    pass


@dataclass(frozen=True)
class VectorWriteBatch:
    batch_id: str
    ordinal: int
    tenant_id: str
    generation_id: str
    namespace: str
    points: tuple[VectorPoint, ...] = field(repr=False)
    estimated_bytes: int


@dataclass(frozen=True)
class VectorBatchPlan:
    operation_id: str
    batches: tuple[VectorWriteBatch, ...]
    point_count: int
    checksum: str


def _point_size(point: VectorPoint) -> int:
    payload_bytes = sum(
        len(key.encode("utf-8")) + len(value.encode("utf-8"))
        for key, value in point.payload
    )
    identity_bytes = sum(len(value.encode("utf-8")) for value in (
        point.point_id,
        point.generation_id,
        point.tenant_id,
        point.embedding_id,
        point.chunk_id,
    ))
    return identity_bytes + payload_bytes + 4 * len(point.vector)


def plan_vector_batches(
    points: tuple[VectorPoint, ...],
    *,
    contract: VectorIndexContract,
    operation_id: str,
) -> VectorBatchPlan:
    if not points:
        raise VectorBatchPlanError("EMPTY_VECTOR_BUILD_INPUT")
    ordered = tuple(sorted(points, key=lambda point: point.point_id))
    if len({point.point_id for point in ordered}) != len(ordered):
        raise VectorBatchPlanError("DUPLICATE_VECTOR_POINT_ID")
    tenant_ids = {point.tenant_id for point in ordered}
    generation_ids = {point.generation_id for point in ordered}
    if tenant_ids != {contract.tenant_id} or len(generation_ids) != 1:
        raise VectorBatchPlanError("CROSS_TENANT_OR_GENERATION_BATCH_INPUT")
    generation_id = ordered[0].generation_id
    namespace = stable_hash((
        contract.namespace_schema_version,
        contract.tenant_id,
        generation_id,
        contract.fingerprint,
    ))
    batches: list[VectorWriteBatch] = []
    pending: list[VectorPoint] = []
    pending_bytes = 0

    def flush() -> None:
        nonlocal pending, pending_bytes
        if not pending:
            return
        ordinal = len(batches)
        ids = tuple(point.point_id for point in pending)
        batch_id = "vector-batch:" + stable_hash((
            operation_id,
            ordinal,
            contract.fingerprint,
            ids,
        )).removeprefix("sha256:")
        batches.append(VectorWriteBatch(
            batch_id=batch_id,
            ordinal=ordinal,
            tenant_id=contract.tenant_id,
            generation_id=generation_id,
            namespace=namespace,
            points=tuple(pending),
            estimated_bytes=pending_bytes,
        ))
        pending = []
        pending_bytes = 0

    for point in ordered:
        point_bytes = _point_size(point)
        if point_bytes > contract.batch_max_bytes:
            raise VectorBatchPlanError(
                f"SINGLE_VECTOR_POINT_EXCEEDS_BATCH_LIMIT:{point.point_id}"
            )
        if pending and (
            len(pending) + 1 > contract.batch_max_items
            or pending_bytes + point_bytes > contract.batch_max_bytes
        ):
            flush()
        pending.append(point)
        pending_bytes += point_bytes
    flush()
    checksum = stable_hash(tuple(
        (
            batch.batch_id,
            batch.ordinal,
            batch.tenant_id,
            batch.generation_id,
            batch.namespace,
            tuple(point.point_id for point in batch.points),
            batch.estimated_bytes,
        )
        for batch in batches
    ))
    plan = VectorBatchPlan(operation_id, tuple(batches), len(ordered), checksum)
    validate_batch_plan(plan, expected_points=ordered)
    return plan


def validate_batch_plan(
    plan: VectorBatchPlan,
    *,
    expected_points: tuple[VectorPoint, ...],
) -> None:
    if not plan.batches:
        raise VectorBatchPlanError("MISSING_VECTOR_BATCH")
    batch_ids = tuple(batch.batch_id for batch in plan.batches)
    if len(set(batch_ids)) != len(batch_ids):
        raise VectorBatchPlanError("DUPLICATE_VECTOR_BATCH_ID")
    if tuple(batch.ordinal for batch in plan.batches) != tuple(
        range(len(plan.batches))
    ):
        raise VectorBatchPlanError("NON_CANONICAL_VECTOR_BATCH_ORDINAL")
    flattened = tuple(point for batch in plan.batches for point in batch.points)
    expected = tuple(sorted(expected_points, key=lambda point: point.point_id))
    if flattened != expected or plan.point_count != len(expected):
        raise VectorBatchPlanError("MISSING_OR_UNKNOWN_VECTOR_BATCH_POINT")
    for batch in plan.batches:
        if any(
            point.tenant_id != batch.tenant_id
            or point.generation_id != batch.generation_id
            for point in batch.points
        ):
            raise VectorBatchPlanError("CROSS_TENANT_OR_GENERATION_BATCH")
