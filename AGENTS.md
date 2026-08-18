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
- Last Completed Lesson: Day69 — Human Approval, Retry, Secrets, Audit and Error Workflows (Phase 6; CONCEPTUAL_STATIC classroom scope).
- Current / Next Lesson: Day70 — n8n + FastAPI + AI Tool Integration Capstone and Interview (Phase 6; Current / Not started; no runtime evidence yet).
- Current phase: Phase 6 — n8n AI Workflow Integration (in progress; Day67–Day69 Completed, Day70 current). Phase 4 and Phase 5 are COMPLETE.

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
- Day59–Day69 are complete; Day70 (the Phase 6 capstone) is Current / Not started and has no runtime evidence yet. Do not skip ahead, and do not claim Day70 is complete or has runtime evidence.
- Day70 directly consumes Day69's hardened contract. Day71 begins Phase 7A (LLM Application Engineering) as a PHASE TRANSITION built on the Day53–Day61 provider/runtime foundations — not a technical dependency on Day69/Day70/n8n.

Do not skip ahead unless explicitly instructed.

## Repository Philosophy

Don't chase tools.

Build engineering capability.
