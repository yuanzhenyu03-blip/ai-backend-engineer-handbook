# Day105 Application Design — RAG Security Boundaries

## Scope

Day105 places application-owned security decisions around the unchanged Day104 lifecycle. It proves
deterministic contract and state-machine mechanics only. Real model, detector, DLP, policy service, database,
vector Provider and production egress remain `NOT_RUN`.

## Frozen Day104 handoff

```text
BS1 = S1 + P1 + E1 + IS1 + W1 + D1
active pointer = refund-serving@G2/r8
G2 = ACTIVE / state_version 10
G1 = RETIRED / state_version 8
eligible = A@v1, C@v1
tombstoned = B@v1
```

Day105 consumers must use the application pointer and one request-scoped ReadView. Generation names never imply
document versions.

## Fixtures

```text
A@v1  current 14-day refund fact
B@v1  historical 30-day fact, D1 Tombstone
C@v1  current online-service channel
X@v1  authorized content carrying a document-instruction attempt
Y@v1  forged/hidden/ranking-manipulated poison candidate
Z1/Z2 cross-document chain
T@v1  another tenant's private occurrence
```

Evidence stores identities and digests, never reusable attack payloads, real secrets or other-tenant text.

## Ownership

| Boundary | Owner | Consumes | Emits |
|---|---|---|---|
| Ingestion security | application security control plane | content/provenance/detector evidence | versioned decision |
| Retrieval security | application retrieval gate | candidates + ReadView + current state | exact allowed/denied IDs |
| Context assembly | application context builder | allowed Bundle | exact assembly Manifest |
| Model invocation | application runtime | trusted policy + Manifest | immutable Invocation Envelope |
| Candidate generation | model adapter | Envelope | untrusted AnswerCandidate |
| Disclosure | application policy | principal/purpose/audience/destination | Disclosure Envelope |
| Output release | application release gate | Candidate + current evidence | RELEASE/ABSTAIN/BLOCKED |
| Incident/revocation | application incident control plane | violation/impact evidence | append-only actions/events |

Scanner, model, retriever and Provider outputs are evidence or candidates. They never self-approve.

## Ten contracts

All records bind stable IDs, versions, content-safe digests, timestamps and reason codes.

1. `IngestionSecurityDecision` — `PASS/FAIL/INCONCLUSIVE/NOT_RUN` plus eligibility disposition.
2. `ContentProvenanceSecurityRecord` — immutable observed origin, digest and processing evidence.
3. `RetrievalSecurityDecision` — exact allowed and denied occurrence IDs for one request binding.
4. `RetrievalBundle` — immutable allowed occurrences only; denied content never enters the model path.
5. `ContextAssemblyManifest` — exact subset/order/projection/budget/serialization/template identity.
6. `ModelInvocationEnvelope` — application-built trusted policy plus explicitly untrusted context.
7. `AnswerCandidate` — model-produced claims, proposed citations and optional proposed Tool intent.
8. `DisclosureEnvelope` — purpose, audience, allowed fields, destination and disclosure budget.
9. `OutputReleaseDecision` — normalized result, disposition, reason codes and evidence digests.
10. `SecurityIncidentRecord` — append-only detection, containment, impact and superseding events.

## Request-scoped security artifact chain

```text
request/principal/tenant/purpose
+ Generation/Manifest/pointer revision
+ ReadView generation/revision/fence
+ exact occurrence IDs/content digests
+ current authorization/provenance/Tombstone/quarantine revisions
+ content-security snapshot and policy
+ parser/scanner/detector versions
+ retrieval config + prompt template + context assembler
+ model/Tool/output policy
+ Disclosure Envelope
+ adversarial-set and evidence digests
```

`RequestSecurityBinding` owns the pre-retrieval request, Day104 receipt and policy identities. RetrievalBundle
and ContextAssemblyManifest add exact occurrence IDs/digests after the application has filtered candidates.
Together the chain above is the finalized request-scoped security identity. A bound identity change requires
explicit invalidation or re-evaluation. One attempt never mixes old content with new security evidence or
different Generations.

## Result and disposition

```text
PASS         required evidence proves the gate
FAIL         an observed non-compensable violation exists
INCONCLUSIVE attempted evaluation lacks sufficient current evidence
NOT_RUN      the assertion did not execute

WAIT / QUARANTINE / DENY / RELEASE / ABSTAIN / BLOCKED
              operational dispositions, not evidence results
```

An observed FAIL remains overall FAIL even beside an unknown detector. A detector timeout never defaults PASS.

## State transitions

```text
UNASSESSED ──complete current evidence──> ELIGIBLE
     │              │
     │ missing      └──observed violation──> DENIED
     v
  WAIT/QUARANTINED ──new current evidence──> re-evaluate
```

Sealed Generations are never edited. A serving-time revocation can immediately deny an occurrence while a new
BuildSnapshot and Generation are prepared.

## Retrieval and assembly gates

1. Acquire one valid ReadView.
2. Validate Generation/Manifest/exact candidate identity.
3. Apply tenant and current authorization before Prompt construction.
4. Apply current provenance, Tombstone and quarantine state.
5. Select least context and freeze an allowed Retrieval Bundle.
6. Analyze the complete Bundle for cross-document composition.
7. Serialize as explicitly untrusted data under a versioned assembler/template.

X may pass authorization yet remain malicious. T may be benign yet unauthorized. The architecture tests both
axes independently.

## Output release gates

The model produces an `AnswerCandidate`, never a response. Release requires:

- grounded claims and exact supporting citations;
- current tenant/authorization/provenance/Tombstone/quarantine checks;
- allowed purpose, audience, fields, destination and disclosure budget;
- DLP/secret and sensitive-metadata validation;
- no system/developer prompt or protected context disclosure;
- content-safe release evidence bound to this Candidate and request.

If no authorized support remains, abstain. A blocked response must not expose detection rules or sensitive data.

## Cache and TOCTOU

Cache identity includes Generation, exact occurrences, current authorization/provenance/deletion/security
revisions, template/assembler/model/output policies and Disclosure Envelope. Cache hits recheck current release
eligibility. Historical namespace existence or an intact old report never proves rollback eligibility.

## Incident sequence

```text
serving-time revoke/quarantine
→ invalidate affected caches and sinks
→ update authoritative security/deletion state
→ preserve append-only incident evidence
→ new BuildSnapshot/Generation
→ validation + Day103 quality + Day105 security evaluation
→ pointer CAS
→ drain/retire
```

If disclosure occurred, additionally rotate credentials, analyze impact, notify/remediate as required and
observe for abuse. Index deletion cannot retract external disclosure.

## Deterministic evaluation

Normal Q1/Q2/Q3 and adversarial X/Y/Z/T slices execute together. Hard gates include zero unauthorized Prompt
occurrences, cross-tenant disclosure, B resurrection, protected metadata leakage and critical attack success.
Exact citations and normal request coverage are also non-compensable. Reject-all is FAIL.

Each seed keeps three meanings separate: `stage_decisions` are real contract outcomes (for example a detector
may correctly return `FAIL` for X); `required_evidence_status` says whether that outcome has complete current
evidence; the case `decision` says whether the end-to-end defense satisfied its hard gates. A detected attack
that is excluded before Prompt can therefore have a stage `FAIL` and a defense `PASS`; missing evidence remains
`INCONCLUSIVE`, while an attack that crosses a critical boundary makes the defense `FAIL`.
The `normal_quality_control_pass` value comes from the independent Q1/Q2/Q3 control suite, not from expecting a
fault-injection request to return an answer. Its non-compensable gate prevents reject-all behavior from passing
the overall evaluation.

## Code and evidence map

- `src/` — Day105 contracts and deterministic security pipeline.
- `tests/test_day105_*.py` — normal, adversarial, identity, failure and incident tests.
- `examples/day105_rag_security.py` — fixed deterministic walkthrough.
- `evals/day105_rag_security_seed.jsonl` — content-safe normal/adversarial cases.
- `evals/run_day105_seed_eval.py` — hard-gate evaluator.
- `evals/run_day105_evidence_replay.py` — offline saved-evidence verifier.
- `evidence/day105-rag-security-report.json` — generated content-safe report.
- `evidence/day105-validation.json` — executed validation boundary.
- [`evidence/day105-pr18-ci-validation.json`](../evidence/day105-pr18-ci-validation.json) — append-only post-seal
  PR #18 CPython 3.12 CI evidence.

## Evidence boundary

L2 may prove deterministic identity, policy, state, failure and replay mechanics with fakes. It does not prove
real detector recall, real DLP, model robustness, Provider isolation, database durability, production IAM/TLS,
red-team coverage, load/soak, canary traffic or incident operations. L3 and L4 remain `NOT_RUN` until separately
authorized, executed and saved.

The post-seal CI record proves that the deterministic suite, 21 seed evaluators, seven saved evidence replays
and the Day105 replay passed on CPython 3.12.16. It did not start Docker/PostgreSQL/pgvector or run Day105 L3,
and it does not replace or modify the sealed Day105 validation/report records.
