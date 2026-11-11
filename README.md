# AI-Backend-Handbook

## 🎯 Mission

Build the skills required to become an AI Backend Engineer capable of working for overseas AI startups.

The goal is not to learn frameworks one by one.

The goal is to build engineering thinking.

---

# Learning Roadmap

The official learning order lives in `ROADMAP.md`.

Current phase:

* Phase 7C — Production RAG Engineering — in progress. Day95 establishes active immutable parsed content,
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
  evidence. Production readiness remains
  `MORE_EVIDENCE_NEEDED`.

Last completed lesson:

* [Day104 — Index Update, Delete, Rebuild and Migration](docs/fastapi/day104-index-update-delete-rebuild-and-migration.md)

(For the completed classroom history Day01–Day104, see `ROADMAP.md` and `PROJECT_STATUS.md`.)

Current / next lesson:

* Day105 — RAG Security: Prompt Injection, Poisoned Documents and Data-leakage Boundaries (Phase 7C; planned)

Future direction (Day43 onward, competency-gated, current planning horizon ~Day130 — see `ROADMAP.md` and `CURRICULUM.md`):

* Phase 4 — Production AI API Engineering (FastAPI, SQLAlchemy/Alembic, Redis/Outbox/Worker, OpenAI-compatible provider)
* Phase 5 — Production Runtime Integration and Browser Tool Engineering (Day59–Day66)
* Phase 6 — n8n AI Workflow Integration (Day67–Day70)
* Phase 7A — LLM Application Engineering (Day71–Day78)
* Phase 7B — Agent Runtime and MCP Engineering (Day79–Day94; Framework/Job-Market Refresh at Day87, framework chosen Day88 behind a replaceable adapter)
* Phase 7C — Production RAG Engineering (Day95–Day106)
* Phase 7D — AI Evaluation, Safety and Operations (Day107–Day116)
* Phase 8 — Final Employment Capstone (Day117–Day130)

The roadmap is competency-gated, not day-count-gated: the lesson numbers are planning coordinates, and
completion is defined by passing the Employment Readiness Gate, not by reaching a fixed final day.

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
