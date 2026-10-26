"""Deterministic Day98 provider batch planner."""

from __future__ import annotations

from rag_chunking_contracts import stable_hash
from rag_embedding_contracts import BatchLimits, EmbeddingBatch, EmbeddingItem


class BatchPlanError(ValueError):
    pass


def plan_batches(
    items: tuple[EmbeddingItem, ...],
    *,
    limits: BatchLimits,
    operation_id: str,
) -> tuple[EmbeddingBatch, ...]:
    """Split only between chunks while preserving exact source order."""

    if not items:
        raise BatchPlanError("EMPTY_EMBEDDING_INPUT")
    batches: list[EmbeddingBatch] = []
    pending: list[EmbeddingItem] = []
    tokens = 0
    utf8_bytes = 0

    def flush() -> None:
        nonlocal pending, tokens, utf8_bytes
        if not pending:
            return
        ordinal = len(batches)
        batch_id = "embedding-batch:" + stable_hash((
            operation_id,
            ordinal,
            tuple(item.chunk_id for item in pending),
        )).removeprefix("sha256:")
        batches.append(EmbeddingBatch(
            batch_id,
            ordinal,
            tuple(pending),
            tokens,
            utf8_bytes,
        ))
        pending = []
        tokens = 0
        utf8_bytes = 0

    for item in items:
        if (
            item.token_count > limits.max_tokens
            or item.utf8_bytes > limits.max_utf8_bytes
        ):
            raise BatchPlanError(
                f"SINGLE_CHUNK_EXCEEDS_BATCH_LIMIT:{item.chunk_id}"
            )
        would_overflow = pending and (
            len(pending) + 1 > limits.max_items
            or tokens + item.token_count > limits.max_tokens
            or utf8_bytes + item.utf8_bytes > limits.max_utf8_bytes
        )
        if would_overflow:
            flush()
        pending.append(item)
        tokens += item.token_count
        utf8_bytes += item.utf8_bytes
    flush()
    flattened = tuple(item.chunk_id for batch in batches for item in batch.items)
    if flattened != tuple(item.chunk_id for item in items):
        raise AssertionError("batch planner changed exact Chunk order")
    return tuple(batches)
