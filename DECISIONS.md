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
