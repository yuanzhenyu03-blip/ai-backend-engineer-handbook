"""Validate a late remote response into a reconciliation proposal only."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mcp_reconciliation import (
    ApplicationOperationBinding,
    ReconciliationDecision,
    ReconciliationDecisionKind,
)
from mcp_remote_session import (
    RemoteResponseCorrelation,
    RemoteResponseCorrelationOutcome,
)


@dataclass(frozen=True)
class LateSuccessCandidate:
    """Decoded late result; untrusted until every local check passes."""

    binding: ApplicationOperationBinding
    external_object_id: str
    protocol_schema_valid: bool
    application_output_valid: bool
    evidence_source: str


class LateResponseOutcome(str, Enum):
    PROPOSAL_READY = "PROPOSAL_READY"
    CORRELATION_REJECTED = "CORRELATION_REJECTED"
    BINDING_CONFLICT = "BINDING_CONFLICT"
    PROTOCOL_REJECTED = "PROTOCOL_REJECTED"
    OUTPUT_REJECTED = "OUTPUT_REJECTED"


@dataclass(frozen=True)
class LateResponseDecision:
    outcome: LateResponseOutcome
    proposal: ReconciliationDecision | None = None
    committer_calls: int = 0
    durable_transition: bool = False


def validate_late_success(
    correlation: RemoteResponseCorrelation,
    *,
    authoritative_binding: ApplicationOperationBinding,
    candidate: LateSuccessCandidate,
) -> LateResponseDecision:
    """Produce evidence for a separate Committer; never write business state."""

    remote_binding = correlation.binding
    if (
        correlation.outcome is not RemoteResponseCorrelationOutcome.MATCHED
        or remote_binding is None
    ):
        return LateResponseDecision(LateResponseOutcome.CORRELATION_REJECTED)
    if (
        remote_binding.operation_id != authoritative_binding.operation_id
        or remote_binding.idempotency_key
        != authoritative_binding.idempotency_key
        or candidate.binding != authoritative_binding
    ):
        return LateResponseDecision(LateResponseOutcome.BINDING_CONFLICT)
    if not candidate.protocol_schema_valid:
        return LateResponseDecision(LateResponseOutcome.PROTOCOL_REJECTED)
    if not candidate.application_output_valid:
        return LateResponseDecision(LateResponseOutcome.OUTPUT_REJECTED)
    if not candidate.external_object_id or not candidate.evidence_source:
        return LateResponseDecision(LateResponseOutcome.OUTPUT_REJECTED)
    return LateResponseDecision(
        LateResponseOutcome.PROPOSAL_READY,
        ReconciliationDecision(
            ReconciliationDecisionKind.RESOLVED_SUCCEEDED,
            authoritative_binding,
            evidence_source=candidate.evidence_source,
            external_object_id=candidate.external_object_id,
        ),
    )
