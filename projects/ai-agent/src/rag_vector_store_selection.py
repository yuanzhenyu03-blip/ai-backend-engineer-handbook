"""Hard-gate-first, evidence-bounded Day99 vector store selection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HardGateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


FROZEN_WEIGHTS = {
    "security_and_tenant_isolation": 0.25,
    "correctness_and_versionability": 0.20,
    "durability_and_recovery": 0.15,
    "measured_local_index_behavior": 0.15,
    "filtering_and_day100_fit": 0.10,
    "cost": 0.10,
    "operability_and_developer_experience": 0.05,
}


@dataclass(frozen=True)
class VectorStoreCandidate:
    candidate_id: str
    product_version: str
    deployment_mode: str
    hard_gates: tuple[tuple[str, HardGateStatus], ...]
    criterion_scores: tuple[tuple[str, float], ...]
    unresolved: tuple[str, ...]


def evaluate_candidates(
    candidates: tuple[VectorStoreCandidate, ...],
) -> dict[str, object]:
    if abs(sum(FROZEN_WEIGHTS.values()) - 1.0) > 1e-12:
        raise ValueError("vector store selection weights must sum to 100%")
    rows: list[dict[str, object]] = []
    eligible_rows: list[dict[str, object]] = []
    for candidate in candidates:
        gates = dict(candidate.hard_gates)
        scores = dict(candidate.criterion_scores)
        if set(scores) != set(FROZEN_WEIGHTS):
            raise ValueError("every weighted criterion must be frozen before scoring")
        if any(not 0.0 <= score <= 100.0 for score in scores.values()):
            raise ValueError("criterion scores must be between 0 and 100")
        eligible = bool(gates) and all(
            status is HardGateStatus.PASS for status in gates.values()
        )
        weighted_score = (
            sum(scores[name] * weight for name, weight in FROZEN_WEIGHTS.items())
            if eligible
            else None
        )
        row: dict[str, object] = {
            "candidate_id": candidate.candidate_id,
            "product_version": candidate.product_version,
            "deployment_mode": candidate.deployment_mode,
            "hard_gates": {
                name: status.value for name, status in candidate.hard_gates
            },
            "eligible": eligible,
            "weighted_score": weighted_score,
            "criterion_scores": scores,
            "unresolved": list(candidate.unresolved),
        }
        rows.append(row)
        if eligible:
            eligible_rows.append(row)
    eligible_rows.sort(
        key=lambda row: (-float(row["weighted_score"]), str(row["candidate_id"]))
    )
    selected = (
        str(eligible_rows[0]["candidate_id"]) if eligible_rows else None
    )
    return {
        "weights": FROZEN_WEIGHTS,
        "candidates": rows,
        "selected_candidate_id": selected,
        "outcome": (
            "PROVISIONAL_SELECTED" if selected is not None else "NO_ELIGIBLE_CANDIDATE"
        ),
        "evidence_scope": "OFFICIAL_STATIC_PLUS_POLICY_EXECUTION",
        "real_database_execution": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }


def classroom_candidates() -> tuple[VectorStoreCandidate, ...]:
    gate_names = (
        "vector_contract_compatibility",
        "homogeneous_embedding_contract",
        "application_owned_record_identity",
        "tenant_isolation_strategy",
        "protected_vector_egress",
        "versioned_generation",
        "exact_manifest_validation",
        "shadow_and_repairable_cutover",
        "timeout_reconciliation",
        "generation_safe_update_delete",
        "api_or_schema_version_strategy",
        "backup_restore_facts",
        "filter_path_not_authorization",
        "license_or_commercial_acceptability",
        "adapter_type_isolation",
    )

    def gates(**overrides: HardGateStatus):
        return tuple(
            (name, overrides.get(name, HardGateStatus.PASS))
            for name in gate_names
        )

    def scores(**values: float):
        return tuple((name, values[name]) for name in FROZEN_WEIGHTS)

    return (
        VectorStoreCandidate(
            "postgresql-pgvector-0.8.7",
            "pgvector 0.8.7 / PostgreSQL 13+",
            "SELF_HOSTED_POSTGRES",
            gates(),
            scores(
                security_and_tenant_isolation=85,
                correctness_and_versionability=90,
                durability_and_recovery=80,
                measured_local_index_behavior=0,
                filtering_and_day100_fit=85,
                cost=80,
                operability_and_developer_experience=75,
            ),
            (
                "real pgvector runtime NOT RUN",
                "workload ANN recall/latency NOT RUN",
                "backup/restore drill NOT RUN",
            ),
        ),
        VectorStoreCandidate(
            "qdrant-1.20.0",
            "1.20.0",
            "SELF_HOSTED_OR_MANAGED",
            gates(
                shadow_and_repairable_cutover=HardGateStatus.UNKNOWN,
                backup_restore_facts=HardGateStatus.UNKNOWN,
            ),
            scores(
                security_and_tenant_isolation=80,
                correctness_and_versionability=80,
                durability_and_recovery=70,
                measured_local_index_behavior=0,
                filtering_and_day100_fit=90,
                cost=70,
                operability_and_developer_experience=80,
            ),
            (
                "application DB plus Qdrant alias atomicity not established",
                "distributed restore drill NOT RUN",
                "real Qdrant runtime NOT RUN",
            ),
        ),
        VectorStoreCandidate(
            "pinecone-api-2025-10",
            "2025-10 stable control-plane API",
            "MANAGED_SERVERLESS_OR_BYOC",
            gates(
                protected_vector_egress=HardGateStatus.UNKNOWN,
                shadow_and_repairable_cutover=HardGateStatus.UNKNOWN,
                backup_restore_facts=HardGateStatus.UNKNOWN,
            ),
            scores(
                security_and_tenant_isolation=65,
                correctness_and_versionability=70,
                durability_and_recovery=70,
                measured_local_index_behavior=0,
                filtering_and_day100_fit=80,
                cost=55,
                operability_and_developer_experience=85,
            ),
            (
                "protected-vector managed egress approval UNKNOWN",
                "cross-system atomic cutover not established",
                "backup API evidence observed only on alpha page",
                "offline/local runtime unavailable and real API NOT RUN",
            ),
        ),
    )


def run_store_selection_experiment() -> dict[str, object]:
    return evaluate_candidates(classroom_candidates())
