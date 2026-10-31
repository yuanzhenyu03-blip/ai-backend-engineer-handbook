# Day99 Application Design — Vector Database and Index

## Authority model

The application database owns the current Day98 EmbeddingSet selection, immutable Day99 generation registry,
evidence, selected bundle and Outbox. A Provider write/read/query is external execution evidence, not authority.

## Components

- `rag_vector_contracts.py`: physical generation, retrieval policy, manifest, evidence and bundle values.
- `rag_vector_store_selection.py`: frozen hard gates, weighted criteria and provisional selection.
- `rag_vector_index_authorization.py`: exact index-build action and pre-dispatch/precommit current-state guard.
- `rag_vector_index_planner.py`: deterministic tenant-scoped batches, IDs, byte limits and plan checksum.
- `rag_vector_adapter.py`: replaceable Provider port, deterministic fake, Exact/Flat oracle and score Adapter.
- `rag_vector_validator.py`: ACK correlation, readback digest, score semantics and Exact/Flat validation.
- `rag_vector_committer.py`: stable identity, DB-generated fence, immutable seal, CAS activation and Outbox.
- `rag_vector_orchestrator.py`: thin EmbeddingSet-to-shadow-generation workflow and reconciliation entry point.
- `rag_vector_index_experiments.py`: replayable 256-vector exact and simulated-ANN correctness experiment.

## State path

```text
Day98 selected EmbeddingSet
  -> exact embedding_set:read_for_indexing authorization
  -> freeze selected VectorIndexContract revision
  -> claim stable build operation / fresh attempt
  -> create tenant+generation+embedding point identities
  -> deterministic tenant-only write batches
  -> correlate every request/batch/point acknowledgement
  -> readback manifest + checkpoint
  -> compare query behavior with Exact/Flat
  -> recheck authorization, provenance, set, contract and fence
  -> seal immutable generation + Outbox
  -> MORE_EVIDENCE_NEEDED
  -> production activation rejected
```

## Failure rules

- Missing, duplicate, unknown, partial, wrong-tenant/namespace/generation/request ACK fails correlation.
- ACK-only, partial write, cross-tenant point, wrong vector or wrong payload fails readback.
- Wrong query order fails Exact/Flat parity.
- Timeout after dispatch becomes `UNKNOWN`; blind retry is blocked.
- Reconciliation reads Provider state and may converge the original operation.
- A late lower fencing token cannot write.
- Changed authorization, lineage, Day98 selection or VectorIndexContract blocks the precommit transaction.
- Exact replay converges; changed content under one stable result identity conflicts.
- Competing operations converge to one stable generation; delayed selection Outbox is classified `STALE`.

## Evidence boundary

This design runs in one process with synthetic vectors and a deterministic fake. The dependency-free exact
corpus verifies recall@k calculation, but its approximate proposal is `SIMULATED`, not real ANN. A synthetic
all-pass state exists only inside one unit test to verify the atomic activation state machine; it is explicitly
labeled `SYNTHETIC_STATE_MACHINE_TEST_ONLY` and never enters saved evidence.

Official static research retains pgvector 0.8.7, Qdrant 1.20.0 and Pinecone API 2025-10. pgvector is only the
provisional classroom approach; no real vector database process was started.

## Production replacement points

Replace the in-memory control plane with PostgreSQL transactions and row/CAS locking. Replace the fake Provider
through `VectorProviderPort`. Add real Exact/Flat fixtures, HNSW/IVFFlat shadow builds, recall and latency tests,
durable Outbox/Inbox relay, deletion ledger, backup/restore and alias reconciliation before production use.
