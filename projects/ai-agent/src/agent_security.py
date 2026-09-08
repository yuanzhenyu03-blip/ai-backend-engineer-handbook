"""Day86 application-owned Agent security admission boundary.

This module is a deterministic, in-process policy core. It classifies candidates
and returns structured decisions. It does not call a Provider, Tool, network, or
operating-system sandbox and is not evidence of production isolation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json


class SecurityDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    WAIT = "WAIT"
    QUARANTINE = "QUARANTINE"


class TrustClass(str, Enum):
    TRUSTED_INSTRUCTION = "TRUSTED_INSTRUCTION"
    UNTRUSTED_CONTENT = "UNTRUSTED_CONTENT"


class ContentChannel(str, Enum):
    APPLICATION = "APPLICATION"
    USER = "USER"
    WEB = "WEB"
    DOCUMENT = "DOCUMENT"
    TOOL_RESULT = "TOOL_RESULT"
    AGENT_MESSAGE = "AGENT_MESSAGE"
    SANDBOX_RESULT = "SANDBOX_RESULT"


class InjectionSignal(str, Enum):
    NONE = "NONE"
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"


class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    SECRET = "SECRET"


class ToolPortMode(str, Enum):
    SUCCESS = "SUCCESS"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class SandboxPortMode(str, Enum):
    SUCCESS = "SUCCESS"
    TIMEOUT_AFTER_DISPATCH = "TIMEOUT_AFTER_DISPATCH"
    CLEANUP_FAILURE = "CLEANUP_FAILURE"


class ExecutionState(str, Enum):
    NOT_DISPATCHED = "NOT_DISPATCHED"
    RESULT_CANDIDATE = "RESULT_CANDIDATE"
    VERIFIED = "VERIFIED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    INCOMPLETE = "INCOMPLETE"
    QUARANTINED = "QUARANTINED"


class OperationBindingStatus(str, Enum):
    NEW = "NEW"
    DUPLICATE = "DUPLICATE"
    SEMANTIC_CONFLICT = "SEMANTIC_CONFLICT"


class SecuritySlotStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PENDING = "PENDING"
    QUARANTINED = "QUARANTINED"


class SecurityFanInStatus(str, Enum):
    READY = "READY"
    WAITING_FOR_REQUIRED = "WAITING_FOR_REQUIRED"
    PARENT_TERMINAL = "PARENT_TERMINAL"


class IncidentStage(str, Enum):
    UNDISPATCHED = "UNDISPATCHED"
    VERIFIED_EFFECT = "VERIFIED_EFFECT"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    CONFIRMED_EXFILTRATION = "CONFIRMED_EXFILTRATION"


class IncidentAction(str, Enum):
    CANCEL_AND_RELEASE_CONFIRMED_UNUSED = (
        "CANCEL_AND_RELEASE_CONFIRMED_UNUSED"
    )
    SETTLE_AND_AUTHORIZE_COMPENSATION = (
        "SETTLE_AND_AUTHORIZE_COMPENSATION"
    )
    RECONCILE_ORIGINAL_IDENTITY_AND_HOLD = (
        "RECONCILE_ORIGINAL_IDENTITY_AND_HOLD"
    )
    CONTAIN_ROTATE_AND_AUTHORIZE_COMPENSATION = (
        "CONTAIN_ROTATE_AND_AUTHORIZE_COMPENSATION"
    )


@dataclass(frozen=True)
class ContentRecord:
    """Application-bound provenance; content cannot assign its own trust."""

    content_id: str
    source_id: str
    source_version: str
    channel: ContentChannel
    trust_class: TrustClass
    injection_signal: InjectionSignal
    allowed_influence: tuple[str, ...]
    content_hash: str


def bind_untrusted_content(
    *,
    content_id: str,
    source_id: str,
    source_version: str,
    channel: ContentChannel,
    text: str,
    injection_suspected: bool,
    allowed_influence: tuple[str, ...] = ("MODEL_INPUT_DATA",),
) -> ContentRecord:
    """Bind external content as data and record a non-authoritative risk signal."""
    if channel is ContentChannel.APPLICATION:
        raise ValueError("application instructions require a separate trusted path")
    signal = InjectionSignal.NONE
    if injection_suspected:
        signal = (
            InjectionSignal.DIRECT
            if channel is ContentChannel.USER
            else InjectionSignal.INDIRECT
        )
    return ContentRecord(
        content_id=content_id,
        source_id=source_id,
        source_version=source_version,
        channel=channel,
        trust_class=TrustClass.UNTRUSTED_CONTENT,
        injection_signal=signal,
        allowed_influence=allowed_influence,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


@dataclass(frozen=True)
class DataField:
    name: str
    classification: DataClassification


@dataclass(frozen=True)
class ToolCandidate:
    tenant_id: str
    job_id: str
    attempt_id: str
    step_id: str
    handoff_id: str
    operation_id: str
    capability: str
    tool_name: str
    tool_version: str
    arguments: tuple[tuple[str, str], ...]
    resource_tenant_id: str
    destination: str | None
    purpose: str
    audience: str
    disclosed_fields: tuple[DataField, ...]
    fence_token: int
    policy_version: str

    @property
    def canonical_arguments_hash(self) -> str:
        payload = json.dumps(
            sorted(self.arguments), separators=(",", ":"), ensure_ascii=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @property
    def approval_fingerprint(self) -> str:
        payload = {
            "tenant_id": self.tenant_id,
            "operation_id": self.operation_id,
            "capability": self.capability,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "arguments_hash": self.canonical_arguments_hash,
            "destination": self.destination,
            "purpose": self.purpose,
            "audience": self.audience,
        }
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ToolContract:
    tool_name: str
    tool_version: str
    capability: str
    allowed_argument_names: tuple[str, ...]
    required_argument_names: tuple[str, ...]
    requires_approval: bool


@dataclass(frozen=True)
class ApprovalBinding:
    approval_id: str
    tenant_id: str
    candidate_fingerprint: str
    expires_at: int
    revoked: bool = False


@dataclass(frozen=True)
class SandboxProfile:
    profile_id: str
    version: str
    readable_paths: tuple[str, ...]
    writable_paths: tuple[str, ...]
    network_destinations: tuple[str, ...]
    allowed_environment_names: tuple[str, ...]
    allow_subprocess: bool


@dataclass(frozen=True)
class SandboxRequest:
    readable_paths: tuple[str, ...]
    writable_paths: tuple[str, ...]
    network_destinations: tuple[str, ...]
    environment_names: tuple[str, ...]
    allow_subprocess: bool


@dataclass(frozen=True)
class CurrentSecurityFacts:
    tenant_id: str
    current_policy_version: str
    policy_authority_available: bool
    granted_capabilities: tuple[str, ...]
    currently_allowed_capabilities: tuple[str, ...]
    current_fence_token: int
    allowed_destinations: tuple[str, ...]
    allowed_purposes: tuple[str, ...]
    allowed_audiences: tuple[str, ...]
    allowed_disclosure_fields: tuple[str, ...]
    approval: ApprovalBinding | None
    sandbox_profile: SandboxProfile


@dataclass(frozen=True)
class AdmissionResult:
    decision: SecurityDecision
    reason_code: str
    operation_id: str
    canonical_arguments_hash: str
    tool_dispatch_allowed: bool = False
    egress_allowed: bool = False
    sandbox_run_allowed: bool = False


@dataclass(frozen=True)
class SecurityEvidence:
    """Minimal admission evidence; it deliberately excludes raw payloads."""

    tenant_id: str
    job_id: str
    attempt_id: str
    step_id: str
    handoff_id: str
    operation_id: str
    outbox_intent_id: str | None
    reservation_id: str | None
    delegated_capabilities: tuple[str, ...]
    artifact_reference: str | None
    provenance_references: tuple[str, ...]
    audience: str
    approval_id: str | None
    destination: str | None
    sandbox_profile_id: str
    sandbox_profile_version: str
    policy_version: str
    tool_name: str
    tool_version: str
    outcome_contract: str
    context_contract: str
    canonical_arguments_hash: str
    decision: SecurityDecision
    reason_code: str
    dispatch_marker: bool


def _result(
    candidate: ToolCandidate,
    decision: SecurityDecision,
    reason_code: str,
    *,
    admitted: bool = False,
) -> AdmissionResult:
    return AdmissionResult(
        decision=decision,
        reason_code=reason_code,
        operation_id=candidate.operation_id,
        canonical_arguments_hash=candidate.canonical_arguments_hash,
        tool_dispatch_allowed=admitted,
        egress_allowed=admitted and candidate.destination is not None,
        sandbox_run_allowed=admitted,
    )


def build_security_evidence(
    *,
    candidate: ToolCandidate,
    facts: CurrentSecurityFacts,
    admission: AdmissionResult,
    provenance: tuple[ContentRecord, ...],
    outbox_intent_id: str | None,
    reservation_id: str | None,
    artifact_reference: str | None,
    outcome_contract: str,
    context_contract: str,
    dispatch_marker: bool = False,
) -> SecurityEvidence:
    """Build correlation evidence without copying arguments or source text."""
    approval_id = facts.approval.approval_id if facts.approval else None
    provenance_references = tuple(
        f"{item.source_id}@{item.source_version}:{item.content_hash}"
        for item in provenance
    )
    return SecurityEvidence(
        tenant_id=candidate.tenant_id,
        job_id=candidate.job_id,
        attempt_id=candidate.attempt_id,
        step_id=candidate.step_id,
        handoff_id=candidate.handoff_id,
        operation_id=candidate.operation_id,
        outbox_intent_id=outbox_intent_id,
        reservation_id=reservation_id,
        delegated_capabilities=facts.granted_capabilities,
        artifact_reference=artifact_reference,
        provenance_references=provenance_references,
        audience=candidate.audience,
        approval_id=approval_id,
        destination=candidate.destination,
        sandbox_profile_id=facts.sandbox_profile.profile_id,
        sandbox_profile_version=facts.sandbox_profile.version,
        policy_version=candidate.policy_version,
        tool_name=candidate.tool_name,
        tool_version=candidate.tool_version,
        outcome_contract=outcome_contract,
        context_contract=context_contract,
        canonical_arguments_hash=admission.canonical_arguments_hash,
        decision=admission.decision,
        reason_code=admission.reason_code,
        dispatch_marker=dispatch_marker,
    )


def admit_tool_candidate(
    *,
    candidate: ToolCandidate,
    contract: ToolContract,
    facts: CurrentSecurityFacts,
    sandbox_request: SandboxRequest,
    now: int,
) -> AdmissionResult:
    """Return a pure security decision without dispatching any side effect."""
    if not facts.policy_authority_available:
        return _result(candidate, SecurityDecision.WAIT, "AUTHORITY_UNAVAILABLE")
    if candidate.tenant_id != facts.tenant_id:
        return _result(candidate, SecurityDecision.QUARANTINE, "TENANT_MISMATCH")
    if candidate.resource_tenant_id != facts.tenant_id:
        return _result(
            candidate, SecurityDecision.QUARANTINE, "RESOURCE_TENANT_MISMATCH",
        )
    if candidate.policy_version != facts.current_policy_version:
        return _result(candidate, SecurityDecision.DENY, "STALE_POLICY")
    if candidate.fence_token != facts.current_fence_token:
        return _result(candidate, SecurityDecision.DENY, "STALE_FENCE")

    exact_tool = (
        candidate.tool_name == contract.tool_name
        and candidate.tool_version == contract.tool_version
        and candidate.capability == contract.capability
    )
    if not exact_tool:
        return _result(candidate, SecurityDecision.DENY, "TOOL_IDENTITY_MISMATCH")
    if candidate.capability not in facts.granted_capabilities:
        return _result(candidate, SecurityDecision.DENY, "OUTSIDE_DELEGATED_GRANT")
    if candidate.capability not in facts.currently_allowed_capabilities:
        return _result(candidate, SecurityDecision.DENY, "CURRENT_PERMISSION_DENIED")

    argument_names = tuple(name for name, _ in candidate.arguments)
    if len(set(argument_names)) != len(argument_names):
        return _result(candidate, SecurityDecision.DENY, "DUPLICATE_ARGUMENT")
    if not set(argument_names) <= set(contract.allowed_argument_names):
        return _result(candidate, SecurityDecision.DENY, "UNEXPECTED_ARGUMENT")
    if not set(contract.required_argument_names) <= set(argument_names):
        return _result(candidate, SecurityDecision.DENY, "MISSING_ARGUMENT")

    if contract.requires_approval:
        approval = facts.approval
        if approval is None:
            return _result(candidate, SecurityDecision.WAIT, "APPROVAL_REQUIRED")
        if approval.revoked or now >= approval.expires_at:
            return _result(candidate, SecurityDecision.WAIT, "APPROVAL_NOT_CURRENT")
        if (
            approval.tenant_id != facts.tenant_id
            or approval.candidate_fingerprint != candidate.approval_fingerprint
        ):
            return _result(candidate, SecurityDecision.WAIT, "APPROVAL_BINDING_MISMATCH")

    if candidate.purpose not in facts.allowed_purposes:
        return _result(candidate, SecurityDecision.DENY, "PURPOSE_DENIED")
    if candidate.audience not in facts.allowed_audiences:
        return _result(candidate, SecurityDecision.DENY, "AUDIENCE_DENIED")
    if candidate.destination is not None:
        if candidate.destination not in facts.allowed_destinations:
            return _result(candidate, SecurityDecision.DENY, "DESTINATION_DENIED")
        disclosed_names = {field.name for field in candidate.disclosed_fields}
        if not disclosed_names <= set(facts.allowed_disclosure_fields):
            return _result(candidate, SecurityDecision.DENY, "FIELD_DISCLOSURE_DENIED")
        if any(
            field.classification is DataClassification.SECRET
            for field in candidate.disclosed_fields
        ):
            return _result(candidate, SecurityDecision.DENY, "RAW_SECRET_EGRESS_DENIED")

    profile = facts.sandbox_profile
    if not set(sandbox_request.readable_paths) <= set(profile.readable_paths):
        return _result(candidate, SecurityDecision.DENY, "SANDBOX_READ_EXPANSION")
    if not set(sandbox_request.writable_paths) <= set(profile.writable_paths):
        return _result(candidate, SecurityDecision.DENY, "SANDBOX_WRITE_EXPANSION")
    if not set(sandbox_request.network_destinations) <= set(
        profile.network_destinations
    ):
        return _result(candidate, SecurityDecision.DENY, "SANDBOX_NETWORK_EXPANSION")
    if not set(sandbox_request.environment_names) <= set(
        profile.allowed_environment_names
    ):
        return _result(candidate, SecurityDecision.DENY, "SANDBOX_ENV_EXPANSION")
    if sandbox_request.allow_subprocess and not profile.allow_subprocess:
        return _result(candidate, SecurityDecision.DENY, "SANDBOX_PROCESS_EXPANSION")

    return _result(candidate, SecurityDecision.ALLOW, "ADMITTED", admitted=True)


@dataclass(frozen=True)
class ToolPortOutcome:
    outcome_known: bool
    evidence_reference: str | None


class FakeToolPort:
    """Deterministic Tool fixture; it performs no real external operation."""

    def __init__(self, mode: ToolPortMode = ToolPortMode.SUCCESS) -> None:
        self.mode = mode
        self.operation_ids: list[str] = []

    def dispatch(self, operation_id: str) -> ToolPortOutcome:
        self.operation_ids.append(operation_id)
        if self.mode is ToolPortMode.OUTCOME_UNKNOWN:
            return ToolPortOutcome(False, None)
        return ToolPortOutcome(True, f"fake-tool-evidence:{operation_id}")


class FakeEgressPort:
    """Records admitted synthetic destinations without network access."""

    def __init__(self) -> None:
        self.destinations: list[str] = []

    def send(self, destination: str) -> None:
        self.destinations.append(destination)


class FakeSandboxPort:
    """Models sandbox lifecycle decisions, not OS or container isolation."""

    def __init__(self, mode: SandboxPortMode = SandboxPortMode.SUCCESS) -> None:
        self.mode = mode
        self.run_operation_ids: list[str] = []
        self.cleanup_operation_ids: list[str] = []

    def start(self, operation_id: str) -> None:
        self.run_operation_ids.append(operation_id)

    def timed_out_after_dispatch(self) -> bool:
        return self.mode is SandboxPortMode.TIMEOUT_AFTER_DISPATCH

    def cleanup(self, operation_id: str) -> bool:
        self.cleanup_operation_ids.append(operation_id)
        return self.mode is not SandboxPortMode.CLEANUP_FAILURE


@dataclass(frozen=True)
class ResultCandidate:
    tenant_id: str
    operation_id: str
    policy_version: str
    fence_token: int
    evidence_reference: str


@dataclass(frozen=True)
class ExecutionResult:
    state: ExecutionState
    operation_id: str
    dispatch_marker: bool
    result_candidate: ResultCandidate | None
    cleanup_complete: bool | None
    tool_calls: int
    egress_calls: int
    sandbox_runs: int


def execute_admitted_candidate(
    *,
    admission: AdmissionResult,
    candidate: ToolCandidate,
    tool_port: FakeToolPort,
    egress_port: FakeEgressPort,
    sandbox_port: FakeSandboxPort,
) -> ExecutionResult:
    """Cross Fake ports only after ALLOW; returned output remains a candidate."""
    if admission.decision is not SecurityDecision.ALLOW:
        return ExecutionResult(
            ExecutionState.NOT_DISPATCHED,
            candidate.operation_id,
            False,
            None,
            None,
            len(tool_port.operation_ids),
            len(egress_port.destinations),
            len(sandbox_port.run_operation_ids),
        )

    sandbox_port.start(candidate.operation_id)
    dispatch_marker = True
    tool_outcome = tool_port.dispatch(candidate.operation_id)
    if candidate.destination is not None:
        egress_port.send(candidate.destination)

    cleanup_complete = sandbox_port.cleanup(candidate.operation_id)
    if not tool_outcome.outcome_known or sandbox_port.timed_out_after_dispatch():
        state = ExecutionState.PENDING_RECONCILIATION
        result_candidate = None
    elif not cleanup_complete:
        state = ExecutionState.INCOMPLETE
        result_candidate = ResultCandidate(
            candidate.tenant_id,
            candidate.operation_id,
            candidate.policy_version,
            candidate.fence_token,
            tool_outcome.evidence_reference or "missing-evidence",
        )
    else:
        state = ExecutionState.RESULT_CANDIDATE
        result_candidate = ResultCandidate(
            candidate.tenant_id,
            candidate.operation_id,
            candidate.policy_version,
            candidate.fence_token,
            tool_outcome.evidence_reference or "missing-evidence",
        )
    return ExecutionResult(
        state,
        candidate.operation_id,
        dispatch_marker,
        result_candidate,
        cleanup_complete,
        len(tool_port.operation_ids),
        len(egress_port.destinations),
        len(sandbox_port.run_operation_ids),
    )


def verify_result_candidate(
    result: ResultCandidate,
    *,
    facts: CurrentSecurityFacts,
    expected_operation_id: str,
) -> ExecutionState:
    """Classify evidence against current facts without changing business state."""
    if (
        result.tenant_id != facts.tenant_id
        or result.operation_id != expected_operation_id
        or result.policy_version != facts.current_policy_version
        or result.fence_token != facts.current_fence_token
    ):
        return ExecutionState.QUARANTINED
    return ExecutionState.VERIFIED


@dataclass(frozen=True)
class OperationBinding:
    operation_id: str
    canonical_arguments_hash: str


def classify_operation_binding(
    existing: OperationBinding | None,
    candidate: ToolCandidate,
) -> OperationBindingStatus:
    """Classify stable operation identity without mutating a ledger."""
    if existing is None or existing.operation_id != candidate.operation_id:
        return OperationBindingStatus.NEW
    if existing.canonical_arguments_hash == candidate.canonical_arguments_hash:
        return OperationBindingStatus.DUPLICATE
    return OperationBindingStatus.SEMANTIC_CONFLICT


@dataclass(frozen=True)
class SecuritySlot:
    slot_id: str
    required: bool
    status: SecuritySlotStatus


@dataclass(frozen=True)
class SecurityFanInResult:
    status: SecurityFanInStatus
    required_total: int
    required_verified: int
    parent_completed: bool


def evaluate_security_fan_in(
    slots: tuple[SecuritySlot, ...],
    *,
    parent_terminal: bool,
) -> SecurityFanInResult:
    """Evaluate security prerequisites without completing the parent."""
    required = tuple(slot for slot in slots if slot.required)
    verified = sum(
        slot.status is SecuritySlotStatus.VERIFIED for slot in required
    )
    if parent_terminal:
        status = SecurityFanInStatus.PARENT_TERMINAL
    elif verified != len(required):
        status = SecurityFanInStatus.WAITING_FOR_REQUIRED
    else:
        status = SecurityFanInStatus.READY
    return SecurityFanInResult(status, len(required), verified, False)


@dataclass(frozen=True)
class PolicyContainmentResult:
    quarantined_policy_version: str
    blocked_transitions: tuple[str, ...]
    preserve_existing_evidence: bool


def quarantine_policy(policy_version: str) -> PolicyContainmentResult:
    """Describe fail-closed containment for a known-bad policy version."""
    return PolicyContainmentResult(
        quarantined_policy_version=policy_version,
        blocked_transitions=(
            "ACCEPTANCE",
            "CLAIM",
            "DISPATCH",
            "FAN_IN",
            "EGRESS",
        ),
        preserve_existing_evidence=True,
    )


@dataclass(frozen=True)
class IncidentOperation:
    operation_id: str
    stage: IncidentStage


@dataclass(frozen=True)
class IncidentDisposition:
    operation_id: str
    action: IncidentAction
    allocation_status: str
    preserve_evidence: bool


@dataclass(frozen=True)
class IncidentAuditEvent:
    event_id: str
    event_type: str
    operation_id: str
    evidence_reference: str


def append_incident_event(
    existing: tuple[IncidentAuditEvent, ...],
    event: IncidentAuditEvent,
) -> tuple[IncidentAuditEvent, ...]:
    """Return a new audit sequence while preserving every earlier fact."""
    if any(item.event_id == event.event_id for item in existing):
        raise ValueError("incident event identity must be unique")
    return existing + (event,)


def classify_incident_operation(
    operation: IncidentOperation,
) -> IncidentDisposition:
    """Classify one affected operation without performing remediation."""
    mapping = {
        IncidentStage.UNDISPATCHED: (
            IncidentAction.CANCEL_AND_RELEASE_CONFIRMED_UNUSED,
            "RELEASE_AFTER_NO_EFFECT_PROOF",
        ),
        IncidentStage.VERIFIED_EFFECT: (
            IncidentAction.SETTLE_AND_AUTHORIZE_COMPENSATION,
            "SETTLE_VERIFIED_USAGE",
        ),
        IncidentStage.OUTCOME_UNKNOWN: (
            IncidentAction.RECONCILE_ORIGINAL_IDENTITY_AND_HOLD,
            "HELD",
        ),
        IncidentStage.CONFIRMED_EXFILTRATION: (
            IncidentAction.CONTAIN_ROTATE_AND_AUTHORIZE_COMPENSATION,
            "SETTLE_VERIFIED_USAGE",
        ),
    }
    action, allocation_status = mapping[operation.stage]
    return IncidentDisposition(
        operation.operation_id,
        action,
        allocation_status,
        True,
    )
