"""Pure Day97 metadata projection candidate builder."""

from __future__ import annotations

from rag_metadata_contracts import (
    MetadataAssertion,
    MetadataProjectionAttempt,
    MetadataProjectionCandidate,
    MetadataProjectionOperation,
)


class MetadataProjector:
    """Build an untrusted candidate without creating durable truth."""

    def project(
        self,
        *,
        operation: MetadataProjectionOperation,
        attempt: MetadataProjectionAttempt,
        assertions: tuple[MetadataAssertion, ...],
    ) -> MetadataProjectionCandidate:
        if attempt.operation_id != operation.operation_id:
            raise ValueError("metadata attempt does not bind the operation")
        return MetadataProjectionCandidate(operation, attempt, assertions)
