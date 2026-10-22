# Day97 Metadata, Tenant, ACL and Provenance — Application Contract

## Authority and reuse

Day97 reuses Day92 `AuthenticatedPrincipal`, Day95 active Document/DocumentVersion/SourceArtifact/
ParsedArtifact facts and Day96 committed selected ChunkSet/Chunk facts. It does not create a second identity,
ingestion, chunking, retry or selected-pointer model.

The application owns resource/action identity, metadata schema, ACL semantics, decision evidence, permit claims
and the protected-text exit. A future policy engine, database, RLS rule or vector filter is an Adapter or
defense-in-depth layer, not a replacement authority.

## Current-input and provenance gate

`CurrentRAGProvenanceValidator` rereads both in-process authorities and requires:

```text
ACTIVE Document head
+ active pointer == immutable DocumentVersion
+ ACTIVE version and completed ingestion
+ exact SourceArtifact ↔ ParsedArtifact checksums/bindings
+ committed selected ChunkSet for that same version
+ valid ChunkSet manifest
+ each Chunk content hash and exact canonical source spans
```

Repeated content hashes remain separate provenance occurrences. Outbox payloads and guessed IDs never enter
the current path without authoritative reread.

## Metadata contract and publication

`MetadataFieldDefinition` binds namespace, name, value type, allowed origins, sensitivity and filterability.
`SOURCE_DECLARED` remains untrusted. Authority-bearing fields are rejected even if syntactically valid.

```text
MetadataProjector → MetadataProjectionCandidate
MetadataCandidateValidator → READY/REJECTED
MetadataCommitter claim → generation/fence
MetadataCommitter persist → immutable snapshot + pointer CAS + Outbox intent
```

Exact duplicate operations converge. Same operation plus changed contract conflicts. A new contract uses a new
operation and creates a new immutable snapshot. ACL changes do not create metadata snapshots, DocumentVersions
or ChunkSets.

## Resource and ACL semantics

The hierarchy is tenant → document → document version → ChunkSet → Chunk. Policy snapshots carry explicit
action catalog, entries, policy/ACL/role/action versions and per-resource authorization epoch.

- default result is `DENY`;
- any applicable explicit `DENY` overrides `ALLOW`;
- same tenant without grant is denied;
- an exact Chunk allow cannot expand missing parent permission unless an explicit application policy enables it;
- a service principal requires the exact service action;
- policy/membership outage is `INDETERMINATE` and maps to `503` externally.

Unauthorized and nonexistent resources share `Resource not found or inaccessible` with external `404`.

## Permit and guarded release

PIP loads facts; PDP decides; PermitIssuer signs only ALLOW; PEP/GuardedChunkReader enforces. Permit claims bind
subject, tenant, audience, purpose, action, immutable resource IDs, exact Chunk IDs, expiry, one-time ID,
policy/ACL/membership/role/action revisions, epoch, selected revision and document state/fence.

PEP verifies signature and every binding, rereads current provenance and authorization state, consumes the
permit once, then returns minimal `AuthorizedChunkView` values. Revocation advances ACL revision and epoch.
Outage, replay, expiry, tampering or stale state releases zero text.

## Authorization cache

`BoundedAuthorizationDecisionCache` stores only bounded decision evidence. Its key includes principal, tenant,
resource, action, audience, purpose, chunks, all authorization revisions, epoch, selected revision and document
state/fence. It never stores a reusable permit and still requires current PIP reads.

## Observability boundary

Content-safe audit contains decision ID, hashed permit/principal identifiers, outcome, reason, action and count.
It excludes credentials, raw text, protected metadata and source URI. High-cardinality request/resource IDs do
not belong in metric labels.

## Evidence boundary

The implementation and tests are deterministic in-process evidence. HMAC proves claim tamper rejection only;
it does not prove production key custody or rotation. In-memory locks do not prove distributed transaction,
multi-process fence, crash recovery or revocation latency. Readiness is `MORE_EVIDENCE_NEEDED`.
