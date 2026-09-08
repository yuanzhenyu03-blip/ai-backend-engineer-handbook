"""Deterministic Day87 handoff: research evidence, never final selection."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from framework_selection_evidence import (  # noqa: E402
    Confidence, ContractAssessment, ContractFit, EvidenceKind, EvidenceRecord,
    Freshness, Readiness, SourceType, build_day88_handoff,
)


def main() -> None:
    docs = EvidenceRecord(
        "candidate-b-docs", "candidate-b", "offers Tool hooks",
        "official documentation claim; application boundary not executed",
        "https://example.com/candidate-b/docs", "Candidate B",
        SourceType.OFFICIAL_DOCS, EvidenceKind.DOCUMENTATION, "1.2.3",
        "2026-09-01T00:00:00+00:00", "2026-09-08T16:08:29+08:00",
        Freshness.CURRENT, "", Confidence.HIGH,
    )
    boundary = ContractAssessment(
        "candidate-b", "application-adapter-current-auth", True,
        ContractFit.UNKNOWN, (), True,
    )
    handoff = build_day88_handoff(
        candidate="candidate-b", assessments=(boundary,), evidence=(docs,),
        score_scenarios=(
            {"candidate-a": 8.0, "candidate-b": 8.1},
            {"candidate-a": 8.2, "candidate-b": 8.0},
        ),
    )
    assert handoff.readiness is Readiness.MORE_EVIDENCE_NEEDED
    assert not handoff.framework_selection_final
    print(json.dumps({
        "day": 87,
        "readiness": handoff.readiness.value,
        "candidate": handoff.candidate,
        "blocking_contracts": handoff.blocking_contracts,
        "day88_discriminating_spike": handoff.discriminating_spike,
        "framework_selection_final": handoff.framework_selection_final,
        "real_external_calls": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
