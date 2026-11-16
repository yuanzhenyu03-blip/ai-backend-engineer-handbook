# Day105 Repository Update Report

Date: 2026-11-15

## Outcome

Day105 — RAG Security: Prompt Injection, Poisoned Documents and Data-leakage Boundaries is implemented at
guided classroom Level 2 with deterministic mechanics. The learner assessment is 86/100 after remediation.
Level 3, Level 4 and production readiness are not claimed.

## Included artifacts

- formal 16-section lesson;
- application design and actual classroom record;
- typed contracts and deterministic security pipeline;
- normal/adversarial/failure tests;
- deterministic example;
- content-safe seed/evaluator and offline evidence replay;
- generated evidence and validation records;
- Decision 023 and Day106 handoff;
- synchronized navigation, status, cheat sheet and interview material.

## Validation

Exact executable counts, commands, runtime versions and report checksums are recorded in
`projects/ai-agent/evidence/day105-validation.json` and
`projects/ai-agent/evidence/day105-rag-security-report.json`. This report does not duplicate unverified numbers.

## Claim boundary

The deterministic fake exercises identity binding, trust/authority separation, ingestion and retrieval gates,
bundle/context isolation, model/tool/output ownership, cache invalidation, incident sequencing and hard-gate
evaluation. It does not prove real scanner recall, DLP quality, model robustness, database or Provider
enforcement, distributed currentness, protected egress, latency/capacity/cost, red-team coverage, operational
incident response or production traffic.

## NOT_RUN

- Day105 local real PostgreSQL/pgvector and retrieval-path integration;
- real model, scanner, detector, DLP, policy and egress integrations;
- restart/recovery replay of Day105 security state;
- production IAM/TLS/secret rotation and multi-tenant enforcement;
- continuously updated red-team corpus, load/soak and canary traffic;
- incident drill and observation window;
- Level 4 and production readiness.

## Git boundary

At seal time, this report did not claim commit, push, pull request, merge or CI execution. That historical
boundary remains unchanged; later CI evidence is append-only and does not rewrite the sealed local runtime
reports.

## Post-seal CI evidence

PR #18 head `8f80d3532c9f1fe99918a85b2f0f73e210be0b75` merged to `main` as
`293075c3021a20a21d2d586098f2b8e857dfd00d` at `2026-11-15T14:40:40Z`. GitHub Actions workflow
`368931184`, run `43725541551` (#28, attempt 1), job `132846558835` passed on CPython 3.12.16: 1334 tests PASS
with 7 skipped, all 21 seed evaluators PASS, all seven saved evidence replays PASS and the Day105 replay PASS.

The result is recorded in
[`day105-pr18-ci-validation.json`](../evidence/day105-pr18-ci-validation.json). The original
`day105-validation.json` and `day105-rag-security-report.json` remain frozen. The CI job did not start
Docker/PostgreSQL/pgvector or execute Day105 L3, so L3 remains `NOT_RUN` and the claim boundary above is not
upgraded.
