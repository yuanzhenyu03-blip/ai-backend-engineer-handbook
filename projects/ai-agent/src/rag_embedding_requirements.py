"""Frozen Day98 requirements and authorized input preprocessing gates."""

from __future__ import annotations

from dataclasses import dataclass

from rag_authorized_chunk_reader import AuthorizedEmbeddingInput
from rag_embedding_contracts import EmbeddingContract, EmbeddingItem
from rag_tokenizer_adapter import TokenizerPort


class EmbeddingEligibilityError(ValueError):
    """Input cannot enter provider execution or durable commit."""


class ReturnToDay96Required(EmbeddingEligibilityError):
    """An already committed Chunk exceeds the frozen model token contract."""


@dataclass(frozen=True)
class FrozenEmbeddingRequirements:
    version: str
    required_languages: tuple[str, ...]
    protected_data: bool
    exact_revision_required: bool = True
    tokenizer_revision_required: bool = True
    correlation_required: bool = True
    silent_truncation_forbidden: bool = True
    tenant_isolation_required: bool = True


@dataclass(frozen=True)
class FrozenWeightedPreferences:
    version: str
    local_retrieval_quality: int = 35
    security_and_governance: int = 25
    reproducibility: int = 15
    reliability_and_observability: int = 10
    cost: int = 10
    latency_and_operability: int = 5

    def __post_init__(self) -> None:
        if sum((
            self.local_retrieval_quality,
            self.security_and_governance,
            self.reproducibility,
            self.reliability_and_observability,
            self.cost,
            self.latency_and_operability,
        )) != 100:
            raise ValueError("selection weights must be frozen and sum to 100")


def prepare_authorized_items(
    handoff: AuthorizedEmbeddingInput,
    *,
    contract: EmbeddingContract,
    tokenizer: TokenizerPort,
) -> tuple[EmbeddingItem, ...]:
    """Apply frozen preprocessing and exact-token admission, never truncation."""

    if handoff.action != "chunk:read_for_embedding":
        raise EmbeddingEligibilityError("EXACT_EMBEDDING_ACTION_REQUIRED")
    tokenizer_contract = tokenizer.contract
    if (
        tokenizer_contract.name != contract.tokenizer.name
        or tokenizer_contract.version != contract.tokenizer.version
    ):
        raise EmbeddingEligibilityError("TOKENIZER_CONTRACT_MISMATCH")
    if contract.preprocessing_version != "prefix-only-v1":
        raise EmbeddingEligibilityError("UNSUPPORTED_PREPROCESSING_VERSION")

    prepared: list[EmbeddingItem] = []
    for ordinal, chunk in enumerate(handoff.chunks):
        text = contract.input_prefix + chunk.text
        token_count = tokenizer.count(text)
        if token_count > contract.hard_max_tokens:
            raise ReturnToDay96Required(
                f"CHUNK_EXCEEDS_EMBEDDING_TOKEN_LIMIT:{chunk.chunk_id}"
            )
        prepared.append(EmbeddingItem(
            chunk_id=chunk.chunk_id,
            ordinal=ordinal,
            text=text,
            content_hash=chunk.content_hash,
            source_segments=chunk.source_segments,
            token_count=token_count,
            utf8_bytes=len(text.encode("utf-8")),
        ))
    if tuple(item.chunk_id for item in prepared) != handoff.authorized_chunk_ids:
        raise EmbeddingEligibilityError("AUTHORIZED_CHUNK_ORDER_CHANGED")
    return tuple(prepared)
