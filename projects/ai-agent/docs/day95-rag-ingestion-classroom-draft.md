# Day95 Classroom Draft

## Classroom result

The learner completed the incident-driven identity, lifecycle, recovery, retry,
quarantine, tombstone, and production-evidence discussion. The independent synthesis
result is `PASS_WITH_REQUIRED_BOUNDARY_CORRECTIONS`; the English interview result is
`PASS_WITH_LANGUAGE_CORRECTIONS`.

## Required corrections retained

1. A source artifact is already admitted and verified as received bytes; it is not
   yet parsed or validated knowledge.
2. Re-ingestion preserves tenant and logical document identity but creates a new
   immutable version and normally a new source, operation, and idempotency identity.
3. Reconciliation queries are not parser retries.
4. Safe retry begins only after the Committer persists `PROVEN_NOT_EXECUTED`.
5. Quarantine is a security/validation isolation state; tombstone is a lifecycle
   unavailability fact.
6. Day96 requires the complete active document/version/artifact/completed-operation
   predicate, not only an active pointer.

## Mental model

```text
source artifact = verified reference to received bytes
parsed candidate = untrusted parser proposal
active version = Committer-published application fact
```

```text
timeout after dispatch
→ PENDING_RECONCILIATION
→ bounded authoritative query
├── SUCCEEDED → validate candidate → Committer
├── FAILED → Committer persists failure
├── NOT_EXECUTED → Committer persists fact → independent retry policy
└── NOT_FOUND/UNKNOWN → remain pending → bounded re-query/operator alert
```

## Evidence boundary

The classroom uses synthetic documents, an in-memory lifecycle transaction model,
and a real local child process for the controlled parser. It proves application
control flow and process-boundary behavior, not distributed production durability.
