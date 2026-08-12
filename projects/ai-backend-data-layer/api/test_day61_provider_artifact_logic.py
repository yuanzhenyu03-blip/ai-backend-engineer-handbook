"""Day61 — EXECUTED_LOCAL_RUNTIME unit tests for the pure Provider/Artifact/telemetry logic.

Standard-library control flow ONLY. Proves the RULES: outcome classification, deterministic
per-Attempt key, HEAD verify / non-overwrite conflict, checkpoint ordering, the lease-token
completion gate, and telemetry safety. NOT integration evidence (no PostgreSQL, no Object
Storage, no OTel, no broker).
"""

from day61_provider_artifact_logic import (
    ArtifactVerdict,
    Checkpoint,
    ExecutionDecision,
    ExpectedArtifact,
    HeadMetadata,
    ProviderOutcome,
    can_complete,
    classify_provider_outcome,
    exporter_failure_must_not_fail_job,
    external_call_checkpoint_order,
    metric_labels_allowed,
    result_artifact_key,
    telemetry_safe_provider_request_ref,
    verify_artifact_head,
)


def test_outcome_classification():
    assert classify_provider_outcome(ProviderOutcome.VALID, True) is ExecutionDecision.VERIFY_ARTIFACT_THEN_COMPLETE
    assert classify_provider_outcome(ProviderOutcome.INVALID_BODY, True) is ExecutionDecision.CONTRACT_FAILURE
    assert classify_provider_outcome(ProviderOutcome.TIMEOUT, True) is ExecutionDecision.PENDING_RECONCILIATION
    assert classify_provider_outcome(ProviderOutcome.TIMEOUT, False) is ExecutionDecision.UNSAFE_NO_MARKER


def test_deterministic_per_attempt_key():
    k1 = result_artifact_key("t1", "j1", "a1")
    assert k1 == "results/t1/j1/a1/result.json"
    assert result_artifact_key("t1", "j1", "a2") != k1   # different Attempt -> different key
    assert result_artifact_key("t1", "j1", "a1") == k1   # same Attempt -> same key (resumable)


def test_head_verify_absent_verified_conflict():
    expected = ExpectedArtifact("sha256:x", 42, "application/json")
    assert verify_artifact_head(HeadMetadata(False, None, None, None), expected) is ArtifactVerdict.ABSENT
    assert verify_artifact_head(HeadMetadata(True, "sha256:x", 42, "application/json"), expected) is ArtifactVerdict.VERIFIED
    # mismatched checksum -> CONFLICT (never overwrite / never succeed)
    assert verify_artifact_head(HeadMetadata(True, "sha256:y", 42, "application/json"), expected) is ArtifactVerdict.CONFLICT
    assert verify_artifact_head(HeadMetadata(True, "sha256:x", 999, "application/json"), expected) is ArtifactVerdict.CONFLICT


def test_checkpoint_order_marker_before_call_requestid_before_success():
    order = external_call_checkpoint_order()
    assert order.index(Checkpoint.PERSIST_DISPATCH_MARKER) < order.index(Checkpoint.PROVIDER_HTTP_CALL)
    assert order.index(Checkpoint.PROVIDER_HTTP_CALL) < order.index(Checkpoint.PERSIST_PROVIDER_REQUEST_ID)
    assert order.index(Checkpoint.PERSIST_PROVIDER_REQUEST_ID) < order.index(Checkpoint.VERIFY_ARTIFACT)
    assert order.index(Checkpoint.VERIFY_ARTIFACT) < order.index(Checkpoint.GUARDED_COMPLETION)


def test_completion_requires_current_matching_lease_token():
    assert can_complete("running", "tokA", "tokA") is True
    assert can_complete("running", "tokA", "tokB") is False   # stale Worker cannot complete
    assert can_complete("succeeded", "tokA", "tokA") is False
    assert can_complete("running", None, "tokA") is False


def test_telemetry_low_cardinality_and_protected_id():
    assert metric_labels_allowed({"provider": "fake", "outcome": "valid"}) is True
    assert metric_labels_allowed({"job_id": "j1"}) is False
    assert metric_labels_allowed({"attempt_id": "a1"}) is False
    assert metric_labels_allowed({"provider_request_id": "p1"}) is False
    ref = telemetry_safe_provider_request_ref("prov-secret-123")
    assert ref.startswith("prid:") and "prov-secret-123" not in ref
    assert exporter_failure_must_not_fail_job() is True
