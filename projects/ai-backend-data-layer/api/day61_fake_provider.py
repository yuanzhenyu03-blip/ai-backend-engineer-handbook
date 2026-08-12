"""Day61 — deterministic FAKE HTTP Provider (a SEPARATE process, not an in-process mock).

Run standalone (a real process the adapter calls over real HTTP):

    DAY61_FAKE_PROVIDER_PORT=9099 python3 day61_fake_provider.py

It verifies REAL HTTP serialization, timeout, header/context propagation, and keeps an
INDEPENDENT idempotency ledger (evidence that survives the Worker). It is NOT a real model
Provider and proves NOTHING about real model cost, rate limits, quality or production
behavior. No secrets/credentials are stored.

Idempotency (P0): the Provider dedupes on the caller's STABLE correlation/idempotency key
(``X-Correlation-Key``). The FIRST request for a key mints exactly ONE external operation
(one ``provider_request_id`` + one result payload + mode + receipt time). Every later request
carrying the SAME key returns that SAME ``provider_request_id`` and the SAME result WITHOUT
creating a second external operation — so a Worker retry of one Attempt can never cause a
second billable Provider execution. The ledger records EACH call attempt separately, proving
"one external operation, many call attempts". A same-key request with an INCOMPATIBLE
``mode``/business parameter is rejected with HTTP 409 (never a silent reuse of the wrong
result).

Modes (chosen by the request's ``mode`` field or the ``X-Provider-Mode`` header):
  * ``success``          -> HTTP 200 with a valid response contract (provider_request_id + artifact info).
  * ``timeout``          -> RECORD the operation FIRST, then (only on the FIRST call) delay beyond
                            the client timeout (receipt happened; the client's timeout does NOT
                            prove non-execution). A later same-key call returns the stored result
                            immediately (reconciliation), still ONE external operation.
  * ``invalid_response`` -> HTTP 200 whose body VIOLATES the response contract.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from day61_provider_artifact_logic import RESULT_CONTENT_TYPE, compute_artifact_metadata


class CorrelationConflict(Exception):
    """A request reused an existing correlation key with an incompatible mode/parameter."""


class RequestLedger:
    """Independent, in-memory idempotency ledger (evidence). A real deployment would persist it;
    here it is process-local and exposed for tests.

    * ``_operations``    — at most ONE external operation per correlation key.
    * ``_call_attempts`` — EVERY inbound call attempt (created or reused), so a reconciliation
      query can prove "one external operation, many call attempts".
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._operations: dict[str, dict[str, Any]] = {}
        self._call_attempts: list[dict[str, Any]] = []

    def get_or_create(
        self, correlation_key: str, mode: str, make_operation: Callable[[], dict[str, Any]]
    ) -> tuple[dict[str, Any], bool]:
        """Return ``(operation, created)`` for ``correlation_key``. The first call for a key
        builds and stores exactly one operation; later calls with the SAME key and SAME mode
        reuse it. A later call with a DIFFERENT mode raises :class:`CorrelationConflict`.

        An empty correlation key cannot be deduped, so each empty-key call gets a fresh
        synthetic key (its own operation) rather than being merged with unrelated calls."""
        effective_key = correlation_key or ("nokey-" + uuid.uuid4().hex)
        with self._lock:
            existing = self._operations.get(effective_key)
            if existing is not None:
                if existing["mode"] != mode:
                    self._call_attempts.append(
                        {"correlation_key": effective_key, "mode": mode,
                         "provider_request_id": None, "reused": False,
                         "outcome": "conflict", "at": time.time()}
                    )
                    raise CorrelationConflict(effective_key)
                self._call_attempts.append(
                    {"correlation_key": effective_key, "mode": mode,
                     "provider_request_id": existing["provider_request_id"], "reused": True,
                     "outcome": "reused", "at": time.time()}
                )
                return existing, False
            op = make_operation()
            op.setdefault("correlation_key", effective_key)
            op.setdefault("mode", mode)
            op.setdefault("received_at", time.time())
            self._operations[effective_key] = op
            self._call_attempts.append(
                {"correlation_key": effective_key, "mode": mode,
                 "provider_request_id": op["provider_request_id"], "reused": False,
                 "outcome": "created", "at": op["received_at"]}
            )
            return op, True

    def find_by_correlation(self, correlation_key: str) -> list[dict[str, Any]]:
        """The external OPERATIONS for a key (0 or 1). Idempotency means this never exceeds 1."""
        with self._lock:
            op = self._operations.get(correlation_key)
            return [op] if op is not None else []

    def call_attempts_for(self, correlation_key: str) -> list[dict[str, Any]]:
        """Every inbound call attempt for a key (created + reused + conflict) — evidence that
        multiple call attempts mapped to ONE external operation."""
        with self._lock:
            return [a for a in self._call_attempts if a["correlation_key"] == correlation_key]

    @property
    def operations(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._operations.values())


def _build_operation(mode: str, correlation_key: str) -> dict[str, Any]:
    """Build the ONE stored operation for a correlation key: a minted provider_request_id and
    the exact response body every later same-key call will reuse."""
    provider_request_id = "prov-" + uuid.uuid4().hex
    if mode == "invalid_response":
        body: dict[str, Any] = {"unexpected": "no contract fields here"}
    else:  # success / timeout share the valid success body
        result_data = {"summary": "ok", "correlation_key": correlation_key}
        meta = compute_artifact_metadata(result_data)
        body = {
            "provider_request_id": provider_request_id,
            "status": "ok",
            "result": {"content_type": RESULT_CONTENT_TYPE, "data": result_data},
            "artifact": {"checksum": meta.checksum, "size_bytes": meta.size_bytes,
                         "content_type": meta.content_type},
        }
    return {"provider_request_id": provider_request_id, "mode": mode, "body": body}


def make_handler(ledger: RequestLedger, timeout_delay_seconds: float = 5.0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:  # keep test output quiet
            pass

        def do_POST(self) -> None:  # noqa: N802 (http.server API)
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                body = {}
            mode = self.headers.get("X-Provider-Mode") or body.get("mode") or "success"
            correlation_key = self.headers.get("X-Correlation-Key") or body.get("correlation_key") or ""

            # Idempotent receipt: ONE external operation per correlation key. Same-key retries
            # reuse it; an incompatible mode for the same key is a 409 conflict.
            try:
                op, created = ledger.get_or_create(correlation_key, mode, lambda: _build_operation(mode, correlation_key))
            except CorrelationConflict:
                self._send(409, {"error": "correlation_key_conflict",
                                 "detail": "same correlation_key reused with an incompatible mode/parameter"})
                return

            if mode == "timeout" and created:
                # Only the FIRST call for this key exceeds the client timeout (receipt already
                # recorded). Later same-key calls return the stored result immediately.
                time.sleep(timeout_delay_seconds)

            self._send(200, op["body"])

        def _send(self, code: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def build_server(host: str = "127.0.0.1", port: int = 0, *, timeout_delay_seconds: float = 5.0):
    """Build a ThreadingHTTPServer + its ledger. ``port=0`` picks an ephemeral port (tests)."""
    ledger = RequestLedger()
    server = ThreadingHTTPServer((host, port), make_handler(ledger, timeout_delay_seconds))
    return server, ledger


def main() -> None:  # pragma: no cover
    import os

    port = int(os.environ.get("DAY61_FAKE_PROVIDER_PORT", "9099"))
    server, _ledger = build_server("127.0.0.1", port)
    server.serve_forever()


if __name__ == "__main__":  # pragma: no cover
    main()
