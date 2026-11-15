# Day105 Classroom Record — RAG Security Boundaries

## Teaching mode

The lesson used one compact concept and one question at a time. Teacher-provided answers did not count as
mastery until a changed-condition question was answered independently. The fixed A/B/C and Q1/Q2/Q3 fixture
continued from Day104; X/Y/Z/T were separate attack fixtures.

## Day104 handoff

The learner first confused a ReadView with the BuildSnapshot and proposed rebinding an in-flight request to a
new Generation after authorization changed. Remediation established:

```text
BuildSnapshot = immutable build-time S/P/E/IS/W/D identity
ReadView       = request-time Generation/pointer/fence binding
current authorization may change and is rechecked before release
```

The learner then independently kept a pointer-switched request on its original ReadView, rejected equal-count
`{A,B}` substitution for expected `{A,C}`, and blocked A after current authorization revocation without waiting
for rebuild.

## Threat model and authority

The learner distinguished document injection, corpus poisoning, direct query injection, provenance forgery,
cross-document chains, cross-tenant context exposure and response exfiltration. Important corrected boundaries:

- `authorized != safe` and `safe != authorized`;
- provenance proves origin, not instruction authority;
- official retrieved policy remains data unless admitted through an independent trusted control path;
- Tool output and model output cannot grant permission;
- X is authorized-but-malicious while T is unauthorized even if benign.

## Ingestion and evidence status

Detector timeout was correctly mapped to `INCONCLUSIVE` and quarantine. The learner initially used `FAIL` for
missing new-policy evidence and later mixed `QUARANTINE` with evidence status. Changed-condition questions
established:

```text
observed attack       → FAIL
missing/timeout       → INCONCLUSIVE
not executed          → NOT_RUN
quarantine/deny/wait  → operational action
```

Content digest changes became new versions and new evidence; sealed Generations and old reports remained
append-only. Manual review required reviewer identity, authority, reason, exact digest and original detector
evidence rather than overwriting the failure.

## Retrieval and context

The learner independently rejected cross-security-version mixing, applied least context to exclude C from Q1,
and treated delimiters/escaping as defense in depth. A visualization then separated lifecycle, authority,
security gates, request binding, result semantics and incident flow. The learner correctly placed T at the
retrieval authorization boundary and X at context/output boundaries when an earlier detector missed it.

The contract exercise clarified that a Retrieval Security Decision emits exact allowed/denied IDs, a Retrieval
Bundle contains allowed evidence only, and a Context Assembly Manifest records the actual subset and exact
assembly identities.

## Model, output and disclosure

The learner required application-owned Tool admission beyond schema validity and kept unnecessary secrets out
of model context. Exact citation support remained independent from citation authorization. DLP timeout produced
`INCONCLUSIVE/BLOCKED`; a detected secret produced `FAIL/BLOCKED`. The Disclosure Envelope enforced purpose,
audience, allowed fields, destination and budget, and missing authorized evidence produced abstention.

## Cache, incident and recovery

The learner invalidated cache after authorization revision and rejected rollback based only on physical
namespace or an old replayable report. Remediation corrected three recovery mistakes:

- current revocation stops serving before rebuild;
- durable quarantine/Tombstone truth is updated before a new BuildSnapshot;
- a stale-cache-only bug does not require rebuilding a correct G2.

For an actual credential leak, the learner independently explained why deletion cannot revoke an external copy,
required rotation and impact analysis, and preserved append-only correction events. Canary validation was
corrected as a supplement rather than an incident-closure substitute.

## Evaluation and hard gates

Reject-all was initially labeled `NOT_RUN`; remediation established that executed Q1/Q2/Q3 failures make the
overall result `FAIL`. The learner then independently applied non-compensable gates, stage-by-stage attack-path
measurement and current evidence applicability beyond checksum integrity.

## Contract derivation

The learner derived all ten contracts with field-by-field guidance. Recurring corrections separated:

- observation record from eligibility decision;
- producer from contract owner and release owner;
- request-scoped derived object from content-safe durable audit;
- current failure reason from invalidation of an older decision;
- incident decision owner from audit storage.

## Assessment

```text
Threat model and trust/authority             18/20
Identity/version/invalidation                16/20
Retrieval/context isolation                  18/20
Output release/data leakage                  18/20
Incident/rebuild/evidence boundary           16/20
Total                                        86/100
```

Result: `PASS` after guided remediation. The learner is ready for the Day105 L2 repository implementation.
This classroom result is not executable runtime evidence and does not authorize L3, Docker or production claims.

## Remaining weak areas

- result versus disposition vocabulary;
- failure reason versus invalidator;
- producer, contract owner, decision owner and storage separation;
- independent derivation of complete contract fields without prompts;
- immediate containment versus later rebuild and incident closure.

These distinctions must remain explicit in tests, seed cases and saved evidence.
