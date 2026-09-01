"""Day80 Agent Tool visibility, Schema and permission governance.

This module builds an immutable, auditable capability snapshot for one Agent
Step, binds a returned candidate, and rechecks current trusted facts before
delegating to existing Admission. It reuses Day74 ToolRegistry and Schema
validation. It does not execute a Tool or replace Day66/Day74/Day78 boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from enum import Enum
import hashlib
import json
from typing import Iterable, Mapping

from output_tool_contracts import ToolRegistry, validate_schema_subset


@dataclass(frozen=True)
class TrustedToolContext:
    """Server-derived context; model output must never construct this value."""

    tenant_id: str
    user_id: str
    role: str
    job_id: str
    step_id: str
    granted_tool_ids: frozenset[str]
    argument_enum_constraints: tuple["ArgumentEnumConstraint", ...] = ()

    def __post_init__(self) -> None:
        if not all(
            (self.tenant_id, self.user_id, self.role, self.job_id, self.step_id)
        ):
            raise ValueError("trusted Tool context identities are required")


@dataclass(frozen=True)
class AgentToolCatalogEntry:
    name: str
    version: str
    description: str

    def __post_init__(self) -> None:
        if not self.name or not self.version or not self.description:
            raise ValueError("Tool catalog fields are required")

    @property
    def tool_id(self) -> str:
        return f"{self.name}@{self.version}"


@dataclass(frozen=True)
class ArgumentEnumConstraint:
    """Trusted per-context narrowing for one existing string property."""

    tool_id: str
    property_name: str
    allowed_values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.tool_id or not self.property_name or not self.allowed_values:
            raise ValueError("Schema projection constraint must be non-empty")
        if len(set(self.allowed_values)) != len(self.allowed_values):
            raise ValueError("Schema projection values must be unique")


@dataclass(frozen=True)
class VisibleToolDefinition:
    name: str
    version: str
    description: str
    base_schema_sha256: str
    arguments_schema_json: str
    arguments_schema_sha256: str


@dataclass(frozen=True)
class ToolVisibilityDecision:
    tool_id: str
    visible: bool
    reason: str


@dataclass(frozen=True)
class ToolCapabilitySnapshot:
    snapshot_id: str
    tenant_id: str
    user_id: str
    role: str
    job_id: str
    step_id: str
    visible_tools: tuple[VisibleToolDefinition, ...]
    decisions: tuple[ToolVisibilityDecision, ...]


@dataclass(frozen=True)
class BoundToolInvocation:
    """Server-owned binding for a Provider candidate, never model authority."""

    snapshot_id: str
    tenant_id: str
    user_id: str
    role: str
    job_id: str
    step_id: str
    tool_name: str
    tool_version: str
    arguments_schema_sha256: str

    @property
    def tool_id(self) -> str:
        return f"{self.tool_name}@{self.tool_version}"


class InvocationGovernanceStatus(str, Enum):
    ALLOWED_TO_DAY74_ADMISSION = "ALLOWED_TO_DAY74_ADMISSION"
    ORIGINAL_SNAPSHOT_MISMATCH = "ORIGINAL_SNAPSHOT_MISMATCH"
    ORIGINAL_TOOL_NOT_VISIBLE = "ORIGINAL_TOOL_NOT_VISIBLE"
    CURRENT_PERMISSION_REVOKED = "CURRENT_PERMISSION_REVOKED"
    CURRENT_REGISTRY_BLOCKED = "CURRENT_REGISTRY_BLOCKED"
    SCHEMA_BINDING_MISMATCH = "SCHEMA_BINDING_MISMATCH"


class PolicyEffect(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PermissionLayerResult:
    layer: str
    effect: PolicyEffect
    reason: str

    def __post_init__(self) -> None:
        if not self.layer or not self.reason:
            raise ValueError("permission layer and reason are required")


class CompositePermissionStatus(str, Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    POLICY_UNAVAILABLE = "POLICY_UNAVAILABLE"


@dataclass(frozen=True)
class CompositePermissionDecision:
    status: CompositePermissionStatus
    evaluated_layers: tuple[PermissionLayerResult, ...]
    safe_reason: str


@dataclass(frozen=True)
class GovernedToolCandidate:
    binding: BoundToolInvocation
    arguments: Mapping[str, object]


class BackendPreparationStatus(str, Enum):
    READY_FOR_BACKEND_ADMISSION = "READY_FOR_BACKEND_ADMISSION"
    BLOCKED_BY_GOVERNANCE = "BLOCKED_BY_GOVERNANCE"
    PROJECTED_SCHEMA_INVALID = "PROJECTED_SCHEMA_INVALID"


@dataclass(frozen=True)
class BackendPreparationDecision:
    status: BackendPreparationStatus
    safe_reason: str


class BackendResultPhase(str, Enum):
    """Trusted phase reported by the existing backend/runtime boundary."""

    ACCEPTED = "ACCEPTED"
    VERIFIED_TERMINAL = "VERIFIED_TERMINAL"
    UNVERIFIED_TERMINAL = "UNVERIFIED_TERMINAL"


class AgentObservationStatus(str, Enum):
    WAIT_FOR_TERMINAL_RESULT = "WAIT_FOR_TERMINAL_RESULT"
    SAFE_RESULT_READY = "SAFE_RESULT_READY"
    BLOCKED_UNVERIFIED_RESULT = "BLOCKED_UNVERIFIED_RESULT"


@dataclass(frozen=True)
class SafeToolResult:
    """Minimal backend-approved observation; never a raw Tool payload."""

    tool_call_id: str
    operation_id: str
    result_code: str

    def __post_init__(self) -> None:
        if not self.tool_call_id or not self.operation_id or not self.result_code:
            raise ValueError("Safe Tool Result fields are required")


@dataclass(frozen=True)
class AgentObservationDecision:
    status: AgentObservationStatus
    safe_reason: str
    observation: SafeToolResult | None = None


@dataclass(frozen=True)
class FrameworkToolSpec:
    """Wire-neutral adapter input derived only from an app-owned snapshot."""

    name: str
    version: str
    description: str
    arguments_schema_json: str
    capability_snapshot_id: str


def translate_snapshot_for_framework(
    snapshot: ToolCapabilitySnapshot,
) -> tuple[FrameworkToolSpec, ...]:
    """Translate app decisions; never discover or authorize extra Tools."""

    return tuple(
        FrameworkToolSpec(
            name=tool.name,
            version=tool.version,
            description=tool.description,
            arguments_schema_json=tool.arguments_schema_json,
            capability_snapshot_id=snapshot.snapshot_id,
        )
        for tool in snapshot.visible_tools
    )


def project_backend_result_for_agent(
    *,
    phase: BackendResultPhase,
    verified_safe_result: SafeToolResult | None = None,
) -> AgentObservationDecision:
    """Gate Agent observation after existing backend outcome verification.

    This function does not verify an outcome or advance a Controller state.
    Day66/Day74/Day78 own those boundaries. It only prevents acceptance or an
    unverified terminal payload from becoming an Agent-visible observation.
    """

    if phase is BackendResultPhase.ACCEPTED:
        return AgentObservationDecision(
            AgentObservationStatus.WAIT_FOR_TERMINAL_RESULT,
            "BACKEND_ACCEPTED_NOT_COMPLETED",
        )
    if phase is BackendResultPhase.UNVERIFIED_TERMINAL:
        return AgentObservationDecision(
            AgentObservationStatus.BLOCKED_UNVERIFIED_RESULT,
            "OUTCOME_VERIFICATION_REQUIRED",
        )
    if verified_safe_result is None:
        raise ValueError("verified terminal phase requires a Safe Tool Result")
    return AgentObservationDecision(
        AgentObservationStatus.SAFE_RESULT_READY,
        "VERIFIED_SAFE_RESULT",
        verified_safe_result,
    )


def compose_permission_layers(
    results: Iterable[PermissionLayerResult],
) -> CompositePermissionDecision:
    """Compose trusted policy layers; pre-execution UNKNOWN is not reconciliation."""

    evaluated = tuple(results)
    if not evaluated:
        raise ValueError("at least one permission layer is required")
    denied = next(
        (item for item in evaluated if item.effect is PolicyEffect.DENY),
        None,
    )
    if denied is not None:
        return CompositePermissionDecision(
            CompositePermissionStatus.DENIED,
            evaluated,
            f"DENIED_BY_{denied.layer}",
        )
    unknown = next(
        (item for item in evaluated if item.effect is PolicyEffect.UNKNOWN),
        None,
    )
    if unknown is not None:
        return CompositePermissionDecision(
            CompositePermissionStatus.POLICY_UNAVAILABLE,
            evaluated,
            f"UNKNOWN_AT_{unknown.layer}",
        )
    return CompositePermissionDecision(
        CompositePermissionStatus.ALLOWED,
        evaluated,
        "ALL_REQUIRED_LAYERS_ALLOW",
    )


def prepare_candidate_for_backend_admission(
    *,
    candidate: GovernedToolCandidate,
    original_snapshot: ToolCapabilitySnapshot,
    current_context: TrustedToolContext,
    registry: ToolRegistry,
    catalog: Iterable[AgentToolCatalogEntry],
) -> BackendPreparationDecision:
    """Reuse Day74 Schema validation, then stop before Tool-specific Admission."""

    governance = check_invocation_governance(
        binding=candidate.binding,
        original_snapshot=original_snapshot,
        current_context=current_context,
        registry=registry,
        catalog=catalog,
    )
    if governance is not InvocationGovernanceStatus.ALLOWED_TO_DAY74_ADMISSION:
        return BackendPreparationDecision(
            BackendPreparationStatus.BLOCKED_BY_GOVERNANCE,
            governance.value,
        )

    projected = next(
        tool
        for tool in original_snapshot.visible_tools
        if tool.name == candidate.binding.tool_name
        and tool.version == candidate.binding.tool_version
    )
    schema = json.loads(projected.arguments_schema_json)
    if validate_schema_subset(candidate.arguments, schema):
        return BackendPreparationDecision(
            BackendPreparationStatus.PROJECTED_SCHEMA_INVALID,
            "PROJECTED_ARGUMENT_SCHEMA_INVALID",
        )
    return BackendPreparationDecision(
        BackendPreparationStatus.READY_FOR_BACKEND_ADMISSION,
        "DELEGATE_TO_TOOL_BACKEND",
    )


def _canonical_schema(schema: object) -> str:
    return json.dumps(schema, sort_keys=True, separators=(",", ":"))


def _project_schema(
    *,
    base_schema: object,
    tool_id: str,
    constraints: tuple[ArgumentEnumConstraint, ...],
) -> object:
    """Narrow a base Schema; never add a property or widen a base enum."""

    projected = deepcopy(base_schema)
    if not isinstance(projected, dict):
        raise ValueError("Tool arguments Schema must be an object mapping")
    properties = projected.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("Tool arguments Schema must declare properties")

    for constraint in constraints:
        if constraint.tool_id != tool_id:
            continue
        property_schema = properties.get(constraint.property_name)
        if not isinstance(property_schema, dict):
            raise ValueError("Schema projection cannot add an unknown property")
        if property_schema.get("type") != "string":
            raise ValueError("enum projection supports string properties only")
        base_enum = property_schema.get("enum")
        if base_enum is not None and not set(constraint.allowed_values) <= set(
            base_enum
        ):
            raise ValueError("Schema projection cannot widen the base enum")
        property_schema["enum"] = list(constraint.allowed_values)
    return projected


def build_tool_capability_snapshot(
    *,
    registry: ToolRegistry,
    catalog: Iterable[AgentToolCatalogEntry],
    context: TrustedToolContext,
) -> ToolCapabilitySnapshot:
    """Filter pre-model visibility without granting invocation permission."""

    catalog_entries = tuple(catalog)
    tool_ids = tuple(entry.tool_id for entry in catalog_entries)
    if len(set(tool_ids)) != len(tool_ids):
        raise ValueError("duplicate Tool catalog identity")

    visible: list[VisibleToolDefinition] = []
    decisions: list[ToolVisibilityDecision] = []

    for entry in sorted(catalog_entries, key=lambda item: item.tool_id):
        if entry.tool_id not in context.granted_tool_ids:
            decisions.append(
                ToolVisibilityDecision(
                    entry.tool_id,
                    False,
                    "NOT_GRANTED_FOR_CONTEXT",
                )
            )
            continue

        definition, resolution = registry.resolve(entry.name, entry.version)
        if definition is None:
            decisions.append(
                ToolVisibilityDecision(
                    entry.tool_id,
                    False,
                    resolution.value,
                )
            )
            continue

        base_schema_json = _canonical_schema(definition.arguments_schema)
        projected_schema = _project_schema(
            base_schema=definition.arguments_schema,
            tool_id=entry.tool_id,
            constraints=context.argument_enum_constraints,
        )
        schema_json = _canonical_schema(projected_schema)
        visible.append(
            VisibleToolDefinition(
                name=definition.name,
                version=definition.version,
                description=entry.description,
                base_schema_sha256=hashlib.sha256(
                    base_schema_json.encode("utf-8")
                ).hexdigest(),
                arguments_schema_json=schema_json,
                arguments_schema_sha256=hashlib.sha256(
                    schema_json.encode("utf-8")
                ).hexdigest(),
            )
        )
        decisions.append(
            ToolVisibilityDecision(entry.tool_id, True, "VISIBLE")
        )

    snapshot_material = json.dumps(
        {
            "tenant_id": context.tenant_id,
            "user_id": context.user_id,
            "role": context.role,
            "job_id": context.job_id,
            "step_id": context.step_id,
            "visible": [item.tool_id for item in decisions if item.visible],
            "decisions": [
                [item.tool_id, item.visible, item.reason] for item in decisions
            ],
            "schemas": [
                [item.name, item.version, item.arguments_schema_sha256]
                for item in visible
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    snapshot_id = "tool-snapshot:" + hashlib.sha256(
        snapshot_material.encode("utf-8")
    ).hexdigest()
    return ToolCapabilitySnapshot(
        snapshot_id=snapshot_id,
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        role=context.role,
        job_id=context.job_id,
        step_id=context.step_id,
        visible_tools=tuple(visible),
        decisions=tuple(decisions),
    )


def check_invocation_governance(
    *,
    binding: BoundToolInvocation,
    original_snapshot: ToolCapabilitySnapshot,
    current_context: TrustedToolContext,
    registry: ToolRegistry,
    catalog: Iterable[AgentToolCatalogEntry],
) -> InvocationGovernanceStatus:
    """Recheck current visibility before delegating to Day74 Admission.

    Passing this check means only that the bound candidate may proceed to the
    existing Day74/Day78 boundaries. It never means that Admission or execution
    is authorized.
    """

    original_identity = (
        original_snapshot.snapshot_id,
        original_snapshot.tenant_id,
        original_snapshot.user_id,
        original_snapshot.role,
        original_snapshot.job_id,
        original_snapshot.step_id,
    )
    binding_identity = (
        binding.snapshot_id,
        binding.tenant_id,
        binding.user_id,
        binding.role,
        binding.job_id,
        binding.step_id,
    )
    current_identity = (
        current_context.tenant_id,
        current_context.user_id,
        current_context.role,
        current_context.job_id,
        current_context.step_id,
    )
    if (
        original_identity != binding_identity
        or binding_identity[1:] != current_identity
    ):
        return InvocationGovernanceStatus.ORIGINAL_SNAPSHOT_MISMATCH

    original_tool = next(
        (
            tool
            for tool in original_snapshot.visible_tools
            if tool.name == binding.tool_name
            and tool.version == binding.tool_version
        ),
        None,
    )
    if original_tool is None:
        return InvocationGovernanceStatus.ORIGINAL_TOOL_NOT_VISIBLE
    if (
        original_tool.arguments_schema_sha256
        != binding.arguments_schema_sha256
    ):
        return InvocationGovernanceStatus.SCHEMA_BINDING_MISMATCH

    current_snapshot = build_tool_capability_snapshot(
        registry=registry,
        catalog=catalog,
        context=current_context,
    )
    current_tool = next(
        (
            tool
            for tool in current_snapshot.visible_tools
            if tool.name == binding.tool_name
            and tool.version == binding.tool_version
        ),
        None,
    )
    if current_tool is None:
        current_decision = next(
            (
                item
                for item in current_snapshot.decisions
                if item.tool_id == binding.tool_id
            ),
            None,
        )
        if current_decision is None:
            return InvocationGovernanceStatus.CURRENT_REGISTRY_BLOCKED
        if current_decision.reason == "NOT_GRANTED_FOR_CONTEXT":
            return InvocationGovernanceStatus.CURRENT_PERMISSION_REVOKED
        return InvocationGovernanceStatus.CURRENT_REGISTRY_BLOCKED
    if (
        current_tool.arguments_schema_sha256
        != binding.arguments_schema_sha256
    ):
        return InvocationGovernanceStatus.SCHEMA_BINDING_MISMATCH
    return InvocationGovernanceStatus.ALLOWED_TO_DAY74_ADMISSION
