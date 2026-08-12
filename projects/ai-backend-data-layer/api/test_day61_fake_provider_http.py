"""Day61 — EXECUTED_LOCAL_RUNTIME test: the SEPARATE fake Provider over REAL HTTP loopback.

Starts the deterministic fake HTTP Provider on 127.0.0.1 (ephemeral port) in a background
thread and drives it through the real ``day61_provider_adapter`` over real sockets/HTTP.
This proves REAL HTTP serialization, the timeout-after-receipt semantics, correlation-key
propagation, and the independent request ledger — WITHOUT Docker/PostgreSQL/MinIO/Celery.

This is NOT the full INTEGRATION_RUNTIME matrix (no PostgreSQL/Object Storage/OTel/broker):
those remain NOT RUN (see the design/runbook).
"""

import threading

from day61_artifact_store import InMemoryArtifactStore
from day61_fake_provider import build_server
from day61_provider_adapter import call_provider
from day61_provider_artifact_logic import (
    ArtifactVerdict,
    ProviderOutcome,
    canonical_result_bytes,
    compute_artifact_metadata,
    provider_declaration_matches_bytes,
)


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
        assert r.provider_request_id and r.result_data is not None
        # P0-1: the Provider's DECLARED metadata matches the metadata computed from the actual
        # result bytes; storing THOSE bytes HEAD-verifies as VERIFIED (never CONFLICT).
        assert provider_declaration_matches_bytes(
            r.declared_checksum, r.declared_size_bytes, r.declared_content_type, r.result_data)
        store = InMemoryArtifactStore()
        key = store.key_for("t1", "j1", "a1")
        meta = compute_artifact_metadata(r.result_data)
        verdict = store.put_if_safe(key, canonical_result_bytes(r.result_data), meta.content_type, meta)
        assert verdict is ArtifactVerdict.VERIFIED
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


def test_same_correlation_key_two_success_calls_reuse_one_operation():
    # P0-1: two success calls with the SAME correlation key must map to ONE external operation
    # (same provider_request_id + same result), never a second Provider execution.
    server, ledger = build_server(port=0)
    _serve(server)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/invoke"
        r1 = call_provider(url, correlation_key="idem-1", mode="success", timeout_seconds=2.0)
        r2 = call_provider(url, correlation_key="idem-1", mode="success", timeout_seconds=2.0)
        assert r1.outcome is ProviderOutcome.VALID and r2.outcome is ProviderOutcome.VALID
        assert r1.provider_request_id == r2.provider_request_id           # same external identity
        assert r1.result_data == r2.result_data                          # same result payload
        assert len(ledger.find_by_correlation("idem-1")) == 1            # ONE external operation
        assert len(ledger.call_attempts_for("idem-1")) == 2             # but TWO call attempts
        reused = [a for a in ledger.call_attempts_for("idem-1") if a["reused"]]
        assert len(reused) == 1                                          # the 2nd was a reuse
    finally:
        server.shutdown()


def test_same_key_incompatible_mode_is_rejected_with_conflict():
    # P0-1: reusing a correlation key with an incompatible mode must be an explicit conflict,
    # never a silent reuse of the wrong result — and must NOT create a second operation.
    import json
    import urllib.error
    import urllib.request

    server, ledger = build_server(port=0)
    _serve(server)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/invoke"
        r1 = call_provider(url, correlation_key="idem-2", mode="success", timeout_seconds=2.0)
        assert r1.outcome is ProviderOutcome.VALID
        # Second call: same key, DIFFERENT mode -> HTTP 409 conflict.
        body = json.dumps({"mode": "invalid_response", "correlation_key": "idem-2"}).encode()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "X-Correlation-Key": "idem-2", "X-Provider-Mode": "invalid_response"},
        )
        status = None
        try:
            urllib.request.urlopen(req, timeout=2.0)
        except urllib.error.HTTPError as exc:
            status = exc.code
        assert status == 409                                            # explicit conflict
        assert len(ledger.find_by_correlation("idem-2")) == 1           # still ONE operation
        assert ledger.find_by_correlation("idem-2")[0]["mode"] == "success"  # original preserved
    finally:
        server.shutdown()


def test_timeout_then_same_key_retry_returns_one_operation():
    # P0-1 + timeout-after-receipt: the first timeout call is received (client times out); a
    # later same-key call returns the SAME stored result immediately, still ONE operation.
    server, ledger = build_server(port=0, timeout_delay_seconds=2.0)
    _serve(server)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/invoke"
        first = call_provider(url, correlation_key="idem-3", mode="timeout", timeout_seconds=0.3)
        assert first.outcome is ProviderOutcome.TIMEOUT                  # client timed out
        second = call_provider(url, correlation_key="idem-3", mode="timeout", timeout_seconds=2.0)
        assert second.outcome is ProviderOutcome.VALID                   # reconciliation read
        assert len(ledger.find_by_correlation("idem-3")) == 1           # ONE external operation
        assert second.provider_request_id == ledger.find_by_correlation("idem-3")[0]["provider_request_id"]
    finally:
        server.shutdown()
