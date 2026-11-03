"""Content-safe controlled Day100 pipeline-correctness experiments."""

from __future__ import annotations

from dataclasses import asdict

from examples.day100_hybrid_retrieval_filtering import (
    build_day100_fixture,
    load_real_day99_handoff,
    retrieval_request,
)
from rag_chunking_contracts import stable_hash
from rag_retrieval_filters import FilterExpression


def run_controlled_experiment() -> dict[str, object]:
    queries = (
        ("q-refund", "refund policy", None),
        (
            "q-finance",
            "finance handbook",
            FilterExpression.eq("category", "finance"),
        ),
        (
            "q-owner-or-finance",
            "refund",
            FilterExpression.or_(
                FilterExpression.eq("category", "finance"),
                FilterExpression.eq("owner_id", "principal-day100"),
            ),
        ),
    )
    cases: list[dict[str, object]] = []
    for index, (case_id, query, business_filter) in enumerate(queries, start=1):
        fixture = build_day100_fixture()
        response = fixture.retriever.retrieve(retrieval_request(
            fixture,
            query_text=query,
            top_k=3,
            client_filter=business_filter,
            operation_id=f"experiment-operation-{index}",
            request_id=f"experiment-request-{index}",
        ))
        cases.append({
            "case_id": case_id,
            "query_hash": stable_hash(("PROTECTED_QUERY", query)),
            "filter_fingerprint": (
                business_filter.fingerprint if business_filter else None
            ),
            "outcome": response.outcome.value,
            "returned_occurrence_ids": tuple(
                hit.identity.occurrence_id for hit in response.hits
            ),
            "completed_branches": tuple(
                branch.value for branch in response.completed_branches
            ),
            "missing_branches": tuple(
                branch.value for branch in response.missing_branches
            ),
            "provider_calls": response.provider_calls,
            "database_calls": response.database_calls,
            "raw_query_logged": fixture.audit.events()[-1].raw_query_logged,
            "protected_text_logged": (
                fixture.audit.events()[-1].protected_text_logged
            ),
        })
    fixture = build_day100_fixture()
    corpus_manifest = tuple({
        "occurrence_id": record.identity.occurrence_id,
        "content_hash": record.identity.content_hash,
        "provenance_fingerprint": record.identity.provenance_fingerprint,
        "metadata": record.metadata,
    } for record in fixture.records)
    handoff = load_real_day99_handoff()
    report = {
        "experiment_kind": "PIPELINE_CORRECTNESS_EXPERIMENT",
        "evidence_level": "EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE",
        "fixture_scope": fixture.bundle.fixture_scope,
        "fixture_production_eligible": fixture.bundle.production_eligible,
        "corpus_manifest_checksum": stable_hash(corpus_manifest),
        "query_fixture_checksum": stable_hash(tuple(
            (case_id, stable_hash(("PROTECTED_QUERY", query)))
            for case_id, query, _ in queries
        )),
        "bundle_fingerprint": fixture.bundle.fingerprint,
        "query_encoder_contract_fingerprint": (
            fixture.bundle.query_encoder.fingerprint
        ),
        "lexical_contract_fingerprint": fixture.bundle.lexical.fingerprint,
        "filter_schema_fingerprint": fixture.bundle.filter_schema_fingerprint,
        "retrieval_policy_fingerprint": (
            fixture.bundle.retrieval_policy.fingerprint
        ),
        "fusion_policy_fingerprint": fixture.bundle.fusion_policy.fingerprint,
        "cases": cases,
        "real_day99_handoff": handoff,
        "real_provider": "NOT_RUN",
        "real_postgresql_pgvector_fts": "NOT_RUN",
        "real_qdrant_hybrid": "NOT_RUN",
        "real_pinecone_hybrid": "NOT_RUN",
        "real_ann_recall": "NOT_RUN",
        "real_latency_capacity": "NOT_RUN",
        "real_backup_restore_failover": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "raw_queries_in_report": False,
        "protected_text_in_report": False,
        "vectors_in_report": False,
    }
    report["report_checksum"] = stable_hash(report)
    return report
