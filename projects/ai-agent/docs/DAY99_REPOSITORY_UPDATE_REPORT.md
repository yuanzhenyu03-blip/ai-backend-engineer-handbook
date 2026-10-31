# Repository Update Report

## Lesson

Day: Day99

Title: Vector Database and Vector Index Design

Status: Completed at guided classroom scope; `MORE_EVIDENCE_NEEDED` for production

## Files Added

- `docs/fastapi/day99-vector-database-and-vector-index-design.md`
- `projects/ai-agent/src/rag_vector_*.py` and `rag_vector_index_*.py`
- `projects/ai-agent/tests/test_day99_*.py`
- Day99 example, seed/evaluator, official research, decision and three replayable evidence reports
- Day99 design, classroom record and Day100 handoff

## Files Updated

- Root status, curriculum, roadmap, tasks, changelog, decisions, agent guidance and README files
- FastAPI cheat sheet and interview handbook
- AI-agent classroom workflow and project README

## Main Classroom Content Preserved

- Provider cosine distance `0.18` becomes application similarity `0.82` and passes `>= 0.80`.
- Exact/Flat is the first correctness oracle; real ANN remains `NOT_RUN`.
- HNSW `m`/`ef_construction` and IVF `lists` are physical build parameters; `ef_search`/`probes` are query
  policy parameters.
- Authorization, filters, namespace, generation identity and current pointer are separate facts.
- Timeout after dispatch is `UNKNOWN`; stable operation identity, reconciliation and fencing prevent blind
  duplicate processing.
- Rebuild uses copy-on-write shadow generations; old generations are not overwritten.

## Main Misconceptions Corrected

- Similar ranking does not make cosine, dot product and L2 one score contract.
- Provider ACK/checkpoint is not application commit, exact readback, backup or current selection.
- Database filters and namespaces do not replace current authorization.
- Lease expiry alone does not stop a stale worker; enforceable fencing is required.
- Green fake tests and simulated recall do not prove a real database, ANN, recovery or production readiness.

## Engineering Artifacts Produced

- Narrow signed `embedding_set:read_for_indexing` handoff and two-phase current-state guard.
- Frozen `VectorIndexContract` and separate `RetrievalPolicyRevision`.
- Deterministic tenant-scoped batch plan with stable IDs, byte limits and exact ACK correlation.
- Application-owned score Adapter, Exact/Flat oracle, content-safe manifest/readback Validator.
- Stable operation/fresh attempt/fence workflow, sole Committer, immutable generations, selected-pointer CAS and
  Outbox hint classification.
- Official pgvector/Qdrant/Pinecone hard-gate matrix and 256-vector exact/simulated recall experiment.

## Framework Connections Added

- PostgreSQL + pgvector as the provisional classroom approach, with no claimed local runtime.
- Qdrant collection/alias/snapshot/tenant boundaries and unresolved cross-system cutover/recovery evidence.
- Pinecone version/dimension/metric/namespace/egress boundaries and retained unknown gates.

## AI Backend Connections Added

- Day95–Day99 lineage into a committed current vector generation.
- Clear boundary between index correctness, Day100 hybrid retrieval and Day103 relevance/answer quality.
- Protected-vector logging, cache identity and tenant side-channel controls.

## Interview Material Added

- Beginner score and database/index distinctions.
- Intermediate physical/query parameters and partial-ACK validation.
- Senior shadow-generation, reconciliation, fencing and atomic pointer/Outbox design.

## Validation Performed

- Markdown: required 16 lesson sections and link targets inspected; `git diff --check` passed.
- YAML: workflow diff inspected; authoritative GitHub execution remains pending until push.
- Code: compileall passed; 36/36 focused tests and 941/941 full tests passed on local Python 3.11.5.
- Seeds: Day99 8/8 and every repository seed evaluator passed.
- Replay: build, controlled index experiment and store-selection matrix matched saved JSON exactly.
- JSON: all Day99 evidence files parsed successfully.
- Secrets: synthetic identities/data only; no credentials or raw vectors in ordinary evidence.

## Remaining TODO

- Run the authoritative Python 3.12 GitHub Actions gate after push.
- Execute real pgvector/other Provider, real HNSW/IVF recall, capacity/latency and filter-isolation tests.
- Run durable backup/restore, Outbox relay, deletion-ledger and disaster-recovery drills.
- Activate a selected generation only after every required hard gate is `PASS`.

## Suggested Commit Message

`feat(day99): add governed vector index generations`
