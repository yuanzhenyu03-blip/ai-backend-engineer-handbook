# Day101 Reranker Approach Decision

Status: `PROVISIONAL_EVIDENCE_BOUNDED`

## Decision

Use an application-owned deterministic pointwise fake for Day101 pipeline-correctness evidence. Keep `BAAI/bge-reranker-v2-m3`, Cohere Rerank, and Jina as research candidates only. Do not select a production reranker until real Day100 production candidates, protected-data approval, controlled quality, latency, capacity, failure and cost evidence exist.

## Why

- Day100 has no real selected production retrieval bundle.
- No real local cross-encoder weights were executed.
- No hosted reranker call or protected candidate egress was approved or run.
- A deterministic fake can prove correlation, subset, stable-order, failure and authorization invariants without fabricating model quality.

## Mandatory adapter boundary

```text
application candidate ID
<-> frozen provider input index
<-> validated provider response index
```

Missing, duplicate, out-of-range and unknown outputs invalidate the complete reranker result. The application may use an explicitly configured unreranked fallback; it must never silently repair a malformed result and call it reranked success.

## Evidence boundary

This decision is `OFFICIAL_STATIC + EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`. It is not `CONTROLLED_MODEL_RUNTIME`, `CONTROLLED_PROVIDER_RUNTIME`, or `PRODUCTION` evidence. Day103 owns systematic retrieval and answer quality evaluation.
