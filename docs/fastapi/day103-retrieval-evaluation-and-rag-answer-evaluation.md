# Day103 — Retrieval Evaluation and RAG Answer Evaluation

## 1. Lesson Metadata

- **Status:** Completed at guided classroom scope
- **Template:** `LESSON_TEMPLATE_v2`
- **Phase:** 7C — Production RAG Engineering
- **Difficulty:** Advanced
- **Estimated study time:** 6–8 hours
- **Prerequisites:** Day95–Day102, especially occurrence identity, authorization, reranking and Claim/Citation release
- **Previous lesson:** [Day102 — Grounding, Citations and Source Verification](day102-grounding-citations-and-source-verification.md)
- **Next lesson:** Day104 — Index Updates, Deletes, Rebuilds and Migrations
- **Main artifact:** versioned evaluation dataset, independent labels, deterministic RAG evaluators, slice/hard-gate decision policy and replayable report
- **Evidence:** `EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`
- **Production readiness:** `MORE_EVIDENCE_NEEDED`

## 2. Learning Objectives

By the end of Day103, the learner can:

- distinguish online Verification from offline Evaluation;
- explain why Day102 `VerificationResult` is a prediction rather than Ground Truth;
- freeze dataset, source, authorization, label, evaluator and system identities;
- calculate Precision@k, Recall@k, MRR and nDCG@k by hand;
- separate Answer Correctness from Claim Faithfulness;
- separate Citation Precision, Citation Coverage and Request Coverage;
- evaluate correct Abstention, missed Abstention and over-Abstention;
- use slices to expose failures hidden by overall averages;
- keep hard safety gates non-compensable;
- distinguish `PASS`, `FAIL`, `INCONCLUSIVE` and `NOT_RUN`;
- produce a content-safe, replayable Evaluation Report;
- state exactly what deterministic evidence does and does not prove;
- explain the design in concise interview English.

## 3. Why This Matters

A RAG system can pass every unit test and still return the obsolete 30-day policy. It can produce a factually correct “14 days” answer without evidence, cite one Claim perfectly while omitting another request item, or score well overall while failing every multi-facet Query.

Day103 turns “the answer looks good” into a controlled measurement process. It prevents the system from grading its own output, binds comparisons to one frozen ruler, and keeps safety violations visible even when average quality is high.

## 4. Roadmap Position

```text
Day101 ordered current candidates
        |
        v
Day102 released supported Claims and Citations
        |
        v
Day103 independently measures retrieval and answer quality
        |
        v
Day104 changes index state using a frozen quality baseline
```

Day103 reuses Day96 immutable occurrence identity, Day97 authorization/provenance, Day101 ranked candidates and Day102 structured Claim/Citation output. Day104 depends on the Day103 baseline to detect quality regressions during index rebuilds and migrations.

## 5. Lesson Map

```text
Evaluation Dataset Identity
→ Independent Labels and Adjudication
→ System Predictions
→ Retrieval Metrics
→ Answer / Citation / Abstention Metrics
→ Slice Analysis
→ Thresholds and Hard Gates
→ Regression Decision
→ Content-safe Evidence Report
→ Day104 Baseline Handoff
```

## 6. Core Mental Model

```text
Day102 decides what one request may release.

Day103 measures how well the system performs
across an independently labeled evaluation set.
```

The ownership boundary is:

```text
independent label + review + adjudication → Ground Truth
system under evaluation                  → Prediction
evaluator                                → Measurement
release owner                            → Deployment decision
```

The system may produce predictions. It may not declare those predictions to be Ground Truth.

## 7. Main Concepts

### Concept 1 — Independent Ground Truth

#### Tech Lead Question

Why can Day102 `VerificationResult` not become Day103 Ground Truth?

#### Student Thinking

The learner first described the input as reranked candidates, the output as Claims checked by Verification and the Owner as the system pipeline. After a counterexample, the learner recognized that the deeper problem is circular ownership: a verifier that incorrectly marks “30 days” as `SUPPORTED` would appear correct if its own result were also the label.

#### Student Answer

> “需要独立评价、独立审核以及最终裁决。不能将系统的预测当成事实。”

#### Tech Lead Review

Day102 consumes Claims, Evidence and Citations and emits semantic relations. Those relations are system predictions. Day103 labels must be produced independently and bound to source and policy snapshots. Even a currently accurate verifier cannot own its own evaluation labels.

#### Engineering Thinking

Independence makes false positives and false negatives observable. A separately versioned LLM judge may assist, but remains an evaluator prediction until calibrated against human-adjudicated labels.

### Concept 2 — Fixed Dataset and Retrieval Metrics

The complete lesson uses one synthetic refund-policy dataset:

```text
A: current 2026 policy — unopened items, 14-day refund window
B: superseded 2024 policy — 30-day refund window
C: current service manual — submit through online customer service

Q1: refund window                  → {A}
Q2: submission channel             → {C}
Q3: refund window + channel         → {A, C}
```

B is semantically related but policy-ineligible. Text similarity cannot silently turn it into a positive qrel.

```text
Precision@k = relevant results in top k / k
Recall@k    = relevant results in top k / all relevant labels
RR          = 1 / rank of first relevant result
MRR         = mean RR across Queries
DCG@k       = position-discounted relevance gain
nDCG@k      = DCG@k / ideal DCG@k
```

The classroom comparison `[A, B, C]` versus `[A, C, B]` showed why Precision, Recall and RR can remain unchanged while nDCG improves when the second relevant result moves forward.

### Concept 3 — Answer and Citation Axes

```text
Correctness       → does the answer match independent facts?
Faithfulness      → is each Claim supported by the Evidence actually used?
Citation Precision→ do provided Citations support their mapped Claims?
Citation Coverage → do generated evidence-requiring Claims have support?
Request Coverage  → were all requested items supportedly answered or abstained?
```

A “30 days” answer citing B can be faithful to B while incorrect under current Ground Truth. A “14 days” answer citing only C can be correct while unfaithful. One valid Citation can produce Citation Precision `1/1` while Request Coverage remains `1/2` because the submission channel was omitted.

### Concept 4 — Abstention and Semantic States

```text
evidence insufficient + Abstain → correct Abstention
evidence sufficient + Abstain   → over-Abstention
evidence insufficient + answer  → missed Abstention
```

`SUPPORTED`, `UNSUPPORTED` and `CONTRADICTED` are semantic judgments. `UNAVAILABLE` records that the evidence or evaluator could not be legally or operationally obtained; it must not be rewritten as a semantic result.

### Concept 5 — Slices, Gates and Decisions

In the classroom capstone:

```text
Q1 Recall@2 = 1.0
Q2 Recall@2 = 1.0
Q3 Recall@2 = 0.5

Overall Recall@2 ≈ 0.833 → passes 0.8
multi-facet Recall@2 = 0.5 → fails 0.8
Q3 Request Coverage = 0.5 → hard-gate failure
```

The completed evaluation provides sufficient evidence for `FAIL`, not `INCONCLUSIVE`.

```text
PASS         → complete evidence; all gates and thresholds pass
FAIL         → observed gate violation or quality regression
INCONCLUSIVE → an attempted run lacks enough valid evidence
NOT_RUN      → a specific evaluation did not execute
```

## 8. Common Misconceptions

### Verification prediction as label

❌ The system verifier says `SUPPORTED`, so that is Ground Truth.  
✅ The verifier is part of the system under evaluation; labels require independent ownership.

### Evaluator as repair pipeline

❌ The evaluator should discard B and keep A before scoring.  
✅ The evaluator preserves the original Prediction and measures the error.

### Correctness and Faithfulness

❌ A wrong Citation makes the answer factually incorrect.  
✅ Correctness compares with Ground Truth; Faithfulness compares with actual Evidence.

### Citation Precision and Coverage

❌ One valid Citation across two Claims gives Precision `1/2`.  
✅ Precision is `1/1`; Citation or Request Coverage exposes the missing support.

### Incomplete answer versus incomplete evaluation

❌ A fully measured incomplete answer produces `INCONCLUSIVE`.  
✅ A measured threshold or gate violation produces `FAIL`; evaluator failure produces `INCONCLUSIVE`.

## 9. Engineering Trade-offs

### Exact deterministic labels versus semantic judges

Exact labels are reproducible and ideal for testing mechanics, but cannot capture paraphrase quality at production scale. LLM judges cover broader semantics but introduce model, prompt, schema, cost, latency and calibration dependencies. Day103 keeps the judge behind a versioned evaluator boundary and does not claim one was run.

### Macro averages versus slices

One average is compact but hides group failures. Slices improve diagnosis and governance, but small slices are noisy. Each critical slice therefore binds a definition, minimum sample size and threshold.

### Hard gates versus quality thresholds

Thresholds allow bounded quality trade-offs. Hard gates protect non-compensable boundaries such as unauthorized or superseded-source release. Turning every metric into a hard gate makes iteration brittle; treating safety as an average makes release unsafe.

## 10. Hands-on Exercises

### Exercise 1 — Calculate retrieval metrics

**Question:** For Q3 Ground Truth `{A, C}` and ranking `[A, B, C]`, compute Precision@2, Recall@2, RR and nDCG@3.

**Expected output:** `0.5`, `0.5`, `1.0`, approximately `0.920`.

### Exercise 2 — Separate answer axes

**Question:** Evaluate “30 days through online customer service,” citing B and C.

**Expected output:** the refund Claim is faithful but incorrect; the channel Claim is correct and faithful; B also violates current-source eligibility.

### Exercise 3 — Make a regression decision

**Question:** Overall metrics pass, multi-facet Recall is `0.5`, and Q3 Request Coverage is `0.5` with complete evaluator output.

**Expected output:** `FAIL`, because observed failures are not missing evidence.

Run the artifact:

```sh
PYTHONPATH=src:. python3.12 -m unittest discover -s tests -p 'test_day103_*.py' -q
PYTHONPATH=src:. python3.12 evals/run_day103_seed_eval.py
PYTHONPATH=src:. python3.12 evals/run_day103_evidence_replay.py
PYTHONPATH=src:. python3.12 examples/day103_rag_evaluation.py
```

## 11. Relevant Framework Connections

The Day103 core is framework-independent pure Python. A FastAPI endpoint may start or read an Evaluation Run, but HTTP handlers must not own labels, metric formulas or release policy. A durable worker may execute expensive judges, while immutable run identities and idempotent report persistence remain application contracts.

## 12. AI Backend Connections

The subsystem supports retrieval regression tests, prompt/model comparisons, index migration baselines and offline release reviews. Protected Queries and Evidence may require an internal evaluator identity and egress denial. Evaluation caches must bind dataset, labels, source/authorization snapshots, system, evaluator, metrics, slices and thresholds.

The deterministic fixture proves formulas, correlation and failure handling. Real retriever relevance, model correctness, Claim faithfulness, judge accuracy, latency, capacity, cost and production behavior remain `NOT_RUN`.

## 13. English Interview

### Beginner

**Question:** Why can’t a system’s own verification result be used as Ground Truth?

**Strong answer:** A verification result is a prediction produced by the system under evaluation. Ground Truth must come from an independent labeling, review and adjudication process; otherwise the system grades its own output and can hide errors.

### Intermediate

**Question:** How do you evaluate correctness, faithfulness and Citation Coverage separately?

**Strong answer:** Correctness compares the answer with independent Ground Truth. Faithfulness checks whether Claims are supported by the Evidence actually used. Citation Coverage measures how many evidence-requiring Claims have sufficient Citations.

### Senior

**Question:** How do you stop averages from hiding safety failures or slice regressions?

**Strong answer:** Keep hard safety gates separate from average quality metrics, report critical slices with independent thresholds and minimum sample sizes, and return `INCONCLUSIVE` when slice evidence is insufficient.

## 14. Mental Model Summary

```text
Prediction ≠ Ground Truth
Metric ≠ Threshold
Threshold ≠ Hard Gate
Evaluation Decision ≠ Deployment Authority

Correctness  → independent fact
Faithfulness → actual Evidence
Precision    → returned-result quality
Recall       → relevant-result coverage
MRR          → first relevant rank
nDCG         → position-discounted ranked relevance
```

## 15. Today's Takeaway

The durable engineering rule is controlled independence: freeze the dataset and measurement ruler, vary the system, preserve its unmodified Predictions, measure each quality axis separately, and never allow averages or evaluator failures to erase hard boundaries.

## 16. Before Next Lesson Checklist

- [ ] I can explain why Verification is not Ground Truth.
- [ ] I can calculate Precision, Recall, MRR and nDCG by hand.
- [ ] I can distinguish Correctness, Faithfulness and all three coverage axes.
- [ ] I can classify correct and over-Abstention.
- [ ] I can explain why B remains a negative qrel.
- [ ] I can distinguish `FAIL`, `INCONCLUSIVE` and `NOT_RUN`.
- [ ] I can name the identities that make two runs comparable.
- [ ] I can explain why hard gates are non-compensable.
- [ ] I can state the deterministic evidence boundary in English.
- [ ] I can use the Day103 report as an honest Day104 baseline handoff.
