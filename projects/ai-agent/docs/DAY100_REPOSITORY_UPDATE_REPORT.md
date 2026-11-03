# Repository Update Report

## Lesson

Day: Day100

Title: Hybrid Retrieval and Filtering

Status: Completed at guided classroom scope; `MORE_EVIDENCE_NEEDED` for production

## Files Added

- `docs/fastapi/day100-hybrid-retrieval-and-filtering.md`
- `projects/ai-agent/src/rag_*retrieval*.py`, `rag_query_encoder.py`, `rag_lexical_retrieval.py`,
  `rag_dense_retrieval.py`, `rag_hybrid_fusion.py` and `rag_authorized_retriever.py`
- `projects/ai-agent/tests/test_day100_*.py`
- Day100 example, seed/evaluators, official research, decision record and replayable evidence reports
- Day100 design, classroom record and Day101 handoff

## Files Updated

- Root status, curriculum, roadmap, tasks, changelog, decisions, agent guidance and README files
- FastAPI cheat sheet and interview handbook
- AI-agent classroom workflow and project README

## Main Classroom Content Preserved

- Real Day99 `SEALED` but unselected evidence fails before encoder/filter/BM25/dense/database work.
- Query and document encoder roles, prefixes and full semantic contracts remain distinct.
- Effective scope is current authorization intersected with validated business filter and system exclusions.
- BM25 and dense raw scores remain separate; deterministic weighted RRF combines branch ranks.
- Candidates `A`, `B`, `C` may enter fusion; stale `D` is rejected before fusion and revoked `B` is rejected
  before guarded release.
- Bounded overfetch/refill, explicit partial results and fail-closed cursor invalidation never broaden scope.
- Ordinary audit evidence stores controlled hashes/redacted summaries, not raw query or protected text.

## Main Misconceptions Corrected

- `SEALED` does not mean selected or production-ready.
- A client filter narrows authorization through intersection; it does not grant authority.
- Database pre-filter/post-filter execution does not own application filter logic.
- BM25 and dense raw scores are not directly comparable.
- Pre-query authorization cannot replace final current grant/provenance recheck.
- Synthetic positive evidence cannot prove a real Provider, database, ANN, latency or recovery gate.

## Engineering Artifacts Produced

- Exact selected-bundle and generation admission with zero-call fail-closed behavior.
- Frozen `QueryEncoderContract`, `LexicalRetrievalContract`, filter schema and retrieval/fusion policies.
- Dependency-free BM25 and Exact cosine correctness references.
- Application-owned filter AST with direct, split and bounded post-filter plans.
- Version-bound candidate validation, occurrence deduplication, weighted RRF and deterministic tie-break.
- Guarded current reauthorization/provenance release, bounded refill and typed result completeness.
- Canonical signed cursor and candidate-only cache bound to authority/query/filter/policy identities.

## Framework Connections Added

- PostgreSQL full-text search plus pgvector as a provisional real integration candidate.
- Qdrant dense/sparse fusion and payload-filter capability boundaries.
- Pinecone hybrid and metadata-filter capability boundaries.
- Application authority remains independent of all three Provider execution models.

## AI Backend Connections Added

- Day95–Day99 identity and authority chain into reproducible authorized candidates.
- Day52 authorization and Day56 bounded-failure semantics applied to retrieval.
- Clear Day101 boundary: rewrite/rerank only current authorized Day100 candidates.
- Clear Day103 boundary: pipeline correctness is not relevance or answer-quality evidence.

## Interview Material Added

- Beginner sealed versus selected versus production-ready boundary.
- Intermediate incomparable score scales, filter ownership and exact execution plans.
- Senior authorization-before-retrieval/final-release, generation mismatch, refill and cursor semantics.
- All three original English answers, technical assessments and corrected expressions are retained.

## Validation Performed

- Markdown: required 16 lesson sections, fence balance and relative-link targets inspected.
- Workflow: Day100 saved-evidence replay added to the Python 3.12 quality gate.
- Code: compileall and type checking of all new source modules passed.
- Tests: 64/64 Day100 focused and 1006/1006 full repository tests passed locally.
- Seeds: Day100 8/8 and every available repository seed evaluator passed.
- Replay: saved Day96, Day98, Day99 and Day100 reports matched deterministic output.
- JSON: every Day100 JSON/JSONL evidence file parsed successfully.
- Safety: no raw query, protected text or vector appears in normal Day100 evidence.
- CI: GitHub Actions run `41572660971`, job `125708928954`, passed on Python 3.12.15 with 1006/1006 tests,
  every available seed evaluator and the saved Day100 evidence replay.

## Remaining TODO

- Run a real query Provider and real PostgreSQL/pgvector/FTS, Qdrant or Pinecone integration.
- Measure real ANN recall under selective filters, production latency/throughput/capacity and cost.
- Run backup/restore, failover, deletion propagation, durable cursor/cache and disaster-recovery drills.
- Keep production readiness `MORE_EVIDENCE_NEEDED` until every required hard gate passes.

## Suggested Commit Message

`feat(day100): add authorized hybrid retrieval`
