# Day103 Application Design — Retrieval and RAG Answer Evaluation

## Scope

Day103 evaluates structured Day101/Day102 Predictions against an independently owned, versioned refund-policy dataset. It implements deterministic evaluation mechanics and produces content-safe evidence. It does not integrate a production retriever, generator, human-label platform or LLM judge.

## Architecture

```text
EvaluationDatasetIdentity
  + Q1/Q2/Q3
  + independent qrels
  + request-item labels
  + Citation-support labels
            |
            v
EvaluationValidator
            |
SystemQueryPrediction ──> RetrievalEvaluator
                    ├──> AnswerEvaluator
                    `──> CitationEvaluator
                              |
                              v
                    EvaluationOrchestrator
                    ├── aggregate metrics
                    ├── evaluate slices
                    ├── enforce hard gates
                    ├── classify failures
                    `── emit safe report
                              |
                              v
                    Day104BaselineHandoff
```

## Identity boundary

Every run binds:

- dataset version and Query-set digest;
- source and authorization-policy snapshots;
- labeling policy and adjudication revisions;
- system-under-test identity and Day101/Day102 contract fingerprints;
- evaluator and metric revisions;
- slice and threshold policy revisions.

Baseline and Candidate reports are comparable only when dataset, evaluator and policy fingerprints match. System and Prediction identities are expected to differ.

## Independent labels

Day102 `VerificationResult` is retained as Prediction evidence but is never read as Ground Truth. Day103 owns separate:

- `RelevanceJudgment` qrels;
- `RequestItemLabel` correctness/Abstention labels;
- `CitationSupportLabel` Claim/Evidence relations.

B may independently support the historical “30 days” Claim while remaining policy-ineligible and relevance grade zero for current-policy Questions. This separation allows a response to be faithful to an old source and still be incorrect and release-ineligible.

## Metric implementation

`RetrievalEvaluator` computes binary/graded Precision@k, Recall@k, reciprocal rank, DCG and nDCG. `AnswerEvaluator` computes independent exact-label Correctness, Evidence-based Faithfulness, Request Coverage and Abstention counts. `CitationEvaluator` computes Citation Precision, Citation Coverage, unknown Citation count and superseded-source release count.

All metric functions are deterministic pure functions over correlated contracts. They do not repair Predictions.

## Decision semantics

```text
observed hard-gate violation → FAIL
observed threshold failure  → FAIL
evaluator failure           → INCONCLUSIVE
missing critical result     → INCONCLUSIVE
all complete and passing    → PASS
```

An observed hard-gate violation remains `FAIL` even if another evaluator times out. A timeout is stored as an observed evaluator failure; it is not converted to a score of zero or a semantic judgment.

## Content safety

Reports store Query IDs, digests, aggregate metrics, counts, slices, failure categories and checksums. They do not store raw Queries, protected Claims, full Evidence or Provider payloads. Protected values remain `repr=False` inside immutable contracts.

## Evidence boundary

The saved report uses `EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`. It proves dataset identity, formula implementation, correlation, slice/gate behavior, timeout semantics, report replay and content-safe output. Real model and production quality remain `NOT_RUN`; production readiness remains `MORE_EVIDENCE_NEEDED`.

## Files

- `src/rag_evaluation_contracts.py`
- `src/rag_evaluation_dataset.py`
- `src/rag_retrieval_evaluator.py`
- `src/rag_answer_evaluator.py`
- `src/rag_citation_evaluator.py`
- `src/rag_evaluation_validator.py`
- `src/rag_evaluation_orchestrator.py`
- `src/rag_evaluation_experiments.py`
- `examples/day103_rag_evaluation.py`
- `evals/day103_rag_evaluation_seed.jsonl`
- `evals/run_day103_seed_eval.py`
- `evals/run_day103_evidence_replay.py`
- `evidence/day103-rag-evaluation-report.json`
