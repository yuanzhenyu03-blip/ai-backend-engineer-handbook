"""Offline replay for append-only Day106 L3A integration/restart evidence."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_chunking_contracts import stable_hash  # noqa: E402


SCHEMA_PATH = ROOT / "evidence" / "day106-l3a-evidence-schema.json"
CORRECTION_PATH = ROOT / "evidence" / "day106-l3a-integration-report-v1-correction.json"
SCHEMA_VERSION = "day106-l3a-evidence.v2"
RESTART_SCHEMA_VERSION = "day106-l3-restart-replay.v2"
CORRECTION_SCHEMA_VERSION = "day106-l3a-evidence-correction.v1"
SCENARIO_ID = "day106-production-rag-postgresql-pgvector-l3a-v1"
BASE_COMMIT = "91c2eddf3b10fbe1d6b0e381ee84ebb009039a5c"
SUPERSEDED_REPORT_CHECKSUM = (
    "sha256:cb307938d85c506167f1b76271d5e3da1401f107a9899942f3254e6213990fe8"
)
ARTIFACT_PATHS = {
    "integration_runner": "evals/run_day106_l3a_integration.py",
    "evidence_schema": "evidence/day106-l3a-evidence-schema.json",
    "database_schema": "integration/day106/schema.sql",
    "capstone_repository": "src/rag_capstone_postgres.py",
    "compose": "integration/day106/compose.yaml",
    "day105_integration_runner": "evals/run_day105_l3_integration.py",
    "restart_runner": "evals/run_day106_l3_restart_replay.py",
    "evidence_replay_runner": "evals/run_day106_l3_evidence_replay.py",
}
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
UNSAFE_VALUE_PATTERN = re.compile(
    r"postgres(?:ql)?://|-----BEGIN [A-Z ]+PRIVATE KEY-----|"
    r"(?:^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{12,}",
    re.IGNORECASE,
)
FORBIDDEN_CONTENT_FIELDS = {
    "api_key",
    "answer",
    "answer_candidate",
    "database_url",
    "dsn",
    "prompt",
    "protected_chunk",
    "provider_response",
    "raw_answer",
    "raw_prompt",
    "raw_vector",
    "secret",
    "vector",
}
RESTART_REQUIRED_FIELDS = {
    "schema_version",
    "scenario_id",
    "run_id",
    "status",
    "started_at",
    "completed_at",
    "postmaster_started_at",
    "database_identity_digest",
    "generation_id",
    "pointer_revision",
    "authorization_snapshot_id",
    "authorization_revision",
    "intent_id",
    "intent_identity_digest",
    "final_dispatch_state",
    "recovery_record_count",
    "recovery_record_digests",
    "durable_state_identity_digest",
    "provider_call_count",
    "schemas_reinstalled",
    "schemas_reset",
    "external_provider_called",
    "raw_content_logged",
    "provider_response_logged",
    "secret_logged",
    "raw_vector_logged",
    "database_url_logged",
    "report_checksum",
}


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _digest(value: object, reason: str) -> str:
    _require(isinstance(value, str) and bool(DIGEST_PATTERN.fullmatch(value)), reason)
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


def _validate_content_safe(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _require(
                key.lower() not in FORBIDDEN_CONTENT_FIELDS,
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
        _require(not UNSAFE_VALUE_PATTERN.search(value), f"UNSAFE_VALUE:{path}")


def _validate_checksum(report: dict[str, Any], reason: str) -> str:
    saved = _digest(report.get("report_checksum"), f"{reason}_DIGEST_INVALID")
    payload = dict(report)
    payload.pop("report_checksum", None)
    _require(stable_hash(payload) == saved, f"{reason}_CHECKSUM_MISMATCH")
    return saved


def _validate_artifacts(
    artifacts: object,
    schema: dict[str, Any],
    artifact_root: Path,
) -> None:
    _require(isinstance(artifacts, dict), "ARTIFACTS_MISSING")
    _require(
        set(artifacts) == {"base_commit", "files"},
        "ARTIFACTS_SHAPE_MISMATCH",
    )
    _require(artifacts["base_commit"] == BASE_COMMIT, "BASE_COMMIT_MISMATCH")
    files = artifacts["files"]
    expected_names = set(
        schema["properties"]["artifacts"]["properties"]["files"]["required"]
    )
    _require(
        isinstance(files, dict) and set(files) == expected_names,
        "ARTIFACT_FILES_SHAPE_MISMATCH",
    )
    _require(expected_names == set(ARTIFACT_PATHS), "ARTIFACT_CONTRACT_DRIFT")
    for name, relative_path in ARTIFACT_PATHS.items():
        record = files[name]
        expected_path = f"projects/ai-agent/{relative_path}"
        _require(
            isinstance(record, dict) and set(record) == {"path", "digest"},
            f"ARTIFACT_RECORD_SHAPE_MISMATCH:{name}",
        )
        _require(record["path"] == expected_path, f"ARTIFACT_PATH_MISMATCH:{name}")
        expected_digest = _file_digest(artifact_root / relative_path)
        _require(
            record["digest"] == expected_digest,
            f"ARTIFACT_DIGEST_MISMATCH:{name}",
        )


def validate_correction_record(report: dict[str, Any]) -> str:
    required = {
        "schema_version",
        "record_type",
        "correction_id",
        "recorded_at",
        "status",
        "superseded_report_path",
        "superseded_report_checksum",
        "reason_code",
        "superseded_claim_only",
        "replacement_claims",
        "other_historical_facts",
        "append_only",
        "report_checksum",
    }
    _require(set(report) == required, "CORRECTION_SHAPE_MISMATCH")
    _require(
        report["schema_version"] == CORRECTION_SCHEMA_VERSION,
        "CORRECTION_SCHEMA_MISMATCH",
    )
    _require(report["record_type"] == "EVIDENCE_CORRECTION", "CORRECTION_TYPE_MISMATCH")
    _require(report["status"] == "SUPERSEDED", "CORRECTION_STATUS_MISMATCH")
    _datetime(report["recorded_at"], "CORRECTION_RECORDED_AT_INVALID")
    _require(
        report["superseded_report_path"]
        == "projects/ai-agent/evidence/day106-l3a-integration-report.json",
        "CORRECTION_REPORT_PATH_MISMATCH",
    )
    _require(
        report["superseded_report_checksum"] == SUPERSEDED_REPORT_CHECKSUM,
        "CORRECTION_REPORT_CHECKSUM_MISMATCH",
    )
    _require(
        report["reason_code"] == "PRE_SEND_PERSISTENCE_CLAIM_OVERSTATED",
        "CORRECTION_REASON_MISMATCH",
    )
    _require(
        report["superseded_claim_only"]
        == "hard_gates.model_invocation_pre_send_persisted=PASS",
        "CORRECTION_SCOPE_MISMATCH",
    )
    _require(
        report["replacement_claims"]
        == [
            "hard_gates.model_invocation_persisted_before_release=PASS",
            "hard_gates.external_pre_send_reservation=NOT_RUN",
        ],
        "CORRECTION_REPLACEMENT_MISMATCH",
    )
    _require(
        report["other_historical_facts"] == "PRESERVED_APPEND_ONLY_NOT_OVERRIDDEN",
        "CORRECTION_HISTORY_MISMATCH",
    )
    _require(report["append_only"] is True, "CORRECTION_NOT_APPEND_ONLY")
    checksum = _validate_checksum(report, "CORRECTION_REPORT")
    _validate_content_safe(report)
    return checksum


def validate_initial_report(
    report: dict[str, Any],
    schema: dict[str, Any],
    artifact_root: Path = ROOT,
) -> dict[str, str]:
    required = set(schema["required"])
    _require(set(report) == required, "INITIAL_REPORT_TOP_LEVEL_SHAPE_MISMATCH")
    _require(report["schema_version"] == SCHEMA_VERSION, "INITIAL_SCHEMA_MISMATCH")
    _require(report["scenario_id"] == SCENARIO_ID, "INITIAL_SCENARIO_MISMATCH")
    _require(report["overall_status"] == "PASS", "INITIAL_REPORT_NOT_PASS")
    _require(
        report["evidence_level"]
        == "EXECUTED_LOCAL_DOCKER_INTEGRATION_POSTGRESQL_PGVECTOR_"
        "WITH_DETERMINISTIC_MODEL_DLP_ADAPTERS",
        "INITIAL_EVIDENCE_LEVEL_MISMATCH",
    )
    started = _datetime(report["started_at"], "INITIAL_STARTED_AT_INVALID")
    completed = _datetime(report["completed_at"], "INITIAL_COMPLETED_AT_INVALID")
    _require(completed >= started, "INITIAL_TIMELINE_INVALID")

    environment = report["environment"]
    expected_environment = set(schema["properties"]["environment"]["required"])
    _require(
        isinstance(environment, dict) and set(environment) == expected_environment,
        "ENVIRONMENT_SHAPE_MISMATCH",
    )
    _require(environment["compose_project"] == "day106-l3", "COMPOSE_PROJECT_MISMATCH")
    _require(environment["pgvector_version"] == "0.8.7", "PGVECTOR_VERSION_MISMATCH")
    _require(environment["driver_version"] == "2.9.10", "DRIVER_VERSION_MISMATCH")
    _require(
        isinstance(environment["python_version"], str)
        and bool(environment["python_version"]),
        "PYTHON_VERSION_MISSING",
    )
    database_identity = _digest(
        environment["database_identity_digest"],
        "DATABASE_IDENTITY_INVALID",
    )
    _digest(environment["image_digest"], "IMAGE_DIGEST_INVALID")
    _validate_artifacts(report["artifacts"], schema, artifact_root)

    cross = report["cross_binding"]
    expected_cross = set(schema["properties"]["cross_binding"]["required"])
    _require(
        isinstance(cross, dict) and set(cross) == expected_cross,
        "CROSS_BINDING_SHAPE_MISMATCH",
    )
    for key, value in cross.items():
        if key.endswith("_digest"):
            _digest(value, f"CROSS_BINDING_DIGEST_INVALID:{key}")
    _digest(
        cross["day105_same_execution_report_checksum"],
        "DAY105_SAME_EXECUTION_CHECKSUM_INVALID",
    )
    _require(cross["unauthorized_prompt_count"] == 0, "UNAUTHORIZED_PROMPT_NONZERO")

    gates = report["hard_gates"]
    _require(isinstance(gates, dict) and gates, "HARD_GATES_MISSING")
    expected_pass = {
        "same_execution_real_database_cross_binding",
        "same_execution_day105_prerequisite",
        "real_pgvector_exact_occurrence_binding",
        "unauthorized_occurrence_entering_prompt_zero",
        "decision_intent_atomicity",
        "model_invocation_persisted_before_release",
        "unknown_reconciliation_bounded_retry",
        "winner_fence_and_duplicate_deduplication",
        "append_only_delivery_chain",
    }
    _require(
        all(gates.get(name) == "PASS" for name in expected_pass),
        "REQUIRED_L3A_HARD_GATE_NOT_PASS",
    )
    expected_gates = set(schema["properties"]["hard_gates"]["required"])
    _require(set(gates) == expected_gates, "HARD_GATES_SHAPE_MISMATCH")
    _require(
        gates.get("external_pre_send_reservation") == "NOT_RUN",
        "EXTERNAL_PRE_SEND_CLAIM_MISMATCH",
    )
    _require(
        gates.get("external_provider_boundary") == "NOT_RUN",
        "EXTERNAL_PROVIDER_CLAIM_MISMATCH",
    )
    _require(
        gates.get("canonical_python_3_12") == "NOT_RUN", "PYTHON312_CLAIM_MISMATCH"
    )

    restart = report["restart_evidence"]
    expected_restart = set(schema["properties"]["restart_evidence"]["required"])
    _require(
        isinstance(restart, dict) and set(restart) == expected_restart,
        "INITIAL_RESTART_SHAPE_MISMATCH",
    )
    _require(restart["status"] == "NOT_RUN", "INITIAL_RESTART_MUST_REMAIN_NOT_RUN")
    pre_state = _digest(
        restart["pre_restart_state_digest"], "PRE_RESTART_STATE_INVALID"
    )
    _require(
        restart["post_restart_state_digest"] is None,
        "INITIAL_REPORT_MUST_NOT_CLAIM_POST_RESTART",
    )
    pre_postmaster = _datetime(
        restart["pre_restart_postmaster_started_at"],
        "PRE_RESTART_POSTMASTER_INVALID",
    ).isoformat()
    _require(
        restart["post_restart_postmaster_started_at"] is None,
        "INITIAL_REPORT_MUST_NOT_CLAIM_POSTMASTER_RESTART",
    )

    cleanup = report["cleanup"]
    _require(
        cleanup
        == {
            "status": "NOT_RUN",
            "compose_project_digest": None,
            "volume_identity_digest": None,
        },
        "INITIAL_CLEANUP_MUST_REMAIN_NOT_RUN",
    )
    for key in (
        "raw_prompt_logged",
        "protected_chunk_logged",
        "answer_candidate_text_logged",
        "raw_provider_response_logged",
        "raw_provider_response_id_logged",
        "raw_secret_logged",
        "raw_vector_logged",
        "database_url_logged",
    ):
        _require(report[key] is False, f"CONTENT_SAFETY_FLAG_TRUE:{key}")
    _require(
        report["external_real_boundary"] == "NOT_RUN",
        "L3A_EXTERNAL_REAL_MUST_BE_NOT_RUN",
    )
    _require(
        report["production_readiness"] == "MORE_EVIDENCE_NEEDED",
        "PRODUCTION_READINESS_OVERCLAIM",
    )
    checksum = _validate_checksum(report, "INITIAL_REPORT")
    _validate_content_safe(report)
    return {
        "checksum": checksum,
        "pre_state": pre_state,
        "pre_postmaster": pre_postmaster,
        "database_identity": database_identity,
    }


def validate_restart_report(
    report: dict[str, Any],
    initial: dict[str, str],
) -> str:
    _require(set(report) == RESTART_REQUIRED_FIELDS, "RESTART_REPORT_SHAPE_MISMATCH")
    _require(
        report.get("schema_version") == RESTART_SCHEMA_VERSION,
        "RESTART_SCHEMA_MISMATCH",
    )
    _require(report.get("scenario_id") == SCENARIO_ID, "RESTART_SCENARIO_MISMATCH")
    _require(report.get("status") == "PASS", "RESTART_REPORT_NOT_PASS")
    _require(report.get("generation_id") == "G3", "RESTART_GENERATION_MISMATCH")
    _require(report.get("pointer_revision") == 9, "RESTART_POINTER_MISMATCH")
    _require(
        report.get("authorization_snapshot_id") == "P2",
        "RESTART_AUTHORIZATION_MISMATCH",
    )
    _require(
        report.get("authorization_revision") == 2,
        "RESTART_AUTHORIZATION_REVISION_MISMATCH",
    )
    _require(
        report.get("final_dispatch_state") == "DELIVERED",
        "RESTART_DELIVERY_STATE_MISMATCH",
    )
    _require(
        report.get("recovery_record_count") == 7, "RESTART_RECOVERY_COUNT_MISMATCH"
    )
    _require(report.get("provider_call_count") == 0, "RESTART_PROVIDER_CALL_OCCURRED")
    _require(report.get("schemas_reinstalled") is False, "RESTART_REINSTALLED_SCHEMA")
    _require(report.get("schemas_reset") is False, "RESTART_RESET_SCHEMA")
    _require(report.get("external_provider_called") is False, "RESTART_CALLED_PROVIDER")
    started = _datetime(report.get("started_at"), "RESTART_STARTED_AT_INVALID")
    completed = _datetime(report.get("completed_at"), "RESTART_COMPLETED_AT_INVALID")
    _require(completed >= started, "RESTART_TIMELINE_INVALID")
    database_identity = _digest(
        report.get("database_identity_digest"),
        "RESTART_DATABASE_IDENTITY_INVALID",
    )
    _require(
        database_identity == initial["database_identity"],
        "RESTART_DATABASE_IDENTITY_CHANGED",
    )
    _digest(report.get("intent_identity_digest"), "RESTART_INTENT_IDENTITY_INVALID")
    recovery_digests = report.get("recovery_record_digests")
    _require(
        isinstance(recovery_digests, list) and len(recovery_digests) == 7,
        "RESTART_RECOVERY_DIGESTS_INVALID",
    )
    for index, digest in enumerate(recovery_digests):
        _digest(digest, f"RESTART_RECOVERY_DIGEST_INVALID:{index}")
    for key in (
        "raw_content_logged",
        "provider_response_logged",
        "secret_logged",
        "raw_vector_logged",
        "database_url_logged",
    ):
        _require(report.get(key) is False, f"RESTART_CONTENT_SAFETY_FLAG_TRUE:{key}")
    state = _digest(
        report.get("durable_state_identity_digest"), "RESTART_STATE_DIGEST_INVALID"
    )
    _require(state == initial["pre_state"], "RESTART_DURABLE_STATE_CHANGED")
    postmaster = _datetime(
        report.get("postmaster_started_at"), "RESTART_POSTMASTER_INVALID"
    ).isoformat()
    _require(
        postmaster != initial["pre_postmaster"], "DATABASE_CONTAINER_DID_NOT_RESTART"
    )
    checksum = _validate_checksum(report, "RESTART_REPORT")
    _validate_content_safe(report)
    return checksum


def validate_reports(
    integration_report_path: Path,
    restart_report_path: Path,
    schema_path: Path = SCHEMA_PATH,
    correction_path: Path = CORRECTION_PATH,
    artifact_root: Path = ROOT,
) -> dict[str, object]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    integration = json.loads(integration_report_path.read_text(encoding="utf-8"))
    restart = json.loads(restart_report_path.read_text(encoding="utf-8"))
    correction = json.loads(correction_path.read_text(encoding="utf-8"))
    _require(isinstance(schema, dict), "SCHEMA_MUST_BE_OBJECT")
    _require(isinstance(integration, dict), "INTEGRATION_REPORT_MUST_BE_OBJECT")
    _require(isinstance(restart, dict), "RESTART_REPORT_MUST_BE_OBJECT")
    _require(isinstance(correction, dict), "CORRECTION_REPORT_MUST_BE_OBJECT")
    _require(
        schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION,
        "EVIDENCE_SCHEMA_VERSION_MISMATCH",
    )
    correction_checksum = validate_correction_record(correction)
    initial = validate_initial_report(integration, schema, artifact_root)
    restart_checksum = validate_restart_report(restart, initial)
    return {
        "status": "PASS",
        "checks": {
            "append_only_separate_reports": True,
            "append_only_correction_record": True,
            "artifact_file_digests": True,
            "content_safe": True,
            "database_container_restart_observed": True,
            "durable_state_identity_preserved": True,
            "same_execution_cross_binding": True,
            "external_provider_remained_not_run": True,
            "production_readiness_not_overclaimed": True,
        },
        "correction_report_checksum": correction_checksum,
        "integration_report_checksum": initial["checksum"],
        "restart_report_checksum": restart_checksum,
        "replay_checksum": stable_hash(
            (correction_checksum, initial["checksum"], restart_checksum)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration-report", required=True, type=Path)
    parser.add_argument("--restart-report", required=True, type=Path)
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    parser.add_argument("--correction", type=Path, default=CORRECTION_PATH)
    parser.add_argument("--artifact-root", type=Path, default=ROOT)
    arguments = parser.parse_args()
    try:
        result = validate_reports(
            arguments.integration_report,
            arguments.restart_report,
            arguments.schema,
            arguments.correction,
            arguments.artifact_root,
        )
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "safe_reason": "DAY106_L3_EVIDENCE_REPLAY_FAILED",
                    "error_type": type(exc).__name__,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
