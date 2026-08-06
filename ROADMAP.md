# AI Backend Engineer Roadmap

## Goal

Become an overseas AI Backend Engineer capable of building production-ready AI systems, passing technical interviews, and contributing to real-world backend projects.

Estimated Duration: 100 Days

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
| Day57 | AI Backend Testing, Fake Providers, Contract Tests and Failure Injection | Planned |
| Day58 | Production AI API Capstone, Observability and English Interview | Planned |

Deliverables:

- A runnable FastAPI AI Job backend with PostgreSQL/SQLAlchemy/Alembic, Redis/Outbox/Worker, an Object
  Storage boundary, an OpenAI-compatible provider adapter, auth/tenant isolation, and tests + runtime evidence.

---

# Phase 5 — Playwright Browser Automation and Agent Tools (Day59–Day68)

Objective:
Build Playwright into an isolated, recoverable, auditable Browser Worker and Agent Tool the AI backend can
call — not a fragile click script. Do not teach bypassing website security, captchas, or anti-automation.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day59 | Playwright Runtime Model: Browser, Context, Page and Async Lifecycle | Planned |
| Day60 | Locator, Auto-waiting and Reliable Interaction | Planned |
| Day61 | Authentication, Storage State and Browser Context Isolation | Planned |
| Day62 | Dynamic-page Extraction and Structured Output | Planned |
| Day63 | Network Events, Downloads, Uploads and Artifact Evidence | Planned |
| Day64 | Timeouts, Retries, Diagnostics, Screenshots and Error Recovery | Planned |
| Day65 | Browser Security, SSRF, Credentials, Website Policy and Prompt-injection Boundaries | Planned |
| Day66 | Queue-backed Browser Worker and Durable Job Integration | Planned |
| Day67 | Playwright as an AI Agent Tool | Planned |
| Day68 | FastAPI + Playwright Production Capstone and English Interview | Planned |

Deliverables:

- An isolated, recoverable, auditable Playwright Browser Worker + Agent Tool integrated with the FastAPI backend.

---

# Phase 6 — n8n AI Workflow Orchestration (Day69–Day74)

Objective:
Use n8n to orchestrate the existing API and AI capabilities as an integration/workflow layer — not a
low-code replacement for backend correctness. Durable truth stays in PostgreSQL.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day69 | n8n Workflow Model, Triggers, Nodes and Responsibility Boundaries | Planned |
| Day70 | Webhooks, Schedules, FastAPI Integration and Authentication | Planned |
| Day71 | Long-running AI Jobs: Polling, Callback, Correlation and Idempotency | Planned |
| Day72 | Human Approval and AI-assisted Business Workflows | Planned |
| Day73 | Retry, Error Workflow, Secrets, Audit and Production Operations | Planned |
| Day74 | n8n + FastAPI + AI Workflow Capstone and Interview | Planned |

Deliverables:

- n8n workflows orchestrating the FastAPI AI backend and browser tools, with idempotent long-job handling and audit.

---

# Phase 7 — AI Agent, RAG, MCP and Evaluation Engineering (Day75–Day90)

Objective:
Build a testable, constrained, recoverable Production AI Agent Backend: tool calling, MCP, RAG, vector
retrieval, memory, security boundaries, and automated evaluation with runtime traces.

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day75 | LLM Application Architecture, Tokens, Context and Model Failure Modes | Planned |
| Day76 | Prompt Contracts, Structured Output and Function Calling | Planned |
| Day77 | Tool Registry, Tool Schemas, Permissions and Execution Boundaries | Planned |
| Day78 | Agent Loop, State, Termination, Retry and Error Handling | Planned |
| Day79 | MCP Foundations: Client, Server, Resources and Tools | Planned |
| Day80 | MCP Authentication, Authorization, Security and Production Operations | Planned |
| Day81 | RAG Ingestion: Parsing, Chunking, Metadata and Provenance | Planned |
| Day82 | Embeddings, Vector Database and Index Design | Planned |
| Day83 | Retrieval Quality: Hybrid Search, Filtering and Re-ranking | Planned |
| Day84 | Grounding, Citations, Hallucination Boundaries and Source Verification | Planned |
| Day85 | Conversation Memory and Durable Memory Boundaries | Planned |
| Day86 | Prompt Injection, Tool Abuse, Data Exfiltration and Sandboxing | Planned |
| Day87 | Durable Agent Jobs, Checkpoints, Recovery and Human Escalation | Planned |
| Day88 | Evaluation Datasets, Golden Sets, Graders, Trials and Traces | Planned |
| Day89 | AI Observability, Cost, Model Routing, Regression and Release Gates | Planned |
| Day90 | Production AI Agent Backend Capstone and English Interview | Planned |

Deliverables:

- An AI Agent Backend with Tool Calling, MCP, RAG, Vector Retrieval, Memory, security boundaries, automated
  evaluation, and runtime traces.

---

# Phase 8 — Final Capstone, Portfolio and Overseas Interview (Day91–Day100)

Objective:
Convert all capabilities into deployable, demonstrable, interview-ready employment evidence.

Implementation boundaries (Day91 updates `projects/final-capstone/README.md` and is placeholder-until-then;
Day94 is a thin end-to-end vertical integration of already-built components, not a re-implementation day;
Day95 uses limited, representative drills rather than exhaustive failure enumeration) are recorded in
`CURRICULUM.md` under "Future Lesson Implementation Boundaries."

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day91 | Product Requirements, Architecture Review and Scope Control | Planned |
| Day92 | Final Capstone Skeleton, Contracts and Threat Model | Planned |
| Day93 | FastAPI + PostgreSQL + Redis + Object Storage Integration | Planned |
| Day94 | Agent + RAG + MCP + Playwright + n8n Integration | Planned |
| Day95 | Failure Recovery, Load, Security and Data-repair Drills | Planned |
| Day96 | Cloud Deployment, Managed Services and Production Configuration | Planned |
| Day97 | Evaluation Report, Observability, SLO and Operational Runbook | Planned |
| Day98 | AI Backend System Design and Python/SQL Coding Interview | Planned |
| Day99 | English Project Story, Behavioral Interview, Resume and Open-source Evidence | Planned |
| Day100 | Final Mock Interview, Portfolio Review and Job-application Readiness | Planned |

Deliverables:

- A deployable Production AI Backend capstone, a complete GitHub portfolio, and English system-design/
  behavioral/resume readiness for overseas AI Backend Engineer applications.

---

# Knowledge Chain (Day42 → Day100)

```text
Day42 Data Ownership and Failure Contracts
    -> FastAPI Production AI API (Phase 4)
    -> Playwright Browser Automation / Agent Tool (Phase 5)
    -> n8n Workflow Integration (Phase 6)
    -> AI Agent + Tool Calling + MCP + RAG + Memory + Evaluation (Phase 7)
    -> Final Production Capstone (Phase 8)
    -> Portfolio + Overseas Interview
```

FastAPI and Playwright are the core engineering skills; n8n is the integration layer and does not replace
backend code. From Phase 4 onward every phase is built around a real AI backend scenario — a **Multi-tenant
AI Research and Automation Platform** — reusing the existing project directories (`fastapi-todo`,
`fastapi-auth`, `fastapi-playwright`, `playwright-login`, `playwright-scraper`, `n8n-workflows`, `ai-agent`,
`final-capstone`, `ai-backend-data-layer`) rather than creating new ones.

# Employment-Readiness Boundary

This curriculum builds core AI Backend capabilities and portfolio evidence but does **not** guarantee a job,
and 100 days of training is not equivalent to years of production experience. Target roles are Junior /
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
