"""Replay the saved Day104 deterministic lifecycle evidence exactly."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from examples.day104_index_lifecycle import run_example  # noqa: E402
from rag_chunking_contracts import stable_hash  # noqa: E402


REPORT_PATH = ROOT / "evidence" / "day104-index-lifecycle-report.json"


def build_report_payload() -> dict[str, object]:
    """Return the deterministic, content-safe Day104 report payload."""

    example = json.loads(json.dumps(run_example(), sort_keys=True))
    payload: dict[str, object] = {
        "day": 104,
        "scenario_id": "day104-refund-index-generation-lifecycle-v1",
        "evidence_level": ("EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"),
        "fixture_production_eligible": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "example": example,
        "example_checksum": stable_hash(example),
        "raw_content_logged": False,
        "raw_vectors_logged": False,
        "not_run": [
            "real PostgreSQL transaction isolation",
            "real vector database and ANN",
            "distributed leases and multi-process crash recovery",
            "physical purge across caches and retained backups",
            "latency, capacity, cost and error-rate gates",
            "production traffic",
        ],
        "claim_boundary": (
            "Deterministic evidence proves immutable-generation identity, "
            "Manifest read-back, READY gates, CAS activation, alias "
            "reconciliation, leased ReadView drain, logical deletion and "
            "serving-index absence mechanics. It does not prove real "
            "database isolation, a real vector Provider, physical erasure, "
            "zero downtime or production readiness."
        ),
    }
    payload["report_checksum"] = stable_hash(payload)
    return payload


def run() -> dict[str, object]:
    saved = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    replayed = build_report_payload()
    saved_without_checksum = {
        key: value for key, value in saved.items() if key != "report_checksum"
    }
    example = replayed["example"]
    assert isinstance(example, dict)
    pointer = example.get("active_pointer")
    checks = {
        "report_checksum": (
            saved.get("report_checksum")
            == stable_hash(saved_without_checksum)
            == replayed["report_checksum"]
        ),
        "example_checksum": (
            saved.get("example_checksum") == replayed["example_checksum"]
        ),
        "deterministic_example": saved.get("example") == example,
        "normal_generation_migration": (
            example.get("ready_generations") == ["G1", "G2"]
            and example.get("activation_outcome") == "ACTIVATED"
            and pointer == {"generation_id": "G2", "revision": 8}
            and example.get("provider_alias") == "G2"
            and example.get("old_generation_state") == "RETIRED"
        ),
        "delete_and_retire_boundary": (
            example.get("deletion_outcome") == "VERIFIED"
            and example.get("physical_purge") == "NOT_RUN"
        ),
        "production_boundary": (
            saved.get("fixture_production_eligible") is False
            and saved.get("production_readiness") == "MORE_EVIDENCE_NEEDED"
            and example.get("real_database") == "NOT_RUN"
            and example.get("real_vector_provider") == "NOT_RUN"
        ),
        "content_safe": (
            saved.get("raw_content_logged") is False
            and saved.get("raw_vectors_logged") is False
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
