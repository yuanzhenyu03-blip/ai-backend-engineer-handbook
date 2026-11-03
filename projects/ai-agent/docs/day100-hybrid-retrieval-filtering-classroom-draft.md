# Day100 classroom draft — Authorized hybrid retrieval and filtering

Status: isolated classroom worktree; not committed, pushed or production-ready.

## Mental model

Day99 builds, validates, seals and eventually selects an immutable vector index
generation. Day100 consumes only an application-selected retrieval bundle and
answers a different question: how can a currently authorized principal search
the aligned lexical and dense corpus without allowing a database result to
become an authorization decision?

The short memory aid is:

```text
Day99: build → validate → seal → select
Day100: gate → contract → scope → retrieve → fuse → recheck → release
```

The saved Day99 classroom generation is `SEALED`, but its real Provider, ANN,
latency/capacity and recovery gates are `NOT_RUN`; it has no selected pointer.
The real handoff therefore exercises only the negative Day100 path and produces
`NO_CURRENT_SELECTED_RETRIEVAL_BUNDLE` with zero Provider and database calls.

Positive behavior uses a separate `DAY100_CLASSROOM_ONLY` fixture. Its selected
pointer exists only inside an isolated in-process authority, carries
`production_eligible=false`, and cannot alter Day99 evidence.

## End-to-end boundary

```text
authenticated request
→ application-selected retrieval bundle
→ query contract and egress policy
→ current authorization-derived scope
→ application-owned business-filter plan
→ BM25 lexical branch + Exact/Flat dense branch
→ version-bound candidate validation
→ Reciprocal Rank Fusion
→ current authorization/provenance recheck
→ guarded content release
→ bounded FULL/PARTIAL/EMPTY response
```

No selected bundle, authorization failure, query-contract mismatch or invalid
filter may degrade into a broader query.

## Contracts

`rag_retrieval_contracts.py` owns:

- `QueryEncoderContract`, including immutable model revision, query/document
  roles and prefixes, dimensions, normalization and egress-policy revision;
- `LexicalRetrievalContract`, including corpus generation, analyzer/tokenizer
  versions, `k1`, `b`, stop words, stemming and field weights;
- selected bundle identity across vector generation, EmbeddingSet, ChunkSet,
  lexical corpus, filter schema, retrieval policy and fusion policy;
- occurrence-based candidates, branch ranks, fused candidates and content-safe
  response/audit types.

Equal model names or dimensions do not prove query/document compatibility.
Input role, prefix, tokenizer, pooling and normalization belong to the semantic
contract.

## Lexical and dense references

The dependency-free BM25 implementation uses:

```text
IDF(t) = log(1 + (N - df(t) + 0.5) / (df(t) + 0.5))

score(t,d) = IDF(t) × tf(t,d)(k1 + 1)
             / (tf(t,d) + k1(1 - b + b × |d|/avgdl))
```

`k1` controls term-frequency saturation. `b` controls document-length
normalization. Analyzer and tokenizer versions are part of the contract because
changing tokenization changes the index and ranking.

The dense reference exhaustively computes cosine similarity. It is an
Exact/Flat correctness oracle, not ANN evidence. The adapter exposes
`HIGHER_IS_BETTER`; callers never reinterpret Provider-specific distance values.

## Filters and authorization

The filter AST is application-owned. It validates allowed fields, types,
operators, nesting depth and node count before a database call.

```text
effective scope = current authorization-derived scope
                  AND validated business filter
                  AND system-safety exclusions
```

Provider capabilities determine only how the business condition is executed:
direct pre-filter, explicitly split `OR` queries, or authorization pre-filter
plus bounded application post-filter. Unsupported semantics are never silently
dropped. Authorization is always enforced independently and checked again at
the content exit.

## Fusion and identity

BM25 and dense raw scores have different scales and meanings. The reference
therefore uses rank-only RRF:

```text
RRF(candidate) = Σ branch_weight / (rrf_k + branch_rank)
```

The deterministic order is RRF score descending, best branch rank ascending,
then occurrence ID ascending. Deduplication uses occurrence identity, not
content hash, so repeated text with different provenance remains distinct.

Every candidate must bind the selected bundle, vector generation, lexical
generation, tenant, ChunkSet, occurrence and provenance before fusion.

## Final release, top-k and degradation

The guarded releaser reads current authorization and provenance immediately
before protected text is returned. Candidates revoked or made stale during the
query are removed.

Candidate depth exceeds final `top_k` to allow for deduplication, post-filtering
and final reauthorization. Refill is bounded by rounds and candidate budget and
never relaxes authorization. Exhausted corpus may return fewer than `top_k` as
a complete result; an exhausted budget before corpus exhaustion is `PARTIAL`.

One branch may degrade only if the selected policy explicitly allows it. The
response identifies completed and missing branches and the degradation reason.
If neither branch completes, the result is `UNAVAILABLE`, not partial or empty.

## Cursor and cache

Cursors are signed and canonically encoded. They bind tenant/principal,
authorization scope, selected bundle, generation, query/filter hashes,
retrieval/fusion policies, branch offsets and expiry. Bundle, authorization,
query, policy or filter changes invalidate the cursor.

The cache stores derived fused candidates, never protected text. Its key binds
the same current identities, and every cache hit passes through current
authorization/provenance recheck before release.

## Evidence

Executed classroom evidence:

- deterministic fake query encoder;
- dependency-free BM25;
- Exact/Flat cosine reference;
- application-owned filter oracle;
- deterministic RRF and tie-break;
- synthetic current authorization and guarded release;
- signed cursor and derived candidate cache;
- controlled pipeline-correctness report and exact evidence replay.

Not executed:

- real query Provider;
- PostgreSQL/pgvector/FTS, Qdrant or Pinecone calls;
- real ANN recall under selective filters;
- production latency, throughput and capacity;
- backup/restore, failover and RTO/RPO;
- production relevance or answer-quality evaluation.

The only honest readiness result is `MORE_EVIDENCE_NEEDED`.

## Local verification

From the repository root:

```text
PYTHONPATH=projects/ai-agent/src:projects/ai-agent python \
  -m unittest discover -s projects/ai-agent/tests -p 'test_day100_*.py' -q

PYTHONPATH=projects/ai-agent/src:projects/ai-agent python \
  projects/ai-agent/evals/run_day100_seed_eval.py

PYTHONPATH=projects/ai-agent/src:projects/ai-agent python \
  projects/ai-agent/evals/run_day100_evidence_replay.py
```

## Scope boundary

Day100 does not implement query rewriting, multi-query expansion, HyDE,
reranking, answer generation, grounding or citations. Those belong to Day101
and Day102. Broad retrieval- and answer-quality evaluation belongs to Day103.
