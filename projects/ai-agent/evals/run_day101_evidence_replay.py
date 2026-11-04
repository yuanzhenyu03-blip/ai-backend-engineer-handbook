from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from rag_reranking_experiments import run_controlled_experiment  # noqa: E402


def run() -> dict[str, object]:
    path = ROOT / "evidence" / "day101-query-rewrite-rerank-report.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    replayed = json.loads(json.dumps(
        run_controlled_experiment(), sort_keys=True
    ))
    checks = {
        "report_checksum": saved["report_checksum"] == replayed["report_checksum"],
        "fixture_checksum": saved["fixture_checksum"] == replayed["fixture_checksum"],
        "real_negative": saved["real_production_negative"] == replayed["real_production_negative"],
        "cases": saved["cases"] == replayed["cases"],
        "production_boundary": (
            saved["fixture_production_eligible"] is False
            and saved["production_readiness"] == "MORE_EVIDENCE_NEEDED"
            and saved["real_provider_calls"] == 0
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
