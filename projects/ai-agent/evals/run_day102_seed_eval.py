from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from examples.day102_grounding_citations import (  # noqa: E402
    CLAIM_CHANNEL,
    build_day102_fixture,
    default_claim_templates,
)
from rag_grounding_adapters import AdapterMode, ClaimTemplate  # noqa: E402
from rag_grounding_contracts import SemanticRelation  # noqa: E402
from rag_reranker_contracts import Day101Outcome  # noqa: E402


SEED_PATH = ROOT / "evals" / "day102_grounding_citations_seed.jsonl"


def _revoke(fixture, occurrence_id: str) -> None:
    request = fixture.request
    fixture.authorization.revoke_occurrence(
        tenant_id=request.tenant_id,
        principal_subject=request.principal_subject,
        action=request.action,
        purpose=request.purpose,
        occurrence_id=occurrence_id,
    )


def _run_case(case: dict[str, object]) -> tuple[bool, dict[str, object]]:
    case_id = str(case["case_id"])
    options: dict[str, object] = {}
    if case_id == "degraded-upstream":
        options["day101_outcome"] = Day101Outcome.DEGRADED
    elif case_id == "generator-egress-denied":
        options["allow_generator_egress"] = False
    elif case_id == "out-of-bundle-citation":
        options["claim_templates"] = (
            default_claim_templates()[0],
            ClaimTemplate(
                "claim:submission-channel",
                "request-item:submission-channel",
                CLAIM_CHANNEL,
                ("occurrence:B",),
            ),
        )
    elif case_id == "unsupported-claim":
        options["relations_by_claim_id"] = {
            "claim:refund-window": SemanticRelation.SUPPORTED,
            "claim:submission-channel": SemanticRelation.UNSUPPORTED,
        }
    elif case_id == "contradicted-claim":
        options["relations_by_claim_id"] = {
            "claim:refund-window": SemanticRelation.CONTRADICTION,
            "claim:submission-channel": SemanticRelation.SUPPORTED,
        }
    elif case_id == "generator-timeout":
        options["generator_mode"] = AdapterMode.TIMEOUT
    elif case_id == "verifier-timeout-fallback":
        options.update(
            verifier_mode=AdapterMode.TIMEOUT,
            use_verifier_fallback=True,
        )
    fixture = build_day102_fixture(**options)
    if case_id == "tampered-handoff":
        fixture.request = replace(
            fixture.request,
            day101_handoff_digest="sha256:tampered",
        )
    if case_id == "post-verify-revocation":
        original_verify = fixture.verifier.verify

        def verify_then_revoke(**kwargs):
            results = original_verify(**kwargs)
            _revoke(fixture, "occurrence:A")
            return results

        fixture.verifier.verify = verify_then_revoke
    response = fixture.pipeline.execute(fixture.request)
    actual: dict[str, object] = {
        "outcome": response.outcome.value,
        "safe_reason": response.safe_reason,
        "upstream_outcome": response.upstream_outcome,
        "released_claim_ids": [
            item.claim_id for item in response.released_claims
        ],
        "rejected_reasons": sorted(
            item.reason for item in response.rejected_claims
        ),
        "abstained_count": sum(
            item.status.value == "ABSTAINED"
            for item in response.request_coverage
        ),
        "generator_calls": response.generator_calls,
        "verifier_calls": response.verifier_calls,
    }
    expected = dict(case["expected"])
    passed = all(actual.get(key) == value for key, value in expected.items())
    return passed, {
        "case_id": case_id,
        "passed": passed,
        "expected": expected,
        "actual": actual,
    }


def run() -> dict[str, object]:
    cases = [
        json.loads(line)
        for line in SEED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results = [_run_case(case) for case in cases]
    return {
        "cases": len(results),
        "passed": sum(passed for passed, _ in results),
        "all_passed": all(passed for passed, _ in results),
        "results": [detail for _, detail in results],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
