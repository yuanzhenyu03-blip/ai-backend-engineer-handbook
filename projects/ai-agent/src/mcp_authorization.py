"""Application-owned Day92 authorization and operation identity binding."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Mapping, Protocol

from mcp_auth import AuthenticatedPrincipal


class AuthorizationOutcome(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    PRINCIPAL_REVOKED = "PRINCIPAL_REVOKED"
    INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"
    TENANT_MEMBERSHIP_MISMATCH = "TENANT_MEMBERSHIP_MISMATCH"
    TOOL_PERMISSION_DENIED = "TOOL_PERMISSION_DENIED"
    PROMPT_PERMISSION_DENIED = "PROMPT_PERMISSION_DENIED"
    RESOURCE_PERMISSION_DENIED = "RESOURCE_PERMISSION_DENIED"
    PROMPT_ARGUMENT_PRIVILEGE_ESCALATION = (
        "PROMPT_ARGUMENT_PRIVILEGE_ESCALATION"
    )
    DUPLICATE = "DUPLICATE"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    AUTHORIZATION_UNAVAILABLE = "AUTHORIZATION_UNAVAILABLE"


class AuthorizationFactsUnavailable(RuntimeError):
    """Expected failure when current revocation or grant facts cannot be read."""


class OperationBindingOutcome(str, Enum):
    BOUND = "BOUND"
    DUPLICATE = "DUPLICATE"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


@dataclass(frozen=True)
class ToolAuthorizationRequest:
    """Trusted operation identity plus untrusted requested target values."""

    application_operation_id: str
    idempotency_key: str
    requested_tenant_id: str
    tool_name: str

    def __post_init__(self) -> None:
        if not self.application_operation_id:
            raise ValueError("authorization requires an application operation ID")
        if not self.idempotency_key:
            raise ValueError("authorization requires an idempotency key")
        if not self.requested_tenant_id:
            raise ValueError("authorization requires a requested tenant")
        if not self.tool_name:
            raise ValueError("authorization requires a Tool name")


@dataclass(frozen=True)
class ToolAuthorizationPermit:
    """Exact authority for one principal, operation, tenant and Tool."""

    principal_issuer: str
    principal_subject: str
    application_operation_id: str
    idempotency_key: str
    tenant_id: str
    tool_name: str


@dataclass(frozen=True)
class AuthorizationDecision:
    outcome: AuthorizationOutcome
    safe_external_message: str
    permit: ToolAuthorizationPermit | None = None

    def __post_init__(self) -> None:
        authorized = self.outcome is AuthorizationOutcome.AUTHORIZED
        if authorized != (self.permit is not None):
            raise ValueError("only an authorized decision carries a permit")


@dataclass(frozen=True)
class PromptAuthorizationRequest:
    """Requested Prompt target plus arguments that carry no authority."""

    requested_tenant_id: str
    prompt_name: str
    arguments: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.requested_tenant_id:
            raise ValueError("Prompt authorization requires a requested tenant")
        if not self.prompt_name:
            raise ValueError("Prompt authorization requires a Prompt name")


@dataclass(frozen=True)
class PromptAuthorizationPermit:
    """Exact permission to render one Prompt; never permission to call tools."""

    principal_issuer: str
    principal_subject: str
    tenant_id: str
    prompt_name: str


@dataclass(frozen=True)
class PromptAuthorizationDecision:
    outcome: AuthorizationOutcome
    safe_external_message: str
    permit: PromptAuthorizationPermit | None = None

    def __post_init__(self) -> None:
        authorized = self.outcome is AuthorizationOutcome.AUTHORIZED
        if authorized != (self.permit is not None):
            raise ValueError("only an authorized Prompt decision carries a permit")


@dataclass(frozen=True)
class ResourceAuthorizationRequest:
    """A requested Resource location, never tenant-membership evidence."""

    requested_tenant_id: str
    resource_kind: str
    resource_id: str
    resource_uri: str

    def __post_init__(self) -> None:
        if not self.requested_tenant_id:
            raise ValueError("Resource authorization requires a requested tenant")
        if not self.resource_kind:
            raise ValueError("Resource authorization requires a Resource kind")
        if not self.resource_id:
            raise ValueError("Resource authorization requires a Resource ID")
        if not self.resource_uri:
            raise ValueError("Resource authorization requires a Resource URI")


@dataclass(frozen=True)
class ResourceAuthorizationPermit:
    """Exact read authority derived from current facts, never from the URI."""

    principal_issuer: str
    principal_subject: str
    tenant_id: str
    resource_kind: str
    resource_id: str


@dataclass(frozen=True)
class ResourceAuthorizationDecision:
    outcome: AuthorizationOutcome
    safe_external_message: str
    permit: ResourceAuthorizationPermit | None = None

    def __post_init__(self) -> None:
        authorized = self.outcome is AuthorizationOutcome.AUTHORIZED
        if authorized != (self.permit is not None):
            raise ValueError("only an authorized Resource decision carries a permit")


class CurrentAuthorizationFacts(Protocol):
    """Current facts; token claims alone do not implement this port."""

    def is_principal_revoked(self, principal: AuthenticatedPrincipal) -> bool: ...

    def tenant_memberships(
        self,
        principal: AuthenticatedPrincipal,
    ) -> frozenset[str]: ...

    def permitted_tools(
        self,
        principal: AuthenticatedPrincipal,
        tenant_id: str,
    ) -> frozenset[str]: ...

    def permitted_prompts(
        self,
        principal: AuthenticatedPrincipal,
        tenant_id: str,
    ) -> frozenset[str]: ...

    def permitted_resources(
        self,
        principal: AuthenticatedPrincipal,
        tenant_id: str,
        resource_kind: str,
    ) -> frozenset[str]: ...


@dataclass(frozen=True)
class OperationAuthorizationBinding:
    principal_issuer: str
    principal_subject: str
    application_operation_id: str
    idempotency_key: str
    tenant_id: str
    tool_name: str


class OperationAuthorizationBindingPort(Protocol):
    def bind(
        self,
        binding: OperationAuthorizationBinding,
    ) -> OperationBindingOutcome: ...


class InMemoryOperationAuthorizationBindings:
    """Deterministic teaching store; production requires durable storage."""

    def __init__(self) -> None:
        self._bindings: dict[str, OperationAuthorizationBinding] = {}
        self._lock = Lock()

    def bind(
        self,
        binding: OperationAuthorizationBinding,
    ) -> OperationBindingOutcome:
        with self._lock:
            existing = self._bindings.get(binding.application_operation_id)
            if existing is None:
                self._bindings[binding.application_operation_id] = binding
                return OperationBindingOutcome.BOUND
            if existing == binding:
                return OperationBindingOutcome.DUPLICATE
            return OperationBindingOutcome.IDENTITY_CONFLICT


@dataclass(frozen=True)
class ApplicationAuthorizationService:
    facts: CurrentAuthorizationFacts
    bindings: OperationAuthorizationBindingPort
    required_scope_by_tool: Mapping[str, str]
    required_scope_by_prompt: Mapping[str, str] = field(default_factory=dict)
    required_scope_by_resource_kind: Mapping[str, str] = field(
        default_factory=dict
    )

    _PROMPT_AUTHORITY_ARGUMENTS = frozenset({
        "role",
        "scope",
        "subject",
        "tenant_id",
        "tenant_membership",
        "user_id",
    })

    def authorize_tool(
        self,
        principal: AuthenticatedPrincipal,
        request: ToolAuthorizationRequest,
    ) -> AuthorizationDecision:
        try:
            revoked = self.facts.is_principal_revoked(principal)
        except AuthorizationFactsUnavailable:
            return self._rejected(AuthorizationOutcome.AUTHORIZATION_UNAVAILABLE)
        if revoked:
            return self._rejected(AuthorizationOutcome.PRINCIPAL_REVOKED)

        required_scope = self.required_scope_by_tool.get(request.tool_name)
        if required_scope is None or required_scope not in principal.scopes:
            return self._rejected(AuthorizationOutcome.INSUFFICIENT_SCOPE)

        try:
            memberships = self.facts.tenant_memberships(principal)
        except AuthorizationFactsUnavailable:
            return self._rejected(AuthorizationOutcome.AUTHORIZATION_UNAVAILABLE)
        if request.requested_tenant_id not in memberships:
            return self._rejected(
                AuthorizationOutcome.TENANT_MEMBERSHIP_MISMATCH,
                message="Resource is unavailable",
            )

        try:
            permitted_tools = self.facts.permitted_tools(
                principal,
                request.requested_tenant_id,
            )
        except AuthorizationFactsUnavailable:
            return self._rejected(AuthorizationOutcome.AUTHORIZATION_UNAVAILABLE)
        if request.tool_name not in permitted_tools:
            return self._rejected(AuthorizationOutcome.TOOL_PERMISSION_DENIED)

        binding = OperationAuthorizationBinding(
            principal_issuer=principal.issuer,
            principal_subject=principal.subject,
            application_operation_id=request.application_operation_id,
            idempotency_key=request.idempotency_key,
            tenant_id=request.requested_tenant_id,
            tool_name=request.tool_name,
        )
        binding_outcome = self.bindings.bind(binding)
        if binding_outcome is OperationBindingOutcome.DUPLICATE:
            return self._rejected(AuthorizationOutcome.DUPLICATE)
        if binding_outcome is OperationBindingOutcome.IDENTITY_CONFLICT:
            return self._rejected(AuthorizationOutcome.IDENTITY_CONFLICT)

        return AuthorizationDecision(
            outcome=AuthorizationOutcome.AUTHORIZED,
            safe_external_message="Authorized",
            permit=ToolAuthorizationPermit(
                principal_issuer=principal.issuer,
                principal_subject=principal.subject,
                application_operation_id=request.application_operation_id,
                idempotency_key=request.idempotency_key,
                tenant_id=request.requested_tenant_id,
                tool_name=request.tool_name,
            ),
        )

    def authorize_prompt(
        self,
        principal: AuthenticatedPrincipal,
        request: PromptAuthorizationRequest,
    ) -> PromptAuthorizationDecision:
        """Authorize rendering only; Prompt arguments cannot mint authority."""
        try:
            revoked = self.facts.is_principal_revoked(principal)
        except AuthorizationFactsUnavailable:
            return self._prompt_rejected(
                AuthorizationOutcome.AUTHORIZATION_UNAVAILABLE
            )
        if revoked:
            return self._prompt_rejected(AuthorizationOutcome.PRINCIPAL_REVOKED)

        required_scope = self.required_scope_by_prompt.get(request.prompt_name)
        if required_scope is None or required_scope not in principal.scopes:
            return self._prompt_rejected(AuthorizationOutcome.INSUFFICIENT_SCOPE)

        if self._PROMPT_AUTHORITY_ARGUMENTS.intersection(request.arguments):
            return self._prompt_rejected(
                AuthorizationOutcome.PROMPT_ARGUMENT_PRIVILEGE_ESCALATION,
            )

        try:
            memberships = self.facts.tenant_memberships(principal)
        except AuthorizationFactsUnavailable:
            return self._prompt_rejected(
                AuthorizationOutcome.AUTHORIZATION_UNAVAILABLE
            )
        if request.requested_tenant_id not in memberships:
            return self._prompt_rejected(
                AuthorizationOutcome.TENANT_MEMBERSHIP_MISMATCH,
                message="Resource is unavailable",
            )

        try:
            permitted_prompts = self.facts.permitted_prompts(
                principal,
                request.requested_tenant_id,
            )
        except AuthorizationFactsUnavailable:
            return self._prompt_rejected(
                AuthorizationOutcome.AUTHORIZATION_UNAVAILABLE
            )
        if request.prompt_name not in permitted_prompts:
            return self._prompt_rejected(
                AuthorizationOutcome.PROMPT_PERMISSION_DENIED,
            )

        return PromptAuthorizationDecision(
            outcome=AuthorizationOutcome.AUTHORIZED,
            safe_external_message="Authorized",
            permit=PromptAuthorizationPermit(
                principal_issuer=principal.issuer,
                principal_subject=principal.subject,
                tenant_id=request.requested_tenant_id,
                prompt_name=request.prompt_name,
            ),
        )

    def authorize_resource(
        self,
        principal: AuthenticatedPrincipal,
        request: ResourceAuthorizationRequest,
    ) -> ResourceAuthorizationDecision:
        """Authorize an exact read from current facts, not URI contents."""
        try:
            revoked = self.facts.is_principal_revoked(principal)
        except AuthorizationFactsUnavailable:
            return self._resource_rejected(
                AuthorizationOutcome.AUTHORIZATION_UNAVAILABLE
            )
        if revoked:
            return self._resource_rejected(AuthorizationOutcome.PRINCIPAL_REVOKED)

        required_scope = self.required_scope_by_resource_kind.get(
            request.resource_kind
        )
        if required_scope is None or required_scope not in principal.scopes:
            return self._resource_rejected(AuthorizationOutcome.INSUFFICIENT_SCOPE)

        try:
            memberships = self.facts.tenant_memberships(principal)
        except AuthorizationFactsUnavailable:
            return self._resource_rejected(
                AuthorizationOutcome.AUTHORIZATION_UNAVAILABLE
            )
        if request.requested_tenant_id not in memberships:
            return self._resource_rejected(
                AuthorizationOutcome.TENANT_MEMBERSHIP_MISMATCH,
                message="Resource is unavailable",
            )

        try:
            permitted_resource_ids = self.facts.permitted_resources(
                principal,
                request.requested_tenant_id,
                request.resource_kind,
            )
        except AuthorizationFactsUnavailable:
            return self._resource_rejected(
                AuthorizationOutcome.AUTHORIZATION_UNAVAILABLE
            )
        if request.resource_id not in permitted_resource_ids:
            return self._resource_rejected(
                AuthorizationOutcome.RESOURCE_PERMISSION_DENIED,
                message="Resource is unavailable",
            )

        return ResourceAuthorizationDecision(
            outcome=AuthorizationOutcome.AUTHORIZED,
            safe_external_message="Authorized",
            permit=ResourceAuthorizationPermit(
                principal_issuer=principal.issuer,
                principal_subject=principal.subject,
                tenant_id=request.requested_tenant_id,
                resource_kind=request.resource_kind,
                resource_id=request.resource_id,
            ),
        )

    @staticmethod
    def _rejected(
        outcome: AuthorizationOutcome,
        *,
        message: str = "Operation is not permitted",
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            outcome=outcome,
            safe_external_message=message,
        )

    @staticmethod
    def _prompt_rejected(
        outcome: AuthorizationOutcome,
        *,
        message: str = "Operation is not permitted",
    ) -> PromptAuthorizationDecision:
        return PromptAuthorizationDecision(
            outcome=outcome,
            safe_external_message=message,
        )

    @staticmethod
    def _resource_rejected(
        outcome: AuthorizationOutcome,
        *,
        message: str = "Operation is not permitted",
    ) -> ResourceAuthorizationDecision:
        return ResourceAuthorizationDecision(
            outcome=outcome,
            safe_external_message=message,
        )
