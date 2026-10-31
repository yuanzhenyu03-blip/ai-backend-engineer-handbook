# Day99 to Day100 Handoff

Day100 production retrieval may consume only a committed immutable generation that is also the current
application-selected bundle and has every required evidence gate at `PASS`. The Outbox event is a wake-up hint,
not authority; Day100 must reread the application database.

The handoff includes generation and EmbeddingSet identities, VectorIndexContract fingerprint, dimensions,
numeric type, normalization, metric, Provider/build identity, point/payload schema versions, manifest digests,
checkpoint and explicit evidence states.

The saved classroom generation is `SEALED` but not selected: real Provider, ANN, capacity and recovery gates are
`NOT_RUN`, so activation correctly returns `NOT_READY`. Day100 may use its metadata for contract design and
negative tests, but must not execute production retrieval against it or invent a current pointer.

The handoff does not authorize retrieval. Day100 must create a versioned query
encoder and Retrieval/Fusion Policy, derive tenant/filter scope from current server-side authorization, run
lexical and dense retrieval behind application Adapters, and recheck every candidate before return.

Day100 must not:

- interpret Provider-private scores directly;
- call the Day99 fake evidence a real Provider or ANN pass;
- use namespace/filter as the sole authorization control;
- mutate a sealed generation;
- consume an inactive/orphan or merely sealed generation as current;
- create a selected pointer from a delayed or missing Outbox event;
- allow a missing hard gate to become `PASS` through weighted scoring.

Still `NOT_RUN`: real vector database/ANN, BM25 engine, hybrid fusion, production authorization/filter behavior,
capacity/latency, durable relay/recovery and production traffic. Readiness remains `MORE_EVIDENCE_NEEDED`.

```text
Day100 may build hybrid retrieval and filtering only on a committed,
current, homogeneous VectorIndexGeneration. It may not weaken Day97
authorization, reinterpret Day98 vector semantics, mix generations,
or treat database filters as the sole authorization authority.
```
