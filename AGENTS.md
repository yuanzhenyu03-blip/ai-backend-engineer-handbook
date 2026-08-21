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
- Last Completed Lesson: Day72 — Provider Capabilities and the Replaceable Provider Adapter (Phase 7A; CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME classroom scope; INTEGRATION_RUNTIME/PRODUCTION NOT RUN).
- Current / Next Lesson: Day73 — Prompt Contracts, Prompt Versioning and Compatibility (Phase 7A; Current / Not started; no content yet).
- Current phase: Phase 7A — LLM Application Engineering (in progress; Day71–Day72 Completed, Day73 current). Phase 6 (Day67–Day70) is COMPLETE; Phase 4 and Phase 5 are COMPLETE.

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
- Day59–Day72 are complete; Day73 (Prompt Contracts, Prompt Versioning and Compatibility) is Current / Not started and has no content yet. Do not skip ahead, and do not create Day73 content.
- Day70 closed Phase 6. Day71 began Phase 7A (LLM Application Engineering) as a PHASE TRANSITION built on the Day53–Day61 provider/runtime foundations — not a technical dependency on Day69/Day70/n8n. Day72 made the replaceable Provider Adapter executable (CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME; no real SDK/HTTP/Provider). Day73 directly consumes Day72's stable Provider surface.

Do not skip ahead unless explicitly instructed.

## Repository Philosophy

Don't chase tools.

Build engineering capability.
