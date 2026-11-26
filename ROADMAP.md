# AI Backend Engineer Roadmap

## Goal

Become an overseas AI Backend Engineer capable of building production-ready AI systems, passing technical interviews, and contributing to real-world backend projects.

Estimated Duration: competency-gated (current planning horizon ~Day130; not a fixed cap — see Planning Horizon and Completion Model)

---

# Phase 1 — Python Foundations (Day01–Day14)

Objective:
Build Python engineering thinking instead of memorizing syntax.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day01 | Python Object Model | ✅ Completed |
| Day02 | Mutable vs Immutable | ✅ Completed |
| Day03 | Functions & Parameter Passing | ✅ Completed |
| Day04 | Scope & LEGB | ✅ Completed |
| Day05 | Closures | ✅ Completed |
| Day06 | Decorators | ✅ Completed |
| Day07 | Iterators & Generators | ✅ Completed |
| Day08 | Exception Handling | ✅ Completed |
| Day09 | Modules & Packages | ✅ Completed |
| Day10 | Type Hints | ✅ Completed |
| Day11 | Object-Oriented Programming | ✅ Completed |
| Day12 | Context Managers | ✅ Completed |
| Day13 | Async Programming | ✅ Completed |
| Day14 | Mini Project + Mock Interview | ✅ Completed |

Deliverables:

- Python Engineering Handbook
- Cheat Sheets
- Interview Notes
- Mini Project

---

# Phase 2 — Engineering Foundations (Day15–Day28)

Objective:
Follow the Software Delivery Lifecycle: understand WHY each tool exists before HOW to use it.
Every tool solves an engineering problem introduced in a previous lesson.

```text
Git
 -> GitHub
 -> Project Management
 -> CI/CD
 -> GitHub Actions
 -> Docker
 -> Deployment
 -> Kubernetes
 -> Production AI Backend
```

## Git Engineering

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day15 | Git Object Model | ✅ Completed |
| Day16 | Branch & Merge | ✅ Completed |
| Day17 | GitHub Workflow | ✅ Completed |
| Day18 | Merge Strategy & Code Review | ✅ Completed |
| Day19 | GitHub Project Management | ✅ Completed |

## DevOps Foundations

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day20 | CI/CD Foundations | ✅ Completed |
| Day21 | GitHub Actions Fundamentals | ✅ Completed |
| Day22 | GitHub Actions Advanced | ✅ Completed |

## Container Engineering

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day23 | Docker Fundamentals | ✅ Completed |
| Day24 | Docker Compose | ✅ Completed |

## Production Engineering

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day25 | Deployment Foundations | ✅ Completed |
| Day26 | Kubernetes Foundations | ✅ Completed |
| Day27 | Kubernetes Workloads | ✅ Completed |
| Day28 | AI Backend Production Architecture | ✅ Completed |

Deliverables:

- Git & GitHub Workflow
- CI/CD Pipelines with GitHub Actions
- Dockerized Applications and Docker Compose stacks
- Production Deployment (Nginx, SSL, zero downtime)
- Kubernetes Workloads
- Production-ready AI Backend Architecture

---

# Phase 3 — Backend Foundations (Day29-Day42)

Objective:
Turn the conceptual state ownership established in Day28 into an executable, failure-aware data layer:
model durable business truth in PostgreSQL, express and verify it with SQL, preserve correctness under
transactions and concurrency, evolve and operate the database safely, and use Redis only for transient
caching, messaging, rate limiting, and coordination where its lifecycle/failure model fits.

Topics: PostgreSQL, SQL, Redis, Database Design.

## PostgreSQL and SQL

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day29 | PostgreSQL Foundations and Durable Relational State | ✅ Completed |
| Day30 | SQL Data Manipulation and Query Fundamentals | ✅ Completed |
| Day31 | Relational Modeling and Data Integrity | ✅ Completed |
| Day32 | SQL Joins, Aggregation, and Operational Queries | ✅ Completed |
| Day33 | PostgreSQL Transactions and Atomic State Changes | ✅ Completed |
| Day34 | Concurrency Control, MVCC, and Worker Claims | ✅ Completed |
| Day35 | PostgreSQL Indexes and Query Planning | ✅ Completed |
| Day36 | Schema Evolution and Safe Migrations | ✅ Completed |
| Day37 | PostgreSQL Production Reliability | ✅ Completed |

## Redis and Capstone

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day38 | Redis Foundations and Data Structures | ✅ Completed |
| Day39 | Redis Cache Design and Consistency | ✅ Completed |
| Day40 | Redis Messaging and Queue Semantics | ✅ Completed |
| Day41 | Redis Coordination and Production Safety | ✅ Completed |
| Day42 | Backend Data Design Capstone | ✅ Completed |

Deliverables:

- A production-minded AI Backend Data Layer project built progressively across Day29-Day42.
- Raw SQL schema migrations and data-integrity constraints.
- SQL query and operational-query exercises.
- Transactional Job + Outbox state changes and concurrency-safe worker-claim/idempotency examples.
- Index/query-plan evidence and safe schema-evolution exercises.
- PostgreSQL reliability and recovery runbooks.
- Redis keyspace, cache, messaging, rate-limit, and coordination designs.
- A final data ownership/failure/validation matrix connecting PostgreSQL, Redis, Object Storage,
  Celery workers, and the Day28 architecture.

SQLAlchemy and Alembic are Phase 4 topics; Phase 3 teaches raw PostgreSQL/SQL mental models first.

---

# Phase 4 — Production AI API Engineering (Day43–Day58)

Objective:
Turn the Day28–Day42 conceptual architecture and data contracts into a runnable, testable Production AI
Backend API (FastAPI + SQLAlchemy + Alembic + Redis/Outbox/Worker + Object Storage + OpenAI-compatible
provider, with auth and tenant isolation).

Day55 note: Celery runs long-running Provider work on a **supported Celery broker transport** and reuses the
Day40 delivery-semantics mental model (at-least-once, redelivery, ACK timing, idempotency, poison messages).
It does **not** consume the Day40 custom Redis Streams / Consumer Group design and does **not** hand-build a
Celery replacement (see `CURRICULUM.md` Day55 and Day40).

Implementation boundaries (Day50 Outbox scope vs Day55 Celery; Day54 streaming kinds and cancellation
lifecycles) are recorded in `CURRICULUM.md` under "Future Lesson Implementation Boundaries."

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day43 | AI Backend Product Contract and FastAPI Request Lifecycle | ✅ Completed |
| Day44 | Pydantic v2 and Structured AI Input/Output Contracts | ✅ Completed |
| Day45 | Dependency Injection, Lifespan, Configuration and AI Provider Adapters | ✅ Completed |
| Day46 | SQLAlchemy 2.0 Mapping for the Day42 Data Model | ✅ Completed |
| Day47 | Async Sessions, Transactions, Repository and Unit of Work | ✅ Completed |
| Day48 | Alembic and Safe AI Backend Schema Evolution | ✅ Completed |
| Day49 | Upload Sessions, Object Storage and Artifact Verification | ✅ Completed |
| Day50 | Idempotent AI Job API and Transactional Outbox Integration | ✅ Completed |
| Day51 | Authentication, Password Security and JWT | ✅ Completed |
| Day52 | Authorization, Tenant Isolation, Quotas and API Security | ✅ Completed |
| Day53 | OpenAI SDK, Provider Boundaries and Structured Output | ✅ Completed |
| Day54 | AI Streaming, Client Disconnects, Timeouts and Cancellation | ✅ Completed |
| Day55 | Celery, Worker Execution and Long-running AI Jobs | ✅ Completed |
| Day56 | Provider Resilience, Rate Limits, Token Cost and Backpressure | ✅ Completed |
| Day57 | AI Backend Testing, Fake Providers, Contract Tests and Failure Injection | ✅ Completed |
| Day58 | Production AI API Capstone, Observability and English Interview | ✅ Completed |

Deliverables:

- A runnable FastAPI AI Job backend with PostgreSQL/SQLAlchemy/Alembic, Redis/Outbox/Worker, an Object
  Storage boundary, an OpenAI-compatible provider adapter, auth/tenant isolation, and tests + runtime evidence.

Completion note: Day43-Day58 are Completed as CLASSROOM SCOPE plus deterministic, in-process EXECUTED_LOCAL_RUNTIME
artifacts (design + runnable models + tests). The above is the phase DESIGN target; a real runnable FastAPI runtime, a
real OpenTelemetry exporter, real PostgreSQL/Redis/Celery integration, and real Provider traffic are recorded NOT RUN
(INTEGRATION_RUNTIME + PRODUCTION) — see each day's validation matrix in CURRICULUM.md and the project artifacts.

---

# Phase 5 — Production Runtime Integration and Browser Tool Engineering (Day59–Day66)

Objective:
Close the Phase 4 evidence gap first (Day59–61 Production Integration Gate: turn the deterministic in-process
evidence into real local integration for FastAPI + PostgreSQL/Alembic + Redis/Celery + Object Storage +
Provider + OpenTelemetry), then build Playwright into an isolated, recoverable, auditable browser worker
exposed as a permissioned AI tool. Do not teach bypassing website security, captchas, or anti-automation.
Phase 4 still ends at Day58; Day59–61 do not retcon into Phase 4.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day59 | Real FastAPI Runtime, PostgreSQL and Alembic Integration | ✅ Completed |
| Day60 | Outbox, Redis/Celery Broker and Worker Recovery Integration | ✅ Completed |
| Day61 | Object Storage, Provider Adapter and OpenTelemetry End-to-End Evidence | ✅ Completed |
| Day62 | Playwright Runtime, Locators and Reliable Async Interaction | ✅ Completed |
| Day63 | Browser Authentication, Storage State and Tenant Isolation | ✅ Completed |
| Day64 | Dynamic Extraction, Network Events and Artifact Evidence | ✅ Completed |
| Day65 | Browser Failure Recovery and Security Boundaries | ✅ Completed |
| Day66 | Queue-backed Playwright Worker as a Permissioned AI Tool | ✅ Completed |

Deliverables:

- Real local INTEGRATION_RUNTIME evidence for the Phase 4 backend (FastAPI + PostgreSQL + Redis/Celery +
  Object Storage + Provider + OpenTelemetry) + an isolated, recoverable, auditable Playwright browser worker
  exposed as a permissioned AI tool.

---

# Phase 6 — n8n AI Workflow Integration (Day67–Day70) — ✅ COMPLETE

Objective:
Use n8n to orchestrate the now-real API, the permissioned browser tool, and AI capabilities as an
integration/workflow layer — not a low-code replacement for backend correctness. Durable truth stays in
PostgreSQL.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day67 | n8n Workflow Model, Triggers, FastAPI Integration and Responsibility Boundaries | ✅ Completed |
| Day68 | Long-running AI Jobs: Polling, Callback, Correlation and Idempotency | ✅ Completed |
| Day69 | Human Approval, Retry, Secrets, Audit and Error Workflows | ✅ Completed |
| Day70 | n8n + FastAPI + AI Tool Integration Capstone and Interview | ✅ Completed |

Deliverables:

- n8n workflows orchestrating the real FastAPI AI backend and permissioned browser tool, with idempotent
  long-job handling, human approval, and audit.

---

# Planning Horizon and Completion Model (Day71 onward)

```text
The roadmap is competency-gated, not day-count-gated.
The published lesson numbers are planning coordinates, not a promise that the course must end at a fixed number.
```

From Day71 the track is an AI Backend Employment Track. Completion is passing the Employment Readiness Gate,
not reaching a fixed day. The current planning horizon is Day130 — a planning coordinate, not a permanent cap;
if the Gate is not met, Planned lessons may be added, split, merged, or renumbered from real job requirements,
ecosystem changes, learner weak points, and interview feedback. Completed Day01–Day106 lessons, Decisions
001–025 and sealed evidence stay fixed; only Planned Day107+ scope may change.

Day107–Day130 contains 24 milestone coordinates rather than 24 promised calendar days. The intended
approximately eight-week cadence also reserves implementation-buffer, independent-retest, Python/SQL, English,
application and recovery days. A heavy milestone may span 1–3 calendar days and multiple Tickets; calendar
passage never creates completion.

---

# Runnable Checkpoint Cadence (Day71 onward)

Normative execution constraint (details in `CURRICULUM.md`, "Mandatory Runnable Checkpoint Cadence"). Never
more than 4–6 consecutive lessons without running the cumulative Phase Engineering Artifact at a Runnable
Checkpoint. A Checkpoint is an actual run of the evolving Artifact (not review/docs/static design) and must
save: exact command, revision/commit, config, runtime boundary, evidence tier, actual result, tests, safe
logs/traces/metrics and failure point when applicable, and NOT RUN limitations. `pytest passed` stays
`EXECUTED_LOCAL_RUNTIME`; it does not auto-upgrade to `INTEGRATION_RUNTIME` or `PRODUCTION`.

```text
Phase 7A: Day74, Day78
Phase 7B: Day83, Day88, Day94
Phase 7C: Day99, Day103, Day106
Phase 7D: Day110, Day113
Phase 7E: Day117, Day120, Day123
Phase 8:  Day126, Day130
```

No new lesson numbers are added for Checkpoints; they run on the existing Days above. The Planned
Day107–Day130 gaps are 4/3/4/3/3/3/4 lesson coordinates and remain within the maximum gap of six.

---

# Phase 7A — LLM Application Engineering (Day71–Day78)

Objective:
Evolve a single Provider call (Day53–58) into a complete, testable LLM Application Runtime: architecture,
tokens/context/sampling and failure modes, a replaceable Provider Adapter, prompt contracts/versioning,
structured output/function calling, streaming/caching/batching, model routing/fallback/cost, and
fake-Provider contract/regression tests.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day71 | LLM Application Architecture, Tokens, Context, Sampling and Model Failure Modes | ✅ Completed (classroom scope; CONCEPTUAL + STATIC, runtime NOT RUN) |
| Day72 | Provider Capabilities and the Replaceable Provider Adapter | ✅ Completed (classroom scope; CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME 58 tests; INTEGRATION/PRODUCTION NOT RUN) |
| Day73 | Prompt Contracts, Prompt Versioning and Compatibility | ✅ Completed (classroom scope; CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME 39 tests; INTEGRATION/PRODUCTION NOT RUN) |
| Day74 | Structured Output, JSON Schema and Function/Tool Calling | ✅ Completed (classroom scope; CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME 34 Day74 tests / 131 total; Python 3.12 + INTEGRATION/PRODUCTION NOT RUN) |
| Day75 | Streaming, Caching and Batching for LLM Applications | ✅ Completed (classroom scope; CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME 41 Day75 tests; INTEGRATION/PRODUCTION NOT RUN) |
| Day76 | Model Routing, Fallback, Latency and Cost Engineering | ✅ Completed (classroom scope; CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME 18 Day76 tests / 190 total; INTEGRATION/PRODUCTION NOT RUN) |
| Day77 | Fake Provider, Contract Tests and LLM Regression Tests | ✅ Completed (classroom scope; CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME 31 Day77 tests / 221 total; INTEGRATION/PRODUCTION NOT RUN) |
| Day78 | LLM Application Runtime Capstone, Checkpoint and English Interview | ✅ Completed (classroom scope; 22 Day78 / 243 cumulative local tests) |

Deliverables:

- A testable LLM Application Runtime behind a replaceable Provider Adapter, with prompt contracts, structured
  output/function calling, streaming/caching/batching, model routing/cost, and fake-Provider tests.

---

# Phase 7B — Agent Runtime and MCP Engineering (Day79–Day94)

Status: ✅ Complete at guided classroom scope. Day94 reached bounded `RESTART_RECOVERY_RUNTIME`; production
readiness remains `MORE_EVIDENCE_NEEDED`.

Objective:
Build a framework-agnostic Agent Runtime (loop, tools/permissions, state machine, budgets, durable jobs,
human approval, memory vs business-state, multi-agent, security), then run a Framework / Job-Market Refresh,
choose a framework behind a replaceable adapter, and engineer MCP client/server, auth/tenant isolation, and
the remote-MCP lifecycle. Understand the stable contracts first; the framework is replaceable infrastructure,
not the business model. Do not pre-lock LangGraph.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day79 | Framework-agnostic Agent Loop and Control Flow | ✅ Completed (classroom scope; 8 Day79 / 251 cumulative local tests) |
| Day80 | Tool Registry, Tool Schema and Permission Model | ✅ Completed (classroom scope; 22 Day80 / 273 cumulative local tests) |
| Day81 | Agent State Machine, Termination, Loop Detection and Step/Token/Cost Budgets | ✅ Completed (classroom scope; 20 Day81 / 293 cumulative local tests) |
| Day82 | Durable Agent Jobs, Checkpoint, Resume and Recovery | ✅ Completed (classroom scope; 32 Day82 / 325 cumulative local tests) |
| Day83 | Human Approval, Interrupt and Escalation Boundaries | ✅ Completed (guided classroom scope; 53 focused / 378 cumulative local tests; 26/26 seed; checkpoint PASS; independent final synthesis not assessed) |
| Day84 | Conversation Memory vs Durable Business-state Boundaries | ✅ Completed (guided classroom scope; 33 focused / 411 cumulative local tests; 16/16 seed; Day83 26/26 seed regression; independent final synthesis not assessed) |
| Day85 | Multi-agent Handoff and Coordination Boundaries | ✅ Completed (guided classroom scope; 32 focused / 443 cumulative local tests; 18/18 seed; Day84 16/16 and Day83 26/26 seed regressions; independent final synthesis not assessed) |
| Day86 | Agent Security: Prompt Injection, Tool Abuse, Data Exfiltration and Sandboxing | ✅ Completed (guided classroom scope; 31 focused / 474 cumulative local tests; 25/25 seed; Day85 18/18, Day84 16/16 and Day83 26/26 seed regressions; independent final synthesis not assessed) |
| Day87 | Agent Framework and Job-Market Refresh Checkpoint | ✅ Completed (guided classroom scope; 22 focused / 496 cumulative local tests; Day86 25/25, Day85 18/18, Day84 16/16 and Day83 26/26 seed regressions; no framework selected; independent final synthesis not assessed) |
| Day88 | Agent Runtime Framework Selection Behind a Replaceable Adapter | ✅ Completed (guided classroom scope; Candidate C `pydantic-ai-slim==2.41.0` remains default; Decision 010 adds a dependency-free LangGraph-shaped contract translator; amendment matrix 43 focused / 539 cumulative on Python 3.11.5; not LangGraph runtime integration; production readiness MORE_EVIDENCE_NEEDED) |
| Day89 | MCP Foundations and Protocol Model | ✅ Completed (guided classroom scope; current spec `2026-07-28`; 21 focused / 560 cumulative local tests; 16/16 seed; Fake Transport; no real MCP integration; readiness MORE_EVIDENCE_NEEDED) |
| Day90 | MCP Client Engineering | ✅ Completed (guided classroom scope; `mcp==2.2.0`; 21 focused / 581 cumulative tests; controlled separate-process stdio integration; 13/13 seed; evidence INTEGRATION_RUNTIME; production readiness MORE_EVIDENCE_NEEDED) |
| Day91 | MCP Server Engineering: Resources, Tools and Prompts Responsibility Boundaries | ✅ Completed (guided classroom scope; `mcp==2.2.0`; 40 focused / 621 cumulative tests; controlled separate-process stdio integration; 14/14 seed; evidence INTEGRATION_RUNTIME; production readiness MORE_EVIDENCE_NEEDED) |
| Day92 | MCP Authentication, Authorization and Tenant Isolation | ✅ Completed (guided classroom scope; 35 focused / 656 combined tests; 16/16 seed; HTTP/stdin identity + tenant-bound permits; evidence INTEGRATION_RUNTIME; production readiness MORE_EVIDENCE_NEEDED) |
| Day93 | Remote MCP Lifecycle: Timeout, Retry, Versioning and Observability | ✅ Completed (guided classroom scope; `mcp==2.2.0`; 62 focused / 719 combined tests; 16/16 seed; independent-process loopback Streamable HTTP; evidence CONTROLLED_REMOTE_RUNTIME; production readiness MORE_EVIDENCE_NEEDED) |
| Day94 | Agent + MCP Integration Capstone and English Interview | ✅ Completed (guided classroom scope; 38 focused dependency-free + 1 grader + 3 SDK/restart integration tests; 761 total; 16/16 seed; evidence RESTART_RECOVERY_RUNTIME; production readiness MORE_EVIDENCE_NEEDED) |

Deliverables:

- A framework-agnostic Agent Runtime + a chosen framework behind a replaceable adapter + MCP client/server
  with auth, tenant isolation and a hardened remote lifecycle, composed through a runnable restart-recovery
  capstone. Framework / Job-Market Refresh at Day87; framework selection at Day88; phase acceptance at Day94.

---

# Phase 7C — Production RAG Engineering (Day95–Day106)

Status: Complete at guided classroom scope through Day106. Day95 has bounded `INTEGRATION_RUNTIME`
parser-process evidence; Day96–Day106 have deterministic chunking, authorization/provenance, embedding and
exact vector-generation, hybrid-retrieval, rewrite/reranking, evaluation, lifecycle, security and capstone
composition evidence. Day104 and Day105 additionally have bounded local PostgreSQL/pgvector Level 3 evidence.
Day106 now has append-only bounded L3A real local PostgreSQL/pgvector plus container-restart evidence and L3B
five-call real model evidence with 89/320 observed output tokens, four RELEASE decisions, one revoked BLOCKED/
NOT_ATTEMPTED decision, zero unauthorized Prompt occurrences, no dispatch, and restart/offline replay PASS.
The current deterministic/unit suite and saved-evidence replay passed on CPython 3.12.16. Real
Docker/PostgreSQL/Provider L3 re-execution on CPython 3.12, production-scale embedding/vector/query/reranker
quality, external detector/DLP, production IAM/RLS/TLS/egress, HA/restore, durable distributed storage,
independently labeled real-model evaluation, real migration behavior, load/soak, canary and production remain
NOT RUN; readiness is `MORE_EVIDENCE_NEEDED`.

Objective:
Build a runnable, evaluable Production RAG subsystem with permissions and citations — ingestion/parsing,
chunking, metadata/tenant/ACL/provenance, embeddings/index, hybrid retrieval/filtering, query
rewriting/re-ranking, grounding/citations, retrieval/answer evaluation, index migration, and RAG security —
not a chunk-and-search demo.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day95 | RAG Ingestion Pipeline, Parsing and Document Lifecycle | ✅ Completed (guided classroom scope; 60 focused tests; 16/16 seed; independent parser process; evidence INTEGRATION_RUNTIME; production readiness MORE_EVIDENCE_NEEDED) |
| Day96 | Chunking Strategy and Experiments | ✅ Completed (guided classroom scope; 25 focused tests; 16/16 seed; three validated strategies and one rejected run; evidence EXECUTED_LOCAL_RUNTIME; production readiness MORE_EVIDENCE_NEEDED) |
| Day97 | Metadata, Tenant, ACL and Provenance | ✅ Completed (guided classroom scope; 36 focused tests; 24/24 seed; signed narrow permits, guarded reads and immutable metadata/provenance evidence; EXECUTED_LOCAL_RUNTIME; production readiness MORE_EVIDENCE_NEEDED) |
| Day98 | Embedding Model Selection and Versioning | ✅ Completed (guided classroom scope; 23 focused tests; 17/17 seed; eligibility-first selection, frozen contract, whole-operation validation and immutable EmbeddingSet Committer; deterministic fake runtime; production readiness MORE_EVIDENCE_NEEDED) |
| Day99 | Vector Database and Vector Index Design | ✅ Completed (guided classroom scope; 37 focused tests; 8/8 seed; Python 3.12 CI passed; three-store official research, narrow authorization, deterministic batches, Exact/Flat and simulated recall, immutable shadow generation, manifest/readback, fencing/reconciliation; production readiness MORE_EVIDENCE_NEEDED) |
| Day100 | Hybrid Retrieval and Filtering | ✅ Completed (guided classroom scope; 64 focused tests; 8/8 seed; 1006/1006 local + Python 3.12 CI regressions; selected-bundle gate, BM25 + Exact cosine, application filter AST, weighted RRF, final authorization/provenance recheck, bounded refill/degradation and signed cursors; real Day99 unselected negative path; production readiness MORE_EVIDENCE_NEEDED) |
| Day101 | Query Rewriting and Re-ranking | ✅ Completed (guided classroom scope; 56 focused tests; 10/10 seed; 1062/1062 local + Python 3.12 CI regressions; bounded rewrite validation, Day100-per-variant retrieval, occurrence-ID fusion, strict reranker Adapter/Validator, final current authorization/provenance release and signed cache/cursor identities; deterministic fake only; production readiness MORE_EVIDENCE_NEEDED) |
| Day102 | Grounding, Citations and Source Verification | ✅ Completed (guided classroom scope; 44 focused tests; 10/10 seed; 1106/1106 local + Python 3.12 CI regressions; trusted Day101 handoff, immutable Grounding Bundle, exact Claim/Citation mapping, independent source/semantic verification, partial answers, final currentness and authority/content-bound cache identities; deterministic fake only; production readiness MORE_EVIDENCE_NEEDED) |
| Day103 | Retrieval Evaluation and RAG Answer Evaluation | ✅ Completed (guided classroom scope; 27 focused tests; 10/10 seed; 1133/1133 local full regressions on Python 3.11.5 fallback; all 19 seed evaluators and four saved replays; Python 3.12 CI NOT RUN; fixed independent refund labels, Precision/Recall/MRR/nDCG, answer/Citation/Abstention metrics, slices, hard gates and replayable evidence; deterministic fake only; production readiness MORE_EVIDENCE_NEEDED) |
| Day104 | Index Update, Delete, Rebuild and Migration | ✅ Completed (guided classroom L2 + local PostgreSQL 16.15/pgvector 0.8.7 L3; frozen L2 baseline 73/73 focused tests + 10/10 seed; final repository `Ran 1245 tests`, `OK (skipped=7)` on Python 3.11.5 fallback; all 20 seed evaluators and six saved replays; L3 32/32 adapter unit + 7/7 real integration + 17/17 runner gates + container restart replay; PR #16 Python 3.12.16 CI run `42995652875` passed the 1245-test deterministic/unit suite, all seed evaluators and saved replays without Docker; L4/HA/restore/physical purge/load/production traffic MORE_EVIDENCE_NEEDED) |
| Day105 | RAG Security: Prompt Injection, Poisoned Documents and Data-leakage Boundaries | ✅ Completed (guided classroom L2 + bounded local PostgreSQL 16.15/pgvector 0.8.7 L3; retrieved-content data-only authority, identity-bound ingestion/retrieval/context/output gates, X/Y/Z/T adversarial fixtures, exact citations/DLP/disclosure controls, cache/revocation/incident mechanics and content-safe replay; L3 20/20 repository unit + 9/9 real integration + 20/20 hard gates + 14 cases + 18 failure checkpoints + real container restart and offline replay; deterministic security adapters only; earlier append-only PR #18 CPython 3.12.16 CI passed without Docker/L3; real external detector/model/DLP/Provider integration, L4 and production readiness MORE_EVIDENCE_NEEDED) |
| Day106 | Production RAG Capstone and English Interview | ✅ PASS at recorded course/mastery scope: deterministic L2 and bounded local L3A/L3B evidence on CPython 3.11.5 (real PostgreSQL/pgvector and restart; five bounded real model calls, 89/320 observed output tokens, 4 RELEASE + 1 revoked BLOCKED/NOT_ATTEMPTED, unauthorized Prompt count 0, no dispatch, restart/offline replay PASS); append-only PR #21/post-merge CI replayed the exact L2 checkpoint on CPython 3.11.5 and separately passed the current deterministic/unit plus saved L3A/L3B replay on CPython 3.12.16 without re-executing real L3; original teacher-provided English answer remains historical TAUGHT_NOT_VERIFIED evidence, followed by independent English VERIFIED_PASS on 2026-11-24; external detector/DLP and production controls NOT RUN; readiness MORE_EVIDENCE_NEEDED |

Deliverables:

- A runnable, evaluable Production RAG subsystem: ingestion/parsing + chunking + metadata/tenant/ACL/provenance
  + embeddings/index + hybrid retrieval/filtering + query rewriting/re-ranking + grounding/citations +
  retrieval/answer evaluation + index migration + RAG security boundaries.

---

# Phase 7D — Commerce Data Foundation and Evidence-Grounded Investigation (Day107–Day113)

Status: Planned / not started

Planning evidence: `CONCEPTUAL_STATIC`. Day107–Day130 code, product repository, Provider, Docker/database,
MCP, evaluation, load, cloud and production execution are all `NOT_RUN` until separately authorized and run.

Objective:
Create one bounded **Cross-Border Commerce Intelligence Agent — Evidence-Grounded Contribution-Margin &
Anomaly Investigator**. Immutable RawSnapshots preserve imported source evidence; accepted CanonicalLedgerEntry
records are application-owned normalized analytical facts; versioned MetricContracts define calculation policy;
MetricResults and AnomalyCandidates are derived Artifacts. The bounded Agent may plan investigations, call typed
read Tools and explain exact evidence, but it may not invent numbers or become business authority. This is not
a legal accounting or tax ledger. Start with versioned synthetic data; sanitized real data is optional
integration evidence, while domain-user validation is recorded separately.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day107 | Customer Discovery, Scope Freeze, Metric Contracts, Threat Model and Product Repository Skeleton | Planned / not started |
| Day108 | Async FastAPI/PostgreSQL Import Foundation | Planned |
| Day109 | Canonical Commerce Ledger, Lineage and Reconciliation | Planned |
| Day110 | Deterministic Contribution-Margin and Anomaly Checkpoint | Planned |
| Day111 | Typed Commerce Tools, MCP Boundary and Provider Adapters | Planned |
| Day112 | Bounded Investigation Agent, Evidence Binding and Minimal React/TypeScript Workbench | Planned |
| Day113 | Runnable V0, Stakeholder Review and Independent Verification Checkpoint | Planned |

Deliverables:

- A runnable local V0 that imports one deterministic commerce fixture into an application-owned canonical
  ledger, reconciles source totals, calculates contribution margin by SKU/channel/country, detects a bounded
  anomaly and produces an evidence-grounded explanation through typed read Tools.
- Real Async FastAPI/PostgreSQL seams, one real Streamable-HTTP MCP transport, ReplayProvider plus one
  replaceable real Provider seam, and a minimal four-area workbench. Durable Worker/checkpoint/recovery
  hardening belongs to Day116. Any action recommendation remains non-authoritative; real customer paths are
  read-only.
- A discovery brief, measurable success criteria, schema/metric decisions and an initial FDE delivery narrative.

V0 uses one deterministic marketplace bundle and one primary margin-deterioration scenario, not multiple
production connectors. Day108 rejects or removes PII that is unnecessary for the frozen MetricContract.
Formula, allocation, FX or late-data changes create new revisions/runs; old evidence remains append-only.
Day113 may use an explicitly labeled simulated stakeholder review; real `DOMAIN_USER_REVIEW` evidence remains
`NOT_RUN` until an independent domain user actually participates and never blocks the technical V0 checkpoint.

---

# Phase 7E — Evaluation, Safety and Forward Deployment on Commerce Intelligence (Day114–Day123)

Status: Planned / not started

Objective:
Apply governed commerce fixtures, deterministic ledger/reconciliation graders, calibrated model-based graders,
real-model evaluation, repeated-run trajectory evaluation, adversarial/failure testing, machine release gates,
observability, bounded load/security testing and an executable data-recovery GameDay directly to the Commerce
Agent. Business-number correctness and tenant isolation are non-compensable gates.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day114 | Evaluation Dataset Engineering and Golden-set Governance | Planned |
| Day115 | Deterministic and Calibrated Model-based Graders | Planned |
| Day116 | Durable Import/Investigation Worker, Checkpoint, Resume and Recovery | Planned |
| Day117 | Bounded Real-model and Trajectory Evaluation Checkpoint | Planned |
| Day118 | Tenant, Data and Agent Adversarial Security Evaluation | Planned |
| Day119 | Approval-gated Sandbox Action Contract and UNKNOWN Reconciliation | Planned |
| Day120 | Regression Matrix and CI Release-gate Checkpoint | Planned |
| Day121 | OpenTelemetry and Cost/Quality Observability | Planned |
| Day122 | Bounded Async Load, Backpressure and Capacity Diagnosis | Planned |
| Day123 | Executable Commerce GameDay, Postmortem and Independent Defense Checkpoint | Planned |

Deliverables:

- A versioned evaluation system with honest label/IAA boundaries, exact dataset/ledger/run identities,
  deterministic financial/security graders, a calibrated optional Judge, trajectory evaluation,
  non-compensable correctness/security gates and machine-enforced CI decisions.
- Durable Worker/checkpoint/recovery evidence, OpenTelemetry, bounded latency/concurrency/cost evidence,
  schema-drift and tenant-isolation tests, deterministic sandbox-action/UNKNOWN reconciliation evidence, an
  executable recovery GameDay and append-only Postmortem. An actual external sandbox write is optional and
  separately authorized.

Day117 real-model evidence uses deterministic synthetic/test-tenant data only and requires Provider egress
allowlisting, current authorization, Prompt/data minimization and disclosure preflight before any call.
Day118 expands adversarial coverage; it is not the first establishment of security boundaries.

---

# Phase 8 — Cloud Integration, FDE Delivery and Employment Readiness (Day124–Day130)

Status: Planned / not started

Objective:
Turn the bounded Commerce Agent into reproducible local and bounded-cloud portfolio evidence, an FDE-style
discovery-to-delivery case study and independently defensible employment material without claiming that a
public URL, synthetic fixture or one domain-user review is production.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day124 | Bounded Cloud Deployment: Managed Data, Secrets, Container Release and HTTPS | Planned |
| Day125 | Second Commerce Schema Adapter and Onboarding Proof | Planned |
| Day126 | Public Smoke, Operational Runbook and Cumulative Operations Checkpoint | Planned |
| Day127 | Simulated Forward Deployment Drill: Discovery to Handoff | Planned |
| Day128 | FDE/AI Backend System Design and Timed Python/SQL/English Interview | Planned |
| Day129 | Portfolio, Demo, Behavioral STAR Bank, Résumé and Application Iteration | Planned |
| Day130 | Final FDE Mock Interview, Portfolio Audit and Employment Readiness Gate Review | Planned |

Deliverables:

- Reproducible local and bounded-cloud Commerce Agent evidence, a minimal usable workbench, operational
  Runbook, data-onboarding and metric-contract documentation, cost/quality evidence, architecture/demo assets,
  interview evidence and an honest Employment Readiness review.
- One recorded domain-user review when actually obtained, or an explicitly simulated review/handoff exercise.
  Real or sanitized customer data improves the evidence boundary but is not required to begin; synthetic data,
  simulated delivery and domain review must never be presented as customer adoption or production evidence.

---

# Employment Readiness Gate

Completion is defined by passing this Gate, NOT by reaching a fixed final day. At minimum:

```text
1.  A runnable Cross-Border Commerce Intelligence product with one import-to-investigation path.
2.  A versioned import pipeline, schema mapping, validation and reconciliation.
3.  An application-owned canonical ledger, MetricContract, independently verified contribution-margin
    calculations and deterministic anomaly/abstention behavior.
4.  Async FastAPI, PostgreSQL, Alembic and durable Job/Worker integration.
5.  Bounded Agent state, typed Tools, budgets, checkpoint/resume/cancellation and failure recovery.
6.  One real Streamable-HTTP MCP integration without transferring authority to MCP or the model.
7.  ProviderAdapter plus deterministic replay and bounded real-model evidence.
8.  Exact dataset/ledger/metric/anomaly/Tool/EvidenceBundle/report identities and current authorization.
9.  Tenant isolation, Prompt/data security, disclosure and non-compensable release gates.
10. Retry/idempotency/UNKNOWN reconciliation plus a deterministic sandbox-action contract; an actual external
    write remains optional and separately authorized.
11. Deterministic, trajectory, adversarial and calibrated-Judge evaluation with numeric-truth separation.
12. Machine CI gates, OpenTelemetry, latency/concurrency/cost/quality and GameDay evidence.
13. Reproducible local and bounded-cloud execution with honest execution labels.
14. Discovery, feedback, V1-to-V2 iteration, handoff rehearsal and a reusable second-schema Adapter proof.
15. Python/SQL, system-design, Chinese/English demo, behavioral stories, portfolio, résumé and application
    feedback.
```

Redis/Celery/Object Storage, Playwright, n8n, multi-agent, a second Provider, three production commerce
connectors, Kubernetes and a real write action are not mandatory keywords. pgvector/RAG is used only when a
real metric-definition, policy or evidence-retrieval requirement justifies it; relational queries and the
canonical ledger remain authoritative for numbers.

Decision 008 already permits honest limited applications based on completed evidence; applications do not
have to wait for the final product. Day113 may expand Commerce/FDE-targeted applications only if its runnable
checkpoint, README, CI and evidence actually pass. The curriculum improves competitiveness but does not
promise an offer; completion is not fabricated as Senior/Staff production or customer-delivery experience.

---

# Knowledge Chain (Day42 → current horizon Day130, competency-gated)

```text
Day42 Data Ownership and Failure Contracts
    -> Production AI API foundations (Phase 4)
    -> Real local integration and permissioned browser tooling (Phase 5)
    -> n8n orchestration boundaries (Phase 6)
    -> LLM Application Runtime (Phase 7A)
    -> Agent Runtime + MCP (Phase 7B)
    -> Production RAG (Phase 7C)
    -> Commerce Data Foundation and Evidence-Grounded Investigation (Phase 7D, Day107–113)
    -> Evaluation, Safety and Forward Deployment on Commerce Intelligence (Phase 7E, Day114–123)
    -> Cloud Integration, FDE Delivery and Employment Readiness (Phase 8, Day124–130)
    -> Portfolio + real job applications (Employment Readiness Gate)
```

The completed FastAPI, Playwright, n8n, Agent/MCP and RAG phases remain historical capability evidence.
Playwright, n8n, multi-agent and unrelated infrastructure are not forced into the Commerce Agent. The future
Commerce product belongs in a separate repository only after explicit implementation authorization; this
planning update does not create it. Daily implementation will use Ticket + PR + DoD, while this handbook
remains the curriculum/mastery source of truth and updates canonical status at checkpoints.

# Employment-Readiness Boundary

This curriculum builds core AI Backend capabilities and portfolio evidence but does **not** guarantee a job,
and this training is not equivalent to years of production experience. Target roles are Junior /
Developing AI Backend Engineer, AI Startup Backend Engineer, and Backend Engineer on LLM/RAG/Agent products.
Completion does not by itself demonstrate Senior or Staff level. Phases 4–8 carry a cross-cutting
employment-readiness thread (Python/SQL practice, English technical explanation, system-design communication,
runtime validation evidence, weekly README + interview review) whose goal is accumulated capability evidence,
not an offer guarantee. Testing and observability are continuous engineering disciplines from Day43, not
end-of-phase add-ons: baseline tests, structured logging, correlation IDs (`job_id`/`trace_id`/`attempt_id`),
and validation evidence begin on Day43 and evolve with every Engineering Artifact, so Day57 advances an
existing test suite and Day58 integrates existing observability rather than starting them. Every
implementation day adds proportionate tests and validation evidence; no phase accumulates untested code and
postpones correctness to its Capstone (see `CURRICULUM.md`, Cross-cutting Engineering Discipline).

---
