"""Replay the content-safe Day105 deterministic security evidence."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from examples.day105_rag_security import run_example  # noqa: E402
from rag_chunking_contracts import stable_hash  # noqa: E402
from run_day105_seed_eval import load_cases, run as run_seed  # noqa: E402


REPORT_PATH = ROOT / "evidence" / "day105-rag-security-report.json"
VALIDATION_PATH = ROOT / "evidence" / "day105-validation.json"
EVIDENCE_LEVEL = "EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"


def build_report_payload() -> dict[str, object]:
    """Build the deterministic, content-safe Day105 report payload."""

    seed = run_seed()
    if not seed["all_passed"]:
        raise RuntimeError("Day105 seed cases must pass before report replay")
    example = run_example()
    if example.get("evidence_level") != EVIDENCE_LEVEL:
        raise RuntimeError("Day105 example has the wrong evidence level")
    if example.get("fixture_production_eligible") is not False:
        raise RuntimeError("Day105 example cannot claim production eligibility")
    example_evaluation = example.get("evaluation")
    if not isinstance(example_evaluation, dict):
        raise ValueError("Day105 example evaluation must be an object")
    if example_evaluation.get("result") != "PASS":
        raise RuntimeError("Day105 deterministic example must pass")
    seed_results = seed.get("results")
    if not isinstance(seed_results, list):
        raise ValueError("seed results must be a list")
    case_summaries: list[dict[str, object]] = []
    for item in seed_results:
        if not isinstance(item, dict):
            raise ValueError("each seed result must be an object")
        actual = item.get("actual")
        if not isinstance(actual, dict):
            raise ValueError("each seed result requires actual observations")
        case_summaries.append(
            {
                "case_id": item["case_id"],
                "decision": actual["decision"],
                "decision_reason": actual["decision_reason"],
                "stage_decisions": actual["stage_decisions"],
                "required_evidence_status": actual["required_evidence_status"],
                "stages": {
                    key: actual[key]
                    for key in (
                        "attack_retrieved",
                        "attack_entered_prompt",
                        "attack_influenced_candidate",
                        "attack_passed_release",
                    )
                },
                "quarantined_occurrence_ids": actual["quarantined_occurrence_ids"],
                "hard_gates": actual["hard_gates"],
            }
        )
    payload: dict[str, object] = {
        "schema_version": "day105-rag-security-evidence.v1",
        "day": 105,
        "scenario_id": "day105-refund-rag-security-boundaries-v1",
        "evidence_level": EVIDENCE_LEVEL,
        "overall_status": "PASS",
        "overall_status_scope": "EXPECTATION_CONFORMANCE",
        "level_3_status": "NOT_RUN",
        "level_4_status": "NOT_RUN",
        "fixture_production_eligible": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "baseline": {
            "generation": "G2",
            "pointer_revision": 8,
            "manifest_occurrence_ids": ["A@v1", "C@v1"],
            "expected_absent_tombstoned_ids": ["B@v1"],
        },
        "hypothetical_adversarial_fixture": {
            "scope": "INDEPENDENT_NEGATIVE_CONTROLS",
            "selected_for_serving": False,
            "generation_identity": "DAY105-ATTACK-LAB-GX",
            "occurrence_ids": [
                "X@v1",
                "Y@v1",
                "Z1@v1",
                "Z2@v1",
                "T@v1",
            ],
            "claim_boundary": (
                "These content-safe observations do not assert that the "
                "attack occurrences belong to the current G2 Manifest."
            ),
        },
        "seed_dataset_digest": stable_hash(load_cases()),
        "seed_evaluation": {
            "cases": seed["cases"],
            "passed": seed["passed"],
            "failed": seed["failed"],
            "decision_counts": seed["decision_counts"],
        },
        "normal_quality_control": {
            "scope": "INDEPENDENT_Q1_Q2_Q3_CONTROL_SUITE",
            "queries": ["Q1", "Q2", "Q3"],
            "non_compensable": True,
        },
        "deterministic_example": example,
        "case_summaries": case_summaries,
        "hard_gate_names": [
            "case_evaluator_execution",
            "unauthorized_occurrence_entering_prompt_zero",
            "cross_tenant_leakage_zero",
            "tombstone_resurrection_zero",
            "sensitive_output_violation_zero",
            "protected_metadata_disclosure_zero",
            "critical_attack_success_zero",
            "unsafe_rollback_activation_zero",
            "citation_exact_binding",
            "normal_quality_preserved",
        ],
        "status_precedence": [
            "FAIL",
            "INCONCLUSIVE",
            "NOT_RUN",
            "PASS",
        ],
        "raw_attack_payloads_logged": False,
        "raw_system_prompts_logged": False,
        "raw_secrets_logged": False,
        "raw_cross_tenant_content_logged": False,
        "not_run": [
            "real PostgreSQL/pgvector retrieval and context assembly",
            "local integration failure injection and restart replay",
            "real model Provider execution",
            "real vector Provider security integration",
            "real multi-tenant IAM and egress enforcement",
            "production red-team and continuously updated attack corpus",
            "production-size load, capacity, cost and soak",
            "canary traffic and incident-response observation window",
        ],
        "claim_boundary": (
            "Deterministic local evidence proves application-owned Day105 "
            "identity, authority, stage-observation, fail-closed and release "
            "decision mechanics for content-safe fixtures. It does not prove "
            "real model or vector Provider behavior, production tenant "
            "isolation, production egress enforcement or readiness."
        ),
    }
    payload["report_checksum"] = stable_hash(payload)
    return payload


def run() -> dict[str, object]:
    """Compare saved evidence with deterministic replay and validation."""

    saved = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    validation = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))
    replayed = build_report_payload()
    saved_without_checksum = {
        key: value for key, value in saved.items() if key != "report_checksum"
    }
    validation_executed = validation.get("executed", {})
    if not isinstance(validation_executed, dict):
        validation_executed = {}
    validation_seed = validation_executed.get("day105_seed", {})
    if not isinstance(validation_seed, dict):
        validation_seed = {}
    replayed_seed = replayed.get("seed_evaluation")
    if not isinstance(replayed_seed, dict):
        raise ValueError("replayed seed evaluation must be an object")
    replayed_example = replayed.get("deterministic_example")
    if not isinstance(replayed_example, dict):
        raise ValueError("replayed deterministic example must be an object")
    saved_example = saved.get("deterministic_example")
    if not isinstance(saved_example, dict):
        saved_example = {}
    hard_gate_names = saved.get("hard_gate_names", [])
    if not isinstance(hard_gate_names, list):
        hard_gate_names = []
    not_run = saved.get("not_run", [])
    if not isinstance(not_run, list):
        not_run = []

    checks = {
        "report_checksum": (
            saved.get("report_checksum")
            == stable_hash(saved_without_checksum)
            == replayed["report_checksum"]
        ),
        "deterministic_payload": saved == replayed,
        "deterministic_example_replay": (
            saved_example == replayed_example
            and saved_example.get("report_checksum")
            == replayed_example.get("report_checksum")
        ),
        "schema_and_identity": (
            saved.get("schema_version") == "day105-rag-security-evidence.v1"
            and saved.get("day") == 105
            and saved.get("scenario_id") == "day105-refund-rag-security-boundaries-v1"
        ),
        "hard_gate_schema": (
            saved.get("hard_gate_names") == replayed["hard_gate_names"]
            and "normal_quality_preserved" in hard_gate_names
        ),
        "content_safe": (
            saved.get("raw_attack_payloads_logged") is False
            and saved.get("raw_system_prompts_logged") is False
            and saved.get("raw_secrets_logged") is False
            and saved.get("raw_cross_tenant_content_logged") is False
        ),
        "production_boundary": (
            saved.get("fixture_production_eligible") is False
            and saved.get("production_readiness") == "MORE_EVIDENCE_NEEDED"
            and len(not_run) >= 6
        ),
        "validation_binding": (
            validation.get("day") == 105
            and validation.get("evidence_level") == EVIDENCE_LEVEL
            and validation.get("day105_report_checksum") == saved.get("report_checksum")
            and validation.get("day105_example_checksum")
            == replayed_example.get("report_checksum")
            and validation_seed.get("status") == "PASS"
            and validation_seed.get("passed") == replayed_seed.get("passed")
            and validation_seed.get("failed") == 0
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "saved_report_checksum": saved.get("report_checksum"),
        "replayed_report_checksum": replayed["report_checksum"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
