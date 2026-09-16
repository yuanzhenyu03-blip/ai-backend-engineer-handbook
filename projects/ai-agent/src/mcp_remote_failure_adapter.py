"""Application-owned trust boundary for remote MCP failure claims."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mcp_client_transport import DispatchCertainty
from mcp_remote_lifecycle import (
    ExecutionCertainty,
    FailureEvidence,
    FailureKind,
    FailurePhase,
)
from mcp_remote_session import (
    RemoteResponseCorrelation,
    RemoteResponseCorrelationOutcome,
)


@dataclass(frozen=True)
class RemoteFailureClaim:
    """Untrusted fields decoded from a remote HTTP/error response."""

    http_status: int
    error_code: str


@dataclass(frozen=True)
class AuthenticatedRemoteContext:
    """Connection facts supplied by trusted transport configuration."""

    server_identity: str
    identity_verified: bool


@dataclass(frozen=True)
class ControlledPreHandlerRejection:
    http_status: int
    error_code: str
    phase: FailurePhase
    kind: FailureKind


DEFAULT_PRE_HANDLER_REJECTIONS = (
    ControlledPreHandlerRejection(
        503,
        "CAPACITY_REJECTED",
        FailurePhase.CAPACITY,
        FailureKind.CAPACITY_REJECTED,
    ),
    ControlledPreHandlerRejection(
        503,
        "CIRCUIT_OPEN",
        FailurePhase.CAPACITY,
        FailureKind.CIRCUIT_OPEN,
    ),
    ControlledPreHandlerRejection(
        503,
        "AUTHENTICATION_DEPENDENCY_UNAVAILABLE",
        FailurePhase.AUTHENTICATION_DEPENDENCY,
        FailureKind.JWKS_REFRESH_FAILED,
    ),
)


@dataclass(frozen=True)
class ControlledRemoteFailureContract:
    """Locally configured meanings, never meanings supplied by the peer."""

    server_identity: str
    pre_handler_rejections: tuple[ControlledPreHandlerRejection, ...] = (
        DEFAULT_PRE_HANDLER_REJECTIONS
    )


class RemoteFailureMappingOutcome(str, Enum):
    VERIFIED_PRE_HANDLER_REJECTION = "VERIFIED_PRE_HANDLER_REJECTION"
    UNVERIFIED_REMOTE_CLAIM = "UNVERIFIED_REMOTE_CLAIM"
    CORRELATION_REJECTED = "CORRELATION_REJECTED"


@dataclass(frozen=True)
class RemoteFailureMapping:
    outcome: RemoteFailureMappingOutcome
    evidence: FailureEvidence | None = None
    controlled_service_calls: int = 0
    committer_calls: int = 0


class ApplicationRemoteFailureAdapter:
    """Convert a remote claim into facts using local trust and correlation."""

    def __init__(self, contract: ControlledRemoteFailureContract) -> None:
        self._contract = contract

    def translate(
        self,
        claim: RemoteFailureClaim,
        *,
        context: AuthenticatedRemoteContext,
        correlation: RemoteResponseCorrelation,
    ) -> RemoteFailureMapping:
        binding = correlation.binding
        if (
            correlation.outcome is not RemoteResponseCorrelationOutcome.MATCHED
            or binding is None
        ):
            return RemoteFailureMapping(
                RemoteFailureMappingOutcome.CORRELATION_REJECTED
            )

        matched_contract = next(
            (
                rejection
                for rejection in self._contract.pre_handler_rejections
                if rejection.http_status == claim.http_status
                and rejection.error_code == claim.error_code
            ),
            None,
        )
        trusted_pre_handler_rejection = (
            context.identity_verified
            and context.server_identity == self._contract.server_identity
            and matched_contract is not None
        )
        return RemoteFailureMapping(
            (
                RemoteFailureMappingOutcome.VERIFIED_PRE_HANDLER_REJECTION
                if trusted_pre_handler_rejection
                else RemoteFailureMappingOutcome.UNVERIFIED_REMOTE_CLAIM
            ),
            FailureEvidence(
                operation_id=binding.operation_id,
                idempotency_key=binding.idempotency_key,
                protocol_request_id=binding.key.protocol_request_id,
                attempt_number=binding.attempt_number,
                phase=(
                    matched_contract.phase
                    if trusted_pre_handler_rejection
                    else FailurePhase.READ
                ),
                kind=(
                    matched_contract.kind
                    if trusted_pre_handler_rejection
                    else FailureKind.UNVERIFIED_REMOTE_FAILURE
                ),
                dispatch_certainty=DispatchCertainty.PROVEN_SENT,
                execution_certainty=(
                    ExecutionCertainty.PROVEN_NOT_EXECUTED
                    if trusted_pre_handler_rejection
                    else ExecutionCertainty.POSSIBLY_EXECUTED
                ),
                evidence_source="application-remote-failure-adapter",
            ),
        )
