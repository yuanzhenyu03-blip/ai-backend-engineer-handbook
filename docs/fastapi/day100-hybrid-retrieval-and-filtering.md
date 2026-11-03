# Day100 — Hybrid Retrieval and Filtering

## 1. Lesson Metadata

- **Phase:** 7C — Production RAG Engineering
- **Previous:** [Day99 — Vector Database and Vector Index Design](day99-vector-database-and-vector-index-design.md)
- **Current:** Day100 — Hybrid Retrieval and Filtering
- **Next:** Day101 — Query Rewriting and Re-ranking
- **Status:** Completed at guided classroom scope
- **Evidence:** `EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`
- **Production readiness:** `MORE_EVIDENCE_NEEDED`
- **Main Artifact:** [`projects/ai-agent/`](../../projects/ai-agent/README.md)

Day100 does not claim that the saved Day99 generation is production-queryable. That generation is immutable
and `SEALED`, but it is not selected and its real Provider, ANN, latency/capacity and recovery gates remain
`NOT_RUN`. The real handoff therefore exercises a negative path with zero encoder and database calls. A
separate `DAY100_CLASSROOM_ONLY`, `production_eligible=false` fixture exercises the positive pipeline.

## 2. Learning Objectives

By the end of this lesson, you can:

1. explain why `SEALED` is not the same as selected or production-ready;
2. fail closed before query encoding when the selected retrieval bundle is missing or mismatched;
3. freeze query-encoder, lexical, filter, retrieval and fusion contracts;
4. combine BM25 and dense retrieval without adding incomparable raw scores;
5. distinguish application filter semantics from database execution capabilities;
6. authorize before retrieval and reauthorize candidates before content release;
7. implement bounded overfetch/refill, partial-result and unavailable-result semantics;
8. bind pagination and cache reuse to current authorization, query and generation identity; and
9. describe exactly what deterministic evidence proves—and what remains `NOT_RUN`.

## 3. Why This Matters

A vector database hit is not permission to disclose text. It is only a candidate proposed under one physical
and query contract. Between request admission and response release, permissions, selected generations and
document provenance can change.

Hybrid retrieval adds a second problem: BM25 and dense scores do not share one numeric scale. Adding `8.7`
BM25 points to `0.82` cosine similarity creates an arbitrary result. A production boundary needs independent
branch ranks, a deterministic fusion rule, exact candidate identity, current authorization and guarded release.

The operational risk is highest in the convenient shortcuts:

- silently querying an old or unselected generation;
- sending raw query text through an unapproved egress path;
- treating a client filter as authorization;
- dropping an unsupported filter clause;
- returning a candidate whose grant was revoked during retrieval;
- refilling `top_k` by weakening scope; or
- accepting a cursor after authorization or generation changed.

Day100 turns each shortcut into an explicit contract or fail-closed gate.

## 4. Roadmap Position

```text
Day95  immutable active parsed content
  ↓
Day96  immutable selected ChunkSet
  ↓
Day97  metadata + tenant + ACL + provenance
  ↓
Day98  homogeneous immutable EmbeddingSet
  ↓
Day99  build → validate → seal → select vector generation
  ↓
Day100 gate → scope → retrieve → fuse → recheck → release
  ↓
Day101 rewrite and rerank only authorized Day100 candidates
  ↓
Day102 ground answers and verify citations
  ↓
Day103 evaluate retrieval and answer quality
```

Day99 owns physical index correctness and selected-generation authority. Day100 consumes only a current
application-selected bundle. Day101 may improve the order of Day100 candidates, but it may not broaden their
authorization scope or recover rejected candidates.

## 5. Lesson Map

```text
                           ┌─────────────────────────────────────┐
authenticated request ───▶│ 1. selected bundle + auth hard gate │
                           └──────────────┬──────────────────────┘
                                          │ mismatch / unavailable
                                          ├──▶ DENY or UNAVAILABLE
                                          │    encoder=0, DB=0
                                          ▼
                           ┌─────────────────────────────────────┐
                           │ 2. query contract + egress policy   │
                           └──────────────┬──────────────────────┘
                                          ▼
                           ┌─────────────────────────────────────┐
                           │ 3. auth scope ∩ business filter     │
                           │    ∩ system safety exclusions       │
                           └──────────────┬──────────────────────┘
                                          ▼
                         ┌────────────────┴────────────────┐
                         ▼                                 ▼
              ┌─────────────────────┐           ┌─────────────────────┐
              │ 4A. BM25 lexical    │           │ 4B. dense Exact/ANN │
              │ rank within scope   │           │ rank within scope   │
              └──────────┬──────────┘           └──────────┬──────────┘
                         └────────────────┬────────────────┘
                                          ▼
                           ┌─────────────────────────────────────┐
                           │ 5. validate bundle + provenance     │
                           │    before fusion; dedup occurrence  │
                           └──────────────┬──────────────────────┘
                                          ▼
                           ┌─────────────────────────────────────┐
                           │ 6. weighted RRF + deterministic tie │
                           └──────────────┬──────────────────────┘
                                          ▼
                           ┌─────────────────────────────────────┐
                           │ 7. current auth/provenance recheck  │
                           │    bounded refill, never broaden    │
                           └──────────────┬──────────────────────┘
                                          ▼
                           ┌─────────────────────────────────────┐
                           │ 8. guarded release                  │
                           │ FULL / PARTIAL / EMPTY / DENIED /   │
                           │ UNAVAILABLE + content-safe audit    │
                           └─────────────────────────────────────┘
```

Memory aid:

```text
Day99: build → validate → seal → select
Day100: gate → contract → scope → retrieve → fuse → recheck → release
```

## 6. Core Mental Model

Treat retrieval as a permissioned proposal pipeline, not a database read:

```text
database hit ≠ authorized response
```

The application owns four separate truths:

1. **selection truth** — which exact retrieval bundle is current;
2. **semantic truth** — which query, lexical, filter and fusion contracts interpret the request;
3. **authorization truth** — which occurrence identities may participate now; and
4. **release truth** — which candidates still have current grant and provenance at the content exit.

The effective searchable set is intersection, never union:

```text
effective scope = current authorization-derived scope
                AND validated client/business filter
                AND system-safety exclusions
```

The client may narrow its own view. It cannot grant itself a broader view.

## 7. Main Concepts

### Concept 1: Selected retrieval bundle is the first hard gate

A bundle binds the current vector generation, EmbeddingSet, ChunkSet, lexical corpus, query encoder, filter
schema, retrieval policy and fusion policy. If the client expects generation `G43` but application authority
selects `G42`, reject `MISMATCH_GENERATION` before query encoding, filter dispatch, BM25, dense retrieval or
database access.

The saved real Day99 report has a `SEALED` generation but no selected bundle. Day100 therefore records
`NO_CURRENT_SELECTED_RETRIEVAL_BUNDLE` and zero downstream calls. It must not auto-select the newest
generation or fall back to another generation.

### Concept 2: Query encoder is a versioned semantic and egress contract

The query encoder contract freezes:

- model and immutable revision;
- query role and prefix, distinct from document role and prefix;
- tokenizer, pooling and preprocessing versions;
- dimension, numeric type, normalization and zero-vector policy;
- input/output schema; and
- egress, retention and data-handling policy revision.

Equal model names or dimensions do not prove query/document compatibility. Before an external encoder call,
the application applies egress policy and approved metadata reduction. It does not send raw query content to
an unapproved destination or silently switch encoders after an egress failure. Ordinary audit records keep a
controlled hash or redacted summary, not raw query text.

### Concept 3: BM25 is lexical rank; dense retrieval is semantic rank

The reference lexical branch uses BM25:

```text
IDF(t) = log(1 + (N - df(t) + 0.5) / (df(t) + 0.5))

score(t,d) = IDF(t) × tf(t,d)(k1 + 1)
             / (tf(t,d) + k1(1 - b + b × |d|/avgdl))
```

`k1` controls term-frequency saturation. `b` controls document-length normalization. Analyzer, tokenizer,
stop-word, stemming and field-weight revisions belong to the lexical contract because they change ranking.

The dense classroom branch exhaustively computes cosine similarity. It is an Exact/Flat correctness oracle,
not ANN proof. A production ANN branch must still pass recall, latency, capacity and selective-filter tests.

### Concept 4: Application filter semantics are separate from database execution

The application-owned AST validates field allowlists, types, operators, nesting depth and node count. It owns
the logical meaning. The database owns only the execution capability.

Supported plans include:

- `DIRECT`: one database pre-filter preserves the exact condition;
- `SPLIT_OR`: run separately authorized branches, union by occurrence identity and deduplicate; and
- `AUTH_PREFILTER_PLUS_POSTFILTER`: database pre-filters authorization scope, while the application applies a
  bounded exact post-filter to candidates before they may proceed.

Unsupported semantics are never removed or approximated. `candidate_depth` provides bounded capacity;
`bounded_refill` may fetch more candidates, but neither may broaden the authorization intersection.

### Concept 5: Candidate validation happens before fusion

Every lexical or dense hit must bind:

- tenant and authorized occurrence identity;
- selected bundle and vector/lexical generations;
- DocumentVersion, ChunkSet and Chunk occurrence;
- complete provenance; and
- branch rank and typed branch score.

A stale or cross-generation candidate is rejected before fusion. In the classroom scenario, candidate `D`
is removed before fusion. `A`, `B` and `C` may enter branch ranks and fusion; if `B` is revoked while the query
runs, final candidate validation removes `B` before release.

### Concept 6: RRF combines ranks, not raw scores

BM25 and dense raw scores have different references, ranges and distributions. The reference uses weighted
Reciprocal Rank Fusion:

```text
RRF(candidate) = Σ branch_weight / (rrf_k + branch_rank)
```

Deduplication uses occurrence identity, not content hash. Repeated text with different provenance remains
separate. Deterministic tie-break order is:

1. RRF score descending;
2. best branch rank ascending; then
3. occurrence ID ascending.

### Concept 7: Authorization is checked before retrieval and again before release

Pre-retrieval authorization prevents unauthorized candidates and side channels from entering the query. It
does not guarantee that the grant remains current. The guarded releaser therefore rereads the grant, policy
revision, authorization epoch, selected generation and provenance immediately before protected text leaves the
system.

If selection changes during retrieval, reject the response; do not silently use the old generation. If one
candidate is revoked, remove it and perform bounded refill if policy permits. If a later page carries stale
authorization or generation identity, fail closed and require a new first-page request.

### Concept 8: Result completeness is explicit

- `FULL`: every required branch completed and the policy's bounded work finished.
- `PARTIAL`: an explicitly allowed branch degradation or bounded budget prevented a complete result; the
  response names completed and missing branches and the reason.
- `EMPTY`: the complete authorized search ran and found no releasable candidates.
- `DENIED`: authorization or request admission failed.
- `UNAVAILABLE`: required authority or all retrieval branches were unavailable.

A lexical-only response may be `PARTIAL` only when the selected policy explicitly permits that degradation.
It must be labeled; it cannot masquerade as a full hybrid result.

### Concept 9: Top-k, overfetch and refill stay bounded

Candidate depth exceeds final `top_k` because deduplication, post-filtering and final reauthorization can remove
candidates. Refill is permitted only within fixed round, candidate and deadline budgets. If the corpus is
exhausted, fewer than `top_k` may still be a complete result. If the budget is exhausted while more eligible
work may remain, report `PARTIAL`.

### Concept 10: Cursor and cache are authority-bound

A signed, canonically encoded cursor binds tenant, principal, authorization scope/revision, selected bundle,
query and filter hashes, retrieval/fusion policies, branch offsets and expiry. Any relevant change invalidates
the cursor.

The cache stores derived candidate identities and ranks, never protected text. Every hit still passes current
authorization and provenance recheck. Non-canonical or tampered cursor encoding is rejected even if it decodes
to the same bytes.

### Concept 11: Hard gates precede weighted criteria

Provider or database candidates must first pass non-negotiable gates: compatible contracts, current selection,
authorization/filter isolation, reproducible identity, recovery/backup expectations, and required ANN/latency
evidence. `FAIL` means the candidate cannot be enabled. `NOT_RUN` means evidence is absent and must be run
later. Only survivors may receive weighted scores.

A low weighted score after every required hard gate passes may still meet the minimum production threshold.
A high score cannot compensate for a failed or unrun hard gate.

## 8. Common Misconceptions

### “`SEALED` means the index can serve traffic.”

No. `SEALED` means the generation is immutable after the gates that actually ran. Selection and production
hard gates are separate facts.

### “The database tenant filter is authorization.”

No. Database pre-filtering executes part of an application-owned scope. Current grant evaluation remains the
authority, and final release rechecks it.

### “Client filter and authorization scope should be unioned.”

No. The correct operation is intersection. Union would let a client broaden permission.

### “Add BM25 and cosine scores, then sort.”

No. Their raw values have incompatible scales. Fuse ranks with a frozen rule such as RRF or calibrate under a
separately validated contract.

### “If an `OR` is unsupported, drop the difficult side.”

No. Use an exact split plan with independently authorized branches or fail closed.

### “A pre-query authorization check is enough.”

No. Authorization and selected provenance can change while retrieval runs. Recheck at the content exit.

### “Always return exactly `top_k`.”

No. Authorization and bounded work are stronger than cardinality. Fewer correct results are safer than
unauthorized or unbounded refill.

### “Green synthetic tests prove production retrieval.”

No. They prove application control logic, deterministic ranking and failure semantics. They do not prove a
real Provider, ANN recall, production latency/capacity, backup/restore or failover.

## 9. Engineering Trade-offs

| Decision | Benefit | Cost / residual risk |
|---|---|---|
| Exact/Flat reference first | deterministic correctness oracle | not production ANN performance evidence |
| RRF over raw-score addition | provider-independent rank fusion | discards magnitude; needs policy tuning |
| authorization pre-filter + final recheck | reduces leakage and closes TOCTOU | more current-state reads |
| occurrence identity dedup | preserves repeated provenance | larger identity and manifest contracts |
| split unsupported `OR` | exact logical semantics | more database calls and union work |
| bounded application post-filter | supports limited provider capability | may return partial under budget |
| candidate-only cache | avoids stale protected text | reauthorization work remains on hits |
| fail closed on generation change | reproducible authority | user restarts pagination |

## 10. Hands-on Exercises

### Exercise 1: Prove the real Day99 negative handoff

Load the saved Day99 report. Assert `generation_state == SEALED`, `selected_bundle == false`, and
`production_readiness == MORE_EVIDENCE_NEEDED`. Submit a Day100 request and assert query encoder, filter branch,
BM25, dense and database call counts all remain zero.

### Exercise 2: Compare lexical and dense ranks

Run the dependency-free BM25 and Exact cosine branches over the synthetic corpus. Inspect each branch's rank
order. Do not compare their raw score magnitude.

### Exercise 3: Revoke one fused candidate

Allow `A`, `B`, `C`; reject stale `D` before fusion; revoke `B` before release. Verify the result contains only
currently authorized candidates and bounded refill does not broaden scope.

### Exercise 4: Exercise a split `OR`

Create an application filter whose exact semantics require two supported branches. Apply current authorization
to each branch separately, union by occurrence identity and use the deterministic tie-break.

### Exercise 5: Force lexical-only degradation

Make dense retrieval unavailable under a policy that explicitly permits lexical-only degradation. Verify
`PARTIAL`, `completed_branches=[LEXICAL]`, `missing_branches=[DENSE]` and a controlled reason. Then disable the
degradation policy and verify `UNAVAILABLE`.

### Exercise 6: Invalidate a second-page cursor

Create page one, then change the selected generation or authorization revision. Verify the second-page request
fails closed and cannot resume against the previous cursor.

### Local commands

```bash
cd projects/ai-agent
PYTHONPATH=src:. python3.12 -m unittest discover -s tests -p 'test_day100_*.py' -q
PYTHONPATH=src:. python3.12 evals/run_day100_seed_eval.py
PYTHONPATH=src:. python3.12 evals/run_day100_evidence_replay.py
PYTHONPATH=src:. python3.12 examples/day100_hybrid_retrieval_filtering.py
```

## 11. Relevant Framework Connections

- **PostgreSQL full-text search:** can provide lexical ranking and structured pre-filtering, but the
  application still owns the lexical contract and authorization semantics.
- **pgvector:** can provide Exact or ANN dense retrieval inside PostgreSQL; metric, operator, score direction,
  index and filter plans remain versioned contracts.
- **Qdrant:** offers dense/sparse fusion and payload filters; current authorization and application-selected
  bundle authority remain outside the database.
- **Pinecone:** offers hybrid search patterns and metadata filtering; namespace or filter syntax is not a
  substitute for current grant evaluation.
- **FastAPI:** the request boundary should distinguish denied, invalid, unavailable, partial, empty and full
  outcomes without exposing protected reason detail.

Current official research retains all three storage approaches. PostgreSQL full-text search plus pgvector is a
provisional classroom candidate, not a selected production winner. Required real hard gates remain `NOT_RUN`.

## 12. AI Backend Connections

Day100 connects security, retrieval and reliability:

- Day52 tenant/authorization boundaries become current query scope.
- Day56 timeout/backpressure thinking becomes branch deadlines and bounded refill.
- Day73/Day98 immutable contracts become query and lexical compatibility fingerprints.
- Day83 approval/authority thinking becomes selected-bundle admission.
- Day95–Day99 provenance becomes exact occurrence identity.
- Day103 will measure whether the authorized retrieval is relevant; Day100 only proves control-flow
  correctness with its current evidence.

The application remains the source of authority even when it delegates computation to an encoder or database.

## 13. English Interview

### Beginner: Why is a sealed generation not automatically production-ready?

**Student's verbatim answer:**

> because it must need to through latency test\ANN test\drill test\back up test.it must need through hard gate

**Technical assessment:** Correct core idea: immutability is not production qualification, and required hard
gates must pass. Add real Provider evidence, capacity, restore/recovery and authoritative selected-pointer
publication.

**Corrected expression:** A sealed generation is immutable, but it is not automatically production-ready. It
must still pass the required real-provider, ANN recall, latency, capacity, backup-and-restore and recovery hard
gates. Only then may the application authority atomically select it for production retrieval.

### Intermediate: Why use RRF instead of adding raw BM25 and dense scores?

**Student's verbatim answer:**

> because system need  separate branch the rank of raw scores.raw scores is not a same reference criteria

**Technical assessment:** Correct. The raw scores use different reference scales. Name BM25 and cosine and
state that RRF combines ranks under one deterministic policy.

**Corrected expression:** BM25 and dense similarity scores use different scales and are not directly
comparable. The system therefore ranks each branch independently and uses Reciprocal Rank Fusion to combine
their ranks under a deterministic policy.

### Senior: Why authorize before retrieval and reauthorize before release?

**Student's verbatim answer:**

> because the authorization could be revoke before retrieval,and final authorization and provenance recheck make sure still current state don't change

**Technical assessment:** Correct boundary. Tighten the timing: a grant may be revoked during retrieval, and
the final check verifies the current grant, revisions, selected generation and provenance immediately before
release.

**Corrected expression:** Pre-retrieval authorization prevents unauthorized candidates and side channels from
entering the query. Because a grant or selected provenance may change while retrieval is running, the guarded
releaser rechecks current authorization and provenance immediately before protected content is returned.

### Follow-up: What if a bundle generation mismatch is discovered?

The learner correctly answered that the request is rejected at the selected retrieval bundle gate and that
query encoder, filter splitting, BM25, dense and database calls must all remain zero. The learner initially
answered “不知道” when asked to distinguish the real negative fixture from the synthetic positive fixture,
then correctly synthesized:

> 真实 Day99 negative fixture证明generation被sealed，Day100 synthetic positive fixture证明状态机、协议、参数等可以正常执行。因为不能证明：
>
> - Day99 真实 generation 已经 selected；
> - 真实 Provider 或数据库可用；
> - ANN recall、生产延迟和容量通过；
> - backup、restore 或 failover 通过；
> - production readiness。所以保持`MORE_EVIDENCE_NEEDED`

## 14. Mental Model Summary

1. `SEALED` proves immutability, not selection or readiness.
2. Bundle and authorization hard gates run before encoder or database work.
3. Query and document encoding roles are separate versioned contracts.
4. Effective scope is authorization **intersection** client filter **intersection** system exclusions.
5. BM25 ranks lexical matches; dense retrieval ranks vector similarity.
6. RRF fuses branch ranks; occurrence identity drives deduplication.
7. Invalid or stale candidates are removed before fusion; current authorization is checked again before
   release.
8. Top-k refill, branch degradation, cursors and caches are bounded and authority-bound.
9. Synthetic control-flow evidence cannot convert real `NOT_RUN` gates into `PASS`.

## 15. Today's Takeaway

Hybrid retrieval is not “run two searches and add the scores.” It is a governed sequence in which the
application first proves that the exact retrieval bundle and authorization scope are current, then runs
versioned lexical and dense branches, validates candidate identity, fuses ranks, rechecks current authority and
only then releases protected content.

The strongest safety rule is simple:

```text
never trade authorization, provenance or bounded work for a fuller top_k
```

## 16. Before Next Lesson Checklist

- [x] Explain `SEALED` versus selected versus production-ready.
- [x] Fail closed on missing/mismatched selected bundle with zero downstream calls.
- [x] Freeze query encoder, lexical, filter, retrieval and fusion contracts.
- [x] Compute BM25 and Exact cosine branch ranks.
- [x] Preserve application-owned filter semantics across direct, split and post-filter plans.
- [x] Validate candidate identity before RRF.
- [x] Reauthorize and recheck provenance before guarded release.
- [x] Distinguish full, partial, empty, denied and unavailable outcomes.
- [x] Bind cursor/cache to current authorization and bundle identity.
- [x] Preserve the real Day99 negative fixture and isolated synthetic positive fixture.
- [ ] Run a real query encoder and PostgreSQL/pgvector/FTS, Qdrant or Pinecone integration.
- [ ] Run real ANN recall, selective-filter, latency/capacity and backup/restore/failover gates.
- [ ] Begin Day101 rewriting and reranking only over current authorized Day100 candidates.
