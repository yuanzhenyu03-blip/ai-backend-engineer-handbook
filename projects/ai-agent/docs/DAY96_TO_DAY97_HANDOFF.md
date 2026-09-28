# Day96 → Day97 Handoff (classroom draft)

Day97 may consume only a ChunkSet that was committed from a Day95 eligible
immutable ParsedArtifact. The `selected` pointer is an independent fact.
Readers must match its `document_version_id` against the current Day95 active
version; an old version's selected set remains historical evidence.

## Immutable fields to carry forward

- `tenant_id`, `document_id`, `document_version_id`;
- `source_artifact_id`, `parsed_artifact_id`, ParseManifest/output checksum;
- `chunk_set_id`, full strategy/tokenizer/normalization/config fingerprint;
- each `chunk_id`, ordinal, content checksum, token count, boundary reason;
- each exact canonical ParsedArtifact `source_segment` and context role;
- overlap provenance and experiment/operation binding.

The application must not infer identity or permission from filename, object key,
`chunk_index`, or content hash. Repeated text at different source spans retains
distinct Chunk records. A repeated heading or table header retains its original
source span in every consuming Chunk.

## Mutable facts and authorization

Day97 should read the authoritative selected ChunkSet and current Day95 active
version rather than trusting a stored `active=true` flag on a Chunk. Tenant
equality is necessary but not sufficient for authorization. ACL decisions must
be evaluated for the requesting principal and current policy before protected
content reaches retrieval results or answer generation.

An outbox notification is a wake-up hint, not authority. It carries the
selection revision/fence; delayed or duplicate delivery must not roll current
selection back. A consumer must check the authoritative pointer before doing
current-only work. Delivery can be at least once; downstream durable effects
need stable idempotency keys.

## Deliberately deferred

Day96 does not build the Day97 ACL subsystem, embeddings, an index, retrieval,
citations, or answer evaluation. Current source offsets are relative to Day95
canonical parsed text, not necessarily byte offsets in the uploaded object.
The in-memory Committer proves control flow only, not a distributed transaction.
