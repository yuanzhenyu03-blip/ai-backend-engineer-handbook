# Day101 → Day102 Handoff

## Day101 output contract

Day102 may receive only a deterministic ordered tuple of `FinalRerankedHit` values that passed the final current authorization and provenance check.

Each hit carries:

- stable occurrence identity;
- final rank;
- source reference;
- prior fusion rank;
- optional reranker score with contract-bound semantics;
- protected text released only through the currentness boundary.

The handoff also carries:

- original-query identity;
- rewrite-set fingerprint and mode;
- candidate-pool digest;
- reranker contract and validated-result identity;
- fallback/degradation state;
- content-safe release rejection evidence.

## Invariant

```text
Day102 input occurrence IDs
⊆ final current authorized Day101 output IDs
⊆ validated reranker input IDs
⊆ current authorized Day100 occurrence IDs
```

## What Day102 must not infer

- Rank one is not an answer.
- A reranker score is not a truth probability.
- HyDE or other generated rewrite text is not source evidence.
- Candidate presence does not establish claim-to-source alignment.
- `FULL` pipeline behavior does not establish citation faithfulness.

## Day102 responsibilities

Day102 owns bounded context assembly, claim extraction/alignment, citation construction, source verification and answer-release boundaries. It must preserve occurrence identity and current authorization through those stages.

## Current limitation

This handoff is proven only with deterministic synthetic fixtures. Real selected Day100 production candidates, real rewrite/reranker models, protected-data egress, ranking quality and production operations remain `NOT_RUN`; readiness is `MORE_EVIDENCE_NEEDED`.
