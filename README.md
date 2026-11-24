# AI-Backend-Handbook

## 🎯 Mission

Build the skills required to become an AI Backend Engineer capable of working for overseas AI startups.

The goal is not to learn frameworks one by one.

The goal is to build engineering thinking.

---

# Learning Roadmap

The official learning order lives in `ROADMAP.md`.

Current phase:

* Phase 7C — Production RAG Engineering — complete at guided classroom scope through Day106. Day95 establishes active immutable parsed content,
  Day96 adds provenance-bound ChunkSets, and Day97 adds metadata/tenant/ACL/provenance enforcement with narrow
  signed permits and guarded reads. Day98 adds eligibility-first embedding selection, a frozen vector-space
  contract and atomic immutable EmbeddingSets. Day99 adds official three-store research, narrow index-build
  authorization, application-owned vector/index contracts, deterministic batches, an exact Flat oracle,
  immutable shadow generations, readback evidence, fencing and reconciliation. Day100 adds authorization-first
  hybrid BM25/Exact retrieval, application-owned filters, deterministic RRF, final reauthorization, bounded
  refill/degradation and authority-bound cursor/cache semantics. Day101 adds bounded validated rewrites,
  per-variant reuse of the Day100 boundary, occurrence-identity fusion, contract-validated re-ranking and a
  final authorization/provenance guarded release. Day102 adds immutable Grounding Bundles, exact Claim-to-
  Citation links, independent source/semantic verification, partial answers and guarded release. Day103 adds a frozen
  independently labeled Q1–Q3 dataset, retrieval/answer/Citation/Abstention evaluators, slice analysis, non-compensable
  hard gates, explicit regression decisions and content-safe replay evidence. Day104 keeps the same refund case and
  adds immutable index Generations, BuildSnapshot/Manifest/read-back gates, Tombstones, atomic pointer activation,
  leased ReadViews, drain/retirement and safe rollback mechanics, with bounded local PostgreSQL/pgvector L3
  evidence. Day105 preserves that lifecycle while adding application-owned ingestion, retrieval, context,
  model-invocation and output-release security boundaries for document injection, corpus poisoning,
  cross-document attacks and data leakage. Its sealed deterministic Level 2 record is now complemented by a
  bounded local PostgreSQL 16.15/pgvector 0.8.7 Level 3 run: 20/20 repository unit tests, 9/9 real integration
  tests, 20/20 hard gates, 14 security cases, 18 failure checkpoints, a real database-container restart replay
  and offline evidence replay. The security adapters remain deterministic; real external detector/model/DLP/
  Provider integration, Level 4 and production readiness remain `NOT_RUN` / `MORE_EVIDENCE_NEEDED`.
  After the seal, PR #18 merged to `main`; its [append-only CPython 3.12 CI evidence](projects/ai-agent/evidence/day105-pr18-ci-validation.json)
  records 1334 tests PASS with 7 skipped, 21 seed evaluators PASS, seven saved evidence replays PASS and the
  Day105 replay PASS. That earlier CI run did not start Docker/PostgreSQL/pgvector or run Day105 Level 3; the
  later bounded local L3 evidence is recorded separately and does not rewrite the sealed L2 reports.
  Day106 closes the guided Phase 7C classroom sequence by composing those existing owners into one exact
  request-to-delivery evidence chain. It binds the selected Generation/ReadView, security-filtered retrieval,
  context, grounded AnswerCandidate, current release checks, durable decision, response intent and receipt;
  it also exercises revocation/rebuild/CAS and UNKNOWN reconciliation. Append-only bounded Level 3 evidence on
  local CPython 3.11.5 now includes L3A real local PostgreSQL 16.15/pgvector 0.8.7 plus container-restart replay,
  and L3B exactly five bounded real model calls: 89/320 observed output tokens, four RELEASE decisions, one
  P2-revoked BLOCKED/NOT_ATTEMPTED decision, zero unauthorized Prompt occurrences, no dispatch, and restart/
  offline replay PASS. After that local seal, PR #21 merged to `main`; its
  [append-only CI evidence](projects/ai-agent/evidence/day106-pr21-ci-validation.json) records the exact L2
  checkpoint replay on CPython 3.11.5 and, separately, the current deterministic/unit suite plus saved L3A/L3B
  replay on CPython 3.12.16. CI did not re-execute Docker/database/Provider L3. External detector/DLP, production
  IAM/RLS/TLS/egress, HA/restore, load/soak, canary and production remain `NOT_RUN`; readiness remains
  `MORE_EVIDENCE_NEEDED`. The final teacher-provided English response remains `TAUGHT_NOT_VERIFIED`, so Day106
  overall PASS is not claimed.

Last completed lesson:

* [Day106 — Production RAG Capstone and English Interview](docs/fastapi/day106-production-rag-capstone-and-english-interview.md)

(For the completed classroom history Day01–Day106, see `ROADMAP.md` and `PROJECT_STATUS.md`.)

Current / next lesson:

* Day107 — ProofOps Scope Freeze, Threat Model, Two-layer Architecture and Async DB/pgvector Skeleton
  (Phase 7D; planned / not started)

Future direction (Day43 onward, competency-gated, current planning horizon ~Day130 — see `ROADMAP.md` and `CURRICULUM.md`):

* Phase 4 — Production AI API Engineering (FastAPI, SQLAlchemy/Alembic, Redis/Outbox/Worker, OpenAI-compatible provider)
* Phase 5 — Production Runtime Integration and Browser Tool Engineering (Day59–Day66)
* Phase 6 — n8n AI Workflow Integration (Day67–Day70)
* Phase 7A — LLM Application Engineering (Day71–Day78)
* Phase 7B — Agent Runtime and MCP Engineering (Day79–Day94; Framework/Job-Market Refresh at Day87, framework chosen Day88 behind a replaceable adapter)
* Phase 7C — Production RAG Engineering (Day95–Day106)
* Phase 7D — ProofOps Core Runtime and Bounded Incident Resolution (Day107–Day113)
* Phase 7E — Evaluation, Safety and Operations on ProofOps (Day114–Day123)
* Phase 8 — Cloud Integration, Operations and Employment Readiness (Day124–Day130)

The roadmap is competency-gated, not day-count-gated: the lesson numbers are planning coordinates, and
completion is defined by passing the Employment Readiness Gate, not by reaching a fixed final day.

Decision 025 is a planning-only change: ProofOps has not been created or run, and Day107 remains planned. Once
Day107 explicitly begins, delivery switches to Ticket + PR + DoD with dynamic Micro-Socratic Type A/Type B
teaching. A heavy Day coordinate may span multiple calendar days; calendar passage never creates mastery.

The final goal remains becoming an overseas AI Backend Engineer with a runnable, deployable, verifiable
portfolio. This builds capability and evidence; it does not guarantee a job.

---

## Learning Principles

* Build engineering capability instead of chasing tools.
* Always understand why a design exists.
* Prefer enterprise practices over demo code.
* Every lesson must connect theory, engineering, interview questions, and projects.

---

## Daily Learning Workflow

```text
ChatGPT Teaching
        |
        v
Coding Practice
        |
        v
Codex Documentation
        |
        v
ChatGPT Review
        |
        v
Git Commit
        |
        v
GitHub Push
        |
        v
Next Lesson
```

GitHub is the single source of truth for lessons, projects, interview notes, cheat sheets, and progress.

---

## Final Goal

* Enterprise GitHub Portfolio
* Overseas Resume
* Mock Interview Ready
* Remote AI Backend Offer
