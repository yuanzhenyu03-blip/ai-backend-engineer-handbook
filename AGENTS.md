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
- Last Completed Lesson: Day106 — Production RAG Capstone and English Interview (guided classroom coverage plus
  deterministic Level 2 composition and append-only bounded Level 3 evidence on local CPython 3.11.5; L3A ran
  real local PostgreSQL 16.15/pgvector 0.8.7 with transaction/CAS and container-restart replay; L3B ran exactly
  five bounded real model calls with 89/320 observed output tokens, four RELEASE decisions, one P2-revoked
  BLOCKED/NOT_ATTEMPTED decision, zero unauthorized Prompt occurrences, no dispatch, and restart/offline replay
  PASS; later post-merge CI passed the current deterministic/unit suite and saved L3A/L3B replay on CPython
  3.12.16 without re-executing Docker/database/Provider L3; external detector/DLP, production
  IAM/RLS/TLS/egress, HA/restore, load/soak, canary and production remain NOT RUN; readiness
  MORE_EVIDENCE_NEEDED; the final teacher-provided English response remains TAUGHT_NOT_VERIFIED, so Day106
  overall PASS is not claimed; the local L3 seal itself remains the earlier no-push/no-CI checkpoint).
- Day106 post-seal CI: PR #21 merged to `main` as `3b96fe6f4eda7a5c07834ad12870a406d73297c1`;
  append-only evidence records the exact sealed L2 replay on CPython 3.11.5. The CPython 3.12.16 current-tree
  job passed 1444 unittest cases (20 skipped), Day106 pytest with 129 passed and 5 skipped, 22 seed evaluators and 10
  current-tree saved-evidence replays; across both jobs, all 11 configured replays passed. CI did not start
  Docker/PostgreSQL/pgvector or call an external Provider/DLP.
- Day105 post-seal CI: PR #18 merged to `main`; append-only evidence records CPython 3.12.16 with 1334 tests
  PASS, 7 skipped, 21 seed evaluators PASS, seven saved evidence replays PASS and the Day105 replay PASS. CI did
  not start Docker/PostgreSQL/pgvector or run Day105 L3; the later local L3 record is separate and does not
  relabel that CI evidence.
- Day104 integration baseline: Index Update, Delete, Rebuild and Migration (guided classroom Level 2 plus
  bounded local PostgreSQL 16.15/pgvector 0.8.7 Level 3;
  immutable BuildSnapshot-bound Generations; independent Manifest read-back; Day103 quality evidence; READY
  gates; pointer CAS; alias reconciliation; leased ReadViews; Tombstone/deletion evidence; drain, rollback and
  retirement; frozen L2 baseline 73/73 focused tests and 10/10 seed; final post-L3 repository verification
  `Ran 1245 tests`, `OK (skipped=7)`, all 20 seed evaluators and all six saved evidence replays pass on the local
  Python 3.11.5 fallback; L3 also passed 32/32 adapter unit tests, 7/7 real integration tests, 17/17 runner gates
  and container restart replay; subsequent PR #16 Python 3.12.16 CI run `42995652875` passed 1245 tests,
  all 20 seed evaluators and all six saved evidence replays without starting Docker; HA/restore, distributed
  recovery, physical purge,
  production-size load, zero-downtime production migration, operations and production traffic remain NOT RUN;
  production readiness MORE_EVIDENCE_NEEDED).
- Current / Next Lesson: Day107 — Evaluation Datasets and Golden Sets (Phase 7D; Planned / not started).
- Day88 used guided evidence review. Production Provider/Tool/parser/PostgreSQL/Broker/Worker/Object Storage,
  container/bundled distribution and production integration gates remain NOT EVALUATED /
  MORE_EVIDENCE_NEEDED.
- Current phase: Phase 7C — Production RAG Engineering is COMPLETE at guided classroom scope; Phase 7D is next.

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
- Day59–Day106 are complete at their recorded evidence/classroom levels. Day107 is current/next; do not skip
  ahead.
- Day70 closed Phase 6. Day71 began Phase 7A on the Day53–Day61 runtime foundations. Day72–Day77 built and tested the Provider, Prompt, Output/Tool, stream/cache/batch, routing/cost and Fake/regression seams. Day78 integrated them behind one application-owned Runtime lifecycle and closed Phase 7A. Day79 added the application-owned Controller loop above that Runtime. Day80 added governed Tool visibility/schema/permission without bypassing Day74/Day66/Day78. Day81 added explicit state, termination, loop detection, fencing and budgets. Day82 added durable Checkpoint validation, classified resume/recovery, transactional Outbox intent modeling, lease takeover, late-result fencing and reservation reconciliation. Day83 added human control, Day84 bounded context, Day85 added application-owned handoff, delegation, worker ownership, reconciliation and fan-in boundaries, and Day86 added security admission, Egress, Sandbox and incident-containment boundaries outside the model.

Do not skip ahead unless explicitly instructed.

## Repository Philosophy

Don't chase tools.

Build engineering capability.
