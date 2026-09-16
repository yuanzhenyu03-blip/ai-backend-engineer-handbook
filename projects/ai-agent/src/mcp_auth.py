"""Application-owned Day92 authentication facts.

Raw credentials are deliberately absent from this module.  A transport
adapter may inspect a credential long enough to verify it, but application
code receives only the minimized, verified identity facts below.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuthenticationSource(str, Enum):
    HTTP_BEARER = "HTTP_BEARER"
    STDIO_TRUSTED_LAUNCH = "STDIO_TRUSTED_LAUNCH"


class AuthenticationOutcome(str, Enum):
    AUTHENTICATED = "AUTHENTICATED"
    MISSING_CREDENTIAL = "MISSING_CREDENTIAL"
    MALFORMED_CREDENTIAL = "MALFORMED_CREDENTIAL"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    EXPIRED = "EXPIRED"
    NOT_YET_VALID = "NOT_YET_VALID"
    WRONG_ISSUER = "WRONG_ISSUER"
    WRONG_AUDIENCE = "WRONG_AUDIENCE"
    MISSING_SUBJECT = "MISSING_SUBJECT"
    UNKNOWN_SIGNING_KEY = "UNKNOWN_SIGNING_KEY"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Minimized verified identity facts; never a reusable credential."""

    subject: str
    issuer: str
    audiences: frozenset[str]
    scopes: frozenset[str]
    source: AuthenticationSource
    expires_at: int | None
    client_id: str | None = None
    token_id: str | None = None
    signing_key_id: str | None = None

    def __post_init__(self) -> None:
        if not self.subject:
            raise ValueError("authenticated principal requires a subject")
        if not self.issuer:
            raise ValueError("authenticated principal requires an issuer")
        if not self.audiences:
            raise ValueError("authenticated principal requires an audience")
        if self.source is AuthenticationSource.HTTP_BEARER:
            if self.expires_at is None or self.expires_at <= 0:
                raise ValueError("HTTP bearer principal requires an expiration")
        elif self.expires_at is not None and self.expires_at <= 0:
            raise ValueError("principal expiration must be positive when present")


@dataclass(frozen=True)
class AuthenticationDecision:
    """Authentication result with a safe external message."""

    outcome: AuthenticationOutcome
    safe_external_message: str
    principal: AuthenticatedPrincipal | None = None

    def __post_init__(self) -> None:
        authenticated = self.outcome is AuthenticationOutcome.AUTHENTICATED
        if authenticated != (self.principal is not None):
            raise ValueError(
                "only an authenticated decision may carry a principal"
            )

    @classmethod
    def rejected(
        cls,
        outcome: AuthenticationOutcome,
    ) -> "AuthenticationDecision":
        if outcome is AuthenticationOutcome.AUTHENTICATED:
            raise ValueError("authenticated outcome requires a principal")
        return cls(
            outcome=outcome,
            safe_external_message="Authentication required",
        )

    @classmethod
    def accepted(
        cls,
        principal: AuthenticatedPrincipal,
    ) -> "AuthenticationDecision":
        return cls(
            outcome=AuthenticationOutcome.AUTHENTICATED,
            safe_external_message="Authenticated",
            principal=principal,
        )
