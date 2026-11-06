# Day102 Grounding, Citations and Source Verification

## Status

Completed at guided classroom scope with deterministic in-process fakes. Real generator, Claim extractor, semantic verifier, protected-data egress, labeled quality evaluation and production operations remain `NOT_RUN`. Production readiness is `MORE_EVIDENCE_NEEDED`.

## Problem

Day101 returns ordered, current and authorized candidate occurrences. That ranking is not an answer and does not establish that a source supports every generated Claim. Day102 must turn a trusted Day101 handoff into an answer whose released factual Claims can be traced to exact, current source spans.

## Core invariant

```text
released Claim
requires
current authorized source identity
+ source version and exact span
+ Citation inside the frozen Grounding Bundle
+ validated Claim/Evidence relationship
+ final currentness recheck
```

The durable set boundaries are:

```text
Day102 source-window occurrence IDs
⊆ final Day101 handoff occurrence IDs

final Citation targets
⊆ Grounding Bundle source-window IDs

released Claim IDs
⊆ validated SUPPORTED Claim IDs
```

## Architecture

```text
GroundingRequest
→ trusted Day101 handoff admission
→ current authorization/provenance recheck
→ bounded Context Planner
→ immutable GroundingBundle
→ generator + verifier egress gates
→ structured candidate answer
→ Claim extraction with answer spans
→ Claim-to-Citation validation
→ independent semantic Verification
→ final source currentness recheck
→ Claim-level release/rejection
→ Request Coverage and Abstention
→ structured Day102Response + content-safe audit
```

## Main contracts

### `GroundingRequest`

Carries the original Query, request items, tenant/principal/action/purpose, the trusted `Day101Response` and its immutable handoff digest. The original Query is required for Request Coverage even when Claim/Evidence verification could run without it.

### `GroundingBundle`

An immutable set of exact source windows. Its digest binds:

- original-query identity;
- request-item identity;
- Day101 handoff digest;
- current authorization-scope fingerprint;
- Grounding Contract fingerprint;
- upstream outcome/mode/reason;
- source occurrence, version, span, policy and content digest.

The classroom planner fails closed instead of cutting a source at an unsafe character boundary that could remove negation, scope or exception clauses.

### `ClaimRecord` and `ClaimCitationLink`

Each extracted Claim binds an answer span and digest. Citations are independent records so a Claim may use multiple sources and a source may support multiple Claims. Atomic Claims are preferred because they permit exact verification and partial release.

### `VerificationResult`

The result binds Claim digest, Bundle digest, exact Citations, verifier revision, policy version, semantic relation and reason. `SUPPORTED`, `UNSUPPORTED` and `CONTRADICTION` are completed semantic judgments. Provider timeout/failure is `UNAVAILABLE`, not a semantic negative.

### `Day102Response`

Stores released and rejected Claims separately, Request Coverage, abstained request items, source rejections, upstream ranking mode, generator mode, verification mode and content-safe call counts. The user-facing answer is reassembled only from released Claims; raw Provider prose is never returned directly.

## Authority and currentness

The Day101 handoff digest is necessary but never replaces a current authorization read. Day102 rechecks source authority before Bundle construction and immediately before release. A high rank, valid Citation or previous Verification PASS cannot revive a revoked, superseded or provenance-changed source.

Cache keys bind authority identity and content identity. Query text alone, or principal alone, is insufficient because permissions, source versions, source windows, Claims and verifier policies can change independently.

## Egress and source-as-data

Generator and verifier egress are independent gates. Internal retrieval authorization does not authorize protected Query, Claim or source text to leave the application boundary.

Retrieved source content is untrusted data. Namespaces and structured source blocks reduce prompt-injection risk, but only application-owned Validators and release gates may change authorization, Bundle membership or release status.

## Failure classification

| Condition | Result |
|---|---|
| Invalid or tampered Day101 handoff | `REJECTED` before Provider calls |
| Generator/verifier egress denied | `REJECTED` before protected egress |
| Provider timeout without approved fallback | `UNAVAILABLE` |
| Citation outside Bundle | affected Claim `REJECTED` |
| Evidence does not support Claim | affected Claim `REJECTED` as `UNSUPPORTED` |
| Evidence states the opposite | affected Claim `REJECTED` as `CONTRADICTION` |
| Source revoked/superseded/provenance changed | affected Claim `REJECTED` by Source Verification |
| Some request items still answered | `PARTIAL` response |
| No request item has a released Claim | `ABSTAINED` |
| Approved fallback used | explicit `DEGRADED` mode/history |

`REJECTED` is an artifact-level decision. `Abstention` is a request-coverage decision after the application cannot form a supported Claim for requested information.

## Deterministic evidence

The reference implementation proves with deterministic fakes:

- handoff identity and subset enforcement;
- immutable Bundle and Citation membership;
- exact Claim spans and Citation mappings;
- semantic-result identity validation;
- unsupported/contradicted/out-of-bundle rejection;
- partial answer and Abstention assembly;
- final authorization, provenance and superseded-source checks;
- fallback and upstream degradation propagation;
- authority/content-bound cache identities;
- content-safe audit and saved evidence replay.

It does not prove:

- real generator or extractor quality;
- real NLI or LLM-verifier accuracy;
- citation correctness on a labeled corpus;
- protected-data Provider handling;
- latency, capacity, cost, timeout and error-rate gates;
- real database/ANN/FTS integration;
- production traffic behavior.

## Official capability references

- [OpenAI File Search](https://developers.openai.com/api/docs/guides/tools-file-search)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
- [Anthropic citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- [Anthropic search-result blocks](https://platform.claude.com/docs/en/build-with-claude/search-results)
- [Ollama Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Sentence Transformers NLI CrossEncoder](https://www.sbert.net/examples/cross_encoder/training/nli/README.html)

Provider documentation establishes available pointer/schema capabilities. The conclusion that application-level source and semantic verification are still required is the repository's engineering inference.

## Day103 boundary

Day102 emits structured runtime evidence; it does not grade itself. Day103 must compare verifier predictions and released answers with independent labeled Claim/Evidence data, baselines and operational measurements. Using the same Verifier output as its own ground truth is circular.
