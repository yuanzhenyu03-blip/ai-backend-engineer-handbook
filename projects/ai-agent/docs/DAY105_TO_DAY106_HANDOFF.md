# Day105 → Day106 Handoff

## Trusted security baseline

Day106 must preserve the complete Day104 Generation/ReadView identity and the Day105 request-scoped security
artifact chain:

```text
request/principal/tenant/purpose
+ Generation/Manifest/pointer revision
+ ReadView generation/revision/fence
+ exact occurrence IDs and content digests
+ current authorization/provenance/Tombstone/quarantine revisions
+ content-security snapshot and parser/scanner/detector/policy versions
+ retrieval config + template + context assembler
+ model/Tool/output policy + Disclosure Envelope
+ adversarial-set and evidence digests
```

The pre-retrieval `RequestSecurityBinding` carries the validated Day104 receipt and policy identity; exact
occurrence IDs/digests join only in the RetrievalBundle and ContextAssemblyManifest. Day106 must preserve the
whole chain rather than treating the first object as a complete post-retrieval receipt.

## Required invariants

- retrieved content is data, never instruction authority;
- no unauthorized occurrence enters Prompt, citation, cache, log, telemetry or response;
- one attempt never mixes Generation, ReadView or security revisions;
- the model emits AnswerCandidate only;
- release requires grounding, exact citations, current authorization, DLP and disclosure evidence;
- missing evidence fails closed without treating quarantine as an evidence result;
- normal Q1/Q2/Q3 quality and security hard gates pass together;
- incident containment precedes durable update and immutable Generation rebuild.

## Fixed fixture

A@v1 and C@v1 remain the current normal facts, B@v1 remains D1-tombstoned, and current baseline pointer identity
remains `refund-serving@G2/r8`. X/Y/Z/T are independent adversarial fixtures and do not rewrite that history.

## Day106 ownership

Day106 composes the validated quality, lifecycle and security contracts into a runnable Production RAG
checkpoint. It must not collapse independent gates or upgrade deterministic evidence into integration evidence.

## Evidence boundary

Day105 L2 is deterministic local evidence only. Real detector/DLP/model/Provider behavior, local PostgreSQL/
pgvector integration for Day105 controls, restart replay, production IAM/TLS, real multi-tenant enforcement,
red-team, load/soak, canary traffic and incident drill remain `NOT_RUN` until separately authorized and executed.
Production readiness remains `MORE_EVIDENCE_NEEDED`.
