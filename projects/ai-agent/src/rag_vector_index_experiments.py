"""Content-safe exact oracle and explicitly simulated ANN experiment."""

from __future__ import annotations

import math

from rag_chunking_contracts import stable_hash
from rag_embedding_contracts import canonical_float32_vector
from rag_vector_adapter import ExactFlatReference
from rag_vector_contracts import VectorPoint


CORPUS_VERSION = "day99-controlled-vectors.v1"
CORPUS_SEED = 99
CORPUS_SIZE = 256
CORPUS_DIMENSIONS = 8
QUERY_COUNT = 8
K = 5


def recall_at_k(
    gold_ids: tuple[str, ...],
    candidate_ids: tuple[str, ...],
) -> float:
    if not gold_ids:
        raise ValueError("recall@k requires a non-empty gold result")
    if len(set(gold_ids)) != len(gold_ids):
        raise ValueError("gold result identities must be unique")
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("candidate result identities must be unique")
    return len(set(gold_ids) & set(candidate_ids)) / len(gold_ids)


def rank_overlap(
    left_ids: tuple[str, ...],
    right_ids: tuple[str, ...],
) -> float:
    denominator = min(len(left_ids), len(right_ids))
    if denominator == 0:
        raise ValueError("rank overlap requires two non-empty rankings")
    return len(set(left_ids) & set(right_ids)) / denominator


def controlled_corpus() -> tuple[VectorPoint, ...]:
    points: list[VectorPoint] = []
    generation_id = "experiment-generation:day99-controlled-v1"
    for ordinal in range(CORPUS_SIZE):
        cluster = ordinal % 8
        raw = tuple(
            (
                4.0 if dimension == cluster else 0.0
            )
            + math.sin((ordinal + 1) * (dimension + 1) + CORPUS_SEED) * 0.2
            for dimension in range(CORPUS_DIMENSIONS)
        )
        norm = math.sqrt(sum(value * value for value in raw))
        vector = tuple(value / norm for value in raw)
        point_id = f"controlled-point:{ordinal:04d}"
        tenant_id = f"controlled-tenant:{ordinal % 2}"
        points.append(VectorPoint(
            point_id=point_id,
            generation_id=generation_id,
            tenant_id=tenant_id,
            embedding_id=f"controlled-embedding:{ordinal:04d}",
            chunk_id=f"controlled-chunk:{ordinal:04d}",
            vector=vector,
            payload=(("tenant_id", tenant_id),),
        ))
    return tuple(points)


def run_controlled_index_experiment() -> dict[str, object]:
    """Compare exact gold with a deterministic ANN proposal, never a real ANN."""

    points = controlled_corpus()
    queries = tuple(points[index * 2] for index in range(QUERY_COUNT))
    exact_rankings: list[tuple[str, ...]] = []
    proposal_rankings: list[tuple[str, ...]] = []
    recalls: list[float] = []
    overlaps: list[float] = []
    for ordinal, query in enumerate(queries):
        exact = ExactFlatReference.search(
            points=points,
            query_vector=query.vector,
            tenant_id=query.tenant_id,
            top_k=K + 1,
        )
        gold_ids = tuple(hit.point_id for hit in exact[:K])
        if ordinal % 2 == 0:
            proposal_ids = gold_ids
        else:
            proposal_ids = gold_ids[:-1] + (exact[K].point_id,)
        exact_rankings.append(gold_ids)
        proposal_rankings.append(proposal_ids)
        recalls.append(recall_at_k(gold_ids, proposal_ids))
        overlaps.append(rank_overlap(gold_ids, proposal_ids))
    corpus_checksum = stable_hash(tuple(
        (
            point.point_id,
            point.tenant_id,
            canonical_float32_vector(point.vector),
        )
        for point in points
    ))
    exact_checksum = stable_hash(tuple(exact_rankings))
    proposal_checksum = stable_hash(tuple(proposal_rankings))
    return {
        "experiment_kind": "INDEX_CORRECTNESS_EXPERIMENT",
        "corpus_version": CORPUS_VERSION,
        "seed": CORPUS_SEED,
        "corpus_size": CORPUS_SIZE,
        "dimensions": CORPUS_DIMENSIONS,
        "tenant_partitions": 2,
        "query_count": QUERY_COUNT,
        "k": K,
        "metric": "COSINE_SIMILARITY_OVER_UNIT_L2",
        "exact_method": "DEPENDENCY_FREE_FLAT",
        "approximate_method": "DETERMINISTIC_FAKE_PROPOSAL",
        "approximate_method_is_real_ann": False,
        "corpus_checksum": corpus_checksum,
        "exact_top_k_checksum": exact_checksum,
        "proposal_top_k_checksum": proposal_checksum,
        "mean_recall_at_k": round(sum(recalls) / len(recalls), 12),
        "minimum_recall_at_k": min(recalls),
        "mean_rank_overlap": round(sum(overlaps) / len(overlaps), 12),
        "exact_distance_evaluations": CORPUS_SIZE * QUERY_COUNT // 2,
        "measured_wall_clock": "NOT_REPORTED_AS_BENCHMARK",
        "real_ann_runtime": "NOT_RUN",
        "real_database_runtime": "NOT_RUN",
        "evidence_level": "EXECUTED_LOCAL_RUNTIME_PLUS_SIMULATED",
        "raw_vectors_in_report": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }
