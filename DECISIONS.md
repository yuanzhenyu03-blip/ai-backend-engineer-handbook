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
- **Testing and observability are continuous engineering disciplines from Day43, not end-of-phase add-ons.**
  Baseline tests, structured logging, and correlation IDs begin on Day43 and evolve with every Engineering
  Artifact; every implementation day adds proportionate tests and validation evidence.
- **The goal is employment readiness, not an offer guarantee.** The curriculum targets Junior / Developing
  AI Backend Engineer, AI Startup Backend Engineer, and Backend Engineer on LLM/RAG/Agent products. It does
  not guarantee a job, and 100 days is not equivalent to years of production experience or to Senior/Staff
  level.

### Consequence

Day43–Day100 in `CURRICULUM.md` and `ROADMAP.md` are planned as phases of one product thread with explicit
deliverables and validation requirements. Future days remain `Planned` and are not expanded into full
lessons until they become the current lesson; no future lesson files or new project directories are created
by this planning decision.

---

## Decision 007 — Rebalance Day59–Day90 After the Phase 4 Evidence Audit

Status: Accepted

Date: 2026-08-08

### Context

Phase 4 (Day43–Day58) delivered the AI Job backend as deterministic, in-process EXECUTED_LOCAL_RUNTIME
models with real tests, but every real runtime integration — a real FastAPI process, real PostgreSQL/Alembic,
a real Redis/Celery broker and Worker, real Object Storage, the real Provider adapter, and a real
OpenTelemetry exporter — was honestly recorded as NOT RUN. The previous Day59–Day90 plan spent 10 days on
Playwright and 6 on n8n before ever running the backend for real, and compressed Agent/RAG/MCP/Evaluation —
the actual target-role skills — into 16 days.

### Evidence gap

The backend's correctness was proven only as in-process control flow. No committed-DB evidence from a real
connection, no real broker redelivery/Worker-kill recovery, no real storage/provider/telemetry end-to-end
trace existed. Building browser automation and workflow layers on top of an unintegrated backend would stack
new capability on unproven runtime foundations.

### Options considered

1. Keep the old plan (10 days Playwright, 6 days n8n, 16 days Agent) and defer real integration to the final
   capstone. Rejected: postpones correctness and over-claims a "production" capstone at the end.
2. Delete Playwright/n8n. Rejected: browser automation and workflow orchestration are real, employable
   backend-adjacent skills and part of the product thread.
3. Insert a real integration gate first, compress Playwright and n8n to their essentials, and expand
   Agent/RAG/MCP/Evaluation. Chosen.

### Decision

Rebalance Day59–Day90 into: Phase 5 — Production Runtime Integration and Browser Tool Engineering (Day59–66,
with Day59–61 a **Production Integration Gate** that inherits the Phase 4 models/tests and executes the
previously NOT-RUN real local integration); Phase 6 — n8n AI Workflow Integration (Day67–70); Phase 7 — AI
Agent, RAG, MCP and Evaluation Engineering (Day71–90). Phase 8 (Day91–100) is unchanged. Phase 4 still ends
at Day58; Day59–61 are NOT retconned into Phase 4.

### Why Playwright is retained but compressed (10 -> 5 days)

Playwright stays as a real, isolated, recoverable, permissioned browser tool (Day62–66), but the object-model
and interaction material is compressed to five days because the durable job-lifecycle, isolation, security,
and evidence disciplines it needs are already established in Phases 3–4 and reused rather than re-taught.

### Why n8n is compressed (6 -> 4 days)

n8n is an integration/orchestration layer over correct backends, not backend correctness itself. Four days
(Day67–70) cover the workflow model, long-job polling/callback/idempotency, human approval/retry/secrets/
audit, and a capstone — enough to orchestrate the now-real backend without inflating a low-code layer.

### Why Agent/RAG/MCP/Evaluation is expanded (16 -> 20 days)

These are the actual target-role skills (LLM/RAG/Agent product backend). Twenty days (Day71–90) give proper
room to prompt contracts, a framework-agnostic agent loop, MCP client/server and security, RAG ingestion/
embeddings/retrieval/grounding, memory and business-state boundaries, agent security, durability, multi-agent
orchestration, and automated evaluation with runtime traces.

### Why the Day59–61 gate was added

It converts Phase 4's honest NOT-RUN integration boundaries into real local INTEGRATION_RUNTIME evidence
before any new capability is layered on top, so browser, workflow, and agent work all run on a backend that
has actually executed against real infrastructure.

### Framework selection deferred to Day75

The agent runtime framework (LangGraph / OpenAI Agents SDK / PydanticAI) is deliberately NOT locked now.
Day74 builds a framework-agnostic minimal agent loop; Day75 compares the options and records the choice as a
future Decision, behind a replaceable adapter, keeping the Domain/Tool/Memory/Job/Provider contracts
framework-agnostic.

### Consequence

- `CURRICULUM.md` and `ROADMAP.md` Day59–90 are re-scoped with the new phase boundaries, topics, and
  connections; Day43–58 and Day91–100 are unchanged; the existing Future Lesson Implementation Boundaries are
  preserved.
- Future days remain `Planned`. This decision creates no future lesson files, no new project directories, and
  no Day59+ code; existing project directories are reused.
- No production validation is executed or claimed by this planning decision.

### Validation honesty

This is a curriculum-planning and status decision only. Day59–61 will produce EXECUTED local
INTEGRATION_RUNTIME evidence when actually run and saved; it is not PRODUCTION validation. The deterministic
Day43–58 tests remain EXECUTED_LOCAL_RUNTIME evidence and are not relabeled as integration or production
evidence.
