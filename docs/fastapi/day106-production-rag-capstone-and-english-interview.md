# Day106 — Production RAG Capstone and English Interview

## 1. Lesson Metadata

- Phase: 7C — Production RAG
- Type: cumulative capstone, runnable checkpoint and interview
- Runtime target: deterministic local Level 2
- Fixed domain: refund policy A/C, tombstoned B and adversarial X/Y/Z/T
- Prerequisites: Day95–Day105 contracts and their honest evidence boundaries

## 2. Learning Objectives

By the end of Day106, the learner can:

1. separate durable business truth, derived artifacts, application decisions and external outcomes;
2. preserve one exact identity spine from committed source lineage through release and delivery;
3. explain why ReadView pinning preserves historical identity but not permanent authorization;
4. rebuild and CAS-activate an immutable Generation after revocation;
5. keep retrieval security, grounding, DLP/disclosure and release as independent gates;
6. recover safely from unknown dispatch outcomes without duplicate side effects;
7. make evidence and readiness claims no stronger than the executed boundary;
8. explain the complete system in an English architecture interview.

## 3. Why This Matters

Independent component PASS reports do not prove that their results belong to one execution. A production RAG
answer is releasable only when exact source occurrences, one Generation/ReadView, one request attempt, one
candidate and current release evidence form a continuous application-owned chain. The capstone turns the
previous lessons into a runnable subsystem rather than a slide-only architecture.

## 4. Roadmap Position

Day95–99 establish ingestion, ChunkSet, authorization, EmbeddingSet and immutable vector artifacts. Day100–102
establish authorized retrieval, reranking, grounding and exact citations. Day103 supplies evaluation semantics,
Day104 owns Generation lifecycle and Day105 owns security/release boundaries. Day106 composes them. Day107
begins Phase 7D and may extend evaluation and operations; Day106 does not pre-implement that scope.

## 5. Lesson Map

```text
committed source lineage
→ immutable BuildSnapshot / Generation
→ application pointer CAS / request ReadView
→ Day100 retrieval + Day101 reranking
→ Day105 retrieval security / RetrievalBundle / ContextAssemblyManifest
→ ModelInvocationEnvelope
→ Day102 deterministic generation + grounding + exact-citation verification
→ AnswerCandidate
→ current authorization + provenance + deletion + security rechecks
→ DLP + destination + DisclosureEnvelope
→ durable OutputReleaseDecision + ResponseIntent
→ dispatch / reconciliation / DeliveryReceipt
→ Day103-style hard-gate evaluation
→ seal runtime report with offline replay = NOT_RUN
→ run independent content-safe offline replay
```

## 6. Core Mental Model

Four flows must agree:

| Flow | Question |
|---|---|
| Data | What moves? |
| Control and authority | What permits it? |
| Identity and version | Which exact execution and artifact? |
| Evidence and audit | How can the claim be proved later? |

The model, retriever and vector store contribute results. The application owns source eligibility, serving
selection, release and dispatch decisions.

## 7. Main Concepts

### Composition, not parallel authority

Day106 reads the existing document/version, ChunkSet, EmbeddingSet and Generation owners. Its new receipts bind
their IDs, revisions, fences and digests; they cannot activate or rewrite those artifacts.

### Pre- and post-retrieval identity

`CapstoneRequestBinding` pins request/principal/tenant/purpose, pointer, Generation, BuildSnapshot and ReadView.
It cannot claim retrieved occurrences. `RetrievalAndContextReceipt` later appends the actual RetrievalBundle,
exact occurrence/content digests and ContextAssemblyManifest. The intervening `Day101ExecutionReceipt` is
authenticated by an application-owned issuer; a caller cannot make a foreign query/hit pairing authoritative
by changing all of its public digest fields together.

### Revocation and rebuild

```text
P1 + BS1 + G2/r8 = {A@v1, C@v1}
P2 revokes A immediately
old G2 ReadView remains historical identity, but release recheck blocks A
BS2 freezes current facts
G3 = {C@v1}
CAS G2/r8 → G3/r9
new requests acquire G3/r9 and rerun downstream work
```

### Candidate, decision and delivery

`AnswerCandidate`, `OutputReleaseDecision`, `ResponseIntent`, dispatch acceptance and `DeliveryReceipt` are
different facts. `ALLOWED` does not mean `DISPATCHED`; `DISPATCHED` does not mean `DELIVERED`.

### Unknown outcomes

An unknown response never proves the Provider did nothing. Persist the attempt and idempotency key, reconcile,
and retry only after authoritative `NOT_FOUND`. Duplicate receipts converge through exact identity and do not
rewrite the candidate or decision. Recovery record IDs are unique across the whole ledger, not merely within
one intent, and the same rule applies during live append, restore and sealing.

Current authorization is guarded through the model invocation itself. A recheck just before the call is not
enough if revocation can race between that check and protected Prompt egress; the local L2 guard closes that
in-process interval, while distributed enforcement remains outside this evidence boundary.

### Evidence tiers

The Day106 checkpoint uses in-process deterministic adapters and therefore records
`EXECUTED_LOCAL_RUNTIME`. The current local execution uses Python 3.11.5; canonical CPython 3.12 local
validation is `NOT_RUN`. Day104/105 local PostgreSQL/pgvector evidence is prerequisite evidence, not inherited
Day106 integration evidence. Day95–99 are represented by manually aligned, content-safe lineage receipts in this
fixture; their authoritative stores are not rerun by the Day106 checkpoint.

Later append-only repository evidence records PR #21 and its merge commit passing the configured workflow. The
workflow replayed the exact sealed L2 checkpoint on CPython 3.11.5 and ran the current deterministic/unit suite,
structured-evidence parsing and saved L3A/L3B replay on CPython 3.12.16. It did not start
Docker/PostgreSQL/pgvector or call an external model Provider, detector or DLP, so it is compatibility and
offline-replay evidence—not a CPython 3.12 re-execution of L3. See
[`day106-pr21-ci-validation.json`](../../projects/ai-agent/evidence/day106-pr21-ci-validation.json).

## 8. Common Misconceptions

- “Every component passed, so the answer can release.” Results may belong to different executions.
- “A pinned ReadView freezes permission.” It freezes identity; authorization is rechecked.
- “Same text means the same occurrence.” Occurrence identity comes from committed lineage, not string equality.
- “The model grounded the answer, so it may release.” Grounding does not grant disclosure or destination rights.
- “Timeout means retry.” Unknown side effects require reconciliation first.
- “Checksum replay proves the original behavior was correct.” It proves saved evidence integrity and deterministic
  replay, not the legality of authorization or an unexecuted production boundary.

## 9. Engineering Trade-offs

- More explicit receipts increase storage and implementation cost but prevent cross-execution evidence mixups.
- Immutable Generations require rebuilds but make readback, rollback eligibility and audit tractable.
- Fail-closed security may reduce availability; normal Q1/Q2/Q3 quality remains a non-compensable gate so
  reject-all cannot masquerade as safety.
- In-process deterministic adapters make L2 fast and reproducible but cannot prove database, Provider or
  production enforcement. Export/restore of the response ledger is same-process deterministic rehydration, not
  proof of a real process or container restart.

## 10. Hands-on Exercises

Run from `projects/ai-agent`:

```bash
PYTHONPATH=src:. python examples/day106_production_rag_capstone.py
PYTHONPATH=src:. python evals/run_day106_seed_eval.py
PYTHONPATH=src:. python evals/run_day106_evidence_replay.py
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_day106_*.py' -q
```

Inspect the G2/P1 normal path, P2 old-candidate block, G3/r9 Q2 success, Q1/Q3 safe block, X/Y/Z/T/B negative
controls and `UNKNOWN → reconciliation → bounded retry → DELIVERED` history.

## 11. Relevant Framework Connections

- Python frozen dataclasses express immutable value contracts.
- Injected deterministic adapters preserve Provider boundaries without claiming real integration.
- Application-owned stores model CAS, fencing, append-only history and idempotent recovery.
- JSONL seed evaluation and offline replay provide content-safe regression evidence.

## 12. AI Backend Connections

The same design applies to enterprise assistants, support search, policy QA and agentic systems: retrieval is not
authorization, citations are not disclosure permission, model output is not an application decision, and
external side effects require durable intent plus reconciliation.

## 13. English Interview

Prompt: “Walk me through the normal request path, identity/version binding, revocation and rebuild, security
and egress, failure recovery, and evaluation readiness.”

A strong answer should state that the application selects one Generation/ReadView, lets Day101 retrieve/rerank,
runs Day105 security and exact context assembly before creating the `ModelInvocationEnvelope`, then lets Day102
generate and verify grounding/citations. Day105 still owns final release. The application atomically records the
decision and response intent, reconciles unknown delivery outcomes, and limits readiness claims to the executed
evidence tier.

## 14. Mental Model Summary

```text
historical identity is durable
current permission is rechecked
derived artifacts are immutable and rebuildable
application decisions are explicit and durable
external outcomes are append-only observations
evidence scope limits every readiness claim
```

## 15. Today's Takeaway

A production RAG system is not a chain of individually good components. It is one application-owned,
version-bound, fail-closed execution whose release and delivery claims remain provable without retaining
protected content.

## 16. Before Next Lesson Checklist

- [ ] One request attempt uses one Generation/ReadView identity.
- [ ] Exact occurrences join only after retrieval.
- [ ] Unauthorized occurrences entering Prompt equals zero.
- [ ] Current authorization is rechecked before release.
- [ ] The Day101 handoff is application-authenticated and authorization stays guarded across model invocation.
- [ ] Candidate, decision, intent, dispatch and delivery are distinct.
- [ ] Recovery event identities are globally unique and append-only.
- [ ] Unknown outcomes reconcile before retry.
- [ ] Normal quality and security hard gates pass together.
- [ ] L2, L3 and production claims remain separate.
- [ ] Runtime sealing does not claim replay PASS before the independent replay executes.
