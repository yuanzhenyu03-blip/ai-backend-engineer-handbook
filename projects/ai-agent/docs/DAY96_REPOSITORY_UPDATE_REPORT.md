# Repository Update Report

## Lesson

Day96 — Chunking Strategy and Experiments. Status: completed at guided classroom scope; Phase 7C remains in
progress, with Day97 next. This report describes the Day96 repository-update candidate; a pull request is for
review and is not a production release.

## Files Added

- Formal 16-section lesson, application design, classroom record and Day97 handoff.
- Eight Day96 application-owned chunking/tokenizer/strategy/validation/Committer/experiment modules.
- Synthetic Day95 fixture and deterministic four-attempt chunking example.
- Day96 test modules, 16-case seed and evaluator.
- Controlled experiment, validation and official-source research evidence.

## Files Updated

- Root, docs and project navigation plus `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`,
  `CHANGELOG.md` and `AGENTS.md`.
- FastAPI cheat sheet and interview handbook.
- Day95 in-memory lifecycle store gained one read-only source-artifact accessor for Day96 rechecks; Day95
  lifecycle and activation authority did not change.

## Main Classroom Content Preserved

- The learner rejected overwriting ChunkSet A, reusing its indices/IDs and collapsing identical text from
  different source spans; A remains selected while B is only a valid candidate.
- The learner separated soft target from hard max, overlap from coverage, and structural metrics from
  `Recall@k`, `Precision@k` and MRR.
- The learner chose strict Day95 active-artifact eligibility, conditional Committer selection with a fence,
  outbox intent before notification and downstream idempotency for duplicate delivery.
- The learner's independent synthesis and English Interview passed with recorded boundary/language
  corrections, including principal-specific ACL-filtered gold evidence.

## Main Misconceptions Corrected

- Same text/hash or `chunk_index` is not stable cross-strategy identity or citation provenance.
- Re-chunking does not create a new ParsedArtifact or DocumentVersion; changed source/parser contract belongs
  to Day95 re-ingestion.
- Overlap helps context continuity, not source-gap repair. A failed coverage gate is rejected before ranking.
- A selected pointer is necessary but not sufficient for current retrieval: match Day95 active version and
  current principal authorization.
- Determinism and 100% source coverage are not retrieval-quality evidence.

## Engineering Artifacts Produced

- Versioned `ChunkingContract`, stable operation/idempotency key, fresh attempt identity and exact source
  segment/manifest contracts.
- Fixed-token, recursive and section-aware bounded candidate strategies with explicit fail-closed/fallback
  policy and normalization mapping.
- Independent validation and sole in-memory classroom Committer with immutable set insertion, exact
  duplicate convergence, stale-fence rejection and conditional selection/outbox intent.
- Four-run content-safe experiment report with full contracts, structural metrics and retained failure.

## Framework Connections Added

- LangChain TextSplitter and LlamaIndex node-parser research stays explicitly NOT RUN; their private types
  would remain behind an Adapter and cannot supply application identity or commit authority.
- The dependency-free classroom tokenizer demonstrates control flow only and does not stand in for a fixed
  model-specific tokenizer.

## AI Backend Connections Added

- Day97 receives stable tenant/document/version/source/ParsedArtifact/ChunkSet/Chunk provenance and must apply
  current principal ACL rather than treating tenant equality or pointer selection as permission.
- Day98–Day99 may embed and index an eligible selected set; Day102 citations trace original canonical spans;
  Day103 evaluates actual retrieval and answer results with authorized gold evidence.

## Interview Material Added

- Beginner: ParsedArtifact versus ChunkSet, local index versus identity, character versus token budget.
- Intermediate: overlap provenance, re-ingestion versus re-chunking, oversized structural-unit policy.
- Senior: fair experiments, stale concurrent selection, citation lineage and missing production evidence.
- Weak classroom answers and stronger corrected phrasing are retained in the formal lesson and interview
  handbook without replacing the learner's own synthesis.

## Validation Performed

- Code: 25/25 Day96 focused tests; 60/60 Day95 focused tests; 674/674 available Day-series regressions and
  846/846 full ai-agent tests; 16/16 Day96 seed; all twelve available Day83–Day96 seed evaluators exited zero; deterministic example and
  saved report rerun match; compile PASS on Python 3.11.5.
- Markdown: required 16 lesson sections in order; relative file links checked.
- JSON/JSONL: experiment, validation, research and seed files parsed.
- Whitespace: Python line-length, trailing-whitespace and `git diff --check` checks passed.
- Secrets: credential-pattern scan found no matches in Day96 artifacts; synthetic prompt-like content remains
  fixture data, not an executed instruction.
- YAML: no Day96 YAML or workflow was introduced.

## Remaining TODO

- Python 3.12+ runtime verification; real fixed tokenizer with offline/special-token/concurrency tests.
- Durable transactional ChunkSet/selection/outbox store, multi-process fence and crash/restart recovery.
- Real dispatcher/deduplication, measured CPU/RSS/load/soak, telemetry and alert delivery.
- Day97 ACL, Day98 embedding, Day99 index and Day103 retrieval/answer evaluation.
- Production readiness remains `MORE_EVIDENCE_NEEDED`; this update does not claim deployment.

## Suggested Commit Message

`feat(day96): add versioned chunking experiments and immutable chunk sets`
