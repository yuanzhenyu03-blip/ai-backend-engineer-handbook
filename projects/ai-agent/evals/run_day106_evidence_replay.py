"""Replay and checksum-verify saved Day106 deterministic L2 evidence."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import cast


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from examples.day106_production_rag_capstone import run_example  # noqa: E402
from rag_chunking_contracts import stable_hash  # noqa: E402
from run_day106_seed_eval import run as run_seed  # noqa: E402


REPORT_PATH = ROOT / "evidence" / "day106-production-rag-capstone-report.json"
VALIDATION_PATH = ROOT / "evidence" / "day106-validation.json"

VALIDATION_SCHEMA_VERSION = "day106-validation.v1"
REPORT_SCHEMA_VERSION = "day106-production-rag-capstone-evidence.v2"
SCENARIO_ID = "day106-refund-capstone-l2-v1"
VALIDATION_STATUS = "ENVIRONMENT_LIMITED"
EXPECTED_GIT_IDENTITY: dict[str, object] = {
    "base_revision": "8c1056cbc6d1805b2a8c3d1c19e3191cf6ce576a",
    "branch": "day106-production-rag-capstone",
    "worktree": "UNCOMMITTED",
    "commit": "NOT_CREATED",
    "push": "NOT_RUN",
    "pull_request": "NOT_RUN",
    "merge": "NOT_RUN",
}
EXPECTED_RUNTIME: dict[str, object] = {
    "implementation": "CPython",
    "local_interpreter": "3.11.5",
    "repository_minimum": "3.12+",
    "canonical_python_3_12_local_validation": "NOT_RUN",
}
DEPENDENCY_FREE_EXCLUDED_FILES = (
    "tests/test_day90_mcp_sdk_integration.py",
    "tests/test_day91_mcp_server_sdk_integration.py",
    "tests/test_day93_mcp_remote_integration.py",
    "tests/test_day94_agent_mcp_sdk_integration.py",
    "tests/test_day94_restart_recovery_integration.py",
)
FULL_SUITE_ERROR_CODES = (
    "test_day90_mcp_sdk_integration:MCP_2_2_0_NOT_INSTALLED",
    "test_day91_mcp_server_sdk_integration:MCP_2_2_0_NOT_INSTALLED",
    "test_day93_mcp_remote_integration:HTTPX2_NOT_INSTALLED",
    "test_day94_agent_mcp_sdk_integration:HTTPX2_NOT_INSTALLED",
    "test_day94_restart_recovery_integration:LOOPBACK_BIND_PERMISSION_DENIED",
)
# Counts are the exact unittest summaries for the sealed Python 3.11.5 run.
# Changing the test surface requires updating these constants and resealing evidence.
FOCUSED_TEST_COUNT = 44
DEPENDENCY_FREE_TEST_COUNT = 1376
FULL_SUITE_TESTS_RUN = 1380
SKIPPED_TEST_COUNT = 16
SEED_EVALUATOR_COUNT = 22
HISTORICAL_REPLAY_COUNT = 8
OFFLINE_REPLAY_CHECK_COUNT = 8

FOCUSED_TEST_COMMAND = (
    "PYTHONPATH=src:. python -m unittest discover -s tests "
    "-p 'test_day106_*.py' -v"
)
DEPENDENCY_FREE_COMMAND = (
    "find tests -maxdepth 1 -name 'test_*.py' "
    "! -name 'test_day90_mcp_sdk_integration.py' "
    "! -name 'test_day91_mcp_server_sdk_integration.py' "
    "! -name 'test_day93_mcp_remote_integration.py' "
    "! -name 'test_day94_agent_mcp_sdk_integration.py' "
    "! -name 'test_day94_restart_recovery_integration.py' "
    "-exec basename {} .py \\; | sort | "
    "xargs env PYTHONPATH=src:tests:. python -m unittest"
)
FULL_SUITE_COMMAND = (
    "PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_*.py' -v"
)
DAY106_SEED_COMMAND = "PYTHONPATH=src:. python evals/run_day106_seed_eval.py"
ALL_SEED_COMMAND = (
    "for eval_file in evals/run_day*_seed_eval.py; do "
    "PYTHONPATH=src:. python \"$eval_file\" || exit 1; done"
)
HISTORICAL_REPLAY_COMMAND = (
    "for eval_file in evals/run_day*_evidence_replay.py; do "
    "[ \"$eval_file\" = evals/run_day106_evidence_replay.py ] || "
    "PYTHONPATH=src:. python \"$eval_file\" || exit 1; done"
)
COMPILEALL_COMMAND = "PYTHONPATH=src:. python -m compileall -q src tests evals examples"
GIT_DIFF_COMMAND = "git diff --check"
JSON_PARSE_COMMAND = (
    "PYTHONPATH=src:. python -c \"import json; from pathlib import Path; "
    "root=Path('.'); [json.loads(path.read_text()) for path in "
    "root.rglob('*.json')]; [json.loads(line) for path in "
    "root.rglob('*.jsonl') for line in path.read_text().splitlines() "
    "if line.strip()]\""
)
DETERMINISTIC_EXAMPLE_COMMAND = (
    "PYTHONPATH=src:. python examples/day106_production_rag_capstone.py"
)
OFFLINE_REPLAY_COMMAND = (
    "PYTHONPATH=src:. python evals/run_day106_evidence_replay.py"
)


def _require_object(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"{label} must be a JSON object with string keys")
    return cast(dict[str, object], value)


def _require_exact_keys(
    value: dict[str, object],
    *,
    expected: frozenset[str],
    label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = tuple(sorted(expected - actual))
        unexpected = tuple(sorted(actual - expected))
        raise ValueError(
            f"{label} keys do not match the Day106 validation contract; "
            f"missing={missing!r}, unexpected={unexpected!r}"
        )


def _require_equal(actual: object, expected: object, *, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} does not match the Day106 validation contract: "
            f"expected={expected!r}, actual={actual!r}"
        )


def _require_execution_record(
    executed: dict[str, object],
    *,
    name: str,
    keys: frozenset[str],
    command: str,
    status: str,
) -> dict[str, object]:
    record = _require_object(executed.get(name), label=f"executed.{name}")
    _require_exact_keys(record, expected=keys, label=f"executed.{name}")
    _require_equal(
        record["command"],
        command,
        label=f"executed.{name}.command",
    )
    _require_equal(
        record["status"],
        status,
        label=f"executed.{name}.status",
    )
    return record


def _parse_structured_files() -> tuple[int, int]:
    """Parse the current JSON/JSONL surface and return exact file counts."""

    json_paths = tuple(sorted(ROOT.rglob("*.json")))
    jsonl_paths = tuple(sorted(ROOT.rglob("*.jsonl")))
    for path in json_paths:
        json.loads(path.read_text(encoding="utf-8"))
    for path in jsonl_paths:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSONL at {path.relative_to(ROOT)}:{line_number}"
                ) from exc
    return len(json_paths), len(jsonl_paths)


def _validate_validation_contract(
    *,
    validation: object,
    saved: dict[str, object],
    replayed: dict[str, object],
    seed: dict[str, object],
) -> None:
    """Fail loudly if any saved Day106 validation fact is missing or weakened."""

    payload = _require_object(validation, label="validation")
    _require_exact_keys(
        payload,
        expected=frozenset(
            {
                "schema_version",
                "day",
                "scenario_id",
                "status",
                "report_sha256",
                "git",
                "runtime",
                "executed",
            }
        ),
        label="validation",
    )
    _require_equal(
        payload["schema_version"],
        VALIDATION_SCHEMA_VERSION,
        label="validation.schema_version",
    )
    _require_equal(payload["day"], 106, label="validation.day")
    _require_equal(
        payload["scenario_id"],
        SCENARIO_ID,
        label="validation.scenario_id",
    )
    _require_equal(
        payload["status"],
        VALIDATION_STATUS,
        label="validation.status",
    )
    _require_equal(
        payload["report_sha256"],
        saved.get("report_checksum"),
        label="validation.report_sha256",
    )

    git_identity = _require_object(payload["git"], label="validation.git")
    _require_exact_keys(
        git_identity,
        expected=frozenset(EXPECTED_GIT_IDENTITY),
        label="validation.git",
    )
    _require_equal(
        git_identity,
        EXPECTED_GIT_IDENTITY,
        label="validation.git",
    )
    repository_state = _require_object(
        saved.get("repository_state"),
        label="saved.repository_state",
    )
    for key in ("base_revision", "branch", "worktree"):
        _require_equal(
            git_identity[key],
            repository_state.get(key),
            label=f"validation.git.{key} -> saved.repository_state",
        )

    runtime = _require_object(payload["runtime"], label="validation.runtime")
    _require_exact_keys(
        runtime,
        expected=frozenset(EXPECTED_RUNTIME),
        label="validation.runtime",
    )
    _require_equal(runtime, EXPECTED_RUNTIME, label="validation.runtime")

    executed = _require_object(payload["executed"], label="validation.executed")
    _require_exact_keys(
        executed,
        expected=frozenset(
            {
                "focused_tests",
                "dependency_free_regression",
                "full_ai_agent_tests",
                "day106_seed",
                "all_seed_evaluators",
                "historical_saved_evidence_replays",
                "compileall",
                "git_diff_check",
                "json_and_jsonl_parse",
                "deterministic_example",
                "day106_evidence_replay",
            }
        ),
        label="validation.executed",
    )

    test_keys = frozenset(
        {"command", "status", "tests_run", "failures", "errors", "skipped"}
    )
    focused = _require_execution_record(
        executed,
        name="focused_tests",
        keys=test_keys,
        command=FOCUSED_TEST_COMMAND,
        status="PASS",
    )
    _require_equal(
        focused["tests_run"],
        FOCUSED_TEST_COUNT,
        label="focused_tests.tests_run",
    )
    _require_equal(focused["failures"], 0, label="focused_tests.failures")
    _require_equal(focused["errors"], 0, label="focused_tests.errors")
    _require_equal(focused["skipped"], 0, label="focused_tests.skipped")

    dependency_free = _require_execution_record(
        executed,
        name="dependency_free_regression",
        keys=test_keys | frozenset({"excluded_files"}),
        command=DEPENDENCY_FREE_COMMAND,
        status="PASS",
    )
    _require_equal(
        dependency_free["tests_run"],
        DEPENDENCY_FREE_TEST_COUNT,
        label="dependency_free_regression.tests_run",
    )
    _require_equal(
        dependency_free["failures"],
        0,
        label="dependency_free_regression.failures",
    )
    _require_equal(
        dependency_free["errors"],
        0,
        label="dependency_free_regression.errors",
    )
    _require_equal(
        dependency_free["skipped"],
        SKIPPED_TEST_COUNT,
        label="dependency_free_regression.skipped",
    )
    _require_equal(
        dependency_free["excluded_files"],
        list(DEPENDENCY_FREE_EXCLUDED_FILES),
        label="dependency_free_regression.excluded_files",
    )

    full_suite = _require_execution_record(
        executed,
        name="full_ai_agent_tests",
        keys=test_keys | frozenset({"error_codes"}),
        command=FULL_SUITE_COMMAND,
        status="ENVIRONMENT_LIMITED",
    )
    _require_equal(
        full_suite["tests_run"],
        FULL_SUITE_TESTS_RUN,
        label="full_ai_agent_tests.tests_run",
    )
    _require_equal(
        full_suite["failures"],
        0,
        label="full_ai_agent_tests.failures",
    )
    _require_equal(
        full_suite["errors"],
        len(FULL_SUITE_ERROR_CODES),
        label="full_ai_agent_tests.errors",
    )
    _require_equal(
        full_suite["skipped"],
        SKIPPED_TEST_COUNT,
        label="full_ai_agent_tests.skipped",
    )
    _require_equal(
        full_suite["error_codes"],
        list(FULL_SUITE_ERROR_CODES),
        label="full_ai_agent_tests.error_codes",
    )

    seed_record = _require_execution_record(
        executed,
        name="day106_seed",
        keys=frozenset({"command", "status", "cases", "passed", "failed"}),
        command=DAY106_SEED_COMMAND,
        status="PASS",
    )
    for key in ("cases", "passed", "failed"):
        _require_equal(
            seed_record[key],
            seed.get(key),
            label=f"day106_seed.{key}",
        )
    _require_equal(seed_record["failed"], 0, label="day106_seed.failed")
    _require_equal(seed.get("all_passed"), True, label="replayed seed result")

    all_seeds = _require_execution_record(
        executed,
        name="all_seed_evaluators",
        keys=frozenset(
            {"command", "status", "evaluators", "passed", "failed"}
        ),
        command=ALL_SEED_COMMAND,
        status="PASS",
    )
    _require_equal(
        all_seeds["evaluators"],
        SEED_EVALUATOR_COUNT,
        label="all_seed_evaluators.evaluators",
    )
    _require_equal(
        all_seeds["passed"],
        SEED_EVALUATOR_COUNT,
        label="all_seed_evaluators.passed",
    )
    _require_equal(all_seeds["failed"], 0, label="all_seed_evaluators.failed")

    historical = _require_execution_record(
        executed,
        name="historical_saved_evidence_replays",
        keys=frozenset({"command", "status", "replays", "passed", "failed"}),
        command=HISTORICAL_REPLAY_COMMAND,
        status="PASS",
    )
    _require_equal(
        historical["replays"],
        HISTORICAL_REPLAY_COUNT,
        label="historical_saved_evidence_replays.replays",
    )
    _require_equal(
        historical["passed"],
        HISTORICAL_REPLAY_COUNT,
        label="historical_saved_evidence_replays.passed",
    )
    _require_equal(
        historical["failed"],
        0,
        label="historical_saved_evidence_replays.failed",
    )

    simple_records = (
        ("compileall", COMPILEALL_COMMAND),
        ("git_diff_check", GIT_DIFF_COMMAND),
    )
    for name, command in simple_records:
        _require_execution_record(
            executed,
            name=name,
            keys=frozenset({"command", "status"}),
            command=command,
            status="PASS",
        )

    json_count, jsonl_count = _parse_structured_files()
    structured = _require_execution_record(
        executed,
        name="json_and_jsonl_parse",
        keys=frozenset(
            {"command", "status", "json_files", "jsonl_files", "failed"}
        ),
        command=JSON_PARSE_COMMAND,
        status="PASS",
    )
    _require_equal(structured["json_files"], json_count, label="JSON file count")
    _require_equal(structured["jsonl_files"], jsonl_count, label="JSONL file count")
    _require_equal(structured["failed"], 0, label="JSON/JSONL parse failures")

    deterministic = _require_execution_record(
        executed,
        name="deterministic_example",
        keys=frozenset({"command", "status", "report_sha256"}),
        command=DETERMINISTIC_EXAMPLE_COMMAND,
        status="PASS",
    )
    _require_equal(
        deterministic["report_sha256"],
        replayed.get("report_checksum"),
        label="deterministic_example.report_sha256",
    )

    offline = _require_execution_record(
        executed,
        name="day106_evidence_replay",
        keys=frozenset(
            {
                "command",
                "status",
                "checks",
                "passed",
                "failed",
                "saved_report_sha256",
                "replayed_report_sha256",
            }
        ),
        command=OFFLINE_REPLAY_COMMAND,
        status="PASS",
    )
    _require_equal(
        offline["checks"],
        OFFLINE_REPLAY_CHECK_COUNT,
        label="day106_evidence_replay.checks",
    )
    _require_equal(
        offline["passed"],
        OFFLINE_REPLAY_CHECK_COUNT,
        label="day106_evidence_replay.passed",
    )
    _require_equal(offline["failed"], 0, label="day106_evidence_replay.failed")
    _require_equal(
        offline["saved_report_sha256"],
        saved.get("report_checksum"),
        label="day106_evidence_replay.saved_report_sha256",
    )
    _require_equal(
        offline["replayed_report_sha256"],
        replayed.get("report_checksum"),
        label="day106_evidence_replay.replayed_report_sha256",
    )


def run() -> dict[str, object]:
    """Verify deterministic payload, checksum, validation, and claim boundary."""

    saved = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    validation: object = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))
    # The saved artifact is JSON-native: tuples in frozen runtime contracts
    # round-trip as arrays. Normalize the fresh deterministic report through
    # the same public serialization boundary before exact payload comparison.
    replayed = json.loads(json.dumps(run_example(), sort_keys=True))
    seed = run_seed()
    without_checksum = {
        key: value for key, value in saved.items() if key != "report_checksum"
    }
    _validate_validation_contract(
        validation=validation,
        saved=saved,
        replayed=replayed,
        seed=seed,
    )
    evaluation = saved.get("evaluation", {})
    if not isinstance(evaluation, dict):
        evaluation = {}
    not_run = saved.get("not_run", [])
    if not isinstance(not_run, list):
        not_run = []
    checks = {
        "report_checksum": (
            saved.get("report_checksum")
            == stable_hash(without_checksum)
            == replayed.get("report_checksum")
        ),
        "deterministic_payload": saved == replayed,
        "schema_and_identity": (
            saved.get("schema_version")
            == REPORT_SCHEMA_VERSION
            and saved.get("day") == 106
            and saved.get("scenario_id") == "day106-refund-capstone-l2-v1"
        ),
        "l2_claim_boundary": (
            saved.get("evidence_level") == "EXECUTED_LOCAL_RUNTIME"
            and saved.get("runtime_boundary")
            == "IN_PROCESS_DETERMINISTIC_ADAPTERS"
            and saved.get("fixture_production_eligible") is False
            and saved.get("day106_overall_status")
            == "NOT_CLAIMED_BY_RUNTIME_REPORT"
            and "EXCLUDES_OFFLINE_REPLAY"
            in str(saved.get("overall_status_scope"))
            and saved.get("production_readiness") == "MORE_EVIDENCE_NEEDED"
            and len(not_run) >= 6
        ),
        "content_safe": all(
            saved.get(key) is False
            for key in (
                "raw_prompt_logged",
                "protected_chunk_logged",
                "answer_candidate_text_logged",
                "secret_logged",
                "raw_vector_logged",
            )
        ),
        "runtime_seal_did_not_preclaim_replay": (
            evaluation.get("evidence_replay_at_runtime_seal") == "NOT_RUN"
        ),
        "seed_replay": seed.get("all_passed") is True,
        "validation_contract": True,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "saved_report_checksum": saved.get("report_checksum"),
        "replayed_report_checksum": replayed.get("report_checksum"),
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
