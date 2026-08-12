"""Day61 — deterministic FAKE HTTP Provider (a SEPARATE process, not an in-process mock).

Run standalone (a real process the adapter calls over real HTTP):

    DAY61_FAKE_PROVIDER_PORT=9099 python3 day61_fake_provider.py

It verifies REAL HTTP serialization, timeout, header/context propagation, and keeps an
INDEPENDENT request ledger (evidence that survives the Worker). It is NOT a real model
Provider and proves NOTHING about real model cost, rate limits, quality or production
behavior. No secrets/credentials are stored.

Modes (chosen by the request's ``mode`` field or the ``X-Provider-Mode`` header):
  * ``success``          -> HTTP 200 with a valid response contract (returns provider_request_id + artifact info).
  * ``timeout``          -> RECORD the request in the ledger FIRST, then delay beyond the client timeout
                            (receipt happened; the client's timeout does NOT prove non-execution).
  * ``invalid_response`` -> HTTP 200 whose body VIOLATES the response contract.

The ledger records the caller's stable correlation/idempotency key (``X-Correlation-Key``)
and the minted ``provider_request_id`` so a reconciliation query can confirm receipt.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class RequestLedger:
    """Independent, in-memory receipt ledger (evidence). A real deployment would persist it;
    here it is process-local and exposed for tests."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.entries: list[dict[str, Any]] = []

    def record(self, correlation_key: str, mode: str, provider_request_id: str) -> None:
        with self._lock:
            self.entries.append(
                {
                    "correlation_key": correlation_key,
                    "mode": mode,
                    "provider_request_id": provider_request_id,
                    "received_at": time.time(),
                }
            )

    def find_by_correlation(self, correlation_key: str) -> list[dict[str, Any]]:
        with self._lock:
            return [e for e in self.entries if e["correlation_key"] == correlation_key]


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
            provider_request_id = "prov-" + uuid.uuid4().hex

            # RECEIPT IS RECORDED FIRST — even for timeout — so the ledger proves receipt.
            ledger.record(correlation_key, mode, provider_request_id)

            if mode == "timeout":
                time.sleep(timeout_delay_seconds)  # exceed the client's timeout AFTER receipt
                self._send(200, {"provider_request_id": provider_request_id, "status": "ok",
                                  "artifact": {"checksum": "sha256:x", "size_bytes": 1,
                                               "content_type": "application/json"}})
                return
            if mode == "invalid_response":
                # HTTP 200 but the body violates the contract (missing provider_request_id/artifact).
                self._send(200, {"unexpected": "no contract fields here"})
                return
            # success
            self._send(200, {
                "provider_request_id": provider_request_id,
                "status": "ok",
                "artifact": {"checksum": "sha256:deadbeef", "size_bytes": 42,
                             "content_type": "application/json"},
            })

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
