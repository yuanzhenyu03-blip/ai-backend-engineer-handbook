"""Offline, content-safe replay for Day106 L3B integration evidence."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_chunking_contracts import stable_hash  # noqa: E402


SCHEMA_PATH = ROOT / "evidence" / "day106-l3b-evidence-schema.json"
INTEGRATION_SCHEMA_VERSION = "day106-l3b-external-evidence.v1"
RESTART_SCHEMA_VERSION = "day106-l3b-restart-replay.v1"
REPLAY_SCHEMA_VERSION = "day106-l3b-evidence-replay.v1"
SCENARIO_ID = "day106-production-rag-db-external-provider-l3b-v1"
BASE_COMMIT = "91c2eddf3b10fbe1d6b0e381ee84ebb009039a5c"
REAL_TRANSPORT_BOUNDARY = "REAL_URLLIB_OPENAI_RESPONSES_HTTPS"
REAL_TRANSPORT_BOUNDARY_DIGEST = stable_hash((
    "DAY106_L3B_TRANSPORT_BOUNDARY_V1",
    "UrllibOpenAIResponsesTransport",
    "https://api.openai.com/v1/responses",
    "stdlib-urllib",
    "NO_RETRY",
))
EXPECTED_LABELS = (
    "G2_P1_Q1",
    "G2_P1_Q2",
    "G2_P1_Q3",
    "G2_P1_Q3_PENDING",
    "G3_P2_Q2",
)
EXPECTED_ZERO_CALL_GATES = {
    "DAY105_SECURITY_NEGATIVE_CONTROLS",
    "G3_P2_Q1_REQUIRED_A_UNAVAILABLE",
    "G3_P2_Q3_REQUIRED_A_UNAVAILABLE",
}
EXPECTED_ARTIFACT_COUNTS = {
    "ANSWER_RELEASE": 5,
    "DISPATCH_RECORD": 0,
    "DISPATCH_WINNER": 0,
    "MODEL_INVOCATION": 5,
    "PROVIDER_ATTEMPT": 5,
    "PROVIDER_RECEIPT": 5,
    "REQUEST_BINDING": 5,
    "RESPONSE_INTENT": 4,
    "RETRIEVAL_CONTEXT_RECEIPT": 5,
}
ARTIFACT_PATHS = {
    "integration_runner": "evals/run_day106_l3b_external_integration.py",
    "evidence_schema": "evidence/day106-l3b-evidence-schema.json",
    "database_schema": "integration/day106/schema.sql",
    "capstone_repository": "src/rag_capstone_postgres.py",
    "compose": "integration/day106/compose.yaml",
    "openai_adapter": "src/rag_openai_responses_adapter.py",
    "production_capstone": "examples/day106_production_rag_capstone.py",
    "capstone_support": "examples/day106_capstone_support.py",
    "grounding_adapters": "src/rag_grounding_adapters.py",
    "grounding_orchestrator": "src/rag_grounding_orchestrator.py",
    "day105_integration_runner": "evals/run_day105_l3_integration.py",
    "day106_l3a_integration_runner": "evals/run_day106_l3a_integration.py",
    "restart_runner": "evals/run_day106_l3b_restart_replay.py",
    "evidence_replay_runner": "evals/run_day106_l3b_evidence_replay.py",
}
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
UNSAFE_VALUE_PATTERN = re.compile(
    r"postgres(?:ql)?://|-----BEGIN [A-Z ]+PRIVATE KEY-----|"
    r"(?:^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{12,}|"
    r"(?:^|[^A-Za-z0-9])resp_[A-Za-z0-9_-]{8,}",
    re.IGNORECASE,
)
FORBIDDEN_CONTENT_FIELDS = {
    "api_key",
    "answer",
    "answer_candidate",
    "answer_text",
    "database_url",
    "dsn",
    "prompt",
    "protected_chunk",
    "protected_text",
    "provider_response",
    "raw_answer",
    "raw_prompt",
    "raw_vector",
    "secret",
    "source_text",
    "vector",
}
RESTART_REQUIRED_FIELDS = {
    "schema_version",
    "scenario_id",
    "run_id",
    "status",
    "source_integration_report_checksum",
    "started_at",
    "completed_at",
    "postmaster_started_at",
    "database_identity_digest",
    "generation_id",
    "pointer_revision",
    "authorization_snapshot_id",
    "authorization_revision",
    "durable_state_digest",
    "artifact_counts",
    "artifact_identity_count",
    "provider_summary",
    "cross_binding_summary",
    "decision_summary",
    "schemas_reinstalled",
    "schemas_reset",
    "external_provider_called",
    "raw_prompt_logged",
    "protected_chunk_logged",
    "answer_candidate_text_logged",
    "raw_provider_response_logged",
    "raw_provider_response_id_logged",
    "raw_secret_logged",
    "raw_vector_logged",
    "database_url_logged",
    "production_readiness",
    "report_checksum",
}


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _digest(value: object, reason: str) -> str:
    _require(
        isinstance(value, str) and bool(DIGEST_PATTERN.fullmatch(value)),
        reason,
    )
    return value


def _datetime(value: object, reason: str) -> datetime:
    _require(isinstance(value, str), reason)
    try:
        observed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(reason) from exc
    _require(observed.tzinfo is not None, reason)
    return observed


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_checksum(report: dict[str, Any], reason: str) -> str:
    checksum = _digest(report.get("report_checksum"), f"{reason}_CHECKSUM_INVALID")
    unsigned = dict(report)
    unsigned.pop("report_checksum", None)
    _require(stable_hash(unsigned) == checksum, f"{reason}_CHECKSUM_MISMATCH")
    return checksum


def _validate_content_safe(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = key.lower()
            if not lowered.endswith("_logged"):
                _require(
                    lowered not in FORBIDDEN_CONTENT_FIELDS,
                    f"FORBIDDEN_CONTENT_FIELD:{path}.{key}",
                )
            _validate_content_safe(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_content_safe(item, f"{path}[{index}]")
        return
    if isinstance(value, str):
        _require(len(value) <= 4096, f"CONTENT_VALUE_TOO_LARGE:{path}")
        _require(
            not UNSAFE_VALUE_PATTERN.search(value),
            f"UNSAFE_CONTENT_VALUE:{path}",
        )


def _validate_artifacts(
    artifacts: object,
    *,
    artifact_root: Path,
) -> None:
    _require(isinstance(artifacts, dict), "ARTIFACT_DIGESTS_MISSING")
    _require(
        set(artifacts) == {*ARTIFACT_PATHS, "base_commit"},
        "ARTIFACT_DIGESTS_SHAPE_MISMATCH",
    )
    _require(artifacts["base_commit"] == BASE_COMMIT, "BASE_COMMIT_MISMATCH")
    for name, relative_path in ARTIFACT_PATHS.items():
        expected = _file_digest(artifact_root / relative_path)
        _require(
            artifacts[name] == expected,
            f"ARTIFACT_DIGEST_MISMATCH:{name}",
        )


def validate_initial_report(
    report: dict[str, Any],
    schema: dict[str, Any],
    *,
    artifact_root: Path = ROOT,
) -> dict[str, object]:
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(report),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    _require(
        not errors,
        "INITIAL_SCHEMA_VALIDATION_FAILED:"
        + (errors[0].message if errors else "UNKNOWN"),
    )
    started = _datetime(report["started_at"], "INITIAL_STARTED_AT_INVALID")
    completed = _datetime(report["completed_at"], "INITIAL_COMPLETED_AT_INVALID")
    _require(completed >= started, "INITIAL_TIMELINE_INVALID")
    _require(
        report["transport_boundary"] == REAL_TRANSPORT_BOUNDARY
        and report["transport_boundary_digest"]
        == REAL_TRANSPORT_BOUNDARY_DIGEST,
        "REAL_TRANSPORT_BOUNDARY_ATTESTATION_MISMATCH",
    )
    _validate_artifacts(report["artifact_digests"], artifact_root=artifact_root)

    calls = report["external_calls"]
    _require(isinstance(calls, list), "EXTERNAL_CALLS_INVALID")
    _require(
        tuple(item["label"] for item in calls) == EXPECTED_LABELS,
        "EXTERNAL_CALL_LABEL_ORDER_MISMATCH",
    )
    _require(
        tuple(item["call_ordinal"] for item in calls) == (1, 2, 3, 4, 5),
        "EXTERNAL_CALL_ORDINAL_MISMATCH",
    )
    _require(
        tuple(item["generation_id"] for item in calls)
        == ("G2", "G2", "G2", "G2", "G3"),
        "EXTERNAL_CALL_GENERATION_MISMATCH",
    )
    _require(
        tuple(item["authorization_snapshot_id"] for item in calls)
        == ("P1", "P1", "P1", "P1", "P2"),
        "EXTERNAL_CALL_AUTHORIZATION_MISMATCH",
    )
    _require(
        tuple(item["release_disposition"] for item in calls)
        == ("RELEASE", "RELEASE", "RELEASE", "BLOCKED", "RELEASE"),
        "EXTERNAL_CALL_RELEASE_MATRIX_MISMATCH",
    )
    _require(
        all(
            item["total_token_count"]
            == item["input_token_count"] + item["output_token_count"]
            for item in calls
        ),
        "EXTERNAL_TOKEN_ARITHMETIC_MISMATCH",
    )
    _require(
        sum(item["output_token_count"] for item in calls)
        == report["observed_output_tokens_total"],
        "EXTERNAL_OUTPUT_TOKEN_TOTAL_MISMATCH",
    )
    _require(
        len({item["request_binding_digest"] for item in calls}) == 5
        and len({item["provider_attempt_digest"] for item in calls}) == 5
        and len({item["provider_receipt_digest"] for item in calls}) == 5,
        "EXTERNAL_EXECUTION_IDENTITIES_NOT_UNIQUE",
    )
    _require(
        set(report["zero_call_gates"]) == EXPECTED_ZERO_CALL_GATES,
        "ZERO_CALL_GATE_MATRIX_MISMATCH",
    )
    pending = report["pending_g2_after_p2"]
    _require(
        "CURRENT_AUTHORIZATION_CHANGED" in pending["safe_reason_codes"],
        "PENDING_G2_AUTHORIZATION_REASON_MISSING",
    )
    restart = report["restart_evidence"]
    _require(
        restart["artifact_counts"] == EXPECTED_ARTIFACT_COUNTS
        and restart["artifact_identity_count"] == 34,
        "INITIAL_DURABLE_STATE_COUNT_MISMATCH",
    )
    pre_postmaster = _datetime(
        restart["pre_restart_postmaster_started_at"],
        "INITIAL_POSTMASTER_INVALID",
    ).isoformat()
    pre_state = _digest(
        restart["pre_restart_state_digest"],
        "INITIAL_STATE_DIGEST_INVALID",
    )
    checksum = _validate_checksum(report, "INITIAL_REPORT")
    _validate_content_safe(report)
    return {
        "checksum": checksum,
        "completed_at": completed,
        "pre_postmaster": pre_postmaster,
        "pre_state": pre_state,
    }


def validate_restart_report(
    report: dict[str, Any],
    initial: dict[str, object],
) -> str:
    _require(set(report) == RESTART_REQUIRED_FIELDS, "RESTART_REPORT_SHAPE_MISMATCH")
    _require(report["schema_version"] == RESTART_SCHEMA_VERSION, "RESTART_SCHEMA_MISMATCH")
    _require(report["scenario_id"] == SCENARIO_ID, "RESTART_SCENARIO_MISMATCH")
    _require(report["status"] == "PASS", "RESTART_STATUS_MISMATCH")
    _require(
        report["source_integration_report_checksum"] == initial["checksum"],
        "RESTART_SOURCE_REPORT_MISMATCH",
    )
    started = _datetime(report["started_at"], "RESTART_STARTED_AT_INVALID")
    completed = _datetime(report["completed_at"], "RESTART_COMPLETED_AT_INVALID")
    _require(completed >= started >= initial["completed_at"], "RESTART_TIMELINE_INVALID")
    postmaster = _datetime(
        report["postmaster_started_at"],
        "RESTART_POSTMASTER_INVALID",
    ).isoformat()
    _require(postmaster != initial["pre_postmaster"], "DATABASE_DID_NOT_RESTART")
    _require(
        report["durable_state_digest"] == initial["pre_state"],
        "RESTART_DURABLE_STATE_CHANGED",
    )
    _require(
        report["generation_id"] == "G3"
        and report["pointer_revision"] == 9
        and report["authorization_snapshot_id"] == "P2"
        and report["authorization_revision"] == 2,
        "RESTART_SERVING_AUTHORITY_MISMATCH",
    )
    _require(
        report["artifact_counts"] == EXPECTED_ARTIFACT_COUNTS
        and report["artifact_identity_count"] == 34,
        "RESTART_ARTIFACT_COUNT_MISMATCH",
    )
    provider = report["provider_summary"]
    _require(isinstance(provider, dict), "RESTART_PROVIDER_SUMMARY_INVALID")
    _require(
        provider == {
            "attempt_count": 5,
            "receipt_count": 5,
            "succeeded_receipt_count": 5,
            "failed_receipt_count": 0,
            "unknown_receipt_count": 0,
            "unreceipted_attempt_count": 0,
            "external_model_invocation_count": 5,
            "other_model_invocation_count": 0,
            "call_ordinals": [1, 2, 3, 4, 5],
            "input_token_count": provider.get("input_token_count"),
            "output_token_count": provider.get("output_token_count"),
            "total_token_count": provider.get("total_token_count"),
            "reconciliation_required": False,
            "blind_retry_allowed": False,
        },
        "RESTART_PROVIDER_SUMMARY_SHAPE_MISMATCH",
    )
    for key in ("input_token_count", "output_token_count", "total_token_count"):
        _require(
            isinstance(provider[key], int) and provider[key] >= 0,
            f"RESTART_PROVIDER_TOKEN_INVALID:{key}",
        )
    _require(
        provider["output_token_count"] <= 320
        and provider["total_token_count"]
        == provider["input_token_count"] + provider["output_token_count"],
        "RESTART_PROVIDER_TOKEN_BUDGET_MISMATCH",
    )
    _require(
        report["cross_binding_summary"] == {
            "provider_cross_binding_mismatch_count": 0,
            "release_provider_binding_mismatch_count": 0,
            "unauthorized_prompt_count": 0,
        },
        "RESTART_CROSS_BINDING_MISMATCH",
    )
    _require(
        report["decision_summary"] == {
            "decision_count": 5,
            "released_count": 4,
            "blocked_count": 1,
            "not_attempted_count": 1,
            "response_intent_count": 4,
            "pending_response_state_count": 4,
            "dispatch_winner_count": 0,
            "dispatch_record_count": 0,
        },
        "RESTART_DECISION_SUMMARY_MISMATCH",
    )
    _digest(report["database_identity_digest"], "RESTART_DATABASE_DIGEST_INVALID")
    for key in (
        "schemas_reinstalled",
        "schemas_reset",
        "external_provider_called",
        "raw_prompt_logged",
        "protected_chunk_logged",
        "answer_candidate_text_logged",
        "raw_provider_response_logged",
        "raw_provider_response_id_logged",
        "raw_secret_logged",
        "raw_vector_logged",
        "database_url_logged",
    ):
        _require(report[key] is False, f"RESTART_SAFETY_FLAG_TRUE:{key}")
    _require(
        report["production_readiness"] == "MORE_EVIDENCE_NEEDED",
        "RESTART_PRODUCTION_READINESS_OVERCLAIM",
    )
    checksum = _validate_checksum(report, "RESTART_REPORT")
    _validate_content_safe(report)
    return checksum


def validate_reports(
    integration_report_path: Path,
    restart_report_path: Path,
    *,
    schema_path: Path = SCHEMA_PATH,
    artifact_root: Path = ROOT,
) -> dict[str, object]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    integration = json.loads(integration_report_path.read_text(encoding="utf-8"))
    restart = json.loads(restart_report_path.read_text(encoding="utf-8"))
    _require(isinstance(schema, dict), "SCHEMA_MUST_BE_OBJECT")
    _require(isinstance(integration, dict), "INTEGRATION_REPORT_MUST_BE_OBJECT")
    _require(isinstance(restart, dict), "RESTART_REPORT_MUST_BE_OBJECT")
    _require(
        schema["properties"]["schema_version"]["const"]
        == INTEGRATION_SCHEMA_VERSION,
        "SCHEMA_VERSION_CONTRACT_MISMATCH",
    )
    initial = validate_initial_report(
        integration,
        schema,
        artifact_root=artifact_root,
    )
    restart_checksum = validate_restart_report(restart, initial)
    payload: dict[str, object] = {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "status": "PASS",
        "checks": {
            "append_only_separate_reports": True,
            "artifact_file_digests": True,
            "content_safe": True,
            "database_container_restart_observed": True,
            "durable_state_identity_preserved": True,
            "same_execution_cross_binding": True,
            "provider_call_budget_exactly_five": True,
            "output_token_budget_at_most_320": True,
            "unauthorized_occurrence_entering_prompt_zero": True,
            "delivery_not_overclaimed": True,
            "production_readiness_not_overclaimed": True,
        },
        "integration_report_checksum": initial["checksum"],
        "restart_report_checksum": restart_checksum,
        "replay_checksum": stable_hash((initial["checksum"], restart_checksum)),
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }
    payload["report_checksum"] = stable_hash(payload)
    return payload


def _write_exclusive(path: Path, report: dict[str, object]) -> None:
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration-report", required=True, type=Path)
    parser.add_argument("--restart-report", required=True, type=Path)
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    parser.add_argument("--artifact-root", type=Path, default=ROOT)
    parser.add_argument("--report-path", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.report_path.exists():
        print(json.dumps({
            "status": "FAIL",
            "safe_reason": "DAY106_L3B_REPLAY_REPORT_ALREADY_EXISTS",
        }, indent=2, sort_keys=True))
        return 2
    try:
        result = validate_reports(
            arguments.integration_report,
            arguments.restart_report,
            schema_path=arguments.schema,
            artifact_root=arguments.artifact_root,
        )
        _write_exclusive(arguments.report_path, result)
    except Exception as exc:
        print(json.dumps({
            "status": "FAIL",
            "safe_reason": "DAY106_L3B_EVIDENCE_REPLAY_FAILED",
            "error_type": type(exc).__name__,
        }, indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
