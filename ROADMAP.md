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
| Day59 | Real FastAPI Runtime, PostgreSQL and Alembic Integration | Planned |
| Day60 | Outbox, Redis/Celery Broker and Worker Recovery Integration | Planned |
| Day61 | Object Storage, Provider Adapter and OpenTelemetry End-to-End Evidence | Planned |
| Day62 | Playwright Runtime, Locators and Reliable Async Interaction | Planned |
| Day63 | Browser Authentication, Storage State and Tenant Isolation | Planned |
| Day64 | Dynamic Extraction, Network Events and Artifact Evidence | Planned |
| Day65 | Browser Failure Recovery and Security Boundaries | Planned |
| Day66 | Queue-backed Playwright Worker as a Permissioned AI Tool | Planned |

Deliverables:

- Real local INTEGRATION_RUNTIME evidence for the Phase 4 backend (FastAPI + PostgreSQL + Redis/Celery +
  Object Storage + Provider + OpenTelemetry) + an isolated, recoverable, auditable Playwright browser worker
  exposed as a permissioned AI tool.

---

# Phase 6 — n8n AI Workflow Integration (Day67–Day70)

Objective:
Use n8n to orchestrate the now-real API, the permissioned browser tool, and AI capabilities as an
integration/workflow layer — not a low-code replacement for backend correctness. Durable truth stays in
PostgreSQL.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day67 | n8n Workflow Model, Triggers, FastAPI Integration and Responsibility Boundaries | Planned |
| Day68 | Long-running AI Jobs: Polling, Callback, Correlation and Idempotency | Planned |
| Day69 | Human Approval, Retry, Secrets, Audit and Error Workflows | Planned |
| Day70 | n8n + FastAPI + AI Tool Integration Capstone and Interview | Planned |

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
ecosystem changes, learner weak points, and interview feedback. Completed lessons (Day01–Day58) stay fixed;
only Planned lessons may be renumbered. The AI core is not compressed to keep a tidy number, and the agent
runtime framework is chosen only after an explicit Framework / Job-Market Refresh, behind a replaceable adapter.

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
Phase 7D: Day110, Day113, Day116
Phase 8:  Day120, Day124, Day127, Day130
```

No new lesson numbers are added for Checkpoints; they run on the existing Days above (max gap ≤ 6 lessons).

---

# Phase 7A — LLM Application Engineering (Day71–Day78)

Objective:
Evolve a single Provider call (Day53–58) into a complete, testable LLM Application Runtime: architecture,
tokens/context/sampling and failure modes, a replaceable Provider Adapter, prompt contracts/versioning,
structured output/function calling, streaming/caching/batching, model routing/fallback/cost, and
fake-Provider contract/regression tests.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day71 | LLM Application Architecture, Tokens, Context, Sampling and Model Failure Modes | Planned |
| Day72 | Provider Capabilities and the Replaceable Provider Adapter | Planned |
| Day73 | Prompt Contracts, Prompt Versioning and Compatibility | Planned |
| Day74 | Structured Output, JSON Schema and Function/Tool Calling | Planned |
| Day75 | Streaming, Caching and Batching for LLM Applications | Planned |
| Day76 | Model Routing, Fallback, Latency and Cost Engineering | Planned |
| Day77 | Fake Provider, Contract Tests and LLM Regression Tests | Planned |
| Day78 | LLM Application Runtime Capstone, Checkpoint and English Interview | Planned |

Deliverables:

- A testable LLM Application Runtime behind a replaceable Provider Adapter, with prompt contracts, structured
  output/function calling, streaming/caching/batching, model routing/cost, and fake-Provider tests.

---

# Phase 7B — Agent Runtime and MCP Engineering (Day79–Day94)

Objective:
Build a framework-agnostic Agent Runtime (loop, tools/permissions, state machine, budgets, durable jobs,
human approval, memory vs business-state, multi-agent, security), then run a Framework / Job-Market Refresh,
choose a framework behind a replaceable adapter, and engineer MCP client/server, auth/tenant isolation, and
the remote-MCP lifecycle. Understand the stable contracts first; the framework is replaceable infrastructure,
not the business model. Do not pre-lock LangGraph.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day79 | Framework-agnostic Agent Loop and Control Flow | Planned |
| Day80 | Tool Registry, Tool Schema and Permission Model | Planned |
| Day81 | Agent State Machine, Termination, Loop Detection and Step/Token/Cost Budgets | Planned |
| Day82 | Durable Agent Jobs, Checkpoint, Resume and Recovery | Planned |
| Day83 | Human Approval, Interrupt and Escalation Boundaries | Planned |
| Day84 | Conversation Memory vs Durable Business-state Boundaries | Planned |
| Day85 | Multi-agent Handoff and Coordination Boundaries | Planned |
| Day86 | Agent Security: Prompt Injection, Tool Abuse, Data Exfiltration and Sandboxing | Planned |
| Day87 | Agent Framework and Job-Market Refresh Checkpoint | Planned |
| Day88 | Agent Runtime Framework Selection Behind a Replaceable Adapter | Planned |
| Day89 | MCP Foundations and Protocol Model | Planned |
| Day90 | MCP Client Engineering | Planned |
| Day91 | MCP Server Engineering: Resources, Tools and Prompts Responsibility Boundaries | Planned |
| Day92 | MCP Authentication, Authorization and Tenant Isolation | Planned |
| Day93 | Remote MCP Lifecycle: Timeout, Retry, Versioning and Observability | Planned |
| Day94 | Agent + MCP Integration Capstone and English Interview | Planned |

Deliverables:

- A framework-agnostic Agent Runtime + a chosen framework behind a replaceable adapter + MCP client/server
  with auth, tenant isolation, and a hardened remote lifecycle. Framework / Job-Market Refresh at Day87;
  framework selection at Day88.

---

# Phase 7C — Production RAG Engineering (Day95–Day106)

Objective:
Build a runnable, evaluable Production RAG subsystem with permissions and citations — ingestion/parsing,
chunking, metadata/tenant/ACL/provenance, embeddings/index, hybrid retrieval/filtering, query
rewriting/re-ranking, grounding/citations, retrieval/answer evaluation, index migration, and RAG security —
not a chunk-and-search demo.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day95 | RAG Ingestion Pipeline, Parsing and Document Lifecycle | Planned |
| Day96 | Chunking Strategy and Experiments | Planned |
| Day97 | Metadata, Tenant, ACL and Provenance | Planned |
| Day98 | Embedding Model Selection and Versioning | Planned |
| Day99 | Vector Database and Vector Index Design | Planned |
| Day100 | Hybrid Retrieval and Filtering | Planned |
| Day101 | Query Rewriting and Re-ranking | Planned |
| Day102 | Grounding, Citations and Source Verification | Planned |
| Day103 | Retrieval Evaluation and RAG Answer Evaluation | Planned |
| Day104 | Index Update, Delete, Rebuild and Migration | Planned |
| Day105 | RAG Security: Prompt Injection, Poisoned Documents and Data-leakage Boundaries | Planned |
| Day106 | Production RAG Capstone and English Interview | Planned |

Deliverables:

- A runnable, evaluable Production RAG subsystem: ingestion/parsing + chunking + metadata/tenant/ACL/provenance
  + embeddings/index + hybrid retrieval/filtering + query rewriting/re-ranking + grounding/citations +
  retrieval/answer evaluation + index migration + RAG security boundaries.

---

# Phase 7D — AI Evaluation, Safety and Operations (Day107–Day116)

Objective:
Turn evaluation, safety, and operations into an executable engineering system: datasets/golden sets,
deterministic and model-based graders, retrieval/answer/trajectory/tool-use evaluation, adversarial and
failure-mode evaluation, regression/release gates, AI observability (cost/latency/quality, routing evidence),
load/security testing, and a production incident/rollback/repair exercise.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day107 | Evaluation Datasets and Golden Sets | Planned |
| Day108 | Deterministic Graders | Planned |
| Day109 | Model-based Graders and Their Limits | Planned |
| Day110 | Retrieval and Answer-quality Evaluation | Planned |
| Day111 | Agent Trajectory and Tool-use Correctness Evaluation | Planned |
| Day112 | Adversarial and Failure-mode Evaluation | Planned |
| Day113 | Prompt/Model/Tool Regression and Release Gates | Planned |
| Day114 | AI Observability: Cost, Latency, Quality Trade-offs and Model-routing Evidence | Planned |
| Day115 | Load Testing and AI Security Testing | Planned |
| Day116 | Production Incident, Rollback and Repair Exercise, Capstone and English Interview | Planned |

Deliverables:

- An executable AI Evaluation/Safety/Operations system: datasets/golden sets + deterministic and model-based
  graders + retrieval/answer/trajectory/tool-use evaluation + adversarial/failure-mode evaluation +
  regression/release gates + AI observability + load/security testing + an incident/rollback/repair exercise.

---

# Phase 8 — Final Employment Capstone (Day117–Day130)

Objective:
Assemble all capabilities into one deployable, demonstrable AI Backend, convert it into employment evidence,
and review readiness against the Employment Readiness Gate. The capstone is a thin vertical integration loop,
not a one-day re-implementation.

Implementation boundaries (Day117 updates `projects/final-capstone/README.md` and is placeholder-until-then;
Day123 is a thin end-to-end vertical integration of already-built components, not a re-implementation day;
Day125 uses limited, representative drills rather than exhaustive failure enumeration) are recorded in
`CURRICULUM.md` under "Future Lesson Implementation Boundaries."

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day117 | Product Requirements, Architecture Review and Scope Control | Planned |
| Day118 | Final Capstone Skeleton, Contracts and Threat Model | Planned |
| Day119 | FastAPI + PostgreSQL + Redis/Celery + Object Storage Integration | Planned |
| Day120 | Agent Runtime and MCP Integration | Planned |
| Day121 | Production RAG Integration (ACL, Citations, Retrieval Evaluation) | Planned |
| Day122 | Playwright Permissioned Tool and n8n Human-approval Integration | Planned |
| Day123 | Thin Vertical Integration Loop (End-to-end) | Planned |
| Day124 | Evaluation Gate and Release Decision Integration | Planned |
| Day125 | Failure Recovery, Load, Security and Data-repair Drills | Planned |
| Day126 | Cloud Deployment, Managed Services, Production Configuration and SLOs | Planned |
| Day127 | Observability, Operational Runbook and Cost/Quality Evidence | Planned |
| Day128 | AI Backend System Design and Python/SQL Coding Interview | Planned |
| Day129 | English Project Story, Behavioral Interview, Resume and Open-source Evidence | Planned |
| Day130 | Final Mock Interview, Portfolio Review and Employment Readiness Gate Review | Planned |

Deliverables:

- A deployable Production AI Backend capstone, a complete GitHub portfolio, and English system-design/
  behavioral/resume readiness, reviewed against the Employment Readiness Gate. Reaching Day130 is not itself
  completion — passing the Gate is.

---

# Employment Readiness Gate

Completion is defined by passing this Gate, NOT by reaching a fixed final day. At minimum:

```text
1.  A real, runnable, deployable AI Backend.
2.  Real FastAPI / PostgreSQL / Redis-Celery / Object Storage integration evidence.
3.  An Agent Runtime with explicit state, termination, permission, checkpoint and recovery semantics.
4.  A run MCP Client/Server integration.
5.  A Production RAG with ACL, citations and retrieval evaluation.
6.  Tool permissions and prompt-injection defenses.
7.  Evaluation datasets, graders and a release gate.
8.  AI latency / cost / quality evidence.
9.  Observability, failure, rollback and repair evidence.
10. A reproducible README and run commands.
11. Python and SQL interview capability.
12. Backend / AI system-design capability.
13. English project explanation and behavioral interview stories.
14. Portfolio and resume evidence.
15. Real job applications submitted, with Planned lessons added based on feedback.
```

Trial applications may begin once the Agent + MCP evidence in Phase 7B is complete — not only after the Final
Capstone. The curriculum improves competitiveness but does not promise an offer; target roles are
Junior/Developing AI Backend Engineer, AI Startup Backend Engineer, and Backend Engineer on LLM/RAG/Agent
products; completion is not fabricated as Senior/Staff production experience.

---

# Knowledge Chain (Day42 → current horizon Day130, competency-gated)

```text
Day42 Data Ownership and Failure Contracts
    -> FastAPI Production AI API — deterministic in-process EXECUTED_LOCAL_RUNTIME evidence (Phase 4, ends Day58)
    -> Real local integration gate — FastAPI + PostgreSQL + Redis/Celery + Object Storage + Provider + OpenTelemetry (Phase 5, Day59–61)
    -> Playwright browser automation as a permissioned, queue-backed AI tool (Phase 5, Day62–66)
    -> n8n Workflow Integration — orchestration over correct backends (Phase 6, Day67–70)
    -> LLM Application Runtime (Phase 7A, Day71–78)
    -> Agent Runtime + MCP (Phase 7B, Day79–94; Framework/Job-Market Refresh at Day87, framework chosen Day88 behind a replaceable adapter)
    -> Production RAG (Phase 7C, Day95–106)
    -> AI Evaluation, Safety and Operations (Phase 7D, Day107–116)
    -> Final Employment Capstone + employment evidence (Phase 8, Day117–130)
    -> Portfolio + real job applications (Employment Readiness Gate; horizon extends if the Gate is not yet met)
```

FastAPI and Playwright are the core engineering skills; n8n is the integration layer and does not replace
backend code. From Phase 4 onward every phase is built around a real AI backend scenario — a **Multi-tenant
AI Research and Automation Platform** — reusing the existing project directories (`fastapi-todo`,
`fastapi-auth`, `fastapi-playwright`, `playwright-login`, `playwright-scraper`, `n8n-workflows`, `ai-agent`,
`final-capstone`, `ai-backend-data-layer`) rather than creating new ones.

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
