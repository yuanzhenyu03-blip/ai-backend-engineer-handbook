# Day103 Classroom Record — Retrieval and RAG Answer Evaluation

## Teaching mode

The lesson continued Day102's bridge-mastery pattern. One refund-policy scenario remained fixed while one boundary changed at a time. The learner answered before contracts or formulas were introduced.

## Fixed dataset

```text
A: current policy — 14 days
B: superseded policy — 30 days
C: current manual — online customer service

Q1 → A
Q2 → C
Q3 → A, C
```

## Mental-model evolution

### Stage 1 — Prediction versus Ground Truth

The learner first described `VerificationResult` input as reranked candidates and output as the system verifying Claims. The Owner was correctly identified as the system pipeline. A “30 days marked SUPPORTED” counterexample exposed the missing independence boundary.

Final learner invariant:

> “需要独立评价、独立审核以及最终裁决。不能将系统的预测当成事实。”

The learner then initially treated evaluator output as “keep A and discard B.” The correction established that an evaluator preserves the original Prediction and measures it; repair would inflate quality.

### Stage 2 — Retrieval metrics

The learner correctly calculated:

- Q3 Precision@2 `1/2 = 0.5`;
- Q3 Recall@2 `1/2 = 0.5`;
- three-Query MRR `(0.5 + 1 + 1) / 3 ≈ 0.833`;
- ideal Q3 nDCG `1.0`.

The important progression was from “other Ground Truth is missed” to a precise denominator model. The learner also explained that MRR ignores relevant results after the first and that overall Recall `0.833` hid multi-facet Recall `0.5`.

### Stage 3 — Answer, Citation and Abstention axes

The learner correctly identified a B-backed “30 days” answer as faithful but incorrect. In the reverse case, the learner initially marked a correct “14 days” Claim as incorrect because Citation C did not support it. The correction separated:

```text
Correctness → independent Ground Truth
Faithfulness → Evidence actually used
```

The learner initially used Claim count as the Citation Precision denominator. After correction, the learner derived Citation Precision `1/1` and Citation Coverage `1/2`, then explained why Precision `1.0` could not prove complete support.

For Abstention, the learner correctly classified the result but first explained it as “the user Question has no Claim.” The durable correction was that the request item exists; eligible Evidence availability determines whether answer or Abstention is correct.

### Stage 4 — Regression decisions

The learner established that baseline and Candidate need the same input and measurement ruler while system and output identities differ. Hard gates were correctly treated as non-compensable.

The learner correctly classified evaluator timeout as `INCONCLUSIVE`. During the capstone, the learner initially classified a fully measured slice and Request Coverage failure as `INCONCLUSIVE`; the final correction separated insufficient evidence from sufficient evidence of failure.

### Stage 5 — Evidence honesty and code mapping

The learner mapped contracts, dataset, evaluators, Validator, Orchestrator, report, tests and CI. `MORE_EVIDENCE_NEEDED` was initially named as an evidence level. The final model separated:

```text
Evidence Level       → EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE
Production Readiness → MORE_EVIDENCE_NEEDED
```

## English interview

The learner passed beginner and intermediate questions after terminology corrections. The senior question required direct teaching, then the learner successfully restated hard-gate and slice-regression control in English. Frequent language corrections included `prediction`, `Ground Truth`, `enforce`, `thresholds`, `insufficient` and `inconclusive`.

## Final independent summary

The learner independently reconstructed the complete dataset-to-report pipeline, correctly preserved independent human labeling/review/adjudication, kept Prediction separate from Ground Truth, required both thresholds and hard gates, and stated that deterministic mechanics cannot prove real model quality.

Final assessment: **88/100, passed**. Remaining work is terminology precision: `MRR`, `nDCG`, `Prediction`, metric-layer ownership and all four decision statuses.

## Evidence boundary

The classroom result and implementation use synthetic A/B/C sources and deterministic outputs. Real independent labels, real retriever/generator quality, calibrated LLM judge, protected-data egress and production operations remain `NOT_RUN`.
