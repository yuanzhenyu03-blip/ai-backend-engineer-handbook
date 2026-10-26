"""Repeatable, content-safe Day98 selection and versioning experiment."""

from __future__ import annotations

from dataclasses import asdict

from rag_chunking_contracts import stable_hash
from rag_embedding_requirements import FrozenWeightedPreferences
from rag_embedding_selection import (
    EvidenceLevel,
    ModelCandidateEvidence,
    select_model,
)


def frozen_candidates() -> tuple[ModelCandidateEvidence, ...]:
    """Static official evidence plus explicit NOT RUN local-quality status."""

    return (
        ModelCandidateEvidence(
            "openai/text-embedding-3-large",
            exact_revision_pin=False,
            exact_tokenizer_pin=False,
            no_silent_truncation=True,
            response_correlation=True,
            protected_data_egress_allowed=False,
            tenant_isolation=True,
            quality_score=0,
            governance_score=35,
            reproducibility_score=20,
            reliability_score=85,
            cost_score=70,
            operability_score=90,
            evidence_level=EvidenceLevel.OFFICIAL_STATIC,
            unresolved=("immutable model snapshot not established", "local corpus NOT RUN"),
        ),
        ModelCandidateEvidence(
            "cohere/embed-v5.0-pro",
            exact_revision_pin=False,
            exact_tokenizer_pin=False,
            no_silent_truncation=True,
            response_correlation=False,
            protected_data_egress_allowed=False,
            tenant_isolation=True,
            quality_score=0,
            governance_score=35,
            reproducibility_score=25,
            reliability_score=70,
            cost_score=65,
            operability_score=80,
            evidence_level=EvidenceLevel.OFFICIAL_STATIC,
            unresolved=("dimension docs conflict", "local corpus NOT RUN"),
        ),
        ModelCandidateEvidence(
            "BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181",
            exact_revision_pin=True,
            exact_tokenizer_pin=True,
            no_silent_truncation=True,
            response_correlation=True,
            protected_data_egress_allowed=True,
            tenant_isolation=True,
            quality_score=0,
            governance_score=95,
            reproducibility_score=95,
            reliability_score=60,
            cost_score=75,
            operability_score=45,
            evidence_level=EvidenceLevel.OFFICIAL_STATIC,
            unresolved=("real weights/runtime NOT RUN", "local retrieval quality NOT RUN"),
        ),
    )


def run_selection_experiment() -> dict[str, object]:
    preferences = FrozenWeightedPreferences("day98-selection-weights.v1")
    decision = select_model(frozen_candidates(), preferences=preferences)
    matrix = [asdict(candidate) for candidate in decision.candidates]
    report: dict[str, object] = {
        "outcome": decision.outcome.value,
        "selected_candidate_id": decision.selected_candidate_id,
        "preferences_version": decision.preferences_version,
        "candidates": matrix,
        "evidence_scope": "OFFICIAL_STATIC_PLUS_DETERMINISTIC_POLICY_EXECUTION",
        "real_provider_execution": "NOT_RUN",
        "real_local_retrieval_quality": "NOT_RUN",
        "production_readiness": decision.production_readiness,
    }
    report["replay_checksum"] = stable_hash(report)
    return report
