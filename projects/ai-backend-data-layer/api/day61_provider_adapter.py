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
    # The extracted RESULT payload (data-minimized: only this is kept/stored, never the full
    # raw HTTP body) and the Provider's DECLARED artifact metadata (cross-checked against the
    # bytes computed from result_data by the Worker).
    result_data: object = None
    declared_checksum: Optional[str] = None
    declared_size_bytes: Optional[int] = None
    declared_content_type: Optional[str] = None


def _valid_contract(payload: dict) -> bool:
    art = payload.get("artifact")
    res = payload.get("result")
    return (
        isinstance(payload.get("provider_request_id"), str)
        and payload.get("provider_request_id") != ""
        and isinstance(res, dict)
        and "data" in res
        and isinstance(res.get("content_type"), str)
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
        result_data=payload["result"]["data"],
        declared_checksum=art["checksum"], declared_size_bytes=art["size_bytes"],
        declared_content_type=art["content_type"],
    )
