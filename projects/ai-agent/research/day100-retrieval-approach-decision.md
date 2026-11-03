# Day100 retrieval approach decision

## Decision

Use an application-owned, dependency-free BM25 + Exact/Flat + RRF path as the
Day100 correctness oracle. Retain PostgreSQL FTS + pgvector as the provisional
real-engine candidate, with Qdrant and Pinecone retained until real hard gates
are executed.

No production engine has won. Official documentation is `OFFICIAL_STATIC`, not
runtime evidence, and every real-engine authorization, ANN, capacity and
recovery gate remains `NOT_RUN`.

## Frozen selection order

1. Apply authorization, tenant isolation, contract, filter, score-semantics,
   durability and recovery hard gates.
2. Exclude `FAIL`, `NOT_RUN`, `UNKNOWN` and stale candidates from weighted
   ranking.
3. Rank only eligible candidates with the frozen 30/20/15/10/10/5/5/5
   weighting recorded in `day100-retrieval-approach-matrix.json`.
4. Let application authority commit the selected retrieval bundle. A Provider
   alias, Outbox event or client generation hint cannot make that selection.

## Classroom evidence

The controlled fixture is explicitly `DAY100_CLASSROOM_ONLY`, uses a
deterministic fake query encoder and process-local stores, and has
`production_eligible=false`. It proves pipeline mechanics, not production
quality, capacity, latency or recovery.
