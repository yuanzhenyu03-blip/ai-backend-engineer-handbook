# Repository Update Report

## Lesson

Day95 — RAG Ingestion Pipeline, Parsing and Document Lifecycle is released at guided classroom scope. Phase
7C is now in progress, and Day96 — Chunking Strategy and Experiments is next.

## Files Added

- Formal 16-section lesson, design, classroom record and Day96 handoff.
- Nine application-owned RAG ingestion/lifecycle modules.
- Deterministic example, 16-case seed/evaluator and validation/research evidence.
- Eleven Day95 test modules plus an independent parser-process fixture.

## Files Updated

- Root/course/project navigation and status: `README.md`, `docs/README.md`, `projects/ai-agent/README.md`,
  `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `CHANGELOG.md`, and `AGENTS.md`.
- Day95 FastAPI cheat-sheet and interview sections.

## Main Classroom Content Preserved

- The learner's progression from filename/hash assumptions to stable logical document identity, immutable
  versions, admitted source evidence and application-owned parser contracts.
- Timeout, eventual consistency, reconciliation, retry, quarantine/tombstone and atomic activation reasoning.
- The independent final synthesis and English interview assessment boundaries.

## Main Misconceptions Corrected

- A filename is not stable identity; a content hash proves byte equality, not authorization or semantics.
- A SourceArtifact is admitted immutable source evidence, but it is not an active parsed version.
- A parser result is a candidate, and `NOT_FOUND` is not proof that parsing never executed.
- Retry creates a fresh attempt under the same operation; changed content/contract is re-ingestion under a new
  immutable document version.
- Quarantine isolates evidence; tombstone records logical deletion/unavailability; neither means immediate
  physical erasure.

## Engineering Artifacts Produced

- Source admission, identity contracts, parser Adapter/process, orchestration, sole Committer, recovery, retry
  policy and lifecycle eligibility modules.
- Exact duplicate convergence, conflict fail-closed behavior, re-ingestion, supersede, quarantine and tombstone.
- Conditional `state + version + fence` dispatch/commit gates and atomic active-pointer transition.

## Framework Connections Added

- Parser-specific fields remain behind an Adapter; the application owns `ParsedDocumentCandidate`, validation,
  lifecycle state and commit authority.
- The Day93/Day94 stable-operation, fresh-attempt, preflight, dispatch-marker, reconciliation and sole-Committer
  boundaries are reused rather than duplicated.

## AI Backend Connections Added

- Day95 produces only an activated immutable document version; Day96 chunking is permitted only through the
  committed `Document.active_version_pointer`.
- Source and parsed artifacts retain provenance and lifecycle evidence for future ACL, citation, evaluation and
  index-migration lessons.

## Interview Material Added

- Beginner: filename/document identity, SourceArtifact versus active DocumentVersion, parser candidate status.
- Intermediate: duplicate/re-ingestion/supersede, failed new version, timeout/reconciliation.
- Senior: crash-safe activation, quarantine/tombstone/deletion and remaining production evidence.

## Validation Performed

- 60/60 focused Day95 tests and 16/16 seed cases passed on Python 3.11.5.
- Independent parser-process success and hang-after-parse timeout paths passed.
- Day88–Day94 dependency-free regressions passed; 31/31 available real-`mcp==2.2.0` SDK/restart regressions
  passed in an isolated environment.
- Deterministic example, compile, JSON/JSONL, 16-section lesson order, links, whitespace and credential checks
  passed.

## Remaining TODO

- Production parser deployment and exact deployment checksum/version verification.
- Real authorization, durable transactional storage and versioned Object Storage.
- Distributed concurrency/crash/recovery, load/backpressure and alert-delivery drills.
- Python 3.12 validation. Production readiness remains `MORE_EVIDENCE_NEEDED`.

## Suggested Commit Message

`feat(day95): add RAG ingestion pipeline and document lifecycle`
