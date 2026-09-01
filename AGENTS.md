# AGENTS.md

This repository is an AI Backend Engineer training project.

Every AI coding assistant working in this repository must follow these rules.

## Primary Goal

Help build production-quality engineering skills.

Do not optimize for short demos.

Optimize for real-world engineering.

## Coding Rules

* Python 3.12+
* Type hints are required.
* Follow PEP 8.
* Explain design decisions.
* Prefer readability over clever code.
* Never introduce mutable default arguments.
* Prefer dependency injection.
* Write modular code.
* Write production-style project structures.

## Teaching Style

When generating code:

1. Explain why.
2. Explain trade-offs.
3. Explain enterprise usage.
4. Mention common interview questions.

## Current Progress

Current state:

- Phase 4 — Production AI API Engineering: classroom scope + deterministic in-process `EXECUTED_LOCAL_RUNTIME`
  artifacts Complete. Real FastAPI/PostgreSQL/Redis-Celery/Object Storage/OpenTelemetry/Provider integration
  is NOT RUN.
- Last Completed Lesson: Day80 — Tool Registry, Tool Schema and Permission Model (Phase 7B; CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME classroom scope; 22 Day80 / 273 cumulative tests; INTEGRATION_RUNTIME/PRODUCTION NOT RUN).
- Current / Next Lesson: Day81 — Agent State Machine, Termination, Loop Detection and Step/Token/Cost Budgets (Phase 7B; Planned / not started).
- Current phase: Phase 7B — Agent Runtime and MCP Engineering is IN PROGRESS at classroom scope.

Future direction (competency-gated, NOT day-count-gated; Day130 is the current planning horizon, not a
permanent cap; see ROADMAP.md, CURRICULUM.md, and Decisions 006/007/008 in DECISIONS.md):

```text
Day59–61 Production Integration Gate
-> Day62–66 Playwright permissioned queue-backed AI tool
-> Day67–70 n8n orchestration
-> Day71–78 LLM Application Engineering
-> Day79–94 Agent Runtime + MCP
-> Day95–106 Production RAG
-> Day107–116 AI Evaluation / Safety / Operations
-> Day117–130 Final Employment Capstone
-> Employment Readiness Gate
```

Notes:

- Completion is competency-gated (the Employment Readiness Gate), not reaching a fixed day.
- Day87 runs the Agent Framework / Job-Market Refresh; Day88 selects the framework, behind a replaceable
  adapter (not pre-locked; LangGraph is a candidate only).
- Day59–Day80 are complete at their recorded evidence levels. Day81 is current/next; do not skip ahead.
- Day70 closed Phase 6. Day71 began Phase 7A on the Day53–Day61 runtime foundations. Day72–Day77 built and tested the Provider, Prompt, Output/Tool, stream/cache/batch, routing/cost and Fake/regression seams. Day78 integrated them behind one application-owned Runtime lifecycle and closed Phase 7A. Day79 added the application-owned Controller loop above that Runtime. Day80 added governed Tool visibility/schema/permission without bypassing Day74/Day66/Day78. Day81 adds explicit state, termination, loop detection and budgets.

Do not skip ahead unless explicitly instructed.

## Repository Philosophy

Don't chase tools.

Build engineering capability.
