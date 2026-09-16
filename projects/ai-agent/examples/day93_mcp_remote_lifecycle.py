"""Deterministic Day93 lifecycle example; no network or credentials."""
from __future__ import annotations

import json
from pathlib import Path
import sys

EVALS = Path(__file__).resolve().parents[1] / "evals"
sys.path.insert(0, str(EVALS))

from run_day93_seed_eval import evaluate  # noqa: E402


def main() -> None:
    summary = {
        "day": 93,
        "read_timeout": evaluate("read_timeout_possible_execution"),
        "cancellation_after_dispatch": evaluate(
            "cancellation_after_dispatch"
        ),
        "authoritative_not_executed": evaluate(
            "reconciliation_not_executed"
        ),
        "shutdown": evaluate("graceful_shutdown_unknown"),
        "production_credentials": 0,
        "remote_transport_calls": 0,
        "production": "NOT_RUN",
    }
    assert summary["read_timeout"]["outcome"] == "PENDING_RECONCILIATION"
    assert summary["read_timeout"]["committer_calls"] == 0
    assert summary["shutdown"]["committer_calls"] == 0
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
