# Day100 to Day101 handoff

Day101 may rewrite queries and rerank only candidates produced by the current
authorized Day100 retrieval bundle.

It may not broaden authorization, recover candidates rejected by current access
control, mix stale generations, reinterpret raw database scores, or treat a
reranker as an authority source.

## Day100 owns

- application-selected retrieval-bundle eligibility;
- current authorization-aware retrieval scope;
- exact QueryEncoderContract and LexicalRetrievalContract;
- aligned lexical and dense branch execution;
- filter validation and enforcement;
- version-bound candidate validation;
- RRF, occurrence dedup and deterministic ordering;
- final authorization/provenance recheck;
- guarded protected-content release;
- bounded refill, cursor/cache binding and degradation classification.

## Day101 owns

- query-rewriting contracts;
- multi-query strategy;
- reranking contracts and adapter validation;
- reranker evidence and final candidate reordering before grounding.

## Required handoff identity

Day101 must receive:

- tenant, principal, purpose and current authorization evidence;
- selected bundle revision and fingerprint;
- current DocumentVersion and selected ChunkSet;
- selected homogeneous EmbeddingSet and VectorIndexGeneration;
- aligned lexical corpus generation;
- query encoder, lexical, filter-schema, retrieval-policy and fusion-policy
  fingerprints;
- authorized occurrence identities and complete provenance;
- branch ranks, content-safe scores and deterministic final order;
- explicit `FULL` or `PARTIAL` classification;
- protected-data classification and content-safe audit evidence.

Day101 must reject unauthorized or unvalidated hits, mixed/stale generations,
mixed ChunkSets, incomplete provenance, unknown filter semantics, missing
contract fingerprints, non-deterministic order, raw private Provider responses,
and partial results falsely labeled full.

## Current evidence boundary

The Day100 handoff format is implemented and exercised only with the isolated
synthetic classroom bundle. The saved real Day99 generation remains `SEALED`,
unselected and blocked from production retrieval. Real Provider, real database,
ANN, capacity and recovery evidence remain `NOT_RUN`; readiness remains
`MORE_EVIDENCE_NEEDED`.
