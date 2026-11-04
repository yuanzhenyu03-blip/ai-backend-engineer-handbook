# Day101 Query Rewriting and Re-ranking — Engineering Design

## Authority boundary

```text
rewrite authority != authorization authority
ranking authority != content-release authority
```

Day101 accepts only the exact current Day100 selected bundle. Every approved variant calls `AuthorizedHybridRetriever.retrieve()` with the original tenant, principal, action, purpose and filter. Direct lexical, dense or ANN access is forbidden.

## Pipeline

```text
Day100 handoff eligibility
→ OriginalQueryContract with tenant-keyed digest
→ bounded deterministic rewrite reference
→ QueryVariant validation and stable identity
→ Day100 retrieval per variant
→ occurrence union + cross-variant RRF
→ pre-rerank currentness check
→ versioned protected input windows
→ deterministic pointwise reranker Adapter
→ explicit-index correlation Validator
→ reorder/subselect only
→ post-rerank currentness check
→ Day102 handoff
```

## Application-owned modules

- `rag_query_rewrite_contracts.py` — original query, rewrite contract, variant and mode identities.
- `rag_query_rewriter.py` — bounded fake Provider, semantic-scope oracle and validation.
- `rag_multi_query_retrieval.py` — repeated Day100 boundary with fixed authority fields.
- `rag_multi_query_fusion.py` — occurrence deduplication plus rank-based cross-variant RRF.
- `rag_reranker_contracts.py` — model/window/score/output/correlation/degradation contracts.
- `rag_reranker_adapter.py` — versioned input windows and deterministic pointwise fake.
- `rag_reranking_validator.py` — exact response correlation and fail-closed validation.
- `rag_reranking_orchestrator.py` — eligibility, egress, fallback and two currentness checks.
- `rag_reranking_cache.py` — rewrite/pool/reranker-bound cache and signed cursor identities.
- `rag_reranking_experiments.py` — replayable, content-safe pipeline-correctness report.

## Invariants

1. Original query is variant zero and is never overwritten.
2. Provider output is a candidate, never authority.
3. Query variants cannot carry tenant/filter/purpose fields.
4. Every variant uses the same Day100 boundary.
5. Candidate union deduplicates by complete occurrence identity, not content.
6. Raw scores from different retrieval queries are not summed.
7. Reranker inputs bind explicit candidate IDs and versioned windows.
8. Reranker output IDs are a subset of input IDs.
9. Any unknown, duplicate, out-of-range or contract-mismatched output invalidates the result.
10. Current authorization/provenance is checked before egress and before final release.
11. Score and top-k never override release authority.
12. Cursor/cache identity binds the full rewrite, pool, model and window state.

## Controlled degradation

```text
rewrite unavailable + allowed policy
→ ORIGINAL_ONLY_FALLBACK

reranker unavailable/invalid + allowed policy
→ discard entire reranker output
→ UNRERANKED_FALLBACK
```

Fallback state is part of the response and audit identity. It is not full rewritten/reranked success.

## Run

```sh
cd projects/ai-agent
PYTHONPATH=src:. python3.12 -m unittest discover -s tests -p 'test_day101_*.py' -q
PYTHONPATH=src:. python3.12 evals/run_day101_seed_eval.py
PYTHONPATH=src:. python3.12 evals/run_day101_evidence_replay.py
PYTHONPATH=src:. python3.12 examples/day101_query_rewriting_reranking.py
```

## Evidence limit

The local reference uses deterministic fake rewrite and reranking. It proves application control flow, identity, authorization, correlation, fallback and replay behavior only. Real selected Day100 production candidates, local model weights, hosted Provider calls, protected data egress, quality, latency, capacity and cost are `NOT_RUN`. Production readiness remains `MORE_EVIDENCE_NEEDED`.
