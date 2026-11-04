# Day101 — Query Rewriting and Re-ranking

## 1. Lesson Metadata

- **Status:** Completed at guided classroom scope
- **Template:** `LESSON_TEMPLATE_v2`
- **Phase:** 7C — Production RAG Engineering
- **Difficulty:** Advanced
- **Estimated study time:** 5–7 hours
- **Prerequisites:** Day95–Day100, especially current authorization, provenance, immutable generations and authorized hybrid retrieval
- **Previous lesson:** [Day100 — Hybrid Retrieval and Filtering](day100-hybrid-retrieval-and-filtering.md)
- **Next lesson:** Day102 — Grounding, Citations and Source Verification
- **Main engineering artifact:** application-owned bounded rewrite, multi-query fusion and authorized-candidate reranking subsystem
- **Evidence:** `EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`; real rewrite/reranker models and production are `NOT_RUN`
- **Production readiness:** `MORE_EVIDENCE_NEEDED`

## 2. Learning Objectives

By the end of Day101, the learner can:

- explain why rewrite authority is not authorization authority;
- preserve an immutable original query and stable query-variant identities;
- execute every approved variant through the same Day100 boundary;
- deduplicate by occurrence identity while preserving per-variant rank evidence;
- distinguish Day100 branch fusion from Day101 multi-query fusion;
- construct versioned reranker input windows with explicit candidate correlation;
- reject missing, duplicate, unknown, stale or mismatched reranker output;
- enforce that a reranker may reorder or remove, never add or authorize;
- recheck current authorization and provenance before and after reranking;
- classify original-only and unreranked fallbacks without pretending they are full success;
- bind cache and cursor identity to rewrite, pool and reranker state;
- separate pipeline-correctness evidence from Day103 quality evidence;
- defend these boundaries in an English system-design interview.

## 3. Why This Matters

A user may ask for the right information using words that do not match the corpus. Query rewriting can improve coverage, and a cross-encoder can compare a small candidate set more carefully than first-stage retrieval. Both features also create new security and correctness risks:

- a rewrite can drift into a different business intent;
- a variant can bypass tenant filters if it calls a raw index directly;
- an external reranker can receive protected query or document text without approval;
- array-position correlation can attach a score to the wrong occurrence;
- a Provider can return duplicate, unknown or stale candidates;
- a high score can tempt a team to retain content whose authorization was revoked;
- a synthetic fixture can be mistaken for production-quality evidence.

Day101 is therefore not “add an LLM and sort by score.” It is an application-owned authority, identity, correlation, budget, failure and evidence boundary.

## 4. Roadmap Position

```text
Day95 current SourceArtifact / ParsedArtifact
  → Day96 immutable Chunk occurrences
  → Day97 tenant / ACL / provenance
  → Day98 immutable EmbeddingSet
  → Day99 immutable VectorIndexGeneration
  → Day100 authorized first-stage retrieval
  → Day101 scope-preserving rewrite + authorized-candidate reranking
  → Day102 grounded context / claims / citations
  → Day103 retrieval and answer quality evaluation
```

Day100 supplies the only eligible candidates. Day101 may improve expression and order but cannot broaden authority. Day102 converts current candidates into grounded context and citations. Day103 measures whether the chosen rewrite and reranker actually improve quality.

## 5. Lesson Map

```text
Day100 handoff eligibility
→ frozen original query
→ rewrite egress and bounded candidates
→ stable query variants
→ Day100 retrieval per variant
→ occurrence union + multi-query RRF
→ currentness recheck
→ versioned reranker inputs
→ Adapter + exact validation
→ reorder/subselect only
→ final currentness recheck
→ deterministic Day102 handoff
```

## 6. Core Mental Model

```text
Query rewriting may change retrieval expression.
It may not change authorization.

A reranker may reorder or remove authorized candidates.
It may not add, revive or authorize candidates.
```

The durable set invariant is:

```text
final_reranked_occurrence_ids
⊆ validated_current_authorized_day100_occurrence_ids
```

Metaphor: Day100 is the gate and preliminary round. Query variants are several librarians using different phrases inside the same authorized room. The reranker is a final-round judge who may reorder admitted contestants but cannot bring in an outsider.

## 7. Main Concepts

### Concept 1: Day100 handoff is a hard gate

#### Tech Lead Question

Can a `production_eligible=false` Day100 classroom fixture feed a real hosted reranker and become a production response?

#### Student Thinking

The first answer was simply “不能.” After the lesson was restructured around one request and one gate at a time, the learner identified two separate blockers and their order.

#### Student Answer

> “不能执行，最早应该在验证selected bundle gate进行停止，独立gate是content egress authorization gate”

#### Tech Lead Review

Correct. The earliest failure is the absent real selected Day100 production bundle. That stops before rewrite, reranker, query Provider or database side effects. External query/candidate egress is a later independent gate, not a substitute for the first.

#### Engineering Thinking

Evidence does not upgrade downstream. A real reranker call over synthetic candidates proves that call only; it does not create real database, ANN, authorization or Day100 bundle evidence.

#### Production Example

The executable negative fixture returns `NO_CURRENT_DAY100_BUNDLE` with zero rewrite and reranker Provider calls.

#### Framework Connection

A FastAPI handler should call this application gate before scheduling Provider work. HTTP acceptance cannot manufacture missing retrieval authority.

#### Exercise

Verify `test_day101_handoff_eligibility.py` and explain why the query encoder and database call counters remain zero.

### Concept 2: Original query and bounded variants

#### Tech Lead Question

What is rewrite output, and why does every output go through Day100 again?

#### Student Thinking

The learner initially described “rewrite 的检索结果” as if retrieval happened first. The correction separated query expressions from returned occurrences.

#### Student Answer

> “rewrite输出的是问题的变体，可以对原始查询的语义和意图进行补充。每个输出都需要经过相同的门禁和检索规则。”

#### Tech Lead Review

The output is a candidate query expression, not a retrieval result. “补充” is safe only when a versioned application contract proves that the new expression remains inside the original scope. Variant zero always preserves the original query.

#### Engineering Thinking

The contract binds provider/prompt/tokenizer/normalization/locale/budgets/egress. It rejects empty, long, duplicate, wrong-locale, unsupported-source and semantic-drift candidates. One bounded round prevents recursive cost and authority expansion.

#### Production Example

“Reset MFA after losing a phone” may be paraphrased. “Bypass the company MFA policy” is semantic drift. Decomposition into revoke/register steps is valid only if a controlled domain contract supports that meaning.

#### Framework Connection

Provider SDK output is translated into `RewriteCandidate`; SDK-private types do not enter application core.

#### Exercise

Add a duplicate normalized candidate and confirm it is rejected without removing variant zero.

### Concept 3: Multi-query union and two fusion layers

#### Tech Lead Question

If candidate B appears in three query results, should it enter the reranker three times or lose two branch observations?

#### Student Answer

> “使用occurrence_id进行去重同时保留各个候选在各分支中的排名以避免重复的occurrence_id消耗候选额度并占据位置”

#### Tech Lead Review

Correct. B enters the pool once but retains all variant-rank evidence. Text equality is not identity: two occurrences with identical content may have different document versions or provenance.

#### Engineering Thinking

Day100 fuses lexical and dense branches for one query. Day101 fuses the already-authorized Day100 ranks from multiple query variants. Raw scores are not added across queries; the reference uses rank-based RRF and stable occurrence-ID tie-break.

#### Production Example

```text
Q0 → [A, B, C]
Q1 → [B, D, A]
Q2 → [E, B, F]

pool → [A, B, C, D, E, F]
B keeps three rank observations
```

#### Framework Connection

The planner calls `AuthorizedHybridRetriever.retrieve()` for every variant. It never calls lexical/dense adapters directly.

#### Exercise

Explain why a variant count, per-variant depth, total observation budget and unique-pool budget are all necessary.

### Concept 4: Reranker input, Adapter and Validator

#### Tech Lead Question

Can a hosted Provider response be correlated by response-array position?

#### Student Answer

The learner correctly mapped a response through explicit input indexes and identified duplicate/unknown candidates as fail-closed violations.

> “应该由adapter映射发现不匹配输入集合。静默删除无法确定只是一个出问题，还是整体错位……”

#### Tech Lead Review

Refinement: the Adapter translates a documented Provider index into the frozen application candidate ID. The Validator checks bounds, uniqueness, cardinality and correlation. An invalid complete response is discarded; an explicit unreranked fallback may use the pre-rerank fusion order.

#### Engineering Thinking

The input identity includes model/tokenizer revision, candidate-pool digest, window policy and actual window digest. A reranker score is not automatically a probability. Stable tie-break is score, prior fusion rank, then occurrence ID.

#### Production Example

```text
request: 0→A, 1→B, 2→C
response: [{index:2}, {index:0}]
mapping:  [C, A]
```

#### Framework Connection

Cohere- or Jina-style input indexes remain transport facts. Application candidate identity remains authoritative.

#### Exercise

Run duplicate, unknown, incomplete and attempt-mismatch validation tests.

### Concept 5: Final authorization, provenance and explicit fallback

#### Tech Lead Question

Can reranker first place B remain in the response after B is revoked?

#### Student Answer

> “不可以，至少应该移除B，因为授权撤销的hard gate要高于output policy”

#### Tech Lead Review

Correct. `top_k`, relevance and completeness do not override a release gate. The same applies to current provenance. Internal retrieval permission is also not external processing permission.

#### Engineering Thinking

Day101 rechecks currentness before protected candidate egress and after reranking. Rewrite fallback and reranker fallback are separate dimensions. `ORIGINAL_ONLY_FALLBACK` and `UNRERANKED_FALLBACK` must not be recorded as full success.

#### Production Example

An invalid reranker output is discarded in full. A valid output whose B is later revoked retains the valid relative order of the remaining candidates; this is not an unreranked fallback.

#### Framework Connection

Authorization and protected-data egress policies remain application services outside the model and Provider adapter.

#### Exercise

Inject revocation and provenance change during the fake reranker call and confirm B never reaches the final handoff.

### Concept 6: Cursor, cache and evidence boundaries

#### Tech Lead Question

Can a cursor continue after bundle, authorization, query, rewrite set or reranker revision changes?

#### Student Answer

> “不能，检查rewrite set identity以及reranker model version的变化”

#### Tech Lead Review

Correct. A cursor is a continuation of one frozen ranked result, not a generic page number. Cache hits also require current release checks.

#### Engineering Thinking

Deterministic fakes prove application behavior, not relevance quality. Day103 owns labeled baseline comparisons and Recall/MRR/NDCG evaluation; production also needs real latency, capacity, cost and protected-data evidence.

#### Production Example

A cursor created under G1 is rejected after G2 selection because the old offsets and ranks no longer describe the same candidate universe.

#### Exercise

Change one cache-key field at a time and show that the old entry or cursor cannot be reused.

## 8. Common Misconceptions

### “Rewrite results” are documents

❌ A rewrite produces documents and then Day100 processes them again.
✅ A rewrite produces query expressions; each expression independently calls Day100 online retrieval.

### One final authorization check is enough

❌ Variants may query raw indexes, then authorization can be applied after fusion.
✅ Unapproved content may already have been read or externally processed. Every variant uses the full Day100 boundary.

### Duplicate occurrence means discard all duplicate evidence

❌ Keep B once and forget which variants found it.
✅ Keep B once by occurrence ID and retain all rank observations.

### A high reranker score is a probability or permission

❌ Score `0.94` means 94% correct and may bypass release checks.
✅ Score semantics are model/contract specific and never grant authority.

### Adapter and Validator are the same

❌ The Adapter decides whether Provider output is safe.
✅ The Adapter translates; the Validator decides contract validity.

### `FULL` means exactly top-k and no release rejection

❌ Any candidate removed during guarded release forces Day100 `PARTIAL`.
✅ Current Day100 `FULL` means expected branches completed without a declared system degradation; it does not guarantee exact top-k. This implementation detail was corrected during class.

## 9. Engineering Trade-offs

### Rule-based rewrite vs LLM rewrite

- Rule-based normalization is deterministic, cheap and easier to validate, but has limited coverage.
- LLM rewrite can paraphrase/decompose, but adds semantic drift, egress, latency and cost risks.
- Day101 keeps an application contract around either approach.

### Local vs hosted reranker

- Local/open-weight models reduce external egress but add model hosting, patching and capacity responsibility.
- Hosted rerankers simplify operation but add privacy, retention, region, rate-limit and vendor-contract gates.
- No production choice is made with current evidence.

### Pointwise vs pairwise vs listwise

- Pointwise is simple to batch, correlate and test; it may miss global list interactions.
- Pairwise can model direct preferences but grows approximately with `n²` and can create cycles.
- Listwise sees the list but adds context limits, position bias and batch-merge complexity.
- The deterministic pointwise fake is a correctness reference, not a quality claim.

### Reject vs fallback

- Fail closed is clearest for required behavior.
- Explicit original-only or unreranked fallback can preserve availability but may reduce quality.
- The product contract must choose; telemetry and response state must reveal the path.

## 10. Hands-on Exercises

### Exercise 1: Trace one variant

**Question:** Which fields may differ between the original and rewritten Day100 requests?
**Think First:** Query expression is not authorization.
**Starter Artifact:** `rag_multi_query_retrieval.py`
**Expected Output:** only query/operation/request identity differs; tenant/principal/action/purpose/filter/bundle authority stays fixed.
**Explanation:** a raw lexical/dense call would bypass the boundary.
**Follow-up:** explain why a final filter cannot repair prior protected-data exposure.

### Exercise 2: Validate a malformed ranking

**Question:** Input is `[A,B,C,D]`; Provider returns indexes `[2,0,2]`.
**Think First:** Map first, validate second.
**Starter Artifact:** `rag_reranking_validator.py`
**Expected Output:** duplicate C invalidates the entire response.
**Explanation:** silent deletion cannot prove that remaining correlations are correct.
**Follow-up:** compare full-permutation, top-n and arbitrary-subset cardinality rules.

### Exercise 3: Revoke during reranking

**Question:** B is first-ranked, then revoked before final release.
**Starter Artifact:** `test_day101_reranking_authorization.py`
**Expected Output:** B is absent; remaining order is deterministic; the release rejection is recorded.
**Follow-up:** change provenance instead of authorization.

### Exercise 4: Defend the evidence claim

**Question:** What do 56 focused tests and a 10-case seed prove?
**Expected Output:** bounded application correctness with deterministic fakes, not real rewrite/reranker quality or production operations.

## 11. Relevant Framework Connections

- **FastAPI:** authenticates the request and invokes the application orchestrator; it does not own rewrite or ranking authority.
- **Vector database / FTS:** remains behind Day100 filters and selected-bundle contracts. Day101 never queries a raw index directly.
- **Provider SDKs:** remain inside rewrite/reranker adapters; application types own candidate identity and validation.
- **Redis or database cache:** may store only identities bound to current authority/rewrite/pool/reranker state; a cache hit does not skip current release checks.
- **Observability:** records safe digests, modes, counts and reasons, never raw protected query, candidate text, vectors or secrets.

## 12. AI Backend Connections

This boundary is the center of production RAG query-time control:

```text
recall-oriented first stage
→ bounded multi-query coverage
→ precision-oriented reranking
→ current authorized evidence
→ Day102 grounding
```

It also defines the correct evaluation split. Day101 tests safety and deterministic behavior. Day103 compares original-only, multi-query and reranked baselines using labeled data and operational measurements.

## 13. English Interview

### Key Vocabulary

`scope-preserving rewrite`, `authorization-first retrieval`, `candidate pool`, `explicit correlation`, `input window`, `subset invariant`, `unreranked fallback`, `currentness recheck`.

### Useful Expressions

- “A rewrite may change the query expression, but it must never broaden authorization.”
- “A cursor continues one frozen retrieval result; it is not a generic page number.”
- “Deterministic fake tests prove control-flow correctness, not real-model quality.”

### Beginner Question

**Why must every rewritten query use the same Day100 pipeline?**

Every rewrite may retrieve different candidates. Reusing the same Day100 boundary ensures the tenant, principal, purpose, filters, selected bundle and authorization rules do not change.

### Intermediate Question

**Why can an old cursor not resume after bundle or authorization changes?**

A cursor is bound to one frozen candidate universe and ranking. A changed bundle or authorization changes that universe, so the old offsets may skip, duplicate or expose candidates and must be rejected.

### Senior Question

**Why do deterministic fake tests not prove production reranker quality?**

They prove control-flow, contract validation and safety invariants. Production selection still requires baseline comparisons, labeled quality metrics and real latency, capacity, cost, error-rate and protected-data evidence.

### Common Weak Answer

“The model sorts better, and tests pass.”

### Strong Answer

“I preserve the original query, validate bounded variants, execute each through the same authorization-first Day100 boundary, fuse occurrence ranks, correlate reranker outputs explicitly, enforce an output-subset invariant, and recheck authorization/provenance before release. I keep correctness evidence separate from model-quality and production evidence.”

## 14. Mental Model Summary

```text
Original query       = what the user actually asked
Rewrite candidate    = untrusted proposed retrieval expression
Query variant        = validated, bounded expression; never new authority
Day100               = authorization gate + first-stage retrieval
Day101 fusion        = occurrence union + cross-variant rank evidence
Candidate pool       = frozen authorized reranker input set
Reranker             = reorder/subselect only
Adapter               = Provider translation
Validator             = exact correlation and contract decision
Final recheck         = current authorization + provenance release gate
Day102 handoff        = ordered current candidates, not an answer or citation
```

## 15. Today's Takeaway

- **Mental model:** rewrite expression, never authority; rerank candidates, never authorize.
- **Production risk:** protected content can leak before a late filter, so authorization and egress gates precede side effects.
- **Trade-off:** more variants and stronger rerankers can improve coverage/precision but multiply drift, latency, cost and data-processing risk.
- **Framework connection:** application-owned contracts surround every model or SDK.
- **AI Backend connection:** Day101 produces current ordered evidence for Day102, not a generated answer.
- **Interview answer:** explain the subset invariant and evidence boundary before discussing model choice.

## 16. Before Next Lesson Checklist

- [ ] I can explain why every variant reuses Day100.
- [ ] I can distinguish Day100 branch fusion from Day101 multi-query fusion.
- [ ] I can explain why occurrence ID, not text, is the deduplication key.
- [ ] I can separate Adapter mapping from Validator decisions.
- [ ] I can reject duplicate, unknown, missing or mismatched reranker outputs.
- [ ] I can explain why input-window policy is part of cache identity.
- [ ] I can distinguish retrieval authorization from external candidate egress.
- [ ] I can explain original-only and unreranked fallback states.
- [ ] I can explain why final authorization/provenance checks override score/top-k.
- [ ] I can explain why a cursor is invalid after identity changes.
- [ ] I can state exactly what deterministic fake evidence does and does not prove.
- [ ] I can answer the three Day101 interview questions aloud in English.
- [ ] I understand that Day102, not Day101, owns grounded answers and citations.
