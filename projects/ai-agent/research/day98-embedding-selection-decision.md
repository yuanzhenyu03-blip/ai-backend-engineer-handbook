# Day98 Embedding Selection Decision

Date: 2026-10-26

Decision state: `PROVISIONAL_SELECTED`, evidence-bounded.

The frozen hard gates are exact model and tokenizer revisions, explicit no-truncation behavior, deterministic
response correlation, approved protected-data handling, tenant isolation, and compatibility with the Day97
authorized/provenance-preserving handoff. Weighted preferences were frozen before comparing candidates:
local retrieval quality 35%, security/governance 25%, reproducibility 15%, reliability/observability 10%, cost
10%, and latency/operability 5%.

`BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181` is the provisional real-model candidate because the artifact
and tokenizer can be pinned to an exact Hugging Face revision and self-hosting can avoid runtime text egress.
The OpenAI and Cohere aliases did not establish immutable model/tokenizer artifact revisions for this contract;
the classroom also has no approval to send protected Chunk text to either hosted service. A high weighted score
cannot compensate for these hard-gate failures.

This is not a production recommendation. No candidate weights or real Provider were installed or called, and
no frozen local corpus retrieval experiment ran. The provisional candidate receives a local-quality score of
zero rather than invented evidence. Production readiness is `MORE_EVIDENCE_NEEDED` until the real runtime,
license/supply-chain checks, capacity, protected-vector controls, and Day103 local retrieval/answer evaluation
are executed.

The executable Day98 workflow therefore uses an application-owned deterministic fake contract. It proves
authorization, preprocessing, batching, response validation, attempt/recovery, immutable versioning, CAS and
Outbox control flow only. It does not impersonate BGE-M3 output or quality.
