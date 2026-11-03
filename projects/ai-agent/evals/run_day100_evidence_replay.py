"""Replay the saved content-safe Day100 controlled experiment report."""

from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "src"))

from rag_retrieval_experiments import run_controlled_experiment  # noqa: E402
from rag_chunking_contracts import stable_hash  # noqa: E402


def run() -> dict[str, object]:
    path = PROJECT / "evidence" / "day100-hybrid-retrieval-report.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    replayed = run_controlled_experiment()
    canonical_match = stable_hash(saved) == stable_hash(replayed)
    checksum_match = (
        saved.get("report_checksum") == replayed.get("report_checksum")
    )
    return {
        "replay": "PASS" if canonical_match and checksum_match else "FAIL",
        "saved_checksum": saved.get("report_checksum"),
        "replayed_checksum": replayed.get("report_checksum"),
        "real_provider": replayed["real_provider"],
        "real_ann_recall": replayed["real_ann_recall"],
        "production_readiness": replayed["production_readiness"],
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["replay"] != "PASS":
        raise SystemExit(1)
