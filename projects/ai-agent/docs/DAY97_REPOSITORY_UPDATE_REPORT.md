# Day97 Repository Update Report

## Scope

Day97 adds the metadata, tenant ACL and provenance boundary between Day96 chunk selection and Day98
embedding. The update keeps descriptive metadata separate from application-owned authorization facts,
preserves the exact Day95/Day96 lineage, issues narrow signed permits only after a current decision, and
places a policy-enforcement point directly in front of chunk text release.

This is a classroom implementation. It does not claim production deployment, distributed durability,
real identity-provider integration or embedding execution.

## Added implementation

- Immutable metadata contracts, pure projection, allow-list validation, CAS/idempotent publication and
  outbox intent.
- Resource hierarchy, memberships, ACL entries, revision vector, authorization epoch and current policy
  snapshot.
- PIP fact loading, PDP three-state decisions, bounded decision cache and signed, short-lived,
  single-use permits.
- `GuardedChunkReader` PEP with signature, context, expiry, current revision, epoch, selected pointer,
  document fence and provenance checks before content release.
- Exact Day95 source/parsed-artifact to Day96 selected ChunkSet/Chunk provenance validation.
- A narrow `AuthorizedEmbeddingInput` handoff for Day98 without implementing embeddings.

## Added verification and learning artifacts

- 36 focused tests across metadata, provenance, authorization and guarded content release.
- 24-case deterministic seed evaluator and a saved authorization decision matrix.
- Deterministic end-to-end authorized access example and saved safe-output report.
- Formal 16-section lesson, classroom record, application contract and Day98 handoff contract.
- Official-source research ledger, cheat-sheet entries and beginner/intermediate/senior interview material.
- Repository status, curriculum, roadmap, task, changelog and architectural-decision updates.

## Validation performed locally

- Day97 focused tests: 36/36.
- Day96 regressions: 25/25.
- Day95 regressions: 60/60.
- Dependency-free ai-agent suite: 851/851.
- Day97 seed: 24/24; all 13 available Day83-Day97 seed evaluators exited successfully.
- Deterministic example, saved-report match and compileall: PASS.
- Execution runtime: Python 3.11.5; no model Provider or production data was used.
- GitHub Actions: Python 3.12.15, 882/882 complete tests and every available seed evaluator PASS in
  [run 39753253867](https://github.com/yuanzhenyu03-blip/ai-backend-engineer-handbook/actions/runs/39753253867).

The local environment does not contain the pinned MCP SDK and does not permit the loopback listener used
by the restart test. Therefore the five environment-bound integration test files and Python 3.12 run are
recorded as not run locally; the repository CI result above supplies that bounded integration evidence.

## Security invariants demonstrated

- Same tenant does not imply content-read permission.
- Untrusted source metadata cannot create authority.
- Explicit deny wins; no applicable grant is a deny; unavailable authority is indeterminate and maps to
  503 without releasing content.
- Chunk-level allow does not widen a missing parent permission by default.
- Permit signature alone is insufficient: the PEP rechecks every current mutable fact.
- Revocation advances the relevant epoch/revision, making old permits unusable.
- Ordinary logs and metrics do not contain chunk text or high-cardinality raw identifiers.

## Remaining evidence

- Complete Python 3.12 CI with the pinned real MCP SDK.
- Durable database transactions, distributed CAS/fencing, outbox dispatch and crash/restart recovery.
- Real identity/PAP/PIP/PDP integration and signing-key lifecycle.
- Production telemetry, alerting, load, soak, latency, CPU and memory evidence.
- Day98 embedding, Day99 indexing and later retrieval/citation quality evaluation.

Production readiness remains `MORE_EVIDENCE_NEEDED`.

## Suggested commit

`feat(day97): add metadata acl and provenance guard`
