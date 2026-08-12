"""Day61 — EXECUTED_LOCAL_RUNTIME test: the SEPARATE fake Provider over REAL HTTP loopback.

Starts the deterministic fake HTTP Provider on 127.0.0.1 (ephemeral port) in a background
thread and drives it through the real ``day61_provider_adapter`` over real sockets/HTTP.
This proves REAL HTTP serialization, the timeout-after-receipt semantics, correlation-key
propagation, and the independent request ledger — WITHOUT Docker/PostgreSQL/MinIO/Celery.

This is NOT the full INTEGRATION_RUNTIME matrix (no PostgreSQL/Object Storage/OTel/broker):
those remain NOT RUN (see the design/runbook).
"""

import threading

from day61_fake_provider import build_server
from day61_provider_adapter import call_provider
from day61_provider_artifact_logic import ProviderOutcome


def _serve(server):
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t


def test_success_over_real_http_returns_valid_with_request_id_and_ledger():
    server, ledger = build_server(port=0)
    _serve(server)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/invoke"
        r = call_provider(url, correlation_key="corr-1", mode="success", timeout_seconds=2.0)
        assert r.outcome is ProviderOutcome.VALID
        assert r.provider_request_id and r.checksum and r.size_bytes and r.content_type
        # independent ledger recorded the receipt against OUR correlation key
        assert len(ledger.find_by_correlation("corr-1")) == 1
    finally:
        server.shutdown()


def test_invalid_200_body_is_invalid_outcome():
    server, ledger = build_server(port=0)
    _serve(server)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/invoke"
        r = call_provider(url, correlation_key="corr-2", mode="invalid_response", timeout_seconds=2.0)
        assert r.outcome is ProviderOutcome.INVALID_BODY
        assert len(ledger.find_by_correlation("corr-2")) == 1   # still received
    finally:
        server.shutdown()


def test_timeout_after_receipt_records_ledger_but_client_times_out():
    # Server delays 2s AFTER recording receipt; client timeout is 0.3s.
    server, ledger = build_server(port=0, timeout_delay_seconds=2.0)
    _serve(server)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/invoke"
        r = call_provider(url, correlation_key="corr-3", mode="timeout", timeout_seconds=0.3)
        assert r.outcome is ProviderOutcome.TIMEOUT       # client did NOT get a response in time
        assert len(ledger.find_by_correlation("corr-3")) == 1   # but the Provider DID receive it
    finally:
        server.shutdown()
