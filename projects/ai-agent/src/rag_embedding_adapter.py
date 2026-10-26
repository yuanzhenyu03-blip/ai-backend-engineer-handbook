"""Application-owned embedding port and deterministic fake Provider adapter."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import math
from typing import Protocol

from rag_embedding_contracts import (
    EmbeddingBatch,
    EmbeddingContract,
    ModelIdentity,
    ProviderEmbeddingCandidate,
    ProviderEmbeddingItem,
    UsageConfidence,
)


class FakeResponseMode(str, Enum):
    NORMAL = "NORMAL"
    REVERSED = "REVERSED"
    MISSING = "MISSING"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"
    WRONG_MODEL = "WRONG_MODEL"
    WRONG_DIMENSION = "WRONG_DIMENSION"
    NAN = "NAN"
    INFINITY = "INFINITY"
    ZERO = "ZERO"
    WRONG_TYPE = "WRONG_TYPE"
    WRONG_SCHEMA = "WRONG_SCHEMA"
    WRONG_USAGE = "WRONG_USAGE"
    PERTURBED_VALID = "PERTURBED_VALID"
    PARTIAL = "PARTIAL"
    TIMEOUT_UNKNOWN = "TIMEOUT_UNKNOWN"
    PROVEN_NOT_EXECUTED = "PROVEN_NOT_EXECUTED"
    RATE_LIMITED = "RATE_LIMITED"


class ProviderDispatchError(RuntimeError):
    def __init__(self, reason: str, *, execution_state: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.execution_state = execution_state


class EmbeddingProviderPort(Protocol):
    def embed(
        self,
        *,
        batch: EmbeddingBatch,
        contract: EmbeddingContract,
        request_id: str,
    ) -> ProviderEmbeddingCandidate: ...


@dataclass(frozen=True)
class ProviderCallObservation:
    batch_id: str
    item_count: int
    input_tokens: int
    input_utf8_bytes: int
    latency_ms: float
    cost_microunits: int


class DeterministicFakeEmbeddingAdapter:
    """Produces controlled proposals; it proves control flow, not model quality."""

    def __init__(self, mode: FakeResponseMode = FakeResponseMode.NORMAL) -> None:
        self.mode = mode
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.observations: list[ProviderCallObservation] = []

    def embed(
        self,
        *,
        batch: EmbeddingBatch,
        contract: EmbeddingContract,
        request_id: str,
    ) -> ProviderEmbeddingCandidate:
        self.calls.append((batch.batch_id, tuple(item.chunk_id for item in batch.items)))
        observation = ProviderCallObservation(
            batch.batch_id,
            len(batch.items),
            batch.total_tokens,
            batch.total_utf8_bytes,
            5.0 + batch.ordinal,
            batch.total_tokens * 2,
        )
        self.observations.append(observation)
        if self.mode is FakeResponseMode.TIMEOUT_UNKNOWN:
            raise ProviderDispatchError(
                "TIMEOUT_AFTER_DISPATCH", execution_state="UNKNOWN"
            )
        if self.mode is FakeResponseMode.PROVEN_NOT_EXECUTED:
            raise ProviderDispatchError(
                "CONNECT_FAILED_BEFORE_DISPATCH",
                execution_state="PROVEN_NOT_EXECUTED",
            )
        if self.mode is FakeResponseMode.RATE_LIMITED:
            raise ProviderDispatchError(
                "RATE_LIMITED", execution_state="PROVEN_NOT_EXECUTED"
            )

        items = [ProviderEmbeddingItem(
            item.chunk_id,
            self._vector(item.chunk_id, contract.dimensions),
        ) for item in batch.items]
        if self.mode is FakeResponseMode.REVERSED:
            items.reverse()
        elif self.mode is FakeResponseMode.MISSING:
            items = items[:-1]
        elif self.mode is FakeResponseMode.DUPLICATE:
            items[-1] = items[0]
        elif self.mode is FakeResponseMode.UNKNOWN:
            items[-1] = ProviderEmbeddingItem("chunk:unknown", items[-1].vector)
        elif self.mode is FakeResponseMode.WRONG_DIMENSION:
            items[-1] = ProviderEmbeddingItem(items[-1].item_id, items[-1].vector[:-1])
        elif self.mode is FakeResponseMode.NAN:
            items[-1] = ProviderEmbeddingItem(items[-1].item_id, (math.nan,) + items[-1].vector[1:])
        elif self.mode is FakeResponseMode.INFINITY:
            items[-1] = ProviderEmbeddingItem(items[-1].item_id, (math.inf,) + items[-1].vector[1:])
        elif self.mode is FakeResponseMode.ZERO:
            items[-1] = ProviderEmbeddingItem(items[-1].item_id, (0.0,) * contract.dimensions)
        elif self.mode is FakeResponseMode.WRONG_TYPE:
            unsafe = ("not-a-number",) + items[-1].vector[1:]
            items[-1] = ProviderEmbeddingItem(items[-1].item_id, unsafe)  # type: ignore[arg-type]
        elif self.mode is FakeResponseMode.PERTURBED_VALID:
            items = [ProviderEmbeddingItem(
                item.item_id,
                tuple(-value for value in item.vector),
            ) for item in items]
        model = contract.model
        if self.mode is FakeResponseMode.WRONG_MODEL:
            model = ModelIdentity(
                model.provider,
                model.model_id,
                model.immutable_revision + "-different",
                model.deployment,
            )
        return ProviderEmbeddingCandidate(
            request_id=request_id,
            batch_id=batch.batch_id,
            model=model,
            response_schema_version=(
                "embedding-response.different"
                if self.mode is FakeResponseMode.WRONG_SCHEMA
                else contract.response_schema_version
            ),
            items=tuple(items),
            usage_tokens=(
                sum(item.token_count for item in batch.items) + 1
                if self.mode is FakeResponseMode.WRONG_USAGE
                else sum(item.token_count for item in batch.items)
            ),
            usage_confidence=UsageConfidence.EXACT,
            latency_ms=observation.latency_ms,
            cost_microunits=observation.cost_microunits,
            cost_confidence=UsageConfidence.ESTIMATED,
            partial=self.mode is FakeResponseMode.PARTIAL,
        )

    @staticmethod
    def _vector(item_id: str, dimensions: int) -> tuple[float, ...]:
        values: list[float] = []
        counter = 0
        while len(values) < dimensions:
            digest = hashlib.sha256(f"{item_id}:{counter}".encode()).digest()
            values.extend((byte / 127.5) - 1.0 for byte in digest)
            counter += 1
        values = values[:dimensions]
        norm = math.sqrt(sum(value * value for value in values))
        return tuple(value / norm for value in values)
