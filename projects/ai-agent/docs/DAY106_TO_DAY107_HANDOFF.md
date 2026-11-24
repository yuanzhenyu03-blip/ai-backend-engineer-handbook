# Day106 → Day107 Handoff

## Trusted capstone baseline

Day107 may consume the Day106 L2 report only through its sealed execution manifest and checksum. The minimum
identity is:

```text
repository base + runtime artifact-set fingerprint
+ SourceToOccurrenceLineage digests
+ BuildSnapshot / GenerationArtifact / lifecycle Manifest
+ pointer revision + ReadView generation/revision/fence
+ CapstoneRequestBinding
+ application-authenticated Day101 execution receipt bound to selected Generation/artifact/bundle and handoff
+ Day105 RetrievalBundle + ContextAssemblyManifest exact IDs/digests
+ ModelInvocationEnvelope
+ Day102 generation + grounding/citation verification evidence
+ AnswerCandidate digest
+ ReleaseEvidence + OutputReleaseDecision
+ ResponseIntent/idempotency key
+ append-only recovery/delivery history
+ CapstoneEvaluationDecision
```

The Day104 lifecycle Manifest digest and Day105 security-projection Manifest digest have distinct schemas; the
Day106 composition proves aligned occurrence sets rather than checksum equality.

## Proven deterministic behavior

- G2/r8 under P1 serves normal Q1/Q2/Q3 with exact citations.
- P2 revokes A immediately; an old G2 candidate is retained as evidence but blocked at release.
- retrieval through old G2 rechecks current authorization.
- BS2 builds immutable G3 `{C@v1}` and expected-pointer CAS activates G3/r9.
- new G3 Q2 can release; Q1/Q3 stop before Prompt/generator with `REQUIRED_EVIDENCE_UNAVAILABLE`, never use
  revoked A and do not dispatch.
- X/Y/Z/T/B controls keep unauthorized or unsafe occurrences out of Prompt.
- current authorization is read from the shared authority before context and held under a guarded read across
  model invocation, then checked again at intent commit and before a new send; a changed revision fails closed.
- one output decision owns one exact response intent; decision, intent, dispatch acceptance and delivery remain
  separate and are sealed with the same idempotency key.
- unknown delivery survives same-process deterministic export/rehydration, reconciles, retries only after `NOT_FOUND`, and deduplicates
  the authoritative receipt; `UNKNOWN`/`ACCEPTED` cannot appear without the same-attempt durable
  `SEND_STARTED` predecessor.
- recovery record IDs are globally owned across all response intents during live append, deterministic restore
  and execution sealing.

## Evidence boundary

Day106 evidence is `EXECUTED_LOCAL_RUNTIME` with deterministic in-process adapters on Python 3.11.5. Canonical
CPython 3.12 local validation is `NOT_RUN`. Day95–99 authoritative stores were not rerun; their manually aligned
lineage receipts bind prerequisite evidence. The runtime report seals replay as `NOT_RUN`, while a later
independent replay can append `PASS`. Day106 Docker,
PostgreSQL/pgvector, external Provider/model/DLP, production IAM/RLS/TLS/egress, HA/restore/purge, load/soak,
real process/container restart, canary traffic and incident drill remain `NOT_RUN`; readiness is
`MORE_EVIDENCE_NEEDED`.

Day105 has two non-conflicting timeline entries: seal-time handoff L3 `NOT_RUN`, followed by append-only bounded
local L3 `PASS`. Both are prerequisites only and neither upgrades Day106.

## Day107 guardrails

- do not infer continuous currentness from a point-in-time Day106 PASS;
- do not replace the application pointer or release authority with Provider state;
- do not reuse candidate-bound receipts after candidate/policy/destination changes;
- do not treat offline replay as re-execution of Docker, external-real or production boundaries;
- preserve normal quality beside non-compensable security gates;
- append new evidence; never rewrite this handoff to match a later execution.

## Repository state at handoff authoring

The Day106 worktree is uncommitted. Commit, push, PR, CI and merge remain outside this handoff until separately
authorized and actually executed.

## Later Day106 L3 evidence — 2026-11-24

This section appends evidence without rewriting the L2 handoff above. L3A executed the Day106 path over real
local PostgreSQL 16.15/pgvector 0.8.7 and passed container-restart read-back plus offline replay while its
model/security adapters remained deterministic. L3B executed exactly five real model calls with a 64-output-
token per-call cap and `89/320` observed output tokens. It produced four `RELEASE` decisions and one old-G2/P1
candidate blocked after P2 with dispatch `NOT_ATTEMPTED`; unauthorized occurrences entering Prompt remained
zero. No response dispatch or delivery occurred. The restart and offline replay reports preserve exact durable
identity and artifact bindings.

Day107 may cite these later reports only at their recorded scope. Canonical CPython 3.12, external DLP,
production IAM/RLS/TLS/egress, HA/restore, physical purge, load/soak/canary and production remain `NOT_RUN`;
readiness remains `MORE_EVIDENCE_NEEDED`. The final English response remains `TAUGHT_NOT_VERIFIED`, so Day106
overall PASS is not claimed. This local checkpoint does not claim push, CI, pull request or merge.

## Later post-merge CI evidence — 2026-11-24

This section appends a later repository event without rewriting the handoff-authoring state above. PR #21
merged to `main` as `3b96fe6f4eda7a5c07834ad12870a406d73297c1`; both its final head workflow and the
post-merge push workflow passed. The exact L2 checkpoint replay passed on CPython 3.11.5. The current-tree
deterministic/unit suite plus 10 current-tree saved-evidence replays passed on CPython 3.12.16; across both
jobs, all 11 configured replays passed.

Day107 may cite this as compatibility and offline-replay evidence through
[`day106-pr21-ci-validation.json`](../evidence/day106-pr21-ci-validation.json). CI did not start the database or
call the external Provider/DLP and therefore did not re-execute L3A/L3B. It does not change the
`TAUGHT_NOT_VERIFIED` English result, does not establish Day106 overall PASS and does not upgrade production
readiness.
