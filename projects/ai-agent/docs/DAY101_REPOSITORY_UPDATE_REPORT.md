# Day101 Repository Update Report

Date: 2026-11-04

## Outcome

Day101 — Query Rewriting and Re-ranking is released at guided classroom scope in the continuing
`projects/ai-agent/` Artifact. Day102 — Grounding, Citations and Source Verification is next.

Production readiness remains `MORE_EVIDENCE_NEEDED`.

## Implementation

The update adds application-owned rewrite identities and budgets, semantic-scope validation, explicit
full/partial/original-only modes, per-variant reuse of the unchanged Day100 authorized retriever,
occurrence-identity union with retained rank evidence, deterministic cross-variant RRF, and bounded candidate
observations.

The reranking layer freezes model/tokenizer/input-window/truncation, score, output-mode, egress and degradation
contracts. An explicit input index maps Provider output back to the exact candidate pool. The Adapter and
Validator reject malformed, duplicated, missing-required, unknown, wrong-attempt, wrong-pool and wrong-contract
responses. The reranker can reorder or select only from that pool.

Current authorization and provenance are rechecked before protected reranker egress and before final guarded
release. Cache and signed cursor identities bind the authority, bundle, original query, approved rewrite set,
multi-query plan, candidate pool, reranker contract and input windows.

## Course artifacts

- Formal lesson: `docs/fastapi/day101-query-rewriting-and-re-ranking.md`
- Design: `projects/ai-agent/docs/DAY101_QUERY_REWRITING_RERANKING.md`
- Classroom record: `projects/ai-agent/docs/day101-query-rewriting-reranking-classroom-draft.md`
- Day102 handoff: `projects/ai-agent/docs/DAY101_TO_DAY102_HANDOFF.md`
- Example: `projects/ai-agent/examples/day101_query_rewriting_reranking.py`
- Seed/evaluator: `projects/ai-agent/evals/day101_query_rewriting_reranking_seed.jsonl` and
  `projects/ai-agent/evals/run_day101_seed_eval.py`
- Evidence replay: `projects/ai-agent/evals/run_day101_evidence_replay.py`
- Validation: `projects/ai-agent/evidence/day101-validation.json`
- Research: `projects/ai-agent/research/day101-query-rewrite-reranker-evidence.jsonl` and
  `projects/ai-agent/research/day101-reranker-approach-decision.md`

Global navigation, curriculum, roadmap, project status, sprint tasks, changelog, decisions, cheat sheet,
interview guide, Agent instructions and CI workflow are synchronized through Day101.

## Validation actually executed

- Day101 focused tests: 56/56 PASS.
- Day101 seed: 10/10 PASS.
- Complete AI Agent suite: 1062/1062 PASS on the local Python 3.11.5 fallback runtime.
- Every available seed evaluator: 17/17 evaluator processes PASS.
- Day100 and Day101 saved evidence replay: PASS.
- Day101 deterministic example and Python compileall: PASS.
- Final repository structure, Markdown/link, JSON, protected-file, secret-pattern and diff checks are recorded
  in `projects/ai-agent/evidence/day101-validation.json` after execution.
- Python 3.12 pull-request CI: PASS.

## Evidence boundary

The real saved Day100 path has no current production-selected bundle. It rejects before rewrite, reranker or
database side effects and is the only real handoff evidence. The positive path uses an isolated
`DAY100_CLASSROOM_ONLY`, `production_eligible=false` fixture.

The deterministic fake proves rewrite/candidate budgets, stable identities, unchanged Day100 routing,
occurrence deduplication, deterministic fusion/tie-break, candidate-subset enforcement, Provider response
validation, final authorization/provenance rechecks and explicit fallback state. It does not prove real model
quality, real protected egress, database/ANN behavior, latency, capacity, cost, error rates, recovery or
production suitability.
