# Day94 to Day95 Handoff

Day95 begins Production RAG work only after preserving the Agent + MCP authority and
recovery boundaries proven in Day94.

## Stable inputs for Day95

- application-owned Agent proposal DTO behind replaceable Framework Adapters;
- stable operation/idempotency/tenant/resource/Tool identity;
- separate human approval and current authorization decisions;
- exact tenant/resource/Tool permits and generation-scoped capability checks;
- atomic dispatch marker before transport handoff;
- candidate-only MCP handlers and controlled Tool boundary;
- correlation → protocol validation → output validation → transition proposal;
- sole application-owned Committer with state/version/fence/attempt checks;
- pending reconciliation for possibly executed outcomes;
- read-only authoritative recovery and retry only after committed non-execution;
- credential-safe logs, bounded metrics and non-authoritative traces;
- verified Agent observation only after durable transition.

## Day95 may add

- document and source identity for ingestion;
- chunk lineage and immutable content/version references;
- controlled embedding and indexing proposals;
- retrieval candidates with tenant and authorization binding;
- evidence/citation DTOs that remain separate from durable source truth;
- deterministic Production RAG acceptance scenarios.

## Day95 must not weaken

- model output is never authorization or durable truth;
- retrieval relevance cannot override tenant isolation or current authorization;
- Framework or vector-database identifiers cannot replace application identity;
- ingestion/retrieval retries cannot create a new logical operation to bypass
  duplicate or conflict rules;
- timeout cannot be interpreted as non-execution;
- unknown indexing or Tool effects require reconciliation, not replay;
- retrieval results and generated answers are candidates requiring validation;
- telemetry cannot become source-of-truth or authorization evidence;
- only the Committer may establish durable application transitions.

## Suggested first Day95 question

An ingestion worker times out after sending `report-42` to an embedding/indexing
service. After restart the index query returns `NOT_FOUND`, but the index is
eventually consistent. Which identity must remain stable, what may be queried, and
why is a new ingestion attempt not yet safe?

## Evidence boundary carried forward

Day94 reached `RESTART_RECOVERY_RUNTIME` with a real MCP SDK, independent loopback
Streamable HTTP process and controlled restart. It did not execute production OAuth,
production remote MCP, distributed durable storage, production telemetry, load/soak
testing or real customer RAG data. Production readiness therefore remains
`MORE_EVIDENCE_NEEDED`.
