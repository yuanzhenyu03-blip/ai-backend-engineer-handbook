# Day99 Vector Store Selection Decision

Date: 2026-10-31

Decision state: `PROVISIONAL_SELECTED`, `EVIDENCE_BOUNDED`.

The requirements and weights were frozen before scoring. Hard gates cover vector-contract compatibility,
homogeneous EmbeddingSets, application-owned identity, tenant isolation, protected-vector egress, versioned
generations, exact manifest validation, repairable shadow cutover, unknown-outcome reconciliation,
generation-safe mutation, API/schema compatibility, recovery facts, filter boundaries, license constraints and
an Adapter that prevents private database types from entering application core.

The frozen weighted criteria are security and tenant isolation 25%, correctness and versionability 20%,
durability and recovery 15%, measured local index behavior 15%, filtering and Day100 fit 10%, cost 10%, and
operability/developer experience 5%. The weights total 100%. A `FAIL` or `UNKNOWN` hard gate prevents a
candidate from entering weighted ranking; a high preference score cannot repair missing authority or recovery
evidence.

`PostgreSQL + pgvector 0.8.7` is the provisional classroom approach. It fits the existing application-owned
transactional control plane and lets the course start with Exact/Flat as the correctness oracle. Its measured
local behavior score is deliberately zero because no PostgreSQL/pgvector server, HNSW index or IVFFlat index
was run. This selection does not establish production capacity, ANN recall, backup/restore, replication or
operational readiness.

Qdrant 1.20.0 remains retained with `UNKNOWN` gates for cross-system application-pointer/alias cutover and the
unexecuted distributed recovery path. Pinecone remains retained with `UNKNOWN` gates for protected-vector
egress, cross-system cutover and a stable backup/restore contract; no paid API was called. Namespace and filter
features are never treated as current application authorization.

The executable implementation continues to use an application-owned deterministic fake. Official product
documentation is `OFFICIAL_STATIC`; the fake is `DETERMINISTIC_FAKE`; the dependency-free Exact/Flat corpus is
`EXECUTED_LOCAL_RUNTIME`; real database execution is `NOT_RUN`. Production readiness remains
`MORE_EVIDENCE_NEEDED`.
