from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_evaluation_experiments import run_controlled_experiment  # noqa: E402


def run() -> dict[str, object]:
    path = ROOT / "evidence" / "day103-rag-evaluation-report.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    replayed = json.loads(json.dumps(
        run_controlled_experiment(), sort_keys=True
    ))
    checks = {
        "report_checksum": (
            saved["report_checksum"] == replayed["report_checksum"]
        ),
        "fixture_checksum": (
            saved["fixture_checksum"] == replayed["fixture_checksum"]
        ),
        "cases": saved["cases"] == replayed["cases"],
        "independent_ground_truth": (
            saved["day102_verification_is_ground_truth"] is False
            and saved["ground_truth_owner"]
            == "independent-label-review-adjudication-v1"
        ),
        "production_boundary": (
            saved["fixture_production_eligible"] is False
            and saved["production_readiness"] == "MORE_EVIDENCE_NEEDED"
            and saved["real_retriever"] == "NOT_RUN"
            and saved["real_generator"] == "NOT_RUN"
            and saved["real_independent_human_labels"] == "NOT_RUN"
        ),
        "content_safe": (
            saved["raw_queries_in_report"] is False
            and saved["protected_claims_in_report"] is False
            and saved["protected_evidence_in_report"] is False
            and saved["provider_payloads_in_report"] is False
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "saved_report_checksum": saved["report_checksum"],
        "replayed_report_checksum": replayed["report_checksum"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
