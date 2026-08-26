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
- Last Completed Lesson: Day75 — Streaming, Caching and Batching for LLM Applications (Phase 7A; CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME classroom scope; INTEGRATION_RUNTIME/PRODUCTION NOT RUN).
- Current / Next Lesson: Day76 — Model Routing, Fallback, Latency and Cost Engineering (Phase 7A; Planned / Not started; no content yet).
- Current phase: Phase 7A — LLM Application Engineering (in progress; Day71–Day75 Completed, Day76 current). Phase 6 (Day67–Day70) is COMPLETE; Phase 4 and Phase 5 are COMPLETE.

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
- Day59–Day75 are complete; Day76 (Model Routing, Fallback, Latency and Cost Engineering) is Current / Not started and has no content yet. Do not skip ahead, and do not create Day76 content.
- Day70 closed Phase 6. Day71 began Phase 7A (LLM Application Engineering) as a PHASE TRANSITION built on the Day53–Day61 provider/runtime foundations — not a technical dependency on Day69/Day70/n8n. Day72 made the replaceable Provider Adapter executable; Day73 added the application-owned Prompt Contract + immutable Attempt binding; Day74 added strict output/tool contracts, permissioned Admission/execution, outcome verification and guarded completion; Day75 added streaming/caching/batching while preserving those boundaries (Day72–Day75: CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME; no real Provider/SSE/HTTP/DB/cache/queue/tool for Day75).

Do not skip ahead unless explicitly instructed.

## Repository Philosophy

Don't chase tools.

Build engineering capability.
