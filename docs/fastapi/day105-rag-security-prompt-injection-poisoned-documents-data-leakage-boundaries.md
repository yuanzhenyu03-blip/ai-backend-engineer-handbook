# Day105 — RAG Security: Prompt Injection, Poisoned Documents and Data-leakage Boundaries

## 1. Lesson Metadata

- **Status:** Completed at guided classroom Level 2; executable repository validation recorded separately
- **Template:** `LESSON_TEMPLATE_v2`
- **Phase:** 7C — Production RAG Engineering
- **Difficulty:** Advanced
- **Estimated study time:** 8–10 hours
- **Prerequisites:** Day95–Day104, especially provenance, authorization, grounding,
  evaluation and immutable Generations
- **Previous lesson:** [Day104](day104-index-update-delete-rebuild-and-migration.md)
- **Next lesson:** Day106 — Production RAG Capstone and English Interview
- **Main artifact:** application-owned ingestion, retrieval, context and response-release security boundaries
- **Learning assessment:** 86/100 after guided remediation
- **Evidence boundary:** deterministic local mechanics only; L3 and L4 remain `NOT_RUN`
- **Production readiness:** `MORE_EVIDENCE_NEEDED`

The learning score measures conceptual and contract mastery. It is not runtime, integration or production
evidence. Executable counts and checksums belong only in generated evidence records after the commands run.

## 2. Learning Objectives

By the end of Day105, the learner can:

- distinguish direct injection, document injection, corpus poisoning, provenance forgery, cross-document chains,
  unauthorized retrieval and response exfiltration;
- explain why retrieved content is data rather than instruction authority;
- bind content-security evidence to exact source, occurrence, digest, parser, detector and policy identities;
- fail closed on unavailable, stale or incompatible evidence without confusing result and disposition;
- keep unauthorized occurrences out of model context and apply least-context selection;
- freeze one request-scoped security artifact chain beside the Day104 ReadView;
- separate Retrieval Security Decision, Retrieval Bundle and Context Assembly Manifest;
- treat model output and Tool calls as candidates requiring application-owned admission;
- validate grounding, exact citations, authorization, DLP (Data Loss Prevention, 数据泄漏防护), metadata and
  disclosure before response release;
- invalidate caches and old decisions on currentness changes;
- contain poisoned content before rebuild and preserve append-only incident evidence;
- preserve normal Q1/Q2/Q3 quality while critical attack success stays zero;
- state what deterministic L2 does not prove.

## 3. Why This Matters

Day104 can prove that the application selected the exact sealed Generation, that a result belongs to its
Manifest, that B is tombstoned, and that current authorization permits an occurrence. None of those facts makes
the occurrence a system instruction. A perfectly consistent index can consistently deliver malicious text.

RAG adds an authority-confusion boundary: natural-language evidence and trusted policy share a model context.
The application must preserve the distinction even when a detector misses an attack. It must also treat response
text, citations, caches, logs, telemetry and external destinations as separate egress sinks.

## 4. Roadmap Position

```text
Day103  measure retrieval and answer quality
Day104  build, validate, activate and retire the correct immutable Generation
Day105  prevent retrieved data from taking authority or crossing disclosure boundaries
Day106  compose quality, lifecycle and security into the Production RAG Capstone
```

Day105 inherits, rather than replaces, the Day104 [handoff](../../projects/ai-agent/docs/DAY104_TO_DAY105_HANDOFF.md).
It also reuses Day86 principles only where they touch RAG; this is not a second general Agent-security lesson.

## 5. Lesson Map

```text
durable source
→ provenance / authorization
→ content-security assessment
→ immutable Generation
→ retrieval + ReadView
→ retrieval release gate
→ Context Assembly Manifest
→ Model Invocation Envelope
→ AnswerCandidate
→ Disclosure Envelope + Output Release Decision
→ response / audit / incident / rebuild
```

Fixed normal fixture:

```text
A@v1 — current refund window: 14 days          Q1 → A@v1
B@v1 — superseded 30-day policy, D1 Tombstone
C@v1 — current channel: online service         Q2 → C@v1
                                                 Q3 → A@v1 + C@v1
```

Independent attack fixtures:

```text
X@v1       document instruction attempting authority or disclosure
Y@v1       forged/hidden/ranking-manipulated poisoned content
Z1 + Z2    individually mild documents that compose an attack chain
T@v1       semantically similar private occurrence from another tenant
```

These identities never rewrite A/B/C history. `G2` does not imply any document version.
`X` is a stable logical source/document ID, while `@v1` is that source's immutable version; together `X@v1`
names the occurrence identity used in this lesson. It is not a Generation, and `G2` never means document v2.

Here, the **corpus** is the set of documents/occurrences eligible for RAG ingestion, indexing and retrieval.
Corpus poisoning changes that set's membership, provenance/metadata or ranking exposure so malicious, forged or
stale content becomes more likely to be retrieved; it does not require a literal injection instruction in the
document body.

## 6. Core Mental Model

```text
application-owned trusted control path
        owns task, authorization, Tool policy, destination and disclosure
                              |
                              v
user request → goal candidate | retrieved evidence → untrusted data
                              |
                              v
                         AnswerCandidate
                              |
                              v
                  application-owned release gate
                              |
                       response or block
```

Provenance proves origin and integrity only. Delimiters, escaping, regexes, classifiers and LLM judges reduce
risk but never grant authority. The architecture assumes false negatives.

## 7. Main Concepts

### Threat location and asset

- Query text attempting to expand task, purpose, audience, fields, destination or authorization is direct
  prompt injection.
- Retrieved instructions attempting to become system/developer policy are document prompt injection.
- Poisoning changes corpus membership, provenance, ranking or top-k exposure.
- Z1/Z2 requires bundle-level analysis because models compose meaning across documents.
- T must be removed before Prompt construction; filtering only the final prose is too late.

### Ingestion identity and fail-closed decisions

Content-security evidence binds exact source/version, occurrence, tenant/resource, content digest, provenance
revision, parser, scanner/detector and security-policy versions. Missing required evidence produces
`INCONCLUSIVE`; a confirmed attack produces `FAIL`; a check that did not execute remains `NOT_RUN`.
`WAIT`, `QUARANTINE` and `DENY` are dispositions, not evidence results.

Evaluation also separates a gate's contract outcome from the end-to-end defense result. A content detector may
return `FAIL` for X while the security case passes because X was blocked before Prompt construction. The saved
seed therefore records `stage_decisions`, `required_evidence_status` and the final hard-gate `decision`
separately; it never relabels a detected attack as content-security `PASS` merely because containment worked.
Its `normal_quality_control_pass` is the result of a separate Q1/Q2/Q3 control suite, not a claim that every
fault-injection request returned an answer.

### Request-scoped security artifact chain

The pre-retrieval `RequestSecurityBinding` freezes request/principal/tenant/purpose and the validated Day104
Generation/Manifest/ReadView receipt plus current policy identities. RetrievalBundle and ContextAssemblyManifest
then add the exact occurrence IDs and content digests. Together this request-scoped artifact chain also binds
current authorization, provenance, Tombstone/quarantine, parser/scanner/detector, retrieval config, prompt
template, context assembler, model/Tool policy, disclosure policy and evaluation-evidence identities. A change
cannot be silently mixed into the same attempt.

### Context and model boundary

The Retrieval Security Decision outputs exact allowed and denied occurrences. The Retrieval Bundle contains
only allowed evidence. The Context Assembly Manifest records the actual subset, order, budget, projection,
serialization and template identities. XML or delimiters mark data boundaries but do not guarantee compliance.
The Model Invocation Envelope is built by the application. The model produces only an AnswerCandidate.

### Response release

The Disclosure Envelope fixes purpose, audience, allowed fields, destination and disclosure budget. The Output
Release Decision validates claims, exact citations, current authorization/provenance, Tombstone/quarantine,
DLP/secret findings, metadata stripping and destination. DLP scans an outbound Candidate for secrets, PII,
protected metadata and destination-policy violations. A confirmed finding is `FAIL`; a timeout is
`INCONCLUSIVE`; both produce a blocked response rather than release. A correct body with an unauthorized or
unsupported citation still fails. If no authorized support remains, the safe answer is abstention rather than a
guess.

### Cache, rollback and incident recovery

Cache identity includes security and disclosure currentness, not merely tenant and query text. A historical
namespace or replayable old report does not make rollback eligible. On discovery, first revoke/quarantine at
serving time, then update durable truth, build a new Generation, validate/evaluate/CAS, and drain old requests.
An actual leak additionally requires credential rotation, impact analysis, notification/remediation where
required, monitoring and append-only audit. Rebuild cannot retract disclosed data.

## 8. Common Misconceptions

```text
❌ Official provenance means content is safe or authoritative.
✅ Provenance proves origin; ordinary retrieval remains data-only.

❌ Authorized means safe; safe means authorized.
✅ Authorization and content safety are independent axes.

❌ Escaping or an XML wrapper solves prompt injection.
✅ Safe serialization is defense in depth, not a policy gate.

❌ If the model refused, unauthorized context exposure did not happen.
✅ Unauthorized occurrence entering Prompt is already a hard-gate violation.

❌ QUARANTINE is an evidence result.
✅ PASS/FAIL/INCONCLUSIVE/NOT_RUN describe evidence; quarantine is a disposition.

❌ A cache bug always requires a new Generation.
✅ Repair the faulty derived layer when durable truth and active Generation are correct.

❌ Deleting the index ends a credential leak.
✅ Rotate the credential and run the incident process; the leak already left the system.
```

## 9. Engineering Trade-offs

- Strong identity binding increases storage and invalidation work but prevents stale-evidence substitution.
- Quarantine and manual review reduce false negatives but can create false positives and availability loss.
- Least context lowers attack surface and cost but must preserve Day103 quality thresholds.
- Bundle-level analysis costs more than per-document scanning but detects composition attacks.
- Content-safe audit limits forensic detail; controlled protected evidence access may still be required.
- Blocking on unknown evidence increases latency but avoids converting detector failure into authorization.
- Separating candidate generation from release adds components but makes model behavior non-authoritative.

Reject-all is not an acceptable trade: critical security gates and normal Q1/Q2/Q3 gates are jointly
non-compensable.

## 10. Hands-on Exercises

1. Model the ten contracts: Ingestion Decision, Content/Provenance Record, Retrieval Decision, Retrieval Bundle,
   Context Assembly Manifest, Model Invocation Envelope, AnswerCandidate, Disclosure Envelope, Output Release
   Decision and Incident/Revocation Record.
2. Demonstrate X remains data even after an ingestion false negative.
3. Reject Y on provenance/digest mismatch and on stale detector evidence.
4. Detect Z1/Z2 only at bundle level.
5. Keep T out of Prompt, citations, caches and audit payloads.
6. Prove B cannot return from stale cache or physical storage.
7. Fail closed on detector/DLP timeout while normal Q1/Q2/Q3 remain available.
8. Replay content-safe evidence with exact configuration identities.

The deterministic implementation and commands are documented in the
[design](../../projects/ai-agent/docs/DAY105_RAG_SECURITY_BOUNDARIES.md).

## 11. Relevant Framework Connections

- FastAPI dependencies or middleware can acquire the Day104 ReadView and request security binding once.
- Pydantic-style schemas can represent envelopes and decisions, but schema validation is not authorization.
- PostgreSQL transactions can persist append-only decisions and revocations; Day105 L2 does not prove them.
- Vector providers may execute tenant filters, but the application remains policy authority.
- Model gateways can enforce egress and secret handling; ordinary model refusal remains defense in depth.

No framework is allowed to collapse retrieved data, model output and application-owned policy into one trust
level.

## 12. AI Backend Connections

The production boundary connects:

- ingestion provenance and malware/content scanning;
- policy decision and enforcement points;
- immutable vector-generation lifecycle;
- prompt construction and model gateway controls;
- claim/citation verification and DLP;
- cache key design and revocation propagation;
- incident response, audit and rebuild orchestration.

Each output is consumed as evidence by a later owner. No component self-approves its own output.

## 13. English Interview

**Question:** Why is retrieved content not trusted instruction even when it comes from an official source?

**Answer:** Provenance proves origin and integrity, not benign intent or instruction authority. I treat every
retrieved occurrence as data. The application independently owns task scope, authorization, Tool capability,
destination and disclosure. I bind the request to one Generation, ReadView and security-policy revision, filter
unauthorized occurrences before the model, analyze the final bundle, and validate the AnswerCandidate at an
independent release gate. Missing evidence fails closed, while normal quality gates prevent a reject-all design.

**Follow-up:** What happens after a poisoned document causes a real credential leak?

**Answer:** I immediately revoke serving eligibility and rotate the credential. Then I perform impact analysis,
preserve append-only incident evidence, update durable truth, build and validate a new immutable Generation,
activate it with CAS and drain old readers. Rebuilding the index cannot retract data already disclosed.

## 14. Mental Model Summary

```text
Day104: Did the application select the exact current Generation?
Day105: May each exact occurrence influence facts, and may this exact candidate leave this exact sink?

retrieved content = data
model output       = candidate
application gate   = authority
```

Security is a sequence of independently owned decisions, not a stronger prompt.

## 15. Today's Takeaway

The central invariant is:

> Retrieved evidence may influence a factual answer, but it cannot change the task, authorization, Tool
> capability, security policy, destination or disclosure scope.

Day105 adds current, identity-bound content and egress controls without weakening Day104 Generation, Manifest,
ReadView, authorization or Tombstone gates.

## 16. Before Next Lesson Checklist

- [ ] I can separate direct injection, document injection and corpus poisoning.
- [ ] I can explain provenance versus authority.
- [ ] I can bind security evidence to exact content and processing identities.
- [ ] I can distinguish evidence result from operational disposition.
- [ ] I can keep unauthorized occurrences out of Prompt.
- [ ] I can explain Bundle versus Context Assembly Manifest.
- [ ] I can explain Model Invocation Envelope and AnswerCandidate ownership.
- [ ] I can apply Disclosure Envelope, exact citation and DLP gates.
- [ ] I can invalidate cache and stale rollback evidence.
- [ ] I can sequence containment, durable update, rebuild and incident response.
- [ ] I can preserve normal Q1/Q2/Q3 quality beside zero critical attack success.
- [ ] I can state that deterministic L2 is not L3 or production evidence.

Proceed to Day106 only after the saved Day105 L2 evidence is complete and any requested L3 scope is separately
authorized and executed.

Post-seal note: PR #18 merged to `main`, and its [append-only CPython 3.12 CI record](../../projects/ai-agent/evidence/day105-pr18-ci-validation.json)
shows 1334 tests PASS with 7 skipped, 21 seed evaluators PASS, seven saved evidence replays PASS and the Day105
replay PASS. CI did not start Docker/PostgreSQL/pgvector or run Day105 L3; the L3 and production boundaries above
remain unchanged.
