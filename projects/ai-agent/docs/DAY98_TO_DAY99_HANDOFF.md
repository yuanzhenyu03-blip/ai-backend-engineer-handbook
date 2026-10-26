# Day98 to Day99 Handoff

Day99 may consume only a committed, currently selected, homogeneous `EmbeddingSet` created by the sole Day98
Committer. An Outbox event is a wake-up hint; Day99 rereads the current pointer and immutable set.

The handoff includes:

- tenant/document/version/ChunkSet/EmbeddingSet identities;
- ordered immutable EmbeddingRecord identities and protected vector storage references;
- exact Chunk IDs, content hashes and source-span provenance;
- complete EmbeddingContract fingerprint and model/tokenizer immutable revisions;
- dimensions, numeric type, normalization and input-role/preprocessing versions;
- current selection revision and content-safe Outbox event identity.

The handoff does not authorize retrieval. Day99 must preserve tenant isolation and protection labels. Later
query/retrieval paths must obtain their own exact current authorization and must not treat vector-store filters
as the source of truth.

Day99 must reject mixed contract fingerprints, dimensions, numeric types, normalization policies or model
revisions in one index generation. A new Day98 set creates a new versioned index build; it does not mutate the
old set or silently overwrite its index. ACL-only changes normally update query authorization/filter material,
not embeddings, because the content/vector-space contract did not change.

Still `NOT_RUN`: vector database selection, ANN index, capacity/recall/latency experiments, durable dispatcher,
deletion propagation, real model output, local retrieval quality and production traffic. Readiness remains
`MORE_EVIDENCE_NEEDED`.
