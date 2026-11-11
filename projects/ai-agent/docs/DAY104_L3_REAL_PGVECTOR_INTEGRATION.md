# Day104 L3 — Real PostgreSQL/pgvector Integration Evidence

Date: 2026-11-11

Status: `PASS`

Production readiness: `MORE_EVIDENCE_NEEDED`

## Purpose and claim boundary

This document records the contract and executed evidence that promoted the
Day104 refund-index exercise from deterministic Level 2 mechanics to a
repeatable local Level 3 integration run against real PostgreSQL and pgvector
processes.

The contract and JSON Schema alone do not imply PASS. The saved report now
records a complete local run in which all 17 runner gates passed. This local Level
3 result proves only the recorded PostgreSQL, pgvector, driver, schema and Docker
configuration. It does not prove production readiness.

Executed artifacts:

- [saved L3 integration report](../evidence/day104-l3-integration-report.json);
- [offline saved-evidence replay](../evals/run_day104_l3_evidence_replay.py);
- [real integration runner](../evals/run_day104_l3_integration.py);
- [real integration tests](../tests/test_day104_l3_postgres_integration.py).

Recorded result:

- PostgreSQL `16.15` and pgvector `0.8.7`;
- PostgreSQL adapter unit tests: `32/32 PASS`;
- opt-in real integration tests: `7/7 PASS`;
- runner gates: `17/17 PASS`;
- database-container restart replay: `PASS`;
- saved report checksum:
  `sha256:41e4b36ca1ccd589ca6ddcd99026bc6b48fc57e5a47c231ca8d32433b479ba85`;
- HNSW plan proof: `index_points_embedding_hnsw_cosine_idx` was present in the
  forced-index query plan;
- Python 3.12 pull-request CI: `NOT_RUN`.

## Frozen prerequisite evidence

Day99 made a provisional, evidence-bounded classroom selection:

- evidence: `projects/ai-agent/evidence/day99-vector-store-selection-matrix.json`;
- candidate: `postgresql-pgvector-0.8.7`;
- outcome: `PROVISIONAL_SELECTED`;
- deployment mode: `SELF_HOSTED_POSTGRES`;
- real database execution at selection time: `NOT_RUN`.

The candidate identity includes its pgvector version. The L3 runner must read the
actual extension version from PostgreSQL. A different version cannot silently
inherit the Day99 decision; it requires an explicit new candidate evaluation or an
`INCONCLUSIVE`/`FAIL` result.

Day104 Level 2 remains the executable policy baseline:

- evidence: `projects/ai-agent/evidence/day104-index-lifecycle-report.json`;
- report checksum:
  `sha256:2faf8b4f538de1c5340596eb9b74ec5331fb23ba70a04bbd0fb97569359e7140`;
- evidence level: `EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`.

That checksum is the report's canonical payload checksum, not the raw file-byte
checksum. The L3 report must bind it and must not overwrite or relabel the L2
artifact.

## Fixed scenario and ruler

The real integration run preserves the same classroom corpus and Day103 ruler:

```text
A@v1 — eligible current policy: unopened items may be refunded within 14 days
B@v1 — superseded and Tombstoned historical policy: 30 days
C@v1 — eligible current manual: apply through online customer service

Q1 — refund window       → A@v1
Q2 — application channel → C@v1
Q3 — both facts          → A@v1 + C@v1
```

The initial build identity remains:

```text
BS1 = S1 + P1 + E1 + IS1 + W1 + D1
```

Expected facts must come from a frozen PostgreSQL snapshot. Actual facts must be
produced by a separate read-back path over the persisted pgvector generation.
Counts alone are insufficient: exact occurrence IDs plus content, metadata and
provenance digests are required. Day103 quality evaluation uses the same frozen
dataset, evaluator and policy fingerprints for every candidate being compared.

## Integration architecture

PostgreSQL owns the durable control-plane truth and also hosts pgvector physical
generation rows. These roles still remain logically separate:

- source, authorization and deletion tables own current eligibility facts;
- immutable generation rows are derived serving data;
- the application pointer row chooses the generation for new ReadViews;
- each ReadView pins one pointer revision and one generation for an entire request;
- lifecycle, lease, activation, Inbox and Outbox rows are durable control facts;
- events wake reconcilers, which reread PostgreSQL truth before acting.

pgvector does not require a second Provider alias. The L3 design must not invent an
alias as a competing authority. A generation ID or physical partition selected by
the application pointer is carried through the ReadView and every vector query.
Any cache, materialized lookup or event projection is derived and must be repaired
from the pointer row.

The existing in-memory Committer directly manipulates process-local dictionaries
and locks. It is an executable specification, not a PostgreSQL adapter. L3 must run
the critical transitions as real SQL transactions with database constraints and
conditional updates; swapping only the vector writer would not satisfy this
contract.

## Status and decision rules

The report and each hard gate use exactly one of these states:

- `PASS` — the required assertion ran and emitted bound evidence;
- `FAIL` — the assertion ran and a required invariant was violated;
- `INCONCLUSIVE` — execution occurred but the evidence was unavailable or
  insufficient, including an unclassified timeout;
- `NOT_RUN` — the assertion did not execute.

Overall L3 is `PASS` only when every hard gate is `PASS`. One `FAIL` makes the
overall result `FAIL`. With no failure, any `INCONCLUSIVE` makes the result
`INCONCLUSIVE`; otherwise any `NOT_RUN` keeps it `NOT_RUN`. Skipped tests never
count as PASS.

## Required hard gates

| Hard gate | Required executed evidence |
|---|---|
| `day99_candidate_identity_match` | Read PostgreSQL server and pgvector extension versions; bind the Day99 candidate identity or refuse inheritance. |
| `schema_migration_integrity` | Apply the pinned migration to an empty database, record its digest and prove required PK, FK, unique, check and immutable-identity constraints. |
| `build_snapshot_repeatable_read` | Freeze `S/P/E/IS/W/D` in a real repeatable transaction and prove any later identity change produces a different BuildSnapshot. |
| `physical_generation_immutability` | Bind one generation to one physical namespace; reject namespace reuse, late writes after seal and same-fence content changes. |
| `manifest_exact_readback` | Independently scan the persisted generation and compare count, exact IDs and all content-safe digests; equal-count substitution and B resurrection must fail. |
| `day103_evaluation_hard_gates` | Evaluate Q1/Q2/Q3 with one frozen ruler; thresholds, critical slices and hard gates must all pass. `INCONCLUSIVE` is not releasable. |
| `ready_freshness_guard` | Re-read current `S/P/E/IS/W/D`, authorization metadata revision, provider seal and all evidence before READY; check-then-change must be rejected without partial state. |
| `activation_transaction_atomicity` | Pointer CAS, target ACTIVE, previous DRAINING, ActivationRecord and Outbox commit together or all roll back under injected failures. |
| `concurrent_pointer_cas` | Two independent database sessions compete for the same revision; exactly one successor commits and the loser makes no partial writes. |
| `lease_fencing` | A CAS-rotated higher lease token prevents a delayed worker with the old token from committing. |
| `read_view_single_generation` | An old request remains pinned to its original generation while a new request uses the new generation; one response never mixes generations. |
| `expired_read_view_reaper` | Expire an abandoned leased ReadView with the current fence, decrement its reader count exactly once and reject stale cleanup. |
| `drain_and_retirement` | Durable readers decrement exactly once; expiration is fenced; DRAINING cannot retire before reader zero and the retention boundary. |
| `pointer_projection_authority` | Delayed or duplicate Outbox work rereads the pointer and cannot restore an older revision or generation in any derived lookup. |
| `outbox_inbox_reconciliation` | Commit-before-dispatch, lost ACK, exact replay and same-event/different-digest conflict converge correctly after process restart. |
| `deletion_no_resurrection` | Tombstone, deletion intent and Outbox are atomic; a rebuild from retained source history consumes D1 and exact read-back/search cannot return B. |
| `restart_durability_and_idempotency` | Restart clients/workers and the database container at named checkpoints; committed facts survive and stable operation identities converge to their first result. |

Every PASS gate must reference at least one immutable evidence ID and a content
digest. The runner must retain the exact failure-injection checkpoint and outcome;
an aggregate test count is not enough.

The raw integration runner emits 17 gate results. In the normalized saved report,
`expired_read_view_reaper` is bound into `drain_and_retirement`, so the report has
16 top-level release-gate records while its `day104-l3-runner` test record remains
`17/17 PASS`. The offline replay checks both that consolidation and the reaper
evidence binding.

## Deletion evidence boundary

This local L3 run proved these scopes independently:

- `LOGICAL_RELEASE`: `PASS` — PostgreSQL truth makes B ineligible;
- `SERVING_INDEX_ABSENCE`: `PASS` — exact generation read-back and tested
  retrieval paths do not expose B.

Deletion intent `delete-B-v1` reached `VERIFIED` using only those required
scopes. Exact replay converged to the first result.

`PHYSICAL_PURGE` remains `NOT_RUN`. Removing rows from the tested database cannot
prove erasure from WAL archives, snapshots, backups, replicas, caches or retained
storage. A two-scope local verification policy must not be described as physical
purge.

## Required report bindings

The report contract is
`projects/ai-agent/evidence/day104-l3-evidence-schema.json`. The executed report
is `projects/ai-agent/evidence/day104-l3-integration-report.json`; it includes:

- run ID, UTC start/end timestamps and overall decision;
- Day99 candidate evidence and the exact Day104 L2 report checksum above;
- Docker engine/Compose, image reference/digest, Python and database-driver
  versions;
- PostgreSQL server version, pgvector extension version, transaction isolation and
  migration digest;
- full `S/P/E/IS/W/D/BS` identities and digests;
- physical generation, Manifest, Validation, Evaluation, lease, activation,
  pointer, ReadView, deletion and Inbox/Outbox evidence identities;
- all hard-gate decisions, safe reasons and immutable evidence IDs;
- exact A/B/C and Q1/Q2/Q3 results without raw protected content or raw vectors;
- test-run reports, failure-injection checkpoints and restart evidence;
- an explicit L4 `NOT_RUN` list and cleanup result;
- canonical report checksum and a separate replayed checksum.

The report must set `fixture_production_eligible=false`,
`raw_content_logged=false`, `raw_vectors_logged=false` and
`production_readiness=MORE_EVIDENCE_NEEDED`. Credentials and complete connection
strings are forbidden evidence.

## What the local L3 PASS proves

Subject to the recorded versions and configuration, the completed run proves:

- real PostgreSQL transaction, constraint, row-lock/CAS and restart behavior for
  the tested statements;
- real pgvector storage, filtering and vector-query behavior for the fixed fixture;
- multi-session fencing and pointer competition on one local database;
- application-process restart, at-least-once replay and durable Inbox/Outbox
  convergence;
- exact generation read-back, request pinning and non-resurrection of B on the
  exercised paths.

It does not turn the provisional Day99 selection into a permanent product
choice. It records new evidence for one pinned candidate and workload only.

## Level 4 remains NOT_RUN

The following remain `NOT_RUN` or `MORE_EVIDENCE_NEEDED` after the local L3
PASS:

- PostgreSQL HA, replica failover, restore drills and cross-region recovery;
- multi-node network partitions, split-brain prevention and distributed clocks;
- production IAM, TLS, secret rotation and administrative bypass controls;
- WAL/archive/backup/cache physical erasure and regulatory deletion proof;
- production-size ANN recall, capacity, cost, p95/p99 latency, error rate and soak;
- canary or blue-green production rollout, real traffic, zero-downtime proof;
- incident-response rehearsal and an adequate production observation window.

Python 3.12 pull-request CI also remains `NOT_RUN`. Therefore production
readiness remains `MORE_EVIDENCE_NEEDED` despite the local Level 3 PASS.
