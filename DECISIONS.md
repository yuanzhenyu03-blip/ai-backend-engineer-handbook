# DECISIONS.md

# Decision Log

This file records important technical and curriculum decisions.

These decisions help Codex, ChatGPT, and future contributors understand why the project is designed this way.

---

## Decision 001 — GitHub as the Single Source of Truth

Status: Accepted

Date: 2026-07-02

### Context

Chat is useful for teaching and discussion, but Codex cannot reliably continue from chat history.

### Decision

All final lessons, project files, prompts, standards, and status documents must live in GitHub.

### Consequence

- Chat becomes discussion material.
- GitHub becomes the source of truth.
- Codex can continue work by reading repository files.

---

## Decision 002 — Notion as Reading Layer, Not Source of Truth

Status: Accepted

Date: 2026-07-02

### Context

Notion is good for reading and review, but code assistants work better with GitHub repositories.

### Decision

Use Notion as the learning dashboard and reading layer.

Use GitHub for all canonical content.

---

## Decision 003 — Python Design Before FastAPI

Status: Accepted

Date: 2026-07-02

### Context

The student already understands basic Python syntax but needs deeper engineering thinking.

### Decision

Teach Python design topics first:

- Object Model
- References
- Mutable vs Immutable
- Generator
- Decorator
- Context Manager
- Async/Await

### Consequence

FastAPI and Playwright will be easier to understand later because their design relies heavily on Python's object model.

---

## Decision 004 — FastAPI + Playwright as Core, n8n as Integration Layer

Status: Accepted

Date: 2026-07-02

### Context

n8n is useful for automation workflows, but overseas engineering jobs still require coding ability.

### Decision

Use FastAPI and Playwright as core engineering skills.

Use n8n later as an orchestration and workflow layer.

---

## Decision 005 — Every Lesson Must Connect Theory, Enterprise Practice, and Interview

Status: Accepted

Date: 2026-07-02

### Decision

Every lesson must include:

- Theory
- Memory Model
- Engineering Thinking
- Enterprise Practice
- Interview Questions
- Tech Lead Review
- CTO Thinking
- Cheat Sheet

### Consequence

The project is not a tutorial. It is an interview-ready engineering handbook.

---

## Decision 006 — AI Backend Product Thread Across Day43–Day100

Status: Accepted

Date: 2026-07-26

### Context

After Day42 closes the Phase 3 data-ownership and failure model, the remaining curriculum (Day43–Day100)
could easily degrade into a set of unrelated framework tutorials (FastAPI, then Playwright, then n8n, then
"AI" bolted on at the end). That would not produce an employable AI Backend Engineer or a coherent,
demonstrable portfolio.

### Decision

Day43–Day100 is planned as a single continuous **AI Backend product capability chain**, not isolated
framework tutorials. All phases build one unified production scenario — a **Multi-tenant AI Research and
Automation Platform** — reusing the existing project directories rather than creating new ones.

The capability chain is:

```text
Day42 Data Ownership and Failure Contracts
    -> FastAPI Production AI API (Phase 4)
    -> Playwright Browser Automation / Agent Tool (Phase 5)
    -> n8n Workflow Integration (Phase 6)
    -> AI Agent + Tool Calling + MCP + RAG + Memory + Evaluation (Phase 7)
    -> Final Production Capstone (Phase 8)
    -> Portfolio + Overseas Interview
```

Specific decisions:

- **Not isolated framework tutorials.** Every phase extends the same runnable backend and the same durable
  data-ownership model, so capability compounds instead of resetting each phase.
- **FastAPI and Playwright are core engineering skills; n8n is an integration layer.** This continues
  Decision 004. n8n orchestrates correct backends; it never replaces backend code or backend correctness,
  and durable truth stays in PostgreSQL.
- **AI enters the scenario from Phase 4, not only at the end.** From Phase 4 onward every phase is framed
  around a real AI backend scenario (AI Job API, provider boundaries, streaming, agent tools, RAG, MCP,
  evaluation), rather than deferring all AI to the final days.
- **Runtime evidence, evaluation, and portfolio are completion conditions.** A phase or capstone is complete
  only with real, saved evidence: runnable code, tests, runtime traces, evaluation datasets/reports, and
  failure/recovery drills. Conceptual/static review is distinguished from executed runtime/production
  validation, and production-grade claims require executed, recorded evidence.
- **The goal is employment readiness, not an offer guarantee.** The curriculum targets Junior / Developing
  AI Backend Engineer, AI Startup Backend Engineer, and Backend Engineer on LLM/RAG/Agent products. It does
  not guarantee a job, and 100 days is not equivalent to years of production experience or to Senior/Staff
  level.

### Consequence

Day43–Day100 in `CURRICULUM.md` and `ROADMAP.md` are planned as phases of one product thread with explicit
deliverables and validation requirements. Future days remain `Planned` and are not expanded into full
lessons until they become the current lesson; no future lesson files or new project directories are created
by this planning decision.
