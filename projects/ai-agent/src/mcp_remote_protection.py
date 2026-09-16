"""Local pre-transport protection outcomes for Day93 remote MCP calls."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from mcp_authorization import ToolAuthorizationPermit
from mcp_client_transport import DispatchCertainty
from mcp_remote_lifecycle import (
    ExecutionCertainty,
    FailureEvidence,
    FailureKind,
    FailurePhase,
)


@dataclass(frozen=True)
class LocalProtectionRejection:
    evidence: FailureEvidence
    transport_calls: int = 0
    handler_calls: int = 0
    controlled_service_calls: int = 0


class GlobalLoadSheddingOutcome(str, Enum):
    ADMITTED = "ADMITTED"
    SHED = "SHED"


@dataclass(frozen=True)
class EdgeTransportFacts:
    """Cheap pre-auth facts; deliberately contains no tenant or payload data."""

    source_bucket: str
    route_class: str


@dataclass(frozen=True)
class GlobalLoadSheddingDecision:
    outcome: GlobalLoadSheddingOutcome
    http_status: int | None
    authentication_calls: int = 0
    authorization_calls: int = 0
    handler_calls: int = 0
    controlled_service_calls: int = 0


def admit_global_load(
    facts: EdgeTransportFacts,
    *,
    global_capacity_available: bool,
) -> GlobalLoadSheddingDecision:
    """Perform coarse shedding without inferring identity from the payload."""

    if not facts.source_bucket or not facts.route_class:
        raise ValueError("edge transport facts must be complete")
    if not global_capacity_available:
        return GlobalLoadSheddingDecision(
            GlobalLoadSheddingOutcome.SHED,
            http_status=503,
        )
    return GlobalLoadSheddingDecision(
        GlobalLoadSheddingOutcome.ADMITTED,
        http_status=None,
    )


class TenantCapacityClass(str, Enum):
    STANDARD = "STANDARD"
    PRIORITY = "PRIORITY"


class TenantCapacityOutcome(str, Enum):
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class TenantCapacityDecision:
    outcome: TenantCapacityOutcome
    capacity_class: TenantCapacityClass
    rejection: LocalProtectionRejection | None = None


@dataclass(frozen=True)
class TenantCapacityAdmission:
    """Tenant-aware admission consumes only a current exact authz permit."""

    tenant_classes: Mapping[str, TenantCapacityClass]
    available_classes: frozenset[TenantCapacityClass]

    def admit(
        self,
        permit: ToolAuthorizationPermit,
        *,
        protocol_request_id: str | int,
        attempt_number: int,
    ) -> TenantCapacityDecision:
        capacity_class = self.tenant_classes.get(
            permit.tenant_id,
            TenantCapacityClass.STANDARD,
        )
        if capacity_class in self.available_classes:
            return TenantCapacityDecision(
                TenantCapacityOutcome.ADMITTED,
                capacity_class,
            )
        return TenantCapacityDecision(
            TenantCapacityOutcome.REJECTED,
            capacity_class,
            LocalProtectionRejection(
                FailureEvidence(
                    operation_id=permit.application_operation_id,
                    idempotency_key=permit.idempotency_key,
                    protocol_request_id=protocol_request_id,
                    attempt_number=attempt_number,
                    phase=FailurePhase.CAPACITY,
                    kind=FailureKind.CAPACITY_REJECTED,
                    dispatch_certainty=DispatchCertainty.PROVEN_NOT_SENT,
                    execution_certainty=(
                        ExecutionCertainty.PROVEN_NOT_EXECUTED
                    ),
                    evidence_source="authorized-tenant-capacity-admission",
                )
            ),
        )


def reject_local_circuit_open(
    *,
    operation_id: str,
    idempotency_key: str,
    protocol_request_id: str | int,
    attempt_number: int,
) -> LocalProtectionRejection:
    """Reject before transport; the circuit state does not call the peer."""

    return LocalProtectionRejection(
        FailureEvidence(
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            protocol_request_id=protocol_request_id,
            attempt_number=attempt_number,
            phase=FailurePhase.CAPACITY,
            kind=FailureKind.CIRCUIT_OPEN,
            dispatch_certainty=DispatchCertainty.PROVEN_NOT_SENT,
            execution_certainty=ExecutionCertainty.PROVEN_NOT_EXECUTED,
            evidence_source="application-local-circuit-breaker",
        )
    )
