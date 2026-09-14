"""Deterministic Day91 Server-boundary example; no network or credentials."""
from __future__ import annotations

import json
from pathlib import Path
import sys

EVALS = Path(__file__).resolve().parents[1] / "evals"
sys.path.insert(0, str(EVALS))

from run_day91_seed_eval import evaluate  # noqa: E402


def main() -> None:
    summary = {
        "day": 91,
        "tool_candidate": evaluate("tool_candidate"),
        "tool_identity_conflict": evaluate("tool_identity_conflict"),
        "resource_injection": evaluate("resource_injection"),
        "prompt_rendered_injection": evaluate("prompt_rendered_injection"),
        "drain_timeout": evaluate("drain_timeout"),
        "production_tool_calls": 0,
        "remote_transport_calls": 0,
        "production": "NOT_RUN",
    }
    assert summary["tool_candidate"]["durable_transitions"] == 0
    assert summary["resource_injection"]["resource_reads"] == 1
    assert summary["prompt_rendered_injection"]["resource_reads"] == 0
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
