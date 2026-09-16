"""Day92 transport authentication adapter.

This is the only Day92 module in the first slice that sees a raw bearer
credential.  It extracts the credential, delegates verification, and passes
only an application-owned ``AuthenticatedPrincipal`` downstream.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Protocol

from mcp_auth import (
    AuthenticatedPrincipal,
    AuthenticationDecision,
    AuthenticationOutcome,
    AuthenticationSource,
)
from mcp_authorization import (
    AuthorizationDecision,
    AuthorizationOutcome,
    ToolAuthorizationPermit,
    ToolAuthorizationRequest,
)
from mcp_server import ServerToolDecision, ServerToolRequest


class BearerCredentialVerifier(Protocol):
    """Verify one raw bearer credential without retaining it."""

    def verify(self, credential: str) -> AuthenticationDecision: ...


class EdgeRateLimitPort(Protocol):
    """Coarse identity-independent protection, such as a source IP bucket."""

    def allow(self, source_bucket: str) -> bool: ...


class EdgeProtectionOutcome(str, Enum):
    ADMITTED = "ADMITTED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    RATE_LIMITED = "RATE_LIMITED"


@dataclass(frozen=True)
class EdgeProtectionDecision:
    outcome: EdgeProtectionOutcome
    http_status: int | None


@dataclass(frozen=True)
class HTTPPreAuthenticationGuard:
    """Cheap transport protection that neither knows nor infers a principal."""

    maximum_body_bytes: int
    rate_limit: EdgeRateLimitPort

    def check(
        self,
        *,
        content_length: int,
        source_bucket: str,
    ) -> EdgeProtectionDecision:
        if content_length < 0 or content_length > self.maximum_body_bytes:
            return EdgeProtectionDecision(
                EdgeProtectionOutcome.PAYLOAD_TOO_LARGE,
                413,
            )
        if not self.rate_limit.allow(source_bucket):
            return EdgeProtectionDecision(
                EdgeProtectionOutcome.RATE_LIMITED,
                429,
            )
        return EdgeProtectionDecision(EdgeProtectionOutcome.ADMITTED, None)


@dataclass(frozen=True)
class DeterministicHMACBearerVerifier:
    """Teaching verifier with an injected clock and trusted rotating keys.

    Production should use the issuer's standard JWT/JWKS implementation.  This
    deterministic adapter exists to make every negative security path testable.
    """

    trusted_signing_keys: Mapping[str, bytes]
    expected_issuer: str
    expected_audience: str
    now_epoch_seconds: Callable[[], int]

    def verify(self, credential: str) -> AuthenticationDecision:
        try:
            header_segment, payload_segment, signature_segment = credential.split(
                "."
            )
            header = self._decode_json_segment(header_segment)
            claims = self._decode_json_segment(payload_segment)
            supplied_signature = self._decode_segment(signature_segment)
        except (ValueError, TypeError, json.JSONDecodeError):
            return AuthenticationDecision.rejected(
                AuthenticationOutcome.MALFORMED_CREDENTIAL
            )

        if header.get("alg") != "HS256":
            return AuthenticationDecision.rejected(
                AuthenticationOutcome.INVALID_SIGNATURE
            )

        signing_key_id = header.get("kid")
        if not isinstance(signing_key_id, str):
            return AuthenticationDecision.rejected(
                AuthenticationOutcome.UNKNOWN_SIGNING_KEY
            )
        signing_key = self.trusted_signing_keys.get(signing_key_id)
        if signing_key is None:
            return AuthenticationDecision.rejected(
                AuthenticationOutcome.UNKNOWN_SIGNING_KEY
            )

        signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
        expected_signature = hmac.new(
            signing_key,
            signing_input,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return AuthenticationDecision.rejected(
                AuthenticationOutcome.INVALID_SIGNATURE
            )

        issuer = claims.get("iss")
        if issuer != self.expected_issuer:
            return AuthenticationDecision.rejected(
                AuthenticationOutcome.WRONG_ISSUER
            )

        audiences = self._audiences(claims.get("aud"))
        if self.expected_audience not in audiences:
            return AuthenticationDecision.rejected(
                AuthenticationOutcome.WRONG_AUDIENCE
            )

        expires_at = claims.get("exp")
        if type(expires_at) is not int:
            return AuthenticationDecision.rejected(
                AuthenticationOutcome.MALFORMED_CREDENTIAL
            )
        now = self.now_epoch_seconds()
        if now >= expires_at:
            return AuthenticationDecision.rejected(AuthenticationOutcome.EXPIRED)

        not_before = claims.get("nbf")
        if not_before is not None:
            if type(not_before) is not int:
                return AuthenticationDecision.rejected(
                    AuthenticationOutcome.MALFORMED_CREDENTIAL
                )
            if now < not_before:
                return AuthenticationDecision.rejected(
                    AuthenticationOutcome.NOT_YET_VALID
                )

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            return AuthenticationDecision.rejected(
                AuthenticationOutcome.MISSING_SUBJECT
            )

        scopes = self._scopes(claims.get("scope"))
        return AuthenticationDecision.accepted(AuthenticatedPrincipal(
            subject=subject,
            issuer=issuer,
            audiences=audiences,
            scopes=scopes,
            source=AuthenticationSource.HTTP_BEARER,
            expires_at=expires_at,
            client_id=self._optional_string(claims.get("client_id")),
            token_id=self._optional_string(claims.get("jti")),
            signing_key_id=signing_key_id,
        ))

    @classmethod
    def _decode_json_segment(cls, segment: str) -> dict[str, object]:
        decoded = json.loads(cls._decode_segment(segment))
        if not isinstance(decoded, dict):
            raise TypeError("JWT segment must contain a JSON object")
        return decoded

    @staticmethod
    def _decode_segment(segment: str) -> bytes:
        padding = "=" * (-len(segment) % 4)
        return base64.urlsafe_b64decode(segment + padding)

    @staticmethod
    def _audiences(value: object) -> frozenset[str]:
        if isinstance(value, str) and value:
            return frozenset({value})
        if isinstance(value, list) and all(
            isinstance(item, str) and item for item in value
        ):
            return frozenset(value)
        return frozenset()

    @staticmethod
    def _scopes(value: object) -> frozenset[str]:
        if isinstance(value, str):
            return frozenset(value.split())
        return frozenset()

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return value if isinstance(value, str) else None


class AuthenticatedToolDispatchPort(Protocol):
    """Next security stage, normally application authorization."""

    def dispatch(
        self,
        principal: AuthenticatedPrincipal,
        request: ServerToolRequest,
    ) -> None: ...


class ToolAuthorizationPort(Protocol):
    def authorize_tool(
        self,
        principal: AuthenticatedPrincipal,
        request: ToolAuthorizationRequest,
    ) -> AuthorizationDecision: ...


class AuthorizedToolExecutionPort(Protocol):
    """Execute only after receiving an exact application authorization permit."""

    def execute(
        self,
        request: ServerToolRequest,
        permit: ToolAuthorizationPermit,
    ) -> ServerToolDecision: ...


class AuthenticationGateOutcome(str, Enum):
    REJECTED = "REJECTED"
    FORWARDED_TO_AUTHORIZATION = "FORWARDED_TO_AUTHORIZATION"


@dataclass(frozen=True)
class AuthenticationGateDecision:
    outcome: AuthenticationGateOutcome
    authentication: AuthenticationDecision
    authorization_dispatches: int = 0
    handler_calls: int = 0
    controlled_service_calls: int = 0


class ToolSecurityOutcome(str, Enum):
    AUTHENTICATION_REJECTED = "AUTHENTICATION_REJECTED"
    AUTHORIZATION_REJECTED = "AUTHORIZATION_REJECTED"
    SERVER_DECIDED = "SERVER_DECIDED"


@dataclass(frozen=True)
class TrustedToolOperationContext:
    """Locally owned operation identity; never reconstructed from token claims."""

    application_operation_id: str
    idempotency_key: str
    requested_tenant_id: str


@dataclass(frozen=True)
class ToolSecurityDecision:
    outcome: ToolSecurityOutcome
    authentication: AuthenticationDecision
    authorization: AuthorizationDecision | None = None
    server: ServerToolDecision | None = None
    authentication_calls: int = 0
    authorization_calls: int = 0
    handler_calls: int = 0
    controlled_service_calls: int = 0
    durable_transitions: int = 0


def security_http_status(decision: ToolSecurityDecision) -> int | None:
    """Map only HTTP security failures; MCP protocol owns later outcomes."""
    if decision.outcome is ToolSecurityOutcome.AUTHENTICATION_REJECTED:
        return 401
    if decision.outcome is ToolSecurityOutcome.AUTHORIZATION_REJECTED:
        if (
            decision.authorization is not None
            and decision.authorization.outcome
            is AuthorizationOutcome.AUTHORIZATION_UNAVAILABLE
        ):
            return 503
        return 403
    return None


@dataclass(frozen=True)
class MCPHTTPAuthenticationBoundary:
    """Authenticate before application authorization or Day91 handling."""

    verifier: BearerCredentialVerifier
    authenticated_dispatch: AuthenticatedToolDispatchPort

    def handle_tool(
        self,
        authorization_header: str | None,
        request: ServerToolRequest,
    ) -> AuthenticationGateDecision:
        credential = self._extract_bearer(authorization_header)
        if credential is None:
            outcome = (
                AuthenticationOutcome.MISSING_CREDENTIAL
                if authorization_header is None
                else AuthenticationOutcome.MALFORMED_CREDENTIAL
            )
            return AuthenticationGateDecision(
                outcome=AuthenticationGateOutcome.REJECTED,
                authentication=AuthenticationDecision.rejected(outcome),
            )

        authentication = self.verifier.verify(credential)
        if authentication.outcome is not AuthenticationOutcome.AUTHENTICATED:
            return AuthenticationGateDecision(
                outcome=AuthenticationGateOutcome.REJECTED,
                authentication=authentication,
            )

        assert authentication.principal is not None
        self.authenticated_dispatch.dispatch(authentication.principal, request)
        return AuthenticationGateDecision(
            outcome=AuthenticationGateOutcome.FORWARDED_TO_AUTHORIZATION,
            authentication=authentication,
            authorization_dispatches=1,
        )

    @staticmethod
    def _extract_bearer(authorization_header: str | None) -> str | None:
        if authorization_header is None:
            return None
        parts = authorization_header.split()
        if (
            len(parts) != 2
            or parts[0].casefold() != "bearer"
            or not parts[1]
        ):
            return None
        return parts[1]


@dataclass(frozen=True)
class MCPStdioAuthenticationBoundary:
    """Build identity only from a trusted Launcher-owned process context."""

    trusted_launch_principal: AuthenticatedPrincipal
    authenticated_dispatch: AuthenticatedToolDispatchPort

    def __post_init__(self) -> None:
        if (
            self.trusted_launch_principal.source
            is not AuthenticationSource.STDIO_TRUSTED_LAUNCH
        ):
            raise ValueError("stdio boundary requires a trusted-launch principal")

    def handle_tool(
        self,
        request: ServerToolRequest,
    ) -> AuthenticationGateDecision:
        authentication = AuthenticationDecision.accepted(
            self.trusted_launch_principal
        )
        self.authenticated_dispatch.dispatch(
            self.trusted_launch_principal,
            request,
        )
        return AuthenticationGateDecision(
            outcome=AuthenticationGateOutcome.FORWARDED_TO_AUTHORIZATION,
            authentication=authentication,
            authorization_dispatches=1,
        )


@dataclass(frozen=True)
class MCPToolSecurityBoundary:
    """Compose HTTP authentication, application authorization and execution."""

    verifier: BearerCredentialVerifier
    authorization: ToolAuthorizationPort
    execution: AuthorizedToolExecutionPort

    def handle_tool(
        self,
        authorization_header: str | None,
        operation: TrustedToolOperationContext,
        request: ServerToolRequest,
    ) -> ToolSecurityDecision:
        credential = MCPHTTPAuthenticationBoundary._extract_bearer(
            authorization_header
        )
        if credential is None:
            auth_outcome = (
                AuthenticationOutcome.MISSING_CREDENTIAL
                if authorization_header is None
                else AuthenticationOutcome.MALFORMED_CREDENTIAL
            )
            return ToolSecurityDecision(
                outcome=ToolSecurityOutcome.AUTHENTICATION_REJECTED,
                authentication=AuthenticationDecision.rejected(auth_outcome),
            )

        authentication = self.verifier.verify(credential)
        if authentication.outcome is not AuthenticationOutcome.AUTHENTICATED:
            return ToolSecurityDecision(
                outcome=ToolSecurityOutcome.AUTHENTICATION_REJECTED,
                authentication=authentication,
                authentication_calls=1,
            )

        assert authentication.principal is not None
        authorization = self.authorization.authorize_tool(
            authentication.principal,
            ToolAuthorizationRequest(
                application_operation_id=operation.application_operation_id,
                idempotency_key=operation.idempotency_key,
                requested_tenant_id=operation.requested_tenant_id,
                tool_name=request.tool_name,
            ),
        )
        if authorization.outcome is not AuthorizationOutcome.AUTHORIZED:
            return ToolSecurityDecision(
                outcome=ToolSecurityOutcome.AUTHORIZATION_REJECTED,
                authentication=authentication,
                authorization=authorization,
                authentication_calls=1,
                authorization_calls=1,
            )

        assert authorization.permit is not None
        server = self.execution.execute(request, authorization.permit)
        return ToolSecurityDecision(
            outcome=ToolSecurityOutcome.SERVER_DECIDED,
            authentication=authentication,
            authorization=authorization,
            server=server,
            authentication_calls=1,
            authorization_calls=1,
            handler_calls=server.handler_calls,
            controlled_service_calls=server.controlled_service_calls,
            durable_transitions=server.durable_transitions,
        )
