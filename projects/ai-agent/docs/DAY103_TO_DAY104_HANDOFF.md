# Day103 → Day104 Handoff

## Frozen baseline identity

Day104 must bind index update/delete/rebuild/migration experiments to:

- `EvaluationDatasetIdentity` and Query-set digest;
- source and authorization-policy snapshots;
- independent label and adjudication revisions;
- `EvaluatorIdentity` and metric definitions;
- slice and threshold policy;
- baseline `SystemUnderTestIdentity`;
- Day103 Evaluation Report checksum and evidence level.

## Comparison rule

Day104 may compare pre/post-index systems only when dataset, labels, source/authorization snapshots, evaluator, metrics, slices and thresholds are identical. The index/system identity and resulting Predictions are expected to differ.

## Required gates

- no unauthorized, unknown or superseded source release;
- all critical evaluator outputs present;
- overall Retrieval thresholds pass;
- critical slice thresholds pass;
- Request Coverage hard gate passes;
- observed evaluator failures remain visible;
- incomplete evidence produces `INCONCLUSIVE`, never default `PASS`.

## Current evidence boundary

The Day103 handoff is a deterministic classroom baseline with `EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`. It is suitable for testing Day104 comparison mechanics. It is not a production-quality baseline. Real relevance, generation, independent human labels, calibrated judge behavior, latency, capacity, cost and production remain `NOT_RUN`; readiness remains `MORE_EVIDENCE_NEEDED`.

## Day104 scope guard

Day104 owns index update, delete, rebuild, alias/swap and migration lifecycle. It must consume the Day103 baseline but must not silently change Day103 labels, formulas or release policy to make an index migration pass.
