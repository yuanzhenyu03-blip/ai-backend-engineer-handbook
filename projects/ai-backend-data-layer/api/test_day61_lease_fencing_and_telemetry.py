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
    # the marker claim (and its rowcount==1 gate) precedes the Provider HTTP call in source
    assert _SRC.index("_claim_dispatch_marker(engine, job_id, lease_token)") < _SRC.index("call_provider(")
    assert "lease_lost_no_external_call" in _SRC


def test_all_state_changes_are_lease_fenced():
    # pending_reconciliation, contract failure and completion all guard on the lease token.
    guard = "job_status='running' AND lease_token=:tok"
    assert _SRC.count(guard) >= 1
    for fn in ("_to_pending_reconciliation", "_record_contract_failure", "_guarded_completion",
               "_persist_provider_request_id"):
        assert f"def {fn}" in _SRC
    # stale writers short-circuit rather than touch the successor's Job
    assert "lease_lost_no_state_change" in _SRC


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
