"""Replay the saved Day104 L3 evidence without external dependencies."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "evidence" / "day104-l3-integration-report.json"
CONTRACT_PATH = ROOT / "evidence" / "day104-l3-evidence-schema.json"
MIGRATION_PATH = ROOT / "integration" / "day104" / "schema.sql"
INTEGRATION_RUNNER_PATH = ROOT / "evals" / "run_day104_l3_integration.py"

RUNNER_CHECKSUM = (
    "sha256:eeda55c84c37ae1eebaf81750e61f26a539276ded3f12f56e9a85789aa165507"
)
RESTART_CHECKSUM = (
    "sha256:1950873817bac0ba7bc6fee7c1c4b3947447bd8ce0974bb7f0adf55a8e2a1bce"
)
IMAGE_DIGEST = "sha256:0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f"
L2_CHECKSUM = "sha256:2faf8b4f538de1c5340596eb9b74ec5331fb23ba70a04bbd0fb97569359e7140"
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

REQUIRED_GATES = (
    "day99_candidate_identity_match",
    "schema_migration_integrity",
    "build_snapshot_repeatable_read",
    "physical_generation_immutability",
    "manifest_exact_readback",
    "day103_evaluation_hard_gates",
    "ready_freshness_guard",
    "activation_transaction_atomicity",
    "concurrent_pointer_cas",
    "lease_fencing",
    "read_view_single_generation",
    "drain_and_retirement",
    "pointer_projection_authority",
    "outbox_inbox_reconciliation",
    "deletion_no_resurrection",
    "restart_durability_and_idempotency",
)

LEVEL_4_KEYS = (
    "ha_replica_failover_and_restore",
    "multi_node_partition_and_split_brain",
    "production_iam_tls_and_secret_rotation",
    "physical_purge_across_wal_backups_and_caches",
    "production_scale_recall_capacity_cost_and_soak",
    "canary_or_blue_green_production_traffic",
    "incident_response_and_observation_window",
)

COMMANDS = {
    "day104-l3-unit": (
        "PYTHONPATH=src:tests:. python -m unittest "
        "tests.test_day104_l3_postgres_unit -q"
    ),
    "day104-l3-integration": (
        "DAY104_L3_INTEGRATION=1 PYTHONPATH=src:tests:. python -m unittest "
        "tests.test_day104_l3_postgres_integration -q"
    ),
    "day104-l3-runner": (
        "DAY104_L3_INTEGRATION=1 PYTHONPATH=src:. python "
        "evals/run_day104_l3_integration.py"
    ),
    "day104-l3-restart-replay": (
        "DAY104_L3_INTEGRATION=1 PYTHONPATH=src:. python "
        "evals/run_day104_l3_restart_replay.py"
    ),
}

TEST_EXPECTATIONS = {
    "day104-l3-unit": (32, "summary"),
    "day104-l3-integration": (7, "summary"),
    "day104-l3-runner": (17, RUNNER_CHECKSUM),
    "day104-l3-restart-replay": (1, RESTART_CHECKSUM),
}

FAILURE_EXPECTATIONS = {
    "sealed-generation-late-write": (
        "reject mutation after seal",
        "repository conflict and database trigger rejection",
    ),
    "wrong-evaluation-ruler": (
        "reject READY under changed ruler",
        "identity conflict",
    ),
    "stale-build-snapshot-activation": (
        "reject activation after current BuildSnapshot changed",
        "stale pointer",
    ),
    "activation-record-write-fault": (
        "roll back lifecycle, pointer, activation and Outbox",
        "no partial durable state",
    ),
    "concurrent-pointer-cas": (
        "allow exactly one activation winner",
        "ACTIVATED plus STALE_POINTER",
    ),
    "stale-activation-fence": (
        "reject old committer token",
        "stale fence",
    ),
    "expired-read-view": (
        "expire abandoned lease and decrement once",
        "one ReadView reaped",
    ),
    "stale-outbox-claim": (
        "fence replaced worker and converge exact replay",
        "old worker rejected; exact replay converged; digest conflict rejected",
    ),
}


def stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def parse_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("EXPECTED_DATETIME_STRING")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    require(parsed.tzinfo is not None, "DATETIME_REQUIRES_OFFSET")
    return parsed


def validate_evidence_timeline(
    report: dict[str, Any], report_completed_at: datetime
) -> None:
    structured_time_count = 0

    def walk(value: object, path: str) -> None:
        nonlocal structured_time_count
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if key in {"observed_at", "completed_at"} and child is not None:
                    structured_time_count += 1
                    require(
                        parse_datetime(child) <= report_completed_at,
                        f"EVIDENCE_TIME_AFTER_REPORT_COMPLETION:{child_path}",
                    )
                walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(report, "report")
    cleanup_completed_at = parse_datetime(report["cleanup"]["completed_at"])
    require(
        cleanup_completed_at == report_completed_at,
        "REPORT_COMPLETION_MUST_BIND_CLEANUP_COMPLETION",
    )
    require(structured_time_count > 1, "STRUCTURED_EVIDENCE_TIMES_MISSING")


def validate_core_contract(report: dict[str, Any], contract: dict[str, Any]) -> None:
    properties = contract["properties"]
    require(
        report["schema_version"] == properties["schema_version"]["const"],
        "SCHEMA_VERSION_MISMATCH",
    )
    require(
        report["scenario_id"] == properties["scenario_id"]["const"],
        "SCENARIO_ID_MISMATCH",
    )
    require(
        report["claim_boundary"] == properties["claim_boundary"]["const"],
        "CLAIM_BOUNDARY_MISMATCH",
    )
    require(
        set(REQUIRED_GATES) == set(properties["hard_gates"]["required"]),
        "CONTRACT_GATE_SET_CHANGED",
    )
    require(
        set(LEVEL_4_KEYS) == set(properties["level_4"]["required"]),
        "CONTRACT_LEVEL4_SET_CHANGED",
    )
    l2_const = properties["baselines"]["properties"]["day104_level_2"]["properties"][
        "report_checksum"
    ]["const"]
    require(l2_const == L2_CHECKSUM, "L2_CONTRACT_CHECKSUM_CHANGED")


def validate_environment(report: dict[str, Any]) -> None:
    environment = report["environment"]
    expected = {
        "docker_engine_version": "29.7.2",
        "docker_compose_version": "5.5.0",
        "image_reference": "pgvector/pgvector:0.8.7-pg16",
        "image_digest": IMAGE_DIGEST,
        "python_version": "3.11.5",
        "database_driver": "psycopg2-binary",
        "database_driver_version": "2.9.10",
        "postgresql_server_version": "16.15",
        "postgresql_server_version_num": 160015,
        "pgvector_extension_version": "0.8.7",
        "transaction_isolation": ["READ COMMITTED", "REPEATABLE READ"],
    }
    for key, value in expected.items():
        require(environment.get(key) == value, f"ENVIRONMENT_{key.upper()}_MISMATCH")
    database_identity = stable_hash(
        {
            "database": "day104_l3",
            "postgresql_server_version_num": 160015,
            "pgvector_extension_version": "0.8.7",
            "image_digest": IMAGE_DIGEST,
            "container_started_at": "2026-11-11T09:03:37.897393924Z",
            "postmaster_start_time": "2026-11-11T09:03:37.979252+00:00",
        }
    )
    require(
        environment.get("database_identity_digest") == database_identity,
        "DATABASE_IDENTITY_MISMATCH",
    )


def validate_gates(report: dict[str, Any]) -> None:
    hard_gates = report["hard_gates"]
    require(set(hard_gates) == set(REQUIRED_GATES), "REPORT_GATE_SET_MISMATCH")
    for name in REQUIRED_GATES:
        gate = hard_gates[name]
        require(gate.get("status") == "PASS", f"GATE_NOT_PASS:{name}")
        require(bool(gate.get("safe_reason")), f"GATE_REASON_MISSING:{name}")
        require(bool(gate.get("evidence_ids")), f"GATE_IDS_MISSING:{name}")
        digests = gate.get("evidence_digests", [])
        require(bool(digests), f"GATE_DIGESTS_MISSING:{name}")
        require(
            all(DIGEST_PATTERN.fullmatch(item) for item in digests),
            f"GATE_DIGEST_INVALID:{name}",
        )
        parse_datetime(gate.get("observed_at"))

    drain = hard_gates["drain_and_retirement"]
    require(
        "expired-read-view-reaper" in drain["evidence_ids"],
        "EXPIRED_REAPER_NOT_BOUND_TO_DRAIN_GATE",
    )
    restart = hard_gates["restart_durability_and_idempotency"]
    require(RESTART_CHECKSUM in restart["evidence_digests"], "RESTART_NOT_BOUND")


def validate_deletion_and_level4(report: dict[str, Any]) -> None:
    deletion = report["deletion_evidence"]
    require(
        deletion["verification_policy_id"] == "day104-l3-serving-absence-v1",
        "DELETION_POLICY_MISMATCH",
    )
    for name in ("logical_release", "serving_index_absence"):
        require(deletion[name]["status"] == "PASS", f"DELETION_{name}_NOT_PASS")
    physical = deletion["physical_purge"]
    require(physical["status"] == "NOT_RUN", "PHYSICAL_PURGE_OVERCLAIMED")
    require(physical["evidence_ids"] == [], "PHYSICAL_PURGE_HAS_EVIDENCE_IDS")
    require(physical["evidence_digests"] == [], "PHYSICAL_PURGE_HAS_DIGESTS")
    require(physical["observed_at"] is None, "PHYSICAL_PURGE_HAS_TIME")
    require(
        set(report["level_4"]) == set(LEVEL_4_KEYS)
        and all(value == "NOT_RUN" for value in report["level_4"].values()),
        "LEVEL4_BOUNDARY_CHANGED",
    )


def validate_tests_and_failures(report: dict[str, Any]) -> None:
    runs = report["test_runs"]
    require(len(runs) == len(TEST_EXPECTATIONS), "TEST_RUN_COUNT_MISMATCH")
    by_id = {item["runner_id"]: item for item in runs}
    require(set(by_id) == set(TEST_EXPECTATIONS), "TEST_RUNNER_SET_MISMATCH")
    for runner_id, (passed, report_rule) in TEST_EXPECTATIONS.items():
        item = by_id[runner_id]
        require(item["status"] == "PASS", f"TEST_NOT_PASS:{runner_id}")
        require(
            (item["passed"], item["failed"], item["skipped"]) == (passed, 0, 0),
            f"TEST_COUNTS_MISMATCH:{runner_id}",
        )
        require(
            item["command_digest"] == stable_hash(COMMANDS[runner_id]),
            f"COMMAND_DIGEST_MISMATCH:{runner_id}",
        )
        expected_report = (
            stable_hash(
                {
                    "runner_id": runner_id,
                    "passed": passed,
                    "failed": 0,
                    "skipped": 0,
                }
            )
            if report_rule == "summary"
            else report_rule
        )
        require(
            item["report_digest"] == expected_report,
            f"TEST_REPORT_DIGEST_MISMATCH:{runner_id}",
        )
    require(
        report["artifacts"]["test_report_digest"] == stable_hash(runs),
        "AGGREGATE_TEST_REPORT_DIGEST_MISMATCH",
    )

    failures = report["failure_injections"]
    by_checkpoint = {item["checkpoint_id"]: item for item in failures}
    require(
        set(by_checkpoint) == set(FAILURE_EXPECTATIONS),
        "FAILURE_INJECTION_SET_MISMATCH",
    )
    for checkpoint, (expected, observed) in FAILURE_EXPECTATIONS.items():
        item = by_checkpoint[checkpoint]
        require(item["status"] == "PASS", f"FAILURE_NOT_PASS:{checkpoint}")
        require(item["expected_outcome"] == expected, f"FAILURE_EXPECTED:{checkpoint}")
        require(item["observed_outcome"] == observed, f"FAILURE_OBSERVED:{checkpoint}")
        expected_digest = stable_hash(
            {
                "checkpoint_id": checkpoint,
                "expected_outcome": expected,
                "observed_outcome": observed,
                "runner_checksum": RUNNER_CHECKSUM,
            }
        )
        require(
            item["evidence_digest"] == expected_digest,
            f"FAILURE_DIGEST_MISMATCH:{checkpoint}",
        )


def validate_artifacts(report: dict[str, Any]) -> None:
    artifacts = report["artifacts"]
    require(
        artifacts["schema_migration_digest"] == file_digest(MIGRATION_PATH),
        "SCHEMA_FILE_DIGEST_MISMATCH",
    )
    require(
        artifacts["integration_runner_digest"] == file_digest(INTEGRATION_RUNNER_PATH),
        "INTEGRATION_RUNNER_DIGEST_MISMATCH",
    )
    require(
        artifacts["evidence_replay_runner_digest"]
        == file_digest(Path(__file__).resolve()),
        "EVIDENCE_REPLAY_RUNNER_DIGEST_MISMATCH",
    )


def validate_report() -> dict[str, object]:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    require(isinstance(report, dict), "REPORT_MUST_BE_OBJECT")
    require(isinstance(contract, dict), "CONTRACT_MUST_BE_OBJECT")

    validate_core_contract(report, contract)
    require(report["overall_status"] == "PASS", "REPORT_NOT_PASS")
    require(
        report["evidence_level"]
        == "EXECUTED_LOCAL_DOCKER_INTEGRATION_POSTGRESQL_PGVECTOR",
        "EVIDENCE_LEVEL_MISMATCH",
    )
    started = parse_datetime(report["started_at"])
    completed = parse_datetime(report["completed_at"])
    require(completed >= started, "REPORT_TIME_ORDER_INVALID")
    validate_evidence_timeline(report, completed)
    validate_environment(report)
    validate_gates(report)
    validate_deletion_and_level4(report)
    validate_tests_and_failures(report)
    validate_artifacts(report)

    require(report["fixture_production_eligible"] is False, "FIXTURE_OVERCLAIMED")
    require(report["raw_content_logged"] is False, "RAW_CONTENT_FLAG_INVALID")
    require(report["raw_vectors_logged"] is False, "RAW_VECTOR_FLAG_INVALID")
    require(
        report["production_readiness"] == "MORE_EVIDENCE_NEEDED",
        "PRODUCTION_READINESS_OVERCLAIMED",
    )
    serialized = json.dumps(report, sort_keys=True)
    require("postgresql://" not in serialized, "DATABASE_URL_LEAKED")
    require("DAY104_L3_DATABASE_URL" not in serialized, "DATABASE_ENV_LEAKED")

    checksum_payload = dict(report)
    checksum_payload.pop("report_checksum", None)
    checksum_payload.pop("replayed_report_checksum", None)
    checksum = stable_hash(checksum_payload)
    require(report["report_checksum"] == checksum, "REPORT_CHECKSUM_MISMATCH")
    require(
        report["replayed_report_checksum"] == checksum,
        "REPLAYED_CHECKSUM_MISMATCH",
    )
    return {
        "status": "PASS",
        "checks": {
            "core_schema_constants": True,
            "sixteen_hard_gates": True,
            "expired_reaper_in_drain_gate": True,
            "level_4_boundary": True,
            "test_and_failure_evidence": True,
            "artifact_file_digests": True,
            "evidence_timeline": True,
            "content_safe": True,
            "report_checksum": True,
        },
        "report_checksum": checksum,
        "saved_report_checksum": report["report_checksum"],
    }


def main() -> int:
    try:
        result = validate_report()
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "safe_reason": "DAY104_L3_EVIDENCE_REPLAY_FAILED",
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
