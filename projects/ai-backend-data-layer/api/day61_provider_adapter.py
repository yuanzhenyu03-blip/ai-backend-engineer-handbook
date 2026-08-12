"""Day61 — Provider Adapter over REAL HTTP (standard-library ``urllib``).

Calls the SEPARATE fake HTTP Provider (or, only with explicit user authorization + supplied
credentials + a defined cost scope, a real Provider) across a process boundary, with a
timeout, a stable correlation/idempotency header, and RESPONSE-CONTRACT validation. Returns
a typed ``AdapterResult`` mapped to the pure ``ProviderOutcome`` decision core. The adapter
minimizes data: it extracts only the contract fields, never persisting the full raw body.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from day61_provider_artifact_logic import ProviderOutcome


@dataclass(frozen=True)
class AdapterResult:
    outcome: ProviderOutcome
    provider_request_id: Optional[str] = None
    checksum: Optional[str] = None
    size_bytes: Optional[int] = None
    content_type: Optional[str] = None


def _valid_contract(payload: dict) -> bool:
    art = payload.get("artifact")
    return (
        isinstance(payload.get("provider_request_id"), str)
        and payload.get("provider_request_id") != ""
        and isinstance(art, dict)
        and isinstance(art.get("checksum"), str)
        and isinstance(art.get("size_bytes"), int)
        and isinstance(art.get("content_type"), str)
    )


def call_provider(
    url: str, correlation_key: str, mode: str, *, timeout_seconds: float = 2.0
) -> AdapterResult:
    """POST to the Provider over real HTTP. ``correlation_key`` is OUR stable idempotency key
    (created before the call, reused for retries of the SAME Attempt); the Provider mints its
    own ``provider_request_id`` on receipt (distinct, complementary). A client timeout does
    NOT prove non-execution -> ``ProviderOutcome.TIMEOUT``."""
    data = json.dumps({"mode": mode, "correlation_key": correlation_key}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json",
                 "X-Correlation-Key": correlation_key, "X-Provider-Mode": mode},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:  # includes socket.timeout as exc.reason
        if isinstance(getattr(exc, "reason", None), TimeoutError) or "timed out" in str(exc).lower():
            return AdapterResult(ProviderOutcome.TIMEOUT)
        raise
    except TimeoutError:
        return AdapterResult(ProviderOutcome.TIMEOUT)

    if not _valid_contract(payload):
        return AdapterResult(ProviderOutcome.INVALID_BODY)
    art = payload["artifact"]
    return AdapterResult(
        ProviderOutcome.VALID,
        provider_request_id=payload["provider_request_id"],
        checksum=art["checksum"], size_bytes=art["size_bytes"],
        content_type=art["content_type"],
    )
