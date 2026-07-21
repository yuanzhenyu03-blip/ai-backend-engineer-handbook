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
| Day32 | SQL Joins, Aggregation, and Operational Queries | Planned |
| Day33 | PostgreSQL Transactions and Atomic State Changes | Planned |
| Day34 | Concurrency Control, MVCC, and Worker Claims | Planned |
| Day35 | PostgreSQL Indexes and Query Planning | Planned |
| Day36 | Schema Evolution and Safe Migrations | Planned |
| Day37 | PostgreSQL Production Reliability | Planned |

## Redis and Capstone

| Day | Topic | Status |
|------|-------------------------------|-----------|
| Day38 | Redis Foundations and Data Structures | Planned |
| Day39 | Redis Cache Design and Consistency | Planned |
| Day40 | Redis Messaging and Queue Semantics | Planned |
| Day41 | Redis Coordination and Production Safety | Planned |
| Day42 | Backend Data Design Capstone | Planned |

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

# Phase 4 — FastAPI

Topics:

- Routing
- Dependency Injection
- Pydantic
- Authentication
- SQLAlchemy
- Alembic
- Background Tasks
- Testing

Deliverables:

- Production-ready FastAPI Backend

---

# Phase 5 — Playwright

Topics:

- Browser Automation
- Browser Context
- Page
- Locator
- Async API
- Scraping
- Login Automation

Deliverables:

- Automation Projects

---

# Phase 6 — n8n

Topics:

- Workflow Automation
- FastAPI Integration
- Playwright Integration
- AI Workflow

Deliverables:

- AI Workflow Projects

---

# Phase 7 — AI Agent Engineering

Topics:

- MCP
- Tool Calling
- Function Calling
- RAG
- Memory
- OpenAI SDK

Deliverables:

- AI Agent Backend

---

# Phase 8 — Interview Preparation

Topics:

- Python
- FastAPI
- Playwright
- Docker
- Redis
- PostgreSQL
- System Design
- Behavioral Interview
- English Interview

Deliverables:

- Complete GitHub Portfolio
- Mock Interviews
- Resume
