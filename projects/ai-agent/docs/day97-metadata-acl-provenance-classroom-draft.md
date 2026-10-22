# Day97 — Metadata, Tenant, ACL and Provenance (classroom record)

This record preserves the real guided session and the learner's reasoning. It is not a production-readiness
claim. The fixed classroom baseline was remote `main` commit
`51f8f0b0fa3cea7ead338203a17e3f94729e46da` (merged PR #8, successful Python 3.12 Actions run).

## 1. Lesson Metadata

- Phase 7C, after Day96 ChunkSet selection and before Day98 embeddings.
- Evidence after repository update: deterministic in-process application path on synthetic fixtures.
- Production readiness: `MORE_EVIDENCE_NEEDED`.

## 2. Learning Objectives

Separate identity, membership, grant, permit and enforcement; distinguish metadata, authority and provenance;
invalidate stale cache/permit state; preserve exact lineage; and produce a Day98-safe embedding handoff.

## 3. Why This Matters

The production scenario was an embedding worker notified of a selected same-tenant ChunkSet. The learner
correctly rejected direct read: same tenant and selected pointer do not prove `chunk:read_for_embedding`.

## 4. Roadmap Position

Day95 provides immutable source/parse lineage; Day96 provides immutable selected chunks; Day97 provides safe
use; Day98 may then embed only authorized inputs.

## 5. Lesson Map

`principal → membership → grant → decision → signed permit → PEP current-state recheck → guarded read`.

## 6. Core Mental Model

PIP provides current facts. PDP compares them with PAP rules. PermitIssuer signs only ALLOW. PEP executes and
revalidates. GuardedChunkReader controls the final protected-content exit.

## 7. Main Concepts

The session covered exact permit bindings, deny-overrides, three-state decisions, authorization epoch,
revision-bound cache, source-declared metadata, immutable snapshots, candidate/validator/Committer separation,
CAS/idempotency/fencing, repeated-text provenance, tombstones, Outbox duplicates, safe observability, pagination
post-checks, and Day98 service action.

The learner repeatedly asked for diagrams after the afternoon material became unclear. The course consolidated
the system into one workflow instead of continuing cosmetic variants. The final independent Chinese summary
correctly connected PIP/PDP/PAP/PermitIssuer/PEP, epoch/revision revalidation, provenance and minimal reads.

## 8. Common Misconceptions

Corrections retained from the session:

- tenant match is not authorization;
- provenance completeness does not grant access;
- source metadata validation does not turn `owner` or `acl` into authority;
- `INDETERMINATE` is internally distinct from policy `DENY`;
- content hash cannot merge cross-tenant lineage or authorization;
- vector filters and selected pointers are not permits;
- metrics exclude high-cardinality/sensitive IDs; protected details belong in redacted logs/traces;
- Bloom filters require an exact authorization lookup after a possible match.

## 9. Engineering Trade-offs

Live PEP rereads cost latency but bound revocation delay. Immutable snapshot history costs storage but enables
audit. Generic denial reduces client diagnostics but resists enumeration. One-time permits reduce replay but
require fresh authorization after uncertain delivery.

## 10. Hands-on Exercises

The repository artifact turns the session into executable scenarios: grant/no-grant, cross tenant, explicit
deny, outage, permit tampering/expiry/replay/revocation, selection/fence changes, metadata authority rejection,
CAS convergence, delayed Outbox and provenance gaps/repeated text.

## 11. Relevant Framework Connections

OPA/Cedar/OpenFGA, RLS and vector filters were placed behind the application boundary and explicitly left NOT
RUN. None may replace application-owned exact resource/action enforcement.

## 12. AI Backend Connections

Day98 receives service-principal authorization evidence and protected lineage, not raw PAP tables or a broad
database credential. Future vector results still require post-check authorization.

## 13. English Interview

The learner produced correct short answers for authentication/authorization, tenant grant, outage `503`, epoch
invalidation, permit fields, provenance and PEP TOCTOU. Technical corrections were needed for metadata versus
authority and source metadata. Direct teaching was needed for ACL inheritance, missing production evidence and
the final senior end-to-end answer. Language corrections included articles, verb forms and precise terms such
as `identity`, `explicit`, `issued`, `decision`, `lineage` and `invalidated`.

Result: `COMPLETED_WITH_TECHNICAL_AND_LANGUAGE_CORRECTIONS_AND_DIRECT_TEACHING`.

## 14. Mental Model Summary

```text
current immutable content facts
+ current mutable authorization facts
→ narrow signed permit
→ live PEP recheck
→ minimal content

revocation → ACL revision + epoch → stale cache/permit rejected
```

## 15. Today's Takeaway

Day97 is the RAG safe-use boundary: who may see which exact content, for what exact action, under which current
rules, with what immutable lineage evidence.

## 16. Before Next Lesson Checklist

- [x] Learner final independent summary completed and corrected.
- [x] English Interview covered beginner/intermediate/senior prompts with honest corrections.
- [x] Core model implemented and tested on synthetic data.
- [x] Day98 handoff contract documented.
- [ ] Production integrations, distributed durability and load/recovery evidence remain.
