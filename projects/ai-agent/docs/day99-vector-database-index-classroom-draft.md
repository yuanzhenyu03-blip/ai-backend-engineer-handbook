# Day99 Classroom Record

## Learner synthesis

The learner correctly separated application score semantics from Provider operators; physical build parameters
from query policy revisions; authorization from filters; immutable generations from in-place rebuilds; ACK from
readback; and current authority from cached or aliased state.

The extended guided review covered Exact/Flat versus ANN, HNSW/IVFFlat parameters, shadow builds, quantization,
hard gates, canary capacity bounds, CAS activation, Outbox/Inbox, fencing, reconciliation, deletion/recovery,
hybrid and reranker boundaries, cache/cursor validity and evidence provenance.

## Important correction pattern

The main remaining judgment skill is distinguishing absolute rejection from a safely restricted action. A
bounded canary, scoped tenant rollout, candidate reuse, lexical fallback, partial recovery or restricted serving
can be valid only after the scope is explicit, authority is current, hard caps are enforced and evidence labels
remain honest.

## Implementation decision

Day99 stops the long question sequence and implements the smallest honest checkpoint:

- exact float32/unit-L2/cosine reference first;
- deterministic fake Provider only;
- official static comparison of pgvector, Qdrant and Pinecone with hard gates before weights;
- narrow `embedding_set:read_for_indexing` authorization with a second precommit check;
- deterministic tenant-only batches and exact ACK correlation;
- immutable shadow generation and canonical manifest;
- Provider distance translated to application similarity;
- readback and exact parity gates;
- stable operation, fresh attempt and Committer-issued fence;
- timeout reconciliation rather than blind retry;
- hard-gate refusal of production activation.
- a 256-vector controlled Exact/Flat corpus and explicitly simulated ANN proposal for recall@k arithmetic.

## Evidence statement

The classroom checkpoint combines `OFFICIAL_STATIC`, `DETERMINISTIC_FAKE`, `SIMULATED` and
`EXECUTED_LOCAL_RUNTIME`. Real vector Provider and real ANN execution, capacity/latency, distributed durability,
backup/restore, deletion propagation and production traffic are `NOT_RUN`. Production readiness is
`MORE_EVIDENCE_NEEDED`.
