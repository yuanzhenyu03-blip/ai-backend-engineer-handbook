"""Deterministic Day92 MCP security example; no real credentials or network."""
from __future__ import annotations

import json
from pathlib import Path
import sys

EVALS = Path(__file__).resolve().parents[1] / "evals"
sys.path.insert(0, str(EVALS))

from run_day92_seed_eval import evaluate  # noqa: E402


def main() -> None:
    summary = {
        "day": 92,
        "invalid_signature": evaluate("invalid_signature"),
        "tenant_mismatch": evaluate("tenant_mismatch"),
        "prompt_privilege": evaluate("prompt_privilege"),
        "key_rotation": evaluate("key_rotation"),
        "authorization_unavailable": evaluate("authorization_unavailable"),
        "production_credentials": 0,
        "remote_transport_calls": 0,
        "durable_business_transitions": 0,
        "production": "NOT_RUN",
    }
    assert summary["invalid_signature"]["principal_built"] is False
    assert summary["tenant_mismatch"]["service_calls"] == 0
    assert summary["prompt_privilege"]["handler_calls"] == 0
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
