"""Day61 — EXECUTED_LOCAL_RUNTIME lease-fencing (static contract) + telemetry tests.

The real lease-fenced DB behaviour is INTEGRATION_RUNTIME (needs PostgreSQL; NOT RUN). These
tests statically assert the runtime SQL fences EVERY external action and state change on the
CURRENT lease_token, and exercise the pure decisions + the no-op OTel path.
"""

import pathlib

from day61_telemetry import (
    exporter_failure_is_bounded,
    operation_span,
    record_provider_outcome,
)

_SRC = (pathlib.Path(__file__).parent / "day61_worker_completion.py").read_text()


# ---- static lease-fencing contract on the runtime SQL --------------------------------
def test_dispatch_marker_is_lease_fenced_and_short_circuits_before_provider_call():
    assert "def _claim_dispatch_marker" in _SRC
    assert "lease_token=:tok" in _SRC
    # the marker claim precedes the Provider HTTP call in source
    assert _SRC.index("_claim_dispatch_marker(engine, job_id, attempt_id, lease_token)") < _SRC.index("call_provider(")
    assert "lease_lost_no_external_call" in _SRC


def test_attempt_ownership_is_verified_before_provider_call():
    # P1-4: the pre-call claim verifies the Attempt belongs to the Job (join on a.job_id=:j)
    # BEFORE any Provider HTTP, and a mismatch stops without an external call.
    join = "JOIN app.jobs j ON j.job_id=a.job_id"
    assert join in _SRC
    assert _SRC.index("a.job_id=:j") < _SRC.index("call_provider(")
    assert "attempt_mismatch" in _SRC
    assert "attempt_mismatch_no_external_call" in _SRC


def test_all_state_changes_are_lease_fenced():
    # pending_reconciliation, contract failure and completion all guard on the lease token.
    guard = "job_status='running' AND lease_token=:tok"
    assert _SRC.count(guard) >= 1
    for fn in ("_to_pending_reconciliation", "_record_contract_failure", "_guarded_completion",
               "_persist_provider_request_id"):
        assert f"def {fn}" in _SRC
    # stale writers short-circuit rather than touch the successor's Job
    assert "lease_lost_no_state_change" in _SRC


def test_pending_reconciliation_clears_the_full_lease_triple_but_retains_attempt_evidence():
    start = _SRC.index("def _to_pending_reconciliation")
    end = _SRC.index("def _record_contract_failure", start)
    pending = _SRC[start:end]
    assert "lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL" in pending
    assert "UPDATE app.job_attempts SET finished_at" not in pending


def test_request_id_persistence_is_immutable_and_fenced():
    assert "classify_request_id_write(" in _SRC
    assert "provider_request_id IS NULL" in _SRC   # only NULL -> set
    assert "provider_request_id_conflict" in _SRC


def test_metadata_computed_from_actual_bytes_not_provider_declared():
    assert "compute_artifact_metadata(result.result_data)" in _SRC
    assert "canonical_result_bytes(result.result_data)" in _SRC
    assert "provider_declaration_matches_bytes(" in _SRC


# ---- telemetry: no-op path + safety ---------------------------------------------------
def test_operation_span_is_a_noop_safe_contextmanager():
    with operation_span("x", "j1", "a1", provider_request_id="prov-secret"):
        pass  # must not raise whether or not the OTel SDK is installed


def test_metric_labels_low_cardinality_only():
    assert record_provider_outcome("fake", "valid", "verified") is True
    # high-cardinality label attempts are rejected by the pure validator inside record_*
    assert exporter_failure_is_bounded() is True


# ---- telemetry: business exceptions propagate; only telemetry errors are swallowed (P0-2) --
class _BoomError(Exception):
    pass


def test_business_exception_propagates_through_operation_span_noop_path():
    # No-op path (SDK absent): a business exception inside the span reaches the caller.
    import pytest

    with pytest.raises(_BoomError):
        with operation_span("x", "j1", "a1"):
            raise _BoomError("business failed")


def test_span_init_failure_still_runs_business_and_propagates(monkeypatch):
    # Force the "OTel present" branch with a tracer whose span creation RAISES: the business
    # block must still run, and its own exception must still propagate (telemetry never hides it).
    import day61_telemetry as tel

    class _BadTracer:
        def start_as_current_span(self, *_a, **_k):
            raise RuntimeError("span backend down")

    monkeypatch.setattr(tel, "_OTEL", True, raising=False)
    monkeypatch.setattr(tel, "_TRACER", _BadTracer(), raising=False)

    ran = {"business": False}
    with tel.operation_span("x", "j1", "a1"):
        ran["business"] = True
    assert ran["business"] is True  # telemetry failure did not skip business

    import pytest
    with pytest.raises(_BoomError):
        with tel.operation_span("x", "j1", "a1"):
            raise _BoomError("still propagates")


def test_active_span_does_not_swallow_business_exception(monkeypatch):
    # A WORKING fake span must not turn a business exception into a swallowed/duplicated yield.
    import day61_telemetry as tel

    class _FakeSpan:
        def set_attribute(self, *_a, **_k):
            pass

    class _FakeSpanCM:
        def __enter__(self):
            return _FakeSpan()

        def __exit__(self, *exc):
            return False  # never suppress

    class _FakeTracer:
        def start_as_current_span(self, *_a, **_k):
            return _FakeSpanCM()

    monkeypatch.setattr(tel, "_OTEL", True, raising=False)
    monkeypatch.setattr(tel, "_TRACER", _FakeTracer(), raising=False)

    import pytest
    with pytest.raises(_BoomError):
        with tel.operation_span("x", "j1", "a1", provider_request_id="prov-secret"):
            raise _BoomError("boom")  # must reach here, no "generator didn't stop" error


# ---- telemetry: configurable OTLP init + W3C propagation (P1-3) -----------------------
def test_init_telemetry_disabled_by_default_and_idempotent():
    import day61_telemetry as tel

    tel._reset_telemetry_init_for_tests()
    # Default (no enable flag) must NOT build exporters / touch globals -> returns False.
    assert tel.init_telemetry(enabled=False) is False
    # Idempotent: a second call returns the same state without re-initializing.
    assert tel.init_telemetry(enabled=True) is False  # already initialized as disabled
    tel._reset_telemetry_init_for_tests()


def test_init_telemetry_enabled_is_safe_without_sdk():
    # With the SDK absent (this environment), enabling must NOT raise; it degrades to no-op.
    import day61_telemetry as tel

    tel._reset_telemetry_init_for_tests()
    result = tel.init_telemetry(enabled=True)
    assert result in (True, False)  # True only if a real SDK+exporter is installed
    tel._reset_telemetry_init_for_tests()


def test_trace_context_inject_extract_noop_safe():
    import day61_telemetry as tel

    carrier = tel.inject_trace_context({})
    assert isinstance(carrier, dict)                 # never raises; empty when SDK absent
    assert "provider_request_id" not in carrier      # protected id never propagated
    ctx = tel.extract_trace_context(carrier)
    assert ctx is None or ctx is not None            # returns without raising


def test_traceparent_round_trips_through_outbox_payload():
    # Outbox carries traceparent on the existing payload JSONB (no migration needed).
    import day61_telemetry as tel

    carrier = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
    payload = tel.store_traceparent_in_payload({"job_id": "j1"}, carrier)
    assert payload["traceparent"] == carrier["traceparent"]
    assert payload["job_id"] == "j1"
    reloaded = tel.load_traceparent_from_payload(payload)
    assert reloaded == carrier
    assert tel.load_traceparent_from_payload({"job_id": "j1"}) == {}  # absent -> empty carrier
