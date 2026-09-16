"""Day93 JWKS cache/refresh boundary without raw credential retention."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol


class JWKSRefreshUnavailable(RuntimeError):
    """The trusted key dependency could not be refreshed."""


class JWKSRefreshPort(Protocol):
    def refresh_unknown_key(self, key_id: str) -> bytes | None: ...


class KeyResolutionOutcome(str, Enum):
    RESOLVED_FROM_CACHE = "RESOLVED_FROM_CACHE"
    RESOLVED_AFTER_REFRESH = "RESOLVED_AFTER_REFRESH"
    UNKNOWN_SIGNING_KEY = "UNKNOWN_SIGNING_KEY"
    AUTHENTICATION_DEPENDENCY_UNAVAILABLE = (
        "AUTHENTICATION_DEPENDENCY_UNAVAILABLE"
    )


@dataclass(frozen=True)
class KeyResolutionDecision:
    outcome: KeyResolutionOutcome
    signing_key: bytes | None
    http_status: int | None
    refresh_attempted: bool
    reused_principal: bool = False
    reused_authorization_permit: bool = False
    authorization_calls: int = 0
    handler_calls: int = 0
    controlled_service_calls: int = 0


class RefreshingJWKSResolver:
    """Known cached keys may work; an unknown key requires a fresh trust fact."""

    def __init__(
        self,
        initial_keys: Mapping[str, bytes],
        refresh: JWKSRefreshPort,
    ) -> None:
        self._keys = dict(initial_keys)
        self._refresh = refresh

    def resolve(self, key_id: str) -> KeyResolutionDecision:
        if not key_id:
            raise ValueError("key_id must not be empty")
        cached = self._keys.get(key_id)
        if cached is not None:
            return KeyResolutionDecision(
                KeyResolutionOutcome.RESOLVED_FROM_CACHE,
                cached,
                http_status=None,
                refresh_attempted=False,
            )
        try:
            refreshed = self._refresh.refresh_unknown_key(key_id)
        except JWKSRefreshUnavailable:
            return KeyResolutionDecision(
                KeyResolutionOutcome.AUTHENTICATION_DEPENDENCY_UNAVAILABLE,
                signing_key=None,
                http_status=503,
                refresh_attempted=True,
            )
        if refreshed is None:
            return KeyResolutionDecision(
                KeyResolutionOutcome.UNKNOWN_SIGNING_KEY,
                signing_key=None,
                http_status=401,
                refresh_attempted=True,
            )
        self._keys[key_id] = refreshed
        return KeyResolutionDecision(
            KeyResolutionOutcome.RESOLVED_AFTER_REFRESH,
            refreshed,
            http_status=None,
            refresh_attempted=True,
        )
