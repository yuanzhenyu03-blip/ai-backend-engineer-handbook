# Day102 — Grounding, Citations and Source Verification

## 1. Lesson Metadata

- **Status:** Completed at guided classroom scope
- **Template:** `LESSON_TEMPLATE_v2`
- **Phase:** 7C — Production RAG Engineering
- **Difficulty:** Advanced
- **Estimated study time:** 6–8 hours
- **Prerequisites:** Day95–Day101, especially occurrence identity, authorization, provenance and reranking
- **Previous lesson:** [Day101 — Query Rewriting and Re-ranking](day101-query-rewriting-and-re-ranking.md)
- **Next lesson:** Day103 — Retrieval Evaluation and RAG Answer Evaluation
- **Main artifact:** application-owned immutable Grounding Bundle, Claim/Citation Verification and guarded answer-release subsystem
- **Evidence:** `EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`
- **Production readiness:** `MORE_EVIDENCE_NEEDED`

## 2. Learning Objectives

By the end of Day102, the learner can:

- explain why relevance, authorization and evidentiary support are different judgments;
- admit only a trusted current Day101 handoff;
- plan bounded context across request facets instead of mechanically selecting top-k;
- freeze exact source-window identity, version, span and digest;
- treat retrieved content as untrusted data rather than executable instructions;
- separate Generator and Verifier egress authority;
- extract atomic Claims while preserving scope, negation and modality;
- distinguish Evidence content from Citation location;
- validate Citation membership inside the Grounding Bundle;
- classify support, non-support, contradiction and verifier unavailability;
- distinguish rejected Claims from abstained request items;
- assemble partial answers only from released Claims;
- recheck source authorization and provenance immediately before release;
- bind cache identity to both authority and content state;
- preserve upstream/fallback degradation without rewriting history;
- hand structured independent-evaluation inputs to Day103.

## 3. Why This Matters

Day101 can correctly place A ahead of B and C while A still supports only one sentence, contains stale policy, or fails to cover another part of the request. A Provider may produce a valid JSON schema and a real Citation pointer while attaching it to an unsupported Claim. A cached Verification PASS may refer to an old source version. A retrieved document may contain prompt-injection text that asks the model to ignore release rules.

Day102 is therefore not “prompt the model with the top chunk.” It is an application-owned identity, authority, context, semantic-verification, coverage and release boundary.

## 4. Roadmap Position

```text
Day95 source truth
→ Day96 immutable occurrences
→ Day97 authorization/provenance
→ Day98 embedding identity
→ Day99 index generation
→ Day100 authorized retrieval
→ Day101 query expression + candidate ordering
→ Day102 Claim/Evidence/Citation Verification
→ Day103 independent retrieval/answer evaluation
```

Day101 answers “what should be read first?” Day102 answers “what can be said, from which exact current evidence?” Day103 measures whether those decisions are accurate on independently labeled data.

## 5. Lesson Map

```text
trusted Day101 handoff
→ current source admission
→ request facets + context budget
→ immutable GroundingBundle
→ generator/verifier egress gates
→ candidate answer
→ atomic Claims + answer spans
→ exact Citations
→ source and semantic Verification
→ final currentness recheck
→ released/rejected Claims
→ Request Coverage + Abstention
→ structured response and Day103 evidence
```

## 6. Core Mental Model

```text
Day101: Candidate → Rank
Day102: Claim → Evidence → Citation → Verification → Release
```

Ranking proves relative priority under a ranking policy. Authorization proves a source may be used inside a scope. Neither proves that a passage supports every generated factual Claim.

The release invariant is:

```text
released_claims
⊆ supported_verified_claims

released_citation_targets
⊆ frozen_grounding_bundle_targets

grounding_occurrence_ids
⊆ final_current_day101_handoff_ids
```

## 7. Trusted Day101 Handoff

Day102 consumes the `Day101Response` orchestrator boundary, not the reranker Adapter. The handoff identity binds original-query identity, authorization scope, candidate-pool and validated-rerank digests, final ordered hits, source references, content hashes, upstream modes and release rejections.

Format-valid objects are not trusted handoffs. A caller cannot manufacture D, assign `rank=1`, and gain source authority. The request fails before Provider calls if the handoff digest, Query identity, tenant, hit identity, ranks or content hashes do not match.

## 8. Grounding Bundle and Context Planning

A Grounding Bundle is not a list of document names. It freezes:

- Query and request-item identities;
- trusted Day101 handoff identity;
- current authorization-scope fingerprint;
- selected occurrence identities;
- source versions, exact spans and content digests;
- context-window policy and contract identity;
- upstream outcome, reranker mode and degradation reason.

Context planning may skip global rank two to cover another request facet, but selected windows must remain a subset of current Day101 hits. The classroom implementation fails closed on oversized windows rather than truncating qualifiers, negation or exceptions at an unsafe character boundary.

## 9. Generator, Egress and Source-as-Data

Generator egress and Verifier egress are independent policy gates. Internal read authorization is not permission to transmit protected Query, Claim or source text to an external Provider.

Retrieved content is untrusted data. Source namespaces and structured blocks help, but documents cannot change authorization, Bundle membership, tools, Citation allowlists or release policy. The final user answer is never raw Provider prose; it is reassembled from Claims that survived application validation.

## 10. Claims, Evidence and Citations

A Claim is an independently verifiable factual statement tied to an exact answer span and digest. Terms such as “must,” “may,” “only,” “all,” quantities, dates and exceptions are part of the Claim.

Evidence is the source content that may support the Claim. Citation is the stable address used to find that Evidence:

```text
source occurrence
+ document version
+ exact span
+ evidence digest
```

Atomic Claims are preferred. A compound Claim may use multiple Citations only when Verification records which source supports which portion and checks the aggregate relation.

## 11. Source and Semantic Verification

Source Verification asks whether a source is current, authorized, provenance-consistent and not superseded. Semantic Verification asks whether the exact Evidence supports, fails to support or contradicts the Claim.

```text
valid Citation pointer
≠ current source
≠ semantic support
```

`UNSUPPORTED` and `CONTRADICTION` are completed judgments. Timeout and Provider failure are `UNAVAILABLE`; they must not be rewritten into a semantic result. Approved fallbacks remain explicit degradation history.

## 12. Coverage, Partial Answers and Abstention

Two coverage axes are stored:

- **Claim Coverage:** every released factual Claim has valid Evidence and Citation;
- **Request Coverage:** every requested item is either answered or explicitly abstained.

An existing invalid Claim is `REJECTED`. A requested fact that cannot produce a supported Claim is `Abstention`. If some request items have released Claims, Day102 may return a partial answer. If none do, it abstains entirely.

## 13. Cache, Replay and Currentness

Cache identity binds tenant, principal/authorization-scope digest, action, purpose, Query, request items, Day101 handoff, Grounding Bundle, Claim/Citation mapping, generator/verifier revisions and verification policy. Query-only or principal-only cache keys are unsafe.

Every release performs a new authorization/provenance/superseded-source check. A previous PASS, unexpired TTL or stable document name cannot override a changed source version or revoked permission.

## 14. Testing and Evidence

The deterministic suite covers:

- tampered Day101 handoff and zero Provider calls;
- exact Bundle and Citation subset boundaries;
- out-of-bundle and missing Citations;
- unsupported and contradicted Claims;
- generator/verifier egress denial;
- timeout and explicit fallback modes;
- final authorization/provenance/superseded-source removal;
- partial answer and Request Coverage;
- prompt-injection text excluded from final assembly;
- authorization- and Bundle-bound cache misses;
- real Day101 orchestrator-to-Day102 contract integration;
- saved report checksum replay.

```sh
PYTHONPATH=src:. python3.12 -m unittest discover -s tests -p 'test_day102_*.py' -q
PYTHONPATH=src:. python3.12 evals/run_day102_seed_eval.py
PYTHONPATH=src:. python3.12 evals/run_day102_evidence_replay.py
PYTHONPATH=src:. python3.12 examples/day102_grounding_citations.py
```

Deterministic evidence proves control flow and invariants only. Real generator, extractor, NLI/LLM verifier, labeled quality, protected egress, database/ANN, latency, capacity, cost, error rates and production remain `NOT_RUN`.

## 15. Interview Questions

### Question 1

Why is a top-ranked authorized candidate insufficient evidence for publishing a factual answer?

**Expected answer:** Ranking proves relative priority and authorization proves permitted use. Day102 must still bind each factual Claim to exact current Evidence and independently verify the semantic relationship before release.

### Question 2

Can a valid Citation point to Evidence that does not support the Claim?

**Expected answer:** Yes. Pointer validity and semantic support are separate. The application validates source identity/version/span and then verifies Claim/Evidence support.

### Question 3

What is the difference between `REJECTED` and `Abstention`?

**Expected answer:** `REJECTED` applies to an existing Claim/Citation artifact that fails validation. `Abstention` applies to requested information for which the system cannot form a supported Claim.

## 16. Completion Checklist and Day103 Handoff

- [ ] I can explain Day101 ranking versus Day102 evidence authority.
- [ ] I can derive the three subset invariants without notes.
- [ ] I can distinguish Bundle identity from Day101 rerank identity.
- [ ] I can preserve Claim scope, modality, negation and exceptions.
- [ ] I can distinguish Evidence, Citation, Source Verification and semantic support.
- [ ] I can classify `UNSUPPORTED`, `CONTRADICTION` and `UNAVAILABLE`.
- [ ] I can assemble partial answers and record abstained request items.
- [ ] I can explain why currentness and cache identity must bind source versions.
- [ ] I can explain why deterministic fakes do not prove production quality.
- [ ] I can answer the three interview questions aloud in English.

Day103 receives structured Claims, Citations, source identities, VerificationResults, coverage and mode history. It must use independent labeled Claim/Evidence data and operational measurements; Day102's own Verifier predictions are not ground truth.
