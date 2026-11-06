# Day102 → Day103 Handoff

## Day102 output contract

Day103 may evaluate only structured Day102 responses that preserve:

- original request and request-item identities;
- trusted Day101 handoff and immutable Grounding Bundle digests;
- released and rejected Claim identities/digests;
- Claim-to-Citation mappings;
- source occurrence, version, exact span and evidence digests;
- Verification relations, reasons, verifier and policy identities;
- source currentness rejections;
- answered and abstained request items;
- upstream ranking, generator and verifier execution modes.

## Invariants available to Day103

```text
released Claim IDs
⊆ validated SUPPORTED Claim IDs

released Citation targets
⊆ frozen Grounding Bundle targets

Grounding Bundle occurrence IDs
⊆ final current Day101 handoff IDs
```

## What Day103 must measure independently

- Claim extraction completeness;
- citation precision and coverage;
- Claim faithfulness / entailment;
- contradiction detection;
- request coverage and Abstention quality;
- retrieval and reranking baselines;
- false-positive and false-negative verifier rates;
- latency, capacity, timeout, fallback, cost and error rates.

## Ground-truth rule

Day102 `VerificationResult` values are predictions, not evaluation labels. Day103 needs independently labeled Claim/Evidence pairs, preferably with multiple human annotators and adjudication. A separately calibrated evaluator may assist, but cannot silently become ground truth.

## Current evidence boundary

The Day102 handoff is proven only with deterministic synthetic fixtures. Real generator, Claim extractor, NLI/LLM verifier, protected-data egress, labeled quality set, database/ANN path and production operations remain `NOT_RUN`; readiness is `MORE_EVIDENCE_NEEDED`.
