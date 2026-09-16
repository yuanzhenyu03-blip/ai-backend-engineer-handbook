"""Day93 protocol-version and capability gates scoped to one generation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


METHOD_CAPABILITIES: Mapping[str, str | None] = {
    "server/discover": None,
    "tools/call": "tools",
    "resources/read": "resources",
    "prompts/get": "prompts",
}


class VersionNegotiationOutcome(str, Enum):
    NEGOTIATED = "NEGOTIATED"
    INCOMPATIBLE = "INCOMPATIBLE"


@dataclass(frozen=True)
class VersionNegotiationResult:
    outcome: VersionNegotiationOutcome
    generation: int
    negotiated_version: str | None
    capabilities: frozenset[str]
    supported_versions: tuple[str, ...]
    requires_fresh_preflight: bool = True
    error_code: int | None = None
    handler_calls: int = 0
    controlled_service_calls: int = 0


def negotiate_generation(
    *,
    generation: int,
    client_versions: tuple[str, ...],
    server_versions: frozenset[str],
    server_capabilities: frozenset[str],
) -> VersionNegotiationResult:
    """Select the client's first common version for this generation only."""

    if generation < 1:
        raise ValueError("generation must be positive")
    if not client_versions or not server_versions:
        raise ValueError("both peers must declare supported versions")
    selected = next(
        (version for version in client_versions if version in server_versions),
        None,
    )
    if selected is None:
        return VersionNegotiationResult(
            VersionNegotiationOutcome.INCOMPATIBLE,
            generation,
            negotiated_version=None,
            capabilities=frozenset(),
            supported_versions=tuple(sorted(server_versions, reverse=True)),
            error_code=-32022,
        )
    return VersionNegotiationResult(
        VersionNegotiationOutcome.NEGOTIATED,
        generation,
        negotiated_version=selected,
        capabilities=server_capabilities,
        supported_versions=tuple(sorted(server_versions, reverse=True)),
    )


@dataclass(frozen=True)
class VersionedApplicationPermit:
    """Exact authorization bound to one negotiated transport generation."""

    generation: int
    negotiated_version: str
    capabilities: frozenset[str]
    authorization_revision: int
    method: str
    tenant_id: str
    resource_id: str


class VersionedPermitOutcome(str, Enum):
    ADMITTED = "ADMITTED"
    NEGOTIATION_INCOMPATIBLE = "NEGOTIATION_INCOMPATIBLE"
    STALE_GENERATION = "STALE_GENERATION"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    CAPABILITY_REJECTED = "CAPABILITY_REJECTED"
    METHOD_NOT_BOUND = "METHOD_NOT_BOUND"


@dataclass(frozen=True)
class VersionedPermitDecision:
    outcome: VersionedPermitOutcome
    handler_calls: int = 0
    controlled_service_calls: int = 0


def validate_versioned_permit(
    negotiation: VersionNegotiationResult,
    permit: VersionedApplicationPermit,
    *,
    requested_method: str,
) -> VersionedPermitDecision:
    """Reject stale or downgraded permits before handler entry."""

    if negotiation.outcome is not VersionNegotiationOutcome.NEGOTIATED:
        return VersionedPermitDecision(
            VersionedPermitOutcome.NEGOTIATION_INCOMPATIBLE
        )
    if permit.generation != negotiation.generation:
        return VersionedPermitDecision(VersionedPermitOutcome.STALE_GENERATION)
    if permit.negotiated_version != negotiation.negotiated_version:
        return VersionedPermitDecision(VersionedPermitOutcome.VERSION_MISMATCH)
    if permit.method != requested_method:
        return VersionedPermitDecision(VersionedPermitOutcome.METHOD_NOT_BOUND)
    required_capability = METHOD_CAPABILITIES.get(requested_method)
    if required_capability is None and requested_method != "server/discover":
        return VersionedPermitDecision(VersionedPermitOutcome.METHOD_NOT_BOUND)
    if (
        required_capability is not None
        and (
            required_capability not in negotiation.capabilities
            or required_capability not in permit.capabilities
        )
    ):
        return VersionedPermitDecision(
            VersionedPermitOutcome.CAPABILITY_REJECTED
        )
    return VersionedPermitDecision(VersionedPermitOutcome.ADMITTED)
