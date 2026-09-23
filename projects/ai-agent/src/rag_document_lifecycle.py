"""Pure Day95 document lifecycle eligibility decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag_ingestion_committer import (
    DocumentVersionLifecycle,
    DocumentVersionLifecycleRecord,
    IngestionOperationRecord,
    IngestionOperationState,
)
from rag_ingestion_contracts import DocumentHeadSnapshot, DocumentHeadState


class ChunkingEligibilityOutcome(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    DOCUMENT_NOT_ACTIVE = "DOCUMENT_NOT_ACTIVE"
    ACTIVE_POINTER_MISMATCH = "ACTIVE_POINTER_MISMATCH"
    VERSION_NOT_ACTIVE = "VERSION_NOT_ACTIVE"
    PARSED_ARTIFACT_MISSING = "PARSED_ARTIFACT_MISSING"
    INGESTION_NOT_COMPLETED = "INGESTION_NOT_COMPLETED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


@dataclass(frozen=True)
class ChunkingEligibilityDecision:
    outcome: ChunkingEligibilityOutcome
    safe_reason: str
    parsed_artifact_id: str | None = None
    durable_transitions: int = 0

    @property
    def eligible(self) -> bool:
        return self.outcome is ChunkingEligibilityOutcome.ELIGIBLE


def evaluate_day96_chunking_eligibility(
    *,
    document: DocumentHeadSnapshot,
    version: DocumentVersionLifecycleRecord,
    operation: IngestionOperationRecord,
) -> ChunkingEligibilityDecision:
    """Prove only a committed active version can enter Day96."""

    version_identity = version.definition.identity
    if (
        document.identity != version_identity.document
        or operation.identity.version != version_identity
        or operation.identity.source_artifact_id
        != version.definition.source_artifact_id
    ):
        return ChunkingEligibilityDecision(
            ChunkingEligibilityOutcome.IDENTITY_CONFLICT,
            "DOCUMENT_VERSION_OPERATION_BINDING_CONFLICT",
        )
    if document.state is not DocumentHeadState.ACTIVE:
        return ChunkingEligibilityDecision(
            ChunkingEligibilityOutcome.DOCUMENT_NOT_ACTIVE,
            "DOCUMENT_HEAD_IS_NOT_ACTIVE",
        )
    if document.active_version_id != version_identity.document_version_id:
        return ChunkingEligibilityDecision(
            ChunkingEligibilityOutcome.ACTIVE_POINTER_MISMATCH,
            "VERSION_IS_NOT_THE_DOCUMENT_ACTIVE_POINTER",
        )
    if version.state is not DocumentVersionLifecycle.ACTIVE:
        return ChunkingEligibilityDecision(
            ChunkingEligibilityOutcome.VERSION_NOT_ACTIVE,
            "DOCUMENT_VERSION_IS_NOT_ACTIVE",
        )
    if version.parsed_artifact_id is None:
        return ChunkingEligibilityDecision(
            ChunkingEligibilityOutcome.PARSED_ARTIFACT_MISSING,
            "ACTIVE_VERSION_REQUIRES_IMMUTABLE_PARSED_ARTIFACT",
        )
    if operation.state is not IngestionOperationState.COMPLETED:
        return ChunkingEligibilityDecision(
            ChunkingEligibilityOutcome.INGESTION_NOT_COMPLETED,
            "INGESTION_OPERATION_IS_NOT_DURABLY_COMPLETED",
        )
    return ChunkingEligibilityDecision(
        ChunkingEligibilityOutcome.ELIGIBLE,
        "ACTIVE_VALIDATED_PARSED_ARTIFACT_READY_FOR_DAY96",
        parsed_artifact_id=version.parsed_artifact_id,
    )
