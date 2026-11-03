# Day100 — Hybrid retrieval and filtering

This classroom implementation establishes the application-owned boundary from
the Day99 selected vector generation to authorized Day100 candidates.

## Invariants

1. A merely `SEALED` generation is not queryable. Production retrieval needs a
   current application-selected bundle whose hard gates passed.
2. Current authorization defines the retrieval scope before lexical or dense
   work begins. A client filter can narrow but never broaden it.
3. Query encoder identity is versioned separately from document encoding and
   must prove compatibility with the selected EmbeddingSet.
4. BM25 and dense raw scores are not added. Application-owned RRF combines
   branch ranks and applies a deterministic tie-break.
5. Candidate identity is a Chunk occurrence plus lineage, not a content hash.
6. Database hits are proposals. Current authorization and provenance are
   checked again before the guarded reader releases text.
7. Refill, cursor, cache and degradation remain bounded and version-bound.
8. Synthetic evidence cannot upgrade real `NOT_RUN` production gates.

## Implementation map

| Module | Responsibility |
|---|---|
| `rag_retrieval_contracts.py` | Query, lexical, bundle, policy, candidate and response contracts |
| `rag_query_encoder.py` | Query role/prefix, egress and vector validation |
| `rag_lexical_retrieval.py` | Dependency-free BM25 reference |
| `rag_dense_retrieval.py` | Exact cosine reference and dense score semantics |
| `rag_retrieval_filters.py` | Application-owned AST and capability planning |
| `rag_retrieval_validator.py` | Selected authority and candidate identity checks |
| `rag_hybrid_fusion.py` | RRF, occurrence dedup and deterministic tie-break |
| `rag_authorized_retriever.py` | Current scope and guarded content release |
| `rag_retrieval_cache.py` | Signed cursor and derived candidate cache |
| `rag_retrieval_orchestrator.py` | Authorization-first orchestration and bounded degradation |
| `rag_retrieval_experiments.py` | Content-safe controlled evidence |

## Evidence statement

The tests and seed evaluate pipeline correctness with deterministic fake and
in-process components. PostgreSQL/pgvector, Qdrant, Pinecone, real embedding
providers, ANN, capacity and recovery remain `NOT_RUN`. Production readiness is
`MORE_EVIDENCE_NEEDED`.
