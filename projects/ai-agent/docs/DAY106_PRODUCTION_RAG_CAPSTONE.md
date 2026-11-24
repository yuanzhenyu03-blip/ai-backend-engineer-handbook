# Day106 Application Design — Production RAG Capstone

## Scope

Day106 composes the Day95–Day105 public seams into one deterministic runnable Level 2 checkpoint. Day95–99 are
represented in this run by manually aligned content-safe lineage receipts; their authoritative stores are not
rerun. It adds no
parallel source, ChunkSet, EmbeddingSet, Generation, pointer, authorization or release authority. The only new
durable seam is response intent, dispatch reconciliation and delivery evidence after the existing
application-owned `OutputReleaseDecision`.

## Fixed execution

```text
P1 + BS1 + G2/r8
Manifest(G2) = {A@v1, C@v1}
B@v1 = D1 tombstoned

Q1 → A@v1
Q2 → C@v1
Q3 → A@v1 + C@v1

P2 revokes A@v1 immediately
BS2 + G3/r9
Manifest(G3) = {C@v1}
```

An old G2 request remains correctly bound to G2/r8 but loses permission to release A after P2. A new request
must acquire G3/r9 and rerun retrieval, context, grounding and release gates.

## Ownership

| Fact/artifact | Owner | Day106 use |
|---|---|---|
| source/version/provenance/authorization/deletion | application authoritative stores | read current identity and eligibility |
| ChunkSet/EmbeddingSet | existing committers | reference immutable IDs and digests |
| Generation/Manifest/serving pointer/ReadView | Day104 lifecycle control plane | build, validate, CAS and pin |
| retrieval/reranking | Day100/101 application seam | exact authorized hits and handoff digest |
| grounding/citations | Day102 application seam | generation plus independent claim/citation evidence after the Day105 Prompt gate |
| evaluation | Day103 evaluator | hard-gate semantics, not serving authority |
| context/candidate/release | Day105 security pipeline | Prompt-before-model security/context and final release authority |
| response intent/delivery | Day106 response ledger | durable post-decision outcome history |

## Ten capstone contracts

1. `SourceToOccurrenceLineage` — content-safe projection of committed source, parse, ChunkSet and EmbeddingSet
   identity for one exact occurrence.
2. `CapstoneRequestBinding` — pre-retrieval request, Generation, pointer, BuildSnapshot and ReadView identity.
3. `Day101ExecutionReceipt` — application-owned, MAC-authenticated binding from request/query through the
   selected bundle, Generation/artifact, authorization scope, candidate pool and exact Day101 hits. Matching
   public fields alone are not accepted as proof that the application issued the receipt.
4. `RetrievalAndContextReceipt` — bound Day101 execution receipt, RetrievalBundle, exact occurrence/content
   digests and actual ContextAssemblyManifest.
5. `ReleaseCurrentnessSnapshot` — forward-only current source eligibility, quarantine, provenance, Tombstone,
   content-security policy, DLP, metadata-stripping and destination evidence.
6. `AnswerReleaseRecord` — invocation, Candidate, current authorization/currentness facts, exact released
   occurrences, durable decision and optional atomic response-intent binding.
7. `CapstoneEvaluationDecision` — normal-quality, security, recovery and replay hard-gate result.
8. `ResponseIntent` — the one durable dispatch owner for one exact release decision, destination and idempotency
   key.
9. `RecoveryAndIncidentRecord` — append-only transport/reconciliation/delivery observation.
10. `EndToEndExecutionManifest` — exact command, repository state, runtime boundary, artifact digests, timestamps,
   checks and explicit `NOT_RUN` claims.

## Identity spine

```text
committed SourceToOccurrenceLineage
→ BuildSnapshot
→ immutable GenerationArtifact + GenerationManifest
→ ActivePointer revision
→ ReadView generation/revision/fence
→ CapstoneRequestBinding
→ Day101ExecutionReceipt + handoff/candidate-pool digest
→ RetrievalBundle ID/digest + exact occurrences
→ ContextAssemblyManifest ID/digest
→ ModelInvocationEnvelope
→ AnswerCandidate ID/digest
→ ReleaseEvidence
→ OutputReleaseDecision
→ ResponseIntent/idempotency key
→ dispatch and DeliveryReceipt events
```

The Day104 lifecycle Manifest and Day105 security-projection Manifest use different digest schemas. Day106
carries both digests and proves their canonical occurrence-ID sets agree; it never pretends the checksums are
identical.

## Runtime flows

### Normal G2 path

Day100/101 execute authorized retrieval and reranking. The application verifies the Day101 receipt with its
receipt authority, then rereads the shared authorization authority after the handoff and before context
assembly. Day105 filters the exact candidates, scans the bundle,
admits only least-context occurrences into a versioned untrusted-data envelope and creates the
`ModelInvocationEnvelope`. Day102 takes a guarded current-authorization read that remains stable across the
model invocation; a revocation observed before that guard produces no generator call. Only then does Day102 run
the deterministic generator and grounding/exact-citation
verification that produce evidence for an `AnswerCandidate`. Day105 current authorization, provenance,
Tombstone/security revisions, DLP, metadata stripping, destination and DisclosureEnvelope determine release.

If G3 lacks required A evidence for Q1/Q3, the application records `REQUIRED_EVIDENCE_UNAVAILABLE` before
context/model invocation. No Prompt or generator call occurs and dispatch remains `NOT_ATTEMPTED`.

### P2 and G3

P2 takes effect before rebuild. Retrieval through old G2 rechecks current authorization. An already prepared G2
candidate remains historical evidence but receives `BLOCKED/NOT_RELEASED`. BS2 then produces immutable G3,
which must validate and become READY before the single expected-pointer CAS `G2/r8 → G3/r9`.

### Failure and recovery

Release decision and response intent commit atomically. The deterministic ledger holds authorization and
release-currentness read guards through that commit and again through each new `SEND_STARTED` transition; a
revocation or failed DLP/destination fact therefore fails before state mutation. One decision ID/digest owns at
most one response intent. A transport timeout records `UNKNOWN`; it does not set
`DISPATCHED` and does not authorize an immediate resend. The L2 fixture exports and restores the same values in
one Python process to exercise deterministic rehydration mechanics. It does not prove a real process/container
restart. Reconciliation
`NOT_FOUND` permits a bounded retry with the same idempotency key; acceptance and an authoritative receipt append
`DISPATCHED` and `DELIVERED`. `UNKNOWN` or `ACCEPTED` from a pending intent is valid only after the immediately
preceding `SEND_STARTED` for that same transport attempt; restart replay and execution sealing enforce the same
history rule. Duplicate receipts are deduplicated without rewriting upstream facts.
Recovery record IDs are ledger-global identities: live append, deterministic restore and execution sealing all
reject one ID being reused by a different response intent.

## Evaluation hard gates

- normal historical Q1/Q2/Q3 quality;
- P2 blocks the old G2 candidate and old-G2 retrieval rechecks current authorization;
- G3 Q2 releases while G3 Q1/Q3 never use revoked A;
- unauthorized occurrence entering Prompt equals zero;
- exact grounding and citation binding;
- X/Y/Z/T/B fail closed before Prompt/release;
- pointer CAS, durable decision/intent separation and unknown-outcome recovery;
- exact decision→intent→idempotency-key ownership plus commit/send currentness guards;
- application-authenticated Day101 receipts, model-invocation authorization guard and ledger-global recovery
  record ownership;
- content-safe report seal, followed by a separate deterministic replay.

Reject-all is not a security PASS. `FAIL`, `INCONCLUSIVE` and `NOT_RUN` retain their distinct meanings.

## Evidence boundary

The checkpoint is `EXECUTED_LOCAL_RUNTIME` with in-process deterministic adapters on local Python 3.11.5.
Canonical CPython 3.12 local validation is `NOT_RUN`. The runtime report is sealed with offline replay status
`NOT_RUN`; only the later independent replay may record replay `PASS`. The checkpoint does not run Day106 Docker,
PostgreSQL/pgvector, a real model/Provider/DLP, production IAM/RLS/TLS/egress, HA/restore/purge, load/soak,
real process/container restart, canary traffic or an incident drill. Those boundaries remain `NOT_RUN`; production readiness remains
`MORE_EVIDENCE_NEEDED`.

The Day105 L2 handoff truthfully records its seal-time L3 state as `NOT_RUN`. A later append-only Day105 bounded
PostgreSQL/pgvector L3 report is also `PASS`. They are different points on the evidence timeline. Neither upgrades
Day106 to L3.

## Later append-only L3 checkpoint — 2026-11-24

The original deterministic L2 boundary above remains unchanged. A separately sealed L3A run subsequently
executed real local PostgreSQL 16.15/pgvector 0.8.7, transaction/CAS behavior, container-restart read-back and
offline replay with deterministic model/security adapters. L3B then executed exactly five bounded real model
calls (`max_output_tokens=64`, observed output `89/320`) in one identity-bound database execution: four
decisions released, the old G2/P1 candidate was blocked after P2 with dispatch `NOT_ATTEMPTED`, unauthorized
occurrences entering Prompt remained zero, and no dispatch or delivery record was created. Restart and offline
replay both passed against the sealed artifact digests and durable-state identity.

This evidence upgrades only the explicitly executed local database and external-model boundaries. Canonical
CPython 3.12, external DLP, production IAM/RLS/TLS/egress, HA/restore, physical purge, load/soak/canary and
production remain `NOT_RUN`; production readiness remains `MORE_EVIDENCE_NEEDED`. It also does not change the
`TAUGHT_NOT_VERIFIED` English-interview status or claim Day106 overall PASS.

## Later append-only post-merge CI evidence — 2026-11-24

PR #21 head `2f98d056dc94c5f7ca63b05f300964fac8879d13` merged to `main` as
`3b96fe6f4eda7a5c07834ad12870a406d73297c1`. Both the final PR-head workflow and post-merge push workflow
passed. The post-merge run replayed the exact sealed L2 checkpoint on CPython 3.11.5, while the current-tree
CPython 3.12.16 job passed 1444 unittest cases with 20 skipped, 129 Day106 pytest cases with 5 skipped, 22 seed
evaluators, structured-evidence parsing and all configured saved-evidence replays, including L3A/L3B offline
replay.

This is a later evidence-timeline entry, not a rewrite of the L2 or L3 seals above. CI did not start
Docker/PostgreSQL/pgvector and did not call an external model Provider, detector or DLP. It therefore proves
current-tree CPython 3.12 compatibility and saved-evidence replay, not CPython 3.12 L3 re-execution. External
DLP and production boundaries remain `NOT_RUN`; readiness remains `MORE_EVIDENCE_NEEDED`. The exact record is
[`day106-pr21-ci-validation.json`](../evidence/day106-pr21-ci-validation.json).
