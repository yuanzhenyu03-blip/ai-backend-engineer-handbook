# Day104 Repository Update Report

Date: 2026-11-11

## Outcome

Day104 — Index Update, Delete, Rebuild and Migration is complete at guided
classroom Level 2 and local integration Level 3. The learner's 90/100 assessment
records conceptual and deterministic-mechanics mastery after remediation; it is
not the source of the L3 result. The separate saved L3 report records real
PostgreSQL/pgvector integration evidence. Neither result is production evidence.
Day105 is next.

Production readiness remains `MORE_EVIDENCE_NEEDED`.

## Main classroom content preserved

The formal lesson and classroom record preserve the actual A/B/C refund case, Q1/Q2/Q3, the thin G1→G2
vertical slice, one-failure-at-a-time reasoning, the A@v2 business-truth change and the employee-authorization
transfer case. They retain the learner's correct reasoning and the important corrections around Generation versus
pointer identity, original idempotency bindings, DRAINING versus RETIRED, physical checkpoint/seal, `INCONCLUSIVE`
versus `FAILED`, rollback eligibility and A@v3 ABA prevention.

## Level 2 implementation

- `rag_index_lifecycle_contracts.py` defines frozen BuildSnapshot, EvaluationRuler, Manifest, Generation artifact,
  lifecycle, activation lease/record, ReadView, deletion and Inbox/Outbox contracts.
- `rag_index_lifecycle_orchestrator.py` builds an off-path deterministic Provider namespace, enforces namespace
  set-once, seals it and produces independent Expected-versus-Actual read-back evidence.
- `rag_index_lifecycle_committer.py` enforces global Validation ID set-once, current Day103 ruler, complete READY
  evidence, authority-issued activation fencing, pointer CAS, lifecycle transitions and alias reconciliation.
- `rag_index_read_views.py` models atomic request pinning, heartbeat/release fencing, Reaper, audited reader
  reconciliation, drain and retention-gated retirement.
- `rag_index_deletion_ledger.py` atomically models Tombstone/intent/Outbox, complete operation/idempotency bindings,
  durable verification policy, trusted validation evidence and adopted verification digests.
- The deterministic example follows `BS1 → G1/G2 READY → G2/r8 ACTIVE → G1
  DRAINING/RETIRED`; physical purge remains `NOT_RUN`.

Adversarial review added regression coverage for a wrong Day103 ruler, cross-Generation Validation ID overwrite,
READY evidence substitution, unsigned/stale activation token, reused physical namespace, empty corpus, stale
alias wake-up, ledger-only ReadView repair, zero-scope deletion verification, incomplete idempotency bindings,
timezone ordering and untrusted or incompletely bound deletion evidence.

## Level 3 real integration

The opt-in L3 path ran against PostgreSQL `16.15` with pgvector `0.8.7`. It
preserved the same A/B/C corpus, D1 Tombstone and Q1/Q2/Q3 ruler while exercising
real SQL transactions, two-connection CAS competition, repeatable-read snapshot
stability, activation rollback under fault injection, lease fencing, single-
Generation ReadViews, drain/retirement, durable Inbox/Outbox replay, deletion
non-resurrection and application/database restart read-back. A forced-index
`EXPLAIN` plan contained `index_points_embedding_hnsw_cosine_idx`; the report
stores only content-safe plan evidence.

The saved L3 report records `32/32` PostgreSQL adapter unit tests, `7/7` opt-in
real integration tests, `17/17` runner gates and the database-container restart
replay as PASS. `LOGICAL_RELEASE` and `SERVING_INDEX_ABSENCE` passed;
`PHYSICAL_PURGE` remains `NOT_RUN`.

## Course artifacts

- Formal lesson: `docs/fastapi/day104-index-update-delete-rebuild-and-migration.md`
- Design: `projects/ai-agent/docs/DAY104_INDEX_GENERATION_LIFECYCLE.md`
- Actual classroom record: `projects/ai-agent/docs/day104-index-generation-lifecycle-classroom-draft.md`
- Day105 handoff: `projects/ai-agent/docs/DAY104_TO_DAY105_HANDOFF.md`
- Example: `projects/ai-agent/examples/day104_index_lifecycle.py`
- Seed/evaluator: `projects/ai-agent/evals/day104_index_lifecycle_seed.jsonl` and
  `projects/ai-agent/evals/run_day104_seed_eval.py`
- Evidence replay: `projects/ai-agent/evals/run_day104_evidence_replay.py`
- Saved report: `projects/ai-agent/evidence/day104-index-lifecycle-report.json`
- Validation: `projects/ai-agent/evidence/day104-validation.json`
- L3 contract/evidence notes:
  `projects/ai-agent/docs/DAY104_L3_REAL_PGVECTOR_INTEGRATION.md`
- Saved L3 report:
  `projects/ai-agent/evidence/day104-l3-integration-report.json`
- Offline L3 evidence replay:
  `projects/ai-agent/evals/run_day104_l3_evidence_replay.py`
- Architecture decision: Decision 022 in `DECISIONS.md`

Global navigation, curriculum, roadmap, project status, sprint tasks, changelog, cheat sheet, interview notes and
the Python 3.12 workflow are synchronized through Day104.

## Validation actually executed

- Frozen L2 baseline: Day104 focused tests 73/73 PASS and Day104 seed 10/10 PASS.
- Final repository-wide suite after L3: `Ran 1245 tests` — `OK (skipped=7)`
  on the local Python 3.11.5 fallback runtime.
- Every available seed evaluator: 20/20 evaluator processes PASS.
- Every available saved evidence replay: 6/6 PASS. These are Day100, Day101,
  Day102, Day103, Day104 L2 and Day104 L3; both Day104 report checksums
  reproduced exactly.
- Deterministic example, compileall and mypy over the new Day104 source/example/evaluator surface: PASS.
- Black check, Python line-length scan and JSON/JSONL parsing: PASS.
- PostgreSQL adapter unit tests: 32/32 PASS.
- Opt-in PostgreSQL/pgvector integration tests: 7/7 PASS.
- L3 runner gates: 17/17 PASS on PostgreSQL 16.15 and pgvector 0.8.7.
- Database-container restart replay and offline saved L3 evidence replay: PASS.
- The first restricted-sandbox full-suite attempt could not bind three Day93/Day94 loopback servers; the same
  suite passed after loopback permission. This was an execution-environment restriction, not a test assertion.
- Python 3.12 pull-request CI: `NOT_RUN`; no commit, push or pull request was authorized.

The frozen L2 structural checks remain recorded in
`projects/ai-agent/evidence/day104-validation.json`; the final L3-linked
Markdown-link, 16-section, replay, YAML and `git diff --check` checks were run
separately and do not rewrite that L2 artifact.

## Evidence levels

| Level | Result | What it means |
|---|---|---|
| Level 1 — Conceptual | PASS | The learner explained ownership, lifecycle, rollback and evidence boundaries. |
| Level 2 — Deterministic mechanics | PASS | Process-local tests exercise identity, state, CAS, fencing and replay invariants. |
| Level 3 — Integration | PASS | One pinned local Docker PostgreSQL 16.15/pgvector 0.8.7 lab passed 17/17 runner gates, 32/32 adapter unit tests and 7/7 real integration tests. |
| Level 4 — Production | `NOT_RUN` | No production deployment, traffic, capacity, drills or observation window ran. |

## Claims explicitly not made

This update does not generalize the tested local PostgreSQL statements and HNSW
plan to HA/failover, restore, multi-node partitions, distributed leases,
production-size ANN recall, physical erasure, zero downtime, load, latency,
capacity, cost, error rate, production traffic or production suitability. No
production Vector Store was selected merely to complete the lesson.

## Git boundary

No commit, push, branch publication, pull request or merge was performed.
