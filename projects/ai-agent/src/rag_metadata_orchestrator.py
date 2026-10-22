"""Day97 application orchestration for metadata projection and publication."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag_metadata_committer import MetadataCommitter, MetadataCommitOutcome
from rag_metadata_contracts import (
    MetadataAssertion,
    MetadataContract,
    MetadataProjectionAttempt,
    MetadataProjectionOperation,
    MetadataSnapshot,
)
from rag_metadata_projection import MetadataProjector
from rag_metadata_validator import MetadataCandidateValidator


class MetadataRunOutcome(str, Enum):
    COMMITTED = "COMMITTED"
    ALREADY_COMMITTED = "ALREADY_COMMITTED"
    INELIGIBLE = "INELIGIBLE"
    REJECTED = "REJECTED"
    COMMIT_REJECTED = "COMMIT_REJECTED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class MetadataRunRequest:
    operation: MetadataProjectionOperation
    attempt: MetadataProjectionAttempt
    contract: MetadataContract
    assertions: tuple[MetadataAssertion, ...]
    cancelled: bool = False


@dataclass(frozen=True)
class MetadataRunResult:
    outcome: MetadataRunOutcome
    safe_reason: str
    snapshot: MetadataSnapshot | None = None
    projector_calls: int = 0
    validator_calls: int = 0
    committer_calls: int = 0
    durable_transitions: int = 0


class RAGMetadataOrchestrator:
    def __init__(
        self,
        *,
        projector: MetadataProjector,
        validator: MetadataCandidateValidator,
        committer: MetadataCommitter,
    ) -> None:
        self._projector = projector
        self._validator = validator
        self._committer = committer

    def run(self, request: MetadataRunRequest) -> MetadataRunResult:
        if request.cancelled:
            return MetadataRunResult(
                MetadataRunOutcome.CANCELLED,
                "METADATA_PROJECTION_CANCELLED_BEFORE_CLAIM",
            )
        claim = self._committer.claim(request.operation, request.attempt)
        if claim is None:
            return MetadataRunResult(
                MetadataRunOutcome.INELIGIBLE,
                "METADATA_OPERATION_NOT_CURRENT_OR_CLAIMABLE",
                committer_calls=1,
            )
        candidate = self._projector.project(
            operation=request.operation,
            attempt=request.attempt,
            assertions=request.assertions,
        )
        decision = self._validator.evaluate(
            contract=request.contract,
            candidate=candidate,
        )
        if not decision.ready:
            return MetadataRunResult(
                MetadataRunOutcome.REJECTED,
                decision.safe_reason,
                projector_calls=1,
                validator_calls=1,
                committer_calls=1,
            )
        committed = self._committer.persist(
            decision,
            contract=request.contract,
        )
        outcome = {
            MetadataCommitOutcome.COMMITTED: MetadataRunOutcome.COMMITTED,
            MetadataCommitOutcome.ALREADY_COMMITTED:
                MetadataRunOutcome.ALREADY_COMMITTED,
        }.get(committed.outcome, MetadataRunOutcome.COMMIT_REJECTED)
        return MetadataRunResult(
            outcome,
            committed.safe_reason,
            snapshot=committed.snapshot,
            projector_calls=1,
            validator_calls=1,
            committer_calls=2,
            durable_transitions=int(committed.durable_transition),
        )
