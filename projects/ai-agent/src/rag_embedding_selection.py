"""Eligibility-first, evidence-bounded Day98 model selection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag_embedding_requirements import FrozenWeightedPreferences


class EvidenceLevel(str, Enum):
    OFFICIAL_STATIC = "OFFICIAL_STATIC"
    EXECUTED_LOCAL_RUNTIME = "EXECUTED_LOCAL_RUNTIME"
    NOT_RUN = "NOT_RUN"


class SelectionOutcome(str, Enum):
    PROVISIONAL_SELECTED = "PROVISIONAL_SELECTED"
    NO_ELIGIBLE_CANDIDATE = "NO_ELIGIBLE_CANDIDATE"


@dataclass(frozen=True)
class ModelCandidateEvidence:
    candidate_id: str
    exact_revision_pin: bool
    exact_tokenizer_pin: bool
    no_silent_truncation: bool
    response_correlation: bool
    protected_data_egress_allowed: bool
    tenant_isolation: bool
    quality_score: int | None
    governance_score: int
    reproducibility_score: int
    reliability_score: int
    cost_score: int
    operability_score: int
    evidence_level: EvidenceLevel
    unresolved: tuple[str, ...] = ()

    @property
    def hard_gate_failures(self) -> tuple[str, ...]:
        gates = {
            "EXACT_MODEL_REVISION": self.exact_revision_pin,
            "EXACT_TOKENIZER_REVISION": self.exact_tokenizer_pin,
            "NO_SILENT_TRUNCATION": self.no_silent_truncation,
            "RESPONSE_CORRELATION": self.response_correlation,
            "PROTECTED_DATA_EGRESS": self.protected_data_egress_allowed,
            "TENANT_ISOLATION": self.tenant_isolation,
            "LOCAL_QUALITY_EVIDENCE": self.quality_score is not None,
        }
        return tuple(name for name, passed in gates.items() if not passed)


@dataclass(frozen=True)
class ScoredCandidate:
    candidate_id: str
    eligible: bool
    score: float | None
    hard_gate_failures: tuple[str, ...]
    unresolved: tuple[str, ...]


@dataclass(frozen=True)
class ModelSelectionDecision:
    outcome: SelectionOutcome
    selected_candidate_id: str | None
    preferences_version: str
    candidates: tuple[ScoredCandidate, ...]
    production_readiness: str = "MORE_EVIDENCE_NEEDED"


def select_model(
    candidates: tuple[ModelCandidateEvidence, ...],
    *,
    preferences: FrozenWeightedPreferences,
) -> ModelSelectionDecision:
    """Apply hard gates first; never compensate a failed gate with weights."""

    scored: list[ScoredCandidate] = []
    for candidate in candidates:
        failures = candidate.hard_gate_failures
        score = None
        if not failures:
            assert candidate.quality_score is not None
            score = (
                candidate.quality_score * preferences.local_retrieval_quality
                + candidate.governance_score * preferences.security_and_governance
                + candidate.reproducibility_score * preferences.reproducibility
                + candidate.reliability_score * preferences.reliability_and_observability
                + candidate.cost_score * preferences.cost
                + candidate.operability_score * preferences.latency_and_operability
            ) / 100
        scored.append(ScoredCandidate(
            candidate.candidate_id,
            not failures,
            score,
            failures,
            candidate.unresolved,
        ))
    eligible = [item for item in scored if item.eligible]
    selected = max(
        eligible,
        key=lambda item: (item.score or 0.0, item.candidate_id),
        default=None,
    )
    return ModelSelectionDecision(
        SelectionOutcome.NO_ELIGIBLE_CANDIDATE if selected is None
        else SelectionOutcome.PROVISIONAL_SELECTED,
        None if selected is None else selected.candidate_id,
        preferences.version,
        tuple(scored),
    )
