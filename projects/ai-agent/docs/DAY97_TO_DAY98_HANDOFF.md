# Day97 → Day98 Authorized Embedding-Input Handoff

Day98 may begin embedding work only after Day97 produces a verified `AuthorizedEmbeddingInput` under the exact
action `chunk:read_for_embedding`.

## Required input

- verified service `AuthenticatedPrincipal`;
- current tenant membership and exact embedding grant;
- current Day95 ACTIVE DocumentVersion and immutable ParsedArtifact;
- current Day96 committed selected ChunkSet and exact Chunks;
- complete SourceArtifact → ParsedArtifact → ChunkSet → Chunk → source-segment provenance;
- signed, unexpired, one-time permit bound to subject, tenant, action, audience and purpose;
- policy, ACL, membership, role and action-catalog revisions plus `authorization_epoch`;
- selected-pointer revision and document state version/fence;
- authorization decision ID and content-safe audit evidence;
- protected-data classification.

## Rejection conditions

Day98 must reject missing/expired/replayed/tampered permits, ordinary `chunk.text.read`, same-tenant-only claims,
stale epoch/revision/pointer/fence, disabled principals, incomplete provenance, unselected or historical sets,
untrusted metadata authority and authorization-state outage.

## Day98 ownership

Day98 may select and version an embedding model and its preprocessing/batching contract. It may not weaken
Day97 authorization, reinterpret raw credentials or PAP tables, lose provenance, broaden Chunk scope, or treat
vectors as public merely because they are not plain text.

The in-process handoff proves application control flow only. Production identity/policy/key systems, durable
stores, distributed revocation, telemetry and load/recovery remain `MORE_EVIDENCE_NEEDED`.
