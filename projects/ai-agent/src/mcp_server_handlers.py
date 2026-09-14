"""Application-owned Day91 handlers behind the MCP Server Adapter."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Mapping, Protocol

from mcp_server import (
    ServerPromptDecision,
    ServerPromptOutcome,
    ServerPromptRequest,
    ServerResourceDecision,
    ServerResourceOutcome,
    ServerResourceRequest,
    ServerToolDecision,
    ServerToolOutcome,
    ServerToolRequest,
)


class ApplicationAdmissionOutcome(str, Enum):
    """Application decision made from trusted local facts."""

    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ApplicationToolPermit:
    """Trusted authority produced by the application, never by MCP payload."""

    application_operation_id: str
    tenant_id: str
    idempotency_key: str


@dataclass(frozen=True)
class ApplicationAdmissionDecision:
    """One application admission result with an optional trusted permit."""

    outcome: ApplicationAdmissionOutcome
    safe_reason: str
    permit: ApplicationToolPermit | None = None

    def __post_init__(self) -> None:
        admitted = self.outcome is ApplicationAdmissionOutcome.ADMITTED
        if admitted != (self.permit is not None):
            raise ValueError("only an admitted decision carries a permit")


class ToolAdmissionPort(Protocol):
    """Resolve current application authority from trusted local state."""

    def admit(self, request: ServerToolRequest) -> ApplicationAdmissionDecision: ...


class ResearchLookupPort(Protocol):
    """Narrow controlled service available to the lookup handler."""

    def lookup(
        self,
        query: str,
        permit: ApplicationToolPermit,
    ) -> Mapping[str, object]: ...


class ApplicationOutputValidationOutcome(str, Enum):
    """Semantic application validation after a controlled service returns."""

    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ApplicationOutputValidationDecision:
    outcome: ApplicationOutputValidationOutcome
    safe_reason: str


class ToolOutputValidationPort(Protocol):
    """Validate tenant, provenance and policy beyond JSON Schema shape."""

    def validate(
        self,
        candidate: Mapping[str, object],
        permit: ApplicationToolPermit,
    ) -> ApplicationOutputValidationDecision: ...


class OperationClaimOutcome(str, Enum):
    """Whether one application operation may enter its controlled service."""

    CLAIMED = "CLAIMED"
    DUPLICATE = "DUPLICATE"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


class OperationInvocationStatus(str, Enum):
    """Execution knowledge retained for idempotency and reconciliation."""

    IN_FLIGHT = "IN_FLIGHT"
    COMPLETED = "COMPLETED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"


@dataclass(frozen=True)
class OperationClaimDecision:
    outcome: OperationClaimOutcome
    operation_id: str


class OperationIdempotencyPort(Protocol):
    """Application-owned claim registry keyed by operation identity."""

    def try_claim(
        self,
        permit: ApplicationToolPermit,
    ) -> OperationClaimDecision: ...

    def mark_completed(self, operation_id: str) -> None: ...

    def mark_pending_reconciliation(self, operation_id: str) -> None: ...


class InMemoryOperationRegistry:
    """Thread-safe teaching registry; production uses durable storage."""

    def __init__(self) -> None:
        self._status_by_operation_id: dict[str, OperationInvocationStatus] = {}
        self._idempotency_key_by_operation_id: dict[str, str] = {}
        self._lock = Lock()

    def try_claim(
        self,
        permit: ApplicationToolPermit,
    ) -> OperationClaimDecision:
        with self._lock:
            operation_id = permit.application_operation_id
            if operation_id in self._status_by_operation_id:
                existing_key = self._idempotency_key_by_operation_id[
                    operation_id
                ]
                if existing_key != permit.idempotency_key:
                    return OperationClaimDecision(
                        OperationClaimOutcome.IDENTITY_CONFLICT,
                        operation_id,
                    )
                return OperationClaimDecision(
                    OperationClaimOutcome.DUPLICATE,
                    operation_id,
                )
            self._status_by_operation_id[operation_id] = (
                OperationInvocationStatus.IN_FLIGHT
            )
            self._idempotency_key_by_operation_id[operation_id] = (
                permit.idempotency_key
            )
            return OperationClaimDecision(
                OperationClaimOutcome.CLAIMED,
                operation_id,
            )

    def mark_completed(self, operation_id: str) -> None:
        with self._lock:
            if self._status_by_operation_id.get(operation_id) is not (
                OperationInvocationStatus.IN_FLIGHT
            ):
                raise ValueError("only an in-flight operation may complete")
            self._status_by_operation_id[operation_id] = (
                OperationInvocationStatus.COMPLETED
            )

    def mark_pending_reconciliation(self, operation_id: str) -> None:
        with self._lock:
            if operation_id not in self._status_by_operation_id:
                raise ValueError("cannot reconcile an unclaimed operation")
            self._status_by_operation_id[operation_id] = (
                OperationInvocationStatus.PENDING_RECONCILIATION
            )

    def status(self, operation_id: str) -> OperationInvocationStatus | None:
        with self._lock:
            return self._status_by_operation_id.get(operation_id)


@dataclass(frozen=True)
class ApplicationResourcePermit:
    """Trusted authority for one bounded Resource read."""

    tenant_id: str
    resource_id: str


@dataclass(frozen=True)
class ResourceAdmissionDecision:
    """Application decision made before the Resource read port is called."""

    admitted: bool
    safe_reason: str
    permit: ApplicationResourcePermit | None = None

    def __post_init__(self) -> None:
        if self.admitted != (self.permit is not None):
            raise ValueError("only an admitted Resource decision carries a permit")


class ResourceAdmissionPort(Protocol):
    """Resolve Resource authority from trusted application state."""

    def admit(
        self,
        request: ServerResourceRequest,
    ) -> ResourceAdmissionDecision: ...


class ResearchResourceReadPort(Protocol):
    """Narrow read interface; inaccessible until application admission."""

    def read(self, permit: ApplicationResourcePermit) -> str: ...


class ResourceContentClassification(str, Enum):
    """Application classification of content returned by a Resource read."""

    BENIGN = "BENIGN"
    INDIRECT_PROMPT_INJECTION = "INDIRECT_PROMPT_INJECTION"


@dataclass(frozen=True)
class ResourceContentValidationDecision:
    classification: ResourceContentClassification
    safe_reason: str


class ResourceContentValidationPort(Protocol):
    """Validate untrusted Resource content before model-context assembly."""

    def validate(
        self,
        content: str,
        permit: ApplicationResourcePermit,
    ) -> ResourceContentValidationDecision: ...


@dataclass(frozen=True)
class PromptAdmissionDecision:
    """Safety classification made before Prompt template rendering."""

    admitted: bool
    classification: str
    safe_reason: str


class PromptAdmissionPort(Protocol):
    """Classify untrusted Prompt arguments before interpolation."""

    def admit(self, request: ServerPromptRequest) -> PromptAdmissionDecision: ...


class PromptRenderPort(Protocol):
    """Render one code-owned template from admitted arguments."""

    def render(self, arguments: Mapping[str, str]) -> str: ...


@dataclass(frozen=True)
class PromptOutputValidationDecision:
    """Safety decision for the fully rendered Prompt message."""

    admitted: bool
    classification: str
    safe_reason: str


class PromptOutputValidationPort(Protocol):
    """Validate rendered messages before returning them as candidates."""

    def validate(self, rendered_text: str) -> PromptOutputValidationDecision: ...


@dataclass(frozen=True)
class ResearchLookupHandler:
    """Convert an admitted request into a non-durable result candidate."""

    admission: ToolAdmissionPort
    service: ResearchLookupPort
    idempotency: OperationIdempotencyPort
    output_validation: ToolOutputValidationPort

    def handle(self, request: ServerToolRequest) -> ServerToolDecision:
        decision = self.admission.admit(request)
        if decision.outcome is ApplicationAdmissionOutcome.REJECTED:
            return ServerToolDecision(
                outcome=ServerToolOutcome.APPLICATION_REJECTED,
                request=request,
                reason=decision.safe_reason,
                is_error=True,
                handler_calls=1,
            )

        assert decision.permit is not None
        query = request.arguments.get("query")
        if not isinstance(query, str) or not query:
            return ServerToolDecision(
                outcome=ServerToolOutcome.APPLICATION_REJECTED,
                request=request,
                reason="query must be a non-empty string",
                is_error=True,
                handler_calls=1,
            )

        claim = self.idempotency.try_claim(decision.permit)
        if claim.outcome is OperationClaimOutcome.DUPLICATE:
            return ServerToolDecision(
                outcome=ServerToolOutcome.DUPLICATE_REJECTED,
                request=request,
                reason="application operation was already claimed",
                is_error=True,
                handler_calls=1,
            )
        if claim.outcome is OperationClaimOutcome.IDENTITY_CONFLICT:
            return ServerToolDecision(
                outcome=ServerToolOutcome.IDENTITY_CONFLICT_REJECTED,
                request=request,
                reason="application operation identity conflicts with prior claim",
                is_error=True,
                handler_calls=1,
            )

        try:
            content = dict(self.service.lookup(query, decision.permit))
        except Exception:
            self.idempotency.mark_pending_reconciliation(
                decision.permit.application_operation_id
            )
            raise
        output_decision = self.output_validation.validate(
            content,
            decision.permit,
        )
        self.idempotency.mark_completed(
            decision.permit.application_operation_id
        )
        if (
            output_decision.outcome
            is ApplicationOutputValidationOutcome.REJECTED
        ):
            return ServerToolDecision(
                outcome=ServerToolOutcome.OUTPUT_REJECTED,
                request=request,
                reason=output_decision.safe_reason,
                is_error=True,
                handler_calls=1,
                controlled_service_calls=1,
            )
        return ServerToolDecision(
            outcome=ServerToolOutcome.CANDIDATE_RESULT,
            request=request,
            reason="controlled service returned a candidate result",
            is_error=False,
            structured_content=content,
            handler_calls=1,
            controlled_service_calls=1,
        )


@dataclass(frozen=True)
class ResearchResourceHandler:
    """Authorize a Resource request before invoking the bounded read port."""

    admission: ResourceAdmissionPort
    reader: ResearchResourceReadPort
    content_validation: ResourceContentValidationPort

    def handle(self, request: ServerResourceRequest) -> ServerResourceDecision:
        decision = self.admission.admit(request)
        if not decision.admitted:
            return ServerResourceDecision(
                outcome=ServerResourceOutcome.APPLICATION_REJECTED,
                request=request,
                reason=decision.safe_reason,
                resource_reads=0,
            )

        assert decision.permit is not None
        content = self.reader.read(decision.permit)
        validation = self.content_validation.validate(content, decision.permit)
        if (
            validation.classification
            is ResourceContentClassification.INDIRECT_PROMPT_INJECTION
        ):
            return ServerResourceDecision(
                outcome=(
                    ServerResourceOutcome.INDIRECT_PROMPT_INJECTION_REJECTED
                ),
                request=request,
                reason=validation.safe_reason,
                content=None,
                resource_reads=1,
            )
        return ServerResourceDecision(
            outcome=ServerResourceOutcome.CONTENT_CANDIDATE,
            request=request,
            reason="controlled Resource reader returned candidate content",
            content=content,
            resource_reads=1,
        )


@dataclass(frozen=True)
class ResearchPromptHandler:
    """Reject unsafe arguments before rendering a Prompt template."""

    admission: PromptAdmissionPort
    renderer: PromptRenderPort
    output_validation: PromptOutputValidationPort

    def handle(self, request: ServerPromptRequest) -> ServerPromptDecision:
        decision = self.admission.admit(request)
        if not decision.admitted:
            return ServerPromptDecision(
                outcome=ServerPromptOutcome.PROMPT_INJECTION_REJECTED,
                request=request,
                reason=decision.safe_reason,
                prompt_renders=0,
            )

        rendered = self.renderer.render(request.arguments)
        output_decision = self.output_validation.validate(rendered)
        if not output_decision.admitted:
            return ServerPromptDecision(
                outcome=ServerPromptOutcome.PROMPT_INJECTION_REJECTED,
                request=request,
                reason=output_decision.safe_reason,
                rendered_text=None,
                prompt_renders=1,
                tool_calls=0,
                resource_reads=0,
            )
        return ServerPromptDecision(
            outcome=ServerPromptOutcome.RENDERED_CANDIDATE,
            request=request,
            reason="code-owned Prompt template rendered admitted arguments",
            rendered_text=rendered,
            prompt_renders=1,
        )
