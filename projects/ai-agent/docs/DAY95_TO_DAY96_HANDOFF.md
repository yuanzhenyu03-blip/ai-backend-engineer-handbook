# Day95 to Day96 Handoff

## Input Day96 may accept

Day96 chunking may accept only the immutable parsed artifact selected by this full
durable predicate:

```text
Document.state == ACTIVE
AND Document.active_version_pointer == DocumentVersion.document_version_id
AND DocumentVersion.state == ACTIVE
AND DocumentVersion.parsed_artifact_id IS NOT NULL
AND IngestionOperation.state == COMPLETED
```

The handoff includes tenant, document, immutable version, source artifact, parsed
artifact, parse manifest, parser contract, operation, and lineage references. Day96
must not infer authority from filename, object key, content hash, telemetry, or a
parser success response.

## Inputs Day96 must reject

- `REGISTERED`, `QUARANTINED`, `TOMBSTONED`, `SUPERSEDED`, or stale versions;
- a candidate without a Committer activation;
- a version not named by the current active pointer;
- an operation still pending reconciliation;
- an artifact with mismatched tenant/document/version/source bindings.

## Day96 scope

Day96 may design chunk identity, boundary selection, overlap, token budgets, and
chunk provenance. It must not rewrite Day95 document truth or activate a document
version. Re-chunking must remain bound to the same immutable parsed artifact and
document version unless a new Day95 re-ingestion occurs.

## Still not production-ready

The current store is an in-memory deterministic transaction model. Production Day96
work must not assume that distributed database, Object Storage, parser deployment,
authorization, or telemetry guarantees have already been proven.
