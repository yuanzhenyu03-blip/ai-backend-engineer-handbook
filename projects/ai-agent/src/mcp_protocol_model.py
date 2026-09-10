"""Day89 SDK-independent MCP protocol boundary.

This module models only the protocol checks needed before Day90 builds a full
client.  MCP data remains separate from application operation identity and
never commits durable business state directly.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol


CURRENT_SPECIFICATION_VERSION = "2026-07-28"
SUPPORTED_SPECIFICATION_VERSIONS = frozenset({CURRENT_SPECIFICATION_VERSION})


class ProtocolOutcome(str, Enum):
    PROTOCOL_RESULT = "PROTOCOL_RESULT"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    INVALID_MESSAGE = "INVALID_MESSAGE"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    UNKNOWN_METHOD = "UNKNOWN_METHOD"
    CAPABILITY_REJECTED = "CAPABILITY_REJECTED"
    UNKNOWN_RESPONSE = "UNKNOWN_RESPONSE"
    DUPLICATE = "DUPLICATE"
    CONFLICT = "CONFLICT"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"


class BindingStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    CONFLICT = "CONFLICT"


class ReconciliationOutcome(str, Enum):
    """Application-side classification of evidence for an unknown outcome."""

    EVIDENCE_VALIDATED = "EVIDENCE_VALIDATED"
    RECONCILIATION_CONFLICT = "RECONCILIATION_CONFLICT"


class ReconciledOperationStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"


class ComplianceOutcome(str, Enum):
    COMPLIANT = "COMPLIANT"
    AUTHORIZATION_VIOLATION = "AUTHORIZATION_VIOLATION"


class ExternalContentKind(str, Enum):
    RESOURCE = "RESOURCE"
    PROMPT = "PROMPT"


class OutputValidationOutcome(str, Enum):
    REFERENCE_ADMITTED = "REFERENCE_ADMITTED"
    RESOURCE_SCOPE_REJECTED = "RESOURCE_SCOPE_REJECTED"
    UNTRUSTED_PROMPT = "UNTRUSTED_PROMPT"
    INDIRECT_PROMPT_INJECTION = "INDIRECT_PROMPT_INJECTION"


METHOD_CAPABILITIES: Mapping[str, str | None] = {
    "server/discover": None,
    "tools/call": "tools",
    "resources/read": "resources",
    "prompts/get": "prompts",
}


RequestId = str | int


@dataclass(frozen=True)
class MCPRequestDTO:
    """Application-owned representation of one self-contained MCP request."""

    specification_version: str
    protocol_request_id: RequestId
    method: str
    params: Mapping[str, Any]
    client_capabilities: frozenset[str] = frozenset()
    observed_server_capabilities: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MCPResponseDTO:
    """Minimal JSON-RPC response; exactly one of result or error is present."""

    protocol_request_id: RequestId
    result: Mapping[str, Any] | None = None
    error: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class MCPRequestBinding:
    """Trusted local mapping; application identity never comes from a peer."""

    protocol_request_id: RequestId
    application_operation_id: str
    expected_method: str
    request_fingerprint: str
    tenant_id: str | None = None
    resource_id: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class ReconciliationEvidence:
    """Claim about an external side effect; still untrusted until validated."""

    application_operation_id: str
    tenant_id: str
    resource_id: str
    idempotency_key: str
    external_object_id: str


@dataclass(frozen=True)
class ReconciliationDecision:
    """Validation result only; a separate Committer owns durable repair."""

    outcome: ReconciliationOutcome
    application_operation_id: str
    external_object_id: str | None = None
    reason: str | None = None
    durable_transition: bool = False


@dataclass(frozen=True)
class ReconciliationRepairProposal:
    """Proposed fact repair; still requires a Committer to persist it."""

    application_operation_id: str
    operation_status: ReconciledOperationStatus
    compliance_outcome: ComplianceOutcome
    external_object_id: str
    external_tool_calls: int = 0
    durable_transition: bool = False


@dataclass(frozen=True)
class ExternalContentCandidate:
    """Metadata-only external content candidate; content is not fetched here."""

    kind: ExternalContentKind
    source_id: str
    tenant_id: str | None = None
    resource_id: str | None = None
    injection_suspected: bool = False


@dataclass(frozen=True)
class OutputValidationDecision:
    """Application output decision with explicit negative-effect counters."""

    outcome: OutputValidationOutcome
    reason: str
    resource_reads: int = 0
    policy_mutations: int = 0
    durable_transition: bool = False


@dataclass(frozen=True)
class ProtocolObservation:
    """Protocol evidence, not a durable business fact."""

    outcome: ProtocolOutcome
    protocol_request_id: RequestId | None
    application_operation_id: str | None = None
    payload: Mapping[str, Any] | None = None
    reason: str | None = None
    durable_transition: bool = False


class MCPTransport(Protocol):
    def send(self, request: MCPRequestDTO) -> MCPResponseDTO | None: ...


class TimeoutBeforeSend(RuntimeError):
    """The transport proves that no message left the client."""


class TimeoutAfterPossibleSend(RuntimeError):
    """The message may have reached the peer, so the outcome is unknown."""


def _is_request_id(value: object) -> bool:
    return isinstance(value, str) or (type(value) is int)


def _fingerprint(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_params(method: str, params: Mapping[str, Any]) -> bool:
    if method == "server/discover":
        return not params
    if method == "tools/call":
        return (
            set(params) == {"name", "arguments"}
            and isinstance(params.get("name"), str)
            and bool(params["name"])
            and isinstance(params.get("arguments"), Mapping)
        )
    if method == "resources/read":
        return (
            set(params) == {"uri"}
            and isinstance(params.get("uri"), str)
            and bool(params["uri"])
        )
    if method == "prompts/get":
        return (
            set(params).issubset({"name", "arguments"})
            and "name" in params
            and isinstance(params.get("name"), str)
            and bool(params["name"])
            and (
                "arguments" not in params
                or isinstance(params.get("arguments"), Mapping)
            )
        )
    return False


@dataclass
class MCPProtocolBoundary:
    """Validate, bind, dispatch and correlate a bounded MCP message subset."""

    transport: MCPTransport
    supported_versions: frozenset[str] = SUPPORTED_SPECIFICATION_VERSIONS
    bindings: dict[RequestId, MCPRequestBinding] = field(default_factory=dict)
    binding_status: dict[RequestId, BindingStatus] = field(default_factory=dict)
    response_fingerprints: dict[RequestId, str] = field(default_factory=dict)

    def dispatch(
        self,
        request: MCPRequestDTO,
        *,
        application_operation_id: str,
        tenant_id: str | None = None,
        resource_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ProtocolObservation:
        rejection = self.validate(request)
        if rejection is not None:
            return rejection
        if not application_operation_id:
            return ProtocolObservation(
                ProtocolOutcome.INVALID_MESSAGE,
                request.protocol_request_id,
                reason="empty application operation ID",
            )
        if request.protocol_request_id in self.bindings:
            return ProtocolObservation(
                ProtocolOutcome.CONFLICT,
                request.protocol_request_id,
                reason="protocol request ID already bound",
            )

        binding = MCPRequestBinding(
            request.protocol_request_id,
            application_operation_id,
            request.method,
            _fingerprint({
                "version": request.specification_version,
                "request_id": request.protocol_request_id,
                "method": request.method,
                "params": request.params,
                "client_capabilities": sorted(request.client_capabilities),
                "observed_server_capabilities": sorted(
                    request.observed_server_capabilities
                ),
            }),
            tenant_id,
            resource_id,
            idempotency_key,
        )
        self.bindings[request.protocol_request_id] = binding
        self.binding_status[request.protocol_request_id] = BindingStatus.PENDING

        try:
            response = self.transport.send(request)
        except TimeoutBeforeSend:
            self.bindings.pop(request.protocol_request_id, None)
            self.binding_status.pop(request.protocol_request_id, None)
            return ProtocolObservation(
                ProtocolOutcome.PROTOCOL_ERROR,
                request.protocol_request_id,
                application_operation_id,
                reason="timeout before send",
            )
        except TimeoutAfterPossibleSend:
            self.binding_status[request.protocol_request_id] = (
                BindingStatus.PENDING_RECONCILIATION
            )
            return ProtocolObservation(
                ProtocolOutcome.OUTCOME_UNKNOWN,
                request.protocol_request_id,
                application_operation_id,
                reason="timeout after possible send",
            )

        if response is None:
            self.binding_status[request.protocol_request_id] = (
                BindingStatus.PENDING_RECONCILIATION
            )
            return ProtocolObservation(
                ProtocolOutcome.PENDING_RECONCILIATION,
                request.protocol_request_id,
                application_operation_id,
                reason="no response available",
            )
        return self.correlate(response)

    def validate(self, request: MCPRequestDTO) -> ProtocolObservation | None:
        if request.specification_version not in self.supported_versions:
            return ProtocolObservation(
                ProtocolOutcome.UNSUPPORTED_VERSION,
                request.protocol_request_id,
                reason="unsupported specification version",
            )
        if not _is_request_id(request.protocol_request_id):
            return ProtocolObservation(
                ProtocolOutcome.INVALID_MESSAGE,
                None,
                reason="invalid protocol request ID",
            )
        if request.method not in METHOD_CAPABILITIES:
            return ProtocolObservation(
                ProtocolOutcome.UNKNOWN_METHOD,
                request.protocol_request_id,
                reason="unknown method",
            )
        if not isinstance(request.params, Mapping) or not _validate_params(
            request.method, request.params
        ):
            return ProtocolObservation(
                ProtocolOutcome.INVALID_MESSAGE,
                request.protocol_request_id,
                reason="invalid method params",
            )
        required = METHOD_CAPABILITIES[request.method]
        if (
            required is not None
            and required not in request.observed_server_capabilities
        ):
            return ProtocolObservation(
                ProtocolOutcome.CAPABILITY_REJECTED,
                request.protocol_request_id,
                reason=f"server capability not observed: {required}",
            )
        return None

    def correlate(self, response: MCPResponseDTO) -> ProtocolObservation:
        if not _is_request_id(response.protocol_request_id):
            return ProtocolObservation(
                ProtocolOutcome.INVALID_MESSAGE,
                None,
                reason="invalid response ID",
            )
        binding = self.bindings.get(response.protocol_request_id)
        if binding is None:
            return ProtocolObservation(
                ProtocolOutcome.UNKNOWN_RESPONSE,
                response.protocol_request_id,
                reason="response ID has no local binding",
            )
        if (response.result is None) == (response.error is None):
            return ProtocolObservation(
                ProtocolOutcome.INVALID_MESSAGE,
                response.protocol_request_id,
                binding.application_operation_id,
                reason="response must contain exactly one of result or error",
            )

        response_payload: Mapping[str, Any] = (
            response.result if response.result is not None else response.error or {}
        )
        claimed_operation = response_payload.get("application_operation_id")
        if (
            claimed_operation is not None
            and claimed_operation != binding.application_operation_id
        ):
            self.binding_status[response.protocol_request_id] = BindingStatus.CONFLICT
            return ProtocolObservation(
                ProtocolOutcome.CONFLICT,
                response.protocol_request_id,
                binding.application_operation_id,
                reason="peer operation ID conflicts with local binding",
            )

        fingerprint = _fingerprint({
            "id": response.protocol_request_id,
            "result": response.result,
            "error": response.error,
        })
        previous = self.response_fingerprints.get(response.protocol_request_id)
        if previous is not None:
            outcome = (
                ProtocolOutcome.DUPLICATE
                if previous == fingerprint
                else ProtocolOutcome.CONFLICT
            )
            if outcome is ProtocolOutcome.CONFLICT:
                self.binding_status[response.protocol_request_id] = (
                    BindingStatus.CONFLICT
                )
            return ProtocolObservation(
                outcome,
                response.protocol_request_id,
                binding.application_operation_id,
                reason=(
                    "identical response already observed"
                    if outcome is ProtocolOutcome.DUPLICATE
                    else "same response ID has conflicting content"
                ),
            )

        self.response_fingerprints[response.protocol_request_id] = fingerprint
        self.binding_status[response.protocol_request_id] = BindingStatus.COMPLETED
        return ProtocolObservation(
            (
                ProtocolOutcome.PROTOCOL_RESULT
                if response.result is not None
                else ProtocolOutcome.PROTOCOL_ERROR
            ),
            response.protocol_request_id,
            binding.application_operation_id,
            payload=response_payload,
        )


def validate_reconciliation_evidence(
    binding: MCPRequestBinding,
    evidence: ReconciliationEvidence,
) -> ReconciliationDecision:
    """Fail closed unless every application-owned correlation field matches."""

    expected = {
        "application_operation_id": binding.application_operation_id,
        "tenant_id": binding.tenant_id,
        "resource_id": binding.resource_id,
        "idempotency_key": binding.idempotency_key,
    }
    observed = {
        "application_operation_id": evidence.application_operation_id,
        "tenant_id": evidence.tenant_id,
        "resource_id": evidence.resource_id,
        "idempotency_key": evidence.idempotency_key,
    }
    mismatches = [
        field_name
        for field_name, expected_value in expected.items()
        if expected_value is None or observed[field_name] != expected_value
    ]
    if mismatches:
        return ReconciliationDecision(
            ReconciliationOutcome.RECONCILIATION_CONFLICT,
            binding.application_operation_id,
            reason="reconciliation evidence mismatch: " + ", ".join(mismatches),
        )
    return ReconciliationDecision(
        ReconciliationOutcome.EVIDENCE_VALIDATED,
        binding.application_operation_id,
        external_object_id=evidence.external_object_id,
    )


def propose_fact_repair(
    decision: ReconciliationDecision,
    *,
    authorization_valid_at_effect: bool,
) -> ReconciliationRepairProposal:
    """Represent truth and compliance separately without replaying the tool."""

    if (
        decision.outcome is not ReconciliationOutcome.EVIDENCE_VALIDATED
        or decision.external_object_id is None
    ):
        raise ValueError("fact repair requires validated reconciliation evidence")
    return ReconciliationRepairProposal(
        application_operation_id=decision.application_operation_id,
        operation_status=ReconciledOperationStatus.SUCCEEDED,
        compliance_outcome=(
            ComplianceOutcome.COMPLIANT
            if authorization_valid_at_effect
            else ComplianceOutcome.AUTHORIZATION_VIOLATION
        ),
        external_object_id=decision.external_object_id,
    )


def validate_external_content_candidate(
    binding: MCPRequestBinding,
    candidate: ExternalContentCandidate,
) -> OutputValidationDecision:
    """Validate metadata before any Resource read or Prompt interpretation."""

    if candidate.kind is ExternalContentKind.PROMPT:
        return OutputValidationDecision(
            (
                OutputValidationOutcome.INDIRECT_PROMPT_INJECTION
                if candidate.injection_suspected
                else OutputValidationOutcome.UNTRUSTED_PROMPT
            ),
            "server Prompt remains untrusted application input",
        )
    if (
        binding.tenant_id is None
        or binding.resource_id is None
        or candidate.tenant_id != binding.tenant_id
        or candidate.resource_id != binding.resource_id
    ):
        return OutputValidationDecision(
            OutputValidationOutcome.RESOURCE_SCOPE_REJECTED,
            "Resource tenant or identity does not match local binding",
        )
    return OutputValidationDecision(
        OutputValidationOutcome.REFERENCE_ADMITTED,
        "Resource reference metadata matches; content remains unread",
    )
