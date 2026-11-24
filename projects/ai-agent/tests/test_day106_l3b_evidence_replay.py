"""Synthetic tests for Day106 L3B offline evidence replay."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from evals import run_day106_l3b_evidence_replay as replay
from rag_chunking_contracts import stable_hash


def _digest(label: str) -> str:
    return stable_hash(("TEST", label))


def _artifact_digests() -> dict[str, str]:
    return {
        name: replay._file_digest(replay.ROOT / relative_path)
        for name, relative_path in replay.ARTIFACT_PATHS.items()
    } | {"base_commit": replay.BASE_COMMIT}


def _external_calls() -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []
    for index, label in enumerate(replay.EXPECTED_LABELS, start=1):
        pending = label == "G2_P1_Q3_PENDING"
        calls.append({
            "label": label,
            "generation_id": "G3" if index == 5 else "G2",
            "authorization_snapshot_id": "P2" if index == 5 else "P1",
            "request_binding_digest": _digest(f"request-{index}"),
            "retrieval_context_receipt_digest": _digest(f"retrieval-{index}"),
            "retrieval_bundle_digest": _digest(f"bundle-{index}"),
            "context_manifest_digest": _digest(f"context-{index}"),
            "model_invocation_digest": _digest(f"invocation-{index}"),
            "provider_attempt_digest": _digest(f"attempt-{index}"),
            "provider_receipt_digest": _digest(f"provider-receipt-{index}"),
            "answer_candidate_digest": _digest(f"candidate-{index}"),
            "provider_status": "SUCCEEDED",
            "call_ordinal": index,
            "input_token_count": 10,
            "output_token_count": 2,
            "total_token_count": 12,
            "release_disposition": "BLOCKED" if pending else "RELEASE",
            "safe_reason_codes": (
                [
                    "CURRENT_AUTHORIZATION_CHANGED",
                    "CURRENT_CONTENT_SECURITY_SNAPSHOT_CHANGED",
                ]
                if pending else []
            ),
            "unauthorized_prompt_count": 0,
        })
    return calls


def _initial_report() -> dict[str, object]:
    started = datetime(2026, 11, 24, 1, 0, tzinfo=timezone.utc)
    calls = _external_calls()
    hard_gates = {
        name: "PASS"
        for name in (
            "one_database_execution_not_independent_pass_stitching",
            "real_pgvector_readview_each_external_query",
            "exact_request_rb_cam_mi_provider_binding",
            "model_invocation_persisted_pre_send",
            "provider_attempt_reserved_pre_send",
            "shared_call_budget_exactly_five",
            "each_observed_output_tokens_at_most_64",
            "observed_output_tokens_total_at_most_320",
            "all_security_negative_controls_zero_external_calls",
            "g3_q1_q3_zero_external_calls",
            "pending_g2_candidate_blocked_after_p2",
            "g3_p2_q2_released",
            "unauthorized_occurrence_entering_prompt_zero",
            "pre_restart_durable_state_sealed",
        )
    }
    report: dict[str, object] = {
        "schema_version": replay.INTEGRATION_SCHEMA_VERSION,
        "scenario_id": replay.SCENARIO_ID,
        "run_id": "day106-l3b-0123456789abcdef",
        "status": "PASS",
        "evidence_level": (
            "EXECUTED_LOCAL_POSTGRESQL_PGVECTOR_AND_EXTERNAL_MODEL_BOUNDARY"
        ),
        "started_at": started.isoformat(),
        "completed_at": (started + timedelta(minutes=1)).isoformat(),
        "same_database_execution": True,
        "artifact_digests": _artifact_digests(),
        "day105_execution_checksum": _digest("day105"),
        "external_call_count": 5,
        "observed_output_tokens_total": 10,
        "external_calls": calls,
        "zero_call_gates": sorted(replay.EXPECTED_ZERO_CALL_GATES),
        "pending_g2_after_p2": {
            "disposition": "BLOCKED",
            "safe_reason_codes": [
                "CURRENT_AUTHORIZATION_CHANGED",
                "CURRENT_CONTENT_SECURITY_SNAPSHOT_CHANGED",
            ],
            "response_dispatch_state": "NOT_ATTEMPTED",
        },
        "hard_gates": hard_gates,
        "restart_evidence": {
            "status": "PRE_RESTART_SEALED",
            "pre_restart_postmaster_started_at": started.isoformat(),
            "pre_restart_state_digest": _digest("durable-state"),
            "artifact_counts": dict(replay.EXPECTED_ARTIFACT_COUNTS),
            "artifact_identity_count": 34,
            "post_restart_postmaster_started_at": None,
            "post_restart_state_digest": None,
        },
        "raw_prompt_logged": False,
        "protected_chunk_logged": False,
        "answer_candidate_text_logged": False,
        "raw_provider_response_logged": False,
        "raw_provider_response_id_logged": False,
        "raw_secret_logged": False,
        "raw_vector_logged": False,
        "database_url_logged": False,
        "max_output_tokens": 64,
        "reasoning_effort": "low",
        "store": False,
        "tools_enabled": False,
        "provider_call_budget": 5,
        "canonical_python_3_12": "NOT_RUN",
        "transport_boundary": replay.REAL_TRANSPORT_BOUNDARY,
        "transport_boundary_digest": replay.REAL_TRANSPORT_BOUNDARY_DIGEST,
        "external_model_boundary": "PASS",
        "external_dlp_boundary": "NOT_RUN",
        "production_iam_rls_tls_egress": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "claim_boundary": "Bounded classroom external-model evidence only.",
    }
    report["report_checksum"] = stable_hash(report)
    return report


def _restart_report(initial: dict[str, object]) -> dict[str, object]:
    started = datetime(2026, 11, 24, 1, 2, tzinfo=timezone.utc)
    initial_restart = initial["restart_evidence"]
    assert isinstance(initial_restart, dict)
    report: dict[str, object] = {
        "schema_version": replay.RESTART_SCHEMA_VERSION,
        "scenario_id": replay.SCENARIO_ID,
        "run_id": "day106-l3b-restart-0123456789abcdef",
        "status": "PASS",
        "source_integration_report_checksum": initial["report_checksum"],
        "started_at": started.isoformat(),
        "completed_at": (started + timedelta(seconds=1)).isoformat(),
        "postmaster_started_at": (started - timedelta(seconds=30)).isoformat(),
        "database_identity_digest": _digest("database"),
        "generation_id": "G3",
        "pointer_revision": 9,
        "authorization_snapshot_id": "P2",
        "authorization_revision": 2,
        "durable_state_digest": initial_restart["pre_restart_state_digest"],
        "artifact_counts": dict(replay.EXPECTED_ARTIFACT_COUNTS),
        "artifact_identity_count": 34,
        "provider_summary": {
            "attempt_count": 5,
            "receipt_count": 5,
            "succeeded_receipt_count": 5,
            "failed_receipt_count": 0,
            "unknown_receipt_count": 0,
            "unreceipted_attempt_count": 0,
            "external_model_invocation_count": 5,
            "other_model_invocation_count": 0,
            "call_ordinals": [1, 2, 3, 4, 5],
            "input_token_count": 50,
            "output_token_count": 10,
            "total_token_count": 60,
            "reconciliation_required": False,
            "blind_retry_allowed": False,
        },
        "cross_binding_summary": {
            "provider_cross_binding_mismatch_count": 0,
            "release_provider_binding_mismatch_count": 0,
            "unauthorized_prompt_count": 0,
        },
        "decision_summary": {
            "decision_count": 5,
            "released_count": 4,
            "blocked_count": 1,
            "not_attempted_count": 1,
            "response_intent_count": 4,
            "pending_response_state_count": 4,
            "dispatch_winner_count": 0,
            "dispatch_record_count": 0,
        },
        "schemas_reinstalled": False,
        "schemas_reset": False,
        "external_provider_called": False,
        "raw_prompt_logged": False,
        "protected_chunk_logged": False,
        "answer_candidate_text_logged": False,
        "raw_provider_response_logged": False,
        "raw_provider_response_id_logged": False,
        "raw_secret_logged": False,
        "raw_vector_logged": False,
        "database_url_logged": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }
    report["report_checksum"] = stable_hash(report)
    return report


def _write_reports(
    tmp_path: Path,
    initial: dict[str, object],
    restart: dict[str, object],
) -> tuple[Path, Path]:
    initial_path = tmp_path / "initial.json"
    restart_path = tmp_path / "restart.json"
    initial_path.write_text(json.dumps(initial), encoding="utf-8")
    restart_path.write_text(json.dumps(restart), encoding="utf-8")
    return initial_path, restart_path


def test_synthetic_reports_replay_with_exact_artifact_binding(tmp_path: Path) -> None:
    initial = _initial_report()
    restart = _restart_report(initial)
    initial_path, restart_path = _write_reports(tmp_path, initial, restart)

    result = replay.validate_reports(initial_path, restart_path)

    assert result["status"] == "PASS"
    assert result["checks"]["database_container_restart_observed"] is True
    assert result["checks"]["delivery_not_overclaimed"] is True
    assert result["production_readiness"] == "MORE_EVIDENCE_NEEDED"


@pytest.mark.parametrize(
    "artifact_name",
    ("openai_adapter", "day106_l3a_integration_runner"),
)
def test_replay_rejects_artifact_drift(
    tmp_path: Path,
    artifact_name: str,
) -> None:
    initial = _initial_report()
    initial["artifact_digests"][artifact_name] = _digest("drift")
    initial["report_checksum"] = stable_hash({
        key: value for key, value in initial.items()
        if key != "report_checksum"
    })
    restart = _restart_report(initial)
    initial_path, restart_path = _write_reports(tmp_path, initial, restart)

    with pytest.raises(ValueError, match="ARTIFACT_DIGEST_MISMATCH"):
        replay.validate_reports(initial_path, restart_path)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("transport_boundary", "INJECTED_NON_ATTESTED_TRANSPORT"),
        ("transport_boundary_digest", _digest("fake-transport")),
        ("external_model_boundary", "NOT_RUN"),
    ),
)
def test_real_evidence_rejects_fake_transport_boundary(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    initial = _initial_report()
    initial[field] = value
    initial["report_checksum"] = stable_hash({
        key: item for key, item in initial.items()
        if key != "report_checksum"
    })
    restart = _restart_report(initial)
    initial_path, restart_path = _write_reports(tmp_path, initial, restart)

    with pytest.raises(ValueError, match="INITIAL_SCHEMA_VALIDATION_FAILED"):
        replay.validate_reports(initial_path, restart_path)


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("durable_state_digest", _digest("changed"), "DURABLE_STATE_CHANGED"),
        ("production_readiness", "READY", "PRODUCTION_READINESS"),
    ),
)
def test_replay_rejects_restart_drift_or_overclaim(
    tmp_path: Path,
    field: str,
    value: object,
    reason: str,
) -> None:
    initial = _initial_report()
    restart = _restart_report(initial)
    restart[field] = value
    restart["report_checksum"] = stable_hash({
        key: item for key, item in restart.items()
        if key != "report_checksum"
    })
    initial_path, restart_path = _write_reports(tmp_path, initial, restart)

    with pytest.raises(ValueError, match=reason):
        replay.validate_reports(initial_path, restart_path)


def test_replay_rejects_unknown_provider_outcome(tmp_path: Path) -> None:
    initial = _initial_report()
    restart = _restart_report(initial)
    restart["provider_summary"]["succeeded_receipt_count"] = 4
    restart["provider_summary"]["unknown_receipt_count"] = 1
    restart["provider_summary"]["reconciliation_required"] = True
    restart["report_checksum"] = stable_hash({
        key: value for key, value in restart.items()
        if key != "report_checksum"
    })
    initial_path, restart_path = _write_reports(tmp_path, initial, restart)

    with pytest.raises(ValueError, match="PROVIDER_SUMMARY"):
        replay.validate_reports(initial_path, restart_path)


def test_content_safety_rejects_raw_provider_identifier() -> None:
    with pytest.raises(ValueError, match="UNSAFE_CONTENT_VALUE"):
        replay._validate_content_safe({"safe_note": "resp_sensitive_raw_id"})
